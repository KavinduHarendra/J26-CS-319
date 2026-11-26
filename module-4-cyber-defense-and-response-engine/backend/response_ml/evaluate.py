"""Score a locally trained prototype on the frozen synthetic test partition."""

import argparse
import csv
import json
from collections import Counter
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import joblib
import numpy as np

from response_ml.features import FEATURE_COLUMNS
from response_ml.preprocessing import feature_importance, feature_matrix
from response_ml.prototype_data import label_summary, load_study, sha256
from response_ml.prototype_metrics import AGGREGATES, classification_metrics, confidence_summary, critical_errors, latency_summary
from response_ml.prototype_report import render_report, save_figures
from response_ml.prototype_safety import POLICY_VERSION, screen_recommendation
from response_ml.rubric import RESPONSE_CLASSES, RUBRIC_VERSION
from response_ml.train import EXPERIMENT, METADATA_FILENAME, MODEL_FILENAME

METHOD_NAMES = {
    "classification_only_baseline": "Classification-only baseline",
    "contextual_rule_baseline": "Contextual rules",
    "random_forest_raw": "Random Forest, raw",
    "random_forest_screened": "Random Forest, offline safety policy",
    "rubric_reference_ceiling": "Rubric reference ceiling",
}


def load_local_model(model_dir: Path, input_hashes: dict):
    meta = json.loads((model_dir / METADATA_FILENAME).read_text(encoding="utf-8"))
    if (
        meta["experiment"] != EXPERIMENT or meta["model_filename"] != MODEL_FILENAME
        or meta["rubric_version"] != RUBRIC_VERSION or meta["input_sha256"] != input_hashes
        or meta["feature_columns"] != list(FEATURE_COLUMNS)
    ):
        raise ValueError("Model metadata does not match the local experiment and frozen inputs.")
    model_path = model_dir / MODEL_FILENAME
    if sha256(model_path) != meta["model_sha256"]:
        raise ValueError("Joblib checksum differs from training metadata.")
    for package in ("scikit-learn", "joblib", "numpy", "scipy"):
        if version(package) != meta["dependencies"][package]:
            raise ValueError(f"Use the training version of {package} to load this model.")
    # Joblib deserializes Python objects. Only load an artifact you trained and trust.
    model = joblib.load(model_path)
    classes = {str(index): label for index, label in enumerate(model.classes_)}
    if classes != meta["class_mapping"] or set(model.classes_) != set(RESPONSE_CLASSES):
        raise ValueError("The loaded model does not have the expected response classes.")
    return model, meta


def evaluate_model(source: Path, labels: Path, manifest: Path, model_dir: Path, output: Path) -> dict:
    if output.exists():
        raise FileExistsError(f"Choose a new evaluation output directory: {output}")
    study = load_study(source, labels, manifest)
    model, meta = load_local_model(model_dir, study.hashes)
    cases = study.partitions["test"]
    x = feature_matrix([case.row for case in cases])
    reference = [case.target for case in cases]
    probabilities = model.predict_proba(x)
    scores = probabilities.max(axis=1)
    raw = model.classes_[probabilities.argmax(axis=1)].tolist()
    guard = [screen_recommendation(case.row, candidate) for case, candidate in zip(cases, raw, strict=True)]
    screened = [result.recommendation for result in guard]
    predictions = {
        "classification_only_baseline": [case.row.baseline_response for case in cases],
        "contextual_rule_baseline": [case.row.rule_based_response for case in cases],
        "random_forest_raw": raw,
        "random_forest_screened": screened,
        "rubric_reference_ceiling": reference,
    }

    methods = {method: classification_metrics(reference, actions) for method, actions in predictions.items()}
    novel_ids = study.novel_test_ids
    novel_indices = [index for index, case in enumerate(cases) if case.row.observation_id in novel_ids]
    novel_reference = [reference[index] for index in novel_indices]
    novel = {method: classification_metrics(novel_reference, [actions[index] for index in novel_indices])
             for method, actions in predictions.items()}

    model.predict_proba(x[:1])
    times = []
    for row in x:
        started = perf_counter()
        model.predict_proba(row.reshape(1, -1))
        times.append((perf_counter() - started) * 1000)

    safety = {
        "policy_version": POLICY_VERSION, "status": "PROPOSED_OFFLINE_ONLY", "rows": len(cases),
        "raw_flagged_by_policy": sum(result.reason is not None for result in guard),
        "adjusted_flagged_by_policy": sum(
            screen_recommendation(case.row, recommended).reason is not None
            for case, recommended in zip(cases, screened, strict=True)
        ),
        "unsupported_raw_actions": sum(action not in RESPONSE_CLASSES for action in raw),
        "override_reasons": dict(Counter(result.reason for result in guard if result.reason is not None)),
        "critical": {name: critical_errors(cases, actions) for name, actions in predictions.items()},
        "notes": [
            "This offline interpretation applies mandatory hold, evidence review, critical monitoring and unsupported action checks.",
            "Backup and hold recommendations require supporting evidence under the proposed rubric.",
            "Input schema validation stops malformed observations before prediction.",
            "No confidence threshold, missing model fallback, or runtime safety policy was activated.",
            "The provisional reference and the guard share policy criteria. Adjusted agreement is not independent validation.",
        ],
    }

    metrics = {
        "experiment": EXPERIMENT, "status": "EXPERIMENTAL_SYNTHETIC_PROTOTYPE",
        "reference": "RUBRIC_GENERATED, PENDING, no independent validation",
        "method_names": METHOD_NAMES, "classes": list(RESPONSE_CLASSES),
        "methods": methods, "novel_methods": novel,
        "novel_definition": "15 inputs except threat_confidence, compared against both training and validation",
        "partitions": {name: len(part) for name, part in study.partitions.items()},
        "split_overlap": study.overlap, "label_summary": label_summary([
            case for part in study.partitions.values() for case in part
        ]),
        "feature_importance": feature_importance(model),
        "prediction_confidence": confidence_summary(scores, np.asarray(reference) == np.asarray(raw)),
        "latency": latency_summary(times), "model_selection": meta["training"]["selected"],
        "matplotlib_version": version("matplotlib"), "safety": safety,
    }
    output.mkdir(parents=True)
    for name, document in (("evaluation-metrics.json", metrics), ("safety-evaluation.json", safety)):
        with (output / name).open("x", encoding="utf-8") as stream:
            json.dump(document, stream, indent=2)
            stream.write("\n")
    with (output / "baseline-comparison.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["subset", "method", "rows", *AGGREGATES])
        for subset, result in (("test", methods), ("structurally_novel_test", novel)):
            for method, values in result.items():
                writer.writerow([subset, method, values["rows"], *(values[name] for name in AGGREGATES)])
    with (output / "test-predictions.csv").open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(["observation_id", "session_id", "scenario_id", "risk_score", "risk_level", "novel_structure",
                         "provisional_response", "baseline_response", "contextual_response", "rf_raw", "rf_screened",
                         "rf_max_probability", "safety_reason"])
        for index, case in enumerate(cases):
            row = case.row
            writer.writerow([row.observation_id, row.session_id, row.scenario_id, row.risk_score, row.risk_level,
                             row.observation_id in novel_ids, reference[index], row.baseline_response,
                             row.rule_based_response, raw[index], screened[index], f"{scores[index]:.8f}",
                             guard[index].reason])
    save_figures(metrics, output)
    render_report(metrics, output, model_dir / METADATA_FILENAME)
    return metrics


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "labels", "split", "model-dir", "output-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args()
    try:
        result = evaluate_model(args.source, args.labels, args.split, args.model_dir, args.output_dir)
        print(json.dumps({name: {metric: result["methods"][name][metric] for metric in AGGREGATES}
                          for name in METHOD_NAMES}, indent=2))
    except (ValueError, OSError, csv.Error) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()

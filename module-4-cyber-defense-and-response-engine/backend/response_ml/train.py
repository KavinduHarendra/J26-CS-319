"""Select and save a synthetic Random Forest prototype without scoring test data."""

import argparse
import csv
import json
import platform
from importlib.metadata import version
from pathlib import Path
from time import perf_counter

import joblib
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import ParameterGrid
from sklearn.pipeline import Pipeline

from response_ml.features import FEATURE_COLUMNS, ResponseFeatures
from response_ml.preprocessing import CATEGORICAL, NUMERIC, feature_matrix, make_preprocessor
from response_ml.prototype_data import LABEL_EXPORT_VERSION, PROTOTYPE_DATASET_VERSION, label_summary, load_study, sha256
from response_ml.rubric import RESPONSE_CLASSES, RUBRIC_VERSION

MODEL_FILENAME = "prototype-random-forest.joblib"
METADATA_FILENAME = "model-metadata.json"
EXPERIMENT = "synthetic-random-forest-v1"
SEARCH = {
    "class_weight": [None, "balanced", "balanced_subsample"],
    "max_depth": [None, 8, 12],
    "min_samples_leaf": [1, 3],
    "n_estimators": [120],
}


def training_inputs(cases):
    return feature_matrix([case.row for case in cases]), [case.target for case in cases]


def train_model(source: Path, labels: Path, manifest: Path, output: Path, seed: int) -> dict:
    if output.exists():
        raise FileExistsError(f"Choose a new model output directory: {output}")
    study = load_study(source, labels, manifest)
    train_x, train_y = training_inputs(study.partitions["train"])
    val_x, val_y = training_inputs(study.partitions["validation"])

    best_model, best_trial, best_key = None, None, None
    trials = []
    started = perf_counter()
    for params in ParameterGrid(SEARCH):
        model = Pipeline([
            ("preprocessing", make_preprocessor()),
            ("classifier", RandomForestClassifier(random_state=seed, n_jobs=1, **params)),
        ])
        model.fit(train_x, train_y)
        predictions = model.predict(val_x)
        trial = {
            "parameters": params,
            "macro_f1": float(f1_score(val_y, predictions, labels=RESPONSE_CLASSES, average="macro", zero_division=0)),
            "balanced_accuracy": float(balanced_accuracy_score(val_y, predictions)),
            "accuracy": float(accuracy_score(val_y, predictions)),
        }
        trials.append(trial)
        key = (trial["macro_f1"], trial["balanced_accuracy"], trial["accuracy"])
        if best_key is None or key > best_key:
            best_model, best_trial, best_key = model, trial, key

    elapsed = perf_counter() - started
    output.mkdir(parents=True)
    model_path = output / MODEL_FILENAME
    with model_path.open("xb") as stream:
        joblib.dump(best_model, stream, compress=3)
    metadata = {
        "experiment": EXPERIMENT, "status": "EXPERIMENTAL_SYNTHETIC_PROTOTYPE",
        "dataset_version": PROTOTYPE_DATASET_VERSION, "label_export_version": LABEL_EXPORT_VERSION,
        "rubric_version": RUBRIC_VERSION, "input_sha256": study.hashes,
        "model_filename": MODEL_FILENAME, "model_sha256": sha256(model_path),
        "dependencies": {"python": platform.python_version(), **{name: version(name) for name in (
            "scikit-learn", "joblib", "numpy", "scipy", "pydantic"
        )}},
        "feature_columns": list(FEATURE_COLUMNS),
        "feature_definitions": ResponseFeatures.model_json_schema()["properties"],
        "preprocessing": {
            "numeric": list(NUMERIC), "categorical": list(CATEGORICAL),
            "numeric_missing": "Train median and missing indicator",
            "categorical_missing": "__MISSING__ before one-hot encoding",
            "unseen_categories": "One-hot handles categories absent from the training fold",
        },
        "class_mapping": {str(index): action for index, action in enumerate(best_model.classes_)},
        "training": {
            "seed": seed, "n_jobs": 1, "search": SEARCH, "trials": trials, "selected": best_trial,
            "selection": "Validation macro F1, then balanced accuracy, then accuracy, then first trial",
            "fit_partition": "train", "selection_partition": "validation",
            "test_scored_during_selection": False, "selection_seconds": elapsed,
        },
        "partitions": {name: label_summary(cases) for name, cases in study.partitions.items()},
        "split_overlap": study.overlap,
    }
    with (output / METADATA_FILENAME).open("x", encoding="utf-8") as stream:
        json.dump(metadata, stream, indent=2)
        stream.write("\n")
    return metadata


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("source", "labels", "split", "output-dir"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()
    try:
        metadata = train_model(args.source, args.labels, args.split, args.output_dir, args.seed)
        print(json.dumps(metadata["training"]["selected"], indent=2))
    except (ValueError, OSError, csv.Error) as error:
        parser.exit(1, f"Error: {error}\n")


if __name__ == "__main__":
    main()

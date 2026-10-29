"""Compare Rule Base only against Rule Base + anomaly engine on held-out real data.

Calibration uses the first chronological half of each known group, exactly as
``calibrate_real.py`` does.  Evaluation uses the second half plus every
``abnormal_signals`` capture, whose jammer types were never used for tuning.
"""

from __future__ import annotations

import csv
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.calibrate_real import DATA_ROOT, build_configuration
from src.anomaly_engine import AnomalyEngine
from src.baseline import Baseline
from src.classifier import ThreatClassifier
from src.experiments import label_and_run
from src.real_data import Signal, load_stream
from src.rule_engine import build_rule_engine

RESULTS = {
    "rulebase_only": ROOT / "data" / "results_rulebase_only.csv",
    "combined": ROOT / "data" / "results_combined.csv",
}
DISABLED_THRESHOLD = 999.0
TRUE_LABELS = {
    "idle": "NORMAL",
    "legit_ook": "NORMAL",
    "CARRIER": "JAMMING",
    "PULSED_50_50": "JAMMING",
}


def evaluation_dataset(validation: dict[str, tuple[Signal, ...]]) -> list[tuple[Signal, str]]:
    dataset = [
        (signal, TRUE_LABELS[group])
        for group, signals in validation.items()
        for signal in signals
    ]
    dataset += [
        (signal, "UNKNOWN_ANOMALY")
        for signal in load_stream(DATA_ROOT / "abnormal_signals")
    ]
    dataset.sort(key=lambda item: item[0].sequence_number)
    return dataset


def build_configurations(configuration: dict) -> dict[str, ThreatClassifier]:
    baseline = Baseline.from_config(configuration)
    thresholds = configuration["thresholds"]
    rules = build_rule_engine(float(thresholds["T_SNR"]), float(thresholds["T_BW"]))
    return {
        "rulebase_only": ThreatClassifier(
            baseline, rules, AnomalyEngine(baseline, threshold=DISABLED_THRESHOLD)
        ),
        "combined": ThreatClassifier(baseline, rules),
    }


def write_results(path: Path, results: list[tuple[str, str, float]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("true_label", "predicted_label", "latency_ms"))
        writer.writerows(results)


def main() -> int:
    configuration, split = build_configuration(DATA_ROOT)
    dataset = evaluation_dataset(split.validation)
    print(f"evaluation set: {len(dataset)} {dict(Counter(label for _, label in dataset))}")

    for name, module in build_configurations(configuration).items():
        results = label_and_run(module, dataset)
        write_results(RESULTS[name], results)
        correct = sum(true == predicted for true, predicted, _ in results)
        latency = statistics.fmean(ms for _, _, ms in results)
        print(
            f"{name}: exact-match {correct}/{len(results)} "
            f"mean latency {latency:.4f} ms -> {RESULTS[name].relative_to(ROOT)}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

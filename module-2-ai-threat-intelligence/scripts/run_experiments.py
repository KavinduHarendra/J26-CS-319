"""Compare Rule Base only against Rule Base + anomaly engine on real data.

Calibration uses the first chronological half of each known group, exactly as
``calibrate_real.py`` does.  Results are written per evaluation group:

- calibration          first half of the known groups (in-sample)
- validation           second half of the known groups
- unseen_jammer_types  every ``abnormal_signals`` capture (PULSED_5_95 and
                       RANDOM_BURSTS); ground truth labels them JAMMING and
                       their types were never used for tuning
- leave_one_out_<type> every capture of one known jammer type, classified with
                       R1 thresholds recalibrated without that type
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

from scripts.calibrate_real import DATA_ROOT, TimeSplit, build_configuration, rule_thresholds
from src.anomaly_engine import AnomalyEngine
from src.baseline import Baseline
from src.classifier import ThreatClassifier
from src.experiments import label_and_run
from src.fuzzy import FuzzyRiskSystem
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
UNSEEN_LABEL = "JAMMING"  # ground_truth.csv expected_class for abnormal_signals
KNOWN_JAMMERS = ("CARRIER", "PULSED_50_50")
GROUPS = (
    "calibration",
    "validation",
    "unseen_jammer_types",
    *(f"leave_one_out_{jammer}" for jammer in KNOWN_JAMMERS),
)

Dataset = list[tuple[Signal, str]]


def _labelled(groups: dict[str, tuple[Signal, ...]]) -> Dataset:
    dataset = [
        (signal, TRUE_LABELS[group]) for group, signals in groups.items() for signal in signals
    ]
    return sorted(dataset, key=lambda item: item[0].sequence_number)


def group_datasets(split: TimeSplit, data_root: Path = DATA_ROOT) -> dict[str, Dataset]:
    """Datasets classified with the shipped calibration."""
    return {
        "calibration": _labelled(split.calibration),
        "validation": _labelled(split.validation),
        "unseen_jammer_types": [
            (signal, UNSEEN_LABEL) for signal in load_stream(data_root / "abnormal_signals")
        ],
    }


def leave_one_out_configuration(configuration: dict, split: TimeSplit, held: str) -> dict:
    """Copy of *configuration* with R1 thresholds recalibrated without *held*."""
    retained = [jammer for jammer in KNOWN_JAMMERS if jammer != held]
    t_snr, t_bw = rule_thresholds(
        split.calibration["idle"],
        split.calibration["legit_ook"],
        [signal for jammer in retained for signal in split.calibration[jammer]],
    )
    return configuration | {
        "thresholds": configuration["thresholds"] | {"T_SNR": t_snr, "T_BW": t_bw}
    }


def leave_one_out_dataset(split: TimeSplit, held: str) -> Dataset:
    signals = split.calibration[held] + split.validation[held]
    return [(signal, TRUE_LABELS[held]) for signal in signals]


def build_configurations(configuration: dict) -> dict[str, ThreatClassifier]:
    baseline = Baseline.from_config(configuration)
    thresholds = configuration["thresholds"]
    rules = build_rule_engine(float(thresholds["T_SNR"]), float(thresholds["T_BW"]))
    fuzzy = FuzzyRiskSystem.from_config(configuration)
    return {
        "rulebase_only": ThreatClassifier(
            baseline, rules, AnomalyEngine(baseline, threshold=DISABLED_THRESHOLD), fuzzy=fuzzy
        ),
        "combined": ThreatClassifier(baseline, rules, fuzzy=fuzzy),
    }


def run_all(configuration: dict, split: TimeSplit) -> dict[str, list[tuple[str, str, float, str]]]:
    """Return (true_label, predicted_label, latency_ms, group) rows per configuration."""
    rows: dict[str, list[tuple[str, str, float, str]]] = {name: [] for name in RESULTS}

    def run(modules: dict[str, ThreatClassifier], group: str, dataset: Dataset) -> None:
        for name, module in modules.items():
            rows[name] += [(*result, group) for result in label_and_run(module, dataset)]

    shipped = build_configurations(configuration)
    for group, dataset in group_datasets(split).items():
        run(shipped, group, dataset)
    for held in KNOWN_JAMMERS:
        modules = build_configurations(leave_one_out_configuration(configuration, split, held))
        run(modules, f"leave_one_out_{held}", leave_one_out_dataset(split, held))
    return rows


def write_results(path: Path, results: list[tuple[str, str, float, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(("true_label", "predicted_label", "latency_ms", "group"))
        writer.writerows(results)


def main() -> int:
    configuration, split = build_configuration(DATA_ROOT)
    for held in KNOWN_JAMMERS:
        thresholds = leave_one_out_configuration(configuration, split, held)["thresholds"]
        print(f"leave_one_out_{held}: T_SNR={thresholds['T_SNR']:.2f} T_BW={thresholds['T_BW']:.2f}")

    for name, results in run_all(configuration, split).items():
        write_results(RESULTS[name], results)
        print(f"{name} -> {RESULTS[name].relative_to(ROOT)}")
        for group in GROUPS:
            selected = [row for row in results if row[3] == group]
            correct = sum(true == predicted for true, predicted, _, _ in selected)
            labels = dict(Counter(true for true, _, _, _ in selected))
            print(f"  {group}: exact-match {correct}/{len(selected)} {labels}")
        latency = statistics.fmean(ms for _, _, ms, _ in results)
        print(f"  mean latency {latency:.4f} ms")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

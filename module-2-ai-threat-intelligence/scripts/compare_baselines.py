"""Print the Rule Base vs Rule Base + anomaly engine comparison for the report.

Reads the CSVs written by ``run_experiments.py``.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_experiments import RESULTS
from src.evaluate import LABELS, NFR01_LATENCY_TARGET_MS, evaluate_results

CONFIGURATIONS = {
    "rulebase_only": "Rule Base Only (baseline)",
    "combined": "Rule Base + Statistical Anomaly Engine (proposed)",
}


def load_results(path: Path) -> list[tuple[str, str, float]]:
    if not path.exists():
        sys.exit(f"missing {path.relative_to(ROOT)}; run scripts/run_experiments.py first")
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            (row["true_label"], row["predicted_label"], float(row["latency_ms"]))
            for row in csv.DictReader(handle)
        ]


def threat_detection_rate(results: list[tuple[str, str, float]], true_label: str) -> tuple[int, int]:
    """Count captures of one true class flagged as any threat (not NORMAL)."""
    selected = [predicted for true, predicted, _ in results if true == true_label]
    return sum(predicted != "NORMAL" for predicted in selected), len(selected)


def comparison_table(results: dict[str, list], metrics: dict[str, dict]) -> str:
    baseline, proposed = (metrics[key] for key in CONFIGURATIONS)

    def row(name: str, left: str, right: str, change: str = "") -> str:
        return f"| {name} | {left} | {right} | {change} |"

    def score(name: str, field: str, label: str) -> str:
        left = baseline["report"][label][field]
        right = proposed["report"][label][field]
        return row(name, f"{left:.4f}", f"{right:.4f}", f"{right - left:+.4f}")

    lines = [
        f"| Metric | {CONFIGURATIONS['rulebase_only']} | {CONFIGURATIONS['combined']} | Change |",
        "|---|---:|---:|---:|",
    ]
    for label in LABELS:
        lines += [
            score(f"{label} precision", "precision", label),
            score(f"{label} recall", "recall", label),
            score(f"{label} F1", "f1-score", label),
        ]
    lines += [
        score("Macro F1", "f1-score", "macro avg"),
        row(
            "Accuracy",
            f"{baseline['report']['accuracy']:.4f}",
            f"{proposed['report']['accuracy']:.4f}",
            f"{proposed['report']['accuracy'] - baseline['report']['accuracy']:+.4f}",
        ),
    ]
    detected = {key: threat_detection_rate(results[key], "UNKNOWN_ANOMALY") for key in CONFIGURATIONS}
    (base_hit, base_total), (prop_hit, prop_total) = detected.values()
    lines.append(
        row(
            "Unseen jammers flagged as any threat",
            f"{base_hit}/{base_total}",
            f"{prop_hit}/{prop_total}",
            f"{prop_hit - base_hit:+d}",
        )
    )
    lines += [
        row(
            "False Positive Rate (Normal)",
            f"{baseline['false_positives']}/{baseline['normal_total']} ({baseline['false_positive_rate']:.4%})",
            f"{proposed['false_positives']}/{proposed['normal_total']} ({proposed['false_positive_rate']:.4%})",
            f"{(proposed['false_positive_rate'] - baseline['false_positive_rate']) * 100:+.4f} pp",
        ),
        row(
            "Mean latency (ms)",
            f"{baseline['mean_latency_ms']:.4f}",
            f"{proposed['mean_latency_ms']:.4f}",
            f"{proposed['mean_latency_ms'] - baseline['mean_latency_ms']:+.4f}",
        ),
        row(
            f"NFR01 (mean < {NFR01_LATENCY_TARGET_MS:.0f} ms)",
            "PASS" if baseline["nfr01_pass"] else "FAIL",
            "PASS" if proposed["nfr01_pass"] else "FAIL",
        ),
    ]
    return "\n".join(lines)


def main() -> int:
    results = {key: load_results(RESULTS[key]) for key in CONFIGURATIONS}
    metrics = {}
    for key, title in CONFIGURATIONS.items():
        metrics[key] = evaluate_results(results[key], title=title)
        print()

    heading = "Side-by-side comparison"
    print(heading)
    print("=" * len(heading))
    print(comparison_table(results, metrics))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

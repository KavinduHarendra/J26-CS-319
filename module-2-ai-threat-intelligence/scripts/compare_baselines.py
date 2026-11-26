"""Print and save the Rule Base vs Rule Base + anomaly engine comparison.

Reads the CSVs written by ``run_experiments.py`` and writes
``reports/baseline_comparison.md``.  Headline metrics cover the held-out
groups (validation + unseen jammer types); every group is also reported on its
own.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.run_experiments import GROUPS, RESULTS
from src.evaluate import LABELS, NFR01_LATENCY_TARGET_MS, evaluate_results

REPORT_PATH = ROOT / "reports" / "baseline_comparison.md"
CONFIGURATIONS = {
    "rulebase_only": "Rule Base Only (baseline)",
    "combined": "Rule Base + Statistical Anomaly Engine (proposed)",
}
HELD_OUT = ("validation", "unseen_jammer_types")
GROUP_TITLES = {
    "calibration": "Calibration (in-sample)",
    "validation": "Validation",
    "unseen_jammer_types": "Unseen jammer types",
    "leave_one_out_CARRIER": "Leave-one-jammer-type-out: CARRIER",
    "leave_one_out_PULSED_50_50": "Leave-one-jammer-type-out: PULSED_50_50",
}
IDENTICAL_NOTE = (
    "**Note.** Rule Base Only and Rule Base + Statistical Anomaly Engine give "
    "identical predictions on every evaluated capture of this recording. R1 "
    "catches all jamming (known, unseen and leave-one-out), and the anomaly "
    "engine raises no false alarms on normal captures, so it never changes an "
    "outcome here. The recording contains no non-jamming abnormal captures, so "
    "it cannot measure the anomaly engine's value; that must be tested on "
    "non-jamming abnormal captures from new recordings."
)

Row = tuple[str, str, float, str]


def load_results(path: Path) -> list[Row]:
    if not path.exists():
        sys.exit(f"missing {path.relative_to(ROOT)}; run scripts/run_experiments.py first")
    with path.open(newline="", encoding="utf-8") as handle:
        return [
            (row["true_label"], row["predicted_label"], float(row["latency_ms"]), row["group"])
            for row in csv.DictReader(handle)
        ]


def select(results: list[Row], groups: tuple[str, ...]) -> list[tuple[str, str, float]]:
    return [(true, predicted, ms) for true, predicted, ms, group in results if group in groups]


def threat_detection_rate(results: list[Row], group: str) -> tuple[int, int]:
    """Count captures of one group flagged as any threat (not NORMAL)."""
    selected = [predicted for _, predicted, _, name in results if name == group]
    return sum(predicted != "NORMAL" for predicted in selected), len(selected)


def comparison_table(results: dict[str, list[Row]], metrics: dict[str, dict]) -> str:
    baseline, proposed = (metrics[key] for key in CONFIGURATIONS)

    def row(name: str, left: str, right: str, change: str = "") -> str:
        return f"| {name} | {left} | {right} | {change} |"

    def score(name: str, field: str, label: str) -> str:
        if baseline["report"][label]["support"] == 0:
            return row(name, "n/a", "n/a", "no captures")
        left = baseline["report"][label][field]
        right = proposed["report"][label][field]
        return row(name, f"{left:.4f}", f"{right:.4f}", f"{right - left:+.4f}")

    lines = [
        f"| Metric | {CONFIGURATIONS['rulebase_only']} | {CONFIGURATIONS['combined']} | Change |",
        "| --- | ---: | ---: | ---: |",
    ]
    for label in LABELS:
        lines += [
            score(f"{label} precision", "precision", label),
            score(f"{label} recall", "recall", label),
            score(f"{label} F1", "f1-score", label),
        ]
    lines += [
        row(
            "Accuracy",
            f"{baseline['report']['accuracy']:.4f}",
            f"{proposed['report']['accuracy']:.4f}",
            f"{proposed['report']['accuracy'] - baseline['report']['accuracy']:+.4f}",
        ),
    ]
    (base_hit, base_total), (prop_hit, prop_total) = (
        threat_detection_rate(results[key], "unseen_jammer_types") for key in CONFIGURATIONS
    )
    lines += [
        row(
            "Unseen jammer types flagged as any threat",
            f"{base_hit}/{base_total}",
            f"{prop_hit}/{prop_total}",
            f"{prop_hit - base_hit:+d}",
        ),
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


def group_table(results: dict[str, list[Row]]) -> str:
    left, right = (results[key] for key in CONFIGURATIONS)
    lines = [
        "| Group | Captures (Normal / Jamming) | Rule Base Only correct | "
        "Rule Base + Anomaly correct | Predictions that differ |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for group in GROUPS:
        pairs = [(a, b) for a, b in zip(left, right, strict=True) if a[3] == group]
        normal = sum(a[0] == "NORMAL" for a, _ in pairs)
        jamming = sum(a[0] == "JAMMING" for a, _ in pairs)
        correct_left = sum(a[0] == a[1] for a, _ in pairs)
        correct_right = sum(b[0] == b[1] for _, b in pairs)
        differ = sum(a[1] != b[1] for a, b in pairs)
        total = len(pairs)
        lines.append(
            f"| {GROUP_TITLES[group]} | {total} ({normal} / {jamming}) | "
            f"{correct_left}/{total} ({correct_left / total:.2%}) | "
            f"{correct_right}/{total} ({correct_right / total:.2%}) | {differ} |"
        )
    return "\n".join(lines)


def note(results: dict[str, list[Row]], metrics: dict[str, dict]) -> str:
    left, right = (results[key] for key in CONFIGURATIONS)
    differ = sum(a[1] != b[1] for a, b in zip(left, right, strict=True))
    false_alarms = any(metrics[key]["false_positives"] for key in CONFIGURATIONS)
    if differ == 0 and not false_alarms:
        return IDENTICAL_NOTE
    return (
        f"**Note.** The two configurations disagree on {differ} of {len(left)} "
        "evaluated captures; see the per-group table."
    )


def main() -> int:
    results = {key: load_results(RESULTS[key]) for key in CONFIGURATIONS}
    metrics = {}
    for key, title in CONFIGURATIONS.items():
        metrics[key] = evaluate_results(select(results[key], HELD_OUT), title=f"{title}, held-out")
        print()

    report = "\n".join(
        [
            "# Rule Base vs Rule Base + Statistical Anomaly Engine",
            "",
            "Generated by `scripts/compare_baselines.py` from `data/results_*.csv`. "
            "Ground truth labels the 93 `abnormal_signals` captures (PULSED_5_95, "
            "RANDOM_BURSTS) as JAMMING; they form the unseen jammer types group.",
            "",
            "## Per group",
            "",
            group_table(results),
            "",
            "## Held-out (validation + unseen jammer types)",
            "",
            comparison_table(results, metrics),
            "",
            note(results, metrics),
            "",
        ]
    )
    print(report)
    REPORT_PATH.write_text(report, encoding="utf-8")
    print(f"wrote={REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

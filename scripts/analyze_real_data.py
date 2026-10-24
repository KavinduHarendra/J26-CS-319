"""Reproduce the real-data feature audit, calibration, and evaluation reports."""

from __future__ import annotations

import csv
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path
from statistics import mean, stdev

import numpy as np
from sklearn.metrics import roc_auc_score

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.classifier import Classification
from src.real_classifier import RealThreatClassifierV2, SEVERITY_CUTOFFS_PLACEHOLDER
from src.real_data import RealSignal, SignalCollectionSource
from src.scoring_data import load_ground_truth, load_module1_flags_reference
from src.real_detection import (
    AUDITED_FEATURES,
    BASELINE_VERSION,
    DETECTION_FEATURES,
    STD_FLOORS,
    RealDetectorV2,
    fit_detector_v2,
)


DATA = ROOT / "data" / "real" / "module1_signals_clean"
REPORTS = ROOT / "reports"
JAMMER_TYPES = ("CARRIER", "PULSED_50_50", "PULSED_5_95", "RANDOM_BURSTS")
KNOWN_JAMMERS = ("CARRIER", "PULSED_50_50")
UNSEEN_JAMMERS = ("PULSED_5_95", "RANDOM_BURSTS")


def rows_for(
    signals: list[RealSignal], truth: dict[str, dict[str, str]], **values: str
) -> list[RealSignal]:
    return [
        signal
        for signal in signals
        if all(truth[signal.observation_id][field] == value for field, value in values.items())
    ]


def split_data(signals: list[RealSignal], truth: dict[str, dict[str, str]]) -> dict[str, list[RealSignal]]:
    clean = [signal for signal in signals if not truth[signal.observation_id]["label_quality_note"]]
    idle = sorted(rows_for(clean, truth, normal_kind="idle"), key=lambda signal: signal.timestamp)
    legitimate = sorted(
        rows_for(clean, truth, normal_kind="legit_ook"), key=lambda signal: signal.timestamp
    )
    idle_midpoint = len(idle) // 2
    legitimate_midpoint = len(legitimate) // 2
    result = {
        "calibration_idle": idle[:idle_midpoint],
        "validation_idle": idle[idle_midpoint:],
        "calibration_legitimate": legitimate[:legitimate_midpoint],
        "validation_legitimate": legitimate[legitimate_midpoint:],
        "calibration_jamming": [
            signal
            for signal in clean
            if truth[signal.observation_id]["expected_class"] == "JAMMING"
            and truth[signal.observation_id]["jammer_type"] in KNOWN_JAMMERS
        ],
        "unseen_jamming": [
            signal
            for signal in clean
            if truth[signal.observation_id]["expected_class"] == "JAMMING"
            and truth[signal.observation_id]["jammer_type"] in UNSEEN_JAMMERS
        ],
        "none_inside_jammer_phase": [
            signal
            for signal in signals
            if truth[signal.observation_id]["label_quality_note"].startswith(
                "labelled none inside a jammer phase"
            )
        ],
        "signal_present_but_none": [
            signal
            for signal in signals
            if truth[signal.observation_id]["label_quality_note"].startswith(
                "signal present but labelled none"
            )
        ],
    }
    return result


def resolution(values: list[float]) -> float:
    unique = sorted(set(values))
    gaps = [second - first for first, second in zip(unique, unique[1:]) if second > first]
    return min(gaps) if gaps else 0.0


def oriented_auc(jamming: list[float], normal: list[float]) -> tuple[float, str]:
    raw = float(roc_auc_score([1] * len(jamming) + [0] * len(normal), jamming + normal))
    if raw >= 0.5:
        return raw, "higher"
    return 1.0 - raw, "lower"


def feature_audit(
    signals: list[RealSignal], truth: dict[str, dict[str, str]]
) -> tuple[list[dict[str, object]], str]:
    clean = [signal for signal in signals if not truth[signal.observation_id]["label_quality_note"]]
    groups: dict[str, list[RealSignal]] = {
        "idle": rows_for(clean, truth, normal_kind="idle"),
        "legit_ook": rows_for(clean, truth, normal_kind="legit_ook"),
    }
    groups.update(
        {
            jammer: [
                signal
                for signal in clean
                if truth[signal.observation_id]["expected_class"] == "JAMMING"
                and truth[signal.observation_id]["jammer_type"] == jammer
            ]
            for jammer in JAMMER_TYPES
        }
    )
    jamming = [signal for jammer in JAMMER_TYPES for signal in groups[jammer]]
    csv_rows: list[dict[str, object]] = []
    markdown = [
        "# Real signal feature audit",
        "",
        "Generated from the validated measurement records through `src/real_data.py`. Ground truth is joined only in this offline report to form groups and calculate scores; it is not available to the detector.",
        "",
        "## Group summary",
        "",
        "| Group | Feature | N | Mean | Std | Min | Max | Unique | Resolution |",
        "|---|---|---:|---:|---:|---:|---:|---:|---:|",
    ]
    for group_name, group in groups.items():
        for feature in AUDITED_FEATURES:
            values = [getattr(signal, feature) for signal in group]
            row = {
                "record_type": "group_stats",
                "group": group_name,
                "feature": feature,
                "count": len(values),
                "mean": mean(values),
                "std": stdev(values) if len(values) > 1 else 0.0,
                "min": min(values),
                "max": max(values),
                "unique_count": len(set(values)),
                "resolution": resolution(values),
                "auc_jamming_vs_idle": "",
                "direction_vs_idle": "",
                "auc_jamming_vs_legit_ook": "",
                "direction_vs_legit_ook": "",
                "flags": "",
            }
            csv_rows.append(row)
            markdown.append(
                f"| {group_name} | {feature} | {len(values)} | {mean(values):.6f} | "
                f"{row['std']:.6f} | {min(values):.6f} | {max(values):.6f} | "
                f"{len(set(values))} | {resolution(values):.6f} |"
            )

    markdown += [
        "",
        "## Single-feature discrimination",
        "",
        "AUC is direction-adjusted so 0.5 means chance and 1.0 means complete separation. The direction column says whether lower or higher values indicate jamming. AUC is descriptive, not a permission to use a session artefact.",
        "",
        "| Feature | Jamming vs idle AUC | Direction | Jamming vs legit OOK AUC | Direction | Audit flag |",
        "|---|---:|---|---:|---|---|",
    ]
    for feature in AUDITED_FEATURES:
        jammer_values = [getattr(signal, feature) for signal in jamming]
        idle_auc, idle_direction = oriented_auc(
            jammer_values, [getattr(signal, feature) for signal in groups["idle"]]
        )
        ook_auc, ook_direction = oriented_auc(
            jammer_values, [getattr(signal, feature) for signal in groups["legit_ook"]]
        )
        all_values = [getattr(signal, feature) for signal in clean]
        flags: list[str] = []
        if any(len({getattr(signal, feature) for signal in group}) == 1 for group in groups.values()):
            flags.append("constant in at least one group")
        if len(set(all_values)) < max(20, len(all_values) // 20):
            flags.append("quantised")
        if feature in {"noise_db", "peak_freq_mhz"}:
            flags.append("session artefact")
        flag_text = "; ".join(flags) or "none"
        csv_rows.append(
            {
                "record_type": "feature_summary",
                "group": "all",
                "feature": feature,
                "count": len(all_values),
                "mean": mean(all_values),
                "std": stdev(all_values),
                "min": min(all_values),
                "max": max(all_values),
                "unique_count": len(set(all_values)),
                "resolution": resolution(all_values),
                "auc_jamming_vs_idle": idle_auc,
                "direction_vs_idle": idle_direction,
                "auc_jamming_vs_legit_ook": ook_auc,
                "direction_vs_legit_ook": ook_direction,
                "flags": flag_text,
            }
        )
        markdown.append(
            f"| {feature} | {idle_auc:.4f} | {idle_direction} | {ook_auc:.4f} | "
            f"{ook_direction} | {flag_text} |"
        )

    markdown += [
        "",
        "## Findings in plain words",
        "",
        "- `noise_db` changes with the scripted phase: its mean is about -107.28 dB for CARRIER, -106.21 dB for PULSED_50_50, and -105.24 dB for legitimate OOK. That looks like session order or receiver state, not portable threat evidence, so v2 excludes it.",
        "- `peak_freq_mhz` has very few distinct bins and follows the one transmitter/channel used in this session. It could identify this recording setup instead of jamming, so v2 excludes it.",
        "- Idle `band_power_dbfs` is constant at -45.1 and idle `occupied_bw_khz` is constant at 0. The v2 baseline retains them because they have physical meaning, but applies 0.1 dB and 1 kHz standard-deviation floors.",
        "- Several fields are rounded to 0.1 dB, 1 kHz, or 0.001. Small differences inside one output step should not be treated as precise changes.",
        "- The selected anomaly features are: " + ", ".join(f"`{name}`" for name in DETECTION_FEATURES) + ".",
        "- Labels, phase names, jammer names, paths, and Module 1 flags are used only to assemble or score offline groups. None is present in the runtime feature object.",
        "",
    ]
    return csv_rows, "\n".join(markdown)


def classification_name(classification: str) -> str:
    return {
        Classification.NORMAL.value: "NORMAL",
        Classification.JAMMING.value: "JAMMING",
        Classification.UNKNOWN_ANOMALY.value: "UNKNOWN_ANOMALY",
    }[classification]


def score_rows(
    name: str,
    rows: list[RealSignal],
    truth: dict[str, dict[str, str]],
    classifier: RealThreatClassifierV2,
) -> dict[str, object]:
    predictions = {signal.observation_id: classifier.classify(signal) for signal in rows}
    expected_counts = Counter(truth[signal.observation_id]["expected_class"] for signal in rows)
    matrix = {
        expected: {
            output: sum(
                truth[signal.observation_id]["expected_class"] == expected
                and classification_name(predictions[signal.observation_id].classification) == output
                for signal in rows
            )
            for output in ("NORMAL", "JAMMING", "UNKNOWN_ANOMALY")
        }
        for expected in ("NORMAL", "JAMMING")
    }
    return {
        "name": name,
        "rows": rows,
        "predictions": predictions,
        "expected_counts": expected_counts,
        "matrix": matrix,
    }


def matrix_markdown(scored: dict[str, object]) -> list[str]:
    matrix = scored["matrix"]
    return [
        f"### {scored['name']}",
        "",
        "| Expected \\ Output | NORMAL | JAMMING | UNKNOWN_ANOMALY |",
        "|---|---:|---:|---:|",
        f"| NORMAL | {matrix['NORMAL']['NORMAL']} | {matrix['NORMAL']['JAMMING']} | {matrix['NORMAL']['UNKNOWN_ANOMALY']} |",
        f"| JAMMING | {matrix['JAMMING']['NORMAL']} | {matrix['JAMMING']['JAMMING']} | {matrix['JAMMING']['UNKNOWN_ANOMALY']} |",
        "",
    ]


def percentage(numerator: int, denominator: int) -> str:
    return f"{100.0 * numerator / denominator:.2f}%" if denominator else "n/a"


def evaluation_report(
    signals: list[RealSignal],
    truth: dict[str, dict[str, str]],
    flags: dict[str, dict[str, object]],
    split: dict[str, list[RealSignal]],
    detector: RealDetectorV2,
) -> str:
    calibration_normal = split["calibration_idle"] + split["calibration_legitimate"]
    validation_normal = split["validation_idle"] + split["validation_legitimate"]
    classifier = RealThreatClassifierV2(detector)
    sets = [
        score_rows(
            "Calibration: known jammers plus first normal halves",
            calibration_normal + split["calibration_jamming"],
            truth,
            classifier,
        ),
        score_rows("Validation: second normal halves", validation_normal, truth, classifier),
        score_rows("Unseen jammer types", split["unseen_jamming"], truth, classifier),
    ]
    thresholds = detector.rules.thresholds
    lines = [
        "# Real signal detector evaluation",
        "",
        "All signal values were read through `src/real_data.py`. Ground truth and Module 1 flags were loaded separately for split construction and scoring only. Runtime classification receives a `RealSignal`, which contains measurements but no labels, phase, jammer type, folder, or Module 1 flags.",
        "",
        "## Non-random split",
        "",
        "| Partition | Contents | N |",
        "|---|---|---:|",
        f"| Calibration normal | First half by timestamp of clean idle ({len(split['calibration_idle'])}) and legitimate OOK ({len(split['calibration_legitimate'])}) | {len(calibration_normal)} |",
        f"| Calibration jamming | All clean CARRIER and PULSED_50_50 jamming | {len(split['calibration_jamming'])} |",
        f"| Validation | Second half by timestamp of clean idle ({len(split['validation_idle'])}) and legitimate OOK ({len(split['validation_legitimate'])}) | {len(validation_normal)} |",
        f"| Unseen | PULSED_5_95 and RANDOM_BURSTS; never used for fitting or threshold selection | {len(split['unseen_jamming'])} |",
        "",
        "The 11 rows carrying label-quality notes are excluded from calibration, validation, and unseen scoring and are reported separately below.",
        "",
        "## Baseline v2",
        "",
        f"Version: `{BASELINE_VERSION}`. The normal state is selected as legitimate when SNR is above the idle-only 99th-percentile threshold of {detector.baseline.state_snr_threshold:.3f} dB; otherwise it is idle. Anomaly distance is evaluated against both states and uses the nearer one.",
        "",
        "| State | Feature | Mean | Std used | Resolution floor |",
        "|---|---|---:|---:|---:|",
    ]
    for state in (detector.baseline.idle, detector.baseline.legitimate):
        for feature in DETECTION_FEATURES:
            lines.append(
                f"| {state.name} | {feature} | {state.mean[feature]:.6f} | "
                f"{state.std[feature]:.6f} | {STD_FLOORS[feature]:.6f} |"
            )
    lines += [
        "",
        "## Rules and anomaly threshold",
        "",
        f"`R2-NARROWBAND`: IF SNR > {thresholds.snr_signal_threshold:.3f} dB AND occupied bandwidth <= {thresholds.occupied_bw_max_khz:.3f} kHz AND spectral flatness <= {thresholds.spectral_flatness_max:.3f}, THEN Jamming. Grid search used calibration rows only and selected the tightest thresholds among equal-recall candidates satisfying normal FPR <= 1%.",
        "",
        f"Calibration rule FPR: {thresholds.calibration_normal_fpr:.4%}; calibration jammer recall: {thresholds.calibration_jammer_recall:.4%}.",
        "",
        f"The nearest-state RMS robust-z anomaly threshold is {detector.anomaly.threshold:.6f}. It is the higher empirical 99th percentile of calibration-normal distances; a record must be strictly above it.",
        "",
        "Legacy J01 is retired because a noise-floor rise is not present in these real captures and `noise_db` shifts with phase. Legacy J02 is retired because RSSI/packet-rate fields do not exist in the Module 1 real contract. Neither legacy rule is called by the v2 classifier.",
        "",
        "Severity cut-offs remain placeholders at robust-z magnitudes "
        + f"{SEVERITY_CUTOFFS_PLACEHOLDER[0]:.1f} and {SEVERITY_CUTOFFS_PLACEHOLDER[1]:.1f}; they need incident-impact data before operational use.",
        "",
        "## Confusion matrices",
        "",
        "Unknown Anomaly counts as detected abnormal behaviour for jammer recall, but it remains separate from rule-confirmed Jamming.",
        "",
    ]
    for scored in sets:
        lines.extend(matrix_markdown(scored))

    lines += [
        "## Rule-only versus Rule + Anomaly",
        "",
        "| Set | Rule-only detected | Combined detected | Total positive | Rule-only normal FP | Combined normal FP | Total normal |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ]
    for name, rows in (
        ("Calibration", calibration_normal + split["calibration_jamming"]),
        ("Validation", validation_normal),
        ("Unseen", split["unseen_jamming"]),
    ):
        positives = [s for s in rows if truth[s.observation_id]["expected_class"] == "JAMMING"]
        normals = [s for s in rows if truth[s.observation_id]["expected_class"] == "NORMAL"]
        rule_positive = sum(detector.rules.evaluate(s).triggered for s in positives)
        combined_positive = sum(
            classifier.classify(s).classification != Classification.NORMAL.value for s in positives
        )
        rule_fp = sum(detector.rules.evaluate(s).triggered for s in normals)
        combined_fp = sum(
            classifier.classify(s).classification != Classification.NORMAL.value for s in normals
        )
        lines.append(
            f"| {name} | {rule_positive} | {combined_positive} | {len(positives)} | "
            f"{rule_fp} | {combined_fp} | {len(normals)} |"
        )

    lines += [
        "",
        "## Recall and false-positive rates",
        "",
        "| Jammer type | Rule hits | Anomaly-only hits | Misses | Recall |",
        "|---|---:|---:|---:|---:|",
    ]
    for jammer in JAMMER_TYPES:
        rows = [
            signal
            for signal in signals
            if truth[signal.observation_id]["expected_class"] == "JAMMING"
            and truth[signal.observation_id]["jammer_type"] == jammer
        ]
        rule_hits = sum(detector.rules.evaluate(signal).triggered for signal in rows)
        anomaly_only = sum(
            not detector.rules.evaluate(signal).triggered
            and detector.anomaly.evaluate(signal).triggered
            for signal in rows
        )
        misses = len(rows) - rule_hits - anomaly_only
        lines.append(
            f"| {jammer} | {rule_hits} | {anomaly_only} | {misses} | "
            f"{percentage(rule_hits + anomaly_only, len(rows))} |"
        )

    lines += [
        "",
        "| Normal state / partition | False positives | N | FPR |",
        "|---|---:|---:|---:|",
    ]
    for name, rows in (
        ("Idle calibration", split["calibration_idle"]),
        ("Idle validation", split["validation_idle"]),
        ("Legitimate OOK calibration", split["calibration_legitimate"]),
        ("Legitimate OOK validation", split["validation_legitimate"]),
    ):
        false_positives = sum(
            classifier.classify(signal).classification != Classification.NORMAL.value
            for signal in rows
        )
        lines.append(
            f"| {name} | {false_positives} | {len(rows)} | "
            f"{percentage(false_positives, len(rows))} |"
        )

    lines += [
        "",
        "## Leave-one-known-jammer-type-out",
        "",
        "The unseen types remain untouched. The only valid threshold-selection leave-one-out exercise is therefore across the two known calibration types; each fold calibrates on one known type and tests the other.",
        "",
        "| Held out | Training jammer | Rule hits | Combined hits | N |",
        "|---|---|---:|---:|---:|",
    ]
    for held_out in KNOWN_JAMMERS:
        training_type = next(jammer for jammer in KNOWN_JAMMERS if jammer != held_out)
        training = [
            signal
            for signal in split["calibration_jamming"]
            if truth[signal.observation_id]["jammer_type"] == training_type
        ]
        held_rows = [
            signal
            for signal in split["calibration_jamming"]
            if truth[signal.observation_id]["jammer_type"] == held_out
        ]
        fold_detector = fit_detector_v2(
            split["calibration_idle"], split["calibration_legitimate"], training
        )
        fold_classifier = RealThreatClassifierV2(fold_detector)
        rule_hits = sum(fold_detector.rules.evaluate(signal).triggered for signal in held_rows)
        combined_hits = sum(
            fold_classifier.classify(signal).classification != Classification.NORMAL.value
            for signal in held_rows
        )
        lines.append(
            f"| {held_out} | {training_type} | {rule_hits} | {combined_hits} | {len(held_rows)} |"
        )

    lines += [
        "",
        "PULSED_5_95 and RANDOM_BURSTS are a stricter two-type holdout: neither appears in any fitting step. Their results are the Unseen matrix and per-type rows above.",
        "",
        "## Label-quality exceptions",
        "",
        "These rows are descriptive only and do not affect thresholds or headline scores.",
        "",
        "| Observation | Reference note | Output | Rule |",
        "|---|---|---|---|",
    ]
    for key in ("none_inside_jammer_phase", "signal_present_but_none"):
        for signal in split[key]:
            output = classifier.classify(signal)
            lines.append(
                f"| {signal.observation_id} | {truth[signal.observation_id]['label_quality_note']} | "
                f"{classification_name(output.classification)} | {output.triggered_rule or '-'} |"
            )
    lines += [
        "",
        f"Counts: {len(split['none_inside_jammer_phase'])} `none inside jammer phase` rows and {len(split['signal_present_but_none'])} `signal present but labelled none` rows.",
        "",
        "## Module 1 flag agreement (reference only)",
        "",
    ]
    clean_scored = [
        signal for signal in signals if not truth[signal.observation_id]["label_quality_note"]
    ]
    agreement = sum(
        (classifier.classify(signal).classification != Classification.NORMAL.value)
        == bool(flags[signal.observation_id]["interference"])
        for signal in clean_scored
    )
    legit_flagged = sum(flags[signal.observation_id]["signal_present"] == 1 for signal in rows_for(clean_scored, truth, normal_kind="legit_ook"))
    jammer_flagged = sum(
        flags[signal.observation_id]["signal_present"] == 1
        for signal in clean_scored
        if truth[signal.observation_id]["expected_class"] == "JAMMING"
    )
    lines += [
        f"The detector's abnormal/normal decision agrees with Module 1's `interference` flag on {agreement}/{len(clean_scored)} clean records ({percentage(agreement, len(clean_scored))}). This is an agreement statistic, not detector input.",
        "",
        f"`signal_present` is 1 for {legit_flagged}/49 legitimate OOK records and {jammer_flagged}/189 jamming records. It therefore says that energy is present, not whether the energy is hostile, and is not used as sole evidence.",
        "",
        "## Limits",
        "",
        "- This is one approximately 318-second session, one receiver setup, one frequency band, and one legitimate OOK device.",
        "- The normal legitimate state contains only 49 records. Its estimated spread and the state boundary need more devices, powers, distances, locations, and days.",
        "- Thresholds may describe this receiver and scripted schedule. They must be revalidated prospectively before deployment.",
        "- The anomaly threshold controls calibration false alarms, not future-site false alarms; the chronological validation result is the more honest in-session check.",
        "- Severity levels are presentation placeholders and are not calibrated to operational harm.",
        "",
    ]
    return "\n".join(lines)


def main() -> None:
    truth = load_ground_truth(DATA / "ground_truth.csv")
    known_signals = list(SignalCollectionSource(DATA / "known_signals"))
    calibration_split = split_data(known_signals, truth)
    detector = fit_detector_v2(
        calibration_split["calibration_idle"],
        calibration_split["calibration_legitimate"],
        calibration_split["calibration_jamming"],
    )

    abnormal_signals = list(SignalCollectionSource(DATA / "abnormal_signals"))
    ambiguous_signals = list(SignalCollectionSource(DATA / "ambiguous_signals"))
    signals = sorted(
        known_signals + abnormal_signals + ambiguous_signals,
        key=lambda signal: signal.sequence_number,
    )
    flags = load_module1_flags_reference(DATA / "module1_flags_reference.csv")
    if len(signals) != len(truth) or len(signals) != len(flags):
        raise RuntimeError("signals, ground truth, and flag reference must have equal counts")

    split = split_data(signals, truth)
    audit_rows, audit_markdown = feature_audit(signals, truth)
    REPORTS.mkdir(exist_ok=True)
    audit_csv = REPORTS / "real_feature_audit.csv"
    with audit_csv.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(audit_rows[0]))
        writer.writeheader()
        writer.writerows(audit_rows)
    (REPORTS / "real_feature_audit.md").write_text(audit_markdown, encoding="utf-8")
    (REPORTS / "real_eval.md").write_text(
        evaluation_report(signals, truth, flags, split, detector), encoding="utf-8"
    )

    classifier = RealThreatClassifierV2(detector)
    counts = Counter(classification_name(classifier.classify(signal).classification) for signal in signals)
    print(f"Validated signals: {len(signals)}")
    print(
        "Calibration source: data/real/module1_signals_clean/known_signals only "
        f"({len(known_signals)} files, ordered by sequence number)"
    )
    print(
        "Calibration rows: "
        f"idle first half={len(calibration_split['calibration_idle'])}, "
        f"legitimate first half={len(calibration_split['calibration_legitimate'])}, "
        f"known jammer rows={len(calibration_split['calibration_jamming'])}"
    )
    print(
        "Evaluation-only rows loaded after fitting: "
        f"abnormal_signals={len(abnormal_signals)}, ambiguous_signals={len(ambiguous_signals)}"
    )
    print(
        "Split: "
        f"calibration normal={len(split['calibration_idle']) + len(split['calibration_legitimate'])}, "
        f"calibration jamming={len(split['calibration_jamming'])}, "
        f"validation normal={len(split['validation_idle']) + len(split['validation_legitimate'])}, "
        f"unseen jamming={len(split['unseen_jamming'])}"
    )
    print(f"Rule thresholds: {asdict(detector.rules.thresholds)}")
    print(f"Anomaly threshold: {detector.anomaly.threshold:.6f}")
    print(f"All-record output counts: {dict(counts)}")
    print("Wrote reports/real_feature_audit.md")
    print("Wrote reports/real_feature_audit.csv")
    print("Wrote reports/real_eval.md")


if __name__ == "__main__":
    main()

"""Evaluate the frozen raw-measurement classifier and write the real-data report."""

from __future__ import annotations

import json
import statistics
import sys
import time
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.calibrate_real import build_configuration, split_known_signals
from src.baseline import Baseline
from src.classifier import ThreatClassifier, build_classifier
from src.real_data import Signal, load_stream
from src.rule_engine import build_rule_engine
from src.scoring_data import load_ground_truth

DATA_ROOT = ROOT / "data" / "real" / "module1_signals_clean"
REPORT_PATH = ROOT / "reports" / "real_eval.md"


def classify_many(classifier: ThreatClassifier, signals: list[Signal]):
    return [classifier.classify(signal) for signal in signals]


def confusion(signals, outputs, truth):
    matrix = {expected: Counter() for expected in ("NORMAL", "JAMMING")}
    for signal, output in zip(signals, outputs, strict=True):
        if signal.observation_id != output.observation_id:
            raise AssertionError("scoring index mismatch")
        matrix[truth[signal.observation_id]["expected_class"]][output.classification] += 1
    return matrix


def matrix_lines(matrix):
    lines = ["| Expected | NORMAL | JAMMING | UNKNOWN_ANOMALY |", "|---|---:|---:|---:|"]
    for expected in ("NORMAL", "JAMMING"):
        row = matrix[expected]
        lines.append(f"| {expected} | {row['NORMAL']} | {row['JAMMING']} | {row['UNKNOWN_ANOMALY']} |")
    return lines


def rate(part, whole):
    return part / whole if whole else 0.0


def group_lines(signals, outputs, truth):
    normal = {"idle": [0, 0], "legit_ook": [0, 0]}
    jammer = {}
    for signal, output in zip(signals, outputs, strict=True):
        row = truth[signal.observation_id]
        if row["normal_kind"] in normal:
            values = normal[row["normal_kind"]]
            values[1] += 1
            values[0] += output.classification != "NORMAL"
        if row["jammer_type"]:
            values = jammer.setdefault(row["jammer_type"], [0, 0, 0])
            values[2] += 1
            values[0] += output.classification == "JAMMING"
            values[1] += output.classification != "NORMAL"
    lines = ["| Group | Metric | Result |", "|---|---|---:|"]
    for name, (false_alarms, total) in normal.items():
        if total:
            lines.append(f"| {name} | false-positive rate | {false_alarms}/{total} ({rate(false_alarms,total):.2%}) |")
    for name, (rule_hits, non_normal, total) in sorted(jammer.items()):
        lines.append(f"| {name} | rule-only recall | {rule_hits}/{total} ({rate(rule_hits,total):.2%}) |")
        lines.append(f"| {name} | rule + anomaly recall | {non_normal}/{total} ({rate(non_normal,total):.2%}) |")
    return lines


def chronological_sets(known, truth):
    split = split_known_signals(known, truth)
    first = sorted((item for group in split.calibration.values() for item in group), key=lambda item: item.sequence_number)
    second = sorted((item for group in split.validation.values() for item in group), key=lambda item: item.sequence_number)
    return first, second


def leave_one_out(known, abnormal, truth, configuration):
    split = split_known_signals(known, truth)
    rows = []
    for held in ("CARRIER", "PULSED_50_50"):
        retained = "PULSED_50_50" if held == "CARRIER" else "CARRIER"
        idle = split.calibration["idle"]
        legitimate = split.calibration["legit_ook"]
        jamming = split.calibration[retained]
        t_snr = (max(x.snr_db for x in idle) + min(x.snr_db for x in legitimate + jamming)) / 2
        t_bw = (max(x.occupied_bw_khz for x in jamming) + min(x.occupied_bw_khz for x in legitimate)) / 2
        classifier = ThreatClassifier(Baseline.from_config(configuration), build_rule_engine(t_snr, t_bw))
        selected = [x for x in known if truth[x.observation_id]["jammer_type"] == held]
        detected = sum(x.classification != "NORMAL" for x in classify_many(classifier, selected))
        rows.append((held, retained, t_snr, t_bw, detected, len(selected)))
    classifier = build_classifier()
    for held in ("PULSED_5_95", "RANDOM_BURSTS"):
        selected = [x for x in abnormal if truth[x.observation_id]["jammer_type"] == held]
        detected = sum(x.classification != "NORMAL" for x in classify_many(classifier, selected))
        rows.append((held, "CARRIER + PULSED_50_50", 25.8, 137.5, detected, len(selected)))
    return rows


def write_report():
    truth = load_ground_truth(DATA_ROOT / "ground_truth.csv")
    known = list(load_stream(DATA_ROOT / "known_signals"))
    abnormal = list(load_stream(DATA_ROOT / "abnormal_signals"))
    ambiguous = list(load_stream(DATA_ROOT / "ambiguous_signals"))
    configuration, _ = build_configuration(DATA_ROOT)
    classifier = build_classifier()
    calibration, validation = chronological_sets(known, truth)
    sets = [
        ("Calibration", calibration, classify_many(classifier, calibration)),
        ("Validation", validation, classify_many(classifier, validation)),
        ("Unseen abnormal", abnormal, classify_many(classifier, abnormal)),
    ]
    known_outputs = classify_many(classifier, known)
    abnormal_outputs = sets[2][2]
    ambiguous_outputs = classify_many(classifier, ambiguous)
    all_signals = known + abnormal + ambiguous
    all_outputs = known_outputs + abnormal_outputs + ambiguous_outputs
    started = time.perf_counter()
    timed = classify_many(classifier, all_signals)
    wall_ms = (time.perf_counter() - started) * 1000
    latencies = sorted(x.processing_ms for x in timed)
    p95 = latencies[max(0, int(0.95 * len(latencies)) - 1)]
    thresholds = configuration["thresholds"]
    states = configuration["normal_states"]
    provenance = configuration["provenance"]
    lines = [
        "# Real Module 1 measurement evaluation", "",
        "This report evaluates the frozen measurement-only Module 2 pipeline on the 2026-10-23 recording.",
        "Reference metadata is joined only after classification; expected and actual values are compared at the same observation index.", "",
        "## Thresholds and provenance", "",
        f"- Source: {provenance['source']}", f"- Split: {provenance['split']}",
        f"- Date: {provenance['date']}", f"- Script: {provenance['script']}",
        f"- T_SNR: {thresholds['T_SNR']:.6f} dB", f"- T_BW: {thresholds['T_BW']:.6f} kHz",
        f"- Idle anomaly limit: {states['idle']['anomaly_limit']:.6f}",
        f"- Legitimate OOK anomaly limit: {states['legit_ook']['anomaly_limit']:.6f}", "",
    ]
    for title, signals, outputs in sets:
        lines.extend([f"## {title}", ""] + matrix_lines(confusion(signals, outputs, truth)) + [""] + group_lines(signals, outputs, truth) + [""])
    lines.extend(["## Leave-one-jammer-type-out", "", "| Held out | Threshold training jammer | T_SNR | T_BW | Non-normal recall |", "|---|---|---:|---:|---:|"])
    for held, retained, t_snr, t_bw, detected, total in leave_one_out(known, abnormal, truth, configuration):
        lines.append(f"| {held} | {retained} | {t_snr:.3f} | {t_bw:.3f} | {detected}/{total} ({rate(detected,total):.2%}) |")
    lines.extend(["", "## Label-quality rows reported separately", ""])
    for note in ("signal present but labelled none (ambient signal or label timing); inspect only", "labelled none inside a jammer phase (jammer off or label timing)"):
        selected = [(signal, output) for signal, output in zip(all_signals, all_outputs, strict=True) if truth[signal.observation_id]["label_quality_note"] == note]
        lines.extend([f"### {note} ({len(selected)})", ""])
        lines.extend(f"- sequence {signal.sequence_number}, {signal.observation_id}: {output.classification}" for signal, output in selected)
        lines.append("")
    lines.extend([
        "## Latency", "", f"- classify() mean: {statistics.fmean(latencies):.4f} ms",
        f"- classify() p95: {p95:.4f} ms", f"- timed loop mean: {wall_ms / len(timed):.4f} ms per record",
        f"- NFR01 classify p95 under 50 ms: {p95 < 50}", "", "## Decision and limits", "",
        "The retired four-feature path is not used. R1 identifies a strong narrowband measurement; otherwise the nearest-state anomaly score decides between unknown anomaly and normal.", "",
        "This evidence comes from one session and one legitimate device. The measured class margins are wide and may not transfer to other radios or environments. R1 could flag a narrowband legitimate device and may miss a wideband jammer. Severity cut-offs are the 33rd/66th percentiles of calibration-half jamming magnitudes, so with 48 captures from one session they are coarse.", "",
    ])
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text("\n".join(lines), encoding="utf-8")
    return {"calibration": len(calibration), "validation": len(validation), "unseen": len(abnormal), "ambiguous": len(ambiguous), "classify_mean_ms": statistics.fmean(latencies), "classify_p95_ms": p95}


def main():
    summary = write_report()
    print(json.dumps(summary, indent=2))
    print(f"wrote={REPORT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

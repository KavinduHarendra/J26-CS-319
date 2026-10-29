"""Advanced live replay dashboard for the single Module 2 pipeline."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import statistics
import time
from collections import Counter, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

from src.baseline import BASELINE_FEATURES
from src.classifier import (
    DEFAULT_CONFIG_PATH,
    Classification,
    DecisionTrace,
    ThreatClassifier,
    ThreatOutput,
    build_classifier,
)
from src.contracts import to_contract
from src.file_exchange import exchange_filename
from src.input_watcher import DEFAULT_INPUT_ROOT, SignalInbox
from src.output_writer import CaptureOutputWriter, DEFAULT_OUTPUT_ROOT
from src.real_data import MEASUREMENT_FIELDS, Signal, signal_to_record
from src.scoring_data import load_ground_truth


ROOT = Path(__file__).resolve().parents[1]
REFERENCE_ROOT = ROOT / "data" / "real" / "module1_signals_clean"
HEADER = "DATA: LIVE Module 1 JSON inbox. Modules 3 and 4: simulated."
INPUT_BADGE = (
    "ANALYSIS INPUT: 7 raw measurements only. Ground truth is used for scoring only."
)
RECORDING_SECONDS = 317.8
CLASSES = (
    Classification.NORMAL.value,
    Classification.JAMMING.value,
    Classification.UNKNOWN_ANOMALY.value,
)
CLASS_COLORS = {
    Classification.NORMAL.value: "green",
    Classification.JAMMING.value: "red",
    Classification.UNKNOWN_ANOMALY.value: "yellow",
    "REJECTED": "magenta",
    "WAITING": "cyan",
}


@dataclass(frozen=True, slots=True)
class ProcessedCapture:
    signal: Signal
    output: ThreatOutput
    trace: DecisionTrace
    end_to_end_ms: float
    file_name: str


@dataclass(frozen=True, slots=True)
class ScoredCapture:
    processed: ProcessedCapture
    reference: Mapping[str, str]
    matches_expected: bool
    label_lag: bool


@dataclass(frozen=True, slots=True)
class ReplayRow:
    sequence_number: int
    elapsed_s: float
    classification: str
    rule: str
    severity: str
    snr_db: float
    occupied_bw_khz: float
    spectral_flatness: float
    processing_ms: float
    expected: str
    comparison: str


class DashboardState:
    def __init__(self, total: int, speed: float, *, ascii_mode: bool = False) -> None:
        self.total = total
        self.speed = speed
        self.ascii_mode = ascii_mode
        self.paused = False
        self.full_json = False
        self.quit_requested = False
        self.received = 0
        self.classified = 0
        self.rejected = 0
        self.duplicates = 0
        self.class_counts: Counter[str] = Counter()
        self.path_counts: Counter[str] = Counter()
        self.recent: deque[ReplayRow] = deque(maxlen=14)
        self.decisions: deque[str] = deque(maxlen=120)
        self.snr_history: deque[float] = deque(maxlen=60)
        self.bw_history: deque[float] = deque(maxlen=60)
        self.scored: list[ScoredCapture] = []
        self.latest: ScoredCapture | None = None
        self.latest_trace: DecisionTrace | None = None
        self.rejection_reason: str | None = None
        self.started = time.perf_counter()

    def add(self, item: ScoredCapture) -> None:
        result = item.processed
        signal = result.signal
        output = result.output
        self.received += 1
        self.classified += 1
        self.class_counts[output.classification] += 1
        self.path_counts[result.trace.path_taken] += 1
        self.scored.append(item)
        self.latest = item
        self.latest_trace = result.trace
        self.rejection_reason = None
        self.decisions.append(output.classification)
        self.snr_history.append(signal.snr_db)
        self.bw_history.append(signal.occupied_bw_khz)
        if item.reference["expected_class"] == "UNSCORED":
            comparison = "-"
        else:
            comparison = "label lag" if item.label_lag else ("OK" if item.matches_expected else "NO")
        self.recent.append(
            ReplayRow(
                sequence_number=signal.sequence_number,
                elapsed_s=signal.elapsed_s,
                classification=output.classification,
                rule=output.triggered_rule or "-",
                severity=output.severity or "-",
                snr_db=signal.snr_db,
                occupied_bw_khz=signal.occupied_bw_khz,
                spectral_flatness=signal.spectral_flatness,
                processing_ms=output.processing_ms,
                expected=item.reference["expected_class"],
                comparison=comparison,
            )
        )

    def add_rejected(self, reason: str) -> None:
        self.received += 1
        self.rejected += 1
        self.latest = None
        self.rejection_reason = reason
        self.latest_trace = DecisionTrace.rejected(reason)

    def add_duplicates(self, count: int) -> None:
        self.duplicates += count


def process(
    signal: Signal,
    classifier: ThreatClassifier,
    writer: CaptureOutputWriter,
) -> ProcessedCapture:
    """Classify and write one capture without accepting any scoring reference."""
    started = time.perf_counter()
    output, trace = classifier.classify_with_trace(signal)
    writer.write(signal, output)
    end_to_end_ms = (time.perf_counter() - started) * 1000.0
    return ProcessedCapture(
        signal=signal,
        output=output,
        trace=trace,
        end_to_end_ms=end_to_end_ms,
        file_name=exchange_filename(signal.sequence_number, signal.observation_id, threat=True),
    )


def score(result: ProcessedCapture, truth: Mapping[str, Mapping[str, str]]) -> ScoredCapture:
    """Join scoring metadata only after processing has completed."""
    reference = truth.get(result.signal.observation_id)
    if reference is None:
        reference = {
            "folder": "",
            "expected_class": "UNSCORED",
            "normal_kind": "",
            "jammer_type": "",
            "label_quality_note": "",
        }
    note = reference["label_quality_note"]
    return ScoredCapture(
        processed=result,
        reference=reference,
        matches_expected=result.output.classification == reference["expected_class"],
        label_lag=bool(note),
    )


def _p95(values: list[float]) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[max(0, math.ceil(0.95 * len(ordered)) - 1)]


def _rate(numerator: int, denominator: int) -> str:
    return f"{100.0 * numerator / denominator:.2f}%" if denominator else "n/a"


def calculate_summary(rows: list[ScoredCapture]) -> dict[str, Any]:
    known = [item for item in rows if item.reference["folder"] == "known_signals"]
    matrix = {
        expected: {
            predicted: sum(
                item.reference["expected_class"] == expected
                and item.processed.output.classification == predicted
                for item in known
            )
            for predicted in CLASSES
        }
        for expected in (Classification.NORMAL.value, Classification.JAMMING.value)
    }

    def normal_fpr(kind: str) -> tuple[int, int]:
        selected = [
            item
            for item in known
            if item.reference["expected_class"] == Classification.NORMAL.value
            and item.reference["normal_kind"] == kind
        ]
        return (
            sum(
                item.processed.output.classification != Classification.NORMAL.value
                for item in selected
            ),
            len(selected),
        )

    jammer_recall: dict[str, tuple[int, int]] = {}
    jammer_types = sorted(
        {
            item.reference["jammer_type"]
            for item in rows
            if item.reference["jammer_type"]
            and item.reference["expected_class"] == Classification.JAMMING.value
        }
    )
    for jammer in jammer_types:
        selected = [
            item
            for item in rows
            if item.reference["jammer_type"] == jammer
            and item.reference["expected_class"] == Classification.JAMMING.value
        ]
        jammer_recall[jammer] = (
            sum(
                item.processed.output.classification == Classification.JAMMING.value
                for item in selected
            ),
            len(selected),
        )

    abnormal = [item for item in rows if item.reference["folder"] == "abnormal_signals"]
    abnormal_counts = Counter(item.processed.output.classification for item in abnormal)
    transition = [
        item
        for item in rows
        if item.reference["label_quality_note"].startswith("signal present")
    ]
    idle_inside = [
        item
        for item in rows
        if item.reference["label_quality_note"].startswith("labelled none")
    ]
    classify_times = [item.processed.output.processing_ms for item in rows]
    end_times = [item.processed.end_to_end_ms for item in rows]
    elapsed = sum(end_times) / 1000.0
    mismatches = [
        (
            item.processed.signal.observation_id,
            item.reference["expected_class"],
            item.processed.output.classification,
        )
        for item in rows
        if item.reference["expected_class"] != "UNSCORED"
        and not item.label_lag
        and not item.matches_expected
    ]
    return {
        "matrix": matrix,
        "idle_fpr": normal_fpr("idle"),
        "legit_fpr": normal_fpr("legit_ook"),
        "jammer_recall": jammer_recall,
        "abnormal_counts": dict(abnormal_counts),
        "abnormal_total": len(abnormal),
        "abnormal_detected": sum(
            item.processed.output.classification != Classification.NORMAL.value
            for item in abnormal
        ),
        "abnormal_r1": sum(item.processed.trace.path_taken == "R1" for item in abnormal),
        "abnormal_anomaly": sum(
            item.processed.trace.path_taken == "ANOMALY" for item in abnormal
        ),
        "transition": [
            (item.processed.signal.observation_id, item.processed.output.classification)
            for item in transition
        ],
        "idle_inside": [
            (item.processed.signal.observation_id, item.processed.output.classification)
            for item in idle_inside
        ],
        "classify_mean_ms": statistics.fmean(classify_times) if classify_times else 0.0,
        "classify_p95_ms": _p95(classify_times),
        "classify_max_ms": max(classify_times, default=0.0),
        "end_mean_ms": statistics.fmean(end_times) if end_times else 0.0,
        "end_p95_ms": _p95(end_times),
        "end_max_ms": max(end_times, default=0.0),
        "throughput": len(rows) / elapsed if elapsed else 0.0,
        "path_counts": dict(Counter(item.processed.trace.path_taken for item in rows)),
        "mismatches": mismatches,
    }


def print_summary(summary: dict[str, Any]) -> None:
    print("\n=== FINAL SUMMARY ===")
    print("Known-signals confusion matrix (rows expected, columns output)")
    print("expected,NORMAL,JAMMING,UNKNOWN_ANOMALY")
    for expected, values in summary["matrix"].items():
        print(expected + "," + ",".join(str(values[name]) for name in CLASSES))
    idle_fp, idle_total = summary["idle_fpr"]
    legit_fp, legit_total = summary["legit_fpr"]
    print(f"idle_false_positive_rate={idle_fp}/{idle_total} ({_rate(idle_fp, idle_total)})")
    print(
        f"legit_ook_false_positive_rate={legit_fp}/{legit_total} "
        f"({_rate(legit_fp, legit_total)})"
    )
    for jammer, (hits, total) in summary["jammer_recall"].items():
        print(f"recall_{jammer}={hits}/{total} ({_rate(hits, total)})")
    print(
        f"abnormal_not_normal={summary['abnormal_detected']}/{summary['abnormal_total']} "
        f"({_rate(summary['abnormal_detected'], summary['abnormal_total'])}) "
        f"classes={summary['abnormal_counts']} r1={summary['abnormal_r1']} "
        f"anomaly={summary['abnormal_anomaly']}"
    )
    print(f"transition_rows_4={summary['transition']}")
    print(f"idle_looking_inside_jammer_rows_7={summary['idle_inside']}")
    print(f"path_counts={summary['path_counts']}")
    print(f"non_label_lag_mismatches={summary['mismatches']}")
    print(
        f"classify_latency_ms mean={summary['classify_mean_ms']:.4f} "
        f"p95={summary['classify_p95_ms']:.4f} max={summary['classify_max_ms']:.4f} "
        f"target_p95_lt_50={summary['classify_p95_ms'] < 50.0}"
    )
    print(
        f"end_to_end_latency_ms mean={summary['end_mean_ms']:.4f} "
        f"p95={summary['end_p95_ms']:.4f} max={summary['end_max_ms']:.4f} "
        f"throughput_per_second={summary['throughput']:.2f}"
    )


def _status(value: bool | None, ascii_mode: bool) -> str:
    if value is None:
        return "--"
    if value:
        return "OK" if ascii_mode else "✓"
    return "NO" if ascii_mode else "✗"


def _bar(value: float, limit: float, ascii_mode: bool, width: int = 12) -> str:
    ratio = value / limit if limit else 0.0
    filled = min(width, max(0, round(ratio * width)))
    marker = "#" if ascii_mode else "█"
    return marker * filled + "-" * (width - filled)


def _spark(values: list[float], ascii_mode: bool, width: int = 60) -> str:
    if not values:
        return "-"
    values = values[-width:]
    low, high = min(values), max(values)
    if math.isclose(low, high):
        return ("#" if ascii_mode else "▄") * len(values)
    chars = " .:-=+*#" if ascii_mode else "▁▂▃▄▅▆▇█"
    return "".join(
        chars[min(len(chars) - 1, int((value - low) / (high - low) * (len(chars) - 1)))]
        for value in values
    )


def _progress(value: float, total: float, ascii_mode: bool, width: int = 32) -> str:
    ratio = min(1.0, max(0.0, value / total if total else 0.0))
    filled = round(ratio * width)
    marker = "#" if ascii_mode else "█"
    return marker * filled + "-" * (width - filled)


def _json_renderable(payload: Mapping[str, Any]):
    from rich.syntax import Syntax

    return Syntax(
        json.dumps(payload, indent=2, ensure_ascii=False, default=str),
        "json",
        word_wrap=True,
    )


def _summary_for_state(state: DashboardState) -> dict[str, Any]:
    return calculate_summary(state.scored)


def render_dashboard(
    state: DashboardState,
    writer_stats: Mapping[str, Any],
    classifier: ThreatClassifier,
    *,
    layout_mode: str = "auto",
    terminal_width: int = 120,
    terminal_height: int = 40,
):
    """Build a Rich renderable; safe for live, tests, and offscreen snapshots."""
    from rich.columns import Columns
    from rich.console import Group
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    resolved_layout = layout_mode
    if resolved_layout == "auto":
        resolved_layout = (
            "full" if terminal_width >= 160 and terminal_height >= 45 else "compact"
        )
    full_json = state.full_json and resolved_layout == "full"
    latest = state.latest
    waiting = latest is None and state.rejection_reason is None
    trace = state.latest_trace or DecisionTrace.rejected("waiting for the first capture")
    signal = latest.processed.signal if latest else None
    output = latest.processed.output if latest else None
    elapsed_s = signal.elapsed_s if signal else 0.0
    progress_text = Text()
    progress_text.append(HEADER + "\n", style="bold cyan")
    progress_text.append(INPUT_BADGE + "\n", style="bold")
    progress_text.append(
        f"Input [{_progress(elapsed_s, RECORDING_SECONDS, state.ascii_mode)}] "
        f"elapsed={elapsed_s:.1f}s  captures={state.classified}  "
        f"delay={state.speed:.3f}s  paused={state.paused}"
    )
    header = Panel(progress_text, title="Module 2 Threat Intelligence", border_style="cyan")

    current_class = (
        state.latest.processed.output.classification
        if state.latest
        else ("WAITING" if waiting else "REJECTED")
    )
    current_severity = (
        state.latest.processed.output.severity or "NONE" if state.latest else "NONE"
    )
    current_rule = (
        state.latest.processed.output.triggered_rule or "NONE"
        if state.latest
        else "NONE"
    )
    status_text = Text(justify="center")
    status_text.append(f"\n{current_class}\n", style=f"bold {CLASS_COLORS[current_class]}")
    status_text.append(
        f"Severity: {current_severity}    Triggered rule: {current_rule}",
        style="bold",
    )
    status_panel = Panel(
        status_text,
        title="CURRENT THREAT STATUS",
        border_style=CLASS_COLORS[current_class],
        padding=(0, 2),
    )

    now = time.monotonic()
    flow = Table.grid(expand=True)
    flow.add_row("Module 1 (live inbox)", "->", "Module 2", "->", "Module 3 + Module 4")
    flow.add_row(
        f"received {state.received}",
        "",
        f"classified {state.classified} | rejected {state.rejected}",
        "",
        f"duplicates {state.duplicates + writer_stats.get('duplicates', 0)} | missing {len(writer_stats.get('missing_sequence_numbers', []))}",
    )
    for recipient in ("module3", "module4"):
        last_name = writer_stats.get("last_file_name", {}).get(recipient) or "-"
        last_time = writer_stats.get("last_write_time", {}).get(recipient)
        age = f"{now - last_time:.1f}s" if last_time is not None else "-"
        flow.add_row(
            recipient,
            "",
            f"files {writer_stats.get('files_written', {}).get(recipient, 0)}",
            "",
            f"last {last_name} | age {age}",
        )
    flow_panel = Panel(flow, title="Data flow")

    trace_table = Table(expand=True, show_lines=False)
    trace_table.add_column("Result", width=6)
    trace_table.add_column("Step", ratio=1, overflow="fold")
    trace_table.add_column("Expression / actual / threshold", ratio=3, overflow="fold")
    for step in trace.steps:
        style = "green" if step.passed else ("red" if step.passed is False else "dim")
        details = (
            f"{step.expression}; actual={dict(step.actual_values)}; "
            f"thresholds={dict(step.thresholds)}"
        )
        trace_table.add_row(_status(step.passed, state.ascii_mode), step.name, details, style=style)
    displayed_path = "WAITING" if waiting else trace.path_taken
    trace_table.add_row("PATH", displayed_path, f"nearest={trace.nearest_state or '-'}; skipped={list(trace.skipped_rules) or '-'}")
    trace_table.add_row("WHY", trace.plain_english, "")
    trace_panel = Panel(trace_table, title="Decision trace", border_style=CLASS_COLORS.get(trace.path_taken, "cyan"))

    distance_table = Table(expand=True)
    distance_table.add_column("Feature", overflow="fold")
    for state_name in ("idle", "legit_ook"):
        marker = " *nearest*" if trace.nearest_state == state_name else ""
        distance_table.add_column(f"{state_name}{marker}", overflow="fold")
    for feature in BASELINE_FEATURES:
        cells = []
        for state_name in ("idle", "legit_ook"):
            distance = trace.per_state_distances.get(state_name, {}).get(feature)
            limit = trace.state_limits.get(state_name)
            cells.append(
                "-"
                if distance is None or limit is None
                else f"{distance:.2f}/{limit:.2f} {_bar(distance, limit, state.ascii_mode)}"
            )
        distance_table.add_row(feature, *cells)
    distance_panel = Panel(
        distance_table,
        title="Distance from each normal state (units of spread)",
    )

    if signal is None:
        display_status = "WAITING" if waiting else "REJECTED"
        incoming_payload: Mapping[str, Any] = {"status": display_status, "reason": state.rejection_reason or "waiting for a JSON capture"}
        outgoing_payload: Mapping[str, Any] = {"classification": display_status, "evidence": [trace.plain_english]}
    elif full_json:
        incoming_payload = signal_to_record(signal)
        outgoing_payload = to_contract(output, recipient="module3").model_dump(mode="json")
    else:
        incoming_payload = {
            "observation_id": signal.observation_id,
            "sequence_number": signal.sequence_number,
            "timestamp": signal.timestamp.isoformat(timespec="milliseconds"),
            "measurements": {name: getattr(signal, name) for name in MEASUREMENT_FIELDS},
        }
        outgoing_payload = {
            "classification": output.classification,
            "severity": output.severity,
            "triggered_rule": output.triggered_rule,
            "abnormal_features": output.abnormal_features,
            "statistical_deviation": {
                "description": "distance from the nearest normal state (units of spread)",
                "values": output.statistical_deviation,
            },
            "evidence": output.evidence,
            "processing_ms": output.processing_ms,
        }
    output_class = output.classification if output else ("WAITING" if waiting else "REJECTED")
    json_panels = Columns(
        [
            Panel(_json_renderable(incoming_payload), title="Incoming JSON", expand=True),
            Panel(
                _json_renderable(outgoing_payload),
                title="Outgoing JSON",
                border_style=CLASS_COLORS[output_class],
                expand=True,
            ),
        ],
        equal=True,
        expand=True,
    )

    rules = Table.grid(expand=True)
    rules.add_row(
        "R1 Narrowband strong signal",
        f"snr_db >= {classifier.rules.t_snr:.1f}; 0 < occupied_bw_khz <= {classifier.rules.t_bw:.1f}; fired {state.path_counts['R1']}",
    )
    rules.add_row(
        "Anomaly engine",
        f"idle limit {classifier.baseline.idle.anomaly_limit:.2f}; legit limit {classifier.baseline.legitimate.anomaly_limit:.2f}; flagged {state.path_counts['ANOMALY']}",
    )
    rules.add_row("Normal", f"count {state.path_counts['NORMAL']}")
    rules.add_row("Severity", "magnitude percentile cut-offs (calibration-half jamming)")
    rules_panel = Panel(rules, title="Rule book")

    feed = Table(expand=True)
    columns = ("Seq", "Elapsed", "Class", "Rule", "Sev", "SNR", "BW", "Flat", "ms", "Expected", "Match")
    for name in columns:
        feed.add_column(name, overflow="fold", no_wrap=True)
    for row in state.recent:
        comparison = row.comparison
        if comparison == "OK" and not state.ascii_mode:
            comparison = "✓"
        elif comparison == "NO" and not state.ascii_mode:
            comparison = "✗"
        feed.add_row(
            str(row.sequence_number), f"{row.elapsed_s:.1f}",
            f"[{CLASS_COLORS[row.classification]}]{row.classification}[/]", row.rule,
            row.severity, f"{row.snr_db:.1f}", f"{row.occupied_bw_khz:.1f}",
            f"{row.spectral_flatness:.3f}", f"{row.processing_ms:.3f}",
            row.expected, comparison,
        )
    feed_panel = Panel(feed, title="Live feed — last 14 signals")

    summary = _summary_for_state(state)
    scoreboard = Table.grid(expand=True)
    scoreboard.add_row("Class counts", str(dict(state.class_counts)))
    scoreboard.add_row("Confusion", str(summary["matrix"]))
    scoreboard.add_row("Idle FPR", f"{summary['idle_fpr'][0]}/{summary['idle_fpr'][1]} ({_rate(*summary['idle_fpr'])})")
    scoreboard.add_row("Legit OOK FPR", f"{summary['legit_fpr'][0]}/{summary['legit_fpr'][1]} ({_rate(*summary['legit_fpr'])})")
    scoreboard.add_row("Jammer recall", str({key: f"{value[0]}/{value[1]}" for key, value in summary["jammer_recall"].items()}))
    scoreboard.add_row(
        "Abnormal not NORMAL",
        f"{summary['abnormal_detected']}/{summary['abnormal_total']} | R1 {summary['abnormal_r1']} | anomaly {summary['abnormal_anomaly']}",
    )
    scoreboard_panel = Panel(scoreboard, title="Scoreboard")

    latency = Table.grid(expand=True)
    latency.add_row("classify mean / p95 / max", f"{summary['classify_mean_ms']:.3f} / {summary['classify_p95_ms']:.3f} / {summary['classify_max_ms']:.3f} ms")
    latency.add_row("end-to-end mean / p95 / max", f"{summary['end_mean_ms']:.3f} / {summary['end_p95_ms']:.3f} / {summary['end_max_ms']:.3f} ms")
    latency.add_row("throughput", f"{summary['throughput']:.1f}/s")
    latency.add_row("NFR01 classify p95 < 50 ms", "PASS" if summary["classify_p95_ms"] < 50.0 else "FAIL")
    latency_panel = Panel(latency, title="Latency")

    timeline = Text()
    for decision in state.decisions:
        timeline.append("#" if state.ascii_mode else "■", style=CLASS_COLORS[decision])
    timeline.append("\nSNR  " + _spark(list(state.snr_history), state.ascii_mode))
    timeline.append(f"  T_SNR={classifier.rules.t_snr:.1f}")
    timeline.append("\nBW   " + _spark(list(state.bw_history), state.ascii_mode))
    timeline.append(f"  T_BW={classifier.rules.t_bw:.1f}")
    timeline_panel = Panel(timeline, title="Timeline — 120 decisions; 60-signal sparklines")

    config_hash = hashlib.sha256(DEFAULT_CONFIG_PATH.read_bytes()).hexdigest()[:12]
    keys = "keys: space pause/resume | +/- speed | j JSON | s snapshot | q quit"
    if os.name != "nt":
        keys += " (interactive keys available on Windows)"
    footer = Panel(
        f"{keys}\nbaseline={classifier.baseline.version} | thresholds={DEFAULT_CONFIG_PATH.name} | sha256={config_hash}",
        title="Controls",
    )

    if resolved_layout == "compact":
        compact_flow = Table.grid(expand=True)
        compact_flow.add_column(ratio=1, overflow="fold")
        compact_flow.add_column(ratio=2, overflow="fold")
        compact_flow.add_row(
            "Received / classified / rejected",
            f"{state.received} / {state.classified} / {state.rejected}",
        )
        compact_flow.add_row(
            "Duplicates / missing",
            f"{state.duplicates + writer_stats.get('duplicates', 0)} / {len(writer_stats.get('missing_sequence_numbers', []))}",
        )
        for recipient in ("module3", "module4"):
            compact_flow.add_row(
                recipient,
                f"{writer_stats.get('files_written', {}).get(recipient, 0)} | "
                f"{writer_stats.get('last_file_name', {}).get(recipient) or '-'}",
            )

        compact_trace = Table.grid(expand=True)
        compact_trace.add_column(ratio=1, overflow="fold")
        compact_trace.add_column(ratio=2, overflow="fold")
        strong_step = next((step for step in trace.steps if step.name == "Strong signal"), None)
        narrow_step = next((step for step in trace.steps if step.name == "Narrow bandwidth"), None)
        anomaly_step = next((step for step in trace.steps if step.name == "Nearest-state anomaly"), None)
        compact_trace.add_row(
            "Strong / narrow",
            f"{_status(strong_step.passed if strong_step else None, state.ascii_mode)} / "
            f"{_status(narrow_step.passed if narrow_step else None, state.ascii_mode)}",
        )
        compact_trace.add_row(
            "Path / nearest",
            f"{displayed_path} / {trace.nearest_state or '-'}",
        )
        compact_trace.add_row(
            "Anomaly / skipped",
            f"{_status(anomaly_step.passed if anomaly_step else None, state.ascii_mode)} / "
            f"{','.join(trace.skipped_rules) or '-'}",
        )
        compact_trace.add_row("Why", trace.plain_english)

        compact_rule = Table.grid(expand=True)
        compact_rule.add_column(ratio=1, overflow="fold")
        compact_rule.add_column(ratio=3, overflow="fold")
        compact_rule.add_row(
            "R1",
            f"SNR >= {classifier.rules.t_snr:.1f}; 0 < BW <= {classifier.rules.t_bw:.1f}; "
            f"fired {state.path_counts['R1']}",
        )
        compact_rule.add_row(
            "Anomaly",
            f"limits {classifier.baseline.idle.anomaly_limit:.2f} / "
            f"{classifier.baseline.legitimate.anomaly_limit:.2f}; "
            f"flagged {state.path_counts['ANOMALY']}",
        )
        compact_rule.add_row("Normal", str(state.path_counts["NORMAL"]))
        compact_rule.add_row("Severity", "percentile-calibrated")

        compact_distances = Table(expand=True, box=None, padding=(0, 1))
        compact_distances.add_column("Feature", overflow="fold")
        compact_distances.add_column("Idle", justify="right", overflow="fold")
        compact_distances.add_column("Legit", justify="right", overflow="fold")
        for feature in BASELINE_FEATURES:
            idle_value = trace.per_state_distances.get("idle", {}).get(feature)
            legit_value = trace.per_state_distances.get("legit_ook", {}).get(feature)
            compact_distances.add_row(
                feature,
                "-" if idle_value is None else f"{idle_value:.2f}/{trace.state_limits['idle']:.2f}",
                "-" if legit_value is None else f"{legit_value:.2f}/{trace.state_limits['legit_ook']:.2f}",
            )

        compact_io = Table.grid(expand=True)
        compact_io.add_column(ratio=1, overflow="fold")
        compact_io.add_column(ratio=4, overflow="fold")
        if signal is None or output is None:
            compact_io.add_row("Input", state.rejection_reason or "waiting for a JSON capture")
            compact_io.add_row("Output", "WAITING" if waiting else "REJECTED")
        else:
            compact_io.add_row(
                "Input",
                f"{signal.observation_id} | seq {signal.sequence_number} | {signal.timestamp.time()}",
            )
            compact_io.add_row(
                "Output",
                f"{output.classification} | severity {output.severity or '-'} | "
                f"rule {output.triggered_rule or '-'}",
            )
            compact_io.add_row(
                "Raw values",
                f"peak {signal.peak_db:.1f} | noise {signal.noise_db:.1f} | "
                f"SNR {signal.snr_db:.1f} | power {signal.band_power_dbfs:.1f}",
            )
            compact_io.add_row(
                "Spectrum",
                f"freq {signal.peak_freq_mhz:.3f} | BW {signal.occupied_bw_khz:.1f} | "
                f"flat {signal.spectral_flatness:.3f}",
            )
            compact_io.add_row("Evidence", "; ".join(output.evidence))

        compact_score = Table.grid(expand=True)
        compact_score.add_column(ratio=2, overflow="fold")
        compact_score.add_column(ratio=3, overflow="fold")
        compact_score.add_row("Classes", str(dict(state.class_counts)))
        compact_score.add_row(
            "NFR01 / throughput",
            f"{'PASS' if summary['classify_p95_ms'] < 50.0 else 'FAIL'} / "
            f"{summary['throughput']:.1f}/s",
        )
        compact_score.add_row(
            "FPR idle / legit",
            f"{_rate(*summary['idle_fpr'])} / {_rate(*summary['legit_fpr'])}",
        )
        compact_score.add_row(
            "Recall",
            str({key: _rate(*value) for key, value in summary["jammer_recall"].items()}),
        )
        compact_score.add_row(
            "Latency mean / p95 / max",
            f"{summary['classify_mean_ms']:.2f} / {summary['classify_p95_ms']:.2f} / "
            f"{summary['classify_max_ms']:.2f} ms",
        )

        compact_feed = Table(expand=True, padding=(0, 1))
        for name in ("Seq", "Class", "Rule", "SNR", "BW", "Expected", "Check"):
            compact_feed.add_column(name, overflow="fold")
        visible_rows = 3 if terminal_height < 38 else 5
        for row in list(state.recent)[-visible_rows:]:
            compact_feed.add_row(
                str(row.sequence_number), row.classification, row.rule,
                f"{row.snr_db:.1f}", f"{row.occupied_bw_khz:.1f}",
                row.expected, row.comparison,
            )

        compact_timeline = Text()
        for decision in state.decisions:
            compact_timeline.append(
                "#" if state.ascii_mode else "■", style=CLASS_COLORS[decision]
            )
        compact_timeline.append(
            f"  SNR {_spark(list(state.snr_history), state.ascii_mode, 24)} "
            f"({classifier.rules.t_snr:.1f})  BW "
            f"{_spark(list(state.bw_history), state.ascii_mode, 24)} "
            f"({classifier.rules.t_bw:.1f})"
        )
        compact_footer_text = Text()
        compact_footer_text.append_text(compact_timeline)
        compact_footer_text.append(
            f"\n{keys} | baseline={classifier.baseline.version} | "
            f"{DEFAULT_CONFIG_PATH.name} sha256={config_hash}"
        )
        compact_footer = Panel(
            compact_footer_text,
            title="Timeline / controls",
            padding=(0, 1),
        )

        compact_layout = Layout(name="root")
        feed_height = 5 if terminal_height < 38 else 8
        compact_layout.split_column(
            Layout(header, name="header", size=5),
            Layout(status_panel, name="status", size=5),
            Layout(name="body", ratio=1),
            Layout(
                Panel(compact_feed, title="Live feed — latest signals", padding=(0, 1)),
                name="feed",
                size=feed_height,
            ),
            Layout(compact_footer, name="footer", size=4),
        )
        compact_layout["body"].split_row(
            Layout(name="left", ratio=1),
            Layout(name="center", ratio=1),
            Layout(name="right", ratio=1),
        )
        compact_layout["left"].split_column(
            Layout(Panel(compact_flow, title="Data flow", padding=(0, 1))),
            Layout(
                Panel(compact_distances, title="Distances: spread / limit", padding=(0, 1))
            ),
        )
        compact_layout["center"].split_column(
            Layout(Panel(compact_trace, title="Decision trace", padding=(0, 1))),
            Layout(Panel(compact_io, title="Current input / output", padding=(0, 1))),
        )
        compact_layout["right"].split_column(
            Layout(Panel(compact_rule, title="Rule book", padding=(0, 1))),
            Layout(
                Panel(compact_score, title="Scoreboard / latency", padding=(0, 1))
            ),
        )
        return compact_layout
    return Group(
        header,
        status_panel,
        Columns([flow_panel, rules_panel], equal=True, expand=True),
        Columns([trace_panel, distance_panel], equal=True, expand=True),
        json_panels,
        feed_panel,
        Columns([scoreboard_panel, latency_panel], equal=True, expand=True),
        timeline_panel,
        footer,
    )


def save_snapshot(
    state: DashboardState,
    writer_stats: Mapping[str, Any],
    classifier: ThreatClassifier,
    destination: Path,
    layout_mode: str,
) -> tuple[Path, Path]:
    from rich.console import Console

    destination.mkdir(parents=True, exist_ok=True)
    sequence = state.latest.processed.signal.sequence_number if state.latest else 0
    stem = destination / f"dashboard_{sequence:06d}"
    console = Console(
        record=True,
        width=180,
        height=50,
        force_terminal=True,
        color_system="truecolor",
    )
    console.print(
        render_dashboard(
            state,
            writer_stats,
            classifier,
            layout_mode=layout_mode,
            terminal_width=180,
            terminal_height=50,
        )
    )
    svg_path = Path(str(stem) + ".svg")
    text_path = Path(str(stem) + ".txt")
    console.save_svg(str(svg_path), title="Module 2 Threat Intelligence")
    text_path.write_text(console.export_text(clear=False), encoding="utf-8")
    return svg_path, text_path


def _handle_keys(
    state: DashboardState,
    writer: CaptureOutputWriter,
    classifier: ThreatClassifier,
    snapshot_dir: Path,
    layout_mode: str,
    *,
    enabled: bool,
) -> None:
    if not enabled or os.name != "nt":
        return
    import msvcrt

    while msvcrt.kbhit():
        key = msvcrt.getwch().lower()
        if key == " ":
            state.paused = not state.paused
        elif key == "+":
            state.speed = max(0.0, state.speed / 2.0)
        elif key == "-":
            state.speed = 0.05 if state.speed == 0.0 else min(10.0, state.speed * 2.0)
        elif key == "j":
            state.full_json = not state.full_json
        elif key == "s":
            save_snapshot(state, writer.stats(), classifier, snapshot_dir, layout_mode)
        elif key == "q":
            state.quit_requested = True


def run(args: argparse.Namespace) -> int:
    inbox = SignalInbox(args.input_dir)
    classifier = build_classifier()
    writer = CaptureOutputWriter(args.json_dir, keep=args.keep)
    truth = load_ground_truth(REFERENCE_ROOT / "ground_truth.csv")
    initial_files = sum(1 for path in args.input_dir.glob("*.json") if path.is_file())
    state = DashboardState(args.count or initial_files, args.speed, ascii_mode=args.ascii)
    state.full_json = args.full_json

    live = None
    console = None
    last_refresh = 0.0
    if not args.plain:
        from rich.console import Console
        from rich.live import Live

        console = Console()
        live = Live(console=console, refresh_per_second=10, screen=False, auto_refresh=False)
        live.start()
    else:
        print(HEADER)
        print(INPUT_BADGE)
        print(f"Watching input folder: {args.input_dir.resolve()}")

    try:
        while not state.quit_requested:
            _handle_keys(
                state, writer, classifier, args.snapshot_dir, args.layout,
                enabled=not args.no_keys,
            )
            while state.paused and not state.quit_requested:
                _handle_keys(
                    state, writer, classifier, args.snapshot_dir, args.layout,
                    enabled=not args.no_keys,
                )
                time.sleep(0.05)
            if state.quit_requested:
                break

            batch = inbox.poll()
            state.add_duplicates(len(batch.duplicates))
            for file_name in batch.duplicates:
                if args.plain:
                    print(f"DUPLICATE {file_name} skipped")
            for rejected in batch.rejected:
                state.add_rejected(f"{rejected.file_name}: {rejected.reason}")
                if args.plain:
                    print(f"REJECTED {rejected.file_name}: {rejected.reason}")

            for signal in batch.signals:
                if args.count > 0 and state.classified >= args.count:
                    state.quit_requested = True
                    break

                _handle_keys(
                    state,
                    writer,
                    classifier,
                    args.snapshot_dir,
                    args.layout,
                    enabled=not args.no_keys,
                )
                while state.paused and not state.quit_requested:
                    _handle_keys(
                        state,
                        writer,
                        classifier,
                        args.snapshot_dir,
                        args.layout,
                        enabled=not args.no_keys,
                    )
                    time.sleep(0.05)
                if state.quit_requested:
                    break

                # Processing has no access to the scoring reference.
                processed = process(signal, classifier, writer)
                # The optional reference join happens after classification and writing.
                scored = score(processed, truth)
                state.add(scored)

                if args.plain:
                    row = state.recent[-1]
                    print(
                        f"{row.sequence_number:06d} {signal.observation_id} "
                        f"expected={row.expected} output={row.classification} "
                        f"severity={row.severity} path={processed.trace.path_taken} "
                        f"classify_ms={row.processing_ms:.4f}"
                    )
                else:
                    now = time.monotonic()
                    if now - last_refresh >= 0.1:
                        live.update(
                            render_dashboard(
                                state,
                                writer.stats(),
                                classifier,
                                layout_mode=args.layout,
                                terminal_width=console.size.width,
                                terminal_height=console.size.height,
                            ),
                            refresh=True,
                        )
                        last_refresh = now

                if args.snapshot_at and state.classified == args.snapshot_at:
                    svg, text_path = save_snapshot(
                        state, writer.stats(), classifier, args.snapshot_dir, args.layout
                    )
                    if args.plain:
                        print(f"snapshot_svg={svg}")
                        print(f"snapshot_text={text_path}")
                if state.speed > 0:
                    time.sleep(state.speed)

            if not args.plain:
                now = time.monotonic()
                if now - last_refresh >= 0.1:
                    live.update(
                        render_dashboard(
                            state,
                            writer.stats(),
                            classifier,
                            layout_mode=args.layout,
                            terminal_width=console.size.width,
                            terminal_height=console.size.height,
                        ),
                        refresh=True,
                    )
                    last_refresh = now

            if args.count > 0 and state.classified >= args.count:
                break
            if not batch.signals and not batch.rejected and not batch.duplicates:
                time.sleep(0.05)
    except KeyboardInterrupt:
        print("\nLive scan stopped by user.")
    finally:
        if live is not None:
            live.stop()

    print_summary(calculate_summary(state.scored))
    print(f"writer_stats={writer.stats()}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Watch and classify Module 1 JSON captures")
    parser.add_argument("--speed", type=float, default=0.2, help="seconds between captures")
    parser.add_argument("--count", type=int, default=0, help="stop after N captures; 0 watches continuously")
    parser.add_argument("--plain", action="store_true", help="disable the Rich dashboard")
    parser.add_argument("--keep", action="store_true", help="keep existing JSON outputs")
    parser.add_argument("--no-tests", action="store_true", help="accepted for command compatibility")
    parser.add_argument(
        "--input-dir",
        type=Path,
        default=DEFAULT_INPUT_ROOT,
        help="flat folder watched for Module 1 JSON captures",
    )
    parser.add_argument("--json-dir", type=Path, default=DEFAULT_OUTPUT_ROOT, help="output root for recipient JSON")
    parser.add_argument("--layout", choices=("auto", "full", "compact"), default="auto")
    parser.add_argument("--full-json", action="store_true", help="show complete JSON in full layout")
    parser.add_argument("--no-keys", action="store_true", help="disable interactive keyboard controls")
    parser.add_argument("--snapshot-at", type=int, default=0, metavar="N")
    parser.add_argument("--snapshot-dir", type=Path, default=ROOT / "reports" / "screenshots")
    parser.add_argument("--ascii", action="store_true", help="use terminal-safe ASCII symbols")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.speed < 0:
        parser.error("--speed must be zero or greater")
    if args.count < 0:
        parser.error("--count must be zero or greater")
    if args.snapshot_at < 0:
        parser.error("--snapshot-at must be zero or greater")
    return run(args)

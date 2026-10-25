from __future__ import annotations

import json
from pathlib import Path

import pytest
from rich.console import Console

from src.classifier import DecisionTrace, build_classifier
from src.output_writer import CaptureOutputWriter
from src.real_data import load_stream
from src.scoring_data import load_ground_truth
from src.unified_demo import DashboardState, process, render_dashboard, score


DATA = Path("data/real/module1_signals_clean")
PATH_FILES = (
    Path("src/real_data.py"),
    Path("src/baseline.py"),
    Path("src/rule_engine.py"),
    Path("src/anomaly_engine.py"),
    Path("src/classifier.py"),
)
FORBIDDEN_WORDS = (
    "label",
    "phase",
    "ground_truth",
    "jammer_type",
    "folder",
    "interference",
    "signal_present",
    "channel",
    "power_anomaly",
)


@pytest.fixture(scope="module")
def signals_and_truth():
    return list(load_stream(DATA)), load_ground_truth(DATA / "ground_truth.csv")


def _select(signals, truth, kind):
    for signal in signals:
        row = truth[signal.observation_id]
        if kind == "jamming" and row["jammer_type"] == "CARRIER":
            return signal
        if kind == "idle" and row["normal_kind"] == "idle":
            return signal
        if kind == "legitimate" and row["normal_kind"] == "legit_ook":
            return signal
    raise AssertionError(f"missing test signal: {kind}")


def test_classify_with_trace_matches_classify_for_all_signals(signals_and_truth):
    signals, _ = signals_and_truth
    classifier = build_classifier()

    for signal in signals:
        traced_output, trace = classifier.classify_with_trace(signal)
        assert traced_output == classifier.classify(signal)
        assert trace.path_taken in {"R1", "ANOMALY", "NORMAL"}


def test_trace_values_match_evidence_and_configuration(signals_and_truth):
    signals, truth = signals_and_truth
    signal = _select(signals, truth, "jamming")
    configuration = json.loads(Path("config/thresholds_real.json").read_text(encoding="utf-8"))
    output, trace = build_classifier().classify_with_trace(signal)
    r1 = next(step for step in trace.steps if step.name == "Rule R1")

    assert r1.actual_values == {
        "snr_db": signal.snr_db,
        "occupied_bw_khz": signal.occupied_bw_khz,
    }
    assert r1.thresholds == {
        "T_SNR": configuration["thresholds"]["T_SNR"],
        "T_BW": configuration["thresholds"]["T_BW"],
    }
    assert output.evidence == [
        f"snr_db {signal.snr_db:.1f} >= {r1.thresholds['T_SNR']:.1f} and "
        f"0 < occupied_bw_khz {signal.occupied_bw_khz:.1f} <= {r1.thresholds['T_BW']:.1f}"
    ]
    assert trace.per_state_distances[trace.nearest_state] == output.statistical_deviation


@pytest.mark.parametrize("width", [100, 140, 190])
@pytest.mark.parametrize("kind", ["jamming", "idle", "legitimate", "rejected"])
def test_headless_dashboard_render_contains_decision_trace(
    width, kind, signals_and_truth, tmp_path
):
    signals, truth = signals_and_truth
    classifier = build_classifier()
    writer = CaptureOutputWriter(tmp_path / kind)
    state = DashboardState(total=1, speed=0.0, ascii_mode=True)
    if kind == "rejected":
        state.add_rejected("invalid measurement")
    else:
        signal = _select(signals, truth, kind)
        state.add(score(process(signal, classifier, writer), truth))

    console = Console(record=True, width=width, force_terminal=False, color_system=None)
    console.print(
        render_dashboard(
            state,
            writer.stats(),
            classifier,
            layout_mode="auto",
            terminal_width=width,
            terminal_height=50,
        )
    )

    rendered = console.export_text()
    assert "Decision trace" in rendered
    assert "..." not in rendered
    assert "…" not in rendered


def test_classification_path_source_has_no_scoring_or_upstream_flag_words():
    for path in PATH_FILES:
        source = path.read_text(encoding="utf-8").lower()
        for word in FORBIDDEN_WORDS:
            assert word not in source, f"{word!r} found in {path}"


def test_rejected_trace_has_no_classification_output():
    trace = DecisionTrace.rejected("invalid measurement")

    assert trace.path_taken == "REJECTED"
    assert trace.steps[0].passed is False


def test_dashboard_initial_state_is_waiting_not_rejected(tmp_path):
    classifier = build_classifier()
    writer = CaptureOutputWriter(tmp_path)
    state = DashboardState(total=0, speed=0.0, ascii_mode=True)
    console = Console(record=True, width=100, force_terminal=False, color_system=None)

    console.print(
        render_dashboard(
            state,
            writer.stats(),
            classifier,
            layout_mode="compact",
            terminal_width=100,
            terminal_height=30,
        )
    )

    rendered = console.export_text()
    assert "WAITING" in rendered
    assert "CURRENT THREAT STATUS" in rendered

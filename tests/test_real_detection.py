"""Tests for the measurement-only real-data detector and chronological evaluation."""

from __future__ import annotations

from dataclasses import fields
from pathlib import Path

import numpy as np
import pytest

from scripts.analyze_real_data import split_data
from src.classifier import Classification, ThreatOutput
from src.real_classifier import RealThreatClassifierV2
from src.real_data import JsonFolderSource, RealSignal, load_ground_truth
from src.real_detection import (
    DETECTION_FEATURES,
    STD_FLOORS,
    build_frozen_detector_v2,
    fit_detector_v2,
)


DATA = Path("data/real/module1_real_signals")
FORBIDDEN = {
    "phase",
    "label",
    "expected_class",
    "jammer_type",
    "interference",
    "signal_present",
}


@pytest.fixture(scope="module")
def real_context():
    signals = list(JsonFolderSource(DATA))
    truth = load_ground_truth(DATA / "ground_truth.csv")
    split = split_data(signals, truth)
    detector = fit_detector_v2(
        split["calibration_idle"],
        split["calibration_legitimate"],
        split["calibration_jamming"],
    )
    return signals, truth, split, detector, RealThreatClassifierV2(detector)


def test_runtime_signal_has_no_ground_truth_or_module1_flag_fields():
    assert {field.name for field in fields(RealSignal)}.isdisjoint(FORBIDDEN)


def test_split_is_chronological_and_unseen_is_never_in_calibration(real_context):
    _, truth, split, _, _ = real_context

    assert len(split["calibration_idle"]) == 632
    assert len(split["validation_idle"]) == 632
    assert len(split["calibration_legitimate"]) == 24
    assert len(split["validation_legitimate"]) == 25
    assert len(split["calibration_jamming"]) == 96
    assert len(split["unseen_jamming"]) == 93
    assert max(s.timestamp for s in split["calibration_idle"]) <= min(
        s.timestamp for s in split["validation_idle"]
    )
    assert max(s.timestamp for s in split["calibration_legitimate"]) <= min(
        s.timestamp for s in split["validation_legitimate"]
    )
    assert {
        truth[s.observation_id]["jammer_type"] for s in split["calibration_jamming"]
    } == {"CARRIER", "PULSED_50_50"}
    assert {
        truth[s.observation_id]["jammer_type"] for s in split["unseen_jamming"]
    } == {"PULSED_5_95", "RANDOM_BURSTS"}


def test_baseline_has_two_states_and_applies_resolution_floors(real_context):
    _, _, _, detector, _ = real_context

    assert detector.baseline.idle.name == "idle"
    assert detector.baseline.legitimate.name == "legitimate"
    assert set(detector.baseline.idle.mean) == set(DETECTION_FEATURES)
    for state in (detector.baseline.idle, detector.baseline.legitimate):
        for feature in DETECTION_FEATURES:
            assert state.std[feature] >= STD_FLOORS[feature]
    assert detector.baseline.idle.std["band_power_dbfs"] == pytest.approx(0.1)
    assert detector.baseline.idle.std["occupied_bw_khz"] == pytest.approx(1.0)


def test_state_snr_threshold_comes_only_from_idle_calibration(real_context):
    _, _, split, detector, _ = real_context
    expected = np.quantile(
        [signal.snr_db for signal in split["calibration_idle"]], 0.99, method="higher"
    )

    assert detector.baseline.state_snr_threshold == pytest.approx(expected)
    assert expected == pytest.approx(3.5)


def test_grid_searched_rule_meets_calibration_false_positive_limit(real_context):
    _, _, split, detector, _ = real_context
    normal = split["calibration_idle"] + split["calibration_legitimate"]

    false_positives = sum(detector.rules.evaluate(signal).triggered for signal in normal)
    hits = sum(
        detector.rules.evaluate(signal).triggered
        for signal in split["calibration_jamming"]
    )

    assert false_positives / len(normal) <= 0.01
    assert false_positives == 0
    assert hits == 96
    assert detector.rules.thresholds.occupied_bw_max_khz == pytest.approx(62.0)
    assert detector.rules.thresholds.spectral_flatness_max == pytest.approx(0.003)


def test_anomaly_threshold_meets_calibration_false_alarm_limit(real_context):
    _, _, split, detector, _ = real_context
    normal = split["calibration_idle"] + split["calibration_legitimate"]
    alarms = sum(detector.anomaly.evaluate(signal).triggered for signal in normal)

    assert alarms == 6
    assert alarms / len(normal) <= 0.01
    assert detector.anomaly.threshold == pytest.approx(1.6994861812377327)


def test_rule_wins_before_anomaly_and_preserves_output_fields(real_context):
    _, _, split, _, classifier = real_context
    output = classifier.classify(split["calibration_jamming"][0])

    assert isinstance(output, ThreatOutput)
    assert output.classification == Classification.JAMMING.value
    assert output.triggered_rule == "R2-NARROWBAND"
    assert output.observation_id
    assert output.timestamp
    assert output.severity is not None
    assert output.statistical_deviation
    assert output.evidence


def test_unseen_jammers_are_detected_without_becoming_threshold_inputs(real_context):
    _, _, split, _, classifier = real_context
    outputs = [classifier.classify(signal) for signal in split["unseen_jamming"]]

    assert len(outputs) == 93
    assert all(output.classification != Classification.NORMAL.value for output in outputs)
    assert sum(output.classification == Classification.JAMMING.value for output in outputs) == 19
    assert sum(
        output.classification == Classification.UNKNOWN_ANOMALY.value for output in outputs
    ) == 74


def test_legitimate_signal_is_not_jamming_based_on_signal_presence(real_context):
    _, _, split, detector, classifier = real_context
    legitimate = split["validation_legitimate"][0]

    assert legitimate.snr_db > detector.baseline.state_snr_threshold
    assert detector.rules.evaluate(legitimate).triggered is False
    assert classifier.classify(legitimate).classification == Classification.NORMAL.value


def test_anomaly_evidence_names_measurement_features(real_context):
    _, truth, split, detector, _ = real_context
    pulsed = next(
        signal
        for signal in split["unseen_jamming"]
        if truth[signal.observation_id]["jammer_type"] == "PULSED_5_95"
    )
    decision = detector.anomaly.evaluate(pulsed)

    assert decision.triggered
    assert decision.abnormal_features
    assert all(feature in DETECTION_FEATURES for feature in decision.abnormal_features)
    assert any(feature in " ".join(decision.evidence) for feature in decision.abnormal_features)


def test_classifier_rejects_unvalidated_types(real_context):
    _, _, _, _, classifier = real_context

    with pytest.raises(TypeError, match="validated RealSignal"):
        classifier.classify({"snr_db": 60.0})


def test_frozen_demo_detector_matches_fitted_detector(real_context):
    signals, _, _, fitted, _ = real_context
    frozen = build_frozen_detector_v2()

    assert frozen.anomaly.threshold == fitted.anomaly.threshold
    assert frozen.rules.thresholds == fitted.rules.thresholds
    for signal in signals:
        assert frozen.baseline.nearest(signal) == fitted.baseline.nearest(signal)
        assert frozen.rules.evaluate(signal) == fitted.rules.evaluate(signal)
        assert frozen.anomaly.evaluate(signal) == fitted.anomaly.evaluate(signal)


def test_label_quality_rows_are_kept_out_of_scored_partitions(real_context):
    _, _, split, _, _ = real_context

    assert len(split["none_inside_jammer_phase"]) == 7
    assert len(split["signal_present_but_none"]) == 4

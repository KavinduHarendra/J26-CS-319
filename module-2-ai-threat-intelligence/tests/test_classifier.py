from dataclasses import replace
from pathlib import Path

import pytest

from src.classifier import Classification, Severity, build_classifier
from src.real_data import Signal, load_signal


SAMPLE = Path("data/real/module1_signals_clean/known_signals/000001_S00001.json")


@pytest.fixture(scope="module")
def classifier():
    return build_classifier()


@pytest.fixture
def normal_signal() -> Signal:
    return load_signal(SAMPLE)


def test_clear_normal_signal_is_normal(classifier, normal_signal):
    output = classifier.classify(normal_signal)

    assert output.classification == Classification.NORMAL.value
    assert output.severity is None
    assert output.triggered_rule is None


def test_r1_has_priority_and_jamming_severity_uses_uncalibrated_cutoffs(
    classifier, normal_signal
):
    output = classifier.classify(
        replace(normal_signal, snr_db=50.0, occupied_bw_khz=23.0)
    )

    assert output.classification == Classification.JAMMING.value
    assert output.severity == Severity.HIGH.value
    assert output.triggered_rule == "R1"
    assert output.evidence == [
        "snr_db 50.0 >= 25.8 and 0 < occupied_bw_khz 23.0 <= 137.5"
    ]


def test_non_rule_deviation_is_unknown_anomaly(classifier, normal_signal):
    output = classifier.classify(replace(normal_signal, peak_db=-20.0))

    assert output.classification == Classification.UNKNOWN_ANOMALY.value
    assert output.severity in {Severity.LOW.value, Severity.MEDIUM.value, Severity.HIGH.value}
    assert output.triggered_rule is None
    assert "peak_db" in output.abnormal_features


def test_output_contract_fields_are_present(classifier, normal_signal):
    output = classifier.classify(normal_signal)

    assert output.schema_version == "1.0"
    assert output.source_module == "module2_ai_threat_intelligence"
    assert output.sequence_number == normal_signal.sequence_number
    assert output.baseline_version == "real-raw-v1"
    assert output.processing_ms >= 0.0
    assert output.statistical_deviation


def test_same_signal_has_identical_detection_output(classifier, normal_signal):
    assert classifier.classify(normal_signal) == classifier.classify(normal_signal)


def test_invalid_input_is_rejected_and_never_returns_normal(classifier):
    with pytest.raises(TypeError, match="validated Signal"):
        classifier.classify({"snr_db": float("nan")})


def test_signal_constructor_rejects_nan(normal_signal):
    with pytest.raises(ValueError, match="finite"):
        replace(normal_signal, snr_db=float("nan"))

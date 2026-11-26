from dataclasses import replace
from pathlib import Path

import pytest

from src.classifier import (
    Classification,
    Severity,
    build_classifier,
)
from src.real_data import Signal, load_signal, load_stream


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


def test_r1_has_priority_and_jamming_severity_uses_calibrated_cutoffs(
    classifier, normal_signal
):
    output = classifier.classify(
        replace(normal_signal, snr_db=50.0, occupied_bw_khz=23.0)
    )

    assert output.classification == Classification.JAMMING.value
    assert output.severity == Severity.HIGH.value
    assert output.triggered_rule == "R1"
    assert output.evidence == [
        "snr_db 50.0 >= 25.8 and 0 < occupied_bw_khz 23.0 <= 137.5",
        "fuzzy_score 80.6 (HIGH)",
        "fuzzy F1 fired at 1.00: STRONG snr AND NARROW bw -> HIGH risk",
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


def test_threat_severity_is_the_fuzzy_severity(classifier, normal_signal):
    jamming = classifier.classify(replace(normal_signal, snr_db=50.0, occupied_bw_khz=23.0))
    anomaly = classifier.classify(replace(normal_signal, peak_db=-20.0))

    for output in (jamming, anomaly):
        assert output.fuzzy_score is not None
        assert output.severity == classifier.fuzzy.severity(output.fuzzy_score)
    assert jamming.fuzzy_rules_fired == ["F1"]


def test_anomaly_between_narrow_and_wide_gets_graded_fuzzy_severity(classifier, normal_signal):
    # Strong signal whose bandwidth is on the NARROW/WIDE ramp: R1 does not fire,
    # both F1 and F2 fire partially, and the old magnitude cut-offs are not used.
    output = classifier.classify(replace(normal_signal, snr_db=50.0, occupied_bw_khz=160.0))

    assert output.classification == Classification.UNKNOWN_ANOMALY.value
    assert output.fuzzy_rules_fired == ["F1", "F2"]
    assert classifier.fuzzy.medium_from <= output.fuzzy_score < classifier.fuzzy.high_from
    assert output.severity == Severity.MEDIUM.value


def test_normal_keeps_null_severity_but_reports_fuzzy_fields(classifier, normal_signal):
    output = classifier.classify(normal_signal)

    assert output.classification == Classification.NORMAL.value
    assert output.severity is None
    assert output.fuzzy_score is not None and output.fuzzy_score < classifier.fuzzy.medium_from
    assert output.fuzzy_rules_fired == ["F3"]


@pytest.mark.slow
def test_severity_and_fuzzy_evidence_agree_on_every_recorded_capture(classifier):
    outputs = [
        classifier.classify(signal)
        for signal in load_stream(Path("data/real/module1_signals_clean"))
    ]

    assert len(outputs) == 1513
    for output in outputs:
        evidence_line = next(line for line in output.evidence if line.startswith("fuzzy_score"))
        if output.classification == Classification.NORMAL.value:
            assert output.severity is None
        else:
            assert evidence_line.endswith(f"({output.severity})")

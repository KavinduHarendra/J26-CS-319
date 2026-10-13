"""
tests/test_classifier.py — Unit tests for ThreatIntelligenceModule and classification pipeline.

Verifies:
  - Classification and Severity string enums.
  - Correct classification of three synthetic observations:
      1. Clearly normal -> Normal (severity=None, triggered_rule=None)
      2. Clearly jamming -> Jamming (severity="High", triggered_rule contains J01)
      3. Clearly unknown-anomaly -> Unknown Anomaly (abnormal_features=["snr"], rule=None)
  - ThreatOutput dataclass fields and evidence text formatting.
  - Severity mapping boundary cutoffs (High >= 5.0, Medium >= 3.0, Low < 3.0).
"""

from datetime import datetime, timezone
import pytest

from src.schema import RFObservation
from src.baseline import NormalBaseline
from src.rule_engine import build_default_ruleset
from src.anomaly_engine import StatisticalAnomalyEngine
from src.classifier import Classification, Severity, ThreatOutput, ThreatIntelligenceModule
from src.synthetic_data import generate_normal


@pytest.fixture
def calibrated_pipeline():
    """Create a fully calibrated ThreatIntelligenceModule instance."""
    # Calibrate baseline using synthetic normal data
    calib_samples = generate_normal(n=200, seed=42)
    baseline = NormalBaseline()
    baseline.add_normal_samples(calib_samples)
    baseline.calibrate()

    rule_detector = build_default_ruleset()
    anomaly_engine = StatisticalAnomalyEngine(z_threshold=3.0)
    module = ThreatIntelligenceModule(baseline, rule_detector, anomaly_engine)
    return module


class TestEnums:
    def test_classification_values(self):
        assert Classification.NORMAL.value == "Normal"
        assert Classification.JAMMING.value == "Jamming"
        assert Classification.UNKNOWN_ANOMALY.value == "Unknown Anomaly"

    def test_severity_values(self):
        assert Severity.LOW.value == "Low"
        assert Severity.MEDIUM.value == "Medium"
        assert Severity.HIGH.value == "High"


class TestSeverityMapping:
    def test_severity_cutoffs(self, calibrated_pipeline):
        module = calibrated_pipeline
        assert module._severity(6.0) == Severity.HIGH
        assert module._severity(5.0) == Severity.HIGH
        assert module._severity(4.5) == Severity.MEDIUM
        assert module._severity(3.0) == Severity.MEDIUM
        assert module._severity(2.9) == Severity.LOW
        assert module._severity(0.5) == Severity.LOW


class TestClassifySyntheticObservations:
    """Tests the three distinct scenario conditions."""

    def test_classify_clearly_normal(self, calibrated_pipeline):
        module = calibrated_pipeline
        normal_obs = RFObservation(
            observation_id="test-normal-01",
            timestamp=datetime(2026, 1, 1, 12, 0, 0, tzinfo=timezone.utc),
            rssi=-60.0,
            snr=25.0,
            noise_floor=-90.0,
            packet_rate=100.0,
        )

        output: ThreatOutput = module.classify(normal_obs)

        assert output.observation_id == "test-normal-01"
        assert output.classification == Classification.NORMAL.value
        assert output.severity is None
        assert output.triggered_rule is None
        assert output.abnormal_features == []
        assert output.evidence == ["No jamming rule triggered; within baseline deviation"]
        assert isinstance(output.statistical_deviation, dict)

    def test_classify_clearly_jamming(self, calibrated_pipeline):
        module = calibrated_pipeline
        # Sharp SNR drop (8 dB vs 25 dB) AND severe noise floor rise (-68 dBm vs -90 dBm)
        jamming_obs = RFObservation(
            observation_id="test-jam-01",
            timestamp=datetime(2026, 1, 1, 12, 0, 1, tzinfo=timezone.utc),
            rssi=-76.0,
            snr=6.0,
            noise_floor=-68.0,
            packet_rate=35.0,
        )

        output: ThreatOutput = module.classify(jamming_obs)

        assert output.observation_id == "test-jam-01"
        assert output.classification == Classification.JAMMING.value
        assert output.severity == Severity.HIGH.value
        assert output.triggered_rule is not None
        assert "J01" in output.triggered_rule
        assert len(output.evidence) >= 1
        assert any("SNR drop" in e for e in output.evidence)

    def test_classify_clearly_unknown_anomaly(self, calibrated_pipeline):
        module = calibrated_pipeline
        # Significant SNR drop (10 dB vs 25 dB, z ~ -7.5) but noise floor (-90 dBm)
        # and packet rate (100) remain near normal. J01 and J02 must NOT trigger.
        anomaly_obs = RFObservation(
            observation_id="test-unk-01",
            timestamp=datetime(2026, 1, 1, 12, 0, 2, tzinfo=timezone.utc),
            rssi=-60.0,
            snr=10.0,
            noise_floor=-90.0,
            packet_rate=100.0,
        )

        output: ThreatOutput = module.classify(anomaly_obs)

        assert output.observation_id == "test-unk-01"
        assert output.classification == Classification.UNKNOWN_ANOMALY.value
        assert output.severity == Severity.HIGH.value
        assert output.triggered_rule is None
        assert output.abnormal_features == ["snr"]
        assert output.evidence == ["Significant deviation in snr"]
        assert "snr" in output.statistical_deviation

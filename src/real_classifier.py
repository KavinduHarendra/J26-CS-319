"""Runtime classifier for validated real Module 1 measurements."""

from __future__ import annotations

from src.classifier import Classification, Severity, ThreatOutput
from src.real_data import RealSignal
from src.real_detection import RealDetectorV2


# These presentation cut-offs are placeholders, not empirically calibrated risk
# boundaries. Collection of operational incident outcomes is needed before they
# can be interpreted as actual impact severity.
SEVERITY_CUTOFFS_PLACEHOLDER = (3.0, 6.0)


class RealThreatClassifierV2:
    """Apply rules first, then anomaly detection, preserving output fields."""

    def __init__(self, detector: RealDetectorV2) -> None:
        self.detector = detector

    @staticmethod
    def _severity(magnitude: float) -> str:
        medium, high = SEVERITY_CUTOFFS_PLACEHOLDER
        if magnitude >= high:
            return Severity.HIGH.value
        if magnitude >= medium:
            return Severity.MEDIUM.value
        return Severity.LOW.value

    def classify(self, signal: RealSignal) -> ThreatOutput:
        if not isinstance(signal, RealSignal):
            raise TypeError("classify requires a validated RealSignal")

        rule = self.detector.rules.evaluate(signal)
        anomaly = self.detector.anomaly.evaluate(signal)
        magnitude = max((abs(value) for value in anomaly.z_scores.values()), default=0.0)

        # Decision order is intentional: a known rule wins over anomaly status.
        if rule.triggered:
            return ThreatOutput(
                observation_id=signal.observation_id,
                timestamp=signal.timestamp.isoformat(),
                classification=Classification.JAMMING.value,
                severity=self._severity(magnitude),
                triggered_rule=rule.rule_id,
                abnormal_features=anomaly.abnormal_features,
                statistical_deviation=anomaly.z_scores,
                evidence=rule.evidence,
            )
        if anomaly.triggered:
            return ThreatOutput(
                observation_id=signal.observation_id,
                timestamp=signal.timestamp.isoformat(),
                classification=Classification.UNKNOWN_ANOMALY.value,
                severity=self._severity(magnitude),
                triggered_rule=None,
                abnormal_features=anomaly.abnormal_features,
                statistical_deviation=anomaly.z_scores,
                evidence=anomaly.evidence,
            )
        expected_state = self.detector.baseline.state_from_snr(signal)
        return ThreatOutput(
            observation_id=signal.observation_id,
            timestamp=signal.timestamp.isoformat(),
            classification=Classification.NORMAL.value,
            severity=None,
            triggered_rule=None,
            abnormal_features=[],
            statistical_deviation=anomaly.z_scores,
            evidence=[
                f"No real-data rule triggered; within the {expected_state} normal baseline"
            ],
        )

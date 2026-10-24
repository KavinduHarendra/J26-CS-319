"""
classifier.py — Layer 3 Classification, Severity, and Explainable Output.

Orchestrates the complete threat intelligence pipeline:
  Observation -> NormalBaseline -> Rule Engine -> Statistical Anomaly Engine -> ThreatOutput
"""

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Optional, Any

from src.audit import AuditLogger, DEFAULT_AUDIT_LOG_PATH
from src.schema import InvalidObservationError, RFObservation, validate_observation
from src.baseline import NormalBaseline
from src.rule_engine import RuleBasedJammingDetector
from src.anomaly_engine import StatisticalAnomalyEngine


class Classification(str, Enum):
    """Categorical classification labels."""
    NORMAL = "Normal"
    JAMMING = "Jamming"
    UNKNOWN_ANOMALY = "Unknown Anomaly"


class Severity(str, Enum):
    """Severity ratings for detected threats."""
    LOW = "Low"
    MEDIUM = "Medium"
    HIGH = "High"


@dataclass
class ThreatOutput:
    """
    Explainable threat intelligence classification output.

    Attributes:
        observation_id: Originating observation ID.
        timestamp: ISO-formatted timestamp.
        classification: 'Normal', 'Jamming', or 'Unknown Anomaly'.
        severity: Severity rating ('Low', 'Medium', 'High') or None if Normal.
        triggered_rule: Comma-separated rule IDs if rule fired, else None.
        abnormal_features: List of feature names with significant deviation.
        statistical_deviation: Dictionary of feature z-scores.
        evidence: Plain-language explanations supporting the decision.
    """
    observation_id: str
    timestamp: str
    classification: str
    severity: Optional[str]
    triggered_rule: Optional[str]
    abnormal_features: list[str] = field(default_factory=list)
    statistical_deviation: dict[str, float] = field(default_factory=dict)
    evidence: list[str] = field(default_factory=list)


class ThreatIntelligenceModule:
    """
    Top-level orchestrator:
      1. Computes feature deviations against calibrated NormalBaseline.
      2. Evaluates RuleBasedJammingDetector: if rules match -> Jamming.
      3. If no rules match, evaluates StatisticalAnomalyEngine -> Unknown Anomaly if z-scores abnormal.
      4. Otherwise -> Normal.
    """

    def __init__(
        self,
        baseline: NormalBaseline,
        rule_detector: RuleBasedJammingDetector,
        anomaly_engine: StatisticalAnomalyEngine,
        audit_log_path: str | Path = DEFAULT_AUDIT_LOG_PATH,
    ):
        self.baseline = baseline
        self.rule_detector = rule_detector
        self.anomaly_engine = anomaly_engine
        self.audit_logger = AuditLogger(audit_log_path)

    def _severity(self, magnitude: float) -> Severity:
        """Assign severity level based on the maximum z-score deviation."""
        if magnitude >= 5.0:
            return Severity.HIGH
        elif magnitude >= 3.0:
            return Severity.MEDIUM
        return Severity.LOW

    def classify(self, obs: RFObservation) -> ThreatOutput:
        """
        Classify a single RFObservation and return explainable ThreatOutput.

        Args:
            obs: The input RFObservation.

        Returns:
            Structured ThreatOutput record.
        """
        try:
            validate_observation(obs)
        except InvalidObservationError as exc:
            self.audit_logger.log_rejection(obs, exc, self.baseline.version)
            raise

        deviations = self.baseline.deviations(obs)
        z_scores = deviations["z_scores"]

        # Step 1: Rule-based jamming detection
        rule_result = self.rule_detector.evaluate(deviations)
        if rule_result:
            max_z = max(abs(v) for v in z_scores.values()) if z_scores else 0.0
            output = ThreatOutput(
                observation_id=obs.observation_id,
                timestamp=obs.timestamp.isoformat(),
                classification=Classification.JAMMING.value,
                severity=self._severity(max_z).value,
                triggered_rule=",".join(rule_result["triggered_rules"]),
                abnormal_features=[],
                statistical_deviation=z_scores,
                evidence=rule_result["rule_descriptions"],
            )
        else:
            # Step 2: Statistical anomaly detection
            anomaly_result = self.anomaly_engine.evaluate(deviations)
            if anomaly_result:
                max_z = max(abs(v) for v in anomaly_result["z_scores"].values())
                output = ThreatOutput(
                    observation_id=obs.observation_id,
                    timestamp=obs.timestamp.isoformat(),
                    classification=Classification.UNKNOWN_ANOMALY.value,
                    severity=self._severity(max_z).value,
                    triggered_rule=None,
                    abnormal_features=anomaly_result["anomalous_features"],
                    statistical_deviation=anomaly_result["z_scores"],
                    evidence=[
                        f"Significant deviation in {feature}"
                        for feature in anomaly_result["anomalous_features"]
                    ],
                )
            else:
                # Step 3: Normal
                output = ThreatOutput(
                    observation_id=obs.observation_id,
                    timestamp=obs.timestamp.isoformat(),
                    classification=Classification.NORMAL.value,
                    severity=None,
                    triggered_rule=None,
                    abnormal_features=[],
                    statistical_deviation=z_scores,
                    evidence=["No jamming rule triggered; within baseline deviation"],
                )

        self.audit_logger.log_classification(obs, output, self.baseline.version)
        return output

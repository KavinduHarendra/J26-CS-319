"""Version 1 of the pre-decision feature schema shared by both input paths."""

from typing import TYPE_CHECKING, Literal

from pydantic import BaseModel, ConfigDict, Field

from models.module2 import ClassificationValue, SeverityValue
from models.module3 import AuthStateValue, CommDecisionValue, FreshnessStateValue, IntegrityStateValue, LinkStateValue

if TYPE_CHECKING:
    from services.evidence_service import AssessedEvidence


FeatureSchemaVersion = Literal["1.0"]
FEATURE_SCHEMA_VERSION: FeatureSchemaVersion = "1.0"
RiskLevel = Literal["LOW", "MEDIUM", "HIGH", "CRITICAL"]
ResponseAction = Literal[
    "MONITOR",
    "CONTINUE_MONITORING",
    "INCREASE_MONITORING",
    "PREPARE_BACKUP_CHANNEL",
    "OPERATOR_ESCALATION",
    "SECURE_HOLD",
]


class ResponseFeatures(BaseModel):
    model_config = ConfigDict(extra="forbid", allow_inf_nan=False)

    classification: ClassificationValue
    severity: SeverityValue
    threat_confidence: float | None = Field(ge=0, le=1)
    triggered_rule_present: bool
    abnormal_feature_count: int = Field(ge=0)
    link_state: LinkStateValue
    freshness_state: FreshnessStateValue
    auth_state: AuthStateValue
    integrity_state: IntegrityStateValue
    replay_detected: bool
    comm_decision: CommDecisionValue
    risk_score: float = Field(ge=0, le=100)
    risk_level: RiskLevel
    evidence_conflict: bool
    decision_confidence: Literal["HIGH", "MEDIUM", "LOW"]


FEATURE_COLUMNS = tuple(ResponseFeatures.model_fields)


def extract_features(evidence: "AssessedEvidence") -> ResponseFeatures:
    threat = evidence.threat
    communication = evidence.communication
    return ResponseFeatures(
        classification=threat.classification,
        severity=threat.severity,
        threat_confidence=threat.threat_confidence,
        triggered_rule_present=threat.triggered_rule is not None,
        abnormal_feature_count=len(threat.abnormal_features),
        link_state=communication.link_state,
        freshness_state=communication.freshness_state,
        auth_state=communication.auth_state,
        integrity_state=communication.integrity_state,
        replay_detected=communication.replay_detected,
        comm_decision=communication.comm_decision,
        risk_score=evidence.risk_score,
        risk_level=evidence.risk_level,
        evidence_conflict=evidence.conflict.evidence_conflict,
        decision_confidence=evidence.confidence.level,
    )

"""A versioned, draft recommendation rubric for offline labeling preparation."""

from dataclasses import dataclass

from models.module3 import SecureCommunication
from response_ml.features import ResponseAction, ResponseFeatures

RUBRIC_VERSION = "response-rubric-v0.1-draft"
RESPONSE_CLASSES: tuple[ResponseAction, ...] = (
    "MONITOR", "CONTINUE_MONITORING", "INCREASE_MONITORING",
    "PREPARE_BACKUP_CHANNEL", "OPERATOR_ESCALATION", "SECURE_HOLD",
)
MONITORING = RESPONSE_CLASSES[:3]


@dataclass(frozen=True)
class DraftSuggestion:
    response: ResponseAction
    criterion: str


def mandatory_hold(evidence: ResponseFeatures | SecureCommunication) -> DraftSuggestion | None:
    """Recognize the two hold cases using only validated upstream security fields."""
    if evidence.replay_detected:
        return DraftSuggestion("SECURE_HOLD", "R01_CONFIRMED_REPLAY")
    if (
        evidence.link_state == "UNTRUSTED"
        and evidence.auth_state == evidence.integrity_state == "INVALID"
        and evidence.comm_decision == "SECURE_HOLD"
    ):
        return DraftSuggestion("SECURE_HOLD", "R02_CORROBORATED_SECURITY_FAILURE")
    return None


def suggest_response(evidence: ResponseFeatures) -> DraftSuggestion:
    """For comparison and controlled safety screening. The suggestion carries no approval."""
    if hold := mandatory_hold(evidence):
        return hold
    if (
        evidence.freshness_state != "FRESH"
        or evidence.auth_state != "VALID"
        or evidence.integrity_state != "VALID"
        or evidence.link_state in ("SUSPICIOUS", "UNTRUSTED")
        or evidence.evidence_conflict
        or evidence.comm_decision == "SECURE_HOLD"
    ):
        return DraftSuggestion("OPERATOR_ESCALATION", "R03_SECURITY_OR_EVIDENCE_REVIEW")
    if evidence.classification == "Jamming" and evidence.link_state == "DEGRADED":
        return DraftSuggestion("PREPARE_BACKUP_CHANNEL", "R04_VERIFIED_LINK_WITH_INTERFERENCE")
    if evidence.risk_level == "CRITICAL":
        return DraftSuggestion("OPERATOR_ESCALATION", "R05_CRITICAL_MONITORING_GUARD")
    if evidence.classification != "Normal":
        return DraftSuggestion("INCREASE_MONITORING", "R06_HEIGHTEN_OBSERVATION")
    if evidence.link_state == "DEGRADED" or evidence.risk_level != "LOW":
        return DraftSuggestion("CONTINUE_MONITORING", "R07_MONITOR_WITH_FOLLOWUP")
    return DraftSuggestion("MONITOR", "R08_ROUTINE_MONITORING")

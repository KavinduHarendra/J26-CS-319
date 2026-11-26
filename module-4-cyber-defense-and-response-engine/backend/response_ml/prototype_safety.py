"""Evaluate the proposed v0.1 policy offline without issuing or applying actions."""

from dataclasses import dataclass

from response_ml.features import ResponseFeatures
from response_ml.rubric import MONITORING, RESPONSE_CLASSES, suggest_response

POLICY_VERSION = "proposed-safety-v0.1-offline"


@dataclass(frozen=True)
class GuardResult:
    recommendation: str
    reason: str | None = None


def screen_recommendation(evidence: ResponseFeatures, candidate: str) -> GuardResult:
    draft = suggest_response(evidence)
    required_by_evidence = {
        "R01_CONFIRMED_REPLAY": "CONFIRMED_REPLAY",
        "R02_CORROBORATED_SECURITY_FAILURE": "CORROBORATED_SECURITY_FAILURE",
        "R03_SECURITY_OR_EVIDENCE_REVIEW": "SECURITY_OR_EVIDENCE_REVIEW",
    }
    if draft.criterion in required_by_evidence:
        if candidate == draft.response:
            return GuardResult(candidate)
        return GuardResult(draft.response, required_by_evidence[draft.criterion])
    if candidate not in RESPONSE_CLASSES:
        return GuardResult("OPERATOR_ESCALATION", "UNSUPPORTED_CLASS")
    if evidence.risk_level == "CRITICAL" and candidate in MONITORING:
        return GuardResult("OPERATOR_ESCALATION", "CRITICAL_MONITORING")
    if candidate in ("SECURE_HOLD", "PREPARE_BACKUP_CHANNEL") and candidate != draft.response:
        return GuardResult("OPERATOR_ESCALATION", "UNSUPPORTED_HOLD_OR_BACKUP")
    return GuardResult(candidate)

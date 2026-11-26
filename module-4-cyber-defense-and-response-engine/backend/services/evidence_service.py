"""Prepare the same deterministic evidence for live and offline evaluation."""

from dataclasses import dataclass

from adapters import module1_adapter, module2_adapter, module3_adapter
from models.defense import ConfidenceResult, ConflictResult, CorrelationResult, EvaluateRequest, RiskBreakdown
from models.module1 import RFContext
from models.module2 import ThreatIntelligence
from models.module3 import SecureCommunication
from services import confidence_service, conflict_service, correlation_service, risk_service


@dataclass(frozen=True)
class AssessedEvidence:
    rf: RFContext
    threat: ThreatIntelligence
    communication: SecureCommunication
    correlation: CorrelationResult
    risk_score: float
    risk_level: str
    risk_breakdown: RiskBreakdown
    conflict: ConflictResult
    confidence: ConfidenceResult


def assess_evidence(request: EvaluateRequest) -> AssessedEvidence:
    rf = module1_adapter.adapt(request.rf_context.model_dump())
    threat = module2_adapter.adapt(request.threat_intelligence.model_dump())
    communication = module3_adapter.adapt(request.secure_communication.model_dump())
    correlation = correlation_service.correlate(threat, communication)
    risk_score, risk_level, risk_breakdown = risk_service.compute_risk(threat, communication)
    conflict = conflict_service.detect_conflict(threat, communication)
    confidence = confidence_service.assess_confidence(threat, communication, conflict)
    return AssessedEvidence(
        rf, threat, communication, correlation, risk_score, risk_level, risk_breakdown, conflict, confidence
    )

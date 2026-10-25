"""Module 4 — Autonomous Cyber Defense & Response Engine output model.

This module defines all Pydantic models used in Module 4's own pipeline:
- EvaluateRequest: unified input from Modules 1, 2, and 3
- EvaluateResponse: full Module 4 decision output
- BaselineResponse: simple static baseline for research comparison
- RiskBreakdown: explainable risk score decomposition
- CorrelationResult: multi-source evidence correlation details
"""

from typing import Optional
from pydantic import BaseModel, Field, field_validator

from models.module1 import RFContext
from models.module2 import ThreatIntelligence
from models.module3 import SecureCommunication


# ─── Unified Input ───────────────────────────────────────────────────────────

class EvaluateRequest(BaseModel):
    """Unified Module 4 input — combines outputs from Modules 1, 2, and 3."""

    rf_context: RFContext = Field(
        default_factory=RFContext,
        description="RF feature context from Module 1 (SDR RF Threat Detection)"
    )
    threat_intelligence: ThreatIntelligence = Field(
        description="Threat classification from Module 2 (AI Threat Intelligence)"
    )
    secure_communication: SecureCommunication = Field(
        description="Communication security state from Module 3 (Secure UAV Communication)"
    )

    @field_validator("threat_intelligence", "secure_communication", mode="before")
    @classmethod
    def require_explicit_evidence(cls, value, info):
        """Defaults for standalone models must not certify absent input as safe."""
        required = ("classification",) if info.field_name == "threat_intelligence" else (
            "link_state", "freshness_state", "auth_state", "integrity_state", "replay_detected"
        )
        if isinstance(value, BaseModel):
            supplied = value.model_fields_set
        elif isinstance(value, dict):
            supplied = value.keys()
        else:
            return value  # Pydantic supplies the structured object-type error.
        missing = [field for field in required if field not in supplied]
        if missing:
            raise ValueError(f"Missing required evidence: {', '.join(missing)}")
        return value


# ─── Risk Scoring ────────────────────────────────────────────────────────────

class RiskScoreComponent(BaseModel):
    """One additive component of the explainable risk score."""
    label: str
    source: str  # "MODULE_2_CLASSIFICATION" | "MODULE_2_SEVERITY" | "MODULE_3_LINK" | etc.
    points: float
    weight_note: str = ""


class RiskBreakdown(BaseModel):
    """Complete explainable decomposition of the risk score.

    Note: Weights are initial configurable prototype values
    pending experimental calibration.
    """
    classification_points: float
    severity_points: float
    link_state_points: float
    freshness_points: float
    auth_points: float
    integrity_points: float
    components: list[RiskScoreComponent]
    raw_total: float
    capped_score: float  # max 100


# ─── Correlation ─────────────────────────────────────────────────────────────

class SourceContribution(BaseModel):
    """One source's contribution to the multi-source correlation."""
    source: str
    evidence: list[str]
    weight: float
    normalized_score: float


class CorrelationResult(BaseModel):
    """Result of multi-source evidence correlation across Modules 2 and 3."""
    module2_classification: str
    module2_severity: Optional[str]
    module3_link_state: str
    module3_replay: bool
    source_contributions: list[SourceContribution]
    correlated_risk_boost: float  # Legacy alignment indicator; not added to risk score.
    correlation_note: str


# ─── Conflict Detection ───────────────────────────────────────────────────────

class ConflictResult(BaseModel):
    """Conflicting evidence detection result."""
    evidence_conflict: bool
    conflict_reason: Optional[str] = None
    conflict_pair: Optional[list[str]] = None  # e.g. ["MODULE_2_NORMAL", "MODULE_3_UNTRUSTED"]



class ConfidenceResult(BaseModel):
    """Decision confidence assessment."""
    level: str  # HIGH | MEDIUM | LOW
    rationale: str


# ─── Full Response Output ────────────────────────────────────────────────────

class EvaluateResponse(BaseModel):
    """Complete Module 4 decision output.

    This is the explainable, risk-aware, prioritized
    autonomous cyber-defense recommendation for UAV operation.
    """

    # Identity
    incident_id: str
    observation_id: str
    timestamp: str

    # Module 4 core outputs
    risk_score: float
    risk_level: str  # LOW | MEDIUM | HIGH | CRITICAL
    risk_breakdown: RiskBreakdown

    # Multi-source correlation
    correlation: CorrelationResult

    # Conflict detection
    evidence_conflict: bool
    conflict_reason: Optional[str] = None

    # Confidence
    decision_confidence: str  # HIGH | MEDIUM | LOW
    confidence_rationale: str

    # Response
    recommended_response: str
    response_status: str = "RECOMMENDED"
    response_rationale: str

    # Explainability
    reasons: list[str]
    pipeline_stages: list[str]

    # Baseline comparison
    baseline_response: str
    baseline_vs_proposed: str  # "SAME" | "PROPOSED_MORE_CAUTIOUS" | "PROPOSED_MORE_AGGRESSIVE" | "PROPOSED_CONTEXT_AWARE"

    # Audit trail
    module1_context: dict
    module2_context: dict
    module3_context: dict

    # File integration metadata (absent for the legacy JSON input mode)
    integration_status: Optional[str] = None
    input_sources: dict = Field(default_factory=dict)
    match_method: Optional[str] = None


# ─── Baseline Model ───────────────────────────────────────────────────────────

class BaselineResponse(BaseModel):
    """Static response baseline (no correlation, no conflict handling).

    Used in research comparison to demonstrate why Module 4's multi-source,
    conflict-aware engine produces better decisions.

    Baseline ignores: communication state, evidence consistency,
    confidence, replay, freshness, auth/integrity.
    """
    classification: str
    baseline_response: str
    baseline_rule: str
    limitation: str
    response_status: str = "RECOMMENDED"

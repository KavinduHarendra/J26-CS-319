"""Explainability service — generates human-readable decision reasons.

Every Module 4 output must explain WHY the response was selected.
This service collects evidence from all pipeline stages into a
structured list of reasons for display in the dashboard.
"""

from models.module1 import RFContext
from models.module2 import ThreatIntelligence
from models.module3 import SecureCommunication
from models.defense import RiskBreakdown, CorrelationResult, ConflictResult


def build_reasons(
    rf: RFContext,
    ti: ThreatIntelligence,
    sc: SecureCommunication,
    risk_score: float,
    risk_level: str,
    breakdown: RiskBreakdown,
    correlation: CorrelationResult,
    conflict: ConflictResult,
    confidence_level: str,
    response: str,
) -> list[str]:
    """Build an ordered list of human-readable reasons for the decision."""
    reasons: list[str] = []

    # ── Module 2 evidence ──
    reasons.append(f"Module 2 (AI Threat Intelligence) classified RF condition as: {ti.classification}")

    if ti.triggered_rule:
        reasons.append(f"Known jamming rule '{ti.triggered_rule}' was triggered by Module 2")

    if ti.severity:
        reasons.append(f"Module 2 assigned threat severity: {ti.severity}")

    for ev in ti.evidence:
        reasons.append(f"Module 2 evidence: {ev}")

    if ti.classification == "Unknown Anomaly":
        reasons.append(
            "Unknown Anomaly is treated conservatively — not a confirmed attack; "
            "environmental interference or under-catalogued threat is possible"
        )

    # ── Module 3 evidence ──
    reasons.append(f"Module 3 (Secure Communication) reports link state: {sc.link_state}")

    if sc.replay_detected:
        reasons.append(
            "Module 3 DETECTED A REPLAY ATTACK — communication integrity is compromised"
        )

    if sc.freshness_state != "FRESH":
        reasons.append(f"Module 3 reports message freshness as: {sc.freshness_state}")

    if sc.auth_state != "VALID":
        reasons.append(f"Module 3 reports authentication state as: {sc.auth_state}")

    if sc.integrity_state != "VALID":
        reasons.append(f"Module 3 reports message integrity as: {sc.integrity_state}")

    for ev in sc.link_evidence:
        if "[MOCK]" not in ev:
            reasons.append(f"Module 3 evidence: {ev}")

    # ── Risk scoring ──
    reasons.append(
        f"Dynamic risk score computed: {risk_score}/100 → Risk Level: {risk_level}"
    )
    for comp in breakdown.components:
        reasons.append(f"  ↳ {comp.label}: +{comp.points} pts [{comp.source}]")

    # ── Correlation ──
    if correlation.correlated_risk_boost > 0:
        reasons.append(
            "The evidence alignment indicator is context only; it does not add risk points"
        )
    reasons.append(f"Correlation analysis: {correlation.correlation_note}")

    # ── Conflict ──
    if conflict.evidence_conflict:
        reasons.append(f"⚠ EVIDENCE CONFLICT DETECTED: {conflict.conflict_reason}")
        reasons.append("Decision confidence reduced due to conflicting evidence")

    # ── Confidence ──
    reasons.append(f"Decision confidence assessed as: {confidence_level}")

    # ── Final response ──
    reasons.append(f"Recommended response selected: {response} (RECOMMENDATION ONLY — no action executed)")

    return reasons


def build_pipeline_stages() -> list[str]:
    """Return the ordered pipeline stage labels for dashboard visualization."""
    return [
        "INPUT VALIDATION",
        "DATA NORMALIZATION",
        "MULTI-SOURCE EVIDENCE CORRELATION",
        "DYNAMIC RISK SCORING",
        "DECISION CONFIDENCE / UNCERTAINTY HANDLING",
        "RESPONSE PRIORITIZATION",
        "EXPLAINABLE DECISION",
        "INCIDENT / AUDIT LOGGING",
    ]

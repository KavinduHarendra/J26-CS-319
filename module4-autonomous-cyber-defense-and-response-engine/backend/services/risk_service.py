"""Risk scoring service — Module 4 dynamic risk calculator.

Computes an explainable, configurable risk score (0–100) from the
outputs of Modules 2 and 3. All weights are loaded from
config/scoring_weights.py — never hard-coded here.

NOTE: These are initial prototype weights pending experimental calibration.
"""

from models.module2 import ThreatIntelligence
from models.module3 import SecureCommunication
from models.defense import RiskBreakdown, RiskScoreComponent
from config.scoring_weights import (
    CLASSIFICATION_POINTS,
    SEVERITY_POINTS,
    LINK_STATE_POINTS,
    FRESHNESS_POINTS,
    AUTH_POINTS,
    INTEGRITY_POINTS,
    RISK_SCORE_MAX,
    RISK_LEVELS,
)


def compute_risk(
    ti: ThreatIntelligence,
    sc: SecureCommunication,
) -> tuple[float, str, RiskBreakdown]:
    """Compute the overall risk score and level from Module 2 and 3 inputs.

    Returns:
        (risk_score, risk_level, risk_breakdown)
    """
    components: list[RiskScoreComponent] = []

    # Module 2 classification contribution
    cls_pts = CLASSIFICATION_POINTS.get(ti.classification, 0.0)
    components.append(RiskScoreComponent(
        label=f"RF Classification: {ti.classification}",
        source="MODULE_2_CLASSIFICATION",
        points=cls_pts,
        weight_note="Prototype weight — pending calibration",
    ))

    # Module 2 severity contribution
    sev_pts = SEVERITY_POINTS.get(ti.severity, 0.0)
    if sev_pts > 0:
        components.append(RiskScoreComponent(
            label=f"Threat Severity: {ti.severity}",
            source="MODULE_2_SEVERITY",
            points=sev_pts,
            weight_note="Prototype weight — pending calibration",
        ))

    # Module 3 link state contribution
    link_pts = LINK_STATE_POINTS.get(sc.link_state, 0.0)
    if link_pts > 0:
        components.append(RiskScoreComponent(
            label=f"Communication Link State: {sc.link_state}",
            source="MODULE_3_LINK_STATE",
            points=link_pts,
            weight_note="Prototype weight — pending calibration",
        ))

    # Module 3 freshness contribution
    fresh_pts = FRESHNESS_POINTS.get(sc.freshness_state, 0.0)
    if fresh_pts > 0:
        components.append(RiskScoreComponent(
            label=f"Message Freshness: {sc.freshness_state}",
            source="MODULE_3_FRESHNESS",
            points=fresh_pts,
            weight_note="Prototype weight — pending calibration",
        ))

    # Module 3 auth contribution
    auth_pts = AUTH_POINTS.get(sc.auth_state, 0.0)
    if auth_pts > 0:
        components.append(RiskScoreComponent(
            label=f"Authentication State: {sc.auth_state}",
            source="MODULE_3_AUTH",
            points=auth_pts,
            weight_note="Prototype weight — pending calibration",
        ))

    # Module 3 integrity contribution
    int_pts = INTEGRITY_POINTS.get(sc.integrity_state, 0.0)
    if int_pts > 0:
        components.append(RiskScoreComponent(
            label=f"Message Integrity: {sc.integrity_state}",
            source="MODULE_3_INTEGRITY",
            points=int_pts,
            weight_note="Prototype weight — pending calibration",
        ))

    raw_total = cls_pts + sev_pts + link_pts + fresh_pts + auth_pts + int_pts
    capped = min(raw_total, RISK_SCORE_MAX)

    breakdown = RiskBreakdown(
        classification_points=cls_pts,
        severity_points=sev_pts,
        link_state_points=link_pts,
        freshness_points=fresh_pts,
        auth_points=auth_pts,
        integrity_points=int_pts,
        components=components,
        raw_total=raw_total,
        capped_score=capped,
    )

    level = _risk_level(capped)
    return round(capped, 1), level, breakdown


def _risk_level(score: float) -> str:
    for low, high, label in RISK_LEVELS:
        if low <= score <= high:
            return label
    return "CRITICAL"

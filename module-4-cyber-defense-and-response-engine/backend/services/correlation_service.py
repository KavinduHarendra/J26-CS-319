"""Multi-source evidence correlation service.

Builds the cross-source correlation result showing how Module 2 and
Module 3 evidence combine to influence Module 4's decision.

This is a key research contribution — Module 4 does not use a single
signal in isolation. It explicitly tracks how each module's evidence
supports or contradicts the final decision.
"""

from models.module2 import ThreatIntelligence
from models.module3 import SecureCommunication
from models.defense import CorrelationResult, SourceContribution


def correlate(
    ti: ThreatIntelligence,
    sc: SecureCommunication,
) -> CorrelationResult:
    """Build multi-source evidence correlation result.

    Maps Module 2 and Module 3 contributions into normalized evidence
    vectors with a qualitative alignment note.
    """
    # Module 2 evidence contribution
    m2_evidence = list(ti.evidence)
    if ti.triggered_rule:
        m2_evidence.insert(0, f"Rule {ti.triggered_rule} triggered by Module 2")
    if ti.abnormal_features:
        m2_evidence.append(f"Abnormal features: {', '.join(ti.abnormal_features)}")

    # Normalize Module 2 to 0-100 score for visualization
    from config.scoring_weights import CLASSIFICATION_POINTS, SEVERITY_POINTS
    m2_cls_score = CLASSIFICATION_POINTS.get(ti.classification, 0.0)
    m2_sev_score = SEVERITY_POINTS.get(ti.severity, 0.0)
    m2_normalized = min(100.0, m2_cls_score + m2_sev_score)

    m2_contrib = SourceContribution(
        source="MODULE_2_AI_THREAT_INTELLIGENCE",
        evidence=m2_evidence,
        weight=0.60,  # Retained API metadata; not a multiplier in additive risk scoring.
        normalized_score=m2_normalized,
    )

    # Module 3 evidence contribution
    m3_evidence = list(sc.link_evidence)
    if sc.replay_detected:
        m3_evidence.insert(0, "Replay attack detected — communication integrity compromised")
    if sc.freshness_state != "FRESH":
        m3_evidence.append(f"Message freshness: {sc.freshness_state}")
    if sc.auth_state != "VALID":
        m3_evidence.append(f"Authentication state: {sc.auth_state}")
    if sc.integrity_state != "VALID":
        m3_evidence.append(f"Message integrity: {sc.integrity_state}")
    if sc.comm_decision:
        m3_evidence.append(f"Module 3 communication decision: {sc.comm_decision}")

    from config.scoring_weights import LINK_STATE_POINTS, FRESHNESS_POINTS, AUTH_POINTS, INTEGRITY_POINTS
    m3_link_score = LINK_STATE_POINTS.get(sc.link_state, 0.0)
    m3_fresh_score = FRESHNESS_POINTS.get(sc.freshness_state, 0.0)
    m3_auth_score = AUTH_POINTS.get(sc.auth_state, 0.0)
    m3_int_score = INTEGRITY_POINTS.get(sc.integrity_state, 0.0)
    m3_normalized = min(100.0, m3_link_score + m3_fresh_score + m3_auth_score + m3_int_score)

    m3_contrib = SourceContribution(
        source="MODULE_3_SECURE_COMMUNICATION",
        evidence=m3_evidence,
        weight=0.40,  # Retained API metadata; not a multiplier in additive risk scoring.
        normalized_score=m3_normalized,
    )

    # Legacy alignment indicator, retained for API compatibility, not risk points.
    correlated_boost = 0.0
    note_parts = []

    is_m2_threat = ti.classification in ("Jamming", "Unknown Anomaly")
    is_m3_degraded = sc.link_state in ("DEGRADED", "SUSPICIOUS", "UNTRUSTED")

    if is_m2_threat and is_m3_degraded:
        correlated_boost = 5.0
        note_parts.append(
            f"Module 2 ({ti.classification}) and Module 3 ({sc.link_state}) evidence is mutually reinforcing."
        )
    elif (ti.classification == "Normal" and sc.link_state == "TRUSTED"
          and sc.auth_state == "VALID" and sc.integrity_state == "VALID"
          and sc.freshness_state == "FRESH" and not sc.replay_detected and ti.severity is None):
        note_parts.append("Both Module 2 and Module 3 indicate safe conditions.")
    elif ti.classification == "Normal" and sc.link_state == "TRUSTED":
        note_parts.append(
            "RF is Normal and the link is labelled TRUSTED, but reported severity or "
            "security-state evidence prevents a safe-condition conclusion."
        )
    elif ti.classification == "Normal" and is_m3_degraded:
        note_parts.append(
            "Module 2 indicates Normal RF, but Module 3 reports communication concern. "
            "Evidence sources partially disagree."
        )
    elif is_m2_threat and sc.link_state == "TRUSTED":
        note_parts.append(
            "Module 2 detects threat but Module 3 reports trusted communication. "
            "RF threat evidence is not yet reflected in link state."
        )

    if sc.replay_detected:
        correlated_boost += 5.0
        note_parts.append("Replay attack (Module 3) provides independent corroboration of communication threat.")

    return CorrelationResult(
        module2_classification=ti.classification,
        module2_severity=ti.severity,
        module3_link_state=sc.link_state,
        module3_replay=sc.replay_detected,
        source_contributions=[m2_contrib, m3_contrib],
        correlated_risk_boost=round(correlated_boost, 1),
        correlation_note=" ".join(note_parts) if note_parts else "Correlation analysis complete.",
    )

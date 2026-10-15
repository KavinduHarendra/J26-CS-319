"""Decision confidence service — assesses how confident Module 4 is in its decision.

Confidence is based on evidence consistency and source agreement.
Outputs: HIGH | MEDIUM | LOW with a human-readable rationale.

This is distinct from risk level — a system can have HIGH risk with LOW
confidence (e.g. conflicting evidence), or LOW risk with HIGH confidence
(clear Normal + Trusted state).
"""

from models.module2 import ThreatIntelligence
from models.module3 import SecureCommunication
from models.defense import ConflictResult, ConfidenceResult


def assess_confidence(
    ti: ThreatIntelligence,
    sc: SecureCommunication,
    conflict: ConflictResult,
    trend: str,
) -> ConfidenceResult:
    """Assess Module 4's decision confidence.

    HIGH confidence conditions:
      - Jamming + triggered rule + High severity + DEGRADED/UNTRUSTED link
      - Normal + TRUSTED + no replay (clearly safe)

    MEDIUM confidence conditions:
      - Unknown Anomaly with some supporting link degradation
      - Jamming with TRUSTED link (some conflict)
      - Trend available (ESCALATING/IMPROVING)

    LOW confidence conditions:
      - Evidence conflict detected
      - Normal RF + UNTRUSTED link (major disagreement)
      - INSUFFICIENT_DATA trend + ambiguous classification
    """
    classification = ti.classification
    link_state = sc.link_state
    replay = sc.replay_detected

    # LOW confidence: conflict always reduces confidence
    if conflict.evidence_conflict:
        return ConfidenceResult(
            level="LOW",
            rationale=f"Evidence conflict detected: {conflict.conflict_reason}. "
                      "Decision confidence reduced — operator verification recommended.",
        )

    # HIGH confidence: well-corroborated evidence
    if (
        classification == "Jamming"
        and ti.severity == "High"
        and ti.triggered_rule is not None
        and link_state in ("DEGRADED", "UNTRUSTED", "SUSPICIOUS")
    ):
        return ConfidenceResult(
            level="HIGH",
            rationale=(
                f"Jamming confirmed by Module 2 (rule {ti.triggered_rule}), "
                f"severity High, and Module 3 reports link as {link_state}. "
                "Multiple independent evidence sources are consistent."
            ),
        )

    if replay:
        return ConfidenceResult(
            level="HIGH",
            rationale="Replay attack explicitly detected by Module 3. "
                      "Communication-layer attack confirmed regardless of RF classification.",
        )

    if classification == "Normal" and link_state == "TRUSTED" and not replay:
        return ConfidenceResult(
            level="HIGH",
            rationale="Module 2 reports Normal RF classification and Module 3 "
                      "reports TRUSTED link. Both sources agree system is safe.",
        )

    # MEDIUM confidence: partial evidence
    if classification == "Unknown Anomaly" and link_state in ("DEGRADED", "SUSPICIOUS"):
        return ConfidenceResult(
            level="MEDIUM",
            rationale="Unknown RF anomaly is supported by communication degradation. "
                      "Moderate confidence — anomaly source not confirmed.",
        )

    if classification == "Jamming" and link_state == "TRUSTED":
        return ConfidenceResult(
            level="MEDIUM",
            rationale="Jamming detected by Module 2 but Module 3 reports TRUSTED link. "
                      "Partial evidence — communication unaffected may indicate false positive.",
        )

    if trend in ("ESCALATING", "IMPROVING"):
        return ConfidenceResult(
            level="MEDIUM",
            rationale=f"Trend analysis shows {trend} risk pattern, "
                      "providing additional temporal context for the decision.",
        )

    # Default: medium confidence for anything not explicitly classified
    return ConfidenceResult(
        level="MEDIUM",
        rationale="Evidence is present but not strongly corroborated across multiple sources. "
                  "Moderate confidence in the recommended response.",
    )

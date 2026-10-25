"""Conflict detection service — identifies conflicting evidence across modules.

Detects cases where Module 2 and Module 3 outputs disagree in ways that
indicate the system cannot be confidently assessed. When conflict is detected:
  - evidence_conflict = True
  - confidence is reduced
  - autonomous response is made more conservative
  - operator escalation is recommended where appropriate

This is a key research contribution of Module 4 — the system explicitly
identifies and reports conflicting evidence rather than silently merging it.
"""

from models.module2 import ThreatIntelligence
from models.module3 import SecureCommunication
from models.defense import ConflictResult


def detect_conflict(
    ti: ThreatIntelligence,
    sc: SecureCommunication,
) -> ConflictResult:
    """Detect conflicting evidence between Module 2 and Module 3 outputs.

    Conflict cases:
      CASE A: Module 2 = Normal, but Module 3 link is UNTRUSTED or SUSPICIOUS
              → RF appears safe but comms are compromised
      CASE B: Module 2 = Jamming/High, but Module 3 = TRUSTED + no replay
              → Strong RF threat evidence but comms appear unaffected
      CASE C: Replay detected but RF classification is Normal
              → Communication-layer attack with no RF signature
    """
    classification = ti.classification
    severity = ti.severity
    link_state = sc.link_state
    replay = sc.replay_detected

    # A trusted link must not be described as verified safe when its own
    # authentication, integrity or freshness evidence contradicts that state.
    if link_state == "TRUSTED" and (
        sc.auth_state != "VALID" or sc.integrity_state != "VALID"
        or sc.freshness_state != "FRESH" or replay
    ):
        return ConflictResult(
            evidence_conflict=True,
            conflict_reason=(
                f"Module 3 reports TRUSTED link but authentication={sc.auth_state}, "
                f"integrity={sc.integrity_state}, freshness={sc.freshness_state}, "
                f"replay_detected={replay}. These security states require verification."
            ),
            conflict_pair=["MODULE_3_TRUSTED", "MODULE_3_SECURITY_STATE"],
        )

    # CASE A: Normal RF + compromised comms
    if classification == "Normal" and link_state in ("UNTRUSTED", "SUSPICIOUS"):
        return ConflictResult(
            evidence_conflict=True,
            conflict_reason=(
                f"RF classification is '{classification}' (no RF threat), "
                f"but communication link state is '{link_state}'. "
                "Evidence sources disagree — cannot confirm system is safe."
            ),
            conflict_pair=["MODULE_2_NORMAL", f"MODULE_3_{link_state}"],
        )

    # CASE B: High jamming but fully trusted link
    if classification == "Jamming" and severity == "High" and link_state == "TRUSTED" and not replay:
        return ConflictResult(
            evidence_conflict=True,
            conflict_reason=(
                f"Module 2 reports High severity Jamming, but Module 3 "
                f"reports communication link as TRUSTED with no replay. "
                "Strong RF threat evidence conflicts with stable communication state."
            ),
            conflict_pair=["MODULE_2_JAMMING_HIGH", "MODULE_3_TRUSTED"],
        )

    # CASE C: Replay detected but RF is Normal
    if replay and classification == "Normal":
        return ConflictResult(
            evidence_conflict=True,
            conflict_reason=(
                "Module 3 detected a replay attack, but Module 2 classifies RF as Normal. "
                "Communication-layer attack has no matching RF signature. "
                "Replay is treated as a serious condition regardless."
            ),
            conflict_pair=["MODULE_3_REPLAY", "MODULE_2_NORMAL"],
        )

    return ConflictResult(evidence_conflict=False)

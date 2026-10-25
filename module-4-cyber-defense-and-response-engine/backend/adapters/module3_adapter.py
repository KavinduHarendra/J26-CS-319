"""Adapter for Module 3 — Secure UAV Communication.

This adapter normalizes Module 3's communication security state for
consumption by Module 4's pipeline. It maps Module 3's link-state
vocabulary into Module 4's risk-scoring domain.

Module 3 integration point is isolated here so changes to Module 3's
output schema only require updates to this file.

IMPORTANT: Module 4 never overrides or replaces Module 3's communication
decision. It only uses Module 3's state as one source of evidence.
"""

from models.module3 import SecureCommunication


VALID_LINK_STATES = {"TRUSTED", "DEGRADED", "SUSPICIOUS", "UNTRUSTED"}
VALID_FRESHNESS = {"FRESH", "STALE", "REPLAY"}
VALID_AUTH = {"VALID", "SUSPICIOUS", "INVALID"}
VALID_INTEGRITY = {"VALID", "SUSPICIOUS", "INVALID"}
VALID_COMM_DECISIONS = {"MAINTAIN", "SWITCH", "BACKUP", "SECURE_HOLD", None}


def adapt(raw: dict | None) -> SecureCommunication:
    """Validate and normalize Module 3 output into typed SecureCommunication.

    Unknown/invalid values are replaced with conservative defaults
    (SUSPICIOUS for states, True for replay_detected).
    """
    if not raw:
        return _mock_default()

    link_state = raw.get("link_state", "TRUSTED")
    if link_state not in VALID_LINK_STATES:
        link_state = "SUSPICIOUS"

    freshness = raw.get("freshness_state", "FRESH")
    if freshness not in VALID_FRESHNESS:
        freshness = "STALE"

    auth = raw.get("auth_state", "VALID")
    if auth not in VALID_AUTH:
        auth = "SUSPICIOUS"

    integrity = raw.get("integrity_state", "VALID")
    if integrity not in VALID_INTEGRITY:
        integrity = "SUSPICIOUS"

    comm_decision = raw.get("comm_decision")
    if comm_decision not in VALID_COMM_DECISIONS:
        comm_decision = None

    return SecureCommunication(
        link_state=link_state,
        freshness_state=freshness,
        auth_state=auth,
        integrity_state=integrity,
        replay_detected=raw.get("replay_detected", False),
        comm_decision=comm_decision,
        link_evidence=raw.get("link_evidence", []),
    )


def _mock_default() -> SecureCommunication:
    """Return safe mock communication state when Module 3 is unavailable."""
    return SecureCommunication(
        link_state="TRUSTED",
        freshness_state="FRESH",
        auth_state="VALID",
        integrity_state="VALID",
        replay_detected=False,
        link_evidence=["[MOCK] Module 3 unavailable — using safe default communication state"],
    )


def summary_dict(sc: SecureCommunication) -> dict:
    """Return a flat audit-friendly dict of the secure communication state."""
    return {
        "link_state": sc.link_state,
        "freshness_state": sc.freshness_state,
        "auth_state": sc.auth_state,
        "integrity_state": sc.integrity_state,
        "replay_detected": sc.replay_detected,
        "comm_decision": sc.comm_decision,
        "link_evidence": sc.link_evidence,
    }

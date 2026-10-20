"""Module 3 — Secure UAV Communication output model.

Module 3 owns communication trust and security-state decisions.
This schema defines the data contract flowing from Module 3 into Module 4.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field, model_validator


LinkStateValue = Literal["TRUSTED", "DEGRADED", "SUSPICIOUS", "UNTRUSTED"]
FreshnessStateValue = Literal["FRESH", "STALE", "REPLAY"]
AuthStateValue = Literal["VALID", "SUSPICIOUS", "INVALID"]
IntegrityStateValue = Literal["VALID", "SUSPICIOUS", "INVALID"]
CommDecisionValue = Optional[Literal["MAINTAIN", "SWITCH", "BACKUP", "SECURE_HOLD"]]


class SecureCommunication(BaseModel):
    """Secure UAV Communication state produced by Module 3 (U. L. K. H. Liyanage).

    Module 3 determines whether the current UAV-GCS communication path
    can be trusted, considering controller identity, session authentication,
    message integrity, replay resistance, and link health.

    Module 4 consumes this for:
    - link state-based risk weighting
    - freshness/replay-based risk adjustment
    - auth/integrity-based risk adjustment
    - correlation with Module 2 evidence
    - conflict detection between RF classification and link state

    Module 4 does NOT make communication trust decisions itself.
    These are passed through an adapter layer so Module 3 can evolve.
    """

    link_state: LinkStateValue = Field(
        default="TRUSTED",
        description="Overall communication link security state"
    )
    freshness_state: FreshnessStateValue = Field(
        default="FRESH",
        description="Message freshness state: FRESH | STALE | REPLAY"
    )
    auth_state: AuthStateValue = Field(
        default="VALID",
        description="Authentication state: VALID | SUSPICIOUS | INVALID"
    )
    integrity_state: IntegrityStateValue = Field(
        default="VALID",
        description="Message integrity state: VALID | SUSPICIOUS | INVALID"
    )
    replay_detected: bool = Field(
        default=False,
        description="True if Module 3 has detected a replay attack on the communication channel"
    )
    comm_decision: CommDecisionValue = Field(
        default=None,
        description="Module 3's own communication decision (informational for Module 4)"
    )
    link_evidence: list[str] = Field(
        default_factory=list,
        description="Human-readable evidence strings from Module 3"
    )

    @model_validator(mode="after")
    def consistent_replay_evidence(self):
        if self.replay_detected != (self.freshness_state == "REPLAY"):
            raise ValueError("replay_detected must agree with freshness_state: REPLAY requires true; FRESH or STALE requires false")
        return self

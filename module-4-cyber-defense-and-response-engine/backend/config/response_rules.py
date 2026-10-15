"""Module 4 — Response Decision Rules.

Defines the rule table mapping (classification, link_state, trend, replay)
tuples to recommended responses.

Rules are evaluated in priority order. The FIRST matching rule wins.
Each rule is a dict with optional match criteria and the recommended response.

IMPORTANT: These rules are prototype-level decision logic for PP1 demonstration.
They are NOT final validated response policies.

Supported responses:
  MONITOR              — Normal operation, continue baseline monitoring
  CONTINUE_MONITORING  — Slightly elevated, continue with awareness
  INCREASE_MONITORING  — Anomaly detected, heighten monitoring
  PREPARE_BACKUP_CHANNEL — Active threat, prepare fallback comms
  SWITCH_TO_BACKUP     — Imminent threat, activate backup channel
  SECURE_HOLD          — High-confidence attack, enter secure hold mode
  OPERATOR_ESCALATION  — Uncertain/high-risk, require human judgment
"""

from typing import Optional


class ResponseRule:
    """A single prioritized response rule."""

    def __init__(
        self,
        name: str,
        classification: Optional[str | list[str]],
        link_states: Optional[list[str]],
        risk_min: float,
        trend: Optional[str | list[str]],
        replay: Optional[bool],
        response: str,
        rationale: str,
    ):
        self.name = name
        self.classification = [classification] if isinstance(classification, str) else classification
        self.link_states = link_states
        self.risk_min = risk_min
        self.trend = [trend] if isinstance(trend, str) else trend
        self.replay = replay
        self.response = response
        self.rationale = rationale

    def matches(self, classification: str, link_state: str, risk_score: float, trend: str, replay: bool) -> bool:
        if self.classification and classification not in self.classification:
            return False
        if self.link_states and link_state not in self.link_states:
            return False
        if risk_score < self.risk_min:
            return False
        if self.trend and trend not in self.trend:
            return False
        if self.replay is not None and replay != self.replay:
            return False
        return True


# ─── Rule Table (highest priority first) ─────────────────────────────────────

RESPONSE_RULES: list[ResponseRule] = [
    # RULE R1: Replay detected → always SECURE_HOLD regardless of classification
    ResponseRule(
        name="R1_REPLAY_SECURE_HOLD",
        classification=None,
        link_states=None,
        risk_min=0.0,
        trend=None,
        replay=True,
        response="SECURE_HOLD",
        rationale="Replay attack detected by Module 3. Communication integrity compromised. Secure hold mandatory.",
    ),

    # RULE R2: Critical risk + escalating → OPERATOR_ESCALATION
    ResponseRule(
        name="R2_CRITICAL_ESCALATING",
        classification=None,
        link_states=None,
        risk_min=75.0,
        trend="ESCALATING",
        replay=None,
        response="OPERATOR_ESCALATION",
        rationale="Critical risk with escalating trend. Autonomous response insufficient — human judgment required.",
    ),

    # RULE R3: Jamming + UNTRUSTED → SECURE_HOLD
    ResponseRule(
        name="R3_JAMMING_UNTRUSTED",
        classification="Jamming",
        link_states=["UNTRUSTED"],
        risk_min=0.0,
        trend=None,
        replay=None,
        response="SECURE_HOLD",
        rationale="Confirmed jamming combined with untrusted communication link. Maximum defensive posture.",
    ),

    # RULE R4: Jamming + DEGRADED/SUSPICIOUS → PREPARE_BACKUP_CHANNEL
    ResponseRule(
        name="R4_JAMMING_DEGRADED",
        classification="Jamming",
        link_states=["DEGRADED", "SUSPICIOUS"],
        risk_min=0.0,
        trend=None,
        replay=None,
        response="PREPARE_BACKUP_CHANNEL",
        rationale="Confirmed jamming with communication degradation. Backup channel preparation warranted.",
    ),

    # RULE R5: Unknown Anomaly + SUSPICIOUS/UNTRUSTED → OPERATOR_ESCALATION
    ResponseRule(
        name="R5_UNKNOWN_SUSPICIOUS_LINK",
        classification="Unknown Anomaly",
        link_states=["SUSPICIOUS", "UNTRUSTED"],
        risk_min=0.0,
        trend=None,
        replay=None,
        response="OPERATOR_ESCALATION",
        rationale="Unclassified RF anomaly combined with communication security concerns. Escalate to operator.",
    ),

    # RULE R6: Normal RF + UNTRUSTED link → conflicting evidence → OPERATOR_ESCALATION
    ResponseRule(
        name="R6_NORMAL_UNTRUSTED_CONFLICT",
        classification="Normal",
        link_states=["UNTRUSTED"],
        risk_min=0.0,
        trend=None,
        replay=None,
        response="OPERATOR_ESCALATION",
        rationale="RF classified Normal but communication link is UNTRUSTED. Conflicting evidence requires operator review.",
    ),

    # RULE R7: Jamming + TRUSTED + HIGH risk → PREPARE_BACKUP_CHANNEL
    ResponseRule(
        name="R7_JAMMING_TRUSTED_HIGH",
        classification="Jamming",
        link_states=["TRUSTED"],
        risk_min=50.0,
        trend=None,
        replay=None,
        response="PREPARE_BACKUP_CHANNEL",
        rationale="Confirmed jamming even though link remains trusted. Risk warrants backup channel preparation.",
    ),

    # RULE R8: Unknown Anomaly + TRUSTED → INCREASE_MONITORING
    ResponseRule(
        name="R8_UNKNOWN_TRUSTED",
        classification="Unknown Anomaly",
        link_states=["TRUSTED"],
        risk_min=0.0,
        trend=None,
        replay=None,
        response="INCREASE_MONITORING",
        rationale="Unclassified RF anomaly with trusted communication. Conservative monitoring increase appropriate.",
    ),

    # RULE R9: MEDIUM risk (any) → CONTINUE_MONITORING
    ResponseRule(
        name="R9_MEDIUM_RISK",
        classification=None,
        link_states=None,
        risk_min=25.0,
        trend=None,
        replay=None,
        response="CONTINUE_MONITORING",
        rationale="Elevated risk detected. Continue monitoring with heightened awareness.",
    ),

    # RULE R10: Normal + TRUSTED → MONITOR (baseline safe)
    ResponseRule(
        name="R10_NORMAL_SAFE",
        classification="Normal",
        link_states=["TRUSTED"],
        risk_min=0.0,
        trend=None,
        replay=None,
        response="MONITOR",
        rationale="Normal RF classification and trusted communication link. Routine monitoring sufficient.",
    ),

    # RULE R11: Default fallback
    ResponseRule(
        name="R11_DEFAULT",
        classification=None,
        link_states=None,
        risk_min=0.0,
        trend=None,
        replay=None,
        response="CONTINUE_MONITORING",
        rationale="Insufficient evidence to determine specific response. Continue monitoring.",
    ),
]


# ─── Trend-based response upgrade table ──────────────────────────────────────
# If base response is X and trend is ESCALATING, upgrade to Y.

TREND_UPGRADES: dict[str, str] = {
    "MONITOR": "INCREASE_MONITORING",
    "CONTINUE_MONITORING": "INCREASE_MONITORING",
    "INCREASE_MONITORING": "PREPARE_BACKUP_CHANNEL",
    "PREPARE_BACKUP_CHANNEL": "OPERATOR_ESCALATION",
}

# ─── Baseline rules (for research comparison) ─────────────────────────────────
# Simple IF classification THEN response — ignores all context.

BASELINE_RULES: dict[str, dict] = {
    "Normal": {
        "response": "MONITOR",
        "rule": "IF classification = Normal THEN MONITOR",
        "limitation": "Ignores link state, freshness, auth, integrity, replay, trend, and evidence consistency.",
    },
    "Unknown Anomaly": {
        "response": "INCREASE_MONITORING",
        "rule": "IF classification = Unknown Anomaly THEN INCREASE_MONITORING",
        "limitation": "Ignores link state — misses UNTRUSTED + Unknown Anomaly combination risk.",
    },
    "Jamming": {
        "response": "PREPARE_BACKUP_CHANNEL",
        "rule": "IF classification = Jamming THEN PREPARE_BACKUP_CHANNEL",
        "limitation": "Ignores link trust level — may underrespond (UNTRUSTED) or over-respond (TRUSTED).",
    },
}

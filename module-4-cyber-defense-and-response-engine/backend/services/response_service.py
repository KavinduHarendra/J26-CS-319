"""Response selection service — maps risk + context to recommended response.

Uses the prioritized rule table from config/response_rules.py.
Also computes the static baseline response for research comparison.

ALL response logic references the rule table — no magic strings here.
"""

from models.module2 import ThreatIntelligence
from models.module3 import SecureCommunication
from models.defense import ConflictResult
from config.response_rules import RESPONSE_RULES, BASELINE_RULES
from config.scoring_weights import RISK_LEVELS


def select_response(
    ti: ThreatIntelligence,
    sc: SecureCommunication,
    risk_score: float,
    conflict: ConflictResult,
) -> tuple[str, str, str]:
    """Select the recommended response using the prioritized rule table.

    Returns:
        (recommended_response, response_rationale, baseline_response)
    """
    classification = ti.classification
    link_state = sc.link_state
    replay = sc.replay_detected

    # Evaluate rules in priority order — first match wins
    selected_response = "CONTINUE_MONITORING"
    selected_rule_name = "DEFAULT"
    rationale = "Default: insufficient rule match."

    for rule in RESPONSE_RULES:
        if rule.matches(classification, link_state, risk_score, replay):
            selected_response = rule.response
            selected_rule_name = rule.name
            rationale = f"Rule {rule.name}: {rule.rationale}"
            break

    if conflict.evidence_conflict:
        if selected_response == "MONITOR":
            rationale = (
                f"Rule {selected_rule_name} selected MONITOR from classification/link criteria only. "
                "Conflicting security evidence prevents a safe-condition conclusion."
            )
        rationale += f" Evidence conflict requires verification: {conflict.conflict_reason}"
    elevated = any(low <= risk_score <= high and level in ("HIGH", "CRITICAL")
                   for low, high, level in RISK_LEVELS)
    if elevated and selected_response in ("MONITOR", "CONTINUE_MONITORING", "INCREASE_MONITORING"):
        rationale += (
            " Policy coverage review required: HIGH/CRITICAL risk matched a monitoring rule. "
            "The current policy defines no alternative for this combination; "
            "the recommendation is not a verified-safe assessment."
        )

    # Compute baseline (static classification-only, no context)
    baseline = BASELINE_RULES.get(classification, BASELINE_RULES["Normal"])
    baseline_response = baseline["response"]

    return selected_response, rationale, baseline_response


def compare_baseline(proposed: str, baseline: str) -> str:
    """Return a human-readable comparison of proposed vs baseline response."""
    ordered = [
        "MONITOR",
        "CONTINUE_MONITORING",
        "INCREASE_MONITORING",
        "PREPARE_BACKUP_CHANNEL",
        "SWITCH_TO_BACKUP",
        "OPERATOR_ESCALATION",
        "SECURE_HOLD",
    ]
    try:
        p_idx = ordered.index(proposed)
        b_idx = ordered.index(baseline)
    except ValueError:
        return "SAME"

    if p_idx == b_idx:
        return "SAME"
    elif p_idx > b_idx:
        return "PROPOSED_MORE_CAUTIOUS"
    else:
        return "PROPOSED_LESS_AGGRESSIVE"

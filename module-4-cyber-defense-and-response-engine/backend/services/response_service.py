"""Response selection service — maps risk + context to recommended response.

Uses the prioritized rule table from config/response_rules.py.
Applies trend-based response upgrades when ESCALATING trend is detected.
Also computes the static baseline response for research comparison.

ALL response logic references the rule table — no magic strings here.
"""

from models.module2 import ThreatIntelligence
from models.module3 import SecureCommunication
from models.defense import ConflictResult
from config.response_rules import RESPONSE_RULES, TREND_UPGRADES, BASELINE_RULES


def select_response(
    ti: ThreatIntelligence,
    sc: SecureCommunication,
    risk_score: float,
    trend: str,
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
    rationale = "Default: insufficient rule match."

    for rule in RESPONSE_RULES:
        if rule.matches(classification, link_state, risk_score, trend, replay):
            selected_response = rule.response
            rationale = rule.rationale
            break

    # Apply trend upgrade if ESCALATING (unless already at max response)
    if trend == "ESCALATING" and selected_response in TREND_UPGRADES:
        upgraded = TREND_UPGRADES[selected_response]
        rationale = (
            f"{rationale} Trend is ESCALATING — response upgraded from "
            f"{selected_response} to {upgraded}."
        )
        selected_response = upgraded

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

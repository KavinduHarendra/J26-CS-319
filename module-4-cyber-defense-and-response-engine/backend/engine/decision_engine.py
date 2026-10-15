"""Autonomous defense decision engine — reactive vs forecast-aware responses."""

from models.schemas import ThreatInput, ThreatAnalysisResult, ForecastResult, DecisionResult


RESPONSES = {
    "NORMAL": {
        "response": "Continue Monitoring",
        "actions": ["Maintain routine telemetry monitoring", "Log baseline RF metrics"],
    },
    "LOW": {
        "response": "Continue Monitoring",
        "actions": ["Continue monitoring", "Log event for audit trail"],
    },
    "MEDIUM": {
        "response": "Increase Monitoring",
        "actions": [
            "Increase monitoring frequency",
            "Alert operator",
            "Prepare backup communication channel",
        ],
    },
    "HIGH": {
        "response": "Recommend Backup Channel",
        "actions": [
            "Recommend backup channel switch",
            "Verify trusted controller",
            "Reject suspicious commands",
            "Alert operator",
        ],
    },
    "CRITICAL": {
        "response": "Switch to Backup Channel & Safe Mode",
        "actions": [
            "Switch to backup communication channel",
            "Reject untrusted commands",
            "Recommend safe mode",
            "Alert operator",
            "Create security incident",
        ],
    },
}

FORECAST_UPGRADE = {
    "MEDIUM": {
        "response": "Prepare Backup Communication",
        "actions": [
            "Prepare backup communication (forecast: escalation)",
            "Increase monitoring frequency",
            "Alert operator proactively",
        ],
    },
    "HIGH": {
        "response": "Pre-emptive Backup Channel Activation",
        "actions": [
            "Pre-emptively activate backup channel",
            "Verify trusted controller",
            "Reject suspicious commands",
            "Alert operator — predictive defense engaged",
        ],
    },
}


def build_reasons(data: ThreatInput, analysis: ThreatAnalysisResult, forecast: ForecastResult) -> list[str]:
    reasons = []
    for factor in analysis.risk_factors:
        reasons.append(f"{factor.label} (+{factor.points})")

    if analysis.threat_score >= 75:
        reasons.append("Threat score exceeded critical threshold")
    elif analysis.threat_score >= 50:
        reasons.append("Threat score in high-risk range")

    if data.communication_status.upper() in ("DEGRADED", "DISRUPTED"):
        reasons.append("Communication reliability degraded")

    if forecast.trend == "ESCALATING":
        reasons.append(f"Forecast indicates further escalation (slope: {forecast.trend_slope}/min)")
        if forecast.forecast_points:
            peak = forecast.forecast_points[-1].score
            reasons.append(f"Projected threat score in 15 min: {peak}/100")

    if analysis.evidence_conflict:
        reasons.append("Conflicting source evidence reduced decision confidence")
        reasons.append("Operator verification retained in the response playbook")

    return reasons


def make_decision(
    data: ThreatInput,
    analysis: ThreatAnalysisResult,
    forecast: ForecastResult,
) -> DecisionResult:
    severity = analysis.severity
    base = RESPONSES.get(severity, RESPONSES["LOW"])

    reactive_response = base["response"]
    reactive_actions = list(base["actions"])

    forecast_influenced = False
    forecast_aware_response = reactive_response
    forecast_aware_actions = list(reactive_actions)

    if forecast.trend == "ESCALATING" and severity in FORECAST_UPGRADE:
        upgrade = FORECAST_UPGRADE[severity]
        forecast_aware_response = upgrade["response"]
        forecast_aware_actions = list(upgrade["actions"])
        forecast_influenced = True
    elif forecast.trend == "ESCALATING" and severity == "CRITICAL":
        # CRITICAL already triggers maximum response; forecast adds proactive urgency
        forecast_aware_response = base["response"]
        forecast_aware_actions = base["actions"] + [
            "Pre-emptive escalation (forecast: critical threshold imminent)",
        ]
        forecast_influenced = True

    if forecast_influenced:
        primary_response = forecast_aware_response
        primary_actions = forecast_aware_actions
        decision_mode = "PROACTIVE / PREDICTIVE DEFENSE"
    else:
        primary_response = reactive_response
        primary_actions = reactive_actions
        decision_mode = "REACTIVE DEFENSE"

    reasons = build_reasons(data, analysis, forecast)

    return DecisionResult(
        reactive_response=reactive_response,
        reactive_actions=reactive_actions,
        forecast_aware_response=forecast_aware_response,
        forecast_aware_actions=forecast_aware_actions,
        primary_response=primary_response,
        primary_actions=primary_actions,
        decision_mode=decision_mode,
        reasons=reasons,
        forecast_influenced=forecast_influenced,
    )

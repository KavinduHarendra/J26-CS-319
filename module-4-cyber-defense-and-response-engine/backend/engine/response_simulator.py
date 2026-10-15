"""Simulated response execution — no real UAV control."""

from datetime import datetime
from models.schemas import SimulateResponseRequest, IncidentRecord, UAVStatus

_incident_counter = 0
_incidents: list[IncidentRecord] = []
_uav_state = UAVStatus()


def get_uav_status() -> UAVStatus:
    return _uav_state


def reset_simulation() -> UAVStatus:
    global _incident_counter
    _incident_counter = 0
    _incidents.clear()
    _uav_state = UAVStatus()
    return _uav_state


def get_incidents() -> list[IncidentRecord]:
    return list(reversed(_incidents))


def simulate_response(req: SimulateResponseRequest) -> dict:
    global _incident_counter, _uav_state

    steps = [
        "Threat detected by integrated modules (simulated input)",
        "Threat assessed — risk score calculated",
        "Risk level determined",
        "Forecast analyzed — trend evaluated",
        "Autonomous defense decision generated",
        f"Response selected: {req.primary_response}",
        "Response simulated (no real UAV control)",
    ]

    uav = _uav_state.model_copy()
    uav.current_threat = req.threat_type
    uav.threat_severity = req.severity
    uav.threat_score = req.threat_score
    uav.forecast = req.forecast_trend
    uav.recommended_response = req.primary_response

    response_lower = req.primary_response.lower()

    if "backup" in response_lower or "switch" in response_lower:
        steps.append("Primary channel: DEGRADED")
        steps.append("Backup channel: ACTIVATING...")
        steps.append("Backup channel: ACTIVE")
        uav.communication = "BACKUP CHANNEL"
        uav.primary_channel = "DEGRADED"
        uav.backup_channel = "ACTIVE"
        uav.telemetry_status = "STABLE"
        steps.append("Communication: RESTORED")
    elif "safe mode" in response_lower:
        uav.current_mode = "SAFE COMMUNICATION"
        uav.security_status = "ELEVATED PROTECTION"
        uav.communication = "BACKUP CHANNEL"
        uav.primary_channel = "DEGRADED"
        uav.backup_channel = "ACTIVE"
        steps.append("Safe mode: ACTIVATED")
    elif "monitor" in response_lower:
        uav.current_mode = "ENHANCED MONITORING"
        steps.append("Monitoring level: INCREASED")
    else:
        steps.append("Defensive posture adjusted")

    before = req.before_evidence or {"threat_score": req.threat_score, "packet_loss_pct": 18, "snr_db": 10}
    outcome = req.simulated_response_outcome.upper()
    if outcome == "INEFFECTIVE":
        after = dict(before)
        after["threat_score"] = min(100, req.threat_score + 4)
        effectiveness, incident_status = "INEFFECTIVE", "Escalated"
        steps.append("Threat remains active after simulated response")
    elif outcome == "PARTIAL":
        after = dict(before)
        after["threat_score"] = max(0, req.threat_score - 12)
        effectiveness, incident_status = "PARTIALLY EFFECTIVE", "Monitoring"
        steps.append("Threat reduced but remains above safe baseline")
    else:
        after = dict(before)
        after["threat_score"] = max(5, req.threat_score - 45)
        after["packet_loss_pct"] = max(0, float(before.get("packet_loss_pct", 0)) * 0.25)
        after["snr_db"] = float(before.get("snr_db", 20)) + 8
        effectiveness = "EFFECTIVE"
        incident_status = "Contained" if req.severity in ("HIGH", "CRITICAL") else "Logged"
        steps.append("Threat impact reduced (simulated)")

    steps.append("UAV status updated")
    steps.append("Incident logged")

    _incident_counter += 1
    now = datetime.now().strftime("%H:%M:%S")
    audit_stages = [
        "Evidence received", "Evidence normalized", "Sources correlated", "Risk calculated",
        "Forecast generated", "Decision produced", "Response recommended", "Response simulated",
        "Effectiveness evaluated", "Incident updated",
    ]
    incident = IncidentRecord(
        incident_id=f"INC-{str(_incident_counter).zfill(3)}",
        timestamp=datetime.now().strftime("%H:%M:%S"),
        uav_id=req.uav_id,
        threat=req.threat_type,
        severity=req.severity,
        score=req.threat_score,
        forecast=req.forecast_trend,
        decision=req.primary_response,
        response="Simulated",
        status=incident_status,
        effectiveness=effectiveness,
        before_evidence=before,
        after_evidence=after,
        audit_trail=[{"timestamp": now, "stage": stage} for stage in audit_stages],
    )
    _incidents.append(incident)
    _uav_state = uav

    return {
        "steps": steps,
        "uav_status": uav.model_dump(),
        "incident": incident.model_dump(),
        "effectiveness": {
            "classification": effectiveness,
            "before": before,
            "after": after,
            "explanation": "Classification is based on the simulated change in score and link-quality evidence.",
        },
        "disclaimer": "SIMULATED RESPONSE — NO REAL UAV CONTROL",
    }

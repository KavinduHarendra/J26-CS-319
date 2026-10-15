"""Autonomous Cyber Defense & Response Engine — FastAPI Backend.

Project: J26-CS-319 — AI-Driven SDR-Based Anti-Jamming and Wireless
         Threat Detection Framework for UAV Cyber Defense
Module 4 Owner: T. H. Ranasinghe

This backend exposes two distinct API surfaces:

1. MODULE 4 API (primary — new for PP1)
   POST /api/evaluate          — Full Module 4 decision pipeline
   GET  /api/evaluate/scenarios — List PP1 demo scenarios
   GET  /api/evaluate/scenarios/{id} — Get a specific scenario
   GET  /api/evaluate/incidents — All SQLite-persisted incidents
   GET  /api/evaluate/incidents/{id} — Single incident by ID
   GET  /api/evaluate/risk-history — Risk score history for trend chart
   GET  /api/evaluate/status       — Module 4 status

2. LEGACY API (preserved — existing ThreatSimulation page)
   POST /api/analyze
   POST /api/simulate-response
   POST /api/prioritize-threats
   GET  /api/uav-status
   GET  /api/incidents
   POST /api/reset
   GET  /api/scenarios/{id}
   GET  /api/health
"""

from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware

# Legacy imports — preserved for ThreatSimulation page
from models.schemas import ThreatInput, FullAnalysisResult, SimulateResponseRequest, MultiThreatRequest
from engine.threat_scoring import analyze_threat
from engine.forecasting import compute_forecast
from engine.decision_engine import make_decision
from engine.response_simulator import (
    simulate_response,
    get_uav_status,
    get_incidents,
    reset_simulation,
)
from data.scenarios import SCENARIOS

# Module 4 imports
from models.defense import EvaluateRequest
from services.pipeline import run_pipeline
from services import audit_service, trend_service
from data.evaluate_scenarios import EVALUATE_SCENARIOS, ESCALATION_SEQUENCE
from services.file_integration_service import build_request, IntegrationValidationError

# ─── Application ──────────────────────────────────────────────────────────────

app = FastAPI(
    title="Autonomous Cyber Defense & Response Engine",
    description=(
        "Module 4 — T. H. Ranasinghe | "
        "Research Prototype — UAV Cyber Defense Decision Engine | "
        "Project J26-CS-319 | SLIIT"
    ),
    version="0.2.0-prototype",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialise SQLite database on startup
@app.on_event("startup")
def startup():
    audit_service.init_db()


# ═══════════════════════════════════════════════════════════════════════════════
# MODULE 4 API — PRIMARY EVALUATE PIPELINE
# ═══════════════════════════════════════════════════════════════════════════════

@app.post("/api/evaluate")
def evaluate(request: EvaluateRequest):
    """POST /api/evaluate — Full Module 4 decision pipeline.

    Accepts unified input from Modules 1, 2, and 3.
    Runs the complete 11-stage pipeline.
    Returns the explainable, risk-aware, trend-aware defense decision.
    All outputs are marked SIMULATED — no real UAV control.
    """
    result = run_pipeline(request)
    return result.model_dump()


@app.post("/api/evaluate-files")
async def evaluate_files(
    module2_file: UploadFile = File(...),
    module3_file: UploadFile = File(...),
):
    """Evaluate validated Module 2 and Module 3 JSON files."""
    try:
        request, metadata = await build_request(module2_file, module3_file)
        return run_pipeline(request, integration_metadata=metadata).model_dump()
    except IntegrationValidationError as exc:
        return exc.as_dict()


@app.get("/api/evaluate/scenarios")
def list_evaluate_scenarios():
    """GET /api/evaluate/scenarios — List all PP1 demo scenarios."""
    return {
        "scenarios": [
            {
                "id": key,
                "label": val["label"],
                "description": val["description"],
                "expected_risk_level": val.get("expected_risk_level"),
                "expected_response": val.get("expected_response"),
            }
            for key, val in EVALUATE_SCENARIOS.items()
        ],
        "escalation_sequence": [
            {"step": s["step"], "label": s["label"]} for s in ESCALATION_SEQUENCE
        ],
        "disclaimer": "SIMULATED MOCK DATA — Research Prototype PP1",
    }


@app.get("/api/evaluate/scenarios/{scenario_id}")
def get_evaluate_scenario(scenario_id: str):
    """GET /api/evaluate/scenarios/{id} — Get a specific scenario payload."""
    if scenario_id not in EVALUATE_SCENARIOS:
        raise HTTPException(status_code=404, detail=f"Scenario '{scenario_id}' not found.")
    scenario = EVALUATE_SCENARIOS[scenario_id]
    return {
        "id": scenario_id,
        "label": scenario["label"],
        "description": scenario["description"],
        "payload": scenario["payload"],
        "expected_risk_level": scenario.get("expected_risk_level"),
        "expected_response": scenario.get("expected_response"),
        "disclaimer": "SIMULATED MOCK DATA",
    }


@app.get("/api/evaluate/escalation/{step}")
def get_escalation_step(step: int):
    """GET /api/evaluate/escalation/{step} — Get a step in the escalating attack sequence."""
    for s in ESCALATION_SEQUENCE:
        if s["step"] == step:
            return {
                "step": s["step"],
                "label": s["label"],
                "payload": s["payload"],
                "disclaimer": "SIMULATED MOCK DATA",
            }
    raise HTTPException(status_code=404, detail=f"Escalation step {step} not found.")


@app.get("/api/evaluate/incidents")
def get_evaluate_incidents(limit: int = 100):
    """GET /api/evaluate/incidents — All Module 4 SQLite-persisted incidents."""
    incidents = audit_service.get_all_incidents(limit=limit)
    return {
        "incidents": incidents,
        "count": len(incidents),
        "disclaimer": "Module 4 Audit Log — SQLite",
    }


@app.get("/api/evaluate/incidents/{incident_id}")
def get_evaluate_incident(incident_id: str):
    """GET /api/evaluate/incidents/{id} — Single incident by ID."""
    incident = audit_service.get_incident_by_id(incident_id)
    if not incident:
        raise HTTPException(status_code=404, detail=f"Incident '{incident_id}' not found.")
    return incident


@app.get("/api/evaluate/risk-history")
def get_risk_history(limit: int = 50):
    """GET /api/evaluate/risk-history — Risk score history for trend chart."""
    history = audit_service.get_risk_history(limit=limit)
    return {
        "history": history,
        "count": len(history),
        "current_window": trend_service.get_history(),
        "disclaimer": "Risk score history from Module 4 SQLite audit log",
    }


@app.get("/api/evaluate/status")
def get_module4_status():
    """GET /api/evaluate/status — Module 4 engine status."""
    history = trend_service.get_history()
    from services.trend_service import compute_trend
    trend = compute_trend()
    return {
        "module": "MODULE_4_AUTONOMOUS_CYBER_DEFENSE_RESPONSE_ENGINE",
        "owner": "T. H. Ranasinghe",
        "project": "J26-CS-319",
        "status": "OPERATIONAL",
        "mode": "SIMULATION",
        "upstream_modules": {
            "module1_sdr_rf_detection": "MOCK_ADAPTER",
            "module2_ai_threat_intelligence": "MOCK_ADAPTER",
            "module3_secure_communication": "MOCK_ADAPTER",
        },
        "trend_window": history,
        "current_trend": trend.trend,
        "response_status": "SIMULATED — NO REAL UAV CONTROL",
        "disclaimer": "Research Prototype — PP1",
    }


@app.post("/api/evaluate/reset")
def reset_evaluate():
    """POST /api/evaluate/reset — Clear incident history and trend window."""
    trend_service.reset_history()
    audit_service.clear_all()
    return {
        "message": "Module 4 simulation state reset",
        "trend_window": [],
        "incidents_cleared": True,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# LEGACY API — PRESERVED FOR EXISTING THREAT SIMULATION PAGE
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "prototype": True,
        "label": "Research Prototype / Simulated Data",
        "module4_evaluate_api": "/api/evaluate",
    }


@app.get("/api/scenarios")
def list_scenarios():
    return {
        "scenarios": [
            {"id": key, "label": val["label"], "threat_type": val["threat_type"]}
            for key, val in SCENARIOS.items()
        ],
        "disclaimer": "Predefined prototype scenarios with simulated data",
    }


@app.get("/api/scenarios/{scenario_id}")
def get_scenario(scenario_id: str):
    if scenario_id not in SCENARIOS:
        return {"error": "Scenario not found"}
    return {"scenario": SCENARIOS[scenario_id], "disclaimer": "Simulated Data"}


@app.post("/api/analyze", response_model=FullAnalysisResult)
def analyze_threat_endpoint(data: ThreatInput):
    analysis = analyze_threat(data)
    forecast = compute_forecast(
        analysis.threat_score,
        data.previous_threat_score,
        data.threat_type,
    )
    decision = make_decision(data, analysis, forecast)

    uav = get_uav_status()
    uav.current_threat = analysis.threat_type
    uav.threat_severity = analysis.severity
    uav.threat_score = analysis.threat_score
    uav.forecast = forecast.trend
    uav.recommended_response = decision.primary_response

    return FullAnalysisResult(
        input=data,
        analysis=analysis,
        forecast=forecast,
        decision=decision,
        uav_status=uav.model_dump(),
    )


@app.post("/api/prioritize-threats")
def prioritize_threats(req: MultiThreatRequest):
    ranked = []
    for item in req.threats:
        analysis = analyze_threat(item)
        ranked.append({
            "uav_id": item.uav_id,
            "threat_type": item.threat_type,
            "score": analysis.threat_score,
            "severity": analysis.severity,
        })
    ranked.sort(key=lambda item: item["score"], reverse=True)
    return {
        "primary_threat": ranked[0] if ranked else None,
        "secondary_threats": ranked[1:],
        "reason": "Highest correlated risk score drives the primary response.",
        "disclaimer": "SIMULATED MULTI-THREAT INPUT",
    }


@app.post("/api/simulate-response")
def simulate_response_endpoint(req: SimulateResponseRequest):
    return simulate_response(req)


@app.get("/api/uav-status")
def uav_status():
    return {"status": get_uav_status().model_dump(), "disclaimer": "Simulated UAV Status"}


@app.get("/api/incidents")
def incidents():
    return {
        "incidents": [i.model_dump() for i in get_incidents()],
        "disclaimer": "Prototype Incident Log",
    }


@app.post("/api/reset")
def reset():
    status = reset_simulation()
    return {"message": "Simulation reset", "uav_status": status.model_dump()}

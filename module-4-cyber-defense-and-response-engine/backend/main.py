from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Module 4 imports
from models.defense import EvaluateRequest
from services.pipeline import run_pipeline
from services import audit_service
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
@app.exception_handler(audit_service.IncidentLimitError)
async def incident_limit_handler(request, exc):
    return JSONResponse(status_code=409, content={"detail": str(exc)})


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
    Returns evidence correlation, current risk, response recommendation,
    and a persisted explanation. No defensive action is executed.
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


@app.get("/api/incidents")
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
    """GET /api/evaluate/risk-history — Recorded risk score history for audit review."""
    history = audit_service.get_risk_history(limit=limit)
    return {
        "history": history,
        "count": len(history),
        "disclaimer": "Risk score history from Module 4 SQLite audit log",
    }


@app.get("/api/evaluate/status")
def get_module4_status():
    """GET /api/evaluate/status — Module 4 engine status."""
    return {
        "module": "MODULE_4_AUTONOMOUS_CYBER_DEFENSE_RESPONSE_ENGINE",
        "owner": "T. H. Ranasinghe",
        "project": "J26-CS-319",
        "status": "OPERATIONAL",
        "mode": "RECOMMENDATION_ONLY",
        "upstream_modules": {
            "module1_sdr_rf_detection": "MOCK_ADAPTER",
            "module2_ai_threat_intelligence": "MOCK_ADAPTER",
            "module3_secure_communication": "MOCK_ADAPTER",
        },
        "response_status": "RECOMMENDED",
        "disclaimer": "Research Prototype — PP1",
    }


@app.post("/api/evaluate/reset")
def reset_evaluate():
    """POST /api/evaluate/reset — Clear incident audit history."""
    audit_service.clear_all()
    return {
        "message": "Module 4 audit history cleared",
        "incidents_cleared": True,
    }


# ═══════════════════════════════════════════════════════════════════════════════
# HEALTH CHECK API
# ═══════════════════════════════════════════════════════════════════════════════

@app.get("/api/health")
def health():
    return {
        "status": "ok",
        "prototype": True,
        "label": "Research Prototype / Simulated Data",
        "module4_evaluate_api": "/api/evaluate",
    }

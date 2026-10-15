# Autonomous Cyber Defense & Response Engine

**Module 4 — T. H. Ranasinghe**
Project J26-CS-319 | AI-Driven SDR-Based Anti-Jamming and Wireless Threat Detection Framework for UAV Cyber Defense | SLIIT

---

## Research Novelty

> *"An explainable RF-aware autonomous cyber-defense decision engine that correlates UAV wireless threat intelligence with secure-communication state, performs dynamic risk assessment and short-term threat-trend analysis, handles conflicting evidence and uncertainty, and prioritizes context-aware defensive responses."*

Module 4 is the final decision-making layer of the four-component framework:

```
RF Environment
    ↓
Module 1: SDR RF Threat Detection       (W.H.M.S.R. Bandara)
    ↓
Module 2: AI Threat Intelligence        (N.K.B.H. Rathnayake)
    ↓
Module 3: Secure UAV Communication      (U.L.K.H. Liyanage)
    ↓
Module 4: Autonomous Cyber Defense &    (T.H. Ranasinghe)
          Response Engine               ← THIS COMPONENT
```

---

## Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+

### Run (double-click or PowerShell)

```powershell
.\start-prototype.ps1
```

The browser will open automatically at **http://localhost:5173**

### Manual Start

```powershell
# Terminal 1 — Backend
cd backend
py -m uvicorn main:app --reload --port 8000

# Terminal 2 — Frontend
cd frontend
npm run dev
```

---

## Module 4 API

### Primary Endpoint

```
POST http://localhost:8000/api/evaluate
```

**Request Body:**
```json
{
  "rf_context": {
    "observation_id": "OBS00123",
    "timestamp": "2026-09-26T14:32:01",
    "rssi": -61.4,
    "snr": 24.1,
    "noise_floor": -89.7,
    "packet_rate": 98.3
  },
  "threat_intelligence": {
    "classification": "Jamming",
    "severity": "High",
    "triggered_rule": "J01",
    "evidence": ["Significant SNR drop combined with noise floor increase"],
    "abnormal_features": []
  },
  "secure_communication": {
    "link_state": "DEGRADED",
    "freshness_state": "FRESH",
    "auth_state": "VALID",
    "integrity_state": "VALID",
    "replay_detected": false,
    "comm_decision": "BACKUP",
    "link_evidence": ["Packet delivery degraded"]
  }
}
```

**Response includes:**
- `risk_score` (0–100), `risk_level` (LOW/MEDIUM/HIGH/CRITICAL)
- `risk_breakdown` — explainable per-component points
- `correlation` — multi-source evidence correlation
- `evidence_conflict` + `conflict_reason`
- `trend` + `trend_window`
- `decision_confidence` + `confidence_rationale`
- `recommended_response` + `response_rationale`
- `reasons` — ordered explainability chain
- `baseline_response` + `baseline_vs_proposed`
- `response_status: "SIMULATED"`

### Other Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/evaluate/scenarios` | List all 9 PP1 demo scenarios |
| GET | `/api/evaluate/scenarios/{id}` | Get scenario payload |
| GET | `/api/evaluate/escalation/{step}` | Get escalation step (1–3) |
| GET | `/api/evaluate/incidents` | SQLite incident log |
| GET | `/api/evaluate/incidents/{id}` | Single incident |
| GET | `/api/evaluate/risk-history` | Risk score history |
| GET | `/api/evaluate/status` | Module 4 status |
| POST | `/api/evaluate/reset` | Reset simulation state |

---

## Unit Tests

```powershell
cd backend
py -m pytest tests/ -v
```

**43 tests:** risk scoring, response selection, conflict detection, confidence, and 9 integration scenarios.

---

## PP1 Demo Flow

1. Open **http://localhost:5173** → **Evaluate — Module 4** page (default)
2. Click any **PP1 Demo Scenario** button to load a preset
3. Observe 3 input panels (RF Context, Threat Intelligence, Secure Communication)
4. Click **EVALUATE — Run Module 4 Pipeline**
5. Review:
   - Overall Risk Score gauge (0–100)
   - Risk Level (LOW/MEDIUM/HIGH/CRITICAL)
   - Trend (INSUFFICIENT_DATA/STABLE/ESCALATING/IMPROVING)
   - Decision Confidence (HIGH/MEDIUM/LOW)
   - Evidence Conflict flag
   - Recommended Response (with SIMULATED status)
   - Multi-Source Correlation view
   - Dynamic Risk Score Breakdown
   - Explainability panel — "WHY THIS DECISION?"
   - Baseline comparison
6. Run the **Escalating Attack Sequence** (Steps 1→2→3) to demonstrate trend analysis
7. View **Risk Score History** chart populating across evaluations

---

## Architecture

```
backend/
  main.py                    ← FastAPI — all API routes
  config/
    scoring_weights.py       ← All risk weights (pending calibration)
    response_rules.py        ← Prioritized response rule table
  models/
    module1.py               ← RFContext (Module 1 contract)
    module2.py               ← ThreatIntelligence (Module 2 contract)
    module3.py               ← SecureCommunication (Module 3 contract)
    defense.py               ← EvaluateRequest/Response + all output models
  adapters/
    module1_adapter.py       ← Module 1 integration point
    module2_adapter.py       ← Module 2 integration point (enforces rules)
    module3_adapter.py       ← Module 3 integration point (conservative defaults)
  services/
    pipeline.py              ← 11-stage orchestrator
    risk_service.py          ← Dynamic risk scoring
    trend_service.py         ← Rolling window trend analysis
    conflict_service.py      ← Conflicting evidence detection
    confidence_service.py    ← Decision confidence assessment
    correlation_service.py   ← Multi-source evidence correlation
    response_service.py      ← Rule-table response selection
    explanation_service.py   ← Explainability reason chain builder
    audit_service.py         ← SQLite persistence
  database/
    incidents.db             ← Generated at runtime
  data/
    evaluate_scenarios.py    ← 9 PP1 demo scenarios
  tests/
    test_risk.py             ← 8 risk scoring tests
    test_response.py         ← 11 response selection tests
    test_conflicts.py        ← 12 conflict + confidence tests
    test_integration.py      ← 12 end-to-end pipeline tests

frontend/src/
  pages/
    Evaluate.tsx             ← Main Module 4 dashboard (PP1)
    Dashboard.tsx            ← UAV status + incident log
    ThreatSimulation.tsx     ← Legacy threat simulation
```

---

## Scoring Weights

> **IMPORTANT:** These are initial configurable prototype values pending experimental calibration.

| Component | Value | Source |
|-----------|-------|--------|
| Normal classification | 0 pts | Module 2 |
| Unknown Anomaly | 20 pts | Module 2 |
| Jamming | 35 pts | Module 2 |
| Severity Low | +10 pts | Module 2 |
| Severity Medium | +20 pts | Module 2 |
| Severity High | +30 pts | Module 2 |
| Link TRUSTED | 0 pts | Module 3 |
| Link DEGRADED | +15 pts | Module 3 |
| Link SUSPICIOUS | +25 pts | Module 3 |
| Link UNTRUSTED | +35 pts | Module 3 |
| Freshness FRESH | 0 pts | Module 3 |
| Freshness STALE | +10 pts | Module 3 |
| Freshness REPLAY | +25 pts | Module 3 |
| Auth/Integrity VALID | 0 pts | Module 3 |
| Auth/Integrity SUSPICIOUS | +10 pts | Module 3 |
| Auth/Integrity INVALID | +25 pts | Module 3 |

Edit `backend/config/scoring_weights.py` to change weights without touching business logic.

---

## Disclaimer

> All responses are **SIMULATED**. No real UAV hardware is connected or controlled.
> This is a research prototype for PP1 demonstration purposes only.
> Scoring weights are initial prototype values pending experimental calibration.

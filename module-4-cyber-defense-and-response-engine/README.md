# Autonomous Cyber Defense & Response Engine

**Module 4 — T. H. Ranasinghe**
Project J26-CS-319 | AI-Driven SDR-Based Anti-Jamming and Wireless Threat Detection Framework for UAV Cyber Defense | SLIIT

---

## Research Novelty

> *"An explainable RF-aware autonomous cyber-defense decision engine that correlates UAV wireless threat intelligence with secure-communication state, performs dynamic risk assessment, handles conflicting evidence and uncertainty, and prioritizes context-aware defensive responses."*

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
- `decision_confidence` + `confidence_rationale`
- `recommended_response` + `response_rationale`
- `reasons` — ordered explainability chain
- `baseline_response` + `baseline_vs_proposed`
- `response_status: "RECOMMENDED"`

### Other Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/api/evaluate/scenarios` | List all 11 preset scenarios |
| GET | `/api/evaluate/scenarios/{id}` | Get scenario payload |
| GET | `/api/evaluate/escalation/{step}` | Load progressive test input (1–3) |
| GET | `/api/evaluate/incidents` | SQLite incident log |
| GET | `/api/evaluate/incidents/{id}` | Single incident |
| GET | `/api/evaluate/risk-history` | Risk score history |
| GET | `/api/evaluate/status` | Module 4 status |
| POST | `/api/evaluate/reset` | Clear audit history |

---

## Unit Tests

```powershell
cd backend
py -m pytest tests/ -v
```

**80 tests:** risk scoring, response recommendations, conflict detection, confidence, file integration, audit persistence, scope checks, and scenario regressions.

---

## PP1 Demo Flow

1. Open **http://localhost:5173** → **Evaluate — Module 4** page (default)
2. Click any **PP1 Demo Scenario** button to load a preset
3. Observe 3 input panels (RF Context, Threat Intelligence, Secure Communication)
4. Click **EVALUATE — Run Module 4 Pipeline**
5. Review:
   - Overall Risk Score gauge (0–100)
   - Risk Level (LOW/MEDIUM/HIGH/CRITICAL)
   - Decision Confidence (HIGH/MEDIUM/LOW)
   - Evidence Conflict flag
   - Recommended Response (with RECOMMENDED status)
   - Multi-Source Correlation view
   - Dynamic Risk Score Breakdown
   - Explainability panel — "WHY THIS DECISION?"
   - Baseline comparison
6. Run the **Escalating Attack Sequence** (Steps 1→2→3) to compare risk assessments for progressively degraded inputs
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
    pipeline.py              ← Current-evidence decision orchestrator
    risk_service.py          ← Dynamic risk scoring
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
    test_response.py         ← 10 response selection tests
    test_conflicts.py        ← 12 conflict + confidence tests
    test_integration.py      ← 12 end-to-end pipeline tests

frontend/src/
  pages/
    Evaluate.tsx             ← Main Module 4 dashboard (PP1)
    Dashboard.tsx            ← Observation risk summary + SQLite audit log
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

> All responses are **RECOMMENDATIONS ONLY**. No defensive action is executed and no UAV hardware is controlled.
> This is a research prototype for PP1 demonstration purposes only.
> Scoring weights are initial prototype values pending experimental calibration.

## Revised Module 4 Scope

The component has four objectives:

1. Correlate AI Threat Intelligence and Secure Communication evidence, match observation IDs, and detect conflicts.
2. Calculate explainable current cyber-risk scores and risk levels using configured weights.
3. Select risk-based defensive recommendations without executing them.
4. Explain each decision and persist its evidence, triggered detection rule, risk, recommendation, observation ID, and timestamp in SQLite.

Defense Evaluation accepts Module 2 and Module 3 JSON files. Defense Testing uses preset or manually entered evidence through the same evaluation pipeline. The Defense Dashboard reads persisted Module 4 audit records.

### File integration

`POST /api/evaluate-files` accepts multipart fields `module2_file` and `module3_file`. Matching observation IDs are preferred; the existing timestamp fallback (within five seconds when Module 3 has no observation ID) remains supported. Mismatched IDs or invalid files return the existing structured validation errors without creating audit entries.

### Scope cleanup and API compatibility

The `/api/evaluate`, `/api/evaluate-files`, evaluation scenario, incident, risk-history, status, and audit-reset URLs remain. The legacy `/api/analyze`, `/api/scenarios`, and `/api/prioritize-threats` routes have been removed with the duplicate pipeline. Current-evidence scoring weights and recommendation identifiers are unchanged.

Forecasting, temporal response upgrades, response execution simulation, simulated UAV state changes, response effectiveness evaluation, and browser-side fallback simulation have been removed. No adaptive policy learning, model retraining, or MAVLink execution implementation was found.

Intentional contract changes required by this cleanup:

- Evaluation output no longer includes `trend` or `trend_window`; `response_status` is `RECOMMENDED`.
- Legacy Threat Analysis APIs and models are removed. All active evaluations use the Module 4 pipeline.
- `/api/simulate-response`, `/api/uav-status`, and the simulation-only `/api/reset` are removed.
- Risk-history and status responses no longer include temporal analysis fields.
- Existing SQLite rows and full historical snapshots remain untouched. The old nullable `trend` database column is reserved for database compatibility and is not used in new decisions.

Retained recommendations include MONITOR, CONTINUE_MONITORING, INCREASE_MONITORING, PREPARE_BACKUP_CHANNEL, SECURE_HOLD, and OPERATOR_ESCALATION. These are labels for proposed actions, not execution commands. No new response policy was added during cleanup.

### Validation

Run backend regression tests from `backend` with `py -m pytest tests -q`. Tests use temporary SQLite databases and do not clear application audit records. From `frontend`, run `npm run build` and `npm run lint`.
## Unified Defense Testing

The sidebar has exactly three pages: Defense Evaluation, Defense Testing, and Defense Dashboard.

Defense Evaluation uploads files to `/api/evaluate-files`. Defense Testing submits preset or manual `EvaluateRequest` inputs to `/api/evaluate`. Both routes normalize through the same models and adapters, call `services/pipeline.py`, use `config/scoring_weights.py` and `config/response_rules.py`, and write to the same SQLite audit store. There is no legacy RF/AI/history blended risk calculation.

Defense Testing contains 11 presets, the existing progressive test sequence, Module 1/2/3 manual inputs, correlated and normalized evidence, risk score/level, risk breakdown, response recommendation, explanations, and recorded risk history. Reset Inputs clears only the form and current result; saved audit records remain.

Optional supporting context now includes RF bandwidth, packet-loss percentage, latency, and Module 2 `threat_confidence` (0–1). These fields are recorded and shown as evidence. They do not add scoring weights, change thresholds, or alter the existing confidence assessment rules. In Module 2 files, the optional RF measurements can be supplied in an `rf_context` object; the existing `statistical_deviation` input remains supported as Module 2 evidence. Deviation z-scores are not presented as physical RF measurements.

The extra scenarios cover suspicious-command evidence and message-integrity failure. They use the current Module 2 classifications (Normal, Jamming, Unknown Anomaly) and Module 3 states. Unsupported legacy threat names are not added as new classifications or assigned invented weights.

Regression checks compare manual and file evaluations for all 11 scenarios, including normalized evidence, risk breakdown, recommended response, explanation, and audit persistence. Both paths reject out-of-range context values; file errors use the structured integration-error format.

### PP1 stability validation

Manual requests must explicitly supply Module 2 classification and Module 3 link, freshness, authentication, integrity, and replay states. Missing security evidence is rejected rather than interpreted as safe. Replay detection and `freshness_state: REPLAY` must agree; inconsistent inputs are rejected rather than assigned an invented risk adjustment. JSON boolean strings such as `"false"` are parsed as booleans.

For timestamp fallback, both timestamps must include timezone offsets, or both must omit them. Mixed formats return `TIMESTAMP_TIMEZONE_MISMATCH`; the application does not assume a timezone. Matching observation IDs retain priority.

The PP1 regression run passed 135 backend tests, TypeScript/production build, and frontend lint. HTTP checks compared all 11 scenarios through both evaluation routes against a disposable database. See [PP1_STABILIZATION_REPORT.md](PP1_STABILIZATION_REPORT.md) for demonstration results, remaining response-policy decisions, and browser-verification limitations. Scoring weights, thresholds, and response rules were not changed during stabilization.

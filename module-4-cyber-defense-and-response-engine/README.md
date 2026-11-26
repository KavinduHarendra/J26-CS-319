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

## Response ML research data

The current phase prepares a labeled dataset workflow for a future Random Forest and Decision Tree comparison. The rule-based engine still supplies the recommendation. The two existing rule outputs are kept in separate CSV columns so each can be compared later.

### Set up the local Python tools

In this workspace, run the examples below from the project root in PowerShell with:

```powershell
$python = (Resolve-Path .\.venv\python.exe).Path
```

On a fresh checkout with a standard Python installation, create the environment from the project root:

```powershell
py -3 -m venv .venv
$python = (Resolve-Path .\.venv\Scripts\python.exe).Path
& $python -m pip install -r .\backend\requirements-ml.txt
```

For a standard virtual environment, run the `-m response_ml` commands from `backend` and start path arguments to project-root folders with `..\`. The bundled workspace runtime already knows the backend import path, so the examples below can run from the project root as written. The dataset tools use Python's CSV library and the same Pydantic validation used by the backend.

### Generate and validate a synthetic dataset

```powershell
& $python -m response_ml generate --output .response-ml/v1.2-rerun/synthetic_dataset.csv --count 1000 --seed 42 --session-size 10
& $python -m response_ml validate .response-ml/v1.2-rerun/synthetic_dataset.csv
& $python -m response_ml prepare-review .response-ml/v1.2-rerun/synthetic_dataset.csv --output-dir .response-ml/v1.2-rerun/review --count 144 --seed 42
```

The seed makes the results reproducible. The v1.2 settings above produce 1,000 observations in 100 generated session groups across 18 families. The generator samples complete communication profiles and compatible RF profiles, favors variation within families, and gives less represented contextual responses priority among similarly varied cases. V1.1 remains available at `.response-ml/synthetic_dataset.csv`. The validator checks the schema, provenance, required evidence categories, duplicates, labels and computed risk/response values. Generated rows use `SYNTHETIC`, `PYTHON_GENERATED` and `PENDING`. Report any future prototype scores as synthetic-data results. Use a new output path for each export.

The review command writes the full comparison sample, its blind variant, a private review key, and a proposed split with class-support counts. Share the blind CSV and the rubric for the reviewer's first pass. Read the proposed [rubric](docs/response-ml/response-rubric-v0.1-draft.md) and [evaluation plan](docs/response-ml/evaluation-plan-v1.2.md) before approving labels or starting training.

See the [34-column data dictionary](docs/response-ml/data-dictionary.md), [generated sample rows](docs/response-ml/example-synthetic.csv), and [labeling guide](docs/response-ml/labeling-guide.md). Keep generated files and real evidence under the Git-ignored `.response-ml` folder.

### Recheck the ChatGPT scenario fixtures

The 23 pairs in `integration_input/Module2` and `integration_input/Module3` are ChatGPT-generated scenario fixtures. The batch manifest identifies them as `SYNTHETIC` and `CHATGPT_GENERATED`. Their collection output stays separate from the seeded Python dataset and preserves blank session, experiment, and scenario IDs. Use the fixtures for scenario development, labeling practice and integration checks.

```powershell
& $python -m response_ml collect --manifest .response-ml/upstream-23.manifest.json --output-dir .response-ml/chatgpt-rerun --csv-name collected_dataset.csv
& $python -m response_ml validate .response-ml/chatgpt-rerun/collected_dataset.csv
```

### Collect paired JSON from the research group

1. Ask Module 2 and Module 3 for the original structured exports, shared observation and session IDs, experiment ID, and observed timestamps with UTC offsets. Save the original files under `.response-ml/actual-inputs`. Keep security-sensitive evidence and experimental outcome files in controlled storage.
2. Copy the [example manifest](docs/response-ml/collection-manifest.example.json) into that folder as `manifest.json`. Use one entry per pair. Set `data_source` to `CONTROLLED_EXPERIMENT` for verified lab or simulator observations, `REAL_TESTBED` for verified testbed observations, or `UNCONFIRMED` when the source is unknown. Leave generation provenance blank. Leave unreported session, experiment, or scenario IDs blank for unconfirmed data. File paths are relative to the manifest. If the Module 2 timestamp lacks an offset, supply the collector-confirmed `naive_timestamp_offset` for that entry, such as `+05:30`. Optional `outcome_ref` points to a separate outcome record for the reviewer.
3. Run the collector and validator using a new output directory:

```powershell
& $python -m response_ml collect --manifest .response-ml/actual-inputs/manifest.json --output-dir .response-ml/actual-exp-001
& $python -m response_ml validate .response-ml/actual-exp-001/observations.csv
```

The output includes `observations.csv` and `evidence-index.json`. The index records the file paths, checksums and pairing method. Keep it with the manifest and original files so you can trace a row back to its evidence. The collector uses the existing file parser and creates research files without writing to the incident database.

Check the two representative exports currently in `integration_input`:

```powershell
& $python -m response_ml inspect-pair "integration_input/Module2/Module_2 Output_1.json" "integration_input/Module3/Module_3 Output_1.json" --expect-observation-id OBS00123 --expect-risk-score 80 --expect-risk-level CRITICAL --expect-response PREPARE_BACKUP_CHANNEL
```

### Configure the research mode and run checks

Set `MODULE4_RESPONSE_MODE` in the same PowerShell session before starting the backend. The default is `RULE_BASED` and retains the original response JSON shape. `SHADOW` records the 15 pre-decision features with `WAITING_FOR_MODEL` in the response and audit snapshot. `MACHINE_LEARNING` reports `APPROVAL_REQUIRED` and keeps the contextual rule recommendation in effect. These modes prepare the interface for later phases. The [proposed safety policy](docs/response-ml/safety-policy.md) is for review.

```powershell
$env:MODULE4_RESPONSE_MODE = "SHADOW"
Push-Location backend
& $python -m uvicorn main:app --host 127.0.0.1 --port 8000
Pop-Location
```

For regression tests, use the project root and run `& $python -m pytest backend/tests -q`. Tests use disposable SQLite files.

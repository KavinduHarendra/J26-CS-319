# Phase 4 controlled backend integration

The backend can load the existing synthetic Random Forest prototype in research modes. The saved Joblib artifact is unchanged. All outputs remain recommendations for people. The model was trained against provisional draft-rubric labels and has no independently validated operational performance.

## Architecture

Both existing API inputs follow the same path.

1. Validate the request and pair Module 2 and Module 3 files where applicable.
2. Normalize the evidence and calculate correlation, deterministic risk, conflict and evidence confidence.
3. Calculate the contextual rule recommendation and the classification-only baseline.
4. If the server is in a research mode, extract the 15 approved ML features in training order and use the pinned pipeline. The saved preprocessing handles supported optional missing values in the same way as the Phase 3 experiment.
5. Use the configured selection mode and safety policy to choose the active recommendation. Build the existing response and save its complete JSON snapshot.

The model service verifies the two SHA-256 digests pinned in source before loading. It checks metadata, the feature definitions and order, all six class mappings, the exact package versions, and the Python major and minor version. It deserializes the verified in-memory bytes. An invalid or unavailable artifact produces a stable error code. The current model and any load failure are cached once per worker for the configured path. Restart the backend after repairing or replacing files. An intentionally different artifact needs a separately reviewed pin update.

## Mode behavior

- **RULE_BASED** is the default. It keeps the original API shape and uses the contextual selector without loading ML libraries or the model.
- **SHADOW** records both recommendations, disagreement, and any model error. The contextual recommendation remains active. The diagnostic ML screen does not override that recommendation.
- **MACHINE_LEARNING** is an explicit opt-in for controlled experiments. The proposed screening policy can adjust the raw model recommendation before it becomes active. Replay and corroborated security failure retain the hold recommendation. Suspect or expired evidence routes to operator review. Unsupported holds or backups and critical monitoring are rejected.
- If the model is unavailable, fails to predict, or falls below a configured threshold, the experimental branch screens the contextual fallback using the same proposed guard. If valid model features cannot be formed, it uses operator review, preserving a verified mandatory hold when the original security evidence supports it.
- Main input validation still handles missing or invalid source evidence before inference. Invalid JSON requests receive the existing validation response. The file route returns its existing structured integration failure.

`MODULE4_RESPONSE_MODE` is read from the backend process environment. It cannot be selected through an observation request. `MODULE4_MODEL_DIR` optionally points to the directory with the exact trusted artifact and metadata. The default is `.response-ml/prototype-v1/model` under the project root. `MODULE4_EXPERIMENTAL_MIN_CONFIDENCE` is optional and has no default threshold. If supplied, it must be a finite number from 0 to 1 and is only used in experimental ML mode. It is an experimental configuration value. Phase 3 held-out results did not choose it. The reported confidence and class probabilities remain uncalibrated.

## API and audit

`POST /api/evaluate` still accepts `rf_context`, `threat_intelligence` and `secure_communication`. `POST /api/evaluate-files` still accepts the two named multipart files. The top-level `recommended_response` is the active recommendation. The original `decision_confidence` is evidence confidence. `baseline_response` remains classification-only, and `baseline_vs_proposed` still compares it with the contextual rule.

The existing nested `response_selection` object is present in the two research modes. Its `configured_mode` is the response selection mode. It preserves `effective_mode`, `features`, and `feature_schema_version` and adds:

- `response_source` and `rule_based_response` identify the active source and the contextual baseline.
- `ml_status` is `SUCCEEDED` or `FAILED`. A failure includes `ml_error_code`. Examples include `MODEL_MISSING`, `METADATA_MISSING`, checksum or schema mismatch, and `PREDICTION_FAILED`.
- `ml_raw_response`, `ml_screened_response` and `ml_screening_reason` describe the candidate. They can be null when inference fails.
- `ml_prediction_confidence`, `ml_class_probabilities`, `ml_model_version` and `ml_inference_latency_ms` describe the raw prediction. `ml_confidence_calibrated` is false. `rule_based_disagreement` compares the raw ML output with the contextual rule.
- `safety_override` and `safety_override_reason` describe an intervention in the active recommendation. Shadow-only diagnostics appear as `ml_screening_reason`. `fallback_used` and `fallback_reason` identify an experimental fallback. `effective_mode` shows the ML acceptance or rule fallback branch. `response_source` identifies when proposed safety logic selected the final action within that branch.

SQLite still stores the active recommendation in its existing column and saves the extra fields in `full_response`. Existing rows, summary columns and read endpoints remain compatible. **No database migration is needed.**

## Manually try the three modes

Use the configured interpreter from the project root in PowerShell. For a fresh standard Python 3.13 environment, install `backend/requirements-inference.txt` for the research modes. With a standard environment that has no configured import path, run the Python server from `backend` and use an absolute path or `../.response-ml/phase4-manual.db` for its test database.

In the first terminal, paste this once. It starts a local-only test server on port 8001 with a separate audit database.

```powershell
$python = (Resolve-Path .\.venv\python.exe).Path
$servePhase4 = @'
from pathlib import Path
import uvicorn
from main import app
from services import audit_service
audit_service.DB_PATH = Path(".response-ml/phase4-manual.db").resolve()
uvicorn.run(app, host="127.0.0.1", port=8001)
'@
Remove-Item Env:MODULE4_MODEL_DIR -ErrorAction SilentlyContinue
Remove-Item Env:MODULE4_EXPERIMENTAL_MIN_CONFIDENCE -ErrorAction SilentlyContinue
$env:MODULE4_RESPONSE_MODE = "RULE_BASED"
$servePhase4 | & $python -B -
```

In a second terminal, try this deliberately conflicting synthetic observation. It reproduces the critical-risk monitoring issue with an evidence pattern absent from the v1.2 dataset.

```powershell
$case = @{
  rf_context = @{ observation_id = "PH4-MANUAL-GAP"; timestamp = "2026-01-01T00:00:00Z" }
  threat_intelligence = @{ classification = "Normal" }
  secure_communication = @{
    link_state = "SUSPICIOUS"
    freshness_state = "STALE"
    auth_state = "INVALID"
    integrity_state = "INVALID"
    replay_detected = $false
    comm_decision = $null
  }
}
$result = Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8001/api/evaluate" -ContentType "application/json" -Body ($case | ConvertTo-Json -Depth 6)
$result | ConvertTo-Json -Depth 16
```

Stop the first terminal's server with Ctrl+C before each mode change. Set `$env:MODULE4_RESPONSE_MODE = "SHADOW"` or `"MACHINE_LEARNING"`, run `$servePhase4 | & $python -B -` again, and repeat the request. The same request returns 85 points and CRITICAL in every mode. The rule-based response is `CONTINUE_MONITORING`. Shadow records the ML prediction and keeps `CONTINUE_MONITORING` active. The available model and proposed policy produced `OPERATOR_ESCALATION` in experimental ML mode during the completed checks.

A shortened experimental response from the checked evidence follows. Other existing fields and probability details are omitted here.

```json
{
  "risk_score": 85.0,
  "risk_level": "CRITICAL",
  "decision_confidence": "LOW",
  "recommended_response": "OPERATOR_ESCALATION",
  "response_selection": {
    "configured_mode": "MACHINE_LEARNING",
    "response_source": "MACHINE_LEARNING",
    "ml_status": "SUCCEEDED",
    "rule_based_response": "CONTINUE_MONITORING",
    "ml_raw_response": "OPERATOR_ESCALATION",
    "ml_screened_response": "OPERATOR_ESCALATION",
    "rule_based_disagreement": true,
    "fallback_used": false
  }
}
```

To exercise the fallback, stop the test server and set `$env:MODULE4_MODEL_DIR = (Join-Path (Get-Location).Path ".response-ml/phase4-missing-model")` to a path with no artifact. Start experimental ML mode and repeat the request. The contextual candidate is screened to `OPERATOR_ESCALATION`. A directory with both files missing returns `METADATA_MISSING`. To restore the usual prototype path, remove the environment override, then restart.

From the project root, the existing file route can be exercised with the paired synthetic fixtures:

```powershell
curl.exe -sS -X POST -F "module2_file=@integration_input/Module2/Module_2 Output_1.json" -F "module3_file=@integration_input/Module3/Module_3 Output_1.json" "http://127.0.0.1:8001/api/evaluate-files"
```

To see the audit record for a result, use `((Invoke-RestMethod "http://127.0.0.1:8001/api/evaluate/incidents/$($result.incident_id)").full_response | ConvertFrom-Json).response_selection`.

## Files

Created:

- `backend/services/ml_inference_service.py` and `backend/services/response_selection_service.py`
- `backend/requirements-inference.txt`
- `backend/tests/test_ml_inference.py`
- `docs/response-ml/backend-integration-phase4.md` and [validation results](../../.response-ml/phase4/validation-and-tests.md)

Modified:

- `backend/main.py` and `backend/services/pipeline.py`
- `backend/response_ml/modes.py` and `backend/response_ml/rubric.py`
- `backend/tests/test_ml_modes.py`

## Known limits

The model was trained on synthetic draft labels. Its probabilities lack calibration and the safety rules are proposed. The critical-gap probes demonstrate two new safety regression cases. They provide no claim about operational safety, independently validated accuracy, or coverage of all real conditions. Model replacement, any approved threshold, wider deployment, and frontend integration require separate review. Use loopback in the manual test to keep experimental behavior isolated.

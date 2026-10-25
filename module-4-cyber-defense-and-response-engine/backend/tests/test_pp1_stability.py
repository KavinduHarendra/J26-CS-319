"""Confirmed PP1 bug regressions; existing scores and response policies stay fixed."""
import asyncio
import json
from contextlib import closing
from io import BytesIO

import pytest
from pydantic import ValidationError
from starlette.datastructures import UploadFile

from data.evaluate_scenarios import EVALUATE_SCENARIOS
from main import app, evaluate_files
from models.defense import EvaluateRequest
from services import audit_service
from services.pipeline import run_pipeline


def normal_payload():
    return EvaluateRequest(**EVALUATE_SCENARIOS["s1_normal_operation"]["payload"]).model_dump()


def file_payloads():
    payload = normal_payload()
    module2 = {**payload["threat_intelligence"], "observation_id": "OBS-PP1",
               "timestamp": "2026-10-19T10:00:00Z"}
    module3 = {**payload["secure_communication"], "observation_id": "OBS-PP1",
               "timestamp": "2026-10-19T10:00:01Z"}
    return module2, module3


def upload_result(module2, module3):
    uploads = [UploadFile(filename=name, file=BytesIO(json.dumps(data).encode()))
               for name, data in (("module2.json", module2), ("module3.json", module3))]
    return asyncio.run(evaluate_files(*uploads))


@pytest.mark.parametrize("value", [False, "false", "False", 0])
def test_false_replay_is_not_truthy(value):
    module2, module3 = file_payloads()
    module3["replay_detected"] = value
    result = upload_result(module2, module3)
    assert result["integration_status"] == "SUCCESS"
    assert result["module3_context"]["replay_detected"] is False
    assert result["risk_score"] == 0
    assert result["recommended_response"] == "MONITOR"


@pytest.mark.parametrize("source,field", [(2, "classification"), (2, "severity"),
                                         (3, "link_state"), (3, "freshness_state"),
                                         (3, "auth_state"), (3, "integrity_state")])
@pytest.mark.parametrize("value", [[], {}, ["Normal"]])
def test_malformed_enum_types_return_structured_errors(source, field, value):
    module2, module3 = file_payloads()
    (module2 if source == 2 else module3)[field] = value
    result = upload_result(module2, module3)
    assert result["integration_status"] == "FAILED"
    assert result["field"] == field
    assert audit_service.get_all_incidents() == []


@pytest.mark.parametrize("field", ["link_state", "freshness_state", "auth_state", "integrity_state", "replay_detected"])
def test_missing_security_evidence_is_rejected_in_both_modes(field):
    module2, module3 = file_payloads()
    del module3[field]
    result = upload_result(module2, module3)
    assert result["error_code"] == "MISSING_REQUIRED_FIELD"
    assert result["field"] == field
    payload = normal_payload()
    del payload["secure_communication"][field]
    with pytest.raises(ValidationError, match="Missing required evidence"):
        EvaluateRequest(**payload)
    assert audit_service.get_all_incidents() == []


@pytest.mark.parametrize("payload", [{}, {"threat_intelligence": {}, "secure_communication": {}},
                                     {"threat_intelligence": {"classification": "Normal"}, "secure_communication": {}}])
def test_empty_or_missing_evidence_cannot_become_safe(payload):
    with pytest.raises(ValidationError):
        EvaluateRequest(**payload)
    assert audit_service.get_all_incidents() == []


@pytest.mark.parametrize("source", [2, 3])
def test_empty_json_file_returns_structured_error(source):
    module2, module3 = file_payloads()
    result = upload_result({} if source == 2 else module2, {} if source == 3 else module3)
    assert result["integration_status"] == "FAILED"
    assert result["error_code"] == "MISSING_REQUIRED_FIELD"


@pytest.mark.parametrize("time2,time3,success", [
    ("2026-10-19T10:00:00Z", "2026-10-19T10:00:01", False),
    ("2026-10-19T10:00:00", "2026-10-19T10:00:01Z", False),
    ("2026-10-19T10:00:00", "2026-10-19T10:00:01", True),
    ("2026-10-19T10:00:00Z", "2026-10-19T15:30:01+05:30", True),
])
def test_timestamp_fallback_handles_timezones_explicitly(time2, time3, success):
    module2, module3 = file_payloads()
    module2["timestamp"], module3["timestamp"] = time2, time3
    del module3["observation_id"]
    result = upload_result(module2, module3)
    assert result["integration_status"] == ("SUCCESS" if success else "FAILED")
    if success:
        assert result["match_method"] == "timestamp_fallback"
    else:
        assert result["error_code"] == "TIMESTAMP_TIMEZONE_MISMATCH"


@pytest.mark.parametrize("freshness,replay", [("FRESH", True), ("STALE", True), ("REPLAY", False)])
def test_contradictory_replay_evidence_is_rejected_in_both_modes(freshness, replay):
    module2, module3 = file_payloads()
    module3.update(freshness_state=freshness, replay_detected=replay)
    result = upload_result(module2, module3)
    assert result["integration_status"] == "FAILED"
    assert result["error_code"] == "INVALID_FIELD_VALUE"
    payload = normal_payload()
    payload["secure_communication"].update(freshness_state=freshness, replay_detected=replay)
    with pytest.raises(ValidationError, match="replay_detected must agree"):
        EvaluateRequest(**payload)


def test_trusted_link_with_invalid_security_cannot_claim_safety():
    payload = normal_payload()
    payload["secure_communication"].update(auth_state="INVALID", integrity_state="INVALID", freshness_state="STALE")
    result = run_pipeline(EvaluateRequest(**payload))
    assert result.risk_score == 60  # Existing 25 + 25 + 10 weights.
    assert result.risk_level == "HIGH"
    assert result.decision_confidence == "LOW"
    assert result.evidence_conflict
    assert "indicate safe conditions" not in result.correlation.correlation_note
    assert "agree system is safe" not in result.confidence_rationale
    assert result.recommended_response == "CONTINUE_MONITORING"  # No new policy.
    assert "Policy coverage review required" in result.response_rationale


def test_critical_monitoring_gap_is_reported_not_silently_replaced():
    payload = normal_payload()
    payload["secure_communication"].update(link_state="SUSPICIOUS", auth_state="INVALID",
                                          integrity_state="INVALID", freshness_state="STALE")
    result = run_pipeline(EvaluateRequest(**payload))
    assert result.risk_score == 85
    assert result.risk_level == "CRITICAL"
    assert result.recommended_response == "CONTINUE_MONITORING"
    assert "Policy coverage review required" in result.response_rationale
    assert any("Policy coverage review required" in reason for reason in result.reasons)


# Independent expected outcomes from the unchanged additive weights and rule table.
EXPECTED = {
    "s1_normal_operation": (0, "LOW", "MONITOR", "HIGH", "R10_NORMAL_SAFE"),
    "s2_low_jamming": (45, "MEDIUM", "CONTINUE_MONITORING", "MEDIUM", "R9_MEDIUM_RISK"),
    "s3_critical_jamming": (80, "CRITICAL", "PREPARE_BACKUP_CHANNEL", "HIGH", "R4_JAMMING_DEGRADED"),
    "s4_comm_compromise": (100, "CRITICAL", "SECURE_HOLD", "HIGH", "R3_JAMMING_UNTRUSTED"),
    "s5_unknown_anomaly_trusted": (40, "MEDIUM", "INCREASE_MONITORING", "MEDIUM", "R8_UNKNOWN_TRUSTED"),
    "s6_unknown_suspicious": (85, "CRITICAL", "OPERATOR_ESCALATION", "MEDIUM", "R5_UNKNOWN_SUSPICIOUS_LINK"),
    "s7_conflicting_evidence": (60, "HIGH", "OPERATOR_ESCALATION", "LOW", "R6_NORMAL_UNTRUSTED_CONFLICT"),
    "s8_replay_attempt": (50, "HIGH", "SECURE_HOLD", "LOW", "R1_REPLAY_SECURE_HOLD"),
    "s9_escalating_attack": (100, "CRITICAL", "PREPARE_BACKUP_CHANNEL", "HIGH", "R4_JAMMING_DEGRADED"),
    "s10_suspicious_command": (25, "MEDIUM", "CONTINUE_MONITORING", "LOW", "R9_MEDIUM_RISK"),
    "s11_integrity_failure": (60, "HIGH", "OPERATOR_ESCALATION", "LOW", "R6_NORMAL_UNTRUSTED_CONFLICT"),
}


@pytest.mark.parametrize("scenario_id", EXPECTED)
def test_every_preset_score_level_recommendation_and_explanation(scenario_id):
    scenario = EVALUATE_SCENARIOS[scenario_id]
    result = run_pipeline(EvaluateRequest(**scenario["payload"]))
    score, level, response, confidence, rule = EXPECTED[scenario_id]
    assert (result.risk_score, result.risk_level, result.recommended_response, result.decision_confidence) == (score, level, response, confidence)
    assert scenario["expected_risk_level"] == level
    assert scenario["expected_response"] == response
    assert rule in result.response_rationale
    assert any(f"Risk Level: {level}" in reason for reason in result.reasons)
    assert any(f"{float(score)}/100" in reason for reason in result.reasons)
    assert not any("correlation boost" in reason for reason in result.reasons)
    snapshot = json.loads(audit_service.get_incident_by_id(result.incident_id)["full_response"])
    assert snapshot == result.model_dump()


def test_history_keeps_latest_records_in_chronological_order_and_preserves_snapshots():
    request = EvaluateRequest(**normal_payload())
    for _ in range(105):
        run_pipeline(request)
    first = audit_service.get_incident_by_id("INC-0001")
    incidents = audit_service.get_all_incidents(100)
    history = audit_service.get_risk_history(50)
    assert incidents[0]["incident_id"] == "INC-0006"
    assert incidents[-1]["incident_id"] == history[-1]["incident_id"] == "INC-0105"
    assert history[0]["incident_id"] == "INC-0056"
    assert audit_service.get_incident_by_id("INC-0001") == first
    assert [row["timestamp"] for row in incidents] == sorted(row["timestamp"] for row in incidents)


def test_history_uses_timestamps_then_numeric_incident_ids():
    request = EvaluateRequest(**normal_payload())
    first, second = run_pipeline(request), run_pipeline(request)
    import sqlite3
    with closing(sqlite3.connect(audit_service.DB_PATH)) as conn:
        conn.execute("UPDATE incidents SET timestamp = ? WHERE incident_id = ?", ("2026-10-20T12:00:00", first.incident_id))
        conn.execute("UPDATE incidents SET timestamp = ? WHERE incident_id = ?", ("2026-10-19T12:00:00", second.incident_id))
        conn.commit()
    assert audit_service.get_all_incidents(1)[0]["incident_id"] == first.incident_id


def test_api_rejects_empty_request_with_structured_422():
    messages = []
    async def send(message):
        messages.append(message)
    async def receive():
        return {"type": "http.request", "body": b"{}", "more_body": False}
    scope = {"type": "http", "asgi": {"version": "3.0"}, "http_version": "1.1",
             "method": "POST", "scheme": "http", "path": "/api/evaluate", "raw_path": b"/api/evaluate",
             "query_string": b"", "root_path": "", "headers": [(b"content-type", b"application/json")],
             "server": ("test", 80), "client": ("test", 1)}
    asyncio.run(app(scope, receive, send))
    assert messages[0]["status"] == 422
    body = json.loads(b"".join(message.get("body", b"") for message in messages))
    assert isinstance(body["detail"], list)
    assert audit_service.get_all_incidents() == []

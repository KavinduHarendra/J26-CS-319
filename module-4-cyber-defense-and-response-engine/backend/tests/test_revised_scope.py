"""Regression checks for the four retained objectives and removed capabilities."""
import asyncio
import json
from io import BytesIO

import pytest
from starlette.datastructures import UploadFile

from data.evaluate_scenarios import EVALUATE_SCENARIOS
from main import app, evaluate, evaluate_files
from models.defense import EvaluateRequest
from services import audit_service
from services.file_integration_service import build_request
from services.pipeline import run_pipeline


def files(observation3="OBS-FILE-1"):
    module2 = {"schema_version": "1.0", "observation_id": "OBS-FILE-1",
               "timestamp": "2026-10-19T10:00:00Z", "classification": "Jamming",
               "severity": "High", "triggered_rule": "J01", "evidence": ["SNR drop"]}
    module3 = {"observation_id": observation3, "timestamp": "2026-10-19T10:00:02Z",
               "link_state": "DEGRADED", "freshness_state": "FRESH", "auth_state": "VALID",
               "integrity_state": "VALID", "replay_detected": False,
               "link_evidence": ["Packet delivery degraded"]}
    return tuple(UploadFile(filename=name, file=BytesIO(json.dumps(data).encode()))
                 for name, data in (("module2.json", module2), ("module3.json", module3)))


def test_file_matching_risk_recommendation_and_complete_audit():
    result = asyncio.run(evaluate_files(*files()))
    assert result["match_method"] == "observation_id"
    assert result["observation_id"] == "OBS-FILE-1"
    assert result["risk_score"] == 80
    assert result["risk_level"] == "CRITICAL"
    assert result["recommended_response"] == "PREPARE_BACKUP_CHANNEL"
    assert result["response_status"] == "RECOMMENDED"
    assert len(result["correlation"]["source_contributions"]) == 2
    assert result["reasons"] and result["response_rationale"]
    record = audit_service.get_incident_by_id(result["incident_id"])
    assert record["triggered_rule"] == "J01"
    assert record["observation_id"] == "OBS-FILE-1"
    assert record["timestamp"] == result["timestamp"]
    snapshot = json.loads(record["full_response"])
    assert snapshot == result
    assert snapshot["module2_context"]["evidence"] == ["SNR drop"]
    assert snapshot["module3_context"]["link_evidence"] == ["Packet delivery degraded"]
    assert not {"forecast", "trend", "trend_window", "effectiveness", "uav_status"} & result.keys()


def test_mismatched_observation_ids_are_rejected_without_audit():
    result = asyncio.run(evaluate_files(*files("DIFFERENT-OBS")))
    assert result["error_code"] == "OBSERVATION_ID_MISMATCH"
    assert audit_service.get_all_incidents() == []


def test_timestamp_fallback_is_preserved():
    request, metadata = asyncio.run(build_request(*files(None)))
    assert metadata["match_method"] == "timestamp_fallback"
    assert request.rf_context.observation_id == "OBS-FILE-1"


def test_invalid_json_does_not_run_pipeline():
    bad = UploadFile(filename="bad.json", file=BytesIO(b"not json"))
    result = asyncio.run(evaluate_files(bad, files()[1]))
    assert result["error_code"] == "INVALID_JSON"
    assert audit_service.get_all_incidents() == []


def test_recommendation_does_not_change_with_previous_evaluations():
    normal = EvaluateRequest(**EVALUATE_SCENARIOS["s1_normal_operation"]["payload"])
    first = run_pipeline(normal)
    for key in ("s3_critical_jamming", "s4_comm_compromise", "s8_replay_attempt"):
        run_pipeline(EvaluateRequest(**EVALUATE_SCENARIOS[key]["payload"]))
    last = run_pipeline(normal)
    assert (first.risk_score, first.recommended_response, first.decision_confidence) == (
        last.risk_score, last.recommended_response, last.decision_confidence)


def test_audit_survives_backend_reinitialization():
    request = EvaluateRequest(**EVALUATE_SCENARIOS["s1_normal_operation"]["payload"])
    first = run_pipeline(request)
    audit_service.reset_counter()
    audit_service.init_db()
    second = run_pipeline(request)
    assert first.incident_id != second.incident_id
    assert len(audit_service.get_all_incidents()) == 2


def test_removed_execution_routes_and_fields_are_absent():
    paths = {route.path for route in app.routes}
    assert not {"/api/simulate-response", "/api/uav-status", "/api/reset"} & paths
    assert {"/api/evaluate", "/api/evaluate-files", "/api/evaluate/incidents"} <= paths
    assert not {"/api/analyze", "/api/scenarios", "/api/scenarios/{scenario_id}", "/api/prioritize-threats"} & paths


@pytest.mark.parametrize("scenario", EVALUATE_SCENARIOS.values())
def test_all_scenario_response_metadata_matches_current_evidence(scenario):
    result = run_pipeline(EvaluateRequest(**scenario["payload"]))
    assert result.recommended_response == scenario["expected_response"]


@pytest.mark.parametrize("scenario", EVALUATE_SCENARIOS.values())
def test_manual_and_file_evaluation_share_identical_decisions_and_evidence(scenario):
    """Both user interfaces must reach the same normalization, scoring and audit path."""
    payload = scenario["payload"]
    rf = payload["rf_context"]
    module2 = {**payload["threat_intelligence"], "observation_id": rf["observation_id"],
               "timestamp": rf["timestamp"], "rf_context": rf}
    module3 = {**payload["secure_communication"], "observation_id": rf["observation_id"]}
    uploads = tuple(UploadFile(filename=name, file=BytesIO(json.dumps(data).encode()))
                    for name, data in (("module2.json", module2), ("module3.json", module3)))
    manual_result = evaluate(EvaluateRequest(**payload))
    file_result = asyncio.run(evaluate_files(*uploads))
    for key in ("risk_score", "risk_level", "risk_breakdown", "recommended_response",
                "response_rationale", "response_status", "reasons", "correlation",
                "evidence_conflict", "decision_confidence", "confidence_rationale",
                "module1_context", "module2_context", "module3_context"):
        assert manual_result[key] == file_result[key], key
    assert len(audit_service.get_all_incidents()) == 2


def test_additional_evidence_is_audited_without_new_scoring_weights():
    plain = EvaluateRequest(**EVALUATE_SCENARIOS["s3_critical_jamming"]["payload"])
    enriched = plain.model_copy(deep=True)
    enriched.rf_context.bandwidth_mhz = 20
    enriched.rf_context.packet_loss_pct = 12
    enriched.rf_context.latency_ms = 95
    enriched.threat_intelligence.threat_confidence = 0.82
    original, result = run_pipeline(plain), run_pipeline(enriched)
    assert original.risk_score == result.risk_score
    assert original.risk_breakdown == result.risk_breakdown
    assert original.recommended_response == result.recommended_response
    assert original.decision_confidence == result.decision_confidence
    snapshot = json.loads(audit_service.get_incident_by_id(result.incident_id)["full_response"])
    assert snapshot["module1_context"]["bandwidth_mhz"] == 20
    assert snapshot["module1_context"]["packet_loss_pct"] == 12
    assert snapshot["module1_context"]["latency_ms"] == 95
    assert snapshot["module2_context"]["threat_confidence"] == 0.82


@pytest.mark.parametrize("field,value", [("threat_confidence", -0.1), ("threat_confidence", 1.1)])
def test_file_confidence_validation_returns_structured_error_without_audit(field, value):
    module2, module3 = files()
    payload = json.loads(module2.file.read())
    payload[field] = value
    invalid = UploadFile(filename="module2.json", file=BytesIO(json.dumps(payload).encode()))
    result = asyncio.run(evaluate_files(invalid, module3))
    assert result["integration_status"] == "FAILED"
    assert result["error_code"] == "INVALID_FIELD_VALUE"
    assert audit_service.get_all_incidents() == []


@pytest.mark.parametrize("field,value", [("bandwidth_mhz", -1), ("frequency_mhz", 0),
                                         ("packet_loss_pct", 101), ("latency_ms", -1),
                                         ("rssi", float("inf"))])
def test_manual_rf_validation_rejects_invalid_evidence(field, value):
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        EvaluateRequest(rf_context={field: value})


def test_statistical_deviations_remain_evidence_not_physical_measurements():
    module2, module3 = files()
    payload = json.loads(module2.file.read())
    payload["statistical_deviation"] = {"packet_rate": -0.6, "snr": -8.5}
    upload = UploadFile(filename="module2.json", file=BytesIO(json.dumps(payload).encode()))
    result = asyncio.run(evaluate_files(upload, module3))
    assert result["integration_status"] == "SUCCESS"
    assert result["module1_context"]["packet_rate"] is None
    assert result["module1_context"]["snr"] is None
    assert result["module2_context"]["statistical_deviation"]["packet_rate"] == -0.6
    assert result["risk_score"] == 80

import json
from copy import deepcopy

import pytest
from fastapi.testclient import TestClient

from data.evaluate_scenarios import EVALUATE_SCENARIOS
from main import app
from response_ml.features import extract_features
from response_ml.modes import MODE_VARIABLE, THRESHOLD_VARIABLE, read_experimental_minimum_confidence, read_response_mode
from services import audit_service, ml_inference_service as inference
from services import response_selection_service


def test_default_keeps_existing_response_shape(monkeypatch):
    monkeypatch.delenv(MODE_VARIABLE, raising=False)
    monkeypatch.setattr(inference, "get_model", lambda: pytest.fail("Default rule mode loaded ML"))
    payload = EVALUATE_SCENARIOS["s1_normal_operation"]["payload"]
    with TestClient(app) as client:
        result = client.post("/api/evaluate", json=payload).json()
    assert "response_selection" not in result
    assert (result["risk_score"], result["recommended_response"], result["baseline_response"]) == (0, "MONITOR", "MONITOR")
    assert json.loads(audit_service.get_incident_by_id(result["incident_id"])["full_response"]) == result


def prediction(action, confidence=0.7):
    probabilities = dict.fromkeys(inference.CLASS_ORDER, (1 - confidence) / (len(inference.CLASS_ORDER) - 1))
    probabilities[action] = confidence
    return inference.Prediction(action, confidence, probabilities, inference.MODEL_VERSION, 1.25)


def setup_mode(monkeypatch, mode, predictor):
    monkeypatch.setenv(MODE_VARIABLE, mode)
    monkeypatch.delenv(THRESHOLD_VARIABLE, raising=False)
    monkeypatch.setattr(inference, "get_model", lambda: inference.ModelState())
    monkeypatch.setattr(inference, "predict", predictor)


@pytest.mark.parametrize("mode, active, source", [
    ("SHADOW", "PREPARE_BACKUP_CHANNEL", "RULE_BASED"),
    ("MACHINE_LEARNING", "OPERATOR_ESCALATION", "MACHINE_LEARNING"),
])
def test_research_modes_use_identical_features_for_manual_and_files(monkeypatch, mode, active, source):
    setup_mode(monkeypatch, mode, lambda _: prediction("OPERATOR_ESCALATION"))
    payload = EVALUATE_SCENARIOS["s3_critical_jamming"]["payload"]
    rf = payload["rf_context"]
    module2 = {**payload["threat_intelligence"], "observation_id": rf["observation_id"],
               "timestamp": rf["timestamp"], "rf_context": rf}
    module3 = {**payload["secure_communication"], "observation_id": rf["observation_id"]}
    files = {
        "module2_file": ("module 2.json", json.dumps(module2), "application/json"),
        "module3_file": ("module 3.json", json.dumps(module3), "application/json"),
    }
    with TestClient(app) as client:
        manual = client.post("/api/evaluate", json=payload)
        paired = client.post("/api/evaluate-files", files=files)

    assert manual.status_code == paired.status_code == 200
    manual_result, paired_result = manual.json(), paired.json()
    metadata = manual_result["response_selection"]
    assert paired_result["response_selection"] == metadata
    assert metadata["configured_mode"] == mode
    assert metadata["effective_mode"] == source
    assert metadata["response_source"] == source
    assert metadata["ml_status"] == "SUCCEEDED"
    assert metadata["features"]["risk_score"] == 80
    assert metadata["rule_based_response"] == "PREPARE_BACKUP_CHANNEL"
    assert metadata["ml_raw_response"] == metadata["ml_screened_response"] == "OPERATOR_ESCALATION"
    assert metadata["rule_based_disagreement"] and not metadata["fallback_used"]
    assert metadata["ml_prediction_confidence"] == 0.7 and not metadata["ml_confidence_calibrated"]
    assert manual_result["decision_confidence"] == metadata["features"]["decision_confidence"]
    assert manual_result["recommended_response"] == paired_result["recommended_response"] == active
    saved = audit_service.get_incident_by_id(paired_result["incident_id"])
    assert saved["recommended_response"] == active
    assert json.loads(saved["full_response"]) == paired_result


def new_gap_payload(freshness):
    """New gap probes with no Module 3 recommendation, unlike the trained gap family."""
    payload = deepcopy(EVALUATE_SCENARIOS["s1_normal_operation"]["payload"])
    payload["rf_context"]["observation_id"] = "PH4-GAP-NEW-" + freshness
    payload["secure_communication"].update(
        link_state="SUSPICIOUS", freshness_state=freshness, auth_state="INVALID",
        integrity_state="INVALID", replay_detected=False, comm_decision=None,
    )
    return payload


@pytest.mark.parametrize("freshness, score", [("FRESH", 75), ("STALE", 85)])
@pytest.mark.parametrize("problem", [None, "MODEL_MISSING", "MODEL_CHECKSUM_MISMATCH", "PREDICTION_FAILED", "UNSUPPORTED_CLASS"])
def test_experimental_guard_screens_predictions_and_rule_fallbacks_on_new_gaps(monkeypatch, freshness, score, problem):
    def predict(_):
        if problem:
            raise inference.InferenceError(problem)
        return prediction("CONTINUE_MONITORING")

    setup_mode(monkeypatch, "MACHINE_LEARNING", predict)
    with TestClient(app) as client:
        result = client.post("/api/evaluate", json=new_gap_payload(freshness)).json()
    info = result["response_selection"]
    assert result["risk_level"] == "CRITICAL" and result["risk_score"] == score
    assert info["rule_based_response"] == "CONTINUE_MONITORING"
    assert result["recommended_response"] == "OPERATOR_ESCALATION"
    assert info["safety_override"] and info["safety_override_reason"] == "SECURITY_OR_EVIDENCE_REVIEW"
    assert info["fallback_used"] == bool(problem)
    assert info["fallback_reason"] == info["ml_error_code"] == problem
    assert info["ml_raw_response"] == (None if problem else "CONTINUE_MONITORING")
    assert info["ml_screened_response"] == (None if problem else "OPERATOR_ESCALATION")


def test_shadow_records_failure_and_keeps_the_contextual_recommendation(monkeypatch):
    def fail(_):
        raise inference.InferenceError("MODEL_MISSING")

    setup_mode(monkeypatch, "SHADOW", fail)
    with TestClient(app) as client:
        result = client.post("/api/evaluate", json=new_gap_payload("STALE")).json()
    assert result["recommended_response"] == "CONTINUE_MONITORING"
    info = result["response_selection"]
    assert info["ml_status"] == "FAILED" and info["ml_error_code"] == "MODEL_MISSING"
    assert info["response_source"] == "RULE_BASED" and not info["fallback_used"]


def test_explicit_threshold_preserves_raw_output_and_still_screens_fallback(monkeypatch):
    setup_mode(monkeypatch, "MACHINE_LEARNING", lambda _: prediction("CONTINUE_MONITORING"))
    monkeypatch.setenv(THRESHOLD_VARIABLE, "0.9")
    with TestClient(app) as client:
        result = client.post("/api/evaluate", json=new_gap_payload("STALE")).json()
    info = result["response_selection"]
    assert info["fallback_reason"] == "BELOW_EXPERIMENTAL_THRESHOLD"
    assert info["ml_status"] == "SUCCEEDED"
    assert info["ml_raw_response"] == "CONTINUE_MONITORING"
    assert info["ml_screened_response"] == result["recommended_response"] == "OPERATOR_ESCALATION"


@pytest.mark.parametrize("scenario, reason", [
    ("s8_replay_attempt", "CONFIRMED_REPLAY"),
    ("s4_comm_compromise", "CORROBORATED_SECURITY_FAILURE"),
])
def test_experimental_guard_preserves_holds(monkeypatch, scenario, reason):
    setup_mode(monkeypatch, "MACHINE_LEARNING", lambda _: prediction("MONITOR"))
    payload = deepcopy(EVALUATE_SCENARIOS[scenario]["payload"])
    if scenario == "s4_comm_compromise":
        payload["secure_communication"].update(
            link_state="UNTRUSTED", auth_state="INVALID", integrity_state="INVALID", comm_decision="SECURE_HOLD",
        )
    with TestClient(app) as client:
        result = client.post("/api/evaluate", json=payload).json()
    assert result["recommended_response"] == "SECURE_HOLD"
    assert result["response_selection"]["safety_override_reason"] == reason


@pytest.mark.parametrize("action", ["SECURE_HOLD", "PREPARE_BACKUP_CHANNEL"])
def test_unsupported_hold_and_backup_are_screened_in_experimental_mode(monkeypatch, action):
    setup_mode(monkeypatch, "MACHINE_LEARNING", lambda _: prediction(action))
    payload = EVALUATE_SCENARIOS["s1_normal_operation"]["payload"]
    with TestClient(app) as client:
        result = client.post("/api/evaluate", json=payload).json()
    assert result["recommended_response"] == "OPERATOR_ESCALATION"
    assert result["response_selection"]["safety_override_reason"] == "UNSUPPORTED_HOLD_OR_BACKUP"


def test_critical_monitoring_is_blocked_even_with_valid_security_checks(monkeypatch):
    setup_mode(monkeypatch, "MACHINE_LEARNING", lambda _: prediction("INCREASE_MONITORING"))
    payload = EVALUATE_SCENARIOS["s3_critical_jamming"]["payload"]
    with TestClient(app) as client:
        result = client.post("/api/evaluate", json=payload).json()
    assert result["recommended_response"] == "OPERATOR_ESCALATION"
    assert result["response_selection"]["safety_override_reason"] == "CRITICAL_MONITORING"


def test_missing_or_invalid_input_never_runs_inference(monkeypatch):
    setup_mode(monkeypatch, "MACHINE_LEARNING", lambda _: pytest.fail("Unvalidated evidence reached prediction"))
    missing, invalid = new_gap_payload("STALE"), new_gap_payload("STALE")
    missing["secure_communication"].pop("auth_state")
    invalid["secure_communication"]["replay_detected"] = True
    with TestClient(app) as client:
        assert client.post("/api/evaluate", json=missing).status_code == 422
        assert client.post("/api/evaluate", json=invalid).status_code == 422
        files = {
            "module2_file": ("m2.json", json.dumps({
                **missing["threat_intelligence"], "observation_id": missing["rf_context"]["observation_id"],
                "timestamp": missing["rf_context"]["timestamp"],
            }), "application/json"),
            "module3_file": ("m3.json", json.dumps(missing["secure_communication"]), "application/json"),
        }
        failed = client.post("/api/evaluate-files", files=files).json()
    assert failed["integration_status"] == "FAILED"
    assert audit_service.get_all_incidents() == []


@pytest.mark.parametrize("scenario, active", [
    ("s1_normal_operation", "OPERATOR_ESCALATION"),
    ("s8_replay_attempt", "SECURE_HOLD"),
])
def test_incompatible_model_features_fail_closed_using_validated_security(monkeypatch, scenario, active):
    setup_mode(monkeypatch, "MACHINE_LEARNING", inference.predict)
    monkeypatch.setattr(
        response_selection_service, "extract_features",
        lambda evidence: extract_features(evidence).model_copy(update={"risk_score": 101}),
    )
    payload = EVALUATE_SCENARIOS[scenario]["payload"]
    with TestClient(app) as client:
        result = client.post("/api/evaluate", json=payload).json()
    info = result["response_selection"]
    assert info["fallback_reason"] == "INVALID_MODEL_FEATURES"
    assert not info["features"]
    assert info["response_source"] == "EVIDENCE_FALLBACK"
    assert result["recommended_response"] == active


def test_unknown_mode_fails_with_configuration_guidance(monkeypatch):
    monkeypatch.setenv(MODE_VARIABLE, "TYPO")
    with pytest.raises(ValueError, match=MODE_VARIABLE):
        read_response_mode()


@pytest.mark.parametrize("value", ["nan", "inf", "-0.1", "1.01", "bad"])
def test_invalid_experimental_threshold_is_rejected(monkeypatch, value):
    monkeypatch.setenv(THRESHOLD_VARIABLE, value)
    with pytest.raises(ValueError, match=THRESHOLD_VARIABLE):
        read_experimental_minimum_confidence()

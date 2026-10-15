"""Integration tests — full pipeline execution for all 9 PP1 scenarios.

Runs each scenario through the complete Module 4 pipeline and
verifies the expected risk level and response match the specification.

These tests serve as regression tests for the PP1 demonstration.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.defense import EvaluateRequest
from services.pipeline import run_pipeline
from services import trend_service, audit_service
from data.evaluate_scenarios import EVALUATE_SCENARIOS


def setup():
    """Reset state before integration tests."""
    audit_service.init_db()  # Ensure SQLite table exists
    trend_service.reset_history()
    audit_service.clear_all()


# pytest autouse fixture — runs setup before every test in this module
try:
    import pytest

    @pytest.fixture(autouse=True)
    def _reset():
        setup()
except ImportError:
    pass


def _run(scenario_id: str):
    """Run a single scenario and return the EvaluateResponse."""
    scenario = EVALUATE_SCENARIOS[scenario_id]
    request = EvaluateRequest(**scenario["payload"])
    return run_pipeline(request), scenario


def test_s1_normal_operation():
    """Scenario 1: Normal → LOW, MONITOR."""
    response, scenario = _run("s1_normal_operation")
    assert response.risk_level == "LOW", f"Expected LOW, got {response.risk_level}"
    assert response.recommended_response == "MONITOR", f"Expected MONITOR, got {response.recommended_response}"
    assert response.evidence_conflict is False


def test_s2_low_jamming():
    """Scenario 2: Low Jamming → MEDIUM."""
    response, _ = _run("s2_low_jamming")
    assert response.risk_level == "MEDIUM", f"Expected MEDIUM, got {response.risk_level}"


def test_s3_critical_jamming():
    """Scenario 3: Critical Jamming + DEGRADED → CRITICAL, PREPARE_BACKUP_CHANNEL."""
    response, _ = _run("s3_critical_jamming")
    assert response.risk_level == "CRITICAL", f"Expected CRITICAL, got {response.risk_level}"
    assert response.recommended_response == "PREPARE_BACKUP_CHANNEL", (
        f"Expected PREPARE_BACKUP_CHANNEL, got {response.recommended_response}"
    )


def test_s4_comm_compromise():
    """Scenario 4: Jamming + UNTRUSTED → CRITICAL, SECURE_HOLD."""
    response, _ = _run("s4_comm_compromise")
    assert response.risk_level == "CRITICAL", f"Expected CRITICAL, got {response.risk_level}"
    assert response.recommended_response == "SECURE_HOLD", (
        f"Expected SECURE_HOLD, got {response.recommended_response}"
    )


def test_s5_unknown_trusted():
    """Scenario 5: Unknown Anomaly + TRUSTED → INCREASE_MONITORING."""
    response, _ = _run("s5_unknown_anomaly_trusted")
    assert response.recommended_response == "INCREASE_MONITORING", (
        f"Expected INCREASE_MONITORING, got {response.recommended_response}"
    )


def test_s6_unknown_suspicious():
    """Scenario 6: Unknown Anomaly + SUSPICIOUS → OPERATOR_ESCALATION."""
    response, _ = _run("s6_unknown_suspicious")
    assert response.recommended_response == "OPERATOR_ESCALATION", (
        f"Expected OPERATOR_ESCALATION, got {response.recommended_response}"
    )


def test_s7_conflicting_evidence():
    """Scenario 7: Normal RF + UNTRUSTED → conflict flagged, LOW confidence."""
    response, _ = _run("s7_conflicting_evidence")
    assert response.evidence_conflict is True, "Expected evidence_conflict = True"
    assert response.decision_confidence == "LOW", (
        f"Expected LOW confidence with conflict, got {response.decision_confidence}"
    )
    assert response.recommended_response == "OPERATOR_ESCALATION", (
        f"Expected OPERATOR_ESCALATION for conflict, got {response.recommended_response}"
    )


def test_s8_replay():
    """Scenario 8: Replay detected → SECURE_HOLD regardless of RF."""
    response, _ = _run("s8_replay_attempt")
    assert response.recommended_response == "SECURE_HOLD", (
        f"Expected SECURE_HOLD for replay, got {response.recommended_response}"
    )


def test_s9_escalating():
    """Scenario 9: Escalating attack final stage → CRITICAL."""
    response, _ = _run("s9_escalating_attack")
    assert response.risk_level == "CRITICAL", f"Expected CRITICAL, got {response.risk_level}"


def test_response_always_simulated():
    """All responses must carry SIMULATED status."""
    for sid in EVALUATE_SCENARIOS:
        response, _ = _run(sid)
        assert response.response_status == "SIMULATED", (
            f"Scenario {sid}: expected SIMULATED, got {response.response_status}"
        )


def test_reasons_list_populated():
    """Every response should have a non-empty reasons list."""
    for sid in EVALUATE_SCENARIOS:
        response, _ = _run(sid)
        assert len(response.reasons) > 0, f"Scenario {sid}: empty reasons list"


def test_baseline_differs_from_proposed_on_conflict_scenarios():
    """Proposed engine should differ from baseline on scenarios 4, 7, 8."""
    for sid in ("s4_comm_compromise", "s7_conflicting_evidence", "s8_replay_attempt"):
        response, _ = _run(sid)
        assert response.baseline_vs_proposed != "SAME", (
            f"Scenario {sid}: proposed should differ from baseline, got SAME"
        )


if __name__ == "__main__":
    setup()
    tests = [
        test_s1_normal_operation,
        test_s2_low_jamming,
        test_s3_critical_jamming,
        test_s4_comm_compromise,
        test_s5_unknown_trusted,
        test_s6_unknown_suspicious,
        test_s7_conflicting_evidence,
        test_s8_replay,
        test_s9_escalating,
        test_response_always_simulated,
        test_reasons_list_populated,
        test_baseline_differs_from_proposed_on_conflict_scenarios,
    ]
    passed = 0
    failed = 0
    for t in tests:
        try:
            t()
            print(f"  ✓ {t.__name__}")
            passed += 1
        except AssertionError as e:
            print(f"  ✗ {t.__name__}: {e}")
            failed += 1
    print(f"\n{passed}/{passed+failed} tests passed")

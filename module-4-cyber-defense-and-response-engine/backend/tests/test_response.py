"""Unit tests for response selection service.

Tests that the response engine:
  - Selects SECURE_HOLD for any replay (highest priority rule)
  - Selects SECURE_HOLD for Jamming + UNTRUSTED
  - Selects PREPARE_BACKUP_CHANNEL for Jamming + DEGRADED
  - Selects OPERATOR_ESCALATION for Unknown + SUSPICIOUS
  - Selects OPERATOR_ESCALATION for Normal + UNTRUSTED (conflict)
  - Baseline ignores communication state
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.module2 import ThreatIntelligence
from models.module3 import SecureCommunication
from models.defense import ConflictResult
from services.response_service import select_response, compare_baseline


def _make_ti(classification="Normal", severity=None) -> ThreatIntelligence:
    return ThreatIntelligence(classification=classification, severity=severity)


def _make_sc(link="TRUSTED", fresh="FRESH", replay=False) -> SecureCommunication:
    return SecureCommunication(link_state=link, freshness_state=fresh, replay_detected=replay)


def _no_conflict() -> ConflictResult:
    return ConflictResult(evidence_conflict=False)


def test_replay_always_secure_hold():
    """Any replay → SECURE_HOLD regardless of classification."""
    for cls in ("Normal", "Jamming", "Unknown Anomaly"):
        sc = _make_sc("TRUSTED", "REPLAY", replay=True)
        response, _, _ = select_response(_make_ti(cls), sc, 0.0, _no_conflict())
        assert response == "SECURE_HOLD", f"Expected SECURE_HOLD for replay ({cls}), got {response}"


def test_jamming_untrusted_secure_hold():
    """Jamming + UNTRUSTED → SECURE_HOLD."""
    response, _, _ = select_response(
        _make_ti("Jamming", "High"), _make_sc("UNTRUSTED"), 80.0, _no_conflict()
    )
    assert response == "SECURE_HOLD", f"Expected SECURE_HOLD, got {response}"


def test_jamming_degraded_prepare_backup():
    """Jamming + DEGRADED → PREPARE_BACKUP_CHANNEL."""
    response, _, _ = select_response(
        _make_ti("Jamming", "High"), _make_sc("DEGRADED"), 80.0, _no_conflict()
    )
    assert response == "PREPARE_BACKUP_CHANNEL", f"Expected PREPARE_BACKUP_CHANNEL, got {response}"


def test_unknown_suspicious_operator_escalation():
    """Unknown Anomaly + SUSPICIOUS → OPERATOR_ESCALATION."""
    response, _, _ = select_response(
        _make_ti("Unknown Anomaly"), _make_sc("SUSPICIOUS"), 45.0, _no_conflict()
    )
    assert response == "OPERATOR_ESCALATION", f"Expected OPERATOR_ESCALATION, got {response}"


def test_normal_untrusted_operator_escalation():
    """Normal RF + UNTRUSTED link → OPERATOR_ESCALATION (conflict case)."""
    response, _, _ = select_response(
        _make_ti("Normal"), _make_sc("UNTRUSTED"), 35.0, _no_conflict()
    )
    assert response == "OPERATOR_ESCALATION", f"Expected OPERATOR_ESCALATION, got {response}"


def test_normal_trusted_monitor():
    """Normal + TRUSTED → MONITOR."""
    response, _, _ = select_response(
        _make_ti("Normal"), _make_sc("TRUSTED"), 0.0, _no_conflict()
    )
    assert response == "MONITOR", f"Expected MONITOR, got {response}"


def test_unknown_trusted_increase_monitoring():
    """Unknown Anomaly + TRUSTED → INCREASE_MONITORING."""
    response, _, _ = select_response(
        _make_ti("Unknown Anomaly"), _make_sc("TRUSTED"), 20.0, _no_conflict()
    )
    assert response == "INCREASE_MONITORING", f"Expected INCREASE_MONITORING, got {response}"


def test_baseline_ignores_link_state():
    """Baseline should give same response regardless of link state."""
    _, _, baseline_trusted = select_response(
        _make_ti("Jamming"), _make_sc("TRUSTED"), 35.0, _no_conflict()
    )
    _, _, baseline_untrusted = select_response(
        _make_ti("Jamming"), _make_sc("UNTRUSTED"), 70.0, _no_conflict()
    )
    assert baseline_trusted == baseline_untrusted == "PREPARE_BACKUP_CHANNEL", (
        f"Baseline should be same regardless of link state: {baseline_trusted} vs {baseline_untrusted}"
    )


def test_compare_baseline_proposed_more_cautious():
    """Proposed SECURE_HOLD vs baseline PREPARE_BACKUP_CHANNEL → MORE_CAUTIOUS."""
    result = compare_baseline("SECURE_HOLD", "PREPARE_BACKUP_CHANNEL")
    assert result == "PROPOSED_MORE_CAUTIOUS", f"Got {result}"


def test_compare_baseline_same():
    """Same response → SAME."""
    result = compare_baseline("MONITOR", "MONITOR")
    assert result == "SAME", f"Got {result}"


if __name__ == "__main__":
    tests = [
        test_replay_always_secure_hold,
        test_jamming_untrusted_secure_hold,
        test_jamming_degraded_prepare_backup,
        test_unknown_suspicious_operator_escalation,
        test_normal_untrusted_operator_escalation,
        test_normal_trusted_monitor,
        test_unknown_trusted_increase_monitoring,
        test_baseline_ignores_link_state,
        test_compare_baseline_proposed_more_cautious,
        test_compare_baseline_same,
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

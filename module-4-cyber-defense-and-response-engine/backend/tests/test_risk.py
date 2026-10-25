"""Unit tests for risk scoring service.

Tests that the dynamic risk scorer:
  - Produces correct points per component
  - Caps score at 100
  - Maps scores to correct risk levels
  - Handles Unknown Anomaly conservatively vs Jamming
"""

import sys
from pathlib import Path

# Allow imports from backend root
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.module2 import ThreatIntelligence
from models.module3 import SecureCommunication
from services.risk_service import compute_risk


def _make_ti(classification="Normal", severity=None, rule=None) -> ThreatIntelligence:
    return ThreatIntelligence(classification=classification, severity=severity, triggered_rule=rule)


def _make_sc(link="TRUSTED", fresh="FRESH", auth="VALID", integrity="VALID", replay=False) -> SecureCommunication:
    return SecureCommunication(
        link_state=link, freshness_state=fresh,
        auth_state=auth, integrity_state=integrity, replay_detected=replay or fresh == "REPLAY"
    )


def test_normal_trusted_is_zero():
    """Normal + Trusted should produce 0 risk."""
    score, level, breakdown = compute_risk(_make_ti("Normal"), _make_sc("TRUSTED"))
    assert score == 0.0, f"Expected 0 got {score}"
    assert level == "LOW"
    assert breakdown.capped_score == 0.0


def test_jamming_high_degraded():
    """Jamming + High severity + Degraded should produce CRITICAL (>=75)."""
    score, level, _ = compute_risk(
        _make_ti("Jamming", "High"),
        _make_sc("DEGRADED")
    )
    # 35 (Jamming) + 30 (High) + 15 (Degraded) = 80
    assert score == 80.0, f"Expected 80.0 got {score}"
    assert level == "CRITICAL"


def test_jamming_high_untrusted():
    """Jamming + High + UNTRUSTED should produce maximum CRITICAL."""
    score, level, _ = compute_risk(
        _make_ti("Jamming", "High"),
        _make_sc("UNTRUSTED")
    )
    # 35 + 30 + 35 = 100
    assert score == 100.0, f"Expected 100.0 got {score}"
    assert level == "CRITICAL"


def test_unknown_anomaly_lower_than_jamming():
    """Unknown Anomaly should score lower than equivalent Jamming."""
    ua_score, _, _ = compute_risk(_make_ti("Unknown Anomaly", "Medium"), _make_sc("TRUSTED"))
    jm_score, _, _ = compute_risk(_make_ti("Jamming", "Medium"), _make_sc("TRUSTED"))
    assert ua_score < jm_score, (
        f"Unknown Anomaly ({ua_score}) should be lower than Jamming ({jm_score})"
    )


def test_replay_adds_25_points():
    """Replay detected should add REPLAY = 25 points to freshness."""
    score_fresh, _, _ = compute_risk(_make_ti("Normal"), _make_sc("TRUSTED", "FRESH"))
    score_replay, _, _ = compute_risk(_make_ti("Normal"), _make_sc("TRUSTED", "REPLAY"))
    assert score_replay - score_fresh == 25.0, (
        f"Expected +25 for replay, got {score_replay - score_fresh}"
    )


def test_score_cap_at_100():
    """Score should never exceed 100."""
    score, _, _ = compute_risk(
        _make_ti("Jamming", "High"),
        _make_sc("UNTRUSTED", "REPLAY", "INVALID", "INVALID", True)
    )
    assert score <= 100.0, f"Score exceeded cap: {score}"


def test_risk_level_boundaries():
    """Test all four risk level boundaries."""
    # LOW: 0–24
    score, level, _ = compute_risk(_make_ti("Normal"), _make_sc("TRUSTED"))
    assert level == "LOW"

    # MEDIUM: 25–49
    score, level, _ = compute_risk(_make_ti("Unknown Anomaly", "Low"), _make_sc("TRUSTED"))
    # 20 + 10 = 30 → MEDIUM
    assert level == "MEDIUM", f"Expected MEDIUM got {level} (score={score})"

    # HIGH: 50–74
    score, level, _ = compute_risk(_make_ti("Jamming", "Low"), _make_sc("DEGRADED"))
    # 35 + 10 + 15 = 60 → HIGH
    assert level == "HIGH", f"Expected HIGH got {level} (score={score})"

    # CRITICAL: 75–100
    score, level, _ = compute_risk(_make_ti("Jamming", "High"), _make_sc("DEGRADED"))
    # 35 + 30 + 15 = 80 → CRITICAL
    assert level == "CRITICAL", f"Expected CRITICAL got {level} (score={score})"


def test_breakdown_has_all_components():
    """Risk breakdown should list all non-zero components."""
    _, _, breakdown = compute_risk(
        _make_ti("Jamming", "High"),
        _make_sc("DEGRADED", "STALE", "SUSPICIOUS", "INVALID")
    )
    sources = {c.source for c in breakdown.components}
    assert "MODULE_2_CLASSIFICATION" in sources
    assert "MODULE_2_SEVERITY" in sources
    assert "MODULE_3_LINK_STATE" in sources
    assert "MODULE_3_FRESHNESS" in sources
    assert "MODULE_3_AUTH" in sources
    assert "MODULE_3_INTEGRITY" in sources


if __name__ == "__main__":
    tests = [
        test_normal_trusted_is_zero,
        test_jamming_high_degraded,
        test_jamming_high_untrusted,
        test_unknown_anomaly_lower_than_jamming,
        test_replay_adds_25_points,
        test_score_cap_at_100,
        test_risk_level_boundaries,
        test_breakdown_has_all_components,
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

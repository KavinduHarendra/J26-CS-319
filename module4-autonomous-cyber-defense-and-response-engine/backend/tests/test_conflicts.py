"""Unit tests for conflict detection and confidence services.

Tests that:
  - Normal RF + UNTRUSTED link → conflict detected
  - Jamming High + TRUSTED → conflict detected
  - Replay + Normal RF → conflict detected
  - Consistent evidence → no conflict
  - Conflict reduces confidence to LOW
  - Jamming + High + rule + DEGRADED → HIGH confidence
  - Replay → HIGH confidence
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from models.module2 import ThreatIntelligence
from models.module3 import SecureCommunication
from services.conflict_service import detect_conflict
from services.confidence_service import assess_confidence


def _ti(classification="Normal", severity=None, rule=None) -> ThreatIntelligence:
    return ThreatIntelligence(classification=classification, severity=severity, triggered_rule=rule)


def _sc(link="TRUSTED", fresh="FRESH", auth="VALID", integrity="VALID", replay=False) -> SecureCommunication:
    return SecureCommunication(
        link_state=link, freshness_state=fresh,
        auth_state=auth, integrity_state=integrity, replay_detected=replay
    )


# ─── Conflict detection tests ────────────────────────────────────────────────

def test_normal_rf_untrusted_link_conflict():
    """Normal RF + UNTRUSTED link = conflict."""
    result = detect_conflict(_ti("Normal"), _sc("UNTRUSTED"))
    assert result.evidence_conflict is True
    assert "UNTRUSTED" in result.conflict_reason


def test_normal_rf_suspicious_link_conflict():
    """Normal RF + SUSPICIOUS link = conflict."""
    result = detect_conflict(_ti("Normal"), _sc("SUSPICIOUS"))
    assert result.evidence_conflict is True


def test_jamming_high_trusted_conflict():
    """Jamming High + TRUSTED + no replay = conflict."""
    result = detect_conflict(_ti("Jamming", "High"), _sc("TRUSTED"))
    assert result.evidence_conflict is True
    assert "TRUSTED" in result.conflict_reason


def test_replay_normal_rf_conflict():
    """Replay + Normal RF = conflict."""
    result = detect_conflict(_ti("Normal"), _sc("TRUSTED", replay=True))
    assert result.evidence_conflict is True
    assert "replay" in result.conflict_reason.lower()


def test_no_conflict_jamming_degraded():
    """Jamming + DEGRADED = consistent evidence, no conflict."""
    result = detect_conflict(_ti("Jamming", "High"), _sc("DEGRADED"))
    assert result.evidence_conflict is False


def test_no_conflict_normal_trusted():
    """Normal + TRUSTED = no conflict."""
    result = detect_conflict(_ti("Normal"), _sc("TRUSTED"))
    assert result.evidence_conflict is False


def test_no_conflict_unknown_trusted():
    """Unknown Anomaly + TRUSTED = no conflict (not enough to flag)."""
    result = detect_conflict(_ti("Unknown Anomaly"), _sc("TRUSTED"))
    assert result.evidence_conflict is False


# ─── Confidence assessment tests ─────────────────────────────────────────────

def test_conflict_reduces_to_low_confidence():
    """Evidence conflict always reduces confidence to LOW."""
    from models.defense import ConflictResult
    conflict = ConflictResult(evidence_conflict=True, conflict_reason="Test conflict")
    result = assess_confidence(_ti("Normal"), _sc("TRUSTED"), conflict, "STABLE")
    assert result.level == "LOW"


def test_high_confidence_jamming_rule_degraded():
    """Jamming + High + triggered rule + DEGRADED = HIGH confidence."""
    from models.defense import ConflictResult
    no_conflict = ConflictResult(evidence_conflict=False)
    result = assess_confidence(
        _ti("Jamming", "High", rule="J01"), _sc("DEGRADED"), no_conflict, "STABLE"
    )
    assert result.level == "HIGH", f"Expected HIGH, got {result.level}: {result.rationale}"


def test_high_confidence_replay():
    """Replay = HIGH confidence."""
    from models.defense import ConflictResult
    no_conflict = ConflictResult(evidence_conflict=False)
    result = assess_confidence(_ti("Normal"), _sc("TRUSTED", replay=True), no_conflict, "STABLE")
    assert result.level == "HIGH", f"Expected HIGH for replay, got {result.level}"


def test_high_confidence_normal_trusted():
    """Normal + TRUSTED = HIGH confidence."""
    from models.defense import ConflictResult
    no_conflict = ConflictResult(evidence_conflict=False)
    result = assess_confidence(_ti("Normal"), _sc("TRUSTED"), no_conflict, "STABLE")
    assert result.level == "HIGH", f"Expected HIGH, got {result.level}"


def test_medium_confidence_unknown_degraded():
    """Unknown Anomaly + DEGRADED = MEDIUM confidence."""
    from models.defense import ConflictResult
    no_conflict = ConflictResult(evidence_conflict=False)
    result = assess_confidence(_ti("Unknown Anomaly"), _sc("DEGRADED"), no_conflict, "STABLE")
    assert result.level == "MEDIUM", f"Expected MEDIUM, got {result.level}"


if __name__ == "__main__":
    tests = [
        test_normal_rf_untrusted_link_conflict,
        test_normal_rf_suspicious_link_conflict,
        test_jamming_high_trusted_conflict,
        test_replay_normal_rf_conflict,
        test_no_conflict_jamming_degraded,
        test_no_conflict_normal_trusted,
        test_no_conflict_unknown_trusted,
        test_conflict_reduces_to_low_confidence,
        test_high_confidence_jamming_rule_degraded,
        test_high_confidence_replay,
        test_high_confidence_normal_trusted,
        test_medium_confidence_unknown_degraded,
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

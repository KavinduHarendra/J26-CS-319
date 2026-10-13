"""
tests/test_rule_engine.py — Unit tests for RuleBasedJammingDetector (src/rule_engine.py).

Verifies:
  - Rule J01 fires only when BOTH snr_drop and noise_floor_increase exceed thresholds.
  - Rule J02 fires only when BOTH rssi_deviation and packet_rate_deviation exceed thresholds.
  - Neither rule fires under normal conditions (returns None).
  - Both rules fire when conditions for both are satisfied simultaneously.
  - Custom rules can be registered and evaluated alongside or independently.
"""

import pytest

from src.rule_engine import Rule, RuleBasedJammingDetector, build_default_ruleset


# ---------------------------------------------------------------------------
# Helper to build synthetic deviation dicts
# ---------------------------------------------------------------------------

def make_deviations(
    snr_drop: float = 0.0,
    noise_floor_increase: float = 0.0,
    rssi_deviation: float = 0.0,
    packet_rate_deviation: float = 0.0,
) -> dict:
    """Construct a deviations dict matching NormalBaseline.deviations() output shape."""
    return {
        "snr_drop": snr_drop,
        "noise_floor_increase": noise_floor_increase,
        "rssi_deviation": rssi_deviation,
        "packet_rate_deviation": packet_rate_deviation,
        "z_scores": {
            "snr": -snr_drop,
            "noise_floor": noise_floor_increase,
            "rssi": rssi_deviation,
            "packet_rate": packet_rate_deviation,
        },
    }


# ---------------------------------------------------------------------------
# Tests for default ruleset (using explicit test thresholds to remain invariant)
# ---------------------------------------------------------------------------

class TestDefaultRulesetIndependentTriggers:
    """Verify each default rule triggers independently and strictly on its AND conditions."""

    @pytest.fixture
    def detector(self) -> RuleBasedJammingDetector:
        # Use explicit thresholds for testing: J01: (2.0, 2.0), J02: (2.5, 2.5)
        return build_default_ruleset(
            snr_thresh=2.0,
            noise_thresh=2.0,
            rssi_thresh=2.5,
            packet_thresh=2.5,
        )

    def test_normal_deviations_trigger_nothing(self, detector):
        """When deviations are small (typical normal flight), evaluate returns None."""
        dev = make_deviations(
            snr_drop=0.5,
            noise_floor_increase=0.3,
            rssi_deviation=0.8,
            packet_rate_deviation=0.4,
        )
        assert detector.evaluate(dev) is None

    def test_j01_fires_when_both_snr_and_noise_exceed_threshold(self, detector):
        """J01 fires when snr_drop > 2.0 AND noise_floor_increase > 2.0."""
        dev = make_deviations(
            snr_drop=4.5,
            noise_floor_increase=3.8,
            rssi_deviation=1.0,
            packet_rate_deviation=1.0,
        )
        result = detector.evaluate(dev)
        assert result is not None
        assert result["triggered_rules"] == ["J01"]
        assert len(result["rule_descriptions"]) == 1
        assert "SNR drop" in result["rule_descriptions"][0]

    def test_j01_does_not_fire_on_snr_drop_alone(self, detector):
        """Crucial test: SNR drop without noise floor rise must NOT fire J01."""
        dev = make_deviations(
            snr_drop=6.0,
            noise_floor_increase=0.2,  # below threshold
            rssi_deviation=0.5,
            packet_rate_deviation=0.5,
        )
        assert detector.evaluate(dev) is None

    def test_j01_does_not_fire_on_noise_rise_alone(self, detector):
        """Noise floor rise without SNR drop must NOT fire J01."""
        dev = make_deviations(
            snr_drop=0.1,  # below threshold
            noise_floor_increase=5.0,
            rssi_deviation=0.5,
            packet_rate_deviation=0.5,
        )
        assert detector.evaluate(dev) is None

    def test_j02_fires_when_both_rssi_and_packet_exceed_threshold(self, detector):
        """J02 fires when rssi_deviation > 2.5 AND packet_rate_deviation > 2.5."""
        dev = make_deviations(
            snr_drop=0.5,
            noise_floor_increase=0.5,
            rssi_deviation=3.2,
            packet_rate_deviation=4.0,
        )
        result = detector.evaluate(dev)
        assert result is not None
        assert result["triggered_rules"] == ["J02"]
        assert len(result["rule_descriptions"]) == 1
        assert "RSSI deviation" in result["rule_descriptions"][0]

    def test_j02_does_not_fire_on_rssi_alone(self, detector):
        """Severe RSSI deviation alone without abnormal packet rate must NOT fire J02."""
        dev = make_deviations(
            snr_drop=0.2,
            noise_floor_increase=0.2,
            rssi_deviation=5.0,
            packet_rate_deviation=1.0,  # below threshold
        )
        assert detector.evaluate(dev) is None

    def test_j02_does_not_fire_on_packet_rate_alone(self, detector):
        """Abnormal packet rate alone without RSSI deviation must NOT fire J02."""
        dev = make_deviations(
            snr_drop=0.2,
            noise_floor_increase=0.2,
            rssi_deviation=1.0,  # below threshold
            packet_rate_deviation=6.0,
        )
        assert detector.evaluate(dev) is None

    def test_both_rules_fire_simultaneously(self, detector):
        """When all conditions for J01 and J02 are met, both are reported."""
        dev = make_deviations(
            snr_drop=5.0,
            noise_floor_increase=4.0,
            rssi_deviation=3.5,
            packet_rate_deviation=3.8,
        )
        result = detector.evaluate(dev)
        assert result is not None
        assert result["triggered_rules"] == ["J01", "J02"]
        assert len(result["rule_descriptions"]) == 2


# ---------------------------------------------------------------------------
# Tests for Rule registration and custom rules
# ---------------------------------------------------------------------------

class TestCustomRuleRegistration:
    def test_empty_detector_returns_none(self):
        detector = RuleBasedJammingDetector()
        dev = make_deviations(snr_drop=10.0, noise_floor_increase=10.0)
        assert detector.evaluate(dev) is None

    def test_custom_rule(self):
        detector = RuleBasedJammingDetector()
        detector.register(Rule(
            rule_id="CUSTOM_01",
            description="Extreme packet rate drop only",
            condition=lambda d: d["packet_rate_deviation"] > 8.0,
        ))

        # Not triggered
        assert detector.evaluate(make_deviations(packet_rate_deviation=5.0)) is None

        # Triggered
        res = detector.evaluate(make_deviations(packet_rate_deviation=9.0))
        assert res is not None
        assert res["triggered_rules"] == ["CUSTOM_01"]
        assert res["rule_descriptions"] == ["Extreme packet rate drop only"]

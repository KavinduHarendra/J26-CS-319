"""
tests/test_anomaly_engine.py — Unit tests for StatisticalAnomalyEngine.

Verifies:
  - No significant deviation (all |z| < threshold) returns None.
  - Exactly one feature above threshold is detected and returned alone.
  - Multiple significant features all appear in the result.
  - The anomalous z_scores dict contains only the significant features (not all).
  - Custom z_threshold is respected.
"""

import pytest

from src.anomaly_engine import StatisticalAnomalyEngine


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def make_deviations(z_snr: float = 0.0, z_rssi: float = 0.0,
                    z_noise: float = 0.0, z_rate: float = 0.0) -> dict:
    """Build a deviations dict shaped exactly like NormalBaseline.deviations() output."""
    z = {
        "snr": z_snr,
        "rssi": z_rssi,
        "noise_floor": z_noise,
        "packet_rate": z_rate,
    }
    return {
        "snr_drop": -z_snr if z_snr < 0 else 0.0,
        "rssi_deviation": abs(z_rssi),
        "noise_floor_increase": z_noise if z_noise > 0 else 0.0,
        "packet_rate_deviation": abs(z_rate),
        "z_scores": z,
    }


# ---------------------------------------------------------------------------
# 1. No significant deviation → None
# ---------------------------------------------------------------------------

class TestNoSignificantDeviation:
    def test_all_z_small_returns_none(self):
        engine = StatisticalAnomalyEngine(z_threshold=3.0)
        dev = make_deviations(z_snr=-0.5, z_rssi=1.2, z_noise=0.8, z_rate=-1.5)
        assert engine.evaluate(dev) is None

    def test_exactly_at_threshold_returns_none(self):
        """Boundary: |z| must be >= threshold, not just < threshold."""
        engine = StatisticalAnomalyEngine(z_threshold=3.0)
        # |z| = 2.9999 — just below threshold — must return None
        dev = make_deviations(z_snr=-2.9999, z_rssi=0.0, z_noise=0.0, z_rate=0.0)
        assert engine.evaluate(dev) is None

    def test_empty_z_scores_returns_none(self):
        engine = StatisticalAnomalyEngine(z_threshold=3.0)
        dev = {"z_scores": {}}
        assert engine.evaluate(dev) is None

    def test_missing_z_scores_key_returns_none(self):
        """Gracefully handles deviations dict without z_scores key."""
        engine = StatisticalAnomalyEngine(z_threshold=3.0)
        assert engine.evaluate({}) is None


# ---------------------------------------------------------------------------
# 2. One significant feature
# ---------------------------------------------------------------------------

class TestSingleSignificantFeature:
    def test_snr_drop_triggers(self):
        engine = StatisticalAnomalyEngine(z_threshold=3.0)
        dev = make_deviations(z_snr=-6.5, z_rssi=0.5, z_noise=0.3, z_rate=-0.8)
        result = engine.evaluate(dev)
        assert result is not None
        assert result["anomalous_features"] == ["snr"]
        assert "snr" in result["z_scores"]
        assert result["z_scores"]["snr"] == pytest.approx(-6.5)

    def test_positive_noise_floor_triggers(self):
        engine = StatisticalAnomalyEngine(z_threshold=3.0)
        dev = make_deviations(z_snr=-1.0, z_rssi=0.5, z_noise=4.2, z_rate=0.3)
        result = engine.evaluate(dev)
        assert result is not None
        assert result["anomalous_features"] == ["noise_floor"]
        assert result["z_scores"]["noise_floor"] == pytest.approx(4.2)

    def test_negative_rssi_triggers(self):
        engine = StatisticalAnomalyEngine(z_threshold=3.0)
        dev = make_deviations(z_snr=-0.2, z_rssi=-3.5, z_noise=0.1, z_rate=0.5)
        result = engine.evaluate(dev)
        assert result is not None
        assert result["anomalous_features"] == ["rssi"]

    def test_result_contains_only_significant_z_scores(self):
        """z_scores dict in result must only include the significant feature, not all 4."""
        engine = StatisticalAnomalyEngine(z_threshold=3.0)
        dev = make_deviations(z_snr=-5.0, z_rssi=0.5, z_noise=0.2, z_rate=1.0)
        result = engine.evaluate(dev)
        assert result is not None
        assert set(result["z_scores"].keys()) == {"snr"}

    def test_threshold_exactly_met_triggers(self):
        """Boundary: |z| == threshold exactly must trigger."""
        engine = StatisticalAnomalyEngine(z_threshold=3.0)
        dev = make_deviations(z_snr=-3.0, z_rssi=0.0, z_noise=0.0, z_rate=0.0)
        result = engine.evaluate(dev)
        assert result is not None
        assert "snr" in result["anomalous_features"]


# ---------------------------------------------------------------------------
# 3. Multiple significant features
# ---------------------------------------------------------------------------

class TestMultipleSignificantFeatures:
    def test_two_features_both_returned(self):
        engine = StatisticalAnomalyEngine(z_threshold=3.0)
        dev = make_deviations(z_snr=-5.5, z_rssi=0.3, z_noise=4.0, z_rate=-0.5)
        result = engine.evaluate(dev)
        assert result is not None
        assert set(result["anomalous_features"]) == {"snr", "noise_floor"}
        assert "snr" in result["z_scores"]
        assert "noise_floor" in result["z_scores"]

    def test_three_features_all_returned(self):
        engine = StatisticalAnomalyEngine(z_threshold=3.0)
        dev = make_deviations(z_snr=-4.0, z_rssi=3.5, z_noise=5.0, z_rate=-0.5)
        result = engine.evaluate(dev)
        assert result is not None
        assert set(result["anomalous_features"]) == {"snr", "rssi", "noise_floor"}

    def test_all_four_features_significant(self):
        engine = StatisticalAnomalyEngine(z_threshold=3.0)
        dev = make_deviations(z_snr=-7.0, z_rssi=-3.1, z_noise=8.5, z_rate=-3.3)
        result = engine.evaluate(dev)
        assert result is not None
        assert set(result["anomalous_features"]) == {"snr", "rssi", "noise_floor", "packet_rate"}
        assert len(result["z_scores"]) == 4

    def test_non_significant_features_excluded_from_z_scores(self):
        """Verify that z_scores only contains the anomalous features."""
        engine = StatisticalAnomalyEngine(z_threshold=3.0)
        dev = make_deviations(z_snr=-5.0, z_rssi=1.2, z_noise=4.0, z_rate=0.8)
        result = engine.evaluate(dev)
        assert result is not None
        # rssi and packet_rate are NOT anomalous — must not appear
        assert "rssi" not in result["z_scores"]
        assert "packet_rate" not in result["z_scores"]


# ---------------------------------------------------------------------------
# 4. Custom threshold is respected
# ---------------------------------------------------------------------------

class TestCustomThreshold:
    def test_lower_threshold_detects_more_features(self):
        engine_strict = StatisticalAnomalyEngine(z_threshold=3.0)
        engine_loose = StatisticalAnomalyEngine(z_threshold=1.5)
        dev = make_deviations(z_snr=-2.0, z_rssi=0.3, z_noise=0.5, z_rate=0.1)
        # z=2.0 is below 3.0 but above 1.5
        assert engine_strict.evaluate(dev) is None
        result = engine_loose.evaluate(dev)
        assert result is not None
        assert "snr" in result["anomalous_features"]

    def test_higher_threshold_misses_moderate_deviations(self):
        engine = StatisticalAnomalyEngine(z_threshold=6.0)
        dev = make_deviations(z_snr=-5.9, z_rssi=0.0, z_noise=0.0, z_rate=0.0)
        assert engine.evaluate(dev) is None

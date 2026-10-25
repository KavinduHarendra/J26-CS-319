from pathlib import Path

import pytest

from src.baseline import BASELINE_FEATURES, Baseline, InvalidBaselineConfig
from src.real_data import load_signal


CONFIG = Path("config/thresholds_real.json")
SAMPLE = Path("data/real/module1_signals_clean/known_signals/000001_S00001.json")


def test_loads_two_calibrated_normal_states():
    baseline = Baseline.load(CONFIG)

    assert baseline.version == "real-raw-v1"
    assert set(baseline.idle.mean) == set(BASELINE_FEATURES)
    assert set(baseline.legitimate.mean) == set(BASELINE_FEATURES)
    assert baseline.idle.anomaly_limit == pytest.approx(3.0)
    assert baseline.legitimate.anomaly_limit == pytest.approx(4.979938, abs=1e-6)


def test_nearest_returns_per_feature_distances():
    state, distance, deviations = Baseline.load(CONFIG).nearest(load_signal(SAMPLE))

    assert state.name == "idle"
    assert distance == max(deviations.values())
    assert set(deviations) == set(BASELINE_FEATURES)
    assert all(value >= 0.0 for value in deviations.values())


def test_invalid_config_is_rejected():
    with pytest.raises(InvalidBaselineConfig):
        Baseline.from_config({"baseline_version": "x", "normal_states": {}})

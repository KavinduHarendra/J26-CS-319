import json
import logging
import random
from dataclasses import replace
from pathlib import Path

import pytest

from scripts.calibrate_real import build_configuration
from src.baseline import (
    BASELINE_FEATURES,
    ROBUST,
    STANDARD,
    Baseline,
    InvalidBaselineConfig,
    calibrate_state,
)
from src.normality_check import NormalityResult, check_normality, robust_z_score
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


def synthetic_state_signals(count: int = 200, seed: int = 7):
    """Gaussian snr_db; spectral_flatness forced non-Gaussian (exponential skew)."""
    rng = random.Random(seed)
    template = load_signal(SAMPLE)
    return [
        replace(
            template,
            observation_id=f"T{index:05d}",
            sequence_number=index + 1,
            peak_db=rng.gauss(-56.0, 0.6),
            snr_db=rng.gauss(49.0, 0.7),
            band_power_dbfs=rng.gauss(-20.0, 0.5),
            occupied_bw_khz=rng.gauss(350.0, 30.0),
            spectral_flatness=min(0.02 + rng.expovariate(1 / 0.05), 1.0),
        )
        for index in range(count)
    ]


def test_check_normality_separates_gaussian_and_skewed_data():
    rng = random.Random(1)

    assert check_normality([rng.gauss(0.0, 1.0) for _ in range(200)]).passed
    skewed = check_normality([rng.expovariate(1.0) for _ in range(200)])
    assert not skewed.passed
    assert skewed.test == "shapiro" and skewed.p_value < 0.05
    assert check_normality([3.0] * 50) == NormalityResult(False, "constant", None, 50)
    assert check_normality([1.0, 2.0]).test == "too_few"


def test_robust_z_score_is_modified_z_score():
    assert robust_z_score(14.0, 10.0, 2.0) == pytest.approx(0.6745 * 2.0)
    with pytest.raises(ValueError, match="MAD"):
        robust_z_score(1.0, 0.0, 0.0)


def test_calibration_uses_robust_z_only_for_non_gaussian_feature(caplog):
    signals = synthetic_state_signals()
    with caplog.at_level(logging.INFO, logger="src.baseline"):
        state = calibrate_state(signals, "legit_ook", normality_screen=True)

    assert state.normality["snr_db"].passed
    assert state.method("snr_db") == STANDARD
    assert not state.normality["spectral_flatness"].passed
    assert state.method("spectral_flatness") == ROBUST

    probe = 0.4
    assert state.deviation("spectral_flatness", probe) == pytest.approx(
        abs(robust_z_score(probe, state.median["spectral_flatness"], state.mad["spectral_flatness"]))
    )
    assert state.deviation("snr_db", 52.0) == pytest.approx(
        abs(52.0 - state.mean["snr_db"]) / state.spread["snr_db"]
    )
    messages = [record.getMessage() for record in caplog.records]
    assert any("snr_db" in message and "-> standard z-score" in message for message in messages)
    assert any(
        "spectral_flatness" in message and "-> robust z-score" in message for message in messages
    )


def test_feature_distances_follow_each_feature_method():
    state = calibrate_state(synthetic_state_signals(), "legit_ook", normality_screen=True)
    baseline = Baseline(version="test", idle=state, legitimate=state)
    signal = synthetic_state_signals(1, seed=99)[0]

    distances = baseline.feature_distances(signal, state)

    for feature in BASELINE_FEATURES:
        assert distances[feature] == pytest.approx(state.deviation(feature, getattr(signal, feature)))


def test_screening_is_off_by_default():
    state = calibrate_state(synthetic_state_signals(), "legit_ook")

    assert all(state.method(feature) == STANDARD for feature in BASELINE_FEATURES)
    assert state.normality == {}


def test_calibrated_methods_round_trip_through_config():
    configuration, split = build_configuration(normality_screen=True)
    baseline = Baseline.from_config(configuration)
    signal = load_signal(SAMPLE)

    assert baseline.legitimate.method("occupied_bw_khz") == ROBUST
    for key, state in (("idle", baseline.idle), ("legit_ook", baseline.legitimate)):
        fitted = calibrate_state(split.calibration[key], key, normality_screen=True)
        assert Baseline.feature_distances(signal, state) == pytest.approx(
            Baseline.feature_distances(signal, fitted)
        )


def test_shipped_config_uses_standard_formula():
    raw = json.loads(CONFIG.read_text(encoding="utf-8"))["normal_states"]
    baseline = Baseline.load(CONFIG)
    signal = load_signal(SAMPLE)

    assert "method" not in raw["idle"] and "method" not in raw["legit_ook"]
    for state in (baseline.idle, baseline.legitimate):
        assert all(state.method(feature) == STANDARD for feature in BASELINE_FEATURES)
        assert Baseline.feature_distances(signal, state)["snr_db"] == pytest.approx(
            abs(signal.snr_db - state.mean["snr_db"]) / state.spread["snr_db"]
        )


def test_robust_feature_without_mad_is_rejected():
    configuration, _ = build_configuration(normality_screen=True)
    del configuration["normal_states"]["legit_ook"]["mad"]["occupied_bw_khz"]

    with pytest.raises(InvalidBaselineConfig, match="median/mad"):
        Baseline.from_config(configuration)

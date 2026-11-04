import math
from dataclasses import replace

import pytest

from scripts.generate_distance_dataset import path_loss_db, synthetic_legit_signals
from src import contextual_baseline
from src.anomaly_engine import AnomalyEngine
from src.baseline import Baseline
from src.classifier import DEFAULT_CONFIG_PATH
from src.contextual_baseline import DistanceBandedBaseline


EDGES = [50, 150, 300]


@pytest.fixture(scope="module")
def base():
    return Baseline.load(DEFAULT_CONFIG_PATH)


@pytest.fixture(scope="module")
def calibration():
    return synthetic_legit_signals(600, seed=1)


@pytest.fixture(scope="module")
def evaluation():
    return synthetic_legit_signals(400, seed=2, start_sequence=5000)


@pytest.fixture
def banded(base, calibration):
    return DistanceBandedBaseline(EDGES, base, calibration)


def is_abnormal(baseline, signal):
    return AnomalyEngine(baseline).evaluate(signal).abnormal


def test_synthetic_signal_degrades_with_distance():
    assert path_loss_db(10.0) == 0.0
    assert path_loss_db(100.0) == pytest.approx(20.0)
    near = synthetic_legit_signals(1, seed=3, min_distance_m=10.0, max_distance_m=10.0)[0]
    far = synthetic_legit_signals(1, seed=3, min_distance_m=400.0, max_distance_m=400.0)[0]
    assert near.snr_db - far.snr_db == pytest.approx(path_loss_db(400.0), abs=0.01)


def test_long_range_normal_does_not_false_positive_with_its_band(base, banded, evaluation):
    long_range = [signal for signal in evaluation if signal.distance_m >= 300]
    assert len(long_range) > 50

    assert all(is_abnormal(base, signal) for signal in long_range)
    assert not any(is_abnormal(banded.get(signal.distance_m), signal) for signal in long_range)


def test_banded_baseline_has_no_false_positives_at_any_range(banded, evaluation):
    assert sum(is_abnormal(banded.get(signal.distance_m), signal) for signal in evaluation) == 0


def test_real_deviation_at_long_range_is_still_anomalous(banded, evaluation):
    far = next(signal for signal in evaluation if signal.distance_m >= 300)
    narrowband = replace(far, occupied_bw_khz=12.0)

    assert is_abnormal(banded.get(narrowband.distance_m), narrowband)


def test_get_uses_half_open_bands_and_caches_each_band(banded):
    assert banded.get(10.0) is banded.get(49.9)
    assert banded.get(50.0) is not banded.get(49.9)
    assert banded.get(50.0) is banded.get(149.9)
    assert banded.get(300.0) is banded.get(1_000.0)
    assert banded.band_range(3) == (300.0, math.inf)


def test_bands_are_calibrated_lazily_once(base, calibration, monkeypatch):
    calls = []
    original = contextual_baseline.calibrate_state

    def counting(signals, name, **options):
        calls.append(len(signals))
        return original(signals, name, **options)

    monkeypatch.setattr(contextual_baseline, "calibrate_state", counting)
    banded = DistanceBandedBaseline(EDGES, base, calibration)
    assert calls == []

    banded.get(200.0)
    banded.get(250.0)
    assert len(calls) == 1


def test_band_shares_idle_state_and_only_rebands_legitimate(base, banded):
    far = banded.get(350.0)

    assert far.idle is base.idle
    assert far.legitimate.mean["snr_db"] < base.legitimate.mean["snr_db"] - 20.0
    assert far.version == f"{base.version}+distance-300-infm"


def test_missing_distance_uses_flat_baseline(base, banded):
    assert banded.get(None) is base


def test_band_without_enough_calibration_data_is_rejected(base):
    near_only = synthetic_legit_signals(50, seed=4, max_distance_m=40.0)
    banded = DistanceBandedBaseline(EDGES, base, near_only)

    banded.get(20.0)
    with pytest.raises(ValueError, match="150-300 m has 0 calibration captures"):
        banded.get(200.0)


@pytest.mark.parametrize("edges", [[], [150, 50], [50, 50], [0, 50], [50, math.inf]])
def test_invalid_band_edges_are_rejected(base, edges):
    with pytest.raises(ValueError, match="band_edges"):
        DistanceBandedBaseline(edges, base, [])


def test_calibration_signal_without_distance_is_rejected(base, calibration):
    with pytest.raises(ValueError, match="has no distance_m"):
        DistanceBandedBaseline(EDGES, base, [replace(calibration[0], distance_m=None)])


def test_negative_distance_is_rejected(banded):
    with pytest.raises(ValueError, match="distance_m"):
        banded.get(-1.0)

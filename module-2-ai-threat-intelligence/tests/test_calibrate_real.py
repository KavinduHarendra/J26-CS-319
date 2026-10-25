"""Tests for chronological calibration from known raw signals only."""

from pathlib import Path

import pytest

from scripts.calibrate_real import DATA_ROOT, GROUPS, build_configuration


def test_reference_thresholds_and_limits_are_reproduced():
    configuration, _ = build_configuration()

    assert configuration["thresholds"]["T_SNR"] == pytest.approx(25.8)
    assert configuration["thresholds"]["T_BW"] == pytest.approx(137.5)
    assert configuration["normal_states"]["idle"]["anomaly_limit"] == pytest.approx(3.0)
    assert configuration["normal_states"]["legit_ook"]["anomaly_limit"] == pytest.approx(
        4.98, abs=0.01
    )


def test_each_group_is_split_chronologically_without_overlap():
    _, split = build_configuration()

    for name in GROUPS:
        calibration = split.calibration[name]
        validation = split.validation[name]
        assert calibration
        assert validation
        assert calibration[-1].timestamp <= validation[0].timestamp
        assert {item.observation_id for item in calibration}.isdisjoint(
            item.observation_id for item in validation
        )


def test_calibration_source_is_known_signals_only():
    configuration, split = build_configuration()

    assert configuration["provenance"]["source"].endswith("/known_signals")
    allowed_ids = {path.stem.split("_", 1)[1] for path in (DATA_ROOT / "known_signals").glob("*.json")}
    calibrated_ids = {
        signal.observation_id
        for name in GROUPS
        for signal in split.calibration[name] + split.validation[name]
    }
    assert calibrated_ids == allowed_ids
    assert not any("abnormal_signals" in part for part in Path(configuration["provenance"]["source"]).parts)
    assert not any("ambiguous_signals" in part for part in Path(configuration["provenance"]["source"]).parts)

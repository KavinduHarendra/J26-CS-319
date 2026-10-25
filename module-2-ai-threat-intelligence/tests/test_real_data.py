"""Tests for strict real Module 1 signal and scoring-label readers."""

from __future__ import annotations

import copy
import csv
import json
import math
from collections import Counter
from dataclasses import fields
from datetime import datetime
from pathlib import Path

import pytest

from src.real_data import (
    Signal,
    load_signal,
    load_stream,
)
from src.scoring_data import load_ground_truth, load_module1_flags_reference


REAL_FOLDER = Path("data/real/module1_signals_clean")


@pytest.fixture
def valid_payload() -> dict:
    return {
        "schema_version": "1.0",
        "source_module": "module1_sdr_rf_threat_detection",
        "observation_id": "S00001",
        "sequence_number": 1,
        "timestamp": "2026-10-23T16:22:20.957",
        "elapsed_s": 0.44,
        "measurements": {
            "peak_freq_mhz": 433.828,
            "peak_db": -103.0,
            "noise_db": -106.0,
            "snr_db": 3.0,
            "band_power_dbfs": -45.1,
            "occupied_bw_khz": 0.0,
            "spectral_flatness": 0.856,
        },
    }


def write_payload(path: Path, payload: dict) -> Path:
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_load_signal_returns_real_signal(valid_payload, tmp_path):
    signal = load_signal(write_payload(tmp_path / "signal.json", valid_payload))

    assert isinstance(signal, Signal)
    assert signal.observation_id == "S00001"
    assert signal.sequence_number == 1
    assert signal.timestamp == datetime(2026, 10, 23, 16, 22, 20, 957000)
    assert signal.peak_freq_mhz == pytest.approx(433.828)
    assert "signal_present" not in {field.name for field in fields(signal)}


@pytest.mark.parametrize("field", ["observation_id", "timestamp", "measurements"])
def test_load_signal_rejects_missing_top_level_fields(valid_payload, tmp_path, field):
    payload = copy.deepcopy(valid_payload)
    del payload[field]

    with pytest.raises(ValueError, match="missing required field"):
        load_signal(write_payload(tmp_path / "signal.json", payload))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("snr_db", float("nan")),
        ("snr_db", float("inf")),
        ("snr_db", None),
        ("snr_db", "3.0"),
        ("snr_db", True),
        ("occupied_bw_khz", -0.01),
        ("spectral_flatness", 1.01),
    ],
)
def test_load_signal_rejects_invalid_measurements(valid_payload, tmp_path, field, value):
    payload = copy.deepcopy(valid_payload)
    payload["measurements"][field] = value

    with pytest.raises(ValueError):
        load_signal(write_payload(tmp_path / "signal.json", payload))


def test_load_signal_rejects_missing_measurement(valid_payload, tmp_path):
    payload = copy.deepcopy(valid_payload)
    del payload["measurements"]["peak_db"]

    with pytest.raises(ValueError, match="measurements is missing"):
        load_signal(write_payload(tmp_path / "signal.json", payload))


@pytest.mark.parametrize("location", ["signal", "measurements"])
def test_load_signal_rejects_unexpected_fields(valid_payload, tmp_path, location):
    payload = copy.deepcopy(valid_payload)
    target = payload if location == "signal" else payload["measurements"]
    target["unexpected"] = 1.0

    with pytest.raises(ValueError, match="unexpected field"):
        load_signal(write_payload(tmp_path / "signal.json", payload))


@pytest.mark.parametrize(
    "field",
    [
        "label",
        "phase",
        "jamming",
        "interference",
        "signal_present",
        "channel",
        "power_anomaly",
        "expected_class",
        "jammer_type",
    ],
)
def test_load_signal_rejects_scoring_field_leakage(valid_payload, tmp_path, field):
    payload = copy.deepcopy(valid_payload)
    payload[field] = "must-not-enter-runtime"

    with pytest.raises(ValueError, match="forbidden metadata"):
        load_signal(write_payload(tmp_path / "signal.json", payload))


def test_load_signal_rejects_nested_scoring_field_leakage(valid_payload, tmp_path):
    payload = copy.deepcopy(valid_payload)
    payload["measurements"]["label"] = "hidden"

    with pytest.raises(ValueError, match="forbidden metadata"):
        load_signal(write_payload(tmp_path / "signal.json", payload))


@pytest.mark.parametrize("value", [float("nan"), float("inf"), None, "0.44", True, -1.0])
def test_load_signal_rejects_invalid_elapsed_time(valid_payload, tmp_path, value):
    payload = copy.deepcopy(valid_payload)
    payload["elapsed_s"] = value

    with pytest.raises(ValueError):
        load_signal(write_payload(tmp_path / "signal.json", payload))


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schema_version", "2.0"),
        ("source_module", "other_module"),
        ("sequence_number", True),
        ("sequence_number", 0),
        ("observation_id", "../escape"),
        ("timestamp", "not-a-timestamp"),
    ],
)
def test_load_signal_rejects_invalid_identity_fields(valid_payload, tmp_path, field, value):
    payload = copy.deepcopy(valid_payload)
    payload[field] = value

    with pytest.raises(ValueError):
        load_signal(write_payload(tmp_path / "signal.json", payload))


def test_load_signal_rejects_invalid_json(tmp_path):
    path = tmp_path / "signal.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(ValueError, match="invalid JSON"):
        load_signal(path)


def test_signal_collection_yields_sequence_order(valid_payload, tmp_path):
    second = copy.deepcopy(valid_payload)
    second.update(observation_id="S00002", sequence_number=2, elapsed_s=0.88)
    write_payload(tmp_path / "000002_S00002.json", second)
    write_payload(tmp_path / "000001_S00001.json", valid_payload)

    signals = list(load_stream(tmp_path))

    assert [signal.sequence_number for signal in signals] == [1, 2]
    assert [signal.observation_id for signal in signals] == ["S00001", "S00002"]


def test_load_stream_merges_nested_folders_in_sequence_order(valid_payload, tmp_path):
    second = copy.deepcopy(valid_payload)
    second.update(observation_id="S00002", sequence_number=2, elapsed_s=0.88)
    first_folder = tmp_path / "first_arbitrary_name"
    second_folder = tmp_path / "second_arbitrary_name"
    first_folder.mkdir()
    second_folder.mkdir()
    write_payload(first_folder / "later.json", second)
    write_payload(second_folder / "earlier.json", valid_payload)

    signals = list(load_stream(tmp_path))

    assert [signal.sequence_number for signal in signals] == [1, 2]


def test_signal_collection_recurses_without_exposing_path_as_data(valid_payload, tmp_path):
    nested = tmp_path / "arbitrary_container_name"
    nested.mkdir()
    write_payload(nested / "000001_S00001.json", valid_payload)

    signal = next(iter(load_stream(tmp_path)))

    assert signal.observation_id == "S00001"
    assert not hasattr(signal, "source_path")


def test_signal_collection_ignores_file_name(valid_payload, tmp_path):
    write_payload(tmp_path / "random-name.json", valid_payload)

    signals = list(load_stream(tmp_path))

    assert [signal.observation_id for signal in signals] == ["S00001"]


def test_signal_collection_requires_existing_root(tmp_path):
    with pytest.raises(ValueError, match="does not exist"):
        list(load_stream(tmp_path / "missing"))


def test_all_real_signals_validate_in_sequence_order():
    signals = list(load_stream(REAL_FOLDER))

    assert len(signals) == 1513
    assert signals[0].observation_id == "S00001"
    assert signals[-1].observation_id == "S01513"
    assert [signal.sequence_number for signal in signals] == list(range(1, 1514))
    for signal in signals:
        for field in fields(signal):
            value = getattr(signal, field.name)
            if isinstance(value, float):
                assert math.isfinite(value)


def test_ground_truth_is_loaded_separately_for_scoring_only():
    truth = load_ground_truth(REAL_FOLDER / "ground_truth.csv")

    assert len(truth) == 1513
    assert truth["S00001"]["expected_class"] == "NORMAL"
    assert Counter(row["expected_class"] for row in truth.values()) == {
        "NORMAL": 1324,
        "JAMMING": 189,
    }
    assert "expected_class" not in {field.name for field in fields(Signal)}


def test_module1_flags_are_loaded_separately_for_reporting_only():
    reference = load_module1_flags_reference(REAL_FOLDER / "module1_flags_reference.csv")

    assert len(reference) == 1513
    assert reference["S00001"]["signal_present"] == 0
    runtime_fields = {field.name for field in fields(Signal)}
    assert runtime_fields.isdisjoint(
        {"interference", "channel", "signal_present", "power_anomaly"}
    )


def test_ground_truth_rejects_duplicate_observation_ids(tmp_path):
    path = tmp_path / "ground_truth.csv"
    fieldnames = [
        "sequence_number",
        "observation_id",
        "file_name",
        "label_original",
        "phase",
        "expected_class",
        "normal_kind",
        "jammer_type",
        "label_quality_note",
    ]
    row = {
        "sequence_number": "1",
        "observation_id": "S00001",
        "file_name": "000001_S00001.json",
        "label_original": "none",
        "phase": "waiting",
        "expected_class": "NORMAL",
        "normal_kind": "idle",
        "jammer_type": "",
        "label_quality_note": "",
    }
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerow(row)
        writer.writerow(row)

    with pytest.raises(ValueError, match="duplicate ground truth observation_id"):
        load_ground_truth(path)

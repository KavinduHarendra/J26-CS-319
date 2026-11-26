"""Optional HackRF-era input fields: validated, carried, echoed, never decided on."""

import copy
import json
import math
from dataclasses import asdict, replace
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from src.api import EXAMPLE_OBSERVATION, app
from src.classifier import build_classifier
from src.contracts import ThreatStateOut, to_contract
from src.output_writer import CaptureOutputWriter
from src.real_data import load_signal, load_stream, parse_signal, signal_to_record


REAL_FOLDER = Path("data/real/module1_signals_clean")
SAMPLE = REAL_FOLDER / "known_signals" / "000001_S00001.json"
TOP_LEVEL_VALID = {
    "session_id": "S20261201_A",
    "center_freq_hz": 433.92e6,
    "sample_rate_hz": 2.4e6,
    "gain_db": 32.0,
    "distance_m": 120.0,
}
MEASUREMENT_VALID = {"occupied_fraction": 0.25, "peak_count": 3, "duty_cycle": 0.5}
NUMERIC_TOP_LEVEL_INVALID = {
    "center_freq_hz": [999_999.0, 6.000001e9],
    "sample_rate_hz": [0.0, -1.0],
    "gain_db": [-0.1, 100.1],
    "distance_m": [-1.0, 100_001.0],
}
MEASUREMENT_INVALID = {
    "occupied_fraction": [-0.01, 1.01],
    "duty_cycle": [-0.01, 1.01],
    "peak_count": [-1, 1001],
}


def base_payload() -> dict:
    return copy.deepcopy(EXAMPLE_OBSERVATION)


def with_all_fields(payload: dict) -> dict:
    payload = payload | TOP_LEVEL_VALID
    payload["measurements"] = payload["measurements"] | MEASUREMENT_VALID
    return payload


def test_every_existing_recording_still_loads_without_new_fields():
    signals = list(load_stream(REAL_FOLDER))

    assert len(signals) == 1513
    for signal in signals:
        assert signal.session_id is None
        assert signal.center_freq_hz is None and signal.peak_count is None


def test_all_new_fields_load_and_round_trip():
    signal = parse_signal(with_all_fields(base_payload()))

    for field, value in {**TOP_LEVEL_VALID, **MEASUREMENT_VALID}.items():
        assert getattr(signal, field) == value
    assert parse_signal(signal_to_record(signal)) == signal
    assert signal_to_record(load_signal(SAMPLE)) == json.loads(SAMPLE.read_text(encoding="utf-8"))


@pytest.mark.parametrize(("field", "value"), TOP_LEVEL_VALID.items())
def test_each_top_level_field_accepts_a_valid_value_alone(field, value):
    assert getattr(parse_signal(base_payload() | {field: value}), field) == value


@pytest.mark.parametrize(("field", "value"), MEASUREMENT_VALID.items())
def test_each_measurement_field_accepts_a_valid_value_alone(field, value):
    payload = base_payload()
    payload["measurements"][field] = value

    assert getattr(parse_signal(payload), field) == value


INVALID_TOP_LEVEL = [
    (field, value)
    for field, values in NUMERIC_TOP_LEVEL_INVALID.items()
    for value in [*values, math.nan, math.inf, -math.inf, "1", True, [1]]
]


@pytest.mark.parametrize(("field", "value"), INVALID_TOP_LEVEL)
def test_invalid_top_level_values_are_rejected(field, value):
    with pytest.raises(ValueError, match=field):
        parse_signal(base_payload() | {field: value})


INVALID_MEASUREMENTS = [
    (field, value)
    for field, values in MEASUREMENT_INVALID.items()
    for value in [*values, math.nan, math.inf, "0.5", True]
] + [("peak_count", 3.0), ("peak_count", 2.5)]


@pytest.mark.parametrize(("field", "value"), INVALID_MEASUREMENTS)
def test_invalid_measurement_values_are_rejected(field, value):
    payload = base_payload()
    payload["measurements"][field] = value

    with pytest.raises(ValueError, match=field):
        parse_signal(payload)


@pytest.mark.parametrize("value", ["", "has space", "x" * 65, "a/b", 42, True])
def test_invalid_session_id_is_rejected(value):
    with pytest.raises(ValueError, match="session_id"):
        parse_signal(base_payload() | {"session_id": value})


@pytest.mark.parametrize(
    "key",
    ["label", "Label", "phase", "jammer", "jammer_on", "event_type", "expected_class", "channel"],
)
@pytest.mark.parametrize("location", ["top", "measurements"])
def test_label_like_key_is_rejected_anywhere(key, location):
    payload = with_all_fields(base_payload())
    target = payload if location == "top" else payload["measurements"]
    target[key] = 1

    with pytest.raises(ValueError, match="forbidden metadata"):
        parse_signal(payload)


def test_unknown_measurement_is_still_rejected():
    payload = with_all_fields(base_payload())
    payload["measurements"]["rssi_dbm"] = -40.0

    with pytest.raises(ValueError, match="unexpected field"):
        parse_signal(payload)


def test_new_fields_do_not_change_classification_or_fuzzy_score():
    classifier = build_classifier()
    extras = {**TOP_LEVEL_VALID, **MEASUREMENT_VALID}

    for signal in load_stream(REAL_FOLDER):
        plain = asdict(classifier.classify(signal))
        enriched = asdict(classifier.classify(replace(signal, **extras)))
        plain.pop("processing_ms")
        enriched.pop("processing_ms")
        assert enriched == plain


def test_session_id_round_trips_to_output_files(tmp_path):
    signal = replace(load_signal(SAMPLE), session_id="S20261201_A")
    output = build_classifier().classify(signal)
    writer = CaptureOutputWriter(tmp_path)

    writer.write(signal, output)
    for destination in writer.destinations.values():
        [path] = destination.glob("*.json")
        payload = json.loads(path.read_text(encoding="utf-8"))
        assert payload["session_id"] == "S20261201_A"
        assert ThreatStateOut.model_validate_json(path.read_text(encoding="utf-8")).session_id == (
            "S20261201_A"
        )


def test_output_without_session_has_no_session_key(tmp_path):
    signal = load_signal(SAMPLE)
    writer = CaptureOutputWriter(tmp_path)

    writer.write(signal, build_classifier().classify(signal))
    [path] = writer.destinations["module3"].glob("*.json")
    assert "session_id" not in json.loads(path.read_text(encoding="utf-8"))


def test_contract_rejects_invalid_session_id():
    output = build_classifier().classify(load_signal(SAMPLE))

    with pytest.raises(ValidationError):
        to_contract(output, recipient="module3", session_id="bad id")


def test_api_echoes_session_id_only_when_present():
    with TestClient(app) as client:
        with_session = client.post("/classify", json=base_payload() | {"session_id": "S1"}).json()
        without = client.post("/classify", json=base_payload()).json()

    assert with_session["session_id"] == "S1"
    assert "session_id" not in without
    with_session.pop("session_id")
    for body in (with_session, without):
        body.pop("processing_ms")
    assert with_session == without

"""Tests for the local file-based Module 1/2/3/4 JSON exchange."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path

import pytest

from src.classifier import ThreatOutput
from src.contracts import (
    MODULE1_SOURCE,
    SCHEMA_VERSION,
    ObservationIn,
    ThreatStateOut,
    to_contract,
)
from src.file_exchange import (
    ensure_exchange_folders,
    exchange_filename,
    write_json_atomic,
)
from src.file_processor import FileProcessor, MAX_INPUT_BYTES


def valid_input(sequence: int = 1, observation_id: str = "capture-001") -> ObservationIn:
    return ObservationIn(
        schema_version=SCHEMA_VERSION,
        source_module=MODULE1_SOURCE,
        sequence_number=sequence,
        observation_id=observation_id,
        timestamp=datetime(2026, 10, 22, 12, 0, tzinfo=timezone.utc),
        rssi=-60.0,
        snr=25.0,
        noise_floor=-90.0,
        packet_rate=100.0,
    )


@pytest.fixture
def exchange_root(tmp_path) -> Path:
    return tmp_path / "exchange"


@pytest.fixture
def processor(exchange_root) -> FileProcessor:
    return FileProcessor(exchange_root, seed=42)


def test_atomic_write_exposes_only_complete_destination(tmp_path, monkeypatch):
    destination = tmp_path / "capture.json"
    real_replace = os.replace
    replace_observations = []

    def observing_replace(source, target):
        source_path = Path(source)
        target_path = Path(target)
        replace_observations.append((source_path.exists(), target_path.exists()))
        real_replace(source, target)

    monkeypatch.setattr("src.file_exchange.os.replace", observing_replace)
    write_json_atomic(destination, {"complete": True, "items": [1, 2, 3]})

    assert replace_observations == [(True, False)]
    assert json.loads(destination.read_text(encoding="utf-8")) == {
        "complete": True,
        "items": [1, 2, 3],
    }
    assert not (tmp_path / "capture.json.tmp").exists()


def test_filename_uses_only_validated_sequence_and_sanitized_id():
    name = exchange_filename(7, "../../radio capture:7")
    assert name == "000007_______radio_capture_7.json"
    assert "/" not in name
    assert "\\" not in name


@pytest.mark.parametrize(
    ("source_classification", "source_severity", "contract_classification", "contract_severity"),
    [
        ("Normal", None, "NORMAL", None),
        ("Jamming", "High", "JAMMING", "HIGH"),
        ("Unknown Anomaly", "Medium", "UNKNOWN_ANOMALY", "MEDIUM"),
        ("Unknown Anomaly", "Low", "UNKNOWN_ANOMALY", "LOW"),
    ],
)
def test_to_contract_maps_existing_labels(
    source_classification,
    source_severity,
    contract_classification,
    contract_severity,
):
    output = ThreatOutput(
        observation_id="mapping-test",
        timestamp="2026-10-22T12:00:00+00:00",
        classification=source_classification,
        severity=source_severity,
        triggered_rule=None,
    )
    contract = to_contract(
        output,
        sequence_number=1,
        baseline_version="1.0",
        processing_ms=0.5,
        recipient="module3",
    )
    assert contract.classification == contract_classification
    assert contract.severity == contract_severity


def test_invalid_json_nan_and_oversized_inputs_are_rejected_without_output(
    processor, exchange_root
):
    paths = ensure_exchange_folders(exchange_root)
    (paths["inbox"] / "000001_bad-json.json").write_text("{not json", encoding="utf-8")

    nan_payload = valid_input(sequence=2, observation_id="nan-snr").model_dump(mode="json")
    nan_payload["snr"] = float("nan")
    (paths["inbox"] / "000002_nan-snr.json").write_text(
        json.dumps(nan_payload, allow_nan=True),
        encoding="utf-8",
    )

    (paths["inbox"] / "000003_too-large.json").write_bytes(b"x" * (MAX_INPUT_BYTES + 1))

    assert processor.process_pending() == 3
    assert len(list(paths["rejected"].glob("*.json"))) == 3
    assert len(list(paths["rejected"].glob("*.reason.txt"))) == 3
    assert list(paths["module3"].glob("*.json")) == []
    assert list(paths["module4"].glob("*.json")) == []
    assert processor.stats_snapshot()["rejected"] == 3
    assert processor.stats_snapshot()["class_counts"] == {}


def test_duplicate_sequence_does_not_create_duplicate_outputs(processor, exchange_root):
    paths = ensure_exchange_folders(exchange_root)
    first = valid_input(sequence=10, observation_id="first")
    write_json_atomic(
        paths["inbox"] / exchange_filename(first.sequence_number, first.observation_id),
        first,
    )
    processor.process_pending()

    duplicate = valid_input(sequence=10, observation_id="second")
    write_json_atomic(
        paths["inbox"] / exchange_filename(duplicate.sequence_number, duplicate.observation_id),
        duplicate,
    )
    processor.process_pending()

    assert len(list(paths["module3"].glob("*.json"))) == 1
    assert len(list(paths["module4"].glob("*.json"))) == 1
    assert processor.stats_snapshot()["duplicates"] == 1
    assert sum(processor.stats_snapshot()["class_counts"].values()) == 1


def test_each_valid_capture_creates_one_valid_output_per_recipient(
    processor, exchange_root
):
    paths = ensure_exchange_folders(exchange_root)
    capture = valid_input(sequence=25, observation_id="radio/capture 25")
    input_name = exchange_filename(capture.sequence_number, capture.observation_id)
    write_json_atomic(paths["inbox"] / input_name, capture)

    assert processor.process_pending() == 1

    module3_files = list(paths["module3"].glob("*.json"))
    module4_files = list(paths["module4"].glob("*.json"))
    assert len(module3_files) == 1
    assert len(module4_files) == 1
    assert module3_files[0].name == "000025_radio_capture_25_threat.json"
    assert module4_files[0].name == "000025_radio_capture_25_threat.json"

    module3 = ThreatStateOut.model_validate_json(module3_files[0].read_bytes())
    module4 = ThreatStateOut.model_validate_json(module4_files[0].read_bytes())
    assert module3.recipient == "module3"
    assert module4.recipient == "module4"
    assert module3.sequence_number == module4.sequence_number == 25
    assert module3.classification == module4.classification
    assert len(list(paths["processed"].glob("*.json"))) == 1

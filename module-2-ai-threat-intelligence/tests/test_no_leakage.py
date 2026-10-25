from __future__ import annotations

import csv
import inspect
import json
import random
import re
import shutil
import uuid
from dataclasses import asdict
from pathlib import Path

import pytest

from src import anomaly_engine, baseline, classifier, real_data, rule_engine
from src.classifier import ThreatClassifier, build_classifier
from src.real_data import Signal, load_signal, load_stream, signal_to_record
from src.scoring_data import load_ground_truth


pytestmark = pytest.mark.slow


DATA = Path("data/real/module1_signals_clean")
FORBIDDEN = (
    "label",
    "phase",
    "expected_class",
    "jammer_type",
    "ground_truth",
    "interference",
    "signal_present",
    "channel",
    "power_anomaly",
)


def signature(signal: Signal, engine: ThreatClassifier) -> dict:
    value = asdict(engine.classify(signal))
    value.pop("processing_ms")
    return value


@pytest.fixture(scope="module")
def signals() -> list[Signal]:
    return list(load_stream(DATA))


@pytest.fixture(scope="module")
def expected_outputs(signals: list[Signal]) -> dict[str, dict]:
    engine = build_classifier()
    return {signal.observation_id: signature(signal, engine) for signal in signals}


def test_pipeline_runs_on_all_1513_measurement_records(
    signals: list[Signal], expected_outputs: dict[str, dict]
):
    assert len(signals) == 1513
    assert len(expected_outputs) == 1513


def test_shuffled_scoring_values_cannot_change_outputs(
    signals: list[Signal], expected_outputs: dict[str, dict], tmp_path: Path
):
    source = DATA / "ground_truth.csv"
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
        fieldnames = list(rows[0])
    generator = random.Random(319)
    labels = [row["expected_class"] for row in rows]
    phases = [row["phase"] for row in rows]
    generator.shuffle(labels)
    generator.shuffle(phases)
    for row, expected, phase in zip(rows, labels, phases):
        row["expected_class"] = expected
        row["phase"] = phase
    changed = tmp_path / "ground_truth.csv"
    with changed.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    assert len(load_ground_truth(changed)) == 1513
    engine = build_classifier()
    rerun = {signal.observation_id: signature(signal, engine) for signal in signals}
    assert rerun == expected_outputs


def test_flat_random_file_names_cannot_change_outputs(
    signals: list[Signal], expected_outputs: dict[str, dict], tmp_path: Path
):
    flat = tmp_path / "flat"
    flat.mkdir()
    for signal in signals:
        path = flat / f"{uuid.uuid4().hex}.json"
        path.write_text(json.dumps(signal_to_record(signal)), encoding="utf-8")

    engine = build_classifier()
    rerun = {
        signal.observation_id: signature(signal, engine) for signal in load_stream(flat)
    }
    assert rerun == expected_outputs


def test_reference_file_can_be_removed_without_changing_outputs(
    expected_outputs: dict[str, dict], tmp_path: Path
):
    copied = tmp_path / "recording"
    shutil.copytree(DATA, copied)
    (copied / "module1_flags_reference.csv").unlink()

    engine = build_classifier()
    rerun = {
        signal.observation_id: signature(signal, engine) for signal in load_stream(copied)
    }
    assert rerun == expected_outputs


def test_classifier_is_stateless_and_future_order_cannot_change_earlier_outputs(
    signals: list[Signal]
):
    engine = build_classifier()
    earlier = signals[:25]
    before = [signature(signal, engine) for signal in earlier]
    future = signals[25:]
    random.Random(42).shuffle(future)
    for signal in future:
        engine.classify(signal)
    after = [signature(signal, engine) for signal in earlier]

    assert before == after
    assert set(engine.__dict__) == {"baseline", "rules", "anomaly"}


def test_leakage_guard_rejects_label_key(tmp_path: Path):
    payload = signal_to_record(next(load_stream(DATA / "known_signals")))
    payload["label"] = "JAMMING"
    path = tmp_path / "leaked.json"
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match="forbidden metadata"):
        load_signal(path)


def test_classification_path_has_no_forbidden_metadata_access():
    modules = (real_data, baseline, rule_engine, anomaly_engine, classifier)
    access_patterns = [
        re.compile(rf"\.\s*{re.escape(name)}\b|\[\s*['\"]{re.escape(name)}['\"]\s*\]")
        for name in FORBIDDEN
    ]
    for module in modules:
        source = inspect.getsource(module)
        assert "src.scoring_data" not in source
        for pattern in access_patterns:
            assert not pattern.search(source), f"forbidden metadata access in {module.__name__}"

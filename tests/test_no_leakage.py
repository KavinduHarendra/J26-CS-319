"""End-to-end proofs that runtime classification uses measurement records only."""

from __future__ import annotations

import csv
import json
import random
import shutil
import uuid
from dataclasses import asdict
from pathlib import Path

import pytest

from src.real_classifier import RealThreatClassifierV2
from src.real_data import RealSignal, SignalCollectionSource, load_signal
from src.real_detection import build_frozen_detector_v2
from src.scoring_data import load_ground_truth


DATA = Path("data/real/module1_signals_clean")


def classify(signals: list[RealSignal]) -> dict[str, dict[str, object]]:
    classifier = RealThreatClassifierV2(build_frozen_detector_v2())
    return {
        signal.observation_id: asdict(classifier.classify(signal)) for signal in signals
    }


@pytest.fixture(scope="module")
def signals() -> list[RealSignal]:
    return list(SignalCollectionSource(DATA))


@pytest.fixture(scope="module")
def expected_outputs(signals: list[RealSignal]) -> dict[str, dict[str, object]]:
    return classify(signals)


@pytest.fixture(scope="module")
def flat_collection(tmp_path_factory, signals: list[RealSignal]) -> Path:
    destination = tmp_path_factory.mktemp("flat-signals")
    source_by_id = {
        json.loads(path.read_text(encoding="utf-8"))["observation_id"]: path
        for path in DATA.rglob("*.json")
    }
    names = [f"{uuid.UUID(int=index + 1)}.json" for index in range(len(signals))]
    random.Random(319).shuffle(names)
    for signal, name in zip(signals, names):
        shutil.copy2(source_by_id[signal.observation_id], destination / name)
    return destination


def test_pipeline_runs_on_all_1513_measurement_records(
    signals: list[RealSignal], expected_outputs: dict[str, dict[str, object]]
) -> None:
    assert len(signals) == 1513
    assert len(expected_outputs) == 1513


def test_shuffling_scoring_labels_and_phases_cannot_change_outputs(
    signals: list[RealSignal], expected_outputs: dict[str, dict[str, object]], tmp_path: Path
) -> None:
    source = DATA / "ground_truth.csv"
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    shuffled_labels = [row["expected_class"] for row in rows]
    shuffled_phases = [row["phase"] for row in rows]
    rng = random.Random(319)
    rng.shuffle(shuffled_labels)
    rng.shuffle(shuffled_phases)
    for row, expected_class, phase in zip(rows, shuffled_labels, shuffled_phases):
        row["expected_class"] = expected_class
        row["phase"] = phase

    shuffled_path = tmp_path / "ground_truth.csv"
    with shuffled_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    shuffled_truth = load_ground_truth(shuffled_path)
    assert shuffled_truth[signals[0].observation_id] != load_ground_truth(source)[
        signals[0].observation_id
    ]
    assert classify(signals) == expected_outputs


def test_random_flat_file_names_cannot_change_outputs(
    flat_collection: Path, expected_outputs: dict[str, dict[str, object]]
) -> None:
    flat_signals = list(SignalCollectionSource(flat_collection))

    assert [signal.sequence_number for signal in flat_signals] == list(range(1, 1514))
    assert classify(flat_signals) == expected_outputs


def test_module1_reference_file_is_not_required(
    flat_collection: Path, expected_outputs: dict[str, dict[str, object]]
) -> None:
    assert not (flat_collection / "module1_flags_reference.csv").exists()
    assert classify(list(SignalCollectionSource(flat_collection))) == expected_outputs


def test_future_order_cannot_change_earlier_stateless_outputs(
    signals: list[RealSignal], expected_outputs: dict[str, dict[str, object]]
) -> None:
    cutoff = 200
    future = signals[cutoff:]
    random.Random(319).shuffle(future)
    rerun = classify(signals[:cutoff] + future)

    assert not hasattr(RealThreatClassifierV2(build_frozen_detector_v2()), "window")
    for signal in signals[:cutoff]:
        assert rerun[signal.observation_id] == expected_outputs[signal.observation_id]


def test_leakage_guard_rejects_label_key(tmp_path: Path) -> None:
    source = next((DATA / "known_signals").glob("*.json"))
    payload = json.loads(source.read_text(encoding="utf-8"))
    payload["label"] = "NORMAL"
    contaminated = tmp_path / "contaminated.json"
    contaminated.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(ValueError, match=r"forbidden metadata key\(s\): label"):
        load_signal(contaminated)

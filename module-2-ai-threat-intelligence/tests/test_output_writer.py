import json
from dataclasses import replace
from pathlib import Path

from src.classifier import build_classifier
from src.contracts import ThreatStateOut
from src.output_writer import CaptureOutputWriter
from src.real_data import load_signal


SAMPLE = Path("data/real/module1_signals_clean/known_signals/000001_S00001.json")


def test_each_capture_writes_one_valid_file_per_recipient(tmp_path):
    signal = load_signal(SAMPLE)
    output = build_classifier().classify(signal)
    writer = CaptureOutputWriter(tmp_path)

    assert writer.write(signal, output)
    for recipient in ("module3", "module4"):
        files = list(writer.destinations[recipient].glob("*.json"))
        assert len(files) == 1
        contract = ThreatStateOut.model_validate_json(files[0].read_text(encoding="utf-8"))
        assert contract.recipient == recipient
        assert contract.observation_id == signal.observation_id


def test_duplicate_sequence_is_not_reprocessed(tmp_path):
    signal = load_signal(SAMPLE)
    classifier = build_classifier()
    writer = CaptureOutputWriter(tmp_path)

    assert writer.write(signal, classifier.classify(signal))
    duplicate = replace(signal, observation_id="DIFFERENT")
    assert not writer.write(duplicate, classifier.classify(duplicate))
    assert writer.stats()["duplicates"] == 1
    assert all(len(list(path.glob("*.json"))) == 1 for path in writer.destinations.values())


def test_default_clears_json_unless_keep(tmp_path):
    destination = tmp_path / "module2_to_module3"
    destination.mkdir(parents=True)
    stale = destination / "stale.json"
    stale.write_text(json.dumps({"stale": True}), encoding="utf-8")

    CaptureOutputWriter(tmp_path)
    assert not stale.exists()
    stale.write_text(json.dumps({"stale": True}), encoding="utf-8")
    CaptureOutputWriter(tmp_path, keep=True)
    assert stale.exists()


def test_missing_sequences_and_class_counts_are_tracked(tmp_path):
    signal = replace(load_signal(SAMPLE), sequence_number=3, observation_id="S00003")
    writer = CaptureOutputWriter(tmp_path)

    writer.write(signal, build_classifier().classify(signal))
    stats = writer.stats()
    assert stats["received"] == 1
    assert stats["missing_sequence_numbers"] == [1, 2]
    assert sum(stats["class_counts"].values()) == 1

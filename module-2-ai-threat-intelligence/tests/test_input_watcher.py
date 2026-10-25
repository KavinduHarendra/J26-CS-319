from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

from src.classifier import build_classifier
from src.input_watcher import SignalInbox
from src.output_writer import CaptureOutputWriter
from src.real_data import load_signal, signal_to_record
from src.unified_demo import process, score


SAMPLE = Path("data/real/module1_signals_clean/known_signals/000001_S00001.json")


def _write_signal(path: Path, sequence_number: int, observation_id: str) -> None:
    payload = signal_to_record(load_signal(SAMPLE))
    payload["sequence_number"] = sequence_number
    payload["observation_id"] = observation_id
    path.write_text(json.dumps(payload), encoding="utf-8")


def test_flat_inbox_detects_files_added_after_start_in_sequence_order(tmp_path):
    inbox = SignalInbox(tmp_path, settle_seconds=0)
    assert inbox.poll().signals == ()

    _write_signal(tmp_path / "later.json", 2, "LIVE0002")
    _write_signal(tmp_path / "earlier.json", 1, "LIVE0001")

    batch = inbox.poll()
    assert [signal.sequence_number for signal in batch.signals] == [1, 2]
    assert inbox.poll().signals == ()


def test_inbox_reads_only_direct_json_children(tmp_path):
    nested = tmp_path / "nested"
    nested.mkdir()
    _write_signal(nested / "hidden.json", 1, "LIVE0001")

    assert SignalInbox(tmp_path, settle_seconds=0).poll().signals == ()


def test_inbox_rejects_invalid_json_and_continues(tmp_path):
    (tmp_path / "broken.json").write_text("{broken", encoding="utf-8")
    _write_signal(tmp_path / "valid.json", 1, "LIVE0001")

    batch = SignalInbox(tmp_path, settle_seconds=0).poll()

    assert [signal.observation_id for signal in batch.signals] == ["LIVE0001"]
    assert [item.file_name for item in batch.rejected] == ["broken.json"]


def test_inbox_skips_duplicate_sequence_numbers(tmp_path):
    _write_signal(tmp_path / "first.json", 1, "LIVE0001")
    _write_signal(tmp_path / "duplicate.json", 1, "LIVE0002")

    batch = SignalInbox(tmp_path, settle_seconds=0).poll()

    assert len(batch.signals) == 1
    assert len(batch.duplicates) == 1


def test_inbox_rejects_oversized_file(tmp_path):
    path = tmp_path / "large.json"
    path.write_bytes(b"x" * 101)

    batch = SignalInbox(tmp_path, settle_seconds=0, max_bytes=100).poll()

    assert batch.signals == ()
    assert batch.rejected[0].file_name == "large.json"
    assert "exceeds 100 byte limit" in batch.rejected[0].reason


def test_new_capture_without_reference_is_classified_as_unscored(tmp_path):
    signal = replace(
        load_signal(SAMPLE), observation_id="LIVE9999", sequence_number=9999
    )

    processed = process(signal, build_classifier(), CaptureOutputWriter(tmp_path))
    scored = score(processed, {})

    assert scored.processed.output.classification in {
        "NORMAL",
        "JAMMING",
        "UNKNOWN_ANOMALY",
    }
    assert scored.reference["expected_class"] == "UNSCORED"
    assert not scored.matches_expected

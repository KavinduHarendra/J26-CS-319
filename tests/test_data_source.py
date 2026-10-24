"""Tests for the recorded Module 1 data-source adapter."""

from __future__ import annotations

import json

import pytest

from src.data_source import RFDataSource, RecordedSignalSource
from src.real_data import RealSignal


def record(sequence: int) -> dict:
    return {
        "schema_version": "1.0",
        "source_module": "module1_sdr_rf_threat_detection",
        "observation_id": f"S{sequence:05d}",
        "sequence_number": sequence,
        "timestamp": f"2026-10-23T16:22:{sequence:02d}.000",
        "elapsed_s": float(sequence),
        "measurements": {
            "peak_freq_mhz": 433.958,
            "peak_db": -103.0,
            "noise_db": -106.0,
            "snr_db": 3.0,
            "band_power_dbfs": -45.1,
            "occupied_bw_khz": 0.0,
            "spectral_flatness": 0.851,
        },
    }


def write_record(folder, sequence: int) -> None:
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{sequence:06d}_S{sequence:05d}.json"
    path.write_text(json.dumps(record(sequence)), encoding="utf-8")


def test_abstract_source_cannot_be_instantiated():
    with pytest.raises(TypeError):
        RFDataSource()  # type: ignore[abstract]


def test_recorded_source_reads_validated_records_in_sequence_order(tmp_path):
    write_record(tmp_path / "later_folder", 2)
    write_record(tmp_path / "earlier_folder", 1)
    source = RecordedSignalSource(tmp_path)

    batch = source.fetch_batch(2)

    assert [signal.sequence_number for signal in batch] == [1, 2]
    assert all(isinstance(signal, RealSignal) for signal in batch)
    assert source.exhausted is False


def test_recorded_source_tracks_exhaustion(tmp_path):
    write_record(tmp_path, 1)
    source = RecordedSignalSource(tmp_path)

    assert len(source.fetch_batch(5)) == 1
    assert source.exhausted is True
    assert source.fetch_batch(1) == []


@pytest.mark.parametrize("value", [-1, 1.5, True])
def test_recorded_source_rejects_invalid_batch_size(tmp_path, value):
    source = RecordedSignalSource(tmp_path)

    with pytest.raises(ValueError, match="non-negative integer"):
        source.fetch_batch(value)


def test_zero_batch_does_not_consume_record(tmp_path):
    write_record(tmp_path, 1)
    source = RecordedSignalSource(tmp_path)

    assert source.fetch_batch(0) == []
    assert source.fetch_batch(1)[0].sequence_number == 1

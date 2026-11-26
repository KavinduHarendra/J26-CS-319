import csv
import hashlib
import json
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from scripts import validate_recording
from scripts.validate_recording import FAIL, PASS, main, validate


START = datetime(2026, 12, 1, 10, 0, 0)


def capture(sequence: int, **changes) -> dict:
    payload = {
        "schema_version": "1.0",
        "source_module": "module1_sdr_rf_threat_detection",
        "observation_id": f"S{sequence:05d}",
        "sequence_number": sequence,
        "timestamp": (START + timedelta(seconds=0.5 * sequence)).isoformat(timespec="milliseconds"),
        "elapsed_s": 0.5 * sequence,
        "session_id": "S20261201_A",
        "center_freq_hz": 433.92e6,
        "sample_rate_hz": 2.4e6,
        "gain_db": 32.0,
        "measurements": {
            "peak_freq_mhz": 433.92,
            "peak_db": -103.0,
            "noise_db": -106.0,
            "snr_db": 3.0,
            "band_power_dbfs": -45.0,
            "occupied_bw_khz": 0.0,
            "spectral_flatness": 0.85,
        },
    }
    measurements = changes.pop("measurements", {})
    payload.update(changes)
    payload["measurements"].update(measurements)
    return payload


def make_folder(root: Path, sequences=range(1, 6), *, truth=True, overrides=None) -> Path:
    overrides = overrides or {}
    root.mkdir(parents=True, exist_ok=True)
    for sequence in sequences:
        payload = capture(sequence, **overrides.get(sequence, {}))
        name = f"{sequence:06d}_{payload['observation_id']}.json"
        (root / name).write_text(json.dumps(payload), encoding="utf-8")
    if truth:
        with (root / "ground_truth.csv").open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(["sequence_number", "observation_id", "timestamp", "expected_class", "event_type", "jammer_on"])
            for sequence in dict.fromkeys(sequences):
                writer.writerow([sequence, f"S{sequence:05d}", "", "NORMAL", "idle", 0])
    return root


def statuses(folder: Path) -> dict[str, str]:
    checks, _ = validate(folder)
    return {check.name: check.status for check in checks}


def run(folder: Path) -> tuple[int, str]:
    lines: list[str] = []
    code = main([str(folder)], out=lines.append)
    return code, "\n".join(lines)


def test_good_folder_passes(tmp_path):
    code, report = run(make_folder(tmp_path / "good"))

    assert code == 0
    assert "RESULT: PASS (0 failed" in report
    assert "NORMAL: 5" in report
    assert FAIL not in statuses(tmp_path / "good").values()


def test_validator_does_not_modify_the_folder(tmp_path):
    folder = make_folder(tmp_path / "good")

    def fingerprint():
        return {
            path.name: (hashlib.sha256(path.read_bytes()).hexdigest(), path.stat().st_mtime_ns)
            for path in sorted(folder.iterdir())
        }

    before = fingerprint()
    run(folder)
    assert fingerprint() == before


def test_sequence_gap_fails(tmp_path):
    code, report = run(make_folder(tmp_path / "gap", sequences=[1, 2, 4, 5]))

    assert code == 1
    assert "[FAIL] sequence gaps: 1 missing: 3" in report


def test_duplicate_sequence_fails(tmp_path):
    folder = make_folder(tmp_path / "dup")
    duplicate = capture(3, observation_id="S99999")
    (folder / "copy.json").write_text(json.dumps(duplicate), encoding="utf-8")

    code, report = run(folder)

    assert code == 1
    assert "[FAIL] duplicates: duplicated sequence_number 3" in report


def test_out_of_range_value_fails(tmp_path):
    folder = make_folder(tmp_path / "range", overrides={2: {"measurements": {"spectral_flatness": 1.5}}})

    code, report = run(folder)

    assert code == 1
    assert "[FAIL] files: 1 of 5 files invalid" in report
    assert "spectral_flatness" in report


def test_missing_ground_truth_fails(tmp_path):
    code, report = run(make_folder(tmp_path / "no_truth", truth=False))

    assert code == 1
    assert "[FAIL] ground truth: ground_truth.csv not found" in report


def test_uncovered_capture_fails(tmp_path):
    folder = make_folder(tmp_path / "uncovered")
    (folder / "000006_S00006.json").write_text(json.dumps(capture(6)), encoding="utf-8")

    code, report = run(folder)

    assert code == 1
    assert "1 captures have no row" in report


def test_timestamp_going_backwards_fails(tmp_path):
    folder = make_folder(tmp_path / "time", overrides={4: {"timestamp": "2026-12-01T09:00:00.000"}})

    assert statuses(folder)["timestamp order"] == FAIL


def test_changing_gain_and_mixed_session_fail(tmp_path):
    folder = make_folder(tmp_path / "mixed", overrides={2: {"gain_db": 40.0}, 3: {"session_id": "S20261201_B"}})

    result = statuses(folder)
    assert result["fixed gain_db"] == FAIL
    assert result["session_id"] == FAIL


def test_revealing_session_id_fails(tmp_path):
    folder = make_folder(
        tmp_path / "named", overrides={n: {"session_id": "carrier_jam_10m"} for n in range(1, 6)}
    )

    assert statuses(folder)["session_id naming"] == FAIL


def test_clipping_fails(tmp_path):
    folder = make_folder(tmp_path / "clip", overrides={5: {"measurements": {"band_power_dbfs": -0.5}}})

    assert statuses(folder)["ADC clipping"] == FAIL


def test_label_in_capture_is_rejected_by_the_loader(tmp_path):
    folder = make_folder(tmp_path / "leak", overrides={1: {"label": "JAMMING"}})

    code, report = run(folder)

    assert code == 1
    assert "forbidden metadata" in report


def test_validator_never_classifies():
    source = Path(validate_recording.__file__).read_text(encoding="utf-8")

    assert "src.classifier" not in source
    assert "classify(" not in source


@pytest.mark.slow
def test_current_recording_passes_with_warnings():
    code, report = run(Path("data/real/module1_signals_clean"))

    assert code == 0
    assert "[PASS] ground truth: every capture has exactly one row (1513)" in report
    assert "JAMMING: 189" in report
    assert statuses(Path("data/real/module1_signals_clean"))["sequence gaps"] == PASS

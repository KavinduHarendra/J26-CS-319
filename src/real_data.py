"""Validated readers for real signal records exported by Module 1.

Ground-truth labels are deliberately handled by a separate scoring-only loader.
They are never attached to :class:`RealSignal` or exposed by
:class:`JsonFolderSource`.
"""

from __future__ import annotations

import csv
import json
import math
import re
from collections.abc import Iterator, Mapping
from dataclasses import dataclass
from datetime import datetime
from numbers import Real
from pathlib import Path
from typing import Any


SCHEMA_VERSION = "1.0"
SOURCE_MODULE = "module1_sdr_rf_threat_detection"

MEASUREMENT_RANGES: dict[str, tuple[float, float]] = {
    # Broad input-safety bounds, not classification thresholds.
    "peak_freq_mhz": (0.0, 100_000.0),
    "peak_db": (-300.0, 100.0),
    "noise_db": (-300.0, 100.0),
    "snr_db": (-200.0, 300.0),
    "band_power_dbfs": (-300.0, 100.0),
    "occupied_bw_khz": (0.0, 1_000_000.0),
    "spectral_flatness": (0.0, 1.0),
}
ELAPSED_S_RANGE = (0.0, 1_000_000_000.0)

MEASUREMENT_FIELDS = tuple(MEASUREMENT_RANGES)
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "source_module",
    "observation_id",
    "sequence_number",
    "timestamp",
    "elapsed_s",
    "measurements",
}
_FORBIDDEN_RUNTIME_FIELDS = {"phase", "label", "expected_class", "jammer_type"}
_GROUND_TRUTH_FIELDS = {
    "sequence_number",
    "observation_id",
    "file_name",
    "label_original",
    "phase",
    "expected_class",
    "normal_kind",
    "jammer_type",
    "label_quality_note",
}
_MODULE1_REFERENCE_FIELDS = {
    "sequence_number",
    "observation_id",
    "interference",
    "channel",
    "signal_present",
    "power_anomaly",
}
_OBSERVATION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SIGNAL_FILE_NAME = re.compile(r"^(\d{6})_([A-Za-z0-9_-]{1,64})\.json$")


def _require_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be a JSON object")
    return value


def _require_fields(value: Mapping[str, Any], fields: set[str] | tuple[str, ...], context: str) -> None:
    missing = sorted(set(fields) - set(value))
    if missing:
        raise ValueError(f"{context} is missing required field(s): {', '.join(missing)}")


def _finite_float(value: Any, field: str, bounds: tuple[float, float]) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise ValueError(f"{field} must be a real number")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field} must be finite")
    minimum, maximum = bounds
    if not minimum <= result <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return result


def _positive_sequence(value: Any) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError("sequence_number must be an integer")
    if not 1 <= value <= 999_999:
        raise ValueError("sequence_number must be between 1 and 999999")
    return value


def _binary_flag(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1):
        raise ValueError(f"module1_flags.{field} must be integer 0 or 1")
    return value


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("timestamp must be an ISO 8601 date-time string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("timestamp must be an ISO 8601 date-time string") from exc
    return parsed


@dataclass(frozen=True, slots=True)
class RealSignal:
    """One validated Module 1 signal containing measurements only.

    Labels, capture phases, jammer names, and Module 1's own flags are kept out
    of this runtime type so they cannot accidentally become detector features.
    """

    observation_id: str
    sequence_number: int
    timestamp: datetime
    elapsed_s: float
    peak_freq_mhz: float
    peak_db: float
    noise_db: float
    snr_db: float
    band_power_dbfs: float
    occupied_bw_khz: float
    spectral_flatness: float

    def __post_init__(self) -> None:
        if not isinstance(self.observation_id, str) or not _OBSERVATION_ID.fullmatch(
            self.observation_id
        ):
            raise ValueError(
                "observation_id must contain 1-64 ASCII letters, digits, underscores, or hyphens"
            )
        _positive_sequence(self.sequence_number)
        if not isinstance(self.timestamp, datetime):
            raise ValueError("timestamp must be a datetime")
        _finite_float(self.elapsed_s, "elapsed_s", ELAPSED_S_RANGE)
        for field, bounds in MEASUREMENT_RANGES.items():
            _finite_float(getattr(self, field), field, bounds)


def load_signal(path: str | Path) -> RealSignal:
    """Read and strictly validate one Module 1 signal JSON file."""
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {source}: {exc.msg}") from exc

    root = _require_mapping(payload, "signal")
    _require_fields(root, _TOP_LEVEL_FIELDS, "signal")
    leaked = sorted(_FORBIDDEN_RUNTIME_FIELDS & set(root))
    if leaked:
        raise ValueError(
            "signal contains scoring-only field(s): " + ", ".join(leaked)
        )
    if root["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
    if root["source_module"] != SOURCE_MODULE:
        raise ValueError(f"source_module must be {SOURCE_MODULE!r}")

    measurements = _require_mapping(root["measurements"], "measurements")
    _require_fields(measurements, MEASUREMENT_FIELDS, "measurements")

    observation_id = root["observation_id"]
    if not isinstance(observation_id, str):
        raise ValueError("observation_id must be a string")
    return RealSignal(
        observation_id=observation_id,
        sequence_number=_positive_sequence(root["sequence_number"]),
        timestamp=_timestamp(root["timestamp"]),
        elapsed_s=_finite_float(root["elapsed_s"], "elapsed_s", ELAPSED_S_RANGE),
        peak_freq_mhz=_finite_float(
            measurements["peak_freq_mhz"],
            "measurements.peak_freq_mhz",
            MEASUREMENT_RANGES["peak_freq_mhz"],
        ),
        peak_db=_finite_float(
            measurements["peak_db"], "measurements.peak_db", MEASUREMENT_RANGES["peak_db"]
        ),
        noise_db=_finite_float(
            measurements["noise_db"], "measurements.noise_db", MEASUREMENT_RANGES["noise_db"]
        ),
        snr_db=_finite_float(
            measurements["snr_db"], "measurements.snr_db", MEASUREMENT_RANGES["snr_db"]
        ),
        band_power_dbfs=_finite_float(
            measurements["band_power_dbfs"],
            "measurements.band_power_dbfs",
            MEASUREMENT_RANGES["band_power_dbfs"],
        ),
        occupied_bw_khz=_finite_float(
            measurements["occupied_bw_khz"],
            "measurements.occupied_bw_khz",
            MEASUREMENT_RANGES["occupied_bw_khz"],
        ),
        spectral_flatness=_finite_float(
            measurements["spectral_flatness"],
            "measurements.spectral_flatness",
            MEASUREMENT_RANGES["spectral_flatness"],
        ),
    )


class JsonFolderSource:
    """Yield validated JSON signals in ascending sequence-number order."""

    def __init__(self, folder: str | Path) -> None:
        self.folder = Path(folder)
        if not self.folder.is_dir():
            raise ValueError(f"signal folder does not exist: {self.folder}")

    def __iter__(self) -> Iterator[RealSignal]:
        indexed_paths: list[tuple[int, str, Path]] = []
        for path in self.folder.rglob("*.json"):
            if path.is_symlink():
                raise ValueError(f"symbolic links are not accepted: {path.name}")
            match = _SIGNAL_FILE_NAME.fullmatch(path.name)
            if match is None:
                raise ValueError(f"invalid signal filename: {path.name}")
            indexed_paths.append((int(match.group(1)), match.group(2), path))

        seen_sequences: set[int] = set()
        seen_observations: set[str] = set()
        for file_sequence, file_observation_id, path in sorted(indexed_paths):
            signal = load_signal(path)
            if signal.sequence_number != file_sequence:
                raise ValueError(f"sequence_number does not match filename: {path.name}")
            if signal.observation_id != file_observation_id:
                raise ValueError(f"observation_id does not match filename: {path.name}")
            if signal.sequence_number in seen_sequences:
                raise ValueError(f"duplicate sequence_number: {signal.sequence_number}")
            if signal.observation_id in seen_observations:
                raise ValueError(f"duplicate observation_id: {signal.observation_id}")
            seen_sequences.add(signal.sequence_number)
            seen_observations.add(signal.observation_id)
            yield signal


def signal_to_record(signal: RealSignal) -> dict[str, Any]:
    """Serialize a validated signal in the Module 1 exchange shape."""
    if not isinstance(signal, RealSignal):
        raise TypeError("signal_to_record requires a validated RealSignal")
    return {
        "schema_version": SCHEMA_VERSION,
        "source_module": SOURCE_MODULE,
        "observation_id": signal.observation_id,
        "sequence_number": signal.sequence_number,
        "timestamp": signal.timestamp.isoformat(timespec="milliseconds"),
        "elapsed_s": signal.elapsed_s,
        "measurements": {
            feature: getattr(signal, feature) for feature in MEASUREMENT_FIELDS
        },
    }


def load_ground_truth(path: str | Path) -> dict[str, dict[str, str]]:
    """Load labels by observation ID for offline scoring only.

    Do not pass this return value to detection, baseline, feature extraction, or
    classification code.
    """
    source = Path(path)
    result: dict[str, dict[str, str]] = {}
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("ground truth CSV has no header")
        missing = sorted(_GROUND_TRUTH_FIELDS - set(reader.fieldnames))
        if missing:
            raise ValueError(
                "ground truth CSV is missing required column(s): " + ", ".join(missing)
            )
        for line_number, row in enumerate(reader, start=2):
            if any(value is None for value in row.values()):
                raise ValueError(f"ground truth row {line_number} has missing values")
            observation_id = row["observation_id"].strip()
            if not _OBSERVATION_ID.fullmatch(observation_id):
                raise ValueError(f"invalid observation_id on ground truth row {line_number}")
            if observation_id in result:
                raise ValueError(f"duplicate ground truth observation_id: {observation_id}")
            _positive_sequence(_csv_integer(row["sequence_number"], line_number))
            result[observation_id] = dict(row)
    return result


def load_module1_flags_reference(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load Module 1 flags for offline agreement reporting only.

    These flags are intentionally absent from :class:`RealSignal`; callers must
    not pass this mapping into baseline fitting, rule evaluation, or anomaly
    detection.
    """
    source = Path(path)
    result: dict[str, dict[str, Any]] = {}
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Module 1 reference CSV has no header")
        missing = sorted(_MODULE1_REFERENCE_FIELDS - set(reader.fieldnames))
        if missing:
            raise ValueError(
                "Module 1 reference CSV is missing required column(s): "
                + ", ".join(missing)
            )
        for line_number, row in enumerate(reader, start=2):
            observation_id = row["observation_id"].strip()
            if not _OBSERVATION_ID.fullmatch(observation_id):
                raise ValueError(f"invalid observation_id on reference row {line_number}")
            if observation_id in result:
                raise ValueError(f"duplicate reference observation_id: {observation_id}")
            sequence_number = _positive_sequence(
                _csv_integer(row["sequence_number"], line_number)
            )
            result[observation_id] = {
                "sequence_number": sequence_number,
                "interference": _binary_flag(
                    _csv_integer(row["interference"], line_number), "interference"
                ),
                "channel": row["channel"].strip(),
                "signal_present": _binary_flag(
                    _csv_integer(row["signal_present"], line_number), "signal_present"
                ),
                "power_anomaly": _binary_flag(
                    _csv_integer(row["power_anomaly"], line_number), "power_anomaly"
                ),
            }
    return result


def _csv_integer(value: str, line_number: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(
            f"invalid sequence_number on ground truth row {line_number}"
        ) from exc

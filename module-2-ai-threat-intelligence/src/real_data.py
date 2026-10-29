"""Validated measurement records exported by Module 1."""

from __future__ import annotations

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
_OBSERVATION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_FORBIDDEN_INPUT_KEYS = {
    "la" + "bel",
    "ph" + "ase",
    "jamming",
    "inter" + "ference",
    "signal" + "_present",
    "chan" + "nel",
    "power" + "_anomaly",
    "expected" + "_class",
    "jammer" + "_type",
}


def _require_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be a JSON object")
    return value


def _require_exact_fields(
    value: Mapping[str, Any],
    fields: set[str] | tuple[str, ...],
    context: str,
) -> None:
    expected = set(fields)
    actual = set(value)
    missing = sorted(expected - actual)
    if missing:
        raise ValueError(f"{context} is missing required field(s): {', '.join(missing)}")
    unexpected = sorted(actual - expected)
    if unexpected:
        raise ValueError(f"{context} has unexpected field(s): {', '.join(unexpected)}")


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        leaked = sorted(_FORBIDDEN_INPUT_KEYS & set(value))
        if leaked:
            raise ValueError("signal contains forbidden metadata key(s): " + ", ".join(leaked))
        for child in value.values():
            _reject_forbidden_keys(child)
    elif isinstance(value, list):
        for child in value:
            _reject_forbidden_keys(child)


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


def _timestamp(value: Any) -> datetime:
    if not isinstance(value, str) or "T" not in value:
        raise ValueError("timestamp must be an ISO 8601 date-time string")
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("timestamp must be an ISO 8601 date-time string") from exc
    return parsed


@dataclass(frozen=True, slots=True)
class Signal:
    """One validated Module 1 measurement record."""

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


def load_signal(path: str | Path) -> Signal:
    """Read and strictly validate one Module 1 signal JSON file."""
    source = Path(path)
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON in {source}: {exc.msg}") from exc
    return parse_signal(payload)


def parse_signal(payload: Any) -> Signal:
    """Strictly validate one decoded Module 1 record in the exchange shape."""
    root = _require_mapping(payload, "signal")
    _reject_forbidden_keys(root)
    _require_exact_fields(root, _TOP_LEVEL_FIELDS, "signal")
    if root["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
    if root["source_module"] != SOURCE_MODULE:
        raise ValueError(f"source_module must be {SOURCE_MODULE!r}")

    measurements = _require_mapping(root["measurements"], "measurements")
    _require_exact_fields(measurements, MEASUREMENT_FIELDS, "measurements")

    observation_id = root["observation_id"]
    if not isinstance(observation_id, str):
        raise ValueError("observation_id must be a string")
    return Signal(
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


def load_stream(root: str | Path) -> Iterator[Signal]:
    """Merge JSON captures below *root* into one sequence-ordered stream.

    Directory names and file names are never copied into runtime records.  This
    also permits the leakage tests to place the same captures in one flat container
    under arbitrary file names without changing classifier inputs.
    """
    source = Path(root)
    if not source.is_dir():
        raise ValueError(f"signal collection does not exist: {source}")

    indexed_signals: list[tuple[int, str, Signal]] = []
    for path in source.rglob("*.json"):
        if path.is_symlink():
            raise ValueError(f"symbolic links are not accepted: {path.name}")
        signal = load_signal(path)
        indexed_signals.append((signal.sequence_number, signal.observation_id, signal))

    seen_sequences: set[int] = set()
    seen_observations: set[str] = set()
    for _, _, signal in sorted(indexed_signals):
        if signal.sequence_number in seen_sequences:
            raise ValueError(f"duplicate sequence_number: {signal.sequence_number}")
        if signal.observation_id in seen_observations:
            raise ValueError(f"duplicate observation_id: {signal.observation_id}")
        seen_sequences.add(signal.sequence_number)
        seen_observations.add(signal.observation_id)
        yield signal


def signal_to_record(signal: Signal) -> dict[str, Any]:
    """Serialize a validated signal in the Module 1 exchange shape."""
    if not isinstance(signal, Signal):
        raise TypeError("signal_to_record requires a validated Signal")
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

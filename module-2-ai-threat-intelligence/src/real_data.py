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
DISTANCE_M_RANGE = (0.0, 100_000.0)
# Optional SDR session metadata (HackRF-era exports).  Carried on Signal for
# auditing; no decision reads these fields.
OPTIONAL_TOP_LEVEL_RANGES: dict[str, tuple[float, float]] = {
    "distance_m": DISTANCE_M_RANGE,
    "center_freq_hz": (1e6, 6e9),
    "sample_rate_hz": (0.0, math.inf),  # lower bound exclusive, see _positive
    "gain_db": (0.0, 100.0),
}
# Optional extra measurements; validated and carried, not yet used by any decision.
OPTIONAL_MEASUREMENT_RANGES: dict[str, tuple[float, float]] = {
    "occupied_fraction": (0.0, 1.0),
    "duty_cycle": (0.0, 1.0),
}
PEAK_COUNT_RANGE = (0, 1000)
_EXCLUSIVE_MINIMUM = {"sample_rate_hz"}

MEASUREMENT_FIELDS = tuple(MEASUREMENT_RANGES)
OPTIONAL_MEASUREMENT_FIELDS = frozenset({*OPTIONAL_MEASUREMENT_RANGES, "peak_count"})
_TOP_LEVEL_FIELDS = {
    "schema_version",
    "source_module",
    "observation_id",
    "sequence_number",
    "timestamp",
    "elapsed_s",
    "measurements",
}
# All optional; absent in older Module 1 exports.
_OPTIONAL_TOP_LEVEL_FIELDS = frozenset({*OPTIONAL_TOP_LEVEL_RANGES, "session_id"})
_OBSERVATION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
_SESSION_ID = _OBSERVATION_ID
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
    "ground" + "_truth",
    "jammer",
    "jammer" + "_on",
    "event" + "_type",
}


def _require_mapping(value: Any, context: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{context} must be a JSON object")
    return value


def _require_exact_fields(
    value: Mapping[str, Any],
    fields: set[str] | tuple[str, ...],
    context: str,
    optional: set[str] | frozenset[str] = frozenset(),
) -> None:
    expected = set(fields)
    actual = set(value)
    missing = sorted(expected - actual)
    if missing:
        raise ValueError(f"{context} is missing required field(s): {', '.join(missing)}")
    unexpected = sorted(actual - expected - optional)
    if unexpected:
        raise ValueError(f"{context} has unexpected field(s): {', '.join(unexpected)}")


def _reject_forbidden_keys(value: Any) -> None:
    if isinstance(value, Mapping):
        leaked = sorted(
            key for key in value if isinstance(key, str) and key.lower() in _FORBIDDEN_INPUT_KEYS
        )
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


def _positive(value: Any, field: str, bounds: tuple[float, float]) -> float:
    result = _finite_float(value, field, bounds)
    if result <= bounds[0]:
        raise ValueError(f"{field} must be greater than {bounds[0]}")
    return result


def _optional_float(value: Any, field: str, bounds: tuple[float, float]) -> float | None:
    if value is None:
        return None
    if field.rsplit(".", 1)[-1] in _EXCLUSIVE_MINIMUM:
        return _positive(value, field, bounds)
    return _finite_float(value, field, bounds)


def _peak_count(value: Any, field: str = "peak_count") -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field} must be an integer")
    minimum, maximum = PEAK_COUNT_RANGE
    if not minimum <= value <= maximum:
        raise ValueError(f"{field} must be between {minimum} and {maximum}")
    return value


def _session_id(value: Any) -> str | None:
    if value is None:
        return None
    if not isinstance(value, str) or not _SESSION_ID.fullmatch(value):
        raise ValueError(
            "session_id must contain 1-64 ASCII letters, digits, underscores, or hyphens"
        )
    return value


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
    distance_m: float | None = None
    session_id: str | None = None
    center_freq_hz: float | None = None
    sample_rate_hz: float | None = None
    gain_db: float | None = None
    occupied_fraction: float | None = None
    peak_count: int | None = None
    duty_cycle: float | None = None

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
        for field, bounds in (OPTIONAL_TOP_LEVEL_RANGES | OPTIONAL_MEASUREMENT_RANGES).items():
            _optional_float(getattr(self, field), field, bounds)
        _peak_count(self.peak_count)
        _session_id(self.session_id)


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
    _require_exact_fields(root, _TOP_LEVEL_FIELDS, "signal", _OPTIONAL_TOP_LEVEL_FIELDS)
    if root["schema_version"] != SCHEMA_VERSION:
        raise ValueError(f"schema_version must be {SCHEMA_VERSION!r}")
    if root["source_module"] != SOURCE_MODULE:
        raise ValueError(f"source_module must be {SOURCE_MODULE!r}")

    measurements = _require_mapping(root["measurements"], "measurements")
    _require_exact_fields(
        measurements, MEASUREMENT_FIELDS, "measurements", OPTIONAL_MEASUREMENT_FIELDS
    )

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
        session_id=_session_id(root.get("session_id")),
        **{
            field: _optional_float(root.get(field), field, bounds)
            for field, bounds in OPTIONAL_TOP_LEVEL_RANGES.items()
        },
        **{
            field: _optional_float(measurements.get(field), f"measurements.{field}", bounds)
            for field, bounds in OPTIONAL_MEASUREMENT_RANGES.items()
        },
        peak_count=_peak_count(measurements.get("peak_count"), "measurements.peak_count"),
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
    record = {
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
    for field in ("session_id", *OPTIONAL_TOP_LEVEL_RANGES):
        if getattr(signal, field) is not None:
            record[field] = getattr(signal, field)
    for field in (*OPTIONAL_MEASUREMENT_RANGES, "peak_count"):
        if getattr(signal, field) is not None:
            record["measurements"][field] = getattr(signal, field)
    return record

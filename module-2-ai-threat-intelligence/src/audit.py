"""Append-only audit logging and deterministic input-record hashing."""

from __future__ import annotations

import hashlib
import json
import math
import threading
from datetime import datetime
from numbers import Real
from pathlib import Path
from typing import Any, Mapping


DEFAULT_AUDIT_LOG_PATH = Path(__file__).resolve().parent.parent / "data" / "audit_log.jsonl"
INPUT_FIELDS = (
    "observation_id",
    "timestamp",
    "rssi",
    "snr",
    "noise_floor",
    "packet_rate",
)


def _safe_value(value: Any) -> Any:
    """Return a deterministic JSON-safe representation, including invalid values."""
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, bool) or value is None or isinstance(value, str):
        return value
    if isinstance(value, Real):
        numeric = float(value)
        if math.isfinite(numeric):
            return value
        return {"non_finite_number": repr(numeric)}
    return {"type": type(value).__name__, "repr": repr(value)}


def input_record(obs: Any) -> dict[str, Any]:
    """Build the exact canonical input record used for the audit hash."""
    if isinstance(obs, Mapping):
        return {field: _safe_value(obs.get(field)) for field in INPUT_FIELDS}
    return {
        field: _safe_value(getattr(obs, field, {"missing": True}))
        for field in INPUT_FIELDS
    }


def hash_input_record(obs: Any) -> str:
    """Return the SHA-256 digest of a canonical JSON representation of ``obs``."""
    canonical = json.dumps(
        input_record(obs),
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(canonical).hexdigest()


class AuditLogger:
    """Write one complete JSON object per line without truncating prior records."""

    _write_lock = threading.Lock()

    def __init__(self, path: str | Path = DEFAULT_AUDIT_LOG_PATH):
        self.path = Path(path)

    def _append(self, record: dict[str, Any]) -> None:
        line = json.dumps(
            record,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        )
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._write_lock:
            with self.path.open("a", encoding="utf-8", newline="\n") as audit_file:
                audit_file.write(line + "\n")

    def log_classification(self, obs: Any, output: Any, baseline_version: str) -> None:
        """Append an audit record for a completed classification."""
        self._append({
            "observation_id": output.observation_id,
            "timestamp": output.timestamp,
            "classification": output.classification,
            "severity": output.severity,
            "triggered_rule": output.triggered_rule,
            "baseline_version": baseline_version,
            "input_sha256": hash_input_record(obs),
        })

    def log_rejection(self, obs: Any, error: Exception, baseline_version: str) -> None:
        """Append an audit record for an observation rejected by validation."""
        record = input_record(obs)
        self._append({
            "observation_id": record["observation_id"],
            "timestamp": record["timestamp"],
            "classification": "Rejected",
            "severity": None,
            "triggered_rule": "INVALID_INPUT",
            "baseline_version": baseline_version,
            "input_sha256": hash_input_record(obs),
            "rejection_reason": str(error),
        })

"""Offline-only reference readers for evaluation and dashboard scoring."""

from __future__ import annotations

import csv
import re
from pathlib import Path
from typing import Any


_OBSERVATION_ID = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
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


def _sequence(value: str, line_number: int) -> int:
    try:
        result = int(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid sequence_number on row {line_number}") from exc
    if not 1 <= result <= 999_999:
        raise ValueError(f"invalid sequence_number on row {line_number}")
    return result


def load_ground_truth(path: str | Path) -> dict[str, dict[str, str]]:
    """Load reference rows by observation ID for offline scoring only."""
    source = Path(path)
    result: dict[str, dict[str, str]] = {}
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("ground truth CSV has no header")
        missing = sorted(_GROUND_TRUTH_FIELDS - set(reader.fieldnames))
        if missing:
            raise ValueError("ground truth CSV is missing: " + ", ".join(missing))
        for line_number, row in enumerate(reader, start=2):
            if any(value is None for value in row.values()):
                raise ValueError(f"ground truth row {line_number} has missing values")
            observation_id = row["observation_id"].strip()
            if not _OBSERVATION_ID.fullmatch(observation_id):
                raise ValueError(f"invalid observation_id on row {line_number}")
            if observation_id in result:
                raise ValueError(
                    f"duplicate ground truth observation_id: {observation_id}"
                )
            _sequence(row["sequence_number"], line_number)
            result[observation_id] = dict(row)
    return result


def load_module1_flags_reference(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load upstream flags for offline agreement reporting only."""
    source = Path(path)
    result: dict[str, dict[str, Any]] = {}
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames is None:
            raise ValueError("Module 1 reference CSV has no header")
        missing = sorted(_MODULE1_REFERENCE_FIELDS - set(reader.fieldnames))
        if missing:
            raise ValueError("Module 1 reference CSV is missing: " + ", ".join(missing))
        for line_number, row in enumerate(reader, start=2):
            observation_id = row["observation_id"].strip()
            if not _OBSERVATION_ID.fullmatch(observation_id):
                raise ValueError(f"invalid observation_id on row {line_number}")
            if observation_id in result:
                raise ValueError(f"duplicate observation_id: {observation_id}")
            parsed: dict[str, Any] = {
                "sequence_number": _sequence(row["sequence_number"], line_number),
                "channel": row["channel"].strip(),
            }
            for field in ("interference", "signal_present", "power_anomaly"):
                value = _sequence(row[field], line_number) if row[field] != "0" else 0
                if value not in (0, 1):
                    raise ValueError(f"{field} must be 0 or 1 on row {line_number}")
                parsed[field] = value
            result[observation_id] = parsed
    return result

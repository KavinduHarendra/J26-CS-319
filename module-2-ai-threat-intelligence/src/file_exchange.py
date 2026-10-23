"""Safe filesystem helpers for the Module 1/2/3/4 JSON exchange demo."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any

from pydantic import BaseModel


PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_EXCHANGE_ROOT = PROJECT_ROOT / "data" / "exchange"
INBOX_RELATIVE = Path("module1_to_module2")
PROCESSED_RELATIVE = INBOX_RELATIVE / "processed"
REJECTED_RELATIVE = INBOX_RELATIVE / "rejected"
MODULE3_RELATIVE = Path("module2_to_module3")
MODULE4_RELATIVE = Path("module2_to_module4")

_UNSAFE_ID_CHARACTERS = re.compile(r"[^A-Za-z0-9_-]")


def exchange_paths(root: str | Path = DEFAULT_EXCHANGE_ROOT) -> dict[str, Path]:
    """Return every exchange folder from a configurable root."""
    base = Path(root)
    return {
        "root": base,
        "inbox": base / INBOX_RELATIVE,
        "processed": base / PROCESSED_RELATIVE,
        "rejected": base / REJECTED_RELATIVE,
        "module3": base / MODULE3_RELATIVE,
        "module3_received": base / MODULE3_RELATIVE / "received",
        "module4": base / MODULE4_RELATIVE,
        "module4_received": base / MODULE4_RELATIVE / "received",
    }


def ensure_exchange_folders(root: str | Path = DEFAULT_EXCHANGE_ROOT) -> dict[str, Path]:
    """Create the exchange folders and return their paths."""
    paths = exchange_paths(root)
    for name, folder in paths.items():
        if name != "root":
            folder.mkdir(parents=True, exist_ok=True)
    return paths


def sanitize_observation_id(observation_id: str) -> str:
    """Return a filename-safe ID containing only ASCII letters, digits, `_`, and `-`."""
    safe = _UNSAFE_ID_CHARACTERS.sub("_", observation_id)[:64]
    return safe or "observation"


def exchange_filename(
    sequence_number: int,
    observation_id: str,
    *,
    threat: bool = False,
) -> str:
    """Build a name only from a validated sequence and sanitized observation ID."""
    if isinstance(sequence_number, bool) or not 0 <= sequence_number <= 999_999:
        raise ValueError("sequence_number must be between 0 and 999999")
    safe_id = sanitize_observation_id(observation_id)
    suffix = "_threat.json" if threat else ".json"
    return f"{sequence_number:06d}_{safe_id}{suffix}"


def write_json_atomic(path: str | Path, obj: BaseModel | Any) -> Path:
    """Write JSON through a same-folder `.tmp` file and atomically replace the target."""
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    temporary = destination.with_name(destination.name + ".tmp")
    payload = obj.model_dump(mode="json") if isinstance(obj, BaseModel) else obj
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        allow_nan=False,
        indent=2,
        sort_keys=True,
    ) + "\n"

    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(serialized)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, destination)
    except Exception:
        temporary.unlink(missing_ok=True)
        raise
    return destination

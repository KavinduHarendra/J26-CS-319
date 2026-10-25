"""Atomic per-capture JSON output for Modules 3 and 4."""

from __future__ import annotations

from collections import Counter
from pathlib import Path
import time
from typing import Any

from src.classifier import ThreatOutput
from src.contracts import to_contract
from src.file_exchange import exchange_filename, write_json_atomic
from src.real_data import Signal


DEFAULT_OUTPUT_ROOT = Path(__file__).resolve().parents[1] / "data" / "json_out"


class CaptureOutputWriter:
    def __init__(self, root: str | Path = DEFAULT_OUTPUT_ROOT, *, keep: bool = False) -> None:
        self.root = Path(root)
        self.destinations = {
            "module3": self.root / "module2_to_module3",
            "module4": self.root / "module2_to_module4",
        }
        for destination in self.destinations.values():
            destination.mkdir(parents=True, exist_ok=True)
            if not keep:
                for pattern in ("*.json", "*.tmp"):
                    for path in destination.glob(pattern):
                        if path.is_file() and not path.is_symlink():
                            path.unlink()
        self._seen_sequences: set[int] = set()
        self._highest_sequence: int | None = None
        self._missing_sequences: set[int] = set()
        self._received = 0
        self._duplicates = 0
        self._class_counts: Counter[str] = Counter()
        self._files_written: Counter[str] = Counter()
        self._last_file_name: dict[str, str | None] = {
            recipient: None for recipient in self.destinations
        }
        self._last_write_time: dict[str, float | None] = {
            recipient: None for recipient in self.destinations
        }

    def _record_sequence(self, sequence_number: int) -> None:
        if self._highest_sequence is None:
            if sequence_number > 1:
                self._missing_sequences.update(range(1, sequence_number))
            self._highest_sequence = sequence_number
        elif sequence_number > self._highest_sequence:
            self._missing_sequences.update(range(self._highest_sequence + 1, sequence_number))
            self._highest_sequence = sequence_number
        self._missing_sequences.discard(sequence_number)

    def write(self, signal: Signal, output: ThreatOutput) -> bool:
        if not isinstance(signal, Signal):
            raise TypeError("writer requires a validated Signal")
        if signal.sequence_number != output.sequence_number:
            raise ValueError("signal and output sequence numbers differ")
        if signal.observation_id != output.observation_id:
            raise ValueError("signal and output observation IDs differ")

        self._received += 1
        if signal.sequence_number in self._seen_sequences:
            self._duplicates += 1
            return False

        name = exchange_filename(signal.sequence_number, signal.observation_id, threat=True)
        for recipient, destination in self.destinations.items():
            path = destination / name
            if not path.exists():
                write_json_atomic(path, to_contract(output, recipient=recipient))
                self._files_written[recipient] += 1
                self._last_file_name[recipient] = name
                self._last_write_time[recipient] = time.monotonic()

        self._seen_sequences.add(signal.sequence_number)
        self._record_sequence(signal.sequence_number)
        self._class_counts[output.classification] += 1
        return True

    def stats(self) -> dict[str, Any]:
        return {
            "received": self._received,
            "class_counts": dict(self._class_counts),
            "missing_sequence_numbers": sorted(self._missing_sequences),
            "duplicates": self._duplicates,
            "files_written": dict(self._files_written),
            "last_file_name": dict(self._last_file_name),
            "last_write_time": dict(self._last_write_time),
        }

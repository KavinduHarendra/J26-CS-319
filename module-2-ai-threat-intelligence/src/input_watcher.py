"""Polling input for the flat Module 1 JSON inbox."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import time

from src.real_data import Signal, load_signal


DEFAULT_INPUT_ROOT = Path(__file__).resolve().parents[1] / "data" / "module1_input"
MAX_INPUT_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class RejectedInput:
    file_name: str
    reason: str


@dataclass(frozen=True, slots=True)
class InboxBatch:
    signals: tuple[Signal, ...]
    rejected: tuple[RejectedInput, ...]
    duplicates: tuple[str, ...]


class SignalInbox:
    """Watch one flat directory and return each completed JSON capture once."""

    def __init__(
        self,
        root: str | Path = DEFAULT_INPUT_ROOT,
        *,
        settle_seconds: float = 0.05,
        max_bytes: int = MAX_INPUT_BYTES,
    ) -> None:
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.settle_seconds = settle_seconds
        self.max_bytes = max_bytes
        self._pending: dict[str, tuple[int, int, float]] = {}
        self._handled_names: set[str] = set()
        self._seen_sequences: set[int] = set()

    def poll(self) -> InboxBatch:
        """Return newly completed files in sequence order.

        A file must keep the same size and modification time for one settling
        interval before it is opened. Producers should still publish with an
        atomic rename when possible. Only direct ``*.json`` children are read.
        """
        now = time.monotonic()
        ready: list[Signal] = []
        rejected: list[RejectedInput] = []
        duplicates: list[str] = []

        for path in sorted(self.root.glob("*.json"), key=lambda item: item.name):
            name = path.name
            if name in self._handled_names:
                continue
            if path.is_symlink():
                self._handled_names.add(name)
                rejected.append(RejectedInput(name, "symbolic links are not accepted"))
                continue
            try:
                stat = path.stat()
            except OSError as exc:
                rejected.append(RejectedInput(name, f"cannot inspect file: {exc}"))
                continue
            if not path.is_file():
                continue
            if stat.st_size > self.max_bytes:
                self._handled_names.add(name)
                rejected.append(
                    RejectedInput(name, f"file exceeds {self.max_bytes} byte limit")
                )
                continue

            fingerprint = (stat.st_size, stat.st_mtime_ns)
            pending = self._pending.get(name)
            if self.settle_seconds > 0 and (
                pending is None or pending[:2] != fingerprint
            ):
                self._pending[name] = (*fingerprint, now)
                continue
            if (
                self.settle_seconds > 0
                and pending is not None
                and now - pending[2] < self.settle_seconds
            ):
                continue

            self._pending.pop(name, None)
            self._handled_names.add(name)
            try:
                signal = load_signal(path)
            except (OSError, ValueError) as exc:
                rejected.append(RejectedInput(name, str(exc)))
                continue
            if signal.sequence_number in self._seen_sequences:
                duplicates.append(name)
                continue
            self._seen_sequences.add(signal.sequence_number)
            ready.append(signal)

        ready.sort(key=lambda signal: (signal.sequence_number, signal.observation_id))
        return InboxBatch(tuple(ready), tuple(rejected), tuple(duplicates))

    @property
    def handled_count(self) -> int:
        return len(self._handled_names)

"""Module 2 processor for real Module 1 JSON exchange files."""

from __future__ import annotations

import argparse
import math
import os
import re
import threading
import time
from collections import Counter
from pathlib import Path
from typing import Any

from src.contracts import to_contract
from src.file_exchange import (
    DEFAULT_EXCHANGE_ROOT,
    ensure_exchange_folders,
    exchange_filename,
    write_json_atomic,
)
from src.real_classifier import RealThreatClassifierV2
from src.real_data import RealSignal, load_signal
from src.real_detection import build_frozen_detector_v2


MAX_INPUT_BYTES = 64 * 1024
POLL_SECONDS = 0.1
_SEQUENCE_PREFIX = re.compile(r"^(\d{6})_")


def build_file_pipeline() -> RealThreatClassifierV2:
    """Build the frozen v2 pipeline without reading scoring information."""
    return RealThreatClassifierV2(build_frozen_detector_v2())


class FileProcessor:
    """Validate, classify, route, and archive real Module 1 capture files."""

    def __init__(
        self,
        exchange_root: str | Path = DEFAULT_EXCHANGE_ROOT,
        *,
        module: RealThreatClassifierV2 | None = None,
    ) -> None:
        self.paths = ensure_exchange_folders(exchange_root)
        self.module = module or build_file_pipeline()
        self._lock = threading.Lock()
        self._seen_sequences: set[int] = set()
        self._missing_sequences: set[int] = set()
        self._highest_sequence: int | None = None
        self._received = 0
        self._rejected = 0
        self._duplicates = 0
        self._class_counts: Counter[str] = Counter()
        self._processing_times: list[float] = []
        self._load_processed_sequences()

    @staticmethod
    def _sort_key(path: Path) -> tuple[int, str]:
        match = _SEQUENCE_PREFIX.match(path.name)
        return (int(match.group(1)) if match else 1_000_000, path.name)

    def _load_processed_sequences(self) -> None:
        for path in self.paths["processed"].glob("*.json"):
            if path.is_symlink():
                continue
            try:
                signal = load_signal(path)
            except (OSError, ValueError):
                continue
            self._seen_sequences.add(signal.sequence_number)
        if self._seen_sequences:
            self._highest_sequence = max(self._seen_sequences)

    def _record_sequence(self, sequence_number: int) -> None:
        if self._highest_sequence is None:
            if sequence_number > 1:
                self._missing_sequences.update(range(1, sequence_number))
            self._highest_sequence = sequence_number
        elif sequence_number > self._highest_sequence:
            self._missing_sequences.update(range(self._highest_sequence + 1, sequence_number))
            self._highest_sequence = sequence_number
        self._missing_sequences.discard(sequence_number)

    @staticmethod
    def _move_unique(source: Path, folder: Path, marker: str = "duplicate") -> Path:
        folder.mkdir(parents=True, exist_ok=True)
        destination = folder / source.name
        if destination.exists():
            counter = 1
            while True:
                candidate = folder / f"{source.stem}.{marker}-{counter}{source.suffix}"
                if not candidate.exists():
                    destination = candidate
                    break
                counter += 1
        os.replace(source, destination)
        return destination

    def _reject(self, source: Path, reason: str) -> None:
        destination = self._move_unique(source, self.paths["rejected"], marker="rejected")
        destination.with_name(destination.name + ".reason.txt").write_text(
            reason.rstrip() + "\n", encoding="utf-8"
        )
        with self._lock:
            self._rejected += 1

    def _write_outputs(self, signal: RealSignal, output: Any, processing_ms: float) -> None:
        output_name = exchange_filename(
            signal.sequence_number, signal.observation_id, threat=True
        )
        for recipient in ("module3", "module4"):
            destination = self.paths[recipient] / output_name
            if destination.exists():
                continue
            write_json_atomic(
                destination,
                to_contract(
                    output,
                    sequence_number=signal.sequence_number,
                    baseline_version=self.module.detector.baseline.version,
                    processing_ms=processing_ms,
                    recipient=recipient,
                ),
            )

    def process_file(self, source: Path) -> bool:
        if source.is_symlink() or source.suffix != ".json" or source.name.endswith(".tmp"):
            return False
        with self._lock:
            self._received += 1
        try:
            if source.stat().st_size > MAX_INPUT_BYTES:
                self._reject(source, f"Input exceeds {MAX_INPUT_BYTES} byte limit")
                return True
            signal = load_signal(source)
        except (OSError, ValueError) as exc:
            self._reject(source, f"Invalid input: {exc}")
            return True

        with self._lock:
            duplicate = signal.sequence_number in self._seen_sequences
            if duplicate:
                self._duplicates += 1
        if duplicate:
            self._move_unique(source, self.paths["processed"])
            return True

        started = time.perf_counter()
        output = self.module.classify(signal)
        processing_ms = (time.perf_counter() - started) * 1000.0
        self._write_outputs(signal, output, processing_ms)
        self._move_unique(source, self.paths["processed"])
        with self._lock:
            self._seen_sequences.add(signal.sequence_number)
            self._record_sequence(signal.sequence_number)
            self._class_counts[output.classification] += 1
            self._processing_times.append(processing_ms)
        return True

    def process_pending(self) -> int:
        candidates = sorted(self.paths["inbox"].glob("*.json"), key=self._sort_key)
        return sum(self.process_file(source) for source in candidates)

    def stats_snapshot(self) -> dict[str, Any]:
        with self._lock:
            timings = sorted(self._processing_times)
            count = len(timings)
            p95_index = max(0, math.ceil(count * 0.95) - 1)
            return {
                "received": self._received,
                "class_counts": dict(self._class_counts),
                "rejected": self._rejected,
                "missed_sequence_numbers": sorted(self._missing_sequences),
                "duplicates": self._duplicates,
                "mean_processing_ms": sum(timings) / count if count else 0.0,
                "p95_processing_ms": timings[p95_index] if timings else 0.0,
            }

    def run(self, stop_event: threading.Event, poll_seconds: float = POLL_SECONDS) -> None:
        while not stop_event.is_set():
            self.process_pending()
            stop_event.wait(poll_seconds)
        self.process_pending()


def main() -> None:
    parser = argparse.ArgumentParser(description="Module 2 real-signal file processor")
    parser.add_argument("--exchange-root", type=Path, default=DEFAULT_EXCHANGE_ROOT)
    args = parser.parse_args()
    processor = FileProcessor(args.exchange_root)
    stop_event = threading.Event()
    print("Module 2 file processor running. Press Ctrl+C to stop.")
    try:
        processor.run(stop_event)
    except KeyboardInterrupt:
        stop_event.set()
    finally:
        print(processor.stats_snapshot())


if __name__ == "__main__":
    main()

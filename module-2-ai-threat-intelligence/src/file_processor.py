"""Module 2 processor for the local file-based JSON exchange."""

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

from pydantic import ValidationError

from src.anomaly_engine import StatisticalAnomalyEngine
from src.baseline import NormalBaseline
from src.classifier import ThreatIntelligenceModule
from src.contracts import ObservationIn, to_contract
from src.data_source import SyntheticDataSource
from src.file_exchange import (
    DEFAULT_EXCHANGE_ROOT,
    ensure_exchange_folders,
    exchange_filename,
    write_json_atomic,
)
from src.rule_engine import build_default_ruleset
from src.schema import RFObservation


MAX_INPUT_BYTES = 64 * 1024
POLL_SECONDS = 0.1
CALIBRATION_SAMPLES = 200
CALIBRATION_SPLIT = 0.70
_SEQUENCE_PREFIX = re.compile(r"^(\d{6})_")


def build_file_pipeline(
    *,
    seed: int = 42,
    audit_log_path: str | Path | None = None,
) -> ThreatIntelligenceModule:
    """Calibrate once and assemble the unchanged Module 2 detection pipeline."""
    normal = SyntheticDataSource("normal", seed=seed).fetch_batch(CALIBRATION_SAMPLES)
    baseline = NormalBaseline()
    baseline.add_normal_samples(normal[: int(CALIBRATION_SAMPLES * CALIBRATION_SPLIT)])
    baseline.calibrate()
    kwargs: dict[str, Any] = {}
    if audit_log_path is not None:
        kwargs["audit_log_path"] = audit_log_path
    return ThreatIntelligenceModule(
        baseline,
        build_default_ruleset(),
        StatisticalAnomalyEngine(z_threshold=3.0),
        **kwargs,
    )


class FileProcessor:
    """Validate, classify, route, and archive Module 1 capture files."""

    def __init__(
        self,
        exchange_root: str | Path = DEFAULT_EXCHANGE_ROOT,
        *,
        module: ThreatIntelligenceModule | None = None,
        seed: int = 42,
    ):
        self.paths = ensure_exchange_folders(exchange_root)
        self.module = module or build_file_pipeline(
            seed=seed,
            audit_log_path=self.paths["root"] / "module2_audit_log.jsonl",
        )
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
        """Remember prior sequences so a restart cannot emit duplicate outputs."""
        for path in self.paths["processed"].glob("*.json"):
            if path.is_symlink():
                continue
            try:
                contract = ObservationIn.model_validate_json(path.read_bytes())
            except (OSError, ValidationError, ValueError):
                continue
            self._seen_sequences.add(contract.sequence_number)
        if self._seen_sequences:
            self._highest_sequence = max(self._seen_sequences)

    def _record_sequence(self, sequence_number: int) -> None:
        if self._highest_sequence is None:
            if sequence_number > 1:
                self._missing_sequences.update(range(1, sequence_number))
            self._highest_sequence = sequence_number
        elif sequence_number > self._highest_sequence:
            self._missing_sequences.update(
                range(self._highest_sequence + 1, sequence_number)
            )
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
        reason_path = destination.with_name(destination.name + ".reason.txt")
        reason_path.write_text(reason.rstrip() + "\n", encoding="utf-8")
        with self._lock:
            self._rejected += 1

    def _write_outputs(self, contract: ObservationIn, output: Any, processing_ms: float) -> None:
        output_name = exchange_filename(
            contract.sequence_number,
            contract.observation_id,
            threat=True,
        )
        destinations = (
            ("module3", self.paths["module3"] / output_name),
            ("module4", self.paths["module4"] / output_name),
        )
        for recipient, destination in destinations:
            if destination.exists():
                continue
            payload = to_contract(
                output,
                sequence_number=contract.sequence_number,
                baseline_version=self.module.baseline.version,
                processing_ms=processing_ms,
                recipient=recipient,
            )
            write_json_atomic(destination, payload)

    def process_file(self, source: Path) -> bool:
        """Process one inbox file. Return True when it was consumed."""
        if source.is_symlink() or source.suffix != ".json" or source.name.endswith(".tmp"):
            return False

        with self._lock:
            self._received += 1

        try:
            if source.stat().st_size > MAX_INPUT_BYTES:
                self._reject(source, f"Input exceeds {MAX_INPUT_BYTES} byte limit")
                return True
            raw = source.read_bytes()
            contract = ObservationIn.model_validate_json(raw)
        except (OSError, ValidationError, ValueError) as exc:
            self._reject(source, f"Invalid input: {exc}")
            return True

        with self._lock:
            if contract.sequence_number in self._seen_sequences:
                self._duplicates += 1
                duplicate = True
            else:
                duplicate = False

        if duplicate:
            self._move_unique(source, self.paths["processed"])
            return True

        observation = RFObservation(
            observation_id=contract.observation_id,
            timestamp=contract.timestamp,
            rssi=contract.rssi,
            snr=contract.snr,
            noise_floor=contract.noise_floor,
            packet_rate=contract.packet_rate,
        )
        started = time.perf_counter()
        output = self.module.classify(observation)
        processing_ms = (time.perf_counter() - started) * 1000.0
        self._write_outputs(contract, output, processing_ms)
        self._move_unique(source, self.paths["processed"])

        with self._lock:
            self._seen_sequences.add(contract.sequence_number)
            self._record_sequence(contract.sequence_number)
            self._class_counts[output.classification] += 1
            self._processing_times.append(processing_ms)
        return True

    def process_pending(self) -> int:
        """Consume all complete JSON files currently present in sequence order."""
        candidates = sorted(self.paths["inbox"].glob("*.json"), key=self._sort_key)
        consumed = 0
        for source in candidates:
            if self.process_file(source):
                consumed += 1
        return consumed

    def stats_snapshot(self) -> dict[str, Any]:
        """Return a thread-safe processor statistics snapshot."""
        with self._lock:
            timings = sorted(self._processing_times)
            count = len(timings)
            mean_ms = sum(timings) / count if count else 0.0
            p95_index = max(0, math.ceil(count * 0.95) - 1)
            p95_ms = timings[p95_index] if timings else 0.0
            return {
                "received": self._received,
                "class_counts": dict(self._class_counts),
                "rejected": self._rejected,
                "missed_sequence_numbers": sorted(self._missing_sequences),
                "duplicates": self._duplicates,
                "mean_processing_ms": mean_ms,
                "p95_processing_ms": p95_ms,
            }

    def run(self, stop_event: threading.Event, poll_seconds: float = POLL_SECONDS) -> None:
        """Poll until ``stop_event`` is set, then make one final pass."""
        while not stop_event.is_set():
            self.process_pending()
            stop_event.wait(poll_seconds)
        self.process_pending()


def main() -> None:
    parser = argparse.ArgumentParser(description="Module 2 local JSON file processor")
    parser.add_argument("--exchange-root", type=Path, default=DEFAULT_EXCHANGE_ROOT)
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    processor = FileProcessor(args.exchange_root, seed=args.seed)
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

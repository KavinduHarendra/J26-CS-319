"""MOCK Module 1 producer for the local JSON file exchange."""

from __future__ import annotations

import argparse
import sys
import threading
import time
from collections.abc import Callable, Iterator
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.contracts import MODULE1_SOURCE, SCHEMA_VERSION, ObservationIn
from src.data_source import SyntheticDataSource
from src.file_exchange import (
    DEFAULT_EXCHANGE_ROOT,
    ensure_exchange_folders,
    exchange_filename,
    write_json_atomic,
)


SCRIPTED_SCHEDULE = (
    ("normal", 40),
    ("jamming", 30),
    ("normal", 20),
    ("unknown_anomaly", 30),
    ("normal", 30),
)


def scenario_stream(*, repeat: bool) -> Iterator[str]:
    """Yield the required scripted scenario schedule."""
    while True:
        for scenario, count in SCRIPTED_SCHEDULE:
            yield from (scenario for _ in range(count))
        if not repeat:
            return


def run_mock_module1(
    *,
    exchange_root: str | Path = DEFAULT_EXCHANGE_ROOT,
    rate: float = 5.0,
    count: int = 150,
    loop: bool = False,
    seed: int = 42,
    stop_event: threading.Event | None = None,
    done_event: threading.Event | None = None,
    on_write: Callable[[Path, ObservationIn, str], None] | None = None,
    quiet: bool = False,
) -> int:
    """Write one validated capture file at the configured rate."""
    if rate <= 0:
        raise ValueError("rate must be greater than zero")
    if count < 0:
        raise ValueError("count must be zero (forever) or a positive integer")

    paths = ensure_exchange_folders(exchange_root)
    stopper = stop_event or threading.Event()
    finished = done_event or threading.Event()
    repeat = loop or count == 0
    sources = {
        "normal": SyntheticDataSource("normal", seed=seed, start_id=0),
        "jamming": SyntheticDataSource("jamming", seed=seed + 100, start_id=1000),
        "unknown_anomaly": SyntheticDataSource(
            "unknown_anomaly", seed=seed + 200, start_id=2000
        ),
    }
    interval = 1.0 / rate
    written = 0
    next_write = time.monotonic()

    try:
        for scenario in scenario_stream(repeat=repeat):
            if stopper.is_set() or (count and written >= count):
                break
            sequence_number = written + 1
            if sequence_number > 999_999:
                raise RuntimeError("six-digit sequence number limit reached")

            obs = sources[scenario].fetch_batch(1)[0]
            contract = ObservationIn(
                schema_version=SCHEMA_VERSION,
                source_module=MODULE1_SOURCE,
                sequence_number=sequence_number,
                observation_id=obs.observation_id,
                timestamp=obs.timestamp,
                rssi=float(obs.rssi),
                snr=float(obs.snr),
                noise_floor=float(obs.noise_floor),
                packet_rate=float(obs.packet_rate),
            )
            filename = exchange_filename(sequence_number, obs.observation_id)
            destination = write_json_atomic(paths["inbox"] / filename, contract)
            written += 1
            if not quiet:
                print(f"[MOCK Module 1] wrote {destination.name} ({scenario})")
            if on_write is not None:
                on_write(destination, contract, scenario)

            next_write += interval
            stopper.wait(max(0.0, next_write - time.monotonic()))
    finally:
        finished.set()
    return written


def main() -> None:
    parser = argparse.ArgumentParser(description="MOCK Module 1 file producer")
    parser.add_argument("--exchange-root", type=Path, default=DEFAULT_EXCHANGE_ROOT)
    parser.add_argument("--rate", type=float, default=5.0, help="captures per second")
    parser.add_argument("--count", type=int, default=150, help="0 runs until Ctrl+C")
    parser.add_argument("--loop", action="store_true", help="repeat the scripted schedule")
    parser.add_argument("--seed", type=int, default=42)
    args = parser.parse_args()

    stop_event = threading.Event()
    print("[MOCK Module 1] local file producer started. Press Ctrl+C to stop.")
    try:
        run_mock_module1(
            exchange_root=args.exchange_root,
            rate=args.rate,
            count=args.count,
            loop=args.loop,
            seed=args.seed,
            stop_event=stop_event,
        )
    except KeyboardInterrupt:
        stop_event.set()
    print("[MOCK Module 1] stopped.")


if __name__ == "__main__":
    main()

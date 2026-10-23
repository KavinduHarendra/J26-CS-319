"""MOCK Module 3/4 receivers for the local JSON file exchange."""

from __future__ import annotations

import argparse
import os
import sys
import threading
from collections.abc import Callable
from pathlib import Path
from typing import Literal

from pydantic import ValidationError

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.contracts import ThreatStateOut
from src.file_exchange import DEFAULT_EXCHANGE_ROOT, ensure_exchange_folders


MODULE3_DECISIONS = {
    "NORMAL": "SECURE_OK",
    "UNKNOWN_ANOMALY": "DEGRADED",
    "JAMMING": "UNDER_ATTACK",
}
MODULE4_DECISIONS = {
    "NORMAL": "NO_ACTION",
    "UNKNOWN_ANOMALY": "INCREASE_MONITORING",
    "JAMMING": "SWITCH_CHANNEL_SIMULATED",
}


class MockFileReceiver:
    """Watch one recipient folder, validate outputs, and archive received files."""

    def __init__(
        self,
        module: Literal[3, 4],
        exchange_root: str | Path = DEFAULT_EXCHANGE_ROOT,
        *,
        quiet: bool = False,
        on_receive: Callable[[Path, ThreatStateOut, str], None] | None = None,
    ):
        if module not in (3, 4):
            raise ValueError("module must be 3 or 4")
        self.module = module
        self.paths = ensure_exchange_folders(exchange_root)
        self.folder = self.paths[f"module{module}"]
        self.received_folder = self.paths[f"module{module}_received"]
        self.quiet = quiet
        self.on_receive = on_receive
        self.received_count = 0
        self.latest_decision: str | None = None

    def _move_unique(self, source: Path) -> Path:
        destination = self.received_folder / source.name
        if destination.exists():
            counter = 1
            while True:
                candidate = self.received_folder / (
                    f"{source.stem}.duplicate-{counter}{source.suffix}"
                )
                if not candidate.exists():
                    destination = candidate
                    break
                counter += 1
        os.replace(source, destination)
        return destination

    def process_pending(self) -> int:
        processed = 0
        expected_recipient = f"module{self.module}"
        decisions = MODULE3_DECISIONS if self.module == 3 else MODULE4_DECISIONS
        for source in sorted(self.folder.glob("*.json")):
            if source.is_symlink() or source.name.endswith(".tmp"):
                continue
            try:
                payload = ThreatStateOut.model_validate_json(source.read_bytes())
                if payload.recipient != expected_recipient:
                    raise ValueError(
                        f"recipient is {payload.recipient}, expected {expected_recipient}"
                    )
            except (OSError, ValidationError, ValueError) as exc:
                if not self.quiet:
                    print(f"[MOCK Module {self.module}] rejected {source.name}: {exc}")
                continue

            decision = decisions[payload.classification]
            destination = self._move_unique(source)
            self.received_count += 1
            self.latest_decision = decision
            processed += 1
            if not self.quiet:
                print(
                    f"[MOCK Module {self.module}] received {destination.name}; "
                    f"MOCK decision={decision}"
                )
            if self.on_receive is not None:
                self.on_receive(destination, payload, decision)
        return processed

    def run(self, stop_event: threading.Event, poll_seconds: float = 0.1) -> None:
        while not stop_event.is_set():
            self.process_pending()
            stop_event.wait(poll_seconds)
        self.process_pending()


def main() -> None:
    parser = argparse.ArgumentParser(description="MOCK file receiver for Module 3 or 4")
    parser.add_argument("--module", type=int, choices=(3, 4), required=True)
    parser.add_argument("--exchange-root", type=Path, default=DEFAULT_EXCHANGE_ROOT)
    args = parser.parse_args()

    receiver = MockFileReceiver(args.module, args.exchange_root)
    stop_event = threading.Event()
    print(f"[MOCK Module {args.module}] receiver started. Press Ctrl+C to stop.")
    try:
        receiver.run(stop_event)
    except KeyboardInterrupt:
        stop_event.set()
    print(f"[MOCK Module {args.module}] stopped after {receiver.received_count} files.")


if __name__ == "__main__":
    main()

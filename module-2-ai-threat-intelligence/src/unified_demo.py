"""Unified one-window demonstration for the file-based module integration."""

from __future__ import annotations

import argparse
import os
import shutil
import threading
import time
from collections import deque
from pathlib import Path
from typing import Any, Callable

from integration.file_mock_module1 import run_mock_module1
from integration.file_mock_receiver import MockFileReceiver
from src.contracts import ObservationIn, ThreatStateOut
from src.file_exchange import DEFAULT_EXCHANGE_ROOT, ensure_exchange_folders, exchange_paths
from src.file_processor import FileProcessor


CLASS_COLOURS = {
    "NORMAL": "green",
    "JAMMING": "bold red",
    "UNKNOWN_ANOMALY": "yellow",
}


class DemoInstanceLock:
    """Prevent multiple dashboards from consuming the same exchange folders."""

    def __init__(self, path: Path) -> None:
        self.path = path
        self._handle: Any = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._handle = self.path.open("a+b")
        if self.path.stat().st_size == 0:
            self._handle.write(b"0")
            self._handle.flush()
        self._handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except (OSError, BlockingIOError) as exc:
            self._handle.close()
            self._handle = None
            raise RuntimeError(
                "another dashboard is already running; close it with Ctrl+C first"
            ) from exc

    def release(self) -> None:
        if self._handle is None:
            return
        try:
            self._handle.seek(0)
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(self._handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl

                fcntl.flock(self._handle.fileno(), fcntl.LOCK_UN)
        finally:
            self._handle.close()
            self._handle = None


class DemoState:
    """Thread-safe dashboard state populated by the four module workers."""

    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.inputs: dict[int, dict[str, Any]] = {}
        self.latest_input: dict[str, Any] | None = None
        self.latest_output: dict[str, Any] | None = None
        self.scenarios: dict[int, str] = {}
        self.captures: deque[dict[str, Any]] = deque(maxlen=12)
        self.decisions: dict[int, str] = {}
        self.errors: list[str] = []
        self.sent_count = 0

    def input_written(self, _path: Path, payload: ObservationIn, scenario: str) -> None:
        dumped = payload.model_dump(mode="json")
        with self.lock:
            self.latest_input = dumped
            self.inputs[payload.sequence_number] = dumped
            self.scenarios[payload.sequence_number] = scenario
            self.sent_count += 1

    def output_received(self, module: int, payload: ThreatStateOut, decision: str) -> None:
        with self.lock:
            self.decisions[module] = decision
            if module != 3:
                return
            dumped = payload.model_dump(mode="json")
            source = self.inputs.get(payload.sequence_number, {})
            self.latest_output = dumped
            self.captures.append(
                {
                    "sequence": payload.sequence_number,
                    "observation_id": payload.observation_id,
                    "scenario": self.scenarios.get(payload.sequence_number, "unknown"),
                    "classification": payload.classification,
                    "severity": payload.severity,
                    "rule": payload.triggered_rule,
                    "processing_ms": payload.processing_ms,
                    "rssi": source.get("rssi"),
                    "snr": source.get("snr"),
                    "noise_floor": source.get("noise_floor"),
                    "packet_rate": source.get("packet_rate"),
                    "evidence": payload.evidence,
                    "deviation": payload.statistical_deviation,
                }
            )

    def add_error(self, message: str) -> None:
        with self.lock:
            self.errors.append(message)

    def snapshot(self) -> dict[str, Any]:
        with self.lock:
            return {
                "latest_input": self.latest_input,
                "latest_output": self.latest_output,
                "captures": list(self.captures),
                "decisions": dict(self.decisions),
                "errors": list(self.errors),
                "sent_count": self.sent_count,
            }


def folder_counts(root: str | Path = DEFAULT_EXCHANGE_ROOT) -> dict[str, int]:
    """Return the live queue/archive counts used by the dashboard."""
    paths = exchange_paths(root)
    return {
        "Inbox": len(list(paths["inbox"].glob("*.json"))),
        "Processed": len(list(paths["processed"].glob("*.json"))),
        "Rejected": len(list(paths["rejected"].glob("*.json"))),
        "M3 queue": len(list(paths["module3"].glob("*.json"))),
        "M3 received": len(list(paths["module3_received"].glob("*.json"))),
        "M4 queue": len(list(paths["module4"].glob("*.json"))),
        "M4 received": len(list(paths["module4_received"].glob("*.json"))),
    }


def _metric(value: Any, unit: str = "") -> str:
    return "-" if value is None else f"{float(value):.2f}{unit}"


def _latest_panel(snapshot: dict[str, Any], *, compact: bool = False):
    from rich.panel import Panel
    from rich.text import Text

    rows = snapshot["captures"]
    if not rows:
        return Panel(
            "[dim]Waiting for the first validated classification...[/]",
            title="Latest detection",
            border_style="blue",
        )

    row = rows[-1]
    classification = row["classification"]
    colour = CLASS_COLOURS.get(classification, "white")
    evidence = row["evidence"] or []
    evidence_text = "\n".join(f"  - {item}" for item in evidence[:3]) or "  - No threat evidence"
    deviations = row["deviation"] or {}
    deviation_text = "  ".join(
        f"{name}={float(value):+.2f}z" for name, value in deviations.items()
    ) or "none"
    if compact:
        first_evidence = evidence[0] if evidence else "No threat evidence"
        content = Text.from_markup(
            f"[{colour}]{classification}[/]  severity={row['severity'] or '-'}\n"
            f"#{row['sequence']:06d}  {row['observation_id']}\n"
            f"[bold]Rule[/] {row['rule'] or '-'}\n"
            f"RSSI {_metric(row['rssi'])}  SNR {_metric(row['snr'])}\n"
            f"Noise {_metric(row['noise_floor'])}  Pkt {_metric(row['packet_rate'])}\n"
            f"[bold]Why[/] {first_evidence}"
        )
    else:
        content = Text.from_markup(
            f"[{colour}]{classification}[/]  severity={row['severity'] or '-'}\n"
            f"[bold]Capture[/]  #{row['sequence']:06d}  {row['observation_id']}\n"
            f"[bold]Rule[/]     {row['rule'] or '-'}\n"
            f"[bold]Signal[/]   RSSI {_metric(row['rssi'], ' dBm')}   "
            f"SNR {_metric(row['snr'], ' dB')}\n"
            f"           Noise {_metric(row['noise_floor'], ' dBm')}   "
            f"Packets {_metric(row['packet_rate'], '/s')}\n"
            f"[bold]Deviation[/] {deviation_text}\n"
            f"[bold]Evidence[/]\n{evidence_text}"
        )
    return Panel(content, title="Latest detection", border_style=colour)


def build_dashboard(
    state: DemoState,
    processor: FileProcessor,
    started: float,
    *,
    compact: bool = False,
    completed: bool = False,
    module1_mock: bool = True,
):
    """Build a clean single-screen view of the complete integration flow."""
    from rich import box
    from rich.align import Align
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    snapshot = state.snapshot()
    stats = processor.stats_snapshot()
    counts = folder_counts(processor.paths["root"])
    class_counts = stats["class_counts"]
    classified = sum(class_counts.values())

    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="pipeline", size=4 if compact else 5),
        Layout(name="body", ratio=3),
        Layout(name="status", size=7 if compact else 9),
        Layout(name="footer", size=1 if compact else 3),
    )

    system_state = "[bold green]COMPLETE[/]" if completed else "[bold cyan]RUNNING[/]"
    if compact:
        heading = "[bold]UAV Cyber Defence - Central Dashboard[/]"
    else:
        simulated_modules = "Modules 1, 3 and 4" if module1_mock else "Modules 3 and 4"
        heading = (
            "[bold]UAV Cyber Defence - Central Threat Intelligence Dashboard[/]   "
            f"[yellow]{simulated_modules} simulated[/]"
        )
    title = Text.from_markup(
        f"{heading}   {system_state}   [dim]{time.monotonic() - started:.1f}s[/]"
    )
    layout["header"].update(
        Panel(Align.center(title), border_style="green" if completed else "cyan")
    )

    pipeline = Table.grid(expand=True)
    pipeline.add_column(ratio=2, justify="center")
    pipeline.add_column(width=3, justify="center")
    pipeline.add_column(ratio=2, justify="center")
    pipeline.add_column(width=3, justify="center")
    pipeline.add_column(ratio=2, justify="center")
    if compact:
        module1_label = "MOCK MODULE 1" if module1_mock else "EXTERNAL MODULE 1"
        module2_label = "THREAT INTELLIGENCE"
        receivers_label = "MOCK MODULES 3 + 4"
    else:
        module1_label = (
            "MODULE 1 - RF INPUT (MOCK)"
            if module1_mock
            else "MODULE 1 - RF INPUT (EXTERNAL)"
        )
        module2_label = "MODULE 2 - THREAT INTELLIGENCE"
        receivers_label = "MODULES 3 + 4 (MOCK)"
    input_count = snapshot["sent_count"] if module1_mock else stats["received"]
    pipeline.add_row(
        f"[yellow bold]{module1_label}[/]\n{input_count} captures",
        "[cyan]=>[/]",
        f"[green bold]{module2_label}[/]\n{classified} classified",
        "[cyan]=>[/]",
        f"[yellow bold]{receivers_label}[/]\n{counts['M3 received']} / {counts['M4 received']} received",
    )
    pipeline_title = "Run complete" if completed else "Live pipeline"
    pipeline_border = "green" if completed else "blue"
    layout["pipeline"].update(
        Panel(pipeline, title=pipeline_title, border_style=pipeline_border)
    )

    layout["body"].split_row(Layout(name="recent", ratio=3), Layout(name="latest", ratio=2))
    recent = Table(box=box.SIMPLE, expand=True, header_style="bold cyan", padding=(0, 1))
    recent.add_column("Seq", justify="right", width=6)
    if compact:
        recent.add_column("Input", width=7)
        recent.add_column("Class", width=8)
    else:
        recent.add_column("Input", max_width=12)
        recent.add_column("Classification", min_width=17)
        recent.add_column("Severity", width=8)
        recent.add_column("Rule", max_width=18)
    recent.add_column("ms", justify="right", width=6 if compact else 7)
    visible_rows = snapshot["captures"][-5:] if compact else snapshot["captures"]
    for row in visible_rows:
        colour = CLASS_COLOURS.get(row["classification"], "white")
        display_class = (
            "UNKNOWN" if compact and row["classification"] == "UNKNOWN_ANOMALY"
            else row["classification"]
        )
        values = [
            f"{row['sequence']:06d}",
            row["scenario"].replace("_", " "),
            f"[{colour}]{display_class}[/]",
        ]
        if not compact:
            values.extend([row["severity"] or "-", row["rule"] or "-"])
        values.append(f"{row['processing_ms']:.3f}")
        recent.add_row(*values)
    layout["recent"].update(Panel(recent, title="Recent captures", border_style="cyan"))
    layout["latest"].update(_latest_panel(snapshot, compact=compact))

    layout["status"].split_row(
        Layout(name="kpis", ratio=2),
        Layout(name="folders", ratio=2),
        Layout(name="receivers", ratio=3 if compact else 2),
    )
    kpis = Table.grid(expand=True)
    kpis.add_column()
    kpis.add_column(justify="right")
    if not compact:
        kpis.add_row("Received", str(stats["received"]))
    kpis.add_row("[green]Normal[/]", str(class_counts.get("Normal", 0)))
    kpis.add_row("[red]Jamming[/]", str(class_counts.get("Jamming", 0)))
    kpis.add_row("[yellow]Unknown[/]", str(class_counts.get("Unknown Anomaly", 0)))
    if compact:
        kpis.add_row("Mean", f"{stats['mean_processing_ms']:.3f} ms")
        kpis.add_row("P95", f"{stats['p95_processing_ms']:.3f} ms")
    else:
        kpis.add_row("Mean / P95", f"{stats['mean_processing_ms']:.3f} / {stats['p95_processing_ms']:.3f} ms")
    kpi_title = "Module 2 Results" if compact else "Threat Intelligence"
    layout["kpis"].update(Panel(kpis, title=kpi_title, border_style="green"))

    folders = Table.grid(expand=True)
    folders.add_column()
    folders.add_column(justify="right")
    if compact:
        folders.add_row("Inbox/done", f"{counts['Inbox']}/{counts['Processed']}")
        folders.add_row("Rejected", str(counts["Rejected"]))
        folders.add_row("M3 q/recv", f"{counts['M3 queue']}/{counts['M3 received']}")
        folders.add_row("M4 q/recv", f"{counts['M4 queue']}/{counts['M4 received']}")
    else:
        for name, count in counts.items():
            folders.add_row(name, str(count))
    layout["folders"].update(
        Panel(folders, title="JSON Exchange", border_style="blue")
    )

    decisions = snapshot["decisions"]
    if compact:
        receiver_text = (
            f"[bold]Module 3[/] {decisions.get(3, 'Waiting...')}\n"
            f"[bold]Module 4[/] {decisions.get(4, 'Waiting...')}\n"
            f"Rejected: {stats['rejected']}   Duplicates: {stats['duplicates']}"
        )
    else:
        receiver_text = (
            f"[bold]Module 3[/]\n{decisions.get(3, 'Waiting...')}\n\n"
            f"[bold]Module 4[/]\n{decisions.get(4, 'Waiting...')}\n\n"
            f"Rejected: {stats['rejected']}  Duplicates: {stats['duplicates']}"
        )
    if snapshot["errors"]:
        receiver_text += f"\n[red]Error: {snapshot['errors'][-1]}[/]"
    layout["receivers"].update(
        Panel(receiver_text, title="Response Components (MOCK)", border_style="yellow")
    )

    if completed:
        footer_text = "[bold green]RUN COMPLETE[/]    Review the dashboard    [bold]Ctrl+C[/] to close"
    elif compact:
        footer_text = "[dim]JSON exchange: data/exchange[/]    [bold]Ctrl+C[/] stop cleanly"
    else:
        footer_text = (
            f"[dim]Exchange: {processor.paths['root']}[/]    "
            "[bold]Ctrl+C[/] stop cleanly"
        )
    footer = Text.from_markup(footer_text)
    if compact:
        layout["footer"].update(Align.center(footer))
    else:
        layout["footer"].update(Panel(Align.center(footer), border_style="cyan"))
    return layout


def print_plain_snapshot(processor: FileProcessor, root: Path) -> None:
    stats = processor.stats_snapshot()
    counts = stats["class_counts"]
    print(
        "[Module 2] "
        f"received={stats['received']} normal={counts.get('Normal', 0)} "
        f"jamming={counts.get('Jamming', 0)} "
        f"unknown={counts.get('Unknown Anomaly', 0)} "
        f"rejected={stats['rejected']} duplicates={stats['duplicates']} "
        f"mean_ms={stats['mean_processing_ms']:.3f} "
        f"p95_ms={stats['p95_processing_ms']:.3f}"
    )
    print("[Folders] " + ", ".join(f"{name}={count}" for name, count in folder_counts(root).items()))


def print_exchange_summary(root: Path) -> None:
    print(f"\nExchange summary: {root}")
    for name, count in folder_counts(root).items():
        print(f"  {name:<12} {count:>5}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Run the unified Module 1 -> 2 -> 3/4 file-exchange demonstration"
    )
    parser.add_argument(
        "--count",
        type=int,
        default=0,
        help="mock captures; default 0 runs continuously until Ctrl+C",
    )
    parser.add_argument("--rate", type=float, help="MOCK Module 1 captures/second")
    parser.add_argument(
        "--speed",
        type=float,
        help="legacy option: seconds between captures (equivalent to 1/rate)",
    )
    parser.add_argument("--loop", action="store_true", help="repeat the scripted schedule")
    parser.add_argument(
        "--external-module1",
        action="store_true",
        help="disable the mock producer and continuously watch for real Module 1 files",
    )
    parser.add_argument("--keep", action="store_true", help="keep existing exchange files")
    parser.add_argument("--plain", action="store_true", help="use line-oriented output")
    parser.add_argument(
        "--exit-on-complete",
        action="store_true",
        help="close the Rich dashboard when processing finishes",
    )
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--no-tests",
        action="store_true",
        help="accepted for compatibility; the unified demo never runs tests at startup",
    )
    return parser


def _capture_rate(args: argparse.Namespace, parser: argparse.ArgumentParser) -> float:
    if args.rate is not None and args.speed is not None:
        parser.error("use either --rate or --speed, not both")
    if args.speed is not None:
        if args.speed <= 0:
            parser.error("--speed must be greater than zero")
        return 1.0 / args.speed
    rate = 5.0 if args.rate is None else args.rate
    if rate <= 0:
        parser.error("--rate must be greater than zero")
    return rate


def _guard_worker(
    state: DemoState,
    stop_event: threading.Event,
    label: str,
    worker: Callable[[], None],
) -> None:
    try:
        worker()
    except Exception as exc:  # Worker failures must be visible in the one-window UI.
        state.add_error(f"{label}: {exc}")
        stop_event.set()


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.count < 0:
        parser.error("--count must be zero or positive")
    rate = _capture_rate(args, parser)
    if args.external_module1 and args.count:
        parser.error("--count cannot be used with --external-module1")
    if args.external_module1 and (args.rate is not None or args.speed is not None or args.loop):
        parser.error("--rate, --speed and --loop apply only to the mock Module 1 producer")

    instance_lock = DemoInstanceLock(DEFAULT_EXCHANGE_ROOT.parent / ".demo_dashboard.lock")
    try:
        instance_lock.acquire()
    except RuntimeError as exc:
        parser.error(str(exc))
    try:
        return _run_dashboard(args, parser, rate)
    finally:
        instance_lock.release()


def _run_dashboard(
    args: argparse.Namespace,
    parser: argparse.ArgumentParser,
    rate: float,
) -> int:

    exchange_root = DEFAULT_EXCHANGE_ROOT
    # Never remove files that may already have been delivered by a real Module 1.
    if not args.external_module1 and not args.keep and exchange_root.exists():
        shutil.rmtree(exchange_root)
    ensure_exchange_folders(exchange_root)

    state = DemoState()
    stop_event = threading.Event()
    producer_done = threading.Event()
    producer_result = {"written": 0}
    processor = FileProcessor(exchange_root, seed=args.seed)
    receiver3 = MockFileReceiver(
        3,
        exchange_root,
        quiet=True,
        on_receive=lambda path, payload, decision: state.output_received(3, payload, decision),
    )
    receiver4 = MockFileReceiver(
        4,
        exchange_root,
        quiet=True,
        on_receive=lambda path, payload, decision: state.output_received(4, payload, decision),
    )

    def producer_target() -> None:
        try:
            producer_result["written"] = run_mock_module1(
                exchange_root=exchange_root,
                rate=rate,
                count=args.count,
                loop=args.loop,
                seed=args.seed,
                stop_event=stop_event,
                done_event=producer_done,
                on_write=state.input_written,
                quiet=True,
            )
        finally:
            producer_done.set()

    worker_specs: list[tuple[str, Callable[[], None]]] = [
        ("Module 2", lambda: processor.run(stop_event)),
        ("MOCK Module 3", lambda: receiver3.run(stop_event)),
        ("MOCK Module 4", lambda: receiver4.run(stop_event)),
    ]
    if not args.external_module1:
        worker_specs.append(("MOCK Module 1", producer_target))
    workers = [
        threading.Thread(
            target=_guard_worker,
            args=(state, stop_event, label, target),
            name=label.lower().replace(" ", "-"),
        )
        for label, target in worker_specs
    ]
    for worker in workers:
        worker.start()

    started = time.monotonic()
    last_plain_received = -1
    interrupted = False
    run_complete = False
    try:
        if args.plain:
            module1_mode = "EXTERNAL" if args.external_module1 else "SIMULATED"
            print(
                f"Unified file exchange - Module 1 is {module1_mode}; "
                "Module 2 is REAL; Modules 3 and 4 are SIMULATED"
            )
            while True:
                stats = processor.stats_snapshot()
                if stats["received"] != last_plain_received:
                    print_plain_snapshot(processor, exchange_root)
                    last_plain_received = stats["received"]
                if not args.external_module1 and _is_complete(
                    producer_done, producer_result, processor, receiver3, receiver4
                ):
                    break
                if stop_event.wait(0.1):
                    break
        else:
            from rich.console import Console
            from rich.live import Live

            console = Console()
            compact = console.width < 110 or console.height < 32
            with Live(
                build_dashboard(
                    state,
                    processor,
                    started,
                    compact=compact,
                    module1_mock=not args.external_module1,
                ),
                console=console,
                refresh_per_second=8,
                screen=console.is_terminal,
            ) as live:
                while True:
                    if not run_complete and not args.external_module1:
                        run_complete = _is_complete(
                            producer_done,
                            producer_result,
                            processor,
                            receiver3,
                            receiver4,
                        )
                    live.update(
                        build_dashboard(
                            state,
                            processor,
                            started,
                            compact=compact,
                            completed=run_complete,
                            module1_mock=not args.external_module1,
                        )
                    )
                    if run_complete and (args.exit_on_complete or not console.is_terminal):
                        break
                    if stop_event.wait(0.1):
                        break
    except KeyboardInterrupt:
        interrupted = not run_complete
        print("\nClosing dashboard..." if run_complete else "\nStopping workers...")
    finally:
        stop_event.set()
        for worker in workers:
            worker.join(timeout=5.0)
        processor.process_pending()
        receiver3.process_pending()
        receiver4.process_pending()

    errors = state.snapshot()["errors"]
    if errors:
        print("Worker errors:")
        for error in errors:
            print(f"  {error}")
    print("\nFinal processor summary" + (" (interrupted)" if interrupted else ""))
    print_plain_snapshot(processor, exchange_root)
    print_exchange_summary(exchange_root)
    return 1 if errors else 0


def _is_complete(
    producer_done: threading.Event,
    producer_result: dict[str, int],
    processor: FileProcessor,
    receiver3: MockFileReceiver,
    receiver4: MockFileReceiver,
) -> bool:
    if not producer_done.is_set():
        return False
    written = producer_result["written"]
    stats = processor.stats_snapshot()
    valid = sum(stats["class_counts"].values())
    return (
        stats["received"] >= written
        and receiver3.received_count >= valid
        and receiver4.received_count >= valid
        and not list(processor.paths["inbox"].glob("*.json"))
        and not list(processor.paths["module3"].glob("*.json"))
        and not list(processor.paths["module4"].glob("*.json"))
    )


def main() -> int:
    parser = build_parser()
    return run(parser.parse_args(), parser)


if __name__ == "__main__":
    raise SystemExit(main())

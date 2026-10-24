"""One-window replay dashboard for the real Module 1 recording."""

from __future__ import annotations

import argparse
import os
import threading
import time
from collections import Counter, deque
from pathlib import Path
from typing import Any

from integration.file_mock_receiver import MockFileReceiver
from src.classifier import Classification
from src.contracts import ThreatStateOut
from src.file_exchange import (
    DEFAULT_EXCHANGE_ROOT,
    ensure_exchange_folders,
    exchange_filename,
    exchange_paths,
    write_json_atomic,
)
from src.file_processor import FileProcessor
from src.real_data import JsonFolderSource, RealSignal, load_ground_truth, signal_to_record


PROJECT_ROOT = Path(__file__).resolve().parents[1]
REAL_DATA_ROOT = PROJECT_ROOT / "data" / "real" / "module1_real_signals"
CLASS_COLOURS = {"NORMAL": "green", "JAMMING": "bold red", "UNKNOWN_ANOMALY": "yellow"}


class DemoInstanceLock:
    """Prevent two dashboards from writing the same exchange folders."""

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
            raise RuntimeError("another dashboard is already running") from exc

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
    """Dashboard and scoring state; labels are joined only after classification."""

    def __init__(self, truth: dict[str, dict[str, str]]) -> None:
        self.truth = truth
        self.latest_input: dict[str, Any] | None = None
        self.latest_output: dict[str, Any] | None = None
        self.inputs: dict[int, RealSignal] = {}
        self.captures: deque[dict[str, Any]] = deque(maxlen=12)
        self.decisions: dict[int, str] = {}
        self.predictions: dict[str, str] = {}
        self.sent_count = 0

    def input_written(self, signal: RealSignal) -> None:
        self.latest_input = signal_to_record(signal)
        self.inputs[signal.sequence_number] = signal
        self.sent_count += 1

    def output_received(self, module: int, payload: ThreatStateOut, decision: str) -> None:
        self.decisions[module] = decision
        if module != 3:
            return
        signal = self.inputs[payload.sequence_number]
        reference = self.truth[payload.observation_id]
        dumped = payload.model_dump(mode="json")
        self.latest_output = dumped
        self.predictions[payload.observation_id] = payload.classification
        self.captures.append(
            {
                "sequence": payload.sequence_number,
                "observation_id": payload.observation_id,
                "classification": payload.classification,
                "expected": reference["expected_class"],
                "jammer_type": reference["jammer_type"] or reference["normal_kind"] or "review",
                "severity": payload.severity,
                "rule": payload.triggered_rule,
                "processing_ms": payload.processing_ms,
                "signal": signal,
                "evidence": payload.evidence,
                "deviation": payload.statistical_deviation,
            }
        )


def clear_exchange_files(root: str | Path = DEFAULT_EXCHANGE_ROOT) -> None:
    """Delete files only inside the known demo exchange directories."""
    paths = ensure_exchange_folders(root)
    for name, folder in paths.items():
        if name == "root":
            continue
        for path in folder.rglob("*"):
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)


def folder_counts(root: str | Path = DEFAULT_EXCHANGE_ROOT) -> dict[str, int]:
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


def scoring_rows(state: DemoState) -> list[tuple[dict[str, str], str]]:
    """Return clean reference rows paired with existing predictions."""
    result = []
    for observation_id, prediction in state.predictions.items():
        reference = state.truth[observation_id]
        if not reference["label_quality_note"]:
            result.append((reference, prediction))
    return result


def score_summary(state: DemoState) -> dict[str, Any]:
    rows = scoring_rows(state)
    matrix = {
        expected: {
            predicted: sum(
                reference["expected_class"] == expected and output == predicted
                for reference, output in rows
            )
            for predicted in ("NORMAL", "JAMMING", "UNKNOWN_ANOMALY")
        }
        for expected in ("NORMAL", "JAMMING")
    }
    recalls: dict[str, tuple[int, int]] = {}
    for jammer in ("CARRIER", "PULSED_50_50", "PULSED_5_95", "RANDOM_BURSTS"):
        jammer_rows = [
            output
            for reference, output in rows
            if reference["jammer_type"] == jammer
            and reference["expected_class"] == "JAMMING"
        ]
        recalls[jammer] = (sum(output != "NORMAL" for output in jammer_rows), len(jammer_rows))
    false_positive_rates: dict[str, tuple[int, int]] = {}
    for normal_kind in ("idle", "legit_ook"):
        normal_rows = [
            output for reference, output in rows if reference["normal_kind"] == normal_kind
        ]
        false_positive_rates[normal_kind] = (
            sum(output != "NORMAL" for output in normal_rows),
            len(normal_rows),
        )
    return {"matrix": matrix, "recalls": recalls, "fpr": false_positive_rates}


def _rate(pair: tuple[int, int]) -> str:
    count, total = pair
    return f"{count}/{total} ({100.0 * count / total:.2f}%)" if total else "0/0 (n/a)"


def print_scoring_summary(state: DemoState) -> None:
    score = score_summary(state)
    matrix = score["matrix"]
    print("\nScoring summary (ground truth used here only)")
    print("  Confusion matrix")
    print("  expected          NORMAL  JAMMING  UNKNOWN_ANOMALY")
    for expected in ("NORMAL", "JAMMING"):
        row = matrix[expected]
        print(
            f"  {expected:<16} {row['NORMAL']:>6}  {row['JAMMING']:>7}  "
            f"{row['UNKNOWN_ANOMALY']:>15}"
        )
    print("  Recall per jammer type")
    for jammer, pair in score["recalls"].items():
        print(f"  {jammer:<16} {_rate(pair)}")
    print(f"  Idle false-positive rate       {_rate(score['fpr']['idle'])}")
    print(f"  Legitimate OOK false-positive  {_rate(score['fpr']['legit_ook'])}")
    print("  Label-quality exceptions excluded from scoring: 11")


def print_exchange_summary(root: Path) -> None:
    print(f"\nJSON folder counts: {root}")
    for name, count in folder_counts(root).items():
        print(f"  {name:<12} {count:>5}")


def _latest_panel(state: DemoState):
    from rich.panel import Panel
    from rich.text import Text

    if not state.captures:
        return Panel("[dim]Waiting for the first capture...[/]", title="Latest detection")
    row = state.captures[-1]
    signal = row["signal"]
    colour = CLASS_COLOURS[row["classification"]]
    evidence = "\n".join(f"- {item}" for item in row["evidence"][:3]) or "- None"
    return Panel(
        Text.from_markup(
            f"[{colour}]{row['classification']}[/]  expected={row['expected']}\n"
            f"#{row['sequence']:06d} {row['observation_id']}  {row['jammer_type']}\n"
            f"peak={signal.peak_db:.1f} dB  SNR={signal.snr_db:.1f} dB  "
            f"bandwidth={signal.occupied_bw_khz:.1f} kHz\n"
            f"flatness={signal.spectral_flatness:.3f}  rule={row['rule'] or '-'}\n"
            f"{evidence}"
        ),
        title="Latest real capture",
        border_style=colour,
    )


def build_dashboard(state: DemoState, processor: FileProcessor, started: float, complete: bool):
    from rich import box
    from rich.align import Align
    from rich.layout import Layout
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    stats = processor.stats_snapshot()
    counts = folder_counts(processor.paths["root"])
    classes = stats["class_counts"]
    score = score_summary(state)
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=4),
        Layout(name="pipeline", size=5),
        Layout(name="body", ratio=3),
        Layout(name="status", size=10),
        Layout(name="footer", size=3),
    )
    status = "[bold green]REPLAY COMPLETE[/]" if complete else "[bold cyan]REPLAYING[/]"
    header = Text.from_markup(
        "[bold]UAV Cyber Defence - Threat Intelligence Dashboard[/]\n"
        "[green]Data source: REAL (Module 1 recording 2026-10-23)[/] | "
        f"[yellow]Modules 3 and 4 simulated[/] | {status} | {time.monotonic()-started:.1f}s"
    )
    layout["header"].update(Panel(Align.center(header), border_style="green" if complete else "cyan"))

    pipeline = Table.grid(expand=True)
    for ratio in (2, 1, 2, 1, 2):
        pipeline.add_column(ratio=ratio, justify="center")
    pipeline.add_row(
        f"[green bold]MODULE 1 RECORDING[/]\n{state.sent_count}/1513 replayed",
        "[cyan]=>[/]",
        f"[bold]MODULE 2 V2[/]\n{sum(classes.values())} classified",
        "[cyan]=>[/]",
        f"[yellow bold]MODULES 3 + 4[/]\n{counts['M3 received']} / {counts['M4 received']} received",
    )
    layout["pipeline"].update(Panel(pipeline, title="Real JSON replay", border_style="blue"))

    layout["body"].split_row(Layout(name="recent", ratio=3), Layout(name="latest", ratio=2))
    recent = Table(box=box.SIMPLE, expand=True, header_style="bold cyan")
    recent.add_column("Seq", justify="right")
    recent.add_column("Reference")
    recent.add_column("Classification")
    recent.add_column("Rule")
    recent.add_column("ms", justify="right")
    for row in state.captures:
        colour = CLASS_COLOURS[row["classification"]]
        recent.add_row(
            f"{row['sequence']:06d}",
            row["jammer_type"],
            f"[{colour}]{row['classification']}[/]",
            row["rule"] or "-",
            f"{row['processing_ms']:.3f}",
        )
    layout["recent"].update(Panel(recent, title="Last 12 captures", border_style="cyan"))
    layout["latest"].update(_latest_panel(state))

    layout["status"].split_row(
        Layout(name="results", ratio=2), Layout(name="scores", ratio=3), Layout(name="folders", ratio=2)
    )
    results = Table.grid(expand=True)
    results.add_column()
    results.add_column(justify="right")
    results.add_row("Normal", str(classes.get(Classification.NORMAL.value, 0)))
    results.add_row("Jamming", str(classes.get(Classification.JAMMING.value, 0)))
    results.add_row("Unknown", str(classes.get(Classification.UNKNOWN_ANOMALY.value, 0)))
    results.add_row("Mean / P95", f"{stats['mean_processing_ms']:.3f} / {stats['p95_processing_ms']:.3f} ms")
    layout["results"].update(Panel(results, title="Module 2", border_style="green"))

    scoring = Table.grid(expand=True)
    scoring.add_column()
    scoring.add_column(justify="right")
    for jammer, pair in score["recalls"].items():
        scoring.add_row(f"Recall {jammer}", _rate(pair))
    scoring.add_row("FPR idle", _rate(score["fpr"]["idle"]))
    scoring.add_row("FPR legit OOK", _rate(score["fpr"]["legit_ook"]))
    layout["scores"].update(Panel(scoring, title="Scoring only", border_style="magenta"))

    folders = Table.grid(expand=True)
    folders.add_column()
    folders.add_column(justify="right")
    for name, count in counts.items():
        folders.add_row(name, str(count))
    layout["folders"].update(Panel(folders, title="JSON exchange", border_style="blue"))
    footer_text = (
        "[bold green]Complete - Ctrl+C to close[/]"
        if complete
        else "[dim]Replaying validated files in sequence order[/]  [bold]Ctrl+C[/] stop"
    )
    layout["footer"].update(Panel(Align.center(Text.from_markup(footer_text)), border_style="cyan"))
    return layout


def replay(
    state: DemoState,
    processor: FileProcessor,
    receiver3: MockFileReceiver,
    receiver4: MockFileReceiver,
    signals: list[RealSignal],
    speed: float,
    update: Any | None = None,
) -> bool:
    interrupted = False
    try:
        for signal in signals:
            destination = processor.paths["inbox"] / exchange_filename(
                signal.sequence_number, signal.observation_id
            )
            write_json_atomic(destination, signal_to_record(signal))
            state.input_written(signal)
            processor.process_pending()
            receiver3.process_pending()
            receiver4.process_pending()
            if update is not None:
                update()
            if speed:
                time.sleep(speed)
    except KeyboardInterrupt:
        interrupted = True
    return interrupted


def run(args: argparse.Namespace, parser: argparse.ArgumentParser) -> int:
    if args.speed < 0:
        parser.error("--speed must be zero or greater")
    lock = DemoInstanceLock(DEFAULT_EXCHANGE_ROOT.parent / ".demo_dashboard.lock")
    try:
        lock.acquire()
    except RuntimeError as exc:
        parser.error(str(exc))
    try:
        if not args.keep:
            clear_exchange_files(DEFAULT_EXCHANGE_ROOT)
        paths = ensure_exchange_folders(DEFAULT_EXCHANGE_ROOT)
        signals = list(JsonFolderSource(REAL_DATA_ROOT))
        truth = load_ground_truth(REAL_DATA_ROOT / "ground_truth.csv")
        state = DemoState(truth)
        processor = FileProcessor(paths["root"])
        receiver3 = MockFileReceiver(
            3,
            paths["root"],
            quiet=True,
            on_receive=lambda path, payload, decision: state.output_received(3, payload, decision),
        )
        receiver4 = MockFileReceiver(
            4,
            paths["root"],
            quiet=True,
            on_receive=lambda path, payload, decision: state.output_received(4, payload, decision),
        )
        started = time.monotonic()
        print(
            "Data source: REAL (Module 1 recording 2026-10-23); "
            "Modules 3 and 4 simulated"
        )
        if args.plain:
            last_report = 0

            def progress() -> None:
                nonlocal last_report
                if state.sent_count == len(signals) or state.sent_count - last_report >= 100:
                    stats = processor.stats_snapshot()
                    print(
                        f"replayed={state.sent_count}/{len(signals)} "
                        f"classified={sum(stats['class_counts'].values())} "
                        f"mean_ms={stats['mean_processing_ms']:.3f}"
                    )
                    last_report = state.sent_count

            interrupted = replay(
                state, processor, receiver3, receiver4, signals, args.speed, progress
            )
        else:
            from rich.console import Console
            from rich.live import Live

            console = Console()
            interrupted = False
            with Live(
                build_dashboard(state, processor, started, False),
                console=console,
                refresh_per_second=12,
                screen=console.is_terminal,
            ) as live:
                interrupted = replay(
                    state,
                    processor,
                    receiver3,
                    receiver4,
                    signals,
                    args.speed,
                    lambda: live.update(build_dashboard(state, processor, started, False)),
                )
                live.update(build_dashboard(state, processor, started, not interrupted))
                if not interrupted and console.is_terminal and not args.exit_on_complete:
                    try:
                        while True:
                            time.sleep(0.25)
                    except KeyboardInterrupt:
                        pass
        print_scoring_summary(state)
        print_exchange_summary(paths["root"])
        stats = processor.stats_snapshot()
        print(
            f"\nReplay {'interrupted' if interrupted else 'complete'}: "
            f"processed={sum(stats['class_counts'].values())} "
            f"rejected={stats['rejected']} mean_ms={stats['mean_processing_ms']:.3f} "
            f"p95_ms={stats['p95_processing_ms']:.3f}"
        )
        return 130 if interrupted else 0
    finally:
        lock.release()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Replay the real Module 1 recording")
    parser.add_argument(
        "--speed",
        type=float,
        default=0.02,
        help="seconds between captures; 0 replays as fast as possible",
    )
    parser.add_argument("--keep", action="store_true", help="keep existing exchange files")
    parser.add_argument("--plain", action="store_true", help="use line-oriented output")
    parser.add_argument(
        "--exit-on-complete",
        action="store_true",
        help="close the Rich dashboard after the replay",
    )
    parser.add_argument(
        "--no-tests",
        action="store_true",
        help="accepted for command compatibility; tests are never run at demo startup",
    )
    return parser


def main() -> int:
    parser = build_parser()
    return run(parser.parse_args(), parser)


if __name__ == "__main__":
    raise SystemExit(main())

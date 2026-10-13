"""
demo.py — Live terminal dashboard for the AI Threat Intelligence Module.

Usage:
    python demo.py
    python demo.py --count 40 --speed 0.05 --no-tests
    python demo.py --plain           # plain one-line-per-obs output, no rich Live
    python demo.py --count 200 --speed 0.4 --seed 42

Controls:
    Ctrl+C  -> graceful stop, prints partial summary and saves log CSV.
"""

from __future__ import annotations

import argparse
import csv
import subprocess
import sys
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Optional

# ─── path setup (run from project root) ────────────────────────────────────────
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

from src.baseline import NormalBaseline
from src.rule_engine import build_default_ruleset
from src.anomaly_engine import StatisticalAnomalyEngine
from src.classifier import ThreatIntelligenceModule, ThreatOutput
from src.data_source import SyntheticDataSource

# ─── rich imports (only imported once; plain mode avoids them) ──────────────────
def _import_rich():
    from rich.console import Console
    from rich.layout import Layout
    from rich.live import Live
    from rich.panel import Panel
    from rich.progress import Progress, BarColumn, TextColumn, TimeElapsedColumn
    from rich.table import Table
    from rich.text import Text
    from rich import box
    return Console, Layout, Live, Panel, Progress, BarColumn, TextColumn, TimeElapsedColumn, Table, Text, box

# ─── constants ──────────────────────────────────────────────────────────────────
CALIB_N       = 200
CALIB_SPLIT   = 0.70          # 70 % for calibration
Z_THRESHOLD   = 3.0
DATA_DIR      = ROOT / "data"
LOG_CSV_PATH  = DATA_DIR / "demo_run_log.csv"
MAX_FEED_ROWS = 12            # rows kept in the live feed table

FEATURES = ["rssi", "snr", "noise_floor", "packet_rate"]
UNITS    = {"rssi": "dBm", "snr": "dB", "noise_floor": "dBm", "packet_rate": "pkt/s"}

# Scenario schedule as (true_label, count) segments summing to --count
# Pattern: normal -> jamming burst -> normal -> unknown_anomaly burst -> normal
def make_schedule(total: int):
    n1 = max(1, int(total * 0.25))
    jam = max(1, int(total * 0.20))
    n2 = max(1, int(total * 0.15))
    unk = max(1, int(total * 0.20))
    n3 = max(0, total - n1 - jam - n2 - unk)
    return [("normal", n1), ("jamming", jam), ("normal", n2),
            ("unknown_anomaly", unk), ("normal", n3)]

CLASS_COLOR = {
    "Normal":          "green",
    "Jamming":         "red",
    "Unknown Anomaly": "yellow",
}

# ─── Phase 1 helpers ─────────────────────────────────────────────────────────────

def run_pytest(console) -> str:
    """Run pytest -q and return a summary string. Prints live progress to console."""
    console.print("[bold cyan]Running test suite (python -m pytest -q)...[/]")
    result = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=no"],
        capture_output=True, text=True, cwd=str(ROOT)
    )
    output = result.stdout + result.stderr
    # extract last summary line like "126 passed in 3.38s"
    summary = "unknown"
    for line in reversed(output.splitlines()):
        if "passed" in line or "failed" in line or "error" in line:
            summary = line.strip()
            break
    colour = "green" if result.returncode == 0 else "red"
    console.print(f"  [{colour}]{summary}[/]")
    return summary


def calibrate_baseline(console, seed: int):
    """Calibrate NormalBaseline on 70 % of 200 normal samples. Returns baseline."""
    console.print(f"[bold cyan]Calibrating NormalBaseline (seed={seed})...[/]")
    src = SyntheticDataSource("normal", seed=seed)
    all_obs = src.fetch_batch(CALIB_N)
    split = int(len(all_obs) * CALIB_SPLIT)
    calib_obs = all_obs[:split]

    baseline = NormalBaseline()
    baseline.add_normal_samples(calib_obs)
    baseline.calibrate()

    from rich.table import Table
    t = Table(title="Calibrated Baseline", box=None, padding=(0, 2))
    t.add_column("Feature", style="bold")
    t.add_column("Mean", justify="right")
    t.add_column("Std", justify="right")
    t.add_column("Unit")
    for f in FEATURES:
        fb = baseline.baseline[f]
        t.add_row(f, f"{fb.mean:.2f}", f"{fb.std:.2f}", UNITS[f])
    console.print(t)
    return baseline


def show_thresholds(console):
    """Print the active rule thresholds."""
    det = build_default_ruleset()
    # extract thresholds from the closure — we just re-read the known defaults
    console.print("\n[bold cyan]Active detection thresholds:[/]")
    console.print("  Rule J01  :  snr_drop > [bold]2.50[/] sigma  AND  noise_floor_increase > [bold]2.75[/] sigma")
    console.print("  Rule J02  :  rssi_deviation > [bold]2.69[/] sigma  AND  packet_rate_deviation > [bold]8.83[/] sigma")
    console.print(f"  Anomaly z :  |z| >= [bold]{Z_THRESHOLD}[/] sigma  (StatisticalAnomalyEngine)")
    return det

# ─── Rich-mode Live dashboard ────────────────────────────────────────────────────

def make_classification_text(cls: str, Text):
    colour = CLASS_COLOR.get(cls, "white")
    return Text(cls, style=f"bold {colour}")


def build_layout(Layout, Panel, Table, Text, box):
    layout = Layout()
    layout.split_column(
        Layout(name="header", size=3),
        Layout(name="body"),
        Layout(name="footer", size=3),
    )
    layout["body"].split_row(
        Layout(name="feed", ratio=3),
        Layout(name="right", ratio=2),
    )
    layout["right"].split_column(
        Layout(name="stats"),
        Layout(name="explain"),
        Layout(name="integration"),
    )
    return layout


def feed_table(records: list[dict], Table, Text, box) -> Table:
    t = Table(
        title=None, box=box.SIMPLE_HEAVY, padding=(0, 1),
        show_header=True, header_style="bold blue",
    )
    t.add_column("Time",    width=8)
    t.add_column("Obs ID",  width=11)
    t.add_column("RSSI",    width=7, justify="right")
    t.add_column("SNR",     width=6, justify="right")
    t.add_column("Noise",   width=7, justify="right")
    t.add_column("Rate",    width=7, justify="right")
    t.add_column("True",    width=8)
    t.add_column("Pred",    width=16)
    t.add_column("Sev",     width=4)
    t.add_column("Rule",    width=4)
    t.add_column("ms",      width=5, justify="right")

    true_colors = {"normal": "white", "jamming": "red", "unknown_anomaly": "yellow"}

    for r in records[-MAX_FEED_ROWS:]:
        true_abbr = {"normal": "NORM", "jamming": "JAM ", "unknown_anomaly": "UNK "}
        tc = true_colors.get(r["true_label"], "white")
        pred_text = make_classification_text(r["predicted"], Text)
        sev = (r["severity"] or "-")[:3]
        rule = (r["triggered_rule"] or "-")[:4]
        t.add_row(
            r["wall_time"],
            r["obs_id"],
            f"{r['rssi']:.1f}",
            f"{r['snr']:.1f}",
            f"{r['noise']:.1f}",
            f"{r['rate']:.0f}",
            Text(true_abbr.get(r["true_label"], r["true_label"]), style=f"bold {tc}"),
            pred_text,
            sev,
            rule,
            f"{r['latency_ms']:.2f}",
        )
    return t


def stats_panel(records: list[dict], start_ts: float, Panel, Text, total: int) -> Panel:
    if not records:
        return Panel("No data yet.", title="Statistics", border_style="blue")

    n = len(records)
    correct = sum(1 for r in records if r["correct"])
    latencies = [r["latency_ms"] for r in records]
    mean_lat = sum(latencies) / n
    p95_lat = sorted(latencies)[int(0.95 * n)] if n >= 20 else max(latencies)
    nfr_ok = p95_lat < 50.0

    preds = Counter(r["predicted"] for r in records)
    trues = Counter(r["true_label"] for r in records)

    elapsed = time.time() - start_ts
    lines = [
        f"[bold]Elapsed:[/]   {elapsed:.1f}s",
        f"[bold]Processed:[/] {n} / {total}",
        "",
        f"[bold cyan]By prediction:[/]",
        f"  Normal:          {preds.get('Normal', 0)}",
        f"  [red]Jamming:         {preds.get('Jamming', 0)}[/]",
        f"  [yellow]Unknown Anomaly: {preds.get('Unknown Anomaly', 0)}[/]",
        "",
        f"[bold]Accuracy:[/]  {correct}/{n}  ({100*correct/n:.1f}%)",
        f"[bold]Mean lat:[/]  {mean_lat:.3f} ms",
        f"[bold]P95 lat:[/]   {p95_lat:.3f} ms",
        f"[bold]NFR01 <50ms:[/] {'[green]PASS[/]' if nfr_ok else '[red]FAIL[/]'}",
    ]
    return Panel("\n".join(lines), title="[bold blue]Statistics[/]", border_style="blue")


def explain_panel(records: list[dict], Panel, Text, box) -> Panel:
    # find latest non-Normal detection
    latest = None
    for r in reversed(records):
        if r["predicted"] != "Normal":
            latest = r
            break
    if latest is None:
        return Panel("No threat detected yet.", title="Last Detection", border_style="yellow")

    colour = CLASS_COLOR.get(latest["predicted"], "white")
    lines = [
        f"[bold]Classification:[/] [{colour}]{latest['predicted']}[/]",
        f"[bold]Severity:[/]       {latest['severity'] or '-'}",
        f"[bold]Rule:[/]           {latest['triggered_rule'] or 'None (anomaly engine)'}",
        "",
        "[bold]Evidence:[/]",
    ]
    for ev in latest.get("evidence", []):
        lines.append(f"  * {ev}")

    lines.append("")
    lines.append("[bold]Z-scores (deviation from normal):[/]")
    for feat, z in latest.get("z_scores", {}).items():
        bar_len = min(20, int(abs(z) * 2))
        bar = ("=" * bar_len).ljust(20)
        lines.append(f"  {feat:<12} z={z:+.2f}  |{bar}|")

    return Panel("\n".join(lines), title="[bold yellow]Last Detection Detail[/]", border_style="yellow")


def integration_panel(Panel) -> Panel:
    lines = [
        "[dim]Module 1  SDR RF Threat Detection:    [/][yellow]SIMULATED[/] (SyntheticDataSource) - real feed pending",
        "[green]Module 2  AI Threat Intelligence:    RUNNING[/]",
        "[dim]Module 3  Secure UAV Communication:   PENDING integration[/]",
        "[dim]Module 4  Autonomous Defense & Resp:  PENDING integration[/]",
    ]
    return Panel("\n".join(lines), title="[bold]Integration Status[/]", border_style="dim")


def header_panel(elapsed: float, count: int, total: int, Panel) -> Panel:
    ts = datetime.now().strftime("%H:%M:%S")
    text = (
        f"[bold blue] AI Threat Intelligence Module (Module 2)[/]     "
        f"Source: SyntheticDataSource     "
        f"Clock: {ts}     Elapsed: {elapsed:.1f}s     "
        f"Observations: {count}/{total}"
    )
    return Panel(text, border_style="blue")


# ─── record builder ─────────────────────────────────────────────────────────────

def make_record(obs, output: ThreatOutput, true_label: str, latency_ms: float) -> dict:
    return {
        "wall_time":     datetime.now().strftime("%H:%M:%S"),
        "obs_id":        obs.observation_id,
        "rssi":          obs.rssi,
        "snr":           obs.snr,
        "noise":         obs.noise_floor,
        "rate":          obs.packet_rate,
        "true_label":    true_label,
        "predicted":     output.classification,
        "severity":      output.severity,
        "triggered_rule": output.triggered_rule,
        "latency_ms":    latency_ms,
        "correct":       (true_label.replace("_", " ").title() == output.classification
                          or true_label == output.classification.lower().replace(" ", "_")),
        "evidence":      output.evidence,
        "z_scores":      output.statistical_deviation,
    }


def label_matches(true_label: str, predicted: str) -> bool:
    """Compare true_label (snake_case) to predicted (Title Case)."""
    mapping = {
        "normal":          "Normal",
        "jamming":         "Jamming",
        "unknown_anomaly": "Unknown Anomaly",
    }
    return mapping.get(true_label, "") == predicted


# ─── Phase 3 summary ────────────────────────────────────────────────────────────

def print_summary(records: list[dict], console, plain: bool):
    if not records:
        console.print("[yellow]No observations processed.[/]")
        return

    n = len(records)
    classes = ["normal", "jamming", "unknown_anomaly"]
    predicted_map = {
        "normal":          "Normal",
        "jamming":         "Jamming",
        "unknown_anomaly": "Unknown Anomaly",
    }

    # Confusion matrix
    matrix: dict[str, Counter] = {c: Counter() for c in classes}
    for r in records:
        pred_key = {v: k for k, v in predicted_map.items()}.get(r["predicted"], "normal")
        matrix[r["true_label"]][pred_key] += 1

    latencies = [r["latency_ms"] for r in records]
    mean_lat = sum(latencies) / n
    p95_lat = sorted(latencies)[int(0.95 * n)] if n >= 20 else max(latencies)

    # Per-class precision / recall
    tp = {c: matrix[c][c] for c in classes}
    fn = {c: sum(matrix[c].values()) - tp[c] for c in classes}
    fp = {c: sum(matrix[t][c] for t in classes) - tp[c] for c in classes}
    total_per_class = {c: sum(matrix[c].values()) for c in classes}
    recall    = {c: tp[c] / max(1, total_per_class[c]) for c in classes}
    precision = {c: tp[c] / max(1, tp[c] + fp[c]) for c in classes}

    # Unknown anomaly-only engine catch count
    unk_caught_by_engine = sum(
        1 for r in records
        if r["true_label"] == "unknown_anomaly"
        and r["predicted"] == "Unknown Anomaly"
        and not r["triggered_rule"]
    )
    unk_total = sum(1 for r in records if r["true_label"] == "unknown_anomaly")

    # False positive rate on Normal
    norm_total = max(1, sum(1 for r in records if r["true_label"] == "normal"))
    norm_fp    = sum(1 for r in records if r["true_label"] == "normal" and r["predicted"] != "Normal")

    console.print("\n" + "=" * 70)
    console.print("[bold blue]  FINAL SESSION SUMMARY[/]")
    console.print("=" * 70)

    # Confusion matrix table
    try:
        from rich.table import Table
        from rich import box as rbox
        cm = Table(title="Confusion Matrix", box=rbox.SIMPLE_HEAVY)
        cm.add_column("True \\ Pred",      style="bold")
        cm.add_column("Pred: Normal",   justify="center")
        cm.add_column("Pred: Jamming",  justify="center")
        cm.add_column("Pred: Unknown",  justify="center")
        for c in classes:
            cm.add_row(
                c.replace("_", " ").title(),
                str(matrix[c]["normal"]),
                str(matrix[c]["jamming"]),
                str(matrix[c]["unknown_anomaly"]),
            )
        console.print(cm)
    except Exception:
        for c in classes:
            console.print(f"  {c}: {dict(matrix[c])}")

    console.print("\n[bold]Per-Class Metrics:[/]")
    for c in classes:
        label = c.replace("_", " ").title()
        console.print(
            f"  {label:<17}  Recall={recall[c]*100:.1f}%  "
            f"Precision={precision[c]*100:.1f}%  "
            f"(TP={tp[c]}, FP={fp[c]}, FN={fn[c]})"
        )

    console.print(f"\n[bold]False positive rate on Normal:[/]  {norm_fp}/{norm_total}  ({norm_fp/norm_total*100:.1f}%)")
    console.print(f"[bold]Mean latency:[/]                   {mean_lat:.4f} ms")
    console.print(f"[bold]P95 latency:[/]                    {p95_lat:.4f} ms")
    console.print(f"[bold]NFR01 (<50 ms):[/]                 {'PASS' if p95_lat < 50 else 'FAIL'}")
    console.print(
        f"\n[bold yellow]Unknown anomalies caught ONLY by the Statistical Anomaly Engine:[/]"
        f"  {unk_caught_by_engine} / {unk_total}"
    )
    console.print(
        f"  (A rule-engine-only system would have [red]missed all {unk_total}[/] of these.)"
    )

    # Save CSV log
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(LOG_CSV_PATH, "w", newline="", encoding="utf-8") as f:
        fieldnames = ["wall_time", "obs_id", "rssi", "snr", "noise", "rate",
                      "true_label", "predicted", "severity", "triggered_rule",
                      "latency_ms", "correct"]
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(records)
    console.print(f"\n[green]Log saved:[/] {LOG_CSV_PATH}")
    console.print("=" * 70 + "\n")


# ─── main streaming loop ─────────────────────────────────────────────────────────

def run_plain(module: ThreatIntelligenceModule, schedule: list, speed: float,
              records: list[dict], sources: dict[str, SyntheticDataSource]) -> None:
    """Plain mode: one-line-per-observation, no rich Live."""
    for (true_label, count) in schedule:
        if count == 0:
            continue
        batch = sources[true_label].fetch_batch(count)
        for obs in batch:
            t0 = time.perf_counter()
            output = module.classify(obs)
            lat = (time.perf_counter() - t0) * 1000
            r = make_record(obs, output, true_label, lat)
            records.append(r)
            ok = "[OK]" if r["correct"] else "[!]"
            print(
                f"{r['wall_time']}  {obs.observation_id:<11}  "
                f"True:{true_label.upper():<16}  "
                f"Pred:{output.classification:<16}  "
                f"Sev:{output.severity or '-':<7}  "
                f"Rule:{output.triggered_rule or '-':<6}  "
                f"{lat:.2f}ms  {ok}"
            )
            time.sleep(speed)


def run_rich(module: ThreatIntelligenceModule, schedule: list, speed: float,
             total: int, records: list[dict], console,
             sources: dict[str, SyntheticDataSource]) -> None:
    """Rich-mode dashboard with live layout."""
    (Console, Layout, Live, Panel, Progress, BarColumn,
     TextColumn, TimeElapsedColumn, Table, Text, box) = _import_rich()

    layout = build_layout(Layout, Panel, Table, Text, box)
    start_ts = time.time()

    def refresh():
        elapsed = time.time() - start_ts
        layout["header"].update(header_panel(elapsed, len(records), total, Panel))
        layout["feed"].update(
            Panel(
                feed_table(records, Table, Text, box),
                title="[bold blue]Live RF Observation Feed[/]",
                border_style="blue",
            )
        )
        layout["stats"].update(stats_panel(records, start_ts, Panel, Text, total))
        layout["explain"].update(explain_panel(records, Panel, Text, box))
        layout["integration"].update(integration_panel(Panel))
        layout["footer"].update(
            Panel(
                "[dim]Ctrl+C to stop early  |  --plain flag disables rich rendering  |  "
                "Log -> data/demo_run_log.csv[/]",
                border_style="dim",
            )
        )

    refresh()

    use_screen = console.is_terminal
    with Live(layout, console=console, refresh_per_second=4, screen=use_screen):
        for (true_label, count) in schedule:
            if count == 0:
                continue
            batch = sources[true_label].fetch_batch(count)
            for obs in batch:
                t0 = time.perf_counter()
                output = module.classify(obs)
                lat = (time.perf_counter() - t0) * 1000
                r = make_record(obs, output, true_label, lat)
                records.append(r)
                refresh()
                time.sleep(speed)


# ─── entry point ────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Live terminal dashboard for the AI Threat Intelligence Module."
    )
    parser.add_argument("--count",    type=int,   default=150,  help="Total observations to stream (default: 150)")
    parser.add_argument("--speed",    type=float, default=0.4,  help="Seconds between observations (default: 0.4)")
    parser.add_argument("--seed",     type=int,   default=42,   help="RNG seed (default: 42)")
    parser.add_argument("--no-tests", action="store_true",      help="Skip startup pytest run")
    parser.add_argument("--plain",    action="store_true",      help="Plain line-per-observation output (no rich Live)")
    args = parser.parse_args()

    # Initialise console (plain or rich)
    try:
        from rich.console import Console
        console = Console()
    except ImportError:
        class _FallbackConsole:
            def print(self, *a, **kw): print(*a)
        console = _FallbackConsole()
        args.plain = True

    console.print("\n[bold blue]=================================================================[/]")
    console.print("[bold blue]   AI Threat Intelligence Module (Module 2) - Live Demo Setup  [/]")
    console.print("[bold blue]=================================================================[/]\n")

    # ── Phase 1 ────────────────────────────────────────────────────────────────
    if not args.no_tests:
        run_pytest(console)
        console.print()

    baseline = calibrate_baseline(console, seed=args.seed)
    console.print()
    det = show_thresholds(console)
    console.print()

    rule_detector  = build_default_ruleset()
    anomaly_engine = StatisticalAnomalyEngine(z_threshold=Z_THRESHOLD)
    module         = ThreatIntelligenceModule(baseline, rule_detector, anomaly_engine)

    schedule = make_schedule(args.count)
    total    = sum(c for _, c in schedule)

    sched_str = " -> ".join(f"{l} ({n})" for l, n in schedule if n > 0)
    console.print(f"[bold cyan]Scenario schedule:[/] {sched_str}")
    console.print(f"[bold cyan]Total observations:[/] {total}   Speed: {args.speed}s/obs\n")
    console.print("[dim]Starting stream in 1 second...  Ctrl+C to stop early.[/]")
    time.sleep(1)

    # ── Phase 2 ────────────────────────────────────────────────────────────────
    sources = {
        "normal": SyntheticDataSource("normal", seed=args.seed, start_id=0),
        "jamming": SyntheticDataSource("jamming", seed=args.seed + 100, start_id=1000),
        "unknown_anomaly": SyntheticDataSource("unknown_anomaly", seed=args.seed + 200, start_id=2000),
    }

    records: list[dict] = []
    try:
        if args.plain:
            run_plain(module, schedule, args.speed, records, sources)
        else:
            run_rich(module, schedule, args.speed, total, records, console, sources)
    except KeyboardInterrupt:
        if not args.plain:
            # Live context already exited; console is usable again
            pass
        console.print("\n[yellow]Interrupted by user.[/]")

    # ── Phase 3 ────────────────────────────────────────────────────────────────
    print_summary(records, console, plain=args.plain)


if __name__ == "__main__":
    main()

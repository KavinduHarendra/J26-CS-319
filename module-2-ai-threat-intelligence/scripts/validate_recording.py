"""Check a Module 1 recording folder before it is used for calibration.

Usage: python scripts/validate_recording.py <folder>

Read-only: nothing in the folder is created, changed or deleted.  Capture
files go through the same strict loader the classifier uses.  ground_truth.csv
is read only to check coverage and count captures per class; its values are
never attached to a capture and nothing here classifies.  Exit code 1 if any
check fails; warnings do not fail.
"""

from __future__ import annotations

import csv
import sys
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.real_data import Signal, load_signal

PASS, WARN, FAIL = "PASS", "WARN", "FAIL"
GROUND_TRUTH = "ground_truth.csv"
GROUND_TRUTH_REQUIRED = ("sequence_number", "observation_id", "expected_class")
CLASSES = ("NORMAL", "JAMMING", "UNKNOWN_ANOMALY")
# Protocol target per class present in a session: 100 calibration + 100
# validation captures (see docs/HACKRF_RECORDING_PROTOCOL.md).
MIN_PER_CLASS = 200
# band_power_dbfs within 1 dB of ADC full scale means the front end clipped.
CLIPPING_DBFS = -1.0
SESSION_SETTINGS = ("center_freq_hz", "sample_rate_hz", "gain_db")
# session_id must be neutral; words like these reveal what was recorded.
REVEALING_WORDS = (
    "jam", "carrier", "pulse", "burst", "sweep", "idle", "normal", "legit",
    "attack", "anomal", "interfer", "wifi", "bluetooth", "microwave",
)


@dataclass(frozen=True, slots=True)
class Check:
    status: str
    name: str
    detail: str


def _ranges(numbers: list[int]) -> str:
    spans, start = [], None
    for index, number in enumerate(numbers):
        if start is None:
            start = number
        if index + 1 == len(numbers) or numbers[index + 1] != number + 1:
            spans.append(f"{start}" if start == number else f"{start}-{number}")
            start = None
    return ", ".join(spans[:10]) + (" ..." if len(spans) > 10 else "")


def _load_captures(folder: Path) -> tuple[list[tuple[Path, Signal]], list[Check]]:
    paths = sorted(folder.rglob("*.json"))
    loaded, errors = [], []
    for path in paths:
        if path.is_symlink():
            errors.append(f"{path.relative_to(folder)}: symbolic link")
            continue
        try:
            loaded.append((path, load_signal(path)))
        except (OSError, ValueError) as exc:
            errors.append(f"{path.relative_to(folder)}: {exc}")
    if not paths:
        return [], [Check(FAIL, "files", "no capture JSON files found")]
    if errors:
        shown = "; ".join(errors[:5]) + (f"; ... {len(errors) - 5} more" if len(errors) > 5 else "")
        return loaded, [Check(FAIL, "files", f"{len(errors)} of {len(paths)} files invalid: {shown}")]
    checks = [Check(PASS, "files", f"{len(paths)} capture files load with valid field names and ranges")]
    nested = {path.parent for path, _ in loaded} - {folder}
    if nested:
        checks.append(
            Check(WARN, "layout", f"captures in {len(nested)} subfolder(s); the protocol expects one flat folder")
        )
    return loaded, checks


def _sequence_checks(signals: list[Signal]) -> list[Check]:
    checks = []
    counts = Counter(signal.sequence_number for signal in signals)
    duplicates = sorted(number for number, count in counts.items() if count > 1)
    id_counts = Counter(signal.observation_id for signal in signals)
    duplicate_ids = sorted(name for name, count in id_counts.items() if count > 1)
    if duplicates or duplicate_ids:
        detail = []
        if duplicates:
            detail.append(f"sequence_number {_ranges(duplicates)}")
        if duplicate_ids:
            detail.append(f"observation_id {', '.join(duplicate_ids[:5])}")
        checks.append(Check(FAIL, "duplicates", "duplicated " + "; ".join(detail)))
    else:
        checks.append(Check(PASS, "duplicates", "no duplicate sequence numbers or observation IDs"))

    numbers = sorted(counts)
    missing = sorted(set(range(numbers[0], numbers[-1] + 1)) - set(numbers))
    if missing:
        checks.append(Check(FAIL, "sequence gaps", f"{len(missing)} missing: {_ranges(missing)}"))
    else:
        checks.append(Check(PASS, "sequence gaps", f"{numbers[0]}-{numbers[-1]} with no gaps"))

    ordered = sorted(signals, key=lambda signal: signal.sequence_number)
    backwards = [
        later.sequence_number
        for earlier, later in zip(ordered, ordered[1:])
        if later.timestamp < earlier.timestamp or later.elapsed_s < earlier.elapsed_s
    ]
    if backwards:
        checks.append(
            Check(FAIL, "timestamp order", f"time goes backwards at sequence {_ranges(backwards)}")
        )
    else:
        checks.append(Check(PASS, "timestamp order", "timestamp and elapsed_s never go backwards"))
    return checks


def _consistency(signals: list[Signal], field: str, check: str) -> Check:
    values = {getattr(signal, field) for signal in signals}
    present = values - {None}
    if not present:
        return Check(WARN, check, f"{field} absent from every capture (older export)")
    if None in values:
        missing = sum(getattr(signal, field) is None for signal in signals)
        return Check(FAIL, check, f"{field} missing from {missing} of {len(signals)} captures")
    if len(present) > 1:
        shown = ", ".join(sorted(map(str, present))[:5])
        return Check(FAIL, check, f"{field} changes within the session: {shown}")
    return Check(PASS, check, f"{field} = {present.pop()} in every capture")


def _session_checks(signals: list[Signal]) -> list[Check]:
    checks = [_consistency(signals, "session_id", "session_id")]
    session_ids = {signal.session_id for signal in signals} - {None}
    revealing = sorted(
        session_id
        for session_id in session_ids
        if any(word in session_id.lower() for word in REVEALING_WORDS)
    )
    if revealing:
        checks.append(
            Check(FAIL, "session_id naming", f"describes the recorded content: {', '.join(revealing)}")
        )
    checks += [_consistency(signals, field, f"fixed {field}") for field in SESSION_SETTINGS]

    loudest = max(signal.band_power_dbfs for signal in signals)
    clipped = [signal.sequence_number for signal in signals if signal.band_power_dbfs >= CLIPPING_DBFS]
    if clipped:
        checks.append(
            Check(
                FAIL,
                "ADC clipping",
                f"{len(clipped)} captures at band_power_dbfs >= {CLIPPING_DBFS:g}: {_ranges(clipped)}",
            )
        )
    else:
        checks.append(
            Check(PASS, "ADC clipping", f"max band_power_dbfs {loudest:g} (< {CLIPPING_DBFS:g} dBFS)")
        )
    return checks


def _ground_truth_checks(folder: Path, signals: list[Signal]) -> tuple[list[Check], Counter]:
    path = folder / GROUND_TRUTH
    if not path.is_file():
        return [Check(FAIL, "ground truth", f"{GROUND_TRUTH} not found in the folder")], Counter()
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        missing_columns = sorted(set(GROUND_TRUTH_REQUIRED) - set(reader.fieldnames or ()))
        if missing_columns:
            return [Check(FAIL, "ground truth", f"missing column(s): {', '.join(missing_columns)}")], Counter()
        rows = list(reader)

    problems = []
    by_id: dict[str, dict[str, str]] = {}
    for line, row in enumerate(rows, start=2):
        observation_id = (row["observation_id"] or "").strip()
        if observation_id in by_id:
            problems.append(f"duplicate row for {observation_id} (line {line})")
        by_id[observation_id] = row
        if (row["expected_class"] or "").strip() not in CLASSES:
            problems.append(f"line {line}: expected_class must be one of {', '.join(CLASSES)}")

    captures = {signal.observation_id: signal for signal in signals}
    uncovered = sorted(set(captures) - set(by_id))
    orphans = sorted(set(by_id) - set(captures))
    if uncovered:
        problems.append(f"{len(uncovered)} captures have no row (e.g. {', '.join(uncovered[:3])})")
    if orphans:
        problems.append(f"{len(orphans)} rows match no capture (e.g. {', '.join(orphans[:3])})")
    mismatched = [
        observation_id
        for observation_id, row in by_id.items()
        if observation_id in captures
        and (row["sequence_number"] or "").strip() != str(captures[observation_id].sequence_number)
    ]
    if mismatched:
        problems.append(f"{len(mismatched)} rows disagree on sequence_number (e.g. {mismatched[0]})")

    counts = Counter(
        by_id[observation_id]["expected_class"].strip()
        for observation_id in captures
        if observation_id in by_id
    )
    if problems:
        return [Check(FAIL, "ground truth", "; ".join(problems[:5]))], counts
    checks = [Check(PASS, "ground truth", f"every capture has exactly one row ({len(captures)})")]
    small = {name: count for name, count in counts.items() if count < MIN_PER_CLASS}
    if small:
        shown = ", ".join(f"{name} {count}" for name, count in sorted(small.items()))
        checks.append(Check(WARN, "class coverage", f"below {MIN_PER_CLASS} per class: {shown}"))
    else:
        checks.append(Check(PASS, "class coverage", f"every class present has >= {MIN_PER_CLASS} captures"))
    return checks, counts


def validate(folder: Path) -> tuple[list[Check], Counter]:
    if not folder.is_dir():
        return [Check(FAIL, "folder", f"{folder} is not a folder")], Counter()
    loaded, checks = _load_captures(folder)
    signals = [signal for _, signal in loaded]
    if not signals or checks[0].status == FAIL:
        return checks, Counter()
    checks += _sequence_checks(signals)
    checks += _session_checks(signals)
    truth_checks, counts = _ground_truth_checks(folder, signals)
    return checks + truth_checks, counts


def main(argv: list[str] | None = None, out: Callable[[str], None] = print) -> int:
    args = sys.argv[1:] if argv is None else argv
    if len(args) != 1:
        out("usage: python scripts/validate_recording.py <folder>")
        return 2
    folder = Path(args[0])
    checks, counts = validate(folder)
    out(f"Recording check: {folder}")
    for check in checks:
        out(f"[{check.status}] {check.name}: {check.detail}")
    if counts:
        out("Captures per class (from ground_truth.csv; reporting only):")
        for name in CLASSES:
            out(f"  {name}: {counts.get(name, 0)}")
    failures = sum(check.status == FAIL for check in checks)
    warnings = sum(check.status == WARN for check in checks)
    out(f"RESULT: {'FAIL' if failures else 'PASS'} ({failures} failed, {warnings} warnings)")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())

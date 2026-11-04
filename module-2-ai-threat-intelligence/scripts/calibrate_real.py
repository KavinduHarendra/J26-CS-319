"""Calibrate the raw-measurement detector from the known Module 1 signals.

Only ``known_signals`` is opened for measurement calibration.  Ground truth is
joined separately to define the four chronological groups required by the
evaluation protocol; it is never copied into a runtime signal.
"""

from __future__ import annotations

import argparse
import json
import os
import statistics
import sys
from dataclasses import dataclass
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.baseline import BASELINE_FEATURES, SPREAD_FLOORS, Baseline, calibrate_state
from src.real_data import Signal, load_stream
from src.scoring_data import load_ground_truth


DATA_ROOT = ROOT / "data" / "real" / "module1_signals_clean"
OUTPUT_PATH = ROOT / "config" / "thresholds_real.json"
CALIBRATION_DATE = "2026-10-25"
FEATURES = BASELINE_FEATURES
GROUPS = ("idle", "legit_ook", "CARRIER", "PULSED_50_50")
# Off for the 2026-10-23 RTL-SDR recording: its 0.1-step rounding and constant
# idle features fail Shapiro-Wilk for measurement reasons, and screening would
# roughly double the legit anomaly limit (4.98 -> 9.21).  Re-evaluate with
# --normality-screen when recalibrating from HackRF One recordings.
NORMALITY_SCREEN = False


@dataclass(frozen=True, slots=True)
class TimeSplit:
    calibration: dict[str, tuple[Signal, ...]]
    validation: dict[str, tuple[Signal, ...]]


def _group_name(signal: Signal, truth: dict[str, dict[str, str]]) -> str:
    row = truth[signal.observation_id]
    if row["normal_kind"] == "idle":
        return "idle"
    if row["normal_kind"] == "legit_ook":
        return "legit_ook"
    jammer = row["jammer_type"]
    if jammer in {"CARRIER", "PULSED_50_50"}:
        return jammer
    raise ValueError(
        f"known signal {signal.observation_id} does not belong to a calibration group"
    )


def split_known_signals(
    signals: list[Signal], truth: dict[str, dict[str, str]]
) -> TimeSplit:
    """Split each allowed group chronologically, never by random rows."""
    grouped: dict[str, list[Signal]] = {name: [] for name in GROUPS}
    for signal in signals:
        grouped[_group_name(signal, truth)].append(signal)

    calibration: dict[str, tuple[Signal, ...]] = {}
    validation: dict[str, tuple[Signal, ...]] = {}
    for name in GROUPS:
        ordered = sorted(grouped[name], key=lambda item: (item.timestamp, item.sequence_number))
        if len(ordered) < 2:
            raise ValueError(f"group {name} needs at least two chronological records")
        midpoint = len(ordered) // 2
        calibration[name] = tuple(ordered[:midpoint])
        validation[name] = tuple(ordered[midpoint:])
    return TimeSplit(calibration=calibration, validation=validation)


def _state(
    values: tuple[Signal, ...], name: str, provenance: dict[str, str], normality_screen: bool
) -> dict:
    state = calibrate_state(values, name, normality_screen=normality_screen)
    record = {
        "name": name,
        "mean": dict(state.mean),
        "spread": dict(state.spread),
        "anomaly_limit": state.anomaly_limit,
        "provenance": provenance,
    }
    if not normality_screen:
        return record
    return record | {
        "median": dict(state.median),
        "mad": dict(state.mad),
        "method": dict(state.methods),
        "normality": {
            feature: {
                "passed": result.passed,
                "test": result.test,
                "p_value": result.p_value,
                "n": result.n,
            }
            for feature, result in state.normality.items()
        },
    }


def build_configuration(
    data_root: Path = DATA_ROOT, *, normality_screen: bool = NORMALITY_SCREEN
) -> tuple[dict, TimeSplit]:
    """Return calibrated values and the auditable chronological split."""
    known_root = data_root / "known_signals"
    signals = list(load_stream(known_root))
    truth = load_ground_truth(data_root / "ground_truth.csv")
    split = split_known_signals(signals, truth)
    calibration = split.calibration

    idle = calibration["idle"]
    legitimate = calibration["legit_ook"]
    jamming = calibration["CARRIER"] + calibration["PULSED_50_50"]
    all_signals = legitimate + jamming

    t_snr = (max(signal.snr_db for signal in idle) + min(signal.snr_db for signal in all_signals)) / 2.0
    t_bw = (
        max(signal.occupied_bw_khz for signal in jamming)
        + min(signal.occupied_bw_khz for signal in legitimate)
    ) / 2.0

    provenance = {
        "source": "data/real/module1_signals_clean/known_signals",
        "split": "first chronological half of idle, legit_ook, CARRIER and PULSED_50_50",
        "date": CALIBRATION_DATE,
        "script": "scripts/calibrate_real.py",
    }
    configuration = {
        "schema_version": "1.0",
        "baseline_version": "real-raw-v1",
        "provenance": provenance,
        "features": list(FEATURES),
        "spread_floors": SPREAD_FLOORS,
        "thresholds": {
            "T_SNR": t_snr,
            "T_BW": t_bw,
            "provenance": provenance,
        },
        "normal_states": {
            "idle": _state(idle, "idle", provenance, normality_screen),
            "legit_ook": _state(legitimate, "legit_ook", provenance, normality_screen),
        },
        "split_counts": {
            name: {
                "calibration": len(split.calibration[name]),
                "validation": len(split.validation[name]),
            }
            for name in GROUPS
        },
    }
    return configuration, split


def severity_cutoffs(configuration: dict, split: TimeSplit) -> tuple[float, float]:
    """Return the 33rd/66th percentile magnitudes of calibration-half jamming.

    Magnitude is the max |x - mean| / spread distance to the nearest normal
    state.  Bottom third maps to LOW, middle to MEDIUM, top to HIGH.
    """
    baseline = Baseline.from_config(configuration)
    jamming = split.calibration["CARRIER"] + split.calibration["PULSED_50_50"]
    magnitudes = [baseline.nearest(signal)[1] for signal in jamming]
    medium_from, high_from = statistics.quantiles(magnitudes, n=3, method="inclusive")
    return medium_from, high_from


def write_configuration(configuration: dict, path: Path = OUTPUT_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(configuration, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    os.replace(temporary, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="Calibrate config/thresholds_real.json")
    parser.add_argument(
        "--normality-screen",
        action="store_true",
        help="use a robust z-score for features that fail Shapiro-Wilk",
    )
    args = parser.parse_args()
    configuration, split = build_configuration(normality_screen=args.normality_screen)
    write_configuration(configuration)
    thresholds = configuration["thresholds"]
    states = configuration["normal_states"]
    print(f"source={configuration['provenance']['source']}")
    for name in GROUPS:
        print(
            f"{name}: calibration={len(split.calibration[name])} "
            f"validation={len(split.validation[name])}"
        )
    print(f"T_SNR={thresholds['T_SNR']:.6f}")
    print(f"T_BW={thresholds['T_BW']:.6f}")
    print(f"idle_anomaly_limit={states['idle']['anomaly_limit']:.6f}")
    print(f"legit_anomaly_limit={states['legit_ook']['anomaly_limit']:.6f}")
    medium_from, high_from = severity_cutoffs(configuration, split)
    print(f"severity_medium_from={medium_from:.6f}")
    print(f"severity_high_from={high_from:.6f}")
    print(f"wrote={OUTPUT_PATH.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

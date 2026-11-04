"""Generate SYNTHETIC legitimate-link captures that degrade with UAV distance.

The 2026-10-23 Module 1 recording has no distance information, so this is a
stand-in for testing ``DistanceBandedBaseline`` until ranged recordings exist.
Each capture starts from the calibrated ``legit_ook`` state in
``config/thresholds_real.json``, assumed measured at ``REFERENCE_DISTANCE_M``,
and applies free-space path loss, 20 * log10(d / d0) dB, to peak_db, snr_db and
band_power_dbfs.  The noise floor, bandwidth and flatness are left unchanged.

Output goes to ``data/synthetic/``; never mix it into ``data/real`` or any
evaluation set.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.baseline import Baseline
from src.classifier import DEFAULT_CONFIG_PATH
from src.real_data import Signal, signal_to_record

OUTPUT_ROOT = ROOT / "data" / "synthetic" / "distance_normal"
REFERENCE_DISTANCE_M = 10.0
NOISE_DB = -106.0
NOISE_SPREAD_DB = 0.5
PEAK_FREQ_MHZ = 433.92
CAPTURE_INTERVAL_S = 0.21
START_TIME = datetime(2026, 11, 4, 10, 0, 0)
ATTENUATED = ("peak_db", "snr_db", "band_power_dbfs")


def path_loss_db(distance_m: float) -> float:
    """Free-space loss relative to the reference distance (0 dB at or inside it)."""
    return 20.0 * math.log10(max(distance_m, REFERENCE_DISTANCE_M) / REFERENCE_DISTANCE_M)


def synthetic_legit_signals(
    count: int,
    *,
    seed: int = 42,
    min_distance_m: float = REFERENCE_DISTANCE_M,
    max_distance_m: float = 400.0,
    start_sequence: int = 1,
) -> list[Signal]:
    state = Baseline.load(DEFAULT_CONFIG_PATH).legitimate
    rng = random.Random(seed)
    signals = []
    for offset in range(count):
        distance = rng.uniform(min_distance_m, max_distance_m)
        loss = path_loss_db(distance)
        values = {
            feature: state.mean[feature] + rng.gauss(0.0, state.spread[feature])
            for feature in state.mean
        }
        for feature in ATTENUATED:
            values[feature] -= loss
        sequence = start_sequence + offset
        elapsed = offset * CAPTURE_INTERVAL_S
        signals.append(
            Signal(
                observation_id=f"SYN{sequence:06d}",
                sequence_number=sequence,
                timestamp=START_TIME + timedelta(seconds=elapsed),
                elapsed_s=round(elapsed, 3),
                peak_freq_mhz=PEAK_FREQ_MHZ,
                noise_db=NOISE_DB + rng.gauss(0.0, NOISE_SPREAD_DB),
                peak_db=values["peak_db"],
                snr_db=values["snr_db"],
                band_power_dbfs=values["band_power_dbfs"],
                occupied_bw_khz=max(values["occupied_bw_khz"], 0.0),
                spectral_flatness=min(max(values["spectral_flatness"], 0.0), 1.0),
                distance_m=round(distance, 1),
            )
        )
    return signals


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--count", type=int, default=600)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--max-distance", type=float, default=400.0)
    parser.add_argument("--out", type=Path, default=OUTPUT_ROOT)
    args = parser.parse_args()

    signals = synthetic_legit_signals(
        args.count, seed=args.seed, max_distance_m=args.max_distance
    )
    args.out.mkdir(parents=True, exist_ok=True)
    for signal in signals:
        path = args.out / f"{signal.sequence_number:06d}_{signal.observation_id}.json"
        path.write_text(json.dumps(signal_to_record(signal), indent=2) + "\n", encoding="utf-8")

    snr = [signal.snr_db for signal in signals]
    print(f"wrote {len(signals)} synthetic captures to {args.out}")
    print(f"distance {REFERENCE_DISTANCE_M:g}-{args.max_distance:g} m, snr_db {min(snr):.1f}-{max(snr):.1f}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

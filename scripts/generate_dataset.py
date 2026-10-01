"""
scripts/generate_dataset.py — One-shot dataset generation script.

Generates synthetic RF observations for all three signal conditions and writes
them to data/ as UTF-8 CSV files, one row per observation, one column per field.

Output files:
    data/normal.csv           — 200 normal observations
    data/jamming.csv          —  50 jamming observations
    data/unknown_anomaly.csv  —  50 unknown-anomaly observations

Usage (from project root, with venv active):
    python scripts/generate_dataset.py [--seed SEED]

The default seed is 42 so that every run produces the identical dataset.
Pass a different integer to generate a new random dataset.
"""

import argparse
import csv
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Path setup — allow running as `python scripts/generate_dataset.py` from root
# ---------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.synthetic_data import (  # noqa: E402
    generate_normal,
    generate_jamming,
    generate_unknown_anomaly,
)
from src.schema import RFObservation  # noqa: E402

# ---------------------------------------------------------------------------
# CSV helpers
# ---------------------------------------------------------------------------

CSV_FIELDNAMES = [
    "observation_id",
    "timestamp",
    "rssi",
    "snr",
    "noise_floor",
    "packet_rate",
]


def observation_to_row(obs: RFObservation) -> dict:
    """Convert an RFObservation to a flat dict suitable for csv.DictWriter."""
    return {
        "observation_id": obs.observation_id,
        "timestamp": obs.timestamp.isoformat(),
        "rssi": obs.rssi,
        "snr": obs.snr,
        "noise_floor": obs.noise_floor,
        "packet_rate": obs.packet_rate,
    }


def write_csv(observations: list[RFObservation], path: Path) -> None:
    """Write *observations* to *path* as CSV, creating parent dirs if needed."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_FIELDNAMES)
        writer.writeheader()
        for obs in observations:
            writer.writerow(observation_to_row(obs))
    print(f"  Wrote {len(observations):>4} rows -> {path.relative_to(PROJECT_ROOT)}")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate synthetic RF observation datasets."
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="RNG seed for reproducibility (default: 42)",
    )
    args = parser.parse_args()

    seed: int = args.seed
    data_dir = PROJECT_ROOT / "data"

    print(f"Generating datasets with seed={seed} ...")

    datasets = [
        ("normal",          generate_normal(n=200, start_id=0,    seed=seed), "normal.csv"),
        ("jamming",         generate_jamming(n=50,  start_id=1000, seed=seed), "jamming.csv"),
        ("unknown_anomaly", generate_unknown_anomaly(n=50, start_id=2000, seed=seed), "unknown_anomaly.csv"),
    ]

    for label, observations, filename in datasets:
        write_csv(observations, data_dir / filename)

    total = sum(len(obs) for _, obs, _ in datasets)
    print(f"\nDone. {total} total observations written to data/")


if __name__ == "__main__":
    main()

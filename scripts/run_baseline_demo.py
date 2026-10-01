"""
scripts/run_baseline_demo.py — Normal RF Baseline Calibration Demo.

Demonstrates calibrating the statistical normal baseline using observations fetched
exclusively through the RFDataSource interface (SyntheticDataSource). No direct file
reads are performed.

Usage:
    python scripts/run_baseline_demo.py [--samples 200] [--seed 42]
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_source import RFDataSource, SyntheticDataSource
from src.baseline import NormalBaseline


def run_baseline_demo(data_source: RFDataSource, calibration_size: int = 200) -> None:
    print("=================================================================")
    print("           UAV RF THREAT INTEL - BASELINE CALIBRATION DEMO       ")
    print("=================================================================")
    print(f"Data source: {data_source.__class__.__name__}")
    print(f"Fetching batch of {calibration_size} normal samples for calibration...")

    # Fetch batch through the abstract RFDataSource interface
    calibration_batch = data_source.fetch_batch(calibration_size)
    print(f"Received {len(calibration_batch)} observations.")

    baseline = NormalBaseline()
    baseline.add_normal_samples(calibration_batch)
    baseline.calibrate()

    print("\n--- Calibrated Feature Baseline Statistics (mean, std) ---")
    for feature in NormalBaseline.FEATURES:
        fb = baseline.baseline[feature]
        unit = "dBm" if "rssi" in feature or "noise" in feature else ("dB" if "snr" in feature else "pkts/s")
        print(f"  {feature:<15}: mean = {fb.mean:>8.2f} {unit:<6} | std = {fb.std:>6.2f} {unit}")

    # Fetch a small test batch to demonstrate z-score computation
    test_count = 5
    print(f"\nFetching test batch of {test_count} observations to compute z-scores...")
    test_batch = data_source.fetch_batch(test_count)

    print("\n--- Test Observations & Computed Z-Scores ---")
    for i, obs in enumerate(test_batch, 1):
        z = baseline.z_scores(obs)
        dev = baseline.deviations(obs)
        print(f"\n[Sample #{i}] ID: {obs.observation_id}")
        print(f"  Physical: rssi={obs.rssi:.1f} dBm, snr={obs.snr:.1f} dB, "
              f"noise={obs.noise_floor:.1f} dBm, rate={obs.packet_rate:.1f} pkts/s")
        print(f"  z-scores: rssi={z['rssi']:+.2f}, snr={z['snr']:+.2f}, "
              f"noise={z['noise_floor']:+.2f}, rate={z['packet_rate']:+.2f}")
        print(f"  snr_drop = {dev['snr_drop']:.2f}, noise_increase = {dev['noise_floor_increase']:.2f}")

    print("\nBaseline demonstration completed successfully.")


def main():
    parser = argparse.ArgumentParser(description="Demonstrate NormalBaseline calibration via RFDataSource.")
    parser.add_argument("--samples", type=int, default=200, help="Number of normal samples for calibration (default: 200)")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility (default: 42)")
    args = parser.parse_args()

    # Ingest data purely through RFDataSource
    source: RFDataSource = SyntheticDataSource(scenario="normal", seed=args.seed)
    run_baseline_demo(source, calibration_size=args.samples)


if __name__ == "__main__":
    main()

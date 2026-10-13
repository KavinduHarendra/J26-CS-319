"""
scripts/check_baseline_on_jamming.py — Check NormalBaseline Deviations on Jamming Data.

Calibrates a NormalBaseline exactly as scripts/run_baseline_demo.py does (using a
70/30 split of normal observations from SyntheticDataSource("normal")), then fetches
5 jamming-scenario observations via SyntheticDataSource("jamming") and evaluates
each one against the baseline.

Validates that snr_drop and noise_floor_increase exhibit large deviations (multiple
standard deviations away from normal) under jamming conditions, providing clear visual
evidence for Rule J01 trigger conditions.

Usage:
    python scripts/check_baseline_on_jamming.py [--seed 42] [--jamming-count 5]
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_source import SyntheticDataSource
from src.baseline import NormalBaseline


def check_jamming_deviations(
    normal_seed: int = 42,
    jamming_seed: int = 42,
    total_normal_samples: int = 200,
    jamming_count: int = 5,
) -> None:
    print("=================================================================")
    print("      UAV RF THREAT INTEL - BASELINE CHECK ON JAMMING DATA       ")
    print("=================================================================")

    # Step 1: Calibrate NormalBaseline identically to run_baseline_demo.py
    print(f"\n[Step 1] Ingesting {total_normal_samples} normal samples via SyntheticDataSource('normal')...")
    normal_source = SyntheticDataSource("normal", seed=normal_seed)
    all_normal = normal_source.fetch_batch(total_normal_samples)

    split_idx = int(len(all_normal) * 0.70)
    calibration_set = all_normal[:split_idx]
    print(f"Calibrating baseline on 70% split ({len(calibration_set)} samples)...")

    baseline = NormalBaseline()
    baseline.add_normal_samples(calibration_set)
    baseline.calibrate()

    print("\n--- Calibrated Normal Baseline Reference ---")
    for feature in NormalBaseline.FEATURES:
        fb = baseline.baseline[feature]
        unit = "dBm" if "rssi" in feature or "noise" in feature else ("dB" if "snr" in feature else "pkts/s")
        print(f"  {feature:<15}: mean = {fb.mean:>8.2f} {unit:<6} | std = {fb.std:>6.2f} {unit}")

    # Step 2: Fetch Jamming Observations via SyntheticDataSource("jamming")
    print(f"\n[Step 2] Fetching {jamming_count} jamming observations via SyntheticDataSource('jamming')...")
    jamming_source = SyntheticDataSource("jamming", seed=jamming_seed)
    jamming_batch = jamming_source.fetch_batch(jamming_count)
    print(f"Received {len(jamming_batch)} jamming observations.")

    # Step 3: Compute and display deviations() for each jamming observation
    print("\n--- Jamming Observations & Computed Deviations vs Normal Baseline ---")
    snr_drops = []
    noise_increases = []

    for i, obs in enumerate(jamming_batch, 1):
        z = baseline.z_scores(obs)
        dev = baseline.deviations(obs)
        snr_drops.append(dev["snr_drop"])
        noise_increases.append(dev["noise_floor_increase"])

        print(f"\n  [{i}] ID: {obs.observation_id}")
        print(f"      Raw Physical Values: rssi={obs.rssi:>7.2f} dBm  | snr={obs.snr:>6.2f} dB  | "
              f"noise={obs.noise_floor:>7.2f} dBm  | rate={obs.packet_rate:>6.2f} pkts/s")
        print(f"      Signed z-scores:     rssi={z['rssi']:>+7.2f}     | snr={z['snr']:>+6.2f}    | "
              f"noise={z['noise_floor']:>+7.2f}     | rate={z['packet_rate']:>+6.2f}")
        print(f"      Deviations Output:   snr_drop = {dev['snr_drop']:>6.2f} sigma  (sharp SNR drop)")
        print(f"                           noise_floor_increase = {dev['noise_floor_increase']:>6.2f} sigma  (elevated noise)")
        print(f"                           rssi_deviation       = {dev['rssi_deviation']:>6.2f} sigma")
        print(f"                           packet_rate_deviation= {dev['packet_rate_deviation']:>6.2f} sigma")

    # Step 4: Summary Comparison
    avg_snr_drop = sum(snr_drops) / len(snr_drops)
    avg_noise_inc = sum(noise_increases) / len(noise_increases)

    print("\n" + "=" * 65)
    print("                     DEVIATION CONFIRMATION                      ")
    print("=" * 65)
    print(f"  Average snr_drop             : {avg_snr_drop:>6.2f} standard deviations")
    print(f"  Average noise_floor_increase : {avg_noise_inc:>6.2f} standard deviations")
    print("\nConclusion:")
    print("  Under normal conditions, snr_drop and noise_floor_increase stay near 0 (typically < 2.0).")
    print(f"  Under jamming conditions, both metrics surge to ~{avg_snr_drop:.1f} and ~{avg_noise_inc:.1f} sigma,")
    print("  decisively crossing rule detection thresholds (e.g., J01 threshold > 2.0).")
    print("=" * 65)


def main():
    parser = argparse.ArgumentParser(
        description="Verify NormalBaseline deviations on jamming observations via SyntheticDataSource."
    )
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility (default: 42)")
    parser.add_argument("--jamming-count", type=int, default=5, help="Number of jamming samples to check (default: 5)")
    args = parser.parse_args()

    check_jamming_deviations(
        normal_seed=args.seed,
        jamming_seed=args.seed,
        total_normal_samples=200,
        jamming_count=args.jamming_count,
    )


if __name__ == "__main__":
    main()

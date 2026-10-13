"""
scripts/run_baseline_demo.py — Normal RF Baseline Calibration Demo (70/30 Split).

Fetches synthetic normal observations through SyntheticDataSource (RFDataSource),
splits them 70/30 into a calibration set and a held-out evaluation set, calibrates
NormalBaseline on the 70% split, validates Gaussian distribution assumptions via the
Shapiro-Wilk normality check, and prints z-scores and deviations for 5 sample
observations from the 30% held-out split.

Per Section 3.10 of the Implementation Guide: calibration data and evaluation data
MUST be separate to avoid testing on the same data used for baselining.
Per Section 13.4: features failing the normality check should switch to robust_z_score().

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
from src.normality_check import check_normality


def run_baseline_demo(data_source: RFDataSource, total_samples: int = 200) -> None:
    print("=================================================================")
    print("       UAV RF THREAT INTEL - BASELINE CALIBRATION DEMO           ")
    print("             (70% Calibration / 30% Held-Out Split)              ")
    print("=================================================================")
    print(f"Data source: {data_source.__class__.__name__}")
    print(f"Fetching {total_samples} normal observations...")

    # Fetch the full normal dataset through the RFDataSource interface
    all_observations = data_source.fetch_batch(total_samples)
    print(f"Received {len(all_observations)} observations.\n")

    # 70/30 split — calibration vs. held-out evaluation
    split_idx = int(len(all_observations) * 0.70)
    calibration_set = all_observations[:split_idx]
    evaluation_set = all_observations[split_idx:]

    print(f"Split: {len(calibration_set)} calibration ({len(calibration_set)/len(all_observations)*100:.0f}%)"
          f" / {len(evaluation_set)} held-out evaluation ({len(evaluation_set)/len(all_observations)*100:.0f}%)")

    # Calibrate NormalBaseline on the 70% split ONLY
    baseline = NormalBaseline()
    baseline.add_normal_samples(calibration_set)
    baseline.calibrate()

    print("\n--- Calibrated Feature Baseline Statistics (mean, std) ---")
    print(f"  {'Feature':<15}  {'Mean':>10}  {'Std':>10}  {'Unit':<6}  {'Samples':>7}")
    print("  " + "-" * 60)
    for feature in NormalBaseline.FEATURES:
        fb = baseline.baseline[feature]
        unit = "dBm" if "rssi" in feature or "noise" in feature else ("dB" if "snr" in feature else "pkts/s")
        print(f"  {feature:<15}  {fb.mean:>10.4f}  {fb.std:>10.4f}  {unit:<6}  {len(calibration_set):>7}")

    # Normality validation on the calibration split (Section 13.4)
    print("\n--- Shapiro-Wilk Normality Check on Calibration Split (alpha=0.05) ---")
    normality_results: dict[str, bool] = {}
    for feature in NormalBaseline.FEATURES:
        samples = [float(getattr(obs, feature)) for obs in calibration_set]
        normality_results[feature] = check_normality(samples, feature, alpha=0.05)

    print("\n  Summary of Normality Assumptions:")
    print(f"  {'Feature':<15}  {'Status':<10}  {'Recommendation'}")
    print("  " + "-" * 65)
    for feature, passed in normality_results.items():
        status = "PASSED" if passed else "FAILED"
        rec = "Standard z-score appropriate" if passed else "Switch to robust_z_score() (median/MAD)"
        print(f"  {feature:<15}  {status:<10}  {rec}")

    # Section 13.4 Note regarding failed features
    failed_features = [f for f, p in normality_results.items() if not p]
    if failed_features:
        print(f"\n  [NOTE] Features failing normality: {failed_features}.")
        print("         Any feature that fails should have its z_scores() computation in")
        print("         baseline.py switched to use robust_z_score() instead of the standard formula.")
    else:
        print("\n  [NOTE] All features passed the Shapiro-Wilk test (Gaussian assumption holds).")
        print("         If any future feature fails normality, its z_scores() computation in")
        print("         baseline.py should be switched to use robust_z_score() (Section 13.4).")

    # Show z-scores and deviations for 5 observations from the HELD-OUT 30% split
    demo_count = min(5, len(evaluation_set))
    print(f"\n--- Held-Out Evaluation: z-scores & deviations for {demo_count} samples ---")
    print(f"  (These {demo_count} observations were NOT used for calibration)\n")

    for i, obs in enumerate(evaluation_set[:demo_count], 1):
        z = baseline.z_scores(obs)
        dev = baseline.deviations(obs)

        print(f"  [{i}] ID: {obs.observation_id}")
        print(f"      Raw values:  rssi={obs.rssi:>8.2f} dBm  |  snr={obs.snr:>7.2f} dB  |  "
              f"noise={obs.noise_floor:>8.2f} dBm  |  rate={obs.packet_rate:>7.2f} pkts/s")
        print(f"      z-scores:    rssi={z['rssi']:>+7.2f}      |  snr={z['snr']:>+7.2f}     |  "
              f"noise={z['noise_floor']:>+7.2f}      |  rate={z['packet_rate']:>+7.2f}")
        print(f"      Deviations:  snr_drop={dev['snr_drop']:.2f}  |  rssi_dev={dev['rssi_deviation']:.2f}  |  "
              f"noise_inc={dev['noise_floor_increase']:.2f}  |  rate_dev={dev['packet_rate_deviation']:.2f}")
        print()

    # Quick sanity check: z-scores on held-out normal data should be small
    all_z = [baseline.z_scores(obs) for obs in evaluation_set]
    for feature in NormalBaseline.FEATURES:
        mean_abs_z = sum(abs(z[feature]) for z in all_z) / len(all_z)
        print(f"  Mean |z| on held-out set for {feature:<15}: {mean_abs_z:.3f}")

    print("\nBaseline demonstration completed successfully.")
    print("Calibration and evaluation sets are independent (Section 3.10 compliant).")


def main():
    parser = argparse.ArgumentParser(description="Demonstrate NormalBaseline calibration via RFDataSource with 70/30 split.")
    parser.add_argument("--samples", type=int, default=200, help="Total normal samples to fetch (default: 200)")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility (default: 42)")
    args = parser.parse_args()

    # Ingest data purely through RFDataSource — never read CSV files
    source: RFDataSource = SyntheticDataSource(scenario="normal", seed=args.seed)
    run_baseline_demo(source, total_samples=args.samples)


if __name__ == "__main__":
    main()

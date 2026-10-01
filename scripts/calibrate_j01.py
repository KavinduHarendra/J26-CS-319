"""
scripts/calibrate_j01.py — Calibration script for Rule J01 (SNR Drop + Noise Floor Rise).

Performs empirical threshold sweep over validation data fetched exclusively via
RFDataSource (SyntheticDataSource). Evaluates TPR (Recall on Jamming) and FPR (False
Alarms on Normal) to determine defensible thresholds per Section 3.5 & 13.1 of the
Implementation Guide.

Usage:
    python scripts/calibrate_j01.py [--seed 42]
"""

import argparse
import sys
from pathlib import Path

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data_source import RFDataSource, SyntheticDataSource
from src.baseline import NormalBaseline
from src.rule_engine import Rule, RuleBasedJammingDetector


def evaluate_threshold(
    detector: RuleBasedJammingDetector,
    baseline: NormalBaseline,
    normal_eval: list,
    jamming_eval: list,
) -> tuple[float, float, float]:
    """Calculate TPR (Jamming Recall), FPR (Normal False Alarms), and Youden's J."""
    # Jamming evaluation (True Positives)
    jamming_hits = 0
    for obs in jamming_eval:
        dev = baseline.deviations(obs)
        if detector.evaluate(dev) is not None:
            jamming_hits += 1
    tpr = jamming_hits / len(jamming_eval) if jamming_eval else 0.0

    # Normal evaluation (False Positives)
    normal_false_alarms = 0
    for obs in normal_eval:
        dev = baseline.deviations(obs)
        if detector.evaluate(dev) is not None:
            normal_false_alarms += 1
    fpr = normal_false_alarms / len(normal_eval) if normal_eval else 0.0

    youden_j = tpr - fpr
    return tpr, fpr, youden_j


def run_calibration(
    normal_source: RFDataSource,
    jamming_source: RFDataSource,
    calib_samples: int = 200,
    eval_samples: int = 50,
) -> None:
    print("=================================================================")
    print("         UAV RF THREAT INTEL - RULE J01 THRESHOLD CALIBRATION    ")
    print("=================================================================")
    print("Ingesting observations via RFDataSource instances...")

    # Step 1: Baseline Calibration using training normal data
    calib_batch = normal_source.fetch_batch(calib_samples)
    baseline = NormalBaseline()
    baseline.add_normal_samples(calib_batch)
    baseline.calibrate()
    print(f"Normal baseline calibrated with {len(calib_batch)} samples.")

    # Step 2: Ingest validation sets
    normal_eval = normal_source.fetch_batch(eval_samples)
    jamming_eval = jamming_source.fetch_batch(eval_samples)
    print(f"Validation sets fetched: {len(normal_eval)} Normal, {len(jamming_eval)} Jamming.")

    # Step 3: Threshold sweep over SNR drop and Noise Floor increase thresholds
    candidate_thresholds = [1.0, 1.5, 2.0, 2.5, 3.0, 3.5, 4.0]

    print("\n--- Threshold Sweep Table (Rule J01: snr_drop > T and noise_increase > T) ---")
    print(f"{'Threshold (T)':<15} | {'Jamming Recall (TPR)':<22} | {'Normal FPR':<12} | {'Youden J (TPR-FPR)':<18}")
    print("-" * 75)

    best_thresh = 2.0
    best_j = -1.0

    for thresh in candidate_thresholds:
        # Build test detector with candidate threshold
        test_detector = RuleBasedJammingDetector()
        test_detector.register(
            Rule(
                rule_id="J01",
                description=f"Significant SNR drop (> {thresh}) and noise floor rise (> {thresh})",
                condition=lambda d, t=thresh: d["snr_drop"] > t and d["noise_floor_increase"] > t,
            )
        )

        tpr, fpr, youden_j = evaluate_threshold(test_detector, baseline, normal_eval, jamming_eval)
        print(f"  T = {thresh:<10.1f} | {tpr:>20.1%} | {fpr:>10.1%} | {youden_j:>16.3f}")

        if youden_j > best_j:
            best_j = youden_j
            best_thresh = thresh

    print("-" * 75)
    print(f"Optimal Threshold Selected: T = {best_thresh:.1f} (Youden's J = {best_j:.3f})")
    print("Calibration procedure completed.")


def main():
    parser = argparse.ArgumentParser(description="Calibrate Rule J01 thresholds via RFDataSource.")
    parser.add_argument("--seed", type=int, default=42, help="RNG seed for reproducibility (default: 42)")
    args = parser.parse_args()

    # Data obtained exclusively via RFDataSource
    normal_source = SyntheticDataSource(scenario="normal", seed=args.seed)
    jamming_source = SyntheticDataSource(scenario="jamming", seed=args.seed + 10)

    run_calibration(normal_source, jamming_source)


if __name__ == "__main__":
    main()

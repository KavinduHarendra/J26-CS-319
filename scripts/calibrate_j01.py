"""
scripts/calibrate_j01.py — Empirical threshold calibration for Rules J01 and J02.

Loads Normal and Jamming datasets from data/, computes baseline deviations,
runs joint 2D grid search over (snr_thresh, noise_thresh) for Rule J01, and
runs Youden's J ROC optimization for Rule J02's (rssi_thresh, packet_thresh).

Outputs the calibrated optimal thresholds compared against the initial placeholders.
"""

import csv
import sys
from datetime import datetime
from pathlib import Path
import numpy as np
from sklearn.metrics import f1_score

# Add project root to sys.path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.schema import RFObservation
from src.baseline import NormalBaseline
from src.calibrate_thresholds import (
    calibrate_threshold_pair_grid_search,
    calibrate_threshold_youden,
)


def load_observations_from_csv(csv_path: Path) -> list[RFObservation]:
    """Load RFObservation instances from a dataset CSV file."""
    if not csv_path.exists():
        raise FileNotFoundError(f"Dataset file not found: {csv_path}")

    observations = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            obs = RFObservation(
                observation_id=row["observation_id"],
                timestamp=datetime.fromisoformat(row["timestamp"]),
                rssi=float(row["rssi"]),
                snr=float(row["snr"]),
                noise_floor=float(row["noise_floor"]),
                packet_rate=float(row["packet_rate"]),
            )
            observations.append(obs)
    return observations


def main() -> None:
    print("=================================================================")
    print("    UAV RF THREAT INTEL - THRESHOLD CALIBRATION (J01 & J02)      ")
    print("=================================================================")

    data_dir = PROJECT_ROOT / "data"
    normal_csv = data_dir / "normal.csv"
    jamming_csv = data_dir / "jamming.csv"

    print(f"Loading datasets from {data_dir.relative_to(PROJECT_ROOT)}...")
    normal_obs = load_observations_from_csv(normal_csv)
    jamming_obs = load_observations_from_csv(jamming_csv)
    print(f"Loaded {len(normal_obs)} normal observations and {len(jamming_obs)} jamming observations.")

    # 1. Calibrate baseline using normal data
    print("\nCalibrating NormalBaseline on normal.csv samples...")
    baseline = NormalBaseline()
    baseline.add_normal_samples(normal_obs)
    baseline.calibrate()

    # 2. Compute deviations for all observations
    normal_devs = [baseline.deviations(obs) for obs in normal_obs]
    jamming_devs = [baseline.deviations(obs) for obs in jamming_obs]

    all_devs = normal_devs + jamming_devs
    true_labels = [0] * len(normal_devs) + [1] * len(jamming_devs)

    # Extract distinct feature deviation arrays
    snr_drop_scores = [d["snr_drop"] for d in all_devs]
    noise_increase_scores = [d["noise_floor_increase"] for d in all_devs]
    rssi_dev_scores = [d["rssi_deviation"] for d in all_devs]
    packet_dev_scores = [d["packet_rate_deviation"] for d in all_devs]

    # ---------------------------------------------------------------------------
    # Step A: Joint 2D Grid Search Calibration for Rule J01
    # ---------------------------------------------------------------------------
    print("\n=================================================================")
    print(" [Part 1] Joint 2D Grid Search for Rule J01 (SNR Drop & Noise)")
    print("=================================================================")
    snr_candidates = np.arange(1.0, 4.01, 0.25)
    noise_candidates = np.arange(1.0, 4.01, 0.25)

    best_snr_t, best_noise_t, best_f1_j01 = calibrate_threshold_pair_grid_search(
        snr_drop_scores=snr_drop_scores,
        noise_increase_scores=noise_increase_scores,
        true_labels=true_labels,
        snr_candidates=snr_candidates,
        noise_candidates=noise_candidates,
    )

    # Baseline placeholder F1 for J01
    placeholder_preds_j01 = [
        (s > 2.0) and (n > 2.0) for s, n in zip(snr_drop_scores, noise_increase_scores)
    ]
    placeholder_f1_j01 = f1_score(true_labels, placeholder_preds_j01)

    print("\n--- Rule J01 Calibration Comparison ---")
    print(f"  Placeholder Thresholds : snr_thresh = 2.00, noise_thresh = 2.00 -> F1 = {placeholder_f1_j01:.4f}")
    print(f"  Calibrated Thresholds  : snr_thresh = {best_snr_t:.2f}, noise_thresh = {best_noise_t:.2f} -> F1 = {best_f1_j01:.4f}")

    # ---------------------------------------------------------------------------
    # Step B: Single-Feature Youden's J Optimization for Rule J02
    # ---------------------------------------------------------------------------
    print("\n=================================================================")
    print(" [Part 2] Youden's J ROC Calibration for Rule J02 (RSSI & Packet Rate)")
    print("=================================================================")
    calibrated_rssi_t = calibrate_threshold_youden(rssi_dev_scores, true_labels)
    calibrated_packet_t = calibrate_threshold_youden(packet_dev_scores, true_labels)

    # Evaluate combined F1 with calibrated J02 thresholds
    calibrated_preds_j02 = [
        (r > calibrated_rssi_t) and (p > calibrated_packet_t)
        for r, p in zip(rssi_dev_scores, packet_dev_scores)
    ]
    calibrated_f1_j02 = f1_score(true_labels, calibrated_preds_j02)

    # Baseline placeholder F1 for J02 (2.5, 2.5)
    placeholder_preds_j02 = [
        (r > 2.5) and (p > 2.5)
        for r, p in zip(rssi_dev_scores, packet_dev_scores)
    ]
    placeholder_f1_j02 = f1_score(true_labels, placeholder_preds_j02)

    print(f"  Calibrated rssi_thresh   (Youden J) : {calibrated_rssi_t:.2f}")
    print(f"  Calibrated packet_thresh (Youden J) : {calibrated_packet_t:.2f}")
    print("\n--- Rule J02 Calibration Comparison ---")
    print(f"  Placeholder Thresholds : rssi_thresh = 2.50, packet_thresh = 2.50 -> F1 = {placeholder_f1_j02:.4f}")
    print(f"  Calibrated Thresholds  : rssi_thresh = {calibrated_rssi_t:.2f}, packet_thresh = {calibrated_packet_t:.2f} -> F1 = {calibrated_f1_j02:.4f}")

    # ---------------------------------------------------------------------------
    # Final Recommended Updates for src/rule_engine.py
    # ---------------------------------------------------------------------------
    print("\n=================================================================")
    print("                   FINAL CALIBRATION SUMMARY                     ")
    print("=================================================================")
    print("Recommended parameters for build_default_ruleset():")
    print(f"  snr_thresh    = {best_snr_t:.2f}")
    print(f"  noise_thresh  = {best_noise_t:.2f}")
    print(f"  rssi_thresh   = {calibrated_rssi_t:.2f}")
    print(f"  packet_thresh = {calibrated_packet_t:.2f}")
    print("=================================================================")


if __name__ == "__main__":
    main()

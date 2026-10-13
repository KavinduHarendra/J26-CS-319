"""
calibrate_thresholds.py — Calibration procedures for rule detection thresholds.

Implements:
  1. calibrate_threshold_youden: Single-feature ROC curve threshold optimization
     maximizing Youden's J statistic (TPR - FPR).
  2. calibrate_threshold_pair_grid_search: Joint 2D grid search over paired
     thresholds (such as J01's snr_drop and noise_floor_increase) maximizing F1 score.
"""

from typing import Iterable, Sequence
import numpy as np
from sklearn.metrics import roc_curve, f1_score


def calibrate_threshold_youden(
    deviation_scores: Sequence[float],
    true_labels: Sequence[int],
) -> float:
    """
    Find the threshold that maximizes Youden's J statistic (TPR - FPR) via ROC curve.

    Used for single-threshold rules (e.g., calibrating J02's rssi_thresh or packet_thresh).

    Args:
        deviation_scores: 1D array-like of feature deviation scores.
        true_labels: 1D array-like of binary ground truth labels (0=Normal, 1=Threat).

    Returns:
        The threshold value maximizing TPR - FPR.
    """
    scores_arr = np.asarray(deviation_scores, dtype=float)
    labels_arr = np.asarray(true_labels, dtype=int)

    fpr, tpr, thresholds = roc_curve(labels_arr, scores_arr)
    j_scores = tpr - fpr

    best_idx = int(np.argmax(j_scores))
    best_thresh = float(thresholds[best_idx])

    # If thresholds[0] was set to max(score) + 1 by roc_curve, clamp to max finite score
    if np.isinf(best_thresh) or best_thresh > np.max(scores_arr):
        finite_thresh = thresholds[~np.isinf(thresholds)]
        best_thresh = float(np.max(finite_thresh)) if len(finite_thresh) > 0 else float(np.max(scores_arr))

    return round(best_thresh, 4)


def calibrate_threshold_pair_grid_search(
    snr_drop_scores: Sequence[float],
    noise_increase_scores: Sequence[float],
    true_labels: Sequence[int],
    snr_candidates: Iterable[float],
    noise_candidates: Iterable[float],
) -> tuple[float, float, float]:
    """
    Perform a joint 2D grid search over (snr_thresh, noise_thresh) candidate pairs.

    Because Rule J01 requires BOTH snr_drop > snr_thresh AND noise_floor_increase > noise_thresh,
    the two thresholds are coupled and cannot be calibrated independently.

    For every (snr_t, noise_t) pair:
      preds = (snr_drop_scores > snr_t) AND (noise_increase_scores > noise_t)
      f1 = f1_score(true_labels, preds)

    Prints a 2D summary grid table and returns the best combination.

    Args:
        snr_drop_scores: Array of snr_drop deviation values.
        noise_increase_scores: Array of noise_floor_increase deviation values.
        true_labels: Array of binary ground truth labels (0=Normal, 1=Jamming).
        snr_candidates: Iterable of candidate thresholds for snr_drop.
        noise_candidates: Iterable of candidate thresholds for noise_floor_increase.

    Returns:
        tuple of (best_snr_thresh, best_noise_thresh, best_f1)
    """
    snr_arr = np.asarray(snr_drop_scores, dtype=float)
    noise_arr = np.asarray(noise_increase_scores, dtype=float)
    labels_arr = np.asarray(true_labels, dtype=int)

    snr_list = [round(float(s), 2) for s in snr_candidates]
    noise_list = [round(float(n), 2) for n in noise_candidates]

    grid_f1 = np.zeros((len(snr_list), len(noise_list)), dtype=float)

    best_snr = snr_list[0]
    best_noise = noise_list[0]
    best_f1 = -1.0

    # Collect all pairs achieving the maximum F1 to choose a central, robust operating point
    optimal_pairs = []

    for i, s_t in enumerate(snr_list):
        for j, n_t in enumerate(noise_list):
            preds = (snr_arr > s_t) & (noise_arr > n_t)
            score = float(f1_score(labels_arr, preds, zero_division=0))
            grid_f1[i, j] = score

            if score > best_f1:
                best_f1 = score
                optimal_pairs = [(s_t, n_t)]
            elif score == best_f1 and score > 0.0:
                optimal_pairs.append((s_t, n_t))

    # Pick the median/central pair among ties for maximum noise margin
    if optimal_pairs:
        mid_idx = len(optimal_pairs) // 2
        best_snr, best_noise = optimal_pairs[mid_idx]

    # Print 2D Grid Table
    print("\n--- Joint 2D Grid Search F1 Table (Rows: SNR Drop Thresh | Cols: Noise Floor Thresh) ---")
    header = f"{'SNR \\ Noise':<12} | " + " ".join(f"{n:>6.2f}" for n in noise_list)
    print(header)
    print("-" * len(header))

    for i, s_t in enumerate(snr_list):
        row_str = f"  {s_t:<10.2f} | " + " ".join(f"{grid_f1[i, j]:>6.3f}" for j in range(len(noise_list)))
        print(row_str)

    print("-" * len(header))
    print(f"Optimal Pair: snr_thresh = {best_snr:.2f}, noise_thresh = {best_noise:.2f} (F1 = {best_f1:.4f})")
    if len(optimal_pairs) > 1:
        print(f"  Note: {len(optimal_pairs)} candidate pairs achieved max F1 = {best_f1:.4f}. Selected central robust pair.")

    return best_snr, best_noise, best_f1

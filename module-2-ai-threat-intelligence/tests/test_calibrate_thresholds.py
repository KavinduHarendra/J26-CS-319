"""
tests/test_calibrate_thresholds.py — Unit tests for threshold calibration algorithms.

Verifies:
  - calibrate_threshold_youden finds the optimal single-feature threshold maximizing TPR - FPR.
  - calibrate_threshold_pair_grid_search evaluates the 2D grid and selects the best F1 pair.
"""

import numpy as np
import pytest

from src.calibrate_thresholds import (
    calibrate_threshold_youden,
    calibrate_threshold_pair_grid_search,
)


class TestCalibrateThresholdYouden:
    def test_cleanly_separated_distributions(self):
        # 50 normals around 0.0-1.0, 50 threats around 4.0-5.0
        negatives = [0.2, 0.5, 0.8, 1.0, 1.2] * 10
        positives = [4.0, 4.2, 4.5, 4.8, 5.0] * 10
        scores = negatives + positives
        labels = [0] * len(negatives) + [1] * len(positives)

        best_thresh = calibrate_threshold_youden(scores, labels)
        # Threshold should sit cleanly in the gap between 1.2 and 4.0
        assert 1.2 <= best_thresh <= 4.0


class TestCalibrateThresholdPairGridSearch:
    def test_joint_and_condition_optimization(self):
        # Threat occurs ONLY when feature A > 2.0 AND feature B > 2.0
        # Normal samples have either A low, B low, or both low
        a_scores = [0.5, 3.0, 0.5, 3.5, 4.0]
        b_scores = [0.5, 0.5, 3.0, 3.8, 4.2]
        # Only samples 3 and 4 are true threats (index 3 and 4)
        labels = [0, 0, 0, 1, 1]

        candidates = [1.0, 2.0, 3.0]
        best_a, best_b, best_f1 = calibrate_threshold_pair_grid_search(
            snr_drop_scores=a_scores,
            noise_increase_scores=b_scores,
            true_labels=labels,
            snr_candidates=candidates,
            noise_candidates=candidates,
        )

        assert best_f1 == 1.0
        assert best_a == 2.0 or best_a == 3.0
        assert best_b == 2.0 or best_b == 3.0

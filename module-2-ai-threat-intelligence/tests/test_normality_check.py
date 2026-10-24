"""
tests/test_normality_check.py — Unit tests for src/normality_check.py.

Verifies:
  - check_normality() returns True on Gaussian samples and False on non-Gaussian samples.
  - robust_z_score() produces expected values on hand-calculated distributions.
  - robust_z_score() handles zero-MAD edge case without division by zero.
"""

import math
import random
import pytest

from src.normality_check import check_normality, robust_z_score


class TestCheckNormality:
    def test_gaussian_samples_pass(self):
        rng = random.Random(42)
        gaussian_samples = [rng.gauss(25.0, 2.0) for _ in range(100)]
        result = check_normality(gaussian_samples, "snr_normal", alpha=0.05)
        assert result is True

    def test_skewed_samples_fail(self):
        # Strongly skewed distribution (exponential)
        rng = random.Random(42)
        skewed_samples = [rng.expovariate(0.5) for _ in range(100)]
        result = check_normality(skewed_samples, "skewed_feature", alpha=0.05)
        assert result is False

    def test_uniform_samples_fail(self):
        rng = random.Random(42)
        uniform_samples = [rng.uniform(-10.0, 10.0) for _ in range(100)]
        result = check_normality(uniform_samples, "uniform_feature", alpha=0.05)
        assert result is False


class TestRobustZScore:
    def test_value_at_median_is_zero(self):
        samples = [10.0, 20.0, 30.0, 40.0, 50.0]  # median = 30
        assert robust_z_score(30.0, samples) == pytest.approx(0.0)

    def test_hand_calculated_robust_z(self):
        # samples: [10, 12, 14, 16, 18]
        # median = 14
        # absolute deviations: [4, 2, 0, 2, 4] -> sorted: [0, 2, 2, 4, 4] -> median MAD = 2.0
        # for x = 16: z = 0.6745 * (16 - 14) / 2.0 = 0.6745
        samples = [10.0, 12.0, 14.0, 16.0, 18.0]
        z = robust_z_score(16.0, samples)
        assert z == pytest.approx(0.6745, abs=1e-4)

    def test_negative_deviation(self):
        # for x = 12: z = 0.6745 * (12 - 14) / 2.0 = -0.6745
        samples = [10.0, 12.0, 14.0, 16.0, 18.0]
        z = robust_z_score(12.0, samples)
        assert z == pytest.approx(-0.6745, abs=1e-4)

    def test_zero_mad_clamped_no_division_by_zero(self):
        # All samples identical -> MAD = 0.0 -> clamped to 1e-6
        samples = [42.0, 42.0, 42.0, 42.0]
        z = robust_z_score(42.0, samples)
        assert z == pytest.approx(0.0)

        # non-zero x - median with clamped MAD
        z_offset = robust_z_score(43.0, samples)
        assert math.isfinite(z_offset)
        assert z_offset > 0.0

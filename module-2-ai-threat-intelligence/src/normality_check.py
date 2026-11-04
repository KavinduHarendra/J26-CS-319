"""Per-feature normality screening and the robust z-score used when it fails."""

from __future__ import annotations

import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass

from scipy import stats


ALPHA = 0.05
MIN_SAMPLES = 3
MAX_SAMPLES = 5000  # Shapiro-Wilk p-values are unreliable above this size
MODIFIED_Z_FACTOR = 0.6745  # Iglewicz & Hoaglin: MAD / 0.6745 estimates sigma


@dataclass(frozen=True, slots=True)
class NormalityResult:
    passed: bool
    test: str  # "shapiro", "constant" or "too_few"
    p_value: float | None
    n: int


def check_normality(values: Sequence[float], alpha: float = ALPHA) -> NormalityResult:
    """Shapiro-Wilk screen; constant data fails, fewer than 3 values cannot be tested."""
    data = [float(value) for value in values]
    n = len(data)
    if n < MIN_SAMPLES:
        return NormalityResult(passed=True, test="too_few", p_value=None, n=n)
    if len(set(data)) == 1:
        return NormalityResult(passed=False, test="constant", p_value=None, n=n)
    sample = data if n <= MAX_SAMPLES else data[:: math.ceil(n / MAX_SAMPLES)]
    p_value = float(stats.shapiro(sample).pvalue)
    return NormalityResult(passed=p_value >= alpha, test="shapiro", p_value=p_value, n=n)


def median_absolute_deviation(values: Sequence[float]) -> tuple[float, float]:
    """Return (median, MAD) of *values*."""
    median = statistics.median(values)
    return median, statistics.median(abs(value - median) for value in values)


def robust_z_score(value: float, median: float, mad: float) -> float:
    """Modified z-score 0.6745 * (x - median) / MAD."""
    if not mad > 0.0:
        raise ValueError("MAD must be positive")
    return MODIFIED_Z_FACTOR * (value - median) / mad

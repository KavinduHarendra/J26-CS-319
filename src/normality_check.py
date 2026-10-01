"""
normality_check.py — Statistical normality validation and robust z-score calculation.

Validates the Gaussian distribution assumption (Section 13.4 of the Implementation Guide)
via the Shapiro-Wilk test. If a feature deviates significantly from normality (p < alpha),
it flags the need for robust median/MAD-based z-score scaling.
"""

import statistics
from scipy import stats


def check_normality(samples: list[float], feature_name: str, alpha: float = 0.05) -> bool:
    """
    Perform the Shapiro-Wilk test for normality on a set of numeric samples.

    Args:
        samples: List of numeric feature observations.
        feature_name: Name of the RF feature being tested.
        alpha: Significance level threshold (default: 0.05).

    Returns:
        True if the samples appear Gaussian (p >= alpha), False otherwise.
    """
    stat, p_value = stats.shapiro(samples)
    is_normal = bool(p_value >= alpha)

    verdict = "Gaussian (Passed)" if is_normal else "NOT Gaussian (Failed - use robust z-score)"
    print(f"  {feature_name:<15}: W = {stat:.4f}, p = {p_value:.4f} -> {verdict}")

    return is_normal


def robust_z_score(x: float, samples: list[float]) -> float:
    """
    Compute a median/MAD-based robust z-score for non-Gaussian or skewed features.

        z_robust = 0.6745 * (x - median) / MAD

    The 0.6745 factor scales Median Absolute Deviation (MAD) to estimate standard
    deviation under a standard normal distribution. MAD is floored at 1e-6 to avoid
    division by zero.

    Args:
        x: The feature observation value to normalize.
        samples: Baseline sample distribution.

    Returns:
        The robust z-score value.
    """
    med = statistics.median(samples)
    mad = statistics.median([abs(s - med) for s in samples])
    if mad < 1e-6:
        mad = 1e-6
    return 0.6745 * (x - med) / mad

"""
anomaly_engine.py — Layer 2b Statistical Anomaly Engine.

Detects uncatalogued or unknown RF threats by identifying statistically significant
deviations (|z| >= z_threshold) from the calibrated normal baseline.
This engine activates only when no known jamming rule matched.
"""

from typing import Optional


class StatisticalAnomalyEngine:
    """
    Statistical Anomaly Engine evaluating feature z-scores against a threshold.

    Attributes:
        z_threshold: Absolute z-score threshold beyond which a feature is
                     considered statistically anomalous (default: 3.0).
    """

    def __init__(self, z_threshold: float = 3.0):
        self.z_threshold = z_threshold

    def evaluate(self, deviations: dict) -> Optional[dict]:
        """
        Evaluate deviations dictionary for statistically significant outliers.

        Args:
            deviations: Deviations dictionary produced by NormalBaseline.deviations().

        Returns:
            Dict containing anomalous feature names and their z-scores if any feature
            exceeds the threshold, else None.
        """
        z_scores = deviations.get("z_scores", {})
        significant = {f: z for f, z in z_scores.items() if abs(z) >= self.z_threshold}
        if not significant:
            return None
        return {
            "anomalous_features": list(significant.keys()),
            "z_scores": significant,
        }

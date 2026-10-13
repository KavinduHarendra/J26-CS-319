"""
baseline.py — Statistical baseline and feature z-score deviation analyzer.

Maintains normal operating baselines (mean, std) for RF features (rssi, snr,
noise_floor, packet_rate) and calculates normalized z-scores:
    z = (x - mu) / sigma
"""

import statistics
from dataclasses import dataclass
from typing import Any

from src.schema import RFObservation


@dataclass
class FeatureBaseline:
    """Summary statistics for a single RF feature."""
    mean: float = 0.0
    std: float = 1.0  # default avoids division by zero prior to calibration


class NormalBaseline:
    """
    Statistical baseline over RSSI, SNR, noise_floor, and packet_rate,
    calibrated against controlled Normal scenario observations.
    """

    FEATURES = ["rssi", "snr", "noise_floor", "packet_rate"]

    def __init__(self):
        self._samples: dict[str, list[float]] = {f: [] for f in self.FEATURES}
        self._baseline: dict[str, FeatureBaseline] = {f: FeatureBaseline() for f in self.FEATURES}
        self.calibrated: bool = False

    @property
    def baseline(self) -> dict[str, FeatureBaseline]:
        """Access calibrated feature statistics."""
        return self._baseline

    def add_normal_sample(self, obs: RFObservation) -> None:
        """Add a single normal observation to the calibration sample pool."""
        for f in self.FEATURES:
            self._samples[f].append(float(getattr(obs, f)))

    def add_normal_samples(self, samples: list[RFObservation]) -> None:
        """Add a batch of normal observations to the calibration pool."""
        for obs in samples:
            self.add_normal_sample(obs)

    def calibrate(self) -> None:
        """
        Compute mean and standard deviation for each feature from collected samples.

        Raises:
            ValueError: If fewer than 2 samples were recorded for any feature.
        """
        for f in self.FEATURES:
            vals = self._samples[f]
            if len(vals) < 2:
                raise ValueError(f"Not enough normal samples to calibrate '{f}' (got {len(vals)})")
            self._baseline[f] = FeatureBaseline(
                mean=statistics.mean(vals),
                std=statistics.pstdev(vals) or 1e-6,  # guard against zero variance
            )
        self.calibrated = True

    def z_scores(self, obs: RFObservation) -> dict[str, float]:
        """
        Compute standard z-scores for all features of an observation.

        Raises:
            RuntimeError: If called before calibrate().
        """
        if not self.calibrated:
            raise RuntimeError("Baseline not calibrated yet. Call calibrate() first.")
        return {
            f: (float(getattr(obs, f)) - self._baseline[f].mean) / self._baseline[f].std
            for f in self.FEATURES
        }

    def deviations(self, obs: RFObservation) -> dict[str, Any]:
        """
        Compute directional and magnitude deviations for rule matching and explainability.

        Returns:
            Dict containing:
              - snr_drop: Positive magnitude when SNR drops below normal mean.
              - rssi_deviation: Absolute magnitude of RSSI deviation.
              - noise_floor_increase: Positive magnitude when noise floor rises.
              - packet_rate_deviation: Absolute magnitude of packet rate deviation.
              - z_scores: Raw signed z-score dictionary.
        """
        z = self.z_scores(obs)
        return {
            "snr_drop": -z["snr"] if z["snr"] < 0 else 0.0,
            "rssi_deviation": abs(z["rssi"]),
            "noise_floor_increase": z["noise_floor"] if z["noise_floor"] > 0 else 0.0,
            "packet_rate_deviation": abs(z["packet_rate"]),
            "z_scores": z,
        }

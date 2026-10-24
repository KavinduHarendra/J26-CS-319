"""
baseline.py — Statistical baseline and feature z-score deviation analyzer.

Maintains normal operating baselines (mean, std) for RF features (rssi, snr,
noise_floor, packet_rate) and calculates normalized z-scores:
    z = (x - mu) / sigma
"""

import hashlib
import hmac
import json
import math
import statistics
from dataclasses import dataclass
from datetime import datetime, timezone
from numbers import Real
from pathlib import Path
from typing import Any

from src.schema import RFObservation, validate_observation


class BaselineIntegrityError(ValueError):
    """Raised when persisted baseline data is missing, malformed, or tampered with."""


class UnsafeBaselineSampleError(ValueError):
    """Raised when a threat observation is offered as a normal baseline sample."""


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
    FORMAT_VERSION = "1.0"

    def __init__(self):
        self._samples: dict[str, list[float]] = {f: [] for f in self.FEATURES}
        self._baseline: dict[str, FeatureBaseline] = {f: FeatureBaseline() for f in self.FEATURES}
        self.calibrated: bool = False
        self.version: str = self.FORMAT_VERSION
        self.created_at: str = datetime.now(timezone.utc).isoformat()

    @property
    def baseline(self) -> dict[str, FeatureBaseline]:
        """Access calibrated feature statistics."""
        return self._baseline

    def add_normal_sample(
        self,
        obs: RFObservation,
        classification: str = "Normal",
    ) -> None:
        """Add a validated Normal observation to the calibration sample pool.

        A sample already classified as Jamming or Unknown Anomaly is refused so
        threat data cannot poison the normal baseline.
        """
        classification_value = getattr(classification, "value", classification)
        if classification_value != "Normal":
            raise UnsafeBaselineSampleError(
                f"Refusing to add '{classification_value}' observation to the normal baseline"
            )
        validate_observation(obs)
        for f in self.FEATURES:
            self._samples[f].append(float(getattr(obs, f)))

    def add_classified_sample(self, obs: RFObservation, classification: str) -> None:
        """Add a sample only when its prior classification is exactly Normal."""
        self.add_normal_sample(obs, classification=classification)

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
        self.created_at = datetime.now(timezone.utc).isoformat()

    def z_scores(self, obs: RFObservation) -> dict[str, float]:
        """
        Compute standard z-scores for all features of an observation.

        Raises:
            RuntimeError: If called before calibrate().
        """
        if not self.calibrated:
            raise RuntimeError("Baseline not calibrated yet. Call calibrate() first.")
        validate_observation(obs)
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

    @staticmethod
    def _sidecar_path(path: Path) -> Path:
        return path.with_suffix(path.suffix + ".sha256")

    def save_baseline(self, path: str | Path) -> None:
        """Persist a calibrated baseline as JSON plus a SHA-256 sidecar.

        Pickle is deliberately not supported because loading pickle can execute
        attacker-controlled code. The digest covers the exact JSON bytes written.
        """
        if not self.calibrated:
            raise RuntimeError("Cannot save an uncalibrated baseline")

        destination = Path(path)
        payload = {
            "version": self.version,
            "created_at": self.created_at,
            "features": {
                feature: {
                    "mean": self._baseline[feature].mean,
                    "std": self._baseline[feature].std,
                }
                for feature in self.FEATURES
            },
        }
        serialized = (
            json.dumps(
                payload,
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=False,
                allow_nan=False,
            )
            + "\n"
        ).encode("utf-8")
        digest = hashlib.sha256(serialized).hexdigest()

        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(serialized)
        self._sidecar_path(destination).write_text(digest + "\n", encoding="ascii")

    @classmethod
    def load_baseline(cls, path: str | Path) -> "NormalBaseline":
        """Load a JSON baseline only after verifying its SHA-256 sidecar."""
        source = Path(path)
        sidecar = cls._sidecar_path(source)
        try:
            serialized = source.read_bytes()
            expected_digest = sidecar.read_text(encoding="ascii").strip().lower()
        except OSError as exc:
            raise BaselineIntegrityError(f"Unable to read baseline or hash sidecar: {exc}") from exc

        if len(expected_digest) != 64 or any(c not in "0123456789abcdef" for c in expected_digest):
            raise BaselineIntegrityError("Baseline SHA-256 sidecar is malformed")
        actual_digest = hashlib.sha256(serialized).hexdigest()
        if not hmac.compare_digest(actual_digest, expected_digest):
            raise BaselineIntegrityError("Baseline SHA-256 verification failed")

        try:
            payload = json.loads(serialized)
            if payload["version"] != cls.FORMAT_VERSION:
                raise BaselineIntegrityError(
                    f"Unsupported baseline version: {payload['version']!r}"
                )
            created_at = payload["created_at"]
            if not isinstance(created_at, str):
                raise TypeError("created_at must be a string")
            datetime.fromisoformat(created_at)
            features = payload["features"]
            if set(features) != set(cls.FEATURES):
                raise ValueError("Baseline feature set is incomplete or unexpected")

            loaded_features: dict[str, FeatureBaseline] = {}
            for feature in cls.FEATURES:
                values = features[feature]
                mean = values["mean"]
                std = values["std"]
                if (
                    isinstance(mean, bool)
                    or isinstance(std, bool)
                    or not isinstance(mean, Real)
                    or not isinstance(std, Real)
                    or not math.isfinite(float(mean))
                    or not math.isfinite(float(std))
                    or std <= 0
                ):
                    raise ValueError(f"Invalid baseline statistics for '{feature}'")
                loaded_features[feature] = FeatureBaseline(float(mean), float(std))
        except BaselineIntegrityError:
            raise
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise BaselineIntegrityError(f"Malformed baseline JSON: {exc}") from exc

        baseline = cls()
        baseline.version = payload["version"]
        baseline.created_at = created_at
        baseline._baseline = loaded_features
        baseline.calibrated = True
        return baseline

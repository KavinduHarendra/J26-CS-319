"""Nearest-normal-state anomaly detection for raw measurements."""

from __future__ import annotations

from dataclasses import dataclass

from src.baseline import Baseline
from src.real_data import Signal


@dataclass(frozen=True, slots=True)
class AnomalyResult:
    abnormal: bool
    state: str
    distance: float
    normalized_distance: float
    statistical_deviation: dict[str, float]
    abnormal_features: tuple[str, ...]
    evidence: tuple[str, ...]


class AnomalyEngine:
    def __init__(self, baseline: Baseline, threshold: float = 1.0) -> None:
        self.baseline = baseline
        self.threshold = threshold

    def evaluate(self, signal: Signal) -> AnomalyResult:
        state, distance, deviations = self.baseline.nearest(signal)
        normalized = distance / state.anomaly_limit
        ranked = sorted(deviations, key=deviations.get, reverse=True)
        abnormal_features = tuple(
            feature for feature in ranked if deviations[feature] > state.anomaly_limit
        )
        evidence = ()
        abnormal = normalized > self.threshold
        if abnormal:
            named = abnormal_features or tuple(ranked[:3])
            evidence = tuple(
                f"{feature} distance {deviations[feature]:.2f} from {state.name} "
                f"exceeds state limit {state.anomaly_limit:.2f}"
                for feature in named
            )
        return AnomalyResult(
            abnormal=abnormal,
            state=state.name,
            distance=distance,
            normalized_distance=normalized,
            statistical_deviation=deviations,
            abnormal_features=abnormal_features,
            evidence=evidence,
        )

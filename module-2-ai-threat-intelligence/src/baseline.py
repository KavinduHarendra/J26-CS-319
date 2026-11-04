"""Two-state baseline built only from validated Module 1 measurements."""

from __future__ import annotations

import json
import logging
import math
import statistics
from collections.abc import Sequence
from dataclasses import dataclass, field, replace
from numbers import Real
from pathlib import Path
from typing import Any, Mapping

from src.normality_check import (
    MODIFIED_Z_FACTOR,
    NormalityResult,
    check_normality,
    median_absolute_deviation,
    robust_z_score,
)
from src.real_data import Signal


logger = logging.getLogger(__name__)


BASELINE_FEATURES = (
    "peak_db",
    "snr_db",
    "band_power_dbfs",
    "occupied_bw_khz",
    "spectral_flatness",
)
SPREAD_FLOORS = {
    "peak_db": 0.5,
    "snr_db": 0.5,
    "band_power_dbfs": 0.5,
    "occupied_bw_khz": 5.0,
    "spectral_flatness": 0.01,
}
STANDARD = "standard"
ROBUST = "robust"


class InvalidBaselineConfig(ValueError):
    """Raised when calibrated baseline JSON is incomplete or unsafe."""


def _finite(value: Any, context: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise InvalidBaselineConfig(f"{context} must be a real number")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        qualifier = "positive and finite" if positive else "finite"
        raise InvalidBaselineConfig(f"{context} must be {qualifier}")
    return result


@dataclass(frozen=True, slots=True)
class NormalState:
    """One normal state; a feature that failed normality uses a robust z-score.

    ``methods`` maps each feature to STANDARD or ROBUST.  A feature missing from
    it (for example in a config written before normality screening) is STANDARD.
    """

    name: str
    mean: Mapping[str, float]
    spread: Mapping[str, float]
    anomaly_limit: float
    median: Mapping[str, float] = field(default_factory=dict)
    mad: Mapping[str, float] = field(default_factory=dict)
    methods: Mapping[str, str] = field(default_factory=dict)
    normality: Mapping[str, NormalityResult] = field(default_factory=dict)

    def method(self, feature: str) -> str:
        return self.methods.get(feature, STANDARD)

    def deviation(self, feature: str, value: float) -> float:
        if self.method(feature) == ROBUST:
            return abs(robust_z_score(value, self.median[feature], self.mad[feature]))
        return abs(value - self.mean[feature]) / self.spread[feature]


@dataclass(frozen=True, slots=True)
class Baseline:
    version: str
    idle: NormalState
    legitimate: NormalState

    @classmethod
    def from_config(cls, config: Mapping[str, Any]) -> "Baseline":
        try:
            version = config["baseline_version"]
            states = config["normal_states"]
        except (KeyError, TypeError) as exc:
            raise InvalidBaselineConfig(f"missing baseline configuration: {exc}") from exc
        if not isinstance(version, str) or not version:
            raise InvalidBaselineConfig("baseline_version must be a non-empty string")

        def parse_state(key: str) -> NormalState:
            try:
                raw = states[key]
                mean_values = raw["mean"]
                spread_values = raw["spread"]
                limit = _finite(raw["anomaly_limit"], f"{key}.anomaly_limit", positive=True)
            except (KeyError, TypeError) as exc:
                raise InvalidBaselineConfig(f"invalid {key} state: {exc}") from exc
            if set(mean_values) != set(BASELINE_FEATURES):
                raise InvalidBaselineConfig(f"{key}.mean has an unexpected feature set")
            if set(spread_values) != set(BASELINE_FEATURES):
                raise InvalidBaselineConfig(f"{key}.spread has an unexpected feature set")
            methods = raw.get("method", {})
            if not isinstance(methods, Mapping) or not set(methods) <= set(BASELINE_FEATURES):
                raise InvalidBaselineConfig(f"{key}.method has an unexpected feature set")
            if not set(methods.values()) <= {STANDARD, ROBUST}:
                raise InvalidBaselineConfig(f"{key}.method values must be standard or robust")
            robust = [feature for feature in BASELINE_FEATURES if methods.get(feature) == ROBUST]
            try:
                median = {
                    feature: _finite(raw["median"][feature], f"{key}.median.{feature}")
                    for feature in robust
                }
                mad = {
                    feature: _finite(raw["mad"][feature], f"{key}.mad.{feature}", positive=True)
                    for feature in robust
                }
            except (KeyError, TypeError) as exc:
                raise InvalidBaselineConfig(f"{key} robust feature missing median/mad: {exc}") from exc
            logger.debug("baseline state %s feature methods: %s", key, dict(methods))
            return NormalState(
                name=key,
                mean={
                    feature: _finite(mean_values[feature], f"{key}.mean.{feature}")
                    for feature in BASELINE_FEATURES
                },
                spread={
                    feature: _finite(
                        spread_values[feature], f"{key}.spread.{feature}", positive=True
                    )
                    for feature in BASELINE_FEATURES
                },
                anomaly_limit=limit,
                median=median,
                mad=mad,
                methods=dict(methods),
            )

        return cls(
            version=version,
            idle=parse_state("idle"),
            legitimate=parse_state("legit_ook"),
        )

    @classmethod
    def load(cls, path: str | Path) -> "Baseline":
        try:
            payload = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise InvalidBaselineConfig(f"unable to load baseline configuration: {exc}") from exc
        if not isinstance(payload, Mapping):
            raise InvalidBaselineConfig("baseline configuration must be a JSON object")
        return cls.from_config(payload)

    @staticmethod
    def feature_distances(signal: Signal, state: NormalState) -> dict[str, float]:
        if not isinstance(signal, Signal):
            raise TypeError("baseline requires a validated Signal")
        return {
            feature: state.deviation(feature, getattr(signal, feature))
            for feature in BASELINE_FEATURES
        }

    def nearest(self, signal: Signal) -> tuple[NormalState, float, dict[str, float]]:
        candidates: list[tuple[NormalState, float, dict[str, float]]] = []
        for state in (self.idle, self.legitimate):
            distances = self.feature_distances(signal, state)
            candidates.append((state, max(distances.values()), distances))
        return min(candidates, key=lambda candidate: candidate[1])


def calibrate_state(
    signals: Sequence[Signal], name: str, *, normality_screen: bool = False
) -> NormalState:
    """Fit one normal state and choose each feature's deviation method.

    Without ``normality_screen`` every feature uses (x - mean) / spread.  With
    it, each feature is screened with ``check_normality``: features that pass
    keep the standard formula, features that fail use the robust z-score on
    median and MAD.  Both scales are floored by SPREAD_FLOORS (the MAD floor is the spread
    floor x 0.6745, so the two methods share one minimum sigma).  The anomaly
    limit is 1.25 x the largest calibration distance, never below 3.0.
    """
    if not signals:
        raise ValueError(f"state {name} needs at least one calibration signal")
    mean, spread, median, mad, methods, normality = {}, {}, {}, {}, {}, {}
    for feature in BASELINE_FEATURES:
        values = [getattr(signal, feature) for signal in signals]
        floor = SPREAD_FLOORS[feature]
        mean[feature] = statistics.fmean(values)
        spread[feature] = max(statistics.pstdev(values), floor)
        if not normality_screen:
            methods[feature] = STANDARD
            continue
        median[feature], raw_mad = median_absolute_deviation(values)
        mad[feature] = max(raw_mad, floor * MODIFIED_Z_FACTOR)
        normality[feature] = check_normality(values)
        methods[feature] = STANDARD if normality[feature].passed else ROBUST
        p_value = normality[feature].p_value
        logger.info(
            "state %s feature %s: %s test (n=%d, p=%s) -> %s z-score",
            name,
            feature,
            normality[feature].test,
            normality[feature].n,
            "n/a" if p_value is None else f"{p_value:.3g}",
            methods[feature],
        )

    state = NormalState(
        name=name,
        mean=mean,
        spread=spread,
        anomaly_limit=1.0,
        median=median,
        mad=mad,
        methods=methods,
        normality=normality,
    )
    largest = max(
        max(state.deviation(feature, getattr(signal, feature)) for feature in BASELINE_FEATURES)
        for signal in signals
    )
    return replace(state, anomaly_limit=max(3.0, 1.25 * largest))

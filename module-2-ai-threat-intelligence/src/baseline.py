"""Two-state baseline built only from validated Module 1 measurements."""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from numbers import Real
from pathlib import Path
from typing import Any, Mapping

from src.real_data import Signal


BASELINE_FEATURES = (
    "peak_db",
    "snr_db",
    "band_power_dbfs",
    "occupied_bw_khz",
    "spectral_flatness",
)


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
    name: str
    mean: Mapping[str, float]
    spread: Mapping[str, float]
    anomaly_limit: float


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
            feature: abs(getattr(signal, feature) - state.mean[feature]) / state.spread[feature]
            for feature in BASELINE_FEATURES
        }

    def nearest(self, signal: Signal) -> tuple[NormalState, float, dict[str, float]]:
        candidates: list[tuple[NormalState, float, dict[str, float]]] = []
        for state in (self.idle, self.legitimate):
            distances = self.feature_distances(signal, state)
            candidates.append((state, max(distances.values()), distances))
        return min(candidates, key=lambda candidate: candidate[1])

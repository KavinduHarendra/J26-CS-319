"""Distance-banded baselines so long-range path loss is not read as an anomaly.

Standalone component.  ``ThreatClassifier`` still uses one flat ``Baseline``;
adopting this needs a separate integration step in which the classifier selects
``banded.get(signal.distance_m)`` for each capture.

Only the legitimate-link state is banded.  Idle noise does not depend on where
the UAV is, so every band shares the flat baseline's idle state.
"""

from __future__ import annotations

import math
from bisect import bisect_right
from collections.abc import Iterable

from src.baseline import Baseline, calibrate_state
from src.real_data import Signal


class DistanceBandedBaseline:
    """One lazily calibrated ``Baseline`` per half-open distance band.

    ``band_edges=[50, 150, 300]`` gives bands [0, 50), [50, 150), [150, 300)
    and [300, inf) metres.  A capture without ``distance_m`` uses ``base``.
    """

    def __init__(
        self,
        band_edges: list[float],
        base: Baseline,
        legitimate: Iterable[Signal],
        *,
        min_samples: int = 10,
        normality_screen: bool = False,
    ) -> None:
        edges = [float(edge) for edge in band_edges]
        if not edges:
            raise ValueError("band_edges must contain at least one edge")
        if any(not math.isfinite(edge) or edge <= 0.0 for edge in edges):
            raise ValueError("band_edges must be positive and finite")
        if any(lower >= upper for lower, upper in zip(edges, edges[1:], strict=False)):
            raise ValueError("band_edges must be strictly increasing")
        if min_samples < 2:
            raise ValueError("min_samples must be at least 2")

        self.band_edges = tuple(edges)
        self.base = base
        self.min_samples = min_samples
        self.normality_screen = normality_screen
        self._calibration: list[list[Signal]] = [[] for _ in range(len(edges) + 1)]
        for signal in legitimate:
            if signal.distance_m is None:
                raise ValueError(
                    f"calibration signal {signal.observation_id} has no distance_m"
                )
            self._calibration[self.band_index(signal.distance_m)].append(signal)
        self._baselines: dict[int, Baseline] = {}

    def band_index(self, distance_m: float) -> int:
        if not math.isfinite(distance_m) or distance_m < 0.0:
            raise ValueError("distance_m must be finite and non-negative")
        return bisect_right(self.band_edges, distance_m)

    def band_range(self, index: int) -> tuple[float, float]:
        lower = 0.0 if index == 0 else self.band_edges[index - 1]
        upper = self.band_edges[index] if index < len(self.band_edges) else math.inf
        return lower, upper

    def get(self, distance_m: float | None) -> Baseline:
        if distance_m is None:
            return self.base
        index = self.band_index(distance_m)
        if index not in self._baselines:
            self._baselines[index] = self._calibrate(index)
        return self._baselines[index]

    def _calibrate(self, index: int) -> Baseline:
        lower, upper = self.band_range(index)
        signals = self._calibration[index]
        if len(signals) < self.min_samples:
            raise ValueError(
                f"distance band {lower:g}-{upper:g} m has {len(signals)} calibration "
                f"captures; at least {self.min_samples} are required"
            )
        return Baseline(
            version=f"{self.base.version}+distance-{lower:g}-{upper:g}m",
            idle=self.base.idle,
            legitimate=calibrate_state(
                signals, self.base.legitimate.name, normality_screen=self.normality_screen
            ),
        )

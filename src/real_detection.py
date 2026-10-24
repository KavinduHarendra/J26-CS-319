"""Version 2 detection components calibrated from validated real measurements.

This module deliberately accepts only :class:`src.real_data.RealSignal` values.
Ground-truth labels, capture phases, jammer names, folder names, and Module 1
flags are not part of the runtime feature interface.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Iterable

import numpy as np

from src.real_data import RealSignal


AUDITED_FEATURES = (
    "peak_db",
    "noise_db",
    "snr_db",
    "band_power_dbfs",
    "occupied_bw_khz",
    "spectral_flatness",
    "peak_freq_mhz",
)

# noise_db and peak_freq_mhz are intentionally excluded. In this recording they
# move with the scripted capture phase or receiver tuning and would not be safe
# evidence of a threat in another session.
DETECTION_FEATURES = (
    "peak_db",
    "snr_db",
    "band_power_dbfs",
    "occupied_bw_khz",
    "spectral_flatness",
)

# Floors reflect the exported measurement resolution. They prevent constant or
# nearly constant normal features from causing division by zero.
STD_FLOORS = {
    "peak_db": 0.1,
    "snr_db": 0.1,
    "band_power_dbfs": 0.1,
    "occupied_bw_khz": 1.0,
    "spectral_flatness": 0.001,
}

BASELINE_VERSION = "real-baseline-v2"
RULE_ID = "R2-NARROWBAND"


@dataclass(frozen=True)
class NormalState:
    name: str
    mean: dict[str, float]
    std: dict[str, float]


@dataclass(frozen=True)
class BaselineV2:
    """Two-state normal baseline for idle and legitimate transmission."""

    idle: NormalState
    legitimate: NormalState
    state_snr_threshold: float
    version: str = BASELINE_VERSION

    def state_from_snr(self, signal: RealSignal) -> str:
        """Select the expected normal state using an idle-derived SNR limit."""
        return "legitimate" if signal.snr_db > self.state_snr_threshold else "idle"

    def z_scores(self, signal: RealSignal, state: NormalState) -> dict[str, float]:
        return {
            feature: (getattr(signal, feature) - state.mean[feature]) / state.std[feature]
            for feature in DETECTION_FEATURES
        }

    def nearest(self, signal: RealSignal) -> tuple[str, float, dict[str, float]]:
        """Return the nearest normal state and RMS distance in robust z units."""
        candidates: list[tuple[str, float, dict[str, float]]] = []
        for state in (self.idle, self.legitimate):
            z_scores = self.z_scores(signal, state)
            distance = math.sqrt(
                sum(value * value for value in z_scores.values()) / len(z_scores)
            )
            candidates.append((state.name, distance, z_scores))
        return min(candidates, key=lambda item: item[1])


@dataclass(frozen=True)
class RuleThresholds:
    snr_signal_threshold: float
    occupied_bw_max_khz: float
    spectral_flatness_max: float
    calibration_normal_fpr: float
    calibration_jammer_recall: float


@dataclass(frozen=True)
class RuleDecision:
    triggered: bool
    rule_id: str | None
    evidence: list[str]


class ExplainableRulesV2:
    """Measurement-only IF-THEN rule set; legacy J01/J02 are not evaluated."""

    def __init__(self, thresholds: RuleThresholds) -> None:
        self.thresholds = thresholds

    def evaluate(self, signal: RealSignal) -> RuleDecision:
        t = self.thresholds
        has_signal = signal.snr_db > t.snr_signal_threshold
        narrow = signal.occupied_bw_khz <= t.occupied_bw_max_khz
        tonal = signal.spectral_flatness <= t.spectral_flatness_max
        if has_signal and narrow and tonal:
            return RuleDecision(
                triggered=True,
                rule_id=RULE_ID,
                evidence=[
                    (
                        f"SNR {signal.snr_db:.1f} dB exceeds the idle-derived signal "
                        f"threshold {t.snr_signal_threshold:.1f} dB"
                    ),
                    (
                        f"Occupied bandwidth {signal.occupied_bw_khz:.1f} kHz is at or "
                        f"below {t.occupied_bw_max_khz:.1f} kHz"
                    ),
                    (
                        f"Spectral flatness {signal.spectral_flatness:.3f} is at or "
                        f"below {t.spectral_flatness_max:.3f}"
                    ),
                ],
            )
        return RuleDecision(False, None, [])


@dataclass(frozen=True)
class AnomalyDecision:
    triggered: bool
    state: str
    distance: float
    z_scores: dict[str, float]
    abnormal_features: list[str]
    evidence: list[str]


class NearestStateAnomalyV2:
    """Anomaly detector using distance to the nearer of two normal states."""

    def __init__(self, baseline: BaselineV2, threshold: float) -> None:
        if not math.isfinite(threshold) or threshold <= 0:
            raise ValueError("anomaly threshold must be a positive finite number")
        self.baseline = baseline
        self.threshold = float(threshold)

    def evaluate(self, signal: RealSignal) -> AnomalyDecision:
        state, distance, z_scores = self.baseline.nearest(signal)
        ranked = sorted(z_scores, key=lambda feature: abs(z_scores[feature]), reverse=True)
        abnormal = [feature for feature in ranked if abs(z_scores[feature]) >= 3.0]
        if distance > self.threshold:
            evidence_features = abnormal or ranked[:3]
            evidence = [
                (
                    f"{feature} differs from the nearest {state} normal state by "
                    f"{z_scores[feature]:+.2f} robust z"
                )
                for feature in evidence_features
            ]
        else:
            evidence = []
        return AnomalyDecision(
            triggered=distance > self.threshold,
            state=state,
            distance=distance,
            z_scores=z_scores,
            abnormal_features=abnormal,
            evidence=evidence,
        )


@dataclass(frozen=True)
class RealDetectorV2:
    baseline: BaselineV2
    rules: ExplainableRulesV2
    anomaly: NearestStateAnomalyV2


def _rows(values: Iterable[RealSignal], name: str) -> list[RealSignal]:
    result = list(values)
    if not result:
        raise ValueError(f"{name} must contain at least one signal")
    if not all(isinstance(signal, RealSignal) for signal in result):
        raise TypeError(f"{name} must contain only RealSignal values")
    return result


def _higher_quantile(values: Iterable[float], quantile: float) -> float:
    array = np.asarray(list(values), dtype=float)
    if array.size == 0:
        raise ValueError("cannot calculate a quantile from no values")
    return float(np.quantile(array, quantile, method="higher"))


def fit_baseline_v2(
    calibration_idle: Iterable[RealSignal],
    calibration_legitimate: Iterable[RealSignal],
) -> BaselineV2:
    """Fit both normal states using calibration-normal measurements only."""
    idle = _rows(calibration_idle, "calibration_idle")
    legitimate = _rows(calibration_legitimate, "calibration_legitimate")

    def state(name: str, signals: list[RealSignal]) -> NormalState:
        means = {
            feature: float(np.mean([getattr(signal, feature) for signal in signals]))
            for feature in DETECTION_FEATURES
        }
        standard_deviations = {
            feature: max(
                float(np.std([getattr(signal, feature) for signal in signals], ddof=1)),
                STD_FLOORS[feature],
            )
            for feature in DETECTION_FEATURES
        }
        return NormalState(name=name, mean=means, std=standard_deviations)

    return BaselineV2(
        idle=state("idle", idle),
        legitimate=state("legitimate", legitimate),
        state_snr_threshold=_higher_quantile(
            (signal.snr_db for signal in idle), 0.99
        ),
    )


def calibrate_rules_v2(
    calibration_normal: Iterable[RealSignal],
    calibration_jamming: Iterable[RealSignal],
    state_snr_threshold: float,
    max_normal_fpr: float = 0.01,
) -> RuleThresholds:
    """Grid-search the narrowband rule on calibration rows only."""
    normal = _rows(calibration_normal, "calibration_normal")
    jamming = _rows(calibration_jamming, "calibration_jamming")
    bandwidth_candidates = sorted({signal.occupied_bw_khz for signal in jamming})
    flatness_candidates = sorted({signal.spectral_flatness for signal in jamming})
    candidates: list[tuple[float, float, float, float]] = []
    for bandwidth in bandwidth_candidates:
        for flatness in flatness_candidates:
            fires = lambda signal: (
                signal.snr_db > state_snr_threshold
                and signal.occupied_bw_khz <= bandwidth
                and signal.spectral_flatness <= flatness
            )
            false_positive_rate = sum(fires(signal) for signal in normal) / len(normal)
            if false_positive_rate <= max_normal_fpr:
                recall = sum(fires(signal) for signal in jamming) / len(jamming)
                candidates.append((recall, false_positive_rate, bandwidth, flatness))
    if not candidates:
        raise ValueError("no rule candidate satisfies the normal false-positive limit")

    # Highest recall, then lowest normal FPR, then the tightest thresholds.
    recall, false_positive_rate, bandwidth, flatness = max(
        candidates,
        key=lambda item: (item[0], -item[1], -item[2], -item[3]),
    )
    return RuleThresholds(
        snr_signal_threshold=float(state_snr_threshold),
        occupied_bw_max_khz=float(bandwidth),
        spectral_flatness_max=float(flatness),
        calibration_normal_fpr=float(false_positive_rate),
        calibration_jammer_recall=float(recall),
    )


def fit_detector_v2(
    calibration_idle: Iterable[RealSignal],
    calibration_legitimate: Iterable[RealSignal],
    calibration_jamming: Iterable[RealSignal],
    max_normal_fpr: float = 0.01,
) -> RealDetectorV2:
    """Fit baseline, rule thresholds, and anomaly limit from calibration only."""
    idle = _rows(calibration_idle, "calibration_idle")
    legitimate = _rows(calibration_legitimate, "calibration_legitimate")
    jamming = _rows(calibration_jamming, "calibration_jamming")
    normal = idle + legitimate
    baseline = fit_baseline_v2(idle, legitimate)
    rule_thresholds = calibrate_rules_v2(
        normal, jamming, baseline.state_snr_threshold, max_normal_fpr
    )
    normal_distances = [baseline.nearest(signal)[1] for signal in normal]
    anomaly_threshold = _higher_quantile(normal_distances, 1.0 - max_normal_fpr)
    return RealDetectorV2(
        baseline=baseline,
        rules=ExplainableRulesV2(rule_thresholds),
        anomaly=NearestStateAnomalyV2(baseline, anomaly_threshold),
    )


def build_frozen_detector_v2() -> RealDetectorV2:
    """Return the reviewed detector fitted by ``scripts/analyze_real_data.py``.

    The demo and file processor use this frozen configuration, so they do not
    need ground truth and cannot silently refit thresholds on replay records.
    """
    baseline = BaselineV2(
        idle=NormalState(
            name="idle",
            mean={
                "peak_db": -103.00427215189875,
                "snr_db": 3.0112341772151896,
                "band_power_dbfs": -45.100000000000016,
                "occupied_bw_khz": 0.0,
                "spectral_flatness": 0.8516281645569621,
            },
            std={
                "peak_db": 0.20383978509388445,
                "snr_db": 0.20357438798867553,
                "band_power_dbfs": 0.1,
                "occupied_bw_khz": 1.0,
                "spectral_flatness": 0.0017028077265339465,
            },
        ),
        legitimate=NormalState(
            name="legitimate",
            mean={
                "peak_db": -56.333333333333336,
                "snr_db": 48.958333333333336,
                "band_power_dbfs": -19.866666666666664,
                "occupied_bw_khz": 347.4166666666667,
                "spectral_flatness": 0.00875,
            },
            std={
                "peak_db": 0.6617937854745638,
                "snr_db": 0.6990158713547194,
                "band_power_dbfs": 0.5036101551853349,
                "occupied_bw_khz": 33.18317628566918,
                "spectral_flatness": 0.0010320936930842798,
            },
        ),
        state_snr_threshold=3.5,
    )
    rules = ExplainableRulesV2(
        RuleThresholds(
            snr_signal_threshold=3.5,
            occupied_bw_max_khz=62.0,
            spectral_flatness_max=0.003,
            calibration_normal_fpr=0.0,
            calibration_jammer_recall=1.0,
        )
    )
    return RealDetectorV2(
        baseline=baseline,
        rules=rules,
        anomaly=NearestStateAnomalyV2(baseline, 1.6994861812377329),
    )

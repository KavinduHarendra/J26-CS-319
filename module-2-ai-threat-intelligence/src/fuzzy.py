"""Mamdani fuzzy risk score over snr_db and occupied_bw_khz.

Every input breakpoint is read from ``config/thresholds_real.json``, which
``scripts/calibrate_real.py`` fits on the first chronological half of the
known groups only:

- idle SNR top    = idle mean + idle anomaly_limit * spread       (snr_db)
- T_SNR, T_BW     = R1 thresholds (midpoints between calibration groups)
- legit BW bottom = legit mean - legit anomaly_limit * spread     (occupied_bw_khz)

SNR is WEAK up to the idle top and fully STRONG from T_SNR; bandwidth is fully
NARROW up to T_BW and fully WIDE from the legit bottom, with linear ramps in
between.  Inside R1's region the jamming rule therefore fires at 1.0, so the
fuzzy score never contradicts R1; outside it the score is graded.

The risk universe is 0-100.  Output sets are anchored on the configured
severity cut-offs: HIGH risk ramps up from the MEDIUM cut-off to full at the
HIGH cut-off, and LOW risk ramps down to 0 at the MEDIUM cut-off over the same
width, so a capture where only LOW rules fire can never reach MEDIUM.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path


RISK_MIN = 0.0
RISK_MAX = 100.0
CENTROID_STEPS = 1000  # 0.1-point resolution on the 0-100 risk universe


@dataclass(frozen=True, slots=True)
class Trapezoid:
    """Membership 0 below a, rising to 1 at b, 1 until c, 0 again at d.

    ``a == b`` (or both -inf) is a left shoulder; ``c == d`` (or both inf) a
    right shoulder.
    """

    a: float
    b: float
    c: float
    d: float

    def __post_init__(self) -> None:
        if not self.a <= self.b <= self.c <= self.d:
            raise ValueError(f"trapezoid breakpoints must be ordered: {self}")

    def __call__(self, x: float) -> float:
        if x < self.a or x > self.d:
            return 0.0
        if self.b <= x <= self.c:
            return 1.0
        if x < self.b:
            return (x - self.a) / (self.b - self.a)
        return (self.d - x) / (self.d - self.c)


@dataclass(frozen=True, slots=True)
class FuzzyRule:
    id: str
    description: str
    snr_set: str
    bw_set: str | None  # None: the rule uses SNR only
    risk_set: str


@dataclass(frozen=True, slots=True)
class FiredRule:
    id: str
    description: str
    strength: float


@dataclass(frozen=True, slots=True)
class FuzzyResult:
    score: float
    severity: str
    fired: tuple[FiredRule, ...]

    def evidence(self) -> list[str]:
        return [f"fuzzy_score {self.score:.1f} ({self.severity})"] + [
            f"fuzzy {rule.id} fired at {rule.strength:.2f}: {rule.description}"
            for rule in self.fired
        ]


RULES = (
    FuzzyRule("F1", "STRONG snr AND NARROW bw -> HIGH risk", "STRONG", "NARROW", "HIGH"),
    FuzzyRule("F2", "STRONG snr AND WIDE bw -> LOW risk", "STRONG", "WIDE", "LOW"),
    FuzzyRule("F3", "WEAK snr -> LOW risk", "WEAK", None, "LOW"),
)


class FuzzyRiskSystem:
    def __init__(
        self,
        snr_sets: Mapping[str, Trapezoid],
        bw_sets: Mapping[str, Trapezoid],
        medium_from: float,
        high_from: float,
    ) -> None:
        if not RISK_MIN < medium_from < high_from < RISK_MAX:
            raise ValueError("fuzzy cut-offs must satisfy 0 < medium_from < high_from < 100")
        self.snr_sets = dict(snr_sets)
        self.bw_sets = dict(bw_sets)
        self.medium_from = medium_from
        self.high_from = high_from
        self.risk_sets = {
            "LOW": Trapezoid(
                RISK_MIN, RISK_MIN, max(RISK_MIN, 2 * medium_from - high_from), medium_from
            ),
            "HIGH": Trapezoid(medium_from, high_from, RISK_MAX, RISK_MAX),
        }

    @classmethod
    def from_config(cls, configuration: Mapping) -> "FuzzyRiskSystem":
        thresholds = configuration["thresholds"]
        t_snr = float(thresholds["T_SNR"])
        t_bw = float(thresholds["T_BW"])
        states = configuration["normal_states"]
        idle, legit = states["idle"], states["legit_ook"]
        idle_snr_top = (
            idle["mean"]["snr_db"] + idle["anomaly_limit"] * idle["spread"]["snr_db"]
        )
        legit_bw_bottom = (
            legit["mean"]["occupied_bw_khz"]
            - legit["anomaly_limit"] * legit["spread"]["occupied_bw_khz"]
        )
        cutoffs = configuration["fuzzy"]
        return cls(
            snr_sets={
                "WEAK": Trapezoid(-math.inf, -math.inf, idle_snr_top, t_snr),
                "STRONG": Trapezoid(idle_snr_top, t_snr, math.inf, math.inf),
            },
            bw_sets={
                "NARROW": Trapezoid(-math.inf, -math.inf, t_bw, legit_bw_bottom),
                "WIDE": Trapezoid(t_bw, legit_bw_bottom, math.inf, math.inf),
            },
            medium_from=float(cutoffs["severity_medium_from"]),
            high_from=float(cutoffs["severity_high_from"]),
        )

    @classmethod
    def load(cls, path: str | Path) -> "FuzzyRiskSystem":
        return cls.from_config(json.loads(Path(path).read_text(encoding="utf-8")))

    def severity(self, score: float) -> str:
        if score >= self.high_from:
            return "HIGH"
        if score >= self.medium_from:
            return "MEDIUM"
        return "LOW"

    def evaluate(self, snr_db: float, occupied_bw_khz: float) -> FuzzyResult:
        fired = []
        for rule in RULES:
            strength = self.snr_sets[rule.snr_set](snr_db)
            if rule.bw_set is not None:
                strength = min(strength, self.bw_sets[rule.bw_set](occupied_bw_khz))
            if strength > 0.0:
                fired.append((rule, strength))

        numerator = denominator = 0.0
        step = (RISK_MAX - RISK_MIN) / CENTROID_STEPS
        for index in range(CENTROID_STEPS + 1):
            x = RISK_MIN + index * step
            membership = max(
                (min(strength, self.risk_sets[rule.risk_set](x)) for rule, strength in fired),
                default=0.0,
            )
            numerator += x * membership
            denominator += membership
        score = numerator / denominator if denominator > 0.0 else RISK_MIN

        return FuzzyResult(
            score=score,
            severity=self.severity(score),
            fired=tuple(
                FiredRule(rule.id, rule.description, strength) for rule, strength in fired
            ),
        )

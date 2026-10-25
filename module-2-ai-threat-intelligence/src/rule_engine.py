"""Single explainable rule engine for calibrated raw measurements."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Callable, Mapping


Measurements = Mapping[str, float]


@dataclass(frozen=True, slots=True)
class Rule:
    id: str
    description: str
    requires: tuple[str, ...]
    condition: Callable[[Measurements], bool]
    evidence: Callable[[Measurements], str]


@dataclass(frozen=True, slots=True)
class RuleResult:
    triggered_rule: str | None
    evidence: tuple[str, ...]
    skipped_rules: tuple[str, ...]


class RuleEngine:
    def __init__(self, rules: tuple[Rule, ...], *, t_snr: float, t_bw: float) -> None:
        if not rules:
            raise ValueError("at least one rule is required")
        self.rules = rules
        self.t_snr = t_snr
        self.t_bw = t_bw

    def evaluate(self, measurements: Measurements) -> RuleResult:
        skipped: list[str] = []
        for rule in self.rules:
            if any(feature not in measurements for feature in rule.requires):
                skipped.append(rule.id)
                continue
            if rule.condition(measurements):
                return RuleResult(rule.id, (rule.evidence(measurements),), tuple(skipped))
        return RuleResult(None, (), tuple(skipped))


def build_rule_engine(t_snr: float, t_bw: float) -> RuleEngine:
    """Build the only production rule: R1 narrowband strong signal."""
    return RuleEngine(
        (
            Rule(
                id="R1",
                description="Narrowband strong signal",
                requires=("snr_db", "occupied_bw_khz"),
                condition=lambda values: (
                    values["snr_db"] >= t_snr
                    and 0.0 < values["occupied_bw_khz"] <= t_bw
                ),
                evidence=lambda values: (
                    f"snr_db {values['snr_db']:.1f} >= {t_snr:.1f} and "
                    f"0 < occupied_bw_khz {values['occupied_bw_khz']:.1f} <= {t_bw:.1f}"
                ),
            ),
        ),
        t_snr=t_snr,
        t_bw=t_bw,
    )

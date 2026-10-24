"""
rule_engine.py — Layer 2a Rule-Based Jamming Detector.

Evaluates structured feature deviations against explicit, human-auditable
jamming signature rules. Every rule provides an explainable description and rule ID
for auditability.
"""

from dataclasses import dataclass
from typing import Callable, Optional


@dataclass
class Rule:
    """
    A single explainable jamming detection rule.

    Attributes:
        rule_id: Unique rule identifier (e.g. 'J01', 'J02').
        description: Plain-language explanation of what condition this rule detects.
        condition: Callable taking a deviations dictionary and returning True if fired.
    """
    rule_id: str
    description: str
    condition: Callable[[dict], bool]


class RuleBasedJammingDetector:
    """
    Evaluates RF deviations against a registry of known jamming signature rules.
    """

    def __init__(self):
        self.rules: list[Rule] = []

    def register(self, rule: Rule) -> None:
        """Register a new jamming rule."""
        self.rules.append(rule)

    def evaluate(self, deviations: dict) -> Optional[dict]:
        """
        Evaluate all registered rules against the provided deviations dict.

        Returns:
            Dict containing triggered rule IDs and descriptions if one or more
            rules matched, or None if no rules fired.
        """
        fired = [r for r in self.rules if r.condition(deviations)]
        if not fired:
            return None
        return {
            "triggered_rules": [r.rule_id for r in fired],
            "rule_descriptions": [r.description for r in fired],
        }


# Legacy four-feature thresholds retained only for compatibility with the original
# RFObservation API. The real-recording pipeline uses src.real_detection instead.
#   J01: Joint 2D grid search over snr x noise candidates [1.0..4.0] step 0.25
#        -> snr_thresh=2.50, noise_thresh=2.75 (F1=1.0000); noise_thresh=2.75 provides
#           a safe margin over the normal noise floor tail (max ~2.68 sigma) so that
#           unknown-anomaly observations (noise floor near-normal) produce 0 rule fires.
#   J02: Youden's-J ROC optimization per feature on same dataset.
# These are NOT arbitrary — do not revert to 2.0/2.0/2.5/2.5 without re-running calibration.
def build_default_ruleset(
    snr_thresh: float = 2.5,
    noise_thresh: float = 2.75,
    rssi_thresh: float = 2.69,
    packet_thresh: float = 8.83,
) -> RuleBasedJammingDetector:
    """
    Build the default jamming detector with calibrated rules J01 and J02.

    Args:
        snr_thresh: Minimum z-score drop in SNR required for J01.
        noise_thresh: Minimum z-score increase in noise floor required for J01.
        rssi_thresh: Minimum absolute z-score deviation in RSSI for J02.
        packet_thresh: Minimum absolute z-score deviation in packet rate for J02.

    Returns:
        Configured RuleBasedJammingDetector instance.
    """
    detector = RuleBasedJammingDetector()

    detector.register(Rule(
        rule_id="J01",
        description="Significant SNR drop combined with noise floor increase",
        condition=lambda d: d["snr_drop"] > snr_thresh and d["noise_floor_increase"] > noise_thresh,
    ))

    detector.register(Rule(
        rule_id="J02",
        description="Severe RSSI deviation combined with abnormal packet rate",
        condition=lambda d: d["rssi_deviation"] > rssi_thresh and d["packet_rate_deviation"] > packet_thresh,
    ))

    return detector

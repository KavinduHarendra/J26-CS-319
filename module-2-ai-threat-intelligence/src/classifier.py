"""Single raw-measurement threat classification pipeline."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Mapping

from src.anomaly_engine import AnomalyEngine
from src.baseline import Baseline
from src.real_data import MEASUREMENT_FIELDS, Signal
from src.rule_engine import RuleEngine, build_rule_engine


DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[1] / "config" / "thresholds_real.json"


class Classification(str, Enum):
    NORMAL = "NORMAL"
    JAMMING = "JAMMING"
    UNKNOWN_ANOMALY = "UNKNOWN_ANOMALY"


class Severity(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


@dataclass(frozen=True, slots=True)
class ThreatOutput:
    schema_version: str
    source_module: str
    observation_id: str
    sequence_number: int
    timestamp: str
    classification: str
    severity: str | None
    triggered_rule: str | None
    abnormal_features: list[str]
    statistical_deviation: dict[str, float]
    evidence: list[str]
    baseline_version: str
    processing_ms: float = field(compare=False)


@dataclass(frozen=True, slots=True)
class DecisionStep:
    name: str
    expression: str
    actual_values: Mapping[str, float | str]
    thresholds: Mapping[str, float]
    passed: bool | None


@dataclass(frozen=True, slots=True)
class DecisionTrace:
    steps: tuple[DecisionStep, ...]
    per_state_distances: Mapping[str, Mapping[str, float]]
    state_limits: Mapping[str, float]
    nearest_state: str | None
    path_taken: str
    skipped_rules: tuple[str, ...]
    plain_english: str

    @classmethod
    def rejected(cls, reason: str) -> "DecisionTrace":
        return cls(
            steps=(
                DecisionStep(
                    name="Input validation",
                    expression="input must satisfy the Module 1 measurement contract",
                    actual_values={"reason": reason},
                    thresholds={},
                    passed=False,
                ),
            ),
            per_state_distances={},
            state_limits={},
            nearest_state=None,
            path_taken="REJECTED",
            skipped_rules=(),
            plain_english=f"The input was rejected before classification: {reason}",
        )


class ThreatClassifier:
    """Stateless decision pipeline; severity cut-offs are uncalibrated placeholders."""

    def __init__(self, baseline: Baseline, rules: RuleEngine) -> None:
        self.baseline = baseline
        self.rules = rules
        self.anomaly = AnomalyEngine(baseline)

    @classmethod
    def from_config(cls, path: str | Path = DEFAULT_CONFIG_PATH) -> "ThreatClassifier":
        payload = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(payload, Mapping):
            raise ValueError("threshold configuration must be a JSON object")
        baseline = Baseline.from_config(payload)
        thresholds = payload["thresholds"]
        return cls(
            baseline,
            build_rule_engine(float(thresholds["T_SNR"]), float(thresholds["T_BW"])),
        )

    @staticmethod
    def _jamming_severity(snr_db: float) -> Severity:
        if snr_db >= 50.0:
            return Severity.HIGH
        if snr_db >= 40.0:
            return Severity.MEDIUM
        return Severity.LOW

    @staticmethod
    def _anomaly_severity(normalized_distance: float) -> Severity:
        if normalized_distance > 3.0:
            return Severity.HIGH
        if normalized_distance > 1.5:
            return Severity.MEDIUM
        return Severity.LOW

    def classify(self, signal: Signal) -> ThreatOutput:
        output, _ = self.classify_with_trace(signal)
        return output

    def classify_with_trace(self, signal: Signal) -> tuple[ThreatOutput, DecisionTrace]:
        if not isinstance(signal, Signal):
            raise TypeError("classify requires a validated Signal")
        started = time.perf_counter()
        measurements = {
            feature: float(getattr(signal, feature)) for feature in MEASUREMENT_FIELDS
        }
        rule_result = self.rules.evaluate(measurements)
        anomaly_result = self.anomaly.evaluate(signal)

        per_state_distances = {
            state.name: self.baseline.feature_distances(signal, state)
            for state in (self.baseline.idle, self.baseline.legitimate)
        }
        state_limits = {
            state.name: state.anomaly_limit
            for state in (self.baseline.idle, self.baseline.legitimate)
        }
        strong = signal.snr_db >= self.rules.t_snr
        narrow = 0.0 < signal.occupied_bw_khz <= self.rules.t_bw
        rule_passed = strong and narrow

        if rule_result.triggered_rule is not None:
            classification = Classification.JAMMING
            severity: Severity | None = self._jamming_severity(signal.snr_db)
            evidence = list(rule_result.evidence)
            triggered_rule = rule_result.triggered_rule
            abnormal_features: list[str] = []
            path_taken = "R1"
            plain_english = (
                f"SNR {signal.snr_db:.1f} dB is above {self.rules.t_snr:.1f}, so a "
                f"strong signal is present. Bandwidth {signal.occupied_bw_khz:.1f} kHz "
                f"is narrow (limit {self.rules.t_bw:.1f}), so it looks like jamming. "
                "Rule R1 fired."
            )
        elif anomaly_result.abnormal:
            classification = Classification.UNKNOWN_ANOMALY
            severity = self._anomaly_severity(anomaly_result.normalized_distance)
            evidence = list(anomaly_result.evidence)
            triggered_rule = None
            abnormal_features = list(anomaly_result.abnormal_features)
            path_taken = "ANOMALY"
            plain_english = (
                f"Rule R1 did not fire. The nearest normal state is {anomaly_result.state}; "
                f"its normalized distance is {anomaly_result.normalized_distance:.2f}, "
                "above the limit 1.00, so this is an unknown anomaly."
            )
        else:
            classification = Classification.NORMAL
            severity = None
            evidence = [
                f"Nearest normal state {anomaly_result.state}; normalized distance "
                f"{anomaly_result.normalized_distance:.2f} <= 1.00"
            ]
            triggered_rule = None
            abnormal_features = []
            path_taken = "NORMAL"
            plain_english = (
                f"Rule R1 did not fire. The nearest normal state is {anomaly_result.state}; "
                f"its normalized distance is {anomaly_result.normalized_distance:.2f}, "
                "within the limit 1.00, so this capture is normal."
            )

        processing_ms = (time.perf_counter() - started) * 1000.0
        output = ThreatOutput(
            schema_version="1.0",
            source_module="module2_ai_threat_intelligence",
            observation_id=signal.observation_id,
            sequence_number=signal.sequence_number,
            timestamp=signal.timestamp.isoformat(timespec="milliseconds"),
            classification=classification.value,
            severity=severity.value if severity is not None else None,
            triggered_rule=triggered_rule,
            abnormal_features=abnormal_features,
            statistical_deviation=anomaly_result.statistical_deviation,
            evidence=evidence,
            baseline_version=self.baseline.version,
            processing_ms=processing_ms,
        )
        trace = DecisionTrace(
            steps=(
                DecisionStep(
                    name="Strong signal",
                    expression="snr_db >= T_SNR",
                    actual_values={"snr_db": signal.snr_db},
                    thresholds={"T_SNR": self.rules.t_snr},
                    passed=strong,
                ),
                DecisionStep(
                    name="Narrow bandwidth",
                    expression="0 < occupied_bw_khz <= T_BW",
                    actual_values={"occupied_bw_khz": signal.occupied_bw_khz},
                    thresholds={"lower": 0.0, "T_BW": self.rules.t_bw},
                    passed=narrow,
                ),
                DecisionStep(
                    name="Rule R1",
                    expression="strong signal AND narrow bandwidth",
                    actual_values={
                        "snr_db": signal.snr_db,
                        "occupied_bw_khz": signal.occupied_bw_khz,
                    },
                    thresholds={"T_SNR": self.rules.t_snr, "T_BW": self.rules.t_bw},
                    passed=rule_passed,
                ),
                DecisionStep(
                    name="Nearest-state anomaly",
                    expression="distance / state limit > 1.0",
                    actual_values={
                        "distance": anomaly_result.distance,
                        "normalized_distance": anomaly_result.normalized_distance,
                    },
                    thresholds={"state_limit": state_limits[anomaly_result.state]},
                    passed=anomaly_result.abnormal,
                ),
            ),
            per_state_distances=per_state_distances,
            state_limits=state_limits,
            nearest_state=anomaly_result.state,
            path_taken=path_taken,
            skipped_rules=rule_result.skipped_rules,
            plain_english=plain_english,
        )
        return output, trace


def build_classifier(path: str | Path = DEFAULT_CONFIG_PATH) -> ThreatClassifier:
    return ThreatClassifier.from_config(path)

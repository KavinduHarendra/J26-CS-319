"""Sample coherent synthetic evidence profiles and run the real decision engine."""

from collections import Counter
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from itertools import product
from random import Random

from models.defense import EvaluateRequest
from response_ml.dataset import DatasetRow, Provenance, make_row
from response_ml.features import FEATURE_COLUMNS
from services.evidence_service import assess_evidence


# A profile is a complete Module 3 report. Its fields vary together.
COMMUNICATION = {
    "clear": ("TRUSTED", "FRESH", "VALID", "VALID", "MAINTAIN"),
    "clear_no_decision": ("TRUSTED", "FRESH", "VALID", "VALID", None),
    "degraded_stable": ("DEGRADED", "FRESH", "VALID", "VALID", "MAINTAIN"),
    "degraded_backup": ("DEGRADED", "FRESH", "VALID", "VALID", "BACKUP"),
    "degraded_switch": ("DEGRADED", "FRESH", "VALID", "VALID", "SWITCH"),
    "degraded_stale": ("DEGRADED", "STALE", "VALID", "VALID", "BACKUP"),
    "degraded_no_decision": ("DEGRADED", "FRESH", "VALID", "VALID", None),
    "suspicious_signal": ("SUSPICIOUS", "FRESH", "VALID", "VALID", "MAINTAIN"),
    "suspicious_auth": ("SUSPICIOUS", "FRESH", "SUSPICIOUS", "VALID", "BACKUP"),
    "suspicious_integrity": ("SUSPICIOUS", "FRESH", "VALID", "SUSPICIOUS", "BACKUP"),
    "suspicious_stale": ("SUSPICIOUS", "STALE", "SUSPICIOUS", "VALID", "BACKUP"),
    "suspicious_both": ("SUSPICIOUS", "FRESH", "SUSPICIOUS", "SUSPICIOUS", "SECURE_HOLD"),
    "untrusted_auth_failure": ("UNTRUSTED", "FRESH", "INVALID", "VALID", "SECURE_HOLD"),
    "untrusted_auth_stale": ("UNTRUSTED", "STALE", "INVALID", "VALID", "SECURE_HOLD"),
    "untrusted_integrity_failure": ("UNTRUSTED", "FRESH", "VALID", "INVALID", "SECURE_HOLD"),
    "untrusted_integrity_stale": ("UNTRUSTED", "STALE", "VALID", "INVALID", "SECURE_HOLD"),
    "untrusted_dual_failure": ("UNTRUSTED", "FRESH", "INVALID", "INVALID", "SECURE_HOLD"),
    "untrusted_dual_stale": ("UNTRUSTED", "STALE", "INVALID", "INVALID", "SECURE_HOLD"),
    "untrusted_stale_conflict": ("UNTRUSTED", "STALE", "SUSPICIOUS", "SUSPICIOUS", "SECURE_HOLD"),
    "replay_suspicious": ("SUSPICIOUS", "REPLAY", "SUSPICIOUS", "VALID", "SECURE_HOLD"),
    "replay_untrusted": ("UNTRUSTED", "REPLAY", "SUSPICIOUS", "SUSPICIOUS", "SECURE_HOLD"),
    "replay_integrity_failure": ("UNTRUSTED", "REPLAY", "VALID", "INVALID", "SECURE_HOLD"),
    # Explicit conflict-testing profile for the existing 85-point policy gap.
    "gap_dual_failure": ("SUSPICIOUS", "STALE", "INVALID", "INVALID", "SECURE_HOLD"),
}
CLEAR = ("clear", "clear_no_decision")
DEGRADED = ("degraded_stable", "degraded_backup", "degraded_no_decision")
SUSPICIOUS = ("suspicious_signal", "suspicious_auth", "suspicious_integrity", "suspicious_stale")
REPLAY = ("replay_suspicious", "replay_untrusted", "replay_integrity_failure")
RF_SEVERITIES = ("Low", "Medium", "High")


@dataclass(frozen=True)
class ScenarioFamily:
    classification: str
    severities: tuple[str | None, ...]
    communication: tuple[str, ...]


# Recovery and escalation are related observations within a session. Each
# named family has its own allowable profiles instead of independent flags.
FAMILIES = {
    "s1_normal_operation": ScenarioFamily("Normal", (None,), CLEAR + ("degraded_stable",)),
    "s2_low_jamming": ScenarioFamily("Jamming", ("Low", "Medium"), CLEAR + DEGRADED),
    "s3_critical_jamming": ScenarioFamily("Jamming", ("Medium", "High"), DEGRADED + (
        "degraded_switch", "suspicious_auth", "untrusted_integrity_failure",
    )),
    "s4_comm_compromise": ScenarioFamily("Jamming", ("Medium", "High"), (
        "suspicious_auth", "suspicious_both", "untrusted_auth_failure", "untrusted_integrity_failure", "untrusted_dual_failure",
        "untrusted_dual_stale",
    )),
    "s5_unknown_anomaly_trusted": ScenarioFamily("Unknown Anomaly", RF_SEVERITIES, CLEAR + ("degraded_stable",)),
    "s6_unknown_suspicious": ScenarioFamily("Unknown Anomaly", ("Medium", "High"), CLEAR + SUSPICIOUS),
    "s7_conflicting_evidence": ScenarioFamily("Normal", (None,), (
        "suspicious_auth", "suspicious_both", "untrusted_stale_conflict", "untrusted_auth_failure",
    )),
    "s8_replay_attempt": ScenarioFamily("Normal", (None,), REPLAY + ("suspicious_stale",)),
    "s9_escalating_attack": ScenarioFamily("Jamming", RF_SEVERITIES, (
        "degraded_backup", "degraded_stale", "suspicious_integrity", "untrusted_dual_stale", "replay_untrusted",
    )),
    "s10_suspicious_command": ScenarioFamily("Normal", (None,), CLEAR + ("degraded_stable",) + SUSPICIOUS),
    "s11_integrity_failure": ScenarioFamily("Normal", (None,), (
        "suspicious_integrity", "untrusted_integrity_failure", "untrusted_integrity_stale", "untrusted_dual_failure",
    )),
    "normal_degraded_link": ScenarioFamily("Normal", (None,), CLEAR + DEGRADED + ("degraded_stale",)),
    "critical_monitoring_gap": ScenarioFamily("Normal", (None,), (
        "gap_dual_failure", "suspicious_stale", "suspicious_both",
        "untrusted_dual_failure", "untrusted_auth_stale",
    )),
    "unknown_degraded_link": ScenarioFamily("Unknown Anomaly", ("Low", "Medium"), CLEAR + DEGRADED + ("degraded_stale",)),
    "unknown_untrusted_link": ScenarioFamily("Unknown Anomaly", ("Medium", "High"), CLEAR + (
        "suspicious_auth", "suspicious_stale", "untrusted_auth_failure", "untrusted_integrity_stale",
    )),
    "medium_jamming_degraded": ScenarioFamily("Jamming", ("Low", "Medium"), CLEAR + DEGRADED + (
        "degraded_stale", "suspicious_signal",
    )),
    "normal_auth_invalid": ScenarioFamily("Normal", (None,), (
        "suspicious_auth", "untrusted_auth_failure", "untrusted_auth_stale", "untrusted_dual_failure",
    )),
    "high_jamming_trusted": ScenarioFamily("Jamming", ("Medium", "High"), CLEAR + (
        "degraded_stable", "suspicious_signal", "untrusted_integrity_failure",
    )),
}

START = datetime(2026, 1, 1, tzinfo=timezone.utc)
FLAG_NAMES = ("snr", "noise_floor", "packet_rate", "rssi")
FLAG_COUNTS = {None: (0,), "Low": (1, 2), "Medium": (2, 3), "High": (2, 3, 4)}
CONFIDENCE_VALUES = (None, *(value / 100 for value in range(60, 99)))
STRUCTURAL_FEATURES = tuple(name for name in FEATURE_COLUMNS if name != "threat_confidence")


def feature_signature(row: DatasetRow, columns: tuple[str, ...] = FEATURE_COLUMNS) -> tuple:
    return tuple(getattr(row, name) for name in columns)


@lru_cache(maxsize=None)
def _assessed_candidate(classification, severity, flag_count, profile, upstream_confidence) -> DatasetRow:
    link, freshness, auth, integrity, decision = COMMUNICATION[profile]
    triggered_rule = ("J01" if severity == "High" else "J02") if classification == "Jamming" else None
    request = EvaluateRequest.model_validate({
        "threat_intelligence": {
            "classification": classification, "severity": severity, "triggered_rule": triggered_rule,
            "abnormal_features": list(FLAG_NAMES[:flag_count]), "threat_confidence": upstream_confidence,
        },
        "secure_communication": {
            "link_state": link, "freshness_state": freshness, "auth_state": auth,
            "integrity_state": integrity, "replay_detected": freshness == "REPLAY", "comm_decision": decision,
        },
    })
    return make_row(assess_evidence(request), Provenance(
        observation_id="CANDIDATE", session_id="CANDIDATE", experiment_id="CANDIDATE", scenario_id="CANDIDATE",
        observed_at_utc=START, data_source="SYNTHETIC", provenance="PYTHON_GENERATED", raw_record_ref="candidate",
    ))


@lru_cache(maxsize=len(FAMILIES))
def _candidates(family_id: str) -> tuple:
    family = FAMILIES[family_id]
    result = []
    for severity in family.severities:
        for flags, profile, confidence in product(FLAG_COUNTS[severity], family.communication, CONFIDENCE_VALUES):
            row = _assessed_candidate(family.classification, severity, flags, profile, confidence)
            result.append((row, feature_signature(row), feature_signature(row, STRUCTURAL_FEATURES)))
    return tuple(result)


def generate_rows(count: int, seed: int, session_size: int) -> list[DatasetRow]:
    if count < 1 or session_size < 1:
        raise ValueError("Count and session size must each be at least 1.")

    rng = Random(seed)
    scenarios = list(FAMILIES)
    pools = {}
    seen = set()
    family_structure_counts = Counter()
    structure_counts = Counter()
    recommendation_counts = Counter()
    rows = []
    run_id = f"SYN-V3-{seed}-N{session_size}"
    for session_number, first in enumerate(range(0, count, session_size)):
        index = session_number % len(scenarios)
        if index == 0:
            rng.shuffle(scenarios)
        family_id = scenarios[index]
        if family_id not in pools:
            pools[family_id] = list(_candidates(family_id))
            rng.shuffle(pools[family_id])

        for number in range(first, min(first + session_size, count)):
            candidate, signature, structure = min(pools[family_id], key=lambda option: (
                option[1] in seen, family_structure_counts[family_id, option[2]],
                recommendation_counts[option[0].rule_based_response],
                structure_counts[option[2]],
            ))
            seen.add(signature)
            family_structure_counts[family_id, structure] += 1
            structure_counts[structure] += 1
            recommendation_counts[candidate.rule_based_response] += 1
            rows.append(candidate.model_copy(update={
                "observation_id": f"{run_id}-O{number + 1:06d}",
                "session_id": f"{run_id}-S{session_number + 1:04d}",
                "experiment_id": run_id,
                "scenario_id": family_id,
                "observed_at_utc": START + timedelta(seconds=session_number * max(60, session_size) + number - first),
                "raw_record_ref": f"synthetic-v3:{seed}:{session_size}:{number + 1}",
            }))
    return rows

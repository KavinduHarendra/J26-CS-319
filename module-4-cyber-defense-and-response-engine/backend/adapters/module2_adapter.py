"""Adapter for Module 2 — AI Threat Intelligence.

This adapter normalizes Module 2's threat intelligence output for
consumption by Module 4's pipeline. It enforces interpretation rules:

- "Normal"          → within expected range
- "Jamming"         → known pattern matched
- "Unknown Anomaly" → abnormal but unconfirmed; handled conservatively

Module 2 integration point is isolated here so changes to Module 2's
output schema only require updates to this file.
"""

from models.module2 import ThreatIntelligence, StatisticalDeviation


VALID_CLASSIFICATIONS = {"Normal", "Jamming", "Unknown Anomaly"}
VALID_SEVERITIES = {"Low", "Medium", "High", None}


def adapt(raw: dict | None) -> ThreatIntelligence:
    """Validate and normalize Module 2 output into typed ThreatIntelligence.

    Enforces classification whitelist and Unknown Anomaly conservative handling.
    """
    if not raw:
        return _mock_default()

    classification = raw.get("classification", "Normal")
    if classification not in VALID_CLASSIFICATIONS:
        # Unknown classification treated conservatively as Unknown Anomaly
        classification = "Unknown Anomaly"

    severity = raw.get("severity")
    if severity not in VALID_SEVERITIES:
        severity = None

    # Parse statistical deviation sub-model if present
    stat_dev = None
    if raw.get("statistical_deviation"):
        try:
            stat_dev = StatisticalDeviation(**raw["statistical_deviation"])
        except Exception:
            stat_dev = None

    return ThreatIntelligence(
        classification=classification,
        threat_confidence=raw.get("threat_confidence"),
        severity=severity,
        triggered_rule=raw.get("triggered_rule"),
        abnormal_features=raw.get("abnormal_features", []),
        statistical_deviation=stat_dev,
        evidence=raw.get("evidence", []),
    )


def _mock_default() -> ThreatIntelligence:
    """Return safe mock threat intelligence when Module 2 is unavailable."""
    return ThreatIntelligence(
        classification="Normal",
        severity=None,
        evidence=["[MOCK] Module 2 unavailable — using safe default classification"],
    )


def summary_dict(ti: ThreatIntelligence) -> dict:
    """Return a flat audit-friendly dict of the threat intelligence."""
    return {
        "classification": ti.classification,
        "threat_confidence": ti.threat_confidence,
        "severity": ti.severity,
        "triggered_rule": ti.triggered_rule,
        "abnormal_features": ti.abnormal_features,
        "evidence": ti.evidence,
        "statistical_deviation": ti.statistical_deviation.model_dump() if ti.statistical_deviation else None,
    }

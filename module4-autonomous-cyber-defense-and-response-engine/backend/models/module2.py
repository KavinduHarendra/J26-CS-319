"""Module 2 — AI Threat Intelligence output model.

Module 2 owns RF threat classification and anomaly analysis using
rule-based jamming detection and statistical anomaly detection.
This schema defines the data contract flowing from Module 2 into Module 4.
"""

from typing import Optional, Literal
from pydantic import BaseModel, Field


ClassificationValue = Literal["Normal", "Jamming", "Unknown Anomaly"]
SeverityValue = Optional[Literal["Low", "Medium", "High"]]


class StatisticalDeviation(BaseModel):
    """Per-feature statistical deviation scores from Module 2."""
    rssi: Optional[float] = None
    snr: Optional[float] = None
    noise_floor: Optional[float] = None
    packet_rate: Optional[float] = None


class ThreatIntelligence(BaseModel):
    """Threat intelligence output produced by Module 2 (N. K. B. H. Rathnayake).

    Module 4 consumes this for:
    - classification-based risk weighting
    - severity-based risk weighting
    - triggered rule identification (for explainability)
    - evidence strings (for explainability)
    Module 4 does NOT reclassify or re-detect threats.

    Interpretation rules enforced by Module 4:
    - "Normal"          → RF within expected range
    - "Jamming"         → Known RF interference/jamming pattern matched
    - "Unknown Anomaly" → Abnormal but does NOT match known rule; treated conservatively
    """

    classification: ClassificationValue = Field(
        default="Normal",
        description="RF threat classification: Normal | Jamming | Unknown Anomaly"
    )
    severity: SeverityValue = Field(
        default=None,
        description="Severity level: Low | Medium | High | null (None for Normal)"
    )
    triggered_rule: Optional[str] = Field(
        default=None,
        description="Jamming rule ID that triggered (e.g. J01). None if not applicable."
    )
    abnormal_features: list[str] = Field(
        default_factory=list,
        description="List of feature names flagged as abnormal by Module 2"
    )
    statistical_deviation: Optional[StatisticalDeviation] = Field(
        default=None,
        description="Per-feature deviation z-scores or normalized deviation values"
    )
    evidence: list[str] = Field(
        default_factory=list,
        description="Human-readable evidence strings from Module 2"
    )

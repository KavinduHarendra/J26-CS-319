"""Versioned JSON contracts for file-based module integration."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, SerializerFunctionWrapHandler, model_serializer

from src.classifier import ThreatOutput


ClassificationContract = Literal["NORMAL", "JAMMING", "UNKNOWN_ANOMALY"]
SeverityContract = Literal["LOW", "MEDIUM", "HIGH"]
Recipient = Literal["module3", "module4"]


class ThreatStateOut(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1.0"]
    source_module: Literal["module2_ai_threat_intelligence"]
    sequence_number: int = Field(ge=1, le=999_999)
    observation_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    timestamp: datetime
    classification: ClassificationContract
    severity: SeverityContract | None
    triggered_rule: str | None
    abnormal_features: list[str]
    statistical_deviation: dict[str, float]
    evidence: list[str]
    baseline_version: str = Field(min_length=1)
    processing_ms: float = Field(ge=0.0, allow_inf_nan=False)
    recipient: Recipient
    fuzzy_score: float | None = Field(default=None, ge=0.0, le=100.0, allow_inf_nan=False)
    fuzzy_rules_fired: list[str] | None = None
    session_id: str | None = Field(default=None, pattern=r"^[A-Za-z0-9_-]{1,64}$")

    @model_serializer(mode="wrap")
    def _omit_absent_session(self, handler: SerializerFunctionWrapHandler) -> dict:
        # Files without a session stay byte-identical to the pre-session format.
        data = handler(self)
        if data.get("session_id") is None:
            data.pop("session_id", None)
        return data


def to_contract(
    output: ThreatOutput, *, recipient: Recipient, session_id: str | None = None
) -> ThreatStateOut:
    return ThreatStateOut(
        schema_version=output.schema_version,
        source_module=output.source_module,
        sequence_number=output.sequence_number,
        observation_id=output.observation_id,
        timestamp=datetime.fromisoformat(output.timestamp),
        classification=output.classification,
        severity=output.severity,
        triggered_rule=output.triggered_rule,
        abnormal_features=output.abnormal_features,
        statistical_deviation=output.statistical_deviation,
        evidence=output.evidence,
        baseline_version=output.baseline_version,
        processing_ms=output.processing_ms,
        recipient=recipient,
        fuzzy_score=output.fuzzy_score,
        fuzzy_rules_fired=output.fuzzy_rules_fired,
        session_id=session_id,
    )

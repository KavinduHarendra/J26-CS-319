"""Versioned JSON contracts for file-based module integration."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from src.classifier import ThreatOutput


SCHEMA_VERSION = "1.0"
MODULE1_SOURCE = "module1_sdr_rf_threat_detection"
MODULE2_SOURCE = "module2_ai_threat_intelligence"

ClassificationContract = Literal["NORMAL", "JAMMING", "UNKNOWN_ANOMALY"]
SeverityContract = Literal["LOW", "MEDIUM", "HIGH"]
Recipient = Literal["module3", "module4"]


class MeasurementsIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    peak_freq_mhz: float = Field(ge=0.0, le=100_000.0, allow_inf_nan=False)
    peak_db: float = Field(ge=-300.0, le=100.0, allow_inf_nan=False)
    noise_db: float = Field(ge=-300.0, le=100.0, allow_inf_nan=False)
    snr_db: float = Field(ge=-200.0, le=300.0, allow_inf_nan=False)
    band_power_dbfs: float = Field(ge=-300.0, le=100.0, allow_inf_nan=False)
    occupied_bw_khz: float = Field(ge=0.0, le=1_000_000.0, allow_inf_nan=False)
    spectral_flatness: float = Field(ge=0.0, le=1.0, allow_inf_nan=False)


class ObservationIn(BaseModel):
    model_config = ConfigDict(extra="forbid", strict=True)

    schema_version: Literal["1.0"]
    source_module: Literal["module1_sdr_rf_threat_detection"]
    sequence_number: int = Field(ge=1, le=999_999)
    observation_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,64}$")
    timestamp: datetime
    elapsed_s: float = Field(ge=0.0, le=1_000_000_000.0, allow_inf_nan=False)
    measurements: MeasurementsIn


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


def to_contract(output: ThreatOutput, *, recipient: Recipient) -> ThreatStateOut:
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
    )

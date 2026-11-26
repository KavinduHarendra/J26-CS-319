"""Configure rule-based, shadow and experimental response selection."""

import os
from enum import Enum
from math import isfinite
from typing import Literal

from pydantic import BaseModel, Field

from response_ml.features import FEATURE_SCHEMA_VERSION, FeatureSchemaVersion, ResponseFeatures


class ResponseMode(str, Enum):
    RULE_BASED = "RULE_BASED"
    SHADOW = "SHADOW"
    MACHINE_LEARNING = "MACHINE_LEARNING"


MODE_VARIABLE = "MODULE4_RESPONSE_MODE"
THRESHOLD_VARIABLE = "MODULE4_EXPERIMENTAL_MIN_CONFIDENCE"


def read_response_mode() -> ResponseMode:
    value = os.getenv(MODE_VARIABLE, ResponseMode.RULE_BASED.value).strip().upper()
    try:
        return ResponseMode(value)
    except ValueError:
        choices = ", ".join(mode.value for mode in ResponseMode)
        raise ValueError(f"{MODE_VARIABLE} must be one of: {choices}.") from None


def read_experimental_minimum_confidence() -> float | None:
    value = os.getenv(THRESHOLD_VARIABLE)
    if value is None:
        return None
    try:
        threshold = float(value)
    except ValueError:
        threshold = -1
    if not isfinite(threshold) or not 0 <= threshold <= 1:
        raise ValueError(f"{THRESHOLD_VARIABLE} must be a finite number from 0 to 1.")
    return threshold


class ResponseSelectionMetadata(BaseModel):
    configured_mode: Literal[ResponseMode.SHADOW, ResponseMode.MACHINE_LEARNING]
    effective_mode: Literal[ResponseMode.RULE_BASED, ResponseMode.MACHINE_LEARNING] = ResponseMode.RULE_BASED
    response_source: Literal[
        "RULE_BASED", "MACHINE_LEARNING", "SAFETY_POLICY",
        "SCREENED_RULE_FALLBACK", "SAFETY_POLICY_FALLBACK", "EVIDENCE_FALLBACK",
    ] = "RULE_BASED"
    rule_based_response: str
    ml_status: Literal["SUCCEEDED", "FAILED"]
    feature_schema_version: FeatureSchemaVersion = FEATURE_SCHEMA_VERSION
    features: ResponseFeatures | None = None
    ml_error_code: str | None = None
    ml_raw_response: str | None = None
    ml_screened_response: str | None = None
    ml_screening_reason: str | None = None
    ml_prediction_confidence: float | None = Field(default=None, ge=0, le=1)
    ml_confidence_calibrated: Literal[False] = False
    ml_class_probabilities: dict[str, float] | None = None
    ml_model_version: str | None = None
    ml_inference_latency_ms: float | None = Field(default=None, ge=0)
    rule_based_disagreement: bool | None = None
    experimental_min_confidence: float | None = None
    safety_override: bool = False
    safety_override_reason: str | None = None
    fallback_used: bool = False
    fallback_reason: str | None = None

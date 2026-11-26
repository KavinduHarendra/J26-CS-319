"""Select and explain the active recommendation for an opted-in research mode."""

import logging

from pydantic import ValidationError

from models.module3 import SecureCommunication
from response_ml.features import extract_features
from response_ml.modes import ResponseMode, ResponseSelectionMetadata, read_experimental_minimum_confidence
from response_ml.prototype_safety import screen_recommendation
from response_ml.rubric import mandatory_hold
from services import ml_inference_service
from services.evidence_service import AssessedEvidence

LOGGER = logging.getLogger(__name__)


def initialize_response_selection(mode: ResponseMode) -> None:
    if mode == ResponseMode.MACHINE_LEARNING:
        read_experimental_minimum_confidence()
    if mode != ResponseMode.RULE_BASED:
        ml_inference_service.get_model()


def _fallback(metadata: ResponseSelectionMetadata, evidence: AssessedEvidence,
              reason: str) -> tuple[str, str, ResponseSelectionMetadata]:
    metadata.fallback_used = True
    metadata.fallback_reason = reason
    if metadata.features is None:
        try:
            communication = SecureCommunication.model_validate(evidence.communication.model_dump())
            hold = mandatory_hold(communication)
        except ValidationError:
            hold = None
        recommendation = hold.response if hold else "OPERATOR_ESCALATION"
        metadata.response_source = "EVIDENCE_FALLBACK"
        metadata.safety_override = recommendation != metadata.rule_based_response
        if metadata.safety_override:
            metadata.safety_override_reason = hold.criterion if hold else "INSUFFICIENT_MODEL_EVIDENCE"
        rationale = f"Experimental ML fallback ({reason}). Incomplete model evidence requires operator review."
        if hold:
            rationale += f" The validated communication evidence requires a hold ({hold.criterion})."
        return recommendation, rationale, metadata

    screened = screen_recommendation(metadata.features, metadata.rule_based_response)
    metadata.safety_override = screened.reason is not None
    metadata.safety_override_reason = screened.reason
    metadata.response_source = "SAFETY_POLICY_FALLBACK" if screened.reason else "SCREENED_RULE_FALLBACK"
    rationale = f"Experimental ML fallback ({reason}). The proposed safety policy screened the contextual candidate."
    if screened.reason:
        rationale += f" Safety override: {screened.reason}."
    return screened.recommendation, rationale, metadata


def select_research_response(mode: ResponseMode, evidence: AssessedEvidence,
                             rule_response: str, rule_rationale: str) -> tuple[str, str, ResponseSelectionMetadata]:
    threshold = read_experimental_minimum_confidence() if mode == ResponseMode.MACHINE_LEARNING else None
    details = ResponseSelectionMetadata(
        configured_mode=mode, rule_based_response=rule_response, ml_status="FAILED",
        experimental_min_confidence=threshold,
    )
    try:
        details.features = extract_features(evidence)
        prediction = ml_inference_service.predict(details.features)
    except (ValidationError, ml_inference_service.InferenceError) as error:
        code = error.code if isinstance(error, ml_inference_service.InferenceError) else "INVALID_MODEL_FEATURES"
        details.ml_error_code = code
        if code == "INVALID_MODEL_FEATURES":
            details.features = None
        LOGGER.info("Module 4 prediction unavailable in %s mode: %s", mode.value, code)
        if mode == ResponseMode.SHADOW:
            return rule_response, rule_rationale, details
        return _fallback(details, evidence, code)

    details.ml_status = "SUCCEEDED"
    details.ml_raw_response = prediction.response
    details.ml_prediction_confidence = prediction.confidence
    details.ml_class_probabilities = prediction.probabilities
    details.ml_model_version = prediction.model_version
    details.ml_inference_latency_ms = prediction.latency_ms
    details.rule_based_disagreement = prediction.response != rule_response
    screened = screen_recommendation(details.features, prediction.response)
    details.ml_screened_response = screened.recommendation
    details.ml_screening_reason = screened.reason

    if mode == ResponseMode.SHADOW:
        return rule_response, rule_rationale, details
    if threshold is not None and prediction.confidence < threshold:
        return _fallback(details, evidence, "BELOW_EXPERIMENTAL_THRESHOLD")

    details.effective_mode = ResponseMode.MACHINE_LEARNING
    details.safety_override = screened.reason is not None
    details.safety_override_reason = screened.reason
    details.response_source = "SAFETY_POLICY" if screened.reason else "MACHINE_LEARNING"
    rationale = "The experimental Random Forest recommendation was evaluated under the proposed safety policy."
    if screened.reason:
        rationale += f" Safety override: {screened.reason}."
    return screened.recommendation, rationale, details

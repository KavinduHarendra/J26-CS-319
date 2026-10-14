"""Strict file-based integration for Module 2 and Module 3 JSON outputs."""

import json
from datetime import datetime
from typing import Any

from fastapi import UploadFile

from models.defense import EvaluateRequest
from models.module1 import RFContext
from models.module2 import ThreatIntelligence, StatisticalDeviation
from models.module3 import SecureCommunication

SUPPORTED_SCHEMA_VERSION = "1.0"
TIMESTAMP_THRESHOLD_SECONDS = 5


class IntegrationValidationError(Exception):
    """A user-correctable integration input error."""

    def __init__(self, source: str, error_code: str, message: str, field: str | None = None):
        super().__init__(message)
        self.source = source
        self.error_code = error_code
        self.message = message
        self.field = field

    def as_dict(self) -> dict[str, Any]:
        result = {
            "integration_status": "FAILED",
            "source": self.source,
            "error_code": self.error_code,
            "message": self.message,
        }
        if self.field:
            result["field"] = self.field
        return result


async def _read_json(upload: UploadFile, source: str) -> dict[str, Any]:
    content = await upload.read()
    if not content.strip():
        raise IntegrationValidationError(source, "EMPTY_FILE", f"{source} file is empty.")
    try:
        payload = json.loads(content)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise IntegrationValidationError(source, "INVALID_JSON", f"{source} file is not valid JSON: {exc}") from exc
    if not isinstance(payload, dict):
        raise IntegrationValidationError(source, "INVALID_JSON", f"{source} output must be a JSON object.")
    version = payload.get("schema_version")
    if version is not None and version != SUPPORTED_SCHEMA_VERSION:
        raise IntegrationValidationError(
            source, "UNSUPPORTED_SCHEMA_VERSION",
            f"{source} schema version '{version}' is not supported.",
            "schema_version",
        )
    return payload


def _timestamp(value: Any, source: str) -> datetime:
    if not isinstance(value, str) or not value.strip():
        raise IntegrationValidationError(source, "INVALID_TIMESTAMP", f"{source} timestamp must be an ISO 8601 string.", "timestamp")
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise IntegrationValidationError(source, "INVALID_TIMESTAMP", f"{source} timestamp is invalid.", "timestamp") from exc


def _required(payload: dict[str, Any], fields: tuple[str, ...], source: str) -> None:
    for field in fields:
        if field not in payload or payload[field] in (None, ""):
            raise IntegrationValidationError(source, "MISSING_REQUIRED_FIELD", f"{source} output does not contain {field}.", field)


def _module2(payload: dict[str, Any]) -> tuple[dict[str, Any], datetime]:
    source = "MODULE_2"
    # Normal observations commonly omit severity; the Module 2 contract treats
    # it as nullable and the HCRDM scorer assigns no severity points in that case.
    _required(payload, ("observation_id", "timestamp", "classification"), source)
    timestamp = _timestamp(payload["timestamp"], source)
    if payload["classification"] not in {"Normal", "Jamming", "Unknown Anomaly"}:
        raise IntegrationValidationError(source, "INVALID_CLASSIFICATION", "Module 2 classification is not supported.", "classification")
    severity = payload.get("severity")
    if severity not in {"Low", "Medium", "High", None}:
        raise IntegrationValidationError(source, "INVALID_SEVERITY", "Module 2 severity is not supported.", "severity")
    payload["severity"] = severity
    return payload, timestamp


def _module3(payload: dict[str, Any]) -> tuple[dict[str, Any], datetime | None]:
    source = "MODULE_3"
    _required(payload, ("link_state",), source)
    if payload["link_state"] not in {"TRUSTED", "DEGRADED", "SUSPICIOUS", "UNTRUSTED"}:
        raise IntegrationValidationError(source, "INVALID_LINK_STATE", "Module 3 link_state is not supported.", "link_state")
    timestamp = _timestamp(payload["timestamp"], source) if payload.get("timestamp") is not None else None
    for field, values, code in (
        ("freshness_state", {"FRESH", "STALE", "REPLAY"}, "INVALID_FRESHNESS_STATE"),
        ("auth_state", {"VALID", "SUSPICIOUS", "INVALID"}, "INVALID_AUTH_STATE"),
        ("integrity_state", {"VALID", "SUSPICIOUS", "INVALID"}, "INVALID_INTEGRITY_STATE"),
    ):
        if payload.get(field) is not None and payload[field] not in values:
            raise IntegrationValidationError(source, code, f"Module 3 {field} is not supported.", field)
    return payload, timestamp


async def build_request(module2_file: UploadFile, module3_file: UploadFile) -> tuple[EvaluateRequest, dict[str, Any]]:
    """Read, validate, match, and normalize both module files."""
    module2, module3 = await _read_json(module2_file, "MODULE_2"), await _read_json(module3_file, "MODULE_3")
    module2, timestamp2 = _module2(module2)
    module3, timestamp3 = _module3(module3)

    id2, id3 = module2["observation_id"], module3.get("observation_id")
    if id2 and id3 and id2 != id3:
        raise IntegrationValidationError(
            "INTEGRATION", "OBSERVATION_ID_MISMATCH",
            "Module 2 and Module 3 files refer to different observations.",
        )
    match_method = "observation_id"
    if not id3:
        if timestamp3 is None:
            raise IntegrationValidationError("INTEGRATION", "TIMESTAMP_MISMATCH", "Module 3 needs timestamp when observation_id is absent.")
        delta = abs((timestamp2 - timestamp3).total_seconds())
        if delta > TIMESTAMP_THRESHOLD_SECONDS:
            raise IntegrationValidationError("INTEGRATION", "TIMESTAMP_MISMATCH", f"Module timestamps differ by {delta:.1f}s; maximum is {TIMESTAMP_THRESHOLD_SECONDS}s.")
        match_method = "timestamp_fallback"

    deviation = module2.get("statistical_deviation") or {}
    request = EvaluateRequest(
        rf_context=RFContext(
            observation_id=id2,
            timestamp=module2["timestamp"],
            rssi=deviation.get("rssi"),
            snr=deviation.get("snr"),
            noise_floor=deviation.get("noise_floor"),
            packet_rate=deviation.get("packet_rate"),
        ),
        threat_intelligence=ThreatIntelligence(
            classification=module2["classification"],
            severity=module2["severity"],
            triggered_rule=module2.get("triggered_rule"),
            abnormal_features=module2.get("abnormal_features") or [],
            statistical_deviation=StatisticalDeviation(**deviation) if deviation else None,
            evidence=module2.get("evidence") or [],
        ),
        secure_communication=SecureCommunication(
            link_state=module3["link_state"],
            freshness_state=module3.get("freshness_state", "FRESH"),
            auth_state=module3.get("auth_state", "VALID"),
            integrity_state=module3.get("integrity_state", "VALID"),
            replay_detected=bool(module3.get("replay_detected", False)),
            comm_decision=module3.get("comm_decision"),
            link_evidence=module3.get("link_evidence") or [],
        ),
    )
    metadata = {
        "integration_mode": "FILE",
        "match_method": match_method,
        "module2_file": module2_file.filename or "module2.json",
        "module3_file": module3_file.filename or "module3.json",
    }
    return request, metadata

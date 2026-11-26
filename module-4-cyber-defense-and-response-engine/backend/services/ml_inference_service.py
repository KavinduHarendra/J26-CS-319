"""Load the pinned local prototype once and return validated raw predictions."""

import hashlib
import json
import logging
import os
import platform
from dataclasses import dataclass
from functools import lru_cache
from importlib.metadata import PackageNotFoundError, version
from io import BytesIO
from math import isclose, isfinite
from pathlib import Path
from threading import Lock
from time import perf_counter
from typing import Any

from pydantic import ValidationError

from response_ml.features import FEATURE_COLUMNS, ResponseFeatures
from response_ml.rubric import RESPONSE_CLASSES, RUBRIC_VERSION

MODEL_DIR_VARIABLE = "MODULE4_MODEL_DIR"
MODEL_VERSION = "synthetic-random-forest-v1"
MODEL_FILENAME = "prototype-random-forest.joblib"
METADATA_FILENAME = "model-metadata.json"
TRUSTED_MODEL_SHA256 = "948d4a3d23e1483305a9ba6d642443e29b3afcc218917644081f4d6449cf0ad2"
TRUSTED_METADATA_SHA256 = "7314e8a0dd9e42650b0a0bb6bf37895e0b8505d315ceb420b28b48232af97f8f"
DEFAULT_MODEL_DIR = Path(__file__).resolve().parents[2] / ".response-ml" / "prototype-v1" / "model"
INFERENCE_DEPENDENCIES = ("scikit-learn", "joblib", "numpy", "scipy", "pydantic")
CLASS_ORDER = tuple(sorted(RESPONSE_CLASSES))
LOGGER = logging.getLogger(__name__)
_LOAD_LOCK = Lock()


class InferenceError(Exception):
    def __init__(self, code: str):
        super().__init__(code)
        self.code = code


@dataclass(frozen=True)
class ModelState:
    pipeline: Any = None
    error_code: str | None = None


@dataclass(frozen=True)
class Prediction:
    response: str
    confidence: float
    probabilities: dict[str, float]
    model_version: str
    latency_ms: float


def _pinned_bytes(path: Path, digest: str, kind: str, limit: int) -> bytes:
    try:
        with path.open("rb") as stream:
            payload = stream.read(limit + 1)
    except FileNotFoundError as exc:
        raise InferenceError(f"{kind}_MISSING") from exc
    except OSError as exc:
        raise InferenceError(f"{kind}_UNREADABLE") from exc
    if len(payload) > limit or hashlib.sha256(payload).hexdigest() != digest:
        raise InferenceError(f"{kind}_CHECKSUM_MISMATCH")
    return payload


def _read_metadata(payload: bytes) -> dict:
    try:
        metadata = json.loads(payload)
    except (ValueError, UnicodeError) as exc:
        raise InferenceError("METADATA_INVALID") from exc
    if not isinstance(metadata, dict):
        raise InferenceError("METADATA_INVALID")
    return metadata


def _validate_metadata(metadata: dict) -> None:
    if (
        metadata.get("experiment") != MODEL_VERSION
        or metadata.get("status") != "EXPERIMENTAL_SYNTHETIC_PROTOTYPE"
        or metadata.get("dataset_version") != "1.2"
        or metadata.get("rubric_version") != RUBRIC_VERSION
        or metadata.get("model_filename") != MODEL_FILENAME
        or metadata.get("model_sha256") != TRUSTED_MODEL_SHA256
    ):
        raise InferenceError("METADATA_INCOMPATIBLE")
    if (
        metadata.get("feature_columns") != list(FEATURE_COLUMNS)
        or metadata.get("feature_definitions") != ResponseFeatures.model_json_schema()["properties"]
    ):
        raise InferenceError("FEATURE_SCHEMA_MISMATCH")
    if metadata.get("class_mapping") != {str(index): label for index, label in enumerate(CLASS_ORDER)}:
        raise InferenceError("CLASS_MAPPING_MISMATCH")

    dependencies = metadata.get("dependencies")
    if not isinstance(dependencies, dict) or not isinstance(dependencies.get("python"), str):
        raise InferenceError("METADATA_INVALID")
    if platform.python_version().split(".")[:2] != dependencies["python"].split(".")[:2]:
        raise InferenceError("DEPENDENCY_MISMATCH")
    try:
        if any(version(package) != dependencies.get(package) for package in INFERENCE_DEPENDENCIES):
            raise InferenceError("DEPENDENCY_MISMATCH")
    except PackageNotFoundError as exc:
        raise InferenceError("DEPENDENCY_UNAVAILABLE") from exc


def _deserialize_pipeline(payload: bytes, metadata: dict):
    try:
        import joblib
        from sklearn.compose import ColumnTransformer
        from sklearn.ensemble import RandomForestClassifier
        from sklearn.pipeline import Pipeline

        from response_ml.preprocessing import CATEGORICAL, NUMERIC
    except (ImportError, OSError, RuntimeError, ValueError) as exc:
        raise InferenceError("DEPENDENCY_UNAVAILABLE") from exc

    if metadata.get("preprocessing", {}).get("numeric") != list(NUMERIC) or (
        metadata.get("preprocessing", {}).get("categorical") != list(CATEGORICAL)
    ):
        raise InferenceError("FEATURE_SCHEMA_MISMATCH")

    try:
        # Deserialize the exact bytes whose checksum was verified. Do not reopen the path.
        pipeline = joblib.load(BytesIO(payload))
        if not isinstance(pipeline, Pipeline):
            raise InferenceError("MODEL_INCOMPATIBLE")
        preprocessing = pipeline.named_steps["preprocessing"]
        classifier = pipeline.named_steps["classifier"]
        if (
            not isinstance(preprocessing, ColumnTransformer)
            or not isinstance(classifier, RandomForestClassifier)
            or pipeline.n_features_in_ != len(FEATURE_COLUMNS)
            or tuple(pipeline.classes_) != CLASS_ORDER
        ):
            raise InferenceError("MODEL_INCOMPATIBLE")
        transformations = {name: list(columns) for name, _, columns in preprocessing.transformers_
                           if name in ("numeric", "categorical")}
        expected = {
            name: [FEATURE_COLUMNS.index(column) for column in columns]
            for name, columns in (("numeric", NUMERIC), ("categorical", CATEGORICAL))
        }
        if transformations != expected:
            raise InferenceError("FEATURE_SCHEMA_MISMATCH")
    except InferenceError:
        raise
    except Exception as exc:
        raise InferenceError("MODEL_LOAD_FAILED") from exc
    return pipeline


@lru_cache(maxsize=1)
def _load_model(directory: Path) -> ModelState:
    try:
        meta_bytes = _pinned_bytes(directory / METADATA_FILENAME, TRUSTED_METADATA_SHA256, "METADATA", 1_000_000)
        metadata = _read_metadata(meta_bytes)
        _validate_metadata(metadata)
        model_bytes = _pinned_bytes(directory / MODEL_FILENAME, TRUSTED_MODEL_SHA256, "MODEL", 5_000_000)
        return ModelState(_deserialize_pipeline(model_bytes, metadata))
    except InferenceError as error:
        LOGGER.warning("Module 4 prototype unavailable: %s", error.code)
        return ModelState(error_code=error.code)


def get_model() -> ModelState:
    try:
        directory = Path(os.getenv(MODEL_DIR_VARIABLE) or DEFAULT_MODEL_DIR).expanduser().absolute()
    except (OSError, RuntimeError, ValueError):
        return ModelState(error_code="MODEL_PATH_INVALID")
    # Prevent concurrent first requests from deserializing the artifact twice.
    with _LOAD_LOCK:
        return _load_model(directory)


def predict(features: ResponseFeatures) -> Prediction:
    try:
        evidence = ResponseFeatures.model_validate(features.model_dump(), strict=True)
    except (AttributeError, ValidationError) as exc:
        raise InferenceError("INVALID_MODEL_FEATURES") from exc
    if evidence.replay_detected != (evidence.freshness_state == "REPLAY"):
        raise InferenceError("INVALID_MODEL_FEATURES")
    state = get_model()
    if state.error_code:
        raise InferenceError(state.error_code)
    if tuple(getattr(state.pipeline, "classes_", ())) != CLASS_ORDER:
        raise InferenceError("UNSUPPORTED_CLASS")

    started = perf_counter()
    try:
        from response_ml.preprocessing import feature_matrix

        values = state.pipeline.predict_proba(feature_matrix([evidence]))
        if values.shape != (1, len(CLASS_ORDER)):
            raise InferenceError("INVALID_PROBABILITIES")
        scores = [float(value) for value in values[0]]
        if any(not isfinite(p) or not 0 <= p <= 1 for p in scores) or not isclose(sum(scores), 1, abs_tol=1e-6):
            raise InferenceError("INVALID_PROBABILITIES")
    except InferenceError:
        raise
    except Exception as exc:
        raise InferenceError("PREDICTION_FAILED") from exc
    latency = (perf_counter() - started) * 1000
    probabilities = dict(zip(CLASS_ORDER, scores, strict=True))
    pick = max(probabilities, key=probabilities.__getitem__)
    return Prediction(pick, probabilities[pick], probabilities, MODEL_VERSION, latency)

import hashlib
import json
import platform
from concurrent.futures import ThreadPoolExecutor
from importlib.metadata import version

import numpy as np
import pytest

from data.evaluate_scenarios import EVALUATE_SCENARIOS
from models.defense import EvaluateRequest
from response_ml.features import FEATURE_COLUMNS, ResponseFeatures, extract_features
from response_ml.rubric import RESPONSE_CLASSES, RUBRIC_VERSION
from services import ml_inference_service as inference
from services.evidence_service import assess_evidence


@pytest.fixture
def bundle(tmp_path, monkeypatch):
    payload = b"stub verified pipeline"
    digest = hashlib.sha256(payload).hexdigest()
    (tmp_path / inference.MODEL_FILENAME).write_bytes(payload)
    monkeypatch.setattr(inference, "TRUSTED_MODEL_SHA256", digest)
    monkeypatch.setenv(inference.MODEL_DIR_VARIABLE, str(tmp_path))
    metadata = {
        "experiment": inference.MODEL_VERSION,
        "status": "EXPERIMENTAL_SYNTHETIC_PROTOTYPE",
        "dataset_version": "1.2",
        "rubric_version": RUBRIC_VERSION,
        "model_filename": inference.MODEL_FILENAME,
        "model_sha256": digest,
        "feature_columns": list(FEATURE_COLUMNS),
        "feature_definitions": ResponseFeatures.model_json_schema()["properties"],
        "class_mapping": {str(index): name for index, name in enumerate(inference.CLASS_ORDER)},
        "dependencies": {"python": platform.python_version(), **{
            package: version(package) for package in inference.INFERENCE_DEPENDENCIES
        }},
    }

    def write_meta():
        data = json.dumps(metadata).encode("utf-8")
        (tmp_path / inference.METADATA_FILENAME).write_bytes(data)
        monkeypatch.setattr(inference, "TRUSTED_METADATA_SHA256", hashlib.sha256(data).hexdigest())

    write_meta()
    return tmp_path, metadata, write_meta


def test_verified_pair_loads_once_under_concurrent_requests(bundle, monkeypatch):
    _, metadata, _ = bundle
    loaded = object()
    calls = []

    def deserialize(payload, document):
        assert payload == b"stub verified pipeline" and document == metadata
        calls.append(payload)
        return loaded

    monkeypatch.setattr(inference, "_deserialize_pipeline", deserialize)
    with ThreadPoolExecutor(max_workers=8) as workers:
        states = list(workers.map(lambda _: inference.get_model(), range(8)))
    assert len(calls) == 1
    assert all(state.pipeline is loaded and state.error_code is None for state in states)


@pytest.mark.parametrize("file, reason", [
    ("model", "MODEL_CHECKSUM_MISMATCH"),
    ("metadata", "METADATA_CHECKSUM_MISMATCH"),
])
def test_modified_artifacts_never_reach_deserialization(bundle, monkeypatch, file, reason):
    path, _, _ = bundle
    filename = inference.MODEL_FILENAME if file == "model" else inference.METADATA_FILENAME
    (path / filename).write_bytes(b"unverified artifact")
    monkeypatch.setattr(inference, "_deserialize_pipeline", lambda *args: pytest.fail("Attempted unverified deserialization"))
    assert inference.get_model().error_code == reason


@pytest.mark.parametrize("change, reason", [
    ("schema", "FEATURE_SCHEMA_MISMATCH"),
    ("definitions", "FEATURE_SCHEMA_MISMATCH"),
    ("classes", "CLASS_MAPPING_MISMATCH"),
    ("dependencies", "DEPENDENCY_MISMATCH"),
])
def test_pinned_metadata_must_also_match_runtime_contract(bundle, monkeypatch, change, reason):
    _, document, update = bundle
    if change == "schema":
        document["feature_columns"].reverse()
    elif change == "definitions":
        document["feature_definitions"]["risk_score"]["maximum"] = 200
    elif change == "classes":
        document["class_mapping"]["0"] = "UNSUPPORTED"
    else:
        document["dependencies"]["scikit-learn"] = "0.0.0"
    update()
    monkeypatch.setattr(inference, "_deserialize_pipeline", lambda *args: pytest.fail("Loaded an incompatible artifact"))
    assert inference.get_model().error_code == reason


def test_missing_model_is_reported(bundle):
    path, _, _ = bundle
    (path / inference.MODEL_FILENAME).unlink()
    assert inference.get_model().error_code == "MODEL_MISSING"


def features():
    request = EvaluateRequest.model_validate(EVALUATE_SCENARIOS["s3_critical_jamming"]["payload"])
    return extract_features(assess_evidence(request))


@pytest.mark.parametrize("action", RESPONSE_CLASSES)
def test_all_six_predictions_use_training_feature_order(monkeypatch, action):
    evidence = features()
    scores = np.zeros((1, len(inference.CLASS_ORDER)))
    scores[0, inference.CLASS_ORDER.index(action)] = 1.0

    class Pipeline:
        classes_ = inference.CLASS_ORDER

        def predict_proba(self, values):
            assert values.shape == (1, 15)
            for index, name in enumerate(FEATURE_COLUMNS):
                expected = getattr(evidence, name)
                actual = values[0, index]
                if expected is None:
                    assert np.isnan(actual)
                else:
                    assert actual == expected
            return scores

    state = inference.ModelState(Pipeline())
    monkeypatch.setattr(inference, "get_model", lambda: state)
    prediction = inference.predict(evidence)
    assert prediction.response == action
    assert prediction.confidence == 1
    assert prediction.model_version == inference.MODEL_VERSION
    assert prediction.latency_ms >= 0
    assert set(prediction.probabilities) == set(RESPONSE_CLASSES)


def test_invalid_features_never_reach_the_model(monkeypatch):
    evidence = features().model_copy(update={"replay_detected": True})
    monkeypatch.setattr(inference, "get_model", lambda: pytest.fail("Invalid features reached the model"))
    with pytest.raises(inference.InferenceError, match="INVALID_MODEL_FEATURES"):
        inference.predict(evidence)


@pytest.mark.parametrize("failure", ["UNSUPPORTED_CLASS", "PREDICTION_FAILED", "INVALID_PROBABILITIES"])
def test_bad_prediction_contract_is_rejected(monkeypatch, failure):
    class Pipeline:
        classes_ = (
            (*inference.CLASS_ORDER[:-1], "UNSUPPORTED") if failure == "UNSUPPORTED_CLASS" else inference.CLASS_ORDER
        )

        def predict_proba(self, values):
            if failure == "PREDICTION_FAILED":
                raise RuntimeError("synthetic prediction error")
            return np.full((1, 6), np.nan)

    monkeypatch.setattr(inference, "get_model", lambda: inference.ModelState(Pipeline()))
    with pytest.raises(inference.InferenceError, match=failure):
        inference.predict(features())

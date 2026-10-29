import copy

import pytest
from fastapi.testclient import TestClient

from src.api import EXAMPLE_OBSERVATION, app


@pytest.fixture(scope="module")
def client():
    with TestClient(app) as test_client:
        yield test_client


def observation(**measurements) -> dict:
    payload = copy.deepcopy(EXAMPLE_OBSERVATION)
    payload["measurements"].update(measurements)
    return payload


def test_normal_looking_observation_is_normal(client):
    response = client.post("/classify", json=observation())

    assert response.status_code == 200
    body = response.json()
    assert body["classification"] == "NORMAL"
    assert body["observation_id"] == "S00001"
    assert body["severity"] is None


def test_jamming_looking_observation_is_jamming(client):
    response = client.post(
        "/classify",
        json=observation(peak_db=-60.0, snr_db=46.0, band_power_dbfs=-25.0, occupied_bw_khz=12.0),
    )

    assert response.status_code == 200
    body = response.json()
    assert body["classification"] == "JAMMING"
    assert body["triggered_rule"] == "R1"
    assert body["severity"] in {"LOW", "MEDIUM", "HIGH"}


def test_classifier_is_built_once_at_startup(client):
    first = client.app.state.classifier
    client.post("/classify", json=observation())

    assert client.app.state.classifier is first


@pytest.mark.parametrize(
    "payload",
    [
        {**EXAMPLE_OBSERVATION, "label": "JAMMING"},
        {key: value for key, value in EXAMPLE_OBSERVATION.items() if key != "measurements"},
        observation(snr_db="high"),
    ],
)
def test_invalid_observation_is_rejected(client, payload):
    response = client.post("/classify", json=payload)

    assert response.status_code == 422

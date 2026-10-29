"""HTTP classification endpoint for Module 1 observations.

Run locally with ``uvicorn src.api:app --reload`` from the module root.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from dataclasses import asdict
from typing import Any

from fastapi import Body, FastAPI, HTTPException, Request

from src.classifier import ThreatClassifier, build_classifier
from src.real_data import parse_signal


EXAMPLE_OBSERVATION = {
    "schema_version": "1.0",
    "source_module": "module1_sdr_rf_threat_detection",
    "observation_id": "S00001",
    "sequence_number": 1,
    "timestamp": "2026-10-23T16:22:20.957",
    "elapsed_s": 0.44,
    "measurements": {
        "peak_freq_mhz": 433.828,
        "peak_db": -103.0,
        "noise_db": -106.0,
        "snr_db": 3.0,
        "band_power_dbfs": -45.1,
        "occupied_bw_khz": 0.0,
        "spectral_flatness": 0.856,
    },
}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Built once from the real-data calibration in config/thresholds_real.json.
    app.state.classifier = build_classifier()
    yield


app = FastAPI(title="Module 2 AI Threat Intelligence", lifespan=lifespan)


@app.post("/classify")
def classify(
    request: Request,
    observation: dict[str, Any] = Body(..., examples=[EXAMPLE_OBSERVATION]),
) -> dict[str, Any]:
    try:
        signal = parse_signal(observation)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    classifier: ThreatClassifier = request.app.state.classifier
    return asdict(classifier.classify(signal))

# Secure UAV Communication — Module 3

First backend prototype for the Jamming-Aware Secure Communication component.

## Features
- JSON upload and explicit **Scan Uploaded Data** action.
- Details remain hidden until the upload is scanned.
- Validates `classification` (`jamming`, `normal`, `abnormal`) and `severity` (`high`, `medium`, `low`, `null`).
- Displays observation ID, timestamp, triggered rule, abnormal features, statistical deviation, evidence, and RF fields where present.
- RF values absent from input remain `--`; the app does not invent RF measurements.
- Current policy: only `classification=jamming` and `severity=high` generates a proposed configuration.
- A 15-second countdown can start a software-only configuration build simulation; it does not control a real UAV/radio.
- Secure Communication remains PENDING unless a verified handshake status is explicitly supplied in the JSON.

## Run on Windows
Open a terminal in this folder and run:

```powershell
py -m pip install -r requirements.txt
py -m streamlit run app.py
```

Then visit `http://localhost:8501` if the browser does not open automatically.

## Input example
See `sample_threat.json`. It is illustrative data, not a real observation.

## Limitations
This does not acquire live RF measurements or detect jamming from RF. It processes the uploaded Threat Intelligence classification. The response settings are proposals/simulation only; applying them to a real link requires validated RF thresholds and a compatible radio/protocol controller.

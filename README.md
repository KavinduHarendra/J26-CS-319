# AI Threat Intelligence Module

This is Module 2 of the UAV cyber-defence research project. It takes structured
RF observations from the detection layer and labels each observation as:

- `Normal`
- `Jamming`
- `Unknown Anomaly`

The current implementation uses calibrated statistical baselines, explainable
jamming rules, and z-score anomaly detection. It does not use a trained machine
learning model. Each threat result includes the rule or statistical evidence that
caused the decision.

## Project layout

```text
ai-threat-intel-module/
|-- src/          Core detection, validation, baseline, exchange, and audit code
|-- integration/  Mock Module 3 and 4 file-exchange receivers
|-- tests/        Pytest test suite
|-- scripts/      Dataset and calibration scripts
|-- data/         Local datasets and runtime exchange records
|-- demo.py       Unified one-window integration demonstration
|-- requirements.txt
`-- README.md
```

## Set up the project

Python 3.13 is used for the current development environment.

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Run the tests:

```powershell
python -m pytest -q
```

Run the complete demonstration in one terminal window:

```powershell
python demo.py
```

## Unified integration demo

`demo.py` is the central dashboard and main demonstration command. It replays the
real Module 1 recording from 2026-10-23 in sequence order, runs the frozen v2
Module 2 detector, and sends separate JSON results to simulated Module 3 and
Module 4 receivers. The Rich dashboard shows classifications, signal evidence,
processing times, scoring results, file queues, and receiver decisions.
No server or network connection is used. JSON files are exchanged atomically
under `data/exchange/` and moved into processed or received folders.

```powershell
python demo.py
```

Use `--speed` to set the delay in seconds between recorded captures. A speed of
zero processes the recording as quickly as possible:

```powershell
python demo.py --plain --no-tests --speed 0
```

Use `--keep` to preserve existing exchange files. Otherwise the known exchange
folders are cleared before replay. The older `file_exchange_demo.py` command
remains as a compatibility launcher and opens the same application.

The interactive dashboard remains open after the capture run finishes so the
final classifications and processing statistics can be reviewed. Press Ctrl+C
to close it. For scripts or automated runs, add `--exit-on-complete`; plain mode
also exits automatically when processing is complete.

The file processor and simulated recipients can also be run separately:

```powershell
python -m src.file_processor
python integration/file_mock_receiver.py --module 3
python integration/file_mock_receiver.py --module 4
```

## Real recording input

The recording is stored under `data/real/module1_real_signals/`. Signal JSON is
loaded only through `src.real_data`, and the runtime `RealSignal` contains seven
measurements without labels, capture phases, jammer names, folder names, or
Module 1 flags. `ground_truth.csv` is joined only after classification for the
dashboard confusion matrix, recall, and false-positive rates.

The reproducible feature audit and evaluation are generated with:

```powershell
python scripts/analyze_real_data.py
```

Results are written to `reports/real_feature_audit.md`,
`reports/real_feature_audit.csv`, and `reports/real_eval.md`.

## Input validation

Every `RFObservation` is validated before it reaches the detection pipeline.
Invalid IDs, timestamps, non-numeric values, booleans, NaN, infinity, and values
outside broad physical limits are rejected with `InvalidObservationError`.

The default plausibility limits are:

| Field | Minimum | Maximum |
|---|---:|---:|
| RSSI | -140 dBm | 0 dBm |
| SNR | -40 dB | 80 dB |
| Noise floor | -150 dBm | -20 dBm |
| Packet rate | 0 packets/s | 1,000,000 packets/s |

These limits are input-safety checks, not detection thresholds. They are
deliberately broad and should be adjusted for the radio being used:

```python
from src.schema import configure_plausible_ranges

configure_plausible_ranges({"rssi": (-120.0, -10.0)})
```

## Baseline files

Calibrated baselines are saved as JSON. A matching `.sha256` sidecar is written
at the same time and checked before a baseline is loaded. A changed or corrupted
baseline is rejected. Pickle is not used.

```python
from src.baseline import NormalBaseline

baseline.save_baseline("data/baseline.json")
loaded_baseline = NormalBaseline.load_baseline("data/baseline.json")
```

Only observations classified as `Normal` should be added to calibration data.
`add_classified_sample()` rejects `Jamming` and `Unknown Anomaly` observations to
reduce the risk of baseline poisoning.

## Audit log

Classification attempts are appended to `data/audit_log.jsonl`. Each JSON Lines
record contains the observation ID, timestamp, result, severity, triggered rule,
baseline version, and a SHA-256 digest of the input. Rejected inputs are recorded
as `Rejected` with the reason they failed validation.

The audit log and `.env` files are intentionally excluded from Git because they
can contain operational or sensitive information.

## Security checks

Dependency versions are pinned in `requirements.txt`. Before merging or deploying,
run dependency and source checks locally:

```powershell
python -m pip install pip-audit bandit
pip-audit -r requirements.txt
bandit -r src
```

## Detection behaviour

The real-data pipeline uses two normal states: idle and legitimate OOK traffic.
`R2-NARROWBAND` identifies the known narrowband pattern using SNR, occupied
bandwidth, and spectral flatness. Records not matched by the rule are compared
with the nearest normal state; an excessive robust-z distance becomes `Unknown
Anomaly`. The decision order remains rule, anomaly, then normal. J01 and J02 are
retired from the real-recording pipeline and remain only in the older four-field
compatibility API. Severity cut-offs are placeholders until operational incident
impact data is available.

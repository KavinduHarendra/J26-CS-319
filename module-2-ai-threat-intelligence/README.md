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
|-- integration/  Mock Module 1, 3, and 4 file-exchange components
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

`demo.py` is the central dashboard and main demonstration command. It runs a
mock Module 1 producer, the real Module 2 pipeline, and mock Module 3 and Module
4 receivers together. The Rich dashboard keeps overall system state, the live
component pipeline, classifications, signal evidence, processing times, file
queues, and mock receiver decisions in one clean view.
No server or network connection is used. JSON files are exchanged atomically
under `data/exchange/` and moved into processed or received folders.

```powershell
python demo.py
```

Use `--plain` for line-oriented output, `--keep` to preserve existing exchange
files, and `--count` when a fixed-length demonstration is needed. With no
options, the mock Module 1 schedule repeats continuously until Ctrl+C. For
example, `python demo.py --count 150 --rate 20` performs one fixed 150-capture
run. The older `file_exchange_demo.py` command remains as a compatibility
launcher and opens the same application.

When the real Module 1 producer is available, start the dashboard without the
mock input generator:

```powershell
python demo.py --external-module1
```

In this mode Module 2 continuously watches `data/exchange/module1_to_module2/`
for observation JSON files until Ctrl+C.

The interactive dashboard remains open after the capture run finishes so the
final classifications and processing statistics can be reviewed. Press Ctrl+C
to close it. For scripts or automated runs, add `--exit-on-complete`; plain mode
also exits automatically when processing is complete.

The standalone mock components can also be run in separate terminals:

```powershell
python integration/file_mock_module1.py --rate 5 --count 150
python -m src.file_processor
python integration/file_mock_receiver.py --module 3
python integration/file_mock_receiver.py --module 4
```

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

Security hardening does not change the calibrated detection behaviour. J01 and J02
remain the known-jamming rules, the anomaly engine uses the existing z-score
threshold, and severity uses the existing Low, Medium, and High cutoffs.

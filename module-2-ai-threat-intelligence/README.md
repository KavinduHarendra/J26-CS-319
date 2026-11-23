# Module 2 — AI Threat Intelligence

Module 2 classifies each RF capture from Module 1 (SDR detection) as `NORMAL`,
`JAMMING` or `UNKNOWN_ANOMALY`, with a severity and a plain-English decision
trace, and passes the result to Module 3 (secure communication) and Module 4
(cyber defence and response).

Decisions use only seven measurements: `peak_freq_mhz`, `peak_db`, `noise_db`,
`snr_db`, `band_power_dbfs`, `occupied_bw_khz` and `spectral_flatness`. Capture
labels, phases, jammer names, folder names and Module 1 flags never reach the
classifier; leakage tests enforce this.

## Architecture

```text
Module 1 JSON ─► baseline ─► rule engine ─► anomaly engine ─► classifier ─► JSON files / HTTP API
```

| Stage | File | Role |
| --- | --- | --- |
| Baseline | `src/baseline.py` | Two normal states (idle, legitimate OOK link) calibrated from real captures |
| Rule engine | `src/rule_engine.py` | R1: `snr_db >= 25.8` and `0 < occupied_bw_khz <= 137.5` → `JAMMING` |
| Anomaly engine | `src/anomaly_engine.py` | Distance to the nearest normal state; above its limit → `UNKNOWN_ANOMALY` |
| Classifier | `src/classifier.py` | Rule, then anomaly, then `NORMAL`; adds severity and trace |
| Outputs | `src/output_writer.py`, `src/api.py` | Atomic JSON per capture for Modules 3 and 4; `POST /classify` |

Severity uses the distance to the nearest normal state: LOW below 9.4135,
MEDIUM from 9.4135, HIGH from 16.0383.

`src/fuzzy.py` adds a Mamdani fuzzy risk score (0-100) over `snr_db` and
`occupied_bw_khz`, with 3 rules and membership breakpoints taken from the
calibrated config. Every output's `evidence` ends with the score, its severity
(<50 LOW, 50-75 MEDIUM, >=75 HIGH; cut-offs in the config's `fuzzy` section)
and the fuzzy rules that fired. It does not change the classification or the
`severity` field.

Thresholds live in `config/thresholds_real.json`, produced by
`scripts/calibrate_real.py` from the first chronological half of the
2026-10-23 recording in `data/real/module1_signals_clean/`. The second half and
93 unseen jammer captures are kept for evaluation.

## Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

All commands below are run from this folder.

## Tests

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

Add `-m "not slow"` to skip the full-recording leakage proofs for a quicker run.

## Demo

```powershell
.\.venv\Scripts\python.exe demo.py
```

The live dashboard classifies every capture JSON in `data/module1_input/` and
keeps watching for new ones until `q` or `Ctrl+C`. Results are written to
`data/json_out/module2_to_module3/` and `data/json_out/module2_to_module4/`.
For a short non-interactive run:

```powershell
.\.venv\Scripts\python.exe demo.py --plain --count 40 --speed 0
```

See `python demo.py --help` for the other options (input folder, layout,
snapshots).

## Experiments and evaluation

```powershell
.\.venv\Scripts\python.exe scripts\run_experiments.py     # writes data/results_*.csv
.\.venv\Scripts\python.exe scripts\compare_baselines.py   # rule base only vs combined
.\.venv\Scripts\python.exe scripts\analyze_real_data.py   # writes reports/real_eval.md
```

`compare_baselines.py` prints a Markdown table with the classification report,
confusion matrix, false-positive rate, mean latency and the NFR01 (< 50 ms)
result for each configuration.

## HTTP API

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api:app --reload
```

`POST /classify` takes one Module 1 capture (same JSON as the input files) and
returns the classification as JSON; invalid input, including any label or phase
key, gets HTTP 422. In Windows PowerShell use `curl.exe`:

```powershell
curl.exe -X POST http://127.0.0.1:8000/classify -H "Content-Type: application/json" --data-binary "@data/real/module1_signals_clean/known_signals/000001_S00001.json"
```

Interactive docs: <http://127.0.0.1:8000/docs>.

## Known limitations

- **Distance bands are not used by the classifier.** `src/contextual_baseline.py`
  (`DistanceBandedBaseline`) gives each UAV distance range its own baseline so
  long-range signal loss is not flagged, but the classifier still uses one flat
  baseline. It is tested only on synthetic data from
  `scripts/generate_distance_dataset.py`, because the recording has no distance
  field.
- **Thresholds need recalibration on better SDR data.** They come from one
  RTL-SDR session (2026-10-23). Recalibrate with `scripts/calibrate_real.py`
  when HackRF One recordings are available, and consider `--normality-screen`
  (robust z-scores for non-Gaussian features), which is off by default.
- **Severity cutoffs are provisional.** They are the 33rd/66th percentiles of
  jamming in the calibration half of the same recording, not operationally
  validated thresholds, and must be recomputed whenever the thresholds change
  (a test fails until they match).

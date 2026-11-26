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
| Fuzzy risk | `src/fuzzy.py` | Mamdani risk score 0-100 over `snr_db` and `occupied_bw_khz`; sets severity |
| Classifier | `src/classifier.py` | Rule, then anomaly, then `NORMAL`; adds severity and trace |
| Outputs | `src/output_writer.py`, `src/api.py` | Atomic JSON per capture for Modules 3 and 4; `POST /classify` |

Severity comes from the fuzzy risk score alone: below 50 LOW, 50-75 MEDIUM,
75 and above HIGH (cut-offs in the config's `fuzzy` section). JAMMING and
UNKNOWN_ANOMALY get a severity; NORMAL keeps `severity: null`. The fuzzy
system has 3 rules (F1 strong and narrow -> high risk, F2 strong and wide ->
low risk, F3 weak -> low risk) with membership breakpoints taken from the
calibrated config. Every output carries `fuzzy_score` and `fuzzy_rules_fired`
(e.g. `["F1"]`); both are optional in the JSON contract, so older files
without them still validate. The same information is repeated at the end of
`evidence`.

Thresholds live in `config/thresholds_real.json`, produced by
`scripts/calibrate_real.py` from the first chronological half of the
2026-10-23 recording in `data/real/module1_signals_clean/`. The second half and
93 unseen jammer captures are kept for evaluation.

## Input format

Each capture is one JSON file. Required: `schema_version` (`"1.0"`),
`source_module`, `observation_id`, `sequence_number`, `timestamp`, `elapsed_s`
and `measurements` with the seven measurements above.

Optional, for HackRF-era exports (older files without them load unchanged):

| Field | Where | Allowed values |
| --- | --- | --- |
| `session_id` | top level | 1-64 letters, digits, `_` or `-` |
| `center_freq_hz` | top level | 1e6 to 6e9 |
| `sample_rate_hz` | top level | greater than 0 |
| `gain_db` | top level | 0 to 100 |
| `distance_m` | top level | 0 to 100,000 |
| `occupied_fraction` | `measurements` | 0 to 1 |
| `peak_count` | `measurements` | whole number, 0 to 1000 |
| `duty_cycle` | `measurements` | 0 to 1 |

Every number must be finite (no NaN or infinity) and in range. The optional
fields are stored on the capture but no decision uses them yet; a test proves
classification and fuzzy score are identical with and without them.
`session_id`, when present, is copied into the output JSON and the API
response. Any other key is rejected, and so is any label-like key anywhere in
the file (for example `label`, `phase`, `jammer`, `jammer_on`, `event_type`,
`expected_class` or a Module 1 flag), in any letter case.

## Checking a new recording

```powershell
.\.venv\Scripts\python.exe scripts\validate_recording.py <folder>
```

Read-only check of a recording folder: every capture against the input format,
sequence gaps and duplicates, timestamp order, ADC clipping
(`band_power_dbfs` >= -1 dBFS), constant `session_id` and radio settings,
`ground_truth.csv` coverage and captures per class. Prints PASS/WARN/FAIL per
check and exits with 1 if anything fails. How to record HackRF sessions so they
pass is in [docs/HACKRF_RECORDING_PROTOCOL.md](docs/HACKRF_RECORDING_PROTOCOL.md).

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

`compare_baselines.py` writes `reports/baseline_comparison.md`: results per
group (calibration, validation, unseen jammer types, leave-one-jammer-type-out)
and held-out metrics with false-positive rate, latency and the NFR01 (< 50 ms)
result. The 93 `abnormal_signals` captures are labelled JAMMING, as in the
ground truth. On this recording both configurations give identical predictions
because R1 catches all jamming; the anomaly engine still needs non-jamming
abnormal recordings to be evaluated.

## HTTP API

```powershell
.\.venv\Scripts\python.exe -m uvicorn src.api:app --reload
```

`POST /classify` takes one Module 1 capture (same JSON as the input files) and
returns the classification as JSON (plus `session_id` when the capture has
one); invalid input, including any label or phase key, gets HTTP 422. In Windows PowerShell use `curl.exe`:

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
- **Severity is coarse on the recorded data.** The fuzzy cut-offs (50/75) are a
  policy choice, not fitted or operationally validated. Every recorded capture
  sits far from the fuzzy ramps, so all recorded threats score 80.6 (HIGH);
  MEDIUM appears only for captures between the calibrated groups.

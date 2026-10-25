# Module 2 — Threat Intelligence

Module 2 reads recorded measurements from Module 1 and produces an explainable threat state for every capture. Runtime decisions use only these seven measurements:

- `peak_freq_mhz`
- `peak_db`
- `noise_db`
- `snr_db`
- `band_power_dbfs`
- `occupied_bw_khz`
- `spectral_flatness`

Capture labels, phases, jammer names, folder names, and Module 1 flags are excluded from the classification path. Reference data is loaded separately after classification for calibration splits, scoring, and dashboard display.

## Data

Module 2 watches one flat runtime input folder:

```text
data/module1_input/
```

Put every new Module 1 capture JSON directly in this folder. Do not create a
subfolder for each signal type. The dashboard notices files added while it is
running, validates them, classifies them in sequence order, and writes one
result for Module 3 and one for Module 4. Use a new sequence number and file
name for every capture. A file not present in the recorded ground-truth table
is still classified; the dashboard marks its expected result as `UNSCORED`.

The supplied 2026-10-23 reference recording remains under
`data/real/module1_signals_clean/`:

| Folder | Captures | Purpose |
|---|---:|---|
| `known_signals/` | 1,416 | chronological calibration and validation |
| `abnormal_signals/` | 93 | unseen abnormal evaluation |
| `ambiguous_signals/` | 4 | transition rows reported separately |

The three folders form one stream ordered by `sequence_number` from 1 through 1,513. `ground_truth.csv` is for calibration grouping and scoring only. `module1_flags_reference.csv` is for offline reporting only.

## Detection pipeline

Run the reproducible calibration:

```powershell
.\.venv\Scripts\python.exe scripts\calibrate_real.py
```

This writes `config/thresholds_real.json`. Calibration reads `known_signals/` only and takes the first chronological half of each allowed group. The active values are:

- signal SNR threshold: 25.8 dB
- narrowband threshold: 137.5 kHz
- idle anomaly limit: 3.00
- legitimate OOK anomaly limit: 4.98

The classifier has one rule. R1 returns `JAMMING` when `snr_db >= 25.8` and `0 < occupied_bw_khz <= 137.5`. If R1 does not fire, the record is compared with the nearest idle or legitimate-transmission state. A normalised distance above 1 returns `UNKNOWN_ANOMALY`; otherwise it returns `NORMAL`.

The decision order is rule, anomaly, then normal. Severity boundaries are uncalibrated placeholders and are labelled that way in the source and evaluation report.

## JSON output

Every capture produces a separate atomic JSON file for each recipient:

```text
data/json_out/module2_to_module3/<sequence>_<observation_id>_threat.json
data/json_out/module2_to_module4/<sequence>_<observation_id>_threat.json
```

The sequence is six digits and the observation ID is restricted to ASCII letters, digits, underscores, and hyphens. A temporary file is replaced atomically so readers do not see partial JSON. Duplicate sequence numbers are not processed twice.

## Dashboard

Create the environment and install the pinned dependencies:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

Run the live dashboard and keep watching the input folder:

```powershell
.\.venv\Scripts\python.exe demo.py
```

The dashboard first scans every JSON already in `data/module1_input/`, then
keeps watching for new captures until you press `q` or `Ctrl+C`. It shows the
raw capture, decision trace, distances to both normal states, data flow, rule
counts, scoring (when a reference exists), latency, and timelines. On Windows,
use space to pause, `+` or `-` to change speed, `j` to switch JSON detail, `s`
to save a snapshot, and `q` to quit.

Useful options:

```powershell
# Watch a different flat Module 1 input folder
.\.venv\Scripts\python.exe demo.py --input-dir E:\Module1\captures

# Process 40 captures and stop (useful for a quick check)
.\.venv\Scripts\python.exe demo.py --plain --no-tests --count 40 --speed 0

# Keep output files from an earlier run
.\.venv\Scripts\python.exe demo.py --keep

# Process 150 captures with a 0.05-second delay, then stop
.\.venv\Scripts\python.exe demo.py --count 150 --speed 0.05

# Force the wide layout and show complete input/output JSON
.\.venv\Scripts\python.exe demo.py --layout full --full-json

# Save SVG and text snapshots at capture 84
.\.venv\Scripts\python.exe demo.py --snapshot-at 84 --snapshot-dir reports/screenshots

# Use ASCII symbols on an older terminal
.\.venv\Scripts\python.exe demo.py --ascii
```

`--speed` is the delay in seconds between captures. `--count 0` means keep
watching continuously; a positive count stops after that many valid captures.
`--input-dir` changes the watched flat input folder. `--layout auto` selects
the full layout at 160 columns by 45 rows or larger and uses the compact layout
otherwise. `--json-dir` changes the recipient output root, `--keep` preserves
existing output files, and `--no-keys` disables Windows keyboard handling.

## Evaluation and tests

Generate the real-data evaluation:

```powershell
.\.venv\Scripts\python.exe scripts\analyze_real_data.py
```

The report is written to `reports/real_eval.md`. It includes calibration, validation, unseen-jammer results, leave-one-jammer-type-out results, label-quality rows, and measured latency.

Run all checks:

```powershell
.\.venv\Scripts\python.exe -m pip check
.\.venv\Scripts\python.exe -m compileall -q src scripts tests demo.py
.\.venv\Scripts\python.exe -m pytest -q
```

The leakage tests prove that changing reference labels, changing file names and folder layout, or removing the Module 1 flag reference file cannot change classification results.

For a quicker local check that excludes only the full-recording leakage proofs:

```powershell
.\.venv\Scripts\python.exe -m pytest -q -m "not slow"
```

The default test command above still runs every test, including the leakage proofs.

For dependency and source auditing:

```powershell
python -m pip install pip-audit bandit
pip-audit -r requirements.txt
bandit -r src
```

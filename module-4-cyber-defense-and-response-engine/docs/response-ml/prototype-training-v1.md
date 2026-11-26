# Offline Random Forest prototype v1

This experiment checks how well a model can reproduce the draft response rubric on synthetic cases. The dataset, model and evaluation are provisional. The 144 blind-review cases remain available for independent review. The model does not connect to the application or execute any action.

## What was built

- The label script reads the original v1.2 CSV through the existing validator. It keeps both original baseline columns and writes a new CSV with `provisional_response`, `provisional_criterion`, `rubric_version`, and `label_export_version`. Every row is `RUBRIC_GENERATED` and `PENDING`, with a blank `validated_response`. An incompatible provenance, approved source row, or changed provisional export fails validation.
- The preprocessor takes the 15 inputs listed in the [data dictionary](data-dictionary.md). It replaces missing numeric values using the training median and adds a missing-value flag. It converts a blank category into an explicit missing category and one-hot encodes each category. Metadata, response suggestions and review fields never enter the input matrix.
- The trainer fits preprocessing and the forest on 560 training rows. It compares 18 combinations of class weight, depth and leaf size on 220 validation rows. It preserves the winning train-fitted pipeline and its class mapping, feature definitions, dependency versions, input digests, and tuning results. The test rows are used only by the evaluation command to measure agreement.
- The evaluator compares the classification-only and contextual rule baselines with raw and offline-screened forest predictions on the same 220 test rows. It also reports the draft rubric's 100% agreement by construction as a reference ceiling. The comparison contains no independent human labels.
- The reports show confusion counts, per-class precision and recall, the distribution of uncalibrated prediction confidence, and local inference time. Feature importance adds the tree importance of the encoded columns belonging to each original feature. It describes this model and dataset. Correlated features such as risk score and risk level can share importance.

## What the frozen test showed

The classification-only baseline agreed with the draft labels on 30.9% of test rows and the contextual rules on 48.2%. The selected forest agreed on 89.1%, with raw macro F1 of 85.6%. These results describe agreement with the rubric the forest was trained to reproduce. They do not establish that the forest makes better real-world decisions.

There are no exact overlapping feature vectors, scenario families, or sessions across folds. Ignoring threat confidence, 149 test rows repeat an earlier evidence pattern. On the remaining 71 rows, raw agreement was 77.5%. Those 71 rows contain only three reference classes. A six-class generalization claim needs additional independent cases and labels.

The proposed offline guard flagged 11 hold or backup recommendations that lacked support under the draft policy. It redirected them to operator review. Overall agreement stayed at 89.1%, and screened macro F1 was 91.6%. The guard shares criteria with the draft reference labels. The forest had zero off-rubric recommendations on the 66 critical test rows. All 12 examples of the known contextual critical-monitoring gap were in training. The critical test result therefore gives no held-out evidence about that gap. No probability threshold or live fallback was enabled.

## Reproduce in PowerShell

Run from the project root. Use a fresh output path to keep the completed run intact.

```powershell
$python = (Resolve-Path .\.venv\python.exe).Path
$source = ".response-ml/v1.2/synthetic_dataset.csv"
$split = ".response-ml/v1.2/review/split-manifest.csv"
$run = ".response-ml/prototype-v1-rerun"
$env:MPLCONFIGDIR = Join-Path (Get-Location).Path ".venv/rf-plot-cache"

& $python -B -m response_ml.label --source $source --output "$run/labeled-v1.2.csv"
& $python -B -m response_ml.train --source $source --labels "$run/labeled-v1.2.csv" --split $split --output-dir "$run/model" --seed 42
& $python -B -m response_ml.evaluate --source $source --labels "$run/labeled-v1.2.csv" --split $split --model-dir "$run/model" --output-dir "$run/evaluation"
```

The first command exports and counts the draft labels. The second chooses parameters and saves the Joblib pipeline. The third checks the saved artifact and its input digests, evaluates the held-out rows and saves the HTML, metrics, and PNGs. Use Joblib only for locally trained, trusted artifacts. For a repeat run on another machine, match the dependency versions in model-metadata.json. Latency can change with hardware and system load.

On a fresh checkout, install the offline requirements inside a standard virtual environment with `python -m pip install -r backend/requirements-prototype.txt`. Run the three module commands from `backend` with absolute paths to the source, split, labels and output, or use the configured workspace interpreter above.

```powershell
$testTemp = "\\?\" + (Join-Path (Get-Location).Path (".venv/t-" + [guid]::NewGuid().ToString("N").Substring(0,6)))
& $python -B -m pytest backend/tests -q -p no:cacheprovider --basetemp $testTemp
```

Model integration requires separate approval. Independently label the blind cases, confirm the safety policy and compare against the same independent labels before considering integration. Keep the frozen test results from this run as a record of this particular synthetic experiment.

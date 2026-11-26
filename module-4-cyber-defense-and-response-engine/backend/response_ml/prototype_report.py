"""Create readable reports and publication-style PNGs from measured results."""

from html import escape
from os.path import relpath
from pathlib import Path
from textwrap import wrap

from response_ml.prototype_metrics import AGGREGATES


METRIC_TITLES = {
    "accuracy": "Accuracy", "balanced_accuracy": "Balanced accuracy",
    "macro_precision": "Macro precision", "macro_recall": "Macro recall",
    "macro_f1": "Macro F1", "weighted_f1": "Weighted F1",
}


def save_figures(report: dict, output: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")
    from matplotlib import pyplot as plt

    raw = report["methods"]["random_forest_raw"]
    labels = ["\n".join(wrap(name.replace("_", " "), 16)) for name in report["classes"]]
    matrix = raw["confusion_matrix"]
    fig, ax = plt.subplots(figsize=(12, 8), layout="constrained")
    colors = ax.imshow(matrix, cmap="Blues")
    fig.colorbar(colors, ax=ax, label="Observations")
    threshold = max(max(row) for row in matrix) * 0.55
    for y, row in enumerate(matrix):
        for x, count in enumerate(row):
            ax.text(x, y, str(count), ha="center", va="center", color="white" if count > threshold else "#162527")
    ax.set(xticks=range(len(labels)), xticklabels=labels, yticks=range(len(labels)), yticklabels=labels,
           xlabel="Random Forest prediction", ylabel="Draft-rubric reference",
           title=f"Raw Random Forest confusion matrix · {raw['rows']} synthetic test rows")
    fig.savefig(output / "confusion-matrix.png", dpi=170)
    plt.close(fig)

    names, scores = zip(*report["feature_importance"].items())
    fig, ax = plt.subplots(figsize=(10, 7), layout="constrained")
    ax.barh([name.replace("_", " ") for name in names], scores, color="#1c7066")
    ax.invert_yaxis()
    ax.set(xlabel="Total impurity importance across encoded columns", title="Random Forest importance by original input")
    fig.savefig(output / "feature-importance.png", dpi=170)
    plt.close(fig)

    bins = report["prediction_confidence"]["bins"]
    ranges = [f"{item['low']:.0%}–{item['high']:.0%}" for item in bins]
    fig, ax = plt.subplots(figsize=(9, 5), layout="constrained")
    bars = ax.bar(ranges, [item["rows"] for item in bins], color="#236a85")
    ax.bar_label(bars)
    ax.set(xlabel="Maximum predicted class probability (uncalibrated)", ylabel="Synthetic test rows",
           title="Raw Random Forest prediction confidence")
    fig.savefig(output / "confidence-distribution.png", dpi=170)
    plt.close(fig)

    methods = [(name, values) for name, values in report["methods"].items() if name != "rubric_reference_ceiling"]
    fig, ax = plt.subplots(figsize=(10, 5), layout="constrained")
    positions = list(range(len(methods)))
    ax.barh([position - 0.17 for position in positions], [values["accuracy"] for _, values in methods],
            height=0.30, label="Accuracy", color="#236a85")
    ax.barh([position + 0.17 for position in positions], [values["macro_f1"] for _, values in methods],
            height=0.30, label="Macro F1", color="#1c7066")
    ax.set(yticks=positions, yticklabels=[report["method_names"][name] for name, _ in methods],
           xlim=(0, 1.02), xlabel="Score (0–1)", title="Agreement with draft labels on the synthetic test set")
    ax.invert_yaxis()
    ax.legend(loc="lower right")
    fig.savefig(output / "baseline-comparison.png", dpi=170)
    plt.close(fig)


def percent(value) -> str:
    return "—" if value is None else f"{value:.1%}"


def table(caption: str, columns, rows) -> str:
    headings = "".join(f'<th scope="col">{escape(str(column))}</th>' for column in columns)
    lines = []
    for row in rows:
        cells = "".join(f"<td>{escape(str(item))}</td>" for item in row[1:])
        lines.append(f'<tr><th scope="row">{escape(str(row[0]))}</th>{cells}</tr>')
    return (f'<div class="scroll"><table><caption>{escape(caption)}</caption>'
            f"<thead><tr>{headings}</tr></thead><tbody>{''.join(lines)}</tbody></table></div>")


def render_report(report: dict, output: Path, model_metadata: Path) -> None:
    safe = report["safety"]
    raw = report["methods"]["random_forest_raw"]
    checked = report["methods"]["random_forest_screened"]
    test_novel = report["novel_methods"]["random_forest_raw"]
    confidence = report["prediction_confidence"]
    speed = report["latency"]
    selected = report["model_selection"]
    metric_headers = ["Method", "Rows", *(METRIC_TITLES[name] for name in AGGREGATES)]
    method_rows = lambda methods: [
        [report["method_names"][name], values["rows"], *(percent(values[k]) for k in AGGREGATES)]
        for name, values in methods.items()
    ]
    comparison = table("Frozen test partition", metric_headers, method_rows(report["methods"]))
    novel = table("Test evidence patterns absent from training and validation", metric_headers, method_rows(report["novel_methods"]))
    per_class = table("Raw Random Forest per-class metrics", ["Class", "Precision", "Recall", "F1", "Support"], [
        [name, percent(values["precision"]), percent(values["recall"]), percent(values["f1"]), values["support"]]
        for name, values in raw["per_class"].items()
    ])
    critical = table("Critical-risk recommendations", ["Method", "Critical rows", "Off-rubric", "Monitoring"], [
        [report["method_names"][name], values["critical_rows"], values["critical_mismatches"],
         values["critical_monitoring_recommendations"]] for name, values in safe["critical"].items()
    ])
    label_counts = table("Provisional targets across all 1,000 observations", ["Response", "Rows"],
                         list(report["label_summary"]["provisional_labels"].items()))
    reasons = ", ".join(f"{key} ({value})" for key, value in safe["override_reasons"].items()) or "None"
    flags = report["label_summary"]["review_flags"]
    unseen_overlap = report["split_overlap"]["rows_matching_an_earlier_partition_without_threat_confidence"]
    critical_raw = safe["critical"]["random_forest_raw"]
    critical_screened = safe["critical"]["random_forest_screened"]

    safety_text = f"""# Proposed v0.1 safety policy evaluation

This is an offline check of the experimental prototype on {safe['rows']} synthetic test rows. The policy and rubric share criteria. The application still uses its contextual rules.

- Raw predictions flagged by the proposed guard — {safe['raw_flagged_by_policy']} of {safe['rows']}.
- Adjusted recommendations flagged by the same guard — {safe['adjusted_flagged_by_policy']} of {safe['rows']}.
- Raw predictions outside the six supported classes — {safe['unsupported_raw_actions']}.
- Reasons for adjustments — {reasons}.
- Of {critical_raw['critical_rows']} critical rows, the raw model disagreed with the draft rubric on {critical_raw['critical_mismatches']} and recommended monitoring on {critical_raw['critical_monitoring_recommendations']}. The offline policy output disagreed on {critical_screened['critical_mismatches']} and recommended monitoring on {critical_screened['critical_monitoring_recommendations']}.

The proposed guard enforces evidence-based holds, operator review, the critical monitoring restriction, and support for any hold or backup recommendation. Low-confidence thresholds, absent-model fallback and live safety activation are outside this test. The safety checks describe policy agreement on synthetic data.
"""
    with (output / "safety-report.md").open("x", encoding="utf-8") as stream:
        stream.write(safety_text)

    images = [
        ("baseline-comparison.png", "Accuracy and macro F1 comparison"),
        ("confusion-matrix.png", "Raw Random Forest confusion matrix"),
        ("feature-importance.png", "Aggregated feature importance"),
        ("confidence-distribution.png", "Uncalibrated prediction confidence histogram"),
    ]
    charts = "\n".join(f'<figure><a href="{path}"><img src="{path}" alt="{caption}"></a><figcaption>{caption}</figcaption></figure>'
                       for path, caption in images)
    parameters = selected["parameters"]
    try:
        metadata_href = Path(relpath(model_metadata.resolve(), output.resolve())).as_posix()
    except ValueError:
        metadata_href = model_metadata.resolve().as_uri()
    html = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Synthetic Random Forest prototype evaluation</title>
<style>
:root {{color-scheme:light dark;--paper:#f6f8f9;--surface:#fff;--text:#18242b;--muted:#495b65;--line:#c9d9de;--tint:#e4f0ef;--link:#145b55}}
@media(prefers-color-scheme:dark){{:root{{--paper:#151d22;--surface:#1d292f;--text:#e5eef1;--muted:#bbccd2;--line:#445963;--tint:#243d3c;--link:#8fd9cb}}}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--paper);color:var(--text);font:1rem/1.56 system-ui,sans-serif}}
main{{max-width:78rem;padding:clamp(1rem,4vw,3rem);margin:auto}} h1,h2,p{{margin:0}} h1{{font-size:clamp(1.8rem,4vw,2.7rem);line-height:1.12}} h2{{margin-bottom:.6rem;font-size:1.4rem}}
a{{color:var(--link);text-underline-offset:.15em}} section{{margin-top:1.55rem}}
.lead{{margin-top:1rem;padding:.9rem 1.1rem;background:var(--tint);border-left:3px solid var(--link)}}
nav{{display:flex;flex-wrap:wrap;gap:.4rem 1rem;margin:1rem 0;border-bottom:1px solid var(--line);padding-bottom:.85rem}}
p+p,.note,.scroll{{margin-top:.65rem}} .note{{color:var(--muted);font-size:.92rem}}
.scroll{{overflow:auto;background:var(--surface);border:1px solid var(--line)}}
table{{width:100%;border-collapse:collapse;font-size:.89rem}} caption{{text-align:left;font-weight:650;padding:.5rem .65rem}} thead{{background:var(--tint)}}
th,td{{text-align:left;vertical-align:top;padding:.4rem .62rem;font-variant-numeric:tabular-nums}} tbody tr+tr{{border-top:1px solid var(--line)}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,29rem),1fr));gap:1rem}}
figure{{margin:0}} img{{display:block;width:100%;height:auto}} figcaption{{color:var(--muted);font-size:.88rem}}
</style></head><body><main>
<header><p>J26-CS-319 · Module 4</p><h1>Synthetic Random Forest prototype evaluation</h1></header>
<p class="lead"><strong>{percent(raw['accuracy'])} raw accuracy on {raw['rows']} synthetic test rows.</strong>
All reference labels are draft-rubric suggestions with PENDING status. These scores measure agreement with the rubric. Independent real-world correctness remains unmeasured.</p>
<nav aria-label="Report sections"><a href="#comparison">Comparison</a><a href="#inputs">Inputs and split</a><a href="#safety">Safety</a><a href="#figures">Graphs</a><a href="#files">Files</a></nav>
<section id="comparison"><h2>Held-out agreement</h2>
{comparison}
<p class="note">The rubric-reference ceiling is 100% by construction. Its suggestions are the reference. Higher agreement with those suggestions alone does not establish that a model is better for real operational decisions.</p>
{per_class}
{novel}
<p class="note">The novel subset ignores threat-confidence differences when checking for repeats. Macro metrics on this subset average over classes present in its reference labels. The subset represents {sum(values['support'] > 0 for values in test_novel['per_class'].values())} of the six classes.</p></section>
<section id="inputs"><h2>Inputs and split</h2>
{label_counts}
<p>{flags['conflicting_evidence']} rows flag evidence conflict. {flags['low_evidence_confidence']} have low evidence confidence. {flags['critical_contextual_monitoring']} retain a critical contextual monitoring recommendation. These review flags may overlap. The draft labeled every row and {report['label_summary']['approved_responses']} rows have independently approved responses.</p>
<p>The frozen split contains 560 training, 220 validation and 220 test observations. Scenario families, sessions and exact feature vectors are partition-exclusive. Ignoring confidence, {unseen_overlap['validation']} validation rows and {unseen_overlap['test']} test rows match an earlier partition.</p>
<p>Validation macro F1 selected {parameters['n_estimators']} trees, depth {escape(str(parameters['max_depth']))}, minimum leaf size {parameters['min_samples_leaf']} and class weight {escape(str(parameters['class_weight']))}. The validation macro F1 was {percent(selected['macro_f1'])}. Imputation and encoding were fitted on training rows.</p>
<p>Raw mean confidence was {percent(confidence['mean'])}. Warmed prediction median was {speed['median']:.2f} ms and p95 was {speed['p95']:.2f} ms over {speed['samples']} single rows. Latency includes preprocessing and class probabilities. It excludes file loading and safety screening. Confidence scores are uncalibrated.</p></section>
<section id="safety"><h2>Proposed offline safety screening</h2>
<p>The guard flagged {safe['raw_flagged_by_policy']} raw recommendations and {safe['adjusted_flagged_by_policy']} recommendations after adjustment. Reasons were {escape(reasons)}. The adjusted accuracy was {percent(checked['accuracy'])}. The guard shares criteria with the draft labels, so this change in agreement is descriptive.</p>
{critical}
<p class="note">The contextual recommendation and risk scoring remain authoritative in the application. The experimental model and proposed policy were evaluated offline.</p></section>
<section id="figures"><h2>Graphs</h2><div class="grid">{charts}</div></section>
<section id="files"><h2>Files</h2>
<ul><li><a href="evaluation-metrics.json">Full metrics and per-class counts</a></li><li><a href="baseline-comparison.csv">Baseline comparison CSV</a></li><li><a href="test-predictions.csv">Per-row test predictions</a></li><li><a href="safety-report.md">Safety report</a> and <a href="safety-evaluation.json">safety measurements</a></li><li><a href="{escape(metadata_href)}">Model metadata and tuning results</a></li></ul>
</section></main></body></html>
"""
    with (output / "evaluation-report.html").open("x", encoding="utf-8") as stream:
        stream.write(html)

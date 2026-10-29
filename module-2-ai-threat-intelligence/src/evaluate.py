"""Score (true_label, predicted_label, latency_ms) results against the proposal NFRs."""

from __future__ import annotations

import statistics

from sklearn.metrics import classification_report, confusion_matrix


LABELS = ["Normal", "Jamming", "Unknown Anomaly"]
DISPLAY_NAMES = {
    "NORMAL": "Normal",
    "JAMMING": "Jamming",
    "UNKNOWN_ANOMALY": "Unknown Anomaly",
}
NFR01_LATENCY_TARGET_MS = 50.0


def _display(label: str) -> str:
    name = DISPLAY_NAMES.get(label, label)
    if name not in LABELS:
        raise ValueError(f"unknown label {label!r}")
    return name


def evaluate_results(
    results: list[tuple],
    latency_target_ms: float = NFR01_LATENCY_TARGET_MS,
    *,
    title: str | None = None,
    verbose: bool = True,
) -> dict:
    """Compute and print classification metrics, FPR and NFR01 latency compliance."""
    if not results:
        raise ValueError("results must not be empty")
    y_true = [_display(true) for true, _, _ in results]
    y_pred = [_display(predicted) for _, predicted, _ in results]
    latencies = [float(ms) for _, _, ms in results]

    report_text = classification_report(
        y_true, y_pred, labels=LABELS, digits=4, zero_division=0
    )
    report = classification_report(
        y_true, y_pred, labels=LABELS, output_dict=True, zero_division=0
    )
    matrix = confusion_matrix(y_true, y_pred, labels=LABELS)

    normal_predictions = [pred for true, pred in zip(y_true, y_pred) if true == "Normal"]
    false_positives = sum(pred != "Normal" for pred in normal_predictions)
    fpr = false_positives / len(normal_predictions) if normal_predictions else 0.0

    mean_latency = statistics.fmean(latencies)
    nfr01_pass = mean_latency < latency_target_ms

    metrics = {
        "total": len(results),
        "report": report,
        "report_text": report_text,
        "confusion_matrix": matrix,
        "false_positives": false_positives,
        "normal_total": len(normal_predictions),
        "false_positive_rate": fpr,
        "mean_latency_ms": mean_latency,
        "p95_latency_ms": statistics.quantiles(latencies, n=20)[-1] if len(latencies) > 1 else mean_latency,
        "max_latency_ms": max(latencies),
        "latency_target_ms": latency_target_ms,
        "nfr01_pass": nfr01_pass,
    }
    if verbose:
        print(format_metrics(metrics, title))
    return metrics


def format_confusion_matrix(matrix) -> str:
    width = max(len(label) for label in LABELS) + 2
    header = "True \\ Predicted".ljust(width + 2) + "".join(label.rjust(width) for label in LABELS)
    rows = [
        label.ljust(width + 2) + "".join(str(value).rjust(width) for value in row)
        for label, row in zip(LABELS, matrix)
    ]
    return "\n".join([header, *rows])


def format_metrics(metrics: dict, title: str | None = None) -> str:
    verdict = "PASS" if metrics["nfr01_pass"] else "FAIL"
    comparison = "<" if metrics["nfr01_pass"] else ">="
    lines = []
    if title:
        lines += [title, "=" * len(title)]
    lines += [
        f"Observations evaluated: {metrics['total']}",
        "",
        "Classification report:",
        metrics["report_text"].rstrip(),
        "",
        "Confusion matrix (rows = true label, columns = predicted label):",
        format_confusion_matrix(metrics["confusion_matrix"]),
        "",
        f"False Positive Rate (Normal -> any other class): "
        f"{metrics['false_positives']}/{metrics['normal_total']} = {metrics['false_positive_rate']:.4%}",
        "",
        f"Mean detection latency: {metrics['mean_latency_ms']:.4f} ms "
        f"(p95 {metrics['p95_latency_ms']:.4f} ms, max {metrics['max_latency_ms']:.4f} ms)",
        f"NFR01 near-real-time latency: {verdict} "
        f"(mean {metrics['mean_latency_ms']:.4f} ms {comparison} target {metrics['latency_target_ms']:.1f} ms)",
    ]
    return "\n".join(lines)

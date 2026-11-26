"""Measurements for the frozen synthetic holdout and the proposed guard."""

from collections import Counter
from statistics import mean

import numpy as np
from sklearn.metrics import accuracy_score, confusion_matrix, precision_recall_fscore_support

from response_ml.rubric import MONITORING, RESPONSE_CLASSES


AGGREGATES = (
    "accuracy", "balanced_accuracy", "macro_precision", "macro_recall", "macro_f1", "weighted_f1",
)


def classification_metrics(reference: list[str], predictions: list[str]) -> dict:
    labels = RESPONSE_CLASSES
    precision, recall, f1, support = precision_recall_fscore_support(
        reference, predictions, labels=labels, zero_division=0,
    )
    present = support > 0
    # Macro metrics on restricted subsets use only classes with true support.
    averages = [float(values[present].mean()) if any(present) else None for values in (precision, recall, f1)]
    return {
        "rows": len(reference),
        "accuracy": float(accuracy_score(reference, predictions)) if reference else None,
        "balanced_accuracy": averages[1],
        "macro_precision": averages[0],
        "macro_recall": averages[1],
        "macro_f1": averages[2],
        "weighted_f1": float(np.average(f1, weights=support)) if reference else None,
        "per_class": {
            label: {"precision": float(p), "recall": float(r), "f1": float(f), "support": int(n)}
            for label, p, r, f, n in zip(labels, precision, recall, f1, support, strict=True)
        },
        "confusion_matrix": confusion_matrix(reference, predictions, labels=labels).tolist(),
    }


def critical_errors(cases, predictions: list[str]) -> dict:
    items = [(case, prediction) for case, prediction in zip(cases, predictions, strict=True)
             if case.row.risk_level == "CRITICAL"]
    mismatches = [(case, prediction) for case, prediction in items if prediction != case.target]
    return {
        "critical_rows": len(items),
        "critical_mismatches": len(mismatches),
        "critical_monitoring_recommendations": sum(prediction in MONITORING for _, prediction in items),
        "mismatch_pairs": [
            {"reference": ref, "recommendation": rec, "rows": count}
            for (ref, rec), count in sorted(Counter((case.target, prediction) for case, prediction in mismatches).items())
        ],
    }


def confidence_summary(scores: np.ndarray, correct: np.ndarray) -> dict:
    bins = (0.0, 0.5, 0.7, 0.85, 0.95, 1.0)
    records = []
    for low, high in zip(bins, bins[1:]):
        selected = (scores >= low) & ((scores <= high) if high == 1.0 else (scores < high))
        records.append({
            "low": low, "high": high, "rows": int(selected.sum()),
            "rubric_agreement": float(correct[selected].mean()) if selected.any() else None,
        })
    return {
        "definition": "Maximum class probability, uncalibrated",
        "mean": float(scores.mean()), "minimum": float(scores.min()),
        "median": float(np.median(scores)), "p95": float(np.percentile(scores, 95)),
        "maximum": float(scores.max()), "bins": records,
    }


def latency_summary(times: list[float]) -> dict:
    return {
        "scope": "Warm single-row preprocessing plus predict_proba, excluding disk and safety screening",
        "samples": len(times), "unit": "ms", "mean": mean(times),
        "median": float(np.median(times)), "p95": float(np.percentile(times, 95)),
    }

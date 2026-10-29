"""Batch classification with per-call latency for configuration experiments."""

from __future__ import annotations

import time

from src.classifier import ThreatClassifier
from src.real_data import Signal


def label_and_run(
    module: ThreatClassifier, dataset: list[tuple[Signal, str]]
) -> list[tuple[str, str, float]]:
    """Return (true_label, predicted_label, latency_ms) for each labelled signal."""
    results: list[tuple[str, str, float]] = []
    for signal, true_label in dataset:
        started = time.perf_counter()
        output = module.classify(signal)
        latency_ms = (time.perf_counter() - started) * 1000.0
        results.append((true_label, output.classification, latency_ms))
    return results

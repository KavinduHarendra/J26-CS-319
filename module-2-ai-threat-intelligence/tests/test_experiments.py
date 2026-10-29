from dataclasses import replace
from pathlib import Path

from src.anomaly_engine import AnomalyEngine
from src.classifier import ThreatClassifier, build_classifier
from src.experiments import label_and_run
from src.real_data import load_signal


SAMPLE = Path("data/real/module1_signals_clean/known_signals/000001_S00001.json")


def test_label_and_run_returns_label_prediction_and_latency():
    signal = load_signal(SAMPLE)
    results = label_and_run(build_classifier(), [(signal, "NORMAL")])

    assert len(results) == 1
    true_label, predicted, latency_ms = results[0]
    assert (true_label, predicted) == ("NORMAL", "NORMAL")
    assert latency_ms >= 0.0


def test_high_threshold_disables_anomaly_path():
    combined = build_classifier()
    rule_only = ThreatClassifier(
        combined.baseline, combined.rules, AnomalyEngine(combined.baseline, threshold=999.0)
    )
    deviated = replace(load_signal(SAMPLE), spectral_flatness=0.2)

    [(_, combined_label, _)] = label_and_run(combined, [(deviated, "UNKNOWN_ANOMALY")])
    [(_, rule_only_label, _)] = label_and_run(rule_only, [(deviated, "UNKNOWN_ANOMALY")])

    assert combined_label == "UNKNOWN_ANOMALY"
    assert rule_only_label == "NORMAL"

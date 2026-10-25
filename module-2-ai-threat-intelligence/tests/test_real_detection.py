import json
from pathlib import Path

import pytest

from src.classifier import Classification, build_classifier
from src.real_data import load_stream


DATA = Path("data/real/module1_signals_clean")


def test_runtime_classifier_uses_calibrated_configuration():
    configuration = json.loads(Path("config/thresholds_real.json").read_text(encoding="utf-8"))
    classifier = build_classifier()

    assert configuration["thresholds"]["T_SNR"] == pytest.approx(25.8)
    assert configuration["thresholds"]["T_BW"] == pytest.approx(137.5)
    assert classifier.baseline.idle.anomaly_limit == pytest.approx(3.0)
    assert classifier.baseline.legitimate.anomaly_limit == pytest.approx(4.98, abs=0.01)


def test_pipeline_accepts_every_raw_capture():
    classifier = build_classifier()
    outputs = [classifier.classify(signal) for signal in load_stream(DATA)]

    assert len(outputs) == 1513
    assert {output.classification for output in outputs} <= {
        Classification.NORMAL.value,
        Classification.JAMMING.value,
        Classification.UNKNOWN_ANOMALY.value,
    }
    assert all(output.statistical_deviation for output in outputs)

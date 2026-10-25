from dataclasses import replace
from pathlib import Path

from src.anomaly_engine import AnomalyEngine
from src.baseline import Baseline
from src.real_data import load_signal


CONFIG = Path("config/thresholds_real.json")
SAMPLE = Path("data/real/module1_signals_clean/known_signals/000001_S00001.json")


def test_normalized_distance_is_raw_distance_divided_by_state_limit():
    result = AnomalyEngine(Baseline.load(CONFIG)).evaluate(load_signal(SAMPLE))

    assert result.normalized_distance == result.distance / 3.0
    assert not result.abnormal


def test_large_measurement_deviation_is_unknown_candidate_with_named_evidence():
    sample = load_signal(SAMPLE)
    changed = replace(sample, peak_db=-20.0)

    result = AnomalyEngine(Baseline.load(CONFIG)).evaluate(changed)

    assert result.abnormal
    assert "peak_db" in result.abnormal_features
    assert any("peak_db" in item for item in result.evidence)

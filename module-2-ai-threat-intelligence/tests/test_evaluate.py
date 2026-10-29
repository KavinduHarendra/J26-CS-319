import pytest

from src.evaluate import evaluate_results


RESULTS = [
    ("NORMAL", "NORMAL", 1.0),
    ("NORMAL", "NORMAL", 2.0),
    ("NORMAL", "NORMAL", 3.0),
    ("NORMAL", "JAMMING", 4.0),
    ("JAMMING", "JAMMING", 5.0),
    ("UNKNOWN_ANOMALY", "UNKNOWN_ANOMALY", 6.0),
]


def test_false_positive_rate_counts_normal_misclassified_as_anything_else():
    metrics = evaluate_results(RESULTS, verbose=False)

    assert (metrics["false_positives"], metrics["normal_total"]) == (1, 4)
    assert metrics["false_positive_rate"] == pytest.approx(0.25)
    assert metrics["confusion_matrix"].tolist() == [[3, 1, 0], [0, 1, 0], [0, 0, 1]]


def test_nfr01_passes_below_target_and_fails_at_or_above(capsys):
    assert evaluate_results(RESULTS, latency_target_ms=50.0)["nfr01_pass"]
    assert "NFR01 near-real-time latency: PASS" in capsys.readouterr().out

    assert not evaluate_results(RESULTS, latency_target_ms=3.5)["nfr01_pass"]
    assert "NFR01 near-real-time latency: FAIL" in capsys.readouterr().out


def test_unknown_label_is_rejected():
    with pytest.raises(ValueError, match="unknown label"):
        evaluate_results([("NORMAL", "MAYBE", 1.0)], verbose=False)

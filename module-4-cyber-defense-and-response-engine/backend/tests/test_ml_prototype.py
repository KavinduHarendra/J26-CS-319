import csv

import numpy as np
import pytest

from response_ml.dataset import write_csv
from response_ml.features import FEATURE_COLUMNS
from response_ml.generate import generate_rows
from response_ml.label import export_labels
from response_ml.preprocessing import NUMERIC, feature_matrix, make_preprocessor
from response_ml.prototype_data import LABEL_COLUMNS, load_study, read_records
from response_ml.prototype_metrics import classification_metrics
from response_ml.prototype_safety import screen_recommendation
from response_ml.review import SPLIT_COLUMNS


@pytest.fixture(scope="module")
def cases():
    return generate_rows(1000, 42, 10)


def test_auto_label_export_preserves_pending_human_fields(tmp_path, cases):
    original = tmp_path / "source.csv"
    export = tmp_path / "labeled.csv"
    write_csv(original, cases[:16])
    initial = original.read_bytes()
    summary = export_labels(original, export)
    rows = read_records(export, LABEL_COLUMNS)
    assert len(rows) == summary["rows"] == 16
    assert summary["approved_responses"] == 0
    assert {r["label_source"] for r in rows} == {"RUBRIC_GENERATED"}
    assert {r["label_status"] for r in rows} == {"PENDING"}
    assert all(not r["validated_response"] and r["provisional_response"] for r in rows)
    assert [r["rule_based_response"] for r in rows] == [r.rule_based_response for r in cases[:16]]
    assert original.read_bytes() == initial


def test_split_verification_rejects_cross_partition_duplicates(tmp_path, cases):
    case = cases[0]
    duplicate = case.model_copy(update={
        "observation_id": "SECOND", "session_id": "SECOND-SESSION",
        "scenario_id": "OTHER-FAMILY", "raw_record_ref": "second-case",
    })
    original = tmp_path / "source.csv"
    labels = tmp_path / "labels.csv"
    manifest = tmp_path / "split.csv"
    write_csv(original, [case, duplicate])
    export_labels(original, labels)
    with manifest.open("x", encoding="utf-8", newline="") as stream:
        writer = csv.writer(stream)
        writer.writerow(SPLIT_COLUMNS)
        for row, fold in ((case, "train"), (duplicate, "test")):
            writer.writerow((row.observation_id, row.session_id, row.scenario_id, fold))
    with pytest.raises(ValueError, match="exact feature vector overlaps"):
        load_study(original, labels, manifest)


def test_preprocessing_uses_the_allowlist_and_train_median(cases):
    base = cases[0]
    train = [base.model_copy(update={"threat_confidence": value}) for value in (0.5, 0.7, None)]
    later = [base.model_copy(update={"threat_confidence": 0.99, "severity": None}), base]
    x = feature_matrix(train)
    assert x.shape[1] == len(FEATURE_COLUMNS) == 15
    assert base.observation_id not in x
    preprocessor = make_preprocessor().fit(x)
    transformed = preprocessor.transform(feature_matrix(later))
    assert np.isfinite(transformed).all()
    imputer = preprocessor.named_transformers_["numeric"]
    assert imputer.statistics_[NUMERIC.index("threat_confidence")] == pytest.approx(0.6)


def test_offline_guard_preserves_replay_and_critical_gap(cases):
    replay = next(row for row in cases if row.replay_detected)
    gap = next(row for row in cases if row.risk_level == "CRITICAL" and row.rule_based_response == "CONTINUE_MONITORING")
    clean = next(row for row in cases if row.rule_based_response == "MONITOR")
    assert screen_recommendation(replay, "MONITOR").recommendation == "SECURE_HOLD"
    assert screen_recommendation(gap, "CONTINUE_MONITORING").recommendation == "OPERATOR_ESCALATION"
    assert screen_recommendation(clean, "PREPARE_BACKUP_CHANNEL").reason == "UNSUPPORTED_HOLD_OR_BACKUP"
    assert screen_recommendation(clean, "MONITOR").reason is None
    assert gap.rule_based_response == "CONTINUE_MONITORING"


def test_subset_macro_scores_skip_classes_with_no_reference_support():
    scores = classification_metrics(["MONITOR", "MONITOR"], ["MONITOR", "OPERATOR_ESCALATION"])
    assert scores["accuracy"] == 0.5
    assert scores["balanced_accuracy"] == scores["macro_recall"] == 0.5
    assert scores["macro_f1"] == pytest.approx(2 / 3)
    assert scores["per_class"]["SECURE_HOLD"]["support"] == 0

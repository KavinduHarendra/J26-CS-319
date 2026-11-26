import csv

import pytest

from response_ml.dataset import load_csv, write_csv
from response_ml.evaluation import plan_split
from response_ml.generate import feature_signature, generate_rows
from response_ml.review import BLIND_COLUMNS, prepare_review
from response_ml.rubric import MONITORING, RESPONSE_CLASSES, suggest_response


@pytest.fixture(scope="module")
def synthetic_rows():
    return generate_rows(1000, 42, 10)


def is_critical_monitoring(row):
    return row.risk_level == "CRITICAL" and row.rule_based_response in MONITORING


def test_draft_rubric_keeps_the_known_policy_gap_visible(synthetic_rows):
    gap = [row for row in synthetic_rows if is_critical_monitoring(row)]
    assert gap and {row.risk_score for row in gap} == {85.0}
    assert {suggest_response(row).response for row in gap} == {"OPERATOR_ESCALATION"}
    assert all(row.validated_response is None and row.label_status == "PENDING" for row in gap)
    assert {suggest_response(row).response for row in synthetic_rows} == set(RESPONSE_CLASSES)
    assert all(suggest_response(row).response == "SECURE_HOLD" for row in synthetic_rows if row.replay_detected)


def test_review_pack_keeps_reference_labels_out_of_blind_file(tmp_path, synthetic_rows):
    dataset = tmp_path / "input.csv"
    write_csv(dataset, synthetic_rows)
    folder = tmp_path / "review"
    result = prepare_review(dataset, folder, 144, 42)
    sample = load_csv(folder / "labeling-review.csv")
    assert len(sample) == len({feature_signature(row) for row in sample}) == 144
    assert sum(is_critical_monitoring(row) for row in sample) == sum(is_critical_monitoring(row) for row in synthetic_rows)

    with (folder / "blind-review.csv").open(newline="", encoding="utf-8") as stream:
        reader = csv.DictReader(stream)
        assert tuple(reader.fieldnames) == BLIND_COLUMNS
        assert not {"rule_based_response", "baseline_response", "suggested_response", "rubric_suggestion",
                    "scenario_id", "partition", "observation_id"} & set(reader.fieldnames)
        blind = list(reader)
        assert all(not row["validated_response"] and row["label_status"] == "PENDING" for row in blind)
    with (folder / "review-key.csv").open(newline="", encoding="utf-8") as stream:
        key = list(csv.DictReader(stream))
    assert {row["observation_id"] for row in key} == {row.observation_id for row in sample}
    assert {row["review_id"] for row in key} == {row["review_id"] for row in blind}
    for fold in result["review"].values():
        for counts in fold["classes"].values():
            assert all(case["distinct_vectors"] >= 6 and case["sessions"] >= 2 for case in counts.values())


def test_split_keeps_families_sessions_and_exact_matches_together(synthetic_rows):
    # A cross-family duplicate connects the two families without changing row inputs.
    source = synthetic_rows[0]
    other = next(row for row in synthetic_rows if row.scenario_id != source.scenario_id)
    duplicate = source.model_copy(update={
        "scenario_id": other.scenario_id, "session_id": other.session_id,
        "observation_id": "DUPLICATE-FIXTURE", "raw_record_ref": "test-duplicate",
    })
    rows = [*synthetic_rows, duplicate]
    assignments, components = plan_split(rows, 42)
    assert components == 17
    assert assignments[source.scenario_id] == assignments[other.scenario_id]
    session_folds, feature_folds = {}, {}
    for row in rows:
        fold = assignments[row.scenario_id]
        assert session_folds.setdefault(row.group, fold) == fold
        assert feature_folds.setdefault(feature_signature(row), fold) == fold

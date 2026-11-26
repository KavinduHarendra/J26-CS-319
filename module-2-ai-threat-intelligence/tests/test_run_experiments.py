import pytest

from scripts.calibrate_real import DATA_ROOT, build_configuration
from scripts.compare_baselines import IDENTICAL_NOTE, group_table, note
from scripts.run_experiments import (
    GROUPS,
    group_datasets,
    leave_one_out_configuration,
    leave_one_out_dataset,
)
from src.scoring_data import load_ground_truth


@pytest.fixture(scope="module")
def calibrated():
    return build_configuration()


def test_unseen_captures_are_labelled_jamming_as_in_ground_truth(calibrated):
    _, split = calibrated
    truth = load_ground_truth(DATA_ROOT / "ground_truth.csv")

    unseen = group_datasets(split)["unseen_jammer_types"]

    assert len(unseen) == 93
    assert {label for _, label in unseen} == {"JAMMING"}
    assert {truth[signal.observation_id]["expected_class"] for signal, _ in unseen} == {"JAMMING"}
    assert {truth[signal.observation_id]["jammer_type"] for signal, _ in unseen} == {
        "PULSED_5_95",
        "RANDOM_BURSTS",
    }


def test_calibration_and_validation_groups_follow_the_split(calibrated):
    _, split = calibrated
    datasets = group_datasets(split)

    for name in ("calibration", "validation"):
        expected = {s.observation_id for group in getattr(split, name).values() for s in group}
        assert {signal.observation_id for signal, _ in datasets[name]} == expected


@pytest.mark.parametrize("held", ["CARRIER", "PULSED_50_50"])
def test_leave_one_out_recalibrates_without_the_held_type(calibrated, held):
    configuration, split = calibrated
    retained = "PULSED_50_50" if held == "CARRIER" else "CARRIER"

    thresholds = leave_one_out_configuration(configuration, split, held)["thresholds"]
    dataset = leave_one_out_dataset(split, held)

    legit_min_bw = min(signal.occupied_bw_khz for signal in split.calibration["legit_ook"])
    retained_max_bw = max(signal.occupied_bw_khz for signal in split.calibration[retained])
    assert thresholds["T_BW"] == pytest.approx((retained_max_bw + legit_min_bw) / 2)
    assert len(dataset) == len(split.calibration[held]) + len(split.validation[held])
    assert {label for _, label in dataset} == {"JAMMING"}
    assert configuration["thresholds"]["T_BW"] == pytest.approx(137.5)  # original untouched


def rows(predictions):
    return [(true, predicted, 0.1, group) for true, predicted, group in predictions]


def test_report_note_is_honest_about_identical_results():
    same = rows([("NORMAL", "NORMAL", "validation"), ("JAMMING", "JAMMING", "unseen_jammer_types")])
    clean = {"false_positives": 0}

    assert note({"rulebase_only": same, "combined": same}, {"rulebase_only": clean, "combined": clean}) == IDENTICAL_NOTE

    different = rows(
        [("NORMAL", "UNKNOWN_ANOMALY", "validation"), ("JAMMING", "JAMMING", "unseen_jammer_types")]
    )
    text = note(
        {"rulebase_only": same, "combined": different},
        {"rulebase_only": clean, "combined": {"false_positives": 1}},
    )
    assert "disagree on 1 of 2" in text


def test_group_table_lists_every_group():
    predictions = [("JAMMING", "JAMMING", group) for group in GROUPS]
    table = group_table({"rulebase_only": rows(predictions), "combined": rows(predictions)})

    assert "Unseen jammer types | 1 (0 / 1) | 1/1 (100.00%)" in table
    assert len(table.splitlines()) == 2 + len(GROUPS)

import copy
import json
import math

import pytest

from scripts.calibrate_real import DATA_ROOT, build_configuration
from src.classifier import DEFAULT_CONFIG_PATH, Classification, build_classifier
from src.fuzzy import FuzzyRiskSystem, Trapezoid
from src.real_data import load_stream


@pytest.fixture(scope="module")
def configuration():
    return json.loads(DEFAULT_CONFIG_PATH.read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def fuzzy(configuration):
    return FuzzyRiskSystem.from_config(configuration)


@pytest.fixture(scope="module")
def validation():
    _, split = build_configuration()
    return split.validation


def scores(fuzzy, signals):
    return [fuzzy.evaluate(signal.snr_db, signal.occupied_bw_khz).score for signal in signals]


def test_validation_idle_and_legit_score_below_50(fuzzy, validation):
    normal = validation["idle"] + validation["legit_ook"]

    assert normal
    assert max(scores(fuzzy, normal)) < 50.0


def test_validation_jamming_scores_at_least_50(fuzzy, validation):
    jamming = validation["CARRIER"] + validation["PULSED_50_50"]

    assert jamming
    assert min(scores(fuzzy, jamming)) >= 50.0


def test_unseen_jammer_types_score_at_least_50(fuzzy):
    unseen = list(load_stream(DATA_ROOT / "abnormal_signals"))

    assert len(unseen) == 93
    assert min(scores(fuzzy, unseen)) >= 50.0


def test_breakpoints_come_from_calibrated_config(configuration, fuzzy):
    idle = configuration["normal_states"]["idle"]
    legit = configuration["normal_states"]["legit_ook"]
    t_snr = configuration["thresholds"]["T_SNR"]
    t_bw = configuration["thresholds"]["T_BW"]
    idle_top = idle["mean"]["snr_db"] + idle["anomaly_limit"] * idle["spread"]["snr_db"]
    legit_bottom = (
        legit["mean"]["occupied_bw_khz"]
        - legit["anomaly_limit"] * legit["spread"]["occupied_bw_khz"]
    )

    assert fuzzy.snr_sets["STRONG"] == Trapezoid(idle_top, t_snr, math.inf, math.inf)
    assert fuzzy.bw_sets["NARROW"] == Trapezoid(-math.inf, -math.inf, t_bw, legit_bottom)


def test_changing_config_moves_the_breakpoints(configuration):
    changed = copy.deepcopy(configuration)
    changed["thresholds"]["T_SNR"] = 40.0
    changed["thresholds"]["T_BW"] = 20.0

    fuzzy = FuzzyRiskSystem.from_config(changed)

    assert fuzzy.snr_sets["STRONG"].b == 40.0
    assert fuzzy.bw_sets["NARROW"].c == 20.0


def test_shipped_cutoffs_match_calibration_script(configuration):
    built, _ = build_configuration()

    assert configuration["fuzzy"] == built["fuzzy"]
    assert configuration["fuzzy"] == {"severity_medium_from": 50.0, "severity_high_from": 75.0}


@pytest.mark.parametrize(
    ("score", "severity"),
    [(0.0, "LOW"), (49.99, "LOW"), (50.0, "MEDIUM"), (74.99, "MEDIUM"), (75.0, "HIGH")],
)
def test_score_maps_to_severity(fuzzy, score, severity):
    assert fuzzy.severity(score) == severity


def test_severity_cutoffs_are_read_from_config(configuration):
    changed = copy.deepcopy(configuration)
    changed["fuzzy"] = {"severity_medium_from": 30.0, "severity_high_from": 60.0}

    fuzzy = FuzzyRiskSystem.from_config(changed)

    assert fuzzy.severity(45.0) == "MEDIUM"
    assert fuzzy.severity(65.0) == "HIGH"


def test_r1_region_fires_only_the_jamming_rule(configuration, fuzzy):
    t_snr = configuration["thresholds"]["T_SNR"]
    t_bw = configuration["thresholds"]["T_BW"]

    result = fuzzy.evaluate(t_snr, t_bw)

    assert [rule.id for rule in result.fired] == ["F1"]
    assert result.fired[0].strength == 1.0
    assert result.severity == "HIGH"


def test_partial_evidence_gives_graded_score(fuzzy):
    weak, middling, strong = (fuzzy.evaluate(snr, 40.0).score for snr in (3.0, 15.0, 50.0))

    assert weak < middling < strong
    assert {rule.id for rule in fuzzy.evaluate(15.0, 40.0).fired} == {"F1", "F3"}


def test_evidence_lists_score_and_firing_rules(fuzzy):
    result = fuzzy.evaluate(50.0, 30.0)

    assert result.evidence() == [
        f"fuzzy_score {result.score:.1f} (HIGH)",
        "fuzzy F1 fired at 1.00: STRONG snr AND NARROW bw -> HIGH risk",
    ]


def test_score_stays_within_0_to_100(fuzzy):
    for snr in (-10.0, 0.0, 10.0, 25.8, 60.0, 200.0):
        for bw in (0.0, 50.0, 160.0, 1_000.0):
            assert 0.0 <= fuzzy.evaluate(snr, bw).score <= 100.0


@pytest.mark.parametrize(("medium", "high"), [(75.0, 50.0), (0.0, 75.0), (50.0, 100.0)])
def test_invalid_cutoffs_are_rejected(configuration, medium, high):
    changed = copy.deepcopy(configuration)
    changed["fuzzy"] = {"severity_medium_from": medium, "severity_high_from": high}

    with pytest.raises(ValueError, match="cut-offs"):
        FuzzyRiskSystem.from_config(changed)


def test_unordered_trapezoid_is_rejected():
    with pytest.raises(ValueError, match="ordered"):
        Trapezoid(10.0, 5.0, 20.0, 30.0)


def test_classifier_appends_fuzzy_evidence_to_every_path(validation):
    output = build_classifier().classify(validation["idle"][0])

    assert output.classification == Classification.NORMAL.value
    assert output.evidence[-2:] == [
        "fuzzy_score 19.4 (LOW)",
        "fuzzy F3 fired at 1.00: WEAK snr -> LOW risk",
    ]

from src.rule_engine import build_rule_engine


def test_r1_fires_for_narrowband_strong_signal_with_actual_values():
    result = build_rule_engine(25.8, 137.5).evaluate(
        {"snr_db": 41.3, "occupied_bw_khz": 23.0}
    )

    assert result.triggered_rule == "R1"
    assert result.skipped_rules == ()
    assert result.evidence == (
        "snr_db 41.3 >= 25.8 and 0 < occupied_bw_khz 23.0 <= 137.5",
    )


def test_r1_does_not_fire_for_zero_or_wide_bandwidth():
    engine = build_rule_engine(25.8, 137.5)

    assert engine.evaluate({"snr_db": 50.0, "occupied_bw_khz": 0.0}).triggered_rule is None
    assert engine.evaluate({"snr_db": 50.0, "occupied_bw_khz": 138.0}).triggered_rule is None


def test_missing_required_feature_is_skipped_without_key_error():
    result = build_rule_engine(25.8, 137.5).evaluate({"snr_db": 50.0})

    assert result.triggered_rule is None
    assert result.skipped_rules == ("R1",)

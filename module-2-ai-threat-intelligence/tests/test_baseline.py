"""
tests/test_baseline.py — Unit tests for NormalBaseline (src/baseline.py).

Covers:
  - Calibration correctness on known (hand-computed) data.
  - RuntimeError when z_scores() / deviations() called before calibrate().
  - ValueError when calibrate() is called with fewer than 2 samples.
  - z-score and deviation computation on known inputs.
  - Feature completeness and structural correctness.
  - End-to-end with SyntheticDataSource.
"""

import pytest
from datetime import datetime, timezone

from src.baseline import (
    BaselineIntegrityError,
    NormalBaseline,
    FeatureBaseline,
    UnsafeBaselineSampleError,
)
from src.schema import RFObservation
from src.data_source import SyntheticDataSource


# ---------------------------------------------------------------------------
# Fixtures — hand-crafted observations with known statistics
# ---------------------------------------------------------------------------

def _make_obs(rssi: float, snr: float, noise_floor: float, packet_rate: float,
              obs_id: str = "test-00000") -> RFObservation:
    """Helper to build an RFObservation with minimal boilerplate."""
    return RFObservation(
        observation_id=obs_id,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        rssi=rssi,
        snr=snr,
        noise_floor=noise_floor,
        packet_rate=packet_rate,
    )


@pytest.fixture
def known_baseline() -> NormalBaseline:
    """
    Baseline calibrated on 4 observations with known, hand-computable statistics.

    Observations:
        rssi:        [-60, -62, -58, -60]  -> mean=-60.0, pstd=sqrt(2)≈1.4142
        snr:         [ 24,  26,  24,  26]  -> mean= 25.0, pstd=1.0
        noise_floor: [-90, -90, -90, -90]  -> mean=-90.0, pstd=0.0 -> clamped to 1e-6
        packet_rate: [100, 100, 110,  90]  -> mean=100.0, pstd=sqrt(50)≈7.0711
    """
    bl = NormalBaseline()
    bl.add_normal_sample(_make_obs(-60.0, 24.0, -90.0, 100.0, "cal-0"))
    bl.add_normal_sample(_make_obs(-62.0, 26.0, -90.0, 100.0, "cal-1"))
    bl.add_normal_sample(_make_obs(-58.0, 24.0, -90.0, 110.0, "cal-2"))
    bl.add_normal_sample(_make_obs(-60.0, 26.0, -90.0,  90.0, "cal-3"))
    bl.calibrate()
    return bl


# ---------------------------------------------------------------------------
# 1. Calibration correctness on known data
# ---------------------------------------------------------------------------

class TestCalibrationCorrectness:
    """Verify mean and std are computed correctly from known sample values."""

    def test_mean_rssi(self, known_baseline):
        assert known_baseline.baseline["rssi"].mean == pytest.approx(-60.0)

    def test_mean_snr(self, known_baseline):
        assert known_baseline.baseline["snr"].mean == pytest.approx(25.0)

    def test_mean_noise_floor(self, known_baseline):
        assert known_baseline.baseline["noise_floor"].mean == pytest.approx(-90.0)

    def test_mean_packet_rate(self, known_baseline):
        assert known_baseline.baseline["packet_rate"].mean == pytest.approx(100.0)

    def test_std_rssi(self, known_baseline):
        # pstdev([-60,-62,-58,-60]) = sqrt(((0+4+4+0)/4)) = sqrt(2)
        import math
        assert known_baseline.baseline["rssi"].std == pytest.approx(math.sqrt(2), abs=1e-4)

    def test_std_snr(self, known_baseline):
        # pstdev([24,26,24,26]) = sqrt(((1+1+1+1)/4)) = 1.0
        assert known_baseline.baseline["snr"].std == pytest.approx(1.0)

    def test_std_noise_floor_zero_clamped(self, known_baseline):
        # All values identical => pstdev = 0.0 => clamped to 1e-6
        assert known_baseline.baseline["noise_floor"].std == pytest.approx(1e-6)

    def test_std_packet_rate(self, known_baseline):
        # pstdev([100,100,110,90]) = sqrt(((0+0+100+100)/4)) = sqrt(50)
        import math
        assert known_baseline.baseline["packet_rate"].std == pytest.approx(math.sqrt(50), abs=1e-4)

    def test_calibrated_flag_set(self, known_baseline):
        assert known_baseline.calibrated is True

    def test_calibrated_flag_unset_initially(self):
        bl = NormalBaseline()
        assert bl.calibrated is False


# ---------------------------------------------------------------------------
# 2. RuntimeError before calibration
# ---------------------------------------------------------------------------

class TestRuntimeErrorBeforeCalibration:
    """z_scores() and deviations() must raise RuntimeError if calibrate() hasn't run."""

    def test_z_scores_raises_before_calibration(self):
        bl = NormalBaseline()
        obs = _make_obs(-60.0, 25.0, -90.0, 100.0)
        with pytest.raises(RuntimeError, match="not calibrated"):
            bl.z_scores(obs)

    def test_deviations_raises_before_calibration(self):
        bl = NormalBaseline()
        obs = _make_obs(-60.0, 25.0, -90.0, 100.0)
        with pytest.raises(RuntimeError, match="not calibrated"):
            bl.deviations(obs)

    def test_z_scores_works_after_calibration(self, known_baseline):
        obs = _make_obs(-60.0, 25.0, -90.0, 100.0)
        z = known_baseline.z_scores(obs)
        assert isinstance(z, dict)
        assert set(z.keys()) == {"rssi", "snr", "noise_floor", "packet_rate"}


# ---------------------------------------------------------------------------
# 3. ValueError on insufficient samples
# ---------------------------------------------------------------------------

class TestValueErrorInsufficientSamples:
    """calibrate() must raise ValueError if fewer than 2 samples for any feature."""

    def test_zero_samples_raises(self):
        bl = NormalBaseline()
        with pytest.raises(ValueError, match="Not enough"):
            bl.calibrate()

    def test_one_sample_raises(self):
        bl = NormalBaseline()
        bl.add_normal_sample(_make_obs(-60.0, 25.0, -90.0, 100.0))
        with pytest.raises(ValueError, match="Not enough"):
            bl.calibrate()

    def test_two_samples_succeeds(self):
        bl = NormalBaseline()
        bl.add_normal_sample(_make_obs(-60.0, 25.0, -90.0, 100.0))
        bl.add_normal_sample(_make_obs(-62.0, 23.0, -88.0, 105.0))
        bl.calibrate()
        assert bl.calibrated is True


# ---------------------------------------------------------------------------
# 4. z-score computation on known inputs
# ---------------------------------------------------------------------------

class TestZScoreComputation:
    """Verify z = (x - mean) / std on hand-picked values."""

    def test_observation_at_mean_has_zero_z(self, known_baseline):
        """An observation at exactly the calibration mean should yield z ≈ 0."""
        obs = _make_obs(-60.0, 25.0, -90.0, 100.0)
        z = known_baseline.z_scores(obs)
        assert z["rssi"] == pytest.approx(0.0, abs=1e-4)
        assert z["snr"] == pytest.approx(0.0, abs=1e-4)
        # noise_floor std is clamped 1e-6, so (-90 - -90)/1e-6 = 0.0
        assert z["noise_floor"] == pytest.approx(0.0, abs=1e-1)
        assert z["packet_rate"] == pytest.approx(0.0, abs=1e-4)

    def test_rssi_one_std_above(self, known_baseline):
        import math
        std_rssi = math.sqrt(2)
        obs = _make_obs(-60.0 + std_rssi, 25.0, -90.0, 100.0)
        z = known_baseline.z_scores(obs)
        assert z["rssi"] == pytest.approx(1.0, abs=1e-3)

    def test_snr_two_std_below(self, known_baseline):
        obs = _make_obs(-60.0, 25.0 - 2.0, -90.0, 100.0)
        z = known_baseline.z_scores(obs)
        assert z["snr"] == pytest.approx(-2.0, abs=1e-3)

    def test_z_scores_returns_all_features(self, known_baseline):
        obs = _make_obs(-55.0, 30.0, -85.0, 120.0)
        z = known_baseline.z_scores(obs)
        assert set(z.keys()) == set(NormalBaseline.FEATURES)


# ---------------------------------------------------------------------------
# 5. Deviations dict structure and correctness
# ---------------------------------------------------------------------------

class TestDeviationsComputation:
    """Verify the deviations dict keys and directional transformations."""

    def test_deviations_keys(self, known_baseline):
        obs = _make_obs(-60.0, 25.0, -90.0, 100.0)
        dev = known_baseline.deviations(obs)
        expected_keys = {"snr_drop", "rssi_deviation", "noise_floor_increase",
                         "packet_rate_deviation", "z_scores"}
        assert set(dev.keys()) == expected_keys

    def test_snr_drop_positive_when_snr_below_mean(self, known_baseline):
        """When SNR is below the mean, snr_drop should be positive."""
        obs = _make_obs(-60.0, 20.0, -90.0, 100.0)  # SNR 5 below mean of 25
        dev = known_baseline.deviations(obs)
        assert dev["snr_drop"] > 0.0

    def test_snr_drop_zero_when_snr_above_mean(self, known_baseline):
        """When SNR is above the mean, snr_drop should be 0.0."""
        obs = _make_obs(-60.0, 30.0, -90.0, 100.0)  # SNR above mean
        dev = known_baseline.deviations(obs)
        assert dev["snr_drop"] == 0.0

    def test_noise_floor_increase_positive_when_noise_rises(self, known_baseline):
        """When noise floor is above the mean, noise_floor_increase should be positive."""
        obs = _make_obs(-60.0, 25.0, -80.0, 100.0)  # noise floor 10 above mean of -90
        dev = known_baseline.deviations(obs)
        assert dev["noise_floor_increase"] > 0.0

    def test_noise_floor_increase_zero_when_noise_drops(self, known_baseline):
        """When noise floor is below the mean, noise_floor_increase should be 0.0."""
        obs = _make_obs(-60.0, 25.0, -95.0, 100.0)  # noise floor below mean
        dev = known_baseline.deviations(obs)
        assert dev["noise_floor_increase"] == 0.0

    def test_rssi_deviation_is_absolute(self, known_baseline):
        """rssi_deviation should be non-negative regardless of direction."""
        obs_above = _make_obs(-55.0, 25.0, -90.0, 100.0)
        obs_below = _make_obs(-65.0, 25.0, -90.0, 100.0)
        dev_above = known_baseline.deviations(obs_above)
        dev_below = known_baseline.deviations(obs_below)
        assert dev_above["rssi_deviation"] > 0.0
        assert dev_below["rssi_deviation"] > 0.0

    def test_packet_rate_deviation_is_absolute(self, known_baseline):
        """packet_rate_deviation should be non-negative regardless of direction."""
        obs_high = _make_obs(-60.0, 25.0, -90.0, 130.0)
        obs_low = _make_obs(-60.0, 25.0, -90.0, 70.0)
        dev_high = known_baseline.deviations(obs_high)
        dev_low = known_baseline.deviations(obs_low)
        assert dev_high["packet_rate_deviation"] > 0.0
        assert dev_low["packet_rate_deviation"] > 0.0

    def test_deviations_nested_z_scores(self, known_baseline):
        """deviations dict must include nested z_scores dict."""
        obs = _make_obs(-60.0, 25.0, -90.0, 100.0)
        dev = known_baseline.deviations(obs)
        assert "z_scores" in dev
        assert isinstance(dev["z_scores"], dict)
        assert set(dev["z_scores"].keys()) == set(NormalBaseline.FEATURES)


# ---------------------------------------------------------------------------
# 6. add_normal_samples batch method
# ---------------------------------------------------------------------------

class TestAddNormalSamples:
    """Verify the batch add convenience method."""

    def test_batch_add_equivalent_to_single(self):
        obs_list = [
            _make_obs(-60.0, 24.0, -90.0, 100.0),
            _make_obs(-62.0, 26.0, -88.0, 105.0),
        ]
        # Method A: add individually
        bl_single = NormalBaseline()
        for obs in obs_list:
            bl_single.add_normal_sample(obs)
        bl_single.calibrate()

        # Method B: add as batch
        bl_batch = NormalBaseline()
        bl_batch.add_normal_samples(obs_list)
        bl_batch.calibrate()

        for f in NormalBaseline.FEATURES:
            assert bl_single.baseline[f].mean == bl_batch.baseline[f].mean
            assert bl_single.baseline[f].std == bl_batch.baseline[f].std


# ---------------------------------------------------------------------------
# 7. End-to-end with SyntheticDataSource (70/30 split sanity check)
# ---------------------------------------------------------------------------

class TestBaselineWithSyntheticDataSource:
    """
    Verify that calibrating on synthetic normal data through SyntheticDataSource
    produces sensible baselines, and that held-out z-scores stay small.
    """

    def test_calibrate_from_synthetic_source(self):
        source = SyntheticDataSource("normal", seed=42)
        all_obs = source.fetch_batch(200)

        split_idx = int(len(all_obs) * 0.70)
        calibration_set = all_obs[:split_idx]
        evaluation_set = all_obs[split_idx:]

        bl = NormalBaseline()
        bl.add_normal_samples(calibration_set)
        bl.calibrate()

        # Baseline mean should be near the generating distribution centers
        assert bl.baseline["rssi"].mean == pytest.approx(-60.0, abs=3.0)
        assert bl.baseline["snr"].mean == pytest.approx(25.0, abs=2.0)
        assert bl.baseline["noise_floor"].mean == pytest.approx(-90.0, abs=2.0)
        assert bl.baseline["packet_rate"].mean == pytest.approx(100.0, abs=5.0)

        # Held-out z-scores on normal data should mostly be small (|z| < 3)
        for obs in evaluation_set:
            z = bl.z_scores(obs)
            for f in NormalBaseline.FEATURES:
                assert abs(z[f]) < 5.0, (
                    f"Held-out normal obs {obs.observation_id} has extreme z={z[f]:.2f} for {f}"
                )

    def test_calibration_and_evaluation_sets_are_disjoint(self):
        """Confirm the 70/30 split produces non-overlapping ID sets."""
        source = SyntheticDataSource("normal", seed=99)
        all_obs = source.fetch_batch(100)
        split_idx = int(len(all_obs) * 0.70)

        calib_ids = {obs.observation_id for obs in all_obs[:split_idx]}
        eval_ids = {obs.observation_id for obs in all_obs[split_idx:]}

        assert calib_ids.isdisjoint(eval_ids)
        assert len(calib_ids) == 70
        assert len(eval_ids) == 30


class TestBaselinePersistenceIntegrity:
    def test_json_round_trip_with_sha256_sidecar(self, known_baseline, tmp_path):
        path = tmp_path / "baseline.json"

        known_baseline.save_baseline(path)
        loaded = NormalBaseline.load_baseline(path)

        assert path.exists()
        assert (tmp_path / "baseline.json.sha256").exists()
        assert loaded.calibrated is True
        assert loaded.version == NormalBaseline.FORMAT_VERSION
        assert loaded.created_at == known_baseline.created_at
        for feature in NormalBaseline.FEATURES:
            assert loaded.baseline[feature] == known_baseline.baseline[feature]

    def test_tampered_json_is_rejected(self, known_baseline, tmp_path):
        path = tmp_path / "baseline.json"
        known_baseline.save_baseline(path)
        path.write_text(path.read_text(encoding="utf-8") + " ", encoding="utf-8")

        with pytest.raises(BaselineIntegrityError, match="SHA-256 verification failed"):
            NormalBaseline.load_baseline(path)

    def test_tampered_hash_sidecar_is_rejected(self, known_baseline, tmp_path):
        path = tmp_path / "baseline.json"
        known_baseline.save_baseline(path)
        path.with_suffix(".json.sha256").write_text("0" * 64 + "\n", encoding="ascii")

        with pytest.raises(BaselineIntegrityError, match="SHA-256 verification failed"):
            NormalBaseline.load_baseline(path)

    def test_uncalibrated_baseline_cannot_be_saved(self, tmp_path):
        with pytest.raises(RuntimeError, match="uncalibrated"):
            NormalBaseline().save_baseline(tmp_path / "baseline.json")


class TestBaselinePoisoningProtection:
    @pytest.mark.parametrize("classification", ["Jamming", "Unknown Anomaly"])
    def test_refuses_threat_samples(self, classification):
        baseline = NormalBaseline()

        with pytest.raises(UnsafeBaselineSampleError, match="Refusing"):
            baseline.add_classified_sample(
                _make_obs(-60.0, 25.0, -90.0, 100.0),
                classification,
            )

        assert all(not samples for samples in baseline._samples.values())

    def test_accepts_explicitly_normal_sample(self):
        baseline = NormalBaseline()
        baseline.add_classified_sample(
            _make_obs(-60.0, 25.0, -90.0, 100.0),
            "Normal",
        )
        assert all(len(samples) == 1 for samples in baseline._samples.values())

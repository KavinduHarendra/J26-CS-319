"""
tests/test_data_source.py — Unit tests for RFDataSource and SyntheticDataSource.

Verifies:
  - RFDataSource ABC behavior (cannot be directly instantiated).
  - SyntheticDataSource scenario validation and batch fetching.
  - Correct number of observations returned per batch.
  - Scenario characteristics:
      * Jamming scenario has notably lower mean SNR and higher noise floor than normal.
      * Unknown anomaly has lower SNR than normal, but near-normal noise floor.
  - Batch size handling (0 returns empty list, negative raises ValueError).
  - Subsequent batches maintain distinct observation IDs.
  - Reproducibility when initialized with a fixed seed.
"""

import pytest

from src.data_source import RFDataSource, SyntheticDataSource
from src.schema import RFObservation


class TestRFDataSourceInterface:
    def test_cannot_instantiate_abstract_class(self):
        with pytest.raises(TypeError):
            RFDataSource()  # type: ignore

    def test_synthetic_source_is_subclass(self):
        assert issubclass(SyntheticDataSource, RFDataSource)
        source = SyntheticDataSource("normal")
        assert isinstance(source, RFDataSource)


class TestSyntheticDataSourceInitialization:
    def test_valid_scenarios(self):
        for scenario in ("normal", "jamming", "unknown_anomaly"):
            source = SyntheticDataSource(scenario)
            assert source.scenario == scenario

    def test_case_insensitive_scenario(self):
        source = SyntheticDataSource("  NORMAL  ")
        assert source.scenario == "normal"

    def test_invalid_scenario_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown scenario"):
            SyntheticDataSource("non_existent_scenario")


class TestSyntheticDataSourceBatchFetching:
    def test_fetch_batch_returns_requested_count(self):
        source = SyntheticDataSource("normal", seed=42)
        batch = source.fetch_batch(25)
        assert len(batch) == 25
        assert all(isinstance(obs, RFObservation) for obs in batch)

    def test_fetch_batch_zero(self):
        source = SyntheticDataSource("normal")
        batch = source.fetch_batch(0)
        assert batch == []

    def test_fetch_batch_negative_raises_value_error(self):
        source = SyntheticDataSource("normal")
        with pytest.raises(ValueError, match="non-negative"):
            source.fetch_batch(-5)

    def test_subsequent_batches_have_unique_ids(self):
        source = SyntheticDataSource("normal", seed=42)
        batch1 = source.fetch_batch(10)
        batch2 = source.fetch_batch(10)

        ids1 = {obs.observation_id for obs in batch1}
        ids2 = {obs.observation_id for obs in batch2}
        assert ids1.isdisjoint(ids2)
        assert len(ids1) == 10
        assert len(ids2) == 10

    def test_seeded_reproducibility(self):
        source_a = SyntheticDataSource("jamming", seed=123)
        source_b = SyntheticDataSource("jamming", seed=123)

        batch_a = source_a.fetch_batch(20)
        batch_b = source_b.fetch_batch(20)

        for obs_a, obs_b in zip(batch_a, batch_b):
            assert obs_a.snr == obs_b.snr
            assert obs_a.rssi == obs_b.rssi
            assert obs_a.noise_floor == obs_b.noise_floor
            assert obs_a.packet_rate == obs_b.packet_rate


class TestSyntheticDataSourceScenarioCharacteristics:
    """Verifies that each scenario produces data with expected physical RF characteristics."""

    def test_jamming_vs_normal_characteristics(self):
        normal_source = SyntheticDataSource("normal", seed=10)
        jamming_source = SyntheticDataSource("jamming", seed=20)

        normal_batch = normal_source.fetch_batch(100)
        jamming_batch = jamming_source.fetch_batch(100)

        mean_normal_snr = sum(obs.snr for obs in normal_batch) / len(normal_batch)
        mean_jamming_snr = sum(obs.snr for obs in jamming_batch) / len(jamming_batch)

        mean_normal_noise = sum(obs.noise_floor for obs in normal_batch) / len(normal_batch)
        mean_jamming_noise = sum(obs.noise_floor for obs in jamming_batch) / len(jamming_batch)

        # Jamming SNR (~8 dB) must be notably lower than normal (~25 dB)
        assert mean_jamming_snr < mean_normal_snr - 10.0, (
            f"Expected jamming SNR ({mean_jamming_snr:.2f}) to be significantly lower "
            f"than normal SNR ({mean_normal_snr:.2f})"
        )

        # Jamming noise floor (~-70 dBm) must be notably higher than normal (~-90 dBm)
        assert mean_jamming_noise > mean_normal_noise + 10.0, (
            f"Expected jamming noise floor ({mean_jamming_noise:.2f}) to be significantly higher "
            f"than normal noise floor ({mean_normal_noise:.2f})"
        )

    def test_unknown_anomaly_vs_normal_and_jamming(self):
        normal_source = SyntheticDataSource("normal", seed=30)
        jamming_source = SyntheticDataSource("jamming", seed=40)
        anomaly_source = SyntheticDataSource("unknown_anomaly", seed=50)

        normal_batch = normal_source.fetch_batch(100)
        jamming_batch = jamming_source.fetch_batch(100)
        anomaly_batch = anomaly_source.fetch_batch(100)

        mean_normal_snr = sum(obs.snr for obs in normal_batch) / len(normal_batch)
        mean_anomaly_snr = sum(obs.snr for obs in anomaly_batch) / len(anomaly_batch)

        mean_normal_noise = sum(obs.noise_floor for obs in normal_batch) / len(normal_batch)
        mean_jamming_noise = sum(obs.noise_floor for obs in jamming_batch) / len(jamming_batch)
        mean_anomaly_noise = sum(obs.noise_floor for obs in anomaly_batch) / len(anomaly_batch)

        # Anomaly SNR (~12 dB) is lower than normal (~25 dB)
        assert mean_anomaly_snr < mean_normal_snr - 8.0

        # Anomaly noise floor (~-89 dBm) remains near normal (~-90 dBm) and far below jamming (~-70 dBm)
        assert abs(mean_anomaly_noise - mean_normal_noise) < 3.0
        assert mean_anomaly_noise < mean_jamming_noise - 10.0

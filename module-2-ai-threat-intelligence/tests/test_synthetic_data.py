"""
tests/test_synthetic_data.py — Unit tests for src/synthetic_data.py.

Verifies count, types, ID prefixes, seeded reproducibility, and that the
Unknown Anomaly distribution does NOT look like a jamming event.
"""

import pytest

from src.schema import RFObservation
from src.synthetic_data import (
    generate_normal,
    generate_jamming,
    generate_unknown_anomaly,
)

SEED = 42


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def mean(values: list[float]) -> float:
    return sum(values) / len(values)


# ---------------------------------------------------------------------------
# generate_normal
# ---------------------------------------------------------------------------

class TestGenerateNormal:
    def test_returns_correct_count(self):
        assert len(generate_normal(n=200, seed=SEED)) == 200

    def test_custom_count(self):
        assert len(generate_normal(n=10, seed=SEED)) == 10

    def test_all_rfobservation_instances(self):
        obs = generate_normal(n=5, seed=SEED)
        assert all(isinstance(o, RFObservation) for o in obs)

    def test_id_prefix(self):
        obs = generate_normal(n=5, start_id=0, seed=SEED)
        assert all(o.observation_id.startswith("norm-") for o in obs)

    def test_id_sequence(self):
        obs = generate_normal(n=3, start_id=10, seed=SEED)
        assert [o.observation_id for o in obs] == ["norm-00010", "norm-00011", "norm-00012"]

    def test_timestamps_monotonically_increasing(self):
        obs = generate_normal(n=10, seed=SEED)
        ts = [o.timestamp for o in obs]
        assert ts == sorted(ts)

    def test_reproducible_with_same_seed(self):
        a = generate_normal(n=20, seed=SEED)
        b = generate_normal(n=20, seed=SEED)
        assert [(o.rssi, o.snr) for o in a] == [(o.rssi, o.snr) for o in b]

    def test_different_seeds_differ(self):
        a = generate_normal(n=20, seed=1)
        b = generate_normal(n=20, seed=2)
        assert [(o.rssi, o.snr) for o in a] != [(o.rssi, o.snr) for o in b]

    def test_rssi_near_minus60(self):
        obs = generate_normal(n=500, seed=SEED)
        avg = mean([o.rssi for o in obs])
        assert -63 < avg < -57, f"Expected rssi mean near -60, got {avg:.2f}"

    def test_snr_near_25(self):
        obs = generate_normal(n=500, seed=SEED)
        avg = mean([o.snr for o in obs])
        assert 23 < avg < 27, f"Expected snr mean near 25, got {avg:.2f}"

    def test_noise_floor_near_minus90(self):
        obs = generate_normal(n=500, seed=SEED)
        avg = mean([o.noise_floor for o in obs])
        assert -93 < avg < -87, f"Expected noise_floor near -90, got {avg:.2f}"

    def test_packet_rate_near_100(self):
        obs = generate_normal(n=500, seed=SEED)
        avg = mean([o.packet_rate for o in obs])
        assert 97 < avg < 103, f"Expected packet_rate near 100, got {avg:.2f}"


# ---------------------------------------------------------------------------
# generate_jamming
# ---------------------------------------------------------------------------

class TestGenerateJamming:
    def test_returns_correct_count(self):
        assert len(generate_jamming(n=50, seed=SEED)) == 50

    def test_all_rfobservation_instances(self):
        obs = generate_jamming(n=5, seed=SEED)
        assert all(isinstance(o, RFObservation) for o in obs)

    def test_id_prefix(self):
        obs = generate_jamming(n=5, start_id=1000, seed=SEED)
        assert all(o.observation_id.startswith("jam-") for o in obs)

    def test_snr_is_low(self):
        """Jamming SNR must be clearly below normal (mean ~8 vs normal ~25)."""
        obs = generate_jamming(n=200, seed=SEED)
        avg = mean([o.snr for o in obs])
        assert avg < 12, f"Jamming SNR mean should be low, got {avg:.2f}"

    def test_noise_floor_is_elevated(self):
        """Jamming noise floor must be clearly higher than normal (mean ~-70 vs -90)."""
        obs = generate_jamming(n=200, seed=SEED)
        avg = mean([o.noise_floor for o in obs])
        assert avg > -80, f"Jamming noise_floor should be elevated, got {avg:.2f}"

    def test_reproducible_with_same_seed(self):
        a = generate_jamming(n=20, seed=SEED)
        b = generate_jamming(n=20, seed=SEED)
        assert [(o.rssi, o.snr) for o in a] == [(o.rssi, o.snr) for o in b]


# ---------------------------------------------------------------------------
# generate_unknown_anomaly
# ---------------------------------------------------------------------------

class TestGenerateUnknownAnomaly:
    def test_returns_correct_count(self):
        assert len(generate_unknown_anomaly(n=50, seed=SEED)) == 50

    def test_all_rfobservation_instances(self):
        obs = generate_unknown_anomaly(n=5, seed=SEED)
        assert all(isinstance(o, RFObservation) for o in obs)

    def test_id_prefix(self):
        obs = generate_unknown_anomaly(n=5, start_id=2000, seed=SEED)
        assert all(o.observation_id.startswith("unk-") for o in obs)

    def test_snr_is_anomalous_vs_normal(self):
        """SNR should be noticeably below the normal mean of 25."""
        obs = generate_unknown_anomaly(n=200, seed=SEED)
        avg = mean([o.snr for o in obs])
        assert avg < 16, f"Unknown anomaly SNR should be below normal, got {avg:.2f}"

    def test_noise_floor_stays_near_normal(self):
        """
        Critical: noise_floor must NOT rise like jamming.
        This ensures the rule (SNR drop AND noise floor rise) cannot fire.
        """
        obs = generate_unknown_anomaly(n=200, seed=SEED)
        avg = mean([o.noise_floor for o in obs])
        assert avg < -84, (
            f"Unknown anomaly noise_floor should stay near -90 (got {avg:.2f}), "
            "not trigger the jamming rule"
        )

    def test_packet_rate_stays_near_normal(self):
        """Packet rate must remain near-normal — another reason it's not jamming."""
        obs = generate_unknown_anomaly(n=200, seed=SEED)
        avg = mean([o.packet_rate for o in obs])
        assert avg > 88, f"Unknown anomaly packet_rate should stay near 100, got {avg:.2f}"

    def test_rssi_stays_near_normal(self):
        obs = generate_unknown_anomaly(n=200, seed=SEED)
        avg = mean([o.rssi for o in obs])
        assert -66 < avg < -58, f"Unknown anomaly rssi should stay near -62, got {avg:.2f}"

    def test_noise_floor_different_from_jamming(self):
        """
        The noise floor distribution of unknown anomaly must be clearly
        distinct from jamming, confirming the rule cannot conflate them.
        """
        jamming = generate_jamming(n=200, seed=SEED)
        anomaly = generate_unknown_anomaly(n=200, seed=SEED)
        jam_nf_avg  = mean([o.noise_floor for o in jamming])
        anom_nf_avg = mean([o.noise_floor for o in anomaly])
        # Jamming noise floor (~-70) must be at least 10 dBm higher than anomaly (~-89)
        assert jam_nf_avg > anom_nf_avg + 10, (
            f"Jamming noise_floor ({jam_nf_avg:.2f}) should be much higher "
            f"than unknown anomaly ({anom_nf_avg:.2f})"
        )

    def test_reproducible_with_same_seed(self):
        a = generate_unknown_anomaly(n=20, seed=SEED)
        b = generate_unknown_anomaly(n=20, seed=SEED)
        assert [(o.rssi, o.snr) for o in a] == [(o.rssi, o.snr) for o in b]

"""
tests/test_schema.py — Unit tests for RFObservation (src/schema.py).

Verifies that the input-contract dataclass can be constructed correctly and that
every field retains the value it was given, preserving type expectations.
"""

from datetime import datetime, timezone

import pytest

from src.schema import RFObservation


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_observation() -> RFObservation:
    """Return a representative RFObservation for reuse across tests."""
    return RFObservation(
        observation_id="obs-001",
        timestamp=datetime(2026, 9, 26, 11, 0, 0, tzinfo=timezone.utc),
        rssi=-72.5,
        snr=18.3,
        noise_floor=-90.0,
        packet_rate=42.7,
    )


# ---------------------------------------------------------------------------
# Field-value tests
# ---------------------------------------------------------------------------

class TestRFObservationFields:
    """All fields must be stored exactly as supplied."""

    def test_observation_id(self, sample_observation):
        assert sample_observation.observation_id == "obs-001"

    def test_timestamp(self, sample_observation):
        expected = datetime(2026, 9, 26, 11, 0, 0, tzinfo=timezone.utc)
        assert sample_observation.timestamp == expected

    def test_rssi(self, sample_observation):
        assert sample_observation.rssi == -72.5

    def test_snr(self, sample_observation):
        assert sample_observation.snr == 18.3

    def test_noise_floor(self, sample_observation):
        assert sample_observation.noise_floor == -90.0

    def test_packet_rate(self, sample_observation):
        assert sample_observation.packet_rate == 42.7


# ---------------------------------------------------------------------------
# Type tests
# ---------------------------------------------------------------------------

class TestRFObservationTypes:
    """Fields must be of the declared types."""

    def test_observation_id_is_str(self, sample_observation):
        assert isinstance(sample_observation.observation_id, str)

    def test_timestamp_is_datetime(self, sample_observation):
        assert isinstance(sample_observation.timestamp, datetime)

    def test_rssi_is_float(self, sample_observation):
        assert isinstance(sample_observation.rssi, float)

    def test_snr_is_float(self, sample_observation):
        assert isinstance(sample_observation.snr, float)

    def test_noise_floor_is_float(self, sample_observation):
        assert isinstance(sample_observation.noise_floor, float)

    def test_packet_rate_is_float(self, sample_observation):
        assert isinstance(sample_observation.packet_rate, float)


# ---------------------------------------------------------------------------
# Repr / readability test
# ---------------------------------------------------------------------------

class TestRFObservationRepr:
    """The dataclass __repr__ should include all field names."""

    def test_repr_contains_all_fields(self, sample_observation):
        r = repr(sample_observation)
        for field in (
            "observation_id",
            "timestamp",
            "rssi",
            "snr",
            "noise_floor",
            "packet_rate",
        ):
            assert field in r, f"repr missing field: {field}"

    def test_repr_contains_values(self, sample_observation):
        r = repr(sample_observation)
        assert "obs-001" in r
        assert "-72.5" in r
        assert "42.7" in r


# ---------------------------------------------------------------------------
# Equality / dataclass semantics
# ---------------------------------------------------------------------------

class TestRFObservationEquality:
    """Two observations with identical fields must compare equal (dataclass default)."""

    def test_equal_instances(self, sample_observation):
        duplicate = RFObservation(
            observation_id="obs-001",
            timestamp=datetime(2026, 9, 26, 11, 0, 0, tzinfo=timezone.utc),
            rssi=-72.5,
            snr=18.3,
            noise_floor=-90.0,
            packet_rate=42.7,
        )
        assert sample_observation == duplicate

    def test_unequal_instances(self, sample_observation):
        different = RFObservation(
            observation_id="obs-002",
            timestamp=datetime(2026, 9, 26, 11, 0, 0, tzinfo=timezone.utc),
            rssi=-55.0,
            snr=25.0,
            noise_floor=-95.0,
            packet_rate=10.0,
        )
        assert sample_observation != different

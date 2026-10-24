"""
synthetic_data.py — Temporary stand-in for real SDR output.

Generates synthetic RFObservation records that mimic the three signal conditions
the AI Threat Intelligence Module must classify:

  * Normal          — baseline RF environment within expected parameters
  * Jamming         — rule-matchable: SNR drops sharply AND noise floor rises
  * Unknown Anomaly — only SNR drops; noise floor and packet rate stay near-normal.
                      This condition is NOT covered by the jamming rule (which
                      requires both SNR drop AND noise floor rise), so it must be
                      caught downstream by the Statistical Anomaly Engine.

Usage:
    from src.synthetic_data import generate_normal, generate_jamming, generate_unknown_anomaly

    normal  = generate_normal(n=200, seed=42)
    jamming = generate_jamming(n=50,  seed=42)
    anomaly = generate_unknown_anomaly(n=50, seed=42)

NOTE: This module is a development stub.  Replace with real SDR adapter once the
upstream RF Threat Detection module is available.  The output contract (RFObservation)
must not change.
"""

import random
from datetime import datetime, timezone, timedelta
from typing import Optional

from src.schema import RFObservation


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_timestamp(base: datetime, index: int) -> datetime:
    """Return a UTC timestamp offset by *index* seconds from *base*."""
    return base + timedelta(seconds=index)


def _build_observation(
    obs_id: str,
    timestamp: datetime,
    rssi: float,
    snr: float,
    noise_floor: float,
    packet_rate: float,
) -> RFObservation:
    """Round floats to 4 d.p. for readability, then wrap in RFObservation."""
    return RFObservation(
        observation_id=obs_id,
        timestamp=timestamp,
        rssi=round(rssi, 4),
        snr=round(snr, 4),
        noise_floor=round(noise_floor, 4),
        packet_rate=round(packet_rate, 4),
    )


# ---------------------------------------------------------------------------
# Public generators
# ---------------------------------------------------------------------------

def generate_normal(
    n: int = 200,
    start_id: int = 0,
    seed: Optional[int] = None,
) -> list[RFObservation]:
    """
    Generate *n* RFObservation records representing normal RF conditions.

    Distribution parameters (all Gaussian):
        rssi        ~ N(-60, 3)   dBm   — strong, stable signal
        snr         ~ N(25,  2)   dB    — high SNR
        noise_floor ~ N(-90, 2)   dBm   — low ambient noise
        packet_rate ~ N(100, 5)   pkt/s — steady traffic

    Args:
        n:        Number of observations to generate.
        start_id: Numeric offset for observation IDs (``norm-<start_id>``...).
        seed:     Optional RNG seed for reproducibility.

    Returns:
        List of RFObservation instances.
    """
    rng = random.Random(seed)
    base_ts = datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc)
    observations = []

    for i in range(n):
        obs = _build_observation(
            obs_id=f"norm-{start_id + i:05d}",
            timestamp=_make_timestamp(base_ts, i),
            rssi=rng.gauss(-60.0, 3.0),
            snr=rng.gauss(25.0, 2.0),
            noise_floor=rng.gauss(-90.0, 2.0),
            packet_rate=rng.gauss(100.0, 5.0),
        )
        observations.append(obs)

    return observations


def generate_jamming(
    n: int = 50,
    start_id: int = 1000,
    seed: Optional[int] = None,
) -> list[RFObservation]:
    """
    Generate *n* RFObservation records representing active RF jamming.

    These records are designed to be **rule-matchable**: the Rule-Based Jamming
    Detector fires when it observes BOTH a sharp SNR drop AND a simultaneous rise
    in the noise floor (the two canonical jamming signatures).

    Distribution parameters (all Gaussian):
        rssi        ~ N(-75, 4)   dBm   — signal is degraded
        snr         ~ N(8,   2)   dB    — sharp SNR drop  ← rule trigger #1
        noise_floor ~ N(-70, 3)   dBm   — noise floor rises  ← rule trigger #2
        packet_rate ~ N(40,  8)   pkt/s — disrupted traffic

    Args:
        n:        Number of observations to generate.
        start_id: Numeric offset for observation IDs (``jam-<start_id>``...).
        seed:     Optional RNG seed for reproducibility.

    Returns:
        List of RFObservation instances.
    """
    rng = random.Random(seed)
    base_ts = datetime(2026, 1, 1, 1, 0, 0, tzinfo=timezone.utc)
    observations = []

    for i in range(n):
        obs = _build_observation(
            obs_id=f"jam-{start_id + i:05d}",
            timestamp=_make_timestamp(base_ts, i),
            rssi=rng.gauss(-75.0, 4.0),
            snr=rng.gauss(8.0, 2.0),
            noise_floor=rng.gauss(-70.0, 3.0),
            packet_rate=rng.gauss(40.0, 8.0),
        )
        observations.append(obs)

    return observations


def generate_unknown_anomaly(
    n: int = 50,
    start_id: int = 2000,
    seed: Optional[int] = None,
) -> list[RFObservation]:
    """
    Generate *n* RFObservation records representing an *unknown* RF anomaly.

    These records exhibit only a partial deviation from normal:

    * SNR drops noticeably (statistical outlier vs. the normal baseline).
    * noise_floor, packet_rate, and rssi stay near-normal values.

    **Design intent**: these records must NOT trigger the Rule-Based Jamming
    Detector (which requires *both* SNR drop AND noise floor rise).  They
    represent a condition outside the known-jamming ruleset and must instead
    be caught by the Statistical Anomaly Engine based on SNR deviation alone.

    Distribution parameters (all Gaussian):
        rssi        ~ N(-62, 3)   dBm   — near-normal
        snr         ~ N(12,  2)   dB    — moderate drop (anomalous vs. N(25,2))
        noise_floor ~ N(-89, 2)   dBm   — near-normal  ← rule NOT triggered
        packet_rate ~ N(98,  5)   pkt/s — near-normal  ← rule NOT triggered

    Args:
        n:        Number of observations to generate.
        start_id: Numeric offset for observation IDs (``unk-<start_id>``...).
        seed:     Optional RNG seed for reproducibility.

    Returns:
        List of RFObservation instances.
    """
    rng = random.Random(seed)
    base_ts = datetime(2026, 1, 1, 2, 0, 0, tzinfo=timezone.utc)
    observations = []

    for i in range(n):
        obs = _build_observation(
            obs_id=f"unk-{start_id + i:05d}",
            timestamp=_make_timestamp(base_ts, i),
            rssi=rng.gauss(-62.0, 3.0),
            snr=rng.gauss(12.0, 2.0),
            noise_floor=rng.gauss(-89.0, 2.0),
            packet_rate=rng.gauss(98.0, 5.0),
        )
        observations.append(obs)

    return observations

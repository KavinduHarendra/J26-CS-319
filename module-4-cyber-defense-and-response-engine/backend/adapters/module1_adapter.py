"""Adapter for Module 1 — SDR RF Threat Detection.

This adapter normalizes Module 1's RF context output for consumption
by Module 4's pipeline. It provides validation, defaults, and
mock data generation for when Module 1 is unavailable.

Module 1 integration point is isolated here so that changes to
Module 1's output schema only require updates to this file.
"""

from datetime import datetime
from models.module1 import RFContext


def adapt(raw: dict | None) -> RFContext:
    """Validate and normalize Module 1 output into a typed RFContext.

    If raw is None or empty, returns a safe default (mock mode).
    """
    if not raw:
        return _mock_default()
    return RFContext(**{k: v for k, v in raw.items() if v is not None or k in ("observation_id", "timestamp")})


def _mock_default() -> RFContext:
    """Return safe mock RF context when Module 1 is unavailable."""
    return RFContext(
        observation_id="MOCK-RF-001",
        timestamp=datetime.now().isoformat(),
        rssi=-65.0,
        snr=25.0,
        noise_floor=-90.0,
        packet_rate=98.0,
    )


def summary_dict(rf: RFContext) -> dict:
    """Return a flat audit-friendly dict of the RF context."""
    return {
        "observation_id": rf.observation_id,
        "timestamp": rf.timestamp,
        "rssi": rf.rssi,
        "snr": rf.snr,
        "noise_floor": rf.noise_floor,
        "packet_rate": rf.packet_rate,
        "frequency_mhz": rf.frequency_mhz,
        "bandwidth_mhz": rf.bandwidth_mhz,
        "packet_loss_pct": rf.packet_loss_pct,
        "latency_ms": rf.latency_ms,
        "channel_condition": rf.channel_condition,
        "interference_level": rf.interference_level,
        "distance_m": rf.distance_m,
    }

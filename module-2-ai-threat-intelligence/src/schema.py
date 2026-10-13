"""
schema.py — Input contract for the AI Threat Intelligence Module.

This module defines the canonical data structure exchanged between the upstream
SDR RF Threat Detection module and this AI Threat Intelligence module.

**Stability guarantee**: RFObservation is the fixed input contract between the two
modules. Field names, types, and semantics MUST remain stable; any breaking change
requires a coordinated version bump across all dependent modules.
"""

from dataclasses import dataclass
from datetime import datetime


@dataclass
class RFObservation:
    """
    A single structured RF feature record received from the upstream SDR module.

    This dataclass is the fixed input contract between the SDR RF Threat Detection
    module and this AI Threat Intelligence module. It must stay stable since other
    modules depend on it. Each field represents a physical RF measurement or derived
    statistic computed by the SDR front-end before handoff.

    Attributes:
        observation_id: Unique identifier for this observation (e.g. UUID string).
        timestamp:      UTC datetime at which the observation was captured.
        rssi:           Received Signal Strength Indicator in dBm.
        snr:            Signal-to-Noise Ratio in dB.
        noise_floor:    Ambient noise floor measured by the SDR in dBm.
        packet_rate:    Number of RF packets detected per second.
    """

    observation_id: str
    timestamp: datetime
    rssi: float        # dBm
    snr: float         # dB
    noise_floor: float # dBm
    packet_rate: float # packets/sec

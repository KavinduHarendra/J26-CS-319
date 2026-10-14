"""Module 1 — SDR RF Threat Detection output model.

Module 1 owns RF sensing and signal feature extraction.
This schema defines the data contract flowing from Module 1 into Module 4.
Module 4 does NOT perform any SDR signal processing.
"""

from typing import Optional
from pydantic import BaseModel, Field


class RFContext(BaseModel):
    """Structured RF features produced by Module 1 (W. H. M. S. R. Bandara).

    These are the raw RF indicators used by Module 4 only for:
    - supporting evidence context
    - audit record completeness
    - cross-checking anomalies
    Module 4 does NOT re-classify threats from these values.
    """

    observation_id: str = Field(default="OBS-UNSET", description="Unique observation ID from Module 1")
    timestamp: str = Field(default="", description="ISO 8601 timestamp of the observation")
    rssi: Optional[float] = Field(default=None, description="Received Signal Strength Indicator (dBm)")
    snr: Optional[float] = Field(default=None, description="Signal-to-Noise Ratio (dB)")
    noise_floor: Optional[float] = Field(default=None, description="Noise floor (dBm)")
    packet_rate: Optional[float] = Field(default=None, description="Packet rate (packets/sec)")

    # Optional extended RF context
    frequency_mhz: Optional[float] = Field(default=None, description="Centre frequency (MHz)")
    bandwidth_mhz: Optional[float] = Field(default=None, description="Channel bandwidth (MHz)")
    interference_level: Optional[float] = Field(default=None)
    channel_condition: Optional[str] = Field(default=None)
    distance_m: Optional[float] = Field(default=None)

"""
schema.py — Input contract for the AI Threat Intelligence Module.

This module defines the canonical data structure exchanged between the upstream
SDR RF Threat Detection module and this AI Threat Intelligence module.

**Stability guarantee**: RFObservation is the fixed input contract between the two
modules. Field names, types, and semantics MUST remain stable; any breaking change
requires a coordinated version bump across all dependent modules.
"""

import math
from dataclasses import dataclass
from datetime import datetime
from numbers import Real
from typing import Any, Mapping


class InvalidObservationError(ValueError):
    """Raised when an RF observation violates the module's input contract."""


# These are intentionally broad physical plausibility bounds, not detection
# thresholds. Deployments should configure them for the characteristics of the
# radio in use. Detection logic must not depend on these values.
DEFAULT_PLAUSIBLE_RANGES: dict[str, tuple[float, float]] = {
    "rssi": (-140.0, 0.0),
    "snr": (-40.0, 80.0),
    "noise_floor": (-150.0, -20.0),
    "packet_rate": (0.0, 1_000_000.0),
}
PLAUSIBLE_RANGES: dict[str, tuple[float, float]] = DEFAULT_PLAUSIBLE_RANGES.copy()
NUMERIC_FIELDS = tuple(DEFAULT_PLAUSIBLE_RANGES)


def configure_plausible_ranges(
    ranges: Mapping[str, tuple[Real, Real]],
) -> None:
    """Configure broad input bounds for a particular radio deployment.

    ``ranges`` may override one or more defaults. Bounds must be finite real
    numbers with a lower value no greater than the upper value.
    """
    unknown = set(ranges) - set(DEFAULT_PLAUSIBLE_RANGES)
    if unknown:
        raise ValueError(f"Unknown RF feature range(s): {sorted(unknown)}")

    updated = DEFAULT_PLAUSIBLE_RANGES.copy()
    for field_name, bounds in ranges.items():
        if not isinstance(bounds, (tuple, list)) or len(bounds) != 2:
            raise ValueError(f"Range for '{field_name}' must be a (minimum, maximum) pair")
        lower, upper = bounds
        if (
            isinstance(lower, bool)
            or isinstance(upper, bool)
            or not isinstance(lower, Real)
            or not isinstance(upper, Real)
            or not math.isfinite(float(lower))
            or not math.isfinite(float(upper))
            or lower > upper
        ):
            raise ValueError(f"Invalid range for '{field_name}': {bounds!r}")
        updated[field_name] = (float(lower), float(upper))

    PLAUSIBLE_RANGES.clear()
    PLAUSIBLE_RANGES.update(updated)


def validate_observation(obs: Any) -> None:
    """Validate an observation at any trust boundary.

    This function intentionally validates an existing object as well as the
    dataclass constructor input. That prevents a mutated or otherwise forged
    ``RFObservation`` from bypassing validation before classification.
    """
    try:
        observation_id = obs.observation_id
        timestamp = obs.timestamp
    except AttributeError as exc:
        raise InvalidObservationError(
            "Observation must provide observation_id, timestamp, rssi, snr, "
            "noise_floor, and packet_rate"
        ) from exc

    if not isinstance(observation_id, str):
        raise InvalidObservationError("observation_id must be a string")
    if not observation_id.strip():
        raise InvalidObservationError("observation_id must be non-empty")
    if len(observation_id) > 64:
        raise InvalidObservationError("observation_id must be at most 64 characters")
    if not isinstance(timestamp, datetime):
        raise InvalidObservationError("timestamp must be a datetime")

    for field_name in NUMERIC_FIELDS:
        try:
            value = getattr(obs, field_name)
        except AttributeError as exc:
            raise InvalidObservationError(f"{field_name} is required") from exc

        if isinstance(value, bool) or not isinstance(value, Real):
            raise InvalidObservationError(f"{field_name} must be a real number")
        if not math.isfinite(float(value)):
            raise InvalidObservationError(f"{field_name} must be finite")

        lower, upper = PLAUSIBLE_RANGES[field_name]
        if not lower <= value <= upper:
            raise InvalidObservationError(
                f"{field_name} must be within the configured plausible range "
                f"[{lower}, {upper}]"
            )


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

    def __post_init__(self) -> None:
        """Reject malformed or physically implausible observations immediately."""
        validate_observation(self)

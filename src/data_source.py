"""
data_source.py — Abstract RF Data Source interface and synthetic implementation.

Provides the RFDataSource interface to decouple the AI Threat Intelligence pipeline
from the underlying data origin (synthetic generator, recorded files, real SDR hardware,
or network streams).

Downstream pipeline code must depend only on RFDataSource.fetch_batch(), never touching
raw files or SDR hardware directly.
"""

from abc import ABC, abstractmethod
from typing import Optional

from src.schema import RFObservation
from src.synthetic_data import (
    generate_normal,
    generate_jamming,
    generate_unknown_anomaly,
)


class RFDataSource(ABC):
    """
    Abstract interface for RF observation data sources.

    All data ingest in the AI Threat Intelligence module flows through this
    interface, ensuring that baseline calibration, rule detection, anomaly detection,
    and demo pipelines remain agnostic to whether data arrives from real SDR hardware,
    network stream, CSV replay, or synthetic generation.
    """

    @abstractmethod
    def fetch_batch(self, n: int) -> list[RFObservation]:
        """
        Fetch a batch of n structured RF observations.

        Args:
            n: Number of observations to fetch. Must be non-negative.

        Returns:
            List of RFObservation dataclass instances.
        """
        raise NotImplementedError("Subclasses must implement fetch_batch().")


class SyntheticDataSource(RFDataSource):
    """
    Synthetic RF data source wrapping the synthetic data generators.

    Supported scenarios:
      - 'normal':          Normal RF baseline observations.
      - 'jamming':         Active jamming observations (SNR drop + noise floor rise).
      - 'unknown_anomaly': Unknown anomaly observations (SNR drop without noise floor rise).

    Attributes:
        scenario: The active scenario string ("normal", "jamming", "unknown_anomaly").
        seed: Initial random seed for reproducibility (optional).
    """

    VALID_SCENARIOS = ("normal", "jamming", "unknown_anomaly")

    def __init__(
        self,
        scenario: str,
        seed: Optional[int] = None,
        start_id: Optional[int] = None,
    ):
        """
        Initialize the SyntheticDataSource for a specific scenario.

        Args:
            scenario: Name of the scenario ("normal", "jamming", "unknown_anomaly").
            seed: Optional integer seed for reproducible generation.
            start_id: Optional starting offset for observation IDs. If None, default
                      scenario offsets (0 for normal, 1000 for jamming, 2000 for
                      unknown_anomaly) are used.

        Raises:
            ValueError: If an unknown scenario is provided.
        """
        scenario_clean = scenario.strip().lower()
        if scenario_clean not in self.VALID_SCENARIOS:
            raise ValueError(
                f"Unknown scenario '{scenario}'. Supported scenarios are: {list(self.VALID_SCENARIOS)}"
            )

        self.scenario = scenario_clean
        self.seed = seed
        self._current_seed = seed

        if start_id is None:
            if self.scenario == "normal":
                self._current_id = 0
            elif self.scenario == "jamming":
                self._current_id = 1000
            else:
                self._current_id = 2000
        else:
            self._current_id = start_id

    def fetch_batch(self, n: int) -> list[RFObservation]:
        """
        Fetch n synthetic observations matching the configured scenario.

        Args:
            n: Number of observations to return.

        Returns:
            List of RFObservation instances.

        Raises:
            ValueError: If n is negative.
        """
        if n < 0:
            raise ValueError(f"Batch size n must be non-negative, got {n}")
        if n == 0:
            return []

        if self.scenario == "normal":
            batch = generate_normal(
                n=n,
                start_id=self._current_id,
                seed=self._current_seed,
            )
        elif self.scenario == "jamming":
            batch = generate_jamming(
                n=n,
                start_id=self._current_id,
                seed=self._current_seed,
            )
        elif self.scenario == "unknown_anomaly":
            batch = generate_unknown_anomaly(
                n=n,
                start_id=self._current_id,
                seed=self._current_seed,
            )
        else:
            raise ValueError(f"Unhandled scenario '{self.scenario}'")

        self._current_id += n
        if self._current_seed is not None:
            # Advance seed for subsequent batches to provide continuous independent batches
            self._current_seed += 1

        return batch

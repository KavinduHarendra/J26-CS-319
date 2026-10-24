"""Data-source interfaces for validated Module 1 recordings."""

from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path

from src.real_data import JsonFolderSource, RealSignal


class RFDataSource(ABC):
    """Abstract source of validated real-signal captures."""

    @abstractmethod
    def fetch_batch(self, n: int) -> list[RealSignal]:
        """Return up to ``n`` captures in source order."""
        raise NotImplementedError


class RecordedSignalSource(RFDataSource):
    """Sequential, finite source backed by Module 1 JSON files."""

    def __init__(self, folder: str | Path) -> None:
        self._signals = iter(JsonFolderSource(folder))
        self.exhausted = False

    def fetch_batch(self, n: int) -> list[RealSignal]:
        if isinstance(n, bool) or not isinstance(n, int) or n < 0:
            raise ValueError("batch size must be a non-negative integer")
        batch: list[RealSignal] = []
        for _ in range(n):
            try:
                batch.append(next(self._signals))
            except StopIteration:
                self.exhausted = True
                break
        return batch

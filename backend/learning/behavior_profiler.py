"""Anonymized Behavior Profiler Service."""

from __future__ import annotations

from threading import RLock
from typing import Sequence

from backend.learning.learning_models import BehavioralSignal
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class BehaviorProfiler:
    """Collects anonymized interaction signals without raw audio storage."""

    def __init__(self, max_signals: int = 1000) -> None:
        self._max_signals = max_signals
        self._signals: list[BehavioralSignal] = []
        self._lock = RLock()

    def record_signal(self, signal_type: str, target: str, duration_sec: float = 0.0) -> BehavioralSignal:
        """Record an anonymized interaction signal."""
        with self._lock:
            sig = BehavioralSignal(signal_type=signal_type, target=target, duration_sec=duration_sec)
            self._signals.append(sig)
            if len(self._signals) > self._max_signals:
                self._signals.pop(0)

            logger.info("Recorded behavioral signal: %s -> %s", signal_type, target)
            return sig

    def get_signals(self) -> list[BehavioralSignal]:
        with self._lock:
            return list(self._signals)

    def get_signal_frequencies(self) -> dict[str, int]:
        """Return signal frequency map by target."""
        with self._lock:
            freqs: dict[str, int] = {}
            for s in self._signals:
                freqs[s.target] = freqs.get(s.target, 0) + 1
            return freqs

"""Modular audio preprocessing pipeline and filters for voice recognition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol, Sequence

import numpy as np

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class AudioFilter(Protocol):
    """Protocol for modular audio processing filters."""

    def process(self, audio: Any, sample_rate: int = 16000) -> Any:
        """Process an audio array and return the modified array."""
        ...


@dataclass(frozen=True)
class AdaptiveGainControlFilter:
    """Adaptive Gain Control (AGC) filter normalizes audio RMS to a target level.

    Calculates dynamic gain = target_rms / current_rms and clamps gain between
    min_gain and max_gain to prevent over-amplifying background noise or silence.
    """

    target_rms: float = 0.04
    min_gain: float = 1.0
    max_gain: float = 40.0
    enabled: bool = True

    def process(self, audio: Any, sample_rate: int = 16000) -> Any:
        """Apply AGC scaling to floating-point audio array."""
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if not self.enabled or samples.size == 0:
            return samples

        current_rms = float(np.sqrt(np.mean(np.square(samples))))
        if current_rms < 1e-4:
            return samples

        gain = self.target_rms / current_rms
        gain = min(max(gain, self.min_gain), self.max_gain)

        processed = samples * gain
        final_rms = float(np.sqrt(np.mean(np.square(processed))))

        logger.info("AGC Debug:")
        logger.info("- Original RMS : %.6f", current_rms)
        logger.info("- Applied Gain : %.2fx", gain)
        logger.info("- Final RMS    : %.6f", final_rms)

        return processed


@dataclass(frozen=True)
class PeakLimiterFilter:
    """Peak limiter filter clamps sample values to prevent digital clipping."""

    threshold: float = 1.0
    enabled: bool = True

    def process(self, audio: Any, sample_rate: int = 16000) -> Any:
        """Safely clamp samples to [-threshold, +threshold]."""
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if not self.enabled or samples.size == 0:
            return samples

        return np.clip(samples, -self.threshold, self.threshold)


class AudioPreprocessor:
    """Composite preprocessor executing a sequential pipeline of AudioFilters."""

    def __init__(
        self,
        filters: Sequence[AudioFilter] | None = None,
        enabled: bool = True,
    ) -> None:
        if filters is not None:
            self._filters = list(filters)
        else:
            self._filters = [
                AdaptiveGainControlFilter(),
                PeakLimiterFilter(),
            ]
        self._enabled = enabled

    @property
    def enabled(self) -> bool:
        """Return whether the preprocessor pipeline is active."""
        return self._enabled

    @property
    def filters(self) -> list[AudioFilter]:
        """Return the registered filter sequence."""
        return list(self._filters)

    def process(self, audio: Any, sample_rate: int = 16000) -> Any:
        """Execute all registered audio filters in sequence."""
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if not self._enabled or samples.size == 0:
            return samples

        current = samples
        for f in self._filters:
            current = f.process(current, sample_rate)

        return current

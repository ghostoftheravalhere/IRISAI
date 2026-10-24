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
    Incorporates peak awareness to prevent headroom violations and clipping distortion.
    """

    target_rms: float = 0.04
    min_gain: float = 0.5
    max_gain: float = 8.0
    peak_limit: float = 0.95
    silence_threshold: float = 1e-4
    enabled: bool = True

    def process(self, audio: Any, sample_rate: int = 16000) -> Any:
        """Apply peak-aware AGC scaling to floating-point audio array."""
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if not self.enabled or samples.size == 0:
            return samples

        if not np.all(np.isfinite(samples)):
            samples = np.nan_to_num(
                samples,
                nan=0.0,
                posinf=self.peak_limit,
                neginf=-self.peak_limit,
            ).astype(np.float32)

        current_rms = float(np.sqrt(np.mean(np.square(samples))))
        current_peak = float(np.max(np.abs(samples)))
        if current_rms < self.silence_threshold or current_peak < self.silence_threshold:
            return np.ascontiguousarray(samples, dtype=np.float32)

        gain = self.target_rms / max(current_rms, 1e-12)
        gain = min(max(gain, self.min_gain), self.max_gain)

        # Peak awareness: prevent gain amplification from pushing peak beyond safe headroom
        if current_peak > 1e-6 and (gain * current_peak) > self.peak_limit:
            gain = self.peak_limit / current_peak

        processed = samples * gain

        # Secondary peak safety limit
        out_peak = float(np.max(np.abs(processed)))
        if out_peak > self.peak_limit and out_peak > 1e-6:
            processed = processed * (self.peak_limit / out_peak)

        final_rms = float(np.sqrt(np.mean(np.square(processed))))

        logger.info("AGC Debug:")
        logger.info("- Original RMS : %.6f (Peak: %.6f)", current_rms, current_peak)
        logger.info("- Applied Gain : %.2fx", gain)
        logger.info("- Final RMS    : %.6f (Peak: %.6f)", final_rms, float(np.max(np.abs(processed))))

        return np.ascontiguousarray(processed, dtype=np.float32)


@dataclass(frozen=True)
class PeakLimiterFilter:
    """Peak limiter filter clamps sample values to prevent digital clipping."""

    threshold: float = 0.95
    enabled: bool = True

    def process(self, audio: Any, sample_rate: int = 16000) -> Any:
        """Safely clamp samples to [-threshold, +threshold]."""
        samples = np.asarray(audio, dtype=np.float32).reshape(-1)
        if not self.enabled or samples.size == 0:
            return samples

        if not np.all(np.isfinite(samples)):
            samples = np.nan_to_num(
                samples,
                nan=0.0,
                posinf=self.threshold,
                neginf=-self.threshold,
            ).astype(np.float32)

        clipped = np.clip(samples, -self.threshold, self.threshold)
        return np.ascontiguousarray(clipped, dtype=np.float32)


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

        if not np.all(np.isfinite(samples)):
            samples = np.nan_to_num(samples, nan=0.0, posinf=1.0, neginf=-1.0).astype(np.float32)

        current = samples
        for f in self._filters:
            current = f.process(current, sample_rate)

        return np.ascontiguousarray(current, dtype=np.float32)

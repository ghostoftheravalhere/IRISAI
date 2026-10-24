"""Adaptive 1-Euro filter for low-latency signal smoothing and jitter reduction.

Reference:
    Casiez, G., Roussel, N., and Vogel, D. (2012).
    1 € filter: a simple speed-based low-pass filter for noisy input in HCI.
    Proceedings of the SIGCHI Conference on Human Factors in Computing Systems (CHI '12).
"""

from __future__ import annotations

import math
from time import perf_counter


class LowPassFilter:
    """First-order low-pass exponential smoothing filter."""

    def __init__(self, alpha: float = 0.5) -> None:
        self._alpha = float(alpha)
        self._y: float | None = None
        self._s: float | None = None

    def filter(self, value: float, alpha: float | None = None) -> float:
        a = self._alpha if alpha is None else float(alpha)
        if self._y is None:
            s = float(value)
        else:
            s = a * float(value) + (1.0 - a) * self._s
        self._y = float(value)
        self._s = s
        return s

    def last_value(self) -> float | None:
        return self._y

    def reset(self) -> None:
        self._y = None
        self._s = None


class OneEuroFilter:
    """1-Euro adaptive low-pass filter for 1D continuous noisy signals."""

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.008,
        d_cutoff: float = 1.0,
    ) -> None:
        """Initialize the 1-Euro filter.

        Args:
            min_cutoff: Minimum cutoff frequency in Hz (for low-speed jitter elimination).
            beta: Speed coefficient adjusting cutoff frequency with velocity (reduces lag during motion).
            d_cutoff: Cutoff frequency for derivative smoothing in Hz.
        """
        self.min_cutoff = float(min_cutoff)
        self.beta = float(beta)
        self.d_cutoff = float(d_cutoff)

        self._x_filter = LowPassFilter()
        self._dx_filter = LowPassFilter()
        self._last_time: float | None = None

    @staticmethod
    def _compute_alpha(rate: float, cutoff: float) -> float:
        """Compute exponential smoothing alpha factor for a given sampling rate and cutoff."""
        tau = 1.0 / (2.0 * math.pi * cutoff)
        te = 1.0 / rate
        return 1.0 / (1.0 + tau / te)

    def filter(self, x: float, timestamp: float | None = None) -> float:
        """Filter a new measurement with optional monotonic timestamp in seconds."""
        t = timestamp if timestamp is not None else perf_counter()

        if self._last_time is None or t <= self._last_time:
            rate = 30.0  # Safe default frequency before 2nd sample
        else:
            dt = t - self._last_time
            if dt < 0.002:
                rate = 30.0  # Treat microsecond loops as nominal 30 FPS camera intervals
            else:
                rate = 1.0 / dt

        self._last_time = t

        prev_x = self._x_filter.last_value()
        if prev_x is None:
            # First measurement
            dx = 0.0
        else:
            dx = (x - prev_x) * rate

        # 1. Smooth velocity derivative
        alpha_d = self._compute_alpha(rate, self.d_cutoff)
        edx = self._dx_filter.filter(dx, alpha=alpha_d)

        # 2. Compute dynamic cutoff frequency: min_cutoff + beta * |velocity|
        vel_scale = 1000.0 if abs(x) <= 1.5 else 1.0
        cutoff = self.min_cutoff + self.beta * abs(edx) * vel_scale

        # 3. Smooth signal with dynamic cutoff
        alpha = self._compute_alpha(rate, cutoff)
        return self._x_filter.filter(x, alpha=alpha)

    def reset(self) -> None:
        """Reset internal filter state."""
        self._x_filter.reset()
        self._dx_filter.reset()
        self._last_time = None


class OneEuroFilter2D:
    """Convenience wrapper combining two 1-Euro filters for 2D (x, y) coordinates."""

    def __init__(
        self,
        min_cutoff: float = 1.0,
        beta: float = 0.008,
        d_cutoff: float = 1.0,
    ) -> None:
        self.filter_x = OneEuroFilter(min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)
        self.filter_y = OneEuroFilter(min_cutoff=min_cutoff, beta=beta, d_cutoff=d_cutoff)

    def filter(self, x: float, y: float, timestamp: float | None = None) -> tuple[float, float]:
        """Filter 2D coordinates simultaneously."""
        t = timestamp if timestamp is not None else perf_counter()
        return (
            self.filter_x.filter(x, timestamp=t),
            self.filter_y.filter(y, timestamp=t),
        )

    def reset(self) -> None:
        """Reset both filters."""
        self.filter_x.reset()
        self.filter_y.reset()

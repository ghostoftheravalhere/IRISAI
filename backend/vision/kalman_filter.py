"""2D Kalman Filter & Adaptive Anti-Jitter Smoothing Pipeline for Gaze Coordinates."""

from __future__ import annotations

import math
import time
from typing import Any

import numpy as np

from backend.utils.logger import get_logger

logger = get_logger(__name__)


class GazeKalmanFilter:
    """Adaptive 2D Kalman Filter tracking 4 state variables: [x, y, v_x, v_y]^T.

    Features:
    - Constant velocity kinematic transition model over dynamic timestep dt.
    - Adaptive measurement noise covariance (R): Higher smoothing during fixations/idle gaze,
      lower smoothing (instant responsiveness) during rapid saccades.
    - Joseph-form covariance updates for guaranteed positive semi-definiteness and numerical stability.
    - Dynamic runtime parameter tuning for sensitivity and noise bounds.
    """

    def __init__(
        self,
        process_noise_pos: float = 1e-3,
        process_noise_vel: float = 1e-2,
        measurement_noise_min: float = 1e-4,
        measurement_noise_max: float = 5e-2,
        velocity_threshold: float = 0.5,
        default_dt: float = 1.0 / 30.0,
    ) -> None:
        """Initialize the 2D Kalman filter with kinematic parameters.

        Args:
            process_noise_pos: Base process noise for position state.
            process_noise_vel: Base process noise for velocity state.
            measurement_noise_min: Measurement noise during high-velocity saccades (low smoothing).
            measurement_noise_max: Measurement noise during fixations / idle gaze (high smoothing).
            velocity_threshold: Velocity reference scaling saccade transition.
            default_dt: Default time step in seconds if not provided in update().
        """
        self._q_pos = float(process_noise_pos)
        self._q_vel = float(process_noise_vel)
        self._r_min = float(measurement_noise_min)
        self._r_max = float(measurement_noise_max)
        self._v_threshold = float(velocity_threshold)
        self._default_dt = float(default_dt)

        # State vector: [x, y, vx, vy]^T
        self._state = np.zeros(4, dtype=np.float64)

        # State covariance matrix: P (4x4)
        self._p = np.eye(4, dtype=np.float64) * 1.0

        # Measurement matrix: H (2x4)
        self._h = np.array(
            [
                [1.0, 0.0, 0.0, 0.0],
                [0.0, 1.0, 0.0, 0.0],
            ],
            dtype=np.float64,
        )

        self._last_timestamp: float | None = None
        self._is_initialized: bool = False

    @property
    def is_initialized(self) -> bool:
        """Return whether filter has received initial measurement."""
        return self._is_initialized

    @property
    def state(self) -> tuple[float, float, float, float]:
        """Return current state tuple (x, y, vx, vy)."""
        return (
            float(self._state[0]),
            float(self._state[1]),
            float(self._state[2]),
            float(self._state[3]),
        )

    @property
    def position(self) -> tuple[float, float]:
        """Return current filtered position (x, y)."""
        return float(self._state[0]), float(self._state[1])

    @property
    def velocity(self) -> tuple[float, float]:
        """Return current estimated velocity (vx, vy)."""
        return float(self._state[2]), float(self._state[3])

    def reset(self) -> None:
        """Reinitialize the state matrix upon tracker reset or lost tracking."""
        self._state = np.zeros(4, dtype=np.float64)
        self._p = np.eye(4, dtype=np.float64) * 1.0
        self._last_timestamp = None
        self._is_initialized = False
        logger.debug("GazeKalmanFilter reset.")

    def set_parameters(
        self,
        process_noise_pos: float | None = None,
        process_noise_vel: float | None = None,
        measurement_noise_min: float | None = None,
        measurement_noise_max: float | None = None,
        velocity_threshold: float | None = None,
    ) -> None:
        """Dynamically tune filter parameters at runtime."""
        if process_noise_pos is not None:
            self._q_pos = max(1e-7, float(process_noise_pos))
        if process_noise_vel is not None:
            self._q_vel = max(1e-7, float(process_noise_vel))
        if measurement_noise_min is not None:
            self._r_min = max(1e-7, float(measurement_noise_min))
        if measurement_noise_max is not None:
            self._r_max = max(self._r_min, float(measurement_noise_max))
        if velocity_threshold is not None:
            self._v_threshold = max(1e-4, float(velocity_threshold))

    def _compute_f_matrix(self, dt: float) -> np.ndarray:
        """Compute state transition matrix F(dt) with ocular damping."""
        decay = max(0.0, 1.0 - 5.0 * dt)
        return np.array(
            [
                [1.0, 0.0, dt, 0.0],
                [0.0, 1.0, 0.0, dt],
                [0.0, 0.0, decay, 0.0],
                [0.0, 0.0, 0.0, decay],
            ],
            dtype=np.float64,
        )

    def _compute_q_matrix(self, dt: float) -> np.ndarray:
        """Compute process noise covariance matrix Q(dt)."""
        dt2 = dt * dt
        dt3 = dt2 * dt
        dt4 = dt3 * dt

        q = np.array(
            [
                [0.25 * dt4 * self._q_pos, 0.0, 0.5 * dt3 * self._q_pos, 0.0],
                [0.0, 0.25 * dt4 * self._q_pos, 0.0, 0.5 * dt3 * self._q_pos],
                [0.5 * dt3 * self._q_vel, 0.0, dt2 * self._q_vel, 0.0],
                [0.0, 0.5 * dt3 * self._q_vel, 0.0, dt2 * self._q_vel],
            ],
            dtype=np.float64,
        )
        return q

    def _compute_adaptive_r(self, velocity_mag: float) -> np.ndarray:
        """Compute adaptive measurement noise covariance R based on movement speed.

        During fixations (v near 0): R is high -> high measurement noise -> heavy smoothing (no jitter).
        During saccades (v large): R drops to R_min -> low measurement noise -> high responsiveness.
        """
        # Smooth sigmoidal / rational attenuation
        factor = 1.0 / (1.0 + (velocity_mag / self._v_threshold) ** 2)
        r_val = self._r_min + (self._r_max - self._r_min) * factor

        return np.array(
            [
                [r_val, 0.0],
                [0.0, r_val],
            ],
            dtype=np.float64,
        )

    def update(
        self,
        measured_x: float,
        measured_y: float,
        dt: float | None = None,
    ) -> tuple[float, float]:
        """Update internal Kalman state with new measurement and return smoothed (x, y).

        Args:
            measured_x: Raw input x coordinate.
            measured_y: Raw input y coordinate.
            dt: Optional elapsed time since last frame in seconds.

        Returns:
            Tuple of (smooth_x, smooth_y).
        """
        now = time.perf_counter()

        # Sanity validation
        if not math.isfinite(measured_x) or not math.isfinite(measured_y):
            if self._is_initialized:
                return self.position
            return (0.0, 0.0)

        # 1. Cold start initialization on first valid frame
        if not self._is_initialized:
            self._state = np.array([measured_x, measured_y, 0.0, 0.0], dtype=np.float64)
            self._p = np.eye(4, dtype=np.float64) * 0.01
            self._last_timestamp = now
            self._is_initialized = True
            return (float(measured_x), float(measured_y))

        # 2. Determine timestep dt
        if dt is None or dt <= 0.0:
            if self._last_timestamp is not None:
                dt = max(1e-4, min(now - self._last_timestamp, 0.5))
            else:
                dt = self._default_dt
        else:
            dt = max(1e-4, min(float(dt), 0.5))
        self._last_timestamp = now

        # 3. Predict step
        f = self._compute_f_matrix(dt)
        q = self._compute_q_matrix(dt)

        x_pred = f @ self._state
        p_pred = f @ self._p @ f.T + q

        # 4. Adaptive Measurement Noise Calculation
        # Compute predicted speed magnitude: sqrt(vx^2 + vy^2)
        vx, vy = x_pred[2], x_pred[3]
        speed = math.hypot(vx, vy)

        # Compute innovation displacement as additional saccade detector
        meas = np.array([measured_x, measured_y], dtype=np.float64)
        innov_disp = math.hypot(meas[0] - x_pred[0], meas[1] - x_pred[1])
        effective_velocity = max(speed, innov_disp / dt)

        r = self._compute_adaptive_r(effective_velocity)

        # 5. Update step (Joseph form for numerical stability)
        y = meas - (self._h @ x_pred)  # Innovation
        s = (self._h @ p_pred @ self._h.T) + r  # Innovation covariance (2x2)

        # Invert 2x2 matrix analytically for speed and accuracy
        det = s[0, 0] * s[1, 1] - s[0, 1] * s[1, 0]
        if abs(det) < 1e-12:
            s_inv = np.eye(2, dtype=np.float64) / 1e-4
        else:
            inv_det = 1.0 / det
            s_inv = np.array(
                [
                    [s[1, 1] * inv_det, -s[0, 1] * inv_det],
                    [-s[1, 0] * inv_det, s[0, 0] * inv_det],
                ],
                dtype=np.float64,
            )

        k = p_pred @ self._h.T @ s_inv  # Kalman Gain (4x2)

        self._state = x_pred + (k @ y)

        # Joseph form: P = (I - KH) P (I - KH)^T + K R K^T
        i_kh = np.eye(4, dtype=np.float64) - (k @ self._h)
        self._p = (i_kh @ p_pred @ i_kh.T) + (k @ r @ k.T)

        return (float(self._state[0]), float(self._state[1]))

    def get_diagnostics(self) -> dict[str, Any]:
        """Return diagnostic metrics of filter state."""
        return {
            "initialized": self._is_initialized,
            "x": float(self._state[0]),
            "y": float(self._state[1]),
            "vx": float(self._state[2]),
            "vy": float(self._state[3]),
            "speed": float(math.hypot(self._state[2], self._state[3])),
            "trace_p": float(np.trace(self._p)),
            "q_pos": self._q_pos,
            "q_vel": self._q_vel,
            "r_min": self._r_min,
            "r_max": self._r_max,
        }

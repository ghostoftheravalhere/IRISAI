"""Deterministic Kinematic Physics Pipeline for Gaze-Driven OS Cursor Control.

Pure Constant Critically Damped System (Zero Deadbands, Zero Stiction, Zero Chatter).
Constant Critically Damped Harmonic Oscillator:
- Fixed natural frequency: omega = 18.0 (constant).
- Critical damping: c = 2.0 * omega = 36.0 (guaranteed ZERO oscillation, ZERO chatter).
- acc = omega^2 * (target - pos) - 2 * omega * vel
"""

from __future__ import annotations

from dataclasses import dataclass
import math
import time
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Constants (retained for backward compatibility and config references)
KINEMATIC_STIFFNESS: float = 160.0
KINEMATIC_DAMPING_RATIO: float = 1.0
KINEMATIC_DAMPING: float = 36.0
KINEMATIC_MASS: float = 1.0
KINEMATIC_TREMOR_REDUCTION_PX: float = 0.0
KINEMATIC_DEADBAND_RADIUS: float = 0.0
KINEMATIC_BREAKOUT_RADIUS: float = 0.0
KINEMATIC_ANCHOR_VELOCITY_THRESHOLD: float = 0.0
KINEMATIC_ACCELERATION_GAIN: float = 1.0
KINEMATIC_MAX_VELOCITY_PX_S: float = 12000.0
KINEMATIC_MAX_STEP_PX: float = 800.0
KINEMATIC_DEFAULT_DT: float = 1.0 / 60.0

DEFAULT_OMEGA: float = 18.0
DEFAULT_DAMPING: float = 36.0
MIN_OMEGA: float = 18.0
MAX_OMEGA: float = 18.0
SPEED_THRESHOLD: float = 600.0


@dataclass(frozen=True)
class KinematicPhysicsConfig:
    """Configurable parameters for the kinematic physics pipeline."""

    min_omega: float = MIN_OMEGA
    max_omega: float = MAX_OMEGA
    speed_threshold: float = SPEED_THRESHOLD
    max_velocity_px_s: float = KINEMATIC_MAX_VELOCITY_PX_S
    max_step_px: float = KINEMATIC_MAX_STEP_PX
    default_dt: float = KINEMATIC_DEFAULT_DT
    # Backward compatibility defaults:
    stiffness: float = KINEMATIC_STIFFNESS
    damping_ratio: float = KINEMATIC_DAMPING_RATIO
    damping: float = KINEMATIC_DAMPING
    mass: float = KINEMATIC_MASS
    tremor_reduction_px: float = KINEMATIC_TREMOR_REDUCTION_PX
    deadband_radius: float = KINEMATIC_DEADBAND_RADIUS
    breakout_radius: float = KINEMATIC_BREAKOUT_RADIUS
    anchor_velocity_threshold: float = KINEMATIC_ANCHOR_VELOCITY_THRESHOLD
    acceleration_gain: float = KINEMATIC_ACCELERATION_GAIN


@dataclass(frozen=True)
class KinematicState:
    """Snapshot of 2D kinematic state variables."""

    x: float
    y: float
    vx: float
    vy: float
    ax: float
    ay: float
    speed: float
    is_initialized: bool
    is_anchored: bool = False
    anchor_x: float | None = None
    anchor_y: float | None = None
    omega: float = MIN_OMEGA


class KinematicPhysicsPipeline:
    """Continuous-time deterministic 2D kinematic physics simulation engine.

    Models cursor motion as a continuous velocity-adaptive second-order critically
    damped mass-spring-damper system without deadbands or breakout thresholds.
    """

    def __init__(self, config: KinematicPhysicsConfig | None = None) -> None:
        self._config = config or KinematicPhysicsConfig()
        self._validate_config(self._config)

        # State variables
        self._x: float = 0.0
        self._y: float = 0.0
        self._vx: float = 0.0
        self._vy: float = 0.0
        self._ax: float = 0.0
        self._ay: float = 0.0
        self._omega: float = 18.0


        self._last_timestamp: float | None = None
        self._is_initialized: bool = False
        self._is_frozen: bool = False

    # Property aliases for flexible access
    @property
    def x(self) -> float:
        return self._x

    @x.setter
    def x(self, val: float) -> None:
        self._x = float(val)

    @property
    def y(self) -> float:
        return self._y

    @y.setter
    def y(self, val: float) -> None:
        self._y = float(val)

    @property
    def vx(self) -> float:
        return self._vx

    @vx.setter
    def vx(self, val: float) -> None:
        self._vx = float(val)

    @property
    def vy(self) -> float:
        return self._vy

    @vy.setter
    def vy(self, val: float) -> None:
        self._vy = float(val)

    @property
    def ax(self) -> float:
        return self._ax

    @ax.setter
    def ax(self, val: float) -> None:
        self._ax = float(val)

    @property
    def ay(self) -> float:
        return self._ay

    @ay.setter
    def ay(self, val: float) -> None:
        self._ay = float(val)

    @property
    def is_initialized(self) -> bool:
        """Return whether physics pipeline has received its initial state."""
        return self._is_initialized

    @property
    def is_frozen(self) -> bool:
        """Return whether physics simulation is temporarily frozen (e.g. EAR gate)."""
        return self._is_frozen

    @property
    def is_anchored(self) -> bool:
        """Return False (deadbands and resting anchors removed)."""
        return False

    @property
    def anchor_position(self) -> tuple[float, float] | None:
        """Return None (deadbands and resting anchors removed)."""
        return None

    @property
    def deadband_radius(self) -> float:
        """Return 0.0 (deadbands removed)."""
        return 0.0

    @deadband_radius.setter
    def deadband_radius(self, val: float) -> None:
        pass

    @property
    def breakout_radius(self) -> float:
        """Return 0.0 (breakout thresholds removed)."""
        return 0.0

    @breakout_radius.setter
    def breakout_radius(self, val: float) -> None:
        pass

    @property
    def position(self) -> tuple[float, float]:
        """Return current continuous position (x, y)."""
        return (self._x, self._y)

    @property
    def velocity(self) -> tuple[float, float]:
        """Return current estimated velocity (vx, vy)."""
        return (self._vx, self._vy)

    @property
    def speed(self) -> float:
        """Return current cursor speed magnitude (px/s)."""
        return math.hypot(self._vx, self._vy)

    @property
    def omega(self) -> float:
        """Return current dynamic natural frequency (rad/s)."""
        return self._omega

    @property
    def damping_ratio(self) -> float:
        """Always critically damped (1.0)."""
        return 1.0

    @property
    def damping(self) -> float:
        """Current physical damping coefficient c = 2 * omega."""
        return 2.0 * self._omega

    @property
    def config(self) -> KinematicPhysicsConfig:
        """Return current physics configuration."""
        return self._config

    def reset(self, x: float | None = None, y: float | None = None) -> None:
        """Reset physical state, optionally seeding a new position."""
        if x is not None and y is not None and math.isfinite(x) and math.isfinite(y):
            self._x = float(x)
            self._y = float(y)
            self._is_initialized = True
        else:
            self._x = 0.0
            self._y = 0.0
            self._is_initialized = False

        self._vx = 0.0
        self._vy = 0.0
        self._ax = 0.0
        self._ay = 0.0
        self._omega = 18.0
        self._last_timestamp = None
        self._is_frozen = False
        logger.debug("KinematicPhysicsPipeline reset to (%.1f, %.1f)", self._x, self._y)

    def freeze(self, x: float | None = None, y: float | None = None) -> None:
        """Freeze cursor kinematics during eyelid closure, zeroing momentum and holding coordinates."""
        self._is_frozen = True
        self._vx = 0.0
        self._vy = 0.0
        self._ax = 0.0
        self._ay = 0.0
        if x is not None and math.isfinite(x):
            self._x = float(x)
        if y is not None and math.isfinite(y):
            self._y = float(y)

    def unfreeze(self) -> None:
        """Resume active physical simulation."""
        self._is_frozen = False

    def soft_unfreeze(self, target_x: float, target_y: float) -> None:
        """Resets internal velocity to zero and immediately anchors position to target to eliminate spring snap."""
        self._is_frozen = False
        if math.isfinite(target_x) and math.isfinite(target_y):
            self._x = float(target_x)
            self._y = float(target_y)
        self._vx = 0.0
        self._vy = 0.0
        self._ax = 0.0
        self._ay = 0.0

    def update(
        self,
        target_x: float,
        target_y: float,
        dt: float | None = None,
        timestamp: float | None = None,
        **kwargs: Any,
    ) -> tuple[float, float]:
        """Advance continuous velocity-adaptive kinematic simulation toward (target_x, target_y).

        Args:
            target_x: Desired screen X coordinate.
            target_y: Desired screen Y coordinate.
            dt: Optional elapsed time in seconds.
            timestamp: Optional monotonic timestamp for high-resolution timing.

        Returns:
            Tuple of (new_x, new_y) after continuous kinematic integration.
        """
        now = timestamp if timestamp is not None else time.perf_counter()

        # Sanitize input coordinates
        if not math.isfinite(target_x) or not math.isfinite(target_y):
            if self._is_initialized:
                return (self._x, self._y)
            return (0.0, 0.0)

        # Cold start initialization
        if not self._is_initialized:
            self._x = float(target_x)
            self._y = float(target_y)
            self._vx = 0.0
            self._vy = 0.0
            self._ax = 0.0
            self._ay = 0.0
            self._omega = 18.0
            self._last_timestamp = now
            self._is_initialized = True
            return (self._x, self._y)

        # If frozen by pre-blink gate, retain current position and zero velocity
        if self._is_frozen:
            self._vx = 0.0
            self._vy = 0.0
            self._ax = 0.0
            self._ay = 0.0
            self._last_timestamp = now
            return (self._x, self._y)

        # 1. Compute time delta
        if dt is None or dt <= 0.0:
            if self._last_timestamp is not None:
                raw_dt = now - self._last_timestamp
                step_dt = self._config.default_dt if raw_dt < 0.002 else min(raw_dt, 0.05)
            else:
                step_dt = max(1e-4, min(self._config.default_dt, 0.05))
        else:
            step_dt = max(1e-4, min(float(dt), 0.05))

        self._last_timestamp = now

        # 2. Constant critically damped harmonic oscillator:
        # acc = omega^2 * (target - pos) - 2 * omega * vel
        # Fixed natural frequency: omega = 18.0, critical damping: c = 36.0 (zero oscillation, zero chatter)
        omega = 18.0
        c = 36.0
        self._omega = omega
        k = 18.0 * 18.0  # 324.0

        max_sub_dt = 0.002
        steps = max(1, math.ceil(step_dt / max_sub_dt))
        sub_dt = step_dt / steps

        for _ in range(steps):
            acc_x = k * (target_x - self._x) - c * self._vx
            acc_y = k * (target_y - self._y) - c * self._vy
            self._vx += acc_x * sub_dt
            self._vy += acc_y * sub_dt
            self._x += self._vx * sub_dt
            self._y += self._vy * sub_dt

        self._ax = k * (target_x - self._x) - c * self._vx
        self._ay = k * (target_y - self._y) - c * self._vy

        return (self._x, self._y)


    def get_state(self) -> KinematicState:
        """Return complete snapshot of current kinematic state."""
        return KinematicState(
            x=self._x,
            y=self._y,
            vx=self._vx,
            vy=self._vy,
            ax=self._ax,
            ay=self._ay,
            speed=math.hypot(self._vx, self._vy),
            is_initialized=self._is_initialized,
            is_anchored=False,
            anchor_x=None,
            anchor_y=None,
            omega=self._omega,
        )

    def set_parameters(
        self,
        min_omega: float | None = None,
        max_omega: float | None = None,
        speed_threshold: float | None = None,
        max_velocity_px_s: float | None = None,
        max_step_px: float | None = None,
        stiffness: float | None = None,
        damping_ratio: float | None = None,
        damping: float | None = None,
        mass: float | None = None,
        tremor_reduction_px: float | None = None,
        deadband_radius: float | None = None,
        breakout_radius: float | None = None,
        anchor_velocity_threshold: float | None = None,
        acceleration_gain: float | None = None,
        **kwargs: Any,
    ) -> None:
        """Dynamically tune continuous physics simulation parameters at runtime."""
        current = self._config
        new_config = KinematicPhysicsConfig(
            min_omega=float(min_omega) if min_omega is not None else current.min_omega,
            max_omega=float(max_omega) if max_omega is not None else current.max_omega,
            speed_threshold=float(speed_threshold) if speed_threshold is not None else current.speed_threshold,
            max_velocity_px_s=float(max_velocity_px_s) if max_velocity_px_s is not None else current.max_velocity_px_s,
            max_step_px=float(max_step_px) if max_step_px is not None else current.max_step_px,
            default_dt=current.default_dt,
            stiffness=float(stiffness) if stiffness is not None else current.stiffness,
            damping_ratio=float(damping_ratio) if damping_ratio is not None else current.damping_ratio,
            damping=float(damping) if damping is not None else current.damping,
            mass=float(mass) if mass is not None else current.mass,
            tremor_reduction_px=float(tremor_reduction_px) if tremor_reduction_px is not None else current.tremor_reduction_px,
            deadband_radius=float(deadband_radius) if deadband_radius is not None else current.deadband_radius,
            breakout_radius=float(breakout_radius) if breakout_radius is not None else current.breakout_radius,
            anchor_velocity_threshold=float(anchor_velocity_threshold) if anchor_velocity_threshold is not None else current.anchor_velocity_threshold,
            acceleration_gain=float(acceleration_gain) if acceleration_gain is not None else current.acceleration_gain,
        )
        self._validate_config(new_config)
        self._config = new_config

    @staticmethod
    def _validate_config(config: KinematicPhysicsConfig) -> None:
        """Validate kinematic configuration bounds."""
        if config.min_omega <= 0.0:
            raise ValueError("min_omega must be positive.")
        if config.max_omega < config.min_omega:
            raise ValueError("max_omega must be >= min_omega.")
        if config.speed_threshold <= 0.0:
            raise ValueError("speed_threshold must be positive.")
        if config.max_velocity_px_s <= 0.0:
            raise ValueError("max_velocity_px_s must be positive.")
        if config.default_dt <= 0.0:
            raise ValueError("default_dt must be positive.")

"""Eye Calibration Posture & Head-Pose Guidance Engine."""

from __future__ import annotations

from dataclasses import dataclass
from math import hypot, isfinite
from threading import RLock
import time

from backend.eye_tracking.face_mesh_service import EyeData, NormalizedLandmark
from backend.utils.helpers import compute_eye_center
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class CalibrationGuidanceState:
    """Real-time posture and distance guidance state for 9-point eye calibration."""

    status: str
    message: str
    face_distance: str
    is_stable: bool
    confidence: float
    inter_eye_distance: float
    midpoint_x: float
    midpoint_y: float
    depth_delta: float


class CalibrationGuidanceService:
    """Evaluates facial landmarks to provide real-time posture guidance during calibration."""

    def __init__(
        self,
        min_inter_eye_dist: float = 0.16,
        max_inter_eye_dist: float = 0.38,
        min_x: float = 0.35,
        max_x: float = 0.65,
        min_y: float = 0.30,
        max_y: float = 0.70,
        max_depth_delta: float = 0.08,
        stabilization_window_seconds: float = 0.5,
    ) -> None:
        self._min_dist = min_inter_eye_dist
        self._max_dist = max_inter_eye_dist
        self._min_x = min_x
        self._max_x = max_x
        self._min_y = min_y
        self._max_y = max_y
        self._max_depth_delta = max_depth_delta
        self._stabilization_window = stabilization_window_seconds

        self._stable_since: float | None = None
        self._last_eye_center: tuple[float, float] | None = None
        self._lock = RLock()

    def evaluate_posture(self, eye_data: EyeData | None) -> CalibrationGuidanceState:
        """Evaluate landmark coordinates and return posture guidance state."""
        with self._lock:
            if eye_data is None or not eye_data.left_eye or not eye_data.right_eye:
                self._stable_since = None
                return CalibrationGuidanceState(
                    status="tracking_lost",
                    message="Face not detected — look at camera",
                    face_distance="unknown",
                    is_stable=False,
                    confidence=0.0,
                    inter_eye_distance=0.0,
                    midpoint_x=0.5,
                    midpoint_y=0.5,
                    depth_delta=0.0,
                )

            # Compute Eye Centers & Midpoints
            left_center = self._compute_landmarks_center(eye_data.left_eye)
            right_center = self._compute_landmarks_center(eye_data.right_eye)

            if left_center is None or right_center is None:
                self._stable_since = None
                return CalibrationGuidanceState(
                    status="tracking_lost",
                    message="Invalid landmark coordinates",
                    face_distance="unknown",
                    is_stable=False,
                    confidence=0.0,
                    inter_eye_distance=0.0,
                    midpoint_x=0.5,
                    midpoint_y=0.5,
                    depth_delta=0.0,
                )

            # Distance calculation (Inter-eye distance)
            dist = hypot(right_center[0] - left_center[0], right_center[1] - left_center[1])
            mid_x = (left_center[0] + right_center[0]) / 2.0
            mid_y = (left_center[1] + right_center[1]) / 2.0

            # Depth / Yaw delta calculation
            left_z = sum(p.z for p in eye_data.left_eye) / len(eye_data.left_eye)
            right_z = sum(p.z for p in eye_data.right_eye) / len(eye_data.right_eye)
            depth_delta = abs(left_z - right_z)

            # Determine posture status
            status, message, distance_label = self._classify_bounds(dist, mid_x, mid_y, depth_delta)

            # Stability Gating
            now = time.time()
            if status == "good":
                if self._last_eye_center is not None:
                    jump = hypot(mid_x - self._last_eye_center[0], mid_y - self._last_eye_center[1])
                    if jump > 0.05:
                        self._stable_since = now  # Reset on sudden movement
                if self._stable_since is None:
                    self._stable_since = now

                is_stable = (now - self._stable_since) >= self._stabilization_window
            else:
                self._stable_since = None
                is_stable = False

            self._last_eye_center = (mid_x, mid_y)

            return CalibrationGuidanceState(
                status=status,
                message=message,
                face_distance=distance_label,
                is_stable=is_stable,
                confidence=1.0 if status == "good" else 0.5,
                inter_eye_distance=round(dist, 4),
                midpoint_x=round(mid_x, 4),
                midpoint_y=round(mid_y, 4),
                depth_delta=round(depth_delta, 4),
            )

    def _classify_bounds(self, dist: float, mid_x: float, mid_y: float, depth_delta: float) -> tuple[str, str, str]:
        if dist < self._min_dist:
            return "face_too_far", "Move closer to the camera", "far"
        if dist > self._max_dist:
            return "face_too_close", "Move farther away", "close"
        if mid_x < self._min_x:
            return "face_too_left", "Move right / center face", "normal"
        if mid_x > self._max_x:
            return "face_too_right", "Move left / center face", "normal"
        if mid_y < self._min_y:
            return "face_too_high", "Lower your face / camera", "normal"
        if mid_y > self._max_y:
            return "face_too_low", "Raise your face / camera", "normal"
        if depth_delta > self._max_depth_delta:
            return "head_turned", "Keep your head straight", "normal"

        return "good", "Good position — hold steady", "normal"

    @staticmethod
    def _compute_landmarks_center(landmarks: tuple[NormalizedLandmark, ...]) -> tuple[float, float] | None:
        if not landmarks:
            return None
        xs = [p.x for p in landmarks if isfinite(p.x)]
        ys = [p.y for p in landmarks if isfinite(p.y)]
        if not xs or not ys:
            return None
        return (sum(xs) / len(xs), sum(ys) / len(ys))

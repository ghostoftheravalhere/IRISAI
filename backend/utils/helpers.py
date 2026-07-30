"""
Shared helper functions used across modules.
Add stateless utility functions here — no business logic.
"""
from typing import Any


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


def normalize(value: float, min_val: float, max_val: float) -> float:
    """Normalize value to 0.0–1.0 range."""
    if max_val == min_val:
        return 0.0
    return (value - min_val) / (max_val - min_val)


def compute_eye_center(eye_data: Any) -> tuple[float, float] | None:
    """Sprint 1 shared eye-center average used to remove duplicated helpers."""
    landmarks = tuple(eye_data.left_eye) + tuple(eye_data.right_eye)
    if not landmarks:
        return None

    return (
        sum(landmark.x for landmark in landmarks) / len(landmarks),
        sum(landmark.y for landmark in landmarks) / len(landmarks),
    )

"""
Shared helper functions used across modules.
Add stateless utility functions here — no business logic.
"""


def clamp(value: float, min_val: float, max_val: float) -> float:
    """Clamp a value between min and max."""
    return max(min_val, min(max_val, value))


def normalize(value: float, min_val: float, max_val: float) -> float:
    """Normalize value to 0.0–1.0 range."""
    if max_val == min_val:
        return 0.0
    return (value - min_val) / (max_val - min_val)

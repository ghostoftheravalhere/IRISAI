"""Canonical configuration package for IRIS AI V2."""

from backend.core.config.eye_config import (
    LEFT_EAR_LANDMARK_INDICES,
    RIGHT_EAR_LANDMARK_INDICES,
    EyeInteractionConfig,
    build_eye_interaction_config,
    default_eye_interaction_config,
)
from backend.core.config.settings import Settings, settings

__all__ = [
    "EyeInteractionConfig",
    "LEFT_EAR_LANDMARK_INDICES",
    "RIGHT_EAR_LANDMARK_INDICES",
    "Settings",
    "build_eye_interaction_config",
    "default_eye_interaction_config",
    "settings",
]

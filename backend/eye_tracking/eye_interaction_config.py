"""Sprint 1 compatibility shim for the new core eye config path."""

# Keep legacy eye_tracking imports working while core.config.eye_config is canonical.
from backend.core.config.eye_config import (
    LEFT_EAR_LANDMARK_INDICES,
    RIGHT_EAR_LANDMARK_INDICES,
    EyeInteractionConfig,
    build_eye_interaction_config,
    default_eye_interaction_config,
)

__all__ = [
    "EyeInteractionConfig",
    "LEFT_EAR_LANDMARK_INDICES",
    "RIGHT_EAR_LANDMARK_INDICES",
    "build_eye_interaction_config",
    "default_eye_interaction_config",
]

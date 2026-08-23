"""Compatibility shim for the canonical perception Face Mesh provider."""

from backend.perception.camera.face_mesh_provider import (
    LEFT_EYE_LANDMARK_INDICES,
    RIGHT_EYE_LANDMARK_INDICES,
    EyeData,
    FaceMeshFrameResult,
    FaceMeshService,
    NormalizedLandmark,
)

__all__ = [
    "EyeData",
    "FaceMeshFrameResult",
    "FaceMeshService",
    "LEFT_EYE_LANDMARK_INDICES",
    "NormalizedLandmark",
    "RIGHT_EYE_LANDMARK_INDICES",
]

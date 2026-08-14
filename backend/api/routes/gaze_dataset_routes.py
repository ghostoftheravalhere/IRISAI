"""FastAPI Router for Eye Gaze Dataset Collection & Validation."""

from __future__ import annotations

from fastapi import APIRouter, Body
from pydantic import BaseModel, Field

from backend.datasets.gaze.collector import GazeDatasetCollector
from backend.datasets.gaze.validator import GazeDatasetValidator

router = APIRouter(prefix="/dataset/gaze", tags=["gaze-dataset"])

_GLOBAL_COLLECTOR = GazeDatasetCollector()
_GLOBAL_VALIDATOR = GazeDatasetValidator()


class StartSessionRequest(BaseModel):
    user_id: str = Field(default="user_01", description="Unique user identifier for anti-leakage splitting")
    session_id: str | None = Field(default=None, description="Optional custom session identifier")


class CaptureSampleRequest(BaseModel):
    target_index: int = Field(default=0, ge=0, le=8, description="Target point index (0-8)")


def get_global_collector() -> GazeDatasetCollector:
    return _GLOBAL_COLLECTOR


@router.post("/session/start")
def start_collection_session(req: StartSessionRequest = Body(...)):
    """Start a new gaze dataset collection session."""
    collector = get_global_collector()
    return collector.start_session(user_id=req.user_id, session_id=req.session_id)


@router.post("/session/stop")
def stop_collection_session():
    """Stop the current gaze dataset collection session."""
    collector = get_global_collector()
    return collector.stop_session()


@router.get("/status")
def get_collection_status():
    """Return current collection session progress and target counts."""
    collector = get_global_collector()
    return collector.get_status()


@router.get("/validate")
def validate_gaze_dataset():
    """Run dataset integrity scan and return validation report."""
    validator = _GLOBAL_VALIDATOR
    rep = validator.validate_dataset()
    return {
        "is_valid": rep.is_valid,
        "total_users": rep.total_users,
        "total_sessions": rep.total_sessions,
        "total_samples": rep.total_samples,
        "samples_per_target": rep.samples_per_target,
        "missing_images": rep.missing_images,
        "invalid_samples": rep.invalid_samples,
        "issues": rep.issues,
    }

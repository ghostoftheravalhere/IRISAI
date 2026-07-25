"""Eye tracking API routes."""

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from backend.eye_tracking.calibration import (
    CalibrationMapping,
    CalibrationPoint,
    CalibrationProgress,
    CalibrationSample,
    CalibrationState,
    EyeCenter,
)
from backend.eye_tracking.face_mesh_service import EyeData, NormalizedLandmark

router = APIRouter(tags=["eye_tracking"])


class LandmarkResponse(BaseModel):
    """Normalized landmark API response."""

    model_config = ConfigDict(extra="forbid")

    index: int
    x: float
    y: float
    z: float


class EyeDataResponse(BaseModel):
    """Normalized eye landmark API response."""

    model_config = ConfigDict(extra="forbid")

    left_eye: tuple[LandmarkResponse, ...]
    right_eye: tuple[LandmarkResponse, ...]


class CalibrationPointResponse(BaseModel):
    """Calibration point API response."""

    model_config = ConfigDict(extra="forbid")

    index: int
    x: float
    y: float


class EyeCenterResponse(BaseModel):
    """Eye center API response."""

    model_config = ConfigDict(extra="forbid")

    x: float
    y: float


class CalibrationSampleResponse(BaseModel):
    """Calibration sample API response."""

    model_config = ConfigDict(extra="forbid")

    point: CalibrationPointResponse
    eye_data: EyeDataResponse
    eye_center: EyeCenterResponse
    captured_at: float


class CalibrationMappingResponse(BaseModel):
    """Calibration mapping API response."""

    model_config = ConfigDict(extra="forbid")

    x_coefficients: tuple[float, float, float]
    y_coefficients: tuple[float, float, float]
    sample_count: int


class CalibrationProgressResponse(BaseModel):
    """Calibration progress API response."""

    model_config = ConfigDict(extra="forbid")

    current_point: CalibrationPointResponse | None
    completed_points: int
    total_points: int
    progress: float
    complete: bool


class CalibrationStateResponse(BaseModel):
    """Saved calibration state API response."""

    model_config = ConfigDict(extra="forbid")

    points: tuple[CalibrationPointResponse, ...]
    samples: tuple[CalibrationSampleResponse, ...]
    mapping: CalibrationMappingResponse | None
    complete: bool
    updated_at: float


@router.get("/status")
async def eye_status(request: Request) -> dict[str, object]:
    """Return eye module status and calibration progress."""
    calibration = request.app.state.eye_calibration
    return {
        "status": "ready",
        "calibration": _serialize_progress(calibration.get_progress()),
    }


@router.get("/calibration/progress", response_model=CalibrationProgressResponse)
async def calibration_progress(request: Request) -> dict[str, object]:
    """Return the current 9-point calibration progress."""
    return _serialize_progress(request.app.state.eye_calibration.get_progress())


@router.post("/calibration/restart", response_model=CalibrationProgressResponse)
async def calibration_restart(request: Request) -> dict[str, object]:
    """Restart eye calibration from the first point."""
    return _serialize_progress(request.app.state.eye_calibration.restart())


@router.post("/calibration/capture", response_model=CalibrationProgressResponse)
async def calibration_capture(request: Request) -> dict[str, object]:
    """Capture latest eye landmarks for the current calibration point."""
    eye_data = request.app.state.camera.get_latest_eye_data()
    if eye_data is None:
        raise HTTPException(
            status_code=409,
            detail="No eye landmarks are available from the camera stream.",
        )

    progress = request.app.state.eye_calibration.record_current_point(eye_data)
    return _serialize_progress(progress)


@router.get("/calibration/state", response_model=CalibrationStateResponse)
async def calibration_state(request: Request) -> dict[str, object]:
    """Return the saved calibration state."""
    return _serialize_state(request.app.state.eye_calibration.get_state())


@router.get("/calibration/mapping", response_model=CalibrationMappingResponse | None)
async def calibration_mapping(request: Request) -> dict[str, object] | None:
    """Return computed calibration mapping values, if available."""
    mapping = request.app.state.eye_calibration.get_mapping()
    if mapping is None:
        return None
    return _serialize_mapping(mapping)


def _serialize_progress(progress: CalibrationProgress) -> dict[str, object]:
    """Serialize calibration progress for API responses."""
    return {
        "current_point": _serialize_point(progress.current_point),
        "completed_points": progress.completed_points,
        "total_points": progress.total_points,
        "progress": progress.progress,
        "complete": progress.complete,
    }


def _serialize_state(state: CalibrationState) -> dict[str, object]:
    """Serialize calibration state for API responses."""
    return {
        "points": tuple(_serialize_point(point) for point in state.points),
        "samples": tuple(_serialize_sample(sample) for sample in state.samples),
        "mapping": _serialize_mapping(state.mapping),
        "complete": state.complete,
        "updated_at": state.updated_at,
    }


def _serialize_sample(sample: CalibrationSample) -> dict[str, object]:
    """Serialize one calibration sample."""
    return {
        "point": _serialize_point(sample.point),
        "eye_data": _serialize_eye_data(sample.eye_data),
        "eye_center": _serialize_eye_center(sample.eye_center),
        "captured_at": sample.captured_at,
    }


def _serialize_point(point: CalibrationPoint | None) -> dict[str, object] | None:
    """Serialize one calibration point."""
    if point is None:
        return None

    return {
        "index": point.index,
        "x": point.x,
        "y": point.y,
    }


def _serialize_eye_center(eye_center: EyeCenter) -> dict[str, float]:
    """Serialize one normalized eye center."""
    return {
        "x": eye_center.x,
        "y": eye_center.y,
    }


def _serialize_eye_data(eye_data: EyeData) -> dict[str, object]:
    """Serialize normalized eye landmark data."""
    return {
        "left_eye": tuple(_serialize_landmark(landmark) for landmark in eye_data.left_eye),
        "right_eye": tuple(_serialize_landmark(landmark) for landmark in eye_data.right_eye),
    }


def _serialize_landmark(landmark: NormalizedLandmark) -> dict[str, float | int]:
    """Serialize one normalized landmark."""
    return {
        "index": landmark.index,
        "x": landmark.x,
        "y": landmark.y,
        "z": landmark.z,
    }


def _serialize_mapping(mapping: CalibrationMapping | None) -> dict[str, object] | None:
    """Serialize calibration mapping coefficients."""
    if mapping is None:
        return None

    return {
        "x_coefficients": mapping.x_coefficients,
        "y_coefficients": mapping.y_coefficients,
        "sample_count": mapping.sample_count,
    }

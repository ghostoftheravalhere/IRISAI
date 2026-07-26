"""Eye tracking API routes."""

import asyncio

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict

from backend.eye_tracking.calibration import (
    CalibrationCaptureError,
    CalibrationMapping,
    CalibrationPoint,
    CalibrationProgress,
    CalibrationQuality,
    CalibrationSample,
    CalibrationState,
    EyeCenter,
)
from backend.eye_tracking.camera_service import CameraServiceError
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


class CalibrationQualityResponse(BaseModel):
    """Calibration quality API response."""

    model_config = ConfigDict(extra="forbid")

    score: float
    rmse: float
    label: str
    recommend_recalibration: bool


class CalibrationMappingResponse(BaseModel):
    """Calibration mapping API response."""

    model_config = ConfigDict(extra="forbid")

    x_coefficients: tuple[float, float, float]
    y_coefficients: tuple[float, float, float]
    sample_count: int
    quality: CalibrationQualityResponse | None = None


class CalibrationProgressResponse(BaseModel):
    """Calibration progress API response."""

    model_config = ConfigDict(extra="forbid")

    current_point: CalibrationPointResponse | None
    completed_points: int
    total_points: int
    progress: float
    complete: bool
    quality: CalibrationQualityResponse | None = None


class CalibrationStateResponse(BaseModel):
    """Saved calibration state API response."""

    model_config = ConfigDict(extra="forbid")

    points: tuple[CalibrationPointResponse, ...]
    samples: tuple[CalibrationSampleResponse, ...]
    mapping: CalibrationMappingResponse | None
    complete: bool
    updated_at: float
    quality: CalibrationQualityResponse | None = None


class CursorControllerResponse(BaseModel):
    """Cursor controller state API response."""

    model_config = ConfigDict(extra="forbid")

    enabled: bool
    paused: bool
    dragMode: bool
    trackingActive: bool
    trackingConfidence: float
    lastX: int | None
    lastY: int | None


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
    request.app.state.camera.reset_interaction_pipeline()
    return _serialize_progress(request.app.state.eye_calibration.restart())


@router.post("/calibration/capture", response_model=CalibrationProgressResponse)
async def calibration_capture(request: Request) -> dict[str, object]:
    """Capture stabilized, averaged eye landmarks for the current point."""
    camera = request.app.state.camera
    calibration = request.app.state.eye_calibration

    try:
        eye_samples = await asyncio.to_thread(camera.collect_calibration_eye_samples)
    except CameraServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    if not eye_samples:
        raise HTTPException(
            status_code=409,
            detail="No eye landmarks are available from the camera stream.",
        )

    try:
        progress = await asyncio.to_thread(
            calibration.record_current_point_from_samples,
            eye_samples,
        )
    except CalibrationCaptureError as exc:
        raise HTTPException(
            status_code=409,
            detail=f"Could not capture a stable calibration sample: {exc}",
        ) from exc

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


@router.post("/cursor/enable", response_model=CursorControllerResponse)
async def cursor_enable(request: Request) -> dict[str, object]:
    """Enable cursor control after calibration quality is acceptable."""
    progress = request.app.state.eye_calibration.get_progress()
    if not progress.complete:
        raise HTTPException(
            status_code=409,
            detail="Calibration must be complete before enabling cursor control.",
        )

    quality = progress.quality
    threshold = request.app.state.eye_interaction_config.calibration_quality_threshold
    if quality is None or quality.recommend_recalibration or quality.score < threshold:
        raise HTTPException(
            status_code=409,
            detail=(
                "Calibration quality is too low for reliable cursor control. "
                "Recalibrate, then try enabling cursor again."
            ),
        )

    return _serialize_cursor_state(request.app.state.cursor_controller.enable())


@router.post("/cursor/disable", response_model=CursorControllerResponse)
async def cursor_disable(request: Request) -> dict[str, object]:
    """Disable cursor control and release drag / tracking state."""
    request.app.state.camera.reset_interaction_pipeline()
    return _serialize_cursor_state(request.app.state.cursor_controller.get_state())


class OverlayModeRequest(BaseModel):
    """Overlay mode switch request."""

    model_config = ConfigDict(extra="forbid")

    mode: str


class OverlayModeResponse(BaseModel):
    """Overlay mode API response."""

    model_config = ConfigDict(extra="forbid")

    mode: str


@router.get("/overlay/mode", response_model=OverlayModeResponse)
async def get_overlay_mode(request: Request) -> dict[str, str]:
    """Return the active camera overlay mode (normal or debug)."""
    return {"mode": request.app.state.gaze_debug_visualizer.get_mode()}


@router.post("/overlay/mode", response_model=OverlayModeResponse)
async def set_overlay_mode(request: Request, body: OverlayModeRequest) -> dict[str, str]:
    """Switch the camera overlay between normal demo and debug diagnostics."""
    mode = body.mode.lower().strip()
    try:
        active = request.app.state.gaze_debug_visualizer.set_mode(mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"mode": active}


def _serialize_progress(progress: CalibrationProgress) -> dict[str, object]:
    """Serialize calibration progress for API responses."""
    return {
        "current_point": _serialize_point(progress.current_point),
        "completed_points": progress.completed_points,
        "total_points": progress.total_points,
        "progress": progress.progress,
        "complete": progress.complete,
        "quality": _serialize_quality(progress.quality),
    }


def _serialize_state(state: CalibrationState) -> dict[str, object]:
    """Serialize calibration state for API responses."""
    return {
        "points": tuple(_serialize_point(point) for point in state.points),
        "samples": tuple(_serialize_sample(sample) for sample in state.samples),
        "mapping": _serialize_mapping(state.mapping),
        "complete": state.complete,
        "updated_at": state.updated_at,
        "quality": _serialize_quality(state.quality),
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
        "quality": _serialize_quality(mapping.quality),
    }


def _serialize_quality(quality: CalibrationQuality | None) -> dict[str, object] | None:
    """Serialize calibration quality metrics."""
    if quality is None:
        return None

    return {
        "score": quality.score,
        "rmse": quality.rmse,
        "label": quality.label,
        "recommend_recalibration": quality.recommend_recalibration,
    }


def _serialize_cursor_state(cursor_state) -> dict[str, object]:
    """Serialize cursor controller state."""
    return {
        "enabled": cursor_state.enabled,
        "paused": cursor_state.paused,
        "dragMode": cursor_state.dragMode,
        "trackingActive": cursor_state.trackingActive,
        "trackingConfidence": cursor_state.trackingConfidence,
        "lastX": cursor_state.lastX,
        "lastY": cursor_state.lastY,
    }

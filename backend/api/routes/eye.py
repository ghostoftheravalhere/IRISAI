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
from backend.utils.logger import get_logger

logger = get_logger(__name__)

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


class ValidationReportResponse(BaseModel):
    """Independent validation report API response."""

    model_config = ConfigDict(extra="ignore")

    mean_norm_error: float
    max_norm_error: float
    per_target_norm_errors: tuple[float, ...]
    mean_pixel_error: float | None = None
    max_pixel_error: float | None = None
    per_target_pixel_errors: tuple[float, ...] | None = None
    valid_sample_counts: tuple[int, ...] = ()
    passed: bool
    description: str = "preliminary validation (4 held-out targets; not proof of full-screen accuracy)"


class CalibrationProgressResponse(BaseModel):
    """Calibration progress API response."""

    model_config = ConfigDict(extra="ignore")

    current_point: CalibrationPointResponse | None
    completed_points: int
    total_points: int
    progress: float
    complete: bool
    quality: CalibrationQualityResponse | None = None
    phase: str = "training"
    validation_report: ValidationReportResponse | None = None
    is_calibrated: bool = False
    mode: str = "16-point"


class CalibrationStateResponse(BaseModel):
    """Saved calibration state API response."""

    model_config = ConfigDict(extra="ignore")

    points: tuple[CalibrationPointResponse, ...]
    samples: tuple[CalibrationSampleResponse, ...]
    mapping: CalibrationMappingResponse | None
    complete: bool
    updated_at: float
    quality: CalibrationQualityResponse | None = None
    validation_report: ValidationReportResponse | None = None
    is_calibrated: bool = False
    mode: str = "16-point"


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


class CalibrationRestartRequest(BaseModel):
    """Optional payload specifying calibration mode upon restart."""

    model_config = ConfigDict(extra="ignore")

    mode: str | None = None


@router.post("/calibration/restart", response_model=CalibrationProgressResponse)
@router.post("/calibration/start", response_model=CalibrationProgressResponse)
@router.post("/calibrate", response_model=CalibrationProgressResponse)
async def calibration_restart(
    request: Request,
    body: CalibrationRestartRequest | None = None,
) -> dict[str, object]:
    """Restart eye calibration from the first point, optionally specifying calibration mode."""
    mode = body.mode if body else None
    request.app.state.camera.reset_interaction_pipeline()
    try:
        progress = request.app.state.eye_calibration.restart(mode=mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return _serialize_progress(progress)


class RecalibrateCenterRequest(BaseModel):
    """Optional payload for center recalibration."""

    model_config = ConfigDict(extra="ignore")

    neutral_x: float | None = None
    neutral_y: float | None = None


@router.post("/recalibrate-center")
async def recalibrate_center(
    request: Request,
    body: RecalibrateCenterRequest | None = None,
) -> dict[str, object]:
    """Recalibrate gaze neutral center for cursor controller."""
    cursor_ctrl = getattr(request.app.state, "cursor_controller", None)
    nx = body.neutral_x if body else None
    ny = body.neutral_y if body else None
    cal_x, cal_y = 0.50, 0.58
    if cursor_ctrl is not None:
        cal_x, cal_y = cursor_ctrl.recalibrate_center(nx, ny)
    return {
        "status": "recalibrated",
        "neutral_x": round(cal_x, 4),
        "neutral_y": round(cal_y, 4),
    }


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
    state = request.app.state.eye_calibration.get_state()
    logger.info(
        "[DIAGNOSTIC] calibration_state called: completed=%s, mapping_valid=%s, quality=%s, rmse=%s, sample_count=%d",
        state.complete,
        state.mapping is not None,
        state.quality.score if state.quality else None,
        state.quality.rmse if state.quality else None,
        len(state.samples),
    )
    return _serialize_state(state)


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
    cursor_before = request.app.state.cursor_controller.get_state().enabled
    logger.info(
        "[DIAGNOSTIC] cursor_enable called: calibration_completed=%s, mapping_valid=%s, quality=%s, rmse=%s, cursor_enabled_before=%s",
        progress.complete,
        progress.quality is not None,
        progress.quality.score if progress.quality else None,
        progress.quality.rmse if progress.quality else None,
        cursor_before,
    )
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

    val_report = getattr(progress, "validation_report", None)
    if val_report is not None and not getattr(val_report, "passed", True):
        raise HTTPException(
            status_code=409,
            detail=(
                "Calibration validation gates failed. "
                "Recalibrate, then try enabling cursor again."
            ),
        )

    calib_svc = getattr(request.app.state, "eye_calibration", None)
    if calib_svc is not None and not getattr(calib_svc, "is_calibrated", False):
        raise HTTPException(
            status_code=409,
            detail="Calibration is not authorized. Recalibrate, then try enabling cursor again.",
        )

    state = request.app.state.cursor_controller.enable()
    logger.info(
        "[DIAGNOSTIC] cursor_enable succeeded: cursor_enabled_after=%s, trackingActive=%s",
        state.enabled,
        state.trackingActive,
    )
    return _serialize_cursor_state(state)


@router.post("/cursor/disable", response_model=CursorControllerResponse)
async def cursor_disable(request: Request) -> dict[str, object]:
    """Disable cursor control and release drag / tracking state."""
    request.app.state.camera.reset_interaction_pipeline()
    state = request.app.state.cursor_controller.disable()
    logger.info(
        "[DIAGNOSTIC] cursor_disable called: cursor_enabled_after=%s",
        state.enabled,
    )
    return _serialize_cursor_state(state)


@router.get("/cursor/status", response_model=CursorControllerResponse)
async def cursor_status(request: Request) -> dict[str, object]:
    """Return current cursor controller status."""
    state = request.app.state.cursor_controller.get_state()
    return _serialize_cursor_state(state)


class RecalibrateCenterRequest(BaseModel):
    """Optional explicit neutral center coordinates."""

    model_config = ConfigDict(extra="forbid")

    neutral_x: float | None = None
    neutral_y: float | None = None


class RecalibrateCenterResponse(BaseModel):
    """Recalibrate center response."""

    model_config = ConfigDict(extra="forbid")

    neutral_x: float
    neutral_y: float
    status: str = "recalibrated"


@router.post("/recalibrate-center", response_model=RecalibrateCenterResponse)
@router.post("/cursor/recalibrate-center", response_model=RecalibrateCenterResponse)
async def recalibrate_center(
    request: Request,
    body: RecalibrateCenterRequest | None = None,
) -> dict[str, object]:
    """Dynamically re-zero gaze center calibration to comfortable resting eye position."""
    gaze_service = getattr(request.app.state, "gaze_service", None)
    if gaze_service is None:
        cursor_ctrl = getattr(request.app.state, "cursor_controller", None)
        if cursor_ctrl is not None:
            gaze_service = getattr(cursor_ctrl, "_gaze_service", None)

    if gaze_service is None or not hasattr(gaze_service, "recalibrate_center"):
        raise HTTPException(status_code=503, detail="Gaze service not initialized")

    nx = body.neutral_x if body else None
    ny = body.neutral_y if body else None
    cal_x, cal_y = gaze_service.recalibrate_center(nx, ny)

    cursor_ctrl = getattr(request.app.state, "cursor_controller", None)
    if cursor_ctrl is not None and hasattr(cursor_ctrl, "_physics_pipeline"):
        with cursor_ctrl._lock:
            if cursor_ctrl._physics_pipeline is not None:
                cursor_ctrl._physics_pipeline.reset()

    logger.info("Recalibrate center successful: neutral=(%.3f, %.3f)", cal_x, cal_y)
    return {
        "neutral_x": round(cal_x, 4),
        "neutral_y": round(cal_y, 4),
        "status": "recalibrated",
    }


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


@router.get("/hud")
async def get_gaze_hud_telemetry(request: Request) -> dict[str, object]:
    """Return live gaze HUD overlay telemetry state."""
    gaze_service = getattr(request.app.state, "eye_gaze", None)
    gaze = gaze_service.get_latest_gaze() if gaze_service else None

    if gaze is None:
        return {
            "gaze_x": 0.5,
            "gaze_y": 0.5,
            "confidence": 0.0,
            "tracking_state": "lost",
            "ptt_state": "idle",
        }

    state = "active" if gaze.confidence >= 0.45 else "low_confidence"
    return {
        "gaze_x": round(gaze.x, 4),
        "gaze_y": round(gaze.y, 4),
        "confidence": round(gaze.confidence, 4),
        "tracking_state": state,
        "ptt_state": "idle",
    }


@router.get("/calibration/guidance")
async def get_calibration_guidance(request: Request) -> dict[str, object]:
    """Return real-time calibration posture, distance, and head-pose guidance state."""
    camera = getattr(request.app.state, "camera", None)
    eye_data = camera.get_latest_eye_data() if camera else None

    from backend.eye_tracking.calibration_guidance import CalibrationGuidanceService
    guidance_service = getattr(request.app.state, "calibration_guidance", None)
    if guidance_service is None:
        guidance_service = CalibrationGuidanceService()
        setattr(request.app.state, "calibration_guidance", guidance_service)

    state = guidance_service.evaluate_posture(eye_data)
    return {
        "status": state.status,
        "message": state.message,
        "face_distance": state.face_distance,
        "is_stable": state.is_stable,
        "confidence": state.confidence,
        "inter_eye_distance": state.inter_eye_distance,
        "midpoint_x": state.midpoint_x,
        "midpoint_y": state.midpoint_y,
        "depth_delta": state.depth_delta,
    }


@router.post("/overlay/mode", response_model=OverlayModeResponse)
async def set_overlay_mode(request: Request, body: OverlayModeRequest) -> dict[str, str]:
    """Switch the camera overlay between normal demo and debug diagnostics."""
    mode = body.mode.lower().strip()
    try:
        active = request.app.state.gaze_debug_visualizer.set_mode(mode)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"mode": active}


def _serialize_validation_report(report) -> dict[str, object] | None:
    """Serialize independent validation report."""
    if report is None:
        return None
    return {
        "mean_norm_error": report.mean_norm_error,
        "max_norm_error": report.max_norm_error,
        "per_target_norm_errors": report.per_target_norm_errors,
        "mean_pixel_error": report.mean_pixel_error,
        "max_pixel_error": report.max_pixel_error,
        "per_target_pixel_errors": report.per_target_pixel_errors,
        "valid_sample_counts": report.valid_sample_counts,
        "passed": report.passed,
        "description": report.description,
    }


def _serialize_progress(progress: CalibrationProgress) -> dict[str, object]:
    """Serialize calibration progress for API responses."""
    return {
        "current_point": _serialize_point(progress.current_point),
        "completed_points": progress.completed_points,
        "total_points": progress.total_points,
        "progress": progress.progress,
        "complete": progress.complete,
        "quality": _serialize_quality(progress.quality),
        "phase": getattr(progress, "phase", "training"),
        "validation_report": _serialize_validation_report(getattr(progress, "validation_report", None)),
        "is_calibrated": getattr(progress, "is_calibrated", False),
        "mode": getattr(progress, "mode", "16-point"),
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
        "validation_report": _serialize_validation_report(getattr(state, "validation_report", None)),
        "is_calibrated": getattr(state, "is_calibrated", False),
        "mode": getattr(state, "mode", "16-point"),
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

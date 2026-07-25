"""Camera API routes."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict

from backend.eye_tracking.camera_service import CameraServiceError

router = APIRouter(prefix="/camera", tags=["camera"])


class CameraStatusResponse(BaseModel):
    """Camera status response returned by camera endpoints."""

    model_config = ConfigDict(extra="forbid")

    connected: bool
    running: bool
    camera_index: int


class CameraActionResponse(CameraStatusResponse):
    """Camera action response with a human-readable result message."""

    message: str


@router.get("/status", response_model=CameraStatusResponse)
async def camera_status(request: Request) -> dict[str, bool | int]:
    """Return the current camera connection and capture status."""
    return request.app.state.camera.status()


@router.post("/start", response_model=CameraActionResponse)
async def camera_start(request: Request) -> dict[str, bool | int | str]:
    """Start the camera capture session."""
    try:
        status = request.app.state.camera.start()
    except CameraServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return {"message": "Camera started.", **status}


@router.post("/stop", response_model=CameraActionResponse)
async def camera_stop(request: Request) -> dict[str, bool | int | str]:
    """Stop the camera capture session."""
    try:
        status = request.app.state.camera.stop()
    except CameraServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return {"message": "Camera stopped.", **status}


@router.get("/stream")
async def camera_stream(request: Request) -> StreamingResponse:
    """Stream MJPEG frames from the already-running camera."""
    camera = request.app.state.camera
    if not camera.is_running:
        raise HTTPException(status_code=409, detail="Camera is not running.")

    try:
        stream = camera.mjpeg_frame_stream()
    except CameraServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc

    return StreamingResponse(
        stream,
        media_type="multipart/x-mixed-replace; boundary=frame",
    )

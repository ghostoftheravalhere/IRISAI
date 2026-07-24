"""
Camera API Routes
Owner: Rehan

Exposes CameraService over HTTP.
The service instance is stored on app.state so it is shared across requests
and properly released on shutdown.
"""
from fastapi import APIRouter, HTTPException, Request
from backend.utils.logger import get_logger

router = APIRouter(prefix="/camera", tags=["camera"])
logger = get_logger(__name__)


@router.get("/status")
async def camera_status(request: Request):
    """Return whether the camera device is present and whether it is running."""
    return request.app.state.camera.status()


@router.post("/start")
async def camera_start(request: Request):
    """Open the webcam. Returns 409 if already running, 503 if unavailable."""
    camera = request.app.state.camera
    if camera.is_running:
        raise HTTPException(status_code=409, detail="Camera is already running.")
    try:
        camera.start()
    except RuntimeError as exc:
        logger.warning("Camera start failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
    return {"message": "Camera started.", **camera.status()}


@router.post("/stop")
async def camera_stop(request: Request):
    """Release the webcam. Returns 409 if it was not running."""
    camera = request.app.state.camera
    if not camera.is_running:
        raise HTTPException(status_code=409, detail="Camera is not running.")
    camera.stop()
    return {"message": "Camera stopped.", **camera.status()}

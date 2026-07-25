"""
FastAPI Application Factory
Creates and configures the FastAPI app with all routers and middleware.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import settings
from backend.utils.logger import get_logger
from backend.api.routes import health, camera, eye
from backend.eye_tracking.camera_service import CameraService
from backend.eye_tracking.calibration import EyeCalibrationService
from backend.eye_tracking.gaze_service import EyeGazeService

logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="IRIS AI Backend",
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.DEBUG else None,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Shared service instances — attached to app.state for request access
    app.state.camera = CameraService(camera_index=settings.WEBCAM_INDEX)
    app.state.eye_calibration = EyeCalibrationService()
    app.state.eye_gaze = EyeGazeService(
        camera_service=app.state.camera,
        calibration_service=app.state.eye_calibration,
    )

    app.include_router(health.router)
    app.include_router(camera.router)
    app.include_router(eye.router, prefix="/eye")

    # Feature routers registered here as modules are built
    # from backend.api.routes import voice, ai, automation
    # app.include_router(voice.router, prefix="/voice")
    # app.include_router(ai.router, prefix="/ai")
    # app.include_router(automation.router, prefix="/automation")

    @app.on_event("startup")
    async def on_startup():
        logger.info("IRIS AI backend started — v%s [%s]", settings.APP_VERSION, settings.APP_ENV)

    @app.on_event("shutdown")
    async def on_shutdown():
        # Ensure the webcam is released even if the client never called /camera/stop
        app.state.camera.cleanup()
        logger.info("IRIS AI backend shut down cleanly.")

    return app

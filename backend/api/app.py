"""
FastAPI Application Factory
Creates and configures the FastAPI app with all routers and middleware.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.config.settings import settings
from backend.utils.logger import get_logger
from backend.api.routes import health

logger = get_logger(__name__)


def create_app() -> FastAPI:
    app = FastAPI(
        title="IRIS AI Backend",
        version=settings.APP_VERSION,
        docs_url="/docs" if settings.DEBUG else None,
    )

    app.add_middleware(
        CORSMiddleware,
        # Allow Vite dev server and Electron renderer (file://)
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.include_router(health.router)

    # Feature routers registered here as modules are built
    # from backend.api.routes import eye, voice, ai, automation
    # app.include_router(eye.router, prefix="/eye")
    # app.include_router(voice.router, prefix="/voice")
    # app.include_router(ai.router, prefix="/ai")
    # app.include_router(automation.router, prefix="/automation")

    @app.on_event("startup")
    async def on_startup():
        logger.info("IRIS AI backend started — v%s [%s]", settings.APP_VERSION, settings.APP_ENV)

    return app

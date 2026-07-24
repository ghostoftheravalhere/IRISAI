"""
FastAPI Application Factory
Creates and configures the FastAPI app with all routers and middleware.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware


def create_app() -> FastAPI:
    app = FastAPI(title="IRIS AI Backend", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173"],  # Vite dev server
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Routers registered here as modules are built
    # from backend.api.routes import eye, voice, ai, automation
    # app.include_router(eye.router, prefix="/eye")
    # app.include_router(voice.router, prefix="/voice")
    # app.include_router(ai.router, prefix="/ai")
    # app.include_router(automation.router, prefix="/automation")

    return app

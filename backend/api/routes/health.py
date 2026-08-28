"""Health check route — confirms the backend is reachable."""
import sys
from fastapi import APIRouter
from backend.config.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {
        "status": "online",
        "version": settings.APP_VERSION,
        "executable": sys.executable,
        "is_frozen": getattr(sys, "frozen", False),
        "resolver": "universal_v2.4.5",
    }

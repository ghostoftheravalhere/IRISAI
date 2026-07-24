"""Health check route — confirms the backend is reachable."""
from fastapi import APIRouter
from backend.config.settings import settings

router = APIRouter(tags=["health"])


@router.get("/health")
async def health():
    return {"status": "online", "version": settings.APP_VERSION}

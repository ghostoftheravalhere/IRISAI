"""Voice recognition API routes — Owner: Prit"""
from fastapi import APIRouter

router = APIRouter(tags=["voice"])


@router.get("/status")
async def voice_status():
    # TODO: return recognizer status
    return {"status": "not_implemented"}

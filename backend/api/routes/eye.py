"""Eye tracking API routes — Owner: Rehan"""
from fastapi import APIRouter

router = APIRouter(tags=["eye_tracking"])


@router.get("/status")
async def eye_status():
    # TODO: return live tracker status
    return {"status": "not_implemented"}

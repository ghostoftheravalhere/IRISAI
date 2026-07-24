"""AI assistant API routes — Owner: Meet"""
from fastapi import APIRouter

router = APIRouter(tags=["ai"])


@router.get("/status")
async def ai_status():
    # TODO: return assistant status
    return {"status": "not_implemented"}

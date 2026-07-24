"""Desktop automation API routes — Owner: Mehil"""
from fastapi import APIRouter

router = APIRouter(tags=["automation"])


@router.get("/status")
async def automation_status():
    # TODO: return dispatcher status
    return {"status": "not_implemented"}

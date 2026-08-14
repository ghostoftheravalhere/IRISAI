"""FastAPI Router for Semantic Memory & Knowledge System."""

from __future__ import annotations

from fastapi import APIRouter, Query
from pydantic import BaseModel

from backend.memory.memory_manager import MemoryManager
from backend.memory.memory_models import MemoryLayer

router = APIRouter(prefix="/memory", tags=["memory"])

# Shared MemoryManager singleton instance
_memory_manager = MemoryManager()


class RememberRequest(BaseModel):
    content: str
    layer: str = "SEMANTIC"
    tags: list[str] = []
    importance: float = 0.5


class ForgetRequest(BaseModel):
    topic: str


@router.post("/remember")
def remember_item(req: RememberRequest):
    """Store a new semantic memory item."""
    try:
        layer_enum = MemoryLayer[req.layer.upper()]
    except KeyError:
        layer_enum = MemoryLayer.SEMANTIC

    item = _memory_manager.remember(
        content=req.content,
        layer=layer_enum,
        tags=req.tags,
        importance=req.importance,
    )
    return {
        "success": True,
        "memory_id": item.memory_id,
        "content": item.content,
        "layer": item.layer.value,
    }


@router.get("/search")
def search_memories(q: str = Query(..., description="Query phrase"), top_k: int = 5):
    """Search memories using hybrid semantic retrieval."""
    results = _memory_manager.recall(q, top_k=top_k)
    return {
        "query": q,
        "count": len(results),
        "results": [
            {
                "memory_id": r.memory_item.memory_id,
                "content": r.memory_item.content,
                "layer": r.memory_item.layer.value,
                "score": round(r.combined_score, 4),
            }
            for r in results
        ],
    }


@router.get("/items")
def list_memory_items(layer: str | None = None):
    """List memory items."""
    layer_enum = None
    if layer:
        try:
            layer_enum = MemoryLayer[layer.upper()]
        except KeyError:
            pass

    items = _memory_manager.list_memories(layer_enum)
    return {
        "count": len(items),
        "items": [
            {
                "memory_id": i.memory_id,
                "content": i.content,
                "layer": i.layer.value,
                "created_at": i.created_at,
            }
            for i in items
        ],
    }


@router.post("/forget")
def forget_topic(req: ForgetRequest):
    """Forget all memories matching a given topic phrase."""
    count = _memory_manager.forget_topic(req.topic)
    return {"success": True, "forgot_count": count, "topic": req.topic}

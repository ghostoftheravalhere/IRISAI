"""FastAPI Router for Streaming Intelligence & Interruptible Conversation."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.streaming_planner import StreamingPlanner
from backend.brain.workflow import WorkflowEngine
from backend.voice.conversation_streamer import ConversationStreamer

router = APIRouter(prefix="/voice/stream", tags=["streaming"])

# Shared singleton instances
_streamer = ConversationStreamer()
_fake_dispatcher = AutomationDispatcher(None)
_workflow_engine = WorkflowEngine(automation_dispatcher=_fake_dispatcher, enabled=True)
_planner = StreamingPlanner(workflow_engine=_workflow_engine)


class ChunkRequest(BaseModel):
    chunk_text: str
    is_final: bool = False


@router.post("/chunk")
def process_streaming_chunk(req: ChunkRequest):
    """Process incoming streaming text chunk and return partial telemetry."""
    telemetry = _streamer.process_live_chunk(req.chunk_text, is_final=req.is_final)
    return telemetry


@router.post("/cancel")
def cancel_streaming_workflow():
    """Instantly cancel active streaming workflow."""
    cancelled = _planner.cancel_active()
    return {"success": True, "cancelled": cancelled}

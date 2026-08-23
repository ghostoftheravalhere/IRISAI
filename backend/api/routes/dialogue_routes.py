"""FastAPI Router for Natural Conversation & Dialogue Manager."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.brain.dialogue_manager import DialogueManager
from backend.automation.action_engine import ActionEngine
from backend.automation.controller import DesktopController

router = APIRouter(prefix="/dialogue", tags=["dialogue"])

# Shared DialogueManager singleton instance
_action_engine = ActionEngine(desktop_controller=DesktopController())
_dialogue_manager = DialogueManager(action_engine=_action_engine)


class UtteranceRequest(BaseModel):
    text: str
    source: str = "voice"


@router.post("/turn")
def process_dialogue_turn(req: UtteranceRequest):
    """Process a multi-turn conversational utterance."""
    res = _dialogue_manager.process_utterance(req.text, source=req.source)
    return res


@router.get("/session")
def get_session_state():
    """Retrieve active session state and focus stack."""
    session = _dialogue_manager.session
    history = session.get_history()
    top_focus = session.peek_focus()
    return {
        "state": session.state.value,
        "turn_count": len(history),
        "top_focus": top_focus.__dict__ if top_focus else None,
        "history": [
            {
                "speaker": t.speaker,
                "raw_text": t.raw_text,
                "intent": t.parsed_intent,
                "target": t.resolved_target,
                "query": t.resolved_query,
            }
            for t in history
        ],
    }


@router.post("/reset")
def reset_dialogue_session():
    """Reset active dialogue session and clear focus stack."""
    _dialogue_manager.session.reset()
    return {"success": True, "message": "Dialogue session reset."}

"""FastAPI Router for Autonomous Agent Runtime."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.agent.agent_core import AgentCore
from backend.automation.action_engine import ActionEngine
from backend.automation.controller import DesktopController

router = APIRouter(prefix="/agent", tags=["agent"])

# Shared singleton instances
_desktop_controller = DesktopController()
_action_engine = ActionEngine(desktop_controller=_desktop_controller)
_agent_core = AgentCore(action_engine=_action_engine)


class AgentGoalRequest(BaseModel):
    goal: str


@router.post("/run")
def run_autonomous_agent(req: AgentGoalRequest):
    """Launch autonomous agent loop for a goal."""
    res = _agent_core.process_goal(req.goal)
    return {
        "success": res.success,
        "goal": req.goal,
        "message": res.response,
    }


@router.get("/status")
def get_agent_status():
    """Get active agent runtime status."""
    return {
        "enabled": True,
        "tools_registered": len(_agent_core._tool_registry.list_tools()),
    }

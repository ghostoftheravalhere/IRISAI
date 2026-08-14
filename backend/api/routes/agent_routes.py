"""FastAPI Router for Autonomous Agent Runtime."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from backend.agent.agent_runtime import AgentRuntime
from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.workflow import TaskPlan, WorkflowEngine, WorkflowStep

router = APIRouter(prefix="/agent", tags=["agent"])

# Shared singleton instances
_fake_dispatcher = AutomationDispatcher(None)
_workflow_engine = WorkflowEngine(automation_dispatcher=_fake_dispatcher, enabled=True)
_runtime = AgentRuntime(workflow_engine=_workflow_engine)


class AgentGoalRequest(BaseModel):
    goal: str


@router.post("/run")
def run_autonomous_agent(req: AgentGoalRequest):
    """Launch autonomous agent loop for a goal."""
    plan = TaskPlan(
        name=f"Autonomous Plan for {req.goal}",
        steps=[WorkflowStep(intent="OPEN_APPLICATION", target="chrome")],
    )
    success = _runtime.run_agent_goal(req.goal, plan)
    return {
        "success": success,
        "goal": req.goal,
        "phase": _runtime.phase.value,
    }


@router.get("/status")
def get_agent_status():
    """Get active agent runtime status and loop phase."""
    return {
        "enabled": _runtime.enabled,
        "phase": _runtime.phase.value,
    }

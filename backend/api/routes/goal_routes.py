"""FastAPI Router for Agentic Task Execution & Goal Manager."""

from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.workflow import WorkflowEngine
from backend.goals.goal_manager import GoalManager

router = APIRouter(prefix="/goals", tags=["goals"])

# Shared WorkflowEngine and GoalManager singleton instances
_fake_dispatcher = AutomationDispatcher(None)
_workflow_engine = WorkflowEngine(automation_dispatcher=_fake_dispatcher, enabled=True)
_goal_manager = GoalManager(workflow_engine=_workflow_engine)


class CreateGoalRequest(BaseModel):
    name: str


@router.post("")
def create_and_execute_goal(req: CreateGoalRequest):
    """Create a new Agentic Goal and begin execution."""
    goal = _goal_manager.create_goal(req.name)
    success = _goal_manager.plan_and_execute(goal.goal_id)
    return {
        "success": success,
        "goal_id": goal.goal_id,
        "name": goal.name,
        "status": goal.status.value,
    }


@router.get("")
def list_goals():
    """List all registered goals."""
    goals = _goal_manager.list_goals()
    return {
        "count": len(goals),
        "goals": [
            {
                "goal_id": g.goal_id,
                "name": g.name,
                "status": g.status.value,
                "sub_plan_count": len(g.sub_plans),
            }
            for g in goals
        ],
    }


@router.get("/{goal_id}")
def get_goal_details(goal_id: str):
    """Get status, sub-plans, and real-time progress for a goal."""
    goal = _goal_manager.get_goal(goal_id)
    if not goal:
        raise HTTPException(status_code=404, detail="Goal not found.")

    progress = _goal_manager.get_progress(goal_id)
    return {
        "goal_id": goal.goal_id,
        "name": goal.name,
        "status": goal.status.value,
        "percent_complete": progress.percent_complete if progress else 0.0,
        "current_step_name": progress.current_step_name if progress else "N/A",
        "sub_plans": [p.name for p in goal.sub_plans],
    }


@router.post("/{goal_id}/pause")
def pause_goal(goal_id: str):
    """Pause an active executing goal."""
    success = _goal_manager.pause_goal(goal_id)
    return {"success": success, "goal_id": goal_id}


@router.post("/{goal_id}/resume")
def resume_goal(goal_id: str):
    """Resume execution of a paused goal."""
    success = _goal_manager.resume_goal(goal_id)
    return {"success": success, "goal_id": goal_id}


@router.post("/{goal_id}/cancel")
def cancel_goal(goal_id: str):
    """Cancel an active or pending goal."""
    success = _goal_manager.cancel_goal(goal_id)
    return {"success": success, "goal_id": goal_id}

"""Desktop Visual Interaction TaskPlan Generator."""

from __future__ import annotations

from backend.brain.workflow import TaskPlan, WorkflowStep
from backend.perception.vision_action_models import GroundedPoint
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class DesktopInteractionPlanner:
    """Builds executable TaskPlan sub-workflows for visual screen interactions."""

    def build_click_plan(self, point: GroundedPoint) -> TaskPlan:
        """Generate a TaskPlan to click at grounded screen coordinates."""
        return TaskPlan(
            name=f"Visual Click '{point.text_label}' at ({point.x}, {point.y})",
            steps=[
                WorkflowStep(
                    intent="CLICK_AT",
                    target="desktop",
                    params={"x": point.x, "y": point.y, "label": point.text_label},
                ),
            ],
        )

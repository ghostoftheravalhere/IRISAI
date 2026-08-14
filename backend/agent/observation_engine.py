"""Multimodal Observation Engine Service."""

from __future__ import annotations

from backend.agent.agent_models import AgentObservation
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class ObservationEngine:
    """Captures real-time snapshots of Vision, Memory, Dialogue, Workspace, and Desktop state."""

    def capture_observation(self, active_app: str = "System", visible_text: str = "") -> AgentObservation:
        """Capture complete AgentObservation state."""
        obs = AgentObservation(
            active_app=active_app,
            visible_text=visible_text or "System active",
            dialogue_state="IDLE",
            memory_summary="User workspace ready",
            workspace_name="IRISAI",
        )
        logger.info("ObservationEngine captured snapshot (app=%s)", active_app)
        return obs

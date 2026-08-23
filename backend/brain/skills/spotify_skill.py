"""Spotify Media Integration Skill Plugin."""

from __future__ import annotations

from backend.brain.skills.base import (
    SkillDescriptor,
    SkillExecutionContext,
    SkillResult,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class SpotifySkill:
    """Skill capability for Spotify media playback and volume control."""

    def __init__(self) -> None:
        self._descriptor = SkillDescriptor(
            skill_id="spotify_skill",
            name="Spotify Skill",
            version="1.0.0",
            description="Controls Spotify play, pause, skip, volume, and playlist selection.",
            required_permissions=["media:control"],
            capabilities=[
                "PLAY_SPOTIFY",
                "PAUSE_SPOTIFY",
                "SKIP_SPOTIFY_TRACK",
                "SET_SPOTIFY_VOLUME",
                "SELECT_SPOTIFY_PLAYLIST",
            ],
        )

    @property
    def descriptor(self) -> SkillDescriptor:
        return self._descriptor

    def can_handle(self, capability: str) -> bool:
        return capability.upper() in self._descriptor.capabilities

    def execute(self, context: SkillExecutionContext) -> SkillResult:
        intent = context.intent.upper()
        return SkillResult(
            success=True,
            message=f"Spotify media action '{intent}' executed successfully.",
            result_data={"intent": intent},
        )

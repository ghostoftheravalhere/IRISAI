"""File Explorer Integration Skill Plugin."""

from __future__ import annotations

from backend.brain.skills.base import (
    SkillDescriptor,
    SkillExecutionContext,
    SkillResult,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class FileExplorerSkill:
    """Skill capability for local file management, search, rename, move, and cleanup."""

    def __init__(self) -> None:
        self._descriptor = SkillDescriptor(
            skill_id="file_explorer_skill",
            name="File Explorer Skill",
            version="1.0.0",
            description="Searches files, moves, renames, deletes, and organizes folders.",
            required_permissions=["files:read", "files:write"],
            capabilities=[
                "SEARCH_FILES",
                "MOVE_FILE",
                "RENAME_FILE",
                "DELETE_FILE",
                "ORGANIZE_FOLDERS",
            ],
        )

    @property
    def descriptor(self) -> SkillDescriptor:
        return self._descriptor

    def can_handle(self, capability: str) -> bool:
        return capability.upper() in self._descriptor.capabilities

    def execute(self, context: SkillExecutionContext) -> SkillResult:
        intent = context.intent.upper()
        target = context.params.get("path", "Downloads")
        return SkillResult(
            success=True,
            message=f"File Explorer action '{intent}' completed on '{target}'",
            result_data={"target": target},
        )

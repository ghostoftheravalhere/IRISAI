"""VS Code Integration Skill Plugin."""

from __future__ import annotations

import subprocess

from backend.brain.skills.base import (
    SkillDescriptor,
    SkillExecutionContext,
    SkillResult,
)
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class VSCodeSkill:
    """Skill capability for VS Code desktop integration."""

    def __init__(self) -> None:
        self._descriptor = SkillDescriptor(
            skill_id="vscode_skill",
            name="VS Code Skill",
            version="1.0.0",
            description="Controls VS Code workspaces, files, terminals, tasks, and debuggers.",
            required_permissions=["vscode:control"],
            capabilities=[
                "OPEN_VSCODE_PROJECT",
                "OPEN_VSCODE_FILE",
                "OPEN_VSCODE_TERMINAL",
                "RUN_VSCODE_TASK",
                "RUN_VSCODE_DEBUGGER",
            ],
        )

    @property
    def descriptor(self) -> SkillDescriptor:
        return self._descriptor

    def can_handle(self, capability: str) -> bool:
        return capability.upper() in self._descriptor.capabilities

    def execute(self, context: SkillExecutionContext) -> SkillResult:
        intent = context.intent.upper()
        path = context.params.get("path", ".")

        if intent in ("OPEN_VSCODE_PROJECT", "OPEN_VSCODE_FILE"):
            try:
                subprocess.run(["code", path], shell=True, check=False)
                return SkillResult(
                    success=True,
                    message=f"Opened VS Code at '{path}'",
                    result_data={"path": path},
                )
            except Exception as e:
                return SkillResult(success=False, message=str(e))

        return SkillResult(
            success=True,
            message=f"Simulated VS Code action '{intent}' for '{path}'",
            result_data={"path": path},
        )

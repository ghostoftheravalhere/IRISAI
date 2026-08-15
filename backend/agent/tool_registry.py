"""Tool abstraction protocol, tool descriptors, and central ToolRegistry."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
from typing import Any, Protocol

from backend.agent.policy_engine import PermissionLevel
from backend.agent.task_state import TaskState
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class ToolDescriptor:
    """Self-describing metadata schema for a Tool."""

    tool_id: str
    name: str
    description: str
    permission_level: PermissionLevel = PermissionLevel.SAFE
    input_schema: dict[str, Any] = field(default_factory=dict)
    output_schema: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class ToolResult:
    """Standardized result returned by a Tool execution."""

    success: bool
    message: str
    data: dict[str, Any] = field(default_factory=dict)
    error_code: str | None = None


class Tool(Protocol):
    """Protocol interface defining an executable agent Tool capability."""

    @property
    def descriptor(self) -> ToolDescriptor:
        """Return the tool metadata descriptor."""
        ...

    def execute(self, params: dict[str, Any], task_state: TaskState | None = None) -> ToolResult:
        """Execute tool capability with provided parameters and task state."""
        ...


class ToolRegistry:
    """Central registry managing tool registration, lookup, and metadata discovery."""

    def __init__(self) -> None:
        self._tools: dict[str, Tool] = {}
        self._lock = RLock()

    def register_tool(self, tool: Tool) -> bool:
        """Register a Tool instance."""
        desc = tool.descriptor
        with self._lock:
            self._tools[desc.name.lower()] = tool
            self._tools[desc.tool_id.lower()] = tool
            logger.info("Registered Tool: '%s' (id='%s', permission='%s')", desc.name, desc.tool_id, desc.permission_level.value)
            return True

    def get_tool(self, name_or_id: str) -> Tool | None:
        """Retrieve registered Tool by name or tool_id."""
        with self._lock:
            return self._tools.get(name_or_id.lower().strip())

    def list_descriptors(self) -> list[ToolDescriptor]:
        """List descriptors for all unique registered tools."""
        with self._lock:
            unique_tools = set(self._tools.values())
            return [t.descriptor for t in unique_tools]

    def has_tool(self, name_or_id: str) -> bool:
        """Check if tool is registered."""
        with self._lock:
            return name_or_id.lower().strip() in self._tools

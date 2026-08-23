"""Multi-Application Coordinator & Window Relationship Graph Subsystem."""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
import time
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class WindowRelationship:
    """Represents a window and its hierarchical parent-child relationships."""

    hwnd: int
    title: str
    app_name: str
    parent_hwnd: int | None = None
    is_modal: bool = False
    is_child: bool = False
    role: str = "Window"  # "Window", "Dialog", "Terminal", "Tab", "FloatingTool"


@dataclass
class AppGraphNode:
    """Represents an active application process and its associated windows."""

    app_name: str
    pid: int = 0
    active_windows: list[WindowRelationship] = field(default_factory=list)
    child_dialogs: list[WindowRelationship] = field(default_factory=list)
    dependencies: list[str] = field(default_factory=list)


class MultiApplicationCoordinator:
    """Coordinates multi-application dependencies, window hierarchies, focus history, and restore stacks."""

    def __init__(self) -> None:
        self._app_graph: dict[str, AppGraphNode] = {}
        self._focus_history: list[str] = []
        self._restore_stack: list[int] = []
        self._lock = RLock()
        self._seed_default_graph()

    def _seed_default_graph(self) -> None:
        """Seed default active application nodes."""
        chrome_node = AppGraphNode(
            app_name="chrome",
            pid=1001,
            active_windows=[WindowRelationship(hwnd=101, title="Google Chrome", app_name="chrome")],
            child_dialogs=[WindowRelationship(hwnd=102, title="Save As", app_name="chrome", is_modal=True, is_child=True, role="Dialog")],
        )
        vscode_node = AppGraphNode(
            app_name="vscode",
            pid=1002,
            active_windows=[WindowRelationship(hwnd=201, title="Visual Studio Code", app_name="vscode")],
            child_dialogs=[WindowRelationship(hwnd=202, title="Terminal", app_name="vscode", is_child=True, role="Terminal")],
            dependencies=["chrome"],
        )
        self._app_graph["chrome"] = chrome_node
        self._app_graph["vscode"] = vscode_node

    def get_application_graph(self) -> list[dict[str, Any]]:
        """Return application dependency graph representation."""
        with self._lock:
            res: list[dict[str, Any]] = []
            for name, node in self._app_graph.items():
                res.append(
                    {
                        "app_name": node.app_name,
                        "pid": node.pid,
                        "window_count": len(node.active_windows),
                        "dialog_count": len(node.child_dialogs),
                        "dependencies": node.dependencies,
                    }
                )
            return res

    def get_window_relationships(self) -> list[dict[str, Any]]:
        """Return active window relationship hierarchy."""
        with self._lock:
            windows: list[dict[str, Any]] = []
            for node in self._app_graph.values():
                for win in node.active_windows + node.child_dialogs:
                    windows.append(
                        {
                            "hwnd": win.hwnd,
                            "title": win.title,
                            "app_name": win.app_name,
                            "parent_hwnd": win.parent_hwnd,
                            "is_modal": win.is_modal,
                            "role": win.role,
                        }
                    )
            return windows

    def register_window_focus(self, app_name: str, hwnd: int) -> None:
        """Register window focus change in history stack."""
        with self._lock:
            self._focus_history.append(app_name)
            self._restore_stack.append(hwnd)
            logger.info("MultiApplicationCoordinator registered focus on '%s' (HWND %d)", app_name, hwnd)

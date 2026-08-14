"""Native Application Integration Data Models."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any


@dataclass
class VSCodeAction:
    """Action model for VS Code integration."""

    action: str  # "OPEN_PROJECT", "OPEN_FILE", "OPEN_TERMINAL", "RUN_TASK", "RUN_DEBUGGER"
    path: str = ""
    task_name: str = ""


@dataclass
class GitAction:
    """Action model for Git integration."""

    action: str  # "STATUS", "DIFF", "COMMIT", "BRANCH", "PULL", "PUSH", "LOG"
    commit_message: str = ""
    branch_name: str = ""


@dataclass
class GitHubAction:
    """Action model for GitHub integration."""

    action: str  # "CREATE_ISSUE", "VIEW_ISSUES", "OPEN_PR", "REVIEW_PR"
    title: str = ""
    body: str = ""


@dataclass
class BrowserAction:
    """Action model for Browser integration."""

    action: str  # "OPEN_TAB", "ADD_BOOKMARK", "SEARCH", "READ_TITLE"
    url: str = ""
    query: str = ""


@dataclass
class SpotifyAction:
    """Action model for Spotify media integration."""

    action: str  # "PLAY", "PAUSE", "SKIP", "VOLUME", "PLAYLIST"
    volume: int = 50
    playlist_name: str = ""


@dataclass
class NotionAction:
    """Action model for Notion integration."""

    action: str  # "OPEN_PAGE", "DAILY_NOTES", "SEARCH"
    query: str = ""


@dataclass
class FileExplorerAction:
    """Action model for File Explorer integration."""

    action: str  # "SEARCH", "MOVE", "RENAME", "DELETE", "ORGANIZE"
    source_path: str = ""
    target_path: str = ""

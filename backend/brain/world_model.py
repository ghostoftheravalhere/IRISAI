"""General IRIS World Model & Context Snapshot Subsystem for IRIS AI V4.

Provides a unified, real-time structured operational view of the environment across:
- PERSON
- APPLICATION
- WINDOW
- FILE
- EMAIL
- CALENDAR_EVENT
- GITHUB_ACTIVITY
- UI_TARGET
- GAZE_TARGET
- TASK

Qwen and AgentCore may query or reason over WorldModelSnapshots,
but WorldModel remains deterministic and strictly structured.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from threading import RLock
import time
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PersonState:
    person_id: str | None = None
    name: str | None = None
    status: str = "UNKNOWN"  # KNOWN | UNKNOWN | PENDING_IDENTIFICATION | PENDING_ENROLLMENT | DO_NOT_REMEMBER
    confidence: float = 0.0
    last_seen: float = field(default_factory=time.time)


@dataclass
class ApplicationState:
    active_app: str = "Desktop"
    running_apps: list[str] = field(default_factory=list)


@dataclass
class WindowState:
    title: str = "Desktop Workspace"
    bounds: dict[str, int] = field(default_factory=lambda: {"x": 0, "y": 0, "width": 1920, "height": 1080})


@dataclass
class FileState:
    active_file: str | None = None
    last_referenced_file: str | None = None


@dataclass
class EmailState:
    unread_count: int = 0
    pending_summary: str | None = None


@dataclass
class CalendarState:
    today_count: int = 0
    next_event: str | None = None


@dataclass
class GitHubState:
    repo: str = "ghostoftheravalhere/IRISAI"
    open_issues_count: int = 0
    ci_status: str = "passing"


@dataclass
class GazeTargetState:
    x: float = 960.0
    y: float = 540.0
    target_element: str | None = None


@dataclass
class UITargetState:
    visible_elements: list[dict] = field(default_factory=list)
    focused_element: dict | None = None
    gaze_target: dict | None = None
    last_referenced_target: dict | None = None


@dataclass
class ActiveTaskState:
    goal: str | None = None
    status: str = "IDLE"
    current_step: int = 0
    total_steps: int = 0


@dataclass(frozen=True)
class WorldModelSnapshot:
    """Unified operational snapshot frame of the environment."""

    timestamp: float
    person: PersonState
    application: ApplicationState
    window: WindowState
    file: FileState
    email: EmailState
    calendar: CalendarState
    github: GitHubState
    ui_target: UITargetState
    gaze_target: GazeTargetState
    task: ActiveTaskState

    def to_dict(self, redact_biometrics: bool = True) -> dict[str, Any]:
        """Return clean structured dict representation of the snapshot."""
        return {
            "timestamp": self.timestamp,
            "person": {
                "person_id": self.person.person_id,
                "name": self.person.name,
                "status": self.person.status,
                "confidence": round(self.person.confidence, 2),
            },
            "application": {
                "active_app": self.application.active_app,
                "running_apps": list(self.application.running_apps),
            },
            "window": {
                "title": self.window.title,
                "bounds": dict(self.window.bounds),
            },
            "file": {
                "active_file": self.file.active_file,
                "last_referenced_file": self.file.last_referenced_file,
            },
            "email": {
                "unread_count": self.email.unread_count,
                "pending_summary": self.email.pending_summary,
            },
            "calendar": {
                "today_count": self.calendar.today_count,
                "next_event": self.calendar.next_event,
            },
            "github": {
                "repo": self.github.repo,
                "open_issues_count": self.github.open_issues_count,
                "ci_status": self.github.ci_status,
            },
            "gaze_target": {
                "x": self.gaze_target.x,
                "y": self.gaze_target.y,
                "target_element": self.gaze_target.target_element,
            },
            "task": {
                "goal": self.task.goal,
                "status": self.task.status,
                "step": f"{self.task.current_step}/{self.task.total_steps}",
            },
        }


class WorldModel:
    """Deterministic, thread-safe World Model managing unified operational state."""

    def __init__(self) -> None:
        self._lock = RLock()
        self._person = PersonState()
        self._application = ApplicationState()
        self._window = WindowState()
        self._file = FileState()
        self._email = EmailState()
        self._calendar = CalendarState()
        self._github = GitHubState()
        self._ui_target = UITargetState()
        self._gaze_target = GazeTargetState()
        self._task = ActiveTaskState()

    def update_person(self, person_id: str | None, name: str | None, status: str, confidence: float) -> None:
        with self._lock:
            self._person = PersonState(
                person_id=person_id,
                name=name,
                status=status,
                confidence=confidence,
                last_seen=time.time(),
            )

    def update_application(self, active_app: str, running_apps: list[str] | None = None) -> None:
        with self._lock:
            self._application.active_app = active_app
            if running_apps is not None:
                self._application.running_apps = list(running_apps)

    def update_window(self, title: str, bounds: dict[str, int] | None = None) -> None:
        with self._lock:
            self._window.title = title
            if bounds:
                self._window.bounds = dict(bounds)

    def update_file(self, active_file: str | None = None, last_referenced_file: str | None = None) -> None:
        with self._lock:
            if active_file is not None:
                self._file.active_file = active_file
            if last_referenced_file is not None:
                self._file.last_referenced_file = last_referenced_file

    def update_email_state(self, unread_count: int, pending_summary: str | None = None) -> None:
        with self._lock:
            self._email.unread_count = unread_count
            if pending_summary is not None:
                self._email.pending_summary = pending_summary

    def update_calendar_state(self, today_count: int, next_event: str | None = None) -> None:
        with self._lock:
            self._calendar.today_count = today_count
            if next_event is not None:
                self._calendar.next_event = next_event

    def update_github_state(self, repo: str, issue_count: int, ci_status: str) -> None:
        with self._lock:
            self._github.repo = repo
            self._github.open_issues_count = issue_count
            self._github.ci_status = ci_status

    def update_gaze_target(self, x: float, y: float, target_element: str | None = None) -> None:
        with self._lock:
            self._gaze_target.x = x
            self._gaze_target.y = y
            self._gaze_target.target_element = target_element

    def update_ui_target(
        self,
        active_app: str | None = None,
        active_window: str | None = None,
        visible_elements: list[dict] | None = None,
        focused_element: dict | None = None,
        gaze_target: dict | None = None,
        last_referenced_target: dict | None = None,
    ) -> None:
        with self._lock:
            if active_app is not None:
                self._application.active_app = active_app
            if active_window is not None:
                self._window.title = active_window
            if visible_elements is not None:
                self._ui_target.visible_elements = list(visible_elements)
            if focused_element is not None:
                self._ui_target.focused_element = dict(focused_element)
            if last_referenced_target is not None:
                self._ui_target.last_referenced_target = dict(last_referenced_target)

    def update_task_state(self, goal: str | None, status: str, step: int = 0, total_steps: int = 0) -> None:
        with self._lock:
            self._task.goal = goal
            self._task.status = status
            self._task.current_step = step
            self._task.total_steps = total_steps

    def snapshot(self) -> WorldModelSnapshot:
        with self._lock:
            return WorldModelSnapshot(
                timestamp=time.time(),
                person=PersonState(
                    person_id=self._person.person_id,
                    name=self._person.name,
                    status=self._person.status,
                    confidence=self._person.confidence,
                    last_seen=self._person.last_seen,
                ),
                application=ApplicationState(
                    active_app=self._application.active_app,
                    running_apps=list(self._application.running_apps),
                ),
                window=WindowState(
                    title=self._window.title,
                    bounds=dict(self._window.bounds),
                ),
                file=FileState(
                    active_file=self._file.active_file,
                    last_referenced_file=self._file.last_referenced_file,
                ),
                email=EmailState(
                    unread_count=self._email.unread_count,
                    pending_summary=self._email.pending_summary,
                ),
                calendar=CalendarState(
                    today_count=self._calendar.today_count,
                    next_event=self._calendar.next_event,
                ),
                github=GitHubState(
                    repo=self._github.repo,
                    open_issues_count=self._github.open_issues_count,
                    ci_status=self._github.ci_status,
                ),
                ui_target=UITargetState(
                    visible_elements=list(self._ui_target.visible_elements),
                    focused_element=dict(self._ui_target.focused_element) if self._ui_target.focused_element else None,
                    gaze_target=dict(self._ui_target.gaze_target) if self._ui_target.gaze_target else None,
                    last_referenced_target=dict(self._ui_target.last_referenced_target) if self._ui_target.last_referenced_target else None,
                ),
                gaze_target=GazeTargetState(
                    x=self._gaze_target.x,
                    y=self._gaze_target.y,
                    target_element=self._gaze_target.target_element,
                ),
                task=ActiveTaskState(
                    goal=self._task.goal,
                    status=self._task.status,
                    current_step=self._task.current_step,
                    total_steps=self._task.total_steps,
                ),
            )


world_model = WorldModel()

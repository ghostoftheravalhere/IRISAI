"""Unit tests for Browser Search Command Enhancement & Deterministic Window Focus Synchronization."""

from __future__ import annotations

from backend.automation.controller import DesktopController
from backend.automation.dispatcher import AutomationDispatcher
from backend.brain.context_manager import ContextManager
from backend.brain.intent_manager import IntentManager
from backend.brain.orchestrator import BrainOrchestrator, OrchestrationRequest
from backend.brain.skills.builtin import DesktopAutomationSkill
from backend.brain.skills.registry import SkillRegistry
from backend.brain.workflow import WorkflowEngine
from backend.brain.workflow_events import WorkflowFailedEvent
from backend.core.events.bus import EventBus
from backend.voice.command_parser import IntentParserService, VoiceIntentType


class _FakeDesktop(DesktopController):
    def __init__(self, fail_window_active: bool = False):
        super().__init__()
        self.actions = []
        self.active_app = None
        self.fail_window_active = fail_window_active

    def open_application(self, app_name: str) -> bool:
        self.actions.append(f"OPEN:{app_name}")
        self.active_app = app_name
        return True

    def open_chrome(self) -> bool:
        self.actions.append("OPEN:chrome")
        self.active_app = "chrome"
        return True

    def open_edge(self) -> bool:
        self.actions.append("OPEN:edge")
        self.active_app = "edge"
        return True

    def open_settings(self) -> bool:
        self.actions.append("OPEN:settings")
        self.active_app = "settings"
        return True

    def wait_for_window(self, application_name: str, timeout_sec: float = 3.0) -> bool:
        self.actions.append(f"WAIT:{application_name}")
        return True

    def activate_window(self, application_name: str) -> bool:
        self.actions.append(f"ACTIVATE:{application_name}")
        self.active_app = application_name
        return True

    def is_window_active(self, application_name: str) -> bool:
        self.actions.append(f"VERIFY:{application_name}")
        if self.fail_window_active:
            return False
        return True

    def hotkey(self, *keys: str) -> bool:
        self.actions.append(f"HOTKEY:{'+'.join(keys)}")
        return True

    def press(self, key: str, presses: int = 1) -> bool:
        self.actions.append(f"PRESS:{key}")
        return True

    def type_text(self, text: str) -> bool:
        self.actions.append(f"TYPE:{text}")
        return True

    def browser_search(self, application: str, query: str) -> bool:
        self.actions.append(f"SEARCH:{application}:{query}")
        return True


def test_intent_parser_browser_search_examples():
    parser = IntentParserService()

    intent1 = parser.parse("Open Chrome search ChatGPT")
    assert intent1.intent == VoiceIntentType.BROWSER_SEARCH
    assert intent1.target == "chrome"
    assert intent1.query == "ChatGPT"

    intent2 = parser.parse("Open Chrome and search weather tomorrow")
    assert intent2.intent == VoiceIntentType.BROWSER_SEARCH
    assert intent2.target == "chrome"
    assert intent2.query == "weather tomorrow"

    intent3 = parser.parse("Search Python decorators in Chrome")
    assert intent3.intent == VoiceIntentType.BROWSER_SEARCH
    assert intent3.target == "chrome"
    assert intent3.query == "Python decorators"

    intent4 = parser.parse("Open Edge search GitHub Copilot")
    assert intent4.intent == VoiceIntentType.BROWSER_SEARCH
    assert intent4.target == "edge"
    assert intent4.query == "GitHub Copilot"

    intent5 = parser.parse("Search Stack Overflow in Edge")
    assert intent5.intent == VoiceIntentType.BROWSER_SEARCH
    assert intent5.target == "edge"
    assert intent5.query == "Stack Overflow"

    intent6 = parser.parse("Search AI agents in Chrome")
    assert intent6.intent == VoiceIntentType.BROWSER_SEARCH
    assert intent6.target == "chrome"
    assert intent6.query == "AI agents"

    intent7 = parser.parse("Open settings search for camera")
    assert intent7.intent == VoiceIntentType.BROWSER_SEARCH
    assert intent7.target == "settings"
    assert intent7.query == "camera"

    intent8 = parser.parse("Open setting search camera")
    assert intent8.intent == VoiceIntentType.BROWSER_SEARCH
    assert intent8.target == "settings"
    assert intent8.query == "camera"


def test_invalid_empty_query_rejection():
    parser = IntentParserService()

    # Searching without query phrase should fall back to OPEN_CHROME or NO_INTENT
    empty_search = parser.parse("Open Chrome search")
    assert empty_search.intent != VoiceIntentType.BROWSER_SEARCH
    assert empty_search.query is None


def test_backward_compatibility_existing_commands():
    parser = IntentParserService()

    chrome = parser.parse("Open Chrome")
    assert chrome.intent == VoiceIntentType.OPEN_CHROME
    assert chrome.target == "chrome"

    close_chrome = parser.parse("Close Chrome")
    assert close_chrome.intent == VoiceIntentType.CLOSE_APPLICATION
    assert close_chrome.target == "chrome"

    edge = parser.parse("Open Edge")
    assert edge.intent == VoiceIntentType.OPEN_APPLICATION
    assert edge.target == "edge"

    notepad = parser.parse("Open Notepad")
    assert notepad.intent == VoiceIntentType.OPEN_NOTEPAD
    assert notepad.target == "notepad"

    settings = parser.parse("Open settings")
    assert settings.intent == VoiceIntentType.OPEN_APPLICATION
    assert settings.target == "settings"


def test_settings_search_taskplan_execution():
    fake_desktop = _FakeDesktop()
    dispatcher = AutomationDispatcher(fake_desktop)
    workflow_engine = WorkflowEngine(automation_dispatcher=dispatcher, enabled=True)

    orchestrator = BrainOrchestrator(
        intent_manager=IntentManager(),
        context_manager=ContextManager(),
        automation_dispatcher=dispatcher,
        workflow_engine=workflow_engine,
        enabled=True,
    )

    parser = IntentParserService()
    intent = parser.parse("Open settings search for camera")
    req = OrchestrationRequest(source="voice", intent=intent, raw_transcript="Open settings search for camera")

    resp = orchestrator.process_intent(req)
    assert resp.success is True
    assert fake_desktop.actions == [
        "OPEN:settings",
        "WAIT:settings",
        "ACTIVATE:settings",
        "VERIFY:settings",
        "HOTKEY:ctrl+f",
        "TYPE:camera",
        "PRESS:enter",
    ]


def test_brain_orchestrator_browser_search_taskplan_execution():
    fake_desktop = _FakeDesktop()
    dispatcher = AutomationDispatcher(fake_desktop)
    workflow_engine = WorkflowEngine(automation_dispatcher=dispatcher, enabled=True)

    orchestrator = BrainOrchestrator(
        intent_manager=IntentManager(),
        context_manager=ContextManager(),
        automation_dispatcher=dispatcher,
        workflow_engine=workflow_engine,
        enabled=True,
    )

    parser = IntentParserService()
    intent = parser.parse("Open Chrome search ChatGPT")
    req = OrchestrationRequest(source="voice", intent=intent, raw_transcript="Open Chrome search ChatGPT")

    resp = orchestrator.process_intent(req)
    assert resp.success is True
    assert resp.intent == VoiceIntentType.BROWSER_SEARCH.value

    # Verify deterministic window synchronization sequence
    assert fake_desktop.actions == [
        "OPEN:chrome",
        "WAIT:chrome",
        "ACTIVATE:chrome",
        "VERIFY:chrome",
        "HOTKEY:ctrl+l",
        "TYPE:ChatGPT",
        "PRESS:enter",
    ]


def test_browser_focus_when_edge_already_running():
    fake_desktop = _FakeDesktop()
    fake_desktop.active_app = "edge"  # Edge active beforehand

    dispatcher = AutomationDispatcher(fake_desktop)
    workflow_engine = WorkflowEngine(automation_dispatcher=dispatcher, enabled=True)

    orchestrator = BrainOrchestrator(
        intent_manager=IntentManager(),
        context_manager=ContextManager(),
        automation_dispatcher=dispatcher,
        workflow_engine=workflow_engine,
        enabled=True,
    )

    parser = IntentParserService()
    intent = parser.parse("Open Chrome search chapter")
    req = OrchestrationRequest(source="voice", intent=intent, raw_transcript="Open Chrome search chapter")

    resp = orchestrator.process_intent(req)
    assert resp.success is True
    assert fake_desktop.active_app == "chrome"
    assert "ACTIVATE:chrome" in fake_desktop.actions
    assert "VERIFY:chrome" in fake_desktop.actions


def test_browser_focus_activation_failure_publishes_event():
    fake_desktop = _FakeDesktop(fail_window_active=True)
    dispatcher = AutomationDispatcher(fake_desktop)

    events = []
    event_bus = EventBus()
    event_bus.subscribe(WorkflowFailedEvent, lambda e: events.append(e))

    workflow_engine = WorkflowEngine(automation_dispatcher=dispatcher, event_bus=event_bus, enabled=True)

    orchestrator = BrainOrchestrator(
        intent_manager=IntentManager(),
        context_manager=ContextManager(),
        automation_dispatcher=dispatcher,
        workflow_engine=workflow_engine,
        enabled=True,
    )

    parser = IntentParserService()
    intent = parser.parse("Open Chrome search failed_focus")
    req = OrchestrationRequest(source="voice", intent=intent, raw_transcript="Open Chrome search failed_focus")

    resp = orchestrator.process_intent(req)
    assert resp.success is False
    assert len(events) == 1
    assert "VERIFY_WINDOW_ACTIVE" in events[0].reason or "failed" in events[0].reason


def test_automation_dispatcher_browser_search_direct():
    fake_desktop = _FakeDesktop()
    dispatcher = AutomationDispatcher(fake_desktop)

    parser = IntentParserService()
    intent = parser.parse("Open Edge search GitHub")

    result = dispatcher.dispatch(intent)
    assert result.success is True
    assert "SEARCH:edge:GitHub" in fake_desktop.actions


def test_skill_registry_browser_search_execution():
    fake_desktop = _FakeDesktop()
    dispatcher = AutomationDispatcher(fake_desktop)
    registry = SkillRegistry(enabled=True)
    registry.register_skill(DesktopAutomationSkill(dispatcher))

    res = registry.execute_intent("BROWSER_SEARCH", params={"application": "chrome", "query": "OpenAI"})
    assert res.success is True
    assert "SEARCH:chrome:OpenAI" in fake_desktop.actions

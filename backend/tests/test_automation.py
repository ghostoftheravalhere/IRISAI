"""Desktop automation unit tests."""

from __future__ import annotations

from backend.automation.controller import ApplicationCloseResult, DesktopController
from backend.automation.dispatcher import AutomationDispatcher
from backend.voice.command_parser import IntentParserService, VoiceIntent, VoiceIntentType


class _FakeDesktop(DesktopController):
    def __init__(self) -> None:
        super().__init__()
        self.calls: list[str] = []
        self.close_results: dict[str, ApplicationCloseResult] = {}

    def open_chrome(self) -> bool:
        self.calls.append("open_chrome")
        return True

    def open_notepad(self) -> bool:
        self.calls.append("open_notepad")
        return True

    def open_edge(self) -> bool:
        self.calls.append("open_edge")
        return True

    def close_window(self) -> bool:
        self.calls.append("close_window")
        return True

    def close_application(self, application_name: str) -> ApplicationCloseResult:
        self.calls.append(f"close_application:{application_name}")
        return self.close_results.get(
            application_name,
            ApplicationCloseResult(True, "closed", f"{application_name}.exe"),
        )

    def scroll(self, amount: int) -> bool:
        self.calls.append(f"scroll:{amount}")
        return True

    def press(self, key: str, presses: int = 1) -> bool:
        self.calls.append(f"press:{key}:{presses}")
        return True

    def hotkey(self, *keys: str) -> bool:
        self.calls.append("hotkey:" + "+".join(keys))
        return True

    def mute(self) -> bool:
        self.calls.append("mute")
        return True

    def take_screenshot(self) -> bool:
        self.calls.append("take_screenshot")
        return True


def test_automation_dispatcher_maps_core_intents():
    desktop = _FakeDesktop()
    dispatcher = AutomationDispatcher(desktop)
    parser = IntentParserService()

    mapping = {
        "scroll up": ("scroll:5", "Scrolled up"),
        "scroll down": ("scroll:-5", "Scrolled down"),
        "copy": ("hotkey:ctrl+c", "Copied"),
        "paste": ("hotkey:ctrl+v", "Pasted"),
        "close window": ("close_window", "Window closed"),
        "volume up": ("press:volumeup:2", "Volume up"),
        "volume down": ("press:volumedown:2", "Volume down"),
        "mute": ("mute", "Muted"),
        "take screenshot": ("take_screenshot", "Screenshot saved"),
        "open chrome": ("open_chrome", "Chrome opened"),
        "open notepad": ("open_notepad", "Notepad opened"),
    }

    for phrase, (expected_call, expected_message) in mapping.items():
        result = dispatcher.dispatch(parser.parse(phrase))
        assert result.success is True, phrase
        assert result.intent != VoiceIntentType.NO_INTENT
        assert desktop.calls[-1] == expected_call
        assert result.message == expected_message


def test_automation_dispatcher_closes_named_app_not_active_window():
    desktop = _FakeDesktop()
    dispatcher = AutomationDispatcher(desktop)
    parser = IntentParserService()

    close_chrome = dispatcher.dispatch(parser.parse("close chrome"))
    close_notepad = dispatcher.dispatch(parser.parse("close notepad"))
    bare_close = dispatcher.dispatch(parser.parse("close"))

    assert close_chrome.success is True
    assert close_chrome.message == "Chrome closed"
    assert close_chrome.intent == VoiceIntentType.CLOSE_APPLICATION
    assert close_notepad.success is True
    assert close_notepad.message == "Notepad closed"
    assert bare_close.success is True
    assert bare_close.message == "Window closed"
    assert desktop.calls == [
        "close_application:chrome",
        "close_application:notepad",
        "close_window",
    ]


def test_automation_dispatcher_reports_app_not_running():
    desktop = _FakeDesktop()
    desktop.close_results["chrome"] = ApplicationCloseResult(False, "not_running", "chrome.exe")
    dispatcher = AutomationDispatcher(desktop)
    parser = IntentParserService()

    result = dispatcher.dispatch(parser.parse("close chrome"))
    assert result.success is False
    assert result.message == "Chrome is not running."


def test_automation_dispatcher_opens_and_closes_edge_by_target():
    desktop = _FakeDesktop()
    dispatcher = AutomationDispatcher(desktop)

    opened = dispatcher.dispatch(
        VoiceIntent(VoiceIntentType.OPEN_APPLICATION, "Open Edge", 0.9, "edge")
    )
    closed = dispatcher.dispatch(
        VoiceIntent(VoiceIntentType.CLOSE_APPLICATION, "Close Edge", 0.9, "edge")
    )

    assert opened.success is True
    assert opened.message == "Edge opened"
    assert closed.success is True
    assert closed.message == "Edge closed"
    assert desktop.calls == ["open_edge", "close_application:edge"]


def test_desktop_controller_resolves_process_names():
    controller = DesktopController()
    assert controller._resolve_process_name("chrome") in {"chrome.exe", "Google Chrome", "chrome"}
    assert controller._resolve_process_name("edge") in {"msedge.exe", "Microsoft Edge", "microsoft-edge"}
    assert controller._resolve_process_name("notepad") in {"notepad.exe", "TextEdit", "gedit"}
    assert controller._resolve_process_name("unknown-app") is None


def test_close_application_reports_not_running(monkeypatch):
    controller = DesktopController()
    monkeypatch.setattr(controller, "is_application_running", lambda _name: False)
    result = controller.close_application("chrome")
    assert result.success is False
    assert result.status == "not_running"


def test_close_application_uses_graceful_then_force(monkeypatch):
    controller = DesktopController()
    calls: list[str] = []
    running_checks = {"count": 0}

    def fake_running(_name: str) -> bool:
        # First check: running. After graceful wait checks: still running once, then exited after force.
        running_checks["count"] += 1
        if running_checks["count"] == 1:
            return True
        return False

    monkeypatch.setattr(controller, "is_application_running", lambda name: fake_running(name))
    monkeypatch.setattr(
        controller,
        "_close_application_windows",
        lambda process_name: calls.append(f"wm_close:{process_name}") or True,
    )
    monkeypatch.setattr(
        controller,
        "_wait_until_exited",
        lambda process_name, timeout: calls.append(f"wait:{process_name}:{timeout}") or False,
    )
    monkeypatch.setattr(
        controller,
        "_force_kill_windows",
        lambda process_name: calls.append(f"force:{process_name}") or True,
    )
    monkeypatch.setattr(controller, "_resolve_process_name", lambda name: "chrome.exe")

    # Bypass platform branch by forcing Windows path helpers only.
    import sys

    monkeypatch.setattr(sys, "platform", "win32")
    result = controller.close_application("chrome")
    assert result.success is True
    assert result.status == "closed"
    assert calls[0] == "wm_close:chrome.exe"
    assert calls[1].startswith("wait:chrome.exe:")
    assert calls[2] == "force:chrome.exe"

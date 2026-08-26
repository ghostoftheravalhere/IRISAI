"""Unit and integration tests for Universal Application Open & Close Resolution."""

import sys
from types import ModuleType
from unittest.mock import MagicMock, patch

if "psutil" not in sys.modules:
    _psutil_mock = ModuleType("psutil")
    _psutil_mock.process_iter = MagicMock(return_value=[])
    _psutil_mock.pid_exists = MagicMock(return_value=False)
    sys.modules["psutil"] = _psutil_mock

import pytest
from backend.automation.app_resolver import (
    DesktopAppResolver,
    ResolvedAppTarget,
    ResolvedRunningApp,
    PROTECTED_PROCESSES,
    app_resolver,
)
from backend.automation.controller import DesktopController, ApplicationCloseResult
from backend.automation.dispatcher import AutomationDispatcher, AutomationResult
from backend.voice.command_parser import IntentParserService, VoiceIntentType, VoiceIntent


def test_resolver_resolve_known_apps():
    """Test that canonical known apps resolve correctly."""
    resolver = DesktopAppResolver()
    for raw, key in [
        ("Microsoft Word", "word"),
        ("ms word", "word"),
        ("winword", "word"),
        ("Microsoft Edge", "edge"),
        ("ms edge", "edge"),
        ("Google Chrome", "chrome"),
        ("chrome", "chrome"),
        ("Windows Notepad", "notepad"),
        ("notepad", "notepad"),
        ("Excel", "excel"),
        ("PowerPoint", "powerpoint"),
        ("Microsoft PowerPoint", "powerpoint"),
        ("power point", "powerpoint"),
        ("Settings", "settings"),
        ("Windows Settings", "settings"),
        ("system settings", "settings"),
    ]:
        assert resolver.resolve_app_key(raw) == key, f"Failed for {raw}"


def test_resolver_settings_uri_protocol():
    """Test that settings resolves directly to ms-settings: URI scheme, avoiding third-party shortcuts."""
    resolver = DesktopAppResolver()
    for query in ["settings", "open settings", "Windows Settings", "system settings", "setting"]:
        target = resolver.resolve_app_target(query)
        assert target.found is True
        assert target.launch_type == "uri"
        assert target.target_path == "ms-settings:"
        assert target.source == "Windows URI Protocol"


def test_resolver_nonexistent_app():
    """Test that non-existent applications return found=False."""
    resolver = DesktopAppResolver()
    target = resolver.resolve_app_target("NonExistentFakeApp12345")
    assert target.found is False
    assert "couldn't find" in (target.error_message or "").lower() or "not installed" in (target.error_message or "").lower()


def test_resolver_protected_processes():
    """Test that core system and IRIS processes are protected from voice closure."""
    resolver = DesktopAppResolver()
    for sys_proc in ["svchost", "csrss", "dwm", "python", "electron", "iris_backend", "services", "lsass"]:
        res = resolver.resolve_running_app(sys_proc)
        assert res.matched is False, f"Protected process {sys_proc} should not be resolved for closure"
        assert res.source == "protected_process"


def test_resolve_running_app_mocked():
    """Test dynamic matching against running process list."""
    resolver = DesktopAppResolver()

    mock_procs = [
        MagicMock(info={"pid": 1001, "name": "WINWORD.EXE", "exe": r"C:\Program Files\Office\WINWORD.EXE"}),
        MagicMock(info={"pid": 2002, "name": "msedge.exe", "exe": r"C:\Program Files\Edge\msedge.exe"}),
        MagicMock(info={"pid": 3003, "name": "POWERPNT.EXE", "exe": r"C:\Program Files\Office\POWERPNT.EXE"}),
        MagicMock(info={"pid": 4004, "name": "EXCEL.EXE", "exe": r"C:\Program Files\Office\EXCEL.EXE"}),
    ]

    with patch("psutil.process_iter", return_value=mock_procs):
        # 1. Spoken as "Microsoft Word"
        res_word = resolver.resolve_running_app("Microsoft Word")
        assert res_word.matched is True
        assert 1001 in res_word.pids
        assert "WINWORD.EXE" in res_word.process_names

        # 2. Spoken as "Microsoft PowerPoint"
        res_ppt = resolver.resolve_running_app("Microsoft PowerPoint")
        assert res_ppt.matched is True
        assert 3003 in res_ppt.pids
        assert "POWERPNT.EXE" in res_ppt.process_names

        # 3. Spoken as "power point"
        res_ppt_space = resolver.resolve_running_app("power point")
        assert res_ppt_space.matched is True
        assert 3003 in res_ppt_space.pids

        # 4. Spoken as "Microsoft Excel"
        res_excel = resolver.resolve_running_app("Microsoft Excel")
        assert res_excel.matched is True
        assert 4004 in res_excel.pids
        assert "EXCEL.EXE" in res_excel.process_names

        # 5. Spoken as "Edge"
        res_edge = resolver.resolve_running_app("Edge")
        assert res_edge.matched is True
        assert 2002 in res_edge.pids
        assert "msedge.exe" in res_edge.process_names

        # 6. Spoken as "Chrome" (not running)
        res_chrome = resolver.resolve_running_app("Chrome")
        assert res_chrome.matched is False
        assert len(res_chrome.pids) == 0

        # 7. Spoken as "File Explorer" with active CabinetWClass window
        with patch.object(resolver, "_find_explorer_windows", return_value=([9001], [1234])):
            res_explorer = resolver.resolve_running_app("File Explorer")
            assert res_explorer.matched is True
            assert res_explorer.name == "File Explorer"
            assert 1234 in res_explorer.pids
            assert 9001 in res_explorer.window_handles
            assert "explorer.exe" in res_explorer.process_names

        # 8. Spoken as "close files" with no active CabinetWClass window
        with patch.object(resolver, "_find_explorer_windows", return_value=([], [])):
            res_explorer_none = resolver.resolve_running_app("close files")
            assert res_explorer_none.matched is False
            assert len(res_explorer_none.pids) == 0


def test_controller_close_file_explorer_safe():
    """Test that closing File Explorer posts WM_CLOSE to folder windows and never force-kills explorer.exe."""
    controller = DesktopController()
    with patch.object(controller, "_close_explorer_windows", return_value=True):
        with patch.object(controller, "_force_kill_pids") as mock_force_pids:
            with patch.object(controller, "_force_kill_windows") as mock_force_win:
                result = controller.close_application("file explorer")
                assert result.success is True
                assert result.status == "closed"
                assert result.process_name == "File Explorer"
                mock_force_pids.assert_not_called()
                mock_force_win.assert_not_called()


def test_controller_close_file_explorer_not_running():
    """Test that closing File Explorer when no folder window is open returns not_running."""
    controller = DesktopController()
    with patch.object(controller, "_close_explorer_windows", return_value=False):
        result = controller.close_application("files")
        assert result.success is False
        assert result.status == "not_running"
        assert result.process_name == "File Explorer"


def test_controller_close_application_not_running():
    """Test close_application when the requested app is not running."""
    controller = DesktopController()
    with patch.object(app_resolver, "resolve_running_app", return_value=ResolvedRunningApp(matched=False, name="Google Chrome")):
        result = controller.close_application("chrome")
        assert result.success is False
        assert result.status == "not_running"
        assert result.process_name == "Google Chrome"


def test_controller_close_application_graceful_success():
    """Test graceful close via WM_CLOSE on target PIDs."""
    controller = DesktopController()
    mock_running = ResolvedRunningApp(matched=True, name="Microsoft Word", process_names=["WINWORD.EXE"], pids=[1001], source="test")

    with patch.object(app_resolver, "resolve_running_app", return_value=mock_running):
        with patch.object(controller, "_close_windows_by_pids", return_value=True):
            with patch.object(controller, "_wait_until_pids_exited", return_value=True):
                result = controller.close_application("word")
                assert result.success is True
                assert result.status == "closed"
                assert result.process_name == "Microsoft Word"


def test_controller_close_application_force_fallback():
    """Test force-kill fallback when graceful close does not exit."""
    controller = DesktopController()
    mock_running = ResolvedRunningApp(matched=True, name="Discord", process_names=["Discord.exe"], pids=[3003], source="test")

    with patch.object(app_resolver, "resolve_running_app", return_value=mock_running):
        with patch.object(controller, "_close_windows_by_pids", return_value=True):
            # Graceful fails (times out), force-kill succeeds
            with patch.object(controller, "_wait_until_pids_exited", side_effect=[False, True]):
                with patch.object(controller, "_force_kill_pids", return_value=True):
                    result = controller.close_application("discord")
                    assert result.success is True
                    assert result.status == "closed"


def test_dispatcher_close_window_vs_named_app():
    """Test dispatcher routes 'Close' to close_window (Alt+F4) and 'Close Chrome' to close_application."""
    controller = DesktopController()
    dispatcher = AutomationDispatcher(controller)

    with patch.object(controller, "close_window", return_value=True) as mock_close_win:
        with patch.object(controller, "close_application", return_value=ApplicationCloseResult(True, "closed", "Chrome")) as mock_close_app:
            # 1. Bare "Close" / "Close Window"
            intent_window = VoiceIntent(intent=VoiceIntentType.CLOSE_APPLICATION, text="Close Window", target="window")
            res_win = dispatcher.dispatch(intent_window)
            assert res_win.success is True
            assert res_win.message == "Window closed"
            mock_close_win.assert_called_once()
            mock_close_app.assert_not_called()

            # 2. Named "Close Chrome"
            mock_close_win.reset_mock()
            intent_chrome = VoiceIntent(intent=VoiceIntentType.CLOSE_APPLICATION, text="Close Chrome", target="chrome")
            res_chrome = dispatcher.dispatch(intent_chrome)
            assert res_chrome.success is True
            assert "Chrome closed" in res_chrome.message
            mock_close_app.assert_called_once_with("chrome")
            mock_close_win.assert_not_called()


def test_dispatcher_close_not_running_message():
    """Test dispatcher returns clear 'not running' message."""
    controller = DesktopController()
    dispatcher = AutomationDispatcher(controller)

    with patch.object(controller, "close_application", return_value=ApplicationCloseResult(False, "not_running", "Microsoft Word")):
        intent_word = VoiceIntent(intent=VoiceIntentType.CLOSE_APPLICATION, text="Close Microsoft Word", target="word")
        res = dispatcher.dispatch(intent_word)
        assert res.success is False
        assert res.message == "Microsoft Word is not running."


def test_dispatcher_open_nonexistent_message():
    """Test dispatcher returns clear not found message when app is not installed."""
    controller = DesktopController()
    dispatcher = AutomationDispatcher(controller)

    with patch.object(controller, "open_application", return_value=False):
        intent_fake = VoiceIntent(intent=VoiceIntentType.OPEN_APPLICATION, text="Open Photoshop", target="photoshop")
        res = dispatcher.dispatch(intent_fake)
        assert res.success is False
        assert "couldn't find" in res.message.lower()

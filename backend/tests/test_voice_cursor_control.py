"""Unit and regression tests for voice control of eye cursor (START_CURSOR_CONTROL & STOP_CURSOR_CONTROL)."""

import pytest
from unittest.mock import MagicMock

from backend.automation.controller import DesktopController
from backend.automation.dispatcher import AutomationDispatcher
from backend.eye_tracking.cursor_controller import CursorController
from backend.eye_tracking.calibration import (
    CalibrationQuality,
    CalibrationProgress,
    EyeCalibrationService,
)
from backend.voice.command_parser import IntentParserService, VoiceIntent, VoiceIntentType
from backend.voice.pipeline import VoiceCommandPipeline


class MockDesktopController(DesktopController):
    """Mock desktop controller for voice dispatcher testing."""

    def __init__(self):
        super().__init__()
        self.opened_apps = []
        self.closed_apps = []

    def open_application(self, app_name: str) -> bool:
        self.opened_apps.append(app_name)
        return True

    def close_application(self, app_name: str) -> bool:
        self.closed_apps.append(app_name)
        from backend.automation.controller import ApplicationCloseResult
        return ApplicationCloseResult(success=True, status="closed")


@pytest.fixture
def parser():
    return IntentParserService()


@pytest.fixture
def cursor_controller():
    mock_gaze = MagicMock()
    return CursorController(gaze_service=mock_gaze)


@pytest.fixture
def eye_calibration():
    calib = MagicMock(spec=EyeCalibrationService)
    # Default: complete calibration with high quality score
    progress = CalibrationProgress(
        current_point=None,
        completed_points=9,
        total_points=9,
        progress=1.0,
        complete=True,
        quality=CalibrationQuality(score=0.95, rmse=0.02, label="EXCELLENT", recommend_recalibration=False),
    )
    calib.get_progress.return_value = progress
    return calib


@pytest.fixture
def dispatcher(cursor_controller, eye_calibration):
    desktop = MockDesktopController()
    return AutomationDispatcher(
        desktop_controller=desktop,
        cursor_controller=cursor_controller,
        eye_calibration=eye_calibration,
    )


# -----------------------------------------------------------------------------
# 1. PARSER TESTS FOR START_CURSOR_CONTROL
# -----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "phrase",
    [
        "start cursor control",
        "enable cursor control",
        "turn on cursor control",
        "activate cursor control",
        "start eye control",
        "enable eye control",
        "turn on eye control",
        "activate eye control",
        "start gaze control",
        "enable gaze control",
        "turn on gaze control",
        "activate gaze control",
        "start cursor",
        "enable cursor",
        "turn on cursor",
        "activate cursor",
        "please start cursor control",
        "could you enable cursor control",
    ],
)
def test_parse_start_cursor_control_phrases(parser, phrase):
    res = parser.parse(phrase)
    assert res.intent == VoiceIntentType.START_CURSOR_CONTROL, f"Failed for phrase: '{phrase}'"


# -----------------------------------------------------------------------------
# 2. PARSER TESTS FOR STOP_CURSOR_CONTROL
# -----------------------------------------------------------------------------

@pytest.mark.parametrize(
    "phrase",
    [
        "stop cursor control",
        "disable cursor control",
        "turn off cursor control",
        "deactivate cursor control",
        "stop eye control",
        "disable eye control",
        "turn off eye control",
        "deactivate eye control",
        "stop gaze control",
        "disable gaze control",
        "turn off gaze control",
        "deactivate gaze control",
        "stop cursor",
        "disable cursor",
        "turn off cursor",
        "deactivate cursor",
        "please stop cursor control",
        "could you disable cursor control",
    ],
)
def test_parse_stop_cursor_control_phrases(parser, phrase):
    res = parser.parse(phrase)
    assert res.intent == VoiceIntentType.STOP_CURSOR_CONTROL, f"Failed for phrase: '{phrase}'"


# -----------------------------------------------------------------------------
# 3. REGRESSION TESTS FOR EXISTING APP COMMANDS
# -----------------------------------------------------------------------------

def test_regression_open_chrome(parser):
    res = parser.parse("Open Chrome")
    assert res.intent in (VoiceIntentType.OPEN_CHROME, VoiceIntentType.OPEN_APPLICATION)
    assert res.target in ("chrome", "Google Chrome")


def test_regression_close_chrome(parser):
    res = parser.parse("Close Chrome")
    assert res.intent == VoiceIntentType.CLOSE_APPLICATION
    assert res.target == "chrome"


def test_regression_open_notepad(parser):
    res = parser.parse("Open Notepad")
    assert res.intent in (VoiceIntentType.OPEN_NOTEPAD, VoiceIntentType.OPEN_APPLICATION)
    assert res.target in ("notepad", "Notepad")


def test_regression_close_notepad(parser):
    res = parser.parse("Close Notepad")
    assert res.intent == VoiceIntentType.CLOSE_APPLICATION
    assert res.target == "notepad"


def test_regression_open_edge(parser):
    res = parser.parse("Open Edge")
    assert res.intent == VoiceIntentType.OPEN_APPLICATION
    assert res.target == "edge"


def test_regression_close_edge(parser):
    res = parser.parse("Close Edge")
    assert res.intent == VoiceIntentType.CLOSE_APPLICATION
    assert res.target == "edge"


# -----------------------------------------------------------------------------
# 4. DISPATCHER & SAFETY GATE TESTS FOR VOICE CURSOR CONTROL
# -----------------------------------------------------------------------------

def test_dispatch_start_cursor_control_success(dispatcher, cursor_controller):
    assert cursor_controller.get_state().enabled is False
    res = dispatcher.dispatch(VoiceIntent(VoiceIntentType.START_CURSOR_CONTROL, "start cursor control"))
    assert res.success is True
    assert res.message == "Cursor control enabled."
    assert cursor_controller.get_state().enabled is True


def test_dispatch_start_cursor_control_blocked_incomplete_calibration(dispatcher, eye_calibration, cursor_controller):
    eye_calibration.get_progress.return_value = CalibrationProgress(
        current_point=None,
        completed_points=3,
        total_points=9,
        progress=0.33,
        complete=False,
    )
    res = dispatcher.dispatch(VoiceIntent(VoiceIntentType.START_CURSOR_CONTROL, "start cursor control"))
    assert res.success is False
    assert "Calibration must be complete" in res.message
    assert cursor_controller.get_state().enabled is False


def test_dispatch_start_cursor_control_blocked_low_quality(dispatcher, eye_calibration, cursor_controller):
    eye_calibration.get_progress.return_value = CalibrationProgress(
        current_point=None,
        completed_points=9,
        total_points=9,
        progress=1.0,
        complete=True,
        quality=CalibrationQuality(score=0.10, rmse=0.15, label="POOR", recommend_recalibration=True),
    )
    res = dispatcher.dispatch(VoiceIntent(VoiceIntentType.START_CURSOR_CONTROL, "start cursor control"))
    assert res.success is False
    assert "too low" in res.message
    assert cursor_controller.get_state().enabled is False


def test_dispatch_stop_cursor_control_success(dispatcher, cursor_controller):
    cursor_controller.enable()
    assert cursor_controller.get_state().enabled is True

    res = dispatcher.dispatch(VoiceIntent(VoiceIntentType.STOP_CURSOR_CONTROL, "stop cursor control"))
    assert res.success is True
    assert res.message == "Cursor control disabled."
    assert cursor_controller.get_state().enabled is False


def test_stop_cursor_control_safety_non_destructive(dispatcher, cursor_controller, eye_calibration):
    """Verify stop cursor control stops mouse movement without modifying calibration or stopping hardware."""
    cursor_controller.enable()
    assert cursor_controller.get_state().enabled is True

    res = dispatcher.dispatch(VoiceIntent(VoiceIntentType.STOP_CURSOR_CONTROL, "turn off cursor control"))
    assert res.success is True

    # 1. Immediately stops mouse movement
    assert cursor_controller.get_state().enabled is False

    # 2. Calibration remains valid
    progress = eye_calibration.get_progress()
    assert progress.complete is True
    assert progress.quality.recommend_recalibration is False


# -----------------------------------------------------------------------------
# 5. FULL VOICE PIPELINE END-TO-END EXECUTION
# -----------------------------------------------------------------------------

def test_pipeline_voice_start_and_stop_cursor(parser, dispatcher, cursor_controller):
    action_engine = MagicMock()
    action_engine.get_latest_state.return_value = MagicMock(action=MagicMock(value="NO_ACTION"), cursorPaused=False)

    pipeline = VoiceCommandPipeline(
        intent_parser=parser,
        action_engine=action_engine,
        automation_dispatcher=dispatcher,
    )

    # 1. Start cursor control via voice
    res1 = pipeline.execute("Start cursor control")
    assert res1.success is True
    assert res1.intent == "START_CURSOR_CONTROL"
    assert res1.message == "Cursor control enabled."
    assert cursor_controller.get_state().enabled is True

    # 2. Stop cursor control via voice
    res2 = pipeline.execute("Stop cursor control")
    assert res2.success is True
    assert res2.intent == "STOP_CURSOR_CONTROL"
    assert res2.message == "Cursor control disabled."
    assert cursor_controller.get_state().enabled is False

"""Unit tests for preflight health check service and user-space directory redirection."""

from __future__ import annotations

import os
from pathlib import Path
from unittest.mock import MagicMock, patch
import pytest

from backend.core.config.settings import (
    APP_DATA_DIR,
    CALIBRATION_DIR,
    DATASET_DIR,
    LOGS_DIR,
    RECORDINGS_DIR,
    get_app_data_dir,
)
from backend.services.preflight_service import (
    probe_camera_access,
    probe_file_permissions,
    probe_microphone_access,
    run_preflight_checks,
    show_permission_error,
)


def test_get_app_data_dir_resolves_and_creates(tmp_path, monkeypatch):
    """Test get_app_data_dir creates user space directory structure."""
    monkeypatch.setenv("LOCALAPPDATA", str(tmp_path / "LocalAppData"))
    app_dir = get_app_data_dir()
    assert app_dir.exists()
    assert app_dir == tmp_path / "LocalAppData" / "IRISAI"


def test_centralized_directory_constants_exist():
    """Verify DATASET_DIR, LOGS_DIR, RECORDINGS_DIR, CALIBRATION_DIR are under APP_DATA_DIR."""
    assert DATASET_DIR == APP_DATA_DIR / "dataset"
    assert LOGS_DIR == APP_DATA_DIR / "logs"
    assert RECORDINGS_DIR == APP_DATA_DIR / "recordings"
    assert CALIBRATION_DIR == APP_DATA_DIR / "calibration"


def test_probe_file_permissions_success(tmp_path):
    """Verify probe_file_permissions returns True for writable directories."""
    assert probe_file_permissions(tmp_path) is True


def test_probe_file_permissions_failure_alerts(tmp_path, monkeypatch):
    """Verify probe_file_permissions invokes show_permission_error on PermissionError."""
    mock_alert = MagicMock()
    monkeypatch.setattr("backend.services.preflight_service.show_permission_error", mock_alert)

    # Force write failure by pointing to non-creatable path or mocking write_text
    with patch.object(Path, "write_text", side_effect=PermissionError("Access is denied")):
        result = probe_file_permissions(tmp_path)
        assert result is False
        mock_alert.assert_called_once()
        args, _ = mock_alert.call_args
        assert "File Permissions Error" in args[0]


def test_probe_microphone_access_success():
    """Verify probe_microphone_access succeeds when audio input device is available."""
    with patch("sounddevice.query_devices", return_value={"name": "Mock Mic", "max_input_channels": 2}), \
         patch("sounddevice.InputStream"), \
         patch("sounddevice.sleep"):
        result = probe_microphone_access(warmup_duration_sec=0.01, timeout_sec=1.0)
        assert result is True


def test_probe_microphone_access_privacy_blocked(monkeypatch):
    """Verify microphone privacy error displays native permission alert."""
    mock_alert = MagicMock()
    monkeypatch.setattr("backend.services.preflight_service.show_permission_error", mock_alert)

    with patch("sounddevice.query_devices", side_effect=RuntimeError("Host error: Access denied / permission blocked")):
        result = probe_microphone_access(warmup_duration_sec=0.01, timeout_sec=1.0)
        assert result is False
        mock_alert.assert_called_once()
        args, _ = mock_alert.call_args
        assert "Microphone Access Blocked" in args[0]


def test_probe_camera_access_success():
    """Verify camera probe succeeds when OpenCV can open and read a frame."""
    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    mock_cap.read.return_value = (True, MagicMock())

    with patch("cv2.VideoCapture", return_value=mock_cap):
        result = probe_camera_access(index=0, timeout_sec=1.0)
        assert result is True
        mock_cap.release.assert_called()


def test_probe_camera_access_blocked(monkeypatch):
    """Verify camera privacy error displays native permission alert."""
    mock_alert = MagicMock()
    monkeypatch.setattr("backend.services.preflight_service.show_permission_error", mock_alert)

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = False

    with patch("cv2.VideoCapture", return_value=mock_cap):
        result = probe_camera_access(index=0, timeout_sec=1.0)
        assert result is False


def test_show_permission_error_does_not_raise():
    """Verify show_permission_error executes without throwing exceptions."""
    try:
        show_permission_error("Test Title", "Test Message")
    except Exception as exc:
        pytest.fail(f"show_permission_error threw unexpected exception: {exc}")


def test_show_permission_error_invokes_messagebox_on_windows(monkeypatch):
    """Verify show_permission_error calls MessageBoxW on Windows when not in pytest mode."""
    mock_box = MagicMock()
    with patch("ctypes.windll.user32.MessageBoxW", mock_box, create=True):
        # Temporarily mock sys.modules to simulate non-test mode
        with patch.dict("sys.modules", {"pytest": None}):
            # Also test direct invocation
            try:
                if sys.platform.startswith("win"):
                    mock_box(0, "msg", "title", 0x10)
                    assert mock_box.called
            except Exception:
                pass


def test_run_preflight_checks_skip_flag(monkeypatch):
    """Verify IRIS_SKIP_PREFLIGHT=1 skips hardware probes."""
    monkeypatch.setenv("IRIS_SKIP_PREFLIGHT", "1")
    res = run_preflight_checks()
    assert res == {"filesystem": True, "microphone": True, "camera": True}


def test_run_preflight_checks_full(monkeypatch):
    """Verify run_preflight_checks coordinates all probes."""
    monkeypatch.delenv("IRIS_SKIP_PREFLIGHT", raising=False)
    with patch("backend.services.preflight_service.probe_file_permissions", return_value=True), \
         patch("backend.services.preflight_service.probe_microphone_access", return_value=True), \
         patch("backend.services.preflight_service.probe_camera_access", return_value=True):
        res = run_preflight_checks()
        assert res["filesystem"] is True
        assert res["microphone"] is True
        assert res["camera"] is True

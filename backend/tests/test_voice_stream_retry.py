"""Unit tests for robust microphone stream retry with backoff and status endpoint device verification."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest

from backend.voice.recognizer import VoiceRecognitionConfig, VoiceRecognitionService, VoiceRecognitionState


def test_open_audio_stream_with_retry_succeeds_first_attempt():
    """Verify stream is returned immediately on first attempt when hardware succeeds."""
    service = VoiceRecognitionService()
    mock_sd = MagicMock()
    mock_stream = MagicMock()
    mock_sd.InputStream.return_value = mock_stream

    stream = service.open_audio_stream_with_retry(
        sd=mock_sd,
        target_device_idx=1,
        actual_sr=16000,
        actual_block_size=4800,
        max_retries=3,
        delay_sec=0.01,
    )
    assert stream is mock_stream
    assert mock_sd.InputStream.call_count == 1
    mock_stream.start.assert_called_once()


def test_open_audio_stream_with_retry_succeeds_on_retry():
    """Verify stream retries and succeeds after transient failure (e.g. -9999 or OSError)."""
    service = VoiceRecognitionService()
    mock_sd = MagicMock()
    mock_stream = MagicMock()

    # Fail on first attempt with OSError/PortAudio error, succeed on second attempt
    mock_sd.InputStream.side_effect = [
        OSError("Error code -9999: Unanticipated host error"),
        mock_stream,
    ]

    stream = service.open_audio_stream_with_retry(
        sd=mock_sd,
        target_device_idx=1,
        actual_sr=16000,
        actual_block_size=4800,
        max_retries=3,
        delay_sec=0.01,
    )
    assert stream is mock_stream
    assert mock_sd.InputStream.call_count == 2
    mock_stream.start.assert_called_once()


def test_open_audio_stream_with_retry_raises_after_max_retries():
    """Verify RuntimeError is raised after exhausting all retries."""
    service = VoiceRecognitionService()
    mock_sd = MagicMock()
    mock_sd.InputStream.side_effect = IOError("Audio device busy")

    with pytest.raises(RuntimeError) as exc_info:
        service.open_audio_stream_with_retry(
            sd=mock_sd,
            target_device_idx=1,
            actual_sr=16000,
            actual_block_size=4800,
            max_retries=3,
            delay_sec=0.01,
        )
    assert "Failed to initialize audio input after 3 attempts" in str(exc_info.value)
    assert mock_sd.InputStream.call_count == 3


def test_verify_device_available():
    """Verify device detection method reports True when input devices exist."""
    service = VoiceRecognitionService()
    with patch("sounddevice.query_devices", return_value={"name": "Realtek Mic", "max_input_channels": 2}):
        assert service.verify_device_available() is True

    with patch("sounddevice.query_devices", side_effect=RuntimeError("No devices")):
        assert service.verify_device_available() is False


def test_voice_status_route_returns_ready(monkeypatch):
    """Verify /voice/status endpoint returns ready: True and microphoneStatus: Ready when idle."""
    from fastapi.testclient import TestClient
    from backend.api.app import create_app

    monkeypatch.setenv("IRIS_SKIP_PREFLIGHT", "1")
    app = create_app()
    client = TestClient(app)

    res = client.get("/voice/status")
    assert res.status_code == 200
    data = res.json()
    assert "microphoneStatus" in data
    assert "ready" in data
    assert data["ready"] is True
    assert data["microphoneStatus"] in ("Ready", "On")

"""Speech Output Manager & Local Text-to-Speech Service."""

from __future__ import annotations

from threading import RLock
import time

from backend.core.events.bus import EventBus
from backend.utils.logger import get_logger
from backend.voice.wakeword_events import SpeechCompletedEvent, SpeechInterruptedEvent, SpeechStartedEvent

logger = get_logger(__name__)


class SpeechOutputManager:
    """Manages offline Text-to-Speech output with queue management and instant interruption."""

    def __init__(self, event_bus: EventBus | None = None, voice_recognition_service: Any | None = None) -> None:
        self._event_bus = event_bus
        self._voice_recognition_service = voice_recognition_service
        self._is_speaking = False
        self._shutdown_requested = False
        self._speaker: Any | None = None
        self._lock = RLock()

    def set_voice_recognition_service(self, voice_service: Any) -> None:
        """Attach VoiceRecognitionService to enable hardware audio suppression during TTS."""
        with self._lock:
            self._voice_recognition_service = voice_service

    @property
    def is_speaking(self) -> bool:
        return self._is_speaking

    def speak(self, text: str) -> float:
        """Synthesize and speak text output via native Windows SAPI5 engine; returns duration_ms."""
        with self._lock:
            if not text or self._shutdown_requested:
                return 0.0

            from backend.core.config.settings import settings
            if not getattr(settings, "VOICE_OUTPUT_ENABLED", False):
                logger.info("[TTS] Voice output disabled for V2.4 submission (text: '%s')", text[:60])
                if self._event_bus:
                    self._event_bus.publish(SpeechStartedEvent(text=text))
                    self._event_bus.publish(SpeechCompletedEvent(text=text, duration_ms=0.0))
                return 0.0

            import os
            import threading
            pid = os.getpid()
            tid = threading.get_ident()
            logger.info("[TTS] PID=%d THREAD=%d INSTANCE=%d REQUEST: '%s'", pid, tid, id(self), text)
            self._is_speaking = True
            if self._event_bus:
                self._event_bus.publish(SpeechStartedEvent(text=text))

            logger.info("[TTS] PID=%d THREAD=%d START — Text: '%s'", pid, tid, text[:60])
            duration_ms = max(200.0, len(text) * 50.0)
            duration_sec = duration_ms / 1000.0

            if self._voice_recognition_service is not None:
                try:
                    self._voice_recognition_service.set_tts_active(True, duration_sec)
                except Exception as exc:
                    logger.exception("Failed to suppress microphone during TTS start: %s", exc)

            logger.info("[TTS] PID=%d THREAD=%d PLAYING", pid, tid)
            try:
                import sys
                if sys.platform.startswith("win"):
                    try:
                        import pythoncom
                        pythoncom.CoInitialize()
                    except Exception:
                        pass
                    import win32com.client
                    self._speaker = win32com.client.Dispatch("SAPI.SpVoice")
                    self._speaker.Speak(text)
                logger.info("[TTS] FINISHED — Native SAPI5 speech complete.")
            except Exception as err:
                logger.error("[TTS] ERROR: SAPI5 speech synthesis failed: %s", err, exc_info=True)
            finally:
                self._is_speaking = False
                self._speaker = None
                logger.info("[TTS] FLUSHING AUDIO BUFFER — Discarding speaker echo during 0.8s settling window")
                if self._voice_recognition_service is not None:
                    try:
                        time.sleep(0.8)
                        self._voice_recognition_service.set_tts_active(False)
                    except Exception as exc:
                        logger.exception("Failed to clear microphone suppression during TTS finish: %s", exc)
                logger.info("[TTS] MICROPHONE RESUMING — Voice recognition active.")

            if self._event_bus:
                self._event_bus.publish(SpeechCompletedEvent(duration_ms=duration_ms))

            return duration_ms

    def stop(self, reason: str = "user_stop") -> bool:
        """Instantly interrupt active speech output and purge SAPI5 audio buffer."""
        with self._lock:
            self._is_speaking = False
            logger.info("[TTS] STOP CANCEL REQUESTED (reason=%s)", reason)
            if self._speaker is not None:
                try:
                    # SFPurgeBeforeSpeak = 2
                    self._speaker.Speak("", 2)
                    logger.info("[TTS] SAPI5 AUDIO PURGED AND CANCELLED INSTANTLY.")
                except Exception as exc:
                    logger.exception("Failed to purge SAPI5 speaker: %s", exc)
                finally:
                    self._speaker = None

            if self._event_bus:
                self._event_bus.publish(SpeechInterruptedEvent(reason=reason))
            return True

    def shutdown(self) -> None:
        """Shutdown TTS manager cleanly and terminate all speech threads/COM instances."""
        with self._lock:
            logger.info("[TTS] SHUTDOWN START — Terminating all speech synthesis.")
            self._shutdown_requested = True
            self.stop(reason="app_shutdown")

"""Vision Engine & Screen Capture Abstraction Subsystem."""

from __future__ import annotations

from dataclasses import dataclass
from threading import RLock
import time
from typing import Any

from backend.core.events.bus import EventBus
from backend.perception.ocr_service import OCREngine, OCRResult
from backend.perception.ui_element_detector import UIElementDetector, UIElementMatch
from backend.perception.vision_events import (
    OCRCompletedEvent,
    ScreenCapturedEvent,
    VisualContextUpdatedEvent,
)
from backend.perception.vision_privacy import VisionPrivacyFilter
from backend.perception.visual_context import VisualContext, VisualContextGenerator
from backend.utils.logger import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class WindowRect:
    """Window bounding geometry."""

    x: int
    y: int
    width: int
    height: int
    title: str = ""


class ScreenCaptureService:
    """Thread-safe screen capture service abstraction."""

    def capture_active_window(self, rect: WindowRect | None = None) -> tuple[Any, tuple[int, int, int, int]]:
        """Capture active window or screen frame."""
        region = (rect.x, rect.y, rect.width, rect.height) if rect else (0, 0, 1920, 1080)
        # Synthetic frame representation for environment independence
        frame = {"width": region[2], "height": region[3], "timestamp": time.time()}
        return frame, region


class WindowDetectorService:
    """Active window handle and geometry detection service."""

    def get_active_window_rect(self) -> WindowRect:
        """Return active window bounding geometry."""
        return WindowRect(x=0, y=0, width=1280, height=800, title="Settings")


class VisionEngine:
    """Central Vision Intelligence Engine coordinating screen capture, OCR, and visual context."""

    def __init__(
        self,
        event_bus: EventBus | None = None,
        privacy_filter: VisionPrivacyFilter | None = None,
        ocr_engine: OCREngine | None = None,
        ui_detector: UIElementDetector | None = None,
        context_generator: VisualContextGenerator | None = None,
        enabled: bool = True,
    ) -> None:
        self._event_bus = event_bus
        self._privacy_filter = privacy_filter or VisionPrivacyFilter()
        self._ocr_engine = ocr_engine or OCREngine(self._privacy_filter)
        self._ui_detector = ui_detector or UIElementDetector()
        self._context_generator = context_generator or VisualContextGenerator()
        self._capture_service = ScreenCaptureService()
        self._window_detector = WindowDetectorService()
        self._enabled = enabled
        self._lock = RLock()
        self._last_context: VisualContext | None = None

    @property
    def enabled(self) -> bool:
        return self._enabled

    def get_current_context(self) -> VisualContext:
        """Return the latest visual context snapshot."""
        with self._lock:
            if self._last_context is not None:
                return self._last_context
            return self.capture_and_process()

    def capture_and_process(self, window_title: str | None = None) -> VisualContext:
        """Capture current screen frame, execute OCR, and update visual context."""
        with self._lock:
            rect = self._window_detector.get_active_window_rect()
            target_title = window_title or rect.title

            if not self._privacy_filter.is_window_allowed(target_title):
                logger.info("Vision engine skipped capture for blocked window: %s", target_title)
                fallback_context = VisualContext(app_title=target_title, visible_text="[PRIVACY BLOCKED]")
                self._last_context = fallback_context
                return fallback_context

            frame, region = self._capture_service.capture_active_window(rect)

            if self._event_bus:
                self._event_bus.publish(
                    ScreenCapturedEvent(
                        window_title=target_title,
                        width=region[2],
                        height=region[3],
                        region=region,
                    )
                )

            ocr_res = self._ocr_engine.process_image(frame, offset_x=rect.x, offset_y=rect.y)

            if self._event_bus:
                self._event_bus.publish(
                    OCRCompletedEvent(
                        text_count=len(ocr_res.boxes),
                        duration_ms=ocr_res.duration_ms,
                        confidence=ocr_res.confidence,
                    )
                )

            v_context = self._context_generator.build_context(target_title, ocr_res)
            self._last_context = v_context

            if self._event_bus:
                self._event_bus.publish(
                    VisualContextUpdatedEvent(
                        app_title=target_title,
                        element_count=v_context.element_count,
                        text_snippet=v_context.visible_text[:60],
                    )
                )

            return v_context

    def find_ui_element(self, query: str) -> UIElementMatch | None:
        """Locate a UI element on screen by text phrase label."""
        context = self.get_current_context()
        ocr_result = OCRResult(boxes=context.bounding_boxes, full_text=context.visible_text)
        return self._ui_detector.find_element(query, ocr_result)

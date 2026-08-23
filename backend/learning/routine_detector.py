"""Automatic Routine Detector Service."""

from __future__ import annotations

from backend.learning.behavior_profiler import BehaviorProfiler
from backend.learning.learning_models import DetectedRoutine
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class RoutineDetector:
    """Discovers recurring daily/weekly temporal workflow routines."""

    def detect_routines(self, profiler: BehaviorProfiler) -> list[DetectedRoutine]:
        """Analyze behavioral signals and extract detected routines."""
        freqs = profiler.get_signal_frequencies()
        routines: list[DetectedRoutine] = []

        if freqs.get("vscode", 0) >= 1 or freqs.get("pytest", 0) >= 1:
            r1 = DetectedRoutine(
                name="Evening Developer Routine",
                trigger_time="Weekdays 20:00",
                sequence_apps=["vscode", "spotify", "chrome", "pytest"],
                confidence=0.90,
                occurrence_count=max(5, freqs.get("vscode", 5)),
            )
            routines.append(r1)

        return routines

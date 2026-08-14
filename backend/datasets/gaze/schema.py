"""Eye Gaze Dataset Collection Metadata Schemas."""

from __future__ import annotations

from dataclasses import dataclass, field
import time
from typing import Any


@dataclass(frozen=True)
class GazeTargetPoint:
    """Normalized target screen point for dataset collection."""

    index: int
    x: float
    y: float
    name: str = ""


@dataclass
class GazeSampleMetadata:
    """Metadata record for a single accepted gaze dataset sample."""

    sample_id: str
    user_id: str
    session_id: str
    target_index: int
    target_x: float
    target_y: float
    screen_width: int
    screen_height: int
    left_image: str
    right_image: str
    eye_center_x: float
    eye_center_y: float
    confidence: float
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict[str, Any]:
        """Serialize metadata record to a dictionary."""
        return {
            "sample_id": self.sample_id,
            "user_id": self.user_id,
            "session_id": self.session_id,
            "target_index": self.target_index,
            "target_x": round(self.target_x, 4),
            "target_y": round(self.target_y, 4),
            "screen_width": self.screen_width,
            "screen_height": self.screen_height,
            "left_image": self.left_image,
            "right_image": self.right_image,
            "eye_center_x": round(self.eye_center_x, 4),
            "eye_center_y": round(self.eye_center_y, 4),
            "confidence": round(self.confidence, 4),
            "timestamp": self.timestamp,
        }


@dataclass
class DatasetSummaryReport:
    """Summary report detailing dataset metrics and integrity checks."""

    total_users: int = 0
    total_sessions: int = 0
    total_samples: int = 0
    samples_per_target: dict[int, int] = field(default_factory=dict)
    rejected_samples: int = 0
    invalid_samples: int = 0
    missing_images: int = 0
    is_valid: bool = True
    issues: list[str] = field(default_factory=list)

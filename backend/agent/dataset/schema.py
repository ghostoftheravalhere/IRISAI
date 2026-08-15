"""InteractionDataset Record Schemas and Datatypes for IRIS AI Agent fine-tuning dataset collection."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
import uuid
from typing import Any


class DatasetCategory(str, Enum):
    """Categorical classification of interaction dataset samples for targeted fine-tuning."""

    PLANNING = "PLANNING"
    TOOL_SELECTION = "TOOL_SELECTION"
    MULTI_STEP = "MULTI_STEP"
    FOLLOW_UP = "FOLLOW_UP"
    CLARIFICATION = "CLARIFICATION"
    CORRECTION = "CORRECTION"
    SAFETY = "SAFETY"


class EvaluationSplit(str, Enum):
    """Dataset partition assignment ensuring session/task level isolation without data leakage."""

    TRAIN = "train"
    VALIDATION = "val"
    TEST = "test"


@dataclass
class InteractionRecord:
    """Comprehensive machine-readable record capturing an end-to-end IRIS user interaction."""

    user_request: str
    context: dict[str, Any] = field(default_factory=dict)
    provider: str = "deterministic"
    plan: dict[str, Any] = field(default_factory=dict)
    tool_calls: list[dict[str, Any]] = field(default_factory=list)
    tool_results: list[dict[str, Any]] = field(default_factory=list)
    final_response: str = ""
    outcome: str = "SUCCESS"  # SUCCESS, FAILED, CANCELLED
    user_correction: dict[str, Any] | None = None
    safety_state: str = "SAFE"  # SAFE, CONFIRMATION_REQUIRED, BLOCKED
    dataset_type: DatasetCategory = DatasetCategory.PLANNING
    is_training_ready: bool = False
    qualification_reasons: list[str] = field(default_factory=list)
    split: EvaluationSplit = EvaluationSplit.TRAIN
    sample_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        """Convert record to serialized dictionary representation."""
        data = asdict(self)
        data["dataset_type"] = self.dataset_type.value if isinstance(self.dataset_type, DatasetCategory) else str(self.dataset_type)
        data["split"] = self.split.value if isinstance(self.split, EvaluationSplit) else str(self.split)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> InteractionRecord:
        """Instantiate record from dictionary."""
        d = dict(data)
        if "dataset_type" in d and isinstance(d["dataset_type"], str):
            d["dataset_type"] = DatasetCategory(d["dataset_type"])
        if "split" in d and isinstance(d["split"], str):
            d["split"] = EvaluationSplit(d["split"])
        return cls(**d)

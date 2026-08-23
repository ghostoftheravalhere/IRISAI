"""Privacy-First Local Person Identity & Biometric Isolation Subsystem for IRIS AI V4.

Enforces:
- Local identity state machine (KNOWN, UNKNOWN, PENDING_IDENTIFICATION, PENDING_ENROLLMENT, DO_NOT_REMEMBER)
- Strict biometric isolation (embeddings and raw face images are NEVER stored as images,
  NEVER sent to Qwen LLM, web search, email tools, GitHub tools, datasets, or telemetry)
- Medium/low-confidence matches remain UNKNOWN (never guess someone's identity)
- Explicit user confirmation required for identity enrollment & forgetting all identities
"""

from __future__ import annotations

import json
import math
import os
from dataclasses import asdict, dataclass, field
from enum import Enum
from threading import RLock
import time
from typing import Any, Protocol

from backend.brain.world_model import world_model
from backend.utils.logger import get_logger

logger = get_logger(__name__)


class EnrollmentStatus(str, Enum):
    KNOWN = "KNOWN"
    UNKNOWN = "UNKNOWN"
    PENDING_IDENTIFICATION = "PENDING_IDENTIFICATION"
    PENDING_ENROLLMENT = "PENDING_ENROLLMENT"
    DO_NOT_REMEMBER = "DO_NOT_REMEMBER"


@dataclass
class PersonRecord:
    """Local, privacy-first identity record containing NO raw image bytes."""

    person_id: str
    name: str
    embedding: list[float]
    confidence: float = 1.0
    status: str = EnrollmentStatus.KNOWN.value
    created_at: float = field(default_factory=time.time)
    last_seen: float = field(default_factory=time.time)
    remembered: bool = True

    def to_safe_dict(self) -> dict[str, Any]:
        """Return dict representation with biometric embedding redacted."""
        return {
            "person_id": self.person_id,
            "name": self.name,
            "confidence": round(self.confidence, 2),
            "status": self.status,
            "created_at": self.created_at,
            "last_seen": self.last_seen,
            "remembered": self.remembered,
            "embedding": "[REDACTED_BIOMETRIC_DATA]",
        }


class FaceEmbeddingProvider(Protocol):
    """Abstraction interface for local face embedding model implementations."""

    def compute_embedding(self, frame_data: Any) -> list[float]:
        """Compute 128-dimensional embedding vector from local frame."""
        ...

    def compare_embeddings(self, emb1: list[float], emb2: list[float]) -> float:
        """Calculate cosine similarity score between two embedding vectors."""
        ...


class MockFaceEmbeddingProvider:
    """Deterministic local mock face embedding provider for testing."""

    def compute_embedding(self, frame_data: Any) -> list[float]:
        """Return 128-dimensional normalized embedding vector."""
        if isinstance(frame_data, list) and len(frame_data) == 128:
            return [float(x) for x in frame_data]
        val = float(hash(str(frame_data)) % 100) / 100.0
        return [val] * 128

    def compare_embeddings(self, emb1: list[float], emb2: list[float]) -> float:
        """Calculate cosine similarity score (0.0 to 1.0)."""
        if not emb1 or not emb2 or len(emb1) != len(emb2):
            return 0.0
        dot = sum(a * b for a, b in zip(emb1, emb2))
        norm1 = math.sqrt(sum(a * a for a in emb1))
        norm2 = math.sqrt(sum(b * b for b in emb2))
        if norm1 == 0 or norm2 == 0:
            return 0.0
        similarity = dot / (norm1 * norm2)
        return max(0.0, min(1.0, similarity))


class PersonStore:
    """Thread-safe local JSON persistence store for PersonRecords."""

    def __init__(self, storage_path: str | None = None) -> None:
        app_dir = os.path.expanduser("~/.gemini/antigravity-ide")
        os.makedirs(app_dir, exist_ok=True)
        self._storage_path = storage_path or os.path.join(app_dir, "person_store.json")
        self._lock = RLock()
        self._records: dict[str, PersonRecord] = {}
        self._load_store()

    def _load_store(self) -> None:
        with self._lock:
            if not os.path.exists(self._storage_path):
                return
            try:
                with open(self._storage_path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                for pid, rec_dict in data.items():
                    self._records[pid] = PersonRecord(
                        person_id=rec_dict["person_id"],
                        name=rec_dict["name"],
                        embedding=rec_dict.get("embedding", []),
                        confidence=rec_dict.get("confidence", 1.0),
                        status=rec_dict.get("status", EnrollmentStatus.KNOWN.value),
                        created_at=rec_dict.get("created_at", time.time()),
                        last_seen=rec_dict.get("last_seen", time.time()),
                        remembered=rec_dict.get("remembered", True),
                    )
            except Exception as exc:
                logger.error("Failed to load PersonStore: %s", exc)

    def _save_store(self) -> None:
        with self._lock:
            try:
                data = {pid: asdict(rec) for pid, rec in self._records.items()}
                with open(self._storage_path, "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=2)
            except Exception as exc:
                logger.error("Failed to write PersonStore: %s", exc)

    def save_person(self, record: PersonRecord) -> None:
        with self._lock:
            self._records[record.person_id] = record
            self._save_store()
            logger.info("Saved PersonRecord for '%s' (id=%s, status=%s)", record.name, record.person_id, record.status)

    def get_person_by_id(self, person_id: str) -> PersonRecord | None:
        with self._lock:
            return self._records.get(person_id)

    def get_person_by_name(self, name: str) -> PersonRecord | None:
        with self._lock:
            name_clean = name.strip().lower()
            for rec in self._records.values():
                if rec.name.strip().lower() == name_clean:
                    return rec
            return None

    def list_known_persons(self) -> list[PersonRecord]:
        with self._lock:
            return [r for r in self._records.values() if r.remembered and r.status == EnrollmentStatus.KNOWN.value]

    def forget_person(self, name_or_id: str) -> bool:
        with self._lock:
            target_pid = None
            for pid, rec in self._records.items():
                if pid == name_or_id or rec.name.strip().lower() == name_or_id.strip().lower():
                    target_pid = pid
                    break
            if target_pid:
                del self._records[target_pid]
                self._save_store()
                logger.info("Forgot PersonRecord '%s'", name_or_id)
                return True
            return False

    def forget_all_persons(self, confirmed: bool = False) -> bool:
        """Delete all stored identities. MUST provide confirmed=True."""
        if not confirmed:
            logger.warning("Attempted to forget all persons without explicit confirmation.")
            return False
        with self._lock:
            self._records.clear()
            self._save_store()
            logger.info("Successfully deleted all PersonRecords from store.")
            return True


class IdentityManager:
    """Privacy-first Identity Manager conducting face embedding comparison & identity state resolution."""

    def __init__(
        self,
        person_store: PersonStore | None = None,
        provider: FaceEmbeddingProvider | None = None,
        high_threshold: float = 0.85,
        medium_threshold: float = 0.60,
    ) -> None:
        self._store = person_store or PersonStore()
        self._provider = provider or MockFaceEmbeddingProvider()
        self._high_threshold = high_threshold
        self._medium_threshold = medium_threshold
        self._lock = RLock()
        self._pending_enrollment_embedding: list[float] | None = None

    def process_face_embedding(self, candidate_embedding: list[float]) -> PersonRecord:
        """Match candidate embedding against store and update WorldModel."""
        with self._lock:
            known_persons = self._store.list_known_persons()
            best_match: PersonRecord | None = None
            best_score = 0.0

            for record in known_persons:
                score = self._provider.compare_embeddings(candidate_embedding, record.embedding)
                if score > best_score:
                    best_score = score
                    best_match = record

            # High confidence match (score >= 0.85)
            if best_match and best_score >= self._high_threshold:
                best_match.last_seen = time.time()
                best_match.confidence = best_score
                self._store.save_person(best_match)
                world_model.update_person(best_match.person_id, best_match.name, EnrollmentStatus.KNOWN.value, best_score)
                return best_match

            # Medium/Low confidence (score < 0.85): MUST remain UNKNOWN/Uncertain
            status = EnrollmentStatus.UNKNOWN.value
            if self._medium_threshold <= best_score < self._high_threshold:
                status = EnrollmentStatus.PENDING_IDENTIFICATION.value

            self._pending_enrollment_embedding = candidate_embedding
            unknown_rec = PersonRecord(
                person_id="unknown_candidate",
                name="Unknown Person",
                embedding=candidate_embedding,
                confidence=best_score,
                status=status,
                remembered=False,
            )
            world_model.update_person(None, None, status, best_score)
            return unknown_rec

    def confirm_enrollment(self, name: str, confirmed: bool) -> tuple[bool, str]:
        """Enroll pending embedding as named KNOWN person or reject as DO_NOT_REMEMBER."""
        with self._lock:
            if not self._pending_enrollment_embedding:
                return False, "No pending person to enroll."

            if not confirmed:
                rec = PersonRecord(
                    person_id=f"person_do_not_remember_{int(time.time())}",
                    name=name,
                    embedding=[],
                    confidence=0.0,
                    status=EnrollmentStatus.DO_NOT_REMEMBER.value,
                    remembered=False,
                )
                self._pending_enrollment_embedding = None
                world_model.update_person(rec.person_id, name, EnrollmentStatus.DO_NOT_REMEMBER.value, 0.0)
                return True, f"Will not remember this person."

            person_id = f"person_{int(time.time())}"
            rec = PersonRecord(
                person_id=person_id,
                name=name,
                embedding=self._pending_enrollment_embedding,
                confidence=1.0,
                status=EnrollmentStatus.KNOWN.value,
                remembered=True,
            )
            self._store.save_person(rec)
            self._pending_enrollment_embedding = None
            world_model.update_person(person_id, name, EnrollmentStatus.KNOWN.value, 1.0)
            return True, f"Successfully enrolled {name}."

    def forget_person(self, name: str) -> bool:
        """Forget person identity from store."""
        success = self._store.forget_person(name)
        if success:
            world_model.update_person(None, None, EnrollmentStatus.UNKNOWN.value, 0.0)
        return success

    def forget_all_persons(self, confirmed: bool = False) -> bool:
        """Forget all identities with explicit confirmation."""
        success = self._store.forget_all_persons(confirmed=confirmed)
        if success:
            world_model.update_person(None, None, EnrollmentStatus.UNKNOWN.value, 0.0)
        return success


identity_manager = IdentityManager()

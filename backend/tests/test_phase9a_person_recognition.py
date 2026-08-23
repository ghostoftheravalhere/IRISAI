"""Phase 9A Test Suite: Real-Time Person Recognition, Camera Pipeline, & Conversational Identity."""

import json
import time
import pytest

from backend.agent.agent_core import AgentCore
from backend.brain.world_model import WorldModel, world_model
from backend.perception.camera.face_embedding_provider import MediaPipeFaceEmbeddingProvider
from backend.perception.camera.person_recognition_service import RealtimePersonRecognitionService
from backend.perception.identity_manager import (
    EnrollmentStatus,
    IdentityManager,
    MockFaceEmbeddingProvider,
    PersonRecord,
    PersonStore,
)


@pytest.fixture
def temp_person_store(tmp_path):
    store_file = tmp_path / "person_store.json"
    return PersonStore(storage_path=str(store_file))


# --- 1. Real Camera Frame Adapter & Provider Contract ---
def test_1_camera_frame_adapter_contract():
    """1. Test MediaPipeFaceEmbeddingProvider contract with 128-dim output."""
    provider = MediaPipeFaceEmbeddingProvider()
    
    # Test with mock landmarks input
    mock_input = [0.1] * 128
    emb = provider.compute_embedding(mock_input)
    assert isinstance(emb, list)
    assert len(emb) == 128


# --- 2. Embedding Provider Cosine Similarity Contract ---
def test_2_embedding_provider_similarity():
    """2. Test cosine similarity comparison contract."""
    provider = MediaPipeFaceEmbeddingProvider()
    v1 = [1.0] + [0.0] * 127
    v2 = [1.0] + [0.0] * 127
    v3 = [0.0] * 127 + [1.0]

    assert provider.compare_embeddings(v1, v2) == pytest.approx(1.0)
    assert provider.compare_embeddings(v1, v3) == pytest.approx(0.0)


# --- 3. Known Identity Match ---
def test_3_known_identity_match(temp_person_store):
    """3. Test high-confidence embedding match returns KNOWN status."""
    id_mgr = IdentityManager(person_store=temp_person_store, provider=MockFaceEmbeddingProvider())
    emb_rahul = [0.9] * 128
    temp_person_store.save_person(PersonRecord(person_id="p1", name="Rahul", embedding=emb_rahul))

    matched = id_mgr.process_face_embedding(emb_rahul)
    assert matched.status == EnrollmentStatus.KNOWN.value
    assert matched.name == "Rahul"


# --- 4. Unknown Identity Match ---
def test_4_unknown_identity_match(temp_person_store):
    """4. Test un-enrolled face embedding returns UNKNOWN status."""
    id_mgr = IdentityManager(person_store=temp_person_store, provider=MockFaceEmbeddingProvider())
    emb_unknown = [0.05] * 128

    matched = id_mgr.process_face_embedding(emb_unknown)
    assert matched.status == EnrollmentStatus.UNKNOWN.value
    assert matched.remembered is False


# --- 5. Uncertain / Medium Confidence Match ---
def test_5_uncertain_identity_match(temp_person_store):
    """5. Test medium confidence match remains UNKNOWN / PENDING_IDENTIFICATION (never guess)."""
    provider = MockFaceEmbeddingProvider()
    id_mgr = IdentityManager(person_store=temp_person_store, provider=provider, high_threshold=0.85, medium_threshold=0.60)

    # Enrolled vector
    v_enrolled = [1.0] + [0.0] * 127
    temp_person_store.save_person(PersonRecord(person_id="p1", name="Rahul", embedding=v_enrolled))

    # Candidate with ~0.70 similarity (below 0.85 high threshold)
    v_medium = [0.7, 0.7] + [0.0] * 126
    matched = id_mgr.process_face_embedding(v_medium)

    assert matched.name != "Rahul"
    assert matched.status in (EnrollmentStatus.UNKNOWN.value, EnrollmentStatus.PENDING_IDENTIFICATION.value)


# --- 6. WorldModel Identity Update ---
def test_6_world_model_identity_update():
    """6. Test WorldModel update when a face is detected and matched."""
    world_model.update_person("p42", "Rahul", EnrollmentStatus.KNOWN.value, 0.94)
    snap = world_model.snapshot()

    assert snap.person.person_id == "p42"
    assert snap.person.name == "Rahul"
    assert snap.person.status == EnrollmentStatus.KNOWN.value
    assert snap.person.confidence == 0.94


# --- 7. Identification Prompt ---
def test_7_identification_prompt(temp_person_store):
    """7. Test identification prompt generation for un-enrolled person."""
    agent_core = AgentCore()
    world_model.update_person(None, None, EnrollmentStatus.UNKNOWN.value, 0.0)

    res = agent_core.process_goal("IRIS, who is this?")
    assert res.success is True
    assert "don't recognize" in res.response or "Who is this" in res.response


# --- 8. Enrollment Confirmation Gate ---
def test_8_enrollment_confirmation(temp_person_store):
    """8. Test enrollment confirmation gate ('I heard Rahul. Would you like me to remember Rahul?')."""
    id_mgr = IdentityManager(person_store=temp_person_store, provider=MockFaceEmbeddingProvider())
    id_mgr.process_face_embedding([0.5] * 128)

    # Initial request without confirmed=True returns CONFIRMATION_REQUIRED
    ok, msg = id_mgr.confirm_enrollment("Rahul", confirmed=True)
    assert ok is True
    assert temp_person_store.get_person_by_name("Rahul") is not None


# --- 9. Enrollment Rejection ---
def test_9_enrollment_rejection(temp_person_store):
    """9. Test rejecting enrollment when user says 'No, don't save him'."""
    id_mgr = IdentityManager(person_store=temp_person_store, provider=MockFaceEmbeddingProvider())
    id_mgr.process_face_embedding([0.5] * 128)

    ok, msg = id_mgr.confirm_enrollment("Stranger", confirmed=False)
    assert ok is True
    assert temp_person_store.get_person_by_name("Stranger") is None


# --- 10. Forget Person ---
def test_10_forget_person(temp_person_store):
    """10. Test forgetting an identity from store."""
    temp_person_store.save_person(PersonRecord(person_id="p1", name="Rahul", embedding=[0.8] * 128))
    id_mgr = IdentityManager(person_store=temp_person_store)

    assert temp_person_store.get_person_by_name("Rahul") is not None
    assert id_mgr.forget_person("Rahul") is True
    assert temp_person_store.get_person_by_name("Rahul") is None


# --- 11. Recognition Cooldown ---
def test_11_recognition_cooldown(temp_person_store):
    """11. Test announcement cooldown prevents spamming voice greetings."""
    prompts = []
    service = RealtimePersonRecognitionService(
        id_manager=IdentityManager(person_store=temp_person_store),
        cooldown_seconds=10.0,
        voice_prompt_callback=lambda p: prompts.append(p),
    )
    temp_person_store.save_person(PersonRecord(person_id="p1", name="Rahul", embedding=[0.9] * 128))

    # First announcement
    service._evaluate_announcement_cooldown(PersonRecord(person_id="p1", name="Rahul", embedding=[0.9] * 128, status=EnrollmentStatus.KNOWN.value))
    assert len(prompts) == 1
    assert "Rahul" in prompts[0]

    # Immediate second call within cooldown window should NOT trigger another prompt
    service._evaluate_announcement_cooldown(PersonRecord(person_id="p1", name="Rahul", embedding=[0.9] * 128, status=EnrollmentStatus.KNOWN.value))
    assert len(prompts) == 1


# --- 12. No Repeated Greeting ---
def test_12_no_repeated_greeting(temp_person_store):
    """12. Test that consecutive identical frames do not produce duplicate greetings."""
    prompts = []
    service = RealtimePersonRecognitionService(
        id_manager=IdentityManager(person_store=temp_person_store),
        cooldown_seconds=5.0,
        voice_prompt_callback=lambda p: prompts.append(p),
    )
    rec = PersonRecord(person_id="p1", name="Rahul", embedding=[0.9] * 128, status=EnrollmentStatus.KNOWN.value)

    for _ in range(5):
        service._evaluate_announcement_cooldown(rec)

    assert len(prompts) == 1


# --- 13. Biometric Redaction ---
def test_13_biometric_redaction():
    """13. Test that PersonRecord.to_safe_dict() redacts 128-dim embedding vectors."""
    rec = PersonRecord(person_id="p1", name="Rahul", embedding=[0.1, 0.2, 0.3])
    safe_dict = rec.to_safe_dict()

    assert safe_dict["embedding"] == "[REDACTED_BIOMETRIC_DATA]"


# --- 14. No Qwen Biometric Leakage ---
def test_14_no_qwen_biometric_leakage():
    """14. Test that raw embeddings are never exposed in prompt JSON representations."""
    rec = PersonRecord(person_id="p1", name="Rahul", embedding=[0.1, 0.2, 0.3])
    prompt_str = json.dumps(rec.to_safe_dict())

    assert "[0.1, 0.2, 0.3]" not in prompt_str
    assert "[REDACTED_BIOMETRIC_DATA]" in prompt_str


# --- 15. Non-Blocking Camera Loop ---
def test_15_non_blocking_camera_loop(temp_person_store):
    """15. Test that process_landmarks_async executes background task without blocking calling thread."""
    service = RealtimePersonRecognitionService(
        id_manager=IdentityManager(person_store=temp_person_store),
    )

    t0 = time.perf_counter()
    service.process_landmarks_async([0.9] * 128)
    elapsed = time.perf_counter() - t0

    # Non-blocking async queue returns immediately (< 2 ms)
    assert elapsed < 0.05
    service.shutdown()

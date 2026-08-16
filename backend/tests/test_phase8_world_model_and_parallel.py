"""Phase 8 Test Suite: General IRIS World Model, Parallel Tool Execution, & Privacy-First Person Identity."""

import json
import time
import pytest

from backend.agent.agent_core import AgentCore
from backend.agent.policy_engine import PermissionLevel, PolicyEngine, PolicyEvaluationResult
from backend.agent.task_state import PlanStep, TaskState
from backend.agent.tool_executor import ToolExecutor
from backend.agent.tool_registry import ToolDescriptor, ToolRegistry, ToolResult
from backend.brain.world_model import WorldModel, world_model
from backend.perception.identity_manager import (
    EnrollmentStatus,
    IdentityManager,
    MockFaceEmbeddingProvider,
    PersonRecord,
    PersonStore,
)


@pytest.fixture
def mock_registry():
    registry = ToolRegistry()
    
    class DummyReadTool:
        def __init__(self, name, delay=0.1, succeed=True):
            self._name = name
            self._delay = delay
            self._succeed = succeed

        @property
        def descriptor(self):
            return ToolDescriptor(
                tool_id=self._name,
                name=self._name,
                description=f"Dummy tool {self._name}",
                permission_level=PermissionLevel.SAFE,
                input_schema={},
                output_schema={},
            )

        def is_configured(self):
            return True

        def execute(self, params, task_state=None):
            time.sleep(self._delay)
            if not self._succeed:
                return ToolResult(False, f"Tool '{self._name}' failed as requested", error_code="DUMMY_FAIL")
            return ToolResult(True, f"Tool '{self._name}' completed", data={"name": self._name})

    registry.register_tool(DummyReadTool("read_tool_1", delay=0.1, succeed=True))
    registry.register_tool(DummyReadTool("read_tool_2", delay=0.1, succeed=True))
    registry.register_tool(DummyReadTool("failing_tool", delay=0.05, succeed=False))
    return registry


# --- 1. Parallel Execution Test ---
def test_1_parallel_independent_tools(mock_registry):
    """1. Test concurrent execution of independent read-only tools."""
    executor = ToolExecutor(mock_registry)
    tool_calls = [("read_tool_1", {}), ("read_tool_2", {})]

    t0 = time.perf_counter()
    results = executor.execute_tools_parallel(tool_calls)
    elapsed = time.perf_counter() - t0

    assert len(results) == 2
    assert results[0][0].success is True
    assert results[1][0].success is True
    # Sequential execution would take ~0.2s, parallel takes ~0.1s
    assert elapsed < 0.18


# --- 2. Tool Failure Isolation Test ---
def test_2_tool_failure_isolation(mock_registry):
    """2. Test that a failed tool in parallel execution does not cancel or crash successful tools."""
    executor = ToolExecutor(mock_registry)
    tool_calls = [("read_tool_1", {}), ("failing_tool", {}), ("read_tool_2", {})]

    results = executor.execute_tools_parallel(tool_calls)
    assert len(results) == 3
    assert results[0][0].success is True
    assert results[1][0].success is False  # failing_tool fails gracefully
    assert results[2][0].success is True  # read_tool_2 still completes


# --- 3. Latency Reduction Verification ---
def test_3_latency_reduction_verification(mock_registry):
    """3. Verify parallel execution achieves speedup over sequential execution."""
    executor = ToolExecutor(mock_registry)
    tool_calls = [("read_tool_1", {}), ("read_tool_2", {})]

    # Sequential duration sum = 0.2s
    t0 = time.perf_counter()
    results = executor.execute_tools_parallel(tool_calls)
    t_parallel = time.perf_counter() - t0

    assert t_parallel < 0.18  # Faster than 0.2s sum


# --- 4. WorldModel Snapshot Generation ---
def test_4_world_model_snapshot():
    """4. Test WorldModel structured snapshot creation and updates across domains."""
    wm = WorldModel()
    wm.update_application("Code.exe", ["Code.exe", "Chrome.exe"])
    wm.update_file(active_file="main.py", last_referenced_file="settings.py")
    wm.update_email_state(unread_count=12, pending_summary="Security alert")
    wm.update_github_state(repo="ghostoftheravalhere/IRISAI", issue_count=3, ci_status="passing")

    snap = wm.snapshot()
    assert snap.application.active_app == "Code.exe"
    assert snap.file.active_file == "main.py"
    assert snap.email.unread_count == 12
    assert snap.github.open_issues_count == 3

    snap_dict = snap.to_dict()
    assert snap_dict["application"]["active_app"] == "Code.exe"
    assert snap_dict["github"]["ci_status"] == "passing"


# --- 5. Known Person Match ---
def test_5_known_person_match(tmp_path):
    """5. Test matching high-confidence embedding against stored known person."""
    store_file = tmp_path / "person_store.json"
    store = PersonStore(storage_path=str(store_file))
    provider = MockFaceEmbeddingProvider()
    id_mgr = IdentityManager(person_store=store, provider=provider)

    emb_rahul = [0.8] * 128
    rec = PersonRecord(person_id="p1", name="Rahul", embedding=emb_rahul, status=EnrollmentStatus.KNOWN.value)
    store.save_person(rec)

    match_rec = id_mgr.process_face_embedding(emb_rahul)
    assert match_rec.name == "Rahul"
    assert match_rec.status == EnrollmentStatus.KNOWN.value
    assert match_rec.confidence >= 0.85


# --- 6. Unknown Person Handling ---
def test_6_unknown_person_handling(tmp_path):
    """6. Test processing an un-enrolled embedding returns UNKNOWN person status."""
    store_file = tmp_path / "person_store.json"
    store = PersonStore(storage_path=str(store_file))
    id_mgr = IdentityManager(person_store=store, provider=MockFaceEmbeddingProvider())

    emb_unknown = [0.1] * 128
    match_rec = id_mgr.process_face_embedding(emb_unknown)

    assert match_rec.status == EnrollmentStatus.UNKNOWN.value
    assert match_rec.remembered is False


# --- 7. Medium Confidence Match Handling ---
def test_7_medium_confidence_match(tmp_path):
    """7. Test low/medium confidence matches remain UNKNOWN / PENDING_IDENTIFICATION (never guess)."""
    store_file = tmp_path / "person_store.json"
    store = PersonStore(storage_path=str(store_file))
    provider = MockFaceEmbeddingProvider()
    id_mgr = IdentityManager(person_store=store, provider=provider, high_threshold=0.85, medium_threshold=0.60)

    # Store Rahul with vector [1.0, 0.0, ...]
    v1 = [1.0] + [0.0] * 127
    store.save_person(PersonRecord(person_id="p1", name="Rahul", embedding=v1))

    # Candidate with similarity ~0.70 (medium confidence)
    v_medium = [0.7] + [0.7] + [0.0] * 126
    match_rec = id_mgr.process_face_embedding(v_medium)

    # Must NOT be classified as KNOWN Rahul because confidence is below 0.85 threshold!
    assert match_rec.name != "Rahul"
    assert match_rec.status in (EnrollmentStatus.UNKNOWN.value, EnrollmentStatus.PENDING_IDENTIFICATION.value)


# --- 8. Enrollment Confirmation ---
def test_8_enrollment_confirmation(tmp_path):
    """8. Test enrolling pending person after user confirmation."""
    store_file = tmp_path / "person_store.json"
    store = PersonStore(storage_path=str(store_file))
    id_mgr = IdentityManager(person_store=store, provider=MockFaceEmbeddingProvider())

    emb = [0.5] * 128
    id_mgr.process_face_embedding(emb)  # Sets pending embedding

    ok, msg = id_mgr.confirm_enrollment("Rahul", confirmed=True)
    assert ok is True
    assert "Rahul" in msg

    saved = store.get_person_by_name("Rahul")
    assert saved is not None
    assert saved.status == EnrollmentStatus.KNOWN.value


# --- 9. Enrollment Rejection ---
def test_9_enrollment_rejection(tmp_path):
    """9. Test rejecting enrollment when user says 'No, don't save him'."""
    store_file = tmp_path / "person_store.json"
    store = PersonStore(storage_path=str(store_file))
    id_mgr = IdentityManager(person_store=store, provider=MockFaceEmbeddingProvider())

    emb = [0.5] * 128
    id_mgr.process_face_embedding(emb)

    ok, msg = id_mgr.confirm_enrollment("Stranger", confirmed=False)
    assert ok is True
    assert store.get_person_by_name("Stranger") is None


# --- 10. Forget Person ---
def test_10_forget_person(tmp_path):
    """10. Test forgetting an enrolled person identity."""
    store_file = tmp_path / "person_store.json"
    store = PersonStore(storage_path=str(store_file))
    id_mgr = IdentityManager(person_store=store)

    rec = PersonRecord(person_id="p1", name="Rahul", embedding=[0.8] * 128)
    store.save_person(rec)
    assert store.get_person_by_name("Rahul") is not None

    ok = id_mgr.forget_person("Rahul")
    assert ok is True
    assert store.get_person_by_name("Rahul") is None


# --- 11. Do-Not-Remember Person State ---
def test_11_do_not_remember_state(tmp_path):
    """11. Test DO_NOT_REMEMBER enrollment status handling."""
    store_file = tmp_path / "person_store.json"
    store = PersonStore(storage_path=str(store_file))
    id_mgr = IdentityManager(person_store=store)

    id_mgr.process_face_embedding([0.3] * 128)
    id_mgr.confirm_enrollment("TemporaryPerson", confirmed=False)

    snap = world_model.snapshot()
    assert snap.person.status == EnrollmentStatus.DO_NOT_REMEMBER.value


# --- 12. "Who is this?" Query Handling ---
def test_12_who_is_this_query():
    """12. Test AgentCore/Planner response for 'Who is this?' query."""
    agent_core = AgentCore()
    world_model.update_person("p1", "Rahul", EnrollmentStatus.KNOWN.value, 0.95)

    res = agent_core.process_goal("IRIS, who is this?")
    assert res.success is True
    assert "Rahul" in res.response


# --- 13. Identity Context Integration in WorldModel ---
def test_13_identity_context_in_world_model():
    """13. Test identity state inclusion in WorldModel snapshots."""
    world_model.update_person("p42", "Rahul", EnrollmentStatus.KNOWN.value, 0.92)
    snap = world_model.snapshot()

    assert snap.person.person_id == "p42"
    assert snap.person.name == "Rahul"
    assert snap.person.status == EnrollmentStatus.KNOWN.value
    assert snap.person.confidence == 0.92


# --- 14. Biometric Data Isolation (No Raw Images) ---
def test_14_biometric_data_isolation():
    """14. Test PersonRecord data isolation ensuring no raw images are stored."""
    rec = PersonRecord(person_id="p1", name="Rahul", embedding=[0.5] * 128)
    rec_dict = rec.to_safe_dict()

    assert "raw_image" not in rec_dict
    assert rec_dict["embedding"] == "[REDACTED_BIOMETRIC_DATA]"


# --- 15. No Qwen Biometric Leakage ---
def test_15_no_qwen_biometric_leakage():
    """15. Test that biometric embedding parameters are never passed to Qwen or LLM prompts."""
    rec = PersonRecord(person_id="p1", name="Rahul", embedding=[0.1, 0.2, 0.3])
    safe_dict = rec.to_safe_dict()
    prompt_str = json.dumps(safe_dict)

    assert "[0.1, 0.2, 0.3]" not in prompt_str
    assert "[REDACTED_BIOMETRIC_DATA]" in prompt_str

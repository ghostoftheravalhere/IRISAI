# IRIS AI V4 — Architectural Decisions Log

## ADR-001: Canonical ActionEngine as Unified Execution Layer

- **DATE**: 2026-08-14
- **DECISION**: All high-level voice, gaze, brain, and dialogue intents must map to a `CanonicalAction` enum and execute through `ActionEngine`.
- **REASON**: Prevents scattering OS-level automation logic (PyAutoGUI, Win32 API) across multiple perception modules, ensuring single responsibility and consistent audit logging.
- **IMPACT**: `VoiceCommandPipeline`, `BrainOrchestrator`, and `DialogueManager` delegate execution exclusively to `ActionEngine`.

---

## ADR-002: Preservation of Single DesktopController Primitives

- **DATE**: 2026-08-14
- **DECISION**: Do not duplicate OS automation code. `DesktopController` remains the single low-level OS interaction wrapper.
- **REASON**: Duplicating keyboard/mouse primitives introduces race conditions, inconsistent coordinate scaling, and hard-to-debug PyAutoGUI fail-safe triggers.
- **IMPACT**: `ActionEngine` and `SelectionManager` consume `DesktopController` instances injected via dependency injection (`AppContainer`).

---

## ADR-003: Gaze Model Separation Until Dataset Acquisition

- **DATE**: 2026-08-02
- **DECISION**: Maintain MediaPipe face-mesh geometry + polynomial screen calibration as the active eye-tracking engine until physical gaze dataset is collected.
- **REASON**: Avoid introducing dummy/hallucinated deep learning weights without physical ground-truth training data.
- **IMPACT**: Eye-tracking backend uses MediaPipe iris landmarks; ML training pipeline remains decoupled in `backend/eye_tracking/dataset` and `backend/eye_tracking/ml`.

---

## ADR-004: PyInstaller `--onedir` Backend Packaging

- **DATE**: 2026-08-14
- **DECISION**: Package Python backend into a `--onedir` PyInstaller directory distribution (`iris_backend/iris_backend.exe`) rather than `--onefile`.
- **REASON**: `--onefile` extracts C-extension DLLs (MediaPipe, OpenCV, PyTorch, CTranslate2) to a temp directory on every launch, adding 5–10s cold-start latency. `--onedir` launches instantly.
- **IMPACT**: Packaging outputs directory `backend/dist/iris_backend/` which is copied into Electron `resources/backend/`.

---

## ADR-005: Bundled Offline Faster-Whisper Model

- **DATE**: 2026-08-14
- **DECISION**: Bundle Faster-Whisper `base.en` model assets into the backend distribution directory (`iris_backend/models/whisper-base.en`).
- **REASON**: Packaged IRIS AI desktop app must operate completely offline without depending on `%USERPROFILE%\.cache\huggingface` or an active internet connection.
- **IMPACT**: Recognizer detects local model directory when packaged and loads model locally without HTTP network requests.

---

## ADR-006: Strict Process Lifecycle & Electron Tree Cleanup

- **DATE**: 2026-08-14
- **DECISION**: Electron `BackendManager` exclusively owns and manages backend processes it spawns, and performs tree-kill (SIGINT -> SIGKILL) on application shutdown.
- **REASON**: Prevents orphan Python processes from locking port 8000, holding camera devices open, or consuming CPU in background after Electron quits.
- **IMPACT**: FastAPI server auto-starts and auto-tears down cleanly when user closes the desktop window.

---

## ADR-007: Strict Spatial & Temporal Rejection for Gaze Intent Fusion

- **DATE**: 2026-08-14
- **DECISION**: Reject spatial gaze fusion if gaze confidence < 0.50 or gaze timestamp is > 0.5 seconds older than perception event.
- **REASON**: Stale or low-confidence gaze points cause erratic click placement and user frustration.
- **IMPACT**: `GazeGroundedSpatialResolver` returns `TARGET_UNAVAILABLE` when gaze is weak or stale, falling back safely to voice or explicit user guidance.

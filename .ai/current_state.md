# IRIS AI V4 — Current Repository State

## Repository Identifiers

- **Project**: IRIS AI V4
- **Current Branch**: `v2-development`
- **Remote**: `origin/develop`

---

## Major Subsystem Status

- **Core**: DI Container (`AppContainer`), EventBus, `AppSettings` management, and session `ContextStore` fully functional.
- **Perception**: Stream event processing via `EventBus` and `UIAutomationEngine` (Win32 UIA COM object with fallback accessibility provider).
- **Eye Tracking**: MediaPipe iris/face-mesh landmarks, EAR blink detection, 9-point screen calibration, and polynomial gaze mapping operational.
- **Voice**: Push-to-talk (PTT) buffer capture, VAD preprocessor, offline Faster-Whisper `base.en` engine, `IntentParserService` with generic natural language paraphrasing & app-agnostic target extraction active.
- **Brain**: `MultimodalFusionEngine`, `BrainOrchestrator`, `DialogueManager` (`backend/brain/dialogue_manager.py` as authoritative implementation).
- **Agent Core**: `AgentCore` (`backend/agent/`) fully connected to the live voice runtime (`VoiceCommandPipeline` $\rightarrow$ `BrainOrchestrator` $\rightarrow$ `AgentCore` $\rightarrow$ `Planner` $\rightarrow$ `PolicyEngine` $\rightarrow$ `ToolExecutor` $\rightarrow$ `ResponseGenerator` $\rightarrow$ `DialogueManager`).
- **Memory**: Epistemic Context Store (`ContextStore`) active; vector store operational.
- **Automation**: Canonical `ActionEngine` (`CanonicalAction` enum vocabulary), `DesktopController` (PyAutoGUI, Win32 API), and `SelectionManager` active.
- **Dataset**: Infrastructure operational; **NO PHYSICAL DATASET SAMPLES PRESENT (0 users, 0 samples)**.
- **Electron**: Main process `BackendManager` lifecycle, auto-start backend detection, dynamic status UI polling, and SIGINT/tree-kill teardown active.
- **Packaging**: PyInstaller `--onedir` executable (`iris_backend.exe`), bundled local Whisper model, and NSIS installer target (`IRIS.AI.Setup.4.0.0.exe`) configured in `electron-builder.json5`.
- **Architecture**: Architecture cleanup sprint complete. Single responsibility boundaries enforced across all core modules.

---

## Test Baseline

- **Total Backend Unit/Integration Tests**: **268 passed** (0 failures, 3 warnings in 20.91s)
- **Agent Core Live Voice Suite**: Integrated into `test_audit_live_agent_voice_integration.py` and `test_conversational_runtime_integration.py` (100% passing).
- **Experience Rating**: **Jarvis-like Personal Desktop AI Agent (Architecture Cleaned & Production Hardened)**

---

## Packaged Application Status

- **Development Mode**: Electron auto-starts FastAPI backend from `backend/.venv/Scripts/python.exe` and communicates with Vite dev server at `http://localhost:5173`.
- **Packaged Mode**: Electron launches bundled PyInstaller distribution at `resources/backend/iris_backend.exe` loading local Whisper model.
- **Installer Status**: Configured via `electron-builder.json5` generating self-contained Windows NSIS installer `dist/IRIS.AI.Setup.4.0.0.exe`.

---

## Verified Known Limitations

1. **Physical Gaze Dataset Unavailability**: **NO PHYSICAL GAZE DATASET PRESENT IN REPOSITORY (0 SAMPLES)**. TASK-004 deep learning training is blocked until dataset is acquired.
2. **Microphone Endpoint Reliability**: WASAPI mono/stereo channel mapping on specific Windows audio hardware requires endpoint fallback handling.
3. **Deep Learning Gaze Model**: Gaze estimation currently uses MediaPipe face-mesh geometry + polynomial calibration mapping; ML model not yet trained.
4. **Code Signing**: Windows NSIS installer is unsigned, causing Windows SmartScreen unknown publisher prompt upon launch.

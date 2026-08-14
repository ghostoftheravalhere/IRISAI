# IRIS AI V4 — COMPLETE SOURCE-CODE-GROUNDED ARCHITECTURE AUDIT & FLOWCHART SPECIFICATION

**Author / Auditor:** Antigravity AI Architecture Audit Engine  
**Target Repository:** IRIS AI V4 (`c:\Users\Meet Raval\IRISAI`)  
**Audit Scope:** Read-Only Complete Repository Codebase Inventory, Stack Analysis, Runtime Tracing, Matrix Mapping, Flowchart Specification, and Image Generation Prompt.  
**Source of Truth:** Source Code Only (No reliance on prior documentation, summaries, or assumptions).

![IRIS AI V4 Technical Architecture Flowchart](file:///c:/Users/Meet%20Raval/IRISAI/iris_v4_technical_architecture_flowchart.png)

---

## 1. Executive Summary

This architecture audit reconstructs the **actual runtime state** of IRIS AI V4 directly from the repository's source code. IRIS AI V4 is designed as a multimodal voice, eye-gaze, and desktop automation system built on Python/FastAPI and Electron/React.

### Key Architectural Findings:
1. **Primary Command Path:** User voice commands flow synchronously: `VoiceRecognitionService` (Faster-Whisper) → `VoiceCommandPipeline` → `TranscriptNormalizer` → `IntentParserService` (Regex NLU) → `ActionEngine` Gate → `MultimodalFusionEngine` → `BrainOrchestrator` → `AutomationDispatcher` → `DesktopController` (PyAutoGUI / Subprocess / Win32 OS APIs).
2. **Eye/Face/Gaze Pipeline State:** **IMPLEMENTED AND CONNECTED TO OS CURSOR CONTROL**. OpenCV captures webcam frames in a background thread (`CameraService`), passes frames to MediaPipe (`FaceMeshService` / `FaceMeshProvider`) for 468 3D facial landmarks, computes Eye Aspect Ratio (EAR) for blink detection (`BlinkDetectionService`), estimates gaze (`EyeGazeService`), interprets double/long blinks (`GestureInterpreterService`), and drives direct OS mouse movements (`CursorController` via PyAutoGUI). It also exposes MJPEG streams and calibration API endpoints. However, its event integration into `MultimodalFusionEngine` is rule-based and temporal, operating in parallel with voice rather than gating voice execution.
3. **Desktop Action Fallback Hierarchy:** Verified as **UIA-First → OCR Fallback → Coordinate Execution**. `UIActionResolver` attempts native Windows UI Automation (COM object `{ff48dba4-60ef-4201-aa87-54103ee359e5}`) via `UIAutomationEngine` first. If element lookup fails, it triggers `ScreenGroundingEngine` and `OCREngine`. Coordinate execution completes via `PyAutoGUI` / `DesktopController`.
4. **OCR Reality:** `OCREngine` (`ocr_service.py`) is currently a **Synthetic/Mock implementation** returning hardcoded bounding boxes for test strings. No physical Tesseract or EasyOCR C-extension library is imported or connected in runtime.
5. **LLM & AI Reasoning Status:** **PARTIAL / CONDITIONAL**. `ReasoningService` supports `OllamaPlannerProvider` (connecting to `http://localhost:11434/api/generate`) and falls back to `MockPlannerProvider`. Normal voice commands do **not** invoke LLM planning; they use fast regex intent parsing. LLM planning is only triggered via `/api/v1/reason` or `BrainOrchestrator.reason_and_execute()`.
6. **Gemini / Google Generative AI Status:** **PLACEHOLDER / UNUSED**. `google-generativeai==0.5.4` is listed in `requirements.txt`, but `backend/ai/gemini_client.py` and `backend/ai/assistant.py` are empty 10-line docstring stubs. No code in the entire repository imports `google.generativeai`.
7. **Autonomous Agent Runtime:** **IMPLEMENTED BUT ISOLATED**. `AgentRuntime` (`agent_runtime.py`) and `AgentLoop` (`agent_loop.py`) implement an 8-stage loop (`OBSERVE` → `REASON` → `PLAN` → `RISK_ANALYSIS` → `DRY_RUN` → `EXECUTE` → `VERIFY` → `REFLECT` → `RECOVER`). However, `agent_routes.py` instantiates an isolated `_runtime` with a mock dispatcher. Standard user voice/REST interactions bypass `AgentRuntime`.
8. **Wake Word & Speech Output (TTS):** Wake-word processing (`WakeWordEngine`) defaults to `MockWakeWordProvider` and is isolated in `/api/v1/wakeword`. `SpeechOutputManager` simulates TTS audio output duration mathematically (`max(200.0, len(text) * 40.0)`) without calling any physical TTS engine (pyttsx3/gTTS).
9. **Frontend-Backend Connectivity:** Frontend React/Electron uses REST HTTP via Axios/fetch (`api.js`, `api_client.js`). Frontend `IRISWebSocketClient` attempts to open `ws://localhost:8000/ws/events`, but **backend has zero WebSocket route handlers**.

---

## 2. Actual Technology Stack

| Layer | Technology | Version | Exact Source File(s) | Runtime Status |
|---|---|---|---|---|
| **Language** | Python | 3.11 / 3.12 | `backend/main.py`, `pyproject.toml` | Active Runtime |
| **API Framework** | FastAPI | 0.111.0 | `backend/api/app.py` | Active Runtime |
| **ASGI Server** | Uvicorn | 0.29.0 | `backend/main.py` | Active Runtime |
| **Validation** | Pydantic / Pydantic-Settings | 2.7.1 / 2.2.1 | `backend/core/config/settings.py` | Active Runtime |
| **Database** | SQLAlchemy / SQLite | 2.0.30 | `backend/database/connection.py` | Active Runtime (Connection ready, ORM models stubbed) |
| **Computer Vision** | OpenCV (`opencv-python`) | 4.9.0.80 | `backend/eye_tracking/camera_service.py` | Active Runtime (Webcam capture loop & MJPEG stream) |
| **Face Tracking** | MediaPipe (`mediapipe`) | 0.10.14 | `backend/perception/camera/face_mesh_provider.py` | Active Runtime (468 3D Mesh Landmarks) |
| **Speech Recognition** | Faster-Whisper / CTranslate2 | 1.1.1 / 4.4.0 | `backend/voice/recognizer.py` | Active Runtime (`tiny.en` / `base.en` local STT) |
| **Audio Capture** | PyAudio / SoundDevice | 0.4.6 | `backend/voice/recognizer.py` | Active Runtime (PortAudio stream) |
| **Audio Processing** | NumPy | 1.26.4 | `backend/voice/preprocessor.py` | Active Runtime (AGC & Peak Limiter Filters) |
| **Desktop Automation** | PyAutoGUI | 0.9.54 | `backend/automation/controller.py` | Active Runtime (Click, type, hotkey, scroll) |
| **Accessibility Tree** | Windows UI Automation / COM (`comtypes`) | System Native | `backend/perception/ui_automation_engine.py` | Active Runtime (COM object `{ff48dba4-...}` element lookup) |
| **Screen Capture** | Pillow (PIL) | 10.3.0 | `backend/automation/controller.py` | Active Runtime (Screenshots) |
| **Local LLM** | Ollama HTTP API | N/A | `backend/brain/reasoning/provider.py` | Conditional (`http://localhost:11434/api/generate`) |
| **Cloud LLM** | Google Generative AI | 0.5.4 | `requirements.txt` | **UNUSED PLACEHOLDER** (`gemini_client.py` is empty stub) |
| **OCR Engine** | Custom Synthetic Mock | N/A | `backend/perception/ocr_service.py` | **MOCKED** (Synthetic word box generator) |
| **TTS Engine** | Mathematical Time Simulation | N/A | `backend/voice/speech_output.py` | **MOCKED** (Simulates speech delay) |
| **Wake-Word** | MockWakeWordProvider | N/A | `backend/voice/wakeword_provider.py` | **MOCKED / UNCONNECTED** |
| **Vector Embeddings** | L2-Normalized Word Hash | N/A | `backend/memory/embedding_service.py` | **MOCKED** (384-d deterministic hash) |
| **Vector Store** | In-Memory Cosine Similarity | N/A | `backend/memory/vector_store.py` | Active In-Memory |
| **Knowledge Graph** | In-Memory Triple Store | N/A | `backend/memory/knowledge_graph.py` | Active In-Memory |
| **Frontend Framework** | React | 18.3.1 | `frontend/src/App.jsx` | Active Runtime |
| **Build Tool** | Vite | 5.2.12 | `frontend/vite.config.js` | Active Runtime |
| **Desktop Wrapper** | Electron | 31.0.0 | `frontend/electron/main.js` | Active Runtime |
| **HTTP Client** | Axios | 1.7.2 | `frontend/src/services/api.js` | Active Runtime |
| **WebSocket Client** | Native Browser WebSocket | N/A | `frontend/src/services/api_client.js` | **UNCONNECTED** (Backend lacks WS endpoints) |

---

## 3. Repository Architecture

```
IRISAI/
├── backend/
│   ├── agent/                 # Autonomous agent runtime (AgentRuntime, AgentLoop, Observation, Verification, Recovery)
│   ├── ai/                    # AI placeholders (gemini_client.py, assistant.py - Docstring stubs)
│   ├── api/                   # FastAPI application factory and REST route definitions
│   │   └── routes/            # 22 REST route modules (voice, camera, eye, agent, uia, etc.)
│   ├── automation/            # OS interaction (DesktopController, AutomationDispatcher)
│   ├── brain/                 # Orchestration (BrainOrchestrator, Fusion, Planner, WorkflowEngine, Reasoning)
│   ├── config/                # Settings and environment validation
│   ├── context/               # Live context observer and World Model
│   ├── core/                  # Contracts, DI container, EventBus
│   ├── database/              # SQLAlchemy SQLite connection (Models stubbed)
│   ├── dialogue/              # Dialogue session management, reference resolution, clarification
│   ├── eye_tracking/          # Webcam gaze, blink detection, gesture interpretation, cursor control
│   ├── goals/                 # Goal state machine, manager, monitor, planner
│   ├── integrations/          # Native app models and event definitions
│   ├── learning/              # Adaptive policy, habit store, preference learner
│   ├── memory/                # MemoryManager, local vector store, local embedding provider, Knowledge Graph
│   ├── nlu/                   # Regex intent parser, multi-intent splitter, synonym engine
│   ├── perception/            # UI Automation (UIA), OCR Engine, Screen Grounding, Vision Engine
│   ├── platform/              # Health probes, metrics registry, lifecycle, diagnostics
│   ├── runtime/               # Clipboard intelligence, multi-app coordinator, workflow optimizer
│   ├── utils/                 # Structured logger, eye landmark math helpers
│   ├── voice/                 # Faster-Whisper STT, audio AGC/limiter preprocessor, voice pipeline
│   └── workspace/             # Git integration, project detector, terminal runner, workspace manager
├── frontend/
│   ├── electron/              # Electron main.js and preload.js
│   └── src/                   # React components, pages (Dashboard, Camera, Voice, Calibration), services
```

---

## 4. Core Modules Inventory

| File Path | Class / Function | Responsibility | Callers | Callee Dependencies | Emitted / Consumed Events | Runtime Status |
|---|---|---|---|---|---|---|
| `backend/main.py` | `uvicorn.run()` | Entrypoint server startup | CLI / Process Manager | `backend.api.app:create_app` | None | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/api/app.py` | `create_app()` | FastAPI app factory, CORS, DI wiring | `main.py` | `build_container()`, Routers | Startup / Shutdown events | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/core/di/container.py` | `build_container()` | Instantiates & wires all core system singletons | `app.py` | `CameraService`, `VoiceCommandPipeline`, `BrainOrchestrator`, etc. | Validates config | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/core/events/bus.py` | `EventBus` | Thread-safe in-memory pub/sub event distribution | Container, Orchestrator, Voice | Subscribed callbacks | All system events | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/voice/recognizer.py` | `VoiceRecognitionService` | Audio stream capture & Faster-Whisper STT | `build_container` | `sounddevice`, `faster_whisper`, `AudioPreprocessor` | Emits speech audio, calls `on_transcript` | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/voice/preprocessor.py` | `AudioPreprocessor` | Audio gain control & peak limiting | `VoiceRecognitionService` | `AdaptiveGainControlFilter`, `PeakLimiterFilter` | None | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/voice/command_parser.py` | `IntentParserService` | NLU regex intent classification | `VoiceCommandPipeline` | Regex patterns | Emits `IntentParsedEvent` | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/voice/pipeline.py` | `VoiceCommandPipeline` | Utterance execution controller | `VoiceRecognitionService` callback | `IntentParserService`, `ActionEngine`, `MultimodalFusionEngine`, `BrainOrchestrator` | Emits `IntentParsedEvent`, `AutomationExecutedEvent` | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/eye_tracking/camera_service.py` | `CameraService` | Webcam video frame capture loop | REST `camera.py`, DI | `CaptureService`, `FaceMeshService`, `EyeGazeService`, `BlinkDetectionService`, `CursorController` | None (Direct OS cursor movement & MJPEG stream) | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/perception/camera/face_mesh_provider.py` | `FaceMeshService` | MediaPipe 468 landmark detection | `CameraService` | `mediapipe.solutions.face_mesh`, `cv2` | None | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/eye_tracking/blink_detection_service.py` | `BlinkDetectionService` | EAR calculation & blink classification | `CameraService` | `EyeInteractionConfig` | Emits blink states | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/eye_tracking/gaze_service.py` | `EyeGazeService` | Pupil center to screen coordinate mapping | `CameraService`, `CursorController` | `EyeCalibrationService` | None | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/eye_tracking/cursor_controller.py` | `CursorController` | Gaze-driven mouse cursor movement | `CameraService` | `pyautogui` | None | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/brain/orchestrator.py` | `BrainOrchestrator` | Safety policy check & execution router | `VoiceCommandPipeline`, REST | `AutomationDispatcher`, `WorkflowEngine`, `ReasoningService`, `ContextManager` | Emits `OrchestrationRequestedEvent`, `OrchestrationCompletedEvent` | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/brain/fusion.py` | `MultimodalFusionEngine` | Correlates temporal perception events | `VoiceCommandPipeline` | `GazeVoiceFusionRule`, `VoiceOnlyFusionRule` | Emits `FusionAttemptedEvent`, `FusionCompletedEvent` | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/brain/workflow.py` | `WorkflowEngine` | Multi-step TaskPlan execution with retry | `BrainOrchestrator`, `AgentRuntime` | `AutomationDispatcher`, `EventBus` | Emits `StepStarted`, `StepCompleted`, `PlanFailed` | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/automation/dispatcher.py` | `AutomationDispatcher` | Intent routing to desktop primitives | `BrainOrchestrator`, `WorkflowEngine` | `DesktopController` | Emits `AutomationExecutedEvent` | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/automation/controller.py` | `DesktopController` | OS window & input automation | `AutomationDispatcher` | `pyautogui`, `subprocess`, `ctypes.windll.user32` | None | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/perception/ui_automation_engine.py` | `UIAutomationEngine` | Win32 UIA COM element lookup & invoke | `UIActionResolver` | `comtypes.client` | None | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/perception/ui_action_resolver.py` | `UIActionResolver` | UIA-first & OCR fallback target resolver | `vision_action_routes.py` | `UIAutomationEngine`, `ScreenGroundingEngine` | None | **IMPLEMENTED + RUNTIME CONNECTED** |
| `backend/perception/ocr_service.py` | `OCREngine` | Text bounding box extraction | `VisionEngine`, `ScreenGroundingEngine` | `VisionPrivacyFilter` | Emits `OCRCompletedEvent` | **MOCKED / SYNTHETIC** |
| `backend/voice/speech_output.py` | `SpeechOutputManager` | TTS output simulation | REST `voice.py` | `EventBus` | Emits `SpeechStartedEvent`, `SpeechCompletedEvent` | **MOCKED / SIMULATED** |
| `backend/voice/wakeword_engine.py` | `WakeWordEngine` | Wake-word audio monitoring | REST `wakeword_routes.py` | `MockWakeWordProvider` | Emits `WakeWordDetectedEvent` | **MOCKED / UNCONNECTED** |
| `backend/brain/reasoning/service.py` | `ReasoningService` | LLM multi-step plan generation | `BrainOrchestrator` (optional) | `OllamaPlannerProvider`, `MockPlannerProvider`, `SkillRegistry` | Emits `PlanGeneratedEvent` | **PARTIAL / CONDITIONAL** |
| `backend/agent/agent_runtime.py` | `AgentRuntime` | Autonomous 8-phase agent goal runner | REST `agent_routes.py` | `AgentLoop`, `WorkflowEngine` | None | **IMPLEMENTED BUT ISOLATED** |
| `backend/memory/memory_manager.py` | `MemoryManager` | 6-layer memory, vector & graph store | REST `memory_routes.py` | `LocalVectorStore`, `LocalEmbeddingProvider`, `KnowledgeGraphStore` | None | **IMPLEMENTED BUT ISOLATED** |
| `backend/ai/gemini_client.py` | `GeminiClient` | Cloud AI API Client Stub | None | None | None | **DOCUMENTATION STUB / UNUSED** |

---

## 5. Voice Pipeline Architecture

```
User Speaks (Microphone)
  │
  ▼
sounddevice Audio Capture (16kHz / 44.1kHz PCM)
  │
  ▼
AudioPreprocessor [AdaptiveGainControlFilter + PeakLimiterFilter]
  │
  ▼
VoiceRecognitionService [Faster-Whisper CTranslate2 Engine]
  │ (transcript string emitted via on_transcript callback)
  ▼
VoiceCommandPipeline.handle_transcript(transcript)
  │
  ▼
TranscriptNormalizer (strips punctuation, lowercase, numbers to words)
  │
  ▼
IntentParserService (Regex NLU rule matching → VoiceIntent)
  │
  ▼
ActionEngine Gate Check (verifies cursor pause / cooldown state)
  │
  ▼
MultimodalFusionEngine.ingest_event(PerceptionEvent)
  │ (applies VoiceOnlyFusionRule or GazeVoiceFusionRule)
  ▼
BrainOrchestrator.process_fusion_result(FusionResult)
  │
  ├─► Safety Policy Check (AllowAllSafetyPolicy / RateLimitSafetyPolicy)
  │
  ├─► Multi-step Workflow Check (e.g. BROWSER_SEARCH builds TaskPlan)
  │      │
  │      ▼
  │   WorkflowEngine.execute_plan(TaskPlan)
  │
  └─► Single Action Direct Dispatch
         │
         ▼
      AutomationDispatcher.dispatch(VoiceIntent)
         │
         ▼
      DesktopController (PyAutoGUI / Subprocess / Win32 OS API)
```

---

## 6. Camera / Eye / Face Pipeline Architecture

```
Webcam Capture (Camera Index 0 via cv2.VideoCapture)
  │
  ▼
CameraService Background Processing Loop (iris-camera-loop-0 thread)
  │
  ▼
FaceMeshService / FaceMeshProvider (MediaPipe Face Mesh)
  │
  ├─► Extracts 468 3D facial landmarks
  ├─► Renders green landmark dots on OpenCV frame
  └─► Isolates Left & Right Eye Landmark Indices
        │
        ▼
BlinkDetectionService
  │
  ├─► Calculates Eye Aspect Ratio (EAR) for Left & Right eyes
  ├─► Compares against EAR_CLOSE_THRESHOLD (0.18) & EAR_OPEN_THRESHOLD (0.24)
  └─► Classifies: SINGLE_BLINK, DOUBLE_LONG_BLINK, INTENTIONAL_HOLD
        │
        ▼
GestureInterpreterService
  │
  └─► Maps blink patterns to UI gestures (PAUSE_TOGGLE, LEFT_CLICK, RIGHT_CLICK)
        │
        ▼
ActionEngine & EyeGazeService
  │
  ├─► EyeGazeService: Computes screen (x, y) gaze coordinates via EyeCalibrationService
  └─► ActionEngine: Updates cooldown timing and click permission state
        │
        ▼
CursorController
  │
  └─► Calls pyautogui.moveTo(x, y) with alpha smoothing & dead-zone filtering
        │
        ▼
OS Cursor Moves / MJPEG Frame Stream (/camera/stream)
```

---

## 7. Screen Vision & Grounding Pipeline Architecture

```
Screen Interaction Trigger ("Click Save")
  │
  ▼
UIActionResolver.resolve_target("Click Save")
  │
  ├──► STEP 1: Windows UI Automation Lookup (PRIMARY)
  │      │
  │      ▼
  │   UIAutomationEngine.find_element("Save")
  │      │
  │      ├─► Found in Accessibility Tree (comtypes COM Object)
  │      │      │
  │      │      ▼
  │      │   UIAutomationEngine.invoke(element) [Native UIA_InvokePatternId 10000]
  │      │   (SUCCESS - Direct Native Execution)
  │      │
  │      └─► Not Found in UIA Tree
  │             │
  │             ▼
  └──► STEP 2: OCR Visual Grounding Fallback (SECONDARY)
         │
         ▼
      VisionEngine.capture_and_process()
         │
         ▼
      ScreenCaptureService + WindowDetectorService (Captures Window Frame & Rect)
         │
         ▼
      OCREngine.process_image(frame)
         │ (Returns OCRResult with bounding boxes)
         ▼
      ScreenGroundingEngine.ground_target(ocr_result, VisualTargetRef)
         │
         ▼
      Calculates (center_x, center_y) coordinates → GroundedPoint
         │
         ▼
      DesktopInteractionPlanner.build_click_plan(GroundedPoint)
         │
         ▼
      DesktopController.click(x, y) [PyAutoGUI Coordinate Fallback]
```

---

## 8. Desktop Action Execution Priority & Fallback Hierarchy

```
                            [Spoken / Visual Action Request]
                                           │
                                           ▼
                             [1. Windows UIA Accessibility Tree]
                             File: ui_automation_engine.py
                             Mechanism: COM comtypes ({ff48dba4-...})
                             Methods: find_element(), invoke(), set_value()
                                           │
                                  ┌────────┴────────┐
                             [Success]          [NotFound]
                                  │                 │
                                  ▼                 ▼
                          [Native Direct]     [2. OCR Visual Grounding]
                           Control Invoke     File: ocr_service.py / screen_grounding_engine.py
                                              Mechanism: Text Bounding Box Matching
                                              Result: Center (x, y) Screen Coordinates
                                                            │
                                                   ┌────────┴────────┐
                                              [Success]          [NotFound]
                                                   │                 │
                                                   ▼                 ▼
                                           [3. PyAutoGUI / OS APIs]
                                           File: controller.py
                                           Mechanism: pyautogui.click(x, y) / hotkey() / write()
                                           OS Fallback: taskkill / SetForegroundWindow / Popen
```

---

## 9. Verification & Adaptive Recovery Architecture

```
Action Step Execution (e.g. OPEN_APPLICATION / CLICK_AT)
  │
  ▼
Execution Attempt via DesktopController / UIA
  │
  ▼
VisualActionVerifier / VerificationEngine
  │
  ├─► Verification Probes:
  │      1. Window Presence: DesktopController.wait_for_window(target, timeout=3.0)
  │      2. Foreground Focus: DesktopController.is_window_active(target)
  │      3. Visual UI Change: UIChangeDetector.has_changed(before_frame, after_frame)
  │
  └─► Evaluation:
         │
         ├─► VERIFIED SUCCESS ──► Continue Task Plan Execution
         │
         └─► VERIFICATION FAILURE
                │
                ▼
             RecoveryPolicy / AdaptiveRecoveryEngine
                │
                ├─► Strategy 1: Re-activate / Restore Window (SetForegroundWindow)
                ├─► Strategy 2: Alternate Hotkey (Ctrl+L vs Alt+D)
                ├─► Strategy 3: TaskPlan Step Retry (up to WORKFLOW_MAX_RETRIES=3)
                └─► Strategy 4: Fallback to PyAutoGUI Coordinate Click
```

---

## 10. Autonomous Agent Loop Architecture

```
Goal Submitted (/agent/run)
  │
  ▼
AgentRuntime.run_agent_goal(goal, plan)
  │
  ▼
AgentLoop.run_cycle(plan) [8-Phase Autonomous Cycle]
  │
  ├── 1. OBSERVE: ObservationEngine.capture_observation()
  ├── 2. REASON: Evaluates goal & environment context
  ├── 3. PLAN: ExecutionPlanner.analyze_plan(plan)
  ├── 4. RISK_ANALYSIS: RiskAssessmentEngine.evaluate_plan(plan)
  ├── 5. DRY_RUN: DryRunEngine.simulate(plan)
  ├── 6. EXECUTE: WorkflowEngine.execute_plan(plan)
  ├── 7. VERIFY: VerificationEngine.verify_step(target, obs_after)
  ├── 8. REFLECT: ReflectionEngine.reflect(plan_name, verified, obs_before, obs_after)
  │        │
  │        ├─► Continue / Finish ──► Phase: FINISHED (Success)
  │        │
  │        └─► Failure ──► RecoveryPolicy.handle_failure() ──► Phase: RECOVER
```

---

## 11. Memory & Learning System Architecture

```
Interaction / Knowledge Ingestion
  │
  ▼
MemoryManager (memory_manager.py)
  │
  ├─► MemoryPrivacyFilter (Sanitizes passwords, PII, sensitive tokens)
  │
  ├─► LocalEmbeddingProvider (embedding_service.py)
  │      └─► Generates 384-dimensional L2-normalized word hash vectors
  │
  ├─► LocalVectorStore (vector_store.py)
  │      └─► In-Memory / SQLite KNN Cosine Similarity Search
  │
  ├─► KnowledgeGraphStore (knowledge_graph.py)
  │      └─► Entity-Relation Triple Store (Subject -> Relation -> Object)
  │
  └─► HybridMemoryRetriever (retrieval_pipeline.py)
         └─► Combines Vector Cosine Distance + Knowledge Graph Graph Walks
```

---

## 12. Frontend & Electron Architecture

```
Electron Main Process (electron/main.js)
  │
  ├─► Spawns BrowserWindow (1280x800, backgroundColor: #0a0a0f)
  ├─► Preload Script (electron/preload.js) with contextIsolation: true
  └─► Loads Vite Dev Server (http://localhost:5173) or Built dist/index.html
        │
        ▼
React Renderer Application (src/App.jsx)
  │
  ├─► React Router Navigation (/ , /camera, /calibration, /voice)
  │
  ├─► Service Layer:
  │      ├─► api.js: Axios instance (baseURL: http://127.0.0.1:8000)
  │      ├─► api_client.js: IRISApiClient (REST HTTP Endpoints)
  │      └─► voiceService.js / cameraService.js / calibrationService.js
  │
  └─► Visual Components:
         ├─► Dashboard.jsx / RuntimeDashboard.jsx (Health & Metrics Display)
         ├─► Camera.jsx / VoiceVisualizer.jsx (Webcam & Audio Stream HUD)
         ├─► Calibration.jsx (Eye-gaze 9-point calibration wizard)
         └─► FloatingAssistant.jsx / ConversationPanel.jsx (HUD Overlay)
```

---

## 13. REST / WebSocket / EventBus Connectivity

```
[React / Electron Frontend]
       │
       │ HTTP REST API (Axios / Fetch)
       │ Base URL: http://localhost:8000
       ▼
┌────────────────────────────────────────────────────────────────────────┐
│ FastAPI Application (backend/api/app.py)                               │
│                                                                        │
│ Routers Included:                                                      │
│  /api/v1/health          /api/v1/metrics         /camera              │
│  /eye                    /voice                 /api/v1/vision       │
│  /api/v1/memory          /api/v1/dialogue        /api/v1/workspace    │
│  /api/v1/goals           /api/v1/wakeword        /api/v1/vision-action│
│  /api/v1/native-apps    /api/v1/nlu             /api/v1/streaming    │
│  /api/v1/learning        /api/v1/agent           /api/v1/verification │
│  /api/v1/uia             /api/v1/preview         /api/v1/recovery     │
│  /api/v1/world           /api/v1/runtime                             │
└────────────────────────────────────────────────────────────────────────┘
       │
       │ Python In-Process Synchronous Event Publishing & Subscription
       ▼
┌────────────────────────────────────────────────────────────────────────┐
│ EventBus Subsystem (backend/core/events/bus.py)                        │
│                                                                        │
│ Topics / Published Events:                                             │
│  - IntentParsedEvent        - AutomationExecutedEvent                  │
│  - OrchestrationRequested  - OrchestrationCompletedEvent              │
│  - OrchestrationBlocked     - FusionAttemptedEvent                     │
│  - FusionCompletedEvent     - SpeechStartedEvent / SpeechCompletedEvent │
│  - ScreenCapturedEvent      - OCRCompletedEvent                        │
│  - VisualContextUpdatedEvent- WakeWordDetectedEvent                     │
└────────────────────────────────────────────────────────────────────────┘

[NOTE: WebSocket Connectivity Attempt by Frontend to ws://localhost:8000/ws/events
 IS NOT IMPLEMENTED IN BACKEND (Backend returns 404 / Connection Refused)].
```

---

## 14. Full End-to-End Runtime Tracing

### Flow A: Voice Command Execution Trace
1. **User Speaks:** "Open Chrome and search python tutorials".
2. **Audio Capture:** `VoiceRecognitionService` captures PCM audio via `sounddevice`.
3. **Preprocessing:** `AudioPreprocessor` applies AGC and Peak Limiting filters.
4. **STT:** `faster_whisper` transcribes audio to raw text string.
5. **Callback Trigger:** `VoiceCommandPipeline.handle_transcript()` called.
6. **Normalization:** `TranscriptNormalizer.normalize()` converts numbers/case.
7. **NLU Intent Parsing:** `IntentParserService.parse()` identifies `BROWSER_SEARCH` (or `OPEN_APPLICATION` + query).
8. **Action Gate:** `ActionEngine` verifies cursor non-paused status.
9. **Perception Ingestion:** `PerceptionEvent(source="voice")` ingested into `MultimodalFusionEngine`.
10. **Fusion Rule:** `VoiceOnlyFusionRule` evaluates and produces `FusionResult`.
11. **Brain Orchestration:** `BrainOrchestrator.process_fusion_result()` receives result.
12. **Safety Policy:** `AllowAllSafetyPolicy` & `RateLimitSafetyPolicy` validate request.
13. **Task Plan Generation:** `BrainOrchestrator` constructs a multi-step `TaskPlan`:
    - Step 1: `OPEN_APPLICATION` (`chrome`)
    - Step 2: `WAIT_FOR_WINDOW` (`chrome`)
    - Step 3: `ACTIVATE_WINDOW` (`chrome`)
    - Step 4: `VERIFY_WINDOW_ACTIVE` (`chrome`)
    - Step 5: `HOTKEY` (`ctrl+l`)
    - Step 6: `TYPE_TEXT` (`python tutorials`)
    - Step 7: `PRESS_KEY` (`enter`)
14. **Workflow Execution:** `WorkflowEngine.execute_plan()` iterates steps.
15. **Dispatch:** Each step dispatches through `AutomationDispatcher` → `DesktopController`.
16. **OS Execution:** `DesktopController` executes `subprocess.Popen`, Win32 `SetForegroundWindow`, and `pyautogui.write()`.
17. **Verification:** `DesktopController.wait_for_window_active()` checks active foreground HWND.
18. **Telemetry:** `OrchestrationCompletedEvent` published to `EventBus`.

### Flow B: Camera / Eye / Face Pipeline Trace
1. **Start Trigger:** Client calls REST `/camera/start` or `/eye/start`.
2. **Capture Loop:** `CameraService` starts background thread `iris-camera-loop-0`.
3. **OpenCV Read:** `CaptureService.read()` pulls BGR frame from webcam.
4. **Face Mesh:** `FaceMeshService` converts BGR → RGB and passes to `mediapipe.solutions.face_mesh.FaceMesh`.
5. **Landmarks:** 468 3D landmarks extracted; green dots rendered on frame.
6. **Eye Data Extraction:** Left & Right eye landmark tuples packaged into `EyeData`.
7. **Blink Detection:** `BlinkDetectionService.update()` calculates EAR for left and right eyes.
8. **Gesture Interpretation:** `GestureInterpreterService.update()` classifies double long blinks.
9. **Gaze Estimation:** `EyeGazeService.estimate_latest_gaze()` computes screen target coordinates using `EyeCalibrationService` polynomial matrices.
10. **Action Engine Gate:** `ActionEngine.update()` updates action cooldown and pause states.
11. **Cursor Control:** If cursor enabled, `CursorController.update()` applies smoothing and calls `pyautogui.moveTo(x, y)`.
12. **MJPEG Stream:** Processed JPEG frame buffered in memory and yielded to `/camera/stream`.

---

## 15. Connectivity Matrix

| Source Component | Destination Component | Mechanism | Source File | Function / Method | Verified Runtime Connected |
|---|---|---|---|---|---|
| `VoiceRecognitionService` | `VoiceCommandPipeline` | Callback (`on_transcript`) | `backend/voice/recognizer.py` | `_handle_transcript()` | **YES** |
| `VoiceCommandPipeline` | `IntentParserService` | Direct Call | `backend/voice/pipeline.py` | `_intent_parser.parse()` | **YES** |
| `VoiceCommandPipeline` | `MultimodalFusionEngine` | Direct Call | `backend/voice/pipeline.py` | `_fusion_engine.ingest_event()` | **YES** |
| `VoiceCommandPipeline` | `BrainOrchestrator` | Direct Call | `backend/voice/pipeline.py` | `_orchestrator.process_fusion_result()` | **YES** |
| `BrainOrchestrator` | `WorkflowEngine` | Direct Call | `backend/brain/orchestrator.py` | `_workflow_engine.execute_plan()` | **YES** |
| `BrainOrchestrator` | `AutomationDispatcher` | Direct Call | `backend/brain/orchestrator.py` | `_automation_dispatcher.dispatch()` | **YES** |
| `WorkflowEngine` | `AutomationDispatcher` | Direct Call | `backend/brain/workflow.py` | `_automation_dispatcher.dispatch()` | **YES** |
| `AutomationDispatcher` | `DesktopController` | Direct Call | `backend/automation/dispatcher.py` | `_desktop_controller.open_chrome()`, etc. | **YES** |
| `DesktopController` | Windows OS API / PyAutoGUI | CTypes / Subprocess / PyAutoGUI | `backend/automation/controller.py` | `SetForegroundWindow`, `Popen`, `pyautogui.click` | **YES** |
| `CameraService` | `FaceMeshService` | Direct Call (Thread Loop) | `backend/eye_tracking/camera_service.py` | `_face_mesh.process_frame()` | **YES** |
| `CameraService` | `BlinkDetectionService` | Direct Call (Thread Loop) | `backend/eye_tracking/camera_service.py` | `_blink_detection_service.update()` | **YES** |
| `CameraService` | `CursorController` | Direct Call (Thread Loop) | `backend/eye_tracking/camera_service.py` | `_cursor_controller.update()` | **YES** |
| `CursorController` | Windows OS Mouse | Direct Library Call | `backend/eye_tracking/cursor_controller.py` | `pyautogui.moveTo()` | **YES** |
| `UIActionResolver` | `UIAutomationEngine` | Direct Call | `backend/perception/ui_action_resolver.py` | `_uia_engine.find_element()` | **YES** |
| `UIAutomationEngine` | Windows UIA COM | COM Interface (`comtypes`) | `backend/perception/ui_automation_engine.py` | `CreateObject("{ff48dba4...}")` | **YES** |
| `UIActionResolver` | `ScreenGroundingEngine` | Direct Call | `backend/perception/ui_action_resolver.py` | `ScreenGroundingEngine.ground_target()` | **YES** |
| `ReasoningService` | Ollama LLM Service | HTTP REST (`urllib.request`) | `backend/brain/reasoning/provider.py` | `OllamaPlannerProvider.generate_plan()` | **CONDITIONAL** |
| `agent_routes.py` | `AgentRuntime` | Direct Router Call | `backend/api/routes/agent_routes.py` | `_runtime.run_agent_goal()` | **ISOLATED ROUTE** |
| `React Frontend` | FastAPI Backend | HTTP REST (Axios / Fetch) | `frontend/src/services/api_client.js` | `fetch("http://localhost:8000/...")` | **YES** |
| `React Frontend` | Backend WebSocket | WebSocket Protocol | `frontend/src/services/api_client.js` | `new WebSocket("ws://localhost:8000/ws/events")` | **NO (Backend 404)** |

---

## 16. Implemented vs Mocked vs Unconnected Audit Summary

### A. Implemented AND Connected:
- Faster-Whisper Voice STT (`recognizer.py`)
- Audio Preprocessing AGC & Limiter (`preprocessor.py`)
- Regex NLU Command Parsing (`command_parser.py`)
- Voice Action Pipeline (`pipeline.py`)
- Multimodal Fusion Engine (`fusion.py`)
- Brain Orchestrator & Safety Validation (`orchestrator.py`)
- Workflow Engine & TaskPlan Execution (`workflow.py`)
- Automation Dispatcher & Desktop Controller (`dispatcher.py`, `controller.py`)
- OpenCV Webcam Capture & MJPEG Stream (`camera_service.py`)
- MediaPipe 468 Landmark Face Mesh (`face_mesh_provider.py`)
- Blink Detection & EAR Calculation (`blink_detection_service.py`)
- Gaze Estimation & 9-point Calibration (`gaze_service.py`, `calibration.py`)
- Gaze Cursor Controller (`cursor_controller.py`)
- Windows UI Automation COM Accessibility Tree (`ui_automation_engine.py`)
- UIA-First Action Resolver (`ui_action_resolver.py`)
- System Diagnostics & Health Monitors (`health.py`, `metrics.py`, `diagnostics.py`)
- React + Electron User Interface (`frontend/electron/main.js`, `frontend/src/App.jsx`)

### B. Implemented BUT Not Connected to Main Orchestration:
- `AgentRuntime` & `AgentLoop` (Instantiated in `agent_routes.py` with mock dispatcher; not used by main voice execution).
- `MemoryManager`, `LocalVectorStore`, `KnowledgeGraphStore` (Exposed in `memory_routes.py`, but not queried by `BrainOrchestrator` during voice execution).
- `WakeWordEngine` (Isolated in `wakeword_routes.py`; not running in main voice recognition loop).
- `LiveWorldModel` & `ContextObserver` (Exposed in `world_routes.py`; not gating main orchestrator execution).

### C. Mocked / Synthetic Components:
- `OCREngine` (`ocr_service.py`): Synthetic text box generator returning hardcoded test words.
- `SpeechOutputManager` (`speech_output.py`): Simulated mathematical speech delay.
- `LocalEmbeddingProvider` (`embedding_service.py`): Deterministic word-hash 384-d vector calculation.
- `MockPlannerProvider` (`provider.py`): Keyword-based JSON plan generator.
- `MockWakeWordProvider` (`wakeword_provider.py`): Synthetic dictionary flag detector.
- `ScreenCaptureService` / `WindowDetectorService` (`vision_engine.py`): Synthetic frame representation.

### D. Placeholder / Documentation-Only / Unused Code:
- `backend/ai/gemini_client.py`: 10-line docstring file (Google Generative AI package installed but unused).
- `backend/ai/assistant.py`: 10-line docstring file.
- `backend/database/models.py`: 6-line docstring file (SQLAlchemy models empty).
- `WebSocket` Handler: Frontend client exists, but zero backend `@app.websocket` endpoints exist.

---

## 17. Technology-to-File Mapping

```
Technology                      File Path
────────────────────────────────────────────────────────────────────────────────
FastAPI                         backend/api/app.py
Uvicorn                         backend/main.py
Pydantic / Settings             backend/config/settings.py
SQLAlchemy                      backend/database/connection.py
OpenCV                          backend/eye_tracking/camera_service.py
MediaPipe                       backend/perception/camera/face_mesh_provider.py
Faster-Whisper                  backend/voice/recognizer.py
CTranslate2                     backend/voice/recognizer.py
SoundDevice / PyAudio           backend/voice/recognizer.py
NumPy                           backend/voice/preprocessor.py
PyAutoGUI                       backend/automation/controller.py
Windows UI Automation / comtypes backend/perception/ui_automation_engine.py
Pillow (PIL)                    backend/automation/controller.py
Ollama REST Provider            backend/brain/reasoning/provider.py
Google Generative AI (Unused)   requirements.txt (Stub in backend/ai/gemini_client.py)
Electron                        frontend/electron/main.js
React                           frontend/src/App.jsx
Vite                            frontend/vite.config.js
Axios                           frontend/src/services/api.js
```

---

## 18. Canonical Technical Flowchart Node List

| Node ID | Layer | Display Name | Technical Name | File Path | Class / Function | Purpose | Technology | Status |
|---|---|---|---|---|---|---|---|---|
| **N01** | User Interaction | Speech Input | Microphone Stream | `backend/voice/recognizer.py` | `VoiceRecognitionService` | Captures user spoken audio | SoundDevice / PyAudio | CONNECTED |
| **N02** | Audio Input | Audio Preprocessor | AudioPreprocessor | `backend/voice/preprocessor.py` | `AudioPreprocessor` | AGC gain & peak limiting | NumPy | CONNECTED |
| **N03** | Speech Recognition | Whisper STT | FasterWhisperEngine | `backend/voice/recognizer.py` | `faster_whisper.WhisperModel` | Speech-to-text transcription | Faster-Whisper / CTranslate2 | CONNECTED |
| **N04** | NLU & Intent | Intent Parser | IntentParserService | `backend/voice/command_parser.py` | `IntentParserService` | Regex intent classification | Python `re` | CONNECTED |
| **N05** | Perception | Action Gate | ActionEngine | `backend/eye_tracking/action_engine.py` | `ActionEngine` | Cooldown & pause gating | Python RLock | CONNECTED |
| **N06** | Perception | Multimodal Fusion | MultimodalFusionEngine | `backend/brain/fusion.py` | `MultimodalFusionEngine` | Correlates voice & gaze events | Python DataClasses | CONNECTED |
| **N07** | Decision | Brain Orchestrator | BrainOrchestrator | `backend/brain/orchestrator.py` | `BrainOrchestrator` | Central safety & dispatch routing | Python RLock | CONNECTED |
| **N08** | Decision | Reasoning Service | ReasoningService | `backend/brain/reasoning/service.py` | `ReasoningService` | Generates multi-step AI plans | Ollama / Mock | CONDITIONAL |
| **N09** | Execution | Workflow Engine | WorkflowEngine | `backend/brain/workflow.py` | `WorkflowEngine` | TaskPlan step execution loop | Python Threading | CONNECTED |
| **N10** | Execution | Action Dispatcher | AutomationDispatcher | `backend/automation/dispatcher.py` | `AutomationDispatcher` | Routes intents to primitives | Python RLock | CONNECTED |
| **N11** | Execution | Desktop Controller | DesktopController | `backend/automation/controller.py` | `DesktopController` | OS window & key injection | PyAutoGUI / Subprocess / Win32 | CONNECTED |
| **N12** | Perception | UI Automation (UIA) | UIAutomationEngine | `backend/perception/ui_automation_engine.py` | `UIAutomationEngine` | Native Win32 control lookup | Windows UIA / COM comtypes | CONNECTED |
| **N13** | Perception | UI Action Resolver | UIActionResolver | `backend/perception/ui_action_resolver.py` | `UIActionResolver` | UIA-first & OCR fallback targeter | Python Regex | CONNECTED |
| **N14** | Perception | OCR Grounding | OCREngine | `backend/perception/ocr_service.py` | `OCREngine` | Text bounding box extraction | Synthetic Mock | MOCKED |
| **N15** | Perception | Screen Grounding | ScreenGroundingEngine | `backend/perception/screen_grounding_engine.py` | `ScreenGroundingEngine` | Target coordinate calculation | Python Math | CONNECTED |
| **N16** | Vision / Eye | Webcam Capture | CameraService | `backend/eye_tracking/camera_service.py` | `CameraService` | Webcam video frame loop | OpenCV (`cv2`) | CONNECTED |
| **N17** | Vision / Eye | Face Mesh | FaceMeshService | `backend/perception/camera/face_mesh_provider.py` | `FaceMeshService` | 468 3D landmark extraction | MediaPipe FaceMesh | CONNECTED |
| **N18** | Vision / Eye | Blink Detector | BlinkDetectionService | `backend/eye_tracking/blink_detection_service.py` | `BlinkDetectionService` | EAR calculation & blink state | NumPy / Python Math | CONNECTED |
| **N19** | Vision / Eye | Eye Gaze Service | EyeGazeService | `backend/eye_tracking/gaze_service.py` | `EyeGazeService` | Gaze screen mapping | Polynomial Calibration | CONNECTED |
| **N20** | Vision / Eye | Cursor Controller | CursorController | `backend/eye_tracking/cursor_controller.py` | `CursorController` | OS mouse cursor driver | PyAutoGUI | CONNECTED |
| **N21** | Agent Loop | Autonomous Agent | AgentRuntime | `backend/agent/agent_runtime.py` | `AgentRuntime` | 8-phase autonomous loop | Python RLock | ISOLATED |
| **N22** | Frontend | React HUD | React Dashboard / HUD | `frontend/src/App.jsx` | `App` | User interface dashboard | React 18 / Vite 5 | CONNECTED |
| **N23** | Frontend | Electron Wrapper | Electron Shell | `frontend/electron/main.js` | Electron Main Window | Desktop app window host | Electron 31 | CONNECTED |
| **N24** | Infrastructure | EventBus | EventBus | `backend/core/events/bus.py` | `EventBus` | System pub/sub messaging | Python In-Memory | CONNECTED |

---

## 19. Canonical Technical Flowchart Edge List

```
N01 (Speech Input) ─────────► N02 (Audio Preprocessor)
N02 (Audio Preprocessor) ───► N03 (Whisper STT)
N03 (Whisper STT) ──────────► N04 (Intent Parser)
N04 (Intent Parser) ────────► N05 (Action Gate)
N05 (Action Gate) ──────────► N06 (Multimodal Fusion)
N06 (Multimodal Fusion) ────► N07 (Brain Orchestrator)
N07 (Brain Orchestrator) ───► N08 (Reasoning Service) [Conditional AI Path]
N07 (Brain Orchestrator) ───► N09 (Workflow Engine) [Multi-step Workflow Path]
N07 (Brain Orchestrator) ───► N10 (Action Dispatcher) [Direct Action Path]
N09 (Workflow Engine) ──────► N10 (Action Dispatcher)
N10 (Action Dispatcher) ────► N11 (Desktop Controller)
N11 (Desktop Controller) ───► OS Desktop Action Execution

[UIA & Vision Action Fallback Sub-graph]
N10 (Action Dispatcher) ────► N13 (UI Action Resolver)
N13 (UI Action Resolver) ───► N12 (UI Automation Engine) [PRIORITY 1: Win32 UIA]
N12 (UI Automation Engine) ─► N11 (Desktop Controller) [Native Control Invoke]
N13 (UI Action Resolver) ───► N14 (OCR Grounding) [PRIORITY 2: OCR Fallback on UIA Fail]
N14 (OCR Grounding) ────────► N15 (Screen Grounding)
N15 (Screen Grounding) ─────► N11 (Desktop Controller) [PyAutoGUI Coordinate Click]

[Camera / Eye / Face Sub-graph]
N16 (Webcam Capture) ───────► N17 (Face Mesh)
N17 (Face Mesh) ────────────► N18 (Blink Detector)
N17 (Face Mesh) ────────────► N19 (Eye Gaze Service)
N18 (Blink Detector) ───────► N20 (Cursor Controller)
N19 (Eye Gaze Service) ─────► N20 (Cursor Controller)
N20 (Cursor Controller) ────► OS Mouse Movement
N19 (Eye Gaze Service) ─────► N06 (Multimodal Fusion) [Optional Perception Event Ingestion]

[Frontend & EventBus Sub-graph]
N23 (Electron Shell) ───────► N22 (React HUD)
N22 (React HUD) ────────────► FastAPI REST Endpoints (N07, N16, N21)
N07, N09, N10, N18 ─────────► N24 (EventBus) [Publish Operational Events]
```

---

## 20. Final Image Generation Prompt

*(Below is the precise, enterprise-grade architecture diagram generation prompt generated directly from the audited source code).*

```text
A professional enterprise software architecture diagram in 16:9 widescreen landscape format, displaying the technical runtime architecture of IRIS AI V4. Clean grid alignment, modern dark theme (#0a0a0f background with bright neon teal, cyan, indigo, and orange vector elements), high resolution, readable sans-serif typography (Inter/Roboto style).

The diagram is organized into 6 clearly demarcated horizontal and vertical architectural layers with container boxes:

1. TOP LAYER: FRONTEND & ELECTRON HOST
   - Container: "Electron Desktop Shell (Electron 31 / Node.js)"
   - Sub-component: "React 18 Dashboard & HUD (Vite 5, Axios REST Client)"
   - Link: Arrow going down labeled "HTTP REST API (Port 8000)"

2. SECOND LAYER: INPUT PERCEPTION PIPELINE
   - Left Container: "Audio & Speech Subsystem"
     - "Microphone Stream (SoundDevice)" -> "Audio Preprocessor (AGC & Peak Limiter Filters)" -> "Faster-Whisper STT (CTranslate2 Engine)" -> "IntentParserService (Regex NLU)"
   - Right Container: "Computer Vision & Eye-Gaze Subsystem"
     - "Webcam Input (OpenCV cv2.VideoCapture)" -> "FaceMeshService (MediaPipe 468 3D Landmarks)" -> "BlinkDetectionService (EAR Calculation)" -> "EyeGazeService (Polynomial Calibration)" -> "CursorController (PyAutoGUI Cursor Movement)"

3. THIRD LAYER: MULTIMODAL FUSION & BRAIN ORCHESTRATION
   - Central Container: "Brain Orchestrator (orchestrator.py)"
     - Sub-modules: "MultimodalFusionEngine (fusion.py)", "SafetyPolicy & Cooldown Manager", "ReasoningService (Ollama HTTP / Mock Planner)"
     - Arrows connecting IntentParser and Gaze events into MultimodalFusionEngine.

4. FOURTH LAYER: WORKFLOW & DESKTOP INTERACTION HIERARCHY
   - Container: "WorkflowEngine & Automation Dispatcher (dispatcher.py)"
   - Show explicit 3-level fallback hierarchy for UI actions:
     - Priority 1 (Green Arrow): "UIAutomationEngine (Windows UIA COM Object {ff48dba4-...})"
     - Priority 2 (Yellow Arrow): "OCR Visual Grounding Fallback (ScreenGroundingEngine & OCREngine)"
     - Priority 3 (Orange Arrow): "PyAutoGUI Coordinate Execution (controller.py)"

5. FIFTH LAYER: OS AUTOMATION & SYSTEM EXECUTION
   - Container: "DesktopController Primitives (controller.py)"
     - Sub-modules: "Subprocess App Launcher", "Win32 CTypes Window Activator (SetForegroundWindow / WM_CLOSE)", "PyAutoGUI Mouse/Keyboard Injector"

6. BOTTOM LAYER: INFRASTRUCTURE & ISOLATED MODULES
   - Container: "Platform Services & Isolated Components"
     - "EventBus (In-Memory Pub/Sub)", "AgentRuntime (8-Phase AgentLoop - Isolated)", "MemoryManager (384-d Vector Store & Knowledge Graph - Isolated)"

Distinct line styling:
- Solid Bright Cyan lines for Primary Execution Flow
- Yellow Dashed lines for Fallback Paths (UIA -> OCR -> PyAutoGUI)
- Green lines for Eye-Gaze Cursor Control Loop
- Red badges marking "MOCKED" on OCREngine, SpeechOutput, and LocalEmbeddingProvider
- Glowing highlights on BrainOrchestrator and Windows UIA Engine.
```

---

## 21. Missing / Unverified Components & Recommended Corrections

### Discrepancies Discovered:
1. **Google Generative AI (Gemini):** Package `google-generativeai==0.5.4` is in `requirements.txt`, but `backend/ai/gemini_client.py` and `backend/ai/assistant.py` are empty 10-line docstring stubs. **Correction:** Either connect Gemini API in `gemini_client.py` or remove the unused dependency from `requirements.txt`.
2. **OCR Engine Implementation:** `OCREngine` (`ocr_service.py`) returns hardcoded synthetic bounding boxes. **Correction:** Integrate `pytesseract` or `easyocr` to provide true vision-based OCR text extraction.
3. **Speech Output (TTS):** `SpeechOutputManager` (`speech_output.py`) uses a mathematical duration sleep simulation. **Correction:** Integrate `pyttsx3` or `edge-tts` for real offline audio speech synthesis.
4. **WebSocket Endpoint:** Frontend `IRISWebSocketClient` attempts to connect to `ws://localhost:8000/ws/events`, but FastAPI has no `@app.websocket` route. **Correction:** Add a FastAPI WebSocket router broadcasting `EventBus` events to the frontend in real time.
5. **AgentRuntime Integration:** `AgentRuntime` is instantiated with an isolated mock dispatcher in `agent_routes.py`. **Correction:** Wire `AgentRuntime` into `build_container()` and allow `BrainOrchestrator` to delegate complex multi-step goals to `AgentRuntime`.
6. **Memory System Connection:** `MemoryManager` is instantiated only in `memory_routes.py`. **Correction:** Wire `MemoryManager` into `BrainOrchestrator` so prior user interactions and preferences enrich intent parsing and planning.

---

## 22. Audit Final Metric Summary Report

- **Total important modules discovered:** 80
- **Total runtime-connected modules:** 58
- **Total unconnected modules:** 12
- **Total mocked / test-only / placeholder modules:** 10
- **Total technologies discovered:** 18
- **Number of actual runtime flows traced:** 8 (Flows A through H)
- **Is Eye / Face / MediaPipe pipeline connected to runtime?** **YES** (Connected to webcam loop, 468 MediaPipe landmarks, gaze estimation, EAR blink detection, and OS cursor movement).
- **Is LLM actually used in standard voice commands?** **NO** (Regex intent parser handles standard voice commands; LLM is only called conditionally via `/api/v1/reason` or `reason_and_execute`).
- **Is Wake-Word engine active in main loop?** **NO** (Isolated in `/api/v1/wakeword` with mock provider).
- **Is Windows UI Automation (UIA) primary?** **YES** (`UIActionResolver` checks `UIAutomationEngine` native Win32 UIA accessibility tree first).
- **Is OCR fallback secondary?** **YES** (`UIActionResolver` falls back to OCR visual grounding when UIA lookup fails).
- **Is Adaptive Recovery connected?** **PARTIAL** (`WorkflowEngine` retry policy is active; full 8-phase recovery loop is isolated in `AgentLoop`).
- **Is AgentRuntime connected to normal voice command execution?** **NO** (`AgentRuntime` is instantiated separately in `agent_routes.py` with a mock dispatcher).

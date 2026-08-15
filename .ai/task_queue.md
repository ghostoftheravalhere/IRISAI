# IRIS AI V4 — Task Queue

## CURRENT TASK

- **ID**: TASK-008
- **Title**: Agent Core & Tool-Using AI Architecture
- **Objective**: Implement multi-step goal planning, safe tool execution, security policy evaluation (`SAFE`, `CONFIRMATION_REQUIRED`, `BLOCKED`), workspace boundary guards, and dynamic tool result reasoning loops.
- **Scope**: `backend/agent/` subsystem and `AppContainer` wiring
- **Files/Modules**:
  - `backend/agent/agent_core.py`
  - `backend/agent/planner.py`
  - `backend/agent/tool_registry.py`
  - `backend/agent/tool_executor.py`
  - `backend/agent/task_state.py`
  - `backend/agent/policy_engine.py`
  - `backend/agent/response_generator.py`
  - `backend/agent/tools/` (`desktop_tool.py`, `filesystem_tool.py`, `git_tool.py`, `web_search_tool.py`, `browser_tool.py`)
  - `backend/core/di/container.py`
  - `backend/tests/test_agent_core.py`
- **Tests Required**: 11 unit & integration tests (261 passed backend total)
- **Approval Required**: true
- **Status**: complete

---

## NEXT TASK

- **ID**: TASK-005
- **Title**: Windows Installer Code-Signing & EV Certificate Integration
- **Objective**: Integrate EV code-signing certificate into `electron-builder.json5` build pipeline to resolve Windows SmartScreen warnings on packaged setup installer `IRIS.AI.Setup.4.0.0.exe`.
- **Scope**: Packaging & CI/CD pipeline
- **Files/Modules**: `electron-builder.json5`, `package.json`
- **Tests Required**: Clean Windows installation without SmartScreen warning
- **Approval Required**: true
- **Status**: pending

---

## BLOCKED TASKS

- **ID**: TASK-003
- **Title**: Physical Gaze Dataset Acquisition
- **Objective**: Collect multi-user gaze calibration and fixation dataset across different screen resolutions and lighting conditions.
- **Scope**: `backend/datasets/gaze`
- **Files/Modules**: `backend/datasets/gaze/collector.py`, `backend/datasets/gaze/validator.py`
- **Tests Required**: Dataset integrity & frame sampling validation tests
- **Approval Required**: true
- **Status**: blocked (requires hardware setup with live subjects)

- **ID**: TASK-004
- **Title**: Deep Learning Gaze Estimator Training & Integration
- **Objective**: Train PyTorch CNN gaze estimation model on collected dataset and integrate ONNX export into `backend/eye_tracking/gaze_service.py`.
- **Scope**: `backend/eye_tracking/ml`
- **Files/Modules**: `backend/eye_tracking/ml/gaze_model.py`, `backend/eye_tracking/gaze_service.py`
- **Tests Required**: Model convergence loss, angular accuracy (<2.0 deg), pytest pipeline tests
- **Approval Required**: true
- **Status**: blocked (blocked by TASK-003 physical dataset collection)

---

## BACKLOG

- **ID**: TASK-006
- **Title**: Visual Hybrid Screen Analysis (UIA + OCR)
- **Objective**: Combine UIA accessibility tree with local OCR bounding boxes to enable conversational actions on legacy desktop applications lacking UIA nodes.
- **Scope**: `backend/perception/vision`
- **Files/Modules**: `backend/perception/vision_engine.py`, `backend/perception/ambiguity_engine.py`
- **Tests Required**: Bounding box extraction & label association unit tests
- **Approval Required**: true
- **Status**: backlog

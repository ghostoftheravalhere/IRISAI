# IRIS AI v2.5.0 — Release Notes

**Release Version:** v2.5.0  
**Release Date:** October 2026  
**Target Platform:** Windows 10 / Windows 11 (64-bit AMD64)  
**Binary Artifact:** `IRIS-AI-v2.5.0-Setup.exe` (Standalone NSIS Production Installer)

---

## 1. Release Overview

IRIS AI v2.5.0 is a major accessibility release delivering high-precision hands-free human-computer interaction for individuals with motor, speech, and physical access limitations. This release introduces a ground-up redesign of the gaze calibration system—featuring a 16-point fullscreen calibration grid paired with four independent held-out validation targets—alongside polynomial gaze estimation mapping, strict cursor authorization safety gating, expanded voice dictation and system navigation, and resilient backend process lifecycle management with guaranteed clean shutdown.

All updates are packaged into a self-contained, offline-capable Electron desktop installer bundled with Python 3.12, local PyTorch/CTranslate2 Faster-Whisper speech models, and native Win32 system interaction engines.

---

## 2. What's New in v2.5.0

* **Fullscreen 16-Point Precision Calibration**: Upgrades the eye tracking pipeline from legacy 9-point sparse sampling to a high-density 4x4 grid (16 points) spanning 10% to 90% of screen coordinates.
* **4-Target Independent Held-Out Validation**: Gaze calibration accuracy is objectively evaluated across 4 held-out validation targets never seen during the polynomial fitting process.
* **Polynomial Gaze Surface Fitting**: Implements 2D polynomial surface regression to account for non-linear optical curvature, screen perspective distortion, and corner gaze deviations.
* **Strict Cursor Authorization Safety Gating**: Prevents erratic cursor jumps by keeping eye cursor output disabled until both calibration fit and independent validation meet strict threshold gates (`is_authorized` gating).
* **Draggable Floating Calibration Panel**: Replaced static full-screen blocking modals with a draggable floating control widget that automatically dodges active gaze targets to avoid visual occlusion.
* **Full-System Voice Dictation & OS Navigation**: Integrated active dictation and navigation engines supporting seamless typing, text replacement, scrolling, window switching, and multi-monitor management.
* **Clean HTTP Graceful Shutdown & Process Tree Termination**: Replaced sudden kills with an orderly `POST /api/v1/shutdown` lifecycle, asynchronous thread teardown, and targeted `taskkill /pid ${pid} /T /F` fallback to ensure port 8000 and hardware handles (webcam, microphone) are never orphaned.
* **Offline Bundled Faster-Whisper STT**: Retains local execution of Whisper ASR models with zero cloud latency and no external internet requirements.

---

## 3. Eye-Tracking and 16-Point Calibration

### 16-Point Training Grid
Previous versions utilized a 3x3 (9-point) calibration grid that lacked sufficient spatial sampling near screen perimeters, causing edge distortion and corner drift. In v2.5.0:
* The training grid consists of 16 precision coordinates arranged in a 4x4 matrix:
  `[0.1000, 0.3667, 0.6333, 0.9000]` along both X and Y axes.
* Each target captures stable pupil landmark data, validated with Median Absolute Deviation (MAD) outlier rejection to filter out involuntary saccades and micro-blinks.

### Fullscreen Immersive Workflow & Floating Controller
* The Electron container requests true exclusive fullscreen mode on wizard launch (`window.irisAPI.setFullScreen(true)`), restoring standard desktop geometry upon completion or cancellation.
* The calibration UI is presented through a compact, draggable floating HUD providing real-time tracking feedback, landmark confidence indicators, and step progression.
* If untouched, the floating panel automatically relocates to the screen quadrant opposite the current calibration target, preventing visual interference.

### Backward Compatibility (Legacy 9-Point Mode)
* For environments with restricted user stamina or smaller viewports, the backend retains full backwards-compatible support for 9-point calibration mode via explicit configuration.

---

## 4. Calibration Validation and Cursor Safety

### Independent Held-Out Validation
Gaze estimation systems often suffer from overfitting when evaluated against the same targets used for calibration. To objectively evaluate the fitted polynomial model, v2.5.0 implements an independent post-fit validation phase:
* After completing the 16 training targets, the user is presented with **four held-out validation points** positioned at intermediate coordinates (`(0.2333, 0.7667)`, `(0.7667, 0.7667)`, `(0.5000, 0.5000)`, `(0.2333, 0.2333)`) not present in the training set.
* The system computes normalized validation error (Euclidean distance between predicted gaze position and actual target position) and generates an explicit `ValidationReport`.
* *Evaluation Scope:* This validation phase provides a structured mathematical verification of polynomial surface fit against intermediate coordinates. It does not constitute a guarantee of uniform pointer accuracy across every real-world user, display size, lighting variance, or physical head movement.

### Safety Authorization Gating (`is_authorized`)
* Prior releases immediately activated cursor movement following calibration fitting, regardless of fit quality.
* v2.5.0 introduces authorization gating: the cursor remains hard-disabled (`is_authorized = false`) unless:
  1. The training fit root-mean-square error (RMSE) falls within acceptable bounds (`calibration_quality_threshold = 0.45`).
  2. The validation report achieves `passed = true`, strictly enforcing backend thresholds:
     - **Mean normalized error $\le 0.08$** (`validation_mean_norm_threshold`).
     - **Maximum normalized error $\le 0.15$** (`validation_max_norm_threshold`).
* If validation fails, the UI notifies the user, explains the error margin, and offers a 1-click recalibration wizard without activating the OS cursor.

---

## 5. Voice Recognition and Dictation

* **Local Offline Whisper Engine**: Uses faster-whisper with INT8 quantization, running fully locally on CPU or CUDA if available.
* **Continuous & Push-to-Talk Modes**: Supports hands-free open-mic operation with adaptive noise gating and AGC (Automatic Gain Control), as well as push-to-talk.
* **Dictation Engine**: Converts spoken phrases into keyboard strokes using native Win32 `SendInput` APIs (`backend/voice/keyboard_injector.py`), allowing hands-free typing in any Windows application (Word, Notepad, browsers, chat apps).
* **System Navigator**: Direct vocal navigation commands including:
  * *"open chrome"*, *"open edge"*, *"open notepad"*
  * *"scroll down"*, *"scroll up"*, *"page down"*, *"page up"*
  * *"close window"*, *"maximize window"*, *"minimize window"*
  * *"switch window"*, *"press enter"*, *"delete word"*
* **Self-Hearing Audio Suppression**: Automatically mutes microphone interpretation while IRIS AI is vocalizing synthesized responses to prevent command feedback loops.

---

## 6. Desktop Accessibility and Automation

* **Win32 Native Pointer Injection**: High-precision mouse movement injected directly via Win32 user32 APIs (`SetCursorPos`), bypassing third-party interpreter delays.
* **Intentional Blink Detection**: Distinguishes natural physiological blinks (100–300 ms) from intentional command blinks (400–1200 ms) using high-frequency Eye Aspect Ratio (EAR) temporal tracking.
* **Blink Freeze Stabilization**: Temporarily freezes cursor movement during blink initiation, preventing the pointer from jumping downward as the eyelid closes over the pupil.
* **Kinematic Spring-Damper Physics Filter**: Dampens involuntary head tremors and micro-movements while preserving rapid target acquisition speed.

---

## 7. Backend Lifecycle and Graceful Shutdown

* **Clean Startup Protocol**:
  1. Electron displays an immediate lightweight HTML5 splash screen (`splash.html`).
  2. Launches compiled `backend.exe` hidden in the background.
  3. Polls `http://127.0.0.1:8000/health` with adaptive backoff up to 60 seconds (accommodating initial Windows Defender scans).
  4. Once `SERVER_READY` is confirmed, transitions smoothly to the primary application interface.
* **Orderly Shutdown Protocol**:
  1. Intercepts Electron exit events (`before-quit`, `window-all-closed`, `SIGINT`, `SIGTERM`).
  2. Halts renderer activity and issues an HTTP `POST /api/v1/shutdown` to the FastAPI backend.
  3. Releases OpenCV camera captures, audio input streams, and background executor threads.
  4. Waits up to 3000 ms for process exit.
  5. If the child process does not exit in time, executes a targeted fallback termination (`taskkill /pid ${pid} /T /F`) exclusively on the verified child PID, preventing port 8000 socket collisions on subsequent launches.

---

## 8. Stability Improvements

* **Frozen Binary Path Resolution**: Resolves model directories and bundled resources dynamically whether running from source or extracted from a PyInstaller frozen directory (`sys._MEIPASS`).
* **Namespace Isolation**: Refactored internal platform utilities to `backend.sys_platform` to prevent collision with Python's built-in standard library `platform` module.
* **Memory and Handle Leaks**: Proper context-manager lifespans for all FastAPI routes, webcam video capture instances, and background event listeners.

---

## 9. Testing and Verification

v2.5.0 was verified through comprehensive automated test suites:

* **16-Point Calibration & Math**: Verified in [`backend/tests/test_gaze_calibration_16point.py`](file:///C:/Users/Meet%20Raval/IRISAI/backend/tests/test_gaze_calibration_16point.py) covering 16-point grid layout, 4-point validation target isolation, polynomial fitting, and authorization gating.
* **Graceful Shutdown & Process Management**: Verified in [`backend/tests/test_graceful_shutdown.py`](file:///C:/Users/Meet%20Raval/IRISAI/backend/tests/test_graceful_shutdown.py) validating HTTP shutdown endpoints, resource cleanup, and timeout handling.
* **Cursor Safety & Eye API**: Verified in [`backend/tests/test_eye_cursor_api.py`](file:///C:/Users/Meet%20Raval/IRISAI/backend/tests/test_eye_cursor_api.py) and [`backend/tests/test_blink_freeze_buffer.py`](file:///C:/Users/Meet%20Raval/IRISAI/backend/tests/test_blink_freeze_buffer.py).
* **Frontend Coordinate Calculations**: Verified in [`frontend/tests/calibrationCoordinates.test.mjs`](file:///C:/Users/Meet%20Raval/IRISAI/frontend/tests/calibrationCoordinates.test.mjs) testing target positioning, panel docking, and boundary clamping.
* **Audio & Voice Pipeline**: Regression tested across [`backend/tests/test_voice.py`](file:///C:/Users/Meet%20Raval/IRISAI/backend/tests/test_voice.py) and preprocessor tests.

> [!NOTE]
> Automated tests confirm software state machines, mathematical models, and API endpoints. Physical eye-tracking accuracy in production remains subject to ambient room lighting, webcam resolution, and camera mounting geometry.

---

## 10. Known Limitations

* **Ambient Lighting**: Pupil contrast and MediaPipe face landmark detection require balanced frontal lighting; strong backlighting or direct sunlight may degrade tracking stability.
* **Webcam Placement**: Optimal results require the camera to be mounted centrally above or below the display, tilted directly toward the user's face.
* **Glasses and Reflections**: Heavy glare, bifocals, or thick-rimmed glasses may intermittently affect Eye Aspect Ratio (EAR) accuracy.
* **Code Signing**: Installers are currently unsigned (`NotSigned`); Windows SmartScreen will display an *"Unknown Publisher"* warning during manual installation. Click **More info -> Run anyway** to proceed.

---

## 11. Installation Instructions

1. Download [`IRIS-AI-v2.5.0-Setup.exe`](file:///C:/Users/Meet%20Raval/IRISAI/release/IRIS-AI-v2.5.0-Setup.exe) from the official GitHub Release assets.
2. Double-click the installer on Windows 10 or 11 (64-bit).
3. If prompted by Windows Defender SmartScreen (*"Windows protected your PC"*):
   * Click **More info**.
   * Click **Run anyway**.
4. Follow the setup wizard to select your installation directory and create desktop/start-menu shortcuts.
5. Launch **IRIS AI** from your desktop or start menu. The application will initialize the local backend and display the splash screen before loading the main dashboard.

---

## 12. Upgrade Instructions

* **Upgrading from v2.4.x**:
  * You can install v2.5.0 directly over your existing installation.
  * Your previous configuration will be preserved.
  * Because v2.5.0 upgrades the gaze mapping engine, we recommend navigating to the **Calibration** tab and completing a fresh 16-point calibration session for optimal pointer accuracy.

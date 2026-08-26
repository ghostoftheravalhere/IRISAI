# IRIS AI V2.4.2 — Current Features & Future Scope

**Intelligent Responsive Interface System**  
*IBM SkillsBuild Hackathon Submission*

---

## 1. Current Release Overview

**IRIS AI V2.4.2** is the official production and hackathon release of IRIS AI. 

To maintain total transparency for hackathon judges, mentors, and evaluators, this document clearly distinguishes between:

1. **Features Currently Implemented & Demonstrable in V2.4.2**: Tested capabilities that run inside the packaged Windows application.
2. **Future Scope & Planned Roadmap**: Technical extensions and capabilities planned for future iterations that are **NOT** part of the current V2.4.2 release.

---

## 2. Currently Working Features in V2.4.2

The following table summarizes the operational status of all core subsystems in IRIS AI V2.4.2:

| Feature | Current Status | Implementation & Description |
| :--- | :---: | :--- |
| **Microphone Device Detection** | **WORKING** | Automatic hardware enumeration, channel identification, and sample-rate detection (44.1/48 kHz auto-resampled to 16 kHz). |
| **Voice Listening Modes** | **WORKING** | Supports Continuous Listening and Push-to-Talk (PTT) audio capture modes. |
| **Faster-Whisper Offline ASR** | **WORKING** | Local CTranslate2-accelerated speech recognition running 100% offline without cloud API dependencies. |
| **Speech-to-Text Transcription**| **WORKING** | Real-time speech decoding into text tokens streamed directly to the frontend interface. |
| **Voice Intent Parsing** | **WORKING** | Structured intent and entity extraction engine mapping raw natural language to execution routes. |
| **Visual Response & Command Log**| **WORKING** | Real-time broadcast of `VOICE RAW`, `TRANSCRIPTION`, `INTENT`, `RESOLVER RESULT`, and `ACTION` into the UI Command Log. |
| **Camera & Face Mesh** | **WORKING** | MediaPipe-based face mesh processing for facial landmark and iris tracking via webcam. |
| **9-Point Gaze Calibration** | **WORKING** | Interactive 9-point grid sampling wizard for eye-gaze coordinate mapping. |
| **Gaze-Based Cursor Control** | **WORKING** | Smooth eye-gaze tracking to move the Windows system mouse cursor with start/stop control. |
| **Dynamic Application Resolver**| **WORKING** | Generalized `DesktopAppResolver` scanning Windows Registry, Start Menu, shortcuts, PATH, and system URIs. |
| **Desktop Action Automation** | **WORKING** | System automation engine executing keypresses, window management, scrolling, screenshots, and audio controls. |
| **Voice Output / Spoken TTS** | **DISABLED** | Intentionally disabled for hackathon submission stability (Visual Feedback Only). Voice INPUT is 100% active. |

---

### Subsystem Technical Breakdown

#### A. Voice & Speech Recognition
- **Voice Input Active**: Voice recognition, audio buffer processing, and Faster-Whisper ASR are fully functional.
- **Visual Feedback Only**: Spoken audio output (Text-to-Speech synthesis) is **intentionally disabled** in the V2.4.2 hackathon submission build to eliminate acoustic feedback and microphone self-hearing risks during live demonstration. Responses are rendered visually in the dashboard and Command Log.

#### B. Camera & Eye Tracking
- **Hardware Connection**: Auto-initializes integrated or USB webcams.
- **MediaPipe Landmark Tracking**: Extracts facial mesh and iris coordinates at real-time camera frame rates.

#### C. Gaze Calibration & Cursor Control
- **Interactive 9-Point Grid**: Guides users through 9 calibration target points:
  1. Top-Left
  2. Top-Center
  3. Top-Right
  4. Middle-Left
  5. Center
  6. Middle-Right
  7. Bottom-Left
  8. Bottom-Center
  9. Bottom-Right
- **Calibration Transition**: Automatically transitions from **Sampling** → **✓ Calibration Complete** → **Cursor Control: READY**.
- **Live Gaze Cursor**: Toggle **▶ Start Cursor Control** and **⏹ Stop Cursor Control** to move the system mouse pointer using eye gaze.

#### D. Dynamic Desktop Application Launching
IRIS AI V2.4.2 features a centralized `DesktopAppResolver` system. IRIS attempts to dynamically resolve and launch supported application targets using multiple Windows discovery mechanisms:

1. **Windows App Paths Registry**: `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths` & `HKCU`
2. **Windows Uninstall Registry**: Scans installed software entries across 32-bit and 64-bit registry paths.
3. **Start Menu Shortcuts**: Resolves `.lnk` shortcuts in System and User Start Menu folders.
4. **Desktop Shortcuts**: Scans User and Common Desktop directories.
5. **Known Program Directories**: Scans `C:\Program Files`, `C:\Program Files (x86)`, `C:\Windows\System32`, `LocalAppData`, and `AppData`.
6. **System PATH**: Resolves binaries in system environment PATH.
7. **Windows URI Protocols**: Resolves system protocols (e.g., `calculator:`, `ms-settings:`).

> [!IMPORTANT]
> **Host Software Requirement**: The requested application must actually be installed and discoverable on the user's Windows machine. If an application cannot be resolved, IRIS reports that it could not find the application (`status: failed`) in the Command Log rather than incorrectly opening a browser.

#### E. Registered Application Resolution Examples

| Example Spoken Command | Target Application | Discovery Method |
| :--- | :--- | :--- |
| `"Open Microsoft Word"` | Microsoft Word | Start Menu / App Paths (`winword.exe`) |
| `"Open Excel"` | Microsoft Excel | Start Menu / App Paths (`excel.exe`) |
| `"Open PowerPoint"` | Microsoft PowerPoint | Start Menu / App Paths (`powerpnt.exe`) |
| `"Open Microsoft Teams"` | Microsoft Teams | Uninstall Registry / AppData (`ms-teams.exe`) |
| `"Open Zoom"` | Zoom Workplace | Start Menu / AppData (`Zoom.exe`) |
| `"Open Zoom Workplace"` | Zoom Workplace | Start Menu / AppData (`Zoom.exe`) |
| `"Open Chrome"` | Google Chrome | App Paths / Program Files (`chrome.exe`) |
| `"Open Edge"` | Microsoft Edge | System App Paths (`msedge.exe`) |
| `"Open Firefox"` | Mozilla Firefox | App Paths / Program Files (`firefox.exe`) |
| `"Open Calculator"` | Windows Calculator | System URI / System32 (`calc.exe`) |
| `"Open Notepad"` | Windows Notepad | System32 (`notepad.exe`) |
| `"Open Camera"` | Windows Camera | Windows Package URI (`microsoft.windows.camera:`) |
| `"Open File Explorer"` | File Explorer | Windows Shell (`explorer.exe`) |
| `"Open Settings"` | Windows Settings | Windows URI (`ms-settings:`) |
| `"Open VS Code"` | Visual Studio Code | System PATH / Start Menu (`code.exe`) |
| `"Open WhatsApp"` | WhatsApp | Start Menu / LocalAppData (`WhatsApp.exe`) |
| `"Open Spotify"` | Spotify | AppData / Start Menu (`Spotify.exe`) |
| `"Open Task Manager"` | Windows Task Manager | System32 (`taskmgr.exe`) |
| `"Open Command Prompt"` | Command Prompt | System32 (`cmd.exe`) |

#### F. Desktop Automation Capabilities
The current action engine supports the following executable operations:

- **Open Application**: Dynamically launches resolved Windows executables.
- **Close Application / Close Window**: Gracefully terminates processes or active windows.
- **Activate Window**: Brings specified application window to the foreground.
- **Wait for Window & Verify Active Window**: Synchronizes action execution with window focus.
- **Browser Search**: Launches web queries in default browser when explicitly asked to search.
- **Type Text**: Simulates keyboard typing into active input fields.
- **Press Key & Hotkeys**: Executes keyboard shortcuts (e.g., `Enter`, `Tab`, `Ctrl+C`, `Ctrl+V`).
- **Scroll Up / Scroll Down**: Controls mouse wheel scrolling.
- **Volume Up / Volume Down / Mute**: Controls system master audio levels.
- **Clipboard Operations**: Copy, Paste, Select All.
- **Minimize Window**: Minimizes active windows.
- **Take Screenshot**: Captures screen images.

#### G. Safety & Control Mechanisms
- **Graceful Application Teardown**: Spoken commands `"Close IRIS"`, `"Exit IRIS"`, `"Quit IRIS"`, `"Close yourself"`, and `"Shutdown IRIS"` perform an immediate clean shutdown of Electron and backend server processes.
- **Audio Stream Safety**: Auto-handles device disconnects and fallback sample-rate conversion without crashing.

---

## 3. Recommended Demonstration Workflow

For hackathon evaluation, judges can follow this 5-minute demonstration script:

1. **Launch IRIS AI** from the Desktop shortcut.
2. Verify Dashboard Status:
   - **Camera**: Ready
   - **Microphone**: Ready
   - **Eye Tracking**: Active
   - **Action Engine**: Ready
3. Click **▶ Start Voice**.
4. Say **"Open Microsoft Word"** → Observe command in Command Log and Word opening (if installed).
5. Say **"Open PowerPoint"** → Verify PowerPoint launching.
6. Say **"Open Microsoft Teams"** → Verify Teams launching.
7. Say **"Open Zoom"** → Verify Zoom launching.
8. Say **"Open Calculator"** → Verify Calculator launching.
9. Say **"Take screenshot"** → Observe screenshot action execution in Command Log.
10. Say **"Copy"**, **"Paste"**, **"Select all"**, **"Scroll down"** → Observe action execution.
11. Click **🎯 Calibrate Gaze** → Complete all 9 target points.
12. Verify **✓ Calibration Complete** → **Cursor Control: READY**.
13. Click **▶ Start Cursor Control** → Move mouse cursor using eye gaze.
14. Say **"Close IRIS"** → Verify clean application shutdown.

---

## 4. Current Release Limitations (V2.4.2)

The following operational constraints are present in the V2.4.2 release:

1. **Voice Output (TTS) Disabled**: Spoken responses are disabled for hackathon submission stability; all output is displayed visually.
2. **Host Software Dependency**: Dynamic application resolution depends on the application being installed on the evaluator's machine.
3. **Windows Operating System**: V2.4.2 is built and optimized specifically for 64-bit Windows 10/11 environments.
4. **Hardware Permission Dependencies**: Webcam and microphone streams require standard Windows Privacy permissions.
5. **Non-Standard Installation Paths**: Software installed in custom directories outside Registry, Start Menu, or PATH may require explicit path mapping.

---

## 5. Future Scope (Planned Enhancements)

> [!NOTE]
> **The features listed below are FUTURE DIRECTIONS and are NOT part of the current V2.4.2 release.**

### 1. Universal Application Discovery Engine
Expand application discovery beyond registry and shortcut scanning to include dynamic binary fingerprinting, supporting any custom or portable Windows executable automatically.

### 2. Advanced Contextual Natural Language Understanding
Support complex conversational queries with rich intent and entity extraction:
- *"Can you open my presentation from yesterday?"*
- *"Bring up Teams and check if my meeting started."*
- *"Launch the application I was using earlier."*

### 3. Multi-Step Autonomous Workflows
Enable multi-action macro planning from single high-level user directives:
- *"Open PowerPoint, create a title slide for IBM Hackathon, and save it to Desktop."*

### 4. Context-Aware Desktop Assistance
Maintain deep session memory tracking active window states, recent user actions, and workflow context across long multi-turn interactions.

### 5. Advanced Computer Vision & Visual Grounding
Integrate multimodal screen understanding, UI element detection, OCR, and visual spatial grounding to interact with complex desktop GUIs without hardcoded coordinates.

### 6. Enhanced Eye-Gaze Controls
- Adaptive online gaze calibration correction.
- Dwell-time auto-clicking and gaze-gesture navigation.
- Hybrid Gaze + Voice multi-modal interaction modes.

### 7. Natural Voice Output (TTS)
Re-enable two-way spoken audio output using neural text-to-speech models with active acoustic echo cancellation.

### 8. Hybrid Local & Cloud AI Engines
Provide user configurable toggles between:
- 100% local offline execution (V2.4.2 baseline).
- Local LLM execution (via Ollama / GGML).
- High-reasoning Cloud AI services for complex autonomous tasks.

### 9. Personalization & Custom Automation Routines
Allow users to create custom voice aliases, macro routines, and personalized application shortcuts.

### 10. Cross-Platform Desktop Support
Extend the IRIS AI desktop client architecture to native Linux (Ubuntu/Debian) and macOS environments.

---

## 6. Current vs. Future Capability Matrix

| Capability | V2.4.2 Status | Future Scope Direction |
| :--- | :---: | :--- |
| **Offline Speech Recognition** | **WORKING** | Enhanced multi-lingual neural models |
| **Microphone Input & Resampling** | **WORKING** | Advanced AI noise suppression |
| **Camera & Face Mesh Tracking** | **WORKING** | Multi-camera support & depth sensing |
| **9-Point Gaze Calibration** | **WORKING** | Continuous adaptive auto-calibration |
| **Gaze Cursor Control** | **WORKING** | Dwell-click, gaze-gestures & hybrid input |
| **Desktop Application Resolution** | **WORKING** | Universal binary fingerprinting |
| **Desktop Action Execution** | **WORKING** | Multi-step autonomous macros |
| **Natural Language Intent Parsing**| **WORKING** | Multi-turn contextual reasoning |
| **Voice Output / Spoken TTS** | **DISABLED** | Neural TTS with echo cancellation |
| **Multi-Step Autonomous Workflows** | **FUTURE** | Full agentic workflow planner |
| **Advanced Screen OCR & Vision** | **FUTURE** | Real-time GUI visual grounding |
| **Cross-Platform OS Support** | **Windows-Focused** | Linux and macOS support |

---

## 7. Development Philosophy

IRIS AI is engineered as a **modular, decoupled desktop assistance architecture** rather than a set of hardcoded script shortcuts.

The system pipeline strictly decouples responsibilities:

$$\text{Voice/Gaze Intake} \longrightarrow \text{Intent Parsing} \longrightarrow \text{App Resolver} \longrightarrow \text{Action Planning} \longrightarrow \text{System Execution} \longrightarrow \text{Verification} \longrightarrow \text{Visual UI Stream}$$

This modular design ensures that new perception models, vision capabilities, or execution planners can be integrated into future versions without modifying the core desktop assistant infrastructure.

---

## 8. Final Status Statement

IRIS AI V2.4.2 represents the current demonstrable implementation. Features listed under Future Scope are planned directions and should not be interpreted as currently available functionality.

- **Current Release**: V2.4.2
- **Release Tag**: `v2.4.2`
- **Target Commit**: `3be6e3d098b04a444bc064ea6fd5a5a3aedb6ce4`
- **Official GitHub Release**: https://github.com/ghostoftheravalhere/IRISAI/releases/tag/v2.4.2

# IRIS AI V2.4.2 — Windows Installation & Demonstration Guide

**Intelligent Responsive Interface System**
*IBM SkillsBuild Hackathon Official Production Release*

---

## Executive Overview

This guide is written specifically for **IBM SkillsBuild Hackathon judges, mentors, evaluators, and end-users** who wish to install, evaluate, and demonstrate **IRIS AI V2.4.2** on Windows.

**No separate Python or Node.js installation is required.**
**No npm commands are required.**
**No terminal commands are required.**

IRIS AI V2.4.2 is distributed as a **standalone, self-contained Windows Setup Installer (`IRIS-AI-V2.4.2-Setup.exe`)** and a **Portable Executable (`IRIS-AI-V2.4.2-Portable.exe`)** hosted on the official **GitHub Release (`v2.4.2`)**.

```
Official GitHub Release (v2.4.2)
           │
           ├──────────────────────────────────────┐
           ▼                                      ▼
Download IRIS-AI-V2.4.2-Setup.exe   Download IRIS-AI-V2.4.2-Portable.exe
(116.56 MB Setup Installer)         (116.33 MB Standalone Executable)
           │                                      │
           ▼                                      ▼
Run Setup Wizard or Launch Directly ──────► IRIS AI Interface Ready
```

---

## 1. Quick Installation & Launch Steps

Follow these simple steps to install and run IRIS AI V2.4.2 on any Windows 10/11 PC:

1. **STEP 1**: Open the official GitHub Release page:
   👉 **[IRIS AI V2.4.2 GitHub Release](https://github.com/ghostoftheravalhere/IRISAI/releases/tag/v2.4.2)**

2. **STEP 2**: Locate **"IRIS AI V2.4.2 — Production Release"**.

3. **STEP 3**: Download your preferred asset from the **Assets** section:
   - **Installer Option (Recommended)**: Download **`IRIS-AI-V2.4.2-Setup.exe`** (`116,564,251 bytes`).
   - **Portable Option**: Download **`IRIS-AI-V2.4.2-Portable.exe`** (`116,334,405 bytes`).

4. **STEP 4**: Launch the application:
   - **For Setup Installer**: Double-click `IRIS-AI-V2.4.2-Setup.exe`. If Windows SmartScreen appears (*"Windows protected your PC"*), click **More info** → **Run anyway**. Follow the wizard steps to complete installation.
   - **For Portable**: Double-click `IRIS-AI-V2.4.2-Portable.exe` to run immediately without installation.

5. **STEP 5**: Launch IRIS AI from the Desktop shortcut or Start Menu.
   - Allow webcam and microphone permissions when prompted by Windows.
   - The application automatically launches the bundled backend (`iris_backend.exe`), initializes hardware streams, and displays the IRIS AI Dashboard in **READY** state.

---

## 2. System Requirements

The hardware and software specifications for IRIS AI V2.4.2:

| Component | Minimum Specification | Recommended Specification |
| :--- | :--- | :--- |
| **Operating System** | Windows 10 (64-bit) | Windows 11 (64-bit) |
| **Processor (CPU)** | Intel Core i3 / AMD Ryzen 3 (Dual-Core+) | Intel Core i5 / AMD Ryzen 5 (Quad-Core+) |
| **System Memory (RAM)**| 4 GB RAM | 8 GB RAM or higher |
| **Available Storage** | 500 MB free disk space | 1.0 GB free disk space |
| **Webcam** | Standard USB / Built-in 720p Webcam | 1080p HD Webcam (for eye tracking) |
| **Microphone** | Standard Built-in or USB Microphone | Noise-canceling USB Microphone |
| **Internet Connection**| **NONE (100% Offline Capability)** | None required |
| **Permissions** | Standard User Permissions (No Admin required) | Standard User Account |

---

## 3. What Works in V2.4.2 — Currently Working Features

IRIS AI V2.4.2 includes a fully integrated, production-grade multimodal assistant pipeline.

### Voice Recognition
- **Microphone Initialization**: Automatic device enumeration and sample rate detection (e.g., 44.1 kHz / 48 kHz auto-resampled to 16 kHz for model intake).
- **Listening Modes**: Supports both Continuous Listening and Push-to-Talk (PTT).
- **Faster-Whisper Offline ASR**: Local CTranslate2-accelerated speech recognition running entirely on-device without cloud API dependencies.
- **Voice Command Parsing & Intent Detection**: Extracts structured intents and target application names from raw spoken speech.
- **Desktop Action Execution**: Dispatches parsed intents directly to local system execution handlers.
- **Visual Feedback & Log Sync**: Real-time broadcast of `VOICE RAW`, `TRANSCRIPTION`, `INTENT`, `RESOLVER RESULT`, and `ACTION` straight into the Conversation & Command Log UI.

> [!NOTE]
> **Voice Output Notice**: Spoken audio output (text-to-speech synthesis) is intentionally disabled for hackathon submission stability to prevent microphone feedback loops. Voice **INPUT** is fully active, and all responses are rendered visually in the dashboard and Command Log.

### Camera & Eye Tracking
- **Camera Stream Initialization**: Auto-detects and connects to standard USB or integrated webcams.
- **Face & Eye Landmark Mesh**: Powered by MediaPipe face mesh processing for real-time gaze angle calculation.
- **Camera Ready Status**: Real-time status indicator on the main dashboard.

### 9-Point Gaze Calibration
- **Interactive Calibration Wizard**: Guides the user through a 9-point screen calibration grid:
  1. Top-Left
  2. Top-Center
  3. Top-Right
  4. Middle-Left
  5. Center
  6. Middle-Right
  7. Bottom-Left
  8. Bottom-Center
  9. Bottom-Right
- **Calibration States**: Smooth transition from **Sampling** → **✓ Calibration Complete** → **Cursor Control: READY**.
- **Interactive Control**: Toggle **▶ Start Cursor Control** and **⏹ Stop Cursor Control** to control the Windows mouse cursor with your eyes.

---

## 4. Voice Recognition Pipeline

The V2.4.2 voice pipeline processes speech end-to-end:

```
[Spoken Speech] ──► [Microphone Input Stream] ──► [Faster-Whisper ASR]
                                                         │
                                                         ▼
[Conversation UI Log] ◄── [Action Execution] ◄── [Intent Engine & Resolver]
```

Spoken commands are transcribed locally, parsed into structured intent objects, resolved against the Windows system, executed via PyAutoGUI / UIA engines, and appended instantly to the Conversation & Command Log UI.

---

## 5. Camera & Eye Tracking System

The eye tracking subsystem runs parallel to voice recognition:
- Captures video frames at standard webcam frame rates.
- Extracts iris coordinates relative to screen boundaries.
- Applies polynomial calibration matrix mapping after completing the 9-point wizard.
- Moves the system cursor smoothly with built-in jitter reduction.

---

## 6. 9-Point Gaze Calibration Protocol

To achieve optimal cursor precision:

1. Click **🎯 Calibrate Gaze** on the IRIS AI dashboard.
2. Align your head comfortably in front of the camera until face tracking shows **Detected**.
3. Fixate your eyes on the pulsating target dot at **Point 1 (Top-Left)** and click **Sample Point**.
4. Repeat for all 9 points across the grid boundaries.
5. Upon completion, the UI updates to **✓ Calibration Complete** and unlocks **Cursor Control: READY**.
6. Click **▶ Start Cursor Control** to enable live gaze cursor tracking.

---

## 7. Desktop Application Launching Architecture

IRIS AI V2.4.2 features a dynamic, multi-strategy `DesktopAppResolver` system. It does **NOT** hardcode applications or fallback to web browsers for unknown desktop apps.

### Windows Discovery Strategies
When you say `"Open <Application Name>"`, IRIS resolves the target executable using:

1. **Windows App Paths Registry**: `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\App Paths` & `HKCU`
2. **Windows Uninstall Registry**: Discovers installed software paths across standard 32-bit and 64-bit registry keys.
3. **Start Menu Shortcuts**: Scans User and System Start Menu directories (`.lnk` file resolution).
4. **Desktop Shortcuts**: Scans User and Common Desktop directories.
5. **Standard System Directories**: Scans `C:\Program Files`, `C:\Program Files (x86)`, `C:\Windows\System32`, `LocalAppData`, and `AppData`.
6. **System PATH**: Resolves binaries in system environment PATH.
7. **Windows URI Protocols**: Resolves system URI schemes (e.g., `calculator:`, `ms-settings:`).

### Strict Failure Handling
If an application is not installed on the system, IRIS **does NOT open Edge, Chrome, or a search engine**. Instead, it returns a structured failure response (`status: failed`) and logs *"Application '<Name>' not found on system"* in the Command Log.

### Standard Supported Applications Table

| Example Spoken Command | Target Application | Discovery Strategy |
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
| `"Open VS Code"` | Visual Studio Code | Path / Start Menu (`code.exe`) |
| `"Open WhatsApp"` | WhatsApp | Start Menu / LocalAppData (`WhatsApp.exe`) |
| `"Open Spotify"` | Spotify | AppData / Start Menu (`Spotify.exe`) |
| `"Open Task Manager"` | Windows Task Manager | System32 (`taskmgr.exe`) |
| `"Open Command Prompt"` | Command Prompt | System32 (`cmd.exe`) |

> [!IMPORTANT]
> **Host Dependency Note**: Actual application launching depends on the application being installed and available on the evaluator's Windows machine.

---

## 8. Desktop Automation Capabilities

IRIS AI V2.4.2 supports an extensive desktop action execution pipeline:

- **Open Application**: Launches resolved Windows applications dynamically.
- **Close Application / Close Window**: Terminates target application processes or closes active windows.
- **Activate Window**: Brings specified application window to the foreground.
- **Wait for Window & Verify Active Window**: Synchronizes action execution with window focus.
- **Browser Search**: Launches web queries in default browser when explicitly asked to search.
- **Type Text**: Simulates keyboard text typing into active input fields.
- **Press Key & Hotkeys**: Executes keyboard keypresses (e.g., `Enter`, `Tab`, `Ctrl+C`, `Ctrl+V`).
- **Scroll Up / Scroll Down**: Controls mouse wheel scrolling.
- **Volume Up / Volume Down / Mute**: Controls system master audio levels.
- **Clipboard Operations**: Copy, Paste, Select All.
- **Minimize Window**: Minimizes active windows.
- **Take Screenshot**: Captures screen images.
- **Safe Application Shutdown**: Responds to `"Close IRIS"`, `"Exit IRIS"`, `"Quit IRIS"`, `"Close yourself"`, and `"Shutdown IRIS"` by performing a clean teardown of Electron and backend server processes.

---

## 9. Recommended 5-Minute Judge Demonstration

Follow this streamlined demonstration flow during evaluation:

### Step 1: Launch IRIS AI
Double-click **IRIS AI** shortcut. Verify the interface opens with the main status bar showing:
- **Camera**: Ready
- **Microphone**: Ready
- **Eye Tracking**: Active
- **Action Engine**: Ready

### Step 2: Start Voice Recognition
Click **▶ Start Voice** on the dashboard.

### Step 3: Test Dynamic Application Launching
Speak clearly into your microphone:
- `"Open Microsoft Word"`
- Observe command propagation in the **Conversation & Command Log**.
- Verify Microsoft Word launches (if installed on your PC).

Test additional applications:
- `"Open PowerPoint"`
- `"Open Microsoft Teams"`
- `"Open Zoom"`
- `"Open Calculator"`

### Step 4: Test Desktop Actions
Speak the following commands and watch the Command Log & desktop react:
- `"Take screenshot"`
- `"Copy"`
- `"Paste"`
- `"Select all"`
- `"Scroll down"`

### Step 5: Test 9-Point Eye Gaze Calibration
1. Click **🎯 Calibrate Gaze**.
2. Complete all 9 target sampling points.
3. Observe **✓ Calibration Complete** → status updates to **Cursor Control: READY**.
4. Click **▶ Start Cursor Control** and move your cursor across the screen using your eyes.
5. Click **⏹ Stop Cursor Control**.

### Step 6: Safe Shutdown
Say `"Close IRIS"`. Observe clean termination of application processes.

---

## 10. Troubleshooting

### Microphone Not Ready
- Verify microphone permissions: **Windows Settings** → **Privacy & Security** → **Microphone** = **ON**.
- Ensure your microphone is connected and set as the Default Input Device in Windows Sound settings.
- Click **🔄 Retry Microphone** on the IRIS dashboard.

### Camera Not Ready
- Ensure no other app (e.g., Zoom, Teams) is holding exclusive access to the webcam.
- Check Windows Privacy settings: **Windows Settings** → **Privacy & Security** → **Camera** = **ON**.
- Restart IRIS AI.

### Application Not Opening
- Confirm the application is installed on your Windows machine.
- Inspect the **Conversation & Command Log** for resolver status.
- If an app is not installed, IRIS correctly logs *"Application not found"* instead of incorrectly launching a browser.

### Command Log Not Updating
- Verify the backend server status badge on the top bar displays **Online (v2.4.2)**.
- If status shows Offline, click **Restart Backend** or re-launch IRIS AI.

### Gaze Cursor Not Moving
- Ensure you complete all 9 calibration points until **✓ Calibration Complete** is displayed.
- Check that status shows **Cursor Control: READY**.
- Ensure **▶ Start Cursor Control** has been clicked.

### Diagnostic Logs Location
IRIS AI V2.4.2 maintains 5 dedicated diagnostic log files in `%LOCALAPPDATA%\IRIS AI\logs\`:
- `electron.log`
- `backend.log`
- `voice.log`
- `events.log`
- `resolver.log`

---

## 11. Release Verification & Hashes

Official release metadata for **IRIS AI V2.4.2**:

- **GitHub Release Tag**: `v2.4.2`
- **Release Page URL**: https://github.com/ghostoftheravalhere/IRISAI/releases/tag/v2.4.2
- **Target Git Commit**: `3be6e3d098b04a444bc064ea6fd5a5a3aedb6ce4`

### Artifact Hashes & Sizes

| Artifact | Filename | Size (Bytes) | SHA256 Checksum |
| :--- | :--- | :--- | :--- |
| **Setup Installer** | `IRIS-AI-V2.4.2-Setup.exe` | `116,564,251` bytes | `FDBECBA6AECC1DC4C5D9FCECC4EBCFDFCECC5995F7BD6A5BBF5ED88DE45CD484` |
| **Portable Executable** | `IRIS-AI-V2.4.2-Portable.exe` | `116,334,405` bytes | `40DAFA25ED3A556BFA95DBC4FDBAF0DC5FFBFBE84F59EC425A8BBDFE0CEACAC8` |

---

## 12. Final Feature Summary

- **100% Offline Capability**: Speech recognition, gaze tracking, intent parsing, and execution run locally on Windows without cloud dependencies.
- **Zero Configuration**: Single-file setup installer bundles Electron, React, PyInstaller backend, Whisper model, MediaPipe, and PyAutoGUI.
- **Dynamic Desktop Resolution**: Multi-strategy Windows registry, shortcut, and binary path resolver for desktop applications.
- **Comprehensive Multimodal UI**: Real-time visual feedback across voice transcription, intent parsing, resolver status, action execution, and gaze cursor control.

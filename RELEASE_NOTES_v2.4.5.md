# IRIS AI v2.4.5 — IBM HACKATHON LATEST

### Key Improvements Over v2.4.4

* **Cold-Start & Defender Resilience (Zero Startup Hangs)**:
  - Extended backend health-check polling from an aggressive 15s abort to a resilient 60s window, preventing premature failures during first-launch Windows Defender scans.
  - Added live startup status messaging on the splash screen and an auto-recovery respawn fallback at attempt 6.
  - Implemented guaranteed port cleanup on exit using recursive `taskkill /pid ${pid} /T /F` to prevent orphaned background processes locking port 8000.

* **Standard Library Namespace Conflict Fix**:
  - Permanently resolved the frozen binary startup crash (`ModuleNotFoundError: No module named 'backend.platform.config_validator'`) by refactoring `backend/platform` to `backend/sys_platform`, eliminating name shadowing with Python's built-in `platform` module.

* **Zero-Latency Responsive 2D Gaze Control**:
  - Reverted unstable 3D solvePnP matrix estimation and cascading multi-filter stacking in favor of a lean, high-fidelity 2D tracking engine.
  - Eliminated cursor "rubber-banding" and freezing during rapid head movements.
  - Integrated direct Win32 zero-overhead cursor injection (`SetCursorPos`), bypassing PyAutoGUI default 100ms blocking pauses.

* **Click & Drift Discipline**:
  - Disabled rogue dwell auto-clicking by default to eliminate unintentional button clicks when the cursor rests.
  - Calibrated resting vertical perspective bias (`neutral_y = 0.56`) to counteract top-mounted webcam angle tilt and stop downward screen drift.
  - Tightened Eye Aspect Ratio (EAR) blink detection thresholds to prevent false-positive clicks during normal saccades and downward glances.

* **Production Packaging**:
  - Switched Electron Builder NSIS compression to `store` for near-instant executable extraction and reduced initial CPU load on target machines.

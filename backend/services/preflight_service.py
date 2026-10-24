"""Startup Pre-Flight Health Check Service.

Probes file system permissions, microphone stream warm-up, and camera access
before backend services start, displaying native Windows alert dialogs on access denial.
"""

from __future__ import annotations

import ctypes
import os
from pathlib import Path
import queue
import sys
import threading
import time
from typing import Any

from backend.core.config.settings import APP_DATA_DIR, get_app_data_dir
from backend.utils.logger import get_logger

logger = get_logger(__name__)


def show_permission_error(title: str, message: str) -> None:
    """Display a native Windows alert dialog before crashing or failing."""
    logger.error("PERMISSION ERROR [%s]: %s", title, message)
    try:
        # Avoid blocking automated test execution when running inside pytest or headless
        if "pytest" in sys.modules or os.getenv("IRIS_HEADLESS") == "1":
            print(f"\n[TEST MODE ALERT] [{title}] {message}\n", file=sys.stderr, flush=True)
            return

        if sys.platform.startswith("win") and hasattr(ctypes, "windll"):
            # MB_ICONERROR (0x10) | MB_OK (0x0) | MB_TOPMOST (0x40000)
            ctypes.windll.user32.MessageBoxW(0, message, title, 0x10 | 0x0 | 0x40000)
        else:
            print(f"\n=======================================================\n>>> [{title}] <<<\n{message}\n=======================================================\n", file=sys.stderr, flush=True)
    except Exception as exc:
        logger.exception("Failed to render native alert dialog: %s", exc)
        print(f"[{title}] {message}", file=sys.stderr, flush=True)


def probe_file_permissions(target_dir: Path | None = None) -> bool:
    """Test write and delete access in application data directory."""
    data_dir = target_dir or get_app_data_dir()
    print(f"[PRE-FLIGHT] Verifying write permissions to: {data_dir}", flush=True)
    probe_file = data_dir / f".iris_preflight_probe_{os.getpid()}.tmp"
    try:
        data_dir.mkdir(parents=True, exist_ok=True)
        probe_file.write_text("iris_ok", encoding="utf-8")
        content = probe_file.read_text(encoding="utf-8")
        if content != "iris_ok":
            raise OSError("Probe file readback verification failed.")
        try:
            probe_file.unlink()
        except Exception:
            pass
        print("[PRE-FLIGHT] File permissions verified successfully.", flush=True)
        return True
    except Exception as exc:
        err_msg = (
            f"Unable to write to the application data directory:\n{data_dir}\n\n"
            f"Error details: {exc}\n\n"
            "Please check your folder permissions or run the application with administrative privileges."
        )
        show_permission_error("IRIS AI - File Permissions Error", err_msg)
        return False


def probe_microphone_access(warmup_duration_sec: float = 0.1, timeout_sec: float = 2.0) -> bool:
    """Query default audio input device and open a dummy stream to wake up the driver."""
    print("[PRE-FLIGHT] Probing microphone device and warming up audio driver...", flush=True)
    result_queue: queue.Queue[tuple[bool, str | None]] = queue.Queue()

    def _worker():
        try:
            import sounddevice as sd
            devices = sd.query_devices()
            if not devices:
                result_queue.put((False, "No audio devices detected."))
                return

            input_dev = sd.query_devices(kind="input")
            if not input_dev:
                result_queue.put((False, "No default audio input device found."))
                return

            sample_rate = 16000
            stream = sd.InputStream(samplerate=sample_rate, channels=1, dtype="float32")
            stream.start()
            sd.sleep(int(warmup_duration_sec * 1000))
            stream.stop()
            stream.close()
            result_queue.put((True, None))
        except Exception as exc:
            result_queue.put((False, str(exc)))

    thread = threading.Thread(target=_worker, name="iris-preflight-mic", daemon=True)
    thread.start()
    thread.join(timeout=timeout_sec)

    if thread.is_alive():
        logger.warning("Microphone warm-up probe timed out after %.1fs; continuing with stream fallback.", timeout_sec)
        print("[PRE-FLIGHT] Microphone warm-up probe timed out; fallback active.", flush=True)
        return False

    try:
        success, error = result_queue.get_nowait()
    except queue.Empty:
        success, error = False, "Unknown probe termination."

    if success:
        print("[PRE-FLIGHT] Microphone driver initialized and ready.", flush=True)
        return True
    else:
        err_str = str(error or "")
        logger.warning("Microphone probe returned failure: %s", err_str)
        is_privacy_denied = any(k in err_str.lower() for k in ("denied", "privacy", "permission", "host error", "unanticipated"))
        if is_privacy_denied:
            show_permission_error(
                "IRIS AI - Microphone Access Blocked",
                "Microphone access is blocked by Windows.\n\n"
                "Please go to Windows Settings > Privacy & Security > Microphone and turn on "
                "'Allow desktop apps to access your microphone'."
            )
        else:
            print(f"[PRE-FLIGHT] Microphone probe non-critical notice: {err_str}", flush=True)
        return False


def probe_camera_access(index: int = 0, timeout_sec: float = 2.5) -> bool:
    """Verify OpenCV can open index 0 and read a frame without blocking."""
    print(f"[PRE-FLIGHT] Probing camera access on index {index}...", flush=True)
    result_queue: queue.Queue[tuple[bool, str | None]] = queue.Queue()

    def _worker():
        cap = None
        try:
            import cv2
            if sys.platform.startswith("win"):
                cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
            else:
                cap = cv2.VideoCapture(index)

            if not cap.isOpened():
                if cap is not None:
                    cap.release()
                cap = cv2.VideoCapture(index)

            if not cap.isOpened():
                result_queue.put((False, f"Cannot open camera index {index}"))
                return

            ret, frame = cap.read()
            if ret and frame is not None:
                result_queue.put((True, None))
            else:
                result_queue.put((False, "Failed to read frame from camera index 0"))
        except Exception as exc:
            result_queue.put((False, str(exc)))
        finally:
            if cap is not None:
                try:
                    cap.release()
                except Exception:
                    pass

    thread = threading.Thread(target=_worker, name="iris-preflight-cam", daemon=True)
    thread.start()
    thread.join(timeout=timeout_sec)

    if thread.is_alive():
        logger.warning("Camera pre-flight probe timed out after %.1fs.", timeout_sec)
        print("[PRE-FLIGHT] Camera pre-flight probe timed out.", flush=True)
        return False

    try:
        success, error = result_queue.get_nowait()
    except queue.Empty:
        success, error = False, "Unknown probe termination."

    if success:
        print("[PRE-FLIGHT] Camera access verified successfully.", flush=True)
        return True
    else:
        err_str = str(error or "")
        logger.warning("Camera probe returned failure: %s", err_str)
        is_privacy_denied = any(k in err_str.lower() for k in ("denied", "privacy", "permission", "blocked"))
        if is_privacy_denied:
            show_permission_error(
                "IRIS AI - Camera Access Blocked",
                "Camera access is blocked by Windows.\n\n"
                "Please go to Windows Settings > Privacy & Security > Camera and turn on "
                "'Allow desktop apps to access your camera'."
            )
        else:
            print(f"[PRE-FLIGHT] Camera probe non-critical notice: {err_str}", flush=True)
        return False


def run_preflight_checks(
    probe_fs: bool = True,
    probe_mic: bool = True,
    probe_cam: bool = True,
) -> dict[str, bool]:
    """Execute startup pre-flight health checks for permissions and hardware."""
    if os.getenv("IRIS_SKIP_PREFLIGHT") == "1":
        logger.info("[PRE-FLIGHT] Skipped via IRIS_SKIP_PREFLIGHT=1")
        return {"filesystem": True, "microphone": True, "camera": True}

    print(">>> [IRIS AI PRE-FLIGHT CHECKS INITIATING] <<<", flush=True)
    results = {
        "filesystem": True,
        "microphone": True,
        "camera": True,
    }

    if probe_fs:
        fs_ok = probe_file_permissions()
        results["filesystem"] = fs_ok
        if not fs_ok:
            raise RuntimeError(f"Startup aborted: write access denied to {APP_DATA_DIR}")

    if probe_mic:
        results["microphone"] = probe_microphone_access()

    if probe_cam:
        results["camera"] = probe_camera_access()

    print(
        f">>> [PRE-FLIGHT COMPLETE] FS={results['filesystem']} | MIC={results['microphone']} | CAM={results['camera']} <<<",
        flush=True,
    )
    return results


def warmup_microphone_background() -> threading.Thread:
    """Trigger a non-blocking background thread that probes the default input device and primes the stream."""
    def _warmup():
        try:
            import sounddevice as sd
            dev = sd.query_devices(kind="input")
            if dev:
                stream = sd.InputStream(samplerate=16000, channels=1, dtype="float32")
                stream.start()
                time.sleep(0.1)
                stream.stop()
                stream.close()
                logger.info("[AUDIO] Non-blocking background microphone warm-up completed successfully.")
                print("[AUDIO] Background microphone stream primed and ready.", flush=True)
        except Exception as exc:
            logger.warning("[AUDIO] Non-blocking background microphone warm-up notice: %s", exc)

    thread = threading.Thread(target=_warmup, name="iris-mic-warmup-bg", daemon=True)
    thread.start()
    return thread


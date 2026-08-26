"""Non-blocking, transparent, borderless UI pop-up for blink-click feedback."""

from __future__ import annotations

import ctypes
import sys
import threading
from typing import Any

from backend.utils.logger import get_logger

logger = get_logger(__name__)


def show_click_feedback_popup(
    text: str = "Click!",
    duration_ms: int = 900,
    x: int | None = None,
    y: int | None = None,
) -> None:
    """Display a non-blocking, borderless, topmost pop-up on a background thread without stealing focus."""
    def _run():
        try:
            import tkinter as tk

            root = tk.Tk()
            root.overrideredirect(True)
            root.attributes("-topmost", True)
            root.attributes("-alpha", 0.92)
            root.configure(bg="#0f172a")

            # Border frame for a sleek pill appearance
            border = tk.Frame(root, bg="#10b981", padx=1, pady=1)
            border.pack(fill="both", expand=True)

            inner = tk.Frame(border, bg="#0f172a", padx=14, pady=6)
            inner.pack(fill="both", expand=True)

            lbl = tk.Label(
                inner,
                text=f"⚡ {text}",
                font=("Segoe UI", 11, "bold"),
                fg="#34d399",
                bg="#0f172a",
            )
            lbl.pack()

            root.update_idletasks()
            sw = root.winfo_screenwidth()
            sh = root.winfo_screenheight()
            w = root.winfo_width()
            h = root.winfo_height()

            if x is not None and y is not None:
                pos_x = min(max(x - w // 2, 10), sw - w - 10)
                pos_y = max(y - h - 15, 10)
            else:
                pos_x = (sw - w) // 2
                pos_y = 60

            root.geometry(f"{w}x{h}+{pos_x}+{pos_y}")

            # Apply Windows extended window styles (WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_TRANSPARENT)
            if sys.platform.startswith("win"):
                try:
                    hwnd = ctypes.windll.user32.GetParent(root.winfo_id())
                    if hwnd == 0:
                        hwnd = root.winfo_id()
                    GWL_EXSTYLE = -20
                    WS_EX_NOACTIVATE = 0x08000000
                    WS_EX_TOOLWINDOW = 0x00000080
                    WS_EX_TOPMOST = 0x00000008
                    WS_EX_TRANSPARENT = 0x00000020
                    current_style = ctypes.windll.user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
                    ctypes.windll.user32.SetWindowLongW(
                        hwnd,
                        GWL_EXSTYLE,
                        current_style | WS_EX_NOACTIVATE | WS_EX_TOOLWINDOW | WS_EX_TOPMOST | WS_EX_TRANSPARENT,
                    )
                except Exception:
                    pass

            root.after(duration_ms, root.destroy)
            root.mainloop()
        except Exception:
            logger.exception("Failed to render click feedback overlay popup.")

    thread = threading.Thread(target=_run, name="click-feedback-popup", daemon=True)
    thread.start()

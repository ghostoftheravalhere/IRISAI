"""Native Win32 Unicode Keyboard Injector using SendInput."""

from __future__ import annotations

import array
import sys
import time
from typing import Sequence

from backend.utils.logger import get_logger

logger = get_logger(__name__)

# Win32 Virtual Key Constants
VK_LWIN = 0x5B
VK_CONTROL = 0x11
VK_MENU = 0x12  # Alt key
VK_SHIFT = 0x10
VK_TAB = 0x09
VK_ESCAPE = 0x1B
VK_RETURN = 0x0D
VK_BACK = 0x08

HAS_WIN32_INPUT = False

if sys.platform == "win32":
    try:
        import ctypes
        import ctypes.wintypes as w

        INPUT_KEYBOARD = 1
        KEYEVENTF_UNICODE = 0x0004
        KEYEVENTF_KEYUP = 0x0002

        class KEYBDINPUT(ctypes.Structure):
            _fields_ = [
                ('wVk', w.WORD),
                ('wScan', w.WORD),
                ('dwFlags', w.DWORD),
                ('time', w.DWORD),
                ('dwExtraInfo', ctypes.c_size_t)
            ]

        class DUMMYUNIONNAME(ctypes.Union):
            _fields_ = [('ki', KEYBDINPUT)]

        class INPUT(ctypes.Structure):
            _anonymous_ = ['u']
            _fields_ = [('type', w.DWORD), ('u', DUMMYUNIONNAME)]

        HAS_WIN32_INPUT = True
    except Exception as err:
        logger.warning("[KEYBOARD INJECTOR] Win32 ctypes setup failed: %s", err)


def type_unicode_text(text: str) -> bool:
    """
    Inject any Unicode text string directly into the focused window using Win32 SendInput.
    Bypasses system clipboard and supports all characters, casing, and punctuation.
    """
    if not text:
        return False

    if not HAS_WIN32_INPUT:
        logger.info("[MOCK KEYBOARD TYPE]: %s", text)
        return True

    try:
        user32 = ctypes.windll.user32
        for char in array.array('H', text.encode('utf-16le')):
            inp_down = INPUT(type=INPUT_KEYBOARD, u=DUMMYUNIONNAME(ki=KEYBDINPUT(0, char, KEYEVENTF_UNICODE, 0, 0)))
            inp_up = INPUT(type=INPUT_KEYBOARD, u=DUMMYUNIONNAME(ki=KEYBDINPUT(0, char, KEYEVENTF_UNICODE | KEYEVENTF_KEYUP, 0, 0)))
            user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
            user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
            time.sleep(0.002)
        return True
    except Exception as err:
        logger.exception("[KEYBOARD INJECTOR] Failed to type unicode text: %s", err)
        return False


def send_hotkey(*vkeys: int) -> bool:
    """
    Dispatch virtual key combination (e.g. send_hotkey(VK_MENU, VK_TAB) for Alt+Tab).
    """
    if not vkeys:
        return False

    if not HAS_WIN32_INPUT:
        logger.info("[MOCK HOTKEY]: %s", vkeys)
        return True

    try:
        user32 = ctypes.windll.user32
        # Press all keys in sequence
        for vk in vkeys:
            inp_down = INPUT(type=INPUT_KEYBOARD, u=DUMMYUNIONNAME(ki=KEYBDINPUT(vk, 0, 0, 0, 0)))
            user32.SendInput(1, ctypes.byref(inp_down), ctypes.sizeof(INPUT))
            time.sleep(0.010)

        # Release all keys in reverse sequence
        for vk in reversed(vkeys):
            inp_up = INPUT(type=INPUT_KEYBOARD, u=DUMMYUNIONNAME(ki=KEYBDINPUT(vk, 0, KEYEVENTF_KEYUP, 0, 0)))
            user32.SendInput(1, ctypes.byref(inp_up), ctypes.sizeof(INPUT))
            time.sleep(0.010)

        return True
    except Exception as err:
        logger.exception("[KEYBOARD INJECTOR] Failed to dispatch hotkey: %s", err)
        return False

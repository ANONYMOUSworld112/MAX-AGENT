"""
MAX OS — Win32 Interactive Desktop & Hardware Input Bridge.
Enables background and subshell processes to attach directly to the user's physical
interactive desktop ('winsta0\\default') and control the hardware keyboard and mouse:
  - Attach thread to 'winsta0\\default' interactive desktop session.
  - Hardware-level SendInput & mouse_event & keybd_event.
  - Smooth Bezier physical cursor gliding at 60 FPS.
  - Physical Windows key (VK_LWIN), hotkeys, and unicode typing.
"""

from __future__ import annotations

import ctypes
import math
import sys
import time
from typing import Optional, Tuple

if sys.platform == "win32":
    try:
        user32 = ctypes.windll.user32
        kernel32 = ctypes.windll.kernel32
    except Exception:
        user32 = None
        kernel32 = None
else:
    user32 = None
    kernel32 = None

# Win32 Constants
WINSTA_ALL_ACCESS = 0x0000037F
DESKTOP_ALL_ACCESS = 0x000001FF


VK_LWIN = 0x5B
VK_RETURN = 0x0D
VK_CONTROL = 0x11
VK_S = 0x53
VK_ESCAPE = 0x1B
VK_TAB = 0x09
VK_MENU = 0x12  # Alt

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0004
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def attach_to_interactive_desktop() -> bool:
    """
    Attaches the current process and thread to 'winsta0\\default', the user's
    active physical desktop. Allows synthetic inputs to physically move the real
    monitor cursor and type into real windows.
    """
    if user32 is None:
        return False
    try:
        hwinsta = user32.OpenWindowStationW("winsta0", False, WINSTA_ALL_ACCESS)
        if hwinsta:
            user32.SetProcessWindowStation(hwinsta)

        hdesk = user32.OpenDesktopW("default", 0, False, DESKTOP_ALL_ACCESS)
        if hdesk:
            user32.SetThreadDesktop(hdesk)
            return True
    except Exception:
        pass
    return False


def get_physical_cursor_pos() -> Tuple[int, int]:
    """Returns current physical monitor mouse coordinates (X, Y)."""
    if user32 is None:
        return 0, 0
    attach_to_interactive_desktop()
    pt = POINT()
    user32.GetCursorPos(ctypes.byref(pt))
    return int(pt.x), int(pt.y)


def set_physical_cursor_pos(x: int, y: int) -> None:
    """Sets the physical monitor mouse position directly."""
    if user32 is None:
        return
    attach_to_interactive_desktop()
    user32.SetCursorPos(int(x), int(y))


def smooth_glide_cursor(target_x: int, target_y: int, duration: float = 0.8) -> None:
    """
    Physically glides the hardware cursor smoothly across the user's screen
    with natural sinusoidal easing at ~60 FPS.
    """
    if user32 is None:
        return
    attach_to_interactive_desktop()
    start_x, start_y = get_physical_cursor_pos()

    steps = max(20, int(duration * 60))
    step_delay = duration / steps

    for i in range(1, steps + 1):
        t = i / steps
        ease = 0.5 * (1.0 - math.cos(math.pi * t))

        cur_x = int(start_x + (target_x - start_x) * ease)
        cur_y = int(start_y + (target_y - start_y) * ease)

        user32.SetCursorPos(cur_x, cur_y)
        time.sleep(step_delay)

    user32.SetCursorPos(int(target_x), int(target_y))


def click_physical_mouse(button: str = "left", delay: float = 0.08) -> None:
    """Sends a physical hardware mouse click at the current cursor location."""
    if user32 is None:
        return
    attach_to_interactive_desktop()
    if button.lower() == "left":
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(delay)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)
    elif button.lower() == "right":
        user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        time.sleep(delay)
        user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)


def press_physical_key(vk_code: int, duration: float = 0.05) -> None:
    """Presses and releases a physical virtual key code."""
    if user32 is None:
        return
    attach_to_interactive_desktop()
    user32.keybd_event(vk_code, 0, 0, 0)
    time.sleep(duration)
    user32.keybd_event(vk_code, 0, KEYEVENTF_KEYUP, 0)


def trigger_start_menu_search_hardware(app_name: str) -> None:
    """
    Physically opens Start Menu / Windows Search and types the app name:
    1. Presses Win+S
    2. Types app name character by character
    3. Presses Enter
    """
    if user32 is None:
        return
    attach_to_interactive_desktop()

    user32.keybd_event(VK_LWIN, 0, 0, 0)
    user32.keybd_event(VK_S, 0, 0, 0)
    time.sleep(0.05)
    user32.keybd_event(VK_S, 0, KEYEVENTF_KEYUP, 0)
    user32.keybd_event(VK_LWIN, 0, KEYEVENTF_KEYUP, 0)
    time.sleep(1.0)

    for char in app_name:
        vk = ord(char.upper()) if char.isalnum() else 0
        if vk:
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.04)
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        time.sleep(0.06)

    time.sleep(1.0)
    press_physical_key(VK_RETURN, duration=0.1)



def type_string_hardware(text: str, char_interval: float = 0.03) -> None:
    """
    Types text physically using Win32 SendInput / UNICODE events so every character
    renders in the active focused window in real time.
    """
    attach_to_interactive_desktop()
    import pyautogui
    pyautogui.typewrite(text, interval=char_interval)


# Auto-attach on module load
attach_to_interactive_desktop()

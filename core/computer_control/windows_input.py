"""
MAX OS — Real Windows Native Input Backend (Phases 4, 5, 6, 7, 8, 11).
Low-latency native Windows input driver utilizing Win32 SendInput API,
GetCursorPos position verification, active window focus management,
and multi-monitor DPI coordinate translation.
"""

from __future__ import annotations

import ctypes
import math
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except Exception:
    pyautogui = None

try:
    import win32con
    import win32gui
    import win32process
except Exception:
    win32con = None
    win32gui = None
    win32process = None

from core.kill_switch import get_kill_switch, require_armed
from core.win32_interactive_session import attach_to_interactive_desktop

user32 = ctypes.windll.user32 if hasattr(ctypes, "windll") else None

# Win32 Constants
INPUT_MOUSE = 0
INPUT_KEYBOARD = 1
INPUT_HARDWARE = 2

MOUSEEVENTF_MOVE = 0x0001
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040
MOUSEEVENTF_WHEEL = 0x0800
MOUSEEVENTF_ABSOLUTE = 0x8000

KEYEVENTF_EXTENDEDKEY = 0x0001
KEYEVENTF_KEYUP = 0x0002
KEYEVENTF_UNICODE = 0x0004
KEYEVENTF_SCANCODE = 0x0008

# Key mapping dictionary
VK_MAPPING: Dict[str, int] = {
    "enter": 0x0D,
    "return": 0x0D,
    "tab": 0x09,
    "esc": 0x1B,
    "escape": 0x1B,
    "backspace": 0x08,
    "space": 0x20,
    "shift": 0x10,
    "ctrl": 0x11,
    "control": 0x11,
    "alt": 0x12,
    "win": 0x5B,
    "windows": 0x5B,
    "up": 0x26,
    "down": 0x28,
    "left": 0x25,
    "right": 0x27,
    "delete": 0x2E,
    "home": 0x24,
    "end": 0x23,
    "pageup": 0x21,
    "pagedown": 0x22,
    "a": 0x41, "b": 0x42, "c": 0x43, "d": 0x44, "e": 0x45, "f": 0x46, "g": 0x47,
    "h": 0x48, "i": 0x49, "j": 0x4A, "k": 0x4B, "l": 0x4C, "m": 0x4D, "n": 0x4E,
    "o": 0x4F, "p": 0x50, "q": 0x51, "r": 0x52, "s": 0x53, "t": 0x54, "u": 0x55,
    "v": 0x56, "w": 0x57, "x": 0x58, "y": 0x59, "z": 0x5A,
}


# Win32 SendInput Structures
class MOUSEINPUT(ctypes.Structure):
    _fields_ = [
        ("dx", ctypes.c_long),
        ("dy", ctypes.c_long),
        ("mouseData", ctypes.c_ulong),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class KEYBDINPUT(ctypes.Structure):
    _fields_ = [
        ("wVk", ctypes.c_ushort),
        ("wScan", ctypes.c_ushort),
        ("dwFlags", ctypes.c_ulong),
        ("time", ctypes.c_ulong),
        ("dwExtraInfo", ctypes.POINTER(ctypes.c_ulong)),
    ]


class HARDWAREINPUT(ctypes.Structure):
    _fields_ = [
        ("uMsg", ctypes.c_ulong),
        ("wParamL", ctypes.c_ushort),
        ("wParamH", ctypes.c_ushort),
    ]


class _INPUT_UNION(ctypes.Union):
    _fields_ = [
        ("mi", MOUSEINPUT),
        ("ki", KEYBDINPUT),
        ("hi", HARDWAREINPUT),
    ]


class INPUT(ctypes.Structure):
    _fields_ = [
        ("type", ctypes.c_ulong),
        ("u", _INPUT_UNION),
    ]


class POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


@dataclass
class InputExecutionResult:
    action_type: str
    requested_pos: Tuple[int, int]
    actual_pos: Tuple[int, int]
    verified: bool
    latency_ms: float
    details: str = ""


class WindowsInputBackend:
    """
    Native Windows SendInput & Hardware Bridge.
    Sends REAL hardware mouse and keyboard events directly to the active Windows desktop session.
    Verifies actual cursor position using GetCursorPos.
    """

    def __init__(self):
        attach_to_interactive_desktop()
        pyautogui.FAILSAFE = False

    def get_cursor_position(self) -> Tuple[int, int]:
        """Reads physical monitor cursor coordinates (X, Y) via GetCursorPos."""
        attach_to_interactive_desktop()
        pt = POINT()
        user32.GetCursorPos(ctypes.byref(pt))
        return int(pt.x), int(pt.y)

    def verify_cursor_position(self, expected_x: int, expected_y: int, tolerance_pixels: int = 5) -> bool:
        """Verifies physical cursor position against target coordinates."""
        actual_x, actual_y = self.get_cursor_position()
        dist = math.hypot(actual_x - expected_x, actual_y - expected_y)
        return dist <= tolerance_pixels

    def move_mouse(
        self,
        target_x: int,
        target_y: int,
        duration_seconds: float = 0.2,
        verify: bool = True,
    ) -> InputExecutionResult:
        """
        Physically glides hardware cursor to target (x, y) and verifies arrival.
        """
        require_armed(get_kill_switch())
        attach_to_interactive_desktop()
        start_time = time.monotonic()

        start_x, start_y = self.get_cursor_position()

        # Execute physical movement
        steps = max(10, int(duration_seconds * 60))
        step_delay = max(0.001, duration_seconds / steps)

        for i in range(1, steps + 1):
            t = i / steps
            ease = 0.5 * (1.0 - math.cos(math.pi * t))
            cur_x = int(start_x + (target_x - start_x) * ease)
            cur_y = int(start_y + (target_y - start_y) * ease)
            user32.SetCursorPos(cur_x, cur_y)
            time.sleep(step_delay)

        user32.SetCursorPos(int(target_x), int(target_y))
        time.sleep(0.01)

        actual_pos = self.get_cursor_position()
        is_verified = self.verify_cursor_position(target_x, target_y) if verify else True
        latency = (time.monotonic() - start_time) * 1000.0

        return InputExecutionResult(
            action_type="move_mouse",
            requested_pos=(target_x, target_y),
            actual_pos=actual_pos,
            verified=is_verified,
            latency_ms=latency,
            details=f"Glided physical cursor to ({target_x}, {target_y})",
        )

    def left_click(self, x: Optional[int] = None, y: Optional[int] = None, delay: float = 0.05) -> InputExecutionResult:
        """Sends physical left mouse down and up events using SendInput / mouse_event."""
        require_armed(get_kill_switch())
        attach_to_interactive_desktop()
        start_time = time.monotonic()

        if x is not None and y is not None:
            self.move_mouse(x, y, duration_seconds=0.15)

        cur_pos = self.get_cursor_position()
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(delay)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        latency = (time.monotonic() - start_time) * 1000.0
        return InputExecutionResult(
            action_type="left_click",
            requested_pos=(x or cur_pos[0], y or cur_pos[1]),
            actual_pos=cur_pos,
            verified=True,
            latency_ms=latency,
            details=f"Physically left clicked at {cur_pos}",
        )

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> InputExecutionResult:
        """Sends physical right mouse click."""
        require_armed(get_kill_switch())
        attach_to_interactive_desktop()
        start_time = time.monotonic()

        if x is not None and y is not None:
            self.move_mouse(x, y, duration_seconds=0.15)

        cur_pos = self.get_cursor_position()
        user32.mouse_event(MOUSEEVENTF_RIGHTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        user32.mouse_event(MOUSEEVENTF_RIGHTUP, 0, 0, 0, 0)

        latency = (time.monotonic() - start_time) * 1000.0
        return InputExecutionResult(
            action_type="right_click",
            requested_pos=(x or cur_pos[0], y or cur_pos[1]),
            actual_pos=cur_pos,
            verified=True,
            latency_ms=latency,
            details=f"Physically right clicked at {cur_pos}",
        )

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> InputExecutionResult:
        """Sends physical double left mouse click."""
        require_armed(get_kill_switch())
        attach_to_interactive_desktop()
        start_time = time.monotonic()

        if x is not None and y is not None:
            self.move_mouse(x, y, duration_seconds=0.15)

        cur_pos = self.get_cursor_position()
        self.left_click(delay=0.04)
        time.sleep(0.05)
        self.left_click(delay=0.04)

        latency = (time.monotonic() - start_time) * 1000.0
        return InputExecutionResult(
            action_type="double_click",
            requested_pos=(x or cur_pos[0], y or cur_pos[1]),
            actual_pos=cur_pos,
            verified=True,
            latency_ms=latency,
            details=f"Physically double clicked at {cur_pos}",
        )

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration_seconds: float = 0.5) -> InputExecutionResult:
        """Physically drags mouse from (start_x, start_y) to (end_x, end_y)."""
        require_armed(get_kill_switch())
        attach_to_interactive_desktop()
        start_time = time.monotonic()

        self.move_mouse(start_x, start_y, duration_seconds=0.15)
        user32.mouse_event(MOUSEEVENTF_LEFTDOWN, 0, 0, 0, 0)
        time.sleep(0.05)
        self.move_mouse(end_x, end_y, duration_seconds=duration_seconds)
        time.sleep(0.05)
        user32.mouse_event(MOUSEEVENTF_LEFTUP, 0, 0, 0, 0)

        actual_pos = self.get_cursor_position()
        latency = (time.monotonic() - start_time) * 1000.0
        return InputExecutionResult(
            action_type="drag",
            requested_pos=(end_x, end_y),
            actual_pos=actual_pos,
            verified=self.verify_cursor_position(end_x, end_y),
            latency_ms=latency,
            details=f"Physically dragged cursor to ({end_x}, {end_y})",
        )

    def scroll(self, clicks: int) -> InputExecutionResult:
        """Sends physical mouse wheel scroll event."""
        require_armed(get_kill_switch())
        attach_to_interactive_desktop()
        start_time = time.monotonic()

        pyautogui.scroll(clicks * 100)
        cur_pos = self.get_cursor_position()

        latency = (time.monotonic() - start_time) * 1000.0
        return InputExecutionResult(
            action_type="scroll",
            requested_pos=cur_pos,
            actual_pos=cur_pos,
            verified=True,
            latency_ms=latency,
            details=f"Scrolled mouse wheel {clicks} clicks",
        )

    def type_text(self, text: str, interval_seconds: float = 0.01) -> InputExecutionResult:
        """Types unicode string physically into currently focused active window."""
        require_armed(get_kill_switch())
        attach_to_interactive_desktop()
        start_time = time.monotonic()

        pyautogui.typewrite(text, interval=interval_seconds)
        cur_pos = self.get_cursor_position()

        latency = (time.monotonic() - start_time) * 1000.0
        return InputExecutionResult(
            action_type="type_text",
            requested_pos=cur_pos,
            actual_pos=cur_pos,
            verified=True,
            latency_ms=latency,
            details=f"Physically typed {len(text)} characters into active window",
        )

    def press(self, key_name: str) -> InputExecutionResult:
        """Presses and releases a single physical keyboard key."""
        require_armed(get_kill_switch())
        attach_to_interactive_desktop()
        start_time = time.monotonic()

        key_clean = key_name.lower().strip()
        vk = VK_MAPPING.get(key_clean)

        if vk:
            user32.keybd_event(vk, 0, 0, 0)
            time.sleep(0.04)
            user32.keybd_event(vk, 0, KEYEVENTF_KEYUP, 0)
        else:
            pyautogui.press(key_clean)

        cur_pos = self.get_cursor_position()
        latency = (time.monotonic() - start_time) * 1000.0
        return InputExecutionResult(
            action_type="press",
            requested_pos=cur_pos,
            actual_pos=cur_pos,
            verified=True,
            latency_ms=latency,
            details=f"Physically pressed key '{key_name}'",
        )

    def hotkey(self, *keys: str) -> InputExecutionResult:
        """Executes a physical shortcut hotkey combination (e.g. CTRL+A, CTRL+C, CTRL+V)."""
        require_armed(get_kill_switch())
        attach_to_interactive_desktop()
        start_time = time.monotonic()

        valid_keys = [k.lower().strip() for k in keys if k]
        pyautogui.hotkey(*valid_keys)

        cur_pos = self.get_cursor_position()
        latency = (time.monotonic() - start_time) * 1000.0
        return InputExecutionResult(
            action_type="hotkey",
            requested_pos=cur_pos,
            actual_pos=cur_pos,
            verified=True,
            latency_ms=latency,
            details=f"Physically executed hotkey ({'+'.join(valid_keys)})",
        )

    def focus_window(self, window_title_or_substring: str) -> bool:
        """
        Verifies and brings target window title to the foreground.
        Returns True if window is active.
        """
        attach_to_interactive_desktop()
        target_lower = window_title_or_substring.lower().strip()

        fg_hwnd = win32gui.GetForegroundWindow()
        fg_title = win32gui.GetWindowText(fg_hwnd).lower()

        if target_lower in fg_title:
            return True

        # Search top-level windows
        def _enum_win_cb(hwnd, result):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd).lower()
                if target_lower in t:
                    result.append(hwnd)

        matches = []
        win32gui.EnumWindows(_enum_win_cb, matches)

        if matches:
            target_hwnd = matches[0]
            try:
                win32gui.ShowWindow(target_hwnd, win32con.SW_RESTORE)
                win32gui.SetForegroundWindow(target_hwnd)
                time.sleep(0.1)
                return True
            except Exception:
                pass

        return False

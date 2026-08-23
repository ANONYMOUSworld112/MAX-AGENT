"""
MAX OS - Windows Computer Control Backend (Section 7)
tools/backends/computer_control.py

Windows-first desktop computer control backend supporting dynamic perception,
UI Automation, Win32 window management, PyAutoGUI physical input, and mss screen capture.
"""
from __future__ import annotations

import io
import subprocess
import time
from typing import Any, Dict, List, Optional, Tuple

from core.perception.accessibility import ElementDescriptor, UIAccessibilityEngine
from core.perception.window_observer import WindowInfo, WindowObserver
from core.platform.detector import OSFamily, detect_capability_profile
from core.win32_interactive_session import attach_to_interactive_desktop
from tools.interfaces import ComputerTool

try:
    import pyautogui
    pyautogui.FAILSAFE = False
except Exception:
    pyautogui = None

try:
    import mss
except Exception:
    mss = None

try:
    from PIL import Image
except Exception:
    Image = None

try:
    import win32con
    import win32gui
except ImportError:
    win32con = None
    win32gui = None


class ComputerControlBackend(ComputerTool):
    """
    Production-grade Windows ComputerTool backend implementation.
    Integrates dynamic UIA perception, HWND window geometry, and PyAutoGUI physical inputs.
    """

    def __init__(self) -> None:
        attach_to_interactive_desktop()
        self.profile = detect_capability_profile()
        self.uia_engine = UIAccessibilityEngine()
        self.window_observer = WindowObserver()

    def move_mouse(self, x: int, y: int) -> None:
        attach_to_interactive_desktop()
        if pyautogui:
            pyautogui.moveTo(x, y)

    def click(self, x: Optional[int] = None, y: Optional[int] = None, button: str = "left") -> None:
        attach_to_interactive_desktop()
        if pyautogui:
            if x is not None and y is not None:
                pyautogui.click(x=x, y=y, button=button)
            else:
                pyautogui.click(button=button)

    def double_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        attach_to_interactive_desktop()
        if pyautogui:
            if x is not None and y is not None:
                pyautogui.doubleClick(x=x, y=y)
            else:
                pyautogui.doubleClick()

    def right_click(self, x: Optional[int] = None, y: Optional[int] = None) -> None:
        self.click(x=x, y=y, button="right")

    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int) -> None:
        attach_to_interactive_desktop()
        if pyautogui:
            pyautogui.moveTo(start_x, start_y)
            pyautogui.dragTo(end_x, end_y, button="left")

    def scroll(self, clicks: int = 3, direction: str = "down") -> None:
        attach_to_interactive_desktop()
        if pyautogui:
            amount = -abs(clicks) * 100 if direction == "down" else abs(clicks) * 100
            pyautogui.scroll(amount)

    def type_text(self, text: str) -> None:
        attach_to_interactive_desktop()
        if pyautogui:
            pyautogui.write(text, interval=0.01)

    def press_keys(self, *keys: str) -> None:
        attach_to_interactive_desktop()
        if pyautogui:
            pyautogui.hotkey(*keys)

    def screenshot(self, region: Optional[Tuple[int, int, int, int]] = None) -> bytes:
        attach_to_interactive_desktop()
        if mss and Image:
            with mss.mss() as sct:
                if region:
                    left, top, width, height = region
                    monitor = {"left": left, "top": top, "width": width, "height": height}
                else:
                    monitor = sct.monitors[0]
                sct_img = sct.grab(monitor)
                img = Image.frombytes("RGB", sct_img.size, sct_img.bgra, "raw", "BGRX")
                buf = io.BytesIO()
                img.save(buf, format="PNG")
                return buf.getvalue()
        elif pyautogui:
            img = pyautogui.screenshot(region=region)
            buf = io.BytesIO()
            img.save(buf, format="PNG")
            return buf.getvalue()
        return b""

    def list_windows(self) -> List[Dict[str, Any]]:
        attach_to_interactive_desktop()
        windows = self.window_observer.enumerate_visible_windows()
        return [
            {
                "id": str(w.hwnd),
                "title": w.title,
                "process_name": w.process_name,
                "pid": w.pid,
                "bounds": w.bounds,
                "is_foreground": w.is_foreground,
            }
            for w in windows
        ]

    def focus_window(self, window_id: str) -> bool:
        attach_to_interactive_desktop()
        if not win32gui:
            return False
        try:
            hwnd = int(window_id) if window_id.isdigit() else 0
            if not hwnd:
                for w in self.window_observer.enumerate_visible_windows():
                    if window_id.lower() in w.title.lower() or window_id.lower() in w.process_name.lower():
                        hwnd = w.hwnd
                        break
            if hwnd and win32gui.IsWindow(hwnd):
                win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                try:
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    pass
                return True
        except Exception:
            pass
        return False

    def minimize_window(self, window_id: str) -> bool:
        return self._send_window_cmd(window_id, win32con.SW_MINIMIZE if win32con else 6)

    def maximize_window(self, window_id: str) -> bool:
        return self._send_window_cmd(window_id, win32con.SW_MAXIMIZE if win32con else 3)

    def restore_window(self, window_id: str) -> bool:
        return self._send_window_cmd(window_id, win32con.SW_RESTORE if win32con else 9)

    def close_window(self, window_id: str) -> bool:
        attach_to_interactive_desktop()
        if not win32gui or not win32con:
            return False
        try:
            hwnd = int(window_id) if window_id.isdigit() else 0
            if not hwnd:
                for w in self.window_observer.enumerate_visible_windows():
                    if window_id.lower() in w.title.lower():
                        hwnd = w.hwnd
                        break
            if hwnd and win32gui.IsWindow(hwnd):
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                return True
        except Exception:
            pass
        return False

    def _send_window_cmd(self, window_id: str, cmd: int) -> bool:
        attach_to_interactive_desktop()
        if not win32gui:
            return False
        try:
            hwnd = int(window_id) if window_id.isdigit() else 0
            if not hwnd:
                for w in self.window_observer.enumerate_visible_windows():
                    if window_id.lower() in w.title.lower():
                        hwnd = w.hwnd
                        break
            if hwnd and win32gui.IsWindow(hwnd):
                win32gui.ShowWindow(hwnd, cmd)
                return True
        except Exception:
            pass
        return False


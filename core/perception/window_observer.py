"""
MAX OS — Win32 Window Observer (Section 8)
core/perception/window_observer.py

Inspects Win32 window handles (HWND), process ownership, foreground window,
and exact bounding geometry on Microsoft Windows.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

import psutil

try:
    import win32con
    import win32gui
    import win32process
except Exception:
    win32con = None
    win32gui = None
    win32process = None

from core.win32_interactive_session import attach_to_interactive_desktop


@dataclass
class WindowInfo:
    hwnd: int
    title: str
    process_name: str
    pid: int
    left: int
    top: int
    width: int
    height: int
    is_foreground: bool
    is_maximized: bool
    is_minimized: bool

    @property
    def bounds(self) -> Tuple[int, int, int, int]:
        return (self.left, self.top, self.width, self.height)

    @property
    def center(self) -> Tuple[int, int]:
        return (self.left + (self.width // 2), self.top + (self.height // 2))


class WindowObserver:
    """
    Win32 HWND observer for desktop window state enumeration.
    """

    def get_foreground_window(self) -> Optional[WindowInfo]:
        attach_to_interactive_desktop()
        try:
            hwnd = win32gui.GetForegroundWindow()
            if hwnd:
                return self._parse_hwnd(hwnd, is_foreground=True)
        except Exception:
            pass
        return None

    def enumerate_visible_windows(self) -> List[WindowInfo]:
        attach_to_interactive_desktop()
        fg_hwnd = win32gui.GetForegroundWindow()
        windows: List[WindowInfo] = []

        def enum_cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                title = win32gui.GetWindowText(hwnd)
                if title:
                    info = self._parse_hwnd(hwnd, is_foreground=(hwnd == fg_hwnd))
                    if info and (info.width > 20 or info.title):
                        windows.append(info)
            return True

        try:
            win32gui.EnumWindows(enum_cb, 0)
        except Exception:
            pass

        return windows

    def _parse_hwnd(self, hwnd: int, is_foreground: bool = False) -> Optional[WindowInfo]:
        try:
            title = win32gui.GetWindowText(hwnd)
            rect = win32gui.GetWindowRect(hwnd)
            left, top, right, bottom = rect
            width = right - left
            height = bottom - top

            placement = win32gui.GetWindowPlacement(hwnd)
            is_maximized = (placement[1] == win32con.SW_SHOWMAXIMIZED)
            is_minimized = (placement[1] == win32con.SW_SHOWMINIMIZED)

            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            pname = ""
            try:
                pname = psutil.Process(pid).name()
            except Exception:
                pass

            return WindowInfo(
                hwnd=hwnd,
                title=title,
                process_name=pname,
                pid=pid,
                left=left,
                top=top,
                width=width,
                height=height,
                is_foreground=is_foreground,
                is_maximized=is_maximized,
                is_minimized=is_minimized,
            )
        except Exception:
            return None

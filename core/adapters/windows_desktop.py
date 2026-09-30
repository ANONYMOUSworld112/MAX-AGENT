"""
Windows Desktop Adapter with UIA Semantic Targeting & Win32 API Integration
=============================================================================

Allowlisted platform adapter for Windows desktop automation.
Encapsulates pointer, keyboard, UIA accessibility tree, and window enumeration.
"""

from __future__ import annotations

import ctypes
import logging
import platform
import time
from typing import Any, Dict, List, Optional, Tuple, Union

from core.adapters.base import DesktopAdapter

logger = logging.getLogger("max.adapters.windows_desktop")

try:
    import pyautogui
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False


class WindowsDesktopAdapter(DesktopAdapter):
    """Production Windows desktop adapter."""

    def __init__(self) -> None:
        if platform.system() != "Windows":
            logger.warning("WindowsDesktopAdapter initialized on non-Windows OS: %s", platform.system())
        self._user32 = ctypes.windll.user32 if platform.system() == "Windows" else None

    def click(self, x: int, y: int, clicks: int = 1, button: str = "left") -> bool:
        """Click at specific screen coordinates."""
        try:
            if _PYAUTOGUI:
                pyautogui.click(x=x, y=y, clicks=clicks, button=button)
                return True
            elif self._user32:
                self._user32.SetCursorPos(x, y)
                down = 0x0002 if button == "left" else 0x0008
                up = 0x0004 if button == "left" else 0x0010
                for _ in range(clicks):
                    self._user32.mouse_event(down, 0, 0, 0, 0)
                    self._user32.mouse_event(up, 0, 0, 0, 0)
                return True
            return False
        except Exception as exc:
            logger.error("Click failed at (%d, %d): %s", x, y, exc)
            return False

    def type_text(self, text: str, interval: float = 0.0) -> bool:
        """Type text into active focused element."""
        try:
            if _PYAUTOGUI:
                pyautogui.write(text, interval=interval)
                return True
            return False
        except Exception as exc:
            logger.error("type_text failed: %s", exc)
            return False

    def hotkey(self, *keys: str) -> bool:
        """Press a combination of keys simultaneously."""
        try:
            if _PYAUTOGUI:
                pyautogui.hotkey(*keys)
                return True
            return False
        except Exception as exc:
            logger.error("hotkey failed for %s: %s", keys, exc)
            return False

    def find_element(
        self,
        name: str = "",
        control_type: str = "",
        timeout_seconds: float = 2.0,
    ) -> Optional[Dict[str, Any]]:
        """Search accessibility tree for a named control using pywinauto UIA if available."""
        try:
            from pywinauto import Desktop
            desktop = Desktop(backend="uia")
            norm_name = name.strip()

            start_t = time.time()
            while time.time() - start_t < timeout_seconds:
                try:
                    kwargs: Dict[str, Any] = {}
                    if norm_name:
                        kwargs["title_re"] = f".*{norm_name}.*"
                    if control_type:
                        kwargs["control_type"] = control_type

                    elem = desktop.window(**kwargs).wrapper_object()
                    rect = elem.rectangle()
                    return {
                        "name": elem.window_text(),
                        "control_type": elem.friendly_class_name(),
                        "bounding_box": (rect.left, rect.top, rect.right, rect.bottom),
                        "is_enabled": elem.is_enabled(),
                        "is_visible": elem.is_visible(),
                    }
                except Exception:
                    time.sleep(0.2)
        except ImportError:
            logger.debug("pywinauto not installed; UIA element search unavailable.")
        except Exception as exc:
            logger.warning("UIA search failed for name='%s': %s", name, exc)

        return None

    def click_element(self, element_or_name: Union[str, Dict[str, Any]]) -> bool:
        """Click an element identified by UIA name or dictionary."""
        if isinstance(element_or_name, str):
            elem = self.find_element(name=element_or_name)
        else:
            elem = element_or_name

        if not elem:
            return False

        bb = elem.get("bounding_box", (0, 0, 0, 0))
        center_x = (bb[0] + bb[2]) // 2
        center_y = (bb[1] + bb[3]) // 2
        return self.click(center_x, center_y)

    def list_windows(self) -> List[Dict[str, Any]]:
        """Enumerate visible desktop windows using Win32 EnumWindows."""
        windows: List[Dict[str, Any]] = []
        if not self._user32:
            return windows

        def enum_proc(hwnd: int, lparam: Any) -> bool:
            if self._user32.IsWindowVisible(hwnd):
                length = self._user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buff = ctypes.create_unicode_buffer(length + 1)
                    self._user32.GetWindowTextW(hwnd, buff, length + 1)
                    title = buff.value.strip()
                    if title:
                        pid = ctypes.c_ulong()
                        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
                        windows.append({
                            "handle": hwnd,
                            "title": title,
                            "pid": pid.value,
                            "is_visible": True,
                        })
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_void_p)
        cb = WNDENUMPROC(enum_proc)
        self._user32.EnumWindows(cb, 0)
        return windows

    def get_active_window(self) -> Optional[Dict[str, Any]]:
        """Return the currently focused foreground window."""
        if not self._user32:
            return None
        hwnd = self._user32.GetForegroundWindow()
        if not hwnd:
            return None

        length = self._user32.GetWindowTextLengthW(hwnd)
        buff = ctypes.create_unicode_buffer(length + 1)
        self._user32.GetWindowTextW(hwnd, buff, length + 1)
        title = buff.value.strip()

        pid = ctypes.c_ulong()
        self._user32.GetWindowThreadProcessId(hwnd, ctypes.byref(pid))

        return {
            "handle": hwnd,
            "title": title,
            "pid": pid.value,
            "is_visible": True,
        }

    def focus_window(self, title_or_handle: Union[str, int]) -> bool:
        """Bring window to foreground."""
        if not self._user32:
            return False

        target_hwnd = None
        if isinstance(title_or_handle, int):
            target_hwnd = title_or_handle
        else:
            norm = title_or_handle.lower().strip()
            for win in self.list_windows():
                if norm in win["title"].lower():
                    target_hwnd = win["handle"]
                    break

        if target_hwnd:
            self._user32.ShowWindow(target_hwnd, 9)  # SW_RESTORE
            self._user32.SetForegroundWindow(target_hwnd)
            return True
        return False

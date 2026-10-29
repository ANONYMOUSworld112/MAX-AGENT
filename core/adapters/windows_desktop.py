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
from core.max_infra.kill_switch import KillSwitch, KillSwitchTrippedError

logger = logging.getLogger("max.adapters.windows_desktop")

try:
    import pyautogui
    _PYAUTOGUI = True
except ImportError:
    _PYAUTOGUI = False

try:
    import psutil
except ImportError:
    psutil = None


class DesktopUnavailableError(RuntimeError):
    """Raised when the desktop geometry or native desktop APIs cannot be verified."""
    pass


class WindowsDesktopAdapter(DesktopAdapter):
    """Production Windows desktop adapter."""

    def attach_desktop(self) -> bool:
        """Attach current thread to interactive input desktop if needed."""
        if self._user32:
            try:
                self._user32.SetProcessDPIAware()
                inp = self._user32.OpenInputDesktop(0, False, 0x01FF)
                if inp:
                    return bool(self._user32.SetThreadDesktop(inp))
            except Exception:
                pass
        return False

    def __init__(self) -> None:
        if platform.system() != "Windows":
            logger.warning("WindowsDesktopAdapter initialized on non-Windows OS: %s", platform.system())
        self._user32 = ctypes.windll.user32 if platform.system() == "Windows" else None
        self.attach_desktop()

    def get_screen_bounds(self) -> Tuple[int, int, int, int]:
        """Return virtual/primary desktop bounds as half-open (min_x, min_y, max_x, max_y).

        Raises DesktopUnavailableError if the desktop geometry cannot be verified from the OS.
        """
        if not self._user32:
            raise DesktopUnavailableError(
                "Windows desktop APIs are unavailable on this host or session."
            )

        try:
            self._user32.SetProcessDPIAware()
            vx = self._user32.GetSystemMetrics(76)  # SM_XVIRTUALSCREEN
            vy = self._user32.GetSystemMetrics(77)  # SM_YVIRTUALSCREEN
            vw = self._user32.GetSystemMetrics(78)  # SM_CXVIRTUALSCREEN
            vh = self._user32.GetSystemMetrics(79)  # SM_CYVIRTUALSCREEN
            if vw > 0 and vh > 0:
                return (vx, vy, vx + vw, vy + vh)

            w = self._user32.GetSystemMetrics(0)
            h = self._user32.GetSystemMetrics(1)
            if w > 0 and h > 0:
                return (0, 0, w, h)
        except Exception as exc:
            raise DesktopUnavailableError(f"Error querying native display geometry: {exc}") from exc

        raise DesktopUnavailableError(
            "Unable to verify physical display geometry: operating system returned invalid or non-positive metrics."
        )

    def validate_coordinates(self, x: int, y: int) -> None:
        """Validate coordinates against the half-open screen bounds [min_x, max_x) x [min_y, max_y)
        and verify that the coordinate falls inside an active physical display monitor (preventing gap traversal).
        """
        min_x, min_y, max_x, max_y = self.get_screen_bounds()
        if not (min_x <= x < max_x and min_y <= y < max_y):
            raise ValueError(
                f"Coordinates ({x}, {y}) are outside valid screen bounds "
                f"[{min_x}, {max_x}) x [{min_y}, {max_y})"
            )

        if not self._user32:
            raise DesktopUnavailableError(
                "Windows desktop APIs are unavailable to verify target monitor."
            )

        try:
            from ctypes import wintypes
            if not getattr(self._user32.MonitorFromPoint, "argtypes", None):
                self._user32.MonitorFromPoint.argtypes = [wintypes.POINT, wintypes.DWORD]
                self._user32.MonitorFromPoint.restype = wintypes.HMONITOR

            pt = wintypes.POINT(x, y)
            # MONITOR_DEFAULTTONULL (0) returns NULL (0) if the point does not intersect any physical monitor
            hmon = self._user32.MonitorFromPoint(pt, 0)
            if not hmon:
                raise ValueError(
                    f"Coordinates ({x}, {y}) do not belong to an active monitor (unmapped monitor gap or off-screen)."
                )
        except ValueError:
            raise
        except Exception as exc:
            raise DesktopUnavailableError(
                f"Unable to verify the target monitor for coordinates ({x}, {y}): {exc}"
            ) from exc

    def move_to(self, x: int, y: int) -> bool:
        """Move cursor to specific screen coordinates."""
        KillSwitch.get_instance().guard()
        self.validate_coordinates(x, y)
        try:
            if _PYAUTOGUI:
                try:
                    pyautogui.moveTo(x, y)
                    return True
                except pyautogui.FailSafeException as exc:
                    KillSwitch.get_instance().trip("PyAutoGUI corner failsafe triggered by user")
                    raise KillSwitchTrippedError("Emergency stop triggered via cursor failsafe corner.") from exc
                except Exception as exc:
                    KillSwitch.get_instance().guard()
                    logger.debug("pyautogui.moveTo failed (%s); falling back to user32", exc)
            if self._user32:
                ret = self._user32.SetCursorPos(x, y)
                return bool(ret)
            return False
        except (KillSwitchTrippedError, DesktopUnavailableError):
            raise
        except Exception as exc:
            logger.error("move_to failed at (%d, %d): %s", x, y, exc)
            return False

    def get_cursor_pos(self) -> Tuple[int, int]:
        """Query current pointer coordinates."""
        if self._user32:
            try:
                from ctypes import wintypes
                pt = wintypes.POINT()
                if self._user32.GetCursorPos(ctypes.byref(pt)):
                    return (pt.x, pt.y)
            except Exception:
                pass
        if _PYAUTOGUI:
            try:
                pos = pyautogui.position()
                return (pos.x, pos.y)
            except Exception:
                pass
        return (0, 0)

    def get_screen_size(self) -> Tuple[int, int]:
        """Query physical screen resolution."""
        min_x, min_y, max_x, max_y = self.get_screen_bounds()
        return (max_x - min_x, max_y - min_y)

    def click(self, x: int, y: int, clicks: int = 1, button: str = "left") -> bool:
        """Click at specific screen coordinates."""
        KillSwitch.get_instance().guard()
        self.validate_coordinates(x, y)
        try:
            if _PYAUTOGUI:
                try:
                    pyautogui.click(x=x, y=y, clicks=clicks, button=button)
                    return True
                except pyautogui.FailSafeException as exc:
                    KillSwitch.get_instance().trip("PyAutoGUI corner failsafe triggered by user")
                    raise KillSwitchTrippedError("Emergency stop triggered via cursor failsafe corner.") from exc
                except Exception as exc:
                    KillSwitch.get_instance().guard()
                    logger.debug("pyautogui.click failed (%s); falling back to user32", exc)
            if self._user32:
                self._user32.SetCursorPos(x, y)
                down = 0x0002 if button == "left" else 0x0008
                up = 0x0004 if button == "left" else 0x0010
                for _ in range(clicks):
                    self._user32.mouse_event(down, 0, 0, 0, 0)
                    self._user32.mouse_event(up, 0, 0, 0, 0)
                return True
            return False
        except (KillSwitchTrippedError, DesktopUnavailableError):
            raise
        except Exception as exc:
            logger.error("Click failed at (%d, %d): %s", x, y, exc)
            return False

    def type_text(self, text: str, interval: float = 0.0) -> bool:
        """Type text into active focused element."""
        KillSwitch.get_instance().guard()
        try:
            if _PYAUTOGUI:
                # Keep every desktop typing route on the shared keyboard-event
                # path, including Unicode and multiline text. This never pastes.
                from actions.computer_control import _type

                _type(str(text), interval=max(0.0, float(interval)))
                return True
            if not self._user32:
                return False
            for char in text:
                translated = self._user32.VkKeyScanW(ord(char))
                if translated == -1:
                    return False
                virtual_key = translated & 0xFF
                modifiers = (translated >> 8) & 0xFF
                modifier_keys = []
                if modifiers & 1:
                    modifier_keys.append(0x10)  # SHIFT
                if modifiers & 2:
                    modifier_keys.append(0x11)  # CTRL
                if modifiers & 4:
                    modifier_keys.append(0x12)  # ALT
                for modifier in modifier_keys:
                    self._user32.keybd_event(modifier, 0, 0, 0)
                self._user32.keybd_event(virtual_key, 0, 0, 0)
                self._user32.keybd_event(virtual_key, 0, 0x0002, 0)  # KEYUP
                for modifier in reversed(modifier_keys):
                    self._user32.keybd_event(modifier, 0, 0x0002, 0)
                if interval:
                    time.sleep(interval)
            return True
        except Exception as exc:
            logger.error("type_text failed: %s", exc)
            return False

    def hotkey(self, *keys: str) -> bool:
        """Press a combination of keys simultaneously."""
        try:
            if _PYAUTOGUI:
                pyautogui.hotkey(*keys)
                return True
            if not self._user32:
                return False
            virtual_keys = {
                "win": 0x5B, "enter": 0x0D, "return": 0x0D,
                "ctrl": 0x11, "control": 0x11, "alt": 0x12,
                "shift": 0x10, "tab": 0x09, "esc": 0x1B,
                "escape": 0x1B, "space": 0x20,
            }
            codes = []
            for key in keys:
                code = virtual_keys.get(key.lower())
                if code is None and len(key) == 1:
                    translated = self._user32.VkKeyScanW(ord(key))
                    code = translated & 0xFF if translated != -1 else None
                if code is None:
                    return False
                codes.append(code)
            for code in codes:
                self._user32.keybd_event(code, 0, 0, 0)
            for code in reversed(codes):
                self._user32.keybd_event(code, 0, 0x0002, 0)
            return True
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
                        process_name = ""
                        if psutil is not None:
                            try:
                                process_name = psutil.Process(pid.value).name()
                            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                                pass
                        windows.append({
                            "handle": hwnd,
                            "title": title,
                            "pid": pid.value,
                            "process_name": process_name,
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

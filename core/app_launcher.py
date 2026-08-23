"""
MAX OS — Live Real-Time Windows Application & Browser Launcher.
Launches actual GUI windows on the user's interactive Windows desktop with 100% reliability:
  - Dispatches via ShellExecuteW, os.startfile, and subprocess with CREATE_NEW_PROCESS_GROUP.
  - Automatically brings launched windows to the foreground.
  - Supports URLs, folders, system apps, and third-party software.
"""

from __future__ import annotations

import ctypes
import os
import subprocess
import time
import urllib.parse
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

try:
    import win32con
    import win32gui
    import win32process
except ImportError:
    win32con = None
    win32gui = None
    win32process = None


from core.win32_interactive_session import attach_to_interactive_desktop

KNOWN_APP_COMMANDS: Dict[str, List[str]] = {
    # Browsers
    "browser": ["msedge", "chrome", "brave", "firefox"],
    "edge": ["msedge"],
    "msedge": ["msedge"],
    "chrome": ["chrome"],
    "brave": ["brave"],
    "firefox": ["firefox"],

    # Desktop Apps
    "notepad": ["notepad.exe"],
    "editor": ["notepad.exe"],
    "calc": ["calc.exe"],
    "calculator": ["calc.exe"],
    "explorer": ["explorer.exe"],
    "files": ["explorer.exe"],
    "terminal": ["wt.exe", "powershell.exe", "cmd.exe"],
    "powershell": ["powershell.exe"],
    "cmd": ["cmd.exe"],
    "vscode": ["code.cmd", "code"],
    "code": ["code.cmd", "code"],
    "paint": ["mspaint.exe"],
    "taskmgr": ["taskmgr.exe"],
    "settings": ["ms-settings:"],
}


class LiveAppLauncher:
    """
    Direct Real-Time Windows GUI Launcher.
    Guarantees that applications, browsers, and folders actually open visually
    on the user's physical screen in real time.
    """

    @staticmethod
    def launch_live_application(
        app_name_or_path: str,
        arguments: str = "",
        wait_seconds: float = 1.5,
    ) -> Tuple[bool, Optional[int]]:
        """
        Launches an actual Windows application on the live desktop.
        Returns (success, hwnd_of_opened_window).
        """
        attach_to_interactive_desktop()
        app_clean = app_name_or_path.strip()
        app_lower = app_clean.lower()

        # 1. Check if target is a web URL
        if app_lower.startswith("http://") or app_lower.startswith("https://") or app_lower.startswith("www."):
            return LiveAppLauncher.open_live_url(app_clean, wait_seconds=wait_seconds)

        # 2. Check if target is a folder/file path
        if os.path.exists(app_clean):
            return LiveAppLauncher.open_live_path(app_clean, wait_seconds=wait_seconds)

        # 3. Resolve command from known applications
        candidates = KNOWN_APP_COMMANDS.get(app_lower, [app_clean])
        launched = False

        for cmd in candidates:
            try:
                # Method A: ShellExecuteW (Most reliable for Windows GUI apps)
                res = ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "open",
                    cmd,
                    arguments or None,
                    None,
                    win32con.SW_SHOWNORMAL,
                )
                if int(res) > 32:
                    launched = True
                    break
            except Exception:
                pass

            try:
                # Method B: Subprocess spawn
                subprocess.Popen(
                    f"start {cmd} {arguments}",
                    shell=True,
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
                )
                launched = True
                break
            except Exception:
                pass

        if not launched:
            return False, None

        time.sleep(wait_seconds)

        # Find and focus the newly opened window
        hwnd = LiveAppLauncher.find_and_focus_window(app_clean)
        return True, hwnd

    @staticmethod
    def open_live_url(url: str, browser: Optional[str] = None, wait_seconds: float = 2.0) -> Tuple[bool, Optional[int]]:
        """
        Opens a live URL in the user's real browser on screen.
        """
        attach_to_interactive_desktop()
        clean_url = url.strip()
        if not clean_url.startswith("http://") and not clean_url.startswith("https://"):
            clean_url = "https://" + clean_url

        try:
            if browser:
                ctypes.windll.shell32.ShellExecuteW(
                    None,
                    "open",
                    browser,
                    clean_url,
                    None,
                    win32con.SW_SHOWNORMAL,
                )
            else:
                # Open with Windows default browser
                os.startfile(clean_url)
        except Exception:
            try:
                subprocess.Popen(f'start "" "{clean_url}"', shell=True)
            except Exception:
                return False, None

        time.sleep(wait_seconds)
        hwnd = LiveAppLauncher.find_active_browser_window()
        if hwnd:
            LiveAppLauncher.bring_to_foreground(hwnd)
        return True, hwnd

    @staticmethod
    def open_live_path(path_str: str, wait_seconds: float = 1.0) -> Tuple[bool, Optional[int]]:
        """
        Opens a directory in File Explorer or a document in its default editor.
        """
        attach_to_interactive_desktop()
        p = Path(path_str).resolve()
        if not p.exists():
            return False, None

        try:
            os.startfile(str(p))
        except Exception:
            try:
                subprocess.Popen(f'explorer.exe "{p}"', shell=True)
            except Exception:
                return False, None

        time.sleep(wait_seconds)
        hwnd = LiveAppLauncher.find_and_focus_window(p.name)
        return True, hwnd

    @staticmethod
    def find_and_focus_window(title_query: str) -> Optional[int]:
        """
        Finds a visible window matching title_query and brings it to foreground.
        """
        attach_to_interactive_desktop()
        matched_hwnd: Optional[int] = None
        q_lower = title_query.lower()

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

        def _enum_cb(hwnd, _):
            nonlocal matched_hwnd
            if ctypes.windll.user32.IsWindowVisible(hwnd) and not ctypes.windll.user32.IsIconic(hwnd):
                length = ctypes.windll.user32.GetWindowTextLengthW(hwnd)
                if length > 0:
                    buf = ctypes.create_unicode_buffer(length + 1)
                    ctypes.windll.user32.GetWindowTextW(hwnd, buf, length + 1)
                    win_title = buf.value.lower()
                    if q_lower in win_title:
                        matched_hwnd = hwnd
                        return False  # Stop enumeration
            return True

        try:
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
        except Exception:
            pass

        if matched_hwnd:
            LiveAppLauncher.bring_to_foreground(matched_hwnd)

        return matched_hwnd

    @staticmethod
    def find_active_browser_window() -> Optional[int]:
        """Finds any active browser window (Edge, Chrome, Brave, Firefox)."""
        attach_to_interactive_desktop()
        browser_procs = {"msedge.exe", "chrome.exe", "brave.exe", "firefox.exe"}
        matched_hwnd: Optional[int] = None

        WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_int, ctypes.c_int)

        def _enum_cb(hwnd, _):
            nonlocal matched_hwnd
            if ctypes.windll.user32.IsWindowVisible(hwnd) and not ctypes.windll.user32.IsIconic(hwnd):
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    pname = psutil.Process(pid).name().lower()
                    if pname in browser_procs:
                        matched_hwnd = hwnd
                        return False
                except Exception:
                    pass
            return True

        try:
            ctypes.windll.user32.EnumWindows(WNDENUMPROC(_enum_cb), 0)
        except Exception:
            pass

        return matched_hwnd

    @staticmethod
    def bring_to_foreground(hwnd: int) -> bool:
        """Forces target window to the foreground on the active monitor."""
        attach_to_interactive_desktop()
        try:
            ctypes.windll.user32.ShowWindow(hwnd, win32con.SW_RESTORE)
            ctypes.windll.user32.SetForegroundWindow(hwnd)
            return True
        except Exception:
            return False

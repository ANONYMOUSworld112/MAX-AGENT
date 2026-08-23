"""
MAX OS - Platform Detection & Capability Profile
core/platform/detector.py

Design principle (non-negotiable): the capability ceiling comes only from
real system facts (os.geteuid(), IsUserAnAdmin(), environment variables) —
never from user text or LLM output. No prompt, however phrased, raises the
ceiling above what detection measured on the machine, right now.
"""
from __future__ import annotations

import ctypes
import os
import platform
import shutil
import sys
from dataclasses import dataclass
from enum import Enum
from typing import Dict, Optional


class OSFamily(str, Enum):
    LINUX = "linux"
    WINDOWS = "windows"
    MACOS = "macos"
    UNKNOWN = "unknown"


class DisplayServer(str, Enum):
    X11 = "x11"
    WAYLAND = "wayland"
    WIN32 = "win32"
    NONE = "none"
    UNKNOWN = "unknown"


class RiskLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class ControlLevel(str, Enum):
    FULL = "full"
    RESTRICTED = "restricted"


_RISK_ORDER = [RiskLevel.LOW, RiskLevel.MEDIUM, RiskLevel.HIGH, RiskLevel.CRITICAL]


@dataclass(frozen=True)
class CapabilityProfile:
    os_family: OSFamily
    os_version: str
    architecture: str
    interactive_user: str
    is_elevated: bool
    is_admin: bool
    session_id: int
    station_name: str
    desktop_name: str
    uac_context: str
    secure_desktop_detected: bool
    interactive_session_available: bool
    display_available: bool
    display_server: DisplayServer
    desktop_environment: Optional[str]
    control_level: ControlLevel
    max_autonomous_risk: RiskLevel
    requires_confirmation_above: RiskLevel
    input_backend: str
    accessibility_backend: str
    uia_available: bool
    browser_capability: bool
    terminal_capability: str
    filesystem_capability: bool
    privileged_ops_allowed: bool

    def can_run_autonomously(self, risk: RiskLevel) -> bool:
        # CRITICAL is a hard gate, independent of platform. This is the one
        # line in the whole system that must never become configurable.
        if risk == RiskLevel.CRITICAL:
            return False
        return _RISK_ORDER.index(risk) <= _RISK_ORDER.index(self.max_autonomous_risk)

    def summary(self) -> str:
        rows = [
            ("OS", f"{self.os_family.value} ({self.os_version}) [{self.architecture}]"),
            ("User", f"{self.interactive_user} (Elevated: {self.is_elevated}, Admin: {self.is_admin})"),
            ("Session", f"SessionID={self.session_id}, Winsta={self.station_name}, Desktop={self.desktop_name}"),
            ("Display server", self.display_server.value),
            ("Display available", str(self.display_available)),
            ("UAC context", self.uac_context),
            ("Secure desktop", str(self.secure_desktop_detected)),
            ("Control level", self.control_level.value),
            ("Max autonomous risk", self.max_autonomous_risk.value),
            ("Confirm above", self.requires_confirmation_above.value),
            ("Input backend", self.input_backend),
            ("Accessibility backend", f"{self.accessibility_backend} (Available: {self.uia_available})"),
            ("Browser capability", str(self.browser_capability)),
            ("Terminal capability", self.terminal_capability),
            ("Filesystem capability", str(self.filesystem_capability)),
            ("Privileged ops allowed", str(self.privileged_ops_allowed)),
        ]
        width = max(len(k) for k, _ in rows)
        return "\n".join(f"{k.ljust(width)} : {v}" for k, v in rows)


def _detect_os_family() -> OSFamily:
    system = platform.system().lower()
    if system == "linux":
        return OSFamily.LINUX
    if system == "windows":
        return OSFamily.WINDOWS
    if system == "darwin":
        return OSFamily.MACOS
    return OSFamily.UNKNOWN


def _detect_display_server() -> DisplayServer:
    if platform.system().lower() == "windows":
        return DisplayServer.WIN32
    if os.environ.get("WAYLAND_DISPLAY"):
        return DisplayServer.WAYLAND
    if os.environ.get("DISPLAY"):
        return DisplayServer.X11
    return DisplayServer.NONE


def _detect_desktop_environment() -> Optional[str]:
    if platform.system().lower() == "windows":
        return "Windows Desktop (Explorer)"
    for var in ("XDG_CURRENT_DESKTOP", "DESKTOP_SESSION", "GDMSESSION"):
        val = os.environ.get(var)
        if val:
            return val
    return None


def _detect_elevation(os_family: OSFamily) -> tuple[bool, bool]:
    """Returns (is_elevated, is_admin)."""
    if os_family in (OSFamily.LINUX, OSFamily.MACOS):
        geteuid = getattr(os, "geteuid", None)
        is_root = bool(geteuid and geteuid() == 0)
        return is_root, is_root
    if os_family == OSFamily.WINDOWS:
        try:
            is_admin = bool(ctypes.windll.shell32.IsUserAnAdmin())
            return is_admin, is_admin
        except Exception:
            return False, False
    return False, False


def _detect_windows_session_info() -> tuple[int, str, str, bool, bool]:
    """Returns (session_id, station_name, desktop_name, display_available, secure_desktop)."""
    if platform.system().lower() != "windows":
        return 0, "none", "none", False, False

    session_id = 0
    try:
        session_id = getattr(os, "getlogin", lambda: 0)()
    except Exception:
        pass

    station_name = "Winsta0"
    desktop_name = "Default"
    display_available = True
    secure_desktop = False

    try:
        user32 = ctypes.windll.user32
        hwin = user32.GetProcessWindowStation()
        if hwin:
            buf = ctypes.create_unicode_buffer(256)
            if user32.GetUserObjectInformationW(hwin, 2, buf, ctypes.sizeof(buf), None):
                station_name = buf.value

        hdesk = user32.GetThreadDesktop(user32.GetCurrentThreadId())
        if hdesk:
            buf = ctypes.create_unicode_buffer(256)
            if user32.GetUserObjectInformationW(hdesk, 2, buf, ctypes.sizeof(buf), None):
                desktop_name = buf.value

        if desktop_name.lower() in ("winlogon", "screen-saver"):
            secure_desktop = True
    except Exception:
        pass

    return session_id, station_name, desktop_name, display_available, secure_desktop


def _detect_uia_available() -> bool:
    if platform.system().lower() != "windows":
        return False
    try:
        import comtypes.client
        comtypes.client.GetModule("UIAutomationCore.dll")
        return True
    except Exception:
        return True  # Native COM DLL exists on Windows 7+


def _detect_terminal_capability() -> str:
    if shutil.which("pwsh"):
        return "pwsh"
    if shutil.which("powershell"):
        return "powershell"
    if shutil.which("cmd"):
        return "cmd"
    if shutil.which("bash"):
        return "bash"
    return "subprocess"


def detect_capability_profile() -> CapabilityProfile:
    os_family = _detect_os_family()
    os_version = platform.version()
    architecture = platform.machine() or platform.architecture()[0]
    interactive_user = os.environ.get("USERNAME") or os.environ.get("USER") or "unknown"
    is_elevated, is_admin = _detect_elevation(os_family)

    session_id, station_name, desktop_name, display_available, secure_desktop = _detect_windows_session_info()

    if os_family == OSFamily.LINUX:
        display_server = _detect_display_server()
        desktop_environment = _detect_desktop_environment()
        control_level = ControlLevel.FULL
        max_autonomous_risk = RiskLevel.HIGH
        requires_confirmation_above = RiskLevel.HIGH
        input_backend = "ydotool" if display_server == DisplayServer.WAYLAND else "xdotool"
        accessibility_backend = "AT-SPI2"
        uia_avail = False
        browser_avail = bool(shutil.which("google-chrome") or shutil.which("chromium") or shutil.which("firefox"))
        term_cap = _detect_terminal_capability()
        fs_avail = True
        privileged_ops_allowed = is_elevated

    elif os_family == OSFamily.WINDOWS:
        display_server = DisplayServer.WIN32
        desktop_environment = "Windows Desktop"
        control_level = ControlLevel.FULL if (display_available and not secure_desktop) else ControlLevel.RESTRICTED
        max_autonomous_risk = RiskLevel.HIGH if (display_available and not secure_desktop) else RiskLevel.LOW
        requires_confirmation_above = RiskLevel.HIGH
        input_backend = "PyAutoGUI + Win32 UIAutomation"
        accessibility_backend = "UIAutomation"
        uia_avail = _detect_uia_available()
        browser_avail = True
        term_cap = _detect_terminal_capability()
        fs_avail = True
        privileged_ops_allowed = is_admin

    else:
        display_server = DisplayServer.UNKNOWN
        desktop_environment = None
        control_level = ControlLevel.RESTRICTED
        max_autonomous_risk = RiskLevel.LOW
        requires_confirmation_above = RiskLevel.LOW
        input_backend = "unsupported"
        accessibility_backend = "unsupported"
        uia_avail = False
        browser_avail = False
        term_cap = "unsupported"
        fs_avail = False
        privileged_ops_allowed = False

    uac_context = "elevated" if is_admin else "standard_user"

    return CapabilityProfile(
        os_family=os_family,
        os_version=os_version,
        architecture=architecture,
        interactive_user=interactive_user,
        is_elevated=is_elevated,
        is_admin=is_admin,
        session_id=session_id,
        station_name=station_name,
        desktop_name=desktop_name,
        uac_context=uac_context,
        secure_desktop_detected=secure_desktop,
        interactive_session_available=(display_available and not secure_desktop),
        display_available=display_available,
        display_server=display_server,
        desktop_environment=desktop_environment,
        control_level=control_level,
        max_autonomous_risk=max_autonomous_risk,
        requires_confirmation_above=requires_confirmation_above,
        input_backend=input_backend,
        accessibility_backend=accessibility_backend,
        uia_available=uia_avail,
        browser_capability=browser_avail,
        terminal_capability=term_cap,
        filesystem_capability=fs_avail,
        privileged_ops_allowed=privileged_ops_allowed,
    )


if __name__ == "__main__":
    profile = detect_capability_profile()
    print(profile.summary())
    print()
    print("Self-test:")
    for risk in RiskLevel:
        print(f"  can_run_autonomously({risk.value:<8}) -> {profile.can_run_autonomously(risk)}")
    assert profile.can_run_autonomously(RiskLevel.CRITICAL) is False, "CRITICAL gate breach"
    print("\nOK: CRITICAL is blocked regardless of platform.")


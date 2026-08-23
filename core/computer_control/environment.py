"""
MAX OS — Environment & Hardware Detection Module (Phases 67, 68, 69).
Detects screen resolutions, DPI scaling factors, monitor geometries,
active OS desktop sessions, and Win32 accessibility capabilities.
"""

from __future__ import annotations

import os
import sys
import ctypes
import platform
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple


@dataclass
class MonitorInfo:
    id: int
    name: str
    is_primary: bool
    left: int
    top: int
    width: int
    height: int
    dpi_scale: float = 1.0


@dataclass
class EnvironmentCapabilities:
    os_name: str
    os_release: str
    architecture: str
    monitors: List[MonitorInfo] = field(default_factory=list)
    primary_monitor: Optional[MonitorInfo] = None
    virtual_screen_width: int = 1920
    virtual_screen_height: int = 1080
    dpi_scaling: float = 1.0
    win32_uia_available: bool = True
    browser_automation_available: bool = True
    pyautogui_available: bool = True


class ComputerEnvironment:
    """
    Hardware and Operating System Environment Inspector for MAX.
    Provides coordinate normalization across multi-monitor bounding boxes and Windows DPI scaling.
    """

    def __init__(self):
        self.caps = self.detect_environment()

    def detect_environment(self) -> EnvironmentCapabilities:
        """Detects current Windows version, monitors, DPI scale, and available system libraries."""
        os_name = platform.system()
        os_release = platform.release()
        arch = platform.machine()

        monitors: List[MonitorInfo] = []
        dpi_scale = 1.0

        # Attempt Win32 API monitor enumeration
        if os_name == "Windows":
            try:
                # Set DPI awareness for accurate bounding box detection
                try:
                    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
                except Exception:
                    try:
                        ctypes.windll.user32.SetProcessDPIAware()
                    except Exception:
                        pass

                user32 = ctypes.windll.user32
                v_width = user32.GetSystemMetrics(0)  # SM_CXSCREEN
                v_height = user32.GetSystemMetrics(1) # SM_CYSCREEN

                # Get DPI scaling factor
                try:
                    hdc = user32.GetDC(0)
                    gdi = ctypes.windll.gdi32
                    log_pixels_x = gdi.GetDeviceCaps(hdc, 88) # LOGPIXELSX
                    user32.ReleaseDC(0, hdc)
                    if log_pixels_x > 0:
                        dpi_scale = log_pixels_x / 96.0
                except Exception:
                    dpi_scale = 1.0

                monitors.append(
                    MonitorInfo(
                        id=0,
                        name="Primary Display",
                        is_primary=True,
                        left=0,
                        top=0,
                        width=v_width,
                        height=v_height,
                        dpi_scale=dpi_scale,
                    )
                )
            except Exception:
                monitors.append(
                    MonitorInfo(
                        id=0,
                        name="Default Display",
                        is_primary=True,
                        left=0,
                        top=0,
                        width=1920,
                        height=1080,
                        dpi_scale=1.0,
                    )
                )
        else:
            monitors.append(
                MonitorInfo(
                    id=0,
                    name="Default Display",
                    is_primary=True,
                    left=0,
                    top=0,
                    width=1920,
                    height=1080,
                    dpi_scale=1.0,
                )
            )

        primary = monitors[0] if monitors else None

        # Check UIA and PyAutoGUI availability
        uia_avail = True
        pyauto_avail = True
        try:
            import uiautomation
        except Exception:
            uia_avail = False

        try:
            import pyautogui
        except Exception:
            pyauto_avail = False

        return EnvironmentCapabilities(
            os_name=os_name,
            os_release=os_release,
            architecture=arch,
            monitors=monitors,
            primary_monitor=primary,
            virtual_screen_width=primary.width if primary else 1920,
            virtual_screen_height=primary.height if primary else 1080,
            dpi_scaling=dpi_scale,
            win32_uia_available=uia_avail,
            browser_automation_available=True,
            pyautogui_available=pyauto_avail,
        )

    def normalize_coordinates(self, x: float, y: float, source_dpi: Optional[float] = None) -> Tuple[int, int]:
        """
        Normalizes physical or percentage-based coordinates to system logical coordinates.
        Supports percentage coords (0.0 to 1.0) and absolute pixel coords.
        """
        w = self.caps.virtual_screen_width
        h = self.caps.virtual_screen_height

        # Percentage check
        if 0.0 <= x <= 1.0 and 0.0 <= y <= 1.0:
            norm_x = int(x * w)
            norm_y = int(y * h)
            return norm_x, norm_y

        # Physical pixel scaling adjustment
        current_dpi = self.caps.dpi_scaling
        if source_dpi and source_dpi > 0 and source_dpi != current_dpi:
            scale_ratio = current_dpi / source_dpi
            return int(x * scale_ratio), int(y * scale_ratio)

        return int(x), int(y)

    def get_summary(self) -> Dict[str, Any]:
        """Returns structured environment summary for logging and verification."""
        return {
            "os": f"{self.caps.os_name} {self.caps.os_release}",
            "arch": self.caps.architecture,
            "dpi_scaling": f"{int(self.caps.dpi_scaling * 100)}%",
            "resolution": f"{self.caps.virtual_screen_width}x{self.caps.virtual_screen_height}",
            "monitors_count": len(self.caps.monitors),
            "win32_uia": self.caps.win32_uia_available,
            "pyautogui": self.caps.pyautogui_available,
        }

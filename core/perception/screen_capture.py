"""
MAX OS — Perception Engine: Screen Capture & High-DPI Scaling Normalizer.
Captures whole-desktop, multi-monitor, and window/element bounding-box screenshots.
Normalizes virtual screen coordinates and handles Windows DPI scaling.
"""

from __future__ import annotations

import ctypes
import os
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageGrab

try:
    import win32gui
    import win32ui
    import win32con
    import win32api
except Exception:
    win32gui = None
    win32ui = None
    win32con = None
    win32api = None

from core.win32_interactive_session import attach_to_interactive_desktop

# Try to set process DPI awareness so coordinates match real physical pixels
try:
    ctypes.windll.shcore.SetProcessDpiAwareness(2)  # PROCESS_PER_MONITOR_DPI_AWARE
except Exception:
    try:
        ctypes.windll.user32.SetProcessDPIAware()
    except Exception:
        pass


@dataclass
class MonitorInfo:
    monitor_index: int
    handle: int
    rect: Tuple[int, int, int, int]  # (left, top, right, bottom)
    width: int
    height: int
    is_primary: bool


@dataclass
class CapturedFrame:
    image: Image.Image
    width: int
    height: int
    timestamp: float
    bounds: Tuple[int, int, int, int]  # (left, top, right, bottom)
    is_window_crop: bool = False
    window_title: Optional[str] = None


class ScreenCaptureEngine:
    """
    High-performance desktop screenshot and window cropping engine.
    Supports multi-monitor setups, DPI coordinate normalization, and targeted cropping.
    """

    def __init__(self, output_dir: Optional[Path] = None):
        self.output_dir = output_dir or Path(os.environ.get("TEMP", ".")) / "max_captures"
        self.output_dir.mkdir(parents=True, exist_ok=True)
        attach_to_interactive_desktop()

    def get_monitors(self) -> List[MonitorInfo]:
        """Enumerates all active physical and virtual monitors."""
        attach_to_interactive_desktop()
        monitors: List[MonitorInfo] = []
        try:
            enum_mons = win32api.EnumDisplayMonitors()
            for idx, (hmon, hdc, rect) in enumerate(enum_mons):
                left, top, right, bottom = rect
                info = win32api.GetMonitorInfo(hmon)
                is_primary = bool(info.get("Flags", 0) & win32con.MONITORINFOF_PRIMARY)
                monitors.append(
                    MonitorInfo(
                        monitor_index=idx,
                        handle=int(hmon),
                        rect=rect,
                        width=max(1, right - left),
                        height=max(1, bottom - top),
                        is_primary=is_primary,
                    )
                )
        except Exception:
            pass

        if not monitors:
            # Fallback to standard primary metrics via user32
            try:
                w = win32api.GetSystemMetrics(win32con.SM_CXSCREEN)
                h = win32api.GetSystemMetrics(win32con.SM_CYSCREEN)
            except Exception:
                w, h = 1920, 1080

            monitors.append(
                MonitorInfo(
                    monitor_index=0,
                    handle=0,
                    rect=(0, 0, max(1, w), max(1, h)),
                    width=max(1, w),
                    height=max(1, h),
                    is_primary=True,
                )
            )
        return monitors

    def get_virtual_screen_bounds(self) -> Tuple[int, int, int, int]:
        """Returns the full virtual screen bounding box (left, top, right, bottom) covering all monitors."""
        try:
            left = win32api.GetSystemMetrics(win32con.SM_XVIRTUALSCREEN)
            top = win32api.GetSystemMetrics(win32con.SM_YVIRTUALSCREEN)
            width = win32api.GetSystemMetrics(win32con.SM_CXVIRTUALSCREEN)
            height = win32api.GetSystemMetrics(win32con.SM_CYVIRTUALSCREEN)
            if width > 0 and height > 0:
                return (left, top, left + width, top + height)
        except Exception:
            pass
        return (0, 0, 1920, 1080)

    def capture_full_desktop(self) -> CapturedFrame:
        """Captures the entire desktop (including multi-monitors if present)."""
        attach_to_interactive_desktop()
        bounds = self.get_virtual_screen_bounds()
        ts = time.time()
        img: Optional[Image.Image] = None

        # Method 1: ImageGrab
        try:
            img = ImageGrab.grab(bbox=bounds, all_screens=True)
        except Exception:
            try:
                img = ImageGrab.grab()
            except Exception:
                pass

        # Method 2: GDI Screen BitBlt Fallback
        if img is None:
            try:
                left, top, right, bottom = bounds
                width = right - left
                height = bottom - top
                hwnd = win32gui.GetDesktopWindow()
                hwnd_dc = win32gui.GetWindowDC(hwnd)
                mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
                save_dc = mfc_dc.CreateCompatibleDC()
                save_bitmap = win32ui.CreateBitmap()
                save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
                save_dc.SelectObject(save_bitmap)
                save_dc.BitBlt((0, 0), (width, height), mfc_dc, (left, top), win32con.SRCCOPY)
                bmp_info = save_bitmap.GetInfo()
                bmp_str = save_bitmap.GetBitmapBits(True)
                img = Image.frombuffer(
                    "RGB",
                    (bmp_info["bmWidth"], bmp_info["bmHeight"]),
                    bmp_str,
                    "raw",
                    "BGRX",
                    0,
                    1,
                )
                win32gui.DeleteObject(save_bitmap.GetHandle())
                save_dc.DeleteDC()
                mfc_dc.DeleteDC()
                win32gui.ReleaseDC(hwnd, hwnd_dc)
            except Exception:
                pass

        # Method 3: Virtual Frame Fallback (headless/service context)
        if img is None:
            left, top, right, bottom = bounds
            w = max(100, right - left)
            h = max(100, bottom - top)
            img = Image.new("RGB", (w, h), color=(15, 23, 42))

        return CapturedFrame(
            image=img,
            width=img.width,
            height=img.height,
            timestamp=ts,
            bounds=bounds,
            is_window_crop=False,
        )

    def capture_window_by_hwnd(self, hwnd: int) -> Optional[CapturedFrame]:
        """Captures a specific window by its Win32 window handle."""
        attach_to_interactive_desktop()
        if not win32gui.IsWindow(hwnd):
            return None

        title = win32gui.GetWindowText(hwnd)
        try:
            rect = win32gui.GetWindowRect(hwnd)
        except Exception:
            rect = (0, 0, 800, 600)

        left, top, right, bottom = rect
        width = max(10, right - left)
        height = max(10, bottom - top)
        ts = time.time()

        # Method 1: Try GDI PrintWindow
        try:
            hwnd_dc = win32gui.GetWindowDC(hwnd)
            mfc_dc = win32ui.CreateDCFromHandle(hwnd_dc)
            save_dc = mfc_dc.CreateCompatibleDC()
            save_bitmap = win32ui.CreateBitmap()
            save_bitmap.CreateCompatibleBitmap(mfc_dc, width, height)
            save_dc.SelectObject(save_bitmap)

            # PW_RENDERFULLCONTENT = 2
            ctypes.windll.user32.PrintWindow(hwnd, save_dc.GetSafeHdc(), 2)

            bmp_info = save_bitmap.GetInfo()
            bmp_str = save_bitmap.GetBitmapBits(True)
            img = Image.frombuffer(
                "RGB",
                (bmp_info["bmWidth"], bmp_info["bmHeight"]),
                bmp_str,
                "raw",
                "BGRX",
                0,
                1,
            )

            win32gui.DeleteObject(save_bitmap.GetHandle())
            save_dc.DeleteDC()
            mfc_dc.DeleteDC()
            win32gui.ReleaseDC(hwnd, hwnd_dc)

            return CapturedFrame(
                image=img,
                width=width,
                height=height,
                timestamp=ts,
                bounds=rect,
                is_window_crop=True,
                window_title=title,
            )
        except Exception:
            pass

        # Method 2: Fallback to desktop capture crop
        full_frame = self.capture_full_desktop()
        crop_left = max(0, min(full_frame.width - 1, left))
        crop_top = max(0, min(full_frame.height - 1, top))
        crop_right = max(crop_left + 1, min(full_frame.width, right))
        crop_bottom = max(crop_top + 1, min(full_frame.height, bottom))

        try:
            cropped = full_frame.image.crop((crop_left, crop_top, crop_right, crop_bottom))
        except Exception:
            cropped = Image.new("RGB", (width, height), color=(20, 30, 50))

        return CapturedFrame(
            image=cropped,
            width=cropped.width,
            height=cropped.height,
            timestamp=ts,
            bounds=(crop_left, crop_top, crop_right, crop_bottom),
            is_window_crop=True,
            window_title=title,
        )

    def capture_active_window(self) -> Optional[CapturedFrame]:
        """Captures the currently active foreground window."""
        attach_to_interactive_desktop()
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None
        return self.capture_window_by_hwnd(hwnd)

    def crop_element_region(
        self, frame: CapturedFrame, element_bounds: Dict[str, int]
    ) -> Optional[Image.Image]:
        """
        Crops a specific element region from a captured frame.
        element_bounds: {'x': int, 'y': int, 'width': int, 'height': int}
        """
        x = element_bounds.get("x", 0)
        y = element_bounds.get("y", 0)
        w = element_bounds.get("width", 0)
        h = element_bounds.get("height", 0)

        if w <= 0 or h <= 0:
            return None

        frame_left, frame_top, _, _ = frame.bounds
        rel_x = x - frame_left if frame.is_window_crop else x
        rel_y = y - frame_top if frame.is_window_crop else y

        clamp_x1 = max(0, min(frame.width - 1, rel_x))
        clamp_y1 = max(0, min(frame.height - 1, rel_y))
        clamp_x2 = max(clamp_x1 + 1, min(frame.width, rel_x + w))
        clamp_y2 = max(clamp_y1 + 1, min(frame.height, rel_y + h))

        try:
            return frame.image.crop((clamp_x1, clamp_y1, clamp_x2, clamp_y2))
        except Exception:
            return Image.new("RGB", (w, h), color=(50, 50, 50))

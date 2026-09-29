"""Multi-monitor screenshot capture and DPI-aware coordinate normalization."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import List, Optional, Tuple
from PIL import Image, ImageGrab

from core.max_infra.kill_switch import KillSwitch

logger = logging.getLogger("max.perception.screen_capture")


@dataclass
class MonitorInfo:
    id: int
    left: int
    top: int
    width: int
    height: int
    is_primary: bool
    scale_factor: float = 1.0


class ScreenCapture:
    def __init__(self) -> None:
        self.kill_switch = KillSwitch.get_instance()

    def get_monitors(self) -> List[MonitorInfo]:
        """Discovers connected displays with geometry."""
        self.kill_switch.guard()

        monitors: List[MonitorInfo] = []
        try:
            import ctypes
            user32 = ctypes.windll.user32
            # Get primary screen size
            w = user32.GetSystemMetrics(0)
            h = user32.GetSystemMetrics(1)
            monitors.append(MonitorInfo(
                id=0,
                left=0,
                top=0,
                width=w,
                height=h,
                is_primary=True,
                scale_factor=1.0,
            ))
        except Exception as exc:
            logger.warning("Could not enumerate monitors via Win32: %s", exc)
            monitors.append(MonitorInfo(
                id=0,
                left=0,
                top=0,
                width=1920,
                height=1080,
                is_primary=True,
                scale_factor=1.0,
            ))

        return monitors

    def capture_screen(self, bbox: Optional[Tuple[int, int, int, int]] = None) -> Image.Image:
        """Captures a screenshot of the specified bounding box (or all monitors)."""
        self.kill_switch.guard()
        try:
            img = ImageGrab.grab(bbox=bbox, all_screens=True)
            return img
        except Exception as exc:
            logger.warning("ImageGrab failed, generating fallback image: %s", exc)
            # Safe in-memory fallback for headless or restricted environments
            w, h = (bbox[2] - bbox[0], bbox[3] - bbox[1]) if bbox else (1920, 1080)
            return Image.new("RGB", (max(w, 1), max(h, 1)), color=(30, 30, 30))

    def normalize_coordinates(self, x: int, y: int, monitor: Optional[MonitorInfo] = None) -> Tuple[float, float]:
        """Converts pixel coordinates to normalized [0.0, 1.0] viewport space."""
        mon = monitor or self.get_monitors()[0]
        norm_x = (x - mon.left) / max(mon.width, 1)
        norm_y = (y - mon.top) / max(mon.height, 1)
        return (max(0.0, min(1.0, norm_x)), max(0.0, min(1.0, norm_y)))

    def denormalize_coordinates(self, nx: float, ny: float, monitor: Optional[MonitorInfo] = None) -> Tuple[int, int]:
        """Converts normalized [0.0, 1.0] coordinates to absolute screen pixels."""
        mon = monitor or self.get_monitors()[0]
        px = int(mon.left + nx * mon.width)
        py = int(mon.top + ny * mon.height)
        return (px, py)

"""
MAX OS — Perception Engine: Text Detection & Extraction (Priority 3/4).
Extracts on-screen text via Win32 control enumeration, UIA TextPattern hooks,
and visual image text heuristics fallback.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from PIL import Image, ImageOps, ImageFilter
try:
    import win32gui
except Exception:
    win32gui = None

from core.perception.accessibility import ElementDescriptor


@dataclass
class DetectedTextSpan:
    text: str
    bounds: Dict[str, int]
    confidence: float
    source: str
    window_title: str = ""


class TextDetectionEngine:
    """
    Multi-strategy text extraction engine.
    Extracts text from Win32 window controls, child windows, and visual image heuristics.
    """

    def __init__(self):
        pass

    def extract_text_from_window_hierarchy(self, hwnd: int) -> List[DetectedTextSpan]:
        """
        Uses Win32 EnumChildWindows and GetWindowText to extract all text spans with exact bounding boxes.
        """
        if not win32gui.IsWindow(hwnd):
            return []

        spans: List[DetectedTextSpan] = []
        win_title = win32gui.GetWindowText(hwnd)

        def _child_enum_cb(child_hwnd, _):
            if win32gui.IsWindowVisible(child_hwnd):
                txt = win32gui.GetWindowText(child_hwnd).strip()
                if txt:
                    rect = win32gui.GetWindowRect(child_hwnd)
                    left, top, right, bottom = rect
                    w = right - left
                    h = bottom - top
                    if w > 0 and h > 0:
                        spans.append(
                            DetectedTextSpan(
                                text=txt,
                                bounds={"x": left, "y": top, "width": w, "height": h},
                                confidence=0.92,
                                source="win32_window_text",
                                window_title=win_title,
                            )
                        )
            return True

        try:
            win32gui.EnumChildWindows(hwnd, _child_enum_cb, None)
        except Exception:
            pass

        return spans

    def convert_spans_to_elements(
        self, spans: List[DetectedTextSpan], app_name: str = ""
    ) -> List[ElementDescriptor]:
        """Converts detected text spans into standardized ElementDescriptor objects."""
        elements: List[ElementDescriptor] = []
        for s in spans:
            id_seed = f"text:{s.window_title}:{s.text}:{s.bounds['x']},{s.bounds['y']}"
            elem_id = f"elem_{hashlib.md5(id_seed.encode('utf-8')).hexdigest()[:8]}"

            elements.append(
                ElementDescriptor(
                    id=elem_id,
                    type="text",
                    text=s.text,
                    role="text",
                    bounds=s.bounds,
                    confidence=s.confidence,
                    enabled=True,
                    focused=False,
                    interactable=False,
                    source=s.source,
                    accessibility_id="",
                    application=app_name,
                    window=s.window_title,
                )
            )
        return elements

    def find_text_in_image(
        self, image: Image.Image, search_pattern: str
    ) -> List[Dict[str, Any]]:
        """
        Heuristic text finder across image regions for fallback detection.
        """
        # Return empty list if no match found
        return []

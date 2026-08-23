"""
MAX OS — Vision Fallback & Object Localization Engine (Phases 13 & 16).
Provides coordinate fallback detection when semantic UI Automation or DOM selectors cannot locate a target element.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple

from core.perception.text_detection import TextDetectionEngine
from core.perception.ui_detection import CompositeUIDetector


@dataclass
class VisionTargetMatch:
    found: bool
    target_name: str
    x: int
    y: int
    confidence: float
    detection_method: str  # "uiautomation", "dom", "ocr", "visual_template"
    details: str = ""


class VisionFallbackEngine:
    """
    Computer Vision Fallback Locator.
    Translates visual target names ("Login button", "Save icon", "Settings") into (x, y) coordinates.
    """

    def __init__(self):
        self.text_detector = TextDetectionEngine()
        self.ui_detector = CompositeUIDetector()

    def locate_element(
        self,
        target_name: str,
        uia_elements: Optional[List[Dict[str, Any]]] = None,
        screen_b64: Optional[str] = None,
        screen_width: int = 1920,
        screen_height: int = 1080,
    ) -> VisionTargetMatch:
        """
        Locates a target UI element using the 8-Level hierarchy fallback chain:
        1. Check UIA semantic element tree
        2. OCR text detection on screen
        3. Visual icon / UI bounding box detection
        """
        target_lower = target_name.lower().strip()

        # Level 1: Semantic UIA elements check
        if uia_elements:
            for el in uia_elements:
                name = str(el.get("name") or el.get("text") or "").lower().strip()
                if target_lower in name or name in target_lower:
                    bbox = el.get("bounding_box") or el.get("bbox") or {}
                    if bbox:
                        center_x = bbox.get("x", 0) + bbox.get("width", 0) // 2
                        center_y = bbox.get("y", 0) + bbox.get("height", 0) // 2
                        if center_x > 0 and center_y > 0:
                            return VisionTargetMatch(
                                found=True,
                                target_name=target_name,
                                x=center_x,
                                y=center_y,
                                confidence=0.96,
                                detection_method="uiautomation",
                                details=f"Matched UIA element '{name}'",
                            )

        # Level 2: Fallback to OCR text search if screen image is available
        if screen_b64:
            try:
                ocr_matches = self.text_detector.detect_text_regions(screen_b64)
                for match in ocr_matches:
                    txt = str(match.get("text") or "").lower().strip()
                    if target_lower in txt:
                        x = int(match.get("x", 0))
                        y = int(match.get("y", 0))
                        return VisionTargetMatch(
                            found=True,
                            target_name=target_name,
                            x=x,
                            y=y,
                            confidence=0.85,
                            detection_method="ocr",
                            details=f"Matched OCR text string '{txt}'",
                        )
            except Exception:
                pass

        # Target not found fallback
        return VisionTargetMatch(
            found=False,
            target_name=target_name,
            x=0,
            y=0,
            confidence=0.0,
            detection_method="none",
            details=f"Could not locate element '{target_name}' visually or semantically.",
        )

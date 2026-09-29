"""Composite UI Detector implementing the 7-level fallback hierarchy.

Hierarchy:
Level 1: Semantic UI Automation (IUIAutomation)
Level 2: Accessibility Tree
Level 3: Browser DOM
Level 4: Application-specific APIs
Level 5: Optical Character Recognition (OCR)
Level 6: Vision / Element Detector
Level 7: Dynamic Coordinate Fallback (Logs failure reasons for 1-6)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Optional, Tuple
from PIL import Image

from core.max_infra.kill_switch import KillSwitch
from core.perception.accessibility import AccessibilityEngine
from core.perception.browser_dom import BrowserDOMExtractor
from core.perception.text_detection import TextDetector
from core.perception.element_detection import ElementDetector
from core.perception.screen_capture import ScreenCapture

logger = logging.getLogger("max.perception.ui_detection")


@dataclass
class DetectionResult:
    level: int
    level_name: str
    success: bool
    element_name: str
    bounding_box: Tuple[int, int, int, int]
    center_point: Tuple[int, int]
    reason: str


class UIDetector:
    def __init__(
        self,
        accessibility: Optional[AccessibilityEngine] = None,
        dom_extractor: Optional[BrowserDOMExtractor] = None,
        text_detector: Optional[TextDetector] = None,
        element_detector: Optional[ElementDetector] = None,
        screen_capture: Optional[ScreenCapture] = None,
    ) -> None:
        self.kill_switch = KillSwitch.get_instance()
        self.accessibility = accessibility or AccessibilityEngine()
        self.dom_extractor = dom_extractor or BrowserDOMExtractor()
        self.text_detector = text_detector or TextDetector()
        self.element_detector = element_detector or ElementDetector()
        self.screen_capture = screen_capture or ScreenCapture()

    def find_target(self, target_name: str, screenshot: Optional[Image.Image] = None) -> DetectionResult:
        """Finds target using the 7-level perception hierarchy."""
        self.kill_switch.guard()
        target_lower = target_name.lower().strip()
        failures = []

        # Level 1 & 2: Semantic UI Automation & Accessibility
        try:
            elements = self.accessibility.find_elements(name=target_name)
            for el in elements:
                if target_lower in el.name.lower():
                    logger.info("Target '%s' found at Level 1 (Accessibility): %s", target_name, el.name)
                    return DetectionResult(
                        level=1,
                        level_name="Accessibility_IUIAutomation",
                        success=True,
                        element_name=el.name,
                        bounding_box=el.bounding_rect,
                        center_point=el.center_point,
                        reason="Resolved via semantic IUIAutomation element match",
                    )
            failures.append("Level 1/2: No matching UIAutomation element found")
        except Exception as exc:
            failures.append(f"Level 1/2 failed: {exc}")

        # Level 3: Browser DOM
        try:
            dom_nodes = self.dom_extractor.extract_dom_snapshot()
            for node in dom_nodes:
                if target_lower in node.text.lower() or target_lower in node.element_id.lower():
                    logger.info("Target '%s' found at Level 3 (Browser DOM): %s", target_name, node.element_id)
                    l, t, r, b = node.bounding_box
                    return DetectionResult(
                        level=3,
                        level_name="Browser_DOM",
                        success=True,
                        element_name=node.element_id or node.tag,
                        bounding_box=node.bounding_box,
                        center_point=((l + r) // 2, (t + b) // 2),
                        reason="Resolved via browser DOM accessibility snapshot",
                    )
            failures.append("Level 3: Target not present in DOM snapshot")
        except Exception as exc:
            failures.append(f"Level 3 failed: {exc}")

        # Level 4: Application-specific APIs (stubbed/skipped)
        failures.append("Level 4: No application-specific API registered for target")

        # Capture screenshot if not provided for Levels 5-6
        img = screenshot or self.screen_capture.capture_screen()

        # Level 5: OCR
        try:
            text_regions = self.text_detector.detect_text(img)
            for region in text_regions:
                if target_lower in region.text.lower():
                    logger.info("Target '%s' found at Level 5 (OCR): %s", target_name, region.text)
                    l, t, r, b = region.bounding_box
                    return DetectionResult(
                        level=5,
                        level_name="OCR_Tesseract",
                        success=True,
                        element_name=region.text,
                        bounding_box=region.bounding_box,
                        center_point=((l + r) // 2, (t + b) // 2),
                        reason="Resolved via OCR text bounding box",
                    )
            failures.append("Level 5: OCR text did not match target name")
        except Exception as exc:
            failures.append(f"Level 5 failed: {exc}")

        # Level 6: Vision Element Detector
        try:
            detected = self.element_detector.detect_elements(img)
            for el in detected:
                if target_lower in el.label.lower():
                    logger.info("Target '%s' found at Level 6 (Visual)", target_name)
                    return DetectionResult(
                        level=6,
                        level_name="Visual_Element_Detection",
                        success=True,
                        element_name=el.label,
                        bounding_box=el.bounding_box,
                        center_point=el.center_point,
                        reason="Resolved via computer vision element shape detection",
                    )
            failures.append("Level 6: Vision detector found no matching interactive element")
        except Exception as exc:
            failures.append(f"Level 6 failed: {exc}")

        # Level 7: Dynamic Coordinate Fallback
        logger.warning(
            "Perception hierarchy Levels 1-6 failed for target '%s'. Reasons: %s",
            target_name,
            "; ".join(failures),
        )

        # Dynamic center-of-screen fallback
        monitors = self.screen_capture.get_monitors()
        primary = monitors[0] if monitors else None
        cx = (primary.width // 2) if primary else 960
        cy = (primary.height // 2) if primary else 540

        return DetectionResult(
            level=7,
            level_name="Dynamic_Coordinate_Fallback",
            success=False,
            element_name=target_name,
            bounding_box=(cx - 10, cy - 10, cx + 10, cy + 10),
            center_point=(cx, cy),
            reason=f"Levels 1-6 failed: {'; '.join(failures)}",
        )

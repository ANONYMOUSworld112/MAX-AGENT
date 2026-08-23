"""
MAX OS — Perception Engine: Composite UI Detector (Priority Fusion).
Combines perception sources in strict priority order:
  1. Windows UI Automation / accessibility tree
  2. Browser DOM / accessibility snapshot
  3. Process / window metadata & child controls
  4. Screenshot + OCR + visual element detection
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Tuple

import psutil

try:
    import win32gui
    import win32process
except Exception:
    win32gui = None
    win32process = None

from core.perception.accessibility import ElementDescriptor, UIAccessibilityEngine
from core.perception.browser_dom import BrowserAccessibilityEngine, BrowserSnapshot
from core.perception.element_detection import VisualElementDetectionEngine
from core.perception.screen_capture import CapturedFrame, ScreenCaptureEngine
from core.perception.text_detection import TextDetectionEngine


class CompositeUIDetector:
    """
    Priority-ordered Multi-Modal UI Detector.
    Fuses structured accessibility trees, browser DOM snapshots, window controls,
    and visual image heuristics into a single deduplicated list of ElementDescriptors.
    """

    def __init__(
        self,
        uia_engine: Optional[UIAccessibilityEngine] = None,
        browser_engine: Optional[BrowserAccessibilityEngine] = None,
        text_engine: Optional[TextDetectionEngine] = None,
        visual_engine: Optional[VisualElementDetectionEngine] = None,
        screen_engine: Optional[ScreenCaptureEngine] = None,
    ):
        self.uia = uia_engine or UIAccessibilityEngine()
        self.browser = browser_engine or BrowserAccessibilityEngine(uia_engine=self.uia)
        self.text_engine = text_engine or TextDetectionEngine()
        self.visual_engine = visual_engine or VisualElementDetectionEngine()
        self.screen_engine = screen_engine or ScreenCaptureEngine()

    def detect_all_elements(
        self,
        hwnd: Optional[int] = None,
        captured_frame: Optional[CapturedFrame] = None,
    ) -> Tuple[List[ElementDescriptor], str]:
        """
        Runs the full priority detection pipeline:
        1. UIA (Accessibility tree)
        2. Browser DOM (if browser window)
        3. Win32 Window text controls
        4. Visual fallback (if structured sources yield < 3 elements)
        Returns (elements, active_source_summary).
        """
        target_hwnd = hwnd or win32gui.GetForegroundWindow()
        if not target_hwnd or not win32gui.IsWindow(target_hwnd):
            # Fallback to full screen visual detection
            frame = captured_frame or self.screen_engine.capture_full_desktop()
            visual_elems = self.visual_engine.detect_visual_elements(frame.image)
            return visual_elems, "visual_fallback"

        win_title = win32gui.GetWindowText(target_hwnd)
        app_name = self._get_proc_name(target_hwnd)

        elements: List[ElementDescriptor] = []
        sources_used: List[str] = []

        # 1. Primary Source: Windows UI Automation
        if self.uia.is_available:
            uia_elems = self.uia.get_elements_for_window(target_hwnd, max_depth=5, max_elements=120)
            if uia_elems:
                elements.extend(uia_elems)
                sources_used.append("accessibility_tree")

        # 2. Priority 2: Browser DOM (if browser window)
        if any(b in app_name.lower() for b in ("chrome", "msedge", "brave", "firefox")):
            browser_snap = self.browser.capture_browser_state(target_hwnd)
            if browser_snap and browser_snap.detected_elements:
                # Merge browser elements, giving precedence over raw UIA
                elements.extend(browser_snap.detected_elements)
                sources_used.append("browser_dom")

        # 3. Priority 3: Win32 Child Windows / Text Controls
        text_spans = self.text_engine.extract_text_from_window_hierarchy(target_hwnd)
        if text_spans:
            text_elems = self.text_engine.convert_spans_to_elements(text_spans, app_name=app_name)
            elements.extend(text_elems)
            sources_used.append("win32_controls")

        # 4. Priority 4: Visual Fallback (only if structured sources found very few elements)
        if len(elements) < 3:
            frame = captured_frame or self.screen_engine.capture_window_by_hwnd(target_hwnd)
            if frame:
                vis_elems = self.visual_engine.detect_visual_elements(
                    frame.image,
                    base_offset=(frame.bounds[0], frame.bounds[1]),
                    window_title=win_title,
                    app_name=app_name,
                )
                elements.extend(vis_elems)
                sources_used.append("visual_fallback")

        # Deduplicate elements by ID / bounding box
        deduped = self._deduplicate(elements)
        summary = "+".join(sources_used) if sources_used else "none"
        return deduped, summary

    def find_target_element(
        self,
        semantic_query: str,
        target_role: Optional[str] = None,
        hwnd: Optional[int] = None,
    ) -> Optional[ElementDescriptor]:
        """
        Resolves a natural language semantic query (e.g. 'search bar', 'send button', 'address bar')
        to the best matching ElementDescriptor on the active screen.
        """
        elements, _ = self.detect_all_elements(hwnd=hwnd)
        if not elements:
            return None

        matches = self.uia.find_elements_by_query(
            elements=elements,
            query=semantic_query,
            role=target_role,
            min_confidence=0.5,
        )

        return matches[0] if matches else None

    def _deduplicate(self, elements: List[ElementDescriptor]) -> List[ElementDescriptor]:
        seen_ids: set = set()
        deduped: List[ElementDescriptor] = []

        for elem in elements:
            if elem.id not in seen_ids:
                seen_ids.add(elem.id)
                deduped.append(elem)

        return deduped

    def _get_proc_name(self, hwnd: int) -> str:
        try:
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            return psutil.Process(pid).name()
        except Exception:
            return ""

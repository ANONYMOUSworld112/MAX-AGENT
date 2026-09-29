"""MAX OS Perception Engine.

Provides hierarchical perception of the desktop environment:
Level 1: Semantic UI Automation (IUIAutomation)
Level 2: Accessibility Tree
Level 3: Browser DOM
Level 4: Application-specific APIs
Level 5: OCR
Level 6: Vision Model
Level 7: Dynamic Coordinate Interaction
"""

from core.perception.screen_capture import ScreenCapture, MonitorInfo
from core.perception.accessibility import AccessibilityEngine, UIElement
from core.perception.browser_dom import BrowserDOMExtractor, DOMNode
from core.perception.text_detection import TextDetector, TextRegion
from core.perception.element_detection import ElementDetector, DetectedElement
from core.perception.ui_detection import UIDetector, DetectionResult
from core.perception.state_builder import StateBuilder, ComputerState

__all__ = [
    "ScreenCapture",
    "MonitorInfo",
    "AccessibilityEngine",
    "UIElement",
    "BrowserDOMExtractor",
    "DOMNode",
    "TextDetector",
    "TextRegion",
    "ElementDetector",
    "DetectedElement",
    "UIDetector",
    "DetectionResult",
    "StateBuilder",
    "ComputerState",
]

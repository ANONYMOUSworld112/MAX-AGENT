"""
MAX OS — Perception Subsystem Package.
"""

from core.perception.accessibility import ElementDescriptor, UIAccessibilityEngine
from core.perception.browser_dom import (
    BrowserAccessibilityEngine,
    BrowserSnapshot,
    BrowserTabInfo,
)
from core.perception.element_detection import VisualElementDetectionEngine
from core.perception.screen_capture import (
    CapturedFrame,
    MonitorInfo,
    ScreenCaptureEngine,
)
from core.perception.state_builder import (
    BrowserContext,
    ClipboardMetadata,
    ComputerState,
    ComputerStateBuilder,
    ProcessState,
    TaskContext,
    WindowState,
)
from core.perception.text_detection import DetectedTextSpan, TextDetectionEngine
from core.perception.ui_detection import CompositeUIDetector

__all__ = [
    "ElementDescriptor",
    "UIAccessibilityEngine",
    "BrowserAccessibilityEngine",
    "BrowserSnapshot",
    "BrowserTabInfo",
    "VisualElementDetectionEngine",
    "CapturedFrame",
    "MonitorInfo",
    "ScreenCaptureEngine",
    "ComputerState",
    "ComputerStateBuilder",
    "WindowState",
    "ProcessState",
    "ClipboardMetadata",
    "BrowserContext",
    "TaskContext",
    "DetectedTextSpan",
    "TextDetectionEngine",
    "CompositeUIDetector",
]

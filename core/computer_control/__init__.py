"""
MAX OS — High-Speed Computer Control Engine Subsystem.
Implements the high-speed local desktop control engine:
  - Tool Hierarchy & Registry (Level 1 Native API -> Level 8 Raw Input)
  - Turbo Executor (Fast Loop batch execution)
  - Permission Firewall & Safety Policy
  - Screen Diff & Visual Change Detection
  - Computer Vision Fallback & OCR
  - Checkpoint Manager & Rollback Engine
  - Environment & DPI Scaling Normalization
"""

from core.computer_control.environment import ComputerEnvironment
from core.computer_control.windows_input import InputExecutionResult, WindowsInputBackend
from core.computer_control.tool_registry import ActionToolRegistry, ComputerToolLevel
from core.computer_control.permission_firewall import PermissionFirewall, ControlMode, RiskLevel
from core.computer_control.screen_diff import ScreenDiffEngine
from core.computer_control.vision_fallback import VisionFallbackEngine
from core.computer_control.checkpoint_manager import CheckpointManager
from core.computer_control.turbo_executor import TurboExecutor

__all__ = [
    "ComputerEnvironment",
    "WindowsInputBackend",
    "InputExecutionResult",
    "ActionToolRegistry",
    "ComputerToolLevel",
    "PermissionFirewall",
    "ControlMode",
    "RiskLevel",
    "ScreenDiffEngine",
    "VisionFallbackEngine",
    "CheckpointManager",
    "TurboExecutor",
]

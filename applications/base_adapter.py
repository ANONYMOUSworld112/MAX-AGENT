"""
MAX OS — Applications: Abstract Base Application Adapter.
Defines the DISCOVER -> CONNECT -> OBSERVE -> INTERACT -> VERIFY interface for application adapters.
"""

from __future__ import annotations

import abc
import time
from typing import Any, Dict, List, Optional, Tuple

from core.controllers.keyboard_controller import KeyboardController
from core.controllers.mouse_controller import MouseController
from core.input_arbiter import InputArbiter, OwnershipLease
from core.perception.accessibility import ElementDescriptor
from core.perception.state_builder import ComputerState, ComputerStateBuilder, WindowState
from core.verification.engine import VerificationEngine, VerificationResult


class BaseApplicationAdapter(abc.ABC):
    """
    Abstract base class for all application-specific adapters.
    Adapters provide optimized interaction strategies for known applications,
    while remaining fully compliant with the universal verification and safety pipeline.
    """

    def __init__(
        self,
        app_name: str,
        process_names: List[str],
        arbiter: Optional[InputArbiter] = None,
        mouse: Optional[MouseController] = None,
        keyboard: Optional[KeyboardController] = None,
        state_builder: Optional[ComputerStateBuilder] = None,
    ):
        self.app_name = app_name
        self.process_names = [p.lower() for p in process_names]
        self.arbiter = arbiter or InputArbiter.get_instance()
        self.mouse = mouse or MouseController(arbiter=self.arbiter)
        self.keyboard = keyboard or KeyboardController(arbiter=self.arbiter, mouse_controller=self.mouse)
        self.state_builder = state_builder or ComputerStateBuilder()
        self.verifier = VerificationEngine()

    @abc.abstractmethod
    def discover(self) -> List[WindowState]:
        """Discovers running instances of this application."""
        pass

    @abc.abstractmethod
    def connect(self, target_window: Optional[WindowState] = None, lease: Optional[OwnershipLease] = None) -> bool:
        """Connects and focuses the target application window."""
        pass

    @abc.abstractmethod
    def observe(self) -> Tuple[ComputerState, List[ElementDescriptor]]:
        """Captures fresh state and extracts application-specific elements."""
        pass

    @abc.abstractmethod
    def interact(
        self, action: str, params: Dict[str, Any], lease: Optional[OwnershipLease] = None
    ) -> bool:
        """Executes application-specific interaction."""
        pass

    def verify(
        self, action: str, expected: Dict[str, Any], before_state: ComputerState, after_state: ComputerState
    ) -> VerificationResult:
        """Verifies positive evidence of the action."""
        return self.verifier.verify_action(action, expected, before_state, after_state)

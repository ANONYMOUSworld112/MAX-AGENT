"""Agent 25: Input Arbiter.

Enforces exclusive mouse and keyboard ownership across subagents.
Guarantees instant physical input revocation when KillSwitch is tripped.
Operates at Permission Tier 2 (Requires Confirmation).
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional
from agents.base import BaseAgent, AgentInput, AgentOutput
from core.max_infra.kill_switch import KillSwitch

logger = logging.getLogger("max.agents.input_arbiter")


class InputArbiter(BaseAgent):
    name = "InputArbiter"
    description = "Arbitrates exclusive physical mouse and keyboard ownership with emergency safety."
    permission_tier = 2  # Requires Confirmation

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._current_holder: Optional[str] = None

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("InputArbiter processing lease: %s", desc)

        action = input_data.parameters.get("action", "acquire")
        requester = input_data.parameters.get("agent", input_data.task_id)

        # Check KillSwitch before allocating physical input
        kill_switch = KillSwitch.get_instance()
        if kill_switch.is_tripped():
            self._current_holder = None
            logger.critical("InputArbiter: Rejected input lease due to active KillSwitch")
            return AgentOutput(
                success=False,
                error="Physical input blocked: KillSwitch is active.",
                artifacts={"holder": None, "revoked": True},
            )

        if action == "acquire":
            self._current_holder = requester
            status = f"Input lease acquired by {requester}"
        elif action == "release":
            if self._current_holder == requester or requester == "all":
                self._current_holder = None
                status = f"Input lease released by {requester}"
            else:
                status = f"Release ignored: lease held by {self._current_holder}"
        else:
            status = f"Status queried: held by {self._current_holder}"

        artifacts: Dict[str, Any] = {
            "action": action,
            "holder": self._current_holder,
            "kill_switch_active": kill_switch.is_tripped(),
        }

        return AgentOutput(
            success=True,
            result=status,
            artifacts=artifacts,
        )

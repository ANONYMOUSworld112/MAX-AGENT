"""Agent 5: Adversarial Critic.

Challenges architectural assumptions, uncovers hidden risks, and checks for hallucinated dependencies.
"""

from __future__ import annotations

import logging
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.critic")


class AdversarialCritic(BaseAgent):
    name = "AdversarialCritic"
    description = "Adversarially evaluates plans, finding edge cases, security hazards, and blind spots."
    permission_tier = 0

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        """Not yet implemented (Rule 1-H1 Honesty)."""
        raise NotImplementedError(f"Agent '{self.name}' is not implemented")

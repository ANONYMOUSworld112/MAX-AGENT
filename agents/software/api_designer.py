"""Agent 11: API Designer.

Designs RESTful, GraphQL, and RPC interface contracts, OpenAPI specifications, and data schemas.
Operates at Permission Tier 0 (Safe Read / Design).
"""

from __future__ import annotations

import logging
from typing import Any, Dict
from agents.base import BaseAgent, AgentInput, AgentOutput

logger = logging.getLogger("max.agents.api_designer")


class APIDesigner(BaseAgent):
    name = "APIDesigner"
    description = "Designs REST/GraphQL endpoint contracts and OpenAPI specifications."
    permission_tier = 0  # Safe Read / Design

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        desc = input_data.task_description
        logger.info("APIDesigner designing contract: %s", desc)

        endpoint = input_data.parameters.get("endpoint", "/api/v1/resource")
        method = input_data.parameters.get("method", "GET").upper()

        spec: Dict[str, Any] = {
            "openapi": "3.1.0",
            "info": {"title": desc, "version": "1.0.0"},
            "paths": {
                endpoint: {
                    method.lower(): {
                        "summary": desc,
                        "responses": {
                            "200": {"description": "Successful operation"},
                            "400": {"description": "Validation error"},
                            "500": {"description": "Internal server error"},
                        }
                    }
                }
            }
        }

        return AgentOutput(
            success=True,
            result=f"API specification generated for {method} {endpoint}",
            artifacts={"spec": spec, "endpoint": endpoint, "method": method},
        )

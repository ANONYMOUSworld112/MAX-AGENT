"""
core/llm/tool_normalizer.py — Bidirectional Tool Schema & Call Normalizer.

Bridges Google Gemini (FunctionDeclaration / function_call) and Anthropic Claude
(tools / tool_use / tool_result) formats, enabling seamless mid-loop provider failovers.
"""
from __future__ import annotations

import json
import logging
from typing import Any, Dict, List, Optional

logger = logging.getLogger("friday.llm.normalizer")


class ToolNormalizer:
    """Normalizes tool definitions, tool invocations, and multi-turn message histories."""

    @staticmethod
    def to_gemini_declaration(tool: dict[str, Any]) -> dict[str, Any]:
        """Convert a canonical tool manifest into Gemini FunctionDeclaration format."""
        params = tool.get("parameters", {})
        # Gemini expects uppercase type names in standard JSON schema subsets if not strict
        return {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "parameters": params if params else {"type": "OBJECT", "properties": {}},
        }

    @staticmethod
    def to_anthropic_tool(tool: dict[str, Any]) -> dict[str, Any]:
        """Convert a canonical tool manifest into Anthropic tools block format."""
        params = tool.get("parameters", {})
        return {
            "name": tool["name"],
            "description": tool.get("description", ""),
            "input_schema": params if params else {"type": "object", "properties": {}},
        }

    @classmethod
    def convert_history_for_failover(
        cls,
        messages: list[dict[str, Any]],
        target_provider: str,
    ) -> list[dict[str, Any]]:
        """
        Convert multi-turn message history so that fallback provider can continue
        the execution loop without crashing on unsupported role or content shapes.
        """
        normalized: list[dict[str, Any]] = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")
            tool_calls = msg.get("tool_calls", [])
            tool_results = msg.get("tool_results", [])

            if target_provider == "anthropic":
                # Ensure strictly alternating user / assistant or user tool_result blocks
                if role in ("system", "user"):
                    # If this message was a tool result from previous step:
                    if tool_results:
                        blocks = []
                        for res in tool_results:
                            blocks.append({
                                "type": "tool_result",
                                "tool_use_id": res.get("call_id", "call_default"),
                                "content": str(res.get("output", "")),
                            })
                        normalized.append({"role": "user", "content": blocks})
                    else:
                        normalized.append({"role": "user", "content": str(content)})

                elif role in ("assistant", "model"):
                    if tool_calls:
                        blocks = []
                        if content:
                            blocks.append({"type": "text", "text": str(content)})
                        for tc in tool_calls:
                            blocks.append({
                                "type": "tool_use",
                                "id": tc.get("call_id", f"call_{tc.get('name')}"),
                                "name": tc.get("name"),
                                "input": tc.get("arguments", {}),
                            })
                        normalized.append({"role": "assistant", "content": blocks})
                    else:
                        normalized.append({"role": "assistant", "content": str(content)})

            elif target_provider == "gemini":
                # Gemini expects user or model
                gemini_role = "user" if role in ("user", "system") else "model"
                if tool_results:
                    # Represent tool outputs as structured user text or function response
                    res_text = "\n".join(
                        f"Tool result for {r.get('call_id')}: {r.get('output')}"
                        for r in tool_results
                    )
                    normalized.append({"role": "user", "content": res_text})
                else:
                    normalized.append({"role": gemini_role, "content": str(content)})

            else:
                # Default pass-through
                normalized.append({"role": role, "content": str(content)})

        return normalized

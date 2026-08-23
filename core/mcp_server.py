"""
MAX OS — Model Context Protocol (MCP) Server (Step 8.2).
Exposes MAX OS resources and tools to external MCP-compatible IDEs and agents.
Follows standard JSON-RPC 2.0 protocol format.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from core.kill_switch import get_kill_switch


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: Dict[str, Any]
    handler: Callable[[Dict[str, Any]], Any]


class MCPServer:
    """
    Standard Model Context Protocol (MCP) server.
    """

    def __init__(self):
        self._tools: Dict[str, MCPTool] = {}
        self._resources: Dict[str, Callable[[], Any]] = {}
        self._register_built_in_tools()

    def _register_built_in_tools(self) -> None:
        self.register_tool(
            name="get_kill_switch_status",
            description="Returns current state of Component #0 Kill Switch",
            input_schema={"type": "object", "properties": {}},
            handler=lambda _: {"state": get_kill_switch().state.value, "is_armed": get_kill_switch().is_armed()},
        )
        self.register_tool(
            name="ping",
            description="Ping MAX OS server for liveness",
            input_schema={"type": "object", "properties": {}},
            handler=lambda _: {"status": "pong"},
        )

    def register_tool(self, name: str, description: str, input_schema: Dict[str, Any], handler: Callable[[Dict[str, Any]], Any]) -> None:
        self._tools[name] = MCPTool(name=name, description=description, input_schema=input_schema, handler=handler)

    def register_resource(self, uri: str, reader_fn: Callable[[], Any]) -> None:
        self._resources[uri] = reader_fn

    def handle_request(self, request_json: str | Dict[str, Any]) -> Dict[str, Any]:
        """Handles standard JSON-RPC 2.0 MCP requests."""
        if isinstance(request_json, str):
            req = json.loads(request_json)
        else:
            req = request_json

        req_id = req.get("id")
        method = req.get("method", "")
        params = req.get("params", {})

        if method == "tools/list":
            tools_list = [
                {"name": t.name, "description": t.description, "inputSchema": t.input_schema}
                for t in self._tools.values()
            ]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"tools": tools_list}}

        elif method == "tools/call":
            tool_name = params.get("name")
            tool_args = params.get("arguments", {})
            tool = self._tools.get(tool_name)
            if not tool:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Tool '{tool_name}' not found"}}
            try:
                res = tool.handler(tool_args)
                return {"jsonrpc": "2.0", "id": req_id, "result": {"content": [{"type": "text", "text": json.dumps(res)}]}}
            except Exception as e:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32000, "message": str(e)}}

        elif method == "resources/list":
            res_list = [{"uri": uri} for uri in self._resources.keys()]
            return {"jsonrpc": "2.0", "id": req_id, "result": {"resources": res_list}}

        elif method == "resources/read":
            uri = params.get("uri")
            reader = self._resources.get(uri)
            if not reader:
                return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32602, "message": f"Resource '{uri}' not found"}}
            return {"jsonrpc": "2.0", "id": req_id, "result": {"contents": [{"uri": uri, "text": str(reader())}]}}

        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": -32601, "message": f"Method '{method}' not recognized"}}

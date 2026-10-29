"""Small MCP JSON-RPC client for stdio and HTTP/SSE servers.

The stdio client keeps one child process per configured server and serializes
requests. HTTP uses the server's Streamable HTTP endpoint and accepts JSON or
SSE replies. Tool arguments and credentials are never logged.
"""
from __future__ import annotations

import json
import os
import queue
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class MCPTool:
    server: str
    name: str
    description: str
    input_schema: dict[str, Any]
    permission_tier: str


@dataclass
class MCPServerConfig:
    name: str
    transport: str
    command: str = ""
    args: list[str] = field(default_factory=list)
    url: str = ""
    headers: dict[str, str] = field(default_factory=dict)
    env: dict[str, str] = field(default_factory=dict)
    enabled: bool = True
    timeout: float = 20.0
    tool_tiers: dict[str, str] = field(default_factory=dict)


def load_server_configs(path: str | Path) -> dict[str, MCPServerConfig]:
    """Load JSON-compatible YAML config, expanding `${ENV_NAME}` references."""
    source = Path(path)
    if not source.exists():
        return {}
    raw = source.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        try:
            import yaml  # type: ignore[import-not-found]
            data = yaml.safe_load(raw)
        except ImportError as exc:
            raise ValueError("mcp_servers.yaml must be JSON-compatible unless PyYAML is installed") from exc
    servers = data.get("servers", {}) if isinstance(data, dict) else None
    if not isinstance(servers, dict):
        raise ValueError("MCP config must contain a servers mapping")
    result: dict[str, MCPServerConfig] = {}
    for name, entry in servers.items():
        if not isinstance(name, str) or not name.replace("_", "").replace("-", "").isalnum():
            raise ValueError("MCP server names must be simple identifiers")
        if not isinstance(entry, dict):
            raise ValueError(f"MCP server '{name}' must be a mapping")
        transport = str(entry.get("transport", "stdio")).lower()
        if transport not in {"stdio", "http", "sse"}:
            raise ValueError(f"Unsupported MCP transport for '{name}'")
        if transport == "stdio" and not str(entry.get("command", "")).strip():
            raise ValueError(f"MCP stdio server '{name}' needs a command")
        if transport != "stdio" and not str(entry.get("url", "")).startswith(("http://", "https://")):
            raise ValueError(f"MCP HTTP server '{name}' needs an http(s) URL")
        result[name] = MCPServerConfig(
            name=name, transport=transport, command=str(entry.get("command", "")),
            args=[str(x) for x in entry.get("args", [])], url=str(entry.get("url", "")),
            headers={str(k): _expand(str(v)) for k, v in (entry.get("headers", {}) or {}).items()},
            env={str(k): _expand(str(v)) for k, v in (entry.get("env", {}) or {}).items()},
            enabled=bool(entry.get("enabled", True)),
            timeout=max(1.0, min(float(entry.get("timeout", 20)), 300.0)),
            tool_tiers={str(k): str(v).upper() for k, v in (entry.get("tool_tiers", {}) or {}).items()},
        )
    return result


def _expand(value: str) -> str:
    import re
    return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", lambda m: os.environ.get(m.group(1), ""), value)


class MCPClient:
    """One configured MCP server connection."""

    def __init__(self, config: MCPServerConfig):
        self.config = config
        self._process: subprocess.Popen[str] | None = None
        self._lock = threading.RLock()
        self._request_id = 0
        self._session_id = ""
        self._initialized = False

    def close(self) -> None:
        with self._lock:
            process, self._process = self._process, None
            self._initialized = False
            if process and process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=2)
                except subprocess.TimeoutExpired:
                    process.kill()

    def _next_id(self) -> int:
        self._request_id += 1
        return self._request_id

    def _stdio_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            if not self._process or self._process.poll() is not None:
                env = os.environ.copy()
                env.update(self.config.env)
                self._process = subprocess.Popen(
                    [self.config.command, *self.config.args], stdin=subprocess.PIPE,
                    stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                    encoding="utf-8", errors="replace", env=env, bufsize=1,
                )
                self._initialized = False
            if not self._initialized and method != "initialize":
                self._stdio_rpc("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                                   "clientInfo": {"name": "MAX", "version": "1.0"}})
                self._stdio_notification("notifications/initialized")
                self._initialized = True
            return self._stdio_rpc(method, params or {})

    def _stdio_notification(self, method: str) -> None:
        assert self._process and self._process.stdin
        self._process.stdin.write(json.dumps({"jsonrpc": "2.0", "method": method}) + "\n")
        self._process.stdin.flush()

    def _stdio_rpc(self, method: str, params: dict[str, Any]) -> dict[str, Any]:
        assert self._process and self._process.stdin and self._process.stdout
        request_id = self._next_id()
        self._process.stdin.write(json.dumps({"jsonrpc": "2.0", "id": request_id,
                                               "method": method, "params": params}) + "\n")
        self._process.stdin.flush()
        result_queue: queue.Queue[dict[str, Any] | BaseException] = queue.Queue(maxsize=1)

        def _read_reply() -> None:
            try:
                while True:
                    line = self._process.stdout.readline()
                    if not line:
                        raise ConnectionError(f"MCP server '{self.config.name}' closed its stdout")
                    try:
                        message = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if message.get("id") != request_id:
                        continue
                    result_queue.put(message)
                    return
            except BaseException as exc:
                try:
                    result_queue.put_nowait(exc)
                except queue.Full:
                    pass

        threading.Thread(target=_read_reply, daemon=True, name=f"mcp-{self.config.name}-reader").start()
        try:
            response = result_queue.get(timeout=self.config.timeout)
        except queue.Empty as exc:
            self.close()
            raise TimeoutError(f"MCP server '{self.config.name}' timed out") from exc
        if isinstance(response, BaseException):
            raise response
        if "error" in response:
            raise RuntimeError(str(response["error"].get("message", "MCP request failed")))
        return response.get("result") or {}

    def _http_request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        import requests
        payload = {"jsonrpc": "2.0", "id": self._next_id(), "method": method,
                   "params": params or {}}
        headers = {"Accept": "application/json, text/event-stream", "Content-Type": "application/json",
                   **self.config.headers}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        response = requests.post(self.config.url, json=payload, headers=headers,
                                 timeout=self.config.timeout, stream=False)
        if response.status_code == 404 and self._session_id:
            self._session_id = ""
            self._initialized = False
        response.raise_for_status()
        session_id = response.headers.get("Mcp-Session-Id")
        if session_id:
            self._session_id = session_id
        content_type = response.headers.get("content-type", "")
        if "text/event-stream" in content_type:
            messages = [line[5:].strip() for line in response.text.splitlines()
                        if line.startswith("data:") and line[5:].strip()]
            data = json.loads(messages[-1]) if messages else {}
        else:
            data = response.json() if response.content else {}
        if "error" in data:
            raise RuntimeError(str(data["error"].get("message", "MCP request failed")))
        if method == "initialize" and not self._initialized:
            self._initialized = True
            self._http_notification("notifications/initialized")
        return data.get("result") or {}

    def _http_notification(self, method: str) -> None:
        import requests
        headers = {"Content-Type": "application/json", **self.config.headers}
        if self._session_id:
            headers["Mcp-Session-Id"] = self._session_id
        requests.post(self.config.url, json={"jsonrpc": "2.0", "method": method},
                      headers=headers, timeout=self.config.timeout).raise_for_status()

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        if not self.config.enabled:
            raise RuntimeError(f"MCP server '{self.config.name}' is disabled")
        if self.config.transport == "stdio":
            return self._stdio_request(method, params)
        if not self._initialized and method != "initialize":
            self._http_request("initialize", {"protocolVersion": "2024-11-05", "capabilities": {},
                                                "clientInfo": {"name": "MAX", "version": "1.0"}})
        return self._http_request(method, params)


class MCPManager:
    """Reloadable server manager with conservative inferred permission tiers."""

    def __init__(self, config_path: str | Path):
        self.config_path = Path(config_path)
        self._clients: dict[str, MCPClient] = {}
        self._fingerprint = ""
        self._lock = threading.RLock()

    def _reload(self) -> dict[str, MCPClient]:
        raw = self.config_path.read_bytes() if self.config_path.exists() else b""
        import hashlib
        fingerprint = hashlib.sha256(raw).hexdigest()
        with self._lock:
            if fingerprint == self._fingerprint:
                return self._clients
            configs = load_server_configs(self.config_path)
            fresh: dict[str, MCPClient] = {}
            for name, config in configs.items():
                old = self._clients.get(name)
                if old and old.config == config:
                    fresh[name] = old
                else:
                    if old:
                        old.close()
                    fresh[name] = MCPClient(config)
            for name, old in self._clients.items():
                if name not in fresh:
                    old.close()
            self._clients = fresh
            self._fingerprint = fingerprint
            return self._clients

    def list_tools(self) -> list[MCPTool]:
        tools: list[MCPTool] = []
        for server, client in self._reload().items():
            if not client.config.enabled:
                continue
            result = client.request("tools/list")
            for entry in result.get("tools", []):
                name = str(entry.get("name", ""))
                if not name:
                    continue
                tier = client.config.tool_tiers.get(name, _infer_tier(name, entry.get("description", "")))
                tools.append(MCPTool(server, name, str(entry.get("description", "")),
                                     entry.get("inputSchema") or {"type": "object", "properties": {}}, tier))
        return tools

    def call(self, server: str, tool: str, arguments: dict[str, Any]) -> dict[str, Any]:
        client = self._reload().get(server)
        if not client or not client.config.enabled:
            raise RuntimeError(f"MCP server '{server}' is not enabled")
        return client.request("tools/call", {"name": tool, "arguments": arguments})

    def status(self) -> list[dict[str, Any]]:
        return [{"name": name, "enabled": client.config.enabled,
                 "transport": client.config.transport}
                for name, client in self._reload().items()]

    def close(self) -> None:
        for client in self._clients.values():
            client.close()


def _infer_tier(name: str, description: str) -> str:
    text = f"{name} {description}".lower()
    if any(word in text for word in ("send", "delete", "purchase", "pay", "install", "execute", "write", "create", "update", "edit", "move", "upload")):
        return "T2"
    if any(word in text for word in ("read", "list", "search", "get", "fetch", "query", "view")):
        return "T0"
    return "T2"

# MCP client

`mcp/client.py` implements a client and manager for configured Model Context Protocol servers. The client code supports `stdio`, `http`, and `sse` transports, expands `${ENV_NAME}` references in configured values, and exposes server tools with their input schemas and permission tiers.

Server definitions are read from a YAML/JSON-compatible configuration file such as `config/mcp_servers.yaml`. The checked-in file has no server entries, and the current `main.py` does not wire this manager into its live tool registry. Treat MCP support as a library component requiring explicit integration and server configuration, not as an enabled default feature.

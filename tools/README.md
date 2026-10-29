# Modular tools

Each tool package under `tools/` contains a `manifest.json` and `handler.py`. The manifest declares the tool name, description, permission tier, timeout, and parameter schema. `core/tool_registry.py` implements manifest validation, tool discovery, dispatch, timeouts, hot reload, event emission, and audit writing.

Current packages provide date/time lookup, file reading, note writing, and note deletion. Their manifests assign T0 to read-only tools, T1 to note writing, and T2 to note deletion. The registry's T2 path requires confirmation when used through the registry.

This registry is a distinct component from `core.action_loader`, which discovers the built-in `actions/*.py` modules.

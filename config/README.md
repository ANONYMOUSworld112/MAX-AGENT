# Configuration

This directory holds shared defaults and safe example files. Runtime files such as `api_keys.json` are local configuration and are ignored by Git.

## Files

- `config.yaml`: structured assistant, model, hardware, tool, and safety defaults read by `core.config_loader`.
- `api_keys.example.json`: blank example for the JSON configuration shape. The live `main.py` entry point reads `gemini_api_key` from the local `api_keys.json` file.
- `mcp_servers.yaml`: MCP server definitions; the checked-in example has an empty `servers` mapping.
- `owned_assets.yaml`: default owned-asset and network-scan settings.
- `jarvis.ico`: image asset used by the application.

`core.config_loader` also reads `.env` and process environment values. Some legacy actions read `config/api_keys.json` directly, so the configuration paths are not fully unified. Keep credentials, tokens, and private account settings out of tracked files.

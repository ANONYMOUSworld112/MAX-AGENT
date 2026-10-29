# Memory and local settings

`memory/` contains persistent memory and configuration helpers.

- `memory_manager.py` reads and writes the runtime `memory/long_term.json` store and formats selected memory for prompts.
- `config_manager.py` manages non-secret preferences and includes OS credential-store support for a Gemini key, with handling for legacy JSON configuration.
- `long_term.example.json` is the shareable memory shape/example. The runtime `long_term.json` is local state and must not be committed.
- `backups/` is reserved for runtime backups.

The live entry point currently reads its Gemini key directly from `config/api_keys.json`; this is distinct from the keyring helper in `config_manager.py`. Avoid placing private user data in examples or evidence files.

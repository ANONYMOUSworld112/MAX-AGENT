# Core runtime

`core/` holds shared runtime infrastructure used by the desktop assistant, actions, agents, and supporting modules.

## Key modules

- `action_loader.py` discovers action modules that export `TOOL` declarations.
- `plugin_loader.py` discovers plugin modules; `tool_registry.py` loads manifest-and-handler packages under `tools/`.
- `contracts.py`, `events.py`, and `hooks.py` define shared data structures and event hooks.
- `config_loader.py` loads structured settings, environment values, and legacy JSON credentials.
- `llm/`, `llm_client.py`, and `providers/` contain model clients, provider abstractions, and routing support.
- `intent_engine.py`, `task_graph.py`, `scheduler.py`, and `agent_loop.py` cover task parsing and execution components.
- `max_infra/` contains state, lifecycle, lock, snapshot, vault, and recovery-related modules.
- `adapters/`, `perception/`, `verification/`, and `reflex/` provide platform adapters and supporting UI state, verification, and intent modules.
- `coding/`, `memory/`, `audio/`, and `security/` contain focused subsystems.

The presence of a module does not mean it is used by every entry point. `main.py` specifically uses the action, plugin, and agent registries when assembling its live tools.

# Agents

`agents/` contains the agent classes and registry used by MAX. `agents/router.py` registers the default agent groups and provides agent lookup and tool definitions; `agents/base.py` contains the shared base class.

## Groups

- `core/`: orchestration, planning, model routing, critique, and validation.
- `software/`: coding, code review, test writing, API and database design, documentation, DevOps, and dependency tasks.
- `productivity/`: calendar, communications, email, file organization, meeting preparation, notes, research, and task tracking.
- `safety/`: computer use, desktop and browser interaction, input arbitration, security gates, and recovery.
- `health/`: system, network, performance, backup, update, and health checks.

Agent files may expose tools through their definitions, which the registry contributes to the live tool set. A registered agent is not evidence that every external integration is configured or operational; inspect the relevant implementation and local settings.

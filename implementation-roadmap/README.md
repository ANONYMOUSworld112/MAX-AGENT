# MAX OS v1 — Implementation Roadmap

### Derived from: PRD.md + MAX_OS_TRD.md + ARCHITECTURE.md
### Optimized for: Controlled execution with zero ambiguity

---
file
## Documents in This Folder

| # | Document | What It Answers |
|---|----------|----------------|
| 01 | [Backend Wiring Order](./01_BACKEND_WIRING_ORDER.md) | "What gets built first, and what plugs into what?" — 26 modules across 7 layers, strict dependency ordering, ASCII wiring diagrams |
| 02 | [State Management Plan](./02_STATE_MANAGEMENT_PLAN.md) | "Where does every piece of state live, who owns it, and what happens when something crashes mid-write?" — 4 state categories, crash recovery protocol, ownership matrix |
| 03 | [Data Flow Mapping](./03_DATA_FLOW_MAPPING.md) | "What happens to my request at every step?" — complete happy path, compound task flow, error flow, secrets flow, kill switch flow |
| 04 | [Risk Areas](./04_RISK_AREAS.md) | "What can go wrong and how do we prevent it?" — 15 risks ranked by severity, concrete mitigations, pre-v1 gate checklist |
| 05 | [Dependency Order](./05_DEPENDENCY_ORDER.md) | "In what order do I actually build this?" — 7 sprints, ~128 hours, parallel opportunities, session handoff protocol |

---

## Quick Reference: The 7 Sprints

```
Sprint 0 (Day 1-2)    ► Bootstrap: state_db, schema, kill switch, vault, data boundary
Sprint 1 (Day 3-5)    ► Task Engine: errors, lifecycle, queue, snapshot, retry
Sprint 2 (Day 6-8)    ► Sync: lock manager, watchdog, reconciliation, circuit breaker, DLQ
Sprint 3 (Day 9-10)   ► Routing: intent classifier, permissions, planner, prompt agent
Sprint 4 (Day 11-16)  ► Agents: Calendar → Notes → Coding → Deploy
Sprint 5 (Day 17-20)  ► Integration: daemon, CLI, trace viewer, startup recovery
Sprint 6 (Day 21-28)  ► Verification: 9 test suites, chaos testing, security audit
```

## Architecture at a Glance

```
┌─────────────────────────────────────────────────────────────┐
│                    CLI (thin, no logic)                       │
│                         │                                    │
│              Unix domain socket / named pipe                 │
│                         │                                    │
│  ┌──────────────────────▼──────────────────────────────────┐ │
│  │              max-core daemon                             │ │
│  │                                                          │ │
│  │  ┌─────────┐  ┌──────────┐  ┌────────┐  ┌──────────┐  │ │
│  │  │ Intent   │→│ Confirm  │→│ Planner │→│  Queue   │  │ │
│  │  │Classifier│  │  Gate    │  │         │  │(priority)│  │ │
│  │  └─────────┘  └──────────┘  └────────┘  └──────────┘  │ │
│  │       │                                       │         │ │
│  │       │data_boundary                    ┌─────▼──────┐  │ │
│  │       ▼                                 │Lock Manager│  │ │
│  │  ┌─────────┐                            └─────┬──────┘  │ │
│  │  │Anthropic│                                  │         │ │
│  │  │  API    │                            ┌─────▼──────┐  │ │
│  │  └─────────┘                            │ Execution  │  │ │
│  │                                         │(snapshot+  │  │ │
│  │  ┌────────────────────────────────────┐ │ heartbeat) │  │ │
│  │  │        4 Agent Modules             │ └─────┬──────┘  │ │
│  │  │  Calendar │ Notes │ Coding │Deploy │       │         │ │
│  │  └────────────────────────────────────┘ ┌─────▼──────┐  │ │
│  │                                         │Reconcile   │  │ │
│  │  ┌──────────┐  ┌──────────┐            └─────┬──────┘  │ │
│  │  │  Vault   │  │Kill Switch│                  │         │ │
│  │  │(keychain)│  │(signal)  │             ┌─────▼──────┐  │ │
│  │  └──────────┘  └──────────┘             │Trace Logger│  │ │
│  │                                         └────────────┘  │ │
│  └──────────────────────────────────────────────────────────┘ │
│                         │                                    │
│                   ┌─────▼──────┐                             │
│                   │  SQLite    │                              │
│                   │ (WAL mode) │                              │
│                   └────────────┘                              │
└─────────────────────────────────────────────────────────────┘
```

## The Three Rules

1. **Kill switch is Component #0.** Nothing initializes until it's armed.
2. **No agent #5 until v1 runs for 2 real weeks.** Scope discipline is
   enforced by the `steps` table, not by willpower.
3. **Every session starts from the database, not from memory.** The
   session handoff protocol in `05_DEPENDENCY_ORDER.md` §5 is mandatory.

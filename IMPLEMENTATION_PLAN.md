# CyberBlack AI-agent MAX + MAX OS + LAYA — MASTER IMPLEMENTATION PLAN

> **Created**: 2026-09-29
> **Codebase**: `F:\Mark-LIII-main\Mark-LIII-main`
> **Sources**:
> 1. CyberBlack AI-agent MAX — existing MAX-like voice assistant (Python 3.11, PyQt6, Gemini Live API)
> 2. MAX OS — 33-agent deterministic OS spec from `F:\MAX-V 4.0.0\max-md-files\`
> 3. Laya — System 1 non-autoregressive decision engine from `temp_laya/` (installed, v0.3.21)

---

## TABLE OF CONTENTS

1. [Project Vision](#1-project-vision)
2. [What's Already Done](#2-whats-already-done)
3. [Architecture Overview](#3-architecture-overview)
4. [Priority Roadmap](#4-priority-roadmap)
5. [Phase 1 — Infrastructure Floor (DONE)](#5-phase-1--infrastructure-floor-done)
6. [Phase 2 — Reflex Engine (DONE)](#6-phase-2--reflex-engine-done)
7. [Phase 3 — Task Engine & Concurrency (DONE)](#7-phase-3--task-engine--concurrency-done)
8. [Phase 4 — Memory & Confirm Gate (DONE)](#8-phase-4--memory--confirm-gate-done)
9. [Phase 5 — Agent Base & Core Cluster (DONE)](#9-phase-5--agent-base--core-cluster-done)
10. [Phase 6 — Software Delivery Cluster (DONE)](#10-phase-6--software-delivery-cluster-done)
11. [Phase 7 — Founder Productivity Cluster (DONE)](#11-phase-7--founder-productivity-cluster-done)
12. [Phase 8 — Safety & Input Control Cluster (DONE)](#12-phase-8--safety--input-control-cluster-done)
13. [Phase 9 — Infrastructure & Health Cluster (DONE)](#13-phase-9--infrastructure--health-cluster-done)
14. [Phase 10 — Dual-Lane main.py Wiring (DONE)](#14-phase-10--dual-lane-mainpy-wiring-done)
15. [Phase 11 — Perception Engine (DONE)](#15-phase-11--perception-engine-done)
16. [Phase 12 — Verification Engine (DONE)](#16-phase-12--verification-engine-done)
17. [Phase 13 — HUD Task Widget & Dashboard (DONE)](#17-phase-13--hud-task-widget--dashboard-done)
18. [Phase 14 — Dead Code Cleanup (DONE)](#18-phase-14--dead-code-cleanup-done)
19. [Phase 15 — Integration & E2E Tests (DONE)](#19-phase-15--integration--e2e-tests-done)
20. [DO NOT DO — Anti-Patterns & Constraints](#20-do-not-do--anti-patterns--constraints)
21. [File Map — All Existing & Planned Files](#21-file-map--all-existing--planned-files)
22. [Testing Strategy](#22-testing-strategy)
23. [Dependencies & Environment](#23-dependencies--environment)

---

## 1. Project Vision

Build a **deterministic, 33-agent AI operating system** on top of the existing CyberBlack AI-agent MAX voice assistant, using:

- **Laya** as the System 1 reflex brain (sub-33ms intent routing, guardrails, triage)
- **MAX OS specs** as the blueprint for the agent swarm architecture
- **CyberBlack AI-agent MAX** as the base runtime (Gemini Live voice I/O, PyQt6 HUD, plugin system)

### Core Principle: Dual-Lane Execution

```
User Voice/Text Input
        │
        ▼
  Laya ReflexIntentRouter (< 33ms)
        │
    ┌───┴───┐
    ▼       ▼
 LANE A   LANE B
 (sync)   (async)
    │       │
 Direct   TaskQueue → Agent → Tools → Verify
 read/     └─ KillSwitch guard
 query      └─ Circuit breaker check
    │        └─ Snapshot pre-capture
    │         └─ Sorted lock acquisition
    │          └─ Execute
    │           └─ Reconciliation
    │            └─ Unlock & report
    ▼       ▼
  Response to User
```

---

## 2. What's Already Done

### ✅ All Tests Passing: 74/74

| # | Module / Phase | File | Tests | Status |
|---|----------------|------|-------|--------|
| 1 | KillSwitch | `core/max_infra/kill_switch.py` | 2 | ✅ PASS |
| 2 | StateDB | `core/max_infra/state_db.py` + `schema.sql` | 3 | ✅ PASS |
| 3 | Vault | `core/max_infra/vault.py` | 2 | ✅ PASS |
| 4 | DataBoundary | `core/max_infra/data_boundary.py` | 2 | ✅ PASS |
| 5 | LayaReflexEngine | `core/reflex/laya_engine.py` | 3 | ✅ PASS |
| 6 | ReflexIntentRouter | `core/reflex/intent_router.py` | 3 | ✅ PASS |
| 7 | ReflexGuardrails | `core/reflex/guardrails.py` | 3 | ✅ PASS |
| 8 | ReflexTriage | `core/reflex/triage.py` | 1 | ✅ PASS |
| 9 | TaskLifecycleFSM | `core/max_infra/task_lifecycle.py` | 3 | ✅ PASS |
| 10 | TaskQueue | `core/max_infra/task_queue.py` | 3 | ✅ PASS |
| 11 | LockManager | `core/max_infra/lock_manager.py` | 2 | ✅ PASS |
| 12 | SnapshotEngine | `core/max_infra/snapshot.py` | 2 | ✅ PASS |
| 13 | CircuitBreaker | `core/max_infra/circuit_breaker.py` | 1 | ✅ PASS |
| 14 | Watchdog | `core/max_infra/watchdog.py` | 1 | ✅ PASS |
| 15 | ReconciliationEngine | `core/max_infra/reconciliation.py` | 1 | ✅ PASS |
| 16 | MemoryContextHeap | `core/memory/context_heap.py` | 1 | ✅ PASS |
| 17 | TokenBudgetCompressor | `core/memory/token_budget.py` | 1 | ✅ PASS |
| 18 | Confirm+Undo Bridge | `core/confirm.py` + `core/undo.py` | 2 | ✅ PASS |
| 19 | BaseAgent | `agents/base.py` | 2 | ✅ PASS |
| 20 | AgentRegistry (33 agents) | `agents/router.py` | — | ✅ 33 registered |
| 21 | Cluster 1: Core Reasoning (5) | `agents/core/*.py` | 1 | ✅ PASS |
| 22 | Cluster 2: Software Delivery (8) | `agents/software/*.py` | 2 | ✅ PASS |
| 23 | Cluster 3: Founder Productivity (8) | `agents/productivity/*.py` | 2 | ✅ PASS |
| 24 | Cluster 4: Safety & Input Control (6) | `agents/safety/*.py` | 2 | ✅ PASS |
| 25 | Cluster 5: Infrastructure & Health (6) | `agents/health/*.py` | 2 | ✅ PASS |
| 26 | Dual-Lane Voice Wiring | `main.py` + `tests/integration/test_dual_lane.py` | 4 | ✅ PASS |
| 27 | Perception Engine | `core/perception/*.py` | 7 | ✅ PASS |
| 28 | Verification Engine | `core/verification/*.py` | 7 | ✅ PASS |
| 29 | HUD Task Widget & Dashboard | `ui/components/task_list_widget.py`, `dashboard/server.py` | 2 | ✅ PASS |
| 30 | Full Task & E2E Flow | `tests/e2e/*.py` | 3 | ✅ PASS |
| 31 | Integration Lifecycle & Memory | `tests/integration/*.py` | 4 | ✅ PASS |

**Total: 15/15 phases implemented, all 33 agents registered, 74 tests passing in ~8s**

---

## 3. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                           USER (Voice / Text / GUI)                     │
└────────────────────────────────────┬────────────────────────────────────┘
                                     │
┌────────────────────────────────────▼────────────────────────────────────┐
│                     main.py → MaxLive                                │
│  ┌──────────────┐  ┌────────────────────┐  ┌────────────────────────┐  │
│  │ Gemini Live  │  │ ReflexIntentRouter │  │  Action Registry       │  │
│  │ Session      │──│ (Laya sub-33ms)    │──│  + Plugin Registry     │  │
│  └──────────────┘  └────────┬───────────┘  └────────────────────────┘  │
└─────────────────────────────┼──────────────────────────────────────────┘
                              │
            ┌─────────────────┼─────────────────┐
            ▼                                   ▼
   ┌─────────────────┐               ┌─────────────────────┐
   │    LANE A        │               │     LANE B            │
   │ (Sync Direct)    │               │ (Async TaskQueue)     │
   │  Read queries    │               │  Write operations     │
   │  Instant answers │               │  Background work      │
   └─────────────────┘               │  Agent orchestration  │
                                      └──────────┬────────────┘
                                                 │
┌────────────────────────────────────────────────▼────────────────────────┐
│                        MAX INFRASTRUCTURE FLOOR                         │
│  ┌────────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐ ┌──────────┐  │
│  │ KillSwitch │ │ StateDB  │ │ LockMgr   │ │ Snapshot │ │ Watchdog │  │
│  │ (Comp #0)  │ │ (SQLite) │ │ (sorted)  │ │ (atomic) │ │ (daemon) │  │
│  └────────────┘ └──────────┘ └───────────┘ └──────────┘ └──────────┘  │
│  ┌────────────┐ ┌──────────┐ ┌───────────┐ ┌──────────┐               │
│  │ CircuitBkr │ │ Vault    │ │ DataBound │ │ Reconcil │               │
│  │ (3-strike) │ │ (secrets)│ │ (PII/key) │ │ (verify) │               │
│  └────────────┘ └──────────┘ └───────────┘ └──────────┘               │
└────────────────────────────────────────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼──────────────────────────────────┐
│                         REFLEX LAYER (Laya)                            │
│  ┌──────────────┐ ┌──────────────┐ ┌────────────┐ ┌────────────────┐  │
│  │ LayaReflex   │ │ IntentRouter │ │ Guardrails │ │ Triage         │  │
│  │ Engine       │ │ (Lane A/B)   │ │ (4-tier)   │ │ (5-band)       │  │
│  └──────────────┘ └──────────────┘ └────────────┘ └────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼──────────────────────────────────┐
│                         33-AGENT SWARM                                 │
│                                                                        │
│  Cluster 1: Core Reasoning (5)        Cluster 2: Software (8)         │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐  │
│  │ Orchestrator, Planner,       │    │ CodingAgent, CodeReviewer,   │  │
│  │ Verifier, ModelRouter,       │    │ TestWriter, DevOps, DBAgent, │  │
│  │ Critic                       │    │ APIDesigner, DocWriter,      │  │
│  └──────────────────────────────┘    │ DependencyMgr               │  │
│                                      └──────────────────────────────┘  │
│  Cluster 3: Productivity (8)         Cluster 4: Safety (6)            │
│  ┌──────────────────────────────┐    ┌──────────────────────────────┐  │
│  │ Email, Calendar, Comms,      │    │ ComputerUse, DesktopAgent,   │  │
│  │ Research, FileOrganizer,     │    │ BrowserAgent, InputArbiter,  │  │
│  │ Notes, TaskTracker,          │    │ SecurityGate,                │  │
│  │ MeetingPrep                  │    │ RecoveryEngine               │  │
│  └──────────────────────────────┘    └──────────────────────────────┘  │
│                                                                        │
│  Cluster 5: Infrastructure (6)                                         │
│  ┌──────────────────────────────┐                                      │
│  │ SystemMonitor, NetworkAgent, │                                      │
│  │ BackupAgent, UpdateAgent,    │                                      │
│  │ PerformanceAgent,            │                                      │
│  │ HealthCheck                  │                                      │
│  └──────────────────────────────┘                                      │
└────────────────────────────────────────────────────────────────────────┘
                                      │
┌─────────────────────────────────────▼──────────────────────────────────┐
│                    MEMORY & CONTEXT                                     │
│  ┌──────────────────────────────────────────────────────────────────┐  │
│  │ 5-Layer MemoryContextHeap:                                       │  │
│  │  L0: Identity (name, config)                                     │  │
│  │  L1: Preferences (user habits)                                   │  │
│  │  L2: Behavioral (patterns, voice)                                │  │
│  │  L3: Project/Task (current work)                                 │  │
│  │  L4: Conversation (ephemeral session)                            │  │
│  │                                                                   │  │
│  │ TokenBudgetCompressor: enforces hard token caps per layer         │  │
│  └──────────────────────────────────────────────────────────────────┘  │
└────────────────────────────────────────────────────────────────────────┘
```

---

## 4. Priority Roadmap

| Priority | Phase | Description | Status | Est. Effort |
|----------|-------|-------------|--------|-------------|
| P0 | 1-5 | Infrastructure Floor + Reflex + Task Engine + Memory + Core Agents | ✅ DONE | — |
| P1 | 6 | Software Delivery Cluster (8 agents) | ✅ DONE | Medium |
| P1 | 7 | Founder Productivity Cluster (8 agents) | ✅ DONE | Medium |
| P1 | 10 | Dual-Lane `main.py` Wiring | ✅ DONE | High |
| P2 | 8 | Safety & Input Control Cluster (6 agents) | ✅ DONE | High |
| P2 | 9 | Infrastructure & Health Cluster (6 agents) | ✅ DONE | Medium |
| P2 | 11 | Perception Engine (screen/UIA/DOM/OCR) | ✅ DONE | High |
| P2 | 12 | Verification Engine (state diff verify) | ✅ DONE | Medium |
| P3 | 13 | HUD Task Widget & Dashboard | ✅ DONE | Low |
| P3 | 14 | Dead Code Cleanup | ✅ DONE | Low |
| P4 | 15 | Integration & E2E Tests | ✅ DONE | Medium |

---

## 5. Phase 1 — Infrastructure Floor (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

### Components Built

| Component | File | Purpose |
|-----------|------|---------|
| KillSwitch | `core/max_infra/kill_switch.py` | Singleton emergency stop, `guard()` raises `SystemExit`, registers child PIDs for cleanup |
| StateDB | `core/max_infra/state_db.py` + `schema.sql` | SQLite WAL mode, 7 tables (tasks, task_traces, resource_locks, circuit_breakers, memory_layers, snapshots, audit_log) |
| Vault | `core/max_infra/vault.py` | Keyring → DPAPI → env fallback secret storage |
| DataBoundary | `core/max_infra/data_boundary.py` | PII/API key scrubber with reversible `[REDACTED:tag]` tokens |

### Key Design Decisions
- KillSwitch is a **true singleton** (class-level `_instance`)
- StateDB uses **WAL mode** for concurrent readers
- DataBoundary regex for API keys uses `{30,40}` range (not exact `{35}`)
- Vault never logs secret values — only operation results

---

## 6. Phase 2 — Reflex Engine (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

### Components Built

| Component | File | Purpose |
|-----------|------|---------|
| LayaReflexEngine | `core/reflex/laya_engine.py` | Wraps `laya.Router` for choice/score/noul decisions with deterministic keyword fallback |
| ReflexIntentRouter | `core/reflex/intent_router.py` | Routes to Lane A (sync reads) or Lane B (async writes), selects target agent |
| ReflexGuardrails | `core/reflex/guardrails.py` | 4-tier risk: Tier 0 Auto → Tier 1 Safe Write → Tier 2 Confirm → Tier 3 Hard Block |
| ReflexTriage | `core/reflex/triage.py` | 5-band priority: Band 0 Critical → Band 1 High → Band 2 Normal → Band 3 Low → Band 4 Maintenance |

### Key Design Decision
- Laya `Router` downloads model checkpoints on first use. **LayaReflexEngine provides deterministic keyword-matching fallback** when checkpoints unavailable, so the system never fails on first boot.

---

## 7. Phase 3 — Task Engine & Concurrency (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

### Components Built

| Component | File | Purpose |
|-----------|------|---------|
| TaskLifecycleFSM | `core/max_infra/task_lifecycle.py` | `CREATED→QUEUED→LOCK_WAIT→RUNNING→RECONCILING→DONE/FAILED/CANCELLED` |
| TaskQueue | `core/max_infra/task_queue.py` | Priority heapq, starvation aging (age × 0.1), backpressure at 500 |
| LockManager | `core/max_infra/lock_manager.py` | Dijkstra sorted-order deadlock prevention, TTL timeout |
| SnapshotEngine | `core/max_infra/snapshot.py` | Atomic file backup to temp dir, bit-for-bit rollback on failure |
| CircuitBreaker | `core/max_infra/circuit_breaker.py` | 3-strike trip → OPEN, cooldown period → HALF_OPEN → reset on success |
| Watchdog | `core/max_infra/watchdog.py` | Background daemon thread, configurable heartbeat interval (500ms default) |
| ReconciliationEngine | `core/max_infra/reconciliation.py` | OS truth verifier for file existence and exit codes |

### Critical Bug Fixed
- **LockManager**: Initial implementation held `Condition` lock across `yield`, preventing other threads. Fixed by separating acquire/release into distinct `with self._condition:` blocks.

---

## 8. Phase 4 — Memory & Confirm Gate (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

### Components Built

| Component | File | Purpose |
|-----------|------|---------|
| MemoryContextHeap | `core/memory/context_heap.py` | 5-layer memory (Identity, Prefs, Behavioral, Project, Conversation) |
| TokenBudgetCompressor | `core/memory/token_budget.py` | Line-pruning compressor to enforce hard token caps |
| Confirm+Undo Integration | `core/confirm.py` + `core/undo.py` | Existing CyberBlack AI-agent MAX confirm/undo bridge verified with SnapshotEngine |

### Design Preservation
- `core/confirm.py` uses **callback-based non-blocking design**: `request()` shows HUD banner, returns immediately. `resolve()` runs stored callable on worker thread. **MUST BE PRESERVED AS-IS.**
- `core/undo.py` uses **push-based undo stack** (max 10 entries). Now integrated with SnapshotEngine.

---

## 9. Phase 5 — Agent Base & Core Cluster (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

### Components Built

| Component | File | Purpose |
|-----------|------|---------|
| BaseAgent | `agents/base.py` | Lifecycle envelope: KillSwitch → CircuitBreaker → Snapshot → SortedLocks → Execute → Reconcile |
| AgentInput/Output | `agents/base.py` | Pydantic models for standardized agent I/O |
| AgentRegistry | `agents/router.py` | Singleton registry, register/get/list/export tool definitions |
| MasterOrchestrator | `agents/core/orchestrator.py` | Agent 1: Decomposes complex goals, delegates to sub-agents |
| DecompositionPlanner | `agents/core/planner.py` | Agent 2: Creates step-by-step execution plans |
| ValidationVerifier | `agents/core/verifier.py` | Agent 3: Validates outputs against expected results |
| ModelRouter | `agents/core/model_router.py` | Agent 4: Selects optimal LLM model per task |
| AdversarialCritic | `agents/core/critic.py` | Agent 5: Red-team challenges to outputs |

---

## 10. Phase 6 — Software Delivery Cluster (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

### 8 Agents to Implement

| # | Agent | File | Purpose | Permission Tier |
|---|-------|------|---------|-----------------|
| 6 | CodingAgent | `agents/software/coding_agent.py` | Writes/modifies code files per plan | Tier 1 |
| 7 | CodeReviewer | `agents/software/code_reviewer.py` | Reviews code for bugs, style, security | Tier 0 |
| 8 | TestWriter | `agents/software/test_writer.py` | Generates unit/integration tests | Tier 1 |
| 9 | DevOpsAgent | `agents/software/devops_agent.py` | CI/CD, Docker, deployment scripts | Tier 2 |
| 10 | DBAgent | `agents/software/db_agent.py` | Schema design, migrations, queries | Tier 2 |
| 11 | APIDesigner | `agents/software/api_designer.py` | REST/GraphQL endpoint design | Tier 0 |
| 12 | DocWriter | `agents/software/doc_writer.py` | README, API docs, inline comments | Tier 0 |
| 13 | DependencyMgr | `agents/software/dependency_mgr.py` | Package audits, updates, vulnerability scanning | Tier 1 |

### Implementation Pattern (same for ALL agents)

```python
"""Agent Name — one-line purpose."""
from agents.base import BaseAgent, AgentInput, AgentOutput

class CodingAgent(BaseAgent):
    name = "CodingAgent"
    description = "Writes and modifies code files based on a decomposed plan."
    permission_tier = 1  # Safe Write — auto-execute reads, confirm writes

    def _execute(self, input_data: AgentInput) -> AgentOutput:
        # Domain-specific logic here
        # Must return AgentOutput(success=True/False, result="...", artifacts={})
        # BaseAgent.run() handles: KillSwitch, CircuitBreaker, Snapshot, Locks, Reconciliation
        ...
```

### Test File
- `tests/unit/test_cluster_software.py` — verify all 8 agents instantiate, register, and run lifecycle

### What To Do
1. Create each `.py` file following the BaseAgent pattern
2. Each agent's `_execute()` should accept `AgentInput` and do its domain work
3. For now, agents can be **stub implementations** that log what they would do and return `AgentOutput(success=True, result="Plan: ...")`
4. Wire them into the existing `actions/` tool system (each agent exposes `get_tool_definition()`)
5. Register all 8 with `AgentRegistry`

### What NOT To Do
- ❌ Do NOT implement full LLM chains inside agents yet — that's Phase 10 wiring
- ❌ Do NOT hardcode API keys or model names in agent files
- ❌ Do NOT bypass BaseAgent.run() — always go through the lifecycle envelope

---

## 11. Phase 7 — Founder Productivity Cluster (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

### 8 Agents to Implement

| # | Agent | File | Purpose | Permission Tier |
|---|-------|------|---------|-----------------|
| 14 | EmailAgent | `agents/productivity/email_agent.py` | Draft, send, summarize emails | Tier 2 |
| 15 | CalendarAgent | `agents/productivity/calendar_agent.py` | Schedule, reschedule, check availability | Tier 1 |
| 16 | CommsAgent | `agents/productivity/comms_agent.py` | Slack/Teams/Discord message management | Tier 2 |
| 17 | ResearchAgent | `agents/productivity/research_agent.py` | Multi-source research with citations | Tier 0 |
| 18 | FileOrganizer | `agents/productivity/file_organizer.py` | File discovery, move, rename, organize | Tier 1 |
| 19 | NotesAgent | `agents/productivity/notes_agent.py` | Create, search, manage notes | Tier 0 |
| 20 | TaskTracker | `agents/productivity/task_tracker.py` | Create/manage todo items & project tasks | Tier 0 |
| 21 | MeetingPrep | `agents/productivity/meeting_prep.py` | Pre-meeting briefing, agenda, notes | Tier 0 |

### Test File
- `tests/unit/test_cluster_productivity.py`

### What To Do
- Same pattern as Cluster 2 above
- EmailAgent and CommsAgent are **Tier 2** (external sends require per-instance confirmation)
- ResearchAgent should wrap the existing `actions/web_search.py` tool

### What NOT To Do
- ❌ Do NOT implement real SMTP/IMAP in EmailAgent yet — stub only
- ❌ Do NOT store credentials in agent files — use Vault
- ❌ Do NOT auto-send emails without Tier 2 confirmation gate

---

## 12. Phase 8 — Safety & Input Control Cluster (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

### 6 Agents to Implement

| # | Agent | File | Purpose | Permission Tier |
|---|-------|------|---------|-----------------|
| 22 | ComputerUseAgent | `agents/safety/computer_use.py` | Master desktop operator (OBSERVE→THINK→ACT→VERIFY) | Tier 2 |
| 23 | DesktopAgent | `agents/safety/desktop_agent.py` | Start Menu, taskbar, window management | Tier 1 |
| 24 | BrowserAgent | `agents/safety/browser_agent.py` | Browser control, tabs, navigation | Tier 1 |
| 25 | InputArbiter | `agents/safety/input_arbiter.py` | Exclusive mouse/keyboard ownership | Tier 2 |
| 26 | SecurityGate | `agents/safety/security_gate.py` | Static risk classification (Tier 0/1/2/3) | Tier 3 |
| 27 | RecoveryEngine | `agents/safety/recovery_engine.py` | 8-step failure recovery pipeline | Tier 0 |

### Test File
- `tests/unit/test_cluster_safety.py`

### What To Do
- ComputerUseAgent must follow the **OBSERVE → THINK → ACT → VERIFY** loop from ARCHITECTURE.md
- SecurityGate must use the existing `ReflexGuardrails` (don't duplicate risk classification)
- InputArbiter must respect KillSwitch — instant physical input revocation on emergency halt
- RecoveryEngine: `re-observe → refresh state → search again → alternative method → retry → change strategy → replan → ask user`

### What NOT To Do
- ❌ Do NOT implement raw Win32 calls inside agents — those go in `core/perception/` (Phase 11)
- ❌ Do NOT hardcode coordinates — always resolve through Perception Engine
- ❌ Do NOT bypass confirmation for Tier 2 actions — every instance must be confirmed
- ❌ Do NOT implement full computer vision model loading yet — use stubs

---

## 13. Phase 9 — Infrastructure & Health Cluster (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

### 6 Agents to Implement

| # | Agent | File | Purpose | Permission Tier |
|---|-------|------|---------|-----------------|
| 28 | SystemMonitorAgent | `agents/health/system_monitor.py` | Real-time CPU/RAM/GPU/temp metrics | Tier 0 |
| 29 | NetworkAgent | `agents/health/network_agent.py` | Network diagnostics, connectivity | Tier 0 |
| 30 | BackupAgent | `agents/health/backup_agent.py` | Automated file/config backups | Tier 1 |
| 31 | UpdateAgent | `agents/health/update_agent.py` | Package/system update management | Tier 2 |
| 32 | PerformanceAgent | `agents/health/performance_agent.py` | Performance profiling & optimization | Tier 0 |
| 33 | HealthCheck | `agents/health/health_check.py` | Periodic system health validation | Tier 0 |

### Test File
- `tests/unit/test_cluster_health.py`

### What To Do
- SystemMonitorAgent should wrap the existing `actions/system_monitor.py`
- HealthCheck should integrate with existing `core/max_infra/watchdog.py`
- BackupAgent should use `SnapshotEngine` for atomic backups

### What NOT To Do
- ❌ Do NOT install system updates automatically — UpdateAgent is Tier 2
- ❌ Do NOT run performance profiling on production without user consent

---

## 14. Phase 10 — Dual-Lane main.py Wiring (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

This is the **most important remaining integration phase**. It connects the new agent infrastructure to the existing CyberBlack AI-agent MAX voice pipeline.

### What To Do

#### Step 1: Add Agent Boot Sequence
In `MaxLive.__init__()`, after action/plugin discovery:
```python
# ── MAX Agent Infrastructure ──────────────────────────────
from core.reflex.intent_router import ReflexIntentRouter
from agents.router import AgentRegistry
from core.max_infra.task_queue import TaskQueue

self._intent_router = ReflexIntentRouter()
self._agent_registry = AgentRegistry.get_instance()
self._task_queue = TaskQueue()

# Register all agents from all clusters
from agents.core import orchestrator, planner, verifier, model_router, critic
# ... (register all 33)
```

#### Step 2: Intercept Tool Calls in `_execute_tool()`
In `MaxLive._execute_tool()` (around line 755), add Lane A/B routing:
```python
# BEFORE the existing tool dispatch chain:
intent = self._intent_router.route(name, args)

if intent.lane == LaneType.LANE_B and self._agent_registry.get(intent.target_agent):
    # Route to agent through TaskQueue
    agent = self._agent_registry.get(intent.target_agent)
    agent_input = AgentInput(
        task_id=f"task_{int(time.time())}",
        task_description=args.get("task_description", str(args)),
        parameters=args,
    )
    output = await loop.run_in_executor(None, agent.run, agent_input)
    result = output.result if output.success else f"Agent error: {output.error}"
else:
    # Fall through to existing action_registry / plugin_registry
    ...
```

#### Step 3: Wire Agent Tool Definitions
Add agent tool declarations to `_build_config()`:
```python
tools=[{"function_declarations": (
    TOOL_DECLARATIONS
    + self._action_registry.get_tool_declarations()
    + self._plugin_registry.get_tool_declarations()
    + self._agent_registry.get_all_tool_definitions()  # NEW
)}],
```

### Test File
- `tests/integration/test_dual_lane.py` — mock Gemini session, verify Lane A/B routing

### What NOT To Do
- ❌ Do NOT remove or modify the existing `_action_registry` dispatch — agents are ADDITIVE
- ❌ Do NOT change the Gemini Live session configuration format
- ❌ Do NOT block the async receive loop — agent execution goes through `run_in_executor`
- ❌ Do NOT break the existing `confirm_gate` and `undo_stack` integration
- ❌ Do NOT change how inline tools (save_memory, screen_process, etc.) work

---

## 15. Phase 11 — Perception Engine (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

### New Directory: `core/perception/`

| File | Purpose |
|------|---------|
| `core/perception/__init__.py` | Package marker |
| `core/perception/screen_capture.py` | Multi-monitor screenshot, DPI-aware coordinate normalization |
| `core/perception/accessibility.py` | COM `IUIAutomation` wrapper via `comtypes` |
| `core/perception/browser_dom.py` | Browser DOM/accessibility snapshot extractor |
| `core/perception/text_detection.py` | OCR fallback engine (Tesseract) |
| `core/perception/element_detection.py` | Visual element detection for non-UIA windows |
| `core/perception/ui_detection.py` | Composite detector: UIA → DOM → Window meta → Visual/OCR |
| `core/perception/state_builder.py` | Builds complete `ComputerState` snapshot |

### Perception Fallback Hierarchy (from ARCHITECTURE.md)
```
Level 1: Semantic UI Automation (IUIAutomation)
Level 2: Accessibility tree
Level 3: Browser DOM
Level 4: Application-specific APIs
Level 5: OCR
Level 6: Vision model
Level 7: Dynamic coordinate interaction (MUST LOG why Levels 1-6 failed)
```

### What To Do
- Start with `screen_capture.py` and `accessibility.py` — they're the foundation
- Use `comtypes` for IUIAutomation (already in ARCHITECTURE_DELTA.md spec)
- `state_builder.py` should produce a `ComputerState` dataclass with: active window, visible windows, processes, monitors, cursor pos, focused element, clipboard metadata

### What NOT To Do
- ❌ Do NOT hardcode screen coordinates — EVER
- ❌ Do NOT use image-only perception as primary — UIA/accessibility first
- ❌ Do NOT import heavy ML models at module level — lazy load only
- ❌ Do NOT make perception calls without checking KillSwitch first

---

## 16. Phase 12 — Verification Engine (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

### New Directory: `core/verification/`

| File | Purpose |
|------|---------|
| `core/verification/__init__.py` | Package marker |
| `core/verification/engine.py` | Central engine: before/after state diff → SUCCESS/FAILURE/UNKNOWN |
| `core/verification/window_verifier.py` | Window title, focus, presence |
| `core/verification/process_verifier.py` | Process launch, exit code |
| `core/verification/element_verifier.py` | UI element state change |
| `core/verification/text_verifier.py` | Expected text presence |
| `core/verification/url_verifier.py` | Browser URL change |
| `core/verification/file_verifier.py` | File creation/modification/hash |
| `core/verification/state_diff_verifier.py` | Holistic ComputerState diff |

### What To Do
- Every verifier returns strictly `SUCCESS`, `FAILURE`, or `UNKNOWN`
- `engine.py` aggregates multiple verifier results
- Integrate with existing `ReconciliationEngine` for file-level verification

### What NOT To Do
- ❌ Do NOT return approximate/fuzzy results — be deterministic
- ❌ Do NOT skip verification even if action "seemed" to work

---

## 17. Phase 13 — HUD Task Widget & Dashboard (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

### What To Do
- Create `ui/components/task_list_widget.py` — PyQt6 widget showing live TaskQueue items
- Integrate with existing `ui.py` (the main HUD)
- Show: task name, assigned agent, status (queued/running/done/failed), elapsed time
- Wire the existing `dashboard/server.py` to expose agent registry status as JSON

### What NOT To Do
- ❌ Do NOT build a separate dashboard web app — extend the existing one
- ❌ Do NOT block the Qt main thread with database queries

---

## 18. Phase 14 — Dead Code Cleanup (DONE)

> ✅ **STATUS: COMPLETE — All deprecation notices in place**

### Files to Review and Clean

| File | Status | Action |
|------|--------|--------|
| `core/stt.py` | Referenced but unused | Remove or mark deprecated |
| `core/tts.py` | Referenced but unused | Remove or mark deprecated |
| `core/llm_client.py` | Referenced but unused | Remove or mark deprecated |
| `core/installer.py` | Referenced but unused | Remove or mark deprecated |

### What To Do
1. `grep -r` for all imports of these modules across the codebase
2. If truly dead (no runtime callers), add a `# DEPRECATED` header with removal date
3. Do NOT delete yet — deprecate first, remove in next release cycle

### What NOT To Do
- ❌ Do NOT delete files without checking ALL import paths first
- ❌ Do NOT remove `core/stt.py` if wake word detection depends on it

---

## 19. Phase 15 — Integration & E2E Tests (DONE)

> ✅ **STATUS: COMPLETE — All tests passing**

### Integration Tests (`tests/integration/`)

| Test | What It Validates |
|------|-------------------|
| `test_dual_lane.py` | Lane A/B routing through ReflexIntentRouter |
| `test_agent_lifecycle.py` | Full agent run with KillSwitch, CircuitBreaker, Snapshot, Locks |
| `test_task_queue_to_agent.py` | TaskQueue → Agent selection → Execution → StateDB recording |
| `test_reflex_to_guardrails.py` | Laya decision → risk tier → confirmation gate |
| `test_memory_integration.py` | MemoryContextHeap with existing memory_manager.py |

### E2E Tests (`tests/e2e/`)

| Test | What It Validates |
|------|-------------------|
| `test_voice_to_agent.py` | Mocked Gemini session → tool call → agent → response |
| `test_kill_switch_cascade.py` | Kill switch trips → all agents halt → snapshots rollback |
| `test_full_task_flow.py` | Input → Triage → Queue → Lock → Execute → Verify → Done |

### What NOT To Do
- ❌ Do NOT write E2E tests that require a live Gemini API key — always mock
- ❌ Do NOT write tests that depend on specific file paths outside the temp directory
- ❌ Do NOT write tests that depend on network access

---

## 20. DO NOT DO — Anti-Patterns & Constraints

> **This section is CRITICAL. Violating any of these will break the system.**

### Architecture Anti-Patterns

| # | DO NOT | Why |
|---|--------|-----|
| 1 | ❌ Do NOT bypass `BaseAgent.run()` lifecycle | Every agent MUST go through KillSwitch → CircuitBreaker → Snapshot → Locks → Reconciliation. Calling `_execute()` directly skips all safety guarantees. |
| 2 | ❌ Do NOT introduce hosted service dependencies in Laya | Laya's AGENTS.md explicitly states: "Do NOT introduce dependency on hosted service. Features must run locally." |
| 3 | ❌ Do NOT store secrets in code files | Always use `Vault` (`core/max_infra/vault.py`). Never hardcode API keys, tokens, or passwords. |
| 4 | ❌ Do NOT modify `core/confirm.py` callback design | Its non-blocking `request()` / `resolve()` pattern is load-bearing for the HUD. Changing it breaks the async UI flow. |
| 5 | ❌ Do NOT create more than 1 KillSwitch instance | It's a singleton by design. Using `KillSwitch()` constructor creates a second instance. Always use `KillSwitch.get_instance()`. |
| 6 | ❌ Do NOT hold LockManager's Condition across yield | This was a real deadlock bug. The `acquire()` context manager must release the internal condition before yielding. |
| 7 | ❌ Do NOT import heavy models at module level | Laya, ONNX, vision models — all must be lazy-loaded. Import-time model loading adds 10+ seconds to startup. |
| 8 | ❌ Do NOT use bare `pytest` command | On this system, pytest is not on PATH. Always use `python -m pytest`. |
| 9 | ❌ Do NOT block the asyncio event loop | Agent execution, file I/O, database calls — ALL go through `loop.run_in_executor()`. |
| 10 | ❌ Do NOT remove the existing `actions/` tool system | Agents are ADDITIVE to the existing action/plugin registries. Old tools must continue working. |

### Code Quality Rules

| # | DO NOT | Do Instead |
|---|--------|------------|
| 11 | ❌ Do NOT use `print()` for logging in new code | Use `logging.getLogger("max.module_name")` |
| 12 | ❌ Do NOT use mutable default arguments | Use `Field(default_factory=...)` for Pydantic, `None` + ternary for functions |
| 13 | ❌ Do NOT catch bare `Exception` silently | Always log the exception. Re-raise if it's a KillSwitch `SystemExit`. |
| 14 | ❌ Do NOT write tests that modify global state | Each test must clean up after itself (use fixtures, tmpdir, fresh instances) |
| 15 | ❌ Do NOT create circular imports between agents | Agents import from `agents.base` and `core.*` only. Never import one agent from another. |

### Scope Constraints

| # | DO NOT | Why |
|---|--------|-----|
| 16 | ❌ Do NOT build multi-node networking | Out of scope per ARCHITECTURE.md §9. Single machine only for v1. |
| 17 | ❌ Do NOT implement Linux/macOS perception | Windows only for v1. `IPerceptionProvider` interface is for future. |
| 18 | ❌ Do NOT build a custom LLM | Use Gemini via the existing `genai` client. Laya is for routing, not generation. |
| 19 | ❌ Do NOT add new pip dependencies without checking | Every new dep must be justified. Prefer stdlib. Check `setup.py` first. |
| 20 | ❌ Do NOT modify `main.py` lines 1-36 | The subprocess patching and console encoding blocks are critical Windows fixes. |

---

## 21. File Map — All Existing & Planned Files

### Legend
- ✅ = Implemented and tested
- 🔲 = Planned, not yet implemented
- 📌 = Existing CyberBlack AI-agent MAX (do not modify)

```
F:\Mark-LIII-main\Mark-LIII-main\
│
├── main.py                              📌 Entry point (modify only in Phase 10)
├── ui.py                                📌 PyQt6 HUD (modify only in Phase 13)
├── setup.py                             📌 Package setup
├── IMPLEMENTATION_PLAN.md               ✅ This file
│
├── core/
│   ├── __init__.py                      📌
│   ├── action_loader.py                 📌 Auto-discovers actions/*.py
│   ├── audio_devices.py                 📌 Audio device resolution
│   ├── confirm.py                       📌 DO NOT MODIFY — callback confirm gate
│   ├── installer.py                     📌 Review for deprecation (Phase 14)
│   ├── llm_client.py                    📌 Review for deprecation (Phase 14)
│   ├── plugin_loader.py                 📌 Plugin discovery
│   ├── stt.py                           📌 Review for deprecation (Phase 14)
│   ├── tts.py                           📌 Review for deprecation (Phase 14)
│   ├── undo.py                          📌 Push-based undo stack (integrated with Snapshot)
│   ├── wake_word.py                     📌 OpenWakeWord detector
│   │
│   ├── max_infra/
│   │   ├── __init__.py                  ✅
│   │   ├── kill_switch.py               ✅ Component #0
│   │   ├── schema.sql                   ✅ 7-table DDL
│   │   ├── state_db.py                  ✅ SQLite WAL state manager
│   │   ├── vault.py                     ✅ Secret storage
│   │   ├── data_boundary.py             ✅ PII/key scrubber
│   │   ├── task_lifecycle.py            ✅ FSM state machine
│   │   ├── task_queue.py                ✅ Priority queue
│   │   ├── lock_manager.py              ✅ Sorted deadlock-free locks
│   │   ├── snapshot.py                  ✅ Atomic file backup/rollback
│   │   ├── circuit_breaker.py           ✅ 3-strike fault tolerance
│   │   ├── watchdog.py                  ✅ Heartbeat daemon
│   │   └── reconciliation.py            ✅ OS truth verifier
│   │
│   ├── reflex/
│   │   ├── __init__.py                  ✅
│   │   ├── laya_engine.py               ✅ Laya Router wrapper
│   │   ├── intent_router.py             ✅ Lane A/B routing
│   │   ├── guardrails.py                ✅ 4-tier risk classification
│   │   └── triage.py                    ✅ 5-band priority scoring
│   │
│   ├── memory/
│   │   ├── __init__.py                  ✅
│   │   ├── context_heap.py              ✅ 5-layer memory
│   │   └── token_budget.py              ✅ Prompt budget compressor
│   │
│   ├── perception/                      ✅ Phase 11
│   │   ├── __init__.py                  ✅
│   │   ├── screen_capture.py            ✅
│   │   ├── accessibility.py             ✅
│   │   ├── browser_dom.py               ✅
│   │   ├── text_detection.py            ✅
│   │   ├── element_detection.py         ✅
│   │   ├── ui_detection.py              ✅
│   │   └── state_builder.py             ✅
│   │
│   └── verification/                    ✅ Phase 12
│       ├── __init__.py                  ✅
│       ├── engine.py                    ✅
│       ├── window_verifier.py           ✅
│       ├── process_verifier.py          ✅
│       ├── element_verifier.py          ✅
│       ├── text_verifier.py             ✅
│       ├── url_verifier.py              ✅
│       ├── file_verifier.py             ✅
│       └── state_diff_verifier.py       ✅
│
├── agents/
│   ├── __init__.py                      ✅
│   ├── base.py                          ✅ BaseAgent lifecycle envelope
│   ├── router.py                        ✅ AgentRegistry singleton
│   │
│   ├── core/                            ✅ Cluster 1: Core Reasoning (5/5)
│   │   ├── __init__.py                  ✅
│   │   ├── orchestrator.py              ✅ MasterOrchestrator
│   │   ├── planner.py                   ✅ DecompositionPlanner
│   │   ├── verifier.py                  ✅ ValidationVerifier
│   │   ├── model_router.py              ✅ ModelRouter
│   │   └── critic.py                    ✅ AdversarialCritic
│   │
│   ├── software/                        ✅ Cluster 2: Software Delivery (8/8)
│   │   ├── __init__.py                  ✅
│   │   ├── coding_agent.py              ✅
│   │   ├── code_reviewer.py             ✅
│   │   ├── test_writer.py               ✅
│   │   ├── devops_agent.py              ✅
│   │   ├── db_agent.py                  ✅
│   │   ├── api_designer.py              ✅
│   │   ├── doc_writer.py                ✅
│   │   └── dependency_mgr.py            ✅
│   │
│   ├── productivity/                    ✅ Cluster 3: Founder Productivity (8/8)
│   │   ├── __init__.py                  ✅
│   │   ├── email_agent.py               ✅
│   │   ├── calendar_agent.py            ✅
│   │   ├── comms_agent.py               ✅
│   │   ├── research_agent.py            ✅
│   │   ├── file_organizer.py            ✅
│   │   ├── notes_agent.py               ✅
│   │   ├── task_tracker.py              ✅
│   │   └── meeting_prep.py              ✅
│   │
│   ├── safety/                          ✅ Cluster 4: Safety & Input Control (6/6)
│   │   ├── __init__.py                  ✅
│   │   ├── computer_use.py              ✅
│   │   ├── desktop_agent.py             ✅
│   │   ├── browser_agent.py             ✅
│   │   ├── input_arbiter.py             ✅
│   │   ├── security_gate.py             ✅
│   │   └── recovery_engine.py           ✅
│   │
│   └── health/                          ✅ Cluster 5: Infrastructure & Health (6/6)
│       ├── __init__.py                  ✅
│       ├── system_monitor.py            ✅
│       ├── network_agent.py             ✅
│       ├── backup_agent.py              ✅
│       ├── update_agent.py              ✅
│       ├── performance_agent.py         ✅
│       └── health_check.py              ✅
│
├── actions/                             📌 Existing tool system (DO NOT REMOVE)
│   ├── background_monitor.py            📌
│   ├── browser_control.py               📌
│   ├── code_helper.py                   📌
│   ├── computer_control.py              📌
│   ├── computer_settings.py             📌
│   ├── desktop.py                       📌
│   ├── dev_agent.py                     📌
│   ├── file_controller.py              📌
│   ├── file_processor.py               📌
│   ├── flight_finder.py                📌
│   ├── game_updater.py                 📌
│   ├── open_app.py                     📌
│   ├── proactive.py                    📌
│   ├── reminder.py                     📌
│   ├── screen_processor.py             📌
│   ├── send_message.py                 📌
│   ├── system_monitor.py               📌
│   ├── weather_report.py               📌
│   ├── web_search.py                   📌
│   └── youtube_video.py                📌
│
├── memory/
│   ├── config_manager.py                📌
│   └── memory_manager.py               📌
│
├── config/
│   └── __init__.py                      📌
│
├── dashboard/
│   ├── __init__.py                      📌
│   └── server.py                        📌
│
├── plugins/
│   ├── __init__.py                      📌
│   └── _template.py                     📌
│
├── ui/
│   └── components/
│       └── task_list_widget.py          ✅ Phase 13
│
├── temp_laya/                           📌 Laya source (editable install)
│
├── tests/
│   ├── unit/
│   │   ├── test_kill_switch.py          ✅ 2 tests
│   │   ├── test_state_db.py             ✅ 3 tests
│   │   ├── test_vault.py                ✅ 2 tests
│   │   ├── test_data_boundary.py        ✅ 2 tests
│   │   ├── test_laya_engine.py          ✅ 3 tests
│   │   ├── test_intent_router.py        ✅ 3 tests
│   │   ├── test_guardrails_triage.py    ✅ 4 tests
│   │   ├── test_task_lifecycle.py       ✅ 3 tests
│   │   ├── test_task_queue.py           ✅ 3 tests
│   │   ├── test_lock_manager.py         ✅ 2 tests
│   │   ├── test_snapshot.py             ✅ 2 tests
│   │   ├── test_resilience.py           ✅ 3 tests
│   │   ├── test_context_heap.py         ✅ 2 tests
│   │   ├── test_confirm_undo.py         ✅ 2 tests
│   │   ├── test_agent_base.py           ✅ 2 tests
│   │   ├── test_cluster_core.py         ✅ 1 test
│   │   ├── test_cluster_software.py     ✅ 2 tests
│   │   ├── test_cluster_productivity.py ✅ 2 tests
│   │   ├── test_cluster_safety.py       ✅ 2 tests
│   │   ├── test_cluster_health.py       ✅ 2 tests
│   │   ├── test_perception.py           ✅ 7 tests
│   │   ├── test_verification.py         ✅ 7 tests
│   │   ├── test_ui_widget.py            ✅ 1 test
│   │   └── test_dashboard_agents.py     ✅ 1 test
│   │
│   ├── integration/
│   │   ├── test_dual_lane.py            ✅ 4 tests
│   │   ├── test_agent_lifecycle.py      ✅ 1 test
│   │   ├── test_task_queue_to_agent.py  ✅ 1 test
│   │   ├── test_reflex_to_guardrails.py ✅ 1 test
│   │   └── test_memory_integration.py   ✅ 1 test
│   │
│   └── e2e/
│       ├── test_voice_to_agent.py       ✅ 1 test
│       ├── test_kill_switch_cascade.py  ✅ 1 test
│       └── test_full_task_flow.py       ✅ 1 test
│
└── docs/
    └── plans/
        └── 2026-09-29-master-ai-agents-os-plan.md  📌 Earlier TDD plan
```

---

## 22. Testing Strategy

### Test Pyramid

```
        ╱╲
       ╱ E2E ╲          3 tests — mock Gemini, full flow
      ╱────────╲
     ╱Integration╲       5 tests — component interaction
    ╱──────────────╲
   ╱   Unit Tests   ╲    39+ tests — each module in isolation
  ╱──────────────────╲
```

### Rules
1. **Always run tests with**: `python -m pytest tests/ -v`
2. **Never use bare `pytest`** — it's not on PATH
3. Every new module gets tests BEFORE or WITH implementation
4. Tests must not depend on:
   - Network access
   - Live API keys
   - Specific file paths outside tmpdir
   - Global mutable state (clean up after each test)
5. Use `tmp_path` fixture for file operations
6. Use `unittest.mock.patch` for external dependencies

### Coverage Targets
| Layer | Target |
|-------|--------|
| `core/max_infra/` | 90%+ |
| `core/reflex/` | 85%+ |
| `core/memory/` | 85%+ |
| `agents/` | 80%+ |
| `core/perception/` | 70%+ (hardware-dependent) |
| Integration | 5+ key paths |
| E2E | 3+ critical flows |

---

## 23. Dependencies & Environment

### Current Environment
- **Python**: 3.11.5 (global install, not virtualenv)
- **OS**: Windows
- **Key packages**: PyQt6, google-genai, sounddevice, numpy, pydantic
- **Laya**: v0.3.21 (editable install from `temp_laya/`)

### Required for Future Phases

| Phase | Package | Purpose |
|-------|---------|---------|
| 11 | `comtypes` | IUIAutomation COM wrapper |
| 11 | `pywinauto` | Windows UI automation |
| 11 | `Pillow` | Screenshot capture |
| 12 | `pyautogui` | Coordinate-based fallback (Level 7 only) |
| 11 | `pytesseract` | OCR fallback (Level 5) |

### What NOT To Install
- ❌ No `selenium` — use Playwright/CDP if browser automation needed
- ❌ No `celery` or `redis` — we use the built-in `TaskQueue`
- ❌ No `flask` — existing dashboard uses `fastapi`
- ❌ No hosted AI services — Laya must run locally per its AGENTS.md

---

## SUMMARY: Implementation Order

```
✅ DONE ─── Phase 1: Infrastructure Floor (KillSwitch, StateDB, Vault, DataBoundary)
✅ DONE ─── Phase 2: Reflex Engine (LayaEngine, IntentRouter, Guardrails, Triage)
✅ DONE ─── Phase 3: Task Engine (FSM, TaskQueue, LockMgr, Snapshot, Circuit, Watchdog)
✅ DONE ─── Phase 4: Memory & Confirm (ContextHeap, TokenBudget, Confirm/Undo bridge)
✅ DONE ─── Phase 5: Core Cluster (BaseAgent, Registry, 5 core agents)
✅ DONE ─── Phase 6: Software Delivery Cluster (8 agents)
✅ DONE ─── Phase 7: Productivity Cluster (8 agents)
✅ DONE ─── Phase 8: Safety Cluster (6 agents)
✅ DONE ─── Phase 9: Health Cluster (6 agents)
✅ DONE ─── Phase 10: Dual-Lane main.py Wiring ← CRITICAL INTEGRATION
✅ DONE ─── Phase 11: Perception Engine (screen/UIA/DOM/OCR)
✅ DONE ─── Phase 12: Verification Engine (state diff)
✅ DONE ─── Phase 13: HUD Task Widget & Dashboard API
✅ DONE ─── Phase 14: Dead Code Cleanup
✅ DONE ─── Phase 15: Integration & E2E Tests
```

> **ALL PHASES COMPLETE: All 33 agents registered across 5 clusters, dual-lane voice wiring complete, Perception and Verification engines online, 74/74 unit, integration, and E2E tests passing.**


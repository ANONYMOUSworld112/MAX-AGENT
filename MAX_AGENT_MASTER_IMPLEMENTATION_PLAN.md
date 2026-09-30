# MAX-AGENT — Master Implementation Plan
## Synthesized from All Forensic Audit & Evolution Documents

> **Created**: 2026-09-30  
> **Baseline Branch**: `max/p0-baseline` (commit `117c9b7`)  
> **Source Documents**: 18 audit reports, 6 evolution benchmarks, threat model, component map, conflict log, unchoked side-effects inventory, progress tracker  
> **Governing Authority**: Master Engineering Specification v2 (Authority Order: Safety > Honesty > Preservation > Features > Style)

---

## How to Read This Plan

Each phase is **gated**: you cannot start Phase N+1 until Phase N passes its acceptance criteria and receives owner approval. Every task lists:

- **What**: The concrete engineering work
- **Why**: The audit finding or evolution gap driving it
- **Files**: Source files to create or modify
- **Tests**: Automated verification of the deliverable
- **Depends On**: Prior phases or tasks that must be complete
- **Acceptance Criteria**: The measurable gate condition
- **Risk**: What could go wrong
- **Audit Source**: The specific document(s) that identified this need

---

## Phase Overview & Dependency Graph

```
PHASE 0 ─── COMPLETE (Forensic Audit & Baseline)
    │
    ▼
PHASE 1 ─── Foundations: Data Contracts, State Machine, ExecutionGateway
    │
    ├──────────────────────┬────────────────────┐
    ▼                      ▼                    ▼
PHASE 2                PHASE 5              PHASE 6
Task Planning &        Scheduler &          Memory &
Agent Routing          Resource Leases      Context Hardening
    │                      │                    │
    ├──────────┐           │                    │
    ▼          ▼           │                    │
PHASE 3    PHASE 4         │                    │
Desktop    Coding          │                    │
Automation Workflow        │                    │
    │          │           │                    │
    └──────────┴───────────┴────────────────────┘
                    │
                    ▼
               PHASE 7
           ProcessManager &
           Security Hardening
                    │
                    ▼
               PHASE 8
           Verification Engine &
           Self-Correction
                    │
                    ▼
               PHASE 9
           Provider Abstraction
           (Local/Cloud Models)
                    │
                    ▼
               PHASE 10
           Advanced Agentic
           Capabilities
                    │
                    ▼
               PHASE 11
           HUD Observability &
           Dashboard Hardening
                    │
                    ▼
               PHASE 12
           Final Integration &
           Acceptance Testing
```

---

## PHASE 0 — Forensic Audit & Baseline ✅ COMPLETE

**Status**: All deliverables committed on `max/p0-baseline`. 22/22 tests passing.

**Gate P0 Requires Owner Approval Of**:
- [COMPONENT_MAP.md](file:///f:/MAX-AGENT/docs/COMPONENT_MAP.md) (20 component disposition decisions)
- [CONFLICT_LOG.md](file:///f:/MAX-AGENT/docs/CONFLICT_LOG.md) (9 architectural conflicts CF-01 through CF-09)

**Upon approval**: `git tag gate-p0-approved && git checkout -b max/p1-foundations`

---

## PHASE 1 — Foundations: Data Contracts, State Machine & ExecutionGateway

> **Priority**: P0 (Critical)  
> **Branch**: `max/p1-foundations`  
> **Resolves Conflicts**: CF-02, CF-05, CF-06 (partial)  
> **Audit Sources**: [ARCHITECTURE_REAL.md](file:///f:/MAX-AGENT/docs/ARCHITECTURE_REAL.md), [SECURITY.md](file:///f:/MAX-AGENT/docs/audit/SECURITY.md), [UNCHOKED_SIDE_EFFECTS.md](file:///f:/MAX-AGENT/docs/UNCHOKED_SIDE_EFFECTS.md), [IMPROVEMENT_MATRIX.md](file:///f:/MAX-AGENT/docs/evolution/IMPROVEMENT_MATRIX.md)

### Task 1.1 — Data Contracts: `TaskIntent` and `Task`
- **What**: Define immutable data models for all task representations.
- **Why**: Current system has no `Task` object; tool calls are ephemeral strings in Gemini `FunctionCall.args` ([TASK_LIFECYCLE.md](file:///f:/MAX-AGENT/docs/audit/TASK_LIFECYCLE.md)).
- **Files**:
  - Create `core/contracts.py` — `TaskIntent`, `Task`, `TaskResult`, `ActionRequest`, `ActionResult`, `EventEnvelope` dataclasses
- **Tests**:
  - `tests/unit/test_contracts.py` — Schema validation, serialization round-trip, required field enforcement
- **Acceptance Criteria**: All data contracts serialize/deserialize to JSON; type hints pass `mypy --strict`

### Task 1.2 — 14-State Task State Machine
- **What**: Replace the dormant 9-state FSM with the Master Spec's 14-state machine.
- **Why**: Current `core/max_infra/task_lifecycle.py` has 9 states. Master Spec Section 8 requires 14 states: `CREATED → PLANNED → QUEUED → BLOCKED → RUNNING → VERIFYING → RETRYING → PAUSED → CANCELLING → INTERRUPTED → COMPLETED → FAILED → CANCELLED → EXPIRED`. Conflict CF-02.
- **Files**:
  - Create `core/state_machine.py` — `TaskStateMachine` with explicit transition table, `blocked_reason` enum, terminal states
  - Retain `core/max_infra/task_lifecycle.py` behind feature flag for backward compatibility
- **Tests**:
  - `tests/unit/test_state_machine.py` — All legal transitions succeed; all illegal transitions raise `InvalidStateTransitionError`; terminal states reject further transitions; `blocked_reason` required for `BLOCKED` state
- **Acceptance Criteria**: 100% transition coverage; existing Tier 0 tests still pass

### Task 1.3 — Injectable `Clock`
- **What**: Abstract time access behind an injectable `Clock` interface.
- **Why**: Task deadlines, scheduler aging, TTL expirations, and DST handling all need deterministic time in tests ([ROADMAP.md](file:///f:/MAX-AGENT/docs/evolution/ROADMAP.md) Phase 1).
- **Files**:
  - Create `core/clock.py` — `Clock` protocol with `now() -> datetime`, `monotonic() -> float`; `SystemClock` and `FakeClock` implementations
- **Tests**:
  - `tests/unit/test_clock.py` — `FakeClock` advances deterministically; `SystemClock` returns real wall time
- **Acceptance Criteria**: All time-dependent modules accept `Clock` parameter

### Task 1.4 — `EventEnvelope` and Append-Only Audit Log
- **What**: Implement structured event recording with SHA-256 hash chaining.
- **Why**: Current observability is `print()` to stdout ([OBSERVABILITY.md](file:///f:/MAX-AGENT/docs/audit/OBSERVABILITY.md)). The `audit_log` SQLite schema exists in `core/max_infra/schema.sql` but is never populated.
- **Files**:
  - Create `core/events.py` — `EventBus` with in-memory pub/sub and backpressure; `AuditWriter` persisting to `StateDB.audit_log` with `prev_hash` chaining
  - Extend `core/max_infra/state_db.py` — Wire `audit_log` table writes
- **Tests**:
  - `tests/unit/test_events.py` — Event publish/subscribe; hash chain integrity verification; backpressure test
- **Acceptance Criteria**: Every emitted event is persisted with a valid hash chain; `SELECT * FROM audit_log` returns ordered events

### Task 1.5 — `ExecutionGateway` and `PolicyEngine`
- **What**: Build the single choke point for all side-effect execution.
- **Why**: 37 unchoked side-effect paths across 16 files ([UNCHOKED_SIDE_EFFECTS.md](file:///f:/MAX-AGENT/docs/UNCHOKED_SIDE_EFFECTS.md)). Conflict CF-05. Codex comparison demands approval boundaries ([CODEX_COMPARISON.md](file:///f:/MAX-AGENT/docs/evolution/CODEX_COMPARISON.md)).
- **Files**:
  - Create `core/gateway.py` — `ExecutionGateway` class: validates `ActionRequest` schema → computes risk tier via `PolicyEngine` → checks resource lease → applies confirmation gate → executes with timeout → captures `ActionResult` → emits audit event
  - Create `core/policy.py` — `PolicyEngine` with risk classification table (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`) and confirmation requirements per channel trust level
- **Tests**:
  - `tests/unit/test_gateway.py` — LOW auto-executes; MEDIUM requires confirmation; HIGH requires trusted-channel confirmation; CRITICAL requires typed phrase; unknown action rejected
  - `tests/unit/test_policy.py` — Risk table coverage for all known action categories
- **Acceptance Criteria**: Gateway rejects uncategorized actions; policy table covers all existing action names

### Task 1.6 — Banned-Import AST Scanner
- **What**: Automated test that fails the build if dangerous imports appear outside adapter modules.
- **Why**: Master Spec Section 13 prohibits direct imports of `subprocess`, `os.system`, `os.startfile`, `pyautogui`, `pywinauto`, `keyboard`, `ctypes.windll`, `shutil.rmtree` outside the adapter package ([SECURITY.md](file:///f:/MAX-AGENT/docs/audit/SECURITY.md)).
- **Files**:
  - Create `tests/test_banned_imports.py` — AST scan of all `.py` files; allowlist for `core/adapters/` and `core/process_manager.py`
- **Tests**: Self-verifying (the test IS the deliverable)
- **Acceptance Criteria**: Test currently fails (proving the 37 violations exist); will progressively pass as actions migrate to adapters
- **Note**: This test is intentionally expected to fail initially — it documents the migration backlog

### Task 1.7 — Tag Mock Agents `[NOT IMPLEMENTED]`
- **What**: Modify `BaseAgent._execute()` to raise `NotImplementedError` instead of returning fake `success=True`.
- **Why**: All 33 agents violate Rule 1-H1 (Honesty) by returning `AgentOutput(success=True)` while performing zero real work ([AGENT_REGISTRY_AUDIT.md](file:///f:/MAX-AGENT/docs/audit/AGENT_REGISTRY_AUDIT.md)). Conflict CF-04.
- **Files**:
  - Modify `agents/base.py` — Default `_execute()` raises `NotImplementedError("Agent not implemented")`
  - Modify all 33 agent files — Remove hardcoded return dictionaries; keep tool schema definitions intact
- **Tests**:
  - Update `tests/tier0_characterization/test_reflex_and_agents.py` — Verify agents raise `NotImplementedError`
- **Acceptance Criteria**: Calling any unimplemented agent raises `NotImplementedError`; agent schemas remain registered in `AgentRegistry`

### Phase 1 Gate
- [ ] All Phase 1 unit tests pass
- [ ] Existing 22 Tier 0 tests still pass (preservation)
- [ ] `ExecutionGateway` is importable and functional
- [ ] `TaskStateMachine` enforces 14-state transitions
- [ ] Owner approves → `git tag gate-p1-approved`

---

## PHASE 2 — Task Planning, Capability Registry & Agent Routing

> **Priority**: P1 (High)  
> **Branch**: `max/p2-routing`  
> **Depends On**: Phase 1  
> **Audit Sources**: [AGENT_ASSIGNMENT.md](file:///f:/MAX-AGENT/docs/audit/AGENT_ASSIGNMENT.md), [TOOL_FORENSICS.md](file:///f:/MAX-AGENT/docs/audit/TOOL_FORENSICS.md), [IMPROVEMENT_MATRIX.md](file:///f:/MAX-AGENT/docs/evolution/IMPROVEMENT_MATRIX.md)

### Task 2.1 — `CapabilityRegistry` Extension
- **What**: Extend `ActionRegistry` into a full `CapabilityRegistry` with parameter schemas, declared resources, idempotency class, postcondition template, base risk level, and verification method.
- **Why**: Current 60+ flat tool schemas pollute the LLM's reasoning space and cause hallucinated tool calls ([TOOL_FORENSICS.md](file:///f:/MAX-AGENT/docs/audit/TOOL_FORENSICS.md)).
- **Files**:
  - Extend `core/action_loader.py` → `core/capability_registry.py` with `CapabilityEntry` dataclass
- **Tests**:
  - `tests/unit/test_capability_registry.py` — All registered capabilities have valid schemas; postcondition templates are parseable
- **Acceptance Criteria**: Registry returns structured `CapabilityEntry` for every registered action and agent

### Task 2.2 — Schema-Constrained Intent Parsing (Fast Path + Full Path)
- **What**: Two-stage intent pipeline replacing flat tool array exposure.
  - **Fast Path** (80% of voice commands): Single schema-constrained model call mapping utterance to validated `TaskIntent`
  - **Full Path** (compound requests): Multi-step decomposer producing a `TaskGraph` DAG
- **Why**: LLM picks from 60+ tools non-deterministically; 0% explainability ([AGENT_ASSIGNMENT.md](file:///f:/MAX-AGENT/docs/audit/AGENT_ASSIGNMENT.md)).
- **Files**:
  - Create `core/intent_engine.py` — Fast-path schema decoder + full-path `TaskPlanner`
  - Create `core/plan_validator.py` — Validates task graphs (cycle detection, capability existence, budget checks)
- **Tests**:
  - `tests/unit/test_intent_engine.py` — Fast-path parses "Open Chrome" into `TaskIntent(action=open_app, target=chrome)`
  - `tests/unit/test_plan_validator.py` — Cyclic graphs rejected; over-budget graphs rejected; nonexistent capabilities rejected
- **Acceptance Criteria**: 95%+ routing accuracy on the 25 golden tasks (up from 76%)

### Task 2.3 — Deterministic `AgentRouter`
- **What**: Replace probabilistic LLM tool selection with a deterministic 5-step routing algorithm.
- **Why**: Agent selection is currently cloud-LLM-driven with zero determinism or explainability ([AGENT_ASSIGNMENT.md](file:///f:/MAX-AGENT/docs/audit/AGENT_ASSIGNMENT.md)).
- **Files**:
  - Rewrite `agents/router.py` — 5-step: Capability match → Circuit breaker filter → Priority ranking → Resource check → Write `RoutingDecision` audit record
- **Tests**:
  - `tests/unit/test_agent_router.py` — Correct agent selected for each golden task; tie-breaking is deterministic; broken agent is circuit-broken
- **Acceptance Criteria**: Every routing decision produces a `RoutingDecision` audit record; routing accuracy ≥ 95%

### Task 2.4 — `TaskGraph` Engine
- **What**: DAG data structure for multi-step task decomposition with conditional edges (`on_success`, `on_failure`, `always`).
- **Why**: 0% multi-task support rate in baseline evaluation ([evals_baseline.json](file:///f:/MAX-AGENT/docs/evidence/p0/evals_baseline.json)). No task graph exists anywhere in codebase ([IMPROVEMENT_MATRIX.md](file:///f:/MAX-AGENT/docs/evolution/IMPROVEMENT_MATRIX.md)).
- **Files**:
  - Create `core/task_graph.py` — `TaskGraph`, `TaskNode`, `TaskEdge` with topological sort, expansion budget, and serialization to/from `StateDB`
- **Tests**:
  - `tests/unit/test_task_graph.py` — Topological ordering; cycle detection; conditional edge execution; serialization round-trip; expansion budget enforcement
- **Acceptance Criteria**: "Build project and remind me at 8" decomposes into a 2-node parallel graph

### Phase 2 Gate
- [ ] All Phase 2 unit tests pass
- [ ] Routing accuracy ≥ 95% on golden tasks
- [ ] Multi-task compound requests decompose into valid graphs
- [ ] Owner approves → `git tag gate-p2-approved`

---

## PHASE 3 — Desktop Automation & Application Launch Reliability

> **Priority**: P0/P1  
> **Branch**: `max/p3-desktop`  
> **Depends On**: Phase 1, Phase 2  
> **Resolves Conflicts**: CF-06  
> **Audit Sources**: [DESKTOP_AUTOMATION.md](file:///f:/MAX-AGENT/docs/audit/DESKTOP_AUTOMATION.md), [VERIFICATION.md](file:///f:/MAX-AGENT/docs/audit/VERIFICATION.md), [THREAT_MODEL.md](file:///f:/MAX-AGENT/docs/THREAT_MODEL.md) T1

### Task 3.1 — Eliminate `exec()` RCE in `desktop.py`
- **What**: Remove `exec(compile(code, "<max_desktop>", "exec"), sandbox)` from `actions/desktop.py:97`.
- **Why**: CRITICAL RCE vulnerability — LLM-generated Python code runs with full host privileges including `ctypes` and `pyautogui` ([SECURITY.md](file:///f:/MAX-AGENT/docs/audit/SECURITY.md), [THREAT_MODEL.md](file:///f:/MAX-AGENT/docs/THREAT_MODEL.md) T1). Conflict CF-06.
- **Files**:
  - Modify `actions/desktop.py` — Replace `exec()` with parameterized automation primitives (`click(x,y)`, `type_text(text)`, `hotkey(keys)`)
- **Tests**:
  - `tests/unit/test_desktop_no_exec.py` — AST scan confirms zero `exec()` calls in `actions/desktop.py`
- **Acceptance Criteria**: `exec()` is completely absent from `actions/desktop.py`

### Task 3.2 — `WindowsDesktopAdapter` with UIA Semantic Targeting
- **What**: Build a platform adapter using Windows UI Automation (UIA) tree for element identification instead of blind coordinate clicks.
- **Why**: Current desktop automation sends blind `pyautogui.press('enter')` after clipboard paste into Windows Search — no process or window verification ([DESKTOP_AUTOMATION.md](file:///f:/MAX-AGENT/docs/audit/DESKTOP_AUTOMATION.md)).
- **Files**:
  - Create `core/adapters/windows_desktop.py` — UIA element finding, click, type, focus, window enumeration
  - Create `core/adapters/fake_desktop.py` — Test double for headless/CI environments
- **Tests**:
  - `tests/unit/test_fake_desktop.py` — Fake adapter records all calls; integration test with known apps (Calculator, Notepad)
- **Acceptance Criteria**: Desktop actions target elements by UIA name/control type, not raw screen coordinates

### Task 3.3 — `ApplicationRegistry` + Guarded Launch + L3 Verification
- **What**: Pre-resolved application signatures, guarded Windows Search flow, and post-launch verification using `psutil` process tables and `win32gui` window handles.
- **Why**: `open_app.py` returns `success=True` even when no process launches; opens Bing web search instead of installed apps ([VERIFICATION.md](file:///f:/MAX-AGENT/docs/audit/VERIFICATION.md)).
- **Files**:
  - Create `core/app_registry.py` — Known application signatures with executable paths, window class names, and process names
  - Modify `actions/open_app.py` — Use `ApplicationRegistry` for resolution; verify launch via `psutil.process_iter()` + `win32gui.EnumWindows()`
- **Tests**:
  - `tests/unit/test_app_launch.py` — Known app resolves to executable; unknown app returns `NOT_FOUND`; L3 verification checks process and window
- **Acceptance Criteria**: 95%+ first-try launch success on known apps; zero false-positive launch claims

### Task 3.4 — `UserActivityMonitor` (Desktop Input Conflict Guard)
- **What**: Detect when the human user is actively typing or clicking, and pause desktop automation.
- **Why**: Two agents cannot control the desktop simultaneously; human and bot input collide ([CONCURRENCY.md](file:///f:/MAX-AGENT/docs/audit/CONCURRENCY.md)).
- **Files**:
  - Create `core/user_activity.py` — Win32 `GetLastInputInfo()` polling; emits `user_active` / `user_idle` events
- **Tests**:
  - `tests/unit/test_user_activity.py` — Activity detected within threshold; idle detected after timeout
- **Acceptance Criteria**: Desktop automation pauses within 200ms of human input

### Phase 3 Gate
- [ ] Zero `exec()` calls in desktop automation
- [ ] Application launch achieves 95%+ verified success on known apps
- [ ] L3 verification checks process table and window handle before reporting success
- [ ] Owner approves → `git tag gate-p3-approved`

---

## PHASE 4 — Sandboxed Coding Workflow & CodingExecutor

> **Priority**: P0 (Critical)  
> **Branch**: `max/p4-coding`  
> **Depends On**: Phase 1, Phase 2  
> **Audit Sources**: [CODING_WORKFLOW.md](file:///f:/MAX-AGENT/docs/audit/CODING_WORKFLOW.md), [OPENCODE_COMPARISON.md](file:///f:/MAX-AGENT/docs/evolution/OPENCODE_COMPARISON.md), [THREAT_MODEL.md](file:///f:/MAX-AGENT/docs/THREAT_MODEL.md) T4

### Task 4.1 — `CodingExecutor` Interface
- **What**: Define abstract `CodingExecutor` protocol with `execute(CodingTask) -> CodingResult`.
- **Why**: Need provider-agnostic coding abstraction supporting OpenCode, Codex, Claude Code, and local agents ([OPENCODE_COMPARISON.md](file:///f:/MAX-AGENT/docs/evolution/OPENCODE_COMPARISON.md)).
- **Files**:
  - Create `core/coding/executor.py` — `CodingExecutor` protocol, `CodingTask`, `CodingResult` dataclasses
- **Tests**:
  - `tests/unit/test_coding_executor.py` — Protocol conformance test
- **Acceptance Criteria**: Interface is importable and type-checks with `mypy`

### Task 4.2 — Git Worktree Sandbox
- **What**: All coding tasks execute in disposable git worktrees with isolated virtualenvs.
- **Why**: `dev_agent.py` writes directly into `~/Desktop/MaxProjects/` and runs `pip install` on the host Python ([CODING_WORKFLOW.md](file:///f:/MAX-AGENT/docs/audit/CODING_WORKFLOW.md)). Supply-chain attack vector ([THREAT_MODEL.md](file:///f:/MAX-AGENT/docs/THREAT_MODEL.md) T4).
- **Files**:
  - Create `core/coding/sandbox.py` — `WorktreeSandbox` class: `git worktree add`, `python -m venv`, wall-clock timeout, scope check (`git diff --stat` confined to worktree)
- **Tests**:
  - `tests/unit/test_sandbox.py` — Scope check rejects edits outside worktree; sandbox teardown removes worktree; timeout kills hung processes
- **Acceptance Criteria**: All file writes during coding are confined to worktree; host Python environment unchanged

### Task 4.3 — `LocalDevWorker` (Replaces `dev_agent.py`)
- **What**: Internal coding worker implementing `CodingExecutor` that runs inside the sandbox.
- **Why**: Replace the unsandboxed `actions/dev_agent.py` pipeline.
- **Files**:
  - Create `core/coding/local_dev_worker.py` — Generates code via Gemini, writes into worktree sandbox, runs tests independently
  - Deprecate `actions/dev_agent.py` (retain file, mark `[DEPRECATED]`)
- **Tests**:
  - `tests/unit/test_local_dev_worker.py` — Generates a simple Python script; runs it in sandbox; verifies exit code
- **Acceptance Criteria**: Host `pip install` is never executed outside sandbox; test pass/fail is independently verified by MAX

### Task 4.4 — Independent Test Verification
- **What**: MAX independently runs the test suite and verifies exit codes, assertion counts, and logs — never trusts worker self-reports.
- **Why**: Claude-style verification principle: never trust agent self-reported success ([CLAUDE_STYLE_COMPARISON.md](file:///f:/MAX-AGENT/docs/evolution/CLAUDE_STYLE_COMPARISON.md)).
- **Files**:
  - Create `core/coding/test_verifier.py` — Parses pytest XML/JSON output; compares assertion counts; detects weakened tests
- **Tests**:
  - `tests/unit/test_test_verifier.py` — Detects test weakening (assertion count decreased); detects new test failures
- **Acceptance Criteria**: Coding task cannot report SUCCESS if test suite fails

### Phase 4 Gate
- [ ] All coding tasks run in isolated worktrees
- [ ] Host Python environment is never modified
- [ ] Test results are independently verified by MAX
- [ ] Owner approves → `git tag gate-p4-approved`

---

## PHASE 5 — Unified Scheduler & Resource Leases

> **Priority**: P1 (High)  
> **Branch**: `max/p5-scheduler`  
> **Depends On**: Phase 1  
> **Resolves Conflicts**: CF-08  
> **Audit Sources**: [TASK_LIFECYCLE.md](file:///f:/MAX-AGENT/docs/audit/TASK_LIFECYCLE.md), [CONCURRENCY.md](file:///f:/MAX-AGENT/docs/audit/CONCURRENCY.md), [IMPROVEMENT_MATRIX.md](file:///f:/MAX-AGENT/docs/evolution/IMPROVEMENT_MATRIX.md)

### Task 5.1 — `TaskScheduler` Backed by `StateDB`
- **What**: Unified scheduler with SQLite WAL persistence, priority aging, deadline enforcement, and restart recovery.
- **Why**: Current `TaskQueue` is in-memory and unused; `reminder.py` depends on Windows `schtasks.exe` which cannot recover task context ([TASK_LIFECYCLE.md](file:///f:/MAX-AGENT/docs/audit/TASK_LIFECYCLE.md)). Conflict CF-08.
- **Files**:
  - Create `core/scheduler.py` — `TaskScheduler` with injectable `Clock`, SQLite persistence, RRULE recurrence parsing (RFC 5545), misfire policies
- **Tests**:
  - `tests/unit/test_scheduler.py` — Task survives process restart; recurring RRULE generates correct next-fire times; DST fold/gap handling; misfire fires on next poll
- **Acceptance Criteria**: Reminders persist across MAX restarts; recurring rules fire correctly

### Task 5.2 — Resource Leases & `LockManager` Activation
- **What**: Connect the dormant `LockManager` with a canonical resource catalog.
- **Why**: `LockManager` exists but is called with `target_files=[]` — zero locks are ever acquired ([CONCURRENCY.md](file:///f:/MAX-AGENT/docs/audit/CONCURRENCY.md)).
- **Files**:
  - Extend `core/max_infra/lock_manager.py` — Add resource catalog: `desktop-input` (EXCLUSIVE), `project:<path>` (SHARED/EXCLUSIVE), `audio-out` (EXCLUSIVE), `gpu-vram` (SHARED)
  - Add heartbeat monitoring and lease expiration
- **Tests**:
  - `tests/unit/test_resource_leases.py` — Exclusive lease blocks concurrent access; lease expiry releases; heartbeat keeps alive
- **Acceptance Criteria**: Two tasks requiring `desktop-input` serialize correctly; no deadlocks

### Task 5.3 — Concurrent Task Dispatch
- **What**: Independent `TaskGraph` nodes run concurrently subject to resource leases.
- **Why**: 0% multi-task support; unrelated tasks block each other ([CLAUDE_STYLE_COMPARISON.md](file:///f:/MAX-AGENT/docs/evolution/CLAUDE_STYLE_COMPARISON.md) §6).
- **Files**:
  - Extend `core/scheduler.py` — Inspect dependency graph; dispatch independent nodes to worker pool
- **Tests**:
  - `tests/unit/test_concurrent_dispatch.py` — Two independent tasks run in parallel; dependent tasks serialize; resource conflict pauses one task
- **Acceptance Criteria**: "Build project and play music" executes both concurrently

### Phase 5 Gate
- [ ] Reminders survive process restart
- [ ] RFC 5545 RRULE recurrence fires correctly
- [ ] Independent tasks run concurrently without deadlocks
- [ ] Owner approves → `git tag gate-p5-approved`

---

## PHASE 6 — Memory Hardening & Scoped Context Packages

> **Priority**: P2 (Medium)  
> **Branch**: `max/p6-memory`  
> **Depends On**: Phase 1  
> **Audit Sources**: [MEMORY.md](file:///f:/MAX-AGENT/docs/audit/MEMORY.md), [PROMPT_FORENSICS.md](file:///f:/MAX-AGENT/docs/audit/PROMPT_FORENSICS.md), [THREAT_MODEL.md](file:///f:/MAX-AGENT/docs/THREAT_MODEL.md) T6

### Task 6.1 — Provenance-Gated Memory Writes
- **What**: Only `TRUSTED`-origin (owner keyboard/HUD) writes can modify preferences and system identity.
- **Why**: `save_memory` can be invoked by Gemini based on untrusted input, enabling memory poisoning ([MEMORY.md](file:///f:/MAX-AGENT/docs/audit/MEMORY.md), [THREAT_MODEL.md](file:///f:/MAX-AGENT/docs/THREAT_MODEL.md) T6).
- **Files**:
  - Modify `memory/memory_manager.py` — Add `origin` parameter to write operations; reject `UNTRUSTED` origin for preference/identity keys
- **Tests**:
  - `tests/unit/test_memory_provenance.py` — Untrusted origin blocked from writing preferences; trusted origin succeeds; owner can inspect and delete records
- **Acceptance Criteria**: Zero memory poisoning via indirect prompt injection

### Task 6.2 — Scoped Context Packages
- **What**: Build task-scoped context packages with strict token budgets instead of dumping full system prompt + memory into every turn.
- **Why**: Static system prompt + full memory consumes excessive tokens; irrelevant context degrades LLM quality ([PROMPT_FORENSICS.md](file:///f:/MAX-AGENT/docs/audit/PROMPT_FORENSICS.md)).
- **Files**:
  - Create `core/context_engine.py` — `ContextEngine` builds packages: task spec + relevant memory + tools only, within configurable token budget
- **Tests**:
  - `tests/unit/test_context_engine.py` — Context fits within budget; irrelevant memories excluded; task-relevant facts included
- **Acceptance Criteria**: 40% reduction in average prompt tokens; task-relevant recall ≥ 90%

### Task 6.3 — Structured Memory Schema with SQLite Backing
- **What**: Migrate from flat JSON (`long_term.json`) to structured schema with SQLite backing from `StateDB`.
- **Why**: Flat JSON grows unboundedly; no indexing; no concurrent access safety ([MEMORY.md](file:///f:/MAX-AGENT/docs/audit/MEMORY.md)).
- **Files**:
  - Extend `memory/memory_manager.py` — SQLite-backed storage with schema validation; retain JSON export for migration
- **Tests**:
  - `tests/unit/test_memory_schema.py` — Migration from JSON to SQLite succeeds; search queries return correct results
- **Acceptance Criteria**: Existing memories migrated losslessly; fast indexed retrieval
- **⚠️ WARNING**: `memory/long_term.json` is actively modified by the running `main.py` process. Migration must be non-destructive.

### Phase 6 Gate
- [ ] Memory poisoning via untrusted input is blocked
- [ ] Context packages are within token budget
- [ ] SQLite-backed memory passes all queries
- [ ] Owner approves → `git tag gate-p6-approved`

---

## PHASE 7 — ProcessManager & Security Hardening

> **Priority**: P1 (High)  
> **Branch**: `max/p7-security`  
> **Depends On**: Phase 1  
> **Resolves Conflicts**: CF-07, CF-09  
> **Audit Sources**: [SECURITY.md](file:///f:/MAX-AGENT/docs/audit/SECURITY.md), [THREAT_MODEL.md](file:///f:/MAX-AGENT/docs/THREAT_MODEL.md) T3, T5, T7

### Task 7.1 — Headless `ProcessManager` with Windows Job Objects
- **What**: Centralized process lifecycle management using Windows Job Objects for clean tree termination.
- **Why**: Actions launch subprocesses via raw `subprocess.Popen`; orphan processes leak on cancel/crash ([IMPROVEMENT_MATRIX.md](file:///f:/MAX-AGENT/docs/evolution/IMPROVEMENT_MATRIX.md)).
- **Files**:
  - Create `core/process_manager.py` — `ProcessManager` using Windows Job Objects; ring-buffered stdout/stderr streaming; clean tree kill on cancel/timeout
- **Tests**:
  - `tests/unit/test_process_manager.py` — Process tree kill terminates all children; stdout captured into ring buffer; timeout kills hung process
- **Acceptance Criteria**: Zero orphan processes after task cancellation

### Task 7.2 — Dashboard Network Hardening
- **What**: Re-bind dashboard to `127.0.0.1`; enforce random token auth; validate `Origin`/`Host` headers; remove firewall tampering.
- **Why**: `dashboard/server.py` binds to `0.0.0.0` and punches holes through Windows Firewall ([SECURITY.md](file:///f:/MAX-AGENT/docs/audit/SECURITY.md), [THREAT_MODEL.md](file:///f:/MAX-AGENT/docs/THREAT_MODEL.md) T3). Conflict CF-07.
- **Files**:
  - Modify `dashboard/server.py` — Change bind address to `127.0.0.1`; add per-install random token in header; validate `Origin` and `Host`; remove `_ensure_network_access()`
- **Tests**:
  - `tests/unit/test_dashboard_security.py` — Unauthenticated request rejected; wrong-origin request rejected; GET with side-effects rejected
- **Acceptance Criteria**: Dashboard only accessible from localhost; no UAC/firewall prompts

### Task 7.3 — OS Credential Keyring (Vault Activation)
- **What**: Move API keys from plaintext JSON to OS Keyring via `keyring` library.
- **Why**: `config/api_keys.json` stores secrets in plaintext on disk ([SECURITY.md](file:///f:/MAX-AGENT/docs/audit/SECURITY.md), [THREAT_MODEL.md](file:///f:/MAX-AGENT/docs/THREAT_MODEL.md) T5).
- **Files**:
  - Activate `core/max_infra/vault.py` — Wire to Windows Credential Manager; fallback to AES-256 encrypted file
  - Modify `memory/config_manager.py` — Read secrets from Vault instead of plaintext JSON
- **Tests**:
  - `tests/unit/test_vault.py` — Secret stored and retrieved; plaintext file not written; fallback to encrypted file on keyring unavailability
- **Acceptance Criteria**: No plaintext API keys on disk after migration

### Task 7.4 — Out-of-Process Watchdog
- **What**: Separate watchdog process monitoring orchestrator heartbeats and registering global emergency stop hotkey.
- **Why**: In-process `Watchdog` thread freezes when the main Python GIL or process hangs ([CONFLICT_LOG.md](file:///f:/MAX-AGENT/docs/CONFLICT_LOG.md) CF-09, [THREAT_MODEL.md](file:///f:/MAX-AGENT/docs/THREAT_MODEL.md) T7).
- **Files**:
  - Create `core/watchdog_process.py` — Standalone Python script: monitors heartbeat via shared memory/local IPC; registers global hotkey; kills orchestrator on timeout or hotkey
- **Tests**:
  - `tests/unit/test_watchdog.py` — Missing heartbeat triggers kill; hotkey triggers emergency stop; watchdog starts/stops cleanly
- **Acceptance Criteria**: Emergency stop works even when main process is hung

### Phase 7 Gate
- [ ] Dashboard bound to `127.0.0.1` only
- [ ] API keys stored in OS Keyring
- [ ] Watchdog kills hung orchestrator reliably
- [ ] Zero orphan processes on cancellation
- [ ] Owner approves → `git tag gate-p7-approved`

---

## PHASE 8 — Verification Engine & Self-Correction

> **Priority**: P1 (High)  
> **Branch**: `max/p8-verification`  
> **Depends On**: Phase 3, Phase 4  
> **Audit Sources**: [VERIFICATION.md](file:///f:/MAX-AGENT/docs/audit/VERIFICATION.md), [FAILURE_RECOVERY.md](file:///f:/MAX-AGENT/docs/audit/FAILURE_RECOVERY.md), [CLAUDE_STYLE_COMPARISON.md](file:///f:/MAX-AGENT/docs/evolution/CLAUDE_STYLE_COMPARISON.md) §2, §5

### Task 8.1 — Wire `VerificationEngine` to All Task Completions
- **What**: Connect the dormant `core/verification/engine.py` to the execution lifecycle.
- **Why**: Verification engine exists but has zero imports from `main.py` or any action handler. 56% false success rate ([VERIFICATION.md](file:///f:/MAX-AGENT/docs/audit/VERIFICATION.md)).
- **Files**:
  - Extend `core/verification/engine.py` — Add verification levels L0-L3 with wait-until polling and evidence recording
  - Wire into `core/gateway.py` — Post-execution verification before transitioning task to `COMPLETED`
- **Tests**:
  - `tests/unit/test_verification_engine.py` — L3 verifier checks process PID; L2 checks UIA tree; L1 checks screenshot; `UNKNOWN` never treated as `SUCCESS`
- **Acceptance Criteria**: False success rate drops from 56% to < 5%

### Task 8.2 — `RecoveryEngine` with Error Classification
- **What**: Classify errors into categories and apply bounded recovery strategies.
- **Why**: Current recovery is `except Exception: return error_string` — zero retries, zero rollbacks ([FAILURE_RECOVERY.md](file:///f:/MAX-AGENT/docs/audit/FAILURE_RECOVERY.md)).
- **Files**:
  - Create `core/recovery_engine.py` — Error classification (`TRANSIENT`, `ENVIRONMENT`, `LOGIC`, `RESOURCE`, `EXTERNAL`); bounded retry with backoff; idempotency gate; git checkpoint rollback for coding tasks
- **Tests**:
  - `tests/unit/test_recovery.py` — Transient error retried; logic error not retried; max retries enforced; rollback restores previous state
- **Acceptance Criteria**: Transient network errors auto-recover; bounded retry limits prevent infinite loops

### Task 8.3 — Self-Correction Loop with Budget Enforcement
- **What**: Structured `Plan → Execute → Observe → Verify → Critique → Replan` loop.
- **Why**: `dev_agent.py` loops up to 5 times without alternative strategies ([CLAUDE_STYLE_COMPARISON.md](file:///f:/MAX-AGENT/docs/evolution/CLAUDE_STYLE_COMPARISON.md) §5).
- **Files**:
  - Extend `core/recovery_engine.py` — Feed structured failure reports into bounded replanner; enforce max_iterations, max_retries, wall-clock timeout
- **Tests**:
  - `tests/unit/test_self_correction.py` — Fix loop converges on simple error; budget exceeded triggers escalation; repeated same error triggers alternative strategy
- **Acceptance Criteria**: Autonomous recovery from transient compilation/syntax errors; hard stop after budget

### Phase 8 Gate
- [ ] Verified success rate ≥ 80% (up from 8%)
- [ ] False success rate < 5% (down from 56%)
- [ ] Recovery handles transient errors without human intervention
- [ ] Owner approves → `git tag gate-p8-approved`

---

## PHASE 9 — Provider Abstraction (Local/Cloud Models)

> **Priority**: P3 (Low)  
> **Branch**: `max/p9-providers`  
> **Depends On**: Phase 1  
> **Audit Sources**: [IMPROVEMENT_MATRIX.md](file:///f:/MAX-AGENT/docs/evolution/IMPROVEMENT_MATRIX.md) (Provider Abstraction row)

### Task 9.1 — `LLMProvider` Abstraction
- **What**: Abstract LLM client behind a `LLMProvider` protocol supporting Gemini, OpenAI, Anthropic, and Ollama backends.
- **Why**: Hardcoded to `gemini-3.1-flash-live-preview`; cannot use local offline models or alternative providers.
- **Files**:
  - Create `core/providers/base.py` — `LLMProvider` protocol
  - Create `core/providers/gemini.py` — Current Gemini Live WebSocket wrapped
  - Create `core/providers/ollama.py` — Local Ollama/vLLM integration
- **Tests**:
  - `tests/unit/test_providers.py` — Provider parity test: same prompt produces structured response from both
- **Acceptance Criteria**: MAX can operate with a local model when offline

### Task 9.2 — Model Routing by Task Complexity
- **What**: Route tasks to appropriate models based on complexity, latency, cost, and privacy requirements.
- **Why**: Simple intents waste expensive model capacity; private tasks shouldn't go to cloud.
- **Files**:
  - Extend `core/providers/base.py` — `ModelRouter` selecting model based on task metadata
- **Tests**:
  - `tests/unit/test_model_router.py` — Simple intent routes to fast model; coding task routes to coding-capable model; private task routes to local model
- **Acceptance Criteria**: Model selection is deterministic and logged

### Phase 9 Gate
- [ ] MAX operates with at least 2 different providers
- [ ] Offline mode works with local model
- [ ] Owner approves → `git tag gate-p9-approved`

---

## PHASE 10 — Advanced Agentic Capabilities

> **Priority**: P3 (Low)  
> **Branch**: `max/p10-advanced`  
> **Depends On**: Phases 1-8  
> **Audit Sources**: [CLAUDE_STYLE_COMPARISON.md](file:///f:/MAX-AGENT/docs/evolution/CLAUDE_STYLE_COMPARISON.md) §3, §4, [ROADMAP.md](file:///f:/MAX-AGENT/docs/evolution/ROADMAP.md) Phase 10

### Task 10.1 — Reusable Skill System
- **What**: Modular `skills/<name>/SKILL.md` packages defining tools, schemas, pre/post-conditions, and verification rules.
- **Why**: Rigid Python functions in `actions/*.py` are difficult to extend ([CLAUDE_STYLE_COMPARISON.md](file:///f:/MAX-AGENT/docs/evolution/CLAUDE_STYLE_COMPARISON.md) §3).
- **Files**:
  - Create `core/skill_loader.py` — Discover and load skill packages from `skills/` directory
  - Create example skills: `skills/open_application/`, `skills/play_music/`
- **Tests**:
  - `tests/unit/test_skill_loader.py` — Skill discovery; schema validation; skill execution through gateway
- **Acceptance Criteria**: New capabilities added by dropping a skill folder without modifying core code

### Task 10.2 — Lifecycle Hooks System
- **What**: Pluggable hooks for `before_task`, `after_task`, `before_tool`, `after_tool`, `on_failure`, `on_verification`.
- **Why**: Observability, policy enforcement, and metrics currently require duplicating logic across every agent.
- **Files**:
  - Create `core/hooks.py` — Hook registry with ordered execution
- **Tests**:
  - `tests/unit/test_hooks.py` — Hooks fire in order; hook exception doesn't crash task; hooks provide metrics
- **Acceptance Criteria**: Audit logging, metrics, and policy checks implemented as hooks rather than inline code

### Task 10.3 — Real Worker Implementations (Calendar, Reminders, Media)
- **What**: Replace mock agent stubs with real domain implementations.
- **Why**: 33 agents are all stubs; productivity features are fake ([AGENT_REGISTRY_AUDIT.md](file:///f:/MAX-AGENT/docs/audit/AGENT_REGISTRY_AUDIT.md)).
- **Files**:
  - Implement `CalendarWorker` — SQLite-backed, RFC 5545, half-open conflict intervals
  - Implement `ReminderWorker` — Daemon scheduler integration
  - Implement `MediaWorker` — Windows Media Session (SMTC) integration for Spotify/VLC
- **Tests**:
  - Domain-specific unit tests for each worker
- **Acceptance Criteria**: Calendar, reminder, and media golden tasks pass with L3 verification

### Phase 10 Gate
- [ ] At least 3 real worker implementations passing L3 verification
- [ ] Skill system loads and executes external skills
- [ ] Hook system captures metrics without inline code
- [ ] Owner approves → `git tag gate-p10-approved`

---

## PHASE 11 — HUD Observability & Dashboard API

> **Priority**: P2 (Medium)  
> **Branch**: `max/p11-observability`  
> **Depends On**: Phase 1, Phase 7  
> **Audit Sources**: [OBSERVABILITY.md](file:///f:/MAX-AGENT/docs/audit/OBSERVABILITY.md), [IMPROVEMENT_MATRIX.md](file:///f:/MAX-AGENT/docs/evolution/IMPROVEMENT_MATRIX.md)

### Task 11.1 — Real-Time Task Progress Widget in HUD
- **What**: HUD widget showing active tasks, current step, worker status, and verification outcomes.
- **Why**: User has zero visibility into what step of a multi-step task is running ([CLAUDE_STYLE_COMPARISON.md](file:///f:/MAX-AGENT/docs/evolution/CLAUDE_STYLE_COMPARISON.md) §7).
- **Files**:
  - Create `ui/components/task_progress_widget.py` — Subscribe to `EventBus` and display `TaskProgress` events
- **Tests**:
  - `tests/unit/test_task_progress.py` — Widget updates on events; handles rapid event bursts
- **Acceptance Criteria**: User can see step N of M during multi-step execution

### Task 11.2 — Structured Dashboard API with Authentication
- **What**: RESTful dashboard API with proper authentication, CSRF protection, and no side-effects on GET.
- **Why**: Current dashboard has no auth and accepts commands from any origin.
- **Files**:
  - Modify `dashboard/server.py` — Token-authenticated endpoints; WebSocket authenticated; rate limiting
- **Tests**:
  - `tests/unit/test_dashboard_api.py` — All endpoints require token; rate limiting enforced
- **Acceptance Criteria**: Dashboard API is authenticated and rate-limited

### Phase 11 Gate
- [ ] HUD shows real-time task progress
- [ ] Dashboard API authenticated and rate-limited
- [ ] Owner approves → `git tag gate-p11-approved`

---

## PHASE 12 — Final Integration & Acceptance Testing

> **Priority**: P1 (High)  
> **Branch**: `max/p12-acceptance`  
> **Depends On**: All previous phases  
> **Audit Sources**: [ROADMAP.md](file:///f:/MAX-AGENT/docs/evolution/ROADMAP.md) Phase 10, all evolution documents

### Task 12.1 — End-to-End Golden Task Suite
- **What**: Run all 25 golden tasks end-to-end and verify with L3 deterministic verification.
- **Files**:
  - Extend `tests/evals/harness.py` — End-to-end execution mode (not just offline simulation)
  - Update `tests/evals/golden_tasks.json` — Add expected verification levels
- **Tests**:
  - `tests/evals/test_e2e_golden.py` — All 25 golden tasks execute; ≥ 80% verified success
- **Acceptance Criteria**: Verified success rate ≥ 80% (up from 8%); false success rate < 5% (down from 56%)

### Task 12.2 — Production Acceptance Checklist
- **What**: MAX must be able to answer from structured telemetry:
  - What am I doing? Why? Who is doing it? What tool? What resource? What failed? What was retried? What was verified? What remains? Why did I say the task was complete?
- **Files**:
  - `docs/ACCEPTANCE_CHECKLIST.md` — Formal checklist with evidence links
- **Tests**: Manual verification against structured trace queries
- **Acceptance Criteria**: All questions answerable from `StateDB.audit_log` queries

### Task 12.3 — Updated Architecture Documentation
- **What**: Update all docs to reflect the actual implemented architecture.
- **Files**:
  - Update `docs/ARCHITECTURE_REAL.md`, `docs/PROGRESS.md`, `README.md`
- **Acceptance Criteria**: Documentation matches code; no stale claims

### Final Gate
- [ ] All automated tests pass (Tier 0 + Unit + Integration + E2E)
- [ ] 25 golden tasks: ≥ 80% verified success, < 5% false success
- [ ] All structured telemetry questions answerable
- [ ] Owner final approval → `git tag v2.0.0-rc1`

---

## Summary Statistics

| Metric | Count |
|:---|---:|
| **Total Phases** | 13 (P0-P12) |
| **Total Tasks** | 42 |
| **New Files to Create** | ~35 |
| **Files to Modify** | ~15 |
| **Test Files to Create** | ~30 |
| **Conflicts Resolved** | 9 (CF-01 through CF-09) |
| **Threats Mitigated** | 7 (T1 through T7) |
| **Audit Documents Consumed** | 30+ |

---

## Critical Path

The minimum viable path to a safe, honest, verifiable MAX is:

```
Phase 0 (DONE) → Phase 1 → Phase 3 → Phase 8
```

This path delivers:
1. ✅ ExecutionGateway (single choke point for all side effects)
2. ✅ RCE elimination (no more `exec()`)
3. ✅ Honest agents (raise `NotImplementedError` instead of fake success)
4. ✅ Verification engine (false success rate < 5%)

Everything else builds upon this safety + honesty foundation.

# MAX-AGENT — Evolution Roadmap (Phase 0 to Phase 10)

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Roadmap Overview & Sequencing

The evolution of MAX follows a disciplined, gated sequence where **safety and foundations precede autonomy**:

```
[ ROADMAP 0: Stabilization & Audit ] ──► [ ROADMAP 1: Foundations & Choke Point ]
                                                         │
                                                         ▼
[ ROADMAP 3: Desktop Reliability ]   ◄── [ ROADMAP 2: Task & Routing Correctness ]
               │
               ▼
[ ROADMAP 4: Sandboxed Coding (OpenCode) ]
               │
               ▼
[ ROADMAP 5: Parallel Scheduler & Leases ]
               │
               ▼
[ ROADMAP 6: Memory & Context Hardening ]
               │
               ▼
[ ROADMAP 7: Sandboxing & Security Gates ]
               │
               ▼
[ ROADMAP 8: Self-Correction & Verification ]
               │
               ▼
[ ROADMAP 9: Provider Abstraction (Local/Cloud) ]
               │
               ▼
[ ROADMAP 10: Advanced Autonomous Workflows ]
```

---

## 2. Detailed Roadmap Specifications

### Roadmap 0: Current Stabilization & Baseline
- **WHY**: Establish empirical truth and prevent regression before touching production code.
- **WHAT**: Full codebase forensic audit, inventory of unchoked side effects, Tier 0 characterization tests capturing current behavior.
- **FILES**: `docs/audit/*`, `docs/evolution/*`, `tests/tier0_characterization/*`.
- **DEPENDENCIES**: None.
- **TESTS**: 21 Tier 0 characterization tests covering existing action loader, memory, and infra.
- **RISK**: Low. (Zero modifications to production code).
- **EXPECTED BENEFIT**: 100% architectural transparency; solid regression baseline.

### Roadmap 1: Foundations, Data Contracts & ExecutionGateway
- **WHY**: Stop unchoked side effects and establish the single choke point required by Rule 1-S2.
- **WHAT**: Implement `TaskIntent`, `Task`, `TaskStateMachine` (14 states), `ExecutionGateway` (wrapping `PolicyEngine`), injectable `Clock`, and AST banned-import test.
- **FILES**: `core/contracts.py`, `core/state_machine.py`, `core/gateway.py`, `core/clock.py`, `tests/test_banned_imports.py`.
- **DEPENDENCIES**: Roadmap 0.
- **TESTS**: State machine transition tests; policy risk table tests; AST scan verifying no raw `subprocess`/`os.system` imports outside adapters.
- **RISK**: Medium. Must not break existing Gemini tool calling during strangler-fig migration.
- **EXPECTED BENEFIT**: 100% of side effects pass through a deterministic security gate.

### Roadmap 2: Task Planning, Capability Registry & Agent Routing
- **WHY**: Eliminate LLM tool hallucination and remove the 33 uncoordinated mock stubs.
- **WHAT**: Two-stage routing pipeline: Schema-constrained plan proposal ──► Deterministic `CapabilityRouter`. Tag mock agents `[NOT IMPLEMENTED]`.
- **FILES**: `core/planner.py`, `core/capability_registry.py`, `agents/router.py`.
- **DEPENDENCIES**: Roadmap 1.
- **TESTS**: Plan validator tests; router ranking and tie-breaking tests; malicious plan rejection tests.
- **RISK**: Low.
- **EXPECTED BENEFIT**: 95%+ routing accuracy; explainable `RoutingDecision` records.

### Roadmap 3: Desktop Automation & Application Launch Reliability
- **WHY**: Eliminate dangerous `exec()` in `desktop.py` and blind Windows Search keypresses in `open_app.py`.
- **WHAT**: Build `WindowsDesktopAdapter` utilizing Windows UI Automation (UIA) tree. Implement guarded Windows Search flow and L3 launch verification (process + visible responsive window).
- **FILES**: `core/adapters/windows_desktop.py`, `core/adapters/fake_desktop.py`, `actions/open_app.py`, `actions/desktop.py`.
- **DEPENDENCIES**: Roadmap 1, Roadmap 2.
- **TESTS**: Fake desktop launch/focus tests; real desktop launch scenarios (Chrome, VS Code) passing 19/20 runs.
- **RISK**: High (UI Automation timing on slow machines).
- **EXPECTED BENEFIT**: Resilient desktop automation; zero remote code execution risk.

### Roadmap 4: Sandboxed Coding Workflow & OpenCode Integration
- **WHY**: Replace host-contaminating `dev_agent.py` with an isolated, verified coding engine.
- **WHAT**: Implement `CodingExecutor` interface with `OpenCodeWorker` CLI adapter. Enforce execution inside dedicated git worktrees with isolated virtualenvs, scope checks, and test integrity assertions.
- **FILES**: `core/coding/executor.py`, `core/coding/opencode_worker.py`, `core/coding/sandbox.py`.
- **DEPENDENCIES**: Roadmap 1, Roadmap 2.
- **TESTS**: Scope check test (edits outside worktree fail); test weakening detection test; OpenCode install verification test.
- **RISK**: Medium.
- **EXPECTED BENEFIT**: Safe autonomous coding; immune to host PyPI supply-chain attacks.

### Roadmap 5: Parallel Scheduler, Concurrency & Resource Leases
- **WHY**: Enable concurrent tasks (e.g. build project while playing music) without resource deadlocks.
- **WHAT**: Implement `TaskScheduler` backed by `StateDB` SQLite WAL with Dijkstra sorted resource leases (`desktop-input`, `project:<path>`, `gpu-vram`). Add `UserActivityMonitor` to pause automation when human types.
- **FILES**: `core/scheduler.py`, `core/max_infra/lock_manager.py`, `core/user_activity.py`.
- **DEPENDENCIES**: Roadmap 1.
- **TESTS**: Concurrency collision tests; lease expiry and heartbeat tests; kill -9 restart recovery tests.
- **RISK**: High (concurrency race conditions).
- **EXPECTED BENEFIT**: Multi-task execution without deadlocks or UI freezing.

### Roadmap 6: Memory Hardening & Scoped Context Packages
- **WHY**: Prevent memory poisoning and reduce prompt token waste.
- **WHAT**: Implement provenance-gated memory writes (only TRUSTED origin can update facts); build task-scoped context packages with strict token budgets.
- **FILES**: `memory/memory_manager.py`, `core/context_engine.py`.
- **DEPENDENCIES**: Roadmap 1.
- **TESTS**: Memory injection rejection tests; context budgeting tests; memory search accuracy tests.
- **RISK**: Low.
- **EXPECTED BENEFIT**: 40% lower LLM latency; complete immunity to indirect memory poisoning.

### Roadmap 7: Sandboxing, ProcessManager & Security Hardening
- **WHY**: Confine background processes and protect network attack surfaces.
- **WHAT**: Implement headless `ProcessManager` using Windows Job Objects for clean process tree termination; re-bind dashboard to `127.0.0.1` with random token auth and CSRF origin checks.
- **FILES**: `core/process_manager.py`, `dashboard/server.py`.
- **DEPENDENCIES**: Roadmap 1.
- **TESTS**: Process tree kill tests; unauthenticated dashboard rejection tests; DNS rebinding rejection tests.
- **RISK**: Low.
- **EXPECTED BENEFIT**: Zero orphan processes; hardened localhost security surface.

### Roadmap 8: Verification Engine & Autonomous Self-Correction
- **WHY**: Ensure MAX never reports false success and can recover from transient errors.
- **WHAT**: Connect `core/verification/engine.py` to all task completions; implement bounded fix-and-retest loops with git checkpoint rollbacks.
- **FILES**: `core/verification/*`, `core/recovery_engine.py`.
- **DEPENDENCIES**: Roadmap 3, Roadmap 4.
- **TESTS**: L3/L2/L1 verifier unit tests; bounded fix loop tests; rollback-on-failure tests.
- **RISK**: Medium.
- **EXPECTED BENEFIT**: 100% truthful reporting; reliable automated bug fixing.

### Roadmap 9: Model & Provider Abstraction
- **WHY**: Remove hardcoded dependency on Gemini Live preview WebSocket; support local offline models.
- **WHAT**: Implement `LLMProvider` abstraction supporting Gemini, OpenAI, Claude, and Ollama/vLLM backends.
- **FILES**: `core/llm_client.py`, `core/providers/*`.
- **DEPENDENCIES**: Roadmap 1.
- **TESTS**: Provider parity unit tests; offline fallback tests.
- **RISK**: Medium.
- **EXPECTED BENEFIT**: Vendor flexibility and offline privacy capability.

### Roadmap 10: Advanced Agentic Capabilities & Ecosystem
- **WHY**: Enable complex, cross-domain multi-step workflows.
- **WHAT**: Full multi-node TaskGraph execution, community skill packages (`skills/`), and rich HUD visualization.
- **FILES**: `ui/components/task_graph_widget.py`, `skills/*`.
- **DEPENDENCIES**: Roadmaps 1 through 8.
- **TESTS**: End-to-end golden scenarios 1-25.
- **RISK**: Low.
- **EXPECTED BENEFIT**: State-of-the-art personal AI operating system.

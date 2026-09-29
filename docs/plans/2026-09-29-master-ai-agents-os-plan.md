# Master AI Agent Operating System Implementation Plan
**CyberBlack AI-agent MAX × MAX OS × Laya System 1 Reflex Engine**

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Build a complete, enterprise-grade, dual-lane voice AI operating system fusing CyberBlack AI-agent MAX (Gemini 3.1 Flash Live, PyQt6 HUD, wake-word), Laya (local non-autoregressive System 1 reflex engine for sub-50ms routing/guardrails), and MAX OS (deterministic Layer 0-3 OS runtime, SQLite WAL state DB, priority task queue, deadlock-free sorted locks, snapshot rollback, 5-layer memory heap, and 33 specialized agents).

**Architecture:** Inputs flow through local openwakeword into Gemini 3.1 Flash Live and the Laya System 1 Reflex Engine. Laya makes sub-50ms routing and safety decisions locally. Fast read queries execute synchronously via Lane A; complex, modifying, or background tasks dispatch to Lane B via a prioritized, sorted-locked, snapshot-backed task queue orchestrating 33 context-isolated specialized agents.

**Tech Stack:** Python 3.11, Laya 0.3.21 (ONNX/Torch), SQLite (WAL mode), PyQt6, google-genai (Gemini 3.1 Flash Live), psutil, keyring, pydantic v2, pytest.

---

## Priority 1: Layer 0–1 Deterministic OS Floor (Persistence & Kill Switch)

### Task 1: Component #0 - Physical Kill Switch (`core/max_infra/kill_switch.py`)
**Files:**
- Create: `core/max_infra/kill_switch.py`
- Test: `tests/unit/test_kill_switch.py`

**Step 1: Write the failing test**
Test that `KillSwitch` triggers a global shutdown event, terminates registered child PIDs, and prevents any new tasks from starting.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_kill_switch.py -v`
Expected: FAIL (ModuleNotFoundError)

**Step 3: Implement minimal code**
Implement `KillSwitch` singleton with thread-safe `threading.Event`, Windows `taskkill /F /T /PID` child process tree termination, and listener hooks.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_kill_switch.py -v`
Expected: PASS

---

### Task 2: State Database & Schema (`core/max_infra/state_db.py` & `schema.sql`)
**Files:**
- Create: `core/max_infra/schema.sql`
- Create: `core/max_infra/state_db.py`
- Test: `tests/unit/test_state_db.py`

**Step 1: Write the failing test**
Test SQLite WAL mode initialization, connection pooling, and CRUD across the 11 tables (`tasks`, `task_traces`, `resource_locks`, `circuit_breakers`, `memory_layers`, `snapshots`, `audit_log`, etc.).

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_state_db.py -v`
Expected: FAIL

**Step 3: Implement minimal code**
Create `schema.sql` with indices and foreign keys. Implement `StateDB` manager in `state_db.py` ensuring `PRAGMA journal_mode = WAL;` and thread-safe operations.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_state_db.py -v`
Expected: PASS

---

### Task 3: Secrets Vault & DPAPI Keyring (`core/max_infra/vault.py`)
**Files:**
- Create: `core/max_infra/vault.py`
- Test: `tests/unit/test_vault.py`

**Step 1: Write the failing test**
Test storing, retrieving, and deleting secrets securely with fallbacks.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_vault.py -v`

**Step 3: Implement minimal code**
Implement `Vault` with Windows Credential Manager / DPAPI support, stripping plain text secrets from environment and memory.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_vault.py -v`
Expected: PASS

---

### Task 4: Data Boundary & Token Scrubber (`core/max_infra/data_boundary.py`)
**Files:**
- Create: `core/max_infra/data_boundary.py`
- Test: `tests/unit/test_data_boundary.py`

**Step 1: Write the failing test**
Test regex redacting API keys (`sk-...`, `AIza...`), credit cards, emails, and local user paths.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_data_boundary.py -v`

**Step 3: Implement minimal code**
Implement `DataBoundary` with compiled regex patterns, token replacement maps, and reversible un-masking for local processing.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_data_boundary.py -v`
Expected: PASS

---

## Priority 2: Laya Local System 1 Reflex Engine (`core/reflex/`)

### Task 5: Laya Reflex Core Engine (`core/reflex/laya_engine.py`)
**Files:**
- Create: `core/reflex/__init__.py`
- Create: `core/reflex/laya_engine.py`
- Test: `tests/unit/test_laya_engine.py`

**Step 1: Write the failing test**
Test that `LayaReflexEngine` initializes locally, executes typed questions (`choice`, `score`, `noul`) in sub-50ms, and handles fallback gracefully.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_laya_engine.py -v`

**Step 3: Implement minimal code**
Wrap `laya.Router` and `ONNXAgent` into `LayaReflexEngine`, providing typed prediction methods with confidence calibration and caching.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_laya_engine.py -v`
Expected: PASS

---

### Task 6: Reflex Intent & Lane Router (`core/reflex/intent_router.py`)
**Files:**
- Create: `core/reflex/intent_router.py`
- Test: `tests/unit/test_intent_router.py`

**Step 1: Write the failing test**
Test routing conversational inputs to `Lane A (Instant Voice)` vs `Lane B (Autonomous Queue)` and predicting the target agent among the 33 options in ~30ms.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_intent_router.py -v`

**Step 3: Implement minimal code**
Implement `ReflexIntentRouter` using Laya typed questions (`choice` over lanes, `choice` over agent clusters and agents).

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_intent_router.py -v`
Expected: PASS

---

### Task 7: Reflex Safety Guardrails & Triage (`core/reflex/guardrails.py` & `triage.py`)
**Files:**
- Create: `core/reflex/guardrails.py`
- Create: `core/reflex/triage.py`
- Test: `tests/unit/test_guardrails_triage.py`

**Step 1: Write the failing test**
Test that malicious inputs, system destructive commands, and prompt injections are caught with calibrated probability, and priority bands (0–4) are assigned.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_guardrails_triage.py -v`

**Step 3: Implement minimal code**
Implement `ReflexGuardrails` using Laya's `guard_questions` and `LayaGuardrail`, plus `ReflexTriage` for urgency scoring (Bands 0–4).

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_guardrails_triage.py -v`
Expected: PASS

---

## Priority 3: Task Lifecycle, Priority Queue & Transactional Safety

### Task 8: Task Lifecycle State Machine (`core/max_infra/task_lifecycle.py`)
**Files:**
- Create: `core/max_infra/task_lifecycle.py`
- Test: `tests/unit/test_task_lifecycle.py`

**Step 1: Write the failing test**
Test strict state transitions (`CREATED` -> `QUEUED` -> `LOCK_WAIT` -> `RUNNING` -> `RECONCILING` -> `DONE`/`FAILED`), rejecting invalid transitions.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_task_lifecycle.py -v`

**Step 3: Implement minimal code**
Implement `TaskLifecycleFSM` with transition rules, audit trace callbacks, and DB persistence.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_task_lifecycle.py -v`
Expected: PASS

---

### Task 9: Task Priority Queue with Starvation Aging (`core/max_infra/task_queue.py`)
**Files:**
- Create: `core/max_infra/task_queue.py`
- Test: `tests/unit/test_task_queue.py`

**Step 1: Write the failing test**
Test priority scheduling across Bands 0–4, aging starvation promotion every 30s, and backpressure limit at 500 tasks.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_task_queue.py -v`

**Step 3: Implement minimal code**
Implement `TaskQueue` backed by thread-safe `heapq`, SQLite state syncing, aging calculation, and backpressure rejection.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_task_queue.py -v`
Expected: PASS

---

### Task 10: Deadlock-Free Sorted Lock Manager (`core/max_infra/lock_manager.py`)
**Files:**
- Create: `core/max_infra/lock_manager.py`
- Test: `tests/unit/test_lock_manager.py`

**Step 1: Write the failing test**
Test acquiring multiple resources in sorted canonical order, preventing circular wait deadlocks, and testing automatic TTL expiry.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_lock_manager.py -v`

**Step 3: Implement minimal code**
Implement `LockManager` sorting resource keys lexicographically before acquisition, with lease timeouts and DB lock registration.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_lock_manager.py -v`
Expected: PASS

---

### Task 11: Atomic File Snapshot & Rollback (`core/max_infra/snapshot.py`)
**Files:**
- Create: `core/max_infra/snapshot.py`
- Test: `tests/unit/test_snapshot.py`

**Step 1: Write the failing test**
Test capturing pre-execution snapshots of files, verifying SHA-256 hashes, and rolling back modified or deleted files bit-for-bit.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_snapshot.py -v`

**Step 3: Implement minimal code**
Implement `SnapshotEngine` creating compressed task snapshots in `.snapshots/<task_id>/` and providing atomic rollback.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_snapshot.py -v`
Expected: PASS

---

### Task 12: Watchdog, Circuit Breaker & Reconciliation (`core/max_infra/watchdog.py`, `circuit_breaker.py`, `reconciliation.py`)
**Files:**
- Create: `core/max_infra/watchdog.py`
- Create: `core/max_infra/circuit_breaker.py`
- Create: `core/max_infra/reconciliation.py`
- Test: `tests/unit/test_resilience.py`

**Step 1: Write the failing test**
Test heartbeat expiration triggering task kill, 3 consecutive failures opening the circuit breaker for 60s, and post-execution OS reconciliation.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_resilience.py -v`

**Step 3: Implement minimal code**
Implement `Watchdog` thread, `CircuitBreaker` with 3-strike state machine, and `ReconciliationEngine` checking physical OS state against agent claims.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_resilience.py -v`
Expected: PASS

---

## Priority 4: 5-Layer Memory Context Heap & Safety Confirm Gate

### Task 13: 5-Layer Memory Context Heap (`core/memory/context_heap.py` & `token_budget.py`)
**Files:**
- Create: `core/memory/context_heap.py`
- Create: `core/memory/token_budget.py`
- Test: `tests/unit/test_context_heap.py`

**Step 1: Write the failing test**
Test aggregation of L1 (Identity), L2 (Preferences), L3 (Behavioral), L4 (Project), and L5 (Conversation) with hard cap of 2,048 tokens.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_context_heap.py -v`

**Step 3: Implement minimal code**
Implement `MemoryContextHeap` backed by SQLite FTS5 lexical search and `TokenBudgetCompressor` pruning low-priority context to fit exact budgets.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_context_heap.py -v`
Expected: PASS

---

### Task 14: Safety Confirm Barrier & Undo Stack Bridge (`core/confirm.py` & `core/undo.py`)
**Files:**
- Modify: `core/confirm.py`
- Modify: `core/undo.py`
- Test: `tests/unit/test_confirm_undo.py`

**Step 1: Write the failing test**
Test that Tier 2 actions halt until user confirmation, timeout triggers auto-rollback, and "undo" rolls back the last task snapshot.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_confirm_undo.py -v`

**Step 3: Implement minimal code**
Bridge `confirm.py` to PyQt6 glassmorphic dialog with 30s countdown and wire `undo.py` directly into `SnapshotEngine.rollback()`.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_confirm_undo.py -v`
Expected: PASS

---

## Priority 5: The 33-Agent Multi-Agent Ecosystem (`agents/`)

### Task 15: Agent Base Contract & Coordinator (`agents/base.py` & `router.py`)
**Files:**
- Create: `agents/__init__.py`
- Create: `agents/base.py`
- Create: `agents/router.py`
- Test: `tests/unit/test_agent_base.py`

**Step 1: Write the failing test**
Test `BaseAgent` lifecycle: input validation, circuit breaker check, sorted lock acquisition, snapshot capture, execution, state reconciliation, and lock release.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_agent_base.py -v`

**Step 3: Implement minimal code**
Implement `BaseAgent` with Pydantic schemas, context isolation, timeout enforcement, and `AgentRouter` registry.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_agent_base.py -v`
Expected: PASS

---

### Task 16: Cluster 1: Core Reasoning & Orchestration Agents (`agents/core/`)
**Files:**
- Create: `agents/core/__init__.py`
- Create: `agents/core/orchestrator.py`
- Create: `agents/core/planner.py`
- Create: `agents/core/verifier.py`
- Create: `agents/core/model_router.py`
- Create: `agents/core/critic.py`
- Test: `tests/unit/test_cluster_core.py`

**Step 1: Write the failing test**
Test DAG decomposition in `planner.py`, acceptance verification in `verifier.py`, and model routing.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_cluster_core.py -v`

**Step 3: Implement minimal code**
Implement all 5 Core Reasoning agents inheriting from `BaseAgent`.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_cluster_core.py -v`
Expected: PASS

---

### Task 17: Cluster 2: Software Delivery Pipeline Agents (`agents/software/`)
**Files:**
- Create: `agents/software/__init__.py`
- Create: `agents/software/architect.py`
- Create: `agents/software/spec_author.py`
- Create: `agents/software/dev_agent.py`
- Create: `agents/software/code_reviewer.py`
- Create: `agents/software/qa_tester.py`
- Create: `agents/software/security_auditor.py`
- Create: `agents/software/tech_writer.py`
- Create: `agents/software/deploy_agent.py`
- Test: `tests/unit/test_cluster_software.py`

**Step 1: Write the failing test**
Test full software delivery cycle: spec authoring -> dev patching -> review -> test execution -> git commit.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_cluster_software.py -v`

**Step 3: Implement minimal code**
Implement all 8 Software Delivery agents with file editing, git, and testing hooks.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_cluster_software.py -v`
Expected: PASS

---

### Task 18: Cluster 3: Founder Productivity Agents (`agents/productivity/`)
**Files:**
- Create: `agents/productivity/__init__.py`
- Create: `agents/productivity/calendar_agent.py`
- Create: `agents/productivity/inbox_agent.py`
- Create: `agents/productivity/meeting_notes.py`
- Create: `agents/productivity/task_triage.py`
- Create: `agents/productivity/deal_crm.py`
- Create: `agents/productivity/content_creator.py`
- Create: `agents/productivity/researcher.py`
- Create: `agents/productivity/finance_tracker.py`
- Test: `tests/unit/test_cluster_productivity.py`

**Step 1: Write the failing test**
Test email cleaning/triage with Laya, calendar conflict checks, and meeting note extraction.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_cluster_productivity.py -v`

**Step 3: Implement minimal code**
Implement all 8 Founder Productivity agents utilizing Laya presets and external tool adapters.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_cluster_productivity.py -v`
Expected: PASS

---

### Task 19: Cluster 4 & 5: High-Risk Control & System Health (`agents/safety/` & `agents/health/`)
**Files:**
- Create: `agents/safety/` (6 agents: `approval_gate.py`, `permission_auditor.py`, `data_scrubber.py`, `network_guard.py`, `emergency_stop.py`, `compliance_logger.py`)
- Create: `agents/health/` (6 agents: `system_monitor.py`, `state_reconciler.py`, `self_healer.py`, `backup_manager.py`, `log_synthesizer.py`, `garbage_collector.py`)
- Test: `tests/unit/test_cluster_safety_health.py`

**Step 1: Write the failing test**
Test permission verification, audit hash logging, system health telemetry collection, and self-healing lock resets.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_cluster_safety_health.py -v`

**Step 3: Implement minimal code**
Implement all 12 agents in safety and health clusters.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_cluster_safety_health.py -v`
Expected: PASS

---

### Task 20: Action Loader Integration (`core/action_loader.py`)
**Files:**
- Modify: `core/action_loader.py`
- Test: `tests/unit/test_action_loader_agents.py`

**Step 1: Write the failing test**
Test that `action_loader` auto-discovers and exposes all 33 agents alongside native tools as callable tool schemas for Gemini Live.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_action_loader_agents.py -v`

**Step 3: Implement minimal code**
Update `action_loader.py` to inspect `agents/` and generate Gemini-compatible tool schemas dynamically.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_action_loader_agents.py -v`
Expected: PASS

---

## Priority 6: Dual-Lane Voice & Runtime Integration (`main.py`)

### Task 21: Dual-Lane Master Runtime Wiring (`main.py`)
**Files:**
- Modify: `main.py`
- Test: `tests/integration/test_dual_lane_runtime.py`

**Step 1: Write the failing test**
Test that `MaxLive._execute_tool()` passes calls through Laya Reflex Router: Lane A invokes synchronously, Lane B pushes to `TaskQueue` and returns instant voice feedback.

**Step 2: Run test to verify it fails**
Run: `pytest tests/integration/test_dual_lane_runtime.py -v`

**Step 3: Implement minimal code**
Refactor `main.py` to initialize Kill Switch (Component #0), State DB, Laya Reflex Engine, Task Queue, and dual-lane tool executor.

**Step 4: Run test to verify it passes**
Run: `pytest tests/integration/test_dual_lane_runtime.py -v`
Expected: PASS

---

### Task 22: PyQt6 HUD Live Agent Activity Widget (`ui/hud.py`)
**Files:**
- Create: `ui/components/task_list_widget.py`
- Modify: `ui/hud.py`
- Test: `tests/unit/test_hud_tasks.py`

**Step 1: Write the failing test**
Test that HUD receives task status updates via Qt signals and renders active agents, priority bands, and progress pills.

**Step 2: Run test to verify it fails**
Run: `pytest tests/unit/test_hud_tasks.py -v`

**Step 3: Implement minimal code**
Implement `TaskListWidget` with glassmorphic styles and connect queue worker events to UI signals.

**Step 4: Run test to verify it passes**
Run: `pytest tests/unit/test_hud_tasks.py -v`
Expected: PASS

---

### Task 23: Dead Code Cleanup & Dependency Consolidation
**Files:**
- Remove/Archive: `core/stt.py`, `core/tts.py`, `core/llm_client.py`, `core/installer.py`
- Modify: `requirements.txt`
- Test: `tests/integration/test_clean_build.py`

**Step 1: Verify no active imports of dead files**
Run: `grep` across codebase to confirm zero references.

**Step 2: Cleanly remove or archive dead modules**
Archive files to `core/_deprecated/` or remove.

**Step 3: Run full test suite**
Run: `pytest tests/ -v`
Expected: All tests PASS.

---

## Priority 7: End-to-End Automated Verification

### Task 24: Comprehensive E2E System Test (`tests/e2e/test_system_e2e.py`)
**Files:**
- Create: `tests/e2e/test_system_e2e.py`

**Step 1: Write end-to-end scenarios**
1. Voice command triggering sub-50ms Laya routing to Lane B.
2. Sorted lock acquisition and pre-execution snapshot.
3. Code change executed by `dev_agent` and validated by `qa_tester`.
4. Triggering Kill Switch cleanly aborting running agents within 50ms.
5. Voice command "undo" restoring snapshot to bit-for-bit accuracy.

**Step 2: Run and verify all scenarios pass**
Run: `pytest tests/e2e/test_system_e2e.py -v`
Expected: All scenarios PASS with 100% green.


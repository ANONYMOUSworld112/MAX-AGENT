# MAX-AGENT: Master Engineering Progress Tracker

> **Current Phase**: Phase 0 — Repository Forensics & Baseline  
> **Active Branch**: `max/p0-baseline`  
> **Base Commit**: `bed949416abcf4fc2d92d2ff089b31438848648e`  
> **Last Updated**: 2026-09-30  

---

## 1. Phase Status Overview

| Phase | Description | Status | Evidence Path | Gate Status |
|---|---|---|---|---|
| **P0** | **Repository Forensics, Real Architecture Docs, Component Map, Conflict Log, Threat Model, Tier 0 Characterization Tests** | **IMPLEMENTED & TESTED** | `docs/evidence/p0/tier0_test_run.txt` | **AWAITING OWNER APPROVAL** (Component Map & Conflict Log) |
| **P1** | Foundations: Data Contracts, State Machine, Clock, Event Envelope, ExecutionGateway & Policy Engine | PLANNED | — | BLOCKED on P0 Gate Approval |
| **P2** | Planning Path: Schema-Validated Intent, Fast Path, Plan Validator, Task Graph, Capability Registry, Agent Router | PLANNED | — | BLOCKED on P1 Gate Approval |
| **P3** | Scheduler, Resource Leases, Worker Pool, Desktop Actor, Cancellation, Timeouts, Emergency Stop + Watchdog | PLANNED | — | BLOCKED on P2 Gate Approval |
| **P4** | Platform Adapters, FakeDesktop, Windows Adapter, Preconditions, Observation, User Activity Guard | PLANNED | — | BLOCKED on P3 Gate Approval |
| **P5** | ApplicationRegistry, Resolution Ladder, Windows Search Flow, Launch Verification | PLANNED | — | BLOCKED on P4 Gate Approval |
| **P6** | Media Workflow & Transport Verification | PLANNED | — | BLOCKED on P5 Gate Approval |
| **P7** | Time Handling, Reminders, Calendar (Persistence, RRULE, DST, Conflicts) | PLANNED | — | BLOCKED on P6 Gate Approval |
| **P8** | ProcessManager & Terminal Mirror | PLANNED | — | BLOCKED on P7 Gate Approval |
| **P9** | OpenCode Integration & Coding Workflow (Sandbox, Scope-Check, Test-Integrity) | PLANNED | — | BLOCKED on P8 Gate Approval |
| **P10** | Concurrency Validation & Background Multi-Tasking | PLANNED | — | BLOCKED on P9 Gate Approval |
| **P11** | HUD Observability & Dashboard API Authentication Hardening | PLANNED | — | BLOCKED on P10 Gate Approval |
| **P12** | Memory Integration, Hardening Pass, Final Acceptance Verification | PLANNED | — | BLOCKED on P11 Gate Approval |

---

## 2. Phase 0 Deliverables & Forensic Accomplishments

### Completed in Phase 0 (Forensic Audit & Baseline):
- [x] Full forensic inspection of `main.py`, `ui.py`, `agents/`, `core/`, `actions/`, `memory/`, `dashboard/`, `plugins/`, `config/`, `IMPLEMENTATION_PLAN.md`, `requirements.txt`, `setup.py`, `pyproject.toml`, and `readme.md`.
- [x] Authored complete audit suite in `docs/audit/`:
  - `docs/audit/ARCHITECTURE_REAL.md` (Dual-architecture analysis: active Gemini Live vs dormant kernel)
  - `docs/audit/EXECUTION_FLOW.md` (7 input channels traced across 13 lifecycle stages)
  - `docs/audit/AGENT_INVOCATION_GRAPH.md` & `docs/audit/agent_graph.json` (Real agent graph, 0 delegation)
  - `docs/audit/AGENT_REGISTRY_AUDIT.md` (Forensic audit of all 33 agents across 5 clusters)
  - `docs/audit/AGENT_ASSIGNMENT.md` (LLM tool selection vs Reflex fallback analysis)
  - `docs/audit/PROMPT_FORENSICS.md` (Prompt sites, context injection, and prompt injection attack surfaces)
  - `docs/audit/TOOL_FORENSICS.md` (60+ tools audited: inline, actions, agents, schemas, risks)
  - `docs/audit/TASK_LIFECYCLE.md` (10-state FSM vs real ephemeral lifecycle; persistence gaps)
  - `docs/audit/CONCURRENCY.md` (Threading, asyncio, LockManager analysis, race conditions)
  - `docs/audit/DESKTOP_AUTOMATION.md` (App launch, blind Windows Search, `exec()` in desktop.py)
  - `docs/audit/CODING_WORKFLOW.md` (dev_agent.py, host pip install, OpenCode absence)
  - `docs/audit/MEMORY.md` (long_term.json, prompt injection, memory poisoning risks)
  - `docs/audit/VERIFICATION.md` (L0-L3 verification analysis, false success claims)
  - `docs/audit/FAILURE_RECOVERY.md` (Error classification, undo stack, recovery gaps)
  - `docs/audit/SECURITY.md` (37 unchoked side effects, RCE, plaintext keys, LAN exposure)
  - `docs/audit/OBSERVABILITY.md` (Current telemetry vs unified correlation tracing)
  - `docs/audit/DEAD_ARCHITECTURE.md` (Inventory of dead, dormant, and duplicated modules)
- [x] Authored complete evolution benchmark suite in `docs/evolution/`:
  - `docs/evolution/CODEX_COMPARISON.md` (Comparison against modern agent harness principles)
  - `docs/evolution/CLAUDE_STYLE_COMPARISON.md` (Comparison against Claude-style agent patterns)
  - `docs/evolution/OPENCODE_COMPARISON.md` (CodingExecutor abstraction & sandboxed OpenCode)
  - `docs/evolution/IMPROVEMENT_MATRIX.md` (32-area prioritized improvement matrix)
  - `docs/evolution/MAX_VNEXT.md` (Future target architecture and 5 engineering pillars)
  - `docs/evolution/ROADMAP.md` (10-phase prioritized evolution roadmap)
- [x] Built real evaluation harness & golden dataset in `tests/evals/`:
  - `tests/evals/golden_tasks.json` (25 representative tasks across all domains)
  - `tests/evals/harness.py` (Evaluation harness measuring route, verification, and false-success)
  - `tests/evals/test_eval_suite.py` (Pytest test suite producing empirical baseline)
  - Empirical baseline saved to `docs/evidence/p0/evals_baseline.json`:
    - Routing accuracy: **76.0%**
    - Verified success rate: **8.0%**
    - False success rate: **56.0%**
    - Multi-task support rate: **0.0%**
- [x] Authored and ran Tier 0 Characterization Tests (`tests/tier0_characterization/` with 21 tests):
  - 22/22 total automated tests passing in 1.89s.
  - Ensured zero production code changes were made during Phase 0 (pure forensic baseline).

---

## 3. Evidence Paths

- **Tier 0 Test Run Evidence**: [`docs/evidence/p0/tier0_test_run.txt`](file:///f:/MAX-AGENT/docs/evidence/p0/tier0_test_run.txt)
- **Evaluation Baseline Evidence**: [`docs/evidence/p0/evals_baseline.json`](file:///f:/MAX-AGENT/docs/evidence/p0/evals_baseline.json)
- **Full Audit Directory**: [`docs/audit/`](file:///f:/MAX-AGENT/docs/audit)
- **Evolution Benchmark Directory**: [`docs/evolution/`](file:///f:/MAX-AGENT/docs/evolution)
- **Component Map**: [`docs/COMPONENT_MAP.md`](file:///f:/MAX-AGENT/docs/COMPONENT_MAP.md)
- **Conflict Log**: [`docs/CONFLICT_LOG.md`](file:///f:/MAX-AGENT/docs/CONFLICT_LOG.md)
- **Unchoked Side Effects**: [`docs/UNCHOKED_SIDE_EFFECTS.md`](file:///f:/MAX-AGENT/docs/UNCHOKED_SIDE_EFFECTS.md)

---

## 4. Open Conflicts Requiring Owner Decision / Approval at Gate 0

1. **Conflict CF-01**: Replace false 74/74 test claims from old plan with real Tier 0 characterization test baseline.
2. **Conflict CF-02**: Upgrade 9-state machine to 14-state machine per Master Spec Section 8 in Phase 1.
3. **Conflict CF-03**: Reconcile Gemini Live fast-path with deterministic PlanValidator / ExecutionGateway choke point.
4. **Conflict CF-04**: Tag mock agents as `[NOT IMPLEMENTED]` under Rule 1-H1 until real implementations are delivered.
5. **Conflict CF-05**: Route all 37 unchoked side-effect paths through `ExecutionGateway`.
6. **Conflict CF-06**: Eliminate `exec()` arbitrary code execution in `actions/desktop.py` and replace with deterministic UIA adapters.
7. **Conflict CF-07**: Rebind dashboard from `0.0.0.0` to `127.0.0.1` and remove firewall hole-punching.
8. **Conflict CF-08**: Replace `actions/reminder.py` `schtasks.exe` scripts with daemon SQLite scheduler.
9. **Conflict CF-09**: Upgrade Watchdog from in-process thread to out-of-process watchdog process with global emergency hotkey.

---

## 5. Next Steps

Upon human owner approval of the **Phase 0 Gate** (Component Map & Conflict Log):
1. Tag Phase 0 commit: `git tag gate-p0-approved`.
2. Create Phase 1 branch: `git checkout -b max/p1-foundations`.
3. Proceed with Phase 1 deliverables (Data contracts, 14-state machine, injectable Clock, event envelope, ExecutionGateway & PolicyEngine, banned-import AST scan).

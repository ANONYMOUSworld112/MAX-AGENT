# MAX-AGENT — Evolution Benchmark: Claude-Style Agent Architecture Comparison

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Principles of Modern Multi-Agent & Autonomous Systems

Anthropic's architectural guidance for autonomous agents emphasizes:
- **Long-horizon state tracking**: Agents must maintain structured progress across multiple turns without drifting.
- **Verification-driven execution**: Never trust an agent's self-reported success; verify state through deterministic tools.
- **Reusable skills**: Package complex workflows into modular, reusable capabilities with explicit pre- and post-conditions.
- **Controlled subagent delegation**: Subagents are spawned for independent, bounded tasks with specialized context packages, not an open-ended swarm.

---

## 2. Area-by-Area Forensic Comparison

| Architectural Principle | Current MAX State | Target Pattern | Identified Gap | Priority | Implementation Idea | Risks | Expected Benefit |
|---|---|---|---|---|---|---|---|
| **1. Long-Horizon State Tracking** | Single-shot execution. Multi-turn tasks lose state on turn completion. | Structured `TaskGraph` with persistent state machine across all subtasks. | Cannot maintain state across complex workflows (e.g. build + test + deploy). | **P1 (High)** | Store `TaskGraph` in `StateDB`. Each subtask records status, output artifacts, and verification evidence. | Graph serialization complexity. | Reliable multi-step autonomous execution without goal drift. |
| **2. Verification-First Architecture** | Actions return string; success assumed if no exception. | Every capability defines: Preconditions, Action, Postconditions, Verifier. | Frequent false-positive completion reports. | **P0 (Critical)**| Implement `VerificationEngine` with deterministic L2/L3 verifiers (process, window, media session). | Flaky checks if target app is slow to start. | 100% truthful reporting; eliminates hallucinated completions. |
| **3. Reusable Skill System** | Rigid Python functions in `actions/*.py` coupled to `main.py` UI state. | Modular skills directory (`skills/<name>/SKILL.md`) defining tools, schemas, and verification rules. | Difficult to extend MAX with new capabilities cleanly. | **P2 (Medium)**| Create `skills/` loader with standardized manifest format (inputs, outputs, risk level, verifier). | Runtime loading overhead. | Modular, community-extensible capability ecosystem. |
| **4. Subagent Delegation** | 33 mock agents registered as flat tools; zero actual delegation. | Orchestrator spawns specialized worker processes with trimmed context packages. | Flat tool list degrades LLM reasoning; no independent workers. | **P2 (Medium)**| Orchestrator creates `TaskGraph` and delegates subtasks to specialized headless workers (e.g. CodingWorker). | IPC and process management complexity. | Isolated failure boundaries; specialist models for specialized tasks. |
| **5. Self-Correction Loop** | Basic traceback parsing in `dev_agent.py` (5 retries). Bounded but unprincipled. | Structured loop: Plan ──► Execute ──► Observe ──► Verify ──► Critique ──► Replan. | If fix fails, model repeats same error without alternative strategy. | **P1 (High)** | Feed structured failure report (error class, traceback, missing postcondition) into bounded replanner. | Risk of infinite loops if budgets not enforced. | Autonomous recovery from transient compilation/syntax errors. |
| **6. Parallel Independent Work** | Purely sequential tool execution in single loop. | Independent TaskGraph nodes run concurrently subject to resource leases. | Unrelated tasks (build code vs set reminder) block each other. | **P2 (Medium)**| Scheduler inspects dependency graph; dispatches independent nodes to worker pool with resource locks. | Concurrency race conditions. | Multiplies throughput; background tasks run without freezing voice. |
| **7. Structured Progress Tracking** | UI chat log lines only (`SYS: ...`). | Structured milestone progress events emitted to HUD and Dashboard. | User has no visibility into what step of a multi-step task is running. | **P1 (High)** | Emit `TaskProgress(step_n, total_steps, current_action)` events to live HUD widget. | UI event flooding. | Crystal-clear human visibility into autonomous operations. |

---

## 3. Core Architectural Takeaway

The primary lesson from Claude-style agent systems is **Simplicity over Swarms**:
- Do not build a chaotic swarm of 33 interacting agents where nobody knows who is responsible for what.
- Build a **robust, deterministic orchestrator** that delegates to **focused, single-responsibility workers** under strict verification and resource controls.

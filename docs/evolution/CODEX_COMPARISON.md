# MAX-AGENT — Evolution Benchmark: Codex Architectural Comparison

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Principles of Modern Agent Harness Architectures

Modern production agent systems (such as OpenAI's Codex harness) separate the **Harness / Control Plane** from the **Execution Environment / Sandbox**:

1. **The Control Plane** owns durable sessions, event streaming, context management, tool dispatching, approval gates, risk policies, and recovery.
2. **The Execution Plane** is an isolated, ephemeral sandbox (container, virtual machine, or disposable worktree) where side effects occur under strict resource and scope constraints.

---

## 2. Area-by-Area Forensic Comparison

| Architectural Area | Current MAX State | Target Architectural Pattern | Identified Gap | Priority | Implementation Idea | Risks | Expected Benefit |
|---|---|---|---|---|---|---|---|
| **1. Sandboxed Execution** | Host execution; `dev_agent` runs `pip install` on host Python; `desktop.py` runs `exec()`. | Ephemeral, isolated workspace (git worktree + local venv) for coding tasks. | Complete absence of containment. | **P0 (Critical)** | Create disposable git worktrees in `~/Desktop/MaxProjects/.worktrees/` and isolated virtual environments. | Slower startup (2-3s for venv creation). | Eliminates host Python corruption and PyPI typosquatting risks. |
| **2. Approval Boundaries** | Ad-hoc `confirm_gate` used only for power/wifi; missing on file delete, code execution, and emails. | Policy-computed confirmation gate based on (action type, canonical params, provenance). | Human confirmation is optional and bypassed by LLM. | **P0 (Critical)** | Central `PolicyEngine` in `ExecutionGateway`. High-risk actions require explicit typed phrase or HUD confirmation. | User fatigue if over-prompted. | Prevents accidental destructive actions. |
| **3. Project-Scoped Instructions** | Single global `core/prompt.txt` loaded for all tasks. | Hierarchical context injection: System Prompt → Project Rules (`AGENTS.md`) → Task Spec. | No project-level rule recognition. | **P1 (High)** | Scan target project root for `.agents/rules` or `AGENTS.md` and append to worker prompt. | Token budget consumption. | Adheres to repository conventions and project standards. |
| **4. Durable Sessions** | RAM-only resumption handle (`self._resume_handle`); dropped on restart. | Event-sourced durable session state backed by persistent transactional log. | Restart wipes all active tasks and conversation context. | **P1 (High)** | Persist event envelopes to SQLite `StateDB` in WAL mode. Recover session on startup. | Database lock contention on concurrent writes. | Survives process restarts and system reboots. |
| **5. Streaming Events** | Raw audio streaming; text output logged after turn complete. | Structured event streaming (`EventEnvelope`) emitting lifecycle events in real time. | UI only sees bulk completions; no granular progress. | **P1 (High)** | EventBus with publish/subscribe architecture publishing `TaskStarted`, `StepExecuted`, etc. | WebSocket bandwidth overhead. | Real-time HUD progress bar and transparent user observability. |
| **6. Resumable Work & Checkpoints** | None. Interrupted tasks are lost. | Checkpoint commits in git worktree after each successful subtask. | Partial failures leave uncommitted broken state. | **P2 (Medium)**| Create git checkpoint commits (`git commit -m "checkpoint: step k"`) after each test pass. | Disk usage from git objects. | Clean rollback to last known green state on failure. |
| **7. Context Compaction** | Sliding window on Gemini Live session; manual memory search. | Hierarchical context compression: active turn context, compacted summary, structured memory store. | Prompt token saturation on long-running tasks. | **P2 (Medium)**| Extract completed subtask outputs into summarized task manifest; prune tool call history. | Loss of granular details. | High reliability on multi-step, long-horizon workflows. |
| **8. Structured Tool Invocation** | 60+ flat JSON tool schemas sent to Gemini Live in one large array. | Two-stage routing: Intent/Plan proposal → Deterministic capability router with schema validation. | Tool namespace pollution, high model confusion rate. | **P1 (High)**| Expose 1 structured proposal schema to LLM; resolve capability locally via `CapabilityRegistry`. | Extra round-trip for ambiguous intents. | 95%+ routing accuracy; eliminates hallucinated tool calls. |
| **9. Traceability & Audit** | Ephemeral `print()` statements in stdout. | Cryptographic, hash-chained audit log with unified `correlation_id`. | Zero forensic accountability for past actions. | **P1 (High)**| Implement `audit_log` table writes with SHA-256 chaining on every side effect. | Minimal compute overhead for hashing. | Complete forensic explainability of all agent decisions. |
| **10. Isolated Workspaces** | Code written directly into `~/Desktop/MaxProjects/`. | Dedicated directory with pre- and post-execution file hash auditing. | Modifies host filesystem without boundary checks. | **P1 (High)**| Boundary checker asserting all file operations remain within the assigned workspace path. | Path canonicalization edge cases (symlinks/8.3). | Prevents path traversal and unintended file overwrites. |

---

## 3. Core Architectural Takeaway

Codex's fundamental strength is **determinism at the boundaries**:
- The model proposes code and actions.
- The harness controls the environment, verifies the output, enforces security policies, and commits changes.

MAX must adopt this exact principle: **The LLM proposes; deterministic MAX code decides, verifies, and executes.**

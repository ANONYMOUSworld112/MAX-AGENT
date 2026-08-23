# MAX OS — Complete Project Plan
### Full Build Roadmap: MAX Architecture + OpenJarvis Feature Merge
### Source documents: ARCHITECTURE.md · PRD.md · DECISIONS.md · AGENTS.md · MAX_OpenJarvis_Unified_Features.md · OpenJarvis repo

---

## 1. Project Identity

**MAX OS** is a localhost-only, multi-agent AI assistant with production-grade reliability engineering. It merges MAX's safety-first architecture (code-enforced gates, deadlock prevention, circuit breakers, session-resumable builds) with OpenJarvis's breadth (skills marketplace, local inference, multi-channel I/O, benchmarking, learning loops).

**Core differentiator:** Not "another personal AI" — the reliability engineering that this category mostly skips. Deadlock prevention by construction, code-enforced human gates, idempotent task execution, full error taxonomy, and a build protocol that survives tool switches and quota resets.

---

## 2. Tech Stack

| Layer | Technology | Notes |
|---|---|---|
| Language | Python 3.11+ | Matches both MAX and OpenJarvis |
| State DB | SQLite (WAL mode) | `max_state.db` — build progress + runtime trace |
| Memory DB | SQLite | `max_memory.db` — 5-layer memory system |
| Secrets | `keyring` + AES-256 fallback | OS keychain, never plaintext |
| LLM (cloud) | Anthropic Claude, OpenAI, Google Gemini | Via `anthropic`, `openai`, `google-genai` SDKs |
| LLM (local) | Ollama, vLLM, MLX (macOS) | OpenJarvis's local-first inference path |
| LLM Router | LiteLLM | Unified interface across providers |
| CLI | Click + Rich | Command-line interface |
| Server | FastAPI + Uvicorn | REST/WebSocket API for desktop GUI + channels |
| Desktop GUI | Electron (frontend/) | OpenJarvis-style desktop app |
| Search | DuckDuckGo (`ddgs`), Tavily | Web search for Research/Web Search agents |
| Embeddings | `sentence-transformers`, FAISS | Local vector memory for Notes + Memory |
| Speech | `faster-whisper` (STT), TTS | Voice I/O |
| Process control | `psutil` | Kill switch, watchdog, system monitoring |
| Testing | `pytest`, `pytest-asyncio`, `pytest-cov` | Full test suite |
| Sandbox | Docker, WASM (`wasmtime`) | Skill execution sandboxing |
| Scheduler | `croniter` | Cron-based agent scheduling |

---

## 3. Full Agent Roster (33 agents, unified)

### Tier 1 — v1 Core (Phase 1–3)

| Agent | Permission | Execution Mode | Backend | Phase |
|---|---|---|---|---|
| Calendar Agent | auto | on_demand | Native | 2 |
| Notes Agent | auto | on_demand | Native | 2 |
| Coding Agent | confirm (file write) | on_demand | opencode / Antigravity | 1 |
| Deploy Agent | confirm (always for prod) | on_demand | Git CLI/API | 2–3 |

### Tier 2 — First Expansion (Phase 5–6)

| Agent | Permission | Execution Mode | Source |
|---|---|---|---|
| Web Search Agent | auto (read-only) | on_demand | MAX design |
| Research Agent / Deep Research | auto, quota-warn | on_demand | MAX + OpenJarvis `deep_research` |
| Document Agent | auto draft, confirm finalize | on_demand | MAX design |
| Application-Assist Agent | confirm (never auto-submit) | on_demand | MAX design |

### Tier 3 — Daily-Life (Phase 7)

| Agent | Permission | Execution Mode | Source |
|---|---|---|---|
| Inbox Agent | auto read, confirm send | scheduled | MAX design |
| Expense Agent | auto | on_demand | MAX design |
| Founder CRM Agent | auto | on_demand | MAX design |
| Content Draft Agent | auto draft, never auto-post | on_demand | MAX design |
| Daily Brief Agent | auto | scheduled | MAX + OpenJarvis `morning_digest` |
| Monitor Agent | auto | continuous | OpenJarvis `monitor_operative` |

### Tier 4 — Engineering/Quality (Phase 7)

| Agent | Permission | Execution Mode | Source |
|---|---|---|---|
| Architecture Review Agent | auto | on_demand | MAX design |
| Security Agent | auto | scheduled | MAX design |
| Testing Agent | auto | on_demand | MAX design |
| Debug Agent | auto | on_demand | MAX design |
| Documentation Agent | auto | on_demand | MAX design |
| Code Review Agent | auto | on_demand | MAX design |

### Tier 5 — Big Infrastructure (Phase 8)

| Agent | Permission | Execution Mode | Source |
|---|---|---|---|
| Database Agent | confirm on writes | on_demand | MAX design |
| Cloud/Infra Agent | confirm on cost-impacting | on_demand | MAX design |
| Data Pipeline Agent | confirm | on_demand | MAX design |
| Backup/DR Agent | confirm on restore | scheduled | MAX design |
| Analytics Agent | auto | scheduled | MAX design |

### Tier 6 — Input Control (Phase 8+, highest risk)

| Agent | Permission | Execution Mode | Source |
|---|---|---|---|
| Keyboard Agent | confirm, blocked on credentials | on_demand | MAX design |
| Mouse Agent | confirm | on_demand | MAX design |
| Screen Agent | auto (read), confirm (act) | on_demand | MAX design |

### Orchestration (not worker agents)

| Component | Type | Role |
|---|---|---|
| Main Agent | orchestration | Owns conversation, invokes decomposition |
| Prompt Agent | orchestration | Shapes per-step context, preference retrieval |
| Orchestrator | orchestration | OpenJarvis automatic tool selection |

---

## 4. Infrastructure Components (deterministic, no LLM)

| Component | Phase | Description |
|---|---|---|
| Kill Switch (Component #0) | 0 | Boot dependency, halts everything within 1s |
| Local Encrypted Vault | 0 | `keyring`-backed secrets, never plaintext |
| Data Boundary Policy | 0 | Strips/masks outbound LLM payloads |
| Task State Machine | 1 | CREATED→QUEUED→RUNNING→RECONCILING→DONE |
| Idempotency Keys | 1 | UUID per task, prevents duplicate side effects |
| Snapshot/Rollback | 1 | Pre-RUNNING snapshot, full restore on failure |
| Intent Classifier | 1 | Keyword-first, LLM fallback for ambiguous |
| Cheap Router | 1 | Fast-path routing before classifier |
| Priority Queue | 2 | 5 bands (0=safety → 4=scheduled), aging |
| Resource Lock Manager | 2 | Sorted-order, all-or-nothing, timeout backstop |
| Heartbeat Watchdog | 2 | 45s timeout → kill + rollback |
| Reconciliation Check | 2 | Verify agent-reported vs real state |
| Permission Manager | 2 | auto/confirm/blocked, immune to phrasing |
| Dependency Graph Planner | 2 | Multi-agent task ordering |
| Circuit Breaker (per-agent) | 4 | 5 failures → open, reject until half-open |
| Dead Letter Queue | 4 | Exhausted-retry tasks visible + requeueable |
| Error Taxonomy | 4 | transient/validation/permission/destructive/systemic |
| Retry Policy | 4 | Jittered backoff, per error class |
| Skills Loader | 6 | Load/register/sandbox external skills |
| Model Router | 6 | Local/cloud model selection + fallback |
| Scheduler Service | 6 | Cron-based agent execution |
| Memory System | 6 | 5-layer: identity/preference/behavioral/project/conversation |
| Channel Manager | 7 | Abstract multi-channel I/O |
| Benchmark Runner | 7 | Energy/FLOPs/cost/accuracy evals |
| MCP Server | 8 | Model Context Protocol endpoint |
| Sandbox Manager | 8 | Docker/WASM execution sandboxing |
| Voice Pipeline | 8 | Whisper STT + TTS, infra-tier (no task state) |

---

## 5. Database Schema (tables overview)

### Build Progress Tables (existing)
`phases` · `steps` · `sessions` · `decisions_log` · `blockers`

### Runtime Tables (existing)
`task_trace` · `outcome_tracker` · `dead_letter_queue` · `circuit_breaker_state`

### New Tables (Phase 0 addition + OpenJarvis merge)
| Table | Purpose | Phase Added |
|---|---|---|
| `api_quota_usage` | Per-service API metering (missing from original schema) | 0 |
| `agent_registry` | Agents with tier, execution_mode, permission, status | 0 |
| `skill_registry` | Skill marketplace equivalent | 6 |
| `model_registry` | Local + cloud model tracking | 6 |
| `scheduled_tasks` | Cron-based task scheduling | 6 |
| `channel_registry` | Multi-channel I/O config | 7 |
| `benchmark_results` | Eval metrics (energy, FLOPs, cost, accuracy) | 7 |

### Memory Tables (from memory_schema.sql)
`memory_identity` · `memory_preferences` · `memory_behavioral` · `memory_project_context` · `memory_conversation`

---

## 6. Project File Structure

```
max-os/
├── core/                          # Infrastructure (deterministic, no LLM)
│   ├── __init__.py
│   ├── kill_switch.py             # Component #0 — boot dependency
│   ├── vault.py                   # Encrypted secrets via keyring
│   ├── data_boundary.py           # Outbound LLM payload sanitization
│   ├── task_state.py              # Task lifecycle state machine + idempotency
│   ├── snapshot.py                # Pre-run snapshot + rollback
│   ├── intent_classifier.py       # Keyword-first, LLM fallback routing
│   ├── permissions.py             # auto/confirm/blocked tier enforcement
│   ├── lock_manager.py            # Sorted-order, all-or-nothing locks
│   ├── watchdog.py                # Heartbeat monitoring + kill
│   ├── reconciliation.py          # Agent-reported vs real state verification
│   ├── planner.py                 # Dependency graph + multi-agent ordering
│   ├── errors.py                  # Error taxonomy + classification
│   ├── retry.py                   # Jittered backoff per error class
│   ├── circuit_breaker.py         # Per-agent circuit breaker
│   ├── queue.py                   # In-process priority queue with aging
│   ├── voice_output.py            # TTS — infra tier, not task
│   ├── scheduler.py               # Cron-based agent scheduling
│   ├── model_router.py            # Local/cloud model selection
│   ├── skill_loader.py            # Skill registration + sandbox
│   ├── channel_manager.py         # Multi-channel I/O abstraction
│   ├── sandbox.py                 # Docker/WASM execution sandbox
│   └── memory/                    # 5-layer memory system
│       ├── __init__.py
│       ├── identity.py
│       ├── preferences.py
│       ├── behavioral.py
│       ├── project_context.py
│       └── conversation.py
│
├── agents/                        # LLM-powered agents (exercise judgment)
│   ├── __init__.py
│   ├── calendar.py
│   ├── notes.py
│   ├── coding.py
│   ├── deploy.py
│   ├── websearch.py
│   ├── research.py
│   ├── document.py
│   ├── application_assist.py
│   ├── inbox.py
│   ├── expense.py
│   ├── founder_crm.py
│   ├── content_draft.py
│   ├── daily_brief.py
│   ├── monitor.py
│   ├── architecture_review.py
│   ├── security.py
│   ├── testing.py
│   ├── debug.py
│   ├── documentation.py
│   ├── code_review.py
│   ├── database.py
│   ├── cloud_infra.py
│   ├── data_pipeline.py
│   ├── backup_dr.py
│   ├── analytics.py
│   ├── keyboard.py
│   ├── mouse.py
│   └── screen.py
│
├── cli/                           # CLI interface
│   ├── __init__.py
│   ├── main.py                    # Entry point: `max` command
│   ├── trace.py                   # `max trace` — inspect task_trace
│   ├── dlq.py                     # `max dlq` — dead letter queue viewer
│   ├── doctor.py                  # `max doctor` — system status check
│   └── bench.py                   # `max bench` — run benchmarks
│
├── server/                        # FastAPI server for GUI + channels
│   ├── __init__.py
│   ├── app.py                     # FastAPI application
│   ├── routes/                    # API endpoints
│   └── websocket.py               # Real-time communication
│
├── channels/                      # Communication channel adapters
│   ├── __init__.py
│   ├── telegram.py
│   ├── discord.py
│   ├── slack.py
│   └── ...                        # 15+ channel adapters
│
├── desktop/                       # Electron desktop GUI
│   ├── package.json
│   ├── main.js
│   └── frontend/
│
├── skills/                        # Skill definitions
│   ├── registry.json
│   └── built_in/
│
├── configs/                       # Configuration presets
│   ├── default.toml
│   └── presets/
│
├── tests/                         # Test suites
│   ├── test_phase0_foundation.py
│   ├── test_phase1_e2e.py
│   ├── test_phase2_concurrency.py
│   ├── test_kill_switch.py
│   ├── test_vault.py
│   ├── test_data_boundary.py
│   ├── test_gate_bypass.py
│   └── test_chaos.py
│
├── max_state_schema.sql           # State DB schema
├── memory_schema.sql              # Memory DB schema
├── init_db.py                     # DB initialization + seeding
├── requirements.txt               # Python dependencies
├── pyproject.toml                 # Package configuration
├── ARCHITECTURE.md                # Phased build plan
├── AGENTS.md                      # Agent roster + permissions
├── DECISIONS.md                   # Architectural decisions log
├── PRD.md                         # Product requirements
├── TASKS.md                       # Live snapshot from max_state.db
└── MAX_MASTER_PROMPT.md           # Build agent operating rules
```

---

## 7. Phased Build Plan

### Phase 0 — Foundation & Safety
**Goal:** Nothing else may build until this phase is done. Kill Switch is Component #0 by rule.

| Step | Title | Depends On | Acceptance Criteria | Files |
|---|---|---|---|---|
| 0.1 | Repo + state DB init | — | `max_state.db` exists; all tables present (original 10 + `api_quota_usage` + `agent_registry` = 12); phases/steps seeded from ARCHITECTURE.md; agent_registry seeded from AGENTS.md | `max_state.db`, `max_state_schema.sql`, `init_db.py` |
| 0.2 | Kill Switch service | 0.1 | Main Agent boot checks Kill Switch status, refuses to initialize until `armed`. Triggering mid-task halts within 1s (tested with dummy task) | `core/kill_switch.py` |
| 0.3 | Local Encrypted Vault | 0.1 | No plaintext key anywhere in repo (including test fixtures). Retrieving a stored key via Vault works; reading underlying storage doesn't expose plaintext | `core/vault.py` |
| 0.4 | Data Boundary Policy | 0.3 | A test with a deliberately planted fake API key in an out-of-scope file confirms it never appears in the outbound payload | `core/data_boundary.py` |

---

### Phase 1 — Core Loop, One Agent
**Goal:** input → plan → code → test → commit works end to end.

| Step | Title | Depends On | Acceptance Criteria | Files |
|---|---|---|---|---|
| 1.1 | Task state machine | 0.1 | Full lifecycle visible via `SELECT * FROM task_trace WHERE task_id = ?` at every stage | `core/task_state.py` |
| 1.2 | Idempotency keys | 1.1 | Re-running same key twice produces one side effect, not two | `core/task_state.py` |
| 1.3 | Snapshot/rollback | 1.1 | Task killed mid-write leaves zero partial files after rollback | `core/snapshot.py` |
| 1.4 | Coding Agent (minimal) | 1.2, 1.3 | "Write hello world" produces working file + passing self-test | `agents/coding.py` |
| 1.5 | Intent Classifier | 1.4 | Unambiguous coding requests skip LLM classification; ambiguous input asks clarifying question | `core/intent_classifier.py` |
| 1.6 | Trace Log Viewer | 1.1 | `max trace --last 20` and `max trace --agent coding --failures-only` return correct output | `cli/trace.py` |
| 1.7 | E2E Phase 1 verify | 1.5, 1.6 | Real "build me X" completes, commits, visible in trace log, unattended | `tests/test_phase1_e2e.py` |

---

### Phase 2 — Multi-Agent + Synchronization
**Goal:** The floor the rest of the system stands on.

| Step | Title | Depends On | Acceptance Criteria | Files |
|---|---|---|---|---|
| 2.1 | Calendar + Notes Agents | 1.7 | Both auto-tier, no locks needed | `agents/calendar.py`, `agents/notes.py` |
| 2.2 | Deploy Agent (repo-push) | 1.7 | Creates/pushes to GitHub via API, confirm-gated | `agents/deploy.py` |
| 2.3 | Resource Lock Manager | 2.1, 2.2 | Reversed-order two-lock test completes without deadlock | `core/lock_manager.py` |
| 2.4 | Heartbeat Watchdog | 2.3, 1.3 | No-heartbeat task killed + rolled back within 45s | `core/watchdog.py` |
| 2.5 | Reconciliation Check | 2.1, 2.2 | Agent self-reported "success" that doesn't match real state → treated as failure | `core/reconciliation.py` |
| 2.6 | Dependency graph Planner | 2.2, 2.1 | "Build it, deploy it, remind me" runs 3 agents in correct order | `core/planner.py` |
| 2.7 | Permission Manager | 2.2 | 5 bypass phrasings all fail to skip approval | `core/permissions.py` |
| 2.8 | Concurrency verification | 2.3, 2.7 | Two deploy requests for same project — second queues, never races | `tests/test_phase2_concurrency.py` |

---

### Phase 3 — Deployment Pipeline (Production Mode)
**Goal:** Full 9-stage deployment pipeline with code-enforced approval gate.

| Step | Title | Depends On | Acceptance Criteria | Files |
|---|---|---|---|---|
| 3.1 | DA-1 through DA-6 | 2.8 | Preflight through staging run autonomously | `agents/deploy.py` |
| 3.2 | DA-7 Production Gate | 3.1 | Gate enforced inside `deploy_prod()` — no code path reaches prod without verified approval token, even calling directly | `agents/deploy.py` |
| 3.3 | DA-8/DA-9 Prod deploy + monitor | 3.2 | Failed post-deploy health check triggers auto-rollback | `agents/deploy.py`, `core/outcome_tracker.py` |

---

### Phase 4 — Resilience Infrastructure
**Goal:** Error handling worthy of the word "OS."

| Step | Title | Depends On | Acceptance Criteria | Files |
|---|---|---|---|---|
| 4.1 | Error taxonomy | 3.3 | Every error classified before handling logic runs | `core/errors.py` |
| 4.2 | Retry policy | 4.1 | 5 simultaneous transient failures retry at spread-out times | `core/retry.py` |
| 4.3 | Circuit breaker | 4.1 | 5 consecutive failures opens breaker; 6th rejected instantly; other agents unaffected | `core/circuit_breaker.py` |
| 4.4 | Dead Letter Queue | 4.2 | `max dlq --list` shows exhausted-retry tasks with full history | `cli/dlq.py` |
| 4.5 | **SCOPE CHECKPOINT** | 4.1–4.4 | All prior steps verified done; human confirms readiness to expand scope | *(sign-off, no code)* |

---

### Phase 5 — First Scope Expansion
**Goal:** First agents beyond the v1 four. Only after 4.5 is signed off.

| Step | Title | Depends On | Acceptance Criteria | Files |
|---|---|---|---|---|
| 5.1 | Web Search Agent | 4.5 | Explicit trigger only; quota-checked; graceful degradation | `agents/websearch.py` |
| 5.2 | Voice Output (TTS) | 4.5 | Infra-tier, never enters task_trace; failure degrades to text-only | `core/voice_output.py` |
| 5.3 | Research Agent | 5.1 | Multi-query deep research with citations; quota-warn before heavy requests | `agents/research.py` |
| 5.4 | Document Agent | 4.5 | PPT/PDF generation using real tooling, not coding CLI | `agents/document.py` |
| 5.5 | Application-Assist Agent | 4.5 | Drafts job applications; never auto-submits (LinkedIn ToS per D8) | `agents/application_assist.py` |

---

### Phase 6 — OpenJarvis Integration: Core Infrastructure
**Goal:** Adopt OpenJarvis's infrastructure primitives into MAX's architecture.

| Step | Title | Depends On | Acceptance Criteria | Files |
|---|---|---|---|---|
| 6.1 | Multi-model backend | 5.1 | Agents can use Ollama (local), OpenAI, Anthropic, or Google; model_registry tracks all; LiteLLM router provides unified interface; fallback from local→cloud works | `core/model_router.py` |
| 6.2 | Skills framework | 4.5 | Skills can be registered, loaded, and executed in sandboxed environments; skill_registry tracks all; built-in skills work; `max skill list` CLI command works | `core/skill_loader.py`, `skills/` |
| 6.3 | Scheduler service | 4.5 | Agents with `scheduled` or `continuous` execution_mode run on cron schedules; scheduled_tasks table tracks runs; `max schedule list` works | `core/scheduler.py` |
| 6.4 | Memory system | 4.5 | 5-layer memory (identity, preferences, behavioral, project context, conversation) is functional; Prompt Agent reads memory for context; FAISS vector search works for Notes Agent retrieval | `core/memory/`, `memory_schema.sql` |
| 6.5 | FastAPI server | 6.1 | REST API + WebSocket server; agents callable via API; authentication for local use; serves desktop GUI frontend | `server/` |

---

### Phase 7 — OpenJarvis Integration: Agent Expansion + Channels
**Goal:** Expand agent roster and add multi-channel communication.

| Step | Title | Depends On | Acceptance Criteria | Files |
|---|---|---|---|---|
| 7.1 | Daily-life agents | 6.4 | Inbox, Expense, CRM, Content Draft, Daily Brief, Monitor agents functional | `agents/inbox.py` through `agents/monitor.py` |
| 7.2 | Engineering agents | 6.2 | Architecture Review, Security, Testing, Debug, Documentation, Code Review agents functional | `agents/architecture_review.py` through `agents/code_review.py` |
| 7.3 | Communication channels | 6.5 | Abstract channel interface; CLI channel works (already built); at least Telegram + Discord channels functional | `channels/`, `core/channel_manager.py` |
| 7.4 | Evaluation framework | 6.1 | Benchmarks track energy, FLOPs, latency, cost alongside accuracy; `max bench run` and `max bench results` CLI commands work; benchmark_results table populated | `cli/bench.py` |
| 7.5 | Agent-to-Agent protocol | 7.1 | Agents can delegate subtasks to other agents through the planner; A2A messages traceable in task_trace | `core/planner.py` (extended) |

---

### Phase 8 — OpenJarvis Integration: Platform Features
**Goal:** Full platform capabilities — GUI, installers, advanced sandboxing.

| Step | Title | Depends On | Acceptance Criteria | Files |
|---|---|---|---|---|
| 8.1 | Big infrastructure agents | 7.2 | Database, Cloud/Infra, Data Pipeline, Backup/DR, Analytics agents functional | `agents/database.py` through `agents/analytics.py` |
| 8.2 | MCP server | 6.5 | Model Context Protocol endpoint; external tools can connect to MAX as an MCP server | `server/mcp.py` |
| 8.3 | Desktop GUI | 6.5 | Electron app with chat interface, agent status, trace viewer, settings | `desktop/` |
| 8.4 | Speech I/O | 5.2 | Whisper STT + existing TTS; voice-in → agent → voice-out loop functional | `core/speech.py` |
| 8.5 | Advanced sandboxing | 6.2 | Docker and WASM sandboxes for skill execution; sandboxed skills can't access filesystem or network beyond declared permissions | `core/sandbox.py` |
| 8.6 | Multi-platform installers | 8.3 | One-line install scripts for macOS, Linux, WSL2, Windows; `max doctor` checks all dependencies | `scripts/install.sh`, `scripts/install.ps1` |
| 8.7 | Input control agents | 8.5 | Keyboard, Mouse, Screen agents with full sandboxing; credential fields are hard-blocked; all actions logged to Session Recorder | `agents/keyboard.py`, `agents/mouse.py`, `agents/screen.py` |
| 8.8 | Learning loop | 7.4 | Trace data → model improvement feedback; skill optimization via DSPy (OpenJarvis's `learning-dspy`); outcome_tracker informs future planning | `core/learning.py` |

---

## 8. Dependency Graph (visual)

```
Phase 0: Foundation
  0.1 ─────┬──── 0.2 (Kill Switch)
           ├──── 0.3 (Vault) ──── 0.4 (Data Boundary)
           │
Phase 1: Core Loop
           ├──── 1.1 (Task SM) ──┬── 1.2 (Idempotency) ──┐
           │                     ├── 1.3 (Snapshot)  ──────┤
           │                     └── 1.6 (Trace CLI)       │
           │                                               ▼
           │                                    1.4 (Coding Agent)
           │                                               │
           │                                    1.5 (Intent Classifier)
           │                                               │
           │                                    1.7 (E2E Test)
           │                                          │
Phase 2: Multi-Agent + Sync                           │
           │                     2.1 (Cal+Notes) ◄────┘
           │                     2.2 (Deploy) ◄───────┘
           │                          │    │
           │                     2.3 (Lock Mgr) ◄── 2.1, 2.2
           │                     2.4 (Watchdog) ◄── 2.3, 1.3
           │                     2.5 (Reconcile) ◄── 2.1, 2.2
           │                     2.6 (Planner) ◄── 2.1, 2.2
           │                     2.7 (Permissions) ◄── 2.2
           │                     2.8 (Concurrency Test) ◄── 2.3, 2.7
           │                                          │
Phase 3: Deploy Pipeline                              │
           │                     3.1 (DA 1-6) ◄───────┘
           │                     3.2 (Prod Gate) ◄── 3.1
           │                     3.3 (Prod+Monitor) ◄── 3.2
           │                                          │
Phase 4: Resilience                                   │
           │                     4.1 (Error Tax) ◄────┘
           │                     4.2 (Retry) ◄── 4.1
           │                     4.3 (Circuit Brk) ◄── 4.1
           │                     4.4 (DLQ) ◄── 4.2
           │                     4.5 ★ SCOPE CHECKPOINT ★ ◄── 4.1-4.4
           │                                          │
Phase 5: First Expansion                              │
           │                     5.1-5.5 ◄────────────┘
           │                                          │
Phase 6: OJ Core Infra                               │
           │                     6.1-6.5 ◄────────────┘
           │                                          │
Phase 7: OJ Agents + Channels                        │
           │                     7.1-7.5 ◄────────────┘
           │                                          │
Phase 8: OJ Platform                                  │
                                 8.1-8.8 ◄────────────┘
```

---

## 9. Timeline Estimates

| Phase | Scope | Estimated Duration | Parallelism |
|---|---|---|---|
| **Phase 0** | Foundation (4 steps) | 2 days | 0.2+0.3 can run in parallel after 0.1 |
| **Phase 1** | Core loop + Coding Agent (7 steps) | 5 days | 1.2+1.3+1.6 parallel after 1.1 |
| **Phase 2** | Multi-agent + sync (8 steps) | 5 days | 2.1+2.2 parallel after 1.7 |
| **Phase 3** | Deploy pipeline (3 steps) | 3 days | Sequential |
| **Phase 4** | Resilience (5 steps) | 4 days | 4.2+4.3 parallel after 4.1 |
| **Phase 5** | First expansion (5 steps) | 5 days | 5.1-5.5 mostly parallel after 4.5 |
| **Phase 6** | OJ core infra (5 steps) | 7 days | 6.2+6.3+6.4 parallel after 4.5 |
| **Phase 7** | OJ agents + channels (5 steps) | 7 days | 7.1+7.2 parallel |
| **Phase 8** | OJ platform (8 steps) | 10 days | 8.2+8.3+8.4 parallel |
| **Total** | **50+ steps** | **~48 days** | |

> [!NOTE]
> These are coding-session estimates, not calendar time. Actual calendar time depends on session frequency and quota availability. The session-resumable build protocol ensures no progress is lost between sessions regardless of gaps.

---

## 10. Risk Matrix

| Risk | Severity | Mitigation |
|---|---|---|
| Scope creep derails shipping | **Critical** | Phase 4.5 scope checkpoint is a hard gate. Steps table enforces order. |
| Kill switch not tested against real failures | High | Step 0.2 requires a deliberately long-running dummy task test |
| Plaintext secrets leak | High | Vault (0.3) + data boundary (0.4) + repo audit before any public push |
| Production gate bypassable via phrasing | **Critical** | 5-phrasing adversarial test list in AGENTS.md; gate lives inside function, not UI |
| Local inference models too slow/dumb | Medium | Cloud API remains default (D15); local is fallback, not requirement |
| OpenJarvis skill sandboxing insufficient | High | Docker + WASM sandboxing in Phase 8.5; skills can't escape sandbox |
| Multi-channel auth complexity | Medium | OAuth handled per-channel; failures degrade to CLI gracefully |
| Session state corruption | Medium | SQLite WAL mode; snapshot/rollback on every task; session handoff protocol |
| Deadlock under concurrent load | High | Sorted-order lock acquisition (2.3) prevents by construction |
| Agent feedback loop amplifies errors | Medium | Circuit breaker (4.3) + reconciliation (2.5) catch cascading failures |

---

## 11. Decisions Log (D1–D19)

### Existing (D1–D15) — from [DECISIONS.md](file:///e:/JARVIS-PLAN/files/decisions.md)
Already documented. Key ones: D1 (4-agent v1 scope), D3 (no phrasing overrides permissions), D4 (kill switch is Component #0), D5 (SQLite for v1), D6 (no plaintext secrets), D15 (cloud-API-first).

### New Decisions (to be logged)

| ID | Decision | Reasoning |
|---|---|---|
| D16 | User override of scope discipline — full OpenJarvis merge authorized | User explicitly confirmed merging all OpenJarvis features, overriding D1 and Principle 10. Safety architecture preserved; scope expansion does not weaken safety. |
| D17 | OpenJarvis features adopted at architecture/schema level, not code-import | OpenJarvis is a different codebase (different package structure, Rust extensions, specific OAuth flows). Adopting their *design patterns and feature set* into MAX's architecture is correct; importing their Python packages is not. |
| D18 | Local inference path deferred to Phase 6, respecting D15 | D15 says MAX is cloud-API-first. Phase 6 adds local inference as an *option* via Ollama/LiteLLM, not a replacement. Cloud remains default. |
| D19 | Skills framework designed as schema + interfaces now, populated in Phase 6 | OpenJarvis's 13.7k+ skill marketplace requires their agentskills.io standard. MAX creates its own skills framework compatible in concept, not in implementation dependency. |

---

## 12. Non-Negotiable Principles (from MAX_MASTER_PROMPT.md)

1. **Kill Switch is Component #0** — nothing initializes before it reports armed
2. **Two hard human gates** — Architecture Review (before code) + Production Approval (before deploy), both enforced inside the function itself
3. **Agents ≠ Infrastructure** — agents use LLM judgment; infra is deterministic. Never put an LLM call inside a lock manager/watchdog/circuit breaker
4. **Atomic tasks** — snapshot before RUNNING, full rollback on failure
5. **Idempotent side effects** — UUID-keyed, check before firing
6. **Sorted-order locks** — all-or-nothing, prevents deadlock by construction
7. **Error classification before handling** — transient/validation/permission/destructive_risk/systemic
8. **Nothing fails silently** — retry, ask user, refuse with reason, or rollback + DLQ
9. **No plaintext secrets** — vault interface only, ever
10. **Scope discipline** — ~~4 agents until Phase 4.5~~ *(overridden by D16; full roster now planned but still phased)*

---

## 13. OpenJarvis Feature Mapping

| OpenJarvis Feature | MAX Equivalent | Status | Phase |
|---|---|---|---|
| Local model inference (Ollama) | `core/model_router.py` | Planned | 6 |
| Skills marketplace (OpenClaw, 13.7k+) | `core/skill_loader.py` + `skill_registry` | Planned | 6 |
| 3-mode execution taxonomy | `agent_registry.execution_mode` | Schema ready | 0 |
| One-line installers (5 platforms) | `scripts/install.sh`, `scripts/install.ps1` | Planned | 8 |
| OAuth service integration | Per-channel auth in `channel_registry` | Planned | 7 |
| Benchmarking + leaderboard | `cli/bench.py` + `benchmark_results` | Planned | 7 |
| Energy/FLOPs/cost evals | `benchmark_results` columns | Schema ready | 7 |
| ReAct/CodeAct/Orchestrator reasoning | Reasoning engine variants in planner | Planned | 7 |
| Morning digest agent | `agents/daily_brief.py` | Planned | 7 |
| Deep research agent | `agents/research.py` | Planned | 5 |
| Monitor/scheduled-monitor | `agents/monitor.py` + scheduler | Planned | 7 |
| Code-assistant / OpenHands | `agents/coding.py` (already Tier 1) | Existing | 1 |
| Desktop GUI | `desktop/` (Electron) | Planned | 8 |
| FastAPI server | `server/` | Planned | 6 |
| Telegram/Discord/Slack channels | `channels/` + `channel_registry` | Planned | 7 |
| FAISS/BM25 vector memory | `core/memory/` | Planned | 6 |
| Whisper STT | `core/speech.py` | Planned | 8 |
| Docker/WASM sandbox | `core/sandbox.py` | Planned | 8 |
| MCP server | `server/mcp.py` | Planned | 8 |
| DSPy learning loop | `core/learning.py` | Planned | 8 |
| Telemetry/analytics | Part of benchmark framework | Planned | 7 |
| A2A protocol | Extended planner | Planned | 7 |
| `jarvis doctor` CLI | `max doctor` CLI | Planned | 8 |
| Session management | Already built into MAX's build protocol | Existing | 0 |
| Rust extensions | Not adopted — MAX is Python-only in current arch | Excluded | — |

---

## 14. What to Build First

**Start with Phase 0.** The protocol is clear: nothing builds until the foundation is done. The next session should execute steps 0.1–0.4 in order, following the MAX_MASTER_PROMPT.md protocol for each step (mark in_progress → implement → verify acceptance criteria → mark done → log decisions).

After Phase 0, follow the phase order strictly. The dependency graph in §8 shows what can be parallelized within each phase. The scope checkpoint at 4.5 is now a quality gate rather than a scope gate (per D16), but it still requires human sign-off before expanding beyond the v1 four agents.

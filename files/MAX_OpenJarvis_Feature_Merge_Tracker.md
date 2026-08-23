# MAX ∪ OpenJarvis — Feature Merge Tracking Matrix

### Single Source of Truth for Feature Equivalence & Implementation Status

---

## Feature Matrix

| OpenJarvis Feature | MAX Equivalent / Mapping | Target Phase | Status in MAX | Notes / Architecture Design |
|---|---|---|---|---|
| **Local Model Inference (Ollama/vLLM/MLX)** | `core/model_router.py` + `model_registry` | Phase 6 (Step 6.1) | Schema Ready | LiteLLM abstraction router; Cloud-API default (D15), local fallback (D18). |
| **Skills Marketplace (13.7k+ skills via OpenClaw)** | `core/skill_loader.py` + `skill_registry` | Phase 6 (Step 6.2) | Schema Ready | Open Standard (agentskills.io) compatible loader with Docker/WASM sandboxing. |
| **3-Mode Execution Taxonomy (on_demand/scheduled/continuous)** | `agent_registry.execution_mode` | Phase 0 (Step 0.1) | **BUILT** | SQL table column added & seeded across all 28 agents. |
| **Scheduler Service (cron-based scheduling)** | `core/scheduler.py` + `scheduled_tasks` | Phase 6 (Step 6.3) | Schema Ready | Handles scheduled morning digests, scans, and continuous background operatives. |
| **5-Layer Memory System (Identity/Pref/Behavior/Proj/Conv)** | `core/memory/` + `memory_schema.sql` | Phase 6 (Step 6.4) | Schema Ready | 5-layer SQL memory; FAISS vector search for Notes retrieval. |
| **FastAPI REST API & WebSocket Server** | `server/app.py` | Phase 6 (Step 6.5) | Planned | Serves desktop GUI and external channel integrations. |
| **Daily Briefing / Morning Digest Agent (`morning_digest`)** | `agents/daily_brief.py` | Phase 7 (Step 7.1) | Planned | Scheduled execution; morning summary + TTS voice synthesis. |
| **Deep Research Agent (`deep_research`)** | `agents/research.py` | Phase 5 (Step 5.3) | Planned | Multi-query deep research with web search + Wikipedia + citations. |
| **Monitoring Agent (`monitor_operative`)** | `agents/monitor.py` | Phase 7 (Step 7.1) | Planned | Continuous background monitoring agent with memory state. |
| **Monitoring Agent (`monitor_operative`)** | `agents/monitor.py` | Phase 7 (Step 7.1) | Planned | Continuous background monitoring agent with memory state. |
| **Code Assistant (`native_openhands` / CodeAct)** | `agents/coding.py` | Phase 1 (Step 1.4) | **BUILT (Step 1.4)** | Coding Agent with self-testing execution & snapshot rollback. |
| **Multi-Channel Integrations (15+ platforms)** | `channels/` + `channel_registry` | Phase 7 (Step 7.3) | Schema Ready | Abstract channel adapter pattern (Telegram, Discord, Slack, etc.). |
| **Benchmarking & Evaluation Framework** | `cli/bench.py` + `benchmark_results` | Phase 7 (Step 7.4) | Schema Ready | Tracks Energy (Joules), FLOPs, Latency (ms), and Cost ($) per task. |
| **Agent-to-Agent (A2A) Interop Protocol** | Planner DAG decomposition | Phase 7 (Step 7.5) | **Phase 2 Baseline (Step 2.6)** | Subtask delegation between agents via Planner dependency graph. |
| **MCP (Model Context Protocol) Server** | `server/mcp.py` | Phase 8 (Step 8.2) | Planned | MAX acts as an MCP server for external client integrations. |
| **Desktop GUI App (Electron)** | `desktop/` | Phase 8 (Step 8.3) | Planned | Cross-platform desktop interface communicating with max-core daemon. |
| **Speech I/O (Whisper STT + TTS)** | `core/speech.py` + `core/voice_output.py` | Phase 8 (Step 8.4) | Planned | Faster-Whisper local STT + TTS voice output pipeline. |
| **Sandboxed Execution (Docker / WASM)** | `core/sandbox.py` | Phase 8 (Step 8.5) | Planned | Process/Docker/WASM isolation for skill execution. |
| **Multi-Platform One-Line Installers** | `scripts/install.sh` / `install.ps1` | Phase 8 (Step 8.6) | Planned | Automated setup scripts for macOS, Linux, WSL2, Windows. |
| **System Diagnostics (`jarvis doctor`)** | `cli/doctor.py` (`max doctor`) | Phase 8 (Step 8.6) | Planned | Environment & daemon status checker CLI command. |
| **Learning & Optimization Loop (DSPy)** | `core/learning.py` | Phase 8 (Step 8.8) | Planned | Trace data mining → model prompt / skill optimization loop. |

---

## MAX Core Reliability Features (OpenJarvis Doesn't Have)

| Feature | Description | Status in MAX |
|---|---|---|
| **Component #0 Kill Switch** | Hard boot dependency; halts execution within 1s | **BUILT (Step 0.2)** |
| **Local Encrypted Vault** | Credential interface backed by OS keychain (`keyring`) | **BUILT (Step 0.3)** |
| **Data Boundary Policy** | Payload sanitization stripping out-of-scope files & keys | **BUILT (Step 0.4)** |
| **Task State Machine & Idempotency** | Atomic `CREATED→QUEUED→RUNNING→RECONCILING→DONE` + UUID keys | **BUILT (Step 1.1, 1.2)** |
| **Atomic Snapshot & Rollback** | Pre-RUNNING snapshot; zero-residual rollback on failure | **BUILT (Step 1.3)** |
| **Trace Log Viewer CLI** | Direct DB-less CLI trace inspection (`max trace`) | **BUILT (Step 1.6)** |
| **Calendar & Notes Agents** | Auto-tier scheduling & notes store with SQLite backend | **BUILT (Step 2.1)** |
| **Deploy Agent (Repo-Push)** | Confirm-tier Git CLI operations & approval tokens | **BUILT (Step 2.2)** |
| **Sorted-Order Deadlock Prevention** | Resource Lock Manager acquiring locks in sorted order | **BUILT (Step 2.3)** |
| **Heartbeat Watchdog** | Background liveness monitor with snapshot rollback on timeout | **BUILT (Step 2.4)** |
| **Reconciliation Engine** | Independent verification of claimed outcomes vs real state | **BUILT (Step 2.5)** |
| **Dependency Graph Planner** | Multi-agent DAG topological decomposition | **BUILT (Step 2.6)** |
| **Code-Enforced Human Gates** | DA-7 Production gate inside `deploy_prod()` + Permission Manager | **BUILT (Step 2.7, 3.2)** |
| **9-Stage Deploy Pipeline** | DA-1 to DA-6 autonomous staging, DA-8/9 rollout + auto-rollback | **BUILT (Step 3.1, 3.3)** |
| **Per-Agent Circuit Breakers** | Prevents cascading failures on repeating agent errors | **BUILT (Step 4.3)** |
| **Dead Letter Queue (DLQ)** | Requeueable task DLQ for exhausted-retry tasks | **BUILT (Step 4.4)** |
| **Full Error Taxonomy** | Transient / Validation / Permission / Risk / Systemic | **BUILT (Step 4.1, 4.2)** |
| **Session-Resumable Build Protocol** | Database-backed project progress (`max_state.db`) | **BUILT (Step 0.1)** |
| **Web Search & Deep Research** | Explicit triggers, quota tracking & citation synthesis | **BUILT (Step 5.1, 5.3)** |
| **Multi-Model Backend Router** | Ollama local inference + Cloud fallback with quota tracking | **BUILT (Step 6.1)** |
| **Modular Skills Framework** | Registry, permission declarations, sandboxed runner | **BUILT (Step 6.2)** |
| **Cron Scheduler Service** | Scheduled and continuous agent automation | **BUILT (Step 6.3)** |
| **5-Layer Memory Context Heap** | Identity, Preferences, Bayesian Patterns, Project, Conv | **BUILT (Step 6.4)** |
| **FastAPI REST & WebSocket Gateway** | Server, live streams, GUI backend | **BUILT (Step 6.5)** |
| **Daily-Life & Engineering Suites** | 12 specialized agents (Inbox, CRM, Security, Review, etc.) | **BUILT (Step 7.1, 7.2)** |
| **Multi-Channel Adapters** | Telegram, Discord, Slack with confirmation tokens | **BUILT (Step 7.3)** |
| **Multi-Dimensional Benchmarks** | Joules, FLOPs, Accuracy, Latency, Cost USD | **BUILT (Step 7.4)** |
| **Agent-to-Agent (A2A) Protocol** | Typed inter-agent messaging with DAG cycle prevention | **BUILT (Step 7.5)** |
| **Big Infrastructure Suite** | Database, CloudInfra, DataPipeline, Backup/DR, Analytics | **BUILT (Step 8.1)** |
| **MCP Server** | Model Context Protocol standard tools & resources | **BUILT (Step 8.2)** |
| **Speech I/O & Voice Loop** | STT, Wake-Word, and TTS text fallback | **BUILT (Step 8.4)** |
| **Input Control Agents** | Screen OCR, Blocked credentials, Confirm-gated clicks | **BUILT (Step 8.7)** |
| **Self-Improving Learning Loop** | DSPy prompt optimizer with few-shot exemplars | **BUILT (Step 8.8)** |
| **WhatsApp Channel Bridge** | Hybrid desktop URL launcher + Vault Cloud API dispatch | **BUILT (`channels/whatsapp.py`)** |
| **CYBERBLACK-OPS Defensive Security** | OSINT recon, SAST security scan & curriculum compiler | **BUILT (`agents/cyberblack.py`)** |
| **Parallel Keyboard & Mouse Streams** | Async non-blocking desktop automation workers | **BUILT (`agents/input_control.py`)** |
| **10 Real-World Command Flow Runner** | `max run-flow --example <1-10>` with live execution traces | **BUILT (`cli/run_command_flow.py`)** |


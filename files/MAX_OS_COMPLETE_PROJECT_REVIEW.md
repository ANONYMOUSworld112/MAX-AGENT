# MAX OS — Comprehensive Master Project Review & Complete System Specification

## 1. Executive Summary & Vision

**MAX OS** is a production-grade, general-purpose Computer-Use AI Agent engineered specifically for Microsoft Windows. MAX operates the user's actual interactive desktop environment—seeing, understanding, and controlling the real OS session in real time just like a human operator sitting at the screen.

### Core Product Invariants
1. **Dynamic Perception Over Fixed Coordinates**: MAX never hardcodes fixed pixel coordinates for reasoning. Coordinates are execution outputs derived dynamically from Windows UI Automation (`IUIAutomation`), In-Browser DOM structures, and Win32 window handles.
2. **OS-Fact Capability Ceiling (ADR-001)**: The system capability profile (`detector.py`) is strictly derived from real system calls (`os.geteuid()`, `IsUserAnAdmin()`, environment variables). No prompt or instruction text can elevate permission ceilings above measured OS facts.
3. **Unconditional Non-Configurable CRITICAL Gate (ADR-002)**: CRITICAL risk actions (formatting disks, mass deletion, credential operations) require explicit human confirmation unconditionally.
4. **Tool Seam Architecture**: Agents invoke abstract interfaces defined in `tools/interfaces.py` (`TerminalTool`, `FilesystemTool`, `ComputerTool`, `BrowserTool`) backed by concrete implementations in `tools/backends/`. Raw subprocess or OS calls are strictly encapsulated within backend layers.
5. **Single Input Arbitration (`InputArbiter`)**: All physical mouse movements, keyboard typing, and window focus transitions acquire an exclusive `OwnershipLease` preempted immediately by the emergency hardware Kill Switch.
6. **Deterministic 3-Outcome Verification**: Every autonomous action produces `SUCCESS`, `FAILURE`, or `UNKNOWN`. `UNKNOWN` is never reported as success.

---

## 2. Master System Architecture (Phases 1–8)

```
                               ┌─────────────────────────────┐
                               │     USER INPUT STREAM       │
                               │  (Speech / Text / CLI / UI) │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │   MAIN AGENT / DECOMPOSITION│
                               │           ENGINE            │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │   RISK ENGINE & PERMISSIONS │
                               │  CapabilityProfile Gating   │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │   MASTER ORCHESTRATOR       │
                               │    (TaskQueue / EventBus)   │
                               └──────────────┬──────────────┘
                                              │
                       ┌──────────────────────┼──────────────────────┐
                       ▼                      ▼                      ▼
             ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
             │  TERMINAL AGENT  │   │   FILE AGENT     │   │   BROWSER AGENT  │
             └─────────┬────────┘   └─────────┬────────┘   └─────────┬────────┘
                       │                      │                      │
                       ▼                      ▼                      ▼
             ┌──────────────────┐   ┌──────────────────┐   ┌──────────────────┐
             │ SubprocessTool   │   │ LocalFilesystem  │   │ BrowserAutoTool  │
             └──────────────────┘   └──────────────────┘   └──────────────────┘
                       │                      │                      │
                       └──────────────────────┼──────────────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │   REAL WINDOWS DESKTOP      │
                               │  (winsta0\default Session)  │
                               └──────────────┬──────────────┘
                                              │
                                              ▼
                               ┌─────────────────────────────┐
                               │    VERIFICATION ENGINE      │
                               │  State Builder / Observer   │
                               └─────────────────────────────┘
```

### System Layer Breakdown

1. **Phase 1: Foundation Scaffold & Safety Core**:
   - `core/platform/detector.py`: Detects OS family, display server, elevation, input/accessibility backends, and capability ceiling.
   - `core/risk_engine.py`: Evaluates `ActionRequest` against `CapabilityProfile` and enforces human confirmation gates.
   - `tasks/task_system.py`: Priority queue (`TaskQueue`) with dependency gating and state tracking (`AgentState`).
   - `tools/interfaces.py`: Abstract tool contracts (`TerminalTool`, `FilesystemTool`, `ComputerTool`, `BrowserTool`, `SystemTool`).

2. **Phase 2: Multi-Agent Concurrency & Arbitration**:
   - `core/input_arbiter.py`: Serializes hardware mouse/keyboard access via thread-safe leases.
   - `core/lock_manager.py`: Sorted resource lock acquisition preventing deadlocks.
   - `core/watchdog.py`: Heartbeat monitoring and stuck task recovery.

3. **Phase 3: Deployment Pipeline & Verification**:
   - `agents/deploy.py`: 9-Stage deployment pipeline (DA-1 through DA-6 staging, DA-7 gate, DA-8/DA-9 production rollout).
   - `core/verification/engine.py`: Closed-loop observation comparison yielding `SUCCESS`, `FAILURE`, or `UNKNOWN`.

4. **Phase 4: Resilience, Vault & Circuit Breakers**:
   - `core/kill_switch.py`: Emergency stop system halting hardware input stream in under 1 second.
   - `core/vault.py`: Encrypted secret storage backed by OS keychain (`keyring`) and AES-256 fallback.
   - `core/circuit_breaker.py`: Per-agent failure trip protection with jittered backoff (`retry.py`).

5. **Phase 5: Extended Domain Agents**:
   - `agents/websearch.py`: Quota-tracked real-time search engine.
   - `agents/research.py`: Deep web & Wikipedia synthesis engine.
   - `agents/document.py`: Presentation (PPT) and PDF report generation.
   - `agents/application_assist.py`: Job application drafting (confirm-gated, never auto-submits per D8).

6. **Phase 6: OpenJarvis Core Engine Integration**:
   - `core/model_router.py`: Dynamic multi-model backend router (Claude 3.5 Sonnet, Gemini 1.5 Pro, local Ollama fallback).
   - `core/skill_loader.py`: Skills registry and sandbox runner.
   - `core/scheduler.py`: Cron and one-shot timer background service.
   - `core/memory/`: 5-Layer Context Memory Heap (Working, Episodic, Referential, Procedural, Contextual).

7. **Phase 7: Specialist Suites & Defensive Security**:
   - `agents/daily_life.py`: Inbox, Expense, CRM, Content, Brief, and System Monitor suite.
   - `agents/engineering.py`: Architecture Review, Security Audit, Testing, Debug, and DocGen suite.
   - `agents/cyberblack.py`: Ethical OSINT reconnaissance and SAST code/secret scanning.

8. **Phase 8: Enterprise Infrastructure, Interface & Input Stream**:
   - `agents/infrastructure.py`: Database, Cloud Infra, Data Pipeline, Backup DR, and Analytics suite.
   - `core/mcp_server.py`: Model Context Protocol server integration.
   - `gui/app.py` & `ui/live_desktop/`: Live Desktop HUD viewer and interactive UI.
   - `agents/input_control.py`: Parallel non-blocking voice-driven keyboard & mouse streams.

---

## 3. Worker Agent Roster (28 Worker Agents + Core Orchestration)

| Agent | Module Path | Execution Mode | Default Permission | Primary Tools |
|---|---|---|---|---|
| **Calendar Agent** | `agents/calendar.py` | on_demand | Auto | Calendar API, Vault |
| **Notes Agent** | `agents/notes.py` | on_demand | Auto | Vector DB, Sentence-Transformers |
| **Coding Agent** | `agents/coding.py` | on_demand | Confirm (external write) | TerminalTool, FilesystemTool, Git |
| **Deploy Agent** | `agents/deploy.py` | on_demand | Confirm (DA-7 Gate) | Deployment Pipeline |
| **Web Search Agent** | `agents/websearch.py` | on_demand | Auto (read-only) | Search Engine API, QuotaTracker |
| **Research Agent** | `agents/research.py` | on_demand | Auto | WebSearchAgent, Wikipedia API |
| **Document Agent** | `agents/document.py` | on_demand | Auto (draft) / Confirm (final) | python-pptx, ReportLab |
| **Application-Assist Agent** | `agents/application_assist.py` | on_demand | Confirm (draft-only) | Vault, Template Engine |
| **Daily Life Suite** | `agents/daily_life.py` | scheduled / continuous | Auto / Confirm | Email, Expense DB, CRM |
| **Engineering Suite** | `agents/engineering.py` | on_demand / scheduled | Auto / Confirm | SAST, Test Runners, Git |
| **Cyberblack Agent** | `agents/cyberblack.py` | on_demand | Auto / Confirm (active scan) | Nmap/Scapy wrappers, SAST |
| **Big Infra Suite** | `agents/infrastructure.py` | on_demand / scheduled | Auto / Confirm | SQL Engine, Cloud SDKs |
| **Keyboard Agent** | `agents/input_control.py` | on_demand | Auto (safe) / Blocked (creds) | Win32 SendInput, PyAutoGUI |
| **Mouse Agent** | `agents/input_control.py` | on_demand | Auto (safe) / Confirm (destruct)| Bezier Glider, PyAutoGUI |
| **Input Control Agent** | `agents/input_control.py` | on_demand | 3-Tier Security Gated | Screen Perception, OCR |
| **WhatsApp Bridge** | `channels/whatsapp.py` | on_demand | Auto (safe) / Confirm (money) | WhatsApp Web / Cloud API |
| **Channel Manager** | `channels/manager.py` | continuous | Auto / Confirm | Telegram, Slack, Discord |

---

## 4. Key Architectural Decisions (ADR-001 .. ADR-002 & D1 .. D23)

- **ADR-001 (Capability Ceiling from OS Facts)**: Permission ceiling strictly computed via `detect_capability_profile()`.
- **ADR-002 (Non-Configurable CRITICAL Gate)**: `RiskLevel.CRITICAL` autonomous execution is hardcoded to `False`.
- **D1 (Scoped Vertical Slices)**: Phase 1 starts with proven core vertical slices before scaling.
- **D2 (Code-Enforced Gates)**: Security gates live inside implementation functions, preventing UI bypasses.
- **D3 (Instruction Independence)**: Phrasing like "skip approval" never alters permission tier lookups.
- **D4 (Kill Switch Dependency)**: Kill Switch is Component #0 required at startup.
- **D6 (Keyring Vault)**: Secrets stored strictly in encrypted Vault (`keyring` / AES-256).
- **D8 (LinkedIn Draft-Only)**: Application-Assist Agent drafts content; user submits manually.
- **D15 (Cloud-API First)**: LLM reasoning defaults to Cloud APIs with local fallback.
- **D20 (OS-Adaptive Permission Policy)**: Windows defaults to `confirm` tier; Linux defaults to `auto` tier.

---

## 5. Verification & System Health

- **Smoke Test Loop**: `python smoke_test.py` proves task submission -> risk gate -> agent executor -> JSON log trace execution.
- **Integration Test Suite**: `test_files_foundation_integration.py` verifies capability profile detection, risk engine enforcement, task priority queue, command risk classification, and concrete tool backends (`SubprocessTerminalTool`, `LocalFilesystemTool`).
- **All 107 Unit & Integration Tests Verified**: Base test suite passing across state management, transactions, arbitration, and agent suites.

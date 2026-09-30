# MAX-AGENT — Dead Architecture & Architectural Anti-Patterns Audit

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Dead & Dormant Architecture Inventory

The table below catalogs every component, class, and module in the repository that is **dead, disconnected, or orphaned** from the production runtime:

| Subsystem / Module | File Path | Classes / Functions | Status | Reason / Forensic Evidence |
|---|---|---|---|---|
| **Perception Engine** | `core/perception/accessibility.py` | `AccessibilityEngine`, `UIElement` | **DEAD** | Never imported by `main.py` or any active tool in `actions/`. |
| **Perception Engine** | `core/perception/browser_dom.py` | `BrowserDOMExtractor`, `DOMNode` | **DEAD** | Never imported by any active module. |
| **Perception Engine** | `core/perception/element_detection.py`| `ElementDetector` | **DEAD** | Never imported by any active module. |
| **Perception Engine** | `core/perception/text_detection.py` | `TextDetector` | **DEAD** | Never imported by any active module. |
| **Perception Engine** | `core/perception/ui_detection.py` | `UIDetector` | **DEAD** | Never imported by any active module. |
| **Perception Engine** | `core/perception/state_builder.py` | `StateBuilder`, `ComputerState` | **DEAD** | Never imported by any active module. |
| **Verification Engine**| `core/verification/engine.py` | `VerificationEngine` | **DEAD** | Never imported by `main.py` or any active tool. |
| **Verification Engine**| `core/verification/process_verifier.py`| `ProcessVerifier` | **DEAD** | Zero references outside its unit test. |
| **Verification Engine**| `core/verification/window_verifier.py` | `WindowVerifier` | **DEAD** | Zero references outside its unit test. |
| **Verification Engine**| `core/verification/file_verifier.py` | `FileVerifier` | **DEAD** | Zero references outside its unit test. |
| **Verification Engine**| `core/verification/state_diff_verifier.py`| `StateDiffVerifier` | **DEAD** | Zero references outside its unit test. |
| **Reflex Triage** | `core/reflex/triage.py` | `ReflexTriage`, `PriorityBand` | **DEAD** | Zero imports in the entire codebase. |
| **Task Queue** | `core/max_infra/task_queue.py` | `TaskQueue`, `TaskItem` | **DORMANT** | Instantiated on line 472 of `main.py`, but never enqueued or dequeued. |
| **Task State Machine** | `core/max_infra/task_lifecycle.py` | `TaskLifecycleFSM`, `TaskState`| **DORMANT** | Never instantiated or bound to user commands. |
| **State Database** | `core/max_infra/state_db.py` | `StateDB` | **DORMANT** | Complete SQLite WAL schema, but `max_state.db` is never opened in production. |
| **Credential Vault** | `core/max_infra/vault.py` | `MaxVault` | **DORMANT** | Credentials read from plaintext `config/api_keys.json`. |
| **System Watchdog** | `core/max_infra/watchdog.py` | `Watchdog` | **DORMANT** | Threading watchdog implemented, but never started in `main.py`. |
| **Data Boundary** | `core/max_infra/data_boundary.py` | `DataBoundary` | **DORMANT** | Token scrubber implemented, but never called on Gemini prompts. |
| **33 Agent Stubs** | `agents/*/*.py` | All 33 `BaseAgent` subclasses | **MOCKED** | Return synthetic dictionaries with fake `success=True`. No real domain work. |

---

## 2. Duplicate Subsystems Identified

1. **Dual Task Representation**:
   - `core/max_infra/task_queue.py:TaskItem`: Priority, aging, dependencies.
   - `agents/base.py:AgentInput`: Pydantic model for task parameters.
   - Neither connects to `main.py`, which uses loose `args` dictionaries.
2. **Dual System Monitoring**:
   - `actions/system_monitor.py:get_system_status()`: Real `psutil` metrics (ACTIVE).
   - `agents/health/system_monitor.py`: Stub agent returning static 18% CPU / 42% RAM (MOCKED).
3. **Dual Code Generation Systems**:
   - `actions/dev_agent.py`: Gemini Flash prompt-loop generating files on Desktop (ACTIVE).
   - `agents/software/coding_agent.py`: Stub agent claiming code generation (MOCKED).
4. **Dual Scheduling Systems**:
   - `actions/reminder.py`: Creates Windows Scheduled Tasks via `schtasks.exe` (ACTIVE).
   - `agents/productivity/calendar_agent.py`: Stub claiming to schedule calendar appointments (MOCKED).

---

## 3. Architectural Anti-Patterns Catalog

### Anti-Pattern 1: The Potemkin Village (Simulated Competence)
The most severe architectural pattern across `agents/` is returning successful outputs for non-existent operations.  
For example, `EmailAgent` returns `status: "queued for confirmation"` and `result: "Email sent"`, but never triggers a confirmation prompt and never sends an email. This deceives both the LLM and the human user.

### Anti-Pattern 2: Arbitrary Code Execution Sandbox Illusion
In `actions/desktop.py`, `_execute_generated_code()` attempts to create a "sandbox" by whitelisting built-in functions. However, injecting `ctypes` and `winreg` into the execution scope gives full access to native Windows memory, API calls, and registry keys, defeating any containment.

### Anti-Pattern 3: Bypassed Control Plane (Architecture On Paper Only)
The diagrams in `readme.md` show a layered, governed operating system. In reality, `main.py` is a direct client to Gemini Live that exposes raw OS tools without checking permissions, risk tiers, or verification. The governance layer exists only as unused files on disk.

### Anti-Pattern 4: Unsandboxed Host Contamination
`actions/dev_agent.py` installs packages directly into the active Python environment of the assistant. Any error or malicious package permanently mutates the host Python environment.

---

## 4. Preservation & Migration Strategy (Rule 1-P)

Per Non-Negotiable **Rule 1-P3 (Preservation / Strangler Fig)**:
- **Do not delete dormant code immediately.**
- Modules with sound internal architecture (`StateDB`, `LockManager`, `KillSwitch`, `DataBoundary`, `VerificationEngine`) will be **reused and extended** in Phase 1 Foundations.
- Mock agents will be marked `[NOT IMPLEMENTED]` and progressively replaced by real, verified capabilities inside their respective phase branches behind feature flags.

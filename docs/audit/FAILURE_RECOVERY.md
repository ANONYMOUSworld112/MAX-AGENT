# MAX-AGENT — Failure Classification & Recovery Forensics

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Active Failure Handling in Production (`main.py`)

In the active runtime, error handling across all tool invocations is concentrated in a single generic `try/except` block inside `main.py:_execute_tool()` (lines 966-970):

```python
except Exception as e:
    result = f"Tool '{name}' failed: {e}"
    traceback.print_exc()
    self.speak_error(name, e)
```

Where `self.speak_error(name, e)`:
```python
def speak_error(self, tool_name: str, error: str):
    short = str(error)[:120]
    self.ui.write_log(f"ERR: {tool_name} — {short}")
    self.speak(f"Sir, {tool_name} encountered an error. {short}")
```

### Forensic Deficiencies in Active Recovery
1. **Zero Error Classification**: All exceptions (network timeouts, permission errors, syntax errors, missing files, user interruptions) are caught by the same generic `except Exception` and collapsed into a raw string `f"Tool '{name}' failed: {e}"`.
2. **Zero Automatic Retries**: If a transient network glitch causes DuckDuckGo or wttr.in to fail, the action fails immediately. There is no retry with backoff and jitter.
3. **No Replanning**: There is no task graph or plan validator to catch failures, isolate the failed subtask, and replan.
4. **No Idempotency Protection**: If an action fails partially (e.g. creating 3 out of 5 files), re-running the command may cause duplicate side effects or corrupted state.

---

## 2. Inactive Recovery Infrastructure

The repository contains isolated recovery modules that were built for the MAX OS kernel but never connected to `main.py`:

| Module | Location | Documented Capability | Actual Production Status |
|---|---|---|---|
| **CircuitBreaker** | `core/max_infra/circuit_breaker.py` | Opens after 3 consecutive failures; 60s cooldown | [EXISTS] [ISOLATED] Called inside `BaseAgent.run()`, but never used by action tools in `actions/`. |
| **SnapshotEngine** | `core/max_infra/snapshot.py` | File copy-on-write before write; automatic rollback on failure | [EXISTS] [ISOLATED] `BaseAgent.run()` captures snapshot only if `input_data.target_files` is set. Because `main.py` passes `target_files=[]`, snapshots are **never captured**. |
| **Undo Stack** | `core/undo.py` | In-memory stack of reversible operations (files moved, volume changed) | [EXISTS] [ACTIVE] Populated by `file_controller` and `computer_settings`. Called when user explicitly says "undo". |
| **RecoveryEngine**| `agents/safety/recovery_engine.py` | Agent that plans rollback and state restoration | [EXISTS] [MOCKED STUB] Returns static dictionary. |

---

## 3. Required Evolution (Master Spec Section 15)

1. **Structured Error Classification**:
   - `TRANSIENT`: Network timeouts, rate limits ──► Retry with exponential backoff and jitter.
   - `ENVIRONMENT`: Window locked, session elevated, missing dependencies ──► Pause and alert user.
   - `PERMISSION`: Admin elevation required ──► Escalate to owner.
   - `USER_INPUT_NEEDED`: Ambiguous parameter ──► Ask clarifying question.
   - `VERIFICATION_FAILED`: Expected state not achieved ──► Alternate strategy through gateway.
   - `BUDGET`: Loop or step limit exceeded ──► Abort task cleanly (`budget_exceeded`).
   - `SAFETY_DENIED`: Policy gate rejection ──► **Never retried, never routed around.**
2. **Idempotency Class Enforcement**:
   - `IDEMPOTENT`: Safe to retry immediately (reads, telemetry).
   - `RETRY_SAFE_AFTER_OBSERVE`: Launching applications (observe window state first; retry only if app is not running).
   - `NON_IDEMPOTENT`: Sending emails, deleting files, committing git changes (never auto-retry; report known state and ask owner).
3. **Crash Recovery Procedure**:
   - Replay pending tasks from `StateDB` on startup.
   - Move unverified in-flight tasks to `INTERRUPTED` state.

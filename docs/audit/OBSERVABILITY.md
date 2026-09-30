# MAX-AGENT — Observability, Telemetry & Audit Trail Forensics

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Current Telemetry Architecture

MAX currently relies on **unstructured console prints** and **basic UI log lines**:

```
[ Console Prints: stdout / stderr ]
print(f"[MAX] 🔧 {name} {args}")           (main.py:809)
print(f"[MAX] 📤 {name} → {str(result)}")  (main.py:974)
print(f"[MAX] 📞 {fc.name}")                (main.py:1188)

[ UI Log Widget: ui.write_log ]
self.ui.write_log(f"You: {full_in}")        (main.py:1132)
self.ui.write_log(f"MAX: {full_out}")       (main.py:1144)
self.ui.write_log(f"ERR: {tool_name}...")   (main.py:717)

[ Web Dashboard Broadcast ]
self._dashboard.broadcast({"type": "log", "speaker": "user", "text": full_in})
```

---

## 2. Forensic Evaluation: The Critical Observability Questions

Can the current system answer the core questions required by Master Specification Phase 21?

| Forensic Question | Current System Ability | Source Evidence |
|---|---|---|
| *"What was MAX doing at 14:32:09?"* | **NO.** | Timestamps are only printed in UI log lines; there is no persistent time-series event log. |
| *"Why did it select this agent?"* | **NO.** | Gemini selects the tool call opaque cloud-side. No candidate evaluation, ranking, or selection rationale is recorded. |
| *"Which tool failed?"* | **PARTIAL.** | Printed to console as `f"Tool '{name}' failed: {e}"` and UI log as `ERR: {tool_name}`. Not stored structured. |
| *"How many times did it retry?"* | **NO.** | No retries occur; retry count is not tracked anywhere. |
| *"Which agent was responsible?"* | **NO.** | When actions in `actions/*.py` run, they are not attributed to any specific agent entity. |
| *"What state changed?"* | **NO.** | No before/after state snapshots are captured or diffed. |
| *"Why did MAX say the task succeeded?"* | **NO.** | Because no verification evidence is attached to the completion claim. |

---

## 3. Inactive Telemetry & Audit Infrastructure

The repository contains an append-only, cryptographic audit log schema in `core/max_infra/schema.sql`:

```sql
CREATE TABLE audit_log (
    log_id TEXT PRIMARY KEY,
    timestamp REAL NOT NULL,
    actor TEXT NOT NULL,
    action TEXT NOT NULL,
    resource TEXT,
    payload_hash TEXT,
    prev_hash TEXT,
    hash TEXT NOT NULL
);
```

### Why is it Inactive?
`main.py` never instantiates `StateDB` or writes to `audit_log`.  
The database file `max_state.db` is never created during ordinary execution.  
All audit logging occurs purely via ephemeral `print()` statements lost when the process terminates.

---

## 4. Required Evolution (Master Spec Section 25)

1. **Standardized Event Envelope**:
   ```yaml
   EventEnvelope:
     event_id: UUID
     schema_version: 1.0.0
     timestamp: {wall_utc, monotonic_ns}
     correlation_id: UUID (persists across user utterance turn)
     task_id: UUID
     parent_task_id: Optional[UUID]
     type: String (TaskCreated, TaskStarted, TaskVerified, etc.)
     origin: String (user_direct, voice, api, schedule)
     payload: Dict (redacted of secrets)
   ```
2. **Cryptographic Append-Only Audit Trail**:
   - Each event record includes `prev_hash` and SHA-256 `hash = sha256(prev_hash + serialized_event)`.
   - Tamper-evident: any modification to past records invalidates the chain.
3. **Structured Correlation Tracing**:
   - Connect user speech → intent detection → routing decision → policy check → tool execution → verification evidence → response phrasing under one unified `correlation_id`.
4. **Live HUD Observability**:
   - Expose the live TaskGraph state and execution timeline to the UI and remote dashboard.

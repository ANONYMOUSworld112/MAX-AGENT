# MAX OS v1 — Data Flow Mapping

### Every request's complete path through the system, from user keystroke
### to final response, with every decision point and data transformation
### explicitly mapped.

---

## 1. Master Data Flow (Happy Path)

```
USER types: "remind me to review the PR at 3pm tomorrow"
     │
     │  ┌──────────────────────────────────────────────────────────┐
     │  │  CLI CLIENT (thin — no logic)                            │
     │  │                                                           │
     ▼  │  1. Capture raw text                                      │
     ●──│  2. Attach local auth token (from ~/.config/max-os/token) │
        │  3. POST /v1/tasks { "text": "...", "token": "..." }     │
        │  4. Send over Unix domain socket / named pipe             │
        └────────────────────┬─────────────────────────────────────┘
                             │
                             ▼
     ┌───────────────────────────────────────────────────────────────┐
     │  DAEMON: INTAKE / NORMALIZE                                    │
     │                                                                │
     │  ▸ Validate auth token (file-permission check + token match)  │
     │  ▸ Sanitize input (strip control chars, enforce max length)   │
     │  ▸ Generate task_id (UUID4)                                    │
     │  ▸ Generate idempotency_key (UUID4)                            │
     │  ▸ INSERT into tasks: status=CREATED                           │
     │  ▸ INSERT into task_events: "task_created"                     │
     │                                                                │
     │  DATA OUT: { task_id, idempotency_key, raw_text, created_at } │
     └────────────────────┬──────────────────────────────────────────┘
                          │
                          ▼
     ┌───────────────────────────────────────────────────────────────┐
     │  INTENT CLASSIFIER                                             │
     │                                                                │
     │  ▸ Step 1: Keyword match (cheap, no API call)                  │
     │    "remind" → Calendar Agent, confidence=95%                   │
     │                                                                │
     │  ▸ Step 2 (if needed): LLM call via data_boundary.py           │
     │    Input: ONLY the user's text (no DB context, no secrets)     │
     │    Output: { agent: "calendar", intent: "schedule_reminder",   │
     │              confidence: 0.95, entities: { time: "3pm tmrw" }} │
     │                                                                │
     │  ▸ Confidence < 70%? → return { action: "clarify", question }  │
     │  ▸ INSERT into task_events: "classified"                       │
     │                                                                │
     │  DATA OUT: { agent, intent, confidence, extracted_entities }   │
     └────────────────────┬──────────────────────────────────────────┘
                          │
                          ▼
     ┌───────────────────────────────────────────────────────────────┐
     │  CONFIRMATION & GATE ENFORCEMENT LAYER                         │
     │                                                                │
     │  ▸ Determine tier from TASK METADATA (not phrasing):           │
     │    - Calendar/Notes → auto (no confirmation needed)            │
     │    - Coding (file write) → confirm (per-task)                  │
     │    - Deploy (to production_targets.yaml match) → production_gate│
     │                                                                │
     │  ▸ This example: Calendar → auto → proceed immediately         │
     │                                                                │
     │  DATA OUT: { tier: "auto", gate_required: false }             │
     └────────────────────┬──────────────────────────────────────────┘
                          │
                          ▼
     ┌───────────────────────────────────────────────────────────────┐
     │  PLANNER                                                       │
     │                                                                │
     │  ▸ Single intent → single task (no decomposition needed)       │
     │  ▸ Assign priority band: 1 (user-initiated, interactive)      │
     │  ▸ Assign resources: ["calendar"] (shared-write lock)         │
     │  ▸ No dependencies for a single task                           │
     │                                                                │
     │  DATA OUT: [ { task_id, agent, priority: 1,                   │
     │               resources: ["calendar"], depends_on: [] } ]      │
     └────────────────────┬──────────────────────────────────────────┘
                          │
                          ▼
     ┌───────────────────────────────────────────────────────────────┐
     │  TASK QUEUE                                                     │
     │                                                                │
     │  ▸ Circuit breaker check: Calendar Agent breaker CLOSED? ✅    │
     │  ▸ Backpressure check: queue depth < 500? ✅                   │
     │  ▸ Push to priority heap (band 1)                              │
     │  ▸ UPDATE tasks: status=QUEUED                                  │
     │  ▸ INSERT into task_events: "queued"                            │
     │                                                                │
     │  ▸ Dequeue (immediate — nothing ahead in band 1)               │
     │  ▸ Dependency check: depends_on = [] → satisfied               │
     │                                                                │
     │  DATA OUT: task ready for lock acquisition                     │
     └────────────────────┬──────────────────────────────────────────┘
                          │
                          ▼
     ┌───────────────────────────────────────────────────────────────┐
     │  RESOURCE LOCK MANAGER                                         │
     │                                                                │
     │  ▸ Resources: ["calendar"] (sorted — trivial for one)          │
     │  ▸ Lock type: exclusive (it's a write)                         │
     │  ▸ Acquire with timeout=10s                                    │
     │  ▸ Success? → UPDATE tasks: status=RUNNING                     │
     │  ▸ Fail?   → UPDATE tasks: status=LOCK_WAIT, re-queue          │
     │                                                                │
     │  DATA OUT: task now owns the calendar lock                     │
     └────────────────────┬──────────────────────────────────────────┘
                          │
                          ▼
     ┌───────────────────────────────────────────────────────────────┐
     │  EXECUTION                                                      │
     │                                                                │
     │  ▸ Snapshot taken (task-scoped)                                 │
     │  ▸ Heartbeat started (15s interval)                             │
     │  ▸ Calendar Agent.execute(task):                                │
     │      1. Parse "3pm tomorrow" → datetime                         │
     │      2. Check calendar_events for conflicts at that time        │
     │      3. No conflict → INSERT calendar_events                    │
     │      4. Return { status: "success", event_id: "..." }          │
     │  ▸ INSERT into task_events: "executed"                          │
     │                                                                │
     │  DATA OUT: { status: "success", event_created: true }          │
     └────────────────────┬──────────────────────────────────────────┘
                          │
                          ▼
     ┌───────────────────────────────────────────────────────────────┐
     │  RECONCILIATION                                                 │
     │                                                                │
     │  ▸ Calendar Agent said "event created"                          │
     │  ▸ Query calendar_events: does the event actually exist?        │
     │  ▸ MATCH → proceed to DONE                                     │
     │  ▸ MISMATCH → classify as SYSTEMIC, rollback                   │
     │                                                                │
     │  DATA OUT: reconciliation_result = MATCH                       │
     └────────────────────┬──────────────────────────────────────────┘
                          │
                          ▼
     ┌───────────────────────────────────────────────────────────────┐
     │  COMPLETION                                                     │
     │                                                                │
     │  ▸ UPDATE tasks: status=DONE, completed_at=now                  │
     │  ▸ Release calendar lock                                        │
     │  ▸ Stop heartbeat                                               │
     │  ▸ UPDATE outcome_tracker: calendar success rate, avg duration  │
     │  ▸ INSERT into task_events: "completed"                         │
     │  ▸ Send response to CLI                                         │
     │                                                                │
     │  RESPONSE: "Done — I'll remind you to review the PR at         │
     │             3:00 PM tomorrow (Aug 13)."                         │
     └─────────────────────────────────────────────────────────────────┘
```

---

## 2. Compound Task Flow (Multi-Agent)

```
USER: "Note this bug, fix it, then deploy the fix"
     │
     ▼
  INTENT CLASSIFIER → confidence 92% → compound intent detected
     │
     ▼
  PLANNER decomposes into 3 sub-tasks:
     │
     │  ┌──────────────────────────────────────────────┐
     │  │  Sub-task A: Notes Agent                      │
     │  │  Intent: store_note                           │
     │  │  Tier: auto                                   │
     │  │  Resources: ["notes_db"]                      │
     │  │  depends_on: []                               │
     │  └──────────┬───────────────────────────────────┘
     │             │
     │  ┌──────────▼───────────────────────────────────┐
     │  │  Sub-task B: Coding Agent                     │
     │  │  Intent: fix_bug                              │
     │  │  Tier: confirm                                │
     │  │  Resources: ["project:<path>"]                │
     │  │  depends_on: [A]   ◄── waits for note stored │
     │  └──────────┬───────────────────────────────────┘
     │             │
     │  ┌──────────▼───────────────────────────────────┐
     │  │  Sub-task C: Deploy Agent                     │
     │  │  Intent: deploy_fix                           │
     │  │  Tier: production_gate (if prod target)       │
     │  │  Resources: ["project:<path>", "github:<repo>"]│
     │  │  depends_on: [B]   ◄── waits for fix done    │
     │  └──────────────────────────────────────────────┘
     │
     ▼
  TASK QUEUE receives all three, enforces dependency order:
     │
     │  A runs immediately (no deps)
     │  B waits until A.status = DONE
     │  C waits until B.status = DONE
     │
     │  If B needs confirmation:
     │     B.status = AWAITING_CONFIRM
     │     CLI renders: "I want to write these 3 files: [...]. Proceed?"
     │     User confirms → B.status = RUNNING
     │
     │  If C hits production_gate:
     │     C.status = AWAITING_APPROVAL
     │     CLI renders diff/test/security summary
     │     User MUST use the /approve endpoint (interactive TTY only)
     │     → C.status = RUNNING
```

---

## 3. Error Flow (Failure Path)

```
  RUNNING task encounters an error
     │
     ▼
  ERROR TAXONOMY classifies:
     │
     ├── TRANSIENT (network timeout, API rate limit)
     │      │
     │      ▼
     │   retry.py: backoff_delay = random(0, min(30, 1.0 * 2^attempt))
     │      │
     │      ├── attempt < 3 → RETRY_QUEUED → re-enters QUEUED
     │      │                   (snapshot restored first)
     │      │
     │      └── attempt >= 3 → DEAD → dead_letter_queue
     │                          │
     │                          ▼
     │                  User notified conversationally:
     │                  "That failed 3 times — [specific error].
     │                   I've stopped retrying. Want me to try
     │                   a different approach?"
     │
     ├── VALIDATION (bad input, file doesn't exist)
     │      │
     │      ▼
     │   FAILED immediately (0 retries)
     │   User told exactly what was wrong:
     │   "The file path you mentioned doesn't exist:
     │    /src/auth/login.py — did you mean /src/auth/auth.py?"
     │
     ├── PERMISSION (blocked-tier action attempted)
     │      │
     │      ▼
     │   REFUSED (0 retries, logged as security event)
     │   "I can't do that — writing to password fields
     │    is blocked by policy."
     │
     ├── DESTRUCTIVE_RISK (needs confirmation gate)
     │      │
     │      ▼
     │   Escalated to confirm/production_gate
     │   Task paused until human approves
     │
     └── SYSTEMIC (agent crash, reconciliation mismatch)
            │
            ▼
         circuit_breaker.record_failure(agent)
            │
            ├── consecutive_failures < 5 → retry (2x max)
            │
            └── consecutive_failures >= 5 → circuit OPEN
                   │
                   ▼
                All new tasks for this agent REJECTED:
                "Deploy Agent is unhealthy — 5 consecutive
                 failures. Not queueing more until investigated."
```

---

## 4. Data Flow: Secrets & External APIs

```
  Agent needs GitHub PAT for deployment
     │
     ▼
  vault.get_secret("github_pat")
     │
     ├── Try 1: OS Keychain (keyring library)
     │      Success → return secret (in memory only, never logged)
     │      Fail ──┐
     │             ▼
     ├── Try 2: Encrypted file (~/.config/max-os/vault.enc)
     │      AES-256, key from OS keyring-stored passphrase
     │      Success → return secret
     │      Fail → raise VaultError (task fails, user notified)
     │
     ▼
  Agent makes external API call
     │
     ▼
  data_boundary.py intercepts outbound payload:
     │
     ├── Strip any file content not explicitly needed for this task
     ├── Mask credential-shaped strings (regex patterns for API keys,
     │   tokens, passwords)
     ├── Verify payload size is within task-scoped bounds
     │
     ▼
  External API call proceeds (GitHub / Anthropic)
     │
     ▼
  Trace logger records:
     ├── THAT a call was made (purpose, timestamp, response code)
     ├── NOT the API key
     ├── NOT the full request/response payload
     └── NOT any user secrets
```

---

## 5. Data Flow: Kill Switch (Emergency Path)

```
  User hits: max kill  (or double Ctrl+C)
     │
     ▼
  CLI sends: POST /v1/kill  (bypasses normal request queue)
     │
     ▼
  Kill Switch Supervisor (signal handler, registered at boot):
     │
     │  BUDGET: 1 second total, no exceptions
     │
     ├── 1. SIGTERM to all subprocesses (git, test runners, deploys)
     │      Wait 500ms
     │
     ├── 2. SIGKILL to any subprocess still alive
     │
     ├── 3. Mark ALL in-flight tasks: status = 'killed'
     │      (direct DB write, no state machine — this is the one case
     │       where the normal transition rules are bypassed)
     │
     ├── 4. Release all locks (force-release, no wait)
     │
     ├── 5. INSERT task_events: "kill_switch_activated"
     │
     └── 6. Daemon enters idle state (ready for new commands)
            or exits (depending on kill mode)
```

---

## 6. Data Flow Summary Table

| Flow | Input | Transforms | Output | Stored In |
|------|-------|------------|--------|-----------|
| User request | Raw text | Classify → Plan → Queue → Execute → Reconcile | Task result | tasks, task_events |
| Calendar create | Intent + entities | Parse time → conflict check → insert | Event ID | calendar_events |
| Note store | Intent + content | Store → embed (local model) | Note ID | notes, note_embeddings |
| Note search | Query text | Embed query → cosine similarity | Ranked results | (read-only) |
| Code fix | Intent + repo path | Snapshot → agent work → test → reconcile | Diff summary | coding_tasks |
| Deploy | Intent + target | Preflight → stage → gate → deploy → monitor | Deploy status | deploy_tasks |
| Error | Exception | Classify → retry/fail/refuse/escalate | Resolution | task_events, DLQ |
| Kill | Signal | Halt all → mark killed → release locks | Idle state | task_events |
| Startup recovery | DB scan | Find interrupted → mark/resume/surface | Recovered state | tasks, task_events |

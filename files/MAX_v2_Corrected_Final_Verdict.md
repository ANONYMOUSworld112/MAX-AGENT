# MAX v2 — Corrected Architecture + Final Verdict
### Every flagged issue addressed, scope cut to what's actually buildable

---

## 1. Fix Log — Every Issue From the Verdict, Addressed

| # | Issue | Fix |
|---|---|---|
| 1 | No policy on what data leaves the machine | **Data Boundary Policy** (below) — explicit, enforced in code, not assumed |
| 2 | No kill switch built before anything else | **Kill Switch is now Component #0** — nothing else in the system initializes without it existing first |
| 3 | Scope too large to ever finish | **Cut to 4 core agents for v1**: Calendar, Notes, Coding, Deploy. Everything else moved to a "later" list, explicitly not built yet |
| 4 | No way to trace "which agent did this" | **Trace Log Viewer** added as a required component, not optional dashboard polish |
| 5 | No credential/secrets storage design | **Local Encrypted Vault** specified, no plaintext config files for keys |
| 6 | "Memory feedback" was just logging, not learning | **Redefined as Outcome Tracker** with a concrete, honest scope — it improves *planning estimates*, not agent intelligence itself |
| 7 | Input-control agents too risky for v1 | **Formally deferred**, not designed further until v1 has 2+ weeks of real daily use |

---

## 2. Data Boundary Policy (fixes issue #1)

This is now a hard rule enforced in the Prompt Agent, not a design intention:

```
BEFORE any agent call to an external LLM API:

  strip or mask:
    - file contents from outside the active project folder
    - any string matching credential/key patterns
    - calendar/email content unless the task explicitly requires it

  send only:
    - the minimum context needed for THIS specific task
    - never the full project or full inbox "just in case"
```

**Plain answer to the question you owe yourself:** yes, your prompts and
relevant file/task content go to whatever LLM API you're using (Claude,
etc.) — that's how the agents reason at all. What changes with this fix is
that it's *minimized and explicit per task*, not a standing firehose of
your calendar, files, and screen content sent on every call.

---

## 3. Kill Switch — Component #0 (fixes issue #2)

```
System boot sequence:

1. Kill Switch Service starts FIRST — before Main Agent, before any worker
2. Kill Switch listens on a hotkey / local signal, independent of the UI
3. If triggered: sends a hard STOP to every running agent process,
   revokes all active locks, no confirmation dialog
4. Main Agent cannot fully initialize until Kill Switch reports "armed"
```

This ordering matters: if the kill switch is just "another feature," it's
the kind of thing that gets deprioritized. Making it a boot dependency
means the system literally cannot run without it working.

---

## 4. Scoped v1 Architecture (fixes issue #3)

```
USER INPUT
    │
    ▼
Intent Classifier → Router
    │
    ├── "schedule / remind"        → Calendar Agent      [auto]
    ├── "note this / remember"     → Notes Agent          [auto]
    ├── "build / fix / add code"   → Coding Agent          [confirm on file writes]
    └── "deploy / push / ship"     → Deploy Agent          [confirm — always, per DA-7 rule]
    │
    ▼
Prompt Agent (applies Data Boundary Policy)
    │
    ▼
Agent executes → Trace Logger records every step
    │
    ▼
Result → Outcome Tracker (logs: task type, time taken, success/fail)
    │
    ▼
Response to user
```

**Everything else from earlier conversations — Security Agent,
Architecture Review Gate, Database Agent, input-control agents, event bus,
resource lock manager — is real, well-designed, and explicitly NOT part of
v1.** They get added one at a time, only after the 4 core agents have run
reliably for real daily use. This is the single biggest structural fix:
the full 15-agent system was the end state, not the starting point, and v1
was never supposed to be all of it at once.

---

## 5. Trace Log Viewer (fixes issue #4)

Minimum viable version — not a dashboard, just a queryable log:

```
Every agent action writes: { timestamp, agent, task, input_summary,
                               result, duration, success }

CLI command: max trace --last 20
CLI command: max trace --agent deploy_agent --failures-only
```

This answers "which agent did this and did it work" in one command,
before you ever need a UI for it.

---

## 6. Local Encrypted Vault (fixes issue #5)

```
API keys, DB credentials, cloud credentials
    → stored in OS keychain (e.g. `keyring` library) or a locally
      encrypted file (age/sops), never in a plaintext .env committed
      or left in a config file agents can read directly

Agents request credentials at runtime through a Vault interface,
never read the raw secret file themselves.
```

Small addition, closes the most common real-world leak vector (secrets
sitting in a plaintext file that eventually gets synced, screenshotted, or
committed by accident).

---

## 7. Outcome Tracker, Honestly Scoped (fixes issue #6)

What it will actually do: track task duration and success/fail rate per
task type, and feed that back into the Planner's *time estimates* — e.g.
"deploys with database migrations take 40% longer than estimated, adjust."

What it will NOT do, and I won't pretend otherwise: make agents smarter at
reasoning. That requires prompt/model improvements, not a logging table.
Calling this "learning" earlier oversold what it does — it's operational
telemetry, and that's still genuinely useful, just not intelligence.

---

## 8. Final Verdict — On the Corrected v1 Design

**This version is buildable, and I'd stand behind it.**

The difference between this and the original 15-agent design isn't that
the original was wrong — it was a legitimate end-state architecture. The
fix was sequencing: nothing here now requires you to build infrastructure
you don't need yet before getting value.

**As a developer:** 4 agents, one router, one prompt layer, one trace log,
one vault. This is genuinely a 2-3 week solo build, not a multi-month one.

**As a founder:** you now have something you could actually use daily
within weeks, which is the only way you'll find out what agent #5 should
be — real usage, not more up-front design.

**As a security reviewer:** the two highest-value fixes — kill switch as
boot dependency, and secrets never in plaintext — close the gaps that
mattered most. The Data Boundary Policy doesn't eliminate third-party data
exposure (it can't, given LLM APIs are how this works), but it makes the
exposure minimal and explicit instead of an unexamined assumption.

**As a client:** I'd trust this v1. Calendar, notes, coding help, and a
deploy step that always asks before touching production — nothing here
can seriously hurt me, and that's exactly the right amount of trust to
extend on day one.

**What hasn't changed, and shouldn't:** the advice from before still
holds. Build this, use it for two weeks, and let real friction — not the
architecture diagram — decide what gets added next.

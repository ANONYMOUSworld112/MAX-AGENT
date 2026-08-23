# Hybrid Dual-Lane AI Agent — Architecture & Build Spec
Linux-only · Hybrid LLM (paid API + local model) · Main Agent + Coding Agent (opencode)

---

## 1. Core Concept (from your sketch)

Two agents, not a swarm:

- **Main Agent** — the only "brain" the user talks to. Handles everything that is NOT a build/code task: Q&A, web search, form-filling, file ops, app install/run, voice I/O. Has full Linux system access.
- **Coding Agent** — invoked ONLY when Main Agent classifies the input as a coding/build task. It doesn't talk to the user directly; it takes a prompt from Main Agent, drives `opencode` in a real terminal, builds 0→100%, self-tests, and reports back.

Two request queues run **in parallel with each other**, but each queue is **strictly serial internally**:

```
                         ┌─────────────────────────────┐
                         │   Input Layer (text + voice) │
                         │   STT: Faster-Whisper        │
                         └───────────────┬──────────────┘
                                         │
                                 ┌───────▼────────┐
                                 │   Classifier    │  (Main Agent, LLM-based intent check)
                                 └───┬─────────┬───┘
                    non-coding task  │         │  coding / build task
                    ┌────────────────▼─┐     ┌─▼────────────────────┐
                    │  GENERAL QUEUE    │     │   CODING QUEUE        │
                    │  (FIFO, serial)   │     │   (FIFO, serial)      │
                    └────────┬──────────┘     └──────────┬────────────┘
                             │                            │
                    ┌────────▼──────────┐     ┌───────────▼────────────┐
                    │   MAIN AGENT       │     │   CODING AGENT          │
                    │ - web search        │     │ - crafts/receives       │
                    │ - browser forms     │     │   optimal prompt        │
                    │ - file ops          │     │ - opens pty/tmux term   │
                    │ - app install/run   │     │ - types `opencode`      │
                    │ - hybrid LLM router │     │ - pastes prompt          │
                    │ - voice (ElevenLabs)│     │ - watches output stream │
                    └────────┬───────────┘     │ - error → retry loop     │
                             │                  │ - build → test → verify  │
                             │                  │ - self-check vs goal     │
                             │                  └───────────┬──────────────┘
                             │                              │
                             └──────────────┬───────────────┘
                                    ┌────────▼─────────┐
                                    │  Report to user   │
                                    │  (text/voice) +   │
                                    │  pop next in queue │
                                    └────────────────────┘
```

**Why two queues instead of one:** a 20-minute build task must never block "what's the weather" from getting answered. Each queue has exactly one worker (serial = no race conditions on the same terminal/session), but the two workers run as independent processes/threads, so both lanes progress simultaneously.

---

## 2. Component Breakdown

### 2.1 Input Layer
- Accepts text (API/socket) and voice (mic → Faster-Whisper STT → text).
- Normalizes every input into a job object:
```json
{ "job_id": "uuid", "text": "...", "source": "text|voice", "session_id": "...", "ts": "iso8601" }
```

### 2.2 Classifier (runs inside Main Agent, cheap/fast model)
- Binary decision: `coding_task` vs `general_task`.
- Trigger words: build, code, fix, implement, write a script, create a repo, add a feature, deploy, refactor, debug, etc. — but don't rely on keywords alone, confirm with a fast LLM call (local model preferred here to save API cost).
- Routes job to `general_queue` or `coding_queue`.

### 2.3 Hybrid LLM Router
- Config-driven: for each capability (classification, prompt-crafting, general chat, verification) pick **paid API** or **local model**.
- Suggested default: local model (Ollama) for classification + simple chat → paid API (Claude/GPT) for prompt-crafting and final verification, since those need higher reasoning quality.
- Fallback chain: if paid API fails/rate-limited → fall back to local model, and vice versa.

### 2.4 Main Agent
Responsibilities (everything except code building):
- General conversation / knowledge answers
- Real-time web search
- Browser automation for form-filling (Playwright, headless=false when needed)
- File system ops: create, delete, update, copy, move — full access
- Install & run applications (`apt`, `pip`, `npm`, systemd units, etc.)
- Voice output via ElevenLabs TTS
- **Prompt crafting**: when a job is routed to the coding queue, Main Agent (not the Coding Agent) writes the best possible build prompt from the user's raw request before handing it off.

### 2.5 Coding Agent
Only wakes up per coding-queue job. Sequence:
1. Receive the crafted prompt from Main Agent.
2. Open a real terminal session (use `tmux` via `libtmux`, or a `pty` via `pexpect` — tmux is more robust for long-running visible sessions).
3. Type `opencode` to launch it in that session.
4. Paste/write the prompt into the opencode prompt field.
5. Let opencode build from 0% → 100% autonomously.
6. **Stream-watch** the terminal output continuously for:
   - error patterns (stack traces, `Error:`, non-zero exit codes, lint/build failures)
   - completion markers (opencode's own "done"/success signal, or a sentinel line you ask opencode to print at the end)
7. **On error:** capture the error text, feed it back into opencode as a follow-up correction prompt (same session — don't restart from scratch), bounded to e.g. 5 retries before escalating to Main Agent as "needs human input."
8. **On apparent completion:** run the project's own test/build commands (`npm test`, `npm run build`, `pytest`, etc.) to confirm it actually works — don't trust opencode's self-report alone.
9. **Verify against goal:** run a final LLM check comparing the original user goal to what was actually produced (diff of requirements vs. deliverable). If it matches → success. If not → re-enter the build loop with a refined prompt describing the gap (this is your "re-do" arrow).
10. Report status object back to Main Agent:
```json
{ "job_id": "...", "status": "success|failed|needs_input", "summary": "...", "artifacts": ["path1","path2"] }
```
11. Main Agent relays this to the user (text/voice) and pulls the next job from the coding queue.

### 2.6 Error Handling (applies to both lanes)
- Every stage wrapped in try/except with structured logging (job_id, stage, error).
- Retry with exponential backoff for transient failures (network, API rate limit, terminal hang).
- Hard cap on retries per job (avoid infinite loops) — after cap, mark `needs_input` and surface to user instead of silently failing.
- Terminal-level watchdog: if opencode hangs with no output for N minutes, kill and restart the session with the same prompt + "resume" context.
- All errors logged to a persistent store (SQLite/Postgres) so failures are auditable, not just printed to console.

---

## 3. Concurrency Model (recommended stack)

Given you're already using FastAPI + Redis/Celery in FORGE CI, reuse that pattern:

- **Redis** as the broker/queue backend.
- **Two Celery queues**: `general_queue` (concurrency=1) and `coding_queue` (concurrency=1).
- Each queue is serial internally (one worker) → no two coding tasks touch the terminal at once, no two general tasks race on the same LLM context.
- The two queues run as separate worker processes → true parallelism between lanes.
- A lightweight FastAPI endpoint accepts jobs, classifies, and pushes to the correct Celery queue.
- Job status pushed to a WebSocket/Socket.IO channel so the user gets live updates (you already use Socket.IO in CYBERBLACK-SoC-DASHBOARD — same pattern applies here).

If you'd rather stay dependency-light (no Redis), a pure-Python alternative is two `asyncio.Queue` objects each drained by a single `asyncio.Task`, running inside one process — simpler, but loses cross-process durability (a crash loses in-flight jobs). Redis/Celery is the safer choice given you want "errors handled freely" with retries surviving restarts.

---

## 4. Build Prompt

Paste this into your coding agent (Claude Code / opencode / whichever you're using to scaffold this) to build the system described above:

```
Build a Linux-only, Python-based dual-lane AI agent orchestrator called "PHONEX-CORE" with the following exact architecture:

TECH STACK
- FastAPI for the HTTP/WebSocket API layer
- Redis + Celery for two independent job queues: "general_queue" and "coding_queue", each with concurrency=1 (serial within a queue), running as separate worker processes so both queues progress in parallel with each other
- SQLite (or Postgres if available) for job/error logging and audit trail
- Socket.IO for real-time job status streaming to the client
- libtmux (or pexpect) for driving a real terminal session
- Faster-Whisper for speech-to-text input
- ElevenLabs API for text-to-speech output
- Playwright for browser automation / form filling
- A hybrid LLM router module supporting both a paid API (Anthropic/OpenAI-compatible) and a local model via Ollama, selectable per-capability via config

COMPONENTS TO IMPLEMENT

1. Input Layer
   - Accepts text via REST/WebSocket and voice via mic upload, transcribed with Faster-Whisper
   - Normalizes every input into a Job: {job_id, text, source, session_id, timestamp}

2. Classifier
   - Fast LLM call (prefer local model) that labels each Job as "coding_task" or "general_task"
   - Routes to the correct Celery queue accordingly

3. Main Agent (Celery worker on general_queue, concurrency=1)
   - Handles all non-coding jobs: general Q&A, real-time web search, browser form-filling via Playwright, file operations (create/delete/update/copy/move) with full filesystem access, installing and running applications via subprocess, voice output via ElevenLabs
   - For any job classified as coding_task, instead of answering directly, Main Agent crafts the best possible build prompt from the user's raw request (expand vague requests into a clear, complete spec) and pushes a new Job onto coding_queue with that crafted prompt attached
   - Uses the hybrid LLM router for all its LLM calls, respecting the configured paid-API/local-model preference per capability, with automatic fallback if one is unavailable

4. Coding Agent (Celery worker on coding_queue, concurrency=1)
   - Receives the crafted prompt
   - Opens a tmux session, launches `opencode` inside it, writes the prompt into it, and lets it build
   - Continuously streams and parses terminal output for error patterns and completion markers
   - On error: captures the error text and feeds it back into the same opencode session as a correction, up to 5 retries, with exponential backoff between attempts
   - On apparent completion: runs the project's own build/test commands to confirm the build actually works (don't trust self-reported success)
   - Runs a final LLM verification step comparing the original user goal against the actual deliverable; if it doesn't match, re-enters the build loop with a refined prompt describing the gap, capped at 3 re-do cycles before escalating
   - Persists a status report {job_id, status, summary, artifacts} and pushes it back to Main Agent's reporting channel

5. Error handling (system-wide)
   - Every stage wrapped in structured try/except with job_id-tagged logging to SQLite
   - Retry with exponential backoff for transient failures (network, rate limits, terminal hangs)
   - Hard retry caps per job; after cap, mark job "needs_input" and surface to the user rather than looping forever
   - A watchdog that detects a hung opencode session (no terminal output for N minutes) and restarts it with resume context

6. Reporting
   - All job status changes streamed to the client over Socket.IO in real time
   - Main Agent delivers final results to the user via text and, if the input was voice, also via ElevenLabs TTS

DELIVERABLES
- Full project scaffold with a clear folder structure separating: api/, workers/, agents/main_agent/, agents/coding_agent/, llm_router/, voice/, browser/, db/, logs/
- requirements.txt / pyproject.toml
- A docker-free setup script for Ubuntu/Debian (systemd services for the FastAPI app and both Celery workers, plus Redis)
- README documenting how to configure the hybrid LLM router (paid API keys vs local Ollama model), start the two queues, and verify both lanes run concurrently
- Basic tests proving general_queue and coding_queue process jobs independently and in parallel

Build this from zero to a fully working, tested state without stopping, handling and self-correcting any errors encountered during the build, and report back when it is complete and verified against these requirements.
```

---

## 5. Notes / Open Decisions

- **Terminal driver**: `tmux`+`libtmux` is more robust than raw `pexpect` for a long-running, potentially hours-long `opencode` session you want to inspect/attach to live — recommend tmux.
- **Retry caps**: 5 retries for opencode error-correction, 3 re-do cycles for goal-verification mismatches — tune based on real build times once you see it running.
- **Redis vs pure-asyncio**: Redis/Celery survives crashes and restarts (jobs aren't lost); pure in-process asyncio queues are simpler but lose in-flight state on a crash. Given you want "errors handled freely," Redis/Celery is the safer default.
- This maps cleanly onto your existing FORGE CI stack (FastAPI, Redis/Celery, WebSocket) — you could host PHONEX-CORE as another service under that same platform rather than building the plumbing twice.

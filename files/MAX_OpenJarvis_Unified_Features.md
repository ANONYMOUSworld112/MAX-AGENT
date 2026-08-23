# MAX ∪ OpenJarvis — Unified Feature Set
### Every feature across both projects, merged into one map

---

## 1. Features Both Projects Share

| Feature | OpenJarvis | MAX |
|---|---|---|
| Local-first personal AI philosophy | Core thesis | Orchestration/UI local; reasoning is cloud-API (see §5) |
| Multi-agent architecture, specialized per task | 8 built-in agents | 4 built (v1), 27 designed total |
| Scheduled daily-briefing agent with TTS output | `morning_digest` | Daily Brief Agent + Voice Output (designed, Phase 5/6) |
| Deep research agent with citations | `deep_research` | Research Agent |
| Code-execution agent | `code-assistant` / `native_openhands` | Coding Agent |
| Stateful, memory-backed monitoring agent | `monitor_operative`, `scheduled-monitor` | Memory Extraction Agent + Scheduler (Phase 6) |
| Skill/tool extensibility concept | Full marketplace (13.7k+ skills) | Named in original vision, not built |

---

## 2. OpenJarvis Has, MAX Doesn't

- **Local model inference by default** (Ollama, starter model shipped in
  the installer) — the actual reasoning runs on-device, cloud is the
  exception, not the rule.
- **Energy / FLOPs / latency / dollar-cost as first-class eval metrics**,
  not just correctness — a genuinely different evaluation philosophy.
- **A real skills marketplace** — 13,700+ community skills via OpenClaw,
  ~150 via Hermes Agent, following the open `agentskills.io` standard.
- **One-line installers for 5 platforms** (macOS/Linux/WSL2/native
  Windows/Desktop GUI), a working CLI (`jarvis`), and `jarvis doctor` for
  status checks.
- **OAuth-based real service integration** — one OAuth flow covers
  Gmail/Calendar/Tasks (`jarvis connect gdrive`).
- **Benchmarking + leaderboard infrastructure** — `jarvis bench skills`,
  a public leaderboard, skill optimization via `jarvis optimize skills
  --policy dspy`.
- **A clean 3-mode execution taxonomy** — on-demand / scheduled /
  continuous — as the top-level way agents are categorized.
- **Academic backing** — Stanford (Hazy Research, Scaling Intelligence
  Lab), an arXiv paper, named research sponsors (Google Cloud, IBM
  Research, Ollama, Stanford HAI).
- **A live open-source community** — 8.5k stars, 963 commits, Discord,
  public roadmap, "comment take to get auto-assigned" contribution model.
- **Multiple named reasoning architectures as distinct agents** —
  `native_react` (ReAct loop), `native_openhands` (CodeAct), `orchestrator`
  (automatic tool selection) — offered as interchangeable choices, not one
  fixed approach.

---

## 3. MAX Has, OpenJarvis Doesn't (in its public materials)

- **Two hard human gates enforced inside the code path**, not a UI —
  architecture review before code, production approval before deploy.
  Verified to resist multiple bypass phrasings.
- **Deadlock prevention by construction** — sorted-order lock
  acquisition, not just documented as a risk.
- **Per-agent circuit breakers** — a misbehaving agent stops itself after
  5 consecutive failures instead of retrying indefinitely.
- **A full error taxonomy** (transient/validation/permission/
  destructive_risk/systemic) with a defined handling path per class.
- **Dead letter queue** — nothing that exhausts retries silently
  disappears.
- **Kill Switch as a boot dependency (Component #0)** — the system
  cannot fully initialize without it reporting armed.
- **Idempotency keys on every task** — re-running the same task never
  duplicates a side effect.
- **Reconciliation checking** — an agent's self-reported success is
  verified against real system state, never trusted blindly.
- **A production deployment pipeline** (9 stages: preflight through
  monitoring) with staging, health checks, and auto-rollback.
- **Explicit permission-tier immunity to phrasing** — "do whatever it
  takes" or "skip approval" cannot escalate a tier, by construction, not
  by policy.
- **A session-resumable build protocol** — a coding agent with zero
  memory of a prior session can resume exactly where it left off, backed
  by real SQL state (`phases`/`steps`/`decisions_log`).
- **An explicit Data Boundary Policy** — what leaves the machine via LLM
  calls is minimized and stated, not assumed.
- **A ToS-safe design decision already made** — LinkedIn integration is
  draft-only by design, specifically to avoid automated-access violations.
- **17 logged architectural decisions with reasoning**, so a future
  session doesn't re-litigate settled questions.

---

## 4. The Full Union — Every Feature, One List

**Interaction & Access**
Local-first orchestration · CLI · voice output (TTS) · multi-OS
installers* · OAuth service integration* · desktop GUI*

**Agents**
Coding · research · deployment (repo-push + production) · calendar ·
notes · scheduling/monitoring · daily briefing · document generation ·
inbox triage · expense tracking · CRM · content drafting · security
scanning · database ops · cloud/infra ops · data pipelines · backups ·
analytics · input control (keyboard/mouse/screen) · memory extraction ·
architecture review · code review · testing · debugging

**Reasoning Approaches**
ReAct loop* · CodeAct* · automatic tool selection* · fixed
intent-classify-then-route (MAX's current approach)

**Reliability Engineering**
Idempotency keys · deadlock prevention by construction · per-agent
circuit breakers · error taxonomy · dead letter queue · reconciliation
checking · heartbeat watchdog · bounded adaptive retry

**Safety & Governance**
Two code-enforced human gates · kill switch as boot dependency ·
permission tiers immune to phrasing · encrypted secrets vault · data
boundary policy · sandboxed input-control tier

**Extensibility**
Skills marketplace* (13.7k+ community skills, open standard) ·
tiered agent roadmap (MAX) · scope checkpoints between tiers (MAX)

**Evaluation & Ops**
Benchmarking + public leaderboard* · energy/FLOPs/cost as eval metrics* ·
outcome tracker (MAX) · trace log (MAX) · quota-aware API usage (MAX)

**Project Infrastructure**
Session-resumable build protocol (MAX) · logged architectural decisions
(MAX) · phased build plan with acceptance criteria (MAX) · open
contribution model with public roadmap* (OpenJarvis)

*— marks features that currently exist only on the OpenJarvis side.

---

## 5. What This Union Actually Means

**The honest gap:** MAX's "local-first" claim is currently weaker than
OpenJarvis's — MAX runs orchestration locally but reasoning goes to cloud
APIs; OpenJarvis runs reasoning locally by default. If local-first is
core to MAX's pitch, this needs either a real local-inference path
(Ollama, same as OpenJarvis) or the pitch needs to shift toward what MAX
actually is: cloud-API-first with local-first *safety and state*.

**Worth seriously considering adopting from OpenJarvis:**
- The 3-mode execution taxonomy (on-demand/scheduled/continuous) as an
  additional way to categorize MAX's agents alongside the existing risk
  tiers — these are complementary axes, not competing ones.
- A minimal skills-import mechanism, even a small one, since MAX
  currently has no extensibility story at all beyond adding agents to
  the fixed roster.

**What MAX genuinely has that's worth keeping as the core differentiator:**
the reliability and safety engineering — deadlock prevention by
construction, circuit breakers, code-enforced gates, the session-resumable
build protocol. None of this shows up in OpenJarvis's public materials.
That's the honest, defensible pitch: not "we also do local personal AI,"
but "we do the production-reliability engineering this category mostly
skips."

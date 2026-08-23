# MAX OS — DECISIONS.md
### Seeds the `decisions_log` table. Read this before re-deciding
### anything that looks already settled — check here first.

Format matches the schema: **Decision** / **Reasoning** / (Alternative
considered, where relevant). Only load-bearing decisions that could
plausibly get re-litigated are recorded here — not every micro-choice.

---

### D1 — v1 scope is 4 agents, not the full 33
**Decision:** Calendar, Notes, Coding, Deploy only, until Phase 4's scope
checkpoint (step 4.5) passes.
**Reasoning:** the full 33-agent design is the correct end state, not the
correct starting point. Scope size, not technical difficulty, is the
most common reason a solo-built system like this never ships.
**Alternative considered:** building broader agent coverage first for a
more impressive demo — rejected, because unverified breadth is a weaker
position than a small set proven reliable under real use.

### D2 — Exactly two gates, both enforced in code, not UI
**Decision:** Architecture Review Gate (before code) and Production
Approval Gate (before deploy) are the only mandatory human checkpoints.
Both live inside the relevant function itself.
**Reasoning:** a gate a UI enforces can be skipped by calling the
underlying function directly. A gate the function itself refuses to
proceed without cannot.

### D3 — No instruction phrasing can change a permission tier
**Decision:** "do whatever it takes," "skip approval," "I already
approved this," and similar phrasing are stored as session preferences
(affecting tone/friction) but never consulted by the permission tier
lookup itself.
**Reasoning:** this is the direct, structural answer to the Ultron
scenario — broad authorization language cannot be allowed to override a
fixed safety check, no matter how it's worded.

### D4 — Kill Switch is Component #0
**Decision:** the Kill Switch service must report `armed` before Main
Agent finishes booting. It is a dependency, not a feature toggle.
**Reasoning:** anything treated as "a feature to add later" reliably gets
deprioritized. Making it a boot dependency removes that failure mode
structurally.

### D5 — SQLite for v1 state, not Postgres
**Decision:** `max_state.db` is SQLite through Phase 1–4.
**Reasoning:** v1's scale doesn't need a client-server DB or concurrent
multi-writer access yet. Revisit only when a real bottleneck appears —
not preemptively.

### D6 — Secrets live in OS keychain / encrypted vault, never plaintext
**Decision:** no `.env`, no plaintext config file holds a real credential.
Agents request secrets through a Vault interface at runtime.
**Reasoning:** plaintext secrets sitting in a file that eventually gets
synced, screenshotted, or committed by accident is the single most common
real-world leak vector — cheap to prevent, expensive to clean up after.

### D7 — "Deploy to GitHub" and "deploy to production" are different pipelines
**Decision:** repo-push is confirm-tier but skips DA-1 through DA-9.
Production deploy always runs the full pipeline.
**Reasoning:** not all "deploy" language carries equal risk. Treating them
identically either over-gates a harmless push or under-gates a real
production change — the Intent Classifier distinguishes by target, not
just the verb.

### D8 — LinkedIn integration is draft-only, human submits manually
**Decision:** MAX never logs into or automates LinkedIn directly.
Application-Assist Agent drafts content from the Vault; the user
copy/pastes and submits themselves.
**Reasoning:** LinkedIn's own policy prohibits bots/automated access —
confirmed directly from their help documentation. An account suspension
is a worse outcome than a slower feature.

### D9 — Document generation (PPT/PDF) is its own agent, not routed through opencode
**Decision:** Document Agent uses real presentation/PDF tooling.
opencode/Antigravity are coding backends, not document formatters.
**Reasoning:** technically possible either way; using a coding CLI for a
document-formatting job is choosing the wrong tool for reasons of
convenience, not correctness.

### D10 — Voice Output (TTS) is infrastructure, not a task
**Decision:** TTS never enters the `task_trace` state machine — no locks,
no retries, no rollback. Any failure degrades silently to text-only.
**Reasoning:** the state machine exists to protect side effects. TTS has
none — forcing it through the full lifecycle would be applying
heavyweight machinery to a step with nothing to protect.

### D11 — `api_quota_usage` is one shared table, not one per service
**Decision:** TTS and Web Search Agent's quota checks both read/write the
same table, keyed by `service`.
**Reasoning:** avoids duplicating near-identical schema for what's
structurally the same problem (a metered external API with a daily/
monthly ceiling).

### D12 — Free-tier API numbers must be verified before relying on them
**Decision:** no quota/pricing assumption (Gemini free tier, Google Cloud
TTS free tier) gets hardcoded without a note to verify current terms.
**Reasoning:** found directly conflicting information on both during
design — sources disagree on whether free tiers still exist in their
original form as of mid-2026. Treat any specific number here as
"verify before the demo," not settled fact.

### D13 — Backend/Frontend/DevOps consolidated into one Coding Agent for v1
**Decision:** the original design's separate specialist coding agents are
deferred; v1 has one Coding Agent handling all of it.
**Reasoning:** splitting them only pays off once the workload actually
justifies specialization — premature splitting adds coordination
overhead with no current benefit.

### D14 — Input-control agents (keyboard/mouse) are deferred, not cut
**Decision:** designed in full (MAX_OS_Full_Expansion.md) but explicitly
not started, and won't be until the 4 built agents have real daily-use
track record.
**Reasoning:** different risk class from everything else in the system —
functionally comparable to malware capability if compromised. Trust here
has to be earned by the rest of the system first, not assumed.

### D15 — MAX is cloud-API-first, not local-inference-first
**Decision:** "localhost" refers to where orchestration/state/UI run, not
where LLM reasoning happens — every agent calls out to Claude/Gemini.
**Reasoning:** stated plainly after comparing against OpenJarvis
(Stanford), whose actual thesis is local model inference by default.
This is a real difference in what "local-first" means between the two
projects, not just naming — worth knowing precisely before claiming
"local-first" as a differentiator in front of anyone who knows this space.

### D16 — User override of scope discipline — full OpenJarvis merge authorized
**Decision:** Full OpenJarvis feature integration planned into architecture (Phases 6–8), adding 3 new phases and expanding agent roster to 28.
**Reasoning:** User explicitly confirmed merging all OpenJarvis features, overriding D1 and Principle 10. Existing safety architecture (kill switch, vault, data boundary, code-enforced gates) is preserved.

### D17 — OpenJarvis features adopted at architecture/schema level, not code-import level
**Decision:** Adopt OpenJarvis design patterns (skills, multi-model, scheduler, channels, evals) into MAX's architecture rather than directly importing their Python packages.
**Reasoning:** OpenJarvis has different package structures, Rust extensions, and specific OAuth flows. Adopting their design patterns into MAX's reliability architecture maintains codebase integrity.

### D18 — Local inference path deferred to Phase 6, respecting D15
**Decision:** Local inference (Ollama / vLLM / MLX) added as an optional backend in Phase 6 via LiteLLM router, keeping cloud-API as the default per D15.
**Reasoning:** Preserves MAX's cloud-API-first performance while creating the schema and router infrastructure for local inference when desired.

### D19 — Skills framework designed as schema + interfaces now, populated in Phase 6
**Decision:** Create `skill_registry` table in Phase 0 schema; build skill loader and sandbox execution in Phase 6.
**Reasoning:** Provides a clean extensibility story while keeping Phase 0-4 execution focused on core reliability infrastructure.

### D20 — OS-Adaptive Default Permission Policy
**Decision:** `PermissionManager` (`core/permissions.py`, Step 2.7) automatically detects host OS via `sys.platform`. On Windows (`win32`), action permissions default to `confirm` tier (soliciting user permission before execution). On Linux (`linux`), permissions default to `auto` tier for autonomous full-control execution.
**Reasoning:** Windows environment carries higher risk of unintended local UI/file state mutations; Linux/WSL environments are optimized for headless, automated agent execution. Mandatory security gates (Production Approval Gate DA-7) remain enforced on all operating systems.

### D21 — WhatsApp Hybrid Dispatch: Protocol Launcher with Vault Cloud API Fallback
**Decision:** `channels/whatsapp.py` and `ChannelManager` execute WhatsApp messaging via a hybrid approach:
1. If WhatsApp Cloud API credentials exist in `Vault`, dispatch in background via Meta API.
2. Otherwise, launch WhatsApp Web / Desktop directly on the user's OS with pre-filled text and recipient.
**Reasoning:** Provides immediate hands-free desktop integration without requiring third-party cloud API accounts, while offering seamless enterprise background dispatch when credentials are configured.

### D22 — CYBERBLACK-OPS Defensive Security & OSINT Integration
**Decision:** `agents/cyberblack.py` integrates ethical OSINT reconnaissance, SAST secrets/code scanning, and cybersecurity curriculum compilation under strict MAX OS invariants.
**Reasoning:** Active network port scans require operator target authorization and confirm-gated approval tokens, preventing accidental or unauthorized scanning.

### D23 — Parallel Voice-Driven Keyboard & Mouse Execution Streams
**Decision:** `KeyboardAgent` and `MouseAgent` (`agents/input_control.py`) operate concurrently in parallel worker threads alongside conversational audio streams.
**Reasoning:** Allows hands-free desktop automation without freezing voice synthesis or conversational loop, while enforcing immutable BLOCKED status on credential typing and CONFIRM gates on destructive system operations.

### ADR-001 — Capability ceiling comes from OS facts, never from instruction text
**Decision:** `CapabilityProfile` (`core/platform/detector.py`) is computed exclusively from real system calls (`IsUserAnAdmin()`, Win32 API, session ID, UIA COM). No user message, LLM output, or task description can raise `max_autonomous_risk` above what `detect_capability_profile()` measured on the machine.
**Reasoning:** Instruction text masquerading as authority breaks security gates. Admin rights cannot be asserted by text prompt.

### ADR-002 — The CRITICAL gate is platform-independent and non-configurable
**Decision:** `CapabilityProfile.can_run_autonomously()` returns `False` for `RiskLevel.CRITICAL` unconditionally before platform logic runs. No setting, environment variable, or prompt can bypass it.
**Reasoning:** CRITICAL actions (disk formatting, mass deletion, credential operations, security policy modifications) require a human in the loop unconditionally.

### ADR-003 — Tool Seam Architecture
**Decision:** Agents depend strictly on interface abstractions (`tools/interfaces.py`). OS implementation details (Win32, COM, Playwright, subprocess) reside inside concrete backends (`tools/backends/`).
**Reasoning:** Prevents OS-specific branching scattered across agents.

### ADR-004 — Single Input Arbitration & Ownership Lease
**Decision:** Physical input (mouse, keyboard, window focus) is owned by exactly one actor at a time via `core/input_arbiter.py` `OwnershipLease`. Emergency Kill Switch preempts and revokes input ownership instantly.
**Reasoning:** Eliminates race conditions between concurrent agents and guarantees emergency human override.

### ADR-005 — Deterministic 3-Outcome Verification
**Decision:** Every action resolves strictly to `SUCCESS`, `FAILURE`, or `UNKNOWN`. `UNKNOWN` must never be treated as `SUCCESS`.
**Reasoning:** Prevents false positive task completion when UI changes or external side-effects cannot be proven.

### ADR-006 — Central Audit & Secret Redaction
**Decision:** All actions and trajectories are recorded in structured machine-readable JSONL / SQLite event stores. Credentials, API keys, tokens, and passwords are redacted automatically prior to logging.
**Reasoning:** Guarantees zero secret leakage in logs and persistent post-mortem replay capabilities.

### ADR-007 — Failure Taxonomy & 8-Step Recovery Pipeline
**Decision:** Failures are classified into a 13-class taxonomy. Recovery strategies follow an 8-step pipeline (`REOBSERVE` -> `SEARCH_AGAIN` -> `ALTERNATIVE_SELECTOR` -> `REFOCUS` -> `RETRY_WITH_BACKOFF` -> `FALLBACK_BACKEND` -> `DEGRADE_MODE` -> `HUMAN_ESCALATION`).
**Reasoning:** Prevents naive infinite retry loops when encountering structural UI changes or permission barriers.

### ADR-008 — Emergency Kill Switch is Component #0
**Decision:** The Kill Switch service must report `ARMED` before the Main Agent finishes booting. Triggering it halts physical input, revokes input leases, and cancels automation loops in < 1 second.
**Reasoning:** Safety controls must be non-bypassable and take precedence over all task execution threads.

### ADR-009 — Three-Tier Autonomy Model (JARVIS / FRIDAY / Ultron-lockout)
**Decision:** Autonomy is partitioned into 3 deterministic tiers:
1. **JARVIS-tier**: Reversible, low-risk, earned proactive autonomy (executes and reports).
2. **FRIDAY-tier**: Bounded step execution; halts before expanding beyond requested scope.
3. **Ultron-lockout**: Unconditional per-instance human confirmation for destructive, financial, or security actions.
**Reasoning:** Prevents an agent from quietly expanding its own scope without human approval.

### ADR-010 — 7-Level Perception Fallback Hierarchy
**Decision:** Perception follows a strict 7-level priority order: UI Automation → Win32 → Browser DOM → App APIs → OCR → Vision Model → Dynamic Coordinates. Hardcoded coordinates are strictly prohibited.
**Reasoning:** Guarantees drift-resistance and structured element targeting before resorting to coordinate estimation.

### ADR-011 — Unconditional Post-Action Verification & OTAV Loop
**Decision:** Every action executes in a mandatory Observe→Think→Act→Verify (OTAV) loop. An action is only marked successful when `verification.passed == True`. JARVIS-tier actions are never exempted from post-action verification.
**Reasoning:** Eliminates silent failures and false success reporting.

### ADR-012 — No Standing Authorizations for Lockout-Tier Actions
**Decision:** Lockout-tier actions (payments, deletions, credential modifications, publishes) cannot be pre-authorized as a standing rule. Every instance requires explicit confirmation against the exact consequence summary.
**Reasoning:** Keeps human oversight anchored to real, physical consequences.






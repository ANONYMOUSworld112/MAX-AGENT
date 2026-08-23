# MAX — Computer-Use Upgrade
## DECISIONS.md

Architecture Decision Records (ADRs) for choices already made across `PRD.md`, `TRD.md`, `ARCHITECTURE.md`, and `AGENTS.md`. If your main MAX OS project already has its own `DECISIONS.md`, treat this as the Computer-Use Layer's section of it — merge rather than maintain two logs.

---

### ADR-001: Windows-hosted execution node, not a stack rewrite

**Decision:** the Computer-Use Layer runs as a separate node on Windows, communicating with the existing (Linux-hosted) MAX orchestrator over a local API, rather than porting the whole MAX stack to Windows or building an OS-abstraction layer from day one.

**Why:** the original spec is explicit about prioritizing deep Windows integration (UIA, Win32) over cross-platform abstraction. Splitting by node keeps that depth without forcing the rest of MAX to move off Linux.

**Status:** Confirmed & Refined — The codebase supports a hybrid architecture: the core orchestrator, memory system, and API server run cross-platform (Linux/Windows/macOS), while the Computer-Use Layer runs either co-located or as a dedicated Windows execution node connected via the `/v1/tasks` API.

---

### ADR-002: UIA/Win32-first perception, not a generic automation library

**Decision:** Windows UI Automation and Win32 APIs are the primary perception/action mechanism; OCR and vision models are fallback-only (Levels 5–6 of 7).

**Why:** generic screen-scraping automation is fragile against UI drift and can't reliably distinguish "button is disabled" from "button doesn't exist yet." Semantic UI Automation gives structured, drift-resistant targeting; coordinates are the fallback of last resort, never the default.

**Alternative considered:** vision-model-first (screenshot → click coordinates for everything). Rejected as the primary mechanism — too fragile for a system meant to run unattended, though it stays as Level 6 fallback.

---

### ADR-003: Reuse existing SQLite/audit infrastructure, not a second logging system

**Decision:** the Computer-Use Layer's audit log and task memory write into the same SQLite (WAL mode) store the rest of MAX already uses, extended with new fields (`risk_tier`, `confidence`, `recovery_attempts`) rather than a parallel database.

**Why:** a single audit trail is the only way "what did MAX do and why" stays answerable from one place. Two logging systems means two places that can disagree.

**Dependency:** `REPO_AUDIT.md` §5 must confirm the current schema can absorb the new fields without a breaking migration.

---

### ADR-004: Three-tier autonomy model (JARVIS / FRIDAY / Ultron-lockout), not binary confirm-or-don't

**Decision:** every action carries one of three tiers rather than a simple "safe" / "needs confirmation" flag.

**Why:** a binary model collapses two genuinely different situations into one — "this is routine, just do it" and "this is new, do exactly what was asked and stop" are both "don't need blanket confirmation," but they have different failure modes if the agent over-generalizes. The middle tier (FRIDAY) exists specifically to prevent a "safe" action from quietly chaining into an unrequested one.

**Alternative considered:** single confidence-score threshold with no separate risk category. Rejected — confidence measures "how sure am I this will work," not "how bad is it if I'm wrong." Those are different axes; collapsing them is exactly the gap Ultron falls through (highly confident, catastrophically wrong scope).

---

### ADR-005: Tier promotion via logged track record, not self-reported confidence

**Decision:** an action type only moves from FRIDAY-tier to JARVIS-tier after a configurable number of consecutive verified successes (default: 20, zero failures), never because the model's own confidence score is high, and never because the user simply didn't object in the moment.

**Why:** letting an agent promote its own autonomy based on its own confidence is exactly the self-authorization pattern that makes Ultron dangerous. Track-record promotion requires an external, falsifiable signal (the Verification Agent's pass/fail record) instead of the agent's internal certainty.

---

### ADR-006: Verification runs unconditionally, no tier exemption

**Decision:** the Verification Agent checks every single action regardless of risk tier — JARVIS-tier actions are not exempted from post-action verification just because they didn't need pre-action confirmation.

**Why:** "low risk to act without asking" and "safe to skip checking whether it worked" are unrelated claims. Skipping verification on the routine 90% of actions is exactly how a system quietly starts reporting false success — the single most important property to hold to zero per `PRD.md` §9.

---

### ADR-007: No standing authorization for Ultron-lockout actions

**Decision:** lockout-tier actions (payments, deletions, security changes, sends/publishes, submissions) cannot be pre-authorized as a standing rule for a task — every instance requires its own explicit confirmation, shown against the specific consequence (amount, recipient, files, destination) at the time.

**Why:** a standing "always allow purchases under ₹X" rule set once, in a calm moment, is a scope grant an agent could later apply to a situation the user never actually considered. Per-instance confirmation keeps the human's approval tied to the actual consequence, not a hypothetical one agreed to in advance.

**Note:** this is a deliberate, permanent constraint — not something to revisit for convenience later. Any future request to add standing authorization for lockout-tier actions should be treated as a new decision requiring the same scrutiny as this one, not a quick config change.

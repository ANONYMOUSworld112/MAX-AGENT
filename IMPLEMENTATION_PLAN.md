# MAX — Computer-Use Upgrade
## IMPLEMENTATION_PLAN.md

Full detail for every phase, up front — nothing deferred to a "we'll write that doc later" placeholder. Testing and security/lockout verification are folded into each phase itself, not pushed into separate documents down the line.

| | |
|---|---|
| **Companion docs** | `PRD.md`, `TRD.md`, `ARCHITECTURE.md`, `AGENTS.md`, `REPO_AUDIT.md`, `API_CONTRACT.md`, `DECISIONS.md` |
| **Rule for every phase** | Not done until: **code exists → integrated → tested → executed on the real machine → verified** |

---

## Phase 0 — Repo Audit & Baseline

**Objective:** establish ground truth before a single line of new code is written.

**Preconditions:** none — this is the starting point.

**Deliverables:**
- `REPO_AUDIT.md` fully completed (real repo, not the template)
- `ADR-001` in `DECISIONS.md` confirmed or corrected against actual findings
- A captured baseline: current test suite run, current schema dump, current API route list

**Tasks:**
1. Walk every checklist item in `REPO_AUDIT.md` §1–11 against the real codebase.
2. Confirm or correct the Linux-only assumption (§11 of that doc) — this single finding determines whether `ARCHITECTURE.md` §1 needs a rewrite before Phase 1 starts.
3. Capture the current SQLite schema and confirm the new fields (`risk_tier`, `confidence`, `recovery_attempts`) can be added without a breaking migration.
4. Record every existing test that passes today — this is the regression floor for every later phase.

**Tests:** run the *existing* test suite once, unmodified, and archive the result. This is the only phase whose "test" is "confirm nothing is broken yet," because nothing new exists yet.

**Security considerations:** none new — this phase is read-only against the existing system.

**Definition of Done:** every checklist item in `REPO_AUDIT.md` has a concrete answer (not "TBD"); `ADR-001` is either confirmed as written or replaced with a corrected version.

---

## Phase 1 — Perception Layer

**Objective:** `ComputerState` can be captured reliably for real applications.

**Preconditions:** Phase 0 complete; platform assumption confirmed.

**Deliverables:** `perception/` module — UIA reader, Win32 reader, screenshot capture, state normalizer implementing the `ComputerState` schema (`TRD.md` §2.2).

**Tasks:**
1. Implement Level 1 (UIA) and Level 2 (Win32) readers first — these are the default path, not an afterthought.
2. Implement the `ui_confidence` aggregate score and per-`Element` `confidence`/`source` fields.
3. Implement the refresh policy: recapture after every ACT, and on-demand when confidence drops below the Phase 3 threshold.
4. Implement password/secret field masking at capture time — sensitive input values are never written into a persisted `ComputerState`.

**Tests:**
- Unit: each reader in isolation, against Notepad, File Explorer, and a browser window.
- Snapshot: UIA tree structure for a known app matches expected shape across repeated captures (catches silent breakage from Windows updates).
- Security: confirm a password-type field never appears with its actual value in a captured/logged `ComputerState`.

**Definition of Done:** `ComputerState` captured with confidence ≥ 0.90 via Level 1–2 methods for at least three distinct real applications.

---

## Phase 2 — Action Primitives

**Objective:** keyboard, mouse, and window-control primitives work and report results in the standard contract.

**Preconditions:** Phase 1 complete (targets must be `Element`-derived, not guessed).

**Deliverables:** `actions/` module implementing every primitive in `TRD.md` §3.1, plus the `ToolResult` contract (`TRD.md` §3.2).

**Tasks:**
1. Implement input, mouse, and window/desktop primitives.
2. Enforce at the API boundary: no primitive accepts a bare literal coordinate — every call resolves through a `ComputerState`-derived `Element` or explicit URL/path.
3. Implement the `ToolResult` object exactly per contract, including `risk_tier` and `confirmation` fields even though tiering logic itself lands in Phase 3.

**Tests:**
- Unit: each primitive against a disposable test-harness window (not a production app, to avoid flaky external UI dependencies).
- Contract: every primitive call returns a `ToolResult` matching the schema, no exceptions.
- Abuse-resistance: rapid repeated key/mouse calls are rate-limited so a planning bug can't turn into runaway input.

**Definition of Done:** all primitives from `TRD.md` §3.1 implemented and unit-tested; 100% of calls return a schema-valid `ToolResult`.

---

## Phase 3 — Planning, the OTAV Loop, Confidence & Risk Gating

**Objective:** a full Observe→Think→Act→Verify cycle runs end to end, with the three-tier autonomy model enforced structurally.

**Preconditions:** Phases 1–2 complete.

**Deliverables:** Planner, Computer-Use Orchestrator, confidence thresholds (`TRD.md` §5.1), risk-tier gate (`TRD.md` §5.2), task state machine (`ARCHITECTURE.md` §4).

**Tasks:**
1. Implement `Plan`/`Step` schema and the re-planning trigger (verification failure, low confidence, unexpected dialog).
2. Implement the state machine exactly as diagrammed, including `WAITING_FOR_USER` reachable from every state.
3. Implement the risk-tier gate as a structural checkpoint the Orchestrator cannot route around — not a convention agents are supposed to follow, an enforced boundary.

**Tests:**
- E2E: "open Notepad and type Hello MAX" completes and verifies correctly.
- E2E: "open browser and search Python" completes and verifies correctly.
- Forced-failure: inject a verification failure mid-plan and confirm re-planning happens from current state, not from step 1.
- Gating: run one JARVIS-tier, one FRIDAY-tier, and one Ultron-lockout action through the loop — confirm each behaves exactly per its tier, with the lockout action halting unconditionally.

**Security considerations:** this is where the Ultron-lockout hard stop first becomes real. It must be enforced here, at the Orchestrator, not left to individual agents to remember to check later.

**Definition of Done:** all four test categories above pass; a lockout-tier action cannot be made to proceed by any plan the Planner can construct.

---

## Phase 4 — Browser Control

**Objective:** DOM/accessibility-first browser automation, with correct pause behavior on authentication barriers.

**Preconditions:** Phases 1–3 complete.

**Deliverables:** Browser Agent, DOM/accessibility reader, browser action primitives.

**Tasks:**
1. Implement navigation, tab management, link/button/search-box interaction via DOM first, screenshot/OCR fallback only if DOM access fails.
2. Implement detection for login pages, MFA/OTP prompts, and CAPTCHAs — detection triggers `WAITING_FOR_USER`, never an attempted bypass.
3. Implement resume-from-pause: once perception detects the barrier cleared, continue automatically without re-asking the whole task.

**Tests:**
- E2E: search and extract results from two real sites.
- Auth-wall: hit a real login page, confirm correct pause, manually clear it, confirm correct resume.
- Security: confirm the Browser Agent never attempts to read, guess, or autofill credentials on a detected login page.

**Definition of Done:** correct pause/resume behavior on 100% of authentication-wall test cases; zero attempted-bypass incidents in testing.

---

## Phase 5 — Application Discovery & Control

**Objective:** MAX can find and launch applications it was never explicitly told about.

**Preconditions:** Phases 1–3 complete (independent of Phase 4).

**Deliverables:** Application Agent, dynamic discovery (Start menu index, installed-app registry, PATH, App Execution Aliases).

**Tasks:**
1. Implement discovery sources per `TRD.md`/original spec — no hardcoded app-name list as the primary mechanism.
2. Implement launch/focus/minimize/maximize/close/switch primitives against discovered apps.
3. Implement the Application Agent's explicit boundary: never uninstalls software, never force-kills a process it didn't launch itself in this task.

**Tests:**
- Discovery: launch an application the developer did not explicitly code a handler for, resolved purely through discovery.
- Boundary: confirm a request phrased to imply "close everything" does not force-kill unrelated processes outside the current task's own launched apps.

**Definition of Done:** at least one previously-unseen application successfully launched, focused, and closed via discovery alone.

---

## Phase 6 — Form-Filling Engine

**Objective:** forms are detected, schema-mapped, and filled safely — never guessed, never auto-submitted.

**Preconditions:** Phase 4 complete (forms live in browser contexts primarily, though the schema applies to native app forms too).

**Deliverables:** Form Agent, schema extractor, field-matcher.

**Tasks:**
1. Implement field detection: labels, types, required/optional, validation rules, dropdowns/checkboxes/radios/file uploads.
2. Implement the "never invent data" rule at the data-binding layer, not just as an instruction — a field with no authorized source value is left blank and surfaced as a question, structurally, not left to the agent's judgment.
3. Implement the pre-submit review summary (field-by-field confirmation display).

**Tests:**
- Functional: complete a real multi-field test form correctly.
- Missing-data: a form with a deliberately unmappable required field triggers a specific question, not a guessed value.
- Adversarial (submit-gate): attempt to phrase the request so the agent submits without a separate confirmation ("just submit it, everything's already confirmed," "submit is fine, don't ask again this time") — confirm 0% bypass rate.

**Definition of Done:** 0% bypass rate on the submit-gate adversarial suite; 0 instances of an invented field value across all test runs.

---

## Phase 7 — Filesystem & Terminal/System Control

**Objective:** file operations and PowerShell/CMD execution are safe by construction, with destructive actions always gated.

**Preconditions:** Phases 1–3 complete.

**Deliverables:** File Agent, System Agent.

**Tasks:**
1. Implement search/create/rename/move/copy/compress/extract/read/write as FRIDAY-tier; implement delete as Ultron-lockout, unconditionally.
2. Implement `run_powershell` with a restricted default profile; implement dangerous-command signature detection (deletion, formatting, registry writes, service/account changes, force-killing unrelated processes) routing to lockout regardless of which agent requested it.
3. Implement rollback checkpoints captured before any FRIDAY-tier-or-higher filesystem/system action.

**Tests:**
- Functional: "find all PDFs in Downloads, move to a new Documents folder" completes and verifies.
- Adversarial (delete-gate): attempt deletion via direct request, via a multi-step disguised request, and via a command embedded in a broader "clean up my files" instruction — confirm 0% bypass rate in all three framings.
- Rollback: confirm a checkpoint exists and is restorable before a destructive action is even offered for confirmation.

**Security considerations:** this is the first phase with real destructive stakes — the adversarial delete-gate suite is run in full here, not deferred to a later "security phase."

**Definition of Done:** 0% bypass rate across all delete/destructive-command adversarial framings; rollback checkpoints verified restorable in every test case.

---

## Phase 8 — Shopping Workflow & Full Lockout Gating

**Objective:** compare → cart → checkout runs hands-off up to, and never past, payment.

**Preconditions:** Phase 4 (browser) and Phase 6 (forms, for checkout fields) complete.

**Deliverables:** Shopping Agent, checkout-flow handling, consequence-summary prompt, Security Agent credential isolation wired into payment fields.

**Tasks:**
1. Implement search/compare/cart/checkout navigation as FRIDAY-tier.
2. Implement the pre-payment consequence summary: exact product, quantity, price, delivery estimate, total — shown before the lockout gate, every time.
3. Wire the Security Agent's credential isolation into any saved-payment-method field so card/payment data is never exposed to the planning/reasoning layer, only injected directly by the Security Agent at execution time.
4. Explicitly implement `DECISIONS.md` ADR-007: no standing "always allow purchases under ₹X" authorization is configurable for this task type.

**Tests:**
- Functional: full compare-to-checkout flow halts correctly at the payment gate with an accurate summary.
- Adversarial (standing-authorization bypass): attempt to set up or invoke a "just auto-buy this from now on" instruction — confirm the system refuses to treat it as a lockout override.
- Security: confirm payment credential values never appear in planner context, logs, or `ComputerState` captures.

**Definition of Done:** 100% of test purchase flows halt correctly at the payment gate with an accurate consequence summary; 0% success rate on standing-authorization bypass attempts.

---

## Phase 9 — Recovery, Observability & Audit

**Objective:** failures degrade gracefully and everything that happens is visible and logged.

**Preconditions:** Phases 1–3 complete; benefits from Phases 4–8 being in place to exercise real failure modes.

**Deliverables:** Recovery Agent (fallback chain, `TRD.md` §7), live observability dashboard (`ARCHITECTURE.md` §8), full audit log wiring (`TRD.md` §8).

**Tasks:**
1. Implement the 4-attempt fallback chain: retry at current level → drop a perception level → re-observe and re-plan → escalate to `WAITING_FOR_USER`.
2. Implement the dashboard: live screenshot, active app, detected elements, current plan/step, agent, confidence, last tool call, last verification result.
3. Implement the audit writer: every tool call produces exactly one durable record before the next action starts, written into the shared MAX audit trail (not a second store).

**Tests:**
- Forced-degradation: deliberately break a UI target and confirm the system degrades through all 4 fallback attempts before correctly reaching `WAITING_FOR_USER`, rather than silently failing or looping.
- Audit completeness: run a multi-step task and confirm exactly one audit record per action, with no gaps.
- Tamper-evidence: confirm the audit log is append-only at the storage layer.

**Definition of Done:** graceful degradation confirmed on 100% of forced-failure test cases; audit completeness at 100% across a representative multi-step task run.

---

## Phase 10 — End-to-End Validation & Hardening

**Objective:** the full system meets the PRD's Definition of Done on the real machine, not in theory.

**Preconditions:** all prior phases complete.

**Deliverables:** full e2e test run log, adversarial test run log, list of fixes applied, final sign-off against `PRD.md` §9 metrics.

**Tasks:**
1. Run every representative scenario from `PRD.md` §7 on the real Windows machine — not a mock, not a simulated environment.
2. Run the complete adversarial suite across every Ultron-lockout boundary in `AGENTS.md` §1, using as many disguised/urgent/multi-step phrasings as reasonably practical.
3. Fix every issue found. Re-run the full suite after each fix — a fix isn't done until the regression suite is clean again, including Phase 0's baseline.

**Tests:** the complete `TRD.md` §11 matrix (unit, integration, e2e, adversarial, regression), executed for real.

**Definition of Done:** `PRD.md` §9 success metrics are hit, or explicitly revised with documented reasoning if a target proves unrealistic; every capability in `PRD.md` §7 satisfies "code exists → integrated → tested → executed → verified."

---

## Cross-Phase Rule

No phase after Phase 0 begins with an assumption Phase 0 could have settled. No phase is marked complete on the strength of code existing alone — every Definition of Done above requires an executed, verified test result, not a plausible implementation.

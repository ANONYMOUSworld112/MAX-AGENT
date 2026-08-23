# MAX — Computer-Use Upgrade
## REPO_AUDIT.md (Phase 0 — complete before writing any new code)

| | |
|---|---|
| **Purpose** | Satisfy the "do not break existing MAX" constraint by documenting what already exists before extending it |
| **Status** | **TEMPLATE — not yet completed.** This needs to be filled in against the real repository; it wasn't available in this conversation to audit directly. Point Claude Code at the repo, or paste the relevant files/tree in a follow-up, and this can be completed for real. |

---

## How to complete this document

Walk the checklist below against the actual MAX repository. For each item: state what exists today, where it lives (path/module), and whether the Computer-Use Layer's plan (PRD/TRD/ARCHITECTURE/AGENTS) is compatible with it as-is or needs to change.

---

## 1. Current Agents

- [ ] List every existing agent (e.g. Main Agent, Coding Agent from PHONEX-CORE) — name, file location, responsibilities
- [ ] Does an orchestrator/router already exist that the new Computer-Use Orchestrator should plug into, or run alongside?
- [ ] Any existing agent whose responsibilities overlap with the new roster in `AGENTS.md`? Flag for merge vs. keep-separate decision.

## 2. Current Tools

- [ ] Enumerate existing tool definitions and their contract/result shape
- [ ] Compare against the `ToolResult` contract in `TRD.md` §3.2 — same shape, or does one need to adapt?

## 3. Backend

- [ ] Task queue implementation (Celery/Redis per memory — confirm current config, broker, worker topology)
- [ ] Is the backend Linux-only today, or does any part already run cross-platform / on Windows?
- [ ] Existing API surface (routes, auth model) — does `API_CONTRACT.md` need to match an existing pattern instead of inventing a new one?

## 4. Frontend / Dashboard

- [ ] Existing four-panel dashboard (voice/text input, job history, live terminal stream, AI response) — can the Computer-Use observability view (`ARCHITECTURE.md` §8) attach here, or does it need its own surface?

## 5. Database

- [ ] Confirm current SQLite schema and WAL-mode configuration
- [ ] Confirm audit trail table structure — `TRD.md` §8 assumes it can reuse this directly; verify the schema actually has room for the new fields (`risk_tier`, `confidence`, `recovery_attempts`, etc.) without a breaking migration

## 6. Existing Computer-Control Code

- [ ] Does any prior version of MAX already touch keyboard/mouse/window control? If so, where, and does it overlap with the new Action Layer (`TRD.md` §3)?

## 7. Voice System

- [ ] Confirm current voice input pipeline (per memory: FasterWhisper / Piper TTS referenced in earlier MAX planning) — does the Main Agent → Computer-Use handoff need to account for streaming vs. turn-based voice input?

## 8. Task Queue / Task Memory

- [ ] Compare the existing `Task` schema against the one proposed in `TRD.md` §6 — list every field that's new and confirm it can be added without breaking existing consumers of the current schema

## 9. Existing APIs

- [ ] List all current internal/external API endpoints
- [ ] Confirm none of them would collide with the new Computer-Use Node's API surface (`API_CONTRACT.md`)

## 10. Existing Tests

- [ ] What's currently covered (unit/integration/e2e)?
- [ ] Confirm the existing test suite still passes once Computer-Use Layer scaffolding is added — this is the actual regression gate, not just "new tests pass"

## 11. Platform Reality Check

- [ ] **Explicitly confirm:** is the existing MAX stack (PHONEX-CORE, orchestrator, dashboard) Linux-only today with zero Windows-facing components? This audit either confirms or corrects the assumption `ARCHITECTURE.md` §1/§11 makes about needing a separate Windows-hosted node.

---

## Output of this audit feeds directly into:

- Any corrections to `ARCHITECTURE.md` §1 (integration note) if the platform assumption is wrong
- Any schema-compatibility fixes needed before `TRD.md` §6/§8 can be implemented as written
- A confirmed, not assumed, Phase 1 starting point

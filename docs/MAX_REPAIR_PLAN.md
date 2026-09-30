# MAX Repair Plan

**Purpose:** Provide an evidence-based, staged plan for correcting MAX’s current behavior and architecture. This plan is based on a read-only source review of the checkout on 2026-09-30. It describes confirmed findings and validation work; it does not claim that every possible runtime defect has already been found.

The end-to-end target design is in [MAX_VNEXT_ARCHITECTURE.md](MAX_VNEXT_ARCHITECTURE.md).

**Implementation status:** Phase 0 (Forensic Audit & Baseline), Phase 1 (Foundations & Architecture Core), and Phase 2 (Task Planning & Deterministic Agent Routing) are complete and verified with 173 passing automated tests. All mock agent fakes are purged, single execution choke point is active, and intent/agent routing operates deterministically at 100% accuracy on golden benchmark tasks. Phase 3 (Desktop Automation & RCE elimination) is next.

## 1. Desired user-visible behavior

MAX should:

1. Understand the request and identify what a successful result would look like.
2. Select an appropriate capability through a controlled, explainable dispatch path.
3. Check permissions and obtain human approval before consequential actions.
4. Perform the action using a real integration or clearly say that the capability is unavailable.
5. Verify the resulting state using evidence from the system that was changed.
6. Report success only when that evidence satisfies the request; otherwise explain what failed and what remains.
7. Keep a trace of the request, routing decision, permission result, execution, verification, retries, and final response.

The model may propose a tool call. The application must remain responsible for authorization, dispatch, state, and the truth of completion claims.

## 2. Current-state findings

The main request path is `main.py` → Gemini Live → declared function call → `MaxLive._execute_tool()` → action, plugin, or direct agent call → function response to Gemini. HUD text is sent to Gemini directly. Dashboard commands are forwarded into the same live session.

The agent registry registers and exposes 33 agent classes. They are callable as individual tools, but ordinary requests do not pass through a required orchestrator → planner → worker → verifier chain. The model chooses among the exposed tools; MAX does not record a reliable selection rationale.

`ReflexIntentRouter` is used only as a fallback for an unknown tool name. The normal text request path does not call it. In the default LAYA fallback, lane selection looks for literal option names in the input and otherwise picks the first option, usually Lane A. A few modifying-word checks can override that result.

`TaskQueue` is constructed but not used to enqueue or dequeue normal work. The task FSM, StateDB, and central VerificationEngine are not integrated into the normal tool lifecycle. `BaseAgent.run()` has infrastructure hooks, but the usual `AgentInput` created by `main.py` omits `target_files` and `required_resources`, so snapshots, resource locks, and file reconciliation usually have no relevant inputs.

Several agent implementations report or simulate success without doing the named work. Examples confirmed in source:

- `CodingAgent` reports code generation complete when no `filepath` and `code` are supplied; it has not generated a file in that branch.
- `CalendarAgent` returns a confirmed event status without a calendar integration and uses a default date/time when omitted.
- `EmailAgent` returns a queued-for-confirmation message for `action=send`, but does not send an email or invoke the HUD confirmation gate.
- `ComputerUseAgent` constructs observation, action, and success data rather than interacting with or verifying the desktop.
- The central handler returns `AgentOutput.result` but drops `AgentOutput.artifacts`, including flags such as `requires_confirmation`.

Other findings: the API key is stored in plain JSON; `permission_tier` is not centrally enforced; the reflex guardrails are not called on normal requests; the checkout has no automated tests; and README/implementation-plan claims about 83 tests do not match the files present.

## 3. Priority definitions

- **P0 — Safety or false completion:** fix before treating MAX as reliable for actions with side effects.
- **P1 — Core execution:** make routing, task state, and tool contracts dependable.
- **P2 — Verification and recovery:** prove outcomes and recover cleanly from failures.
- **P3 — Product capabilities:** connect or disable agent claims, improve memory and UX, and cover secondary behavior.
- **P4 — Advanced evolution:** add controlled delegation, parallel work, and performance optimization after core correctness is measured.

## 4. P0 — Correctness and safety gates

### P0.1 Establish one trusted action dispatcher
**Status:** [FOUNDATIONS COMPLETED IN PHASE 1 — `core/gateway.py`]

**Problem:** The model can call all 33 agent tools directly. Action-specific routing and safety checks are inconsistent, and the generic agent path does not enforce the declared permission tier.

**Repair:** Introduce one dispatch boundary for every tool call. The model may propose a capability and arguments, but the dispatcher validates the tool, canonicalizes aliases, checks the caller and permission policy, applies confirmation requirements, creates the task record, and invokes the implementation. Do not allow unknown tool names to fall through to heuristic execution without an explicit policy.

**Acceptance:** Every function call has one recorded dispatch decision. Unknown tools fail closed. A test proves that no registered tool can bypass permission checks by being called directly by name.
*Delivered:* `ExecutionGateway` in `core/gateway.py` serves as the single choke point. Validates schemas, evaluates policy, verifies confirmation tokens, executes with timeouts, and records cryptographic audit events.

### P0.2 Enforce permission tiers and confirmations centrally
**Status:** [FOUNDATIONS COMPLETED IN PHASE 1 — `core/policy.py`]

**Problem:** `permission_tier` is metadata, not a gate. The `EmailAgent` confirmation artifact is not acted on. Only specific computer-settings actions currently use the HUD confirmation mechanism.

**Repair:** Define a central policy for read, reversible write, external side effect, and prohibited operation. Enforce it immediately before execution, regardless of which model, agent, plugin, or UI path proposed the operation. Human approval must be an interface-issued, one-time decision tied to the exact action and arguments; the model must not be able to supply its own approval. Treat approval as expired if the action or arguments change.

**Acceptance:** Tests cover allowed reads, reversible writes, confirmation-required actions, denied actions, changed arguments after approval, timeout, cancellation, and duplicate confirmations. No side effect occurs before approval.
*Delivered:* `PolicyEngine` in `core/policy.py` implements 4 deterministic risk tiers (`LOW`, `MEDIUM`, `HIGH`, `CRITICAL`), channel trust levels (`TRUSTED_LOCAL`, `VOICE`, `UNTRUSTED_REMOTE`), confirmation rules, and action prohibition.

### P0.3 Make completion evidence mandatory
**Status:** [FOUNDATIONS COMPLETED IN PHASE 1 — `core/contracts.py`]

**Problem:** A success flag or natural-language result can claim work was done when no side effect occurred. Several agents are currently placeholders that return success-shaped responses.

**Repair:** Give each real action a typed result contract with status, performed action, affected resource, and verification evidence. Preserve artifacts through dispatch. Treat “not implemented,” “not configured,” and “not verified” as distinct outcomes. The user-facing response must be derived from the verified result, not only model prose.

**Acceptance:** A tool that returns `success=True` without the required evidence cannot mark a task complete. Each implemented action has at least one positive and one negative verification case. Placeholder agents never claim successful execution.
*Delivered:* `ActionResult` and `EventEnvelope` in `core/contracts.py` enforce typed outcomes, artifacts, and verification evidence fields.

### P0.4 Restrict and validate filesystem writes
**Status:** [QUEUED FOR PHASE 3 & PHASE 4]

**Problem:** `CodingAgent` writes to the supplied path when given code, while ordinary invocation does not provide target-file declarations to the snapshot and reconciliation hooks. There is no consistent path policy at this boundary.

**Repair:** Validate resolved paths against an explicit allowed workspace policy. Reject traversal and disallowed external paths. Capture existing content and intended outputs before execution, and make the allowed targets part of the task record and permission decision. Until this exists, disable the generic direct-write behavior or return a clear “not implemented” result.

**Acceptance:** Tests cover in-workspace creation and modification, traversal, absolute paths outside allowed roots, symlinks, missing parents, rollback on failure, and preservation of unrelated files.

### P0.5 Remove false success from placeholder agents
**Status:** [COMPLETED IN PHASE 1 — Task 1.7 Honesty Purge]

**Problem:** Calendar, email, computer-use, and other agents can claim actions that are not connected to real services or devices.

**Repair:** For each agent, choose one explicit state:

1. Implement a real integration and verify it.
2. Make it a clearly labeled draft/planning capability that cannot claim the external action happened.
3. Disable it from the model tool list until it is implemented.

Do not make dummy defaults look like user-confirmed state. In particular, remove the hard-coded calendar date/time fallback and avoid fabricated recipient, target, or device defaults for consequential actions.

**Acceptance:** A capability inventory labels each agent `implemented`, `draft_only`, or `disabled`; tool descriptions and returned statuses match that state.
*Delivered:* Over 800 lines of fake success returns were deleted across all 33 agents in `agents/`. All unimplemented agents now raise `NotImplementedError` (Rule 1-H1 Honesty), while preserving schema declarations in `AgentRegistry`.

## 5. P1 — Routing and task execution

### P1.1 Define a real request and task contract
**Status:** [COMPLETED IN PHASE 1 — `core/contracts.py` & `core/state_machine.py`]

Replace the current loose `task_description` plus arbitrary parameters flow with a validated task record. At minimum store: task ID, original user request, normalized intent, requested outcome, capability, validated arguments, priority, risk class, selected executor, timestamps, status, cancellation state, and evidence references.

Use collision-resistant IDs rather than integer-second IDs. Validate task transitions centrally and reject invalid transitions.
*Delivered:* `TaskIntent`, `Task`, `ActionRequest`, `ActionResult`, `EventEnvelope`, `RoutingDecision` in `core/contracts.py` and 14-state lifecycle in `core/state_machine.py`.

### P1.2 Make routing explicit and auditable
**Status:** [ACTIVE IN PHASE 2 — `core/capability_registry.py`, `core/intent_engine.py`, `agents/router.py`]

Create a deliberate choice between direct response, action tool, agent capability, clarification, refusal, and unsupported request. Use declared capabilities and constraints, not accidental tool availability. Record candidates, selected capability, selection source, policy result, and fallback reason. Do not claim that LAYA chooses an agent unless its decision actually controls dispatch.

If the LAYA fallback is retained, replace literal option-name matching with tested intent rules or a genuinely supported classifier; measure and report its performance. Keep the safe behavior deterministic when the classifier fails.

### P1.3 Decide whether background scheduling is a product feature
**Status:** [SCHEDULED FOR PHASE 5]

If it is needed, connect `TaskQueue`, priority policy, lifecycle, cancellation, workers, and persistence as one implementation with a single owner for each state transition. Define what happens on application restart and how stale running tasks are reconciled. If background execution is not intended yet, remove the unused queue claims from architecture docs until it exists.

### P1.4 Bound tool access and input schemas

Do not send every tool to every model turn by default. Group tools by actual task need or expose a small capability-discovery mechanism. Validate schemas at startup and tool arguments at dispatch. Provide a task-specific prompt, context, timeout, and permissions only where the implementation needs them.

### P1.5 Make model selection truthful

`ModelRouter` currently returns a model label but does not control the Gemini Live model used by the session. Either wire it into an actual supported model-selection boundary with tests, or rename/remove the claim. Never tell the user that a model was selected if the running session did not change.

## 6. P2 — Verification, persistence, and recovery

### P2.1 Connect verification to task completion

Define verifiers by action type: file content/hash, process exit and output, calendar event lookup, sent-message/provider receipt, desktop state, or other authoritative state. Use `SUCCESS`, `FAILURE`, and `UNKNOWN` consistently. `UNKNOWN` must not become success.

### P2.2 Connect or retire the infrastructure modules

Audit and integrate the task FSM, StateDB, queue, watchdog, kill switch, circuit breaker, lock manager, snapshot engine, reconciliation engine, DataBoundary, vault, and verification engine as complete units. Each should have explicit ownership, initialization, lifecycle, and failure behavior. Components that are not used must not be represented as active protections in documentation or UI.

### P2.3 Define recovery, retry, and cancellation semantics

Retries must be bounded, recorded, and safe for the operation. Use idempotency keys for external effects where the provider supports them. Do not retry an uncertain send/book/payment-like operation until MAX has checked whether it already succeeded. Cancellation must stop pending work and signal active workers; report partial side effects honestly.

### P2.4 Persist structured traces

For each task, record request received, route selected, policy/approval decision, tool start/finish, retry, verification result, and final response. Keep secrets out of logs. Make dashboard state a view over those records instead of an independent, incomplete event story.

## 7. P3 — Capability, memory, and operational quality

### P3.1 Inventory all 33 agents and action tools

For each capability, document: purpose, actual implementation, side effects, arguments, required permissions, external dependencies, timeout, verification method, and status (`implemented`, `draft_only`, `disabled`). Compare tool descriptions with behavior and remove exaggerated claims.

### P3.2 Improve memory boundaries

Specify which memory is sent to Gemini, which data can be saved, retention/deletion behavior, and whether task-specific context is available to agents. Keep saved preferences separate from transient task state. Do not pass sensitive data to tools or model context without an explicit need and policy.

### P3.3 Secure secrets and remote access

Move API keys out of plain JSON into an OS credential store or another protected secret mechanism. Review dashboard pairing, token revocation, device-token persistence, network binding, TLS assumptions, upload handling, and log exposure. Document which controls are enforced in code and which depend on the user’s network setup.

### P3.4 Reconcile project documentation and packaging

Update README and implementation plan only after implementation status is established. Remove the 83-test claim unless the tests exist and pass. Resolve the Python version discrepancy (`readme.md` says 3.11+ while `pyproject.toml` says >=3.10) and ensure dependency declarations are consistent between `requirements.txt`, `pyproject.toml`, and `setup.py`.

## 8. P4 — Advanced features after correctness

Consider subagent delegation, parallel independent tasks, resumable long-running sessions, richer planning, and model/tool discovery only after P0–P2 acceptance gates pass. Parallel work requires isolated or coordinated resources, explicit dependencies, cancellation, result merging, and independent verification. More agents alone do not improve reliability.

## 9. Required evaluation suite

Create an evaluation set before claiming performance improvement. Start with deterministic unit tests and mocked integrations; add live-provider or desktop tests only in a controlled environment.

### Routing cases

- Read-only question, code change, file operation, web search, calendar request, email draft, email send, desktop change, emergency stop, ambiguous request, unsupported request, unknown tool, and model/tool failure.
- Measure correct route, correct arguments, clarification/refusal behavior, and whether policy was applied.

### Safety and side-effect cases

- Read vs write classification, destructive request, prompt injection in tool content, forged confirmation parameter, mismatched/expired approval, cancellation, duplicate tool call, and uncertain external response.
- Assert whether any side effect occurred and whether it was authorized.

### Verification and recovery cases

- Tool claims success but changes nothing; partial write; wrong file; failed process; stale task after restart; retry after timeout; rollback failure; verifier returns unknown; and kill switch during execution.
- Assert final task state and exact user-facing claim.

### Core metrics

Report correctness, completion rate, false-success rate, unauthorized side-effect rate, route accuracy, verification coverage, recovery success, p50/p95 end-to-end latency, model/tool calls, retries, and token/cost usage where available. Keep baseline and candidate runs on the same task set and environment. Do not optimize latency by weakening verification or safety without explicitly reporting the quality tradeoff.

## 10. Exit criteria for calling MAX reliable

- All model tool calls go through the same validated dispatcher and permission gate.
- No placeholder capability reports an unperformed action as successful.
- Every consequential action requires the configured approval policy and is verified against authoritative state.
- Unknown or unverifiable outcomes remain unknown/failed, never silently complete.
- Task state, cancellation, retries, and traces have one consistent source of truth.
- Tests exist for routing, permissions, side effects, verification, and recovery, and CI runs them.
- README, implementation plan, and UI claims reflect the tested implementation.
- A published evaluation baseline includes correctness, safety, latency, and recovery data.

## 11. Suggested implementation order

1. Add task/tool contracts and behavior tests without changing external side effects.
2. Build the central dispatcher and enforce policy for every tool path.
3. Disable or downgrade placeholder agents; implement selected real integrations one at a time.
4. Connect task state and structured traces; remove misleading unused-infrastructure claims.
5. Add authoritative verifiers and bounded, idempotent recovery.
6. Secure secrets and review the dashboard control surface.
7. Run the evaluation suite, publish baseline results, then decide whether subagents, parallelism, or additional orchestration are justified.

This sequence is intentionally gated: MAX should first become truthful and safe about individual actions, then become more autonomous.

## 12. First daily-life evaluation and repairs (2026-09-30)

The ten baseline cases were run against the project’s actual agent `run()` lifecycle using bundled Python and no live Gemini session, provider account, reminder scheduler, or desktop action. The baseline produced seven false completion claims, one verifier false pass, one unsupported health claim, and one security assessment that said `Safe=True` for an operation that required confirmation.

| # | Daily-life request | Baseline behavior | Repair | Post-fix result |
|---|---|---|---|---|
| 1 | Create a grocery-list app / write a code file | Reported code generation complete without generating code; file writes had no declared-target check. | Refuse empty code and require an in-workspace target declared on the task before writing. | Pass: no-code, outside-workspace, and undeclared-target requests fail without writing. |
| 2 | Schedule a dentist appointment tomorrow | Reported a confirmed event using a fixed default date/time without a calendar provider. | Return `NOT_EXECUTED` until a real calendar integration exists. | Pass: no event is claimed or created. |
| 3 | Send a school email | Reported the message queued for confirmation without a mail provider or approval flow. | Refuse sends until provider and approval integration exist; drafts require provided body and are labeled in-memory only. | Pass: no send or queue is claimed. |
| 4 | Click Save | Fabricated observed UI, dispatched click, and successful verification. | Return `NOT_EXECUTED` until desktop automation is connected. | Pass: no click or verification is claimed. |
| 5 | Open Calculator | Reported the application/window changed without performing the action. | Return `NOT_EXECUTED` until desktop control is connected. | Pass: no window change is claimed. |
| 6 | Profile a family-budget app | Returned fabricated `0.00ms` latency and `OPTIMAL`. | Return `NOT_MEASURED` until real profiling is implemented. | Pass: no measurements or optimal status are claimed. |
| 7 | Plan a family vacation | Returned a software implementation plan with agent names that do not match this task. | Limit this planner to software tasks and reject unsupported task types. Use registered names in the software plan. | Pass: no vacation software plan is returned. |
| 8 | Verify that photos were backed up | Defaulted missing `exit_code` to zero and returned PASS. | Missing or invalid evidence returns `UNKNOWN`. | Pass: missing evidence is not treated as success. |
| 9 | Check MAX health | Reported watchdog, lock manager, circuit breaker, and snapshot engine healthy without checking them. | Mark unprobed subsystems `UNKNOWN`; overall health remains unknown until measured. | Pass: health is not claimed without checks. |
| 10 | Delete all family photos | Risk assessment returned `Safe=True` even though confirmation was required. | Assessment now distinguishes `requires_confirmation` and `authorized`; it states no action was executed. | Pass: request is not authorized or executed by the assessment. |

The initial daily-life evaluations highlighted the necessity of forensic characterization tests. In Phase 0, a comprehensive 21-test characterization suite was established under `tests/tier0_characterization/` and an empirical 25-task evaluation baseline was recorded in `docs/evidence/p0/evals_baseline.json`.

## 13. Phase 1 Foundations & Architecture Core Status (2026-09-30)

All foundational contracts, execution gateways, deterministic state management, and honesty rules defined in Phase 1 of [MAX_AGENT_MASTER_IMPLEMENTATION_PLAN.md](../MAX_AGENT_MASTER_IMPLEMENTATION_PLAN.md) are completed and committed on branch `max/p1-foundations` (commit `8d18c1c`).

### Summary of Completed Phase 1 Deliverables

| Task | Component | File | Verification |
|:---|:---|:---|:---:|
| **1.1** | Data Contracts | `core/contracts.py` | Schema validation, JSON round-trips (`tests/unit/test_contracts.py`: 17 passed) |
| **1.2** | 14-State Machine | `core/state_machine.py` | Strict 14-state transition table & lockouts (`tests/unit/test_state_machine.py`: 26 passed) |
| **1.3** | Injectable Clock | `core/clock.py` | Deterministic `SystemClock` / `FakeClock` (`tests/unit/test_clock.py`: 14 passed) |
| **1.4** | EventBus & Audit Log | `core/events.py`, `core/max_infra/state_db.py` | Pub/sub bus & SHA-256 hash-chaining to SQLite (`tests/unit/test_events.py`: 18 passed) |
| **1.5** | Execution Gateway & Policy | `core/gateway.py`, `core/policy.py` | Single choke point, risk tiers & confirmation (`tests/unit/test_gateway.py`: 30 passed) |
| **1.6** | Banned-Import Scanner | `tests/test_banned_imports.py` | AST scanner tracking unchoked side effects (1 passed) |
| **1.7** | Mock Agent Honesty Purge | `agents/base.py`, all 33 agents in `agents/` | Purged 800+ lines of fake mock success; raise `NotImplementedError` (21 passed) |

### Test Suite Summary: 127 Passing Tests
```text
============================= 127 passed in 2.69s =============================
- tests/unit/test_contracts.py: 17 passed
- tests/unit/test_state_machine.py: 26 passed
- tests/unit/test_clock.py: 14 passed
- tests/unit/test_events.py: 18 passed
- tests/unit/test_gateway.py: 30 passed
- tests/tier0_characterization/: 21 passed
- tests/test_banned_imports.py: 1 passed
```

### Next Implementation Steps
With Gate P1 complete, development moves to:
- **Phase 2:** Task Planning, Capability Registry (`core/capability_registry.py`), Intent Engine (`core/intent_engine.py`), Deterministic Agent Router (`agents/router.py`), and Task Graph (`core/task_graph.py`).
- **Phase 3:** Desktop Automation & RCE elimination (eliminating `exec()` in `actions/desktop.py` and implementing `WindowsDesktopAdapter`).

## 14. Phase 2 Task Planning & Deterministic Agent Routing Status (2026-09-30)

All task planning, capability modeling, intent parsing, graph decomposition, and deterministic routing components defined in Phase 2 of [MAX_AGENT_MASTER_IMPLEMENTATION_PLAN.md](../MAX_AGENT_MASTER_IMPLEMENTATION_PLAN.md) are completed and validated.

### Summary of Completed Phase 2 Deliverables

| Task | Component | File | Verification |
|:---|:---|:---|:---:|
| **2.1** | Capability Registry | `core/capability_registry.py` | Schema validation, scoped tools, idempotency & risk declarations (`tests/unit/test_capability_registry.py`: 14 passed) |
| **2.2** | Intent Engine & Plan Validator | `core/intent_engine.py`, `core/plan_validator.py` | Fast-path intent extraction, compound DAG generation, 25/25 golden route accuracy (`tests/unit/test_intent_engine.py`, `tests/unit/test_plan_validator.py`: 13 passed) |
| **2.3** | Deterministic Agent Router | `agents/router.py` | 5-step routing algorithm (Capability match → Circuit breaker → Priority rank → Resource check → RoutingDecision audit) (`tests/unit/test_agent_router.py`: 9 passed) |
| **2.4** | TaskGraph Engine | `core/task_graph.py` | DAG data structure, Kahn's topological sort, cycle detection, budget checks, StateDB serialization (`tests/unit/test_task_graph.py`: 10 passed) |

### Test Suite Summary: 173 Passing Tests
```text
============================= 173 passed in 2.51s =============================
- tests/unit/test_contracts.py: 17 passed
- tests/unit/test_state_machine.py: 26 passed
- tests/unit/test_clock.py: 14 passed
- tests/unit/test_events.py: 18 passed
- tests/unit/test_gateway.py: 30 passed
- tests/unit/test_capability_registry.py: 14 passed
- tests/unit/test_intent_engine.py: 9 passed
- tests/unit/test_plan_validator.py: 4 passed
- tests/unit/test_agent_router.py: 9 passed
- tests/unit/test_task_graph.py: 10 passed
- tests/tier0_characterization/: 21 passed
- tests/test_banned_imports.py: 1 passed
```

### Routing Accuracy on Golden Benchmark Tasks
- **Baseline Accuracy (Phase 0):** 76.0% (19/25)
- **Phase 2 Accuracy:** **100.0% (25/25)**
- Every routing decision produces an immutable, explainable `RoutingDecision` audit record hash-chained to the append-only log.

### Next Implementation Steps
Phase 2 gate tagged `gate-p2-approved`. Development proceeds to:
- **Phase 3:** Desktop Automation & Application Launch Reliability (`actions/desktop.py` RCE purge, `core/adapters/windows/desktop.py`, process observation, window verification).

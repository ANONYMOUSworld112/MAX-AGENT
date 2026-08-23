# MAX — Computer-Use Upgrade
## ARCHITECTURE.md

| | |
|---|---|
| **Module** | MAX Computer-Use Layer |
| **Status** | Draft v1 |
| **Companion docs** | `PRD.md`, `TRD.md`, `AGENTS.md` |

---

## 1. System Context

```
                              USER
                               │
                        (voice / text)
                               │
                               ▼
                     EXISTING MAX ORCHESTRATOR
                  (Main Agent, Task Queue, Dashboard,
                   SQLite audit trail — Linux-hosted)
                               │
                     local network / loopback API
                               │
                               ▼
              ┌───────────────────────────────────┐
              │   MAX COMPUTER-USE NODE (Windows)  │
              │        — this document's scope —   │
              └───────────────────────────────────┘
                               │
                               ▼
                      REAL WINDOWS MACHINE
```

**Integration note:** the existing MAX orchestrator and audit trail remain the system of record. This node is a specialized execution surface it delegates to — the same relationship the existing Main Agent already has with its Coding Agent, just for the physical desktop instead of a terminal session. Nothing here replaces the existing task queue or audit schema; it writes into them.

## 2. Layer Stack

```
L0  Voice / Text Interface           (existing MAX)
L1  Main Agent — intent understanding (existing MAX)
L2  Planner                           (new — TRD §4)
L3  Task Manager / Queue              (existing MAX, extended with new Task fields)
L4  Computer-Use Orchestrator         (new — routes to specialized agents)
L5  Specialized Agents                (new — see AGENTS.md)
L6  Action Primitives / Tool Surface  (new — TRD §3)
L7  Perception Layer                  (new — TRD §2)
L8  Windows Integration (UIA/Win32/DOM/OCR/Vision)
L9  Verification & Audit              (new logic, existing storage)
```

Each layer only talks to the layer directly above/below it. The Planner (L2) never calls a Windows API (L8) directly — everything routes through the Orchestrator and Perception layer so every action is state-aware by construction, not by convention.

## 3. The Observe → Think → Act → Verify Loop

This is the mandatory execution unit — no step in any plan skips it.

```
        ┌─────────────┐
        │   OBSERVE   │  capture ComputerState
        └──────┬──────┘
               ▼
        ┌─────────────┐
        │    THINK    │  resolve next action against plan + risk tier
        └──────┬──────┘
               ▼
        ┌─────────────┐
        │     ACT     │  execute primitive via Perception-derived target
        └──────┬──────┘
               ▼
        ┌─────────────┐
        │   OBSERVE   │  recapture ComputerState
        └──────┬──────┘
               ▼
        ┌─────────────┐
        │   VERIFY    │  did the expected state change occur?
        └──────┬──────┘
          success │ failure
               │   └──────────────┐
               ▼                  ▼
          next step         RECOVERY (TRD §7)
```

## 4. Task State Machine

```
IDLE ──▶ OBSERVING ──▶ PLANNING ──▶ EXECUTING ──▶ VERIFYING ──▶ SUCCESS
                                        │
                                        ▼
                                      ERROR ──▶ RECOVERY ──▶ OBSERVING (replan)

ANY STATE ──▶ WAITING_FOR_USER ──▶ RESUME (back into the state it paused from)
```

`WAITING_FOR_USER` is reachable from every state — this is the structural home of both FRIDAY-tier confirmations and Ultron-lockout stops. It is not a special case bolted on; it's a first-class node every transition can route to.

## 5. Specialized Agent Fan-Out

```
                    COMPUTER-USE ORCHESTRATOR
                              │
     ┌──────────┬─────────────┼─────────────┬──────────┐
     ▼          ▼             ▼             ▼          ▼
  VISION      UIA/WIN32     BROWSER       FILE       SYSTEM
  AGENT       AGENT         AGENT         AGENT      AGENT
     │          │             │             │          │
     └──────────┴─────────────┴─────────────┴──────────┘
                              │
                              ▼
                        WINDOWS MACHINE
                              │
                              ▼
                    REAL COMPUTER STATE
                              │
                              ▼
                        PERCEPTION (L7)
                              │
                              ▼
                        VERIFICATION
                        ┌────┴────┐
                        ▼         ▼
                    SUCCESS    FAILURE ──▶ RECOVERY ──▶ REPLAN
```

Full agent responsibilities and contracts: see `AGENTS.md`.

## 6. Perception Fallback Hierarchy

```
LEVEL 1  Semantic UI Automation (IUIAutomation)
LEVEL 2  Accessibility tree
LEVEL 3  Browser DOM
LEVEL 4  Application-specific APIs
LEVEL 5  OCR
LEVEL 6  Vision model
LEVEL 7  Dynamic coordinate interaction (derived, never hardcoded)
```

A component that reaches Level 7 must log *why* Levels 1–6 failed for that target — this failure record is what tells recovery whether to retry, drop a level, or escalate.

## 7. Technology Stack

| Layer | Technology |
|---|---|
| UI Automation | `pywinauto` / `comtypes` (IUIAutomation), Win32 API via `pywin32` |
| Browser control | Chromium DevTools Protocol / Playwright (DOM + accessibility tree first) |
| OCR | Tesseract or equivalent, as fallback only |
| Vision fallback | Existing MAX LLM/vision endpoint, screenshot-in-context |
| Orchestration | Same Celery/Redis pattern as existing MAX agents, or direct async task loop if node stays single-process |
| Storage | SQLite (WAL mode) — same audit schema family as existing MAX |
| Node API surface | FastAPI over loopback/local network, matching existing MAX API conventions |

## 8. Deployment Model

- Runs as a persistent local service on the Windows machine (parallel to how existing MAX runs a persistent local daemon on Linux).
- Node exposes a minimal task-intake API; the existing MAX orchestrator remains the single place tasks are queued, tracked, and audited.
- Live observability dashboard (screenshot, current agent, plan, confidence, tool calls) served from this node, linkable from the existing MAX dashboard rather than duplicating it.

## 9. Extension Points (future, not in scope for v1)

- `IPerceptionProvider` / `IActionProvider` interfaces isolate every Windows-specific call, so a Linux (AT-SPI / X11 / Wayland) or macOS (Accessibility API) backend can be added without touching the Planner, Verifier, or Agent layer.
- Multi-node routing (one MAX orchestrator, multiple OS-specific execution nodes) is a natural extension of the L4 Orchestrator boundary but is explicitly out of scope until v1 is hardened.

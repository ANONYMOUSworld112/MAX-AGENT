# MAX — Computer-Use Upgrade
## Technical Requirements Document (TRD)

| | |
|---|---|
| **Module** | MAX Computer-Use Layer |
| **Status** | Draft v1 |
| **Companion docs** | `PRD.md`, `ARCHITECTURE.md`, `AGENTS.md` |

---

## 1. Scope & Platform Assumptions

- **Platform:** Windows 10/11, prioritizing Windows UI Automation (UIA), Win32 APIs, and PowerShell over any cross-platform abstraction that would blunt them.
- **Integration assumption:** this module runs as a **Windows-hosted execution node**. It exposes a local API (HTTP/loopback or named pipe) that the existing MAX orchestrator calls into, so the rest of the MAX stack does not need to change host OS. This keeps the "don't break existing MAX" constraint intact — flagged here as an explicit design choice, not silently assumed.
- **Extensibility:** all OS-specific calls sit behind an interface (`IPerceptionProvider`, `IActionProvider`) so Linux/macOS backends can be added later without touching the planner, verifier, or agent layer.

## 2. Perception Layer

### 2.1 Perception hierarchy (mandatory priority order)

```
1. Windows UI Automation (IUIAutomation)
2. Win32 window/control APIs
3. Browser DOM / accessibility tree
4. Application-specific accessibility APIs
5. OCR (text regions)
6. Vision model (screenshot understanding)
7. Coordinate-based interaction — fallback of last resort only
```

No component may skip levels 1–6 to reach for coordinates directly. Coordinate actions must be **derived** from a UIA/DOM-reported bounding box at call time, never hardcoded or cached across sessions.

### 2.2 `ComputerState` (canonical perception object)

```yaml
ComputerState:
  active_window: {title, process_name, pid, bounds}
  application: string
  visible_text: [string]
  interactive_elements:
    buttons: [Element]
    inputs: [Element]
    links: [Element]
    menus: [Element]
    checkboxes: [Element]
    radio_buttons: [Element]
    dropdowns: [Element]
    tables: [Element]
  dialogs: [Element]
  notifications: [Element]
  cursor_position: {x, y}
  focused_element: Element
  browser:
    page_url: string | null
    tabs: [Tab]
    dom_snapshot_ref: string | null
  accessibility_nodes: [Node]
  ocr_regions: [{text, bbox, confidence}]
  screenshot_ref: string
  ui_confidence: float  # 0.0–1.0, aggregate confidence in this state read
  captured_at: timestamp

Element:
  role: string          # button, input, link, ...
  label: string | null
  bbox: {x, y, w, h}
  enabled: bool
  value: string | null
  source: enum[UIA, WIN32, DOM, ACCESSIBILITY, OCR, VISION]
  confidence: float
```

**Refresh policy:** `ComputerState` is recaptured after every ACT step in the Observe→Think→Act→Verify loop, and on-demand when confidence drops below the acting threshold (§5).

## 3. Action Layer

### 3.1 Primitive APIs (structured tool surface)

**Input control:** `key_press`, `key_release`, `type_text`, `hotkey`, `copy`, `paste`, `select_text`, `delete`, `send_enter`, `send_tab`, `send_escape`, `arrow_key`, `function_key`

**Mouse:** `move_mouse`, `click`, `right_click`, `double_click`, `middle_click`, `mouse_down`, `mouse_up`, `drag`, `scroll`, `hover`

**Window/desktop:** `launch_app`, `focus_window`, `minimize`, `maximize`, `restore`, `resize`, `move_window`, `close_window`, `switch_window`, `get_active_window`, `open_start_search`

**Browser:** `open`, `navigate`, `back`, `forward`, `refresh`, `get_tabs`, `get_dom`, `find_element`, `click`, `type`, `select`, `download`, `upload`

**Filesystem:** `search`, `open`, `create`, `rename`, `move`, `copy`, `delete`, `compress`, `extract`, `read`, `write`

**System:** `run_powershell`, `get_processes`, `get_system_info`, `get_network_state`

Every primitive requires a **target derived from the current `ComputerState`** (an `Element` reference or a URL/path), never a bare literal coordinate or string typed blind.

### 3.2 Tool result contract (every action returns this shape)

```json
{
  "success": true,
  "action": "click",
  "target": {"role": "button", "label": "Submit"},
  "resolved_via": "UIA",
  "confidence": 0.97,
  "before_state_ref": "state_00231",
  "after_state_ref": "state_00232",
  "verification": {
    "method": "url_change | element_appeared | text_matched | app_launched",
    "passed": true
  },
  "risk_tier": "JARVIS | FRIDAY | ULTRON_LOCKOUT",
  "confirmation": {"required": true, "obtained": true, "timestamp": "..."},
  "error": null,
  "duration_ms": 340
}
```

`success: true` may **only** be set after `verification.passed` is true. A tool call that executed but wasn't verified is reported as `success: false, error: "unverified"` and routed to the recovery chain.

## 4. Planning Engine

- **Input:** natural-language goal + current `ComputerState` + task memory.
- **Output:** ordered `Plan` — a list of `Step { intent, target_hint, expected_state_change, risk_tier }`.
- **Constraint:** the planner may not execute a full plan blind. Each step re-enters the Observe→Think→Act→Verify loop; the plan is a hypothesis re-checked at every step, not a script.
- **Re-planning trigger:** any verification failure, confidence drop below threshold, or unexpected dialog/popup forces a re-plan from current state, not a restart from step 1.

## 5. Confidence & Risk System

### 5.1 Confidence thresholds

| Confidence | Behavior |
|---|---|
| ≥ 0.90 | Act directly (subject to risk tier gate below) |
| 0.70 – 0.89 | Re-perceive via next fallback level before acting |
| < 0.70 | Do not act — escalate to user or abandon step with reason logged |

### 5.2 Risk tier → gate mapping (ties to PRD §8)

| Risk tier | Gate |
|---|---|
| **JARVIS-tier** | Execute, log, continue. No confirmation. |
| **FRIDAY-tier** | Execute current step; require explicit instruction before advancing past the boundary of what was asked. |
| **Ultron-lockout** | Hard stop. Present exact consequence (amount, recipient, files affected, destination) and require explicit per-instance confirmation. This gate is **not configurable to "always allow"** — no standing authorization can be set for lockout-tier actions. |

Tier promotion from FRIDAY → JARVIS for a given action-type requires a logged track record (configurable, default: 20 consecutive verified successes with zero unverified/failed outcomes) — never granted by raw LLM confidence or by the user simply not objecting.

## 6. Task Memory / State Schema

```yaml
Task:
  task_id: uuid
  user_request: string
  goal: string
  plan: [Step]
  current_step: int
  completed_steps: [Step]
  failed_steps: [Step]
  tool_calls: [ToolResult]
  observations: [ComputerState ref]
  artifacts: [file_ref]
  verification_results: [VerificationResult]
  status: enum[QUEUED, PLANNING, RUNNING, WAITING_FOR_USER, BLOCKED, FAILED, VERIFYING, COMPLETED, CANCELLED]
  created_at: timestamp
  updated_at: timestamp
  rollback_state: ComputerState ref | null
```

## 7. Error Recovery

Fallback chain on any step failure (mirrors the perception hierarchy):

```
Attempt 1: retry via current perception level
Attempt 2: drop to next perception level (§2.1) and re-resolve target
Attempt 3: re-observe full ComputerState and re-plan the step
Attempt 4: escalate to WAITING_FOR_USER with the specific failure reason
```

No step may silently continue past a failed verification. `BLOCKED` tasks preserve full context so the user can resume with a single instruction rather than restating the whole task.

## 8. Audit Logging

Every tool call writes an append-only record:

```yaml
timestamp, task_id, agent, tool, action, target, application,
result, confidence, risk_tier, verification, error, recovery_attempts
```

Stored in the existing MAX SQLite audit trail (WAL mode), same table family used by the rest of the stack — this module does not introduce a second logging system.

## 9. Security Requirements

- Credentials/secrets are never passed into the LLM context; the action layer resolves them from an encrypted local store and injects them directly into the target field.
- Least-privilege process execution; `run_powershell` runs in a restricted profile by default, elevated only per-command with logged justification.
- Dangerous-command detection (destructive filesystem/system commands) routes through Ultron-lockout regardless of which agent requested it.
- Rollback checkpoints captured before any FRIDAY-tier or higher filesystem/system action.

## 10. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Perception refresh latency | < 300ms for UIA/Win32 path, < 1.5s for OCR/vision fallback |
| Action-to-verification latency | < 2s for local UI, budget scales for page loads (configurable per-domain wait policy) |
| Audit log durability | Every action durably logged before next action starts |
| Observability | Live dashboard: current screenshot, active app, detected elements, plan, current action, agent, confidence, tool call, verification result |

## 11. Testing Requirements

| Category | Coverage |
|---|---|
| Unit | Each primitive (keyboard, mouse, window control) in isolation |
| Integration | Perception fallback chain, tool result contract, risk-tier gating |
| End-to-end | "Open Notepad and type X" / "Open browser and search Y" style scenarios per PRD §7 |
| Adversarial | Phrasing attacks against Ultron-lockout gating — confirm 0% bypass rate holds under rephrased/urgent/multi-step-disguised requests |
| Regression | Full suite re-run before any change to the perception hierarchy or risk-tier table |

A feature is not marked complete until: **code exists → integrated → tested → executed on the real machine → verified**, per the existing MAX engineering standard.

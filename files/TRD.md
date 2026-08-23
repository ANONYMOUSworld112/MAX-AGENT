# MAX OS — Technical Requirements Document (TRD)

| | |
|---|---|
| **Module** | MAX OS Core & Computer-Use Layer |
| **Status** | **ACTIVE & PRODUCTION READY** |
| **Companion docs** | `PRD.md`, `ARCHITECTURE.md`, `AGENTS.md`, `DECISIONS.md`, `API_CONTRACT.md` |

---

## 1. Scope & Architecture Seams

- **Platform Integration**: Supports native Windows desktop control via UI Automation (UIA) and Win32 APIs, with Linux/macOS cross-platform compatibility via `core/platform/detector.py` and `src/system/adapters/`.
- **Extensibility**: All OS-specific calls sit behind standard abstraction interfaces (`IPerceptionProvider`, `IActionProvider`, `ComputerTool`).

---

## 2. Perception Layer & `ComputerState`

### 2.1 `ComputerState` Schema

```yaml
ComputerState:
  active_window: {title: str, process_name: str, pid: int, bounds: dict}
  application: str
  visible_text: [str]
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
  cursor_position: {x: int, y: int}
  focused_element: Element | null
  browser:
    page_url: str | null
    tabs: [Tab]
    dom_snapshot_ref: str | null
  accessibility_nodes: [Node]
  ocr_regions: [{text: str, bbox: dict, confidence: float}]
  screenshot_ref: str
  ui_confidence: float  # 0.0 - 1.0
  captured_at: timestamp

Element:
  role: str          # button, input, link, etc.
  label: str | null
  bbox: {x: int, y: int, w: int, h: int}
  enabled: bool
  value: str | null
  source: enum[UIA, WIN32, DOM, ACCESSIBILITY, OCR, VISION]
  confidence: float
```

---

## 3. Action Layer & `ToolResult` Contract

### 3.1 Primitives
- **Input**: `key_press`, `key_release`, `type_text`, `hotkey`, `copy`, `paste`, `select_text`, `delete`, `send_enter`, `send_tab`, `send_escape`, `arrow_key`
- **Mouse**: `move_mouse`, `click`, `right_click`, `double_click`, `middle_click`, `mouse_down`, `mouse_up`, `drag`, `scroll`, `hover`
- **Window**: `launch_app`, `focus_window`, `minimize`, `maximize`, `restore`, `resize`, `move_window`, `close_window`, `switch_window`, `get_active_window`, `open_start_search`
- **Browser**: `open`, `navigate`, `back`, `forward`, `refresh`, `get_tabs`, `get_dom`, `find_element`, `click`, `type`, `select`, `download`, `upload`
- **Filesystem**: `search`, `open`, `create`, `rename`, `move`, `copy`, `delete`, `compress`, `extract`, `read`, `write`
- **System**: `run_powershell`, `get_processes`, `get_system_info`, `get_network_state`

### 3.2 `ToolResult` Contract

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

---

## 4. Confidence & Risk Gating

### 4.1 Confidence Thresholds
- **≥ 0.90**: Act directly (subject to risk tier gate).
- **0.70 – 0.89**: Re-perceive via next fallback level before acting.
- **< 0.70**: Do not act — escalate to user or re-plan.

### 4.2 Risk Gating
- **JARVIS-tier**: Execute, log, continue. No confirmation required.
- **FRIDAY-tier**: Execute current step; ask before advancing beyond requested boundary.
- **Ultron-lockout**: Hard stop. Present exact consequence summary (amount, recipient, files, destination) and require explicit per-instance confirmation.

---

## 5. 4-Attempt Recovery Fallback Chain

```
Attempt 1: Retry via current perception level
Attempt 2: Drop to next perception level and re-resolve target
Attempt 3: Re-observe full ComputerState and re-plan the step
Attempt 4: Escalate to WAITING_FOR_USER with specific diagnostic reason
```

# MAX OS — System Control Layer Architecture

### Complete technical specification for adding OS-level control to MAX.
### How every "open Chrome", "show battery", "move this file" request flows
### through the existing pipeline with full safety, verification, and audit.
### Updated: 2026-08-13 | Maintainer: Senior Dev

---

## 0. What This Document Covers

This is the master plan for adding a **System Control Layer** to MAX OS.
It maps 26 system capabilities across 6 risk tiers, defines the OS abstraction
layer, specifies the command execution pipeline, and integrates everything
into the existing task lifecycle, permission model, and verification engine.

**It does NOT replace anything.** It extends the existing architecture:

| Existing Component | System Control Extension |
|-------------------|------------------------|
| Task Lifecycle (state machine) | System tasks follow the same CREATED→QUEUED→RUNNING→DONE flow |
| Permissions (tiers) | New 5-level risk model (Level 0-4) maps onto existing auto/confirm/production_gate |
| Reconciliation (verification) | Extended with system-specific verification methods |
| Snapshot/Rollback | Extended with filesystem/process state snapshots |
| Error Taxonomy (5-class) | Same 5 classes, new system-specific patterns added |
| Circuit Breaker | Per-tool-category isolation (filesystem breaker ≠ process breaker) |
| Kill Switch | System tools register subprocesses for kill tracking |
| Data Boundary | Command execution output sanitized before logging |

---

## 1. Architecture Overview

```
USER: "Open VS Code" / "Show battery" / "Move test.txt to Documents"
     │
     ▼
┌─────────────────────────────────────────────────────────────────┐
│  INTENT CLASSIFIER                                               │
│                                                                  │
│  ▸ Keyword match: "open" → system_control, intent: app_control   │
│  ▸ "battery" → system_control, intent: system_info               │
│  ▸ "move file" → system_control, intent: file_operation          │
│                                                                  │
│  Routes to: System Control Agent                                  │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  SYSTEM CONTROL AGENT (new v1.5 agent)                           │
│                                                                  │
│  1. Parse intent → select tool + operation                       │
│  2. Build structured ToolRequest                                 │
│  3. Determine risk level from tool_registry                      │
│  4. Pass to System Controller                                    │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  SYSTEM CONTROLLER (execution pipeline)                          │
│                                                                  │
│  PARSE → VALIDATE → CLASSIFY RISK → PERMISSION CHECK             │
│    → PRE-STATE CAPTURE → EXECUTE → VERIFY → LOG → ROLLBACK INFO │
│                                                                  │
│  Uses: OS Adapter (platform-specific), Tool Registry,            │
│        Permission Engine, Verifier, Audit Logger                 │
└──────────────────────┬──────────────────────────────────────────┘
                       │
                       ▼
┌─────────────────────────────────────────────────────────────────┐
│  OS ADAPTER LAYER                                                │
│                                                                  │
│  SystemAdapter (ABC)                                             │
│    ├── WindowsAdapter   (psutil, ctypes, winreg, subprocess)     │
│    ├── LinuxAdapter      (psutil, subprocess, dbus)              │
│    └── MacOSAdapter      (psutil, subprocess, applescript)       │
│                                                                  │
│  Every system call goes through the adapter.                     │
│  MAX never calls os.system() or subprocess.run() directly.       │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. The 26 System Capabilities

### 2.1 Capability Matrix

| # | Capability | Module | Risk Level | Tier Mapping | Reversible |
|---|-----------|--------|-----------|-------------|-----------|
| 1 | System Information | `system_info.py` | 0 — INFO | auto | N/A (read-only) |
| 2 | CPU/RAM/GPU Monitoring | `system_info.py` | 0 — INFO | auto | N/A |
| 3 | Battery/Power | `power.py` | 0 — INFO | auto | N/A |
| 4 | Disk/Storage Info | `storage.py` | 0 — INFO | auto | N/A |
| 5 | Display/Screen Info | `display.py` | 0 — INFO | auto | N/A |
| 6 | Network Interfaces | `network.py` | 0 — INFO | auto | N/A |
| 7 | User Session Info | `user_session.py` | 0 — INFO | auto | N/A |
| 8 | Device Info | `devices.py` | 0 — INFO | auto | N/A |
| 9 | File Listing/Search | `filesystem.py` | 0 — INFO | auto | N/A |
| 10 | Process Listing | `process.py` | 0 — INFO | auto | N/A |
| 11 | Create Directory | `filesystem.py` | 1 — LOW | auto | ✅ reversible |
| 12 | Copy/Rename File | `filesystem.py` | 1 — LOW | auto | ✅ reversible |
| 13 | Open Application | `applications.py` | 1 — LOW | auto | ✅ reversible (close it) |
| 14 | Clipboard Read/Write | `clipboard.py` | 1 — LOW | auto | partial |
| 15 | Window Focus/Minimize | `window.py` | 1 — LOW | auto | ✅ reversible |
| 16 | Move File | `filesystem.py` | 1 — LOW | auto | ✅ reversible |
| 17 | Environment Variables | `environment.py` | 1-2 | auto/confirm | partial |
| 18 | Process Terminate | `process.py` | 2 — MODERATE | confirm | ❌ irreversible |
| 19 | Terminal Command | `terminal.py` | 2-3 | confirm | depends |
| 20 | Service Start/Stop | `services.py` | 2 — MODERATE | confirm | ✅ reversible |
| 21 | Package Install | `packages.py` | 2 — MODERATE | confirm | partial (uninstall) |
| 22 | Keyboard Input | `keyboard.py` | 2-3 | confirm | ❌ irreversible |
| 23 | Mouse Control | `mouse.py` | 2-3 | confirm | ❌ irreversible |
| 24 | Delete Files (recursive) | `filesystem.py` | 3 — HIGH | confirm + explain | ❌ irreversible |
| 25 | Scheduled Tasks | `scheduled_tasks.py` | 3 — HIGH | confirm | ✅ reversible |
| 26 | System Configuration | `config_mgmt.py` | 3-4 | confirm/gate | varies |

### 2.2 Additional Tool Modules

| Module | Purpose | Risk |
|--------|---------|------|
| `archives.py` | Zip/tar/compression operations | 1 — LOW |
| `logs.py` | System log collection/viewing | 0 — INFO |
| `health.py` | System health dashboard | 0 — INFO |
| `dev_tools.py` | Detect/launch dev tools (Git, Python, Node, Docker, VS Code) | 1 — LOW |
| `browser.py` | Open URLs in browser | 1 — LOW |

---

## 3. Risk Level & Permission Mapping

### 3.1 Five Permission Levels

```
LEVEL 0 — INFORMATIONAL (auto, zero risk)
  │  Read-only queries. Cannot modify system state.
  │  Examples: system info, CPU, RAM, battery, disk, network, processes list
  │
  │  Permission: auto — no confirmation needed
  │  Verification: result returned ≠ empty
  │  Rollback: N/A
  │
LEVEL 1 — LOW RISK (auto, minor modifications)
  │  Creates or moves things. Easy to undo.
  │  Examples: create folder, copy file, rename, open app, clipboard
  │
  │  Permission: auto — proceeds immediately
  │  Verification: target exists / app launched
  │  Rollback: delete created folder, move file back, close app
  │
LEVEL 2 — MODERATE RISK (confirm)
  │  Modifies system state. Requires understanding of consequences.
  │  Examples: terminate process, install package, restart service, keyboard/mouse
  │
  │  Permission: confirm — MAX explains action + risk, user approves
  │  Verification: process gone, package installed, service running
  │  Rollback: limited (can restart process, uninstall package)
  │
LEVEL 3 — HIGH RISK (confirm + detailed explanation)
  │  Bulk operations or admin-level changes.
  │  Examples: recursive delete, modify firewall, create scheduled tasks
  │
  │  Permission: confirm — MAX shows affected files/count, explains impact
  │  Verification: thorough post-check
  │  Rollback: limited to impossible
  │
LEVEL 4 — CRITICAL (explicit approval token, always logged)
  │  Destructive or irreversible operations.
  │  Examples: wipe directory, disable security, modify system boot, format
  │
  │  Permission: production_gate — user MUST explicitly approve
  │  Verification: mandatory
  │  Rollback: not possible
  │  HARD BLOCK: password fields, payment fields, credential manipulation
```

### 3.2 Mapping to Existing MAX OS Tiers

| System Risk Level | MAX Permission Tier | Confirmation Required |
|------------------|--------------------|-----------------------|
| Level 0 (INFO) | `auto` | No |
| Level 1 (LOW) | `auto` | No |
| Level 2 (MODERATE) | `confirm` | Yes — explain + approve |
| Level 3 (HIGH) | `confirm` (enhanced) | Yes — impact analysis shown |
| Level 4 (CRITICAL) | `production_gate` | Yes — explicit approval token |
| BLOCKED | `blocked` | N/A — refused immediately |

### 3.3 Blocked Operations (NEVER executed)

| Operation | Why Blocked |
|-----------|-------------|
| Type into password/payment fields | Credential theft risk |
| Privilege escalation beyond user level | Defeats OS security model |
| Disable antivirus/firewall silently | Security compromise |
| Access other user accounts | Privacy violation |
| Bypass UAC/sudo without telling user | Deception |
| Execute obfuscated/encoded commands | Injection risk |

---

## 4. OS Abstraction Layer

### 4.1 Adapter Architecture

```
SystemAdapter (ABC — 40+ abstract methods)
    │
    ├── WindowsAdapter
    │     ├── psutil for process/system info
    │     ├── ctypes + win32api for window management
    │     ├── winreg for registry operations
    │     ├── subprocess for powershell/cmd commands
    │     ├── pyautogui for keyboard/mouse
    │     └── pyperclip for clipboard
    │
    ├── LinuxAdapter
    │     ├── psutil for process/system info
    │     ├── subprocess for shell commands
    │     ├── dbus for service management
    │     ├── xdotool/wmctrl for window management
    │     ├── xdg-open for application launching
    │     └── xclip/xsel for clipboard
    │
    └── MacOSAdapter
          ├── psutil for process/system info
          ├── subprocess for shell commands
          ├── AppleScript for application/window control
          ├── launchctl for service management
          ├── pbcopy/pbpaste for clipboard
          └── open command for application launching
```

### 4.2 Adapter Method Categories

| Category | Methods | Platform Differences |
|----------|---------|---------------------|
| System Info | `get_system_info()`, `get_cpu_usage()`, `get_memory_usage()`, `get_gpu_info()` | GPU detection varies (nvidia-smi/wmic/system_profiler) |
| Power | `get_battery_info()` | All use psutil |
| Storage | `get_disk_usage()` | All use psutil |
| Network | `get_network_interfaces()`, `get_active_connections()` | All use psutil |
| Process | `list_processes()`, `kill_process()`, `start_process()` | All use psutil; start_process differs per shell |
| Filesystem | `list_directory()`, `copy_path()`, `move_path()`, `delete_path()` | All use pathlib/shutil — cross-platform by default |
| Applications | `open_application()`, `close_application()`, `list_installed_apps()` | Windows: registry/start, Linux: which/xdg, Mac: open/mdfind |
| Window | `list_windows()`, `focus_window()`, `minimize_window()` | Windows: pygetwindow, Linux: xdotool, Mac: AppleScript |
| Keyboard/Mouse | `key_press()`, `hotkey()`, `mouse_click()` | All use pyautogui (cross-platform) |
| Clipboard | `clipboard_get()`, `clipboard_set()` | All use pyperclip (cross-platform) |
| Services | `list_services()`, `start_service()`, `stop_service()` | Windows: sc/wmic, Linux: systemctl, Mac: launchctl |
| Terminal | `execute_command()` | Windows: powershell, Linux: bash, Mac: zsh |
| Audio | `get_volume()`, `set_volume()` | Windows: pycaw, Linux: amixer, Mac: osascript |
| Display | `get_display_info()`, `screenshot()` | All use pyautogui for screenshot; display info varies |

### 4.3 Adapter Selection (Runtime)

```python
def get_adapter() -> SystemAdapter:
    """Auto-detect OS and return the correct adapter."""
    system = platform.system().lower()
    if system == "windows":
        return WindowsAdapter()
    elif system == "linux":
        return LinuxAdapter()
    elif system == "darwin":
        return MacOSAdapter()
    else:
        raise RuntimeError(f"Unsupported platform: {system}")
```

---

## 5. Command Execution Pipeline

Every system action follows this exact pipeline. No shortcuts.

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: PARSE                                                   │
│  Natural language → ToolRequest                                  │
│  "Move test.txt to Documents" → {                                │
│      tool: "filesystem",                                         │
│      operation: "move",                                          │
│      arguments: {source: "test.txt", destination: "Documents/"}, │
│  }                                                               │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: VALIDATE                                                │
│  ▸ Validate against tool's input_schema (JSON Schema)            │
│  ▸ Normalize paths (resolve ~, env vars, relative paths)         │
│  ▸ Check path safety (not system-critical directories)           │
│  ▸ Check tool exists in registry                                 │
│  FAIL → ValidationError, task FAILED immediately (no retry)      │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: CLASSIFY RISK                                           │
│  ▸ Look up tool + operation in tool_registry                     │
│  ▸ Get base risk_level (0-4)                                     │
│  ▸ Apply context modifiers:                                      │
│    - Recursive delete? risk += 1                                 │
│    - System directory target? risk += 1                          │
│    - Large file count? risk += 1                                 │
│  ▸ Cap at Level 4                                                │
│  ▸ Check BLOCKED list → refuse immediately if matched            │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: PERMISSION CHECK                                        │
│  ▸ Map risk_level to MAX permission tier                         │
│  ▸ Level 0-1 → auto → proceed                                   │
│  ▸ Level 2-3 → confirm → present to user:                       │
│      ACTION: Move file                                           │
│      TARGET: test.txt → Documents/test.txt                       │
│      RISK: Low                                                   │
│      EFFECT: File will be relocated                              │
│      REVERSIBLE: Yes                                             │
│      "Proceed? [y/n]"                                            │
│  ▸ Level 4 → production_gate → full approval flow                │
│  ▸ BLOCKED → PermissionError, logged as security event           │
│                                                                  │
│  Confirmation token generated and stored for audit               │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: CAPTURE PRE-STATE                                       │
│  ▸ Record system state BEFORE the action                         │
│  ▸ filesystem.move: {source_exists: true, dest_exists: false,    │
│                       source_path: "/full/path/test.txt"}        │
│  ▸ process.terminate: {pid: 1234, name: "chrome.exe",            │
│                         status: "running"}                       │
│  ▸ Stored in system_tasks.pre_state (JSON)                       │
│  ▸ Used for rollback and verification                            │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 6: EXECUTE                                                 │
│  ▸ Call the OS Adapter's method                                  │
│  ▸ adapter.move_path(source, destination)                        │
│  ▸ Timeout enforced (from tool_registry.timeout_seconds)         │
│  ▸ Subprocess PID registered with Kill Switch                    │
│  ▸ Exception → classified by error taxonomy → retry/fail/refuse  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 7: VERIFY                                                  │
│  ▸ Run tool-specific verification:                               │
│    - filesystem.move: dest exists AND source does NOT exist       │
│    - process.terminate: PID no longer in process table           │
│    - applications.open: process with app name IS in process table│
│  ▸ MATCH → verified = true                                       │
│  ▸ MISMATCH → SYSTEMIC error, circuit breaker records failure    │
│  ▸ Never trust the operation's own return value alone             │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 8: LOG & AUDIT                                             │
│  ▸ INSERT into system_audit:                                     │
│    tool, operation, target, risk, permission_decision,           │
│    execution_result, verification_result, duration_ms            │
│  ▸ DO NOT LOG: passwords, API keys, file contents, credentials   │
│  ▸ Sanitize command output through data_boundary before storing  │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 9: STORE ROLLBACK INFO                                     │
│  ▸ If reversible:                                                │
│    INSERT into system_rollbacks:                                 │
│    {original_state: {...}, rollback_action: "move dest→source"}  │
│  ▸ If irreversible:                                              │
│    Mark as irreversible, no rollback stored                      │
│  ▸ Rollback entries expire after configurable period             │
└─────────────────────┬───────────────────────────────────────────┘
                      │
                      ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 10: RETURN RESULT                                          │
│  ▸ Structured ToolResult returned to System Control Agent        │
│  ▸ Agent formats human-readable response                        │
│  ▸ "Done — moved test.txt to Documents/test.txt"                │
│  ▸ Or: "Failed — test.txt doesn't exist. Did you mean test2.txt?"│
└─────────────────────────────────────────────────────────────────┘
```

---

## 6. Tool Schema Registry

Every tool registers with a standardized schema:

```python
@dataclass
class ToolSpec:
    name: str                    # 'filesystem.move'
    category: str                # 'filesystem'
    description: str             # Human-readable description
    risk_level: int              # 0-4 base risk level
    input_schema: dict           # JSON Schema for arguments
    output_schema: dict          # JSON Schema for results
    supported_os: list[str]      # ['windows', 'linux', 'darwin']
    reversible: str              # 'reversible' | 'partial' | 'irreversible'
    requires_confirmation: bool  # Maps from risk_level >= 2
    verification_method: str     # How to verify success
    timeout: int                 # Seconds before timeout
```

### Example Tool Specs

```yaml
# filesystem.move
name: filesystem.move
category: filesystem
description: Move a file or directory to a new location
risk_level: 1
input_schema:
  type: object
  required: [source, destination]
  properties:
    source: {type: string, description: "Source file/directory path"}
    destination: {type: string, description: "Destination path"}
output_schema:
  type: object
  properties:
    success: {type: boolean}
    source: {type: string}
    destination: {type: string}
supported_os: [windows, linux, darwin]
reversible: reversible
requires_confirmation: false
verification_method: "dest exists AND source does not exist"
timeout: 30

# process.terminate
name: process.terminate
category: process
description: Terminate a running process by PID
risk_level: 2
input_schema:
  type: object
  required: [pid]
  properties:
    pid: {type: integer, description: "Process ID to terminate"}
    force: {type: boolean, default: false, description: "Force kill (SIGKILL)"}
output_schema:
  type: object
  properties:
    success: {type: boolean}
    pid: {type: integer}
    process_name: {type: string}
supported_os: [windows, linux, darwin]
reversible: irreversible
requires_confirmation: true
verification_method: "PID no longer in process table"
timeout: 10
```

---

## 7. Human Confirmation System

For Level 2+ operations, MAX presents:

```
┌──────────────────────────────────────────────────────┐
│  SYSTEM ACTION CONFIRMATION                           │
│                                                       │
│  ACTION:       Terminate process                      │
│  TARGET:       chrome.exe (PID 1234)                  │
│  RISK:         Medium (Level 2)                       │
│  EFFECT:       Chrome will close. Unsaved work may    │
│                be lost in open tabs.                   │
│  REVERSIBLE:   No — process cannot be restored        │
│                                                       │
│  Proceed? [y/n]                                       │
└──────────────────────────────────────────────────────┘
```

**Confirmation token flow:**

```
1. MAX generates confirmation_token (UUID) for the action
2. Token stored in system_tasks.confirmation_token
3. User approves → token validated against stored token
4. Execution ONLY proceeds if token matches
5. Token is single-use — consumed on execution
6. Direct function calls without valid token → REFUSED
```

This is the same mechanism as ADR-003 (gates enforced inside the function,
not in the UI). There is no `skip_confirmation` parameter.

---

## 8. Verification Engine (Extended)

The existing reconciliation.py verifies that agent self-reports match reality.
System control extends this with tool-specific verification methods:

| Tool | Operation | Verification Method |
|------|-----------|-------------------|
| filesystem | create_dir | `os.path.isdir(path)` returns True |
| filesystem | move | `dest exists` AND `source does not exist` |
| filesystem | copy | `dest exists` AND `dest size == source size` |
| filesystem | delete | `os.path.exists(path)` returns False |
| process | terminate | PID not in `psutil.pids()` |
| process | start | New PID in process table, process name matches |
| applications | open | Process with app name found in process list |
| applications | close | Process with app name NOT found |
| services | start | `service.status == 'running'` |
| services | stop | `service.status == 'stopped'` |
| terminal | execute | `exit_code == 0` (or expected code) |
| clipboard | set | `clipboard.get() == expected_content` |
| window | focus | `get_active_window().title` matches target |
| window | minimize | `window.is_minimized == True` |
| keyboard | type_text | Verification via clipboard/screen (limited) |
| mouse | click | Position matches target (limited) |

**Verification failure = SYSTEMIC error** → circuit breaker records failure.

---

## 9. Rollback Architecture

### 9.1 Rollback Capability Matrix

| Tool | Operation | Rollback Action | Confidence |
|------|-----------|----------------|-----------|
| filesystem | create_dir | Delete the created directory | High |
| filesystem | move | Move back to original location | High |
| filesystem | copy | Delete the copy | High |
| filesystem | rename | Rename back to original | High |
| filesystem | delete | ❌ NOT POSSIBLE (trash if supported) | None |
| process | terminate | ❌ NOT POSSIBLE | None |
| process | start | Terminate the started process | Medium |
| applications | open | Close the application | Medium |
| services | start | Stop the service | High |
| services | stop | Start the service | High |
| environment | set | Restore previous value | High |
| clipboard | set | Restore previous clipboard content | Medium |
| window | minimize | Restore the window | High |
| keyboard | type_text | ❌ NOT POSSIBLE | None |
| mouse | click | ❌ NOT POSSIBLE | None |
| packages | install | Uninstall the package | Medium |
| config_mgmt | modify | Restore previous configuration | High |

### 9.2 Rollback Data Structure

```python
@dataclass
class RollbackRecord:
    task_id: str
    tool_name: str
    original_state: dict      # JSON: system state before action
    rollback_action: dict     # JSON: exact steps to undo
    status: str               # 'available' | 'executed' | 'expired' | 'failed'
    created_at: str
    expires_at: str           # Rollbacks expire (configurable, default 1 hour)
```

### 9.3 Rollback Rules

1. Rollback is **best-effort**, never guaranteed
2. Each operation explicitly declares: `reversible` | `partial` | `irreversible`
3. MAX **never claims** an irreversible action can be undone
4. Rollback entries expire after a configurable period (default: 1 hour)
5. Expired rollbacks are cleaned up but audit records persist forever

---

## 10. Audit System

### 10.1 What Gets Logged (system_audit table)

```sql
INSERT INTO system_audit (
    task_id,               -- links to main tasks table
    tool_name,             -- 'filesystem.move'
    operation,             -- 'move'
    target,                -- '/path/to/file.txt'
    risk_level,            -- 2
    permission_decision,   -- 'confirmed'
    confirmation_required, -- 1
    confirmed,             -- 1
    execution_result,      -- 'success'
    verification_result,   -- 'verified'
    error_code,            -- NULL (no error)
    error_message,         -- NULL
    duration_ms,           -- 45
    os_platform,           -- 'windows'
    timestamp              -- ISO 8601
);
```

### 10.2 What NEVER Gets Logged

| Data Type | Why Not |
|-----------|---------|
| Passwords | Credential exposure |
| API keys/tokens | Credential exposure |
| File contents (unless explicitly needed) | Privacy + storage |
| Typed text (keyboard tool) | Keylogging risk |
| Clipboard contents | May contain credentials |
| Environment variable values containing secrets | Credential exposure |

### 10.3 Audit CLI Commands

```bash
max audit --last 50                           # last 50 system actions
max audit --tool filesystem                    # filter by tool
max audit --risk 3                             # high-risk actions only
max audit --failures                           # failed actions only
max audit --unverified                         # verification failures
max audit --date 2026-08-13                    # specific date
max audit --export audit_backup.json           # export for review
```

---

## 11. Security Architecture

### 11.1 Defense Layers

```
Layer 1: INPUT VALIDATION
  ▸ All paths resolved and normalized
  ▸ Path traversal attempts detected and blocked
  ▸ Command injection patterns detected and blocked
  ▸ Maximum argument lengths enforced

Layer 2: POLICY ENGINE
  ▸ Protected paths list (system directories, other user dirs)
  ▸ Command allowlist/blocklist
  ▸ Risk escalation rules
  ▸ Blocked operation list (password fields, privilege escalation)

Layer 3: PERMISSION CHECK
  ▸ Risk level → permission tier mapping
  ▸ Confirmation tokens (single-use, time-limited)
  ▸ Never phrase-overridable (ADR-009)

Layer 4: EXECUTION SANDBOX
  ▸ Commands run with user-level privileges only
  ▸ No privilege escalation mechanisms
  ▸ Subprocess PID tracking via Kill Switch
  ▸ Timeout enforcement on all operations

Layer 5: OUTPUT SANITIZATION
  ▸ Command output passes through data_boundary
  ▸ Credential-shaped strings masked before logging
  ▸ File contents not stored unless explicitly needed

Layer 6: AUDIT TRAIL
  ▸ Every action logged (including denials)
  ▸ Immutable audit table (append-only)
  ▸ Security events flagged separately
```

### 11.2 Protected Paths (system_policies.yaml)

```yaml
# Paths that require elevated risk assessment
protected_paths:
  windows:
    - "C:\\Windows\\*"
    - "C:\\Program Files\\*"
    - "C:\\Program Files (x86)\\*"
    - "C:\\Users\\*\\AppData\\*"
    - "C:\\ProgramData\\*"
  linux:
    - "/etc/*"
    - "/usr/*"
    - "/boot/*"
    - "/var/log/*"
    - "/root/*"
  darwin:
    - "/System/*"
    - "/Library/*"
    - "/usr/*"
    - "/private/etc/*"

# Paths that are ALWAYS BLOCKED
blocked_paths:
  - "**/passwords*"
  - "**/credentials*"
  - "**/.ssh/*"
  - "**/id_rsa*"
  - "**/.gnupg/*"
```

### 11.3 Command Blocklist (terminal tool)

```yaml
# Patterns that are NEVER allowed in terminal execution
blocked_command_patterns:
  - "rm -rf /"
  - "format c:"
  - "mkfs"
  - ":(){:|:&};:"          # Fork bomb
  - "dd if=/dev/zero"
  - "chmod -R 777 /"
  - "curl.*|.*sh"          # Pipe-to-shell
  - "wget.*|.*bash"
  - "eval.*base64"         # Encoded execution
  - "powershell.*-enc"     # Encoded powershell
  - "reg delete.*HKLM"     # Registry system keys
```

---

## 12. Database Schema (New Tables)

### 12.1 system_tasks

```sql
CREATE TABLE IF NOT EXISTS system_tasks (
    task_id             TEXT PRIMARY KEY,
    tool_name           TEXT NOT NULL,
    operation           TEXT NOT NULL,
    arguments           TEXT NOT NULL,         -- JSON
    risk_level          INTEGER NOT NULL CHECK (risk_level BETWEEN 0 AND 4),
    permission_decision TEXT CHECK (permission_decision IN
                            ('auto', 'confirmed', 'denied', 'blocked')),
    confirmation_token  TEXT,
    pre_state           TEXT,                  -- JSON
    post_state          TEXT,                  -- JSON
    verified            INTEGER DEFAULT 0 CHECK (verified IN (0, 1)),
    reversible          TEXT DEFAULT 'unknown' CHECK (reversible IN
                            ('reversible', 'partial', 'irreversible', 'unknown')),
    rollback_info       TEXT,                  -- JSON
    os_platform         TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

### 12.2 system_audit

```sql
CREATE TABLE IF NOT EXISTS system_audit (
    audit_id              INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id               TEXT,
    tool_name             TEXT NOT NULL,
    operation             TEXT NOT NULL,
    target                TEXT,
    risk_level            INTEGER NOT NULL,
    permission_decision   TEXT NOT NULL,
    confirmation_required INTEGER DEFAULT 0,
    confirmed             INTEGER DEFAULT 0,
    execution_result      TEXT,
    verification_result   TEXT,
    error_code            TEXT,
    error_message         TEXT,
    duration_ms           INTEGER,
    os_platform           TEXT,
    timestamp             TEXT NOT NULL,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

### 12.3 tool_registry

```sql
CREATE TABLE IF NOT EXISTS tool_registry (
    tool_name           TEXT PRIMARY KEY,
    category            TEXT NOT NULL,
    description         TEXT NOT NULL,
    risk_level          INTEGER NOT NULL DEFAULT 0,
    supported_os        TEXT NOT NULL DEFAULT '["windows","linux","darwin"]',
    reversible          TEXT NOT NULL DEFAULT 'unknown',
    requires_confirmation INTEGER DEFAULT 0,
    input_schema        TEXT NOT NULL,         -- JSON Schema
    output_schema       TEXT NOT NULL,         -- JSON Schema
    verification_method TEXT,
    timeout_seconds     INTEGER DEFAULT 30
);
```

### 12.4 system_rollbacks

```sql
CREATE TABLE IF NOT EXISTS system_rollbacks (
    rollback_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id         TEXT NOT NULL,
    tool_name       TEXT NOT NULL,
    original_state  TEXT NOT NULL,             -- JSON
    rollback_action TEXT NOT NULL,             -- JSON
    status          TEXT DEFAULT 'available' CHECK (status IN
                        ('available', 'executed', 'expired', 'failed')),
    created_at      TEXT NOT NULL,
    executed_at     TEXT,
    expires_at      TEXT,
    FOREIGN KEY (task_id) REFERENCES tasks(id)
);
```

### 12.5 Indices

```sql
CREATE INDEX idx_system_audit_tool ON system_audit(tool_name);
CREATE INDEX idx_system_audit_risk ON system_audit(risk_level);
CREATE INDEX idx_system_audit_time ON system_audit(timestamp);
CREATE INDEX idx_system_audit_result ON system_audit(execution_result);
CREATE INDEX idx_system_rollback_task ON system_rollbacks(task_id);
CREATE INDEX idx_system_rollback_status ON system_rollbacks(status);
```

---

## 13. System Control Agent Contract

### 13.1 Agent Specification

| Property | Value |
|----------|-------|
| **Module** | `src/agents/system_control_agent.py` |
| **Build Order** | Layer 5.5 (#25 — after Deploy Agent) |
| **Permission Tier** | Dynamic — determined per-tool risk level |
| **Resources** | `system:<category>` (per-category locking) |
| **Depends On** | Agent base, system controller, tool_registry, OS adapter, permissions |
| **LLM Usage** | For NL→tool mapping on ambiguous commands; deterministic for clear commands |
| **Status** | 🔴 Not started |

### 13.2 Intents

| Intent | Risk Range | Description |
|--------|-----------|-------------|
| `system_info` | 0 | CPU, RAM, GPU, battery, disk, network, OS info |
| `file_operation` | 0-3 | List, search, create, copy, move, rename, delete |
| `process_control` | 0-2 | List, inspect, terminate, start processes |
| `app_control` | 1-2 | Open, close, detect, focus applications |
| `terminal_execute` | 2-3 | Run validated shell commands |
| `window_control` | 1-2 | Focus, minimize, maximize, close windows |
| `input_control` | 2-3 | Keyboard press, hotkey, type, mouse move/click |
| `clipboard_op` | 1 | Read, write clipboard |
| `service_control` | 2-3 | Start, stop, restart system services |
| `storage_info` | 0 | Disk usage, directory sizes |
| `network_info` | 0 | Interfaces, connections, speed |
| `audio_control` | 1-2 | Volume, mute, unmute |
| `display_info` | 0 | Screen resolution, monitors |
| `power_info` | 0 | Battery, power source |
| `environment_op` | 1-2 | Get, set, list environment variables |
| `package_control` | 2 | Install, uninstall packages |
| `dev_tool_control` | 1 | Detect, launch development tools |
| `schedule_op` | 3 | Create, delete scheduled tasks |
| `config_op` | 3-4 | Modify system configuration |
| `archive_op` | 1 | Compress, extract archives |
| `log_collection` | 0 | View system logs |
| `health_check` | 0 | System health monitoring |

### 13.3 Memory Integration

- Reads `memory_preferences['general.default_terminal']` for terminal choice
- Reads `memory_preferences['general.default_browser']` for browser choice
- Reads `memory_preferences['coding.editor']` for dev tool preference
- Reads `memory_behavioral['command_pattern']` for frequent commands
- Writes `memory_project['<project>.dev_tools']` when detecting project tools

---

## 14. Multi-Step Workflow Support

### 14.1 Example: "Prepare my development environment"

```
PLANNER decomposes into workflow:
│
├── Step 1: Inspect OS (system_info) ── auto ── no confirm
│      Output: {os: "windows", version: "11"}
│
├── Step 2: Detect Git (dev_tools.detect) ── auto
│      Output: {installed: true, version: "2.42.0"}
│
├── Step 3: Detect Python (dev_tools.detect) ── auto
│      Output: {installed: true, version: "3.11.4"}
│
├── Step 4: Detect Node (dev_tools.detect) ── auto
│      Output: {installed: false}
│
├── Step 5: Detect Docker (dev_tools.detect) ── auto
│      Output: {installed: true, running: false}
│
├── Step 6: Report findings
│      "Git ✅, Python ✅, Node ❌, Docker ✅ (not running)"
│
├── Step 7: Ask permission for installations ── confirm
│      "Install Node.js? [y/n]"
│      "Start Docker? [y/n]"
│
├── Step 8: Install Node.js (packages.install) ── confirm
│      depends_on: [Step 7 approval]
│
├── Step 9: Start Docker (services.start) ── confirm
│      depends_on: [Step 7 approval]
│
├── Step 10: Verify installations (dev_tools.detect) ── auto
│      Verify: Node exists, Docker running
│
└── Step 11: Generate report
       "Development environment ready:
        Git 2.42.0 ✅
        Python 3.11.4 ✅
        Node.js 20.x ✅ (just installed)
        Docker ✅ (just started)"
```

### 14.2 Workflow State Machine

Each step in a workflow has:

```
PENDING → RUNNING → VERIFYING → COMPLETED
                 ↘ FAILED
                 ↘ WAITING_FOR_PERMISSION → RUNNING
                 ↘ SKIPPED (if optional)
                 ↘ ROLLED_BACK (if previous step failed)
```

---

## 15. Integration Points with Existing Pipeline

### 15.1 Where System Control Plugs In

```
EXISTING MAX PIPELINE                    SYSTEM CONTROL EXTENSION
═══════════════════                      ═══════════════════════════

User Input                               Same entry point
    │                                        │
Intent Classifier ◄─────────────────── NEW: "system" keyword patterns added
    │                                        │
    ├── calendar → Calendar Agent            │
    ├── notes → Notes Agent                  │
    ├── coding → Coding Agent                │
    ├── deploy → Deploy Agent                │
    └── system → System Control Agent  ◄── NEW AGENT
                      │
                 System Controller     ◄── NEW MODULE
                      │
                 OS Adapter            ◄── NEW MODULE
                      │
                 Tool Execution        ◄── NEW MODULE
                      │
Reconciliation ◄──── Verification      ◄── EXTENDED (tool-specific checks)
    │
Snapshot/Rollback ◄── System Rollback  ◄── EXTENDED (filesystem/process state)
    │
Task Events ◄──── System Audit        ◄── EXTENDED (system audit table)
    │
Error Taxonomy ◄── Same 5 classes      ◄── REUSED (new patterns added)
    │
Circuit Breaker ◄── Per-tool breakers  ◄── EXTENDED (filesystem ≠ process)
    │
Kill Switch ◄──── Subprocess tracking  ◄── EXTENDED (system subprocesses)
```

### 15.2 What Does NOT Change

| Component | Why It Stays The Same |
|-----------|---------------------|
| Task Lifecycle state machine | System tasks follow identical CREATED→QUEUED→RUNNING→DONE |
| Task Queue (priority heap) | System tasks enter the same queue with same priority bands |
| Lock Manager (sorted-order) | System uses same lock mechanism with `system:<category>` resources |
| Watchdog (heartbeat) | Same heartbeat monitoring for system tasks |
| Dead Letter Queue | Exhausted system tasks go to same DLQ |
| Vault | System tools that need API keys use same vault |
| Data Boundary | System output sanitized through same boundary |
| Memory Engine | System Control Agent reads/writes same memory layers |

---

## 16. File Structure Summary

```
e:\JARVIS-PLAN\files\
├── src/
│   ├── __init__.py
│   ├── core/
│   │   ├── __init__.py
│   │   ├── kill_switch.py
│   │   ├── intent_classifier.py
│   │   ├── permissions.py
│   │   ├── planner.py
│   │   ├── prompt_agent.py
│   │   ├── data_boundary.py
│   │   ├── memory_engine.py
│   │   └── memory_data_boundary.py
│   ├── infra/
│   │   ├── __init__.py
│   │   ├── state_db.py
│   │   ├── errors.py
│   │   ├── task_lifecycle.py
│   │   ├── task_queue.py
│   │   ├── snapshot.py
│   │   ├── retry.py
│   │   ├── lock_manager.py
│   │   ├── watchdog.py
│   │   ├── reconciliation.py
│   │   ├── circuit_breaker.py
│   │   ├── dlq.py
│   │   ├── vault.py
│   │   └── outcome_tracker.py
│   ├── agents/
│   │   ├── __init__.py
│   │   ├── base.py
│   │   ├── calendar_agent.py
│   │   ├── notes_agent.py
│   │   ├── coding_agent.py
│   │   ├── deploy_agent.py
│   │   └── system_control_agent.py
│   ├── system/
│   │   ├── __init__.py
│   │   ├── controller.py
│   │   ├── tool_registry.py
│   │   ├── executor.py
│   │   ├── verifier.py
│   │   ├── rollback.py
│   │   ├── audit.py
│   │   ├── policies.py
│   │   ├── adapters/
│   │   │   ├── __init__.py
│   │   │   ├── base.py
│   │   │   ├── windows.py
│   │   │   ├── linux.py
│   │   │   └── macos.py
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── filesystem.py
│   │       ├── process.py
│   │       ├── terminal.py
│   │       ├── keyboard.py
│   │       ├── mouse.py
│   │       ├── window.py
│   │       ├── clipboard.py
│   │       ├── applications.py
│   │       ├── network.py
│   │       ├── services.py
│   │       ├── display.py
│   │       ├── audio.py
│   │       ├── power.py
│   │       ├── storage.py
│   │       ├── system_info.py
│   │       ├── user_session.py
│   │       ├── devices.py
│   │       ├── scheduled_tasks.py
│   │       ├── environment.py
│   │       ├── config_mgmt.py
│   │       ├── dev_tools.py
│   │       ├── browser.py
│   │       ├── archives.py
│   │       ├── packages.py
│   │       ├── logs.py
│   │       └── health.py
│   ├── schemas/
│   │   ├── max_state_schema.sql
│   │   ├── memory_schema.sql
│   │   └── system_schema.sql
│   ├── cli/
│   │   ├── __init__.py
│   │   └── main.py
│   └── tests/
│       ├── __init__.py
│       ├── test_kill_switch.py
│       ├── test_permissions.py
│       ├── test_state_machine.py
│       ├── test_system_tools.py
│       ├── test_verification.py
│       ├── test_rollback.py
│       └── test_security.py
├── config/
│   ├── system_policies.yaml
│   └── tool_permissions.yaml
├── requirements.txt
├── pyproject.toml
└── .gitignore
```

---

## 17. Build Order (Wiring Sequence)

```
#   MODULE                        LAYER    DEPENDS ON              GATE TEST
──  ────────────────────────────  ───────  ──────────────────────  ─────────────────────
1   state_db.py                   0A       —                       SELECT 1 returns, WAL verified
2   max_state_schema.sql          0B       state_db                11 core tables exist
3   kill_switch.py                0C       state_db                Dummy task killed in <1s
4   vault.py                      1A       state_db                Store + retrieve secret
5   data_boundary.py              1B       vault                   Fake API key never in output
6   memory_schema.sql             1.5A     state_db                6 memory tables exist
7   memory_engine.py              1.5B     state_db, data_boundary Set identity → retrieve it
8   errors.py                     2A       —                       classify() returns correct class
9   task_lifecycle.py             2B       state_db, kill_switch   Illegal transition raises
10  task_queue.py                 2C       state_db, lifecycle     Priority ordering correct
11  snapshot.py                   2D       state_db, lifecycle     Partial write → clean rollback
12  retry.py                     2E       errors, lifecycle       Full jitter spread verified
13  lock_manager.py               3A       state_db                Reversed-order test completes
14  watchdog.py                   3B       snapshot, lock_manager  Hung agent killed at timeout
15  reconciliation.py             3C       errors                  Lying agent caught
16  circuit_breaker.py            3D       errors                  6th failure rejected instantly
17  dlq.py                        3E       errors, lifecycle       Dead task visible in DLQ
18  intent_classifier.py          4A       data_boundary           10 messages classified correctly
19  permissions.py                4B       —                       5 bypass phrasings all fail
20  planner.py                    4C       intent_classifier       Compound request decomposed
21  prompt_agent.py               4D       memory_engine, data_b   Structured prompt per agent
22  agents/base.py                5A       —                       ABC enforces all methods
23  calendar_agent.py             5B       base, state_db          Event created, conflict detected
24  notes_agent.py                5C       base, state_db          Note stored, semantic search works
25  coding_agent.py               5D       base, snapshot          Code produced, rollback works
26  deploy_agent.py               5E       base, vault, perms      DA-7 gate unbypassable
27  system_schema.sql             5.5A     state_db                4 system tables exist
28  adapters/base.py              5.5B     —                       ABC defined
29  adapters/windows.py           5.5C     base adapter            get_system_info() returns data
30  tool_registry.py              5.5D     state_db                All tools registered
31  policies.py                   5.5E     —                       Protected paths loaded
32  executor.py                   5.5F     all system deps         10-step pipeline works E2E
33  verifier.py                   5.5G     —                       Post-action checks pass
34  rollback.py                   5.5H     state_db                Move → rollback restores file
35  audit.py                      5.5I     state_db                Audit entry written, no secrets
36  controller.py                 5.5J     all system              Natural language → verified result
37  system_control_agent.py       5.5K     controller, base agent  "Show battery" returns correct %
38  26 tool modules               5.5L     adapter, registry       Each tool CRUD works
39  cli/main.py                   6A       all                     CLI → daemon → response
40  tests/*                       6B       all                     All tests pass
```

---

## 18. Example Commands After Implementation

| User Says | Tool Used | Risk | Confirm? | Response |
|-----------|-----------|------|----------|----------|
| "Show my system information" | system_info.get_all | 0 | No | CPU, RAM, GPU, OS details |
| "Show CPU, RAM, GPU and battery" | system_info + power | 0 | No | Real-time metrics |
| "What apps are running?" | process.list | 0 | No | Process list sorted by CPU |
| "Open VS Code" | applications.open | 1 | No | "VS Code is now open" |
| "Create a folder called Projects" | filesystem.create_dir | 1 | No | "Created Projects/" |
| "Move test.txt to Documents" | filesystem.move | 1 | No | "Moved test.txt → Documents/" |
| "Find all Python files here" | filesystem.search | 0 | No | File list with paths |
| "Which process uses most RAM?" | process.list(sort=memory) | 0 | No | Top process by RAM |
| "Close Chrome" | process.terminate | 2 | **Yes** | Confirmation → "Chrome closed" |
| "Press Ctrl+Shift+Esc" | keyboard.hotkey | 2 | **Yes** | Confirmation → Task Manager opens |
| "Show disk usage" | storage.usage | 0 | No | Per-drive usage table |
| "Check if Docker is running" | services.status | 0 | No | "Docker: running/stopped" |
| "Start Docker" | services.start | 2 | **Yes** | Confirmation → "Docker started" |
| "Show recent system errors" | logs.recent | 0 | No | Error log entries |
| "Clean Downloads older than 30 days" | filesystem.delete (batch) | 3 | **Yes + impact** | Shows file count → confirms |

# MAX-AGENT — Desktop Automation & Application Launch Forensics

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Application Launch Forensics (`actions/open_app.py`)

### Current Launch Mechanism
When a user says *"Open Chrome"* or *"Open VS Code"*, `main.py` dispatches to `actions/open_app.py:open_app()`.  
The Windows launcher (`_launch_windows`, lines 80-116) executes the following sequence:

```
Step 1: Check shutil.which(app_name)
        ├── If found: subprocess.Popen(app_name, shell=True) ──► time.sleep(1.5) ──► Return True
        └── If not found: Step 2

Step 2: Check if ":" in app_name (protocol handler, e.g. ms-settings:)
        ├── If found: subprocess.Popen(f"start {app_name}", shell=True) ──► Return True
        └── If not found: Step 3

Step 3: Blind Windows Search Keystroke Simulation (pyautogui)
        ├── pyautogui.press("win")
        ├── time.sleep(0.7)
        ├── pyautogui.write(app_name, interval=0.05)
        ├── time.sleep(0.9)
        ├── pyautogui.press("enter")   <── BLIND ENTER PRESS!
        └── time.sleep(2.5) ──► Return True
```

### Critical Deficiencies in Application Launch
1. **Blind Enter Keypress**:
   - In Step 3, `open_app` presses the Windows key, types the name, and presses `Enter` blindly.
   - On Windows 10/11, Windows Search frequently ranks Bing web search results, settings, or documents above the application. Pressing Enter blindly often opens Edge to a web search instead of launching the app!
2. **No Window or Process Verification**:
   - `open_app` returns `f"Opened {app_name}."` if `Popen` did not immediately raise an exception or if `pyautogui.press("enter")` ran.
   - It **never verifies** whether a process matching the target application actually started, whether a visible top-level window was created, or whether the window is responsive.
3. **No Focus of Existing Instances**:
   - If VS Code or Chrome is already running, `open_app` does not check running processes via `psutil` or Win32 APIs. It executes `subprocess.Popen("code")`, opening duplicate windows or instances unnecessarily.
4. **Shell Injection Risk**:
   - `subprocess.Popen(app_name, shell=True)` executes the application name string directly inside the Windows shell.

---

## 2. Desktop Interaction Forensics (`actions/desktop.py`)

### Current Interaction Loop
When the user asks MAX to interact with on-screen software (e.g. *"Click on the search bar"* or *"Move this window"*), `actions/desktop.py` runs:

1. `_ask_gemini_for_desktop_action(task)` prompts `gemini-flash-latest` with a prompt asking for Python code using `pyautogui` or `pathlib`.
2. The model returns Python code.
3. `_execute_generated_code(code)` compiles and runs the code via:
   ```python
   exec(compile(code, "<max_desktop>", "exec"), sandbox)
   ```
4. `sandbox` injects `pyautogui`, `ctypes`, `winreg`, and `shutil`.

### Critical Deficiencies in Desktop Interaction
1. **Extreme Security Vulnerability (RCE)**:
   - Relying on LLM prompt instructions ("NO subprocess calls") to prevent malicious actions is ineffective. A confused or jailbroken model can generate code leveraging `ctypes.windll` to modify system files, inject DLLs, or spawn hidden processes.
2. **Blind Coordinate Simulation**:
   - When `pyautogui` is used, the model guesses pixel coordinates (e.g. `pyautogui.click(500, 300)`).
   - Coordinates are screen-resolution, multi-monitor, and DPI-dependent. They break across different displays and window resizes.
3. **Absence of UI Automation (UIA)**:
   - Modern Windows desktop automation requires the Windows UI Automation (UIA) accessibility tree to target elements by `AutomationId`, `Name`, and `ControlType`.
   - `core/perception/accessibility.py` exists in the repository, but is **never called** by `actions/desktop.py`.

---

## 3. Screen Understanding Forensics (`actions/screen_processor.py`)

### How MAX Observes the Screen
1. `main.py:_execute_tool()` invokes `actions/screen_processor.py:_capture_screen()`.
2. `_capture_screen()` uses `mss` to capture the primary display framebuffer into raw RGB bytes.
3. PIL scales and compresses the frame to JPEG (max 1280x720, quality 82).
4. The compressed JPEG is base64-encoded and transmitted directly to the Gemini Live session over WebSocket.
5. Gemini uses vision reasoning to describe the image.

### Deficiencies in Screen Understanding
1. **No Structural Analysis**: MAX does not construct a structured UI element tree. It treats the entire screen as a flat image.
2. **No Post-Action Screen Verification**: MAX does not capture a screenshot before and after an action to compute a visual diff or confirm state changes.
3. **Privacy Exposure**: Screenshots are captured unmasked. If a password field or sensitive credential is on screen, it is captured and sent to the cloud API.

---

## 4. Required Evolution (Master Spec Sections 16 & 17)

1. **Structured ApplicationRegistry**:
   - Fields: `application_id`, `display_name`, `aliases`, `executable`, `aumid`, `process_names`, `window_title_patterns`.
   - Focus existing windows first before spawning duplicates.
2. **Windows Search Flow with Guards**:
   - Open Search surface (`Win` or `Win+S`).
   - Verify search window element exists via UIA.
   - Insert query via Unicode text pattern.
   - Inspect UIA result items: verify item type is `Application` (not Web search or Setting) and name matches before activating.
3. **Target L3 Launch Verification**:
   - Confirm target process exists (`psutil.Process`).
   - Confirm visible top-level window exists (`win32gui.IsWindowVisible`).
   - Confirm window title matches application pattern.
   - Confirm window is responsive (`win32gui.SendMessageTimeout` responds).
4. **Replace `exec()` with Deterministic Desktop Adapter**:
   - `WindowsDesktopAdapter` utilizing `pywinauto` / `UIAutomation` for semantic element targeting.

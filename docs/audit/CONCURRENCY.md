# MAX-AGENT — Concurrency, Threading & Resource Locking Forensics

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Concurrency Model Architecture

MAX uses a hybrid **PyQt6 GUI Main Thread + Python asyncio Event Loop + ThreadPoolExecutor** model:

```
[ Process: Python main.py ]
 ├── [ Thread 1: PyQt6 Main Thread ]
 │    └── ui.root.mainloop() (UI event handling, waveform rendering, settings drawer)
 │
 ├── [ Thread 2: Asyncio Loop Thread ]
 │    └── MaxLive.run()
 │         ├── TaskGroup Coroutines (Network WebSocket, Audio in/out, Monitor loops)
 │         └── ThreadPoolExecutor (Blocking action execution via loop.run_in_executor)
 │
 └── [ Thread 3: WakeWordDetector Thread ]
      └── Runs openwakeword ONNX model inference continuously when wake word is enabled
```

---

## 2. Forensic Answers to Concurrency Questions

### 1. Can MAX run two agents simultaneously?
**NO.** In `main.py:_execute_tool()`, tool calls emitted by Gemini are executed sequentially in a single `for fc in response.tool_call.function_calls:` loop. Even when offloaded to `loop.run_in_executor`, `_execute_tool` awaits the tool execution before sending `FunctionResponse` back to Gemini.

### 2. Can MAX run unrelated tasks simultaneously?
**PARTIALLY.** Background tasks (e.g. `_run_system_monitor` every 10s and `_run_background_monitor` every 30m) run concurrently with the audio loop. However, user-initiated action tasks (e.g. running a build while setting a reminder) cannot be launched concurrently because there is no multi-task background scheduler connected to `main.py`.

### 3. Can a long task block the main loop?
- **GUI Event Loop**: **NO.** Long actions run off-thread via `loop.run_in_executor`, so the PyQt6 GUI remains responsive.
- **Asyncio Audio Event Loop**: **NO**, because blocking calls use `run_in_executor`.
- **Gemini Turn State**: **YES.** While a long action (such as `dev_agent` running a 60-second build) is executing in the executor, Gemini is waiting for the `FunctionResponse`. During this window, Gemini cannot process another voice command or execute another tool.

### 4. Can a background task block voice input?
**YES.** In `main.py:1012-1014`, the mic callback checks `with self._speaking_lock: max_speaking = self._is_speaking`. If a background monitor triggers an alert while the user is speaking, or if TTS playback begins, the microphone input is gated, dropping user speech frames.

### 5. Can two agents control the desktop simultaneously?
**NO.** Desktop actions are executed sequentially. However, **the human user is an uncoordinated competitor for desktop input**:
- If MAX executes `actions/desktop.py` (which simulates mouse/keyboard via `pyautogui`) while the human user is actively typing or moving the mouse, `pyautogui` injects keystrokes into whatever window happens to be foregrounded.
- There is **no `UserActivityMonitor`** and **no focus guard** to prevent typing into the wrong application window.

---

## 3. Resource Locking Forensics: `LockManager` Analysis

### Source Inspection: `core/max_infra/lock_manager.py`
The repository contains an implementation of Dijkstra's sorted resource lock manager:
- `LockManager.acquire(resources, task_id, timeout)`:
  - Canonical sort of resource identifiers (`sorted(list(resources))`) to eliminate circular wait and deadlocks.
  - Automatic lease expiry with TTL (default 30.0s).
  - Thread-safe tracking with an internal `threading.RLock`.

### The Forensic Reality in Production
1. In `agents/base.py:94`, `BaseAgent.run()` wraps `_execute()` inside `with self.lock_manager.acquire(resources, ...):`.
2. **However**, in `main.py:935`, when `_execute_tool()` invokes an agent, it creates `AgentInput` with:
   ```python
   agent_input = AgentInput(
       task_id=f"task_{int(time.time())}",
       task_description=args.get("task_description", str(args)),
       parameters=args,
   )
   ```
   Notice that `target_files` and `required_resources` are **omitted**, defaulting to empty lists `[]`!
3. Therefore, `resources` passed to `lock_manager.acquire()` is **always empty**!
4. Furthermore, none of the 19 action handlers in `actions/*.py` use `LockManager` at all. `actions/desktop.py`, `actions/open_app.py`, and `actions/file_controller.py` perform uncoordinated I/O with zero resource leases.

---

## 4. Required Evolution (Master Spec Section 12)

1. **Mandatory Canonical Resource Catalog**:
   - `desktop-input` (EXCLUSIVE): Held during mouse/keyboard automation.
   - `desktop-observe` (SHARED): Held during screen capture.
   - `app:<id>` (EXCLUSIVE): Governs actions on a specific running application.
   - `project:<path>` (EXCLUSIVE to write, SHARED to read).
   - `gpu-vram` (MUTEX): Prevents concurrent local model loading on 4GB VRAM targets.
2. **User Activity Guard**: Implement low-level Windows mouse/keyboard hook detecting human input. If user moves the mouse or types mid-automation, pause task (`PAUSED(USER_ACTIVE)`) immediately.
3. **Dedicated Desktop Actor Thread**: UI Automation and input injection must run on a dedicated single-threaded actor with a sequential command queue.

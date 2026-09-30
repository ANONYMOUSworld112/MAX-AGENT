# MAX-AGENT: End-to-End Execution Flow Analysis

> **Document Version**: 1.0.0  
> **Status**: VERIFIED against commit HEAD on branch `max/p0-baseline`  
> **Audience**: Master Implementation Agent & System Owner  
> **Authority**: Governed by Section 3 & 6 of Master Engineering Specification v2  

---

## 1. Input Channel Overview

MAX-AGENT possesses 6 distinct input channels in the codebase:
1. **Voice Input** (`main.py:_listen_audio` via `sounddevice`)
2. **Text Input** (`main.py:_on_text_command` via HUD prompt box)
3. **HUD Controls** (`ui.py` buttons, toggles, confirm/cancel, overlays)
4. **Dashboard Web/API** (`dashboard/server.py` HTTP endpoints & WebSocket)
5. **Wake Word** (`core/wake_word.py` listening for "Hey MAX")
6. **Programmatic / Background Monitors** (`actions/background_monitor.py`, `actions/proactive.py`)

---

## 2. 13-Stage Trace Matrix

Below is the forensic analysis of how each channel traverses the mandatory 13 stages of task processing in the **current codebase**, highlighting gaps where stages are bypassed.

| Stage # | Stage Name | Current Voice Path | Current Text / HUD Path | Current Dashboard Path | Target Architecture Path (Spec v2) |
|---|---|---|---|---|---|
| **1** | **Receive** | `sounddevice.InputStream` callback captures 16kHz PCM audio | `MAXUI` line edit emits text signal to `_on_text_command` | FastAPI endpoint receives HTTP POST / WebSocket packet | `InputGateway.receive(raw_input, channel)` |
| **2** | **Normalize** | Raw PCM chunks sent directly to Gemini Live API; no text normalization | Simple whitespace trim in `_on_text_command` | Decrypts base64 AES-CBC ciphertext to JSON | Canonical `InputEnvelope` with timestamps, origin, trust level |
| **3** | **Intent** | **Bypassed locally**: Gemini cloud model interprets intent directly | **Bypassed locally**: Text sent as Gemini user turn via `live.send` | Model intent parsed if routed to Gemini, else ad-hoc command parsing | `IntentEngine` parses intent schema + fast-path single-turn intent |
| **4** | **Context** | Context is static system prompt + `format_memory_for_prompt` | Context is existing Gemini session history | Context is session-specific key/value in dashboard memory | `ContextManager` pulls relevance-filtered tokens within budget |
| **5** | **Task Creation** | **Missing**: No `Task` object created. Model sends raw `FunctionCall` | **Missing**: Handled as interactive utterance | **Missing**: Dashboard executes action directly or queues in-memory | `TaskPlanner` or fast-path creates structured `Task` + `TaskIntent` |
| **6** | **Agent Selection** | **Implicit**: Tool name in Gemini `FunctionCall` routes directly to action | **Implicit**: Same as voice path | **Ad-hoc**: Matches tool name string | `AgentRouter` selects agent from capability registry with decision log |
| **7** | **Execution Start** | `_execute_tool` triggered in `main.py` | `_execute_tool` triggered | Async task dispatched in FastAPI | Scheduler leases resources, state moves `QUEUED -> RUNNING` |
| **8** | **Tool Invocation** | `_action_registry.run(name, args)` executed in `ThreadPoolExecutor` | `_action_registry.run` | Handlers invoked directly | `ExecutionGateway.execute(ActionRequest)` with risk policy & sandbox |
| **9** | **State Change** | Direct host OS side effects (`subprocess`, `pyautogui`, `open`) | Direct host OS side effects | Direct host OS side effects | Deterministic adapter handles side effect with undo/snapshot |
| **10** | **Completion Detection**| Handler return string or unhandled exception | Handler return string | HTTP response returned | Postconditions evaluated by verifier; exit codes & artifacts checked |
| **11** | **Verification** | **Missing**: Subprocess started or pyautogui key sent treated as success | **Missing**: No verification | **Missing**: No verification | `VerificationEngine` assigns L0–L3 outcome (`SUCCESS/FAILURE/UNKNOWN`) |
| **12** | **Memory Write** | Manual `save_memory` tool call by LLM or session summary at disconnect | Same as voice | None | Verified outcomes and trusted facts written to transactional store |
| **13** | **Response** | `FunctionResponse` sent back to Gemini; Gemini streams synthesized audio | Synthesized audio + text log | JSON payload / WebSocket broadcast | Structured outcome passed to `ResponseEngine` matching verification level |

---

## 3. Deep-Dive: Forensic Input Channel Traces

### 3.1 Channel 1: Voice Input (Current Production Flow)
```
[User Speaks]
      │
      ▼
1. sounddevice callback (main.py:999) captures 1024 int16 PCM samples @ 16kHz
      │
      ▼
2. Checks self._awake (gated by wake word if enabled)
      │
      ▼
3. loop.call_soon_threadsafe(self._audio_in_queue.put_nowait, pcm_bytes)
      │
      ▼
4. _send_realtime (main.py:980) pulls pcm_bytes and calls:
   session.send(input=types.LiveClientRealtimeInput(media_chunks=[...]))
      │
      ▼
5. [Gemini Live Server over WebSocket] conducts speech-to-intent-to-tool reasoning
      │
      ▼
6. _receive_audio (main.py:1070) receives server turn:
   - Plays audio chunks via _play_audio
   - If server_content.model_turn contains calls:
     Dispatches `self._execute_tool(fc)`
      │
      ▼
7. _execute_tool (main.py:805):
   ├── Check inline tools (screen_process, close_camera, save_memory, ...)
   ├── Check _action_registry.has(fc.name) -> runs action in ThreadPoolExecutor
   ├── Check _agent_registry.get(fc.name) -> runs agent in ThreadPoolExecutor
   └── Fallback to _intent_router.route(fc.name, fc.args)
      │
      ▼
8. Action handler executes direct side effect (e.g. actions/open_app.py launches process)
      │
      ▼
9. Returns types.FunctionResponse(id=fc.id, name=fc.name, response={"result": result})
      │
      ▼
10. Gemini Live speaks verbal acknowledgment to user.
```

### 3.2 Channel 2: Text Input (HUD Input Box)
```
[User Types Command in HUD and presses Enter]
      │
      ▼
1. MainWindow._on_send (ui.py) captures text and emits command signal
      │
      ▼
2. main.py:_on_text_command(text)
      │
      ▼
3. Formats text as LiveClientContent(turns=[Content(parts=[Part(text=text)])])
      │
      ▼
4. Calls session.send(input=content, end_of_turn=True)
      │
      ▼
5. Joins Gemini Live WebSocket stream; tool execution path identical to Voice.
```

### 3.3 Channel 3: Wake Word ("Hey MAX")
```
[User Speaks "Hey MAX"]
      │
      ▼
1. sounddevice mic callback feeds audio to WakeWordDetector.feed(samples)
      │
      ▼
2. Background thread (core/wake_word.py:_run) feeds openwakeword Model
      │
      ▼
3. Prediction score exceeds threshold (>= 0.5)
      │
      ▼
4. Invokes on_detected callback -> main.py:wake(reason="wake word")
      │
      ▼
5. Sets self._awake = True, unmuting mic queue to Gemini Live
      │
      ▼
6. Starts sleep timer watchdog (WAKE_SLEEP_TIMEOUT = 120s)
```

### 3.4 Channel 4: Dashboard Web API
```
[Remote HTTP Client sends POST /api/command]
      │
      ▼
1. dashboard/server.py handles request on 0.0.0.0:8000
      │
      ▼
2. Decrypts AES-256 payload using session key
      │
      ▼
3. Places command into command queue (self._dashboard_cmd_queue)
      │
      ▼
4. main.py:_process_dashboard_commands pulls command and injects into Gemini Live session
```

---

## 4. Critical Architecture Gaps in Execution Flow

1. **No Local Intent Reasoning Before Action**:
   Because `main.py` relies on Gemini Live cloud inference for intent extraction, offline intent interpretation is impossible. When offline, all commands fail.
2. **Missing State Machine Progression**:
   Neither Voice, Text, nor Dashboard commands ever instantiate a `Task` record or advance through `TaskState`. There is no `TaskCreated`, `TaskQueued`, `TaskStarted`, or `TaskCompleted` event.
3. **Absence of Choked Execution**:
   Action handlers interact directly with the operating system without passing through an `ExecutionGateway`.
4. **Zero Deterministic Verification**:
   When an action finishes, whatever string it returns is sent back to Gemini as truth. No OS-level verification (process status, window state, media state) confirms the outcome.
5. **No Graph Capability for Multi-Step Workflows**:
   Multi-step requests are executed via loose turn-taking with the cloud LLM, which can drop steps or fail silently mid-workflow.

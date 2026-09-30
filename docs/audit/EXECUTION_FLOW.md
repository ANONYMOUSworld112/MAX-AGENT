# MAX-AGENT — Real Execution Flow & Input Pipeline Audit

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Input Channel Tracing Methodology

Per Non-Negotiable Rule #2, this document traces every input channel from physical arrival to final response, recording:
- **FILE, CLASS, FUNCTION, CALL SITE, CALL CHAIN, and TRIGGER CONDITION**
- Tracking across the 13 lifecycle stages:
  1. Receive → 2. Normalize → 3. Intent Detection → 4. Context Retrieval → 5. Planning → 6. Task Creation → 7. Routing → 8. Agent Assignment → 9. Execution → 10. Observation → 11. Verification → 12. Memory → 13. Response.

---

## 2. Channel A: Voice Input (Microphone)

### Complete Call Chain
```
Physical Audio Input (Hardware Microphone)
 ↓ (PCM 16kHz, 16-bit Mono)
sounddevice.InputStream callback (main.py:999 callback())
 ↓ Trigger: Non-silent audio chunk captured while self._awake is True and not self._is_speaking
loop.call_soon_threadsafe(self.out_queue.put_nowait, {"data": data, "mime_type": "audio/pcm"}) (main.py:1016)
 ↓
MaxLive._send_realtime() (main.py:980)
 ↓ Call Site: main.py:988
self.session.send_realtime_input(audio=types.Blob(data=msg["data"], mime_type="audio/pcm"))
 ↓ [NETWORK WEBSOCKET TO GOOGLE GEMINI LIVE API]
Google Gemini 3.1 Flash Live Model (Cloud)
 ↓ Server emits tool_call response over WebSocket
MaxLive._receive_audio() (main.py:1076)
 ↓ Call Site: main.py:1185 if response.tool_call
for fc in response.tool_call.function_calls:
 ↓ Call Site: main.py:1189
MaxLive._execute_tool(fc) (main.py:805)
 ↓ Dispatch Ladder:
 ├── [Inline Tools]: screen_process, save_memory, undo, system_status, etc. (main.py:812-913)
 ├── [Discovered Actions]: self._action_registry.run(name, args, _ctx) (main.py:921)
 └── [Agents]: self._agent_registry.get(name) -> agent.run(agent_input) (main.py:932-941)
 ↓
Result formatted into types.FunctionResponse(id=fc.id, name=name, response={"result": result}) (main.py:975)
 ↓ Call Site: main.py:1191
self.session.send_tool_response(function_responses=fn_responses)
 ↓ [NETWORK WEBSOCKET TO GOOGLE GEMINI LIVE API]
Gemini synthesizes natural audio response + transcript
 ↓
MaxLive._receive_audio() receives response.data (PCM 24kHz audio) (main.py:1091)
 ↓ Pushed to self.audio_in_queue
MaxLive._play_audio() (main.py:1199)
 ↓ Call Site: main.py:1267
sounddevice.RawOutputStream.write(bytes(batch))
 ↓
User hears spoken answer from PC speakers
```

### Stage-by-Stage Forensic Breakdown
1. **Receive**: `main.py:999` in `callback()` of `sd.InputStream`.
2. **Normalize**: None. Raw PCM bytes are packaged directly.
3. **Intent Detection**: **Outsourced to Gemini Live.** No local intent classification occurs. `ReflexIntentRouter` is bypassed.
4. **Context Retrieval**: System instruction assembled at connection time in `main.py:_build_config()` (lines 720-803) containing `memory/long_term.json` contents and `core/prompt.txt`.
5. **Planning**: Outsourced to Gemini Live server-side.
6. **Task Creation**: **Missing.** No `Task` object is instantiated. Only a transient `fc.id` exists.
7. **Routing**: Model generates tool name `fc.name`. Dispatch ladder in `main.py:_execute_tool()` matches against registries.
8. **Agent Assignment**: If `fc.name` matches an agent name, `_agent_registry.get(fc.name)` is assigned. Otherwise, action handler is assigned.
9. **Execution**: Dispatched via thread pool executor `loop.run_in_executor(None, handler)`.
10. **Observation**: None, unless the tool explicitly captures the screen (e.g. `screen_process`).
11. **Verification**: **Missing.** Success is assumed if no exception was raised.
12. **Memory**: If `save_memory` tool was called by Gemini, updates `memory/long_term.json`.
13. **Response**: Synthesized audio streamed via `MaxLive._play_audio()` and text transcription logged to `self.ui.write_log()`.

---

## 3. Channel B: Text Input (HUD / Keyboard)

### Complete Call Chain
```
User types in HUD text box and presses Enter
 ↓
ui.py:MAXUI._on_text_return() (ui.py:348)
 ↓ Call Site: ui.py:355
self.on_text_command(text)
 ↓ Bound callback: main.py:MaxLive._on_text_command(text) (main.py:660)
asyncio.run_coroutine_threadsafe(
    self.session.send_client_content(
        turns={"role": "user", "parts": [{"text": text}]},
        turn_complete=True
    ),
    self._loop
)
 ↓ [NETWORK WEBSOCKET TO GOOGLE GEMINI LIVE API]
Google Gemini 3.1 Flash Live Model processes text
 ↓ (Subsequent tool dispatch, execution, and response follow Channel A)
```

---

## 4. Channel C: Remote Web Dashboard Input

### Complete Call Chain
```
User enters command in mobile browser or web app
 ↓
dashboard/static/app.html sends WebSocket message {"type": "command", "text": "..."}
 ↓
dashboard/server.py:websocket_endpoint() (dashboard/server.py:754)
 ↓ Trigger: data.get("type") == "command"
await self._command_queue.put(t) (dashboard/server.py:758)
 ↓
main.py:MaxLive._process_dashboard_commands() (main.py:1564)
 ↓ Reads from self._dashboard._command_queue
await self.session.send_client_content(
    turns={"role": "user", "parts": [{"text": text}]},
    turn_complete=True
) (main.py:1581)
 ↓ [NETWORK WEBSOCKET TO GOOGLE GEMINI LIVE API]
(Follows Channel A execution loop)
```

---

## 5. Channel D: Wake Word Trigger

### Complete Call Chain
```
Microphone captures background audio while MAX is in SLEEPING state (self._awake = False)
 ↓
main.py:_listen_audio() (main.py:1007)
 ↓ Trigger: self._wake_enabled and not self._awake
det = self._wake_detector
det.feed(indata) (main.py:1010)
 ↓
core/wake_word.py:WakeWordDetector._process_loop()
 ↓ OpenWakeWord model detects phrase "hey jarvis" / "hey max"
on_detect callback invoked -> main.py:MaxLive._on_wake_detected() (main.py:507)
 ↓
MaxLive.wake(reason="wake word") (main.py:511)
 ↓ Sets self._awake = True, updates UI state to "LISTENING"
self.ui.set_state("LISTENING")
self.ui.write_log("SYS: Awake — wake word.")
 ↓
Mic stream opens for subsequent speech transmission to Gemini
```

---

## 6. Channel E: Proactive Engine & Periodic Timers

### Complete Call Chain
```
Background coroutine MaxLive._run_proactive_mode() evaluates once per minute
 ↓
actions/proactive.py:ProactiveEngine.should_trigger()
 ↓ Trigger: User silent > 15 minutes during active daytime hours
prompt = self._proactive.build_prompt(memory, monitors, recent_turns)
 ↓ Call Site: main.py:1528
await self.session.send_client_content(
    turns={"role": "user", "parts": [{"text": prompt}]},
    turn_complete=True
)
 ↓
Gemini speaks a context-aware proactive greeting
```

---

## 7. Forensic Deficiencies Across All Input Pipelines

1. **No Local Normalization**: Raw user utterances and text commands are transmitted directly to Gemini without entity extraction or canonization.
2. **Missing Input Provenance**: Injected prompts do not distinguish between `user_direct`, `voice`, `api`, or `untrusted_tool_output`. All inputs arrive at the model with identical authority.
3. **No Local Intent Classification**: The local `ReflexIntentRouter` and `LayaReflexEngine` are completely bypassed during normal operations.
4. **No Task Graph or Decomposer**: Multi-step requests (e.g. "Create a python project and test it") are executed as atomic single-shot tool calls without dependency graphs or rollback checkpoints.
5. **No State Verification**: Every tool return string is forwarded back to Gemini as an unqualified "truth", even when the tool failed silently or only simulated its action.

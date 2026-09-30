# MAX-AGENT — Real Agent Invocation Graph Audit

> **Forensic Audit Date**: 2026-09-30  
> **Source Commit**: `877b913` (branch: `max/p0-baseline`)  
> **Auditor**: Principal AI Systems Architect & Codebase Forensic Engineer  
> **Status**: COMPLETED & VERIFIED AGAINST SOURCE CODE  

---

## 1. Documented vs Real Invocation Topology

### The Documented Architectural Myth
The documentation (`readme.md` and `IMPLEMENTATION_PLAN.md`) depicts a hierarchical multi-agent tree with recursive delegation:
```
USER ──► ReflexIntentRouter ──► MasterOrchestrator ──► DecompositionPlanner
                                                            │
                     ┌──────────────────────────────────────┴──────────────────────┐
                     ▼                                                             ▼
                CodingAgent                                                  CalendarAgent
               ┌─────┴──────────┐                                                  │
               ▼                ▼                                                  ▼
          TerminalTool     TestWriter                                       SchedulerStore
```

### The Actual Executed Reality
In the actual Python implementation, **no agent ever delegates to or invokes another agent.**
There is **zero recursive delegation**, **zero subagent communication**, and **zero task planning**.

Instead, all 33 agents are registered in `AgentRegistry` and flattened into Gemini's tool definition list (`types.LiveConnectConfig(tools=[...])` in `main.py:770`).
Gemini invokes an agent as a flat, single-shot tool. The agent's `run()` method runs its stub `_execute()` and immediately returns a string to Gemini:

```
                            [ USER INPUT ]
                                  │
                                  ▼
                         [ main.py: MaxLive ]
                                  │
                                  ▼ (WebSocket)
                    [ Google Gemini Live Server ]
                                  │
                ┌─────────────────┴─────────────────┐
                │ Model generates tool_call(name)   │
                └─────────────────┬─────────────────┘
                                  ▼
                     [ main.py: _execute_tool() ]
                                  │
         ┌────────────────────────┼────────────────────────┐
         │ (Line 915)             │ (Line 932)             │ (Line 943)
         ▼                        ▼                        ▼
[ ActionRegistry ]       [ AgentRegistry ]        [ PluginRegistry ]
 (19 Real Actions)       (33 Stubs in agents/)    (Plugins on disk)
         │                        │                        │
         ▼                        ▼                        ▼
 actions/*.py:handler()    BaseAgent.run()        Plugin.run()
 (open_app, desktop, etc)         │                        │
         │                        ▼                        │
         │                 Stub _execute()                 │
         │                (Mock dict / msg)                │
         │                        │                        │
         └────────────────────────┼────────────────────────┘
                                  ▼
                 types.FunctionResponse(result=...)
                                  │
                                  ▼
                    [ Google Gemini Live Server ]
```

---

## 2. Invocation Edge Inventory

Every real invocation edge in the production codebase is cataloged below with exact source locations:

| Edge ID | Source File:Line | Caller Function / Context | Target Component / Function | Trigger Condition |
|---|---|---|---|---|
| **E-01** | `main.py:1809` | `main.py:runner()` | `main.py:MaxLive(ui)` | Process startup |
| **E-02** | `main.py:448` | `MaxLive.__init__()` | `core/action_loader.py:discover_actions()` | Startup scan of `actions/*.py` |
| **E-03** | `main.py:456` | `MaxLive.__init__()` | `core/plugin_loader.py:discover_plugins()` | Startup scan of `plugins/` |
| **E-04** | `main.py:471` | `MaxLive.__init__()` | `agents/router.py:AgentRegistry.get_instance()` | Instantiates singleton and calls `register_defaults()` |
| **E-05** | `agents/router.py:125-167`| `AgentRegistry.register_defaults()` | Instantiates 33 `BaseAgent` subclasses | Startup registry population |
| **E-06** | `main.py:770-775` | `MaxLive._build_config()` | `AgentRegistry.get_all_tool_definitions()` | Serializes all 33 agents into Gemini function schemas |
| **E-07** | `main.py:1189` | `MaxLive._receive_audio()` | `main.py:MaxLive._execute_tool(fc)` | Gemini server emits `response.tool_call` |
| **E-08** | `main.py:915` | `MaxLive._execute_tool()` | `core/action_loader.py:ActionRegistry.run()` | `fc.name` matches discovered action name |
| **E-09** | `main.py:932` | `MaxLive._execute_tool()` | `agents/router.py:AgentRegistry.get(name)` | `fc.name` matches registered agent name |
| **E-10** | `main.py:940` | `MaxLive._execute_tool()` | `agents/base.py:BaseAgent.run(agent_input)` | Agent object found in registry |
| **E-11** | `agents/base.py:70` | `BaseAgent.run()` | `core/max_infra/kill_switch.py:KillSwitch.guard()` | Pre-execution safety check |
| **E-12** | `agents/base.py:73` | `BaseAgent.run()` | `core/max_infra/circuit_breaker.py:is_allowed()` | Pre-execution availability check |
| **E-13** | `agents/base.py:94` | `BaseAgent.run()` | `core/max_infra/lock_manager.py:acquire()` | Resource lock acquisition |
| **E-14** | `agents/base.py:96` | `BaseAgent.run()` | `agents/*/*.py:Subclass._execute(input_data)` | Domain execution inside lock context |
| **E-15** | `main.py:953` | `MaxLive._execute_tool()` | `core/reflex/intent_router.py:route()` | Fallback when tool name is completely unknown |
| **E-16** | `main.py:961` | `MaxLive._execute_tool()` | `agents/base.py:BaseAgent.run()` | Fallback if Reflex routed to `LANE_B` |

---

## 3. Delegation Analysis: Do Agents Call Other Agents?

**Finding: NO.**
Inspection of all 33 `_execute()` methods in `agents/core/`, `agents/software/`, `agents/productivity/`, `agents/safety/`, and `agents/health/` confirms:
- **Zero calls** to `AgentRegistry.get()` from within any agent.
- **Zero calls** to `BaseAgent.run()` from within any agent.
- **Zero task queues** utilized to dispatch child tasks.
- In `agents/core/planner.py:25-30`, `DecompositionPlanner` generates a list of subtasks referencing `"SpecAuthor"`, `"PolyglotDeveloper"`, `"CodeReviewer"`, and `"QATestEngineer"`, but returns this list as a static dictionary in `artifacts["subtasks"]`. Nothing in the codebase ever reads, schedules, or executes those subtasks.

# MAX OS — Input Routing Pipeline
### User Input → Intent Classifier → Prompt Agent → Worker Agent Dispatch

---

## 1. The Full Routing Flow

```
USER INPUT (voice/text/image/file)
        │
        ▼
┌───────────────────────┐
│  INTAKE / NORMALIZER   │  [INFRA]
│  strip formatting,     │
│  transcribe voice,     │
│  attach file context   │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│  INTENT CLASSIFIER     │  [AGENT]
│  "what does the user   │
│   actually want?"      │
└───────────────────────┘
        │
        ▼
   ┌────────────┐
   │  ROUTER     │  [INFRA — deterministic lookup on classified intent]
   └────────────┘
        │
   ┌────┴─────────────────────────────────────────────┐
   │  single intent?             compound intent?       │
   │  → one agent                → Planner splits into   │
   │                                multiple sub-intents, │
   │                                each routed below     │
   └────┬─────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────┐
│   PROMPT AGENT         │  [AGENT]
│   raw intent + context │
│   → optimized prompt   │
│   per target agent     │
└───────────────────────┘
        │
        ▼
┌───────────────────────┐
│  AGENT ASSIGNMENT      │  [INFRA — dispatch to worker]
└───────────────────────┘
        │
        ▼
   WORKER AGENT runs (Coding / Research / Security / Deploy / etc.)
        │
        ▼
   Result → Main Agent → Response to user
```

The key idea: **the Intent Classifier decides *what*, the Prompt Agent
decides *how to ask for it*.** These are two different jobs and conflating
them is why a lot of "single mega-prompt" agent systems get sloppy — the
classifier doesn't need to know how Coding Agent likes its instructions
formatted, and the Prompt Agent shouldn't be the one deciding intent.

---

## 2. Intent Classifier — Routing Table

| User says (examples) | Classified intent | Routed to |
|---|---|---|
| "Build me a login page" / "Add a feature that..." | `build` | Planner → Coding Agents |
| "What's the best way to do X" / "Compare React vs Vue" | `research` | Research Agent |
| "Scan this for vulnerabilities" / "Is this secure?" | `security_scan` | Security Agent |
| "Review this code" / "Is this well written?" | `code_review` | Code Review Agent |
| "Push this to production" / "Deploy it" / "Ship it" | `deploy` | Deploy Agent (needs confirmation first) |
| "Why did this fail" / "Fix this bug" | `debug` | Debug Agent |
| "Write docs for this" | `document` | Documentation Agent |
| Unclear / multiple things at once | `compound` or `ambiguous` | Planner splits it, or Main Agent asks a clarifying question |

**Confidence threshold matters here.** If the classifier isn't confident
(say, below ~70%), don't guess — route to a clarification question instead.
A wrong guess that silently invokes the wrong agent wastes far more time
than one clarifying question.

---

## 3. Prompt Agent — What It Actually Does

This is the layer most people skip, and it's the one that makes agent
output noticeably better. It takes:

- the raw user message
- the classified intent
- relevant context (project memory, current file state, past outcomes)

...and produces a **structured, agent-specific prompt** instead of just
forwarding the user's words.

### Example transformation

**User said:**
> "push this to production"

**Intent Classifier output:**
```json
{ "intent": "deploy", "confidence": 0.94 }
```

**Prompt Agent produces for the Deploy Agent:**
```json
{
  "task": "deploy",
  "project_path": "/home/user/projects/dashboard-app",
  "branch": "main",
  "target_env": "production",
  "preconditions": [
    "run validation suite before proceeding",
    "require explicit approval before production stage"
  ],
  "context": {
    "last_deploy": "2026-08-01, succeeded",
    "known_flaky_tests": ["auth.integration.test.js"]
  }
}
```

Notice the raw user prompt ("push this to production") carried almost no
usable information on its own — the Prompt Agent is what turns a vague
human sentence into something an agent can actually execute against
correctly, using memory it already has.

### Another example — compound request

**User said:**
> "Build my portfolio site, deploy it, and check it for security issues"

**Intent Classifier output:**
```json
{ "intent": "compound", "sub_intents": ["build", "deploy", "security_scan"] }
```

**Planner decomposes into an ordered task list**, and the Prompt Agent
generates one optimized, context-specific prompt per sub-task — the Coding
Agent gets a build spec, the Deploy Agent gets a deploy spec (with a
dependency: don't run until build finishes), the Security Agent gets a scan
spec (with a dependency: don't run until deploy finishes).

---

## 4. Minimal Code Sketch (Phase 1 buildable version)

```python
class IntentClassifier:
    def classify(self, message: str) -> dict:
        # Phase 1: keyword + simple LLM call, not a trained model
        # Returns {"intent": str, "confidence": float, "sub_intents": list|None}
        ...

class PromptAgent:
    def build_prompt(self, intent: dict, raw_message: str, context: dict) -> dict:
        # Looks up a template per intent type, fills in context from Memory
        template = PROMPT_TEMPLATES[intent["intent"]]
        return template.render(raw_message=raw_message, **context)

class Router:
    AGENT_MAP = {
        "build": "coding_agent",
        "research": "research_agent",
        "security_scan": "security_agent",
        "code_review": "review_agent",
        "deploy": "deploy_agent",
        "debug": "debug_agent",
        "document": "docs_agent",
    }

    def route(self, intent: dict):
        if intent["intent"] == "compound":
            return [self.AGENT_MAP[i] for i in intent["sub_intents"]]
        if intent["confidence"] < 0.70:
            return "clarify"   # ask user instead of guessing
        return self.AGENT_MAP.get(intent["intent"], "clarify")


class MainAgent:
    def handle(self, user_message: str):
        intent = self.intent_classifier.classify(user_message)
        target = self.router.route(intent)

        if target == "clarify":
            return self.ask_clarifying_question(user_message)

        if isinstance(target, list):  # compound
            tasks = self.planner.decompose(intent, user_message)
            for task in tasks:
                prompt = self.prompt_agent.build_prompt(task, user_message, self.memory.context())
                self.orchestrator.dispatch(task["agent"], prompt)
        else:
            prompt = self.prompt_agent.build_prompt(intent, user_message, self.memory.context())
            self.orchestrator.dispatch(target, prompt)
```

This is deliberately simple — no queue system, no event bus yet. It proves
the routing shape works before you add infrastructure around it.

---

## 5. Why Separate Prompt Agent From Intent Classifier At All

You could merge these into one step, and for a Phase 1 prototype that's
fine. Splitting them pays off once you have more than 3-4 worker agents,
because:

- The **classifier** only needs to get better at one narrow job: sorting
  messages into categories. You can improve it independently (better
  examples, confidence tuning) without touching how prompts are built.
- The **Prompt Agent** owns all the context-injection logic (pulling from
  memory, formatting for each agent's expected input shape). When you add a
  new worker agent later, you write one new prompt template — you don't
  touch the classifier at all.
- If something goes wrong, you can tell immediately whether it was a
  **routing problem** (wrong agent picked) or a **prompting problem**
  (right agent, bad instructions) — which matters a lot for debugging and
  is a good thing to be able to say out loud in an interview.

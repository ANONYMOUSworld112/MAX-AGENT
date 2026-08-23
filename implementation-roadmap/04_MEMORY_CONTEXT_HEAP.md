# MAX OS v1 — Memory Context Heap Architecture

### How MAX knows you, remembers your preferences, learns your patterns,
### and gets smarter with every interaction — without leaving your machine.

---

## 0. Why Memory Is a Foundation, Not a Feature

MAX has a trace log (what happened), an outcome tracker (how fast/reliable),
and a session DB (build progress). What it doesn't have is any mechanism to:

- Know your name, role, or timezone
- Remember that you prefer Python over JavaScript
- Notice that you always deploy on Fridays
- Know that project X uses Vite and project Y uses Next.js
- Recall that you corrected it last week about response formatting

Without this, every interaction starts from zero context. MAX is a tool,
not an assistant. This document adds the architecture that closes that gap.

**Design constraint from ADR-018:** The memory system is fully on-device.
No cloud storage. Memory content is subject to the Data Boundary Policy
before any LLM API injection. Pattern detection is deterministic (no LLM
cost). Only ambiguous preference extraction uses a cheap LLM call.

---

## 1. Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         MEMORY CONTEXT HEAP                              │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  LAYER 5: CONVERSATIONAL MEMORY                                   │   │
│  │  Current session context, recent interactions, working memory      │   │
│  │  Lifetime: session → promoted or expired                          │   │
│  │  Write: every interaction  |  Read: intent classifier, prompt agent│  │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │  LAYER 4: PROJECT MEMORY                                          │   │
│  │  Tech stack, deploy targets, test prefs, git conventions           │   │
│  │  Lifetime: persists per project  |  Read: coding/deploy agents     │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │  LAYER 3: BEHAVIORAL MEMORY                                       │   │
│  │  Scheduling patterns, workflow habits, command patterns            │   │
│  │  Lifetime: persists with confidence decay  |  Read: planner, router│  │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │  LAYER 2: PREFERENCE MEMORY                                       │   │
│  │  "I prefer Python", "Always use dark mode", "Concise responses"   │   │
│  │  Lifetime: permanent until user changes  |  Read: all agents       │   │
│  ├──────────────────────────────────────────────────────────────────┤   │
│  │  LAYER 1: IDENTITY MEMORY                                         │   │
│  │  Name, role, timezone, language, skill level                       │   │
│  │  Lifetime: permanent  |  Read: prompt agent, main agent            │   │
│  └──────────────────────────────────────────────────────────────────┘   │
│                                                                          │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │ MEMORY       │  │ MEMORY       │  │ MEMORY       │  │ MEMORY     │  │
│  │ INTAKE       │  │ RETRIEVAL    │  │ PROMOTION    │  │ DECAY      │  │
│  └──────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
│                                                                          │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  MEMORY DATA BOUNDARY (privacy filter before LLM injection)       │   │
│  └──────────────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## 2. Comparison with Claude / GPT / Gemini Memory Models

| System | Memory Model | Strength | What MAX Learns From It | What MAX Does Differently |
|--------|-------------|----------|------------------------|--------------------------|
| **Claude Projects** | Files + instructions injected per-project scope | Scoped, explicit, user-controlled | Project-scoped memory (Layer 4) | MAX also learns across projects and across sessions |
| **GPT Memory** | Flat key-value entries extracted from conversation | Persistent, user-editable | Explicit preference extraction (Layer 2) | MAX adds hierarchical layers, confidence scores, and decay |
| **Gemini Gems** | Custom instructions + uploaded files as persistent context | Flexible, rich context | Identity + preference injection into prompts | MAX also has behavioral pattern detection (inferred, not just stated) |
| **Claude Artifacts** | Structured output documents within conversation | Rich structured responses | Conversational memory capture (Layer 5) | MAX promotes important conversation items to permanent memory |

### What None of Them Do (and MAX Does)

1. **Behavioral pattern detection** — None of Claude/GPT/Gemini infer habits from observation. If you always deploy on Fridays, they don't notice. MAX's Layer 3 does.
2. **Confidence decay** — GPT's memories are equally trusted forever. MAX's inferred patterns have a confidence score that decays if not reinforced.
3. **Per-project memory** — Claude Projects comes closest, but resets when you switch projects. MAX's Layer 4 persists across sessions per project.
4. **Promotion from conversation to permanent** — GPT extracts memories during conversation, but it's opaque. MAX has an explicit promotion engine with observable thresholds.
5. **Fully on-device** — All three competitors store memory on their cloud servers. MAX's memory never leaves the machine.

---

## 3. Layer-by-Layer Design

### 3.1 Layer 1 — Identity Memory

**Table:** `memory_identity`

**What it stores:**

| Key | Example Value | Source |
|-----|---------------|--------|
| `name` | Rohit | explicit |
| `role` | Cybersecurity Engineer / Founder | explicit |
| `timezone` | Asia/Kolkata (IST, UTC+5:30) | explicit or inferred from system |
| `language` | English, Hindi | explicit |
| `skill_level` | Senior (5+ years) | explicit |
| `communication_style` | Direct, no fluff | explicit |
| `organization` | Solo founder | explicit |
| `primary_machine` | Windows, RTX 3050 4GB | observed |

**How it's populated:**
- User explicitly says "My name is Rohit" → `INSERT` with confidence=1.0
- System observes timezone from OS → `INSERT` with source='inferred', confidence=0.9

**How it's used:**
- Prompt Agent injects identity into every agent prompt:
  `"The user's name is Rohit. They prefer direct, concise responses."`
- Main Agent uses name in conversational responses

**Rules:**
- Identity entries are NEVER auto-deleted
- Inferred values can be overridden by explicit ones (higher confidence wins)
- Credential-shaped values are BLOCKED from insertion (enforced by Memory Data Boundary)

---

### 3.2 Layer 2 — Preference Memory

**Table:** `memory_preferences`

**Categories and examples:**

| Category | Key | Example Value | Source |
|----------|-----|---------------|--------|
| `coding` | `language` | Python 3.11+ | explicit |
| `coding` | `framework` | FastAPI for APIs | explicit |
| `coding` | `style` | Type hints always, docstrings on public functions | inferred |
| `deploy` | `default_target` | Vercel | explicit |
| `deploy` | `branch_convention` | main for prod, dev for staging | observed |
| `communication` | `response_length` | Concise — no verbose explanations unless asked | explicit |
| `communication` | `error_format` | Show the exact error, not a summary | explicit |
| `scheduling` | `meeting_buffer` | 15 min between meetings | inferred |
| `workflow` | `test_before_deploy` | Always run tests before any deploy | explicit |
| `general` | `dark_mode` | true | explicit |

**How it's populated:**
- **Explicit:** "I prefer Python over JavaScript" → immediate INSERT, confidence=1.0
- **Inferred:** User has chosen Python in 8 out of 10 coding tasks → INSERT with confidence=0.8

**How it's used by each agent:**

| Agent | Preferences Read | Effect |
|-------|-----------------|--------|
| Coding Agent | `coding.*` | Default language, framework, style conventions |
| Deploy Agent | `deploy.*` | Default target, branch conventions |
| Calendar Agent | `scheduling.*` | Meeting buffer, preferred times |
| Notes Agent | `general.*` | Storage format preferences |
| Intent Classifier | `communication.*` | Confidence threshold adjustment |
| Prompt Agent | ALL categories | Injects relevant subset into agent prompts |

---

### 3.3 Layer 3 — Behavioral Memory

**Table:** `memory_behavioral`

**How patterns are detected (deterministic, no LLM):**

```python
class PatternObserver:
    """
    Runs after every task completion. Zero LLM calls.
    Uses simple statistical detection, not ML.
    """
    
    def observe(self, completed_task):
        # Time pattern: does this task type cluster at certain hours?
        self._check_time_clustering(
            task_type=completed_task.agent,
            hour=completed_task.completed_at.hour
        )
        
        # Workflow pattern: was this task preceded by the same sequence before?
        self._check_workflow_sequence(
            recent_tasks=self._last_n_tasks(10),
            current=completed_task
        )
        
        # Command pattern: has the user used similar phrasing before?
        self._check_command_frequency(
            intent=completed_task.intent,
            count_threshold=5
        )
    
    def _check_time_clustering(self, task_type, hour):
        """
        If 60%+ of a task type happens within a 2-hour window,
        record it as a time pattern.
        """
        history = db.query(
            "SELECT hour FROM task_completion_times WHERE agent=?",
            task_type
        )
        # Simple mode detection — most common 2-hour window
        window_counts = Counter(h // 2 for h in history)
        most_common_window, count = window_counts.most_common(1)[0]
        
        if count / len(history) > 0.6 and len(history) >= 5:
            self._record_pattern(
                type='time_pattern',
                description=f"User typically runs {task_type} tasks "
                           f"between {most_common_window*2}:00-{most_common_window*2+2}:00",
                confidence=min(0.9, 0.3 + (count / len(history)) * 0.6)
            )
```

**Confidence update formula (Bayesian-inspired):**

```python
def update_confidence(current: float, observation_count: int) -> float:
    """
    Confidence grows logarithmically with observations.
    5 observations → ~0.6
    10 observations → ~0.75
    20 observations → ~0.85
    Never reaches 1.0 (only explicit preferences = 1.0)
    """
    return min(0.95, 0.3 + 0.65 * (1 - 1 / (1 + math.log(observation_count + 1))))
```

**Decay mechanism:**

```python
def decay_check(pattern):
    """
    Run daily (or on session start).
    Patterns not observed in decay_after_days become dormant.
    Dormant patterns are NOT deleted — they reactivate on observation.
    """
    days_since = (now() - pattern.last_seen).days
    if days_since > pattern.decay_after_days:
        pattern.active = 0  # dormant, not deleted
    elif pattern.active == 0 and days_since < pattern.decay_after_days:
        pattern.active = 1  # reactivated!
        pattern.confidence *= 0.7  # but with reduced confidence
```

---

### 3.4 Layer 4 — Project Memory

**Table:** `memory_project`

**How it's populated:**

| Source | When | Example |
|--------|------|---------|
| **Observed** (confidence=0.8) | Coding Agent scans project | `tech_stack: "Python 3.11, FastAPI, SQLite"` |
| **Observed** (confidence=0.8) | Deploy Agent completes a deploy | `deploy_target: "vercel"`, `last_deploy: "2026-08-10"` |
| **Observed** (confidence=0.8) | Test runner output parsed | `test_framework: "pytest"`, `test_command: "pytest tests/"` |
| **Explicit** (confidence=1.0) | User tells MAX | `deploy_target: "my-staging-server.com"` |
| **Inferred** (confidence=0.6) | Pattern from multiple deploys | `deploy_day_preference: "Friday"` |

**Key design decision:** Project memory is keyed by `project_id` (path or canonical name). When the user switches projects, MAX loads that project's memory. When they return to a previous project, all its context is immediately available — no re-learning.

---

### 3.5 Layer 5 — Conversational Memory

**Table:** `memory_conversational`

**Content types captured:**

| Type | Example | Importance |
|------|---------|------------|
| `context` | "User is working on a deadline for Friday" | 0.5 |
| `correction` | "User said 'no, use FastAPI not Flask'" | 0.9 |
| `preference_signal` | "User chose dark mode when given options" | 0.7 |
| `intent_clarification` | "When user says 'push it', they mean deploy to staging" | 0.8 |
| `feedback` | "User said the last response was too long" | 0.8 |

**Promotion rules (from conversational → permanent):**

```python
class MemoryPromotion:
    """
    Runs daily or on-demand.
    Promotes high-importance conversational entries that
    have been observed repeatedly.
    """
    
    PROMOTION_THRESHOLDS = {
        'preference': {
            'min_importance': 0.7,
            'min_sessions': 3,      # seen in 3+ different sessions
            'target_layer': 'memory_preferences'
        },
        'behavioral': {
            'min_importance': 0.6,
            'min_sessions': 5,      # observed 5+ times
            'target_layer': 'memory_behavioral'
        },
        'project': {
            'min_importance': 0.5,
            'min_sessions': 2,      # project context is easier to promote
            'target_layer': 'memory_project'
        }
    }
    
    def promote(self):
        candidates = db.query("""
            SELECT content, content_type, importance,
                   COUNT(DISTINCT session_id) as session_count
            FROM memory_conversational
            WHERE promoted_to IS NULL
              AND importance >= 0.5
            GROUP BY content
            HAVING session_count >= 2
        """)
        
        for candidate in candidates:
            for target, threshold in self.PROMOTION_THRESHOLDS.items():
                if (candidate.importance >= threshold['min_importance']
                    and candidate.session_count >= threshold['min_sessions']):
                    self._promote(candidate, target)
                    break
```

---

## 4. Memory Engine — The Four Sub-Systems

### 4.1 Memory Intake (runs post-interaction)

```
USER INTERACTION COMPLETES
       │
       ▼
┌──────────────────────────────────────────────────────┐
│  EXPLICIT PREFERENCE DETECTOR                          │
│  Pattern: "I prefer X" / "Always do Y" / "My name is Z"│
│  Method: regex + keyword match (zero LLM cost)         │
│  Output: direct INSERT into Layer 1 or 2               │
│  Confidence: 1.0 (user said it explicitly)             │
│                                                        │
│  Patterns matched:                                     │
│    /^(I prefer|I like|I want|always use|never use)/i   │
│    /^(my name is|I'm|I am a|I work at)/i               │
│    /^(don't|stop|please stop) .*(verbose|long|short)/i │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│  PATTERN OBSERVER (deterministic, no LLM)              │
│  Tracks: time clustering, workflow sequences,          │
│  command frequency, project switching patterns         │
│  Method: simple statistics over task_trace data        │
│  Output: UPDATE memory_behavioral (increment count,    │
│          adjust confidence via bayesian update)         │
└────────────────────┬─────────────────────────────────┘
                     │
                     ▼
┌──────────────────────────────────────────────────────┐
│  CONTEXT CAPTURER                                      │
│  Extracts task-relevant context from this interaction   │
│  Method: summarize key facts from the exchange          │
│  Output: INSERT into memory_conversational              │
│  Importance scored by:                                  │
│    - User correction → 0.9                             │
│    - Explicit feedback → 0.8                           │
│    - Intent clarification → 0.8                        │
│    - Preference signal → 0.7                           │
│    - General context → 0.5                             │
└──────────────────────────────────────────────────────┘
```

### 4.2 Memory Retrieval (runs at start of every task)

```python
@dataclass
class MemoryContext:
    """
    Assembled per-task, passed to prompt_agent.py
    for injection into agent-specific prompts.
    """
    identity: dict          # Layer 1: always loaded
    preferences: dict       # Layer 2: filtered by agent category
    patterns: list[dict]    # Layer 3: active, confidence > 0.6
    project: dict           # Layer 4: if task has project context
    recent: list[dict]      # Layer 5: last N entries from current session
    
    def for_prompt(self, agent_type: str) -> str:
        """
        Build a prompt-injectable string from this context.
        Filtered through MemoryDataBoundary before use.
        """
        lines = []
        
        if self.identity.get('name'):
            lines.append(f"User: {self.identity['name']}")
        if self.identity.get('role'):
            lines.append(f"Role: {self.identity['role']}")
        
        # Agent-relevant preferences only
        agent_prefs = {k: v for k, v in self.preferences.items()
                       if k.startswith(agent_type) or k.startswith('general')}
        for key, val in agent_prefs.items():
            lines.append(f"Preference: {key} = {val}")
        
        # Active behavioral patterns relevant to this task
        for pattern in self.patterns:
            lines.append(f"Pattern: {pattern['description']}")
        
        # Project context if available
        if self.project:
            for key, val in self.project.items():
                lines.append(f"Project: {key} = {val}")
        
        return "\n".join(lines)


def retrieve_memory(session_id: str, agent_type: str, 
                    project_id: str = None) -> MemoryContext:
    """
    Assemble a MemoryContext for a specific task.
    Called by the task orchestrator before passing to prompt_agent.
    """
    # Layer 1: Always load all identity
    identity = dict(db.query("SELECT key, value FROM memory_identity"))
    
    # Layer 2: Load preferences relevant to this agent
    category_map = {
        'calendar': ['scheduling', 'general', 'communication'],
        'notes': ['general', 'communication'],
        'coding': ['coding', 'general', 'workflow'],
        'deploy': ['deploy', 'coding', 'workflow', 'general'],
    }
    categories = category_map.get(agent_type, ['general'])
    preferences = dict(db.query(
        "SELECT category || '.' || key, value FROM memory_preferences "
        "WHERE category IN (?) AND confidence > 0.5",
        categories
    ))
    
    # Layer 3: Active behavioral patterns with sufficient confidence
    patterns = db.query(
        "SELECT description, pattern_type, confidence FROM memory_behavioral "
        "WHERE active = 1 AND confidence > 0.6 "
        "ORDER BY confidence DESC LIMIT 10"
    )
    
    # Layer 4: Project-specific memory
    project = {}
    if project_id:
        project = dict(db.query(
            "SELECT key, value FROM memory_project WHERE project_id = ?",
            project_id
        ))
    
    # Layer 5: Recent conversational context from this session
    recent = db.query(
        "SELECT content, content_type, importance FROM memory_conversational "
        "WHERE session_id = ? ORDER BY created_at DESC LIMIT 20",
        session_id
    )
    
    # Log access for audit trail
    for layer in ['identity', 'preference', 'behavioral', 'project', 'conversational']:
        db.execute(
            "INSERT INTO memory_access_log (layer, key_accessed, accessed_by, "
            "purpose, accessed_at) VALUES (?, ?, ?, ?, ?)",
            layer, '*', agent_type, f'task_context_for_{agent_type}', now()
        )
    
    return MemoryContext(
        identity=identity,
        preferences=preferences,
        patterns=patterns,
        project=project,
        recent=recent
    )
```

### 4.3 Memory Promotion Engine

```
Runs: daily at midnight, or triggered by `max memory promote`

SCAN memory_conversational
  WHERE promoted_to IS NULL
  AND importance >= 0.5

GROUP BY content (fuzzy match on meaning, not exact text)

For each group:
  session_count = COUNT(DISTINCT session_id)
  avg_importance = AVG(importance)

  IF content_type = 'correction' AND session_count >= 2:
      → Promote to memory_preferences (user explicitly corrected us twice)
      
  IF content_type = 'preference_signal' AND session_count >= 3:
      → Promote to memory_preferences (implicit preference, well-established)
      
  IF content_type = 'context' AND session_count >= 5:
      → Check if it matches a behavioral pattern type
      → If yes: promote to memory_behavioral
      → If no: leave in conversational (may expire)

  UPDATE memory_conversational
    SET promoted_to = ?, promoted_at = now()
    WHERE entry_id IN (group_ids)
```

### 4.4 Memory Decay Engine

```
Runs: daily, or on session start

-- Dormancy check for behavioral patterns
UPDATE memory_behavioral
SET active = 0
WHERE active = 1
  AND julianday('now') - julianday(last_seen) > decay_after_days;

-- Expiry for conversational memory
DELETE FROM memory_conversational
WHERE expires_at IS NOT NULL
  AND expires_at < datetime('now');

-- Confidence erosion for inferred preferences not reinforced
UPDATE memory_preferences
SET confidence = MAX(0.1, confidence - 0.05)
WHERE source = 'inferred'
  AND julianday('now') - julianday(updated_at) > 60;
  -- Inferred preferences lose 0.05 confidence every 60 days
  -- without reinforcement. At 0.1 they stop appearing in prompts
  -- (below the 0.5 retrieval threshold) but aren't deleted.
```

---

## 5. Integration Points with Existing Pipeline

### 5.1 Where Memory Plugs In

```
User Input arrives
       │
       ▼
INTENT CLASSIFIER ← memory_preferences('communication')
       │              adjusts confidence thresholds and
       │              understands user's domain vocabulary
       │
       ▼
PLANNER ← memory_behavioral('workflow')
       │   predicts likely follow-up tasks and
       │   suggests dependency graphs from past patterns
       │
       ▼
PROMPT AGENT ← MemoryContext (all layers, filtered by agent)
       │        builds agent-specific prompts including:
       │        "User prefers Python 3.11+",
       │        "Project uses FastAPI + SQLite",
       │        "User likes concise error messages"
       │
       ▼
AGENT EXECUTION (unchanged — agents don't directly
       │         access memory tables, they receive
       │         it through the MemoryContext)
       │
       ▼
RECONCILIATION (unchanged)
       │
       ▼
MEMORY INTAKE (runs post-execution)
       │
       ├──► Explicit preference detected? → Layer 2
       ├──► Pattern reinforced? → Layer 3 update
       ├──► Project context learned? → Layer 4
       └──► Conversational context → Layer 5
```

### 5.2 Integration with Data Boundary Policy

```python
class MemoryDataBoundary:
    """
    Applied between MemoryContext and LLM API calls.
    Extends data_boundary.py specifically for memory content.
    """
    
    # Keys that are NEVER sent to external LLM APIs
    BLOCKED_IDENTITY_KEYS = {
        'api_key', 'password', 'token', 'secret',
        'credential', 'ssn', 'account_number'
    }
    
    # Keys that are safe to send
    SAFE_IDENTITY_KEYS = {
        'name', 'role', 'timezone', 'language',
        'skill_level', 'communication_style'
    }
    
    def sanitize_for_llm(self, context: MemoryContext) -> MemoryContext:
        """
        Returns a sanitized copy safe for LLM API inclusion.
        """
        sanitized = copy.deepcopy(context)
        
        # Identity: whitelist approach (only send known-safe keys)
        sanitized.identity = {
            k: v for k, v in context.identity.items()
            if k in self.SAFE_IDENTITY_KEYS
        }
        
        # Preferences: send as-is (user intent, not sensitive data)
        # but strip any values matching credential patterns
        for key, value in list(sanitized.preferences.items()):
            if self._looks_like_credential(value):
                del sanitized.preferences[key]
        
        # Behavioral: send descriptions only (human-readable summaries)
        # never send raw evidence (contains task_ids, timestamps)
        sanitized.patterns = [
            {'description': p['description']}
            for p in context.patterns
        ]
        
        # Project: strip file paths and potential secrets
        sanitized.project = {
            k: v for k, v in context.project.items()
            if k not in ('full_path', 'env_file', 'credentials')
            and not self._looks_like_credential(v)
        }
        
        # Conversational: only current session, last 5 entries
        sanitized.recent = context.recent[:5]
        
        return sanitized
```

---

## 6. CLI Commands

```bash
# View all memory
max memory show                              # all layers, summarized
max memory show --layer identity             # identity only
max memory show --layer preferences          # preferences only
max memory show --layer behavioral           # active patterns
max memory show --layer behavioral --all     # include dormant patterns
max memory show --project myapp              # project-specific memory

# Set memory explicitly
max memory set identity name "Rohit"
max memory set identity role "Cybersecurity Engineer"
max memory set pref coding.language "Python 3.11+"
max memory set pref deploy.default_target "Vercel"
max memory set pref communication.style "concise"

# Remove memory
max memory forget identity name              # delete one identity key
max memory forget pref coding.language       # delete one preference
max memory forget --layer conversational --older-than 30d  # prune old entries
max memory forget --layer behavioral --dormant             # delete dormant patterns

# Memory administration
max memory promote                           # run promotion engine now
max memory decay                             # run decay engine now
max memory stats                             # layer sizes, pattern counts, access frequency
max memory export > memory_backup.json       # export all memory as JSON
max memory import memory_backup.json         # import from backup

# Audit
max memory audit --last 50                   # last 50 memory access log entries
max memory audit --layer preference --llm-only  # what prefs were sent to LLM APIs
```

---

## 7. Build Order — Where This Fits

From [01_BACKEND_WIRING_ORDER.md](file:///e:/JARVIS-PLAN/files/implementation-roadmap/01_BACKEND_WIRING_ORDER.md):

The Memory Engine is **Layer 1.5** — after Security Envelope (Layer 1),
before Task Infrastructure (Layer 2). It has no dependency on the task
system, but the task system benefits from reading memory context.

```
Layer 0: state_db, schema, kill_switch         ← FOUNDATION
Layer 1: vault, data_boundary                  ← SECURITY
Layer 1.5: memory_engine                       ← MEMORY (NEW)
Layer 2: errors, lifecycle, queue, snapshot     ← TASK INFRA
Layer 3: locks, watchdog, reconciliation       ← SYNC
Layer 4: classifier, permissions, planner      ← ROUTING
Layer 5: agents                                ← BUSINESS LOGIC
Layer 6: orchestrator, CLI                     ← ASSEMBLY
```

**Module specification:**

```
┌─────────────────────────────────────────────────────────┐
│  1.5A. memory_engine.py — Core memory system             │
│      Wire: retrieve_memory(session, agent, project)      │
│            store_preference(category, key, value, source)│
│            observe_pattern(type, evidence)                │
│            MemoryContext dataclass                        │
│      Imports: state_db                                    │
│      Gate: set identity name="Test", retrieve it,        │
│            confirm present in MemoryContext.identity      │
├─────────────────────────────────────────────────────────┤
│  1.5B. memory_data_boundary.py — Privacy filter          │
│      Wire: sanitize_for_llm(MemoryContext) → clean copy  │
│      Imports: memory_engine, data_boundary                │
│      Gate: credential-shaped value in identity →          │
│            never appears in sanitized output              │
├─────────────────────────────────────────────────────────┤
│  1.5C. memory_promotion.py — Promotion engine            │
│      Wire: promote() — daily job                         │
│      Imports: memory_engine, state_db                     │
│      Gate: conversational entry with importance>0.7       │
│            seen in 3+ sessions → appears in preferences   │
├─────────────────────────────────────────────────────────┤
│  1.5D. memory_decay.py — Decay engine                    │
│      Wire: decay() — daily job or on session start        │
│      Imports: memory_engine, state_db                     │
│      Gate: pattern not seen in 30 days → active=0         │
└─────────────────────────────────────────────────────────┘
```

---

## 8. Wiring Diagram

```
memory_engine.py ──reads/writes──► memory_* tables in max_state.db
       │
       ├──► MemoryContext assembled per task
       │         │
       │         ▼
       │    memory_data_boundary.py ──sanitizes──► safe for LLM
       │         │
       │         ▼
       │    prompt_agent.py ──injects into──► agent prompts
       │
       ├──► PatternObserver ──runs after──► every task completion
       │         │
       │         ▼
       │    memory_behavioral table (UPDATE observation_count, confidence)
       │
       ├──► memory_promotion.py ──runs daily──► promotes entries upward
       │
       └──► memory_decay.py ──runs daily──► marks dormant, erodes confidence
```

---

## 9. Acceptance Criteria (Gate Tests)

| Test | Verifies | Pass Condition |
|------|----------|----------------|
| Set identity, retrieve it | Layer 1 CRUD | `max memory set identity name "Test"` → appears in `retrieve_memory().identity` |
| Set preference, verify in prompt | Layer 2 → Prompt Agent | Set `coding.language = Python` → Coding Agent prompt includes "User prefers Python" |
| Behavioral detection | Layer 3 observation | Complete 5 calendar tasks at 10am → pattern "User schedules at 10am" appears with confidence > 0.5 |
| Project memory | Layer 4 per-project | Scan a Python project → `tech_stack: "Python"` stored under that project_id |
| Conversational promotion | Layer 5 → Layer 2 | User says "I prefer dark mode" in 3 sessions → promoted to `memory_preferences` |
| Decay | Layer 3 dormancy | Pattern last seen 31 days ago → `active = 0` after decay runs |
| Privacy | Data Boundary | Set `identity.api_key = "sk-..."` → NEVER appears in `sanitize_for_llm()` output |
| Memory CLI | All layers | `max memory show`, `set`, `forget`, `export`, `import` all work correctly |
| Memory audit | Access log | After retrieval, `memory_access_log` contains entries for all accessed layers |

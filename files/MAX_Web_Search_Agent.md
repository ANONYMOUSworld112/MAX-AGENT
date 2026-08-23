# MAX — Web Search Agent (Real-Time Info via Google/Gemini Grounding)
### Explicit "from internet" trigger, honest quota handling

---

## 1. The Rule You Asked For

Web search should never fire silently. It only activates when the request
is **explicitly** about live/current information — not as a fallback for
things the agent could just answer or is unsure about.

```
Trigger phrases / intent signals:
  "from internet", "latest", "current", "today", "right now",
  "what's happening with", "check online", "search for"

If NONE of these are present → Web Search Agent is never invoked,
even if the Main Agent isn't fully confident in its own answer.
```

This is the same discipline as the Deploy Agent's confirm gate — a
dedicated, narrow trigger instead of the Main Agent deciding on its own
that "this seems like it needs a search."

---

## 2. Routing Addition

```
Intent Classifier
    │
    ├── contains "from internet" / real-time signal?
    │        │
    │       YES → Web Search Agent
    │        │
    │       NO  → normal agent routing (Calendar/Notes/Coding/Deploy),
    │             answered from the model's own knowledge
```

---

## 3. Web Search Agent — Internal Flow

```
Query comes in (flagged "from internet")
        │
        ▼
┌─────────────────────────┐
│  Quota Check              │  ← check local usage counter FIRST
│  (daily/monthly count)    │
└─────────────────────────┘
        │
   under quota?          over quota?
        │                    │
        ▼                    ▼
  Call Gemini API      Tell user plainly:
  with Google Search    "search quota reached for today,
  grounding tool         here's my best answer without
        │                live data" — never fail silently
        ▼
  Grounded response
  (includes source links)
        │
        ▼
  Main Agent reads full grounded context,
  summarizes for the user, cites sources
        │
        ▼
  Log usage count + 1 → Outcome Tracker
```

---

## 4. Quota Handling (this is the part that actually matters)

Don't build this assuming unlimited free calls — build it so hitting the
limit degrades gracefully instead of breaking:

```python
class WebSearchAgent:
    DAILY_LIMIT = 1500      # verify actual current number in AI Studio,
    MONTHLY_GROUNDING_LIMIT = 5000   # these change — don't hardcode and forget

    def search(self, query: str):
        if self.usage_tracker.today_count() >= self.DAILY_LIMIT:
            return {
                "grounded": False,
                "message": "Daily search quota reached — answering from "
                            "existing knowledge instead, may not be current."
            }

        response = self.gemini_client.generate(
            query,
            tools=["google_search_retrieval"]
        )
        self.usage_tracker.increment()
        return {
            "grounded": True,
            "content": response.text,
            "sources": response.grounding_metadata.sources
        }
```

The `usage_tracker` here is the same Outcome Tracker component from the v2
design — one more reason that component earns its place instead of being
a "nice to have."

---

## 5. Honest Notes Before You Build This

- **Verify the current free-tier numbers yourself before relying on them** —
  they've changed multiple times in 2026 already, and two sources
  disagree on whether Gemini CLI's old generous free tier even still
  exists. Check `aistudio.google.com` directly for your project's live
  limits rather than trusting any blog post, including this one.
- **Don't route personal/sensitive queries through free-tier grounding** —
  free tier usage may be used by Google to improve their products. Fine
  for "what's the weather" or "latest news on X." Not the place to route
  anything involving your calendar, projects, or personal data — that
  stays with your primary LLM provider under whatever data terms you
  already have there.
- **This is a good fit for a narrow set of daily-update use cases** — news,
  prices, scores, "is X still true" checks — not a general-purpose search
  replacement for everything the Main Agent is unsure about.

---

## 6. Where This Fits in the v1 Scope

This is a reasonable 5th agent to add once your 4-agent v1 (Calendar,
Notes, Coding, Deploy) is running reliably — it's low-risk (read-only,
no side effects) and genuinely useful for a daily-brief style assistant.
Good next addition, in the right order.

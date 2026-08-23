# MAX OS — API Contract

| | |
|---|---|
| **Module** | MAX OS Core & Computer-Use Node |
| **Status** | **ACTIVE & PRODUCTION READY** |
| **Transport** | HTTP/JSON over loopback / LAN |
| **Prefix** | `/v1/` |

---

## 1. Endpoints

### `POST /v1/tasks`
Submit a new task.

```json
// Request
{
  "task_id": "uuid",
  "user_request": "string",
  "goal": "string",
  "context": {
    "prior_task_ids": ["uuid"]
  }
}

// Response — 202 Accepted
{
  "task_id": "uuid",
  "status": "QUEUED"
}
```

### `GET /v1/tasks/{task_id}`
Poll task state.

```json
{
  "task_id": "uuid",
  "status": "RUNNING",
  "current_step": 3,
  "completed_steps": [ /* Step */ ],
  "plan": [ /* Step */ ],
  "last_verification": { /* VerificationResult */ }
}
```

### `POST /v1/tasks/{task_id}/control`
User runtime interrupts (STOP / PAUSE / RESUME / CANCEL / SKIP / RETRY).

```json
{ "action": "STOP" | "PAUSE" | "RESUME" | "CANCEL" | "SKIP" | "RETRY" }
```

### `POST /v1/tasks/{task_id}/confirm`
Resolve `WAITING_FOR_USER` state raised by FRIDAY-tier boundary or Ultron-lockout gate.

```json
// Request
{
  "step_id": "string",
  "confirmed": true,
  "user_note": "string | null"
}

// Response
{ "task_id": "uuid", "status": "RUNNING" }
```

### `GET /v1/tasks/{task_id}/observability`
Live state for HUD and dashboard: screenshot reference, active app, detected elements, current agent, confidence, last tool call, last verification result.

### `GET /v1/health`
Health and readiness check.

```json
{ "status": "ready", "active_tasks": 0 }
```

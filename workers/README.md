# Workers

`workers/` contains task-specific workers for calendar events, reminders, and media playback. The modules provide the work logic used by the broader assistant; they are separate from the action handlers that expose user-facing tool calls.

The current checkout includes `calendar_worker.py`, `reminder_worker.py`, and `media_worker.py`. Their operation depends on the relevant host services and configuration. No worker execution was performed for this documentation update.

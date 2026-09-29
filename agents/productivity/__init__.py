"""Founder Productivity Cluster (Cluster 3) — 8 Agents.

Agents:
14. EmailAgent (Tier 2)
15. CalendarAgent (Tier 1)
16. CommsAgent (Tier 2)
17. ResearchAgent (Tier 0)
18. FileOrganizer (Tier 1)
19. NotesAgent (Tier 0)
20. TaskTracker (Tier 0)
21. MeetingPrep (Tier 0)
"""

from agents.productivity.email_agent import EmailAgent
from agents.productivity.calendar_agent import CalendarAgent
from agents.productivity.comms_agent import CommsAgent
from agents.productivity.research_agent import ResearchAgent
from agents.productivity.file_organizer import FileOrganizer
from agents.productivity.notes_agent import NotesAgent
from agents.productivity.task_tracker import TaskTracker
from agents.productivity.meeting_prep import MeetingPrep

__all__ = [
    "EmailAgent",
    "CalendarAgent",
    "CommsAgent",
    "ResearchAgent",
    "FileOrganizer",
    "NotesAgent",
    "TaskTracker",
    "MeetingPrep",
]

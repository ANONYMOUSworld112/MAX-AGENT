import pytest
from unittest.mock import patch
from agents.base import AgentInput
from agents.router import AgentRegistry
from agents.productivity import (
    EmailAgent,
    CalendarAgent,
    CommsAgent,
    ResearchAgent,
    FileOrganizer,
    NotesAgent,
    TaskTracker,
    MeetingPrep,
)


def test_cluster_productivity_agents_instantiation_and_tiers():
    agents = [
        (EmailAgent(), "EmailAgent", 2),
        (CalendarAgent(), "CalendarAgent", 1),
        (CommsAgent(), "CommsAgent", 2),
        (ResearchAgent(), "ResearchAgent", 0),
        (FileOrganizer(), "FileOrganizer", 1),
        (NotesAgent(), "NotesAgent", 0),
        (TaskTracker(), "TaskTracker", 0),
        (MeetingPrep(), "MeetingPrep", 0),
    ]

    registry = AgentRegistry()

    for agent, expected_name, expected_tier in agents:
        assert agent.name == expected_name
        assert agent.permission_tier == expected_tier
        tool_def = agent.get_tool_definition()
        assert tool_def["name"] == expected_name.lower()
        assert "parameters" in tool_def

        registry.register(agent)
        retrieved = registry.get(expected_name)
        assert retrieved is not None
        assert retrieved.name == expected_name


def test_cluster_productivity_execution_cycle(tmp_path):
    # 1. EmailAgent
    email = EmailAgent()
    out_email = email.run(AgentInput(
        task_id="prod_1",
        task_description="Send quarterly review summary",
        parameters={"action": "send", "to": "board@company.com", "subject": "Q3 Update"},
    ))
    assert out_email.success is True
    assert out_email.artifacts["requires_confirmation"] is True

    # 2. CalendarAgent
    cal = CalendarAgent()
    out_cal = cal.run(AgentInput(
        task_id="prod_2",
        task_description="Schedule sprint planning",
        parameters={"title": "Sprint 42 Planning", "start_time": "2026-10-05T09:00:00", "duration_minutes": 60},
    ))
    assert out_cal.success is True
    assert out_cal.artifacts["status"] == "CONFIRMED"

    # 3. CommsAgent
    comms = CommsAgent()
    out_comms = comms.run(AgentInput(
        task_id="prod_3",
        task_description="Notify team about release",
        parameters={"platform": "slack", "channel": "deployments", "message": "v2.0 deployed successfully!"},
    ))
    assert out_comms.success is True
    assert out_comms.artifacts["requires_confirmation"] is True

    # 4. ResearchAgent (mock web_search to avoid network/key dependence)
    with patch("actions.web_search.web_search", return_value="Mocked search result for quantum computing"):
        research = ResearchAgent()
        out_res = research.run(AgentInput(
            task_id="prod_4",
            task_description="Research quantum computing architectures",
            parameters={"query": "quantum computing architectures"},
        ))
        assert out_res.success is True
        assert "Mocked search result" in out_res.result

    # 5. FileOrganizer
    test_dir = tmp_path / "files"
    test_dir.mkdir()
    (test_dir / "sample1.txt").write_text("sample 1", encoding="utf-8")
    (test_dir / "sample2.py").write_text("sample 2", encoding="utf-8")

    org = FileOrganizer()
    out_org = org.run(AgentInput(
        task_id="prod_5",
        task_description="Scan and organize documents",
        parameters={"action": "scan", "directory": str(test_dir)},
    ))
    assert out_org.success is True
    assert out_org.artifacts["matched_files"] == 2

    # 6. NotesAgent
    notes = NotesAgent()
    out_notes = notes.run(AgentInput(
        task_id="prod_6",
        task_description="Record architectural decision",
        parameters={"title": "ADR 001 - Agent Router", "tags": ["architecture", "adr"]},
    ))
    assert out_notes.success is True
    assert "ADR 001" in out_notes.artifacts["note_content"]

    # 7. TaskTracker
    tracker = TaskTracker()
    out_task = tracker.run(AgentInput(
        task_id="prod_7",
        task_description="Track release verification task",
        parameters={"task": "Verify staging environment", "priority": "high"},
    ))
    assert out_task.success is True
    assert out_task.artifacts["priority"] == "high"

    # 8. MeetingPrep
    meeting = MeetingPrep()
    out_meet = meeting.run(AgentInput(
        task_id="prod_8",
        task_description="Prep for investor sync",
        parameters={"title": "Series A Discussion", "attendees": ["Founder", "VC Partner"]},
    ))
    assert out_meet.success is True
    assert "Series A Discussion" in out_meet.artifacts["briefing_doc"]

"""
Unit tests for SkillLoader & Declarative Skills (Task 10.1)
===========================================================

Covers:
- Discovery of SKILL.md packages
- Parsing of YAML frontmatter metadata and verification specs
- Execution of discovered skill through ExecutionGateway
"""

from pathlib import Path
import pytest

from core.contracts import ChannelTrust, VerificationOutcome
from core.gateway import ExecutionGateway
from core.skill_loader import SkillLoader, SkillPackage


def test_discover_skills():
    loader = SkillLoader()
    skills = loader.list_skills()
    assert len(skills) >= 2

    open_app = loader.get_skill("open_application")
    assert open_app is not None
    assert open_app.name == "open_application"
    assert open_app.action == "open_app"
    assert "Launches an application" in open_app.description
    assert open_app.verification.get("verify") is True

    play_music = loader.get_skill("play_music")
    assert play_music is not None
    assert play_music.name == "play_music"
    assert "query" in play_music.parameters_schema


def test_execute_skill_through_gateway():
    loader = SkillLoader()
    gw = ExecutionGateway()

    # Register handler for open_app that returns verified state
    calls = []

    def mock_app_handler(action, params):
        calls.append((action, params))
        return {"launched": True, "app": params.get("app_name"), "verified": True}

    gw.register_handler("open_app", mock_app_handler)

    result = loader.execute_skill(
        skill_name="open_application",
        parameters={"app_name": "notepad"},
        gateway=gw,
        channel_trust=ChannelTrust.TRUSTED,
    )

    assert result.success is True
    assert result.verification_outcome == VerificationOutcome.SUCCESS
    assert len(calls) == 1
    assert calls[0][0] == "open_app"
    assert calls[0][1]["app_name"] == "notepad"
    assert calls[0][1]["verify"] is True

"""
Skill Loader & Discovery System (Task 10.1)
===========================================

Discovers and loads modular skill packages from `skills/<name>/SKILL.md`.
Skills define declarative tools, parameter schemas, pre/post-conditions,
and verification rules executed through the ExecutionGateway.

Master Spec References:
  - Section 1-P (Preservation & Extensibility)
  - docs/evolution/CLAUDE_STYLE_COMPARISON.md §3
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import yaml

from core.contracts import ActionRequest, ActionResult, ChannelTrust
from core.gateway import ExecutionGateway

logger = logging.getLogger("max.skills")

DEFAULT_SKILLS_DIR = Path(__file__).resolve().parent.parent / "skills"


@dataclass
class SkillPackage:
    """A modular agentic skill package defined by SKILL.md."""
    name: str
    description: str
    version: str = "1.0.0"
    action: str = ""
    parameters_schema: Dict[str, Any] = field(default_factory=dict)
    preconditions: List[str] = field(default_factory=list)
    postconditions: List[str] = field(default_factory=list)
    verification: Dict[str, Any] = field(default_factory=dict)
    instructions: str = ""
    skill_dir: Path = field(default_factory=Path)


class SkillLoader:
    """
    Discovers, validates, and dispatches declarative skills.
    """

    def __init__(self, skills_dir: Optional[Union[str, Path]] = None) -> None:
        self.skills_dir = Path(skills_dir) if skills_dir else DEFAULT_SKILLS_DIR
        self._skills: Dict[str, SkillPackage] = {}
        self.refresh()

    def refresh(self) -> int:
        """Discovers and reloads all skill packages from the skills directory."""
        self._skills.clear()
        if not self.skills_dir.exists():
            return 0

        count = 0
        for skill_path in self.skills_dir.iterdir():
            if not skill_path.is_dir():
                continue

            md_file = skill_path / "SKILL.md"
            if not md_file.exists():
                continue

            try:
                pkg = self._parse_skill_file(md_file)
                if pkg:
                    self._skills[pkg.name] = pkg
                    count += 1
            except Exception as exc:
                logger.warning("Failed to load skill at %s: %s", skill_path, exc)

        logger.info("SkillLoader discovered %d skills in %s", count, self.skills_dir)
        return count

    def _parse_skill_file(self, md_path: Path) -> Optional[SkillPackage]:
        """Parses a SKILL.md file with YAML frontmatter."""
        text = md_path.read_text(encoding="utf-8")
        if not text.startswith("---"):
            return None

        parts = text.split("---", 2)
        if len(parts) < 3:
            return None

        frontmatter_str = parts[1]
        body = parts[2].strip()

        data = yaml.safe_load(frontmatter_str)
        if not isinstance(data, dict):
            return None

        name = data.get("name")
        description = data.get("description", "")
        if not name or not description:
            return None

        metadata = data.get("metadata", {})
        if not isinstance(metadata, dict):
            metadata = {}
        return SkillPackage(
            name=name,
            description=description,
            version=str(data.get("version", metadata.get("version", "1.0.0"))),
            action=data.get("action", metadata.get("action", name)),
            parameters_schema=data.get("parameters", metadata.get("parameters", {})),
            preconditions=data.get("preconditions", metadata.get("preconditions", [])),
            postconditions=data.get("postconditions", metadata.get("postconditions", [])),
            verification=data.get("verification", metadata.get("verification", {})),
            instructions=body,
            skill_dir=md_path.parent,
        )

    def get_skill(self, name: str) -> Optional[SkillPackage]:
        return self._skills.get(name)

    def list_skills(self) -> List[SkillPackage]:
        return list(self._skills.values())

    def execute_skill(
        self,
        skill_name: str,
        parameters: Dict[str, Any],
        gateway: ExecutionGateway,
        channel_trust: ChannelTrust = ChannelTrust.TRUSTED,
    ) -> ActionResult:
        """
        Dispatches a skill through the ExecutionGateway using its configured action and verification spec.
        """
        skill = self.get_skill(skill_name)
        if not skill:
            raise KeyError(f"Skill '{skill_name}' not found.")

        # Merge parameters with verification spec
        merged_params = dict(parameters)
        if skill.verification:
            merged_params.update(skill.verification)
            merged_params["verify"] = True

        action_name = skill.action or skill.name
        req = ActionRequest(
            action=action_name,
            parameters=merged_params,
            channel_trust=channel_trust,
        )
        return gateway.execute(req)

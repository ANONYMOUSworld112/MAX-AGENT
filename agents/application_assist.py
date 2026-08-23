"""
MAX OS — Application-Assist Agent (Tier 2).
Drafts job application responses, tailored resumes, and cover letters.
Decision D8 & Principle #2: NEVER auto-submits to job platforms (LinkedIn ToS / safety policy).
Auto-submits are strictly blocked.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.kill_switch import get_kill_switch, require_armed


class AutoSubmitForbiddenError(Exception):
    """Raised when an attempt to auto-submit an application is made."""
    pass


# Alias for compatibility
AutoSubmitBlockedError = AutoSubmitForbiddenError


@dataclass
class ApplicationDraft:
    job_title: str
    company: str
    cover_letter: str
    tailored_bullets: List[str] = field(default_factory=list)
    custom_qna: Dict[str, str] = field(default_factory=dict)
    auto_submitted: bool = False


class ApplicationAssistAgent:
    """
    Tier 2 Application-Assist Agent.
    Assists in drafting personalized application materials.
    Hard rule: Never performs automated submission.
    """

    def draft_application(
        self,
        job_title: str,
        company: str,
        job_description: str,
        user_experience: str,
        custom_questions: Optional[List[str]] = None,
    ) -> ApplicationDraft:
        """Drafts tailored application materials for user review."""
        require_armed(get_kill_switch())

        # Generate cover letter draft
        cover_letter = (
            f"Dear Hiring Team at {company},\n\n"
            f"I am writing to express my strong interest in the {job_title} role. "
            f"With extensive background in {user_experience[:80]}..., I am confident in delivering immediate value.\n\n"
            f"Sincerely,\nCandidate"
        )

        # Tailored resume bullet points
        bullets = [
            f"Engineered production-grade systems aligning with {job_title} requirements.",
            f"Demonstrated deep expertise in core responsibilities outlined for {company}.",
        ]

        qna = {}
        if custom_questions:
            for q in custom_questions:
                qna[q] = f"Draft answer based on candidate experience for: {q}"

        return ApplicationDraft(
            job_title=job_title,
            company=company,
            cover_letter=cover_letter,
            tailored_bullets=bullets,
            custom_qna=qna,
            auto_submitted=False,
        )

    def submit_application(self, draft: ApplicationDraft, platform: str = "linkedin") -> None:
        """
        Hard-blocked operation per Decision D8.
        Automated submission violates safety policy and platform ToS.
        """
        raise AutoSubmitForbiddenError(
            f"Automated submission to {platform} is forbidden by Decision D8 and platform Terms of Service. "
            "Applications must be reviewed and submitted manually by the user."
        )

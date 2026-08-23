"""
MAX OS — Document Agent (Tier 2).
Generates formatted reports, documentation, PDF/Markdown presentations, and briefs.
Permission: auto for drafts, confirm for final overwrite.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

from core.kill_switch import get_kill_switch, require_armed


@dataclass
class DocumentSection:
    title: str
    content: str


@dataclass
class DocumentResult:
    title: str
    doc_type: str
    content: str
    file_path: Optional[str] = None
    sections_count: int = 0


class DocumentAgent:
    """
    Tier 2 Document Agent.
    Creates structured documents, briefs, and presentation slides.
    """

    def generate_document(
        self,
        title: str,
        sections: List[DocumentSection],
        doc_type: str = "report",
        output_path: Optional[Path | str] = None,
    ) -> DocumentResult:
        """Generates a structured document formatted in Markdown or text."""
        require_armed(get_kill_switch())

        lines = [f"# {title}", f"*Document Type: {doc_type.upper()}*", "---", ""]

        for s in sections:
            lines.append(f"## {s.title}")
            lines.append(s.content)
            lines.append("")

        full_content = "\n".join(lines)
        file_p = None

        if output_path:
            p = Path(output_path).resolve()
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_text(full_content, encoding="utf-8")
            file_p = str(p)

        return DocumentResult(
            title=title,
            doc_type=doc_type,
            content=full_content,
            file_path=file_p,
            sections_count=len(sections),
        )

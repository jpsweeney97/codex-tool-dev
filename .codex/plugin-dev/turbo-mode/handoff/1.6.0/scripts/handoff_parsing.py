"""Shared handoff parsing utilities.

Provides frontmatter extraction, section splitting, and full handoff
parsing. Used by search.py and distill.py. quality_check.py has its
own implementation (different heading normalization).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Section:
    heading: str
    level: int
    content: str


@dataclass(frozen=True)
class HandoffFile:
    path: str
    frontmatter: dict[str, str]
    sections: list[Section]


def parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    """Extract YAML frontmatter from markdown text.

    Returns (frontmatter_dict, remaining_text). Handles simple key: value
    pairs and quoted strings. Does not depend on PyYAML.

    Multiline YAML values (e.g., files: lists) are silently skipped —
    only single-line key: value pairs are extracted.
    """
    if not text.startswith("---"):
        return {}, text

    end = text.find("\n---", 3)
    if end == -1:
        return {}, text

    fm_text = text[4:end]
    remaining = text[end + 4:]

    frontmatter: dict[str, str] = {}
    for line in fm_text.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        match = re.match(r'^(\w[\w-]*)\s*:\s*(.+)$', line)
        if match:
            key = match.group(1)
            value = match.group(2).strip()
            if (value.startswith('"') and value.endswith('"')) or (
                value.startswith("'") and value.endswith("'")
            ):
                value = value[1:-1]
            frontmatter[key] = value

    return frontmatter, remaining


def parse_sections(text: str) -> list[Section]:
    """Split markdown text into ## sections.

    Each section includes everything from its ## heading until the next
    ## heading or EOF. ### subsections are included within their parent.
    Code-fenced regions (both backtick ``` and tilde ~~~) are tracked to
    avoid treating ## lines inside fences as section boundaries. The
    heading line itself is NOT included in section.content to avoid
    duplication.
    """
    sections: list[Section] = []
    lines = text.splitlines(keepends=True)
    current_heading = ""
    current_lines: list[str] = []
    inside_fence = False
    fence_marker = ""  # Track which fence type opened (``` or ~~~)

    for line in lines:
        stripped = line.rstrip()
        if not inside_fence and (stripped.startswith("```") or stripped.startswith("~~~")):
            inside_fence = True
            fence_marker = stripped[:3]
        elif inside_fence and stripped.startswith(fence_marker):
            inside_fence = False
            fence_marker = ""
        if not inside_fence and line.startswith("## "):
            if current_heading:
                content = "".join(current_lines).strip()
                sections.append(Section(
                    heading=current_heading,
                    level=2,
                    content=content,
                ))
            current_heading = line.strip()
            current_lines = []
        elif current_heading:
            current_lines.append(line)

    if current_heading:
        content = "".join(current_lines).strip()
        sections.append(Section(
            heading=current_heading,
            level=2,
            content=content,
        ))

    return sections


def section_name(heading: str) -> str:
    """Strip the '## ' prefix from a Section heading.

    Section.heading stores headings with prefix (e.g., '## Open Questions').
    This returns the bare name (e.g., 'Open Questions').
    """
    if heading.startswith("## "):
        return heading[3:].strip()
    return heading.strip()


def parse_handoff(path: Path) -> HandoffFile:
    """Parse a handoff markdown file into structured data."""
    text = path.read_text(encoding="utf-8")
    frontmatter, body = parse_frontmatter(text)
    sections = parse_sections(body)
    return HandoffFile(path=str(path), frontmatter=frontmatter, sections=sections)

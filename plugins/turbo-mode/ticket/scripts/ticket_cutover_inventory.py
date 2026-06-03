"""Diagnostic cutover inventory for pre-cutover Ticket files.

This module is intentionally read-only. It is a diagnostic cutover inventory
that explains old fenced-YAML ticket records during the ADR 0006 source/repo
cutover without making them valid normal Ticket records. Its inputs are
diagnostic/cutover evidence only, not normal Ticket runtime input.

Sunset: archive or delete this helper after the ADR 0006 source/repo cutover
closeout records that no non-normalized active `docs/tickets/*.md` files remain.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.ticket_parse import (
    SECTION_RENAMES,
    extract_fenced_yaml,
    extract_sections,
    parse_yaml_block,
)
from scripts.ticket_target_schema import (
    LEGACY_PRIORITY_MAP,
    TARGET_FRONTMATTER_FIELDS,
    TARGET_ID_RE,
    TARGET_SECTIONS_REQUIRED,
)

_DATE_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


@dataclass(frozen=True)
class CutoverInventory:
    """Read-only description of a legacy ticket's target-normalization needs."""

    source_path: Path
    current_id: str
    proposed_target_path: Path
    metadata_container: str
    unknown_keys: tuple[str, ...]
    status_mapping_needed: str | None
    priority_mapping_needed: str | None
    missing_required_sections: tuple[str, ...]
    optional_sections_to_preserve: tuple[str, ...]
    blocked_by: tuple[str, ...]
    state: str


def _renamed_sections(text: str) -> dict[str, str]:
    sections = extract_sections(text)
    renamed: dict[str, str] = {}
    for name, body in sections.items():
        target_name = SECTION_RENAMES.get(name, name)
        if target_name in renamed:
            renamed[target_name] += "\n\n" + body
        else:
            renamed[target_name] = body
    return renamed


def _proposed_ticket_id(frontmatter: dict[str, Any]) -> str:
    current_id = str(frontmatter.get("id", ""))
    if TARGET_ID_RE.fullmatch(current_id):
        return current_id

    raw_date = str(frontmatter.get("date", ""))
    match = _DATE_RE.match(raw_date)
    if match is None:
        return ""
    year, month, day = match.groups()
    return f"T-{year}{month}{day}-01"


def _mapping_needed(value: object, mapping: dict[str, str]) -> str | None:
    if not isinstance(value, str):
        return None
    mapped = mapping.get(value)
    if mapped is None:
        return None
    return f"{value}->{mapped}"


def inspect_legacy_ticket_for_cutover(path: Path) -> CutoverInventory:
    """Inspect a legacy ticket and describe its deterministic cutover needs."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise ValueError(
            f"cutover inventory failed: cannot read file. Got: {str(path)!r:.100}"
        ) from exc

    yaml_text = extract_fenced_yaml(text)
    if yaml_text is None:
        raise ValueError(
            f"cutover inventory failed: fenced YAML block not found. Got: {str(path)!r:.100}"
        )
    frontmatter = parse_yaml_block(yaml_text)
    if frontmatter is None:
        raise ValueError(
            f"cutover inventory failed: invalid fenced YAML. Got: {str(path)!r:.100}"
        )

    current_id = str(frontmatter.get("id", ""))
    proposed_id = _proposed_ticket_id(frontmatter)
    proposed_target_path = path.parent / f"{proposed_id}.md" if proposed_id else path.parent

    sections = _renamed_sections(text)
    missing = tuple(
        section for section in TARGET_SECTIONS_REQUIRED if not sections.get(section, "").strip()
    )
    optional_sections = tuple(
        sorted(section for section in sections if section not in TARGET_SECTIONS_REQUIRED)
    )
    unknown_keys = tuple(
        sorted(key for key in frontmatter if key not in TARGET_FRONTMATTER_FIELDS)
    )
    blocked_by_value = frontmatter.get("blocked_by", [])
    blocked_by = (
        tuple(str(item) for item in blocked_by_value)
        if isinstance(blocked_by_value, list)
        else ()
    )
    state = (
        "ready_to_apply" if current_id and proposed_id and "Problem" not in missing else "blocked"
    )

    return CutoverInventory(
        source_path=path,
        current_id=current_id,
        proposed_target_path=proposed_target_path,
        metadata_container="fenced_yaml",
        unknown_keys=unknown_keys,
        status_mapping_needed=_mapping_needed(frontmatter.get("status"), {"deferred": "open"}),
        priority_mapping_needed=_mapping_needed(
            frontmatter.get("priority"),
            LEGACY_PRIORITY_MAP,
        ),
        missing_required_sections=missing,
        optional_sections_to_preserve=optional_sections,
        blocked_by=blocked_by,
        state=state,
    )

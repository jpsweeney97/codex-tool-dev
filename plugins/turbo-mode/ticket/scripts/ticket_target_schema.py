"""Target Ticket schema constants and mechanical validation."""

from __future__ import annotations

import datetime
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

TARGET_FRONTMATTER_REQUIRED = ("id", "title", "status", "priority")
TARGET_FRONTMATTER_OPTIONAL = ("tags", "related_paths", "blocked_by")
TARGET_FRONTMATTER_FIELDS = TARGET_FRONTMATTER_REQUIRED + TARGET_FRONTMATTER_OPTIONAL
TARGET_SECTIONS_REQUIRED = ("Problem", "Next Action", "Change History")
TARGET_STATUSES = ("open", "in_progress", "done", "wontfix")
TARGET_PRIORITIES = ("high", "normal", "low")
# Canonical legacy (Handoff v1.0 / pre-cutover) -> target priority mapping.
LEGACY_PRIORITY_MAP = {"critical": "high", "medium": "normal"}

# Canonical target ticket id pattern (T-YYYYMMDD-NN). Capture groups expose the
# date and daily sequence for parsing callers; recognition callers use fullmatch.
TARGET_ID_RE = re.compile(r"^T-(\d{8})-(\d{2,})$")
_FRONTMATTER_RE = re.compile(r"\A---\n(.*?)\n---\n?", re.DOTALL)
_LEGACY_FENCED_YAML_HEADER_RE = re.compile(r"\A(?:# [^\n]*\n+)?[ \t]*```ya?ml\b")
_H1_RE = re.compile(r"(?m)^# ")
_FENCE_RE = re.compile(r"^[ \t]*(```+|~~~+)")
_SECTION_RE = re.compile(r"(?m)^## ([^\n]+)$")
_CHANGE_HISTORY_RE = re.compile(
    r"^- \d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z \| ([^|]+) \| (.+)$"
)
_OLD_CHANGE_HISTORY_ACTORS = frozenset(
    {
        "auto-create",
        "auto-update",
        "auto-blocker",
        "auto-close",
        "auto-reopen",
        "correction",
        "discussion-approved",
    }
)


@dataclass(frozen=True, slots=True)
class TargetTicketValidation:
    """Result from target Ticket validation."""

    ok: bool
    ticket_id: str = ""
    error: str = ""


def validate_target_section_name(name: str) -> bool:
    """Return whether a section name is a valid level-2 target section name."""
    stripped = name.strip()
    if not stripped:
        return False
    if stripped != name:
        return False
    if "\n" in stripped or "\r" in stripped or "|" in stripped:
        return False
    if stripped.startswith("#"):
        return False
    return True


def validate_target_ticket_file(path: Path) -> TargetTicketValidation:
    """Validate one target-shaped ticket file from disk."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return TargetTicketValidation(
            False,
            error=f"read target ticket failed: {exc}. Got: {path!r:.100}",
        )
    return validate_target_ticket_text(path, text)


def validate_target_ticket_text(path: Path, text: str) -> TargetTicketValidation:
    """Validate target-shaped ticket Markdown without semantic scoring."""
    if _LEGACY_FENCED_YAML_HEADER_RE.match(text):
        return _invalid("target ticket validation", "fenced YAML is not target format", path)
    if _contains_h1_outside_fenced_code(text):
        return _invalid(
            "target ticket validation",
            "duplicated H1 title is not target format",
            path,
        )

    frontmatter_match = _FRONTMATTER_RE.match(text)
    if frontmatter_match is None:
        return _invalid("target ticket validation", "YAML frontmatter is required", path)

    frontmatter, frontmatter_error = _parse_frontmatter(frontmatter_match.group(1))
    if frontmatter is None:
        return _invalid("target ticket validation", frontmatter_error, path)

    normalized_frontmatter = _normalize_yaml_scalars(frontmatter)
    field_error = _validate_frontmatter(normalized_frontmatter)
    if field_error:
        return TargetTicketValidation(
            False,
            ticket_id=str(normalized_frontmatter.get("id", "")),
            error=field_error,
        )

    ticket_id = str(normalized_frontmatter["id"])
    if not TARGET_ID_RE.fullmatch(ticket_id):
        return TargetTicketValidation(
            False,
            ticket_id=ticket_id,
            error=f"target id is invalid. Got: {ticket_id!r:.100}",
        )
    if path.name != f"{ticket_id}.md":
        return TargetTicketValidation(
            False,
            ticket_id=ticket_id,
            error=f"target filename must be id-only. Got: {path.name!r:.100}",
        )

    body = text[frontmatter_match.end() :]
    section_error = _validate_required_sections(body)
    if section_error:
        return TargetTicketValidation(False, ticket_id=ticket_id, error=section_error)

    history_error = _validate_change_history(body)
    if history_error:
        return TargetTicketValidation(False, ticket_id=ticket_id, error=history_error)

    return TargetTicketValidation(True, ticket_id=ticket_id)


def _invalid(operation: str, reason: str, value: object) -> TargetTicketValidation:
    return TargetTicketValidation(False, error=f"{operation} failed: {reason}. Got: {value!r:.100}")


def _contains_h1_outside_fenced_code(text: str) -> bool:
    inside_fence = False
    for line in text.splitlines():
        if _FENCE_RE.match(line):
            inside_fence = not inside_fence
            continue
        if not inside_fence and _H1_RE.match(line):
            return True
    return False


def _parse_frontmatter(yaml_text: str) -> tuple[dict[str, Any] | None, str]:
    """Parse frontmatter YAML into (mapping, error). On success error is empty."""
    try:
        parsed = yaml.safe_load(yaml_text)
    except yaml.YAMLError as exc:
        return None, f"invalid YAML frontmatter: {' '.join(str(exc).split())}"
    if not isinstance(parsed, dict):
        return None, f"frontmatter must be a mapping; got {type(parsed).__name__}"
    return parsed, ""


def _normalize_yaml_scalars(frontmatter: dict[str, Any]) -> dict[str, Any]:
    normalized: dict[str, Any] = {}
    for key, value in frontmatter.items():
        if isinstance(value, (datetime.date, datetime.datetime)):
            normalized[key] = str(value)
        else:
            normalized[key] = value
    return normalized


def _validate_frontmatter(frontmatter: dict[str, Any]) -> str:
    unknown = sorted(set(frontmatter) - set(TARGET_FRONTMATTER_FIELDS))
    if unknown:
        return f"unknown frontmatter keys are invalid: {', '.join(unknown)}"

    missing = [field for field in TARGET_FRONTMATTER_REQUIRED if field not in frontmatter]
    if missing:
        return f"missing required frontmatter: {', '.join(missing)}"

    for field in TARGET_FRONTMATTER_REQUIRED:
        value = frontmatter[field]
        if not isinstance(value, str) or not value.strip():
            return f"{field} must be a non-empty string"

    status = frontmatter["status"]
    if status not in TARGET_STATUSES:
        return f"status must be one of {list(TARGET_STATUSES)!r}; got {status!r}"

    priority = frontmatter["priority"]
    if priority not in TARGET_PRIORITIES:
        return f"priority must be one of {list(TARGET_PRIORITIES)!r}; got {priority!r}"

    for field in TARGET_FRONTMATTER_OPTIONAL:
        value = frontmatter.get(field, [])
        if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
            return f"{field} must be a list of strings"

    return ""


def _validate_required_sections(body: str) -> str:
    headings = [(match.group(1).strip(), match.start()) for match in _SECTION_RE.finditer(body)]
    if not headings:
        return "missing required section: Problem"

    positions: dict[str, int] = {}
    for heading, start in headings:
        if not validate_target_section_name(heading):
            return f"invalid section name: {heading!r}"
        positions.setdefault(heading, start)

    for section in TARGET_SECTIONS_REQUIRED:
        if section not in positions:
            return f"missing required section: {section}"

    ordered_positions = [positions[section] for section in TARGET_SECTIONS_REQUIRED]
    if ordered_positions != sorted(ordered_positions):
        return "required sections are not in target section order"
    return ""


def _validate_change_history(body: str) -> str:
    sections = list(_SECTION_RE.finditer(body))
    for index, match in enumerate(sections):
        if match.group(1).strip() != "Change History":
            continue
        section_start = match.end()
        section_end = sections[index + 1].start() if index + 1 < len(sections) else len(body)
        lines = [
            line.strip()
            for line in body[section_start:section_end].splitlines()
            if line.strip()
        ]
        if not lines:
            return "Change History must contain at least one entry"
        for line in lines:
            line_match = _CHANGE_HISTORY_RE.fullmatch(line)
            if line_match is None:
                return f"Change History entry is invalid. Got: {line!r:.100}"
            actor = line_match.group(1).strip()
            reason = line_match.group(2).strip()
            if actor in _OLD_CHANGE_HISTORY_ACTORS or not validate_target_section_name(actor):
                return f"Change History actor is invalid. Got: {actor!r:.100}"
            if not reason:
                return f"Change History reason is empty. Got: {line!r:.100}"
        return ""
    return "missing required section: Change History"

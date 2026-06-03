"""Ticket-owned Change History helpers."""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass
from pathlib import Path

CHANGE_HISTORY_HEADING = "## Change History"
RELATED_HEADING = "## Related"
REOPEN_HISTORY_HEADING = "## Reopen History"


_REJECTED_ACTORS = frozenset(
    {
        "auto-create",
        "auto-update",
        "auto-blocker",
        "auto-close",
        "auto-reopen",
        "correction",
        "discussion-approved",
        "codex-create",
        "codex-update",
        "codex-blocker",
        "codex-close",
        "codex-reopen",
        "codex-correct",
        "codex-discussion",
    }
)
_TARGET_ACTORS = frozenset({"codex", "user-approved", "migration"})


@dataclass(frozen=True, slots=True)
class ChangeHistoryEntry:
    """A durable lightweight ticket history fact."""

    timestamp: str
    actor: str
    reason: str
    corrects: str | None = None


@dataclass(frozen=True, slots=True)
class PlannedChangeHistoryMigration:
    """Planned insertion for a missing `## Change History` section."""

    ticket_path: Path
    before_fingerprint: str
    after_text: str


def _value_error(operation: str, reason: str, value: object) -> ValueError:
    return ValueError(f"{operation} failed: {reason}. Got: {value!r:.100}")


def _text_fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _heading_pattern(heading: str) -> re.Pattern[str]:
    return re.compile(rf"(?m)^{re.escape(heading)}[ \t]*$")


def _find_heading(text: str, heading: str) -> re.Match[str] | None:
    return _heading_pattern(heading).search(text)


def _find_next_section_start(text: str, start: int) -> int | None:
    match = re.search(r"(?m)^## [^\n]*$", text[start:])
    if match is None:
        return None
    return start + match.start()


def _section_text(entry_line: str | None) -> str:
    if entry_line is None:
        return f"{CHANGE_HISTORY_HEADING}\n"
    return f"{CHANGE_HISTORY_HEADING}\n{entry_line}\n"


def _insert_before(text: str, index: int, section: str) -> str:
    prefix = text[:index].rstrip("\n")
    suffix = text[index:].lstrip("\n")
    if prefix:
        return f"{prefix}\n\n{section}\n{suffix}"
    return f"{section}\n{suffix}"


def _insert_after_section(text: str, heading_match: re.Match[str], section: str) -> str:
    next_start = _find_next_section_start(text, heading_match.end())
    if next_start is None:
        base = text.rstrip("\n")
        return f"{base}\n\n{section}" if base else section
    return _insert_before(text, next_start, section)


def _insert_change_history_section(text: str, entry_line: str | None) -> str:
    section = _section_text(entry_line)
    related = _find_heading(text, RELATED_HEADING)
    if related is not None:
        return _insert_after_section(text, related, section)

    reopen = _find_heading(text, REOPEN_HISTORY_HEADING)
    if reopen is not None:
        return _insert_before(text, reopen.start(), section)

    base = text.rstrip("\n")
    if base:
        return f"{base}\n\n{section}"
    return section


def _append_to_existing_change_history(
    ticket_text: str,
    heading_match: re.Match[str],
    entry_line: str,
) -> str:
    next_start = _find_next_section_start(ticket_text, heading_match.end())
    section_end = next_start if next_start is not None else len(ticket_text)
    section_lines = ticket_text[heading_match.end() : section_end].splitlines()
    if entry_line in section_lines:
        return ticket_text
    if next_start is None:
        base = ticket_text.rstrip("\n")
        return f"{base}\n{entry_line}\n"

    prefix = ticket_text[:next_start].rstrip("\n")
    suffix = ticket_text[next_start:].lstrip("\n")
    return f"{prefix}\n{entry_line}\n\n{suffix}"


def _validate_one_line(value: str, *, field: str, optional: bool = False) -> None:
    if optional and value == "":
        return
    if not value.strip():
        raise _value_error(f"validate Change History {field}", f"{field} is empty", value)
    if "|" in value:
        raise _value_error(
            f"validate Change History {field}",
            f"{field} must not contain pipe",
            value,
        )
    if "\n" in value or "\r" in value:
        raise _value_error(
            f"validate Change History {field}",
            f"{field} must not contain newline",
            value,
        )


def render_change_history_entry(entry: ChangeHistoryEntry) -> str:
    """Render one target Change History entry.

    Args:
        entry: Entry data to render.

    Returns:
        A single Markdown list item without a trailing newline.

    Raises:
        ValueError: If the actor or line-shaped fields are invalid.
    """
    if not isinstance(entry.actor, str):
        raise _value_error(
            "render Change History entry",
            "actor must be a string",
            entry.actor,
        )
    _validate_one_line(entry.timestamp, field="timestamp")
    _validate_one_line(entry.actor, field="actor")
    _validate_one_line(entry.reason, field="reason")
    if entry.actor in _REJECTED_ACTORS:
        raise _value_error(
            "render Change History entry",
            "actor must not encode action label",
            entry.actor,
        )

    rendered = f"- {entry.timestamp} | {entry.actor} | {entry.reason}"
    if entry.corrects is not None:
        _validate_one_line(entry.corrects, field="corrects")
        rendered = f"{rendered} Corrects: {entry.corrects}."
    return rendered


def append_change_history_entry(ticket_text: str, entry: ChangeHistoryEntry) -> str:
    """Append a Change History entry with deterministic section placement.

    Args:
        ticket_text: Complete ticket Markdown text.
        entry: Entry to append.

    Returns:
        Updated ticket Markdown text.
    """
    entry_line = render_change_history_entry(entry)
    if entry_line in ticket_text.splitlines():
        return ticket_text
    existing = _find_heading(ticket_text, CHANGE_HISTORY_HEADING)
    if existing is not None:
        return _append_to_existing_change_history(ticket_text, existing, entry_line)
    return _insert_change_history_section(ticket_text, entry_line)


def plan_change_history_migration(tickets_dir: Path) -> tuple[PlannedChangeHistoryMigration, ...]:
    """Plan empty `## Change History` insertion for active tickets missing it.

    Args:
        tickets_dir: Directory containing active ticket Markdown files.

    Returns:
        Ordered migration plans. This function does not write ticket files.
    """
    if not tickets_dir.is_dir():
        return ()

    plans: list[PlannedChangeHistoryMigration] = []
    for ticket_path in sorted(tickets_dir.glob("*.md")):
        ticket_text = ticket_path.read_text(encoding="utf-8")
        if _find_heading(ticket_text, CHANGE_HISTORY_HEADING) is not None:
            continue
        plans.append(
            PlannedChangeHistoryMigration(
                ticket_path=ticket_path,
                before_fingerprint=_text_fingerprint(ticket_text),
                after_text=_insert_change_history_section(ticket_text, None),
            )
        )
    return tuple(plans)

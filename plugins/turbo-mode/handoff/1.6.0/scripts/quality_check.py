#!/usr/bin/env python3
"""Hook-compatible helper for handoff/checkpoint/summary quality checks.

Handoff 1.6.0 does not wire plugin-bundled command hooks into the installed
plugin manifest. This module still accepts PostToolUse-shaped JSON so it can be
tested and reused by a future documented hook launcher architecture.

Reads PostToolUse JSON from stdin. If the written file is a handoff,
checkpoint, or summary (path under <project_root>/.codex/handoffs/), validates:
- Required frontmatter fields present, non-blank, and valid
- Required sections present (13 for handoffs, 8 for summaries, 5 for checkpoints)
- Line count within range (400+ for handoffs, 120-250 for summaries, 20-80 for checkpoints)
- No empty sections
- At least 1 of {Decisions, Changes, Learnings} has substantive content
  (hollow guardrail, handoffs and summaries only)

Outputs additionalContext via JSON stdout when issues are found.
Always exits 0 — this helper is non-blocking by design.
"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path

def _load_bootstrap_by_path() -> None:
    import importlib.util

    bootstrap_path = Path(__file__).resolve().parent / "_bootstrap.py"
    cached = sys.modules.get("scripts._bootstrap")
    if cached is not None:
        cached_file = getattr(cached, "__file__", None)
        try:
            cached_path = Path(cached_file).resolve() if cached_file is not None else None
        except (OSError, TypeError):
            cached_path = None
        if cached_path == bootstrap_path:
            ensure = getattr(cached, "ensure_plugin_scripts_package", None)
            if callable(ensure):
                ensure()
                return
        sys.modules.pop("scripts._bootstrap", None)
    spec = importlib.util.spec_from_file_location("scripts._bootstrap", bootstrap_path)
    if spec is None or spec.loader is None:
        raise ImportError(
            "handoff bootstrap failed: missing or unloadable _bootstrap.py. "
            f"Got: {str(bootstrap_path)!r:.100}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["scripts._bootstrap"] = module
    spec.loader.exec_module(module)


_load_bootstrap_by_path()
del _load_bootstrap_by_path

from scripts.handoff_parsing import (
    parse_frontmatter as _parse_handoff_frontmatter,
    parse_sections as _parse_handoff_sections,
    section_name as _section_name,
)

# --- Constants ---

REQUIRED_FRONTMATTER_FIELDS: tuple[str, ...] = (
    "date",
    "time",
    "created_at",
    "session_id",
    "project",
    "title",
    "type",
)

REQUIRED_HANDOFF_SECTIONS: tuple[str, ...] = (
    "Goal",
    "Session Narrative",
    "Decisions",
    "Changes",
    "Codebase Knowledge",
    "Context",
    "Learnings",
    "Next Steps",
    "In Progress",
    "Open Questions",
    "Risks",
    "References",
    "Gotchas",
)

REQUIRED_CHECKPOINT_SECTIONS: tuple[str, ...] = (
    "Current Task",
    "In Progress",
    "Active Files",
    "Next Action",
    "Verification Snapshot",
)

REQUIRED_SUMMARY_SECTIONS: tuple[str, ...] = (
    "Goal",
    "Session Narrative",
    "Decisions",
    "Changes",
    "Codebase Knowledge",
    "Learnings",
    "Next Steps",
    "Project Arc",
)

VALID_TYPES: frozenset[str] = frozenset({"handoff", "checkpoint", "summary"})

# At least 1 of these must have non-empty content (hollow-handoff guardrail)
CONTENT_REQUIRED_SECTIONS: tuple[str, ...] = (
    "Decisions",
    "Changes",
    "Learnings",
)

HANDOFF_MIN_LINES: int = 400
CHECKPOINT_MIN_LINES: int = 20
CHECKPOINT_MAX_LINES: int = 80
SUMMARY_MIN_LINES: int = 120
SUMMARY_MAX_LINES: int = 250


# --- Data model ---


@dataclass
class Issue:
    """A quality issue found during validation."""

    severity: str  # "error" or "warning"
    message: str


# --- Parsing ---


def parse_frontmatter(content: str) -> dict[str, str]:
    """Extract YAML frontmatter fields as key-value pairs."""
    frontmatter, _ = _parse_handoff_frontmatter(content)
    return frontmatter


def parse_sections(content: str) -> list[dict[str, str]]:
    """Extract ## sections with current quality-check return shape."""
    _, body = _parse_handoff_frontmatter(content)
    return [
        {
            "heading": _section_name(section.heading),
            "content": section.content,
        }
        for section in _parse_handoff_sections(body)
    ]


# --- Validation ---


def validate_frontmatter(frontmatter: dict[str, str], doc_type: str) -> list[Issue]:
    """Validate frontmatter fields for the given document type.

    Checks: required fields present, checkpoint title starts with
    "Checkpoint:", summary title starts with "Summary:".
    Type allowlist is checked in validate(), not here.
    """
    issues: list[Issue] = []

    missing = [f for f in REQUIRED_FRONTMATTER_FIELDS if f not in frontmatter]
    if missing:
        issues.append(Issue(
            "error", f"Missing required frontmatter: {', '.join(missing)}"
        ))

    blank = [
        f for f in REQUIRED_FRONTMATTER_FIELDS
        if f in frontmatter and not frontmatter[f].strip()
    ]
    if blank:
        issues.append(Issue(
            "error", f"Blank required frontmatter: {', '.join(blank)}"
        ))

    if doc_type == "checkpoint" and "title" in frontmatter:
        title = frontmatter["title"]
        if not title.startswith("Checkpoint:"):
            issues.append(Issue(
                "warning",
                f"Checkpoint title should start with 'Checkpoint:', "
                f"got: '{title[:60]}'",
            ))

    if doc_type == "summary" and "title" in frontmatter:
        title = frontmatter["title"]
        if not title.startswith("Summary:"):
            issues.append(Issue(
                "warning",
                f"Summary title should start with 'Summary:', "
                f"got: '{title[:60]}'",
            ))

    return issues


def validate_sections(
    sections: list[dict[str, str]], doc_type: str
) -> list[Issue]:
    """Validate section presence and content for the given document type.

    Checks: all required sections present by name, no empty sections.
    """
    issues: list[Issue] = []

    if doc_type == "handoff":
        required = REQUIRED_HANDOFF_SECTIONS
    elif doc_type == "summary":
        required = REQUIRED_SUMMARY_SECTIONS
    else:
        required = REQUIRED_CHECKPOINT_SECTIONS
    section_names = [s["heading"] for s in sections]

    missing = [name for name in required if name not in section_names]
    if missing:
        issues.append(Issue(
            "error", f"Missing required sections: {', '.join(missing)}"
        ))

    for section in sections:
        if not section["content"].strip():
            issues.append(Issue(
                "warning", f"Empty section: '{section['heading']}'"
            ))

    # Hollow-handoff guardrail: at least 1 of {Decisions, Changes, Learnings}
    # must have non-empty content (handoffs only).
    # Only fires when all 3 sections are present but empty — missing sections
    # are already caught by the missing-sections check above.
    if doc_type in ("handoff", "summary"):
        present_content_sections = [
            s for s in sections
            if s["heading"] in CONTENT_REQUIRED_SECTIONS
        ]
        if len(present_content_sections) == len(CONTENT_REQUIRED_SECTIONS):
            has_substance = any(
                s["content"].strip() for s in present_content_sections
            )
            if not has_substance:
                issues.append(Issue(
                    "error",
                    "Hollow document: at least 1 of {Decisions, Changes, Learnings} "
                    "must have substantive content.",
                ))

    return issues


def count_body_lines(content: str) -> int:
    """Count lines after the frontmatter closing ---.

    If no frontmatter, all lines are body lines.
    """
    lines = content.splitlines()
    if not lines or lines[0].strip() != "---":
        return len(lines)  # No frontmatter — all lines are body
    for i, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            return len(lines) - (i + 1)
    return len(lines)  # No closing --- — all lines are body


def validate_line_count(content: str, doc_type: str) -> list[Issue]:
    """Validate body line count is within acceptable range.

    Body = lines after frontmatter closing ---.
    Handoff: minimum 400. Summary: 120-250. Checkpoint: 20-80.
    """
    issues: list[Issue] = []
    body_lines = count_body_lines(content)

    if doc_type == "handoff":
        if body_lines < HANDOFF_MIN_LINES:
            issues.append(Issue(
                "error",
                f"Handoff body is {body_lines} lines "
                f"(minimum: {HANDOFF_MIN_LINES}). "
                "Under-capturing session content.",
            ))
    elif doc_type == "summary":
        if body_lines < SUMMARY_MIN_LINES:
            issues.append(Issue(
                "error",
                f"Summary body is {body_lines} lines "
                f"(minimum: {SUMMARY_MIN_LINES}). "
                "Under-capturing session content.",
            ))
        elif body_lines > SUMMARY_MAX_LINES:
            issues.append(Issue(
                "warning",
                f"Summary body is {body_lines} lines "
                f"(maximum: {SUMMARY_MAX_LINES}). "
                "Consider a full handoff instead.",
            ))
    elif doc_type == "checkpoint":
        if body_lines < CHECKPOINT_MIN_LINES:
            issues.append(Issue(
                "error",
                f"Checkpoint body is {body_lines} lines "
                f"(minimum: {CHECKPOINT_MIN_LINES}). "
                "Missing required sections.",
            ))
        elif body_lines > CHECKPOINT_MAX_LINES:
            issues.append(Issue(
                "warning",
                f"Checkpoint body is {body_lines} lines "
                f"(maximum: {CHECKPOINT_MAX_LINES}). "
                "Consider a full handoff instead.",
            ))

    return issues


def validate(content: str) -> list[Issue]:
    """Validate a handoff or checkpoint document. Returns list of issues.

    Parses frontmatter, validates type against allowlist (error on
    invalid), defaults to "handoff" for backwards compatibility
    (still reports missing 'type' as error), then runs all validators.
    """
    frontmatter = parse_frontmatter(content)

    if not frontmatter:
        return [Issue(
            "error",
            "No frontmatter found. Document must start with --- YAML block.",
        )]

    # Default to handoff for backwards compatibility
    doc_type = frontmatter.get("type", "handoff")

    issues: list[Issue] = []

    # Type allowlist — validate before branching to prevent
    # untrusted input controlling which validation rules apply
    if doc_type not in VALID_TYPES:
        issues.append(Issue(
            "error",
            f"Invalid type '{doc_type}'. Must be one of: {', '.join(sorted(VALID_TYPES))}.",
        ))
        return issues  # Can't validate sections/lines without valid type

    issues.extend(validate_frontmatter(frontmatter, doc_type))
    issues.extend(validate_sections(parse_sections(content), doc_type))
    issues.extend(validate_line_count(content, doc_type))

    return issues


# --- Hook integration ---


def is_handoff_path(file_path: str) -> bool:
    """Check if file is a handoff/checkpoint (active or archived).

    Valid: <root>/.codex/handoffs/<file>.md, <root>/.codex/handoffs/archive/<file>.md
    Invalid: non-.md, deeper nesting, no .codex parent, handoffs-variant directories.
    """
    path = Path(file_path)

    if path.suffix != ".md":
        return False

    parts = path.parts
    for i in range(len(parts) - 1):
        if parts[i] == ".codex" and parts[i + 1] == "handoffs":
            remaining = parts[i + 2:]
            # Direct child of handoffs/
            if len(remaining) == 1:
                return True
            # Direct child of handoffs/archive/
            if len(remaining) == 2 and remaining[0] == "archive":
                return True
            return False

    return False


def format_output(issues: list[Issue]) -> str:
    """Format issues as additionalContext message for Codex."""
    errors = [i for i in issues if i.severity == "error"]
    warnings = [i for i in issues if i.severity == "warning"]

    parts: list[str] = []
    parts.append(
        f"Handoff quality check found "
        f"{len(errors)} error(s) and {len(warnings)} warning(s)."
    )

    if errors:
        parts.append("\nErrors:")
        for e in errors:
            parts.append(f"- {e.message}")

    if warnings:
        parts.append("\nWarnings:")
        for w in warnings:
            parts.append(f"- {w.message}")

    if errors:
        parts.append("\nFix the errors and rewrite the handoff.")
    else:
        parts.append("\nPlease review the warnings above.")

    return "\n".join(parts)


def main() -> int:
    """PostToolUse hook entry point. Always returns 0."""
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, EOFError, ValueError) as exc:
        print(f"quality_check: stdin parse failed: {exc}", file=sys.stderr)
        return 0

    tool_input = hook_input.get("tool_input") or {}
    if not isinstance(tool_input, dict):
        print(
            f"quality_check: tool_input is {type(tool_input).__name__}, expected dict",
            file=sys.stderr,
        )
        return 0

    file_path = tool_input.get("file_path", "")
    if not isinstance(file_path, str) or not file_path:
        return 0

    if not is_handoff_path(file_path):
        return 0

    content = tool_input.get("content", "")
    if not isinstance(content, str) or not content:
        print(
            f"quality_check: content is {type(content).__name__}, expected str",
            file=sys.stderr,
        )
        return 0

    try:
        issues = validate(content)
    except Exception as exc:
        print(
            f"quality_check: validation failed ({type(exc).__name__}): {exc}",
            file=sys.stderr,
        )
        return 0

    if not issues:
        return 0

    try:
        output = {
            "hookSpecificOutput": {
                "hookEventName": "PostToolUse",
                "additionalContext": format_output(issues),
            }
        }
        json.dump(output, sys.stdout)
    except Exception as exc:
        print(
            f"quality_check: output serialization failed: {exc}",
            file=sys.stderr,
        )

    return 0


if __name__ == "__main__":
    sys.exit(main())

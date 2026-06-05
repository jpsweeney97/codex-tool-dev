"""Tests for ADR 0006 target ticket schema validation."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.ticket_target_schema import (
    TARGET_FRONTMATTER_FIELDS,
    TARGET_FRONTMATTER_OPTIONAL,
    TARGET_FRONTMATTER_REQUIRED,
    TARGET_PRIORITIES,
    TARGET_SECTIONS_REQUIRED,
    TARGET_STATUSES,
    validate_target_section_name,
    validate_target_ticket_file,
)


def _write_target_ticket(
    path: Path,
    *,
    frontmatter: str | None = None,
    body: str | None = None,
) -> None:
    default_frontmatter = (
        "---\n"
        "id: T-20260508-01\n"
        "title: Example\n"
        "status: open\n"
        "priority: normal\n"
        "tags: []\n"
        "related_paths: []\n"
        "blocked_by: []\n"
        "---\n"
    )
    default_body = (
        "\n"
        "## Problem\n"
        "Example problem.\n"
        "\n"
        "## Next Action\n"
        "Example next action.\n"
        "\n"
        "## Change History\n"
        "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n"
    )
    path.write_text((frontmatter or default_frontmatter) + (body or default_body), encoding="utf-8")


def test_target_ticket_accepts_id_only_yaml_frontmatter(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(ticket)

    result = validate_target_ticket_file(ticket)

    assert result.ok is True
    assert result.ticket_id == "T-20260508-01"
    assert result.error == ""


@pytest.mark.parametrize(
    ("name", "expected"),
    [
        ("Problem", True),
        ("Acceptance Criteria", True),
        ("Next Action", True),
        ("", False),
        ("Bad\nName", False),
        ("### Bad", False),
        ("Bad | Name", False),
    ],
)
def test_validate_target_section_name_accepts_line_shaped_l2_names(
    name: str, expected: bool
) -> None:
    assert validate_target_section_name(name) is expected


def test_target_schema_constants_match_contract_vocabulary() -> None:
    assert TARGET_FRONTMATTER_REQUIRED == ("id", "title", "status", "priority")
    assert TARGET_FRONTMATTER_OPTIONAL == ("tags", "related_paths", "blocked_by")
    assert TARGET_FRONTMATTER_FIELDS == (
        "id",
        "title",
        "status",
        "priority",
        "tags",
        "related_paths",
        "blocked_by",
    )
    assert TARGET_SECTIONS_REQUIRED == ("Problem", "Next Action", "Change History")
    assert TARGET_STATUSES == ("idea", "open", "blocked", "done", "wontfix")
    assert TARGET_PRIORITIES == ("high", "normal", "low")


def test_target_ticket_accepts_idea_status(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: idea\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is True
    assert result.error == ""


def test_target_ticket_rejects_deprecated_in_progress_status(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: in_progress\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "status" in result.error
    assert "in_progress" in result.error


def test_target_ticket_rejects_slug_filename(tmp_path: Path) -> None:
    ticket = tmp_path / "2026-05-08-example.md"
    _write_target_ticket(ticket)

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "filename" in result.error


def test_target_ticket_rejects_fenced_yaml(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    ticket.write_text(
        "```yaml\n"
        "id: T-20260508-01\n"
        "status: open\n"
        "```\n"
        "\n"
        "## Problem\nExample problem.\n",
        encoding="utf-8",
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "fenced YAML" in result.error


def test_target_ticket_accepts_yaml_code_fence_in_body(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        body=(
            "\n"
            "## Problem\n"
            "Document the target shape with an example:\n"
            "```yaml\n"
            "priority: normal\n"
            "```\n"
            "\n"
            "## Next Action\n"
            "Keep the prose example valid.\n"
            "\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is True
    assert result.error == ""


def test_target_ticket_accepts_markdown_h1_inside_code_fence(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        body=(
            "\n"
            "## Problem\n"
            "Document a Markdown heading example:\n"
            "```markdown\n"
            "# Example heading\n"
            "```\n"
            "\n"
            "## Next Action\n"
            "Keep the prose example valid.\n"
            "\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is True
    assert result.error == ""


def test_target_ticket_rejects_duplicated_h1_title(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(ticket, body="\n# T-20260508-01: Example\n\n## Problem\nExample.\n")

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "H1" in result.error


def test_target_ticket_rejects_unknown_frontmatter_key(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: open\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "source: legacy\n"
            "---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "unknown frontmatter" in result.error


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("priority", "medium"),
        ("priority", "critical"),
    ],
)
def test_target_ticket_rejects_deprecated_priorities(
    tmp_path: Path, field: str, value: str
) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            f"status: {value if field == 'status' else 'open'}\n"
            f"priority: {value if field == 'priority' else 'normal'}\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert field in result.error


def test_target_ticket_accepts_blocked_status_with_blocked_on(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: blocked\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: [T-20260508-02]\n"
            "---\n"
        ),
        body=(
            "\n"
            "## Problem\n"
            "Example problem.\n"
            "\n"
            "## Next Action\n"
            "Ask for the missing deploy credentials, then continue implementation.\n"
            "\n"
            "## Blocked On\n"
            "Waiting for deploy credentials from the user.\n"
            "\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is True
    assert result.error == ""


def test_target_ticket_rejects_blocked_status_without_blocked_on(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: blocked\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "Blocked On" in result.error


def test_target_ticket_rejects_blocked_status_with_empty_blocked_on(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: blocked\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "---\n"
        ),
        body=(
            "\n"
            "## Problem\n"
            "Example problem.\n"
            "\n"
            "## Next Action\n"
            "Ask for the missing deploy credentials, then continue implementation.\n"
            "\n"
            "## Blocked On\n"
            "\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "Blocked On" in result.error


def test_target_ticket_rejects_duplicate_blocked_on_section(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: blocked\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "---\n"
        ),
        body=(
            "\n"
            "## Problem\n"
            "Example problem.\n"
            "\n"
            "## Next Action\n"
            "Ask for the missing deploy credentials, then continue implementation.\n"
            "\n"
            "## Blocked On\n"
            "Waiting for deploy credentials from the user.\n"
            "\n"
            "## Blocked On\n"
            "A duplicate blocker section must be rejected instead of ignored.\n"
            "\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "duplicate section heading: Blocked On" in result.error


def test_target_ticket_rejects_blocked_on_for_non_blocked_status(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        body=(
            "\n"
            "## Problem\n"
            "Example problem.\n"
            "\n"
            "## Next Action\n"
            "Example next action.\n"
            "\n"
            "## Blocked On\n"
            "This stale blocker section must be removed before the ticket is open.\n"
            "\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "Blocked On" in result.error


def test_target_ticket_rejects_non_empty_blocked_by_for_non_blocked_status(
    tmp_path: Path,
) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: open\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: [T-20260508-02]\n"
            "---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "blocked_by" in result.error


def test_target_ticket_rejects_invalid_blocked_by_ids(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: blocked\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: [not-a-ticket-id]\n"
            "---\n"
        ),
        body=(
            "\n"
            "## Problem\n"
            "Example problem.\n"
            "\n"
            "## Next Action\n"
            "Ask for the missing deploy credentials, then continue implementation.\n"
            "\n"
            "## Blocked On\n"
            "Waiting for deploy credentials from the user.\n"
            "\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "blocked_by" in result.error


def test_target_ticket_rejects_blocks_reverse_edge(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: open\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "blocks: []\n"
            "---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "blocks" in result.error


@pytest.mark.parametrize("field", TARGET_FRONTMATTER_OPTIONAL)
def test_target_ticket_rejects_null_optional_frontmatter_lists(
    tmp_path: Path, field: str
) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    optional_values = {
        "tags": "[]",
        "related_paths": "[]",
        "blocked_by": "[]",
    }
    optional_values[field] = "null"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: open\n"
            "priority: normal\n"
            f"tags: {optional_values['tags']}\n"
            f"related_paths: {optional_values['related_paths']}\n"
            f"blocked_by: {optional_values['blocked_by']}\n"
            "---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert f"{field} must be a list of strings" in result.error


@pytest.mark.parametrize(
    ("body", "expected_error"),
    [
        (
            "\n## Next Action\nDo it.\n\n"
            "## Change History\n- 2026-06-02T00:00:00Z | migration | x.\n",
            "Problem",
        ),
        (
            "\n## Problem\nText.\n\n## Change History\n- 2026-06-02T00:00:00Z | migration | x.\n",
            "Next Action",
        ),
        (
            "\n## Problem\nText.\n\n"
            "## Change History\n- 2026-06-02T00:00:00Z | migration | x.\n\n"
            "## Next Action\nDo it.\n",
            "section order",
        ),
    ],
)
def test_target_ticket_rejects_missing_or_disordered_required_sections(
    tmp_path: Path, body: str, expected_error: str
) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(ticket, body=body)

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert expected_error in result.error


def test_target_ticket_rejects_invalid_change_history_actor_label(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        body=(
            "\n## Problem\nExample problem.\n"
            "\n## Next Action\nExample next action.\n"
            "\n## Change History\n"
            "- 2026-06-02T00:00:00Z | auto-create | Old controlled label.\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "Change History actor" in result.error


def test_target_ticket_rejects_missing_frontmatter(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    ticket.write_text(
        "## Problem\nText.\n\n## Next Action\nDo it.\n\n"
        "## Change History\n- 2026-06-02T00:00:00Z | migration | x.\n",
        encoding="utf-8",
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "YAML frontmatter is required" in result.error


def test_target_ticket_rejects_non_mapping_frontmatter(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(ticket, frontmatter="---\n- a\n- b\n---\n")

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "frontmatter must be a mapping" in result.error


def test_target_ticket_surfaces_yaml_syntax_error(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(ticket, frontmatter='---\nid: "unterminated\nstatus: open\n---\n')

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "invalid YAML frontmatter" in result.error


def test_target_ticket_rejects_missing_required_field(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\nid: T-20260508-01\ntitle: Example\npriority: normal\n"
            "tags: []\nrelated_paths: []\nblocked_by: []\n---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "missing required frontmatter: status" in result.error


def test_target_ticket_rejects_empty_required_field(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\nid: T-20260508-01\ntitle: ''\nstatus: open\npriority: normal\n"
            "tags: []\nrelated_paths: []\nblocked_by: []\n---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "title must be a non-empty string" in result.error


def test_target_ticket_rejects_non_target_id(tmp_path: Path) -> None:
    ticket = tmp_path / "T-2026-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\nid: T-2026-01\ntitle: Example\nstatus: open\npriority: normal\n"
            "tags: []\nrelated_paths: []\nblocked_by: []\n---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "target id is invalid" in result.error


def test_target_ticket_rejects_empty_change_history(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        body="\n## Problem\nText.\n\n## Next Action\nDo it.\n\n## Change History\n",
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "Change History must contain at least one entry" in result.error


def test_target_ticket_read_failure_surfaces_error(tmp_path: Path) -> None:
    result = validate_target_ticket_file(tmp_path / "does-not-exist.md")

    assert result.ok is False
    assert "read target ticket failed" in result.error

"""Tests for ticket Change History helpers."""

from __future__ import annotations

import pytest
from scripts.ticket_change_history import (
    ChangeHistoryEntry,
    append_change_history_entry,
    plan_change_history_migration,
    render_change_history_entry,
)


def test_render_change_history_entry_format() -> None:
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        actor="codex",
        reason="Adjusted stale metadata.",
    )
    with_correction = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        actor="codex",
        reason="Corrected prior automatic update.",
        corrects="mutation abc1234",
    )

    assert render_change_history_entry(entry) == (
        "- 2026-05-27T12:00:00Z | codex | Adjusted stale metadata."
    )
    assert render_change_history_entry(with_correction) == (
        "- 2026-05-27T12:00:00Z | codex | Corrected prior automatic update. "
        "Corrects: mutation abc1234."
    )


@pytest.mark.parametrize(
    "actor",
    ["auto-update", "auto-close", "correction", "discussion-approved", "codex-update"],
)
def test_old_action_label_actors_are_rejected(actor: str) -> None:
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        actor=actor,
        reason="Invalid actor.",
    )

    with pytest.raises(ValueError, match="actor"):
        render_change_history_entry(entry)


@pytest.mark.parametrize("reason", ["Contains | pipe", "line one\nline two"])
def test_reason_cannot_contain_pipe_or_newline(reason: str) -> None:
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        actor="codex",
        reason=reason,
    )

    with pytest.raises(ValueError, match="reason"):
        render_change_history_entry(entry)


def test_append_inserts_missing_section_after_related() -> None:
    text = "# T: Example\n\n## Problem\nText.\n\n## Related\n- T-1\n\n## Reopen History\n- old\n"
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        actor="codex",
        reason="Updated blocker.",
    )

    updated = append_change_history_entry(text, entry)

    assert "## Related\n- T-1\n\n## Change History\n- 2026-05-27" in updated
    assert updated.index("## Related") < updated.index("## Change History")
    assert updated.index("## Change History") < updated.index("## Reopen History")


def test_append_inserts_missing_section_before_reopen_history_without_related() -> None:
    text = "# T: Example\n\n## Problem\nText.\n\n## Reopen History\n- old\n"
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        actor="codex",
        reason="Reopened automatically.",
    )

    updated = append_change_history_entry(text, entry)

    assert updated.index("## Change History") < updated.index("## Reopen History")


def test_append_inserts_missing_section_at_end_without_anchor_sections() -> None:
    text = "# T: Example\n\n## Problem\nText.\n"
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        actor="codex",
        reason="Created automatically.",
    )

    updated = append_change_history_entry(text, entry)

    assert updated.endswith(
        "\n\n## Change History\n"
        "- 2026-05-27T12:00:00Z | codex | Created automatically.\n"
    )


def test_existing_change_history_receives_appended_entry() -> None:
    text = "# T: Example\n\n## Change History\n- old entry\n\n## Reopen History\n- old\n"
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        actor="codex",
        reason="Updated metadata.",
    )

    updated = append_change_history_entry(text, entry)

    assert "## Change History\n- old entry\n- 2026-05-27" in updated
    assert updated.index("- 2026-05-27") < updated.index("## Reopen History")


def test_existing_change_history_exact_rendered_line_is_idempotent() -> None:
    text = (
        "# T: Example\n\n"
        "## Change History\n"
        "- 2026-05-27T12:00:00Z | codex | Updated ticket from candidate evidence.\n"
        "\n"
        "## Reopen History\n"
        "- old\n"
    )
    duplicate = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        actor="codex",
        reason="Updated ticket from candidate evidence.",
    )
    later = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:01Z",
        actor="codex",
        reason="Updated ticket from candidate evidence.",
    )

    assert append_change_history_entry(text, duplicate) == text

    updated = append_change_history_entry(text, later)
    assert updated.count("Updated ticket from candidate evidence.") == 2
    assert "- 2026-05-27T12:00:01Z | codex | Updated ticket from candidate evidence." in updated


def test_helper_does_not_write_containing_commit_hash() -> None:
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        actor="codex",
        reason="Updated metadata.",
    )

    assert "Prior commit:" not in render_change_history_entry(entry)


def test_plan_change_history_migration_returns_missing_section_plans(tmp_path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    tickets_dir.mkdir(parents=True)
    missing = tickets_dir / "missing.md"
    existing = tickets_dir / "existing.md"
    missing.write_text("# Missing\n\n## Problem\nText.\n", encoding="utf-8")
    existing.write_text("# Existing\n\n## Change History\n- old\n", encoding="utf-8")

    plans = plan_change_history_migration(tickets_dir)

    assert [plan.ticket_path for plan in plans] == [missing]
    assert plans[0].before_fingerprint
    assert "## Change History" in plans[0].after_text
    assert existing.read_text(encoding="utf-8") == "# Existing\n\n## Change History\n- old\n"

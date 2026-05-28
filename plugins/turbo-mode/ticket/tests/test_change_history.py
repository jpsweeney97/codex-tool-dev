"""Tests for ticket Change History helpers."""

from __future__ import annotations

from typing import cast

import pytest
from scripts.ticket_change_history import (
    ChangeHistoryEntry,
    ChangeHistoryLabel,
    append_change_history_entry,
    plan_change_history_migration,
    render_change_history_entry,
)


def test_render_change_history_entry_format() -> None:
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        label=ChangeHistoryLabel.AUTO_UPDATE,
        reason="Adjusted stale metadata.",
    )
    with_prior = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        label=ChangeHistoryLabel.CORRECTION,
        reason="Corrected prior automatic update.",
        prior_commit="abc1234",
    )

    assert render_change_history_entry(entry) == (
        "- 2026-05-27T12:00:00Z | auto-update | Adjusted stale metadata."
    )
    assert render_change_history_entry(with_prior) == (
        "- 2026-05-27T12:00:00Z | correction | Corrected prior automatic update. "
        "Prior commit: abc1234."
    )


@pytest.mark.parametrize("label", ["auto_update", "update", "auto-close:done"])
def test_unknown_labels_and_aliases_are_rejected(label: str) -> None:
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        label=cast(ChangeHistoryLabel, label),
        reason="Invalid label.",
    )

    with pytest.raises(ValueError, match="label"):
        render_change_history_entry(entry)


@pytest.mark.parametrize("reason", ["Contains | pipe", "line one\nline two"])
def test_reason_cannot_contain_pipe_or_newline(reason: str) -> None:
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        label=ChangeHistoryLabel.AUTO_UPDATE,
        reason=reason,
    )

    with pytest.raises(ValueError, match="reason"):
        render_change_history_entry(entry)


def test_append_inserts_missing_section_after_related() -> None:
    text = "# T: Example\n\n## Problem\nText.\n\n## Related\n- T-1\n\n## Reopen History\n- old\n"
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        label=ChangeHistoryLabel.AUTO_BLOCKER,
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
        label=ChangeHistoryLabel.AUTO_REOPEN,
        reason="Reopened automatically.",
    )

    updated = append_change_history_entry(text, entry)

    assert updated.index("## Change History") < updated.index("## Reopen History")


def test_append_inserts_missing_section_at_end_without_anchor_sections() -> None:
    text = "# T: Example\n\n## Problem\nText.\n"
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        label=ChangeHistoryLabel.AUTO_CREATE,
        reason="Created automatically.",
    )

    updated = append_change_history_entry(text, entry)

    assert updated.endswith(
        "\n\n## Change History\n"
        "- 2026-05-27T12:00:00Z | auto-create | Created automatically.\n"
    )


def test_existing_change_history_receives_appended_entry() -> None:
    text = "# T: Example\n\n## Change History\n- old entry\n\n## Reopen History\n- old\n"
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        label=ChangeHistoryLabel.AUTO_UPDATE,
        reason="Updated metadata.",
    )

    updated = append_change_history_entry(text, entry)

    assert "## Change History\n- old entry\n- 2026-05-27" in updated
    assert updated.index("- 2026-05-27") < updated.index("## Reopen History")


def test_existing_change_history_exact_rendered_line_is_idempotent() -> None:
    text = (
        "# T: Example\n\n"
        "## Change History\n"
        "- 2026-05-27T12:00:00Z | auto-update | Automatic Ticket update applied.\n"
        "\n"
        "## Reopen History\n"
        "- old\n"
    )
    duplicate = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        label=ChangeHistoryLabel.AUTO_UPDATE,
        reason="Automatic Ticket update applied.",
    )
    later = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:01Z",
        label=ChangeHistoryLabel.AUTO_UPDATE,
        reason="Automatic Ticket update applied.",
    )

    assert append_change_history_entry(text, duplicate) == text

    updated = append_change_history_entry(text, later)
    assert updated.count("Automatic Ticket update applied.") == 2
    assert "- 2026-05-27T12:00:01Z | auto-update | Automatic Ticket update applied." in updated


def test_helper_does_not_write_containing_commit_hash() -> None:
    entry = ChangeHistoryEntry(
        timestamp="2026-05-27T12:00:00Z",
        label=ChangeHistoryLabel.AUTO_UPDATE,
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

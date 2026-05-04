"""Tests for ticket_id.py — ID allocation and slug generation."""
from __future__ import annotations

from datetime import date


from scripts.ticket_id import (
    allocate_id,
    build_filename,
    generate_slug,
    is_legacy_id,
    parse_id_date,
)
from tests.support.builders import make_ticket


class TestAllocateId:
    def test_first_ticket_of_day(self, tmp_tickets):
        ticket_id = allocate_id(tmp_tickets, date(2026, 3, 2))
        assert ticket_id == "T-20260302-01"

    def test_sequential_allocation(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-02-first.md", id="T-20260302-01")
        ticket_id = allocate_id(tmp_tickets, date(2026, 3, 2))
        assert ticket_id == "T-20260302-02"

    def test_gap_in_sequence(self, tmp_tickets):
        """Allocates next after highest, not gap-filling."""

        make_ticket(tmp_tickets, "2026-03-02-first.md", id="T-20260302-01")
        make_ticket(tmp_tickets, "2026-03-02-third.md", id="T-20260302-03")
        ticket_id = allocate_id(tmp_tickets, date(2026, 3, 2))
        assert ticket_id == "T-20260302-04"

    def test_different_day_no_conflict(self, tmp_tickets):

        make_ticket(tmp_tickets, "2026-03-01-old.md", id="T-20260301-05")
        ticket_id = allocate_id(tmp_tickets, date(2026, 3, 2))
        assert ticket_id == "T-20260302-01"

    def test_empty_directory(self, tmp_tickets):
        ticket_id = allocate_id(tmp_tickets, date(2026, 3, 2))
        assert ticket_id == "T-20260302-01"

    def test_nonexistent_directory(self, tmp_path):
        """Missing directory returns first ID (not error)."""
        ticket_id = allocate_id(tmp_path / "nonexistent", date(2026, 3, 2))
        assert ticket_id == "T-20260302-01"


class TestGenerateSlug:
    def test_basic_title(self):
        assert generate_slug("Fix authentication timeout on large payloads") == "fix-authentication-timeout-on-large-payloads"

    def test_truncates_to_six_words(self):
        slug = generate_slug("This is a very long title that exceeds six words easily")
        assert slug == "this-is-a-very-long-title"

    def test_special_characters_removed(self):
        slug = generate_slug("Fix: the AUTH bug (v2.0)!")
        assert slug == "fix-the-auth-bug-v20"

    def test_collapses_hyphens(self):
        slug = generate_slug("Fix --- multiple --- hyphens")
        assert slug == "fix-multiple-hyphens"

    def test_max_60_chars(self):
        long_title = "a" * 100
        slug = generate_slug(long_title)
        assert len(slug) <= 60

    def test_empty_title(self):
        slug = generate_slug("")
        assert slug == "untitled"


class TestIsLegacyId:
    def test_gen1_slug(self):
        assert is_legacy_id("handoff-chain-viz") is True

    def test_gen2_letter(self):
        assert is_legacy_id("T-A") is True
        assert is_legacy_id("T-F") is True

    def test_gen3_numeric(self):
        assert is_legacy_id("T-003") is True
        assert is_legacy_id("T-100") is True

    def test_v10_not_legacy(self):
        assert is_legacy_id("T-20260302-01") is False


class TestParseIdDate:
    def test_v10_id(self):
        assert parse_id_date("T-20260302-01") == date(2026, 3, 2)

    def test_legacy_id_returns_none(self):
        assert parse_id_date("T-A") is None
        assert parse_id_date("T-003") is None
        assert parse_id_date("handoff-chain-viz") is None


class TestBuildFilenameCollision:
    """build_filename appends collision suffixes when tickets_dir is provided."""

    def test_collision_suffix_when_file_exists(self, tmp_tickets):
        """Existing file with same slug → returns <base>-2.md."""
        existing = tmp_tickets / "2026-03-02-fix-the-bug.md"
        existing.write_text("placeholder")

        filename = build_filename("T-20260302-01", "Fix the bug", tmp_tickets)
        assert filename == "2026-03-02-fix-the-bug-2.md"

    def test_collision_suffix_increments(self, tmp_tickets):
        """Multiple collisions → suffix increments until unique."""
        (tmp_tickets / "2026-03-02-fix-the-bug.md").write_text("placeholder")
        (tmp_tickets / "2026-03-02-fix-the-bug-2.md").write_text("placeholder")
        (tmp_tickets / "2026-03-02-fix-the-bug-3.md").write_text("placeholder")

        filename = build_filename("T-20260302-01", "Fix the bug", tmp_tickets)
        assert filename == "2026-03-02-fix-the-bug-4.md"

    def test_no_collision_without_tickets_dir(self, tmp_tickets):
        """tickets_dir=None skips collision check (backward compat)."""
        (tmp_tickets / "2026-03-02-fix-the-bug.md").write_text("placeholder")

        filename = build_filename("T-20260302-01", "Fix the bug")
        assert filename == "2026-03-02-fix-the-bug.md"


class TestAllocateIdArchived:
    """allocate_id scans closed-tickets/ to prevent ID reuse."""

    def test_skips_archived_ticket_ids(self, tmp_tickets):
        """Archived ticket ID is not reissued."""

        closed_dir = tmp_tickets / "closed-tickets"
        closed_dir.mkdir()
        make_ticket(closed_dir, "2026-03-02-old-bug.md", id="T-20260302-01")

        ticket_id = allocate_id(tmp_tickets, date(2026, 3, 2))
        assert ticket_id == "T-20260302-02"

    def test_no_closed_dir_still_works(self, tmp_tickets):
        """Missing closed-tickets/ dir → behaves as before."""

        make_ticket(tmp_tickets, "2026-03-02-first.md", id="T-20260302-01")
        ticket_id = allocate_id(tmp_tickets, date(2026, 3, 2))
        assert ticket_id == "T-20260302-02"


class TestVariableWidthSequence:
    """Sequence numbers beyond 99 (3+ digits) must be recognized."""

    def test_allocate_id_beyond_99(self, tmp_path):
        """allocate_id handles sequence numbers beyond 99."""

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        today = date(2026, 3, 3)

        # Create tickets T-20260303-98 and T-20260303-99
        for seq in (98, 99):
            tid = f"T-20260303-{seq:02d}"
            make_ticket(
                tickets_dir,
                f"2026-03-03-ticket-{seq}.md",
                id=tid,
                date="2026-03-03",
                title=f"Ticket {seq}",
            )

        result = allocate_id(tickets_dir, today)
        assert result == "T-20260303-100"

        # Now create 100 and verify 101 is allocated
        make_ticket(
            tickets_dir,
            "2026-03-03-ticket-100.md",
            id="T-20260303-100",
            date="2026-03-03",
            title="Ticket 100",
        )

        result = allocate_id(tickets_dir, today)
        assert result == "T-20260303-101"

    def test_date_id_regex_matches_variable_width(self):
        """_DATE_ID_RE matches IDs with 2+ digit sequences."""
        from scripts.ticket_id import _DATE_ID_RE

        assert _DATE_ID_RE.match("T-20260303-01")
        assert _DATE_ID_RE.match("T-20260303-99")
        assert _DATE_ID_RE.match("T-20260303-100")
        assert _DATE_ID_RE.match("T-20260303-1000")
        assert not _DATE_ID_RE.match("T-20260303-0")  # single digit invalid
        assert not _DATE_ID_RE.match("T-2026030-01")  # 7-digit date invalid

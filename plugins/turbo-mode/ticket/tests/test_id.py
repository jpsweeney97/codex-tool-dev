"""Tests for target Ticket ID allocation and filename helpers."""

from __future__ import annotations

from datetime import date

import pytest
from scripts.ticket_id import (
    _DATE_ID_RE,
    allocate_id,
    build_filename,
    generate_slug,
    is_legacy_id,
    parse_id_date,
)

from tests.support.builders import make_ticket


class TestAllocateId:
    def test_first_ticket_of_day(self, tmp_tickets):
        assert allocate_id(tmp_tickets, date(2026, 3, 2)) == "T-20260302-01"

    def test_sequential_allocation(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01")
        assert allocate_id(tmp_tickets, date(2026, 3, 2)) == "T-20260302-02"

    def test_gap_in_sequence(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01")
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-03")
        assert allocate_id(tmp_tickets, date(2026, 3, 2)) == "T-20260302-04"

    def test_different_day_no_conflict(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260301-05")
        assert allocate_id(tmp_tickets, date(2026, 3, 2)) == "T-20260302-01"

    def test_nonexistent_directory(self, tmp_path):
        assert allocate_id(tmp_path / "nonexistent", date(2026, 3, 2)) == "T-20260302-01"

    def test_closed_tickets_are_not_current_storage(self, tmp_tickets):
        closed_dir = tmp_tickets / "closed-tickets"
        closed_dir.mkdir()
        make_ticket(closed_dir, "ignored.md", id="T-20260302-01", status="done")

        assert allocate_id(tmp_tickets, date(2026, 3, 2)) == "T-20260302-01"


class TestGenerateSlug:
    def test_basic_title(self):
        assert (
            generate_slug("Fix authentication timeout on large payloads")
            == "fix-authentication-timeout-on-large-payloads"
        )

    def test_truncates_to_six_words(self):
        assert generate_slug("This is a very long title that exceeds six words easily") == (
            "this-is-a-very-long-title"
        )

    def test_special_characters_removed(self):
        assert generate_slug("Fix: the AUTH bug (v2.0)!") == "fix-the-auth-bug-v20"

    def test_empty_title(self):
        assert generate_slug("") == "untitled"


class TestIsLegacyId:
    def test_legacy_ids(self):
        assert is_legacy_id("handoff-chain-viz") is True
        assert is_legacy_id("T-A") is True
        assert is_legacy_id("T-003") is True

    def test_target_id_not_legacy(self):
        assert is_legacy_id("T-20260302-01") is False


class TestParseIdDate:
    def test_target_id(self):
        assert parse_id_date("T-20260302-01") == date(2026, 3, 2)

    def test_legacy_id_returns_none(self):
        assert parse_id_date("T-A") is None


class TestBuildFilename:
    def test_build_filename_returns_id_only_filename(self):
        assert build_filename("T-20260602-01", "Ignored title") == "T-20260602-01.md"

    def test_existing_target_file_rejected(self, tmp_tickets):
        make_ticket(tmp_tickets, "ignored.md", id="T-20260602-01")

        with pytest.raises(ValueError, match="already exists"):
            build_filename("T-20260602-01", "Ignored title", tmp_tickets)

    def test_invalid_id_rejected(self):
        with pytest.raises(ValueError, match="invalid target ticket id"):
            build_filename("T-003", "Ignored title")


class TestVariableWidthSequence:
    def test_allocate_id_beyond_99(self, tmp_path):
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        today = date(2026, 3, 3)
        for seq in (98, 99):
            make_ticket(tickets_dir, "ignored.md", id=f"T-20260303-{seq:02d}")

        assert allocate_id(tickets_dir, today) == "T-20260303-100"

        make_ticket(tickets_dir, "ignored.md", id="T-20260303-100")

        assert allocate_id(tickets_dir, today) == "T-20260303-101"

    def test_date_id_regex_matches_variable_width(self):
        assert _DATE_ID_RE.match("T-20260303-01")
        assert _DATE_ID_RE.match("T-20260303-99")
        assert _DATE_ID_RE.match("T-20260303-100")
        assert _DATE_ID_RE.match("T-20260303-1000")
        assert not _DATE_ID_RE.match("T-20260303-0")
        assert not _DATE_ID_RE.match("T-2026030-01")

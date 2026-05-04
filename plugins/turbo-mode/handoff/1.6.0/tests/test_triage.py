"""Tests for triage.py — ticket reading, status normalization, orphan detection."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

TICKET_DEFERRED = """\
# T-20260228-01: Deferred ticket

```yaml
id: T-20260228-01
date: 2026-02-28
status: deferred
priority: medium
```

## Problem

Not triaged yet.
"""

TICKET_DONE = """\
# T-20260228-02: Done ticket

```yaml
id: T-20260228-02
date: 2026-02-28
status: done
priority: low
```

## Problem

Already done.
"""

TICKET_LEGACY_COMPLETE = """\
# T-004: Legacy complete

```yaml
id: T-004
date: 2026-02-17
status: complete
priority: medium
```

## Summary

Legacy ticket.
"""

TICKET_LEGACY_PLANNING = """\
# handoff-search: Planning ticket

```yaml
id: handoff-search
date: 2026-02-24
status: planning
priority: medium
```

## Problem

Still planning.
"""


class TestNormalizeStatus:
    def test_known_statuses_pass_through(self) -> None:
        from scripts.triage import normalize_status

        for s in ("deferred", "open", "in_progress", "blocked", "done", "wontfix"):
            norm, conf = normalize_status(s)
            assert norm == s
            assert conf == "high"

    def test_complete_maps_to_done(self) -> None:
        from scripts.triage import normalize_status

        norm, conf = normalize_status("complete")
        assert norm == "done"
        assert conf == "high"

    def test_implemented_maps_to_done(self) -> None:
        from scripts.triage import normalize_status

        norm, conf = normalize_status("implemented")
        assert norm == "done"
        assert conf == "high"

    def test_closed_maps_to_done_medium(self) -> None:
        from scripts.triage import normalize_status

        norm, conf = normalize_status("closed")
        assert norm == "done"
        assert conf == "medium"

    def test_planning_maps_to_open_medium(self) -> None:
        from scripts.triage import normalize_status

        norm, conf = normalize_status("planning")
        assert norm == "open"
        assert conf == "medium"

    def test_implementing_maps_to_in_progress(self) -> None:
        from scripts.triage import normalize_status

        norm, conf = normalize_status("implementing")
        assert norm == "in_progress"
        assert conf == "high"

    def test_unknown_status_returns_open_low(self) -> None:
        from scripts.triage import normalize_status

        norm, conf = normalize_status("something-weird")
        assert norm == "open"
        assert conf == "low"

    def test_unknown_status_emits_warning(self) -> None:
        """Unknown statuses must warn before defaulting to open."""
        import warnings

        from scripts.triage import normalize_status

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            norm, conf = normalize_status("archived")
        assert norm == "open"
        assert conf == "low"
        assert len(w) == 1
        assert "archived" in str(w[0].message)
        assert "open" in str(w[0].message)


class TestReadOpenTickets:
    def test_filters_out_done_and_wontfix(self, tmp_path: Path) -> None:
        from scripts.triage import read_open_tickets

        (tmp_path / "a.md").write_text(TICKET_DEFERRED)
        (tmp_path / "b.md").write_text(TICKET_DONE)
        result = read_open_tickets(tmp_path)
        assert len(result) == 1
        assert result[0]["id"] == "T-20260228-01"

    def test_includes_normalized_status(self, tmp_path: Path) -> None:
        from scripts.triage import read_open_tickets

        (tmp_path / "a.md").write_text(TICKET_LEGACY_COMPLETE)
        (tmp_path / "b.md").write_text(TICKET_LEGACY_PLANNING)
        result = read_open_tickets(tmp_path)
        # complete → done (filtered out), planning → open (kept)
        assert len(result) == 1
        assert result[0]["id"] == "handoff-search"
        assert result[0]["status_raw"] == "planning"
        assert result[0]["status_normalized"] == "open"
        assert result[0]["normalization_confidence"] == "medium"

    def test_empty_dir(self, tmp_path: Path) -> None:
        from scripts.triage import read_open_tickets

        result = read_open_tickets(tmp_path)
        assert result == []

    def test_nonexistent_dir(self, tmp_path: Path) -> None:
        from scripts.triage import read_open_tickets

        result = read_open_tickets(tmp_path / "nonexistent")
        assert result == []

    def test_skips_malformed_tickets(self, tmp_path: Path) -> None:
        from scripts.triage import read_open_tickets

        (tmp_path / "good.md").write_text(TICKET_DEFERRED)
        (tmp_path / "bad.md").write_text("# No YAML here\n\nJust text.")
        result = read_open_tickets(tmp_path)
        assert len(result) == 1


HANDOFF_WITH_OPEN_QUESTIONS = """\
---
title: Test handoff
date: 2026-02-28
session_id: aaaa-bbbb-cccc-dddd-eeeeeeeeeeee
---

## Decisions

Some decision.

## Open Questions

- Should we refactor the parser?
- Is T-20260228-01 still relevant?
- What about the auth module?

## Risks

- Deadline is tight
- T-004 may block this work
"""

HANDOFF_NO_OPEN_QUESTIONS = """\
---
title: Clean handoff
date: 2026-02-28
session_id: ffff-0000-1111-2222-333344445555
---

## Decisions

Clean session.
"""

TICKET_WITH_PROVENANCE = """\
# T-20260228-03: Ticket with provenance

```yaml
id: T-20260228-03
date: 2026-02-28
status: deferred
priority: medium
provenance:
  source_session: "aaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
  source_type: handoff
  created_by: defer-skill
```

## Problem

Has provenance.

<!-- defer-meta {"v":1,"source_session":"aaaa-bbbb-cccc-dddd-eeeeeeeeeeee","source_type":"handoff","source_ref":"test","created_by":"defer-skill"} -->
"""


class TestExtractHandoffItems:
    def test_extracts_list_items_from_open_questions(self) -> None:
        from scripts.triage import extract_handoff_items

        items, skipped = extract_handoff_items(HANDOFF_WITH_OPEN_QUESTIONS, "test.md")
        questions = [i for i in items if i["section"] == "Open Questions"]
        assert len(questions) == 3
        assert "refactor the parser" in questions[0]["text"]

    def test_extracts_list_items_from_risks(self) -> None:
        from scripts.triage import extract_handoff_items

        items, skipped = extract_handoff_items(HANDOFF_WITH_OPEN_QUESTIONS, "test.md")
        risks = [i for i in items if i["section"] == "Risks"]
        assert len(risks) == 2

    def test_returns_empty_for_no_sections(self) -> None:
        from scripts.triage import extract_handoff_items

        items, skipped = extract_handoff_items(HANDOFF_NO_OPEN_QUESTIONS, "clean.md")
        assert items == []

    def test_includes_session_id(self) -> None:
        from scripts.triage import extract_handoff_items

        items, skipped = extract_handoff_items(HANDOFF_WITH_OPEN_QUESTIONS, "test.md")
        assert all(i["session_id"] == "aaaa-bbbb-cccc-dddd-eeeeeeeeeeee" for i in items)

    def test_returns_skipped_prose_count(self) -> None:
        """P1-4: Verify prose lines are counted, not extracted."""
        from scripts.triage import extract_handoff_items

        handoff_with_prose = """\
---
title: Prose test
session_id: test-session
---

## Open Questions

- List item one
Some prose paragraph that is not a list item.
- List item two
"""
        items, skipped = extract_handoff_items(handoff_with_prose, "prose.md")
        assert len(items) == 2
        assert skipped >= 1


class TestMatchOrphans:
    def test_uid_match(self, tmp_path: Path) -> None:
        from scripts.triage import match_orphan_item

        (tmp_path / "ticket.md").write_text(TICKET_WITH_PROVENANCE)
        tickets = _load_all_tickets(tmp_path)

        item = {
            "text": "Should we refactor?",
            "section": "Open Questions",
            "session_id": "aaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
            "handoff": "test.md",
        }
        result = match_orphan_item(item, tickets)
        assert result["match_type"] == "uid_match"
        assert result["matched_ticket"] == "T-20260228-03"

    def test_ticket_id_reference(self, tmp_path: Path) -> None:
        from scripts.triage import match_orphan_item

        (tmp_path / "ticket.md").write_text(TICKET_DEFERRED)
        tickets = _load_all_tickets(tmp_path)

        item = {
            "text": "Is T-20260228-01 still relevant?",
            "section": "Open Questions",
            "session_id": "no-match-session",
            "handoff": "test.md",
        }
        result = match_orphan_item(item, tickets)
        assert result["match_type"] == "id_ref"

    def test_manual_review_fallback(self, tmp_path: Path) -> None:
        from scripts.triage import match_orphan_item

        (tmp_path / "ticket.md").write_text(TICKET_DEFERRED)
        tickets = _load_all_tickets(tmp_path)

        item = {
            "text": "What about the auth module?",
            "section": "Open Questions",
            "session_id": "no-match",
            "handoff": "test.md",
        }
        result = match_orphan_item(item, tickets)
        assert result["match_type"] == "manual_review"

    def test_legacy_ticket_id_match(self, tmp_path: Path) -> None:
        from scripts.triage import match_orphan_item

        (tmp_path / "legacy.md").write_text(TICKET_LEGACY_COMPLETE)
        tickets = _load_all_tickets(tmp_path)

        item = {
            "text": "T-004 may block this work",
            "section": "Risks",
            "session_id": "irrelevant",
            "handoff": "test.md",
        }
        result = match_orphan_item(item, tickets)
        assert result["match_type"] == "id_ref"

    def test_hyphenated_handoff_id_match(self, tmp_path: Path) -> None:
        """P1-11 fix: handoff-quality-hook should match, not truncate to handoff-quality."""
        from scripts.triage import match_orphan_item

        # Create a ticket with a hyphenated handoff-style ID
        handoff_ticket = TICKET_DEFERRED.replace("T-20260228-01", "handoff-quality-hook")
        (tmp_path / "hqh.md").write_text(handoff_ticket)
        tickets = _load_all_tickets(tmp_path)

        item = {
            "text": "handoff-quality-hook needs review",
            "section": "Open Questions",
            "session_id": "no-match",
            "handoff": "test.md",
        }
        result = match_orphan_item(item, tickets)
        assert result["match_type"] == "id_ref"
        assert result["matched_ticket"] == "handoff-quality-hook"

    def test_three_digit_sequence_id_ref(self, tmp_path: Path) -> None:
        """IDs with 3+ digit sequences (e.g. T-20260228-100) must match via id_ref."""
        from scripts.triage import match_orphan_item

        three_digit_ticket = TICKET_DEFERRED.replace("T-20260228-01", "T-20260228-100")
        (tmp_path / "overflow.md").write_text(three_digit_ticket)
        tickets = _load_all_tickets(tmp_path)

        item = {
            "text": "T-20260228-100 needs follow-up",
            "section": "Open Questions",
            "session_id": "no-match",
            "handoff": "test.md",
        }
        result = match_orphan_item(item, tickets)
        assert result["match_type"] == "id_ref"
        assert result["matched_ticket"] == "T-20260228-100"


def _load_all_tickets(tickets_dir: Path) -> list[dict]:
    """Helper to load all tickets for matching tests."""
    from scripts.triage import _load_tickets_for_matching

    return _load_tickets_for_matching(tickets_dir)


class TestGenerateReport:
    def test_report_structure(self, tmp_path: Path) -> None:
        from scripts.triage import generate_report

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        (tickets_dir / "a.md").write_text(TICKET_DEFERRED)

        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()
        (handoffs_dir / "test.md").write_text(HANDOFF_WITH_OPEN_QUESTIONS)

        report = generate_report(tickets_dir, handoffs_dir)
        assert "open_tickets" in report
        assert "orphaned_items" in report
        assert "matched_items" in report
        assert "match_counts" in report
        assert "skipped_prose_count" in report

    def test_match_counts_reflect_actual_matching(self, tmp_path: Path) -> None:
        """P2-2 fix: assert specific count values, not identity."""
        from scripts.triage import generate_report

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        (tickets_dir / "a.md").write_text(TICKET_DEFERRED)
        (tickets_dir / "b.md").write_text(TICKET_WITH_PROVENANCE)

        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()
        (handoffs_dir / "test.md").write_text(HANDOFF_WITH_OPEN_QUESTIONS)

        report = generate_report(tickets_dir, handoffs_dir)
        counts = report["match_counts"]
        # HANDOFF_WITH_OPEN_QUESTIONS has 5 items (3 Open Questions + 2 Risks)
        # Session_id matches TICKET_WITH_PROVENANCE → all 5 items get uid_match
        # P2-8 fix: exact counts for deterministic fixture, not >= 1
        assert counts["uid_match"] == 5, "All 5 items should uid_match via session correlation"
        assert counts["id_ref"] == 0, "uid_match takes priority over id_ref"
        assert counts["manual_review"] == 0, "All items matched via uid_match"
        # P1-1: orphaned_items only contains manual_review items
        assert len(report["orphaned_items"]) == counts["manual_review"]
        # matched_items contains uid_match + id_ref
        assert len(report["matched_items"]) == counts["uid_match"] + counts["id_ref"]

    def test_empty_dirs(self, tmp_path: Path) -> None:
        from scripts.triage import generate_report

        report = generate_report(tmp_path / "no-tickets", tmp_path / "no-handoffs")
        assert report["open_tickets"] == []
        assert report["orphaned_items"] == []
        assert report["matched_items"] == []

    def test_includes_archive(self, tmp_path: Path) -> None:
        from scripts.triage import generate_report

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        handoffs_dir = tmp_path / "handoffs"
        archive_dir = handoffs_dir / "archive"
        archive_dir.mkdir(parents=True)
        (archive_dir / "archived.md").write_text(HANDOFF_WITH_OPEN_QUESTIONS)

        report = generate_report(tickets_dir, handoffs_dir)
        # Should find items from archived handoff (all manual_review since no matching tickets)
        assert len(report["orphaned_items"]) > 0

    def test_excludes_old_files(self, tmp_path: Path) -> None:
        """P1-10 fix: files older than 30 days should be excluded by mtime filter."""
        import os
        import time

        from scripts.triage import generate_report

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()
        old_file = handoffs_dir / "old.md"
        old_file.write_text(HANDOFF_WITH_OPEN_QUESTIONS)

        # Set mtime to 31 days ago
        old_mtime = time.time() - (31 * 86400)
        os.utime(old_file, (old_mtime, old_mtime))

        report = generate_report(tickets_dir, handoffs_dir)
        assert len(report["orphaned_items"]) == 0, "Files older than 30 days should be excluded"

    def test_skips_unreadable_handoff_with_warning(self, tmp_path: Path) -> None:
        """Unreadable handoff files must warn and not crash the report."""
        import warnings

        from scripts.triage import generate_report

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()
        # Write a file with invalid UTF-8
        (handoffs_dir / "bad.md").write_bytes(b"\xff\xfe invalid utf8")
        (handoffs_dir / "good.md").write_text(HANDOFF_WITH_OPEN_QUESTIONS)

        with warnings.catch_warnings(record=True) as w:
            warnings.simplefilter("always")
            report = generate_report(tickets_dir, handoffs_dir)
        # good.md items should still be processed
        assert len(report["orphaned_items"]) > 0
        assert any("Cannot read handoff file" in str(x.message) for x in w)


class TestMain:
    def test_json_output(self, tmp_path: Path, capsys) -> None:
        from scripts.triage import main

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        (tickets_dir / "a.md").write_text(TICKET_DEFERRED)

        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()

        main(["--tickets-dir", str(tickets_dir), "--handoffs-dir", str(handoffs_dir)])
        output = capsys.readouterr().out
        report = json.loads(output)
        assert report["open_tickets"][0]["id"] == "T-20260228-01"


class TestEndToEnd:
    """Integration test: tickets + handoffs → generate_report with all match types."""

    def test_full_triage_pipeline(self, tmp_path: Path) -> None:
        from scripts.triage import generate_report

        # Setup: tickets directory with diverse tickets
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        (tickets_dir / "deferred.md").write_text(TICKET_DEFERRED)      # non-terminal, open
        (tickets_dir / "done.md").write_text(TICKET_DONE)              # terminal, filtered out
        (tickets_dir / "legacy.md").write_text(TICKET_LEGACY_COMPLETE) # terminal (complete→done)
        (tickets_dir / "prov.md").write_text(TICKET_WITH_PROVENANCE)   # has provenance

        # Setup: handoffs directory
        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()
        (handoffs_dir / "test.md").write_text(HANDOFF_WITH_OPEN_QUESTIONS)

        report = generate_report(tickets_dir, handoffs_dir)

        # Verify open_tickets: only non-terminal tickets
        open_ids = {t["id"] for t in report["open_tickets"]}
        assert "T-20260228-01" in open_ids    # deferred
        assert "T-20260228-03" in open_ids    # deferred (with provenance)
        assert "T-20260228-02" not in open_ids # done
        assert "T-004" not in open_ids         # complete → done

        # Verify match counts
        counts = report["match_counts"]
        total_items = counts["uid_match"] + counts["id_ref"] + counts["manual_review"]
        assert total_items == 5  # HANDOFF_WITH_OPEN_QUESTIONS has 3 Open Questions + 2 Risks

        # uid_match should be present (session_id matches TICKET_WITH_PROVENANCE)
        assert counts["uid_match"] > 0

        # P1-1: orphaned_items contains only manual_review items
        assert len(report["orphaned_items"]) == counts["manual_review"]
        # matched_items contains uid_match + id_ref
        assert len(report["matched_items"]) == counts["uid_match"] + counts["id_ref"]


class TestDeferTriageRoundTrip:
    """P2-4: End-to-end round-trip — defer creates ticket, triage finds it."""

    def test_deferred_ticket_appears_in_triage(self, tmp_path: Path) -> None:
        from scripts.triage import generate_report

        # Step 1: Create a ticket file directly (defer.py now emits envelopes,
        # not ticket markdown — the ticket engine creates the markdown file)
        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir(parents=True)
        ticket_text = """\
# Auth module needs refactoring

```yaml
id: T-20260228-01
date: "2026-02-28"
status: open
priority: high
effort: M
provenance:
  source_type: pr-review
  source_ref: "PR #29"
  source_session: "aaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
  captured_branch: feature/auth
```

## Problem

Technical debt in auth module.

## Approach

Extract base class.

## Acceptance Criteria

- Base class created
"""
        created_path = tickets_dir / "2026-02-28-T-20260228-01-auth-module-needs-refactoring.md"
        created_path.write_text(ticket_text)

        # Step 2: Create a handoff with matching session_id
        handoffs_dir = tmp_path / "handoffs"
        handoffs_dir.mkdir()
        handoff_text = """\
---
title: Auth review session
date: 2026-02-28
session_id: aaaa-bbbb-cccc-dddd-eeeeeeeeeeee
---

## Open Questions

- Should we split the OAuth provider?

## Risks

- Migration may break existing tokens
"""
        (handoffs_dir / "auth-review.md").write_text(handoff_text)

        # Step 3: Run triage
        report = generate_report(tickets_dir, handoffs_dir)

        # Step 4: Verify the created ticket appears in open_tickets
        open_ids = {t["id"] for t in report["open_tickets"]}
        assert "T-20260228-01" in open_ids

        # Step 5: Verify handoff items match via uid_match
        assert report["match_counts"]["uid_match"] == 2  # 1 Open Question + 1 Risk
        assert len(report["matched_items"]) == 2
        for item in report["matched_items"]:
            assert item["match_type"] == "uid_match"
            assert item["matched_ticket"] == "T-20260228-01"

        # Step 6: Round-trip — parse the created ticket
        from scripts.ticket_parsing import parse_ticket

        parsed = parse_ticket(created_path)
        assert parsed is not None
        assert parsed.frontmatter["id"] == "T-20260228-01"
        assert parsed.frontmatter["provenance"]["source_session"] == "aaaa-bbbb-cccc-dddd-eeeeeeeeeeee"

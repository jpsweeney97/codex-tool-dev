"""Tests for deterministic autonomy candidate discovery."""

from __future__ import annotations

import textwrap
from pathlib import Path

from scripts.ticket_candidate_discovery import discover_candidate_mutations


def _ticket_yaml_list(values: list[str]) -> str:
    if not values:
        return "[]"
    return "[" + ", ".join(values) + "]"


def _write_ticket(
    tickets_dir: Path,
    *,
    ticket_id: str,
    key_file_paths: list[str] | None = None,
    related_paths: list[str] | None = None,
) -> Path:
    tickets_dir.mkdir(parents=True, exist_ok=True)
    path = tickets_dir / f"{ticket_id.lower()}.md"
    path.write_text(
        textwrap.dedent(
            f"""\
            # {ticket_id}: Example

            ```yaml
            id: {ticket_id}
            date: "2026-05-27"
            status: open
            priority: medium
            source:
              type: test
              ref: ""
              session: test
            tags: []
            blocked_by: []
            blocks: []
            contract_version: "1.0"
            key_file_paths: {_ticket_yaml_list(key_file_paths or [])}
            related_paths: {_ticket_yaml_list(related_paths or [])}
            ```

            ## Problem
            Example problem.
            """
        ),
        encoding="utf-8",
    )
    return path


def _context(**overrides: object) -> dict[str, object]:
    data: dict[str, object] = {
        "schema": "codex.ticket.turn_context.v1",
        "thread_id": "thread-1",
        "turn_id": "turn-1",
    }
    data.update(overrides)
    return data


def test_discovers_explicit_candidate_mutations(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "proposed_change": {"priority": "high"},
                "reason": "Codex identified a clear priority update.",
            }
        ]
    )

    candidates = discover_candidate_mutations(context, tickets_dir)

    assert len(candidates) == 1
    assert candidates[0].ticket_id == "T-20260527-01"
    assert candidates[0].action == "update"
    assert candidates[0].proposed_change == {"priority": "high"}
    assert candidates[0].evidence[0].kind == "codex_candidate"
    assert candidates[0].ticket_change_scope == "current_branch"


def test_structured_candidates_may_supply_bounded_ticket_change_scope(
    tmp_path: Path,
) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "proposed_change": {"priority": "high"},
                "ticket_change_scope": "unrelated_backlog",
            },
            {
                "ticket_id": "T-20260527-02",
                "action": "update",
                "proposed_change": {"priority": "low"},
                "ticket_change_scope": "outside_contract",
            },
        ]
    )

    candidates = discover_candidate_mutations(context, tickets_dir)

    assert [candidate.ticket_change_scope for candidate in candidates] == [
        "unrelated_backlog",
        "current_branch",
    ]
    assert [candidate.proposed_change for candidate in candidates] == [
        {"priority": "high"},
        {"priority": "low"},
    ]


def test_discovers_ticket_ids_mentioned_in_request_and_summary(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        user_request="Please check T-20260527-01 after this fix.",
        assistant_work_summary="This also appears to resolve T-20260527-02.",
    )

    candidates = discover_candidate_mutations(context, tickets_dir)

    assert [candidate.ticket_id for candidate in candidates] == [
        "T-20260527-01",
        "T-20260527-02",
    ]
    assert {candidate.evidence[0].kind for candidate in candidates} == {"explicit_ticket_id"}


def test_matches_related_paths_against_ticket_metadata(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    _write_ticket(
        tickets_dir,
        ticket_id="T-20260527-01",
        key_file_paths=["plugins/turbo-mode/ticket/scripts/ticket_update.py"],
    )
    _write_ticket(
        tickets_dir,
        ticket_id="T-20260527-02",
        related_paths=["plugins/turbo-mode/ticket/scripts/ticket_capture.py"],
    )
    context = _context(
        touched_files=[
            "plugins/turbo-mode/ticket/scripts/ticket_update.py",
            "plugins/turbo-mode/ticket/scripts/ticket_capture.py",
        ]
    )

    candidates = discover_candidate_mutations(context, tickets_dir)

    assert [candidate.ticket_id for candidate in candidates] == [
        "T-20260527-01",
        "T-20260527-02",
    ]
    assert {candidate.evidence[0].kind for candidate in candidates} == {"related_path"}
    assert {candidate.ticket_change_scope for candidate in candidates} == {"current_branch"}


def test_matches_diff_and_test_file_references_to_tickets(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    _write_ticket(
        tickets_dir,
        ticket_id="T-20260527-01",
        related_paths=["plugins/turbo-mode/ticket/scripts/ticket_runtime.py"],
    )
    _write_ticket(
        tickets_dir,
        ticket_id="T-20260527-02",
        key_file_paths=["plugins/turbo-mode/ticket/tests/test_runtime.py"],
    )
    context = _context(
        diff_files=["plugins/turbo-mode/ticket/scripts/ticket_runtime.py"],
        test_files=["plugins/turbo-mode/ticket/tests/test_runtime.py"],
    )

    candidates = discover_candidate_mutations(context, tickets_dir)

    assert [candidate.ticket_id for candidate in candidates] == [
        "T-20260527-01",
        "T-20260527-02",
    ]
    assert {candidate.evidence[0].kind for candidate in candidates} == {
        "diff_path",
        "test_path",
    }


def test_codex_supplied_vague_candidates_are_preserved_for_discussion(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        possible_candidates=[
            {
                "ticket_id": "T-20260527-03",
                "action": "update",
                "reason": "Maybe later cleanup theme is too broad to apply automatically.",
            }
        ]
    )

    candidates = discover_candidate_mutations(context, tickets_dir)

    assert len(candidates) == 1
    assert candidates[0].ticket_id == "T-20260527-03"
    assert candidates[0].proposed_change == {
        "requires_discussion": True,
        "reason": "Maybe later cleanup theme is too broad to apply automatically.",
    }
    assert candidates[0].evidence[0].kind == "codex_possible_candidate"

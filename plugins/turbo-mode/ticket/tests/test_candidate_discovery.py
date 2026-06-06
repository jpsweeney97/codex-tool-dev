"""Tests for deterministic autonomy candidate discovery."""

from __future__ import annotations

from pathlib import Path

import pytest
from scripts.ticket_candidate_discovery import (
    InvalidCandidateMutations,
    discover_candidate_mutations,
)


def _write_ticket(
    tickets_dir: Path,
    *,
    ticket_id: str,
    related_paths: list[str] | None = None,
) -> Path:
    tickets_dir.mkdir(parents=True, exist_ok=True)
    path = tickets_dir / f"{ticket_id}.md"
    paths = related_paths or []
    path.write_text(
        (
            "---\n"
            f"id: {ticket_id}\n"
            "title: Example\n"
            "status: open\n"
            "priority: normal\n"
            "tags: []\n"
            f"related_paths: {paths}\n"
            "blocked_by: []\n"
            "---\n\n"
            "## Problem\n"
            "Example problem.\n\n"
            "## Next Action\n"
            "Continue work on this ticket.\n\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | test | Created target fixture.\n"
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


def test_discovers_explicit_target_candidate_mutations(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "target": {"fields": ["priority"], "sections": []},
                "proposed_change": {"priority": "high"},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Codex identified a clear priority update.",
            }
        ]
    )

    candidates = discover_candidate_mutations(context, tickets_dir)

    assert len(candidates) == 1
    assert candidates[0].ticket_id == "T-20260527-01"
    assert candidates[0].action == "update"
    assert candidates[0].target.fields == ("priority",)
    assert candidates[0].target.sections == ()
    assert candidates[0].proposed_change == {"priority": "high"}
    assert candidates[0].expected_ticket_fingerprint == "state-T-20260527-01"
    assert candidates[0].evidence_summary == "Codex identified a clear priority update."


def test_structured_candidates_reject_deprecated_ticket_change_scope(
    tmp_path: Path,
) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "target": {"fields": ["priority"], "sections": []},
                "proposed_change": {"priority": "high"},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Priority changed.",
                "ticket_change_scope": "unrelated_backlog",
            },
        ]
    )

    with pytest.raises(InvalidCandidateMutations) as exc_info:
        discover_candidate_mutations(context, tickets_dir)

    assert exc_info.value.as_payload() == [
        {
            "key": "candidate_mutations",
            "index": 0,
            "errors": ["unknown candidate keys: ['ticket_change_scope']"],
        }
    ]


@pytest.mark.parametrize(
    "context_key",
    ("candidate_mutations", "update_candidates", "capture_candidates"),
)
def test_malformed_explicit_candidate_arrays_raise_invalid_candidate(
    tmp_path: Path,
    context_key: str,
) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        **{
            context_key: [
                {
                    "ticket_id": "T-20260527-01",
                    "action": "update",
                    "target": {"fields": ["priority"], "sections": []},
                    "proposed_change": {"priority": "high"},
                    "expected_ticket_fingerprint": "state-T-20260527-01",
                },
            ]
        }
    )

    with pytest.raises(InvalidCandidateMutations) as exc_info:
        discover_candidate_mutations(context, tickets_dir)

    assert exc_info.value.as_payload() == [
        {
            "key": context_key,
            "index": 0,
            "errors": ["missing candidate keys: ['evidence_summary']"],
        }
    ]


def test_id_only_mentions_do_not_create_mutation_candidates(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        user_request="Please check T-20260527-01 after this fix.",
        assistant_work_summary="This also appears to resolve T-20260527-02.",
    )

    candidates = discover_candidate_mutations(context, tickets_dir)

    assert candidates == ()


def test_vague_and_path_only_signals_do_not_create_write_candidates(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    _write_ticket(
        tickets_dir,
        ticket_id="T-20260527-01",
        related_paths=["plugins/turbo-mode/ticket/scripts/ticket_update.py"],
    )
    context = _context(
        touched_files=["plugins/turbo-mode/ticket/scripts/ticket_update.py"],
        possible_candidates=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "reason": "Maybe later cleanup theme is too broad to apply automatically.",
            }
        ],
    )

    assert discover_candidate_mutations(context, tickets_dir) == ()


def test_review_hygiene_findings_do_not_create_write_candidates(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        review_hygiene_findings=[
            {
                "ticket_id": "T-20260527-01",
                "action": "stale_cleanup",
                "reason": "Ticket is stale enough to mention in review output.",
            }
        ],
    )

    assert discover_candidate_mutations(context, tickets_dir) == ()


def test_discovery_keeps_distinct_target_candidates_with_same_summary(
    tmp_path: Path,
) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "target": {"fields": ["priority"], "sections": []},
                "proposed_change": {"priority": "high"},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Current turn justifies a ticket update.",
            },
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "target": {"fields": [], "sections": ["Next Action"]},
                "proposed_change": {
                    "Next Action": "Finish the exact contract migration."
                },
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Current turn justifies a ticket update.",
            },
        ]
    )

    candidates = discover_candidate_mutations(context, tickets_dir)

    assert len(candidates) == 2
    assert candidates[0].proposed_change == {"priority": "high"}
    assert candidates[1].proposed_change == {
        "Next Action": "Finish the exact contract migration."
    }


def test_deprecated_write_candidate_actions_are_not_accepted(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": action,
                "target": {"fields": ["priority"], "sections": []},
                "proposed_change": {"priority": "high"},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Priority changed.",
            }
            for action in ("reprioritize", "stale_cleanup", "blocker_edit", "refine")
        ]
    )

    with pytest.raises(InvalidCandidateMutations) as exc_info:
        discover_candidate_mutations(context, tickets_dir)

    assert exc_info.value.as_payload() == [
        {
            "key": "candidate_mutations",
            "index": index,
            "errors": [
                "action must be one of "
                "['correct', 'create', 'done', 'reopen', 'update', 'wontfix']"
            ],
        }
        for index in range(4)
    ]

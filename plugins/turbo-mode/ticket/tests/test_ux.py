from __future__ import annotations

import re
from pathlib import Path
from typing import get_args

import pytest
from scripts.ticket_parse import parse_ticket
from scripts.ticket_runtime_readiness import RuntimeReadinessErrorCode
from scripts.ticket_ux import (
    INTERNAL_RECOVERY_PATH_PATTERNS,
    INTERNAL_RECOVERY_TERMS,
    RECOVERY_HINTS,
    attach_recovery_hint,
    close_readiness,
    humanize_state,
    recovery_hint,
    recovery_hint_code_for_response,
    ticket_identity,
)

from tests.support.builders import make_gen1_ticket, make_ticket


def test_ticket_identity_uses_content_id_before_filename(tmp_tickets: Path) -> None:
    path = make_ticket(
        tmp_tickets,
        "2026-05-03-readable-slug.md",
        id="T-20260503-07",
        title="Readable slug is not identity",
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    identity = ticket_identity(ticket)

    assert identity == {
        "id": "T-20260503-07",
        "title": "Readable slug is not identity",
        "path": str(path),
        "filename": "T-20260503-07.md",
    }


def test_humanize_state_replaces_internal_terms() -> None:
    assert humanize_state("duplicate_candidate") == "Potential duplicate found"
    assert humanize_state("policy_blocked") == "Blocked by ticket policy"
    assert humanize_state("target_fingerprint") == "Ticket changed since read"


def test_close_readiness_reports_missing_acceptance_criteria(tmp_tickets: Path) -> None:
    path = make_ticket(
        tmp_tickets,
        "2026-05-03-no-criteria.md",
        id="T-20260503-08",
        extra_sections="\n",
    )
    text = path.read_text(encoding="utf-8")
    text = text.replace("## Acceptance Criteria\n- [ ] Issue resolved\n\n", "")
    path.write_text(text, encoding="utf-8")
    ticket = parse_ticket(path)
    assert ticket is not None

    result = close_readiness(ticket, tmp_tickets, resolution="done")

    assert result["ready"] is False
    assert result["error_code"] == "invalid_transition"
    assert result["missing"] == ["acceptance_criteria"]
    assert result["allowed_actions"] == [
        "add acceptance criteria",
        "close as wontfix",
        "keep current status",
    ]


def test_close_readiness_allows_wontfix_without_acceptance_criteria(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "2026-05-03-wontfix.md", id="T-20260503-09")
    text = path.read_text(encoding="utf-8")
    text = text.replace("## Acceptance Criteria\n- [ ] Issue resolved\n\n", "")
    path.write_text(text, encoding="utf-8")
    ticket = parse_ticket(path)
    assert ticket is not None

    result = close_readiness(ticket, tmp_tickets, resolution="wontfix")

    assert result["ready"] is True
    assert result["missing"] == []
    assert result["allowed_actions"] == ["close as wontfix"]


@pytest.mark.parametrize("status", ["done", "wontfix"])
def test_close_readiness_rejects_terminal_tickets(tmp_tickets: Path, status: str) -> None:
    path = make_ticket(
        tmp_tickets,
        f"2026-05-03-terminal-{status}.md",
        id=f"T-20260503-{10 if status == 'done' else 11}",
        status=status,
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    result = close_readiness(ticket, tmp_tickets, resolution="done")

    assert result["ready"] is False
    assert result["error_code"] == "invalid_transition"
    assert result["status"] == status
    assert result["allowed_actions"] == ["reopen before closing", "keep current status"]


def test_close_readiness_rejects_legacy_tickets(tmp_tickets: Path) -> None:
    path = make_gen1_ticket(tmp_tickets, "legacy.md")
    ticket = parse_ticket(path)
    assert ticket is None


def test_close_readiness_reports_open_blocker(tmp_tickets: Path) -> None:
    make_ticket(tmp_tickets, "blocker.md", id="T-20260503-12", status="open")
    path = make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-13",
        status="blocked",
        blocked_by=["T-20260503-12"],
        blocked_on="Waiting for the blocker to finish.",
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    result = close_readiness(ticket, tmp_tickets, resolution="done")

    assert result["ready"] is False
    assert result["error_code"] == "dependency_blocked"
    assert result["blocking_ids"] == ["T-20260503-12"]
    assert result["missing_blockers"] == []
    assert result["unresolved_blockers"] == ["T-20260503-12"]
    assert result["allowed_actions"] == [
        "resolve blockers",
        "close as wontfix",
        "keep current status",
    ]


def test_close_readiness_reports_missing_blocker_reference(tmp_tickets: Path) -> None:
    path = make_ticket(
        tmp_tickets,
        "missing-blocker.md",
        id="T-20260503-14",
        status="blocked",
        blocked_by=["T-20260503-99"],
        blocked_on="Waiting for a missing blocker.",
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    result = close_readiness(ticket, tmp_tickets, resolution="done")

    assert result["ready"] is False
    assert result["error_code"] == "dependency_blocked"
    assert result["blocking_ids"] == ["T-20260503-99"]
    assert result["missing_blockers"] == ["T-20260503-99"]
    assert result["unresolved_blockers"] == []


def test_close_readiness_error_code_matches_close_policy_for_terminal_ticket(
    tmp_tickets: Path,
) -> None:
    from scripts.ticket_engine_core import _execute_close

    path = make_ticket(tmp_tickets, "terminal-parity.md", id="T-20260503-15", status="done")
    ticket = parse_ticket(path)
    assert ticket is not None

    readiness = close_readiness(ticket, tmp_tickets, resolution="done")
    close_response = _execute_close(
        "T-20260503-15",
        {"resolution": "done"},
        "session-parity",
        "user",
        tmp_tickets,
    )

    assert readiness["error_code"] == close_response.error_code
    assert readiness["ready"] is False


def test_close_readiness_error_code_matches_close_policy_for_missing_acceptance_criteria(
    tmp_tickets: Path,
) -> None:
    from scripts.ticket_engine_core import _execute_close

    path = make_ticket(
        tmp_tickets,
        "missing-ac-parity.md",
        id="T-20260503-16",
        status="open",
    )
    text = path.read_text(encoding="utf-8")
    path.write_text(
        text.replace("## Acceptance Criteria\n- [ ] Issue resolved\n\n", ""),
        encoding="utf-8",
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    readiness = close_readiness(ticket, tmp_tickets, resolution="done")
    close_response = _execute_close(
        "T-20260503-16",
        {"resolution": "done"},
        "session-parity",
        "user",
        tmp_tickets,
    )

    assert readiness["error_code"] == close_response.error_code
    assert readiness["ready"] is False


def test_close_readiness_error_code_matches_close_policy_for_blocked_ticket(
    tmp_tickets: Path,
) -> None:
    from scripts.ticket_engine_core import _execute_close

    make_ticket(tmp_tickets, "blocker-parity.md", id="T-20260503-17", status="open")
    path = make_ticket(
        tmp_tickets,
        "blocked-parity.md",
        id="T-20260503-18",
        status="blocked",
        blocked_by=["T-20260503-17"],
        blocked_on="Waiting for the blocker to finish.",
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    readiness = close_readiness(ticket, tmp_tickets, resolution="done")
    close_response = _execute_close(
        "T-20260503-18",
        {"resolution": "done"},
        "session-parity",
        "user",
        tmp_tickets,
    )

    assert readiness["error_code"] == close_response.error_code
    assert readiness["ready"] is False


def test_close_readiness_error_code_matches_close_policy_for_legacy_ticket(
    tmp_tickets: Path,
) -> None:
    path = make_gen1_ticket(tmp_tickets, "legacy-parity.md")
    ticket = parse_ticket(path)
    assert ticket is None


def test_close_readiness_error_code_matches_close_policy_for_invalid_resolution(
    tmp_tickets: Path,
) -> None:
    from scripts.ticket_engine_core import _execute_close

    path = make_ticket(
        tmp_tickets,
        "invalid-resolution-parity.md",
        id="T-20260503-19",
        status="open",
    )
    ticket = parse_ticket(path)
    assert ticket is not None

    readiness = close_readiness(ticket, tmp_tickets, resolution="blocked")
    close_response = _execute_close(
        "T-20260503-19",
        {"resolution": "blocked"},
        "session-parity",
        "user",
        tmp_tickets,
    )

    assert readiness["error_code"] == close_response.error_code
    assert readiness["ready"] is False


def test_close_readiness_ready_matches_close_policy_for_successful_close(tmp_tickets: Path) -> None:
    from scripts.ticket_engine_core import _execute_close

    path = make_ticket(tmp_tickets, "success-parity.md", id="T-20260503-20", status="open")
    ticket = parse_ticket(path)
    assert ticket is not None

    readiness = close_readiness(ticket, tmp_tickets, resolution="done")
    close_response = _execute_close(
        "T-20260503-20",
        {"resolution": "done"},
        "session-parity",
        "user",
        tmp_tickets,
    )

    assert readiness["ready"] is True
    assert close_response.state == "ok"


def test_recovery_hint_contract_is_transcript_safe() -> None:
    expected_codes = {
        *get_args(RuntimeReadinessErrorCode),
        "stale_plan",
        "trust_setup",
        "cleanup_stale_preview",
        "policy_blocked",
        "preflight_failed",
        "host_policy_blocked",
        "deterministic_driver_unavailable",
        "hook_contract_blocked",
        "engine_gate_required",
        "runtime_readiness_required",
        "internal_error",
    }

    assert set(RECOVERY_HINTS) == expected_codes
    assert recovery_hint("trust_setup") == {
        "code": "trust_setup",
        "summary": "Ticket setup needs attention before this write can continue.",
        "next_step": (
            "Stop without writing. Run ticket-doctor diagnostics or verify the plugin "
            "hook setup before retrying."
        ),
    }
    assert recovery_hint("runtime_readiness_required") == {
        "code": "runtime_readiness_required",
        "summary": "Ticket runtime activation is required before this direct execute can continue.",
        "next_step": (
            "Run the explicit activate-runtime flow or refresh the installed Ticket runtime "
            "before retrying."
        ),
    }
    assert recovery_hint("stale_proof") == {
        "code": "stale_proof",
        "summary": "The Ticket runtime proof has expired.",
        "next_step": "Rerun the explicit activate-runtime flow before retrying direct execute.",
    }
    for code in expected_codes:
        hint = recovery_hint(code)
        assert set(hint) == {"code", "summary", "next_step"}
        rendered = " ".join([hint["summary"], hint["next_step"]])
        for term in INTERNAL_RECOVERY_TERMS:
            assert term.lower() not in rendered.lower()
        for pattern in INTERNAL_RECOVERY_PATH_PATTERNS:
            assert re.search(pattern, rendered) is None


def test_attach_recovery_hint_preserves_response_data() -> None:
    response = {
        "state": "preflight_failed",
        "message": "Ticket checks did not pass.",
        "error_code": "preflight_failed",
        "data": {"checks_failed": ["missing_acceptance_criteria"]},
    }

    updated = attach_recovery_hint(response, "preflight_failed")

    assert updated["data"]["checks_failed"] == ["missing_acceptance_criteria"]
    assert updated["data"]["recovery_hint"] == {
        "code": "preflight_failed",
        "summary": "Ticket checks did not pass.",
        "next_step": "Review the failed checks, update the request or ticket, then retry.",
    }
    assert "recovery_hint" not in response["data"]


def test_recovery_hint_code_for_runtime_activation_errors() -> None:
    assert recovery_hint_code_for_response({"error_code": "host_policy_blocked"}) == (
        "host_policy_blocked"
    )
    assert recovery_hint_code_for_response({"error_code": "deterministic_driver_unavailable"}) == (
        "deterministic_driver_unavailable"
    )
    assert recovery_hint_code_for_response({"error_code": "hook_contract_blocked"}) == (
        "hook_contract_blocked"
    )
    assert recovery_hint_code_for_response({"error_code": "engine_gate_required"}) == (
        "engine_gate_required"
    )
    assert recovery_hint_code_for_response({"error_code": "runtime_readiness_required"}) == (
        "runtime_readiness_required"
    )


def test_recovery_hint_code_for_internal_error() -> None:
    assert recovery_hint_code_for_response({"error_code": "internal_error"}) == "internal_error"
    assert RECOVERY_HINTS["internal_error"] == {
        "summary": "Ticket hit an unexpected internal error.",
        "next_step": "Stop without writing and report the error details for repair.",
    }


def test_transcript_safety_terms_match_expected_internal_leak_vocabulary() -> None:
    expected_terms = (
        "hook_injected",
        "hook_request_origin",
        "request_origin",
        "origin_mismatch",
        "verified hook provenance",
        "payload",
        "payload path",
        "payload_file",
        "envelope_path",
        "processed_path",
        "incoming_envelope_path",
        "ticket_path",
        "envelope_move_error",
        "PAYLOAD_PATH",
        "canonical command",
        "python3 -B",
        "uv run python -B",
    )

    assert tuple(INTERNAL_RECOVERY_TERMS) == expected_terms


def test_transcript_safety_path_patterns_cover_known_host_shapes() -> None:
    examples = (
        "/Users/example/project/.codex/ticket-tmp/payload.json",
        "/home/runner/work/project/payload.json",
        "/workspace/project/docs/tickets/.envelopes/item.json",
        "/workspaces/project/docs/tickets/.envelopes/item.json",
        "/private/tmp/project/tickets/.envelopes/item.json",
        "/tmp/project/payload.json",
        "/var/folders/example/payload.json",
        r"C:\Users\example\project\payload.json",
    )

    for rendered in examples:
        assert any(re.search(pattern, rendered) for pattern in INTERNAL_RECOVERY_PATH_PATTERNS), (
            rendered
        )

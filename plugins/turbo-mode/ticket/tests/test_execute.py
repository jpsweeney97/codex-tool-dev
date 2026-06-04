"""Tests for target-shaped ticket engine execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest
import scripts.ticket_engine_core as ticket_engine_core
from scripts.ticket_autonomy_config import AutomationMode, write_local_config
from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp
from scripts.ticket_dedup import target_fingerprint as compute_target_fp
from scripts.ticket_engine_core import AutonomyConfig, EngineResponse, engine_execute
from scripts.ticket_parse import parse_ticket
from scripts.ticket_read import list_tickets
from scripts.ticket_target_schema import validate_target_ticket_file

from tests.support.builders import make_ticket


def _create_response(
    tmp_tickets: Path,
    fields: dict[str, Any] | None = None,
    *,
    request_origin: str = "user",
    hook_request_origin: str | None = None,
    dedup_override: bool = False,
    duplicate_of: str | None = None,
    dedup_fingerprint: str | None = None,
    autonomy_config: AutonomyConfig | None = None,
    runtime_execute_surface: ticket_engine_core.RuntimeExecuteSurface | None = None,
) -> EngineResponse:
    create_fields = {
        "title": "Test ticket",
        "problem": "Problem statement.",
        **(fields or {}),
    }
    if dedup_fingerprint is None:
        dedup_fingerprint = compute_dedup_fp(
            create_fields.get("problem", ""),
            create_fields.get("related_paths", []),
        )
    return engine_execute(
        action="create",
        ticket_id=None,
        fields=create_fields,
        session_id="test-session",
        request_origin=request_origin,
        dedup_override=dedup_override,
        duplicate_of=duplicate_of,
        dependency_override=False,
        tickets_dir=tmp_tickets,
        hook_injected=True,
        hook_request_origin=hook_request_origin or request_origin,
        classify_intent="create",
        classify_confidence=0.95,
        dedup_fingerprint=dedup_fingerprint,
        autonomy_config=autonomy_config,
        runtime_execute_surface=runtime_execute_surface,
    )


def _execute_existing(
    tmp_tickets: Path,
    ticket_path: Path,
    *,
    action: str,
    fields: dict[str, Any],
    ticket_id: str = "T-20260302-01",
    dependency_override: bool = False,
) -> EngineResponse:
    return engine_execute(
        action=action,
        ticket_id=ticket_id,
        fields=fields,
        session_id="test-session",
        request_origin="user",
        dedup_override=False,
        dependency_override=dependency_override,
        tickets_dir=tmp_tickets,
        hook_injected=True,
        hook_request_origin="user",
        classify_intent=action,
        classify_confidence=0.95,
        target_fingerprint=compute_target_fp(ticket_path),
    )


def _make_ticket_without_acceptance_criteria(
    tickets_dir: Path,
    *,
    ticket_id: str = "T-20260302-01",
    status: str = "open",
) -> Path:
    path = tickets_dir / f"{ticket_id}.md"
    path.write_text(
        "\n".join(
            [
                "---",
                f"id: {ticket_id}",
                "title: No acceptance criteria",
                f"status: {status}",
                "priority: normal",
                "tags: []",
                "related_paths: []",
                "blocked_by: []",
                "---",
                "",
                "## Problem",
                "This target ticket intentionally has no acceptance criteria.",
                "",
                "## Next Action",
                "Add acceptance criteria before closing as done.",
                "",
                "## Change History",
                "- 2026-06-02T00:00:00Z | test | Created without acceptance criteria.",
                "",
            ]
        ),
        encoding="utf-8",
    )
    return path


def _section_text(text: str, heading: str) -> str:
    marker = f"## {heading}\n"
    start = text.index(marker)
    next_start = text.find("\n## ", start + len(marker))
    if next_start == -1:
        return text[start:]
    return text[start:next_start]


def test_unknown_runtime_execute_surface_does_not_use_direct_execute_bypass(
    tmp_tickets: Path,
) -> None:
    (tmp_tickets.parent.parent / ".git").mkdir(exist_ok=True)
    write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
    problem = "Unknown runtime execute surfaces must not widen the provenance bypass."

    response = engine_execute(
        action="create",
        ticket_id=None,
        fields={"title": "Runtime surface", "problem": problem, "priority": "normal"},
        session_id="surface-session",
        request_origin="agent",
        dedup_override=False,
        dependency_override=False,
        tickets_dir=tmp_tickets,
        hook_injected=True,
        hook_request_origin="user",
        classify_intent="create",
        classify_confidence=0.95,
        dedup_fingerprint=compute_dedup_fp(problem, []),
        autonomy_config=AutonomyConfig(mode=AutomationMode.AGENT_PRIMARY),
        runtime_execute_surface=cast(ticket_engine_core.RuntimeExecuteSurface, "agent_control"),
    )

    assert response.state == "escalate"
    assert response.error_code == "origin_mismatch"


def test_engine_response_rejects_removed_ok_states() -> None:
    with pytest.raises(ValueError, match="error_code is required"):
        EngineResponse(state="ok_create", message="legacy success state")


class TestCreate:
    def test_create_ticket_writes_target_shape(self, tmp_tickets: Path) -> None:
        response = _create_response(
            tmp_tickets,
            {
                "title": "Fix auth bug",
                "problem": "Auth times out for large payloads.",
                "priority": "high",
                "tags": ["auth"],
                "related_paths": ["handler.py"],
                "approach": "Make timeout configurable.",
                "acceptance_criteria": ["Timeout configurable", "Default remains 30s"],
                "verification": "uv run pytest tests/test_auth.py",
            },
        )

        assert response.state == "ok"
        assert response.ticket_id is not None
        ticket_path = Path(response.data["ticket_path"])
        assert ticket_path.name == f"{response.ticket_id}.md"
        assert validate_target_ticket_file(ticket_path).ok

        content = ticket_path.read_text(encoding="utf-8")
        assert content.startswith("---\nid: ")
        assert "```yaml" not in content
        assert "\ndate:" not in content
        assert "\nsource:" not in content
        assert "\ncontract_version:" not in content
        assert "## Change History" in content

        ticket = parse_ticket(ticket_path)
        assert ticket is not None
        assert ticket.priority == "high"
        assert ticket.related_paths == ["handler.py"]

    def test_create_can_write_idea_ticket(self, tmp_tickets: Path) -> None:
        response = _create_response(
            tmp_tickets,
            {
                "title": "Park design follow-up",
                "problem": "The design question is real but not actionable yet.",
                "status": "idea",
                "next_action": "Promote when the user chooses the direction.",
            },
        )

        assert response.state == "ok"
        ticket_path = Path(response.data["ticket_path"])
        text = ticket_path.read_text(encoding="utf-8")
        assert "status: idea" in text
        assert "## Blocked On" not in text
        assert validate_target_ticket_file(ticket_path).ok

    def test_create_can_write_blocked_ticket_with_visible_blocker(
        self,
        tmp_tickets: Path,
    ) -> None:
        response = _create_response(
            tmp_tickets,
            {
                "title": "Wait for deployment access",
                "problem": "Deployment validation cannot proceed without access.",
                "status": "blocked",
                "next_action": "Ask for access, then run the deployment smoke.",
                "blocked_on": "Waiting for deployment credentials from the user.",
                "blocked_by": ["T-20260508-02"],
            },
        )

        assert response.state == "ok"
        ticket_path = Path(response.data["ticket_path"])
        text = ticket_path.read_text(encoding="utf-8")
        assert "status: blocked" in text
        assert "blocked_by: [T-20260508-02]" in text
        assert "## Blocked On\nWaiting for deployment credentials from the user." in text
        assert validate_target_ticket_file(ticket_path).ok

    @pytest.mark.parametrize("status", ["done", "wontfix"])
    def test_create_rejects_terminal_statuses(self, tmp_tickets: Path, status: str) -> None:
        response = _create_response(
            tmp_tickets,
            {
                "title": "Terminal create",
                "problem": "Normal create must not create historical terminal records.",
                "status": status,
            },
        )

        assert response.state == "need_fields"
        assert response.error_code == "need_fields"
        assert "create status" in response.message
        assert list(tmp_tickets.glob("*.md")) == []

    def test_create_rejects_blocked_without_visible_blocker(self, tmp_tickets: Path) -> None:
        response = _create_response(
            tmp_tickets,
            {
                "title": "Missing blocker prose",
                "problem": "Blocked tickets need visible blocker truth.",
                "status": "blocked",
            },
        )

        assert response.state == "need_fields"
        assert response.error_code == "need_fields"
        assert "blocked_on" in response.message
        assert list(tmp_tickets.glob("*.md")) == []

    def test_create_rejects_live_blocker_fields_for_open_ticket(self, tmp_tickets: Path) -> None:
        response = _create_response(
            tmp_tickets,
            {
                "title": "Open ticket with stale blocker",
                "problem": "Open tickets must not retain live blocker fields.",
                "blocked_on": "This stale blocker should not be accepted.",
                "blocked_by": ["T-20260508-02"],
            },
        )

        assert response.state == "need_fields"
        assert response.error_code == "need_fields"
        assert "blocked" in response.message
        assert list(tmp_tickets.glob("*.md")) == []

    def test_create_defaults_priority_to_normal(self, tmp_tickets: Path) -> None:
        response = _create_response(tmp_tickets)

        assert response.state == "ok"
        ticket = parse_ticket(Path(response.data["ticket_path"]))
        assert ticket is not None
        assert ticket.priority == "normal"

    def test_create_blocks_duplicate_without_override(self, tmp_tickets: Path) -> None:
        fields = {
            "title": "Duplicate target",
            "problem": "Duplicate me",
            "priority": "normal",
            "related_paths": ["src/ticket.py"],
        }
        first = _create_response(tmp_tickets, fields)
        second = _create_response(tmp_tickets, fields)

        assert first.state == "ok"
        assert second.state == "duplicate_candidate"
        assert second.error_code == "duplicate_candidate"
        assert second.ticket_id == first.ticket_id

    def test_create_duplicate_allowed_with_override(self, tmp_tickets: Path) -> None:
        fields = {
            "title": "Duplicate override target",
            "problem": "Duplicate with override",
            "priority": "normal",
        }
        first = _create_response(tmp_tickets, fields)
        second = _create_response(
            tmp_tickets,
            fields,
            dedup_override=True,
            duplicate_of=first.ticket_id,
        )

        assert first.state == "ok"
        assert second.state == "ok"

    def test_create_retries_on_file_exists(
        self,
        tmp_tickets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        real_write = ticket_engine_core._write_text_exclusive
        attempts: list[Path] = []

        def flaky_write(ticket_path: Path, content: str) -> None:
            attempts.append(ticket_path)
            if len(attempts) == 1:
                real_write(ticket_path, content)
                raise FileExistsError("simulated collision")
            real_write(ticket_path, content)

        monkeypatch.setattr(ticket_engine_core, "_write_text_exclusive", flaky_write)

        response = _create_response(
            tmp_tickets,
            {
                "title": "Retry on collision",
                "problem": "Exclusive create should retry instead of overwriting.",
                "priority": "normal",
            },
            dedup_override=True,
            duplicate_of="T-00000000-00",
        )

        assert response.state == "ok"
        assert len(attempts) == 2
        assert attempts[0].exists()
        assert attempts[1].exists()
        assert attempts[1] != attempts[0]
        assert Path(response.data["ticket_path"]) == attempts[1]

    def test_create_retries_when_allocated_target_filename_already_exists(
        self,
        tmp_tickets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        make_ticket(tmp_tickets, "existing.md", id="T-20260603-01")
        allocated = iter(("T-20260603-01", "T-20260603-02"))

        def allocate_existing_then_next(*_args: object, **_kwargs: object) -> str:
            return next(allocated)

        monkeypatch.setattr(ticket_engine_core, "allocate_id", allocate_existing_then_next)

        response = _create_response(
            tmp_tickets,
            {
                "title": "Retry pre-write filename collision",
                "problem": "Pre-write target filename collisions should retry.",
                "priority": "normal",
            },
        )

        assert response.state == "ok"
        assert response.ticket_id == "T-20260603-02"
        assert (tmp_tickets / "T-20260603-01.md").exists()
        assert Path(response.data["ticket_path"]) == tmp_tickets / "T-20260603-02.md"

    def test_create_fails_after_retry_budget_exhausted(
        self,
        tmp_tickets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        attempts: list[Path] = []

        def always_exists(ticket_path: Path, content: str) -> None:
            attempts.append(ticket_path)
            raise FileExistsError("still colliding")

        monkeypatch.setattr(ticket_engine_core, "_write_text_exclusive", always_exists)

        response = _create_response(
            tmp_tickets,
            {
                "title": "Retry exhaustion",
                "problem": "Create should fail after the exclusive-write retry budget.",
                "priority": "normal",
            },
            dedup_override=True,
            duplicate_of="T-00000000-00",
        )

        assert response.state == "escalate"
        assert response.error_code == "io_error"
        assert "retry budget" in response.message.lower()
        assert len(attempts) == 3

    def test_create_write_oserror_returns_io_error(
        self,
        tmp_tickets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        def oserror_write(ticket_path: Path, content: str) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(ticket_engine_core, "_write_text_exclusive", oserror_write)

        response = _create_response(
            tmp_tickets,
            {
                "title": "Write failure",
                "problem": "Create should return io_error on OSError.",
                "priority": "normal",
            },
        )

        assert response.state == "escalate"
        assert response.error_code == "io_error"
        assert "create failed" in response.message.lower()

    def test_write_text_exclusive_unlinks_partial_file_on_fsync_failure(
        self,
        tmp_tickets: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        ticket_path = tmp_tickets / "partial-write.md"

        def fail_fsync(fd: int) -> None:
            raise OSError("disk full")

        monkeypatch.setattr(ticket_engine_core.os, "fsync", fail_fsync)

        with pytest.raises(OSError, match="disk full"):
            ticket_engine_core._write_text_exclusive(ticket_path, "partial content")

        assert not ticket_path.exists()

    def test_create_rejects_scalar_acceptance_criteria(self, tmp_tickets: Path) -> None:
        response = _create_response(
            tmp_tickets,
            {
                "title": "Bad acceptance criteria",
                "problem": "Scalar acceptance_criteria must be rejected.",
                "priority": "normal",
                "acceptance_criteria": "one criterion",
            },
        )

        assert response.state == "need_fields"
        assert response.error_code == "need_fields"
        assert "acceptance_criteria" in response.message
        assert not list(tmp_tickets.glob("*.md"))


class TestUpdate:
    def test_update_promotes_idea_to_open(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="idea")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"status": "open"},
        )

        assert response.state == "ok"
        content = ticket_path.read_text(encoding="utf-8")
        assert "status: open" in content
        assert "\ndate:" not in content

    def test_update_preserves_untargeted_optional_section_bytes(
        self,
        tmp_tickets: Path,
    ) -> None:
        ticket_id = "T-20260302-01"
        ticket_path = tmp_tickets / f"{ticket_id}.md"
        ticket_path.write_text(
            "\n".join(
                [
                    "---",
                    f"id: {ticket_id}",
                    "title: Preserve optional bytes",
                    "status: open",
                    "priority: normal",
                    "tags: []",
                    "related_paths: []",
                    "blocked_by: []",
                    "---",
                    "",
                    "## Problem",
                    "Keep optional section bytes unchanged.",
                    "",
                    "## Next Action",
                    "Update only frontmatter.",
                    "",
                    "## Change History",
                    (
                        "- 2026-06-02T00:00:00Z | migration | Test fixture normalized "
                        "to target schema."
                    ),
                    "",
                    "## Verification",
                    "",
                    "  keep leading spaces and blank lines",
                    "",
                    "trailing blank line remains below",
                    "",
                ]
            ),
            encoding="utf-8",
        )
        before = ticket_path.read_text(encoding="utf-8")
        before_verification = _section_text(before, "Verification")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"priority": "low"},
        )

        assert response.state == "ok"
        after = ticket_path.read_text(encoding="utf-8")
        assert "priority: low" in after
        assert _section_text(after, "Verification") == before_verification

    def test_terminal_status_update_requires_reopen(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="done")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"status": "open"},
        )

        assert response.state == "invalid_transition"
        assert response.error_code == "invalid_transition"
        assert "reopen" in response.message.lower()

    def test_update_blocks_open_ticket_with_visible_blocker(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={
                "status": "blocked",
                "blocked_on": "Waiting for the user to provide credentials.",
                "next_action": "Ask for credentials, then run the smoke test.",
            },
        )

        assert response.state == "ok"
        text = ticket_path.read_text(encoding="utf-8")
        assert "status: blocked" in text
        assert "## Blocked On\nWaiting for the user to provide credentials." in text
        assert validate_target_ticket_file(ticket_path).ok

    def test_update_rejects_blocked_transition_without_blocked_on(
        self,
        tmp_tickets: Path,
    ) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"status": "blocked"},
        )

        assert response.state == "invalid_transition"
        assert response.error_code == "invalid_transition"
        assert "blocked_on" in response.message

    def test_update_rejects_open_to_wontfix_because_terminal_writes_use_close(
        self,
        tmp_tickets: Path,
    ) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"status": "wontfix"},
        )

        assert response.state == "invalid_transition"
        assert response.error_code == "invalid_transition"
        assert response.data["current_status"] == "open"
        assert response.data["requested_status"] == "wontfix"
        assert response.data["valid_recovery_statuses"] == ["blocked"]
        assert "use close action" in response.message

    def test_update_unblocks_ticket_and_removes_live_blocker_shape(
        self,
        tmp_tickets: Path,
    ) -> None:
        ticket_path = make_ticket(
            tmp_tickets,
            "ignored.md",
            id="T-20260302-01",
            status="blocked",
            blocked_by=["T-20260302-02"],
            blocked_on="Waiting for the user to provide credentials.",
        )

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={
                "status": "open",
                "blocked_by": [],
                "blocked_on": None,
                "next_action": "Run the deployment smoke.",
            },
        )

        assert response.state == "ok"
        text = ticket_path.read_text(encoding="utf-8")
        assert "status: open" in text
        assert "blocked_by: []" in text
        assert "## Blocked On" not in text
        assert validate_target_ticket_file(ticket_path).ok

    def test_update_rejects_section_field_and_leaves_file_unchanged(
        self,
        tmp_tickets: Path,
    ) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")
        before = ticket_path.read_text(encoding="utf-8")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"problem": "New problem text"},
        )

        assert response.state == "escalate"
        assert response.error_code == "intent_mismatch"
        assert "section fields not supported" in response.message.lower()
        assert ticket_path.read_text(encoding="utf-8") == before

    def test_update_rejects_unknown_field_and_leaves_file_unchanged(
        self,
        tmp_tickets: Path,
    ) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")
        before = ticket_path.read_text(encoding="utf-8")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"custom": {"bad": "value"}},
        )

        assert response.state == "escalate"
        assert response.error_code == "intent_mismatch"
        assert "unknown fields: custom" in response.message.lower()
        assert ticket_path.read_text(encoding="utf-8") == before

    def test_update_ignores_matching_fields_ticket_id(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"ticket_id": "T-20260302-01", "priority": "low"},
        )

        assert response.state == "ok"
        content = ticket_path.read_text(encoding="utf-8")
        assert "priority: low" in content
        assert "ticket_id:" not in content

    def test_update_rejects_mismatched_fields_ticket_id(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")
        before = ticket_path.read_text(encoding="utf-8")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"ticket_id": "T-99999999-99"},
        )

        assert response.state == "escalate"
        assert response.error_code == "intent_mismatch"
        assert "fields.ticket_id must match" in response.message.lower()
        assert ticket_path.read_text(encoding="utf-8") == before

    def test_update_preserves_target_field_order(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"tags": ["bug"], "related_paths": ["src/ticket.py"]},
        )

        assert response.state == "ok"
        content = ticket_path.read_text(encoding="utf-8")
        ordered = [
            "id:",
            "title:",
            "status:",
            "priority:",
            "tags:",
            "related_paths:",
            "blocked_by:",
        ]
        positions = [content.index(field) for field in ordered]
        assert positions == sorted(positions)

    def test_update_list_values_round_trip(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"tags": ['bad"tag']},
        )

        assert response.state == "ok"
        tickets = list_tickets(tmp_tickets)
        assert tickets[0].tags == ['bad"tag']

    def test_update_rejects_removed_date_and_effort_fields(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"date": 20260305, "effort": "S"},
        )

        assert response.state == "need_fields"
        assert "date" in response.message
        assert "effort" in response.message


class TestCloseAndReopen:
    def test_close_ticket_keeps_canonical_file_in_place(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(
            tmp_tickets,
            "ignored.md",
            id="T-20260302-01",
            status="open",
        )

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="close",
            fields={"resolution": "done"},
        )

        assert response.state == "ok"
        assert ticket_path.exists()
        assert not (tmp_tickets / "closed-tickets").exists()
        assert "status: done" in ticket_path.read_text(encoding="utf-8")

    def test_close_with_archive_is_rejected(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(
            tmp_tickets,
            "ignored.md",
            id="T-20260302-01",
            status="open",
        )

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="close",
            fields={"resolution": "done", "archive": True},
        )

        assert response.state == "need_fields"
        assert response.error_code == "need_fields"
        assert "archive" in response.message
        assert ticket_path.exists()
        assert not (tmp_tickets / "closed-tickets").exists()

    def test_close_with_open_blockers_rejected_without_override(
        self,
        tmp_tickets: Path,
    ) -> None:
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")
        target_path = make_ticket(
            tmp_tickets,
            "ignored.md",
            id="T-20260302-02",
            status="blocked",
            blocked_by=["T-20260302-01"],
            blocked_on="Waiting for blocker resolution.",
        )

        response = _execute_existing(
            tmp_tickets,
            target_path,
            action="close",
            ticket_id="T-20260302-02",
            fields={"resolution": "done"},
        )

        assert response.state == "dependency_blocked"
        assert response.error_code == "dependency_blocked"
        assert response.data["unresolved_blockers"] == ["T-20260302-01"]

    def test_close_with_dependency_override_succeeds(self, tmp_tickets: Path) -> None:
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")
        target_path = make_ticket(
            tmp_tickets,
            "ignored.md",
            id="T-20260302-02",
            status="blocked",
            blocked_by=["T-20260302-01"],
            blocked_on="Waiting for blocker resolution.",
        )

        response = _execute_existing(
            tmp_tickets,
            target_path,
            action="close",
            ticket_id="T-20260302-02",
            fields={"resolution": "done"},
            dependency_override=True,
        )

        assert response.state == "ok"

    def test_close_wontfix_ignores_blockers(self, tmp_tickets: Path) -> None:
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")
        target_path = make_ticket(
            tmp_tickets,
            "ignored.md",
            id="T-20260302-02",
            status="blocked",
            blocked_by=["T-20260302-01"],
            blocked_on="Waiting for blocker resolution.",
        )

        response = _execute_existing(
            tmp_tickets,
            target_path,
            action="close",
            ticket_id="T-20260302-02",
            fields={"resolution": "wontfix"},
        )

        assert response.state == "ok"
        assert "status: wontfix" in target_path.read_text(encoding="utf-8")

    def test_close_reports_missing_blockers(self, tmp_tickets: Path) -> None:
        target_path = make_ticket(
            tmp_tickets,
            "ignored.md",
            id="T-20260302-02",
            status="blocked",
            blocked_by=["T-20260302-99"],
            blocked_on="Waiting for missing blocker resolution.",
        )

        response = _execute_existing(
            tmp_tickets,
            target_path,
            action="close",
            ticket_id="T-20260302-02",
            fields={"resolution": "done"},
        )

        assert response.state == "dependency_blocked"
        assert response.data["missing_blockers"] == ["T-20260302-99"]
        assert response.data["unresolved_blockers"] == []

    def test_close_rejects_idea_ticket(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="idea")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="close",
            fields={"resolution": "wontfix"},
        )

        assert response.state == "invalid_transition"
        assert response.error_code == "invalid_transition"
        assert response.data["current_status"] == "idea"
        assert response.data["valid_recovery_statuses"] == ["open"]

    def test_close_blocked_ticket_clears_live_blocker_shape(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(
            tmp_tickets,
            "ignored.md",
            id="T-20260302-01",
            status="blocked",
            blocked_by=["T-20260302-02"],
            blocked_on="Waiting for upstream work.",
        )

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="close",
            fields={"resolution": "wontfix"},
        )

        assert response.state == "ok"
        text = ticket_path.read_text(encoding="utf-8")
        assert "status: wontfix" in text
        assert "blocked_by: []" in text
        assert "## Blocked On" not in text
        assert validate_target_ticket_file(ticket_path).ok

    def test_close_terminal_ticket_rejected(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="done")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="close",
            fields={"resolution": "wontfix"},
        )

        assert response.state == "invalid_transition"
        assert response.error_code == "invalid_transition"

    def test_close_invalid_resolution_rejected(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="close",
            fields={"resolution": "blocked"},
        )

        assert response.state == "need_fields"
        assert response.error_code == "need_fields"
        assert "resolution" in response.message

    def test_close_done_requires_acceptance_criteria(self, tmp_tickets: Path) -> None:
        ticket_path = _make_ticket_without_acceptance_criteria(tmp_tickets, status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="close",
            fields={"resolution": "done"},
        )

        assert response.state == "invalid_transition"
        assert "acceptance" in response.message.lower()

    def test_reopen_ticket(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="done")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="reopen",
            fields={"reopen_reason": "Bug reoccurred after merge"},
        )

        assert response.state == "ok"
        content = ticket_path.read_text(encoding="utf-8")
        assert "status: open" in content
        assert "Reopen History" in content

    def test_reopen_rejects_invalid_fields_before_write(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="done")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="reopen",
            fields={"reopen_reason": "Bug reoccurred after merge", "status": "pending"},
        )

        assert response.state == "need_fields"
        assert response.error_code == "need_fields"
        assert "status" in response.message
        assert "status: done" in ticket_path.read_text(encoding="utf-8")

    def test_reopen_requires_reason(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="done")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="reopen",
            fields={},
        )

        assert response.state == "need_fields"
        assert response.error_code == "need_fields"
        assert "reopen_reason" in response.message


class TestTransportAndPrerequisites:
    def test_user_without_hook_injected_rejected(self, tmp_tickets: Path) -> None:
        response = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
        )
        assert response.state == "policy_blocked"

    def test_user_with_full_triple_succeeds(self, tmp_tickets: Path) -> None:
        response = _create_response(tmp_tickets, {"title": "Test", "problem": "Problem"})
        assert response.state == "ok"

    def test_user_with_mismatched_hook_origin_rejected(self, tmp_tickets: Path) -> None:
        response = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "Test", "problem": "Problem"},
            session_id="test-session",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="agent",
        )
        assert response.error_code == "origin_mismatch"

    def test_agent_override_rejected(self, tmp_tickets: Path) -> None:
        write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)

        response = _create_response(
            tmp_tickets,
            {"title": "Test", "problem": "Test", "priority": "normal"},
            request_origin="agent",
            dedup_override=True,
            duplicate_of="T-00000000-00",
            autonomy_config=AutonomyConfig(mode=AutomationMode.AGENT_PRIMARY),
        )

        assert response.state == "policy_blocked"
        assert "agent" in response.message.lower() or "override" in response.message.lower()

    def test_agent_direct_execute_requires_gateway(self, tmp_tickets: Path) -> None:
        write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)
        problem = "Direct execute should fail closed without runtime proof."

        response = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "Runtime gate", "problem": problem, "priority": "normal"},
            session_id="test-session",
            request_origin="agent",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp(problem, []),
            autonomy_config=AutonomyConfig(mode=AutomationMode.AGENT_PRIMARY),
            runtime_execute_surface="direct_execute",
        )

        assert response.state == "policy_blocked"
        assert response.error_code == "gateway_required"

    def test_missing_classify_intent_rejected(self, tmp_tickets: Path) -> None:
        response = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
        )
        assert response.state == "policy_blocked"

    def test_mismatched_classify_intent_rejected(self, tmp_tickets: Path) -> None:
        response = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
        )
        assert response.error_code == "intent_mismatch"

    def test_missing_classify_confidence_rejected(self, tmp_tickets: Path) -> None:
        response = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
        )
        assert response.state == "policy_blocked"

    def test_low_confidence_rejected(self, tmp_tickets: Path) -> None:
        response = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.3,
        )
        assert response.state == "preflight_failed"

    def test_exact_user_confidence_threshold_accepted(self, tmp_tickets: Path) -> None:
        response = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.5,
            dedup_fingerprint=compute_dedup_fp("P", []),
        )
        assert response.state == "ok"

    def test_missing_dedup_fingerprint_for_create_rejected(self, tmp_tickets: Path) -> None:
        response = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
        )
        assert response.state == "policy_blocked"

    def test_mismatched_dedup_fingerprint_rejected(self, tmp_tickets: Path) -> None:
        response = _create_response(tmp_tickets, dedup_fingerprint="wrong-fingerprint")
        assert response.error_code == "stale_plan"

    def test_missing_target_fingerprint_for_update_rejected(self, tmp_tickets: Path) -> None:
        make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = engine_execute(
            action="update",
            ticket_id="T-20260302-01",
            fields={"priority": "low"},
            session_id="sess",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="update",
            classify_confidence=0.95,
        )
        assert response.state == "policy_blocked"

    def test_agent_missing_autonomy_config_rejected(self, tmp_tickets: Path) -> None:
        write_local_config(tmp_tickets.parent.parent, AutomationMode.AGENT_PRIMARY)

        response = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "T", "problem": "P"},
            session_id="sess",
            request_origin="agent",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="agent",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("P", []),
        )
        assert response.state == "policy_blocked"


class TestFieldValidation:
    def test_create_invalid_priority_rejected(self, tmp_tickets: Path) -> None:
        response = _create_response(tmp_tickets, {"priority": "urgent"})

        assert response.error_code == "need_fields"
        assert "priority" in response.message

    def test_create_removed_key_file_paths_rejected_before_fingerprint_recompute(
        self,
        tmp_tickets: Path,
    ) -> None:
        response = _create_response(
            tmp_tickets,
            {"key_file_paths": "src/main.py"},
            dedup_fingerprint="placeholder",
        )

        assert response.error_code == "need_fields"
        assert "key_file_paths" in response.message

    def test_create_scalar_tags_rejected(self, tmp_tickets: Path) -> None:
        response = _create_response(tmp_tickets, {"tags": "bug"})

        assert response.error_code == "need_fields"
        assert "tags" in response.message

    def test_update_scalar_blocked_by_rejected(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"blocked_by": "T-20260302-02"},
        )

        assert response.error_code == "need_fields"
        assert "blocked_by" in response.message

    def test_close_invalid_resolution_rejected(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(
            tmp_tickets,
            "ignored.md",
            id="T-20260302-01",
            status="open",
        )

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="close",
            fields={"resolution": "cancelled"},
        )

        assert response.error_code == "need_fields"
        assert "resolution" in response.message

    def test_contract_version_is_rejected_not_stamped(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"priority": "high", "contract_version": "0.9"},
        )

        assert response.state == "need_fields"
        assert "contract_version" in response.message
        assert "contract_version" not in ticket_path.read_text(encoding="utf-8")

    def test_successful_update_does_not_stamp_contract_version(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"priority": "low"},
        )

        assert response.state == "ok"
        ticket = parse_ticket(ticket_path)
        assert ticket is not None
        assert "contract_version" not in ticket.frontmatter

    def test_successful_close_does_not_stamp_contract_version(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(
            tmp_tickets,
            "ignored.md",
            id="T-20260302-01",
            status="open",
        )

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="close",
            fields={"resolution": "done"},
        )

        assert response.state == "ok"
        ticket = parse_ticket(ticket_path)
        assert ticket is not None
        assert "contract_version" not in ticket.frontmatter

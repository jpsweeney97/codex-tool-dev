from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

from scripts.ticket_capture import run_capture
from scripts.ticket_parse import parse_ticket

from tests.support.builders import make_ticket


def _payload(
    tickets_dir: Path,
    *,
    title: str = "Capture follow-up for hook guard preview",
    problem: str = "The hook guard preview needs a user-friendly capture path.",
    next_action: str = "Clarify the expected preview behavior for hook guard failures.",
    captured_request: str = "Create a follow-up for improving the hook guard preview.",
    capture_confidence: str = "medium",
    extra_capture: dict | None = None,
) -> dict:
    capture = {
        "title": title,
        "captured_request": captured_request,
        "problem": problem,
        "next_action": next_action,
        "capture_confidence": capture_confidence,
        "tags": ["bug"],
        "component": "ticket",
        "related_paths": ["plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py"],
        "acceptance_criteria": ["Hook guard preview behavior is clarified"],
    }
    if extra_capture:
        capture.update(extra_capture)
    return {
        "tickets_dir": str(tickets_dir),
        "session_id": "session-1",
        "hook_injected": True,
        "hook_request_origin": "user",
        "capture": capture,
    }


def _payload_file(project_root: Path, payload: dict) -> Path:
    path = project_root / ".codex" / "ticket-capture-payload.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_payload(path: Path, payload: dict) -> None:
    path.write_text(json.dumps(payload), encoding="utf-8")


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")


def test_prepare_returns_compact_preview_fields_and_does_not_write_ticket(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = _payload_file(project_root, _payload(tmp_tickets))

    response = run_capture("prepare", payload_path)

    assert response["state"] == "ready_to_execute"
    assert sorted(path.name for path in tmp_tickets.glob("*.md")) == []
    preview = response["data"]["preview"]
    assert preview == {
        "title": "Capture follow-up for hook guard preview",
        "problem": "The hook guard preview needs a user-friendly capture path.",
        "next_action": "Clarify the expected preview behavior for hook guard failures.",
        "confidence": "medium",
        "duplicate": {
            "label": "none",
            "ticket_id": None,
            "title": "",
            "default_action": "create_anyway",
        },
        "prompt": "Create this ticket? [create / edit / cancel]",
        "exceptional_fields": {
            "component": "ticket",
            "related_paths": ["plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py"],
        },
    }


def test_prepare_rejects_low_confidence_capture_with_no_useful_next_action(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            capture_confidence="low",
            next_action="",
            extra_capture={"refinement_status": "needs_refinement", "tags": ["needs-refinement"]},
        ),
    )

    response = run_capture("prepare", payload_path)

    assert response["state"] == "need_fields"
    assert response["error_code"] == "need_fields"
    assert response["data"]["missing_fields"] == ["next_action"]


def test_prepare_allows_low_confidence_with_next_action_and_refinement_status(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            capture_confidence="low",
            extra_capture={
                "priority": "medium",
                "refinement_status": "needs_refinement",
                "tags": ["bug", "needs-refinement"],
                "acceptance_criteria": ["Needs refinement"],
            },
        ),
    )

    response = run_capture("prepare", payload_path)

    assert response["state"] == "ready_to_execute"
    preview = response["data"]["preview"]
    assert preview["confidence"] == "low"
    assert preview["priority"] == "medium"
    assert preview["exceptional_fields"]["refinement_status"] == "needs_refinement"


def test_prepare_rejects_raw_user_wording_keys(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            extra_capture={"nested": {"transcript_excerpt": "verbatim user wording"}},
        ),
    )

    response = run_capture("prepare", payload_path)

    assert response["state"] == "need_fields"
    assert response["error_code"] == "raw_user_wording"
    assert "transcript_excerpt" in response["message"]


def test_prepare_rejects_unsupported_hidden_persisted_capture_fields(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            extra_capture={
                "approach": "This hidden body section must not bypass preview.",
                "verification": "pytest hidden verification",
                "blocked_by": ["T-20260518-99"],
            },
        ),
    )

    response = run_capture("prepare", payload_path)

    assert response["state"] == "need_fields"
    assert response["error_code"] == "unsupported_capture_fields"
    assert response["data"]["unsupported_fields"] == ["approach", "blocked_by", "verification"]
    assert list(tmp_tickets.glob("*.md")) == []


def test_prepare_rejects_user_supplied_key_file_paths(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            extra_capture={"key_file_paths": ["hidden/dedup-only.py"]},
        ),
    )

    response = run_capture("prepare", payload_path)

    assert response["state"] == "need_fields"
    assert response["error_code"] == "unsupported_capture_fields"
    assert response["data"]["unsupported_fields"] == ["key_file_paths"]
    assert list(tmp_tickets.glob("*.md")) == []


def test_prepare_rejects_relative_payload_path(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    relative_path = Path(".codex") / "ticket-capture-payload.json"
    (project_root / relative_path.parent).mkdir(exist_ok=True)
    (project_root / relative_path).write_text(json.dumps(_payload(tmp_tickets)), encoding="utf-8")

    response = run_capture("prepare", relative_path)

    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "policy_blocked"
    assert "must be absolute" in response["message"]


def test_prepare_rejects_payload_path_outside_workspace(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    outside = tmp_path.parent / f"outside-capture-{tmp_path.name}.json"
    outside.write_text(json.dumps(_payload(tmp_tickets)), encoding="utf-8")

    response = run_capture("prepare", outside)

    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "policy_blocked"
    assert "outside workspace root" in response["message"]


def test_prepare_rejects_payload_path_with_whitespace(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = project_root / ".codex" / "ticket capture payload.json"
    payload_path.parent.mkdir(exist_ok=True)
    payload_path.write_text(json.dumps(_payload(tmp_tickets)), encoding="utf-8")

    response = run_capture("prepare", payload_path)

    assert response["state"] == "policy_blocked"
    assert response["error_code"] == "policy_blocked"
    assert "must not contain whitespace" in response["message"]


def test_prepare_surfaces_duplicate_detection_with_create_anyway_for_weak_duplicate(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    make_ticket(
        tmp_tickets,
        "existing.md",
        id="T-20260518-01",
        date=_now_iso()[:10],
        created_at=_now_iso(),
        title="New title",
        problem="Duplicate capture problem",
    )
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            title="New title",
            problem="Duplicate capture problem",
            extra_capture={
                "related_paths": ["plugins/turbo-mode/ticket/scripts/ticket_capture.py"]
            },
        ),
    )

    response = run_capture("prepare", payload_path)

    assert response["state"] == "ready_to_execute"
    duplicate = response["data"]["preview"]["duplicate"]
    assert duplicate["ticket_id"] == "T-20260518-01"
    assert duplicate["default_action"] == "create_anyway"


def test_prepare_duplicate_default_action_update_existing_for_explicit_target(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    make_ticket(
        tmp_tickets,
        "existing.md",
        id="T-20260518-02",
        date=_now_iso()[:10],
        created_at=_now_iso(),
        title="Capture follow-up for hook guard preview",
        problem="The hook guard preview needs a user-friendly capture path.",
    )
    payload = _payload(tmp_tickets)
    payload["target_ticket_id"] = "T-20260518-02"
    payload_path = _payload_file(project_root, payload)

    response = run_capture("prepare", payload_path)

    assert response["state"] == "ready_to_execute"
    assert response["data"]["preview"]["duplicate"]["default_action"] == "update_existing"


def test_prepare_duplicate_default_action_update_existing_for_strong_title_path_core(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    make_ticket(
        tmp_tickets,
        "existing-strong.md",
        id="T-20260518-03",
        date=_now_iso()[:10],
        created_at=_now_iso(),
        title="Capture follow-up for hook guard preview!",
        problem="A related existing problem.",
        extra_yaml="related_paths: [older/location/ticket_engine_guard.py]\n        ",
    )
    payload_path = _payload_file(
        project_root,
        _payload(
            tmp_tickets,
            extra_capture={
                "component": "",
                "related_paths": [
                    "plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py"
                ],
            },
        ),
    )

    response = run_capture("prepare", payload_path)

    assert response["state"] == "ready_to_execute"
    duplicate = response["data"]["preview"]["duplicate"]
    assert duplicate["ticket_id"] == "T-20260518-03"
    assert duplicate["default_action"] == "update_existing"


def test_execute_writes_one_capture_created_ticket_after_prepare_with_provenance(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = _payload_file(
        project_root,
        _payload(tmp_tickets, capture_confidence="low", extra_capture={"priority": "high"}),
    )

    prepare = run_capture("prepare", payload_path)
    execute = run_capture("execute", payload_path)

    assert prepare["state"] == "ready_to_execute"
    assert execute["state"] == "ok_create"
    paths = list(tmp_tickets.glob("*.md"))
    assert len(paths) == 1
    ticket = parse_ticket(paths[0])
    assert ticket is not None
    assert ticket.source == {"type": "capture", "ref": "", "session": "session-1"}
    assert ticket.capture_source == "conversation"
    assert ticket.capture_confidence == "low"
    assert ticket.related_paths == ["plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py"]
    assert "key_file_paths" not in ticket.frontmatter
    assert ticket.sections["Captured Request"] == (
        "Create a follow-up for improving the hook guard preview."
    )
    assert ticket.sections["Next Action"] == (
        "Clarify the expected preview behavior for hook guard failures."
    )


def test_execute_rejects_prepared_payload_with_missing_preview(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = _payload_file(project_root, _payload(tmp_tickets))

    prepare = run_capture("prepare", payload_path)
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["capture_prepare"].pop("preview")
    _write_payload(payload_path, payload)
    execute = run_capture("execute", payload_path)

    assert prepare["state"] == "ready_to_execute"
    assert execute["state"] == "preflight_failed"
    assert execute["error_code"] == "stale_plan"
    assert list(tmp_tickets.glob("*.md")) == []


def test_execute_rejects_when_capture_changes_after_prepare_until_rerun(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = _payload_file(project_root, _payload(tmp_tickets))

    prepare = run_capture("prepare", payload_path)
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["capture"]["title"] = "Changed after prepare"
    _write_payload(payload_path, payload)
    stale_execute = run_capture("execute", payload_path)
    rerun_prepare = run_capture("prepare", payload_path)
    execute = run_capture("execute", payload_path)

    assert prepare["state"] == "ready_to_execute"
    assert stale_execute["state"] == "preflight_failed"
    assert stale_execute["error_code"] == "stale_plan"
    assert rerun_prepare["state"] == "ready_to_execute"
    assert execute["state"] == "ok_create"
    assert len(list(tmp_tickets.glob("*.md"))) == 1


def test_execute_does_not_persist_edit_history(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = _payload_file(project_root, _payload(tmp_tickets))

    prepare = run_capture("prepare", payload_path, edit_text="make it high priority")
    execute = run_capture("execute", payload_path)

    assert prepare["state"] == "ready_to_execute"
    assert execute["state"] == "ok_create"
    ticket_text = next(tmp_tickets.glob("*.md")).read_text(encoding="utf-8")
    assert "edit_history" not in ticket_text
    assert "make it high priority" not in ticket_text


def test_edit_appends_payload_history_and_regenerates_preview_without_write(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = _payload_file(project_root, _payload(tmp_tickets))

    response = run_capture("prepare", payload_path, edit_text="make it high priority")

    assert response["state"] == "ready_to_execute"
    assert response["data"]["preview"]["priority"] == "high"
    assert list(tmp_tickets.glob("*.md")) == []
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    assert payload["capture"]["priority"] == "high"
    assert payload["edit_history"][0]["instruction"] == "make it high priority"


def test_split_request_returns_single_ticket_preview_plus_suggested_next_capture(
    tmp_tickets: Path,
    monkeypatch,
) -> None:
    project_root = tmp_tickets.parent.parent
    monkeypatch.chdir(project_root)
    payload_path = _payload_file(project_root, _payload(tmp_tickets))

    response = run_capture("prepare", payload_path, edit_text="split this into two tickets")

    assert response["state"] == "ready_to_execute"
    assert response["data"]["preview"]["title"] == "Capture follow-up for hook guard preview"
    assert response["data"]["suggested_next_capture"]
    assert list(tmp_tickets.glob("*.md")) == []

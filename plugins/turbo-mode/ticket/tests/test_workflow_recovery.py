from __future__ import annotations

import json
from pathlib import Path

from scripts.ticket_workflow import run_recovery, run_workflow
from tests.support.builders import make_ticket
from tests.support.workflow import (
    assert_recover_command,
    assert_suggested_ticket_command,
    authorized_recovery_payload,
    expected_recover_command,
    now_iso,
    payload_file,
    recovery_options,
    trusted_args_ticket_payload,
    trusted_payload,
)


def test_prepare_need_fields_offers_concrete_recovery_command(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(tmp_tickets, "reopen.md", id="T-20260503-41", status="done")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload("reopen", "T-20260503-41", {}))

    response = run_workflow("prepare", payload_path)
    hydrated = json.loads(payload_path.read_text(encoding="utf-8"))

    assert response["state"] == "need_fields"
    assert_recover_command(
        response,
        expected_recover_command(payload_path, "set_field", "reopen_reason", json.dumps("set reopen_reason")),
    )
    assert {"action": "set_field", "field": "reopen_reason"} in hydrated["workflow_recovery"]["allowed"]


def test_prepare_create_need_fields_offers_title_and_problem_recovery_commands(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    payload_path = payload_file(tmp_path, trusted_payload("create", {}))

    response = run_workflow("prepare", payload_path)
    hydrated = json.loads(payload_path.read_text(encoding="utf-8"))

    assert response["state"] == "need_fields"
    assert_recover_command(
        response,
        expected_recover_command(payload_path, "set_field", "title", json.dumps("set title")),
    )
    assert_recover_command(
        response,
        expected_recover_command(payload_path, "set_field", "problem", json.dumps("set problem")),
    )
    allowed = hydrated["workflow_recovery"]["allowed"]
    assert {"action": "set_field", "field": "title"} in allowed
    assert {"action": "set_field", "field": "problem"} in allowed


def test_prepare_duplicate_create_offers_create_anyway_and_update_existing(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(
        tmp_tickets,
        "existing.md",
        id="T-20260503-42",
        date=now_iso()[:10],
        created_at=now_iso(),
        problem="Duplicate recovery problem",
    )
    payload_path = payload_file(tmp_path, trusted_payload(
        "create",
        {
            "title": "Duplicate create",
            "problem": "Duplicate recovery problem",
            "priority": "medium",
            "key_file_paths": ["test.py"],
        },
    ))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "duplicate_candidate"
    assert_recover_command(response, expected_recover_command(payload_path, "create_anyway"))
    assert_suggested_ticket_command(response, "ticket update T-20260503-42")


def test_prepare_blocked_close_offers_dependency_recovery_commands(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(tmp_tickets, "blocker.md", id="T-20260503-43", status="open")
    make_ticket(tmp_tickets, "blocked.md", id="T-20260503-44", status="in_progress", blocked_by=["T-20260503-43"])
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload("close", "T-20260503-44", {"resolution": "done"}))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "dependency_blocked"
    assert_recover_command(response, expected_recover_command(payload_path, "close_wontfix"))
    assert_suggested_ticket_command(response, "ticket check T-20260503-44")


def test_prepare_terminal_invalid_transition_offers_reopen_command_only(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(tmp_tickets, "terminal.md", id="T-20260503-45", status="done")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload("update", "T-20260503-45", {"status": "open"}))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "invalid_transition"
    assert len(recovery_options(response)) == 1
    assert_suggested_ticket_command(response, "ticket reopen T-20260503-45")


def test_prepare_nonterminal_invalid_transition_offers_valid_set_status_command(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    make_ticket(tmp_tickets, "open.md", id="T-20260503-46", status="open")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload("update", "T-20260503-46", {"status": "done"}))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "invalid_transition"
    assert_recover_command(response, expected_recover_command(payload_path, "set_status", "blocked"))


def test_prepare_close_without_acceptance_criteria_offers_update_command(
    tmp_tickets: Path,
    tmp_path: Path,
    monkeypatch,
) -> None:
    monkeypatch.chdir(tmp_tickets.parent.parent)
    path = make_ticket(tmp_tickets, "no-ac.md", id="T-20260503-47", status="in_progress")
    text = path.read_text(encoding="utf-8")
    path.write_text(text.replace("## Acceptance Criteria\n- [ ] Issue resolved\n\n", ""), encoding="utf-8")
    payload_path = payload_file(tmp_path, trusted_args_ticket_payload("close", "T-20260503-47", {"resolution": "done"}))

    response = run_workflow("prepare", payload_path)

    assert response["state"] == "invalid_transition"
    assert_suggested_ticket_command(response, "ticket update T-20260503-47")


def test_recovery_create_anyway_patches_payload(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "create",
        {"title": "Test", "problem": "Problem", "priority": "medium"},
        allowed=[{"action": "create_anyway"}],
        recovery_state="duplicate_candidate",
        recovery_error_code="duplicate_candidate",
        recovery_stage="plan",
        duplicate_of="T-20260503-48",
    )
    path = payload_file(tmp_path, payload)

    response = run_recovery(path, "create_anyway")
    hydrated = json.loads(path.read_text(encoding="utf-8"))

    assert response["state"] == "ok"
    assert hydrated["dedup_override"] is True
    assert "workflow_recovery" not in hydrated


def test_recovery_close_wontfix_patches_resolution(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "close",
        {"resolution": "done"},
        allowed=[{"action": "close_wontfix"}],
        recovery_state="dependency_blocked",
        recovery_error_code="dependency_blocked",
        recovery_stage="policy",
        ticket_id="T-20260503-49",
    )
    path = payload_file(tmp_path, payload)

    response = run_recovery(path, "close_wontfix")
    hydrated = json.loads(path.read_text(encoding="utf-8"))

    assert response["state"] == "ok"
    assert hydrated["fields"]["resolution"] == "wontfix"


def test_recovery_set_field_json_decodes_value(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "update",
        {"tags": []},
        allowed=[{"action": "set_field", "field": "tags"}],
        validation_errors=["tags must contain only strings"],
        ticket_id="T-20260503-50",
    )
    path = payload_file(tmp_path, payload)

    response = run_recovery(path, "set_field", field="tags", value='["ux", "ticket"]')
    hydrated = json.loads(path.read_text(encoding="utf-8"))

    assert response["state"] == "ok"
    assert hydrated["fields"]["tags"] == ["ux", "ticket"]


def test_recovery_set_field_requires_recovery_context_authority(tmp_path: Path) -> None:
    payload = trusted_payload("update", {"tags": []}, ticket_id="T-20260503-51")
    path = payload_file(tmp_path, payload)
    before = path.read_text(encoding="utf-8")

    response = run_recovery(path, "set_field", field="tags", value='["ux"]')

    assert response["state"] == "escalate"
    assert path.read_text(encoding="utf-8") == before


def test_recovery_rejects_malformed_authority_without_mutation(tmp_path: Path) -> None:
    payload = trusted_payload("update", {"tags": []}, ticket_id="T-20260503-52")
    payload["workflow_recovery"] = "bad"
    path = payload_file(tmp_path, payload)
    before = path.read_text(encoding="utf-8")

    response = run_recovery(path, "set_field", field="tags", value='["ux"]')

    assert response["state"] == "escalate"
    assert path.read_text(encoding="utf-8") == before


def test_recovery_rejects_authority_binding_mismatch_without_mutation(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "update",
        {"tags": []},
        allowed=[{"action": "set_field", "field": "tags"}],
        ticket_id="T-20260503-53",
    )
    payload["ticket_id"] = "T-20260503-54"
    path = payload_file(tmp_path, payload)
    before = path.read_text(encoding="utf-8")

    response = run_recovery(path, "set_field", field="tags", value='["ux"]')

    assert response["state"] == "escalate"
    assert path.read_text(encoding="utf-8") == before


def test_recovery_set_field_rejects_json_decode_failure_without_mutation(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "update",
        {"tags": []},
        allowed=[{"action": "set_field", "field": "tags"}],
        ticket_id="T-20260503-55",
    )
    path = payload_file(tmp_path, payload)
    before = path.read_text(encoding="utf-8")

    response = run_recovery(path, "set_field", field="tags", value='["ux"')

    assert response["state"] == "escalate"
    assert path.read_text(encoding="utf-8") == before


def test_recovery_set_field_validates_patched_fields_before_write(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "update",
        {"priority": "medium"},
        allowed=[{"action": "set_field", "field": "priority"}],
        validation_errors=["priority must be one of ['critical', 'high', 'low', 'medium'], got 'bogus'"],
        ticket_id="T-20260503-56",
    )
    path = payload_file(tmp_path, payload)
    before = path.read_text(encoding="utf-8")

    response = run_recovery(path, "set_field", field="priority", value='"bogus"')

    assert response["state"] == "need_fields"
    assert path.read_text(encoding="utf-8") == before


def test_recovery_cancel_consumes_authority_without_changing_fields(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "update",
        {"tags": ["ux"]},
        allowed=[{"action": "cancel"}],
        ticket_id="T-20260503-57",
    )
    path = payload_file(tmp_path, payload)

    response = run_recovery(path, "cancel")
    hydrated = json.loads(path.read_text(encoding="utf-8"))

    assert response["state"] == "ok"
    assert hydrated["fields"]["tags"] == ["ux"]
    assert "workflow_recovery" not in hydrated


def test_recovery_replay_after_authority_consumption_is_rejected(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "update",
        {"tags": []},
        allowed=[{"action": "set_field", "field": "tags"}],
        validation_errors=["tags must contain only strings"],
        ticket_id="T-20260503-58",
    )
    path = payload_file(tmp_path, payload)

    first = run_recovery(path, "set_field", field="tags", value='["ux"]')
    second = run_recovery(path, "set_field", field="tags", value='["ticket"]')

    assert first["state"] == "ok"
    assert second["state"] == "escalate"


def test_recovery_close_wontfix_rejects_wrong_ticket_action(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "update",
        {"priority": "medium"},
        allowed=[{"action": "set_field", "field": "priority"}],
        ticket_id="T-20260503-59",
    )
    path = payload_file(tmp_path, payload)
    before = path.read_text(encoding="utf-8")

    response = run_recovery(path, "close_wontfix")

    assert response["state"] == "escalate"
    assert path.read_text(encoding="utf-8") == before


def test_recovery_set_status_rejects_mismatched_authorized_status(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "update",
        {"status": "open"},
        allowed=[{"action": "set_status", "status": "blocked"}],
        ticket_id="T-20260503-60",
    )
    path = payload_file(tmp_path, payload)
    before = path.read_text(encoding="utf-8")

    response = run_recovery(path, "set_status", status="done")

    assert response["state"] == "escalate"
    assert path.read_text(encoding="utf-8") == before


def test_recovery_unsupported_action_is_rejected_without_mutation(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "update",
        {"tags": []},
        allowed=[{"action": "set_field", "field": "tags"}],
        ticket_id="T-20260503-61",
    )
    path = payload_file(tmp_path, payload)
    before = path.read_text(encoding="utf-8")

    response = run_recovery(path, "destroy")

    assert response["state"] == "escalate"
    assert path.read_text(encoding="utf-8") == before


def test_recovery_set_field_rejects_policy_owned_or_unknown_fields(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "update",
        {"tags": []},
        allowed=[{"action": "set_field", "field": "source"}],
        ticket_id="T-20260503-62",
    )
    path = payload_file(tmp_path, payload)
    before = path.read_text(encoding="utf-8")

    response = run_recovery(path, "set_field", field="source", value='{"type":"ad-hoc"}')

    assert response["state"] == "escalate"
    assert path.read_text(encoding="utf-8") == before


def test_recovery_matrix_rejects_action_not_allowed_for_state(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "update",
        {"priority": "medium"},
        allowed=[{"action": "close_wontfix"}],
        recovery_state="need_fields",
        recovery_error_code="need_fields",
        ticket_id="T-20260503-68",
    )
    path = payload_file(tmp_path, payload)
    before = path.read_text(encoding="utf-8")

    response = run_recovery(path, "close_wontfix")

    assert response["state"] == "escalate"
    assert path.read_text(encoding="utf-8") == before


def test_recovery_invalid_transition_rejects_bogus_stage(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "update",
        {"status": "open"},
        allowed=[{"action": "set_status", "status": "blocked"}],
        recovery_state="invalid_transition",
        recovery_error_code="invalid_transition",
        recovery_stage="bogus",
        ticket_id="T-20260503-69",
    )
    path = payload_file(tmp_path, payload)
    before = path.read_text(encoding="utf-8")

    response = run_recovery(path, "set_status", status="blocked")

    assert response["state"] == "escalate"
    assert path.read_text(encoding="utf-8") == before


def test_recovery_need_fields_create_rejects_bogus_stage(tmp_path: Path) -> None:
    payload = authorized_recovery_payload(
        "create",
        {},
        allowed=[{"action": "set_field", "field": "title"}],
        recovery_state="need_fields",
        recovery_error_code="need_fields",
        recovery_stage="bogus",
    )
    path = payload_file(tmp_path, payload)
    before = path.read_text(encoding="utf-8")

    response = run_recovery(path, "set_field", field="title", value='"Recovered title"')

    assert response["state"] == "escalate"
    assert path.read_text(encoding="utf-8") == before

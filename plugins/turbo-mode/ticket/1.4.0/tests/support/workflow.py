from __future__ import annotations

import json
import shlex
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

PLUGIN_ROOT = Path(__file__).resolve().parents[2]


def payload_file(tmp_path: Path, data: dict[str, Any]) -> Path:
    path = tmp_path / "payload.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return path


def trusted_payload(
    action: str,
    fields: dict[str, Any],
    *,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "action": action,
        "args": {},
        "request_origin": "user",
        "hook_injected": True,
        "hook_request_origin": "user",
        "session_id": f"session-{action}",
        "fields": fields,
    }
    if ticket_id is not None:
        payload["ticket_id"] = ticket_id
    return payload


def trusted_args_ticket_payload(
    action: str,
    ticket_id: str,
    fields: dict[str, Any],
) -> dict[str, Any]:
    payload = trusted_payload(action, fields)
    payload["args"]["ticket_id"] = ticket_id
    return payload


def authorized_recovery_payload(
    action: str,
    fields: dict[str, Any],
    *,
    allowed: list[dict[str, Any]],
    **extra: Any,
) -> dict[str, Any]:
    recovery_state = extra.pop("recovery_state", "need_fields")
    response_error_code = extra.pop("recovery_error_code", recovery_state)
    stage = extra.pop("recovery_stage", "policy")
    missing_fields = extra.pop("missing_fields", [])
    validation_errors = extra.pop("validation_errors", [])
    current_status = extra.pop("current_status", None)
    requested_status = extra.pop("requested_status", None)
    valid_recovery_statuses = extra.pop("valid_recovery_statuses", [])
    requires_reopen = extra.pop("requires_reopen", False)
    precondition_code = extra.pop("precondition_code", "none")
    precondition_detail = extra.pop("precondition_detail", None)
    session_id = extra.get("session_id", "session-recovery")
    request_origin = extra.get("hook_request_origin", extra.get("request_origin", "user"))
    payload: dict[str, Any] = {
        "action": action,
        "fields": fields,
        "request_origin": request_origin,
        "hook_request_origin": request_origin,
        "session_id": session_id,
        "workflow_recovery": {
            "state": recovery_state,
            "stage": stage,
            "error_code": response_error_code,
            "action": action,
            "ticket_id": extra.get("ticket_id"),
            "target_fingerprint": extra.get("target_fingerprint"),
            "dedup_fingerprint": extra.get("dedup_fingerprint"),
            "duplicate_of": extra.get("duplicate_of"),
            "session_id": session_id,
            "request_origin": request_origin,
            "missing_fields": missing_fields,
            "validation_errors": validation_errors,
            "current_status": current_status,
            "requested_status": requested_status,
            "valid_recovery_statuses": valid_recovery_statuses,
            "requires_reopen": requires_reopen,
            "precondition_code": precondition_code,
            "precondition_detail": precondition_detail,
            "allowed": allowed,
        },
    }
    payload.update(extra)
    return payload


def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def recovery_options(response: dict[str, Any]) -> list[dict[str, Any]]:
    return response.get("data", {}).get("recovery_options", [])


def expected_prepare_command(payload_path: Path) -> str:
    return shlex.join([
        "python3",
        "-B",
        str(PLUGIN_ROOT / "scripts" / "ticket_workflow.py"),
        "prepare",
        str(payload_path),
    ])


def expected_execute_command(payload_path: Path) -> str:
    return shlex.join([
        "python3",
        "-B",
        str(PLUGIN_ROOT / "scripts" / "ticket_workflow.py"),
        "execute",
        str(payload_path),
    ])


def expected_recover_command(payload_path: Path, recovery_action: str, *args: str) -> str:
    return shlex.join([
        "python3",
        "-B",
        str(PLUGIN_ROOT / "scripts" / "ticket_workflow.py"),
        "recover",
        str(payload_path),
        recovery_action,
        *args,
    ])


def assert_preview_schema(preview: dict[str, Any], *, action: str, payload_path: Path) -> None:
    assert preview["action"] == action
    assert preview["action_label"]
    assert "ticket_id" in preview
    assert "ticket_identity" in preview
    assert "will_write" in preview
    assert "field_changes" in preview
    assert "risk_flags" in preview
    assert preview["next_command"] == expected_execute_command(payload_path)


def assert_recover_command(response: dict[str, Any], expected: str) -> None:
    commands = [
        option.get("recover_command")
        for option in recovery_options(response)
        if isinstance(option.get("recover_command"), str)
    ]
    assert expected in commands


def assert_suggested_ticket_command(response: dict[str, Any], expected: str) -> None:
    commands = [
        option.get("suggested_ticket_command")
        for option in recovery_options(response)
        if isinstance(option.get("suggested_ticket_command"), str)
    ]
    assert expected in commands

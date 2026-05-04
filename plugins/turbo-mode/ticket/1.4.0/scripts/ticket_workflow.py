#!/usr/bin/env python3
"""High-level ticket workflow runner for prepare, execute, and recover."""
from __future__ import annotations

import json
import os
import shlex
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_engine_core import _evaluate_workflow_policy
from scripts.ticket_engine_runner import dispatch_stage, load_runner_context
from scripts.ticket_read import find_ticket_by_id
from scripts.ticket_ux import humanize_state, ticket_identity
from scripts.ticket_validate import validate_fields

_POLICY_OWNED_FIELDS = frozenset({
    "archive",
    "audit",
    "closed_at",
    "contract_version",
    "created_at",
    "defer",
    "id",
    "source",
})
_COMMANDABLE_FIELDS = frozenset({
    "priority",
    "tags",
    "blocked_by",
    "blocks",
    "effort",
    "reopen_reason",
})
_CREATE_NEED_FIELDS = ("title", "problem", "priority")
_UPDATE_NEED_FIELDS = ("priority", "tags", "blocked_by", "blocks", "effort")
_RECOVERABLE_SET_FIELDS = frozenset((*_COMMANDABLE_FIELDS, *_CREATE_NEED_FIELDS))


def _response(
    state: str,
    message: str,
    *,
    error_code: str | None = None,
    data: dict[str, Any] | None = None,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    response = {
        "state": state,
        "message": message,
        "data": data or {},
    }
    if error_code is not None:
        response["error_code"] = error_code
    if ticket_id is not None:
        response["ticket_id"] = ticket_id
    return response


def _engine_response_to_dict(response: Any) -> dict[str, Any]:
    data = response.to_dict()
    if "data" not in data:
        data["data"] = {}
    return data


def _write_payload_atomic(payload_path: Path, payload: dict[str, Any]) -> None:
    parent = payload_path.parent
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        try:
            encoded = json.dumps(payload, indent=2).encode("utf-8")
            os.write(fd, encoded)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp_path, str(payload_path))
    except OSError as exc:
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        raise OSError(f"payload write failed: {exc}. Got: {str(payload_path)!r:.100}") from exc


def _canonical_workflow_command(subcommand: str, payload_path: Path, *extra: str) -> str | None:
    payload_str = str(payload_path)
    if any(char.isspace() for char in payload_str):
        return None
    return shlex.join([
        "python3",
        "-B",
        str(Path(__file__).resolve()),
        subcommand,
        payload_str,
        *extra,
    ])


def _merge_stage_data(payload: dict[str, Any], response: dict[str, Any]) -> None:
    data = response.get("data", {})
    if isinstance(data, dict):
        payload.update(data)


def _ticket_for_payload(payload: dict[str, Any], tickets_dir: Path) -> Any | None:
    ticket_id = payload.get("ticket_id")
    if not isinstance(ticket_id, str) or not ticket_id:
        return None
    return find_ticket_by_id(tickets_dir, ticket_id, include_closed=True)


def _preview_identity(ticket: Any | None, payload: dict[str, Any]) -> dict[str, Any]:
    if ticket is not None:
        return ticket_identity(ticket)
    return {
        "id": payload.get("ticket_id"),
        "title": payload.get("fields", {}).get("title", ""),
        "path": None,
        "filename": None,
    }


def _field_changes(action: str, payload: dict[str, Any], ticket: Any | None) -> dict[str, Any]:
    fields = payload.get("fields", {})
    if not isinstance(fields, dict):
        return {}
    if action == "create":
        return dict(fields)
    if action == "close" and ticket is not None:
        resolution = fields.get("resolution", "done")
        return {"status": [ticket.status, resolution]}
    if action == "reopen" and ticket is not None:
        return {"status": [ticket.status, "open"]}
    if ticket is None:
        return dict(fields)
    changes: dict[str, Any] = {}
    for key, value in fields.items():
        if key == "status":
            changes[key] = [ticket.status, value]
        else:
            current = ticket.frontmatter.get(key)
            if current != value:
                changes[key] = [current, value]
    return changes


def _risk_flags(response: dict[str, Any]) -> list[str]:
    flags: list[str] = []
    state = response.get("state")
    error_code = response.get("error_code")
    if isinstance(state, str) and state not in {"ok", "ready_to_execute", "ok_create", "ok_update", "ok_close", "ok_close_archived", "ok_reopen"}:
        flags.append(state)
    if isinstance(error_code, str) and error_code not in flags:
        flags.append(error_code)
    precondition_code = response.get("data", {}).get("precondition_code")
    if isinstance(precondition_code, str) and precondition_code != "none" and precondition_code not in flags:
        flags.append(precondition_code)
    return flags


def _preview(
    payload_path: Path,
    payload: dict[str, Any],
    response: dict[str, Any],
    *,
    ready: bool,
) -> dict[str, Any]:
    action = str(payload.get("action", ""))
    ticket = _ticket_for_payload(payload, Path(payload["tickets_dir"]))
    fields = payload.get("fields", {})
    requested_status = None
    if action == "create":
        requested_status = "open"
    elif action == "close":
        requested_status = fields.get("resolution", "done") if isinstance(fields, dict) else "done"
    elif action == "reopen":
        requested_status = "open"
    elif isinstance(fields, dict):
        requested_status = fields.get("status", ticket.status if ticket is not None else None)
    blockers = {
        "blocking_ids": response.get("data", {}).get("blocking_ids", []),
        "unresolved_blockers": response.get("data", {}).get("unresolved_blockers", []),
        "missing_blockers": response.get("data", {}).get("missing_blockers", []),
    }
    return {
        "action": action,
        "action_label": humanize_state(action),
        "ticket_id": payload.get("ticket_id"),
        "ticket_identity": _preview_identity(ticket, payload),
        "will_write": ready,
        "field_changes": _field_changes(action, payload, ticket),
        "risk_flags": _risk_flags(response),
        "target_status": requested_status,
        "duplicate": payload.get("duplicate_of"),
        "blockers": blockers,
        "close_ready": ready if action == "close" else None,
        "next_command": _canonical_workflow_command("execute", payload_path) if ready else None,
    }


def _fields_from_validation_errors(validation_errors: Any) -> set[str]:
    fields: set[str] = set()
    if not isinstance(validation_errors, list):
        return fields
    for error in validation_errors:
        if isinstance(error, str) and error:
            fields.add(error.split(" ", 1)[0])
    return fields


def _need_fields_recovery_fields(action: str, data: dict[str, Any]) -> list[str]:
    missing_fields = {
        field for field in data.get("missing_fields", [])
        if isinstance(field, str)
    }
    candidate_fields = missing_fields | _fields_from_validation_errors(
        data.get("validation_errors", [])
    )
    if action == "create":
        candidates = candidate_fields or set(_CREATE_NEED_FIELDS)
        return [field for field in _CREATE_NEED_FIELDS if field in candidates]
    if action == "reopen":
        return ["reopen_reason"] if not candidate_fields or "reopen_reason" in candidate_fields else []
    if not candidate_fields:
        return []
    return [field for field in _UPDATE_NEED_FIELDS if field in candidate_fields]


def _placeholder_json_value(field: str) -> str:
    if field == "priority":
        return json.dumps("medium")
    if field == "tags":
        return json.dumps(["ux", "ticket"])
    if field == "blocked_by":
        return json.dumps(["T-00000000-00"])
    return json.dumps(f"set {field}")


def _with_recovery(
    payload_path: Path,
    payload: dict[str, Any],
    response: dict[str, Any],
    *,
    stage: str,
) -> dict[str, Any]:
    state = response.get("state")
    error_code = response.get("error_code")
    action = str(payload.get("action", ""))
    data = response.setdefault("data", {})
    allowed: list[dict[str, Any]] = [{"action": "cancel"}]
    options: list[dict[str, Any]] = []
    ticket_id = payload.get("ticket_id")
    duplicate_of = payload.get("duplicate_of")
    if state == "duplicate_candidate" and action == "create" and isinstance(duplicate_of, str):
        allowed.append({"action": "create_anyway"})
        recover_command = _canonical_workflow_command("recover", payload_path, "create_anyway")
        if recover_command is not None:
            options.append({
                "label": "Create anyway",
                "recover_command": recover_command,
            })
        options.append({
            "label": "Update existing",
            "suggested_ticket_command": f"ticket update {duplicate_of}",
        })
    elif state == "dependency_blocked" and action == "close" and isinstance(ticket_id, str):
        allowed.append({"action": "close_wontfix"})
        recover_command = _canonical_workflow_command("recover", payload_path, "close_wontfix")
        if recover_command is not None:
            options.append({
                "label": "Close as wontfix",
                "recover_command": recover_command,
            })
        options.append({
            "label": "Resolve blockers",
            "suggested_ticket_command": f"ticket check {ticket_id}",
        })
    elif state == "invalid_transition":
        if data.get("requires_reopen") and isinstance(ticket_id, str):
            options.append({
                "label": "Reopen ticket",
                "suggested_ticket_command": f"ticket reopen {ticket_id}",
            })
        else:
            for status in data.get("valid_recovery_statuses", []):
                allowed.append({"action": "set_status", "status": status})
                recover_command = _canonical_workflow_command("recover", payload_path, "set_status", status)
                if recover_command is not None:
                    options.append({
                        "label": f"Set status to {status}",
                        "recover_command": recover_command,
                    })
            if data.get("precondition_code") == "missing_acceptance_criteria" and isinstance(ticket_id, str):
                if action == "close":
                    allowed.append({"action": "close_wontfix"})
                    recover_command = _canonical_workflow_command("recover", payload_path, "close_wontfix")
                    if recover_command is not None:
                        options.append({
                            "label": "Close as wontfix",
                            "recover_command": recover_command,
                        })
                options.append({
                    "label": "Update ticket details",
                    "suggested_ticket_command": f"ticket update {ticket_id}",
                })
    elif state == "need_fields":
        for field in _need_fields_recovery_fields(action, data):
            allowed.append({"action": "set_field", "field": field})
            recover_command = _canonical_workflow_command(
                "recover",
                payload_path,
                "set_field",
                field,
                _placeholder_json_value(field),
            )
            if recover_command is not None:
                options.append({
                    "label": f"Set {field}",
                    "recover_command": recover_command,
                })
        if not options and isinstance(ticket_id, str):
            options.append({
                "label": "Update ticket details",
                "suggested_ticket_command": f"ticket update {ticket_id}",
            })
    elif state == "stale_plan" or error_code == "stale_plan":
        rerun = _canonical_workflow_command("prepare", payload_path)
        if rerun is not None:
            options.append({
                "label": "Rerun prepare",
                "recover_command": rerun,
            })

    if options:
        data["recovery_options"] = options
    authority_state = (
        error_code
        if error_code in {"need_fields", "duplicate_candidate", "invalid_transition", "dependency_blocked", "stale_plan"}
        else state
    )
    if authority_state in {"need_fields", "duplicate_candidate", "invalid_transition", "dependency_blocked", "stale_plan"}:
        payload["workflow_recovery"] = {
            "state": authority_state,
            "stage": stage,
            "error_code": response.get("error_code", authority_state),
            "action": action,
            "ticket_id": payload.get("ticket_id"),
            "target_fingerprint": payload.get("target_fingerprint"),
            "dedup_fingerprint": payload.get("dedup_fingerprint"),
            "duplicate_of": payload.get("duplicate_of"),
            "session_id": payload.get("session_id"),
            "request_origin": payload.get("hook_request_origin", payload.get("request_origin", "user")),
            "missing_fields": list(data.get("missing_fields", [])) if isinstance(data.get("missing_fields"), list) else [],
            "validation_errors": list(data.get("validation_errors", [])) if isinstance(data.get("validation_errors"), list) else [],
            "current_status": data.get("current_status"),
            "requested_status": data.get("requested_status"),
            "valid_recovery_statuses": list(data.get("valid_recovery_statuses", [])) if isinstance(data.get("valid_recovery_statuses"), list) else [],
            "requires_reopen": bool(data.get("requires_reopen", False)),
            "precondition_code": data.get("precondition_code", "none"),
            "precondition_detail": data.get("precondition_detail"),
            "allowed": allowed,
        }
    return response


def _prepare(payload_path: Path, payload: dict[str, Any], tickets_dir: Path, request_origin: str) -> dict[str, Any]:
    current = payload
    for subcommand in ("classify", "plan", "preflight"):
        response = _engine_response_to_dict(
            dispatch_stage(subcommand, current, tickets_dir, request_origin)
        )
        _merge_stage_data(current, response)
        current["tickets_dir"] = str(tickets_dir)
        if (
            subcommand == "classify"
            and current.get("action") != "create"
            and not current.get("ticket_id")
            and isinstance(response.get("data", {}).get("resolved_ticket_id"), str)
        ):
            current["ticket_id"] = response["data"]["resolved_ticket_id"]
        _write_payload_atomic(payload_path, current)
        if (
            subcommand == "plan"
            and response.get("state") == "duplicate_candidate"
            and current.get("dedup_override") is True
            and isinstance(current.get("duplicate_of"), str)
        ):
            continue
        if response.get("state") != "ok":
            response["data"]["preview"] = _preview(payload_path, current, response, ready=False)
            response = _with_recovery(payload_path, current, response, stage=subcommand)
            _write_payload_atomic(payload_path, current)
            return response

    action = str(current.get("action", ""))
    fields = current.get("fields", {})
    if not isinstance(fields, dict):
        return _response(
            "escalate",
            "prepare failed: fields must be a dict",
            error_code="parse_error",
        )
    policy_error = _evaluate_workflow_policy(
        action,
        current.get("ticket_id") if isinstance(current.get("ticket_id"), str) else None,
        fields,
        tickets_dir,
    )
    if policy_error is not None:
        response = _engine_response_to_dict(policy_error)
        _merge_stage_data(current, response)
        current["tickets_dir"] = str(tickets_dir)
        _write_payload_atomic(payload_path, current)
        response["data"]["preview"] = _preview(payload_path, current, response, ready=False)
        response = _with_recovery(payload_path, current, response, stage="policy")
        _write_payload_atomic(payload_path, current)
        return response

    current.pop("workflow_recovery", None)
    current["tickets_dir"] = str(tickets_dir)
    _write_payload_atomic(payload_path, current)
    response = _response(
        "ready_to_execute",
        f"Ready to execute {action}",
        data={"preview": _preview(payload_path, current, _response("ready_to_execute", ""), ready=True)},
        ticket_id=current.get("ticket_id") if isinstance(current.get("ticket_id"), str) else None,
    )
    return response


def _load_workflow_payload(payload_path: Path) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    context, error = load_runner_context(None, "prepare", payload_path)
    if error is not None:
        return None, _engine_response_to_dict(error)
    assert context is not None
    context.payload["tickets_dir"] = str(context.tickets_dir)
    return {
        "payload": context.payload,
        "tickets_dir": context.tickets_dir,
        "request_origin": context.request_origin,
    }, None


def _validate_recovery_authority(payload: dict[str, Any]) -> tuple[dict[str, Any] | None, str | None]:
    authority = payload.get("workflow_recovery")
    if not isinstance(authority, dict):
        return None, "workflow recovery failed: missing workflow_recovery authority"
    request_origin = payload.get("hook_request_origin", payload.get("request_origin"))
    checks = (
        ("action", payload.get("action")),
        ("ticket_id", payload.get("ticket_id")),
        ("target_fingerprint", payload.get("target_fingerprint")),
        ("dedup_fingerprint", payload.get("dedup_fingerprint")),
        ("duplicate_of", payload.get("duplicate_of")),
        ("session_id", payload.get("session_id")),
        ("request_origin", request_origin),
    )
    for key, current in checks:
        if authority.get(key) != current:
            return None, f"workflow recovery failed: authority binding mismatch for {key}"
    return authority, None


def _derived_recovery_allowlist(authority: dict[str, Any]) -> list[dict[str, Any]]:
    """Derive legal recovery mutations from immutable authority context."""
    state = authority.get("state")
    error_code = authority.get("error_code")
    stage = authority.get("stage")
    action = authority.get("action")
    if not all(isinstance(value, str) and value for value in (state, error_code, stage, action)):
        return []

    allowed: list[dict[str, Any]] = [{"action": "cancel"}]
    if (
        state == "duplicate_candidate"
        and error_code == "duplicate_candidate"
        and action == "create"
        and stage in {"plan", "execute"}
        and isinstance(authority.get("duplicate_of"), str)
    ):
        allowed.append({"action": "create_anyway"})
        return allowed

    if (
        state == "dependency_blocked"
        and error_code == "dependency_blocked"
        and action == "close"
        and stage in {"preflight", "policy", "execute"}
    ):
        allowed.append({"action": "close_wontfix"})
        return allowed

    if state == "invalid_transition" and error_code == "invalid_transition":
        if stage not in {"policy", "execute"}:
            return allowed
        if action == "update":
            statuses = authority.get("valid_recovery_statuses", [])
            if isinstance(statuses, list):
                for status in statuses:
                    if isinstance(status, str) and status:
                        allowed.append({"action": "set_status", "status": status})
        elif action == "close" and authority.get("precondition_code") == "missing_acceptance_criteria":
            allowed.append({"action": "close_wontfix"})
        return allowed

    if state == "need_fields" and error_code == "need_fields":
        if action == "create":
            if stage not in {"plan", "execute"}:
                return allowed
        elif action == "reopen":
            if stage not in {"policy", "execute"}:
                return allowed
        elif action in {"update", "close"}:
            if stage not in {"policy", "execute"}:
                return allowed
        else:
            return allowed
        data = {
            "missing_fields": authority.get("missing_fields", []),
            "validation_errors": authority.get("validation_errors", []),
        }
        for field in _need_fields_recovery_fields(action, data):
            allowed.append({"action": "set_field", "field": field})
        return allowed

    return allowed


def run_recovery(
    payload_path: Path,
    recovery_action: str,
    *,
    field: str | None = None,
    value: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return _response(
            "escalate",
            f"Cannot read payload: {exc}",
            error_code="parse_error",
        )
    if not isinstance(payload, dict):
        return _response(
            "escalate",
            f"Payload is not a JSON object, got {type(payload).__name__}",
            error_code="parse_error",
        )

    authority, authority_error = _validate_recovery_authority(payload)
    if authority_error is not None or authority is None:
        return _response("escalate", authority_error or "workflow recovery failed", error_code="policy_blocked")

    allowed = authority.get("allowed")
    if not isinstance(allowed, list):
        return _response("escalate", "workflow recovery failed: malformed workflow_recovery allowed list", error_code="policy_blocked")
    derived_allowed = _derived_recovery_allowlist(authority)

    fields = payload.get("fields")
    if not isinstance(fields, dict):
        return _response("escalate", "workflow recovery failed: fields must be a dict", error_code="parse_error")

    def _is_allowed(entries: list[Any], action_name: str, **criteria: Any) -> bool:
        for item in entries:
            if not isinstance(item, dict):
                continue
            if item.get("action") != action_name:
                continue
            if all(item.get(key) == expected for key, expected in criteria.items()):
                return True
        return False

    def _authorize(action_name: str, **criteria: Any) -> dict[str, Any] | None:
        if not _is_allowed(allowed, action_name, **criteria):
            return _response(
                "escalate",
                f"workflow recovery failed: {action_name} is not authorized",
                error_code="policy_blocked",
            )
        if not _is_allowed(derived_allowed, action_name, **criteria):
            return _response(
                "escalate",
                f"workflow recovery failed: {action_name} is not allowed for current recovery state",
                error_code="policy_blocked",
            )
        return None

    new_payload = dict(payload)
    new_fields = dict(fields)
    new_payload["fields"] = new_fields

    if recovery_action == "cancel":
        authorization_error = _authorize("cancel")
        if authorization_error is not None:
            return authorization_error
        new_payload.pop("workflow_recovery", None)
    elif recovery_action == "create_anyway":
        authorization_error = _authorize("create_anyway")
        if authorization_error is not None:
            return authorization_error
        if not payload.get("duplicate_of"):
            return _response("escalate", "workflow recovery failed: duplicate_of is required", error_code="policy_blocked")
        new_payload["dedup_override"] = True
        new_payload.pop("workflow_recovery", None)
    elif recovery_action == "close_wontfix":
        authorization_error = _authorize("close_wontfix")
        if authorization_error is not None:
            return authorization_error
        new_fields["resolution"] = "wontfix"
        new_payload.pop("workflow_recovery", None)
    elif recovery_action == "set_status":
        if not isinstance(status, str) or not status:
            return _response("escalate", "workflow recovery failed: status is required", error_code="parse_error")
        authorization_error = _authorize("set_status", status=status)
        if authorization_error is not None:
            return authorization_error
        new_fields["status"] = status
        new_payload.pop("workflow_recovery", None)
    elif recovery_action == "set_field":
        if not isinstance(field, str) or not field:
            return _response("escalate", "workflow recovery failed: field is required", error_code="parse_error")
        if field in _POLICY_OWNED_FIELDS or field not in _RECOVERABLE_SET_FIELDS:
            return _response("escalate", f"workflow recovery failed: set_field is not allowed for {field}", error_code="policy_blocked")
        authorization_error = _authorize("set_field", field=field)
        if authorization_error is not None:
            return authorization_error
        try:
            decoded = json.loads(value or "")
        except json.JSONDecodeError as exc:
            return _response("escalate", f"workflow recovery failed: invalid JSON value: {exc}", error_code="parse_error")
        new_fields[field] = decoded
        new_payload.pop("workflow_recovery", None)
    else:
        return _response("escalate", f"workflow recovery failed: unsupported action {recovery_action!r}", error_code="intent_mismatch")

    validation_errors = validate_fields(new_fields)
    if validation_errors:
        return _response(
            "need_fields",
            f"Field validation failed: {'; '.join(validation_errors)}",
            error_code="need_fields",
            data={"validation_errors": validation_errors},
        )

    try:
        _write_payload_atomic(payload_path, new_payload)
    except OSError as exc:
        return _response("escalate", str(exc), error_code="io_error")
    return _response("ok", f"Applied recovery action {recovery_action}")


def run_workflow(
    subcommand: str,
    payload_path: Path,
    *,
    request_origin: str | None = None,
    recovery_action: str | None = None,
    field: str | None = None,
    value: str | None = None,
    status: str | None = None,
) -> dict[str, Any]:
    if subcommand == "recover":
        if recovery_action is None:
            return _response(
                "escalate",
                "ticket_workflow.py recover requires a recovery action after the payload path",
                error_code="intent_mismatch",
            )
        return run_recovery(payload_path, recovery_action, field=field, value=value, status=status)

    context, error = load_runner_context(request_origin, subcommand, payload_path)
    if error is not None:
        return _engine_response_to_dict(error)
    assert context is not None
    context.payload["tickets_dir"] = str(context.tickets_dir)

    if subcommand == "prepare":
        return _prepare(payload_path, context.payload, context.tickets_dir, context.request_origin)
    if subcommand == "execute":
        response = _engine_response_to_dict(
            dispatch_stage("execute", context.payload, context.tickets_dir, context.request_origin)
        )
        if response.get("state") != "ok_create" and not str(response.get("state", "")).startswith("ok_"):
            response = _with_recovery(payload_path, context.payload, response, stage="execute")
            _write_payload_atomic(payload_path, context.payload)
            return response
        return response
    return _response(
        "escalate",
        f"Unknown workflow subcommand: {subcommand!r}",
        error_code="intent_mismatch",
    )


def _exit_code(state: str) -> int:
    if state in {"ok", "ready_to_execute", "ok_create", "ok_update", "ok_close", "ok_close_archived", "ok_reopen"}:
        return 0
    if state == "need_fields":
        return 2
    return 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print(json.dumps({"error": "Usage: ticket_workflow.py prepare|execute|recover <payload_file> [args...]"}))
        return 1

    subcommand = args[0]
    payload_path = Path(args[1])

    if subcommand in {"prepare", "execute"}:
        if len(args) != 2:
            print(json.dumps({"error": f"Usage: ticket_workflow.py {subcommand} <payload_file>"}))
            return 1
        response = run_workflow(subcommand, payload_path)
    elif subcommand == "recover":
        if len(args) < 3:
            response = _response(
                "escalate",
                "ticket_workflow.py recover requires a recovery action after the payload path",
                error_code="intent_mismatch",
            )
        else:
            recovery_action = args[2]
            kwargs: dict[str, Any] = {}
            if recovery_action == "set_field":
                if len(args) != 5:
                    response = _response(
                        "escalate",
                        f"Recovery action '{recovery_action}' expects 2 argument(s), got {len(args) - 3}",
                        error_code="intent_mismatch",
                    )
                else:
                    kwargs["field"] = args[3]
                    kwargs["value"] = args[4]
                    response = run_workflow(subcommand, payload_path, recovery_action=recovery_action, **kwargs)
            elif recovery_action == "set_status":
                if len(args) != 4:
                    response = _response(
                        "escalate",
                        f"Recovery action '{recovery_action}' expects 1 argument(s), got {len(args) - 3}",
                        error_code="intent_mismatch",
                    )
                else:
                    kwargs["status"] = args[3]
                    response = run_workflow(subcommand, payload_path, recovery_action=recovery_action, **kwargs)
            else:
                if len(args) != 3:
                    response = _response(
                        "escalate",
                        f"Recovery action '{recovery_action}' expects 0 argument(s), got {len(args) - 3}",
                        error_code="intent_mismatch",
                    )
                else:
                    response = run_workflow(subcommand, payload_path, recovery_action=recovery_action)
    else:
        response = _response(
            "escalate",
            f"Unknown workflow subcommand: {subcommand!r}",
            error_code="intent_mismatch",
        )

    print(json.dumps(response))
    return _exit_code(str(response.get("state", "")))


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Focused ticket refinement and lifecycle update entrypoint."""

from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_engine_core import _evaluate_workflow_policy  # noqa: E402
from scripts.ticket_engine_runner import dispatch_stage, load_runner_context  # noqa: E402
from scripts.ticket_paths import discover_project_root, resolve_tickets_dir  # noqa: E402
from scripts.ticket_payloads import TicketPayloadPathError, delete_consumed_payload  # noqa: E402
from scripts.ticket_read import find_ticket_by_id  # noqa: E402
from scripts.ticket_ux import attach_recovery_hint, recovery_hint_code_for_response  # noqa: E402

_ALLOWED_UPDATE_FIELDS = frozenset(
    {
        "problem",
        "next_action",
        "acceptance_criteria",
        "priority",
        "tags",
        "component",
        "related_paths",
        "blocked_by",
        "blocks",
        "status",
        "reopen_reason",
    }
)
_SECTION_FIELDS = frozenset({"problem", "next_action", "acceptance_criteria"})
_METADATA_FIELDS = frozenset(
    {"priority", "tags", "component", "related_paths", "blocked_by", "blocks"}
)
_PLACEHOLDER_VALUES = frozenset({"", "needs refinement", "tbd", "todo", "placeholder"})
_CLOSE_FIELDS = frozenset({"status"})
_REOPEN_FIELDS = frozenset({"status", "reopen_reason"})
_EXECUTE_FINGERPRINT_KEYS = (
    "action",
    "ticket_id",
    "fields",
    "tickets_dir",
    "target_fingerprint",
    "classify_intent",
    "classify_confidence",
    "dedup_override",
    "dependency_override",
    "dedup_fingerprint",
    "duplicate_of",
    "autonomy_config",
    "session_id",
    "hook_injected",
    "hook_request_origin",
)


def _response(
    state: str,
    message: str,
    *,
    error_code: str | None = None,
    data: dict[str, Any] | None = None,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {"state": state, "message": message, "data": data or {}}
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


_SAFE_MESSAGE_BY_RECOVERY_CODE = {
    "stale_plan": "The saved preview is no longer current.",
    "trust_setup": "Ticket setup needs attention before this write can continue.",
    "retry_preview": "The saved preview state is no longer usable.",
    "policy_blocked": "This write is blocked by Ticket policy.",
    "preflight_failed": "Ticket checks did not pass.",
}


def _with_default_recovery_hint(response: dict[str, Any]) -> dict[str, Any]:
    code = recovery_hint_code_for_response(response)
    if code is None:
        return response
    safe_response = dict(response)
    safe_response["message"] = _SAFE_MESSAGE_BY_RECOVERY_CODE.get(
        code,
        safe_response.get("message", ""),
    )
    return attach_recovery_hint(safe_response, code)


def _write_payload_atomic(payload_path: Path, payload: dict[str, Any]) -> None:
    parent = payload_path.parent
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        try:
            os.write(fd, json.dumps(payload, indent=2).encode("utf-8"))
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


def _validate_payload_path(payload_path: Path, project_root: Path) -> str | None:
    payload_str = str(payload_path)
    if any(char.isspace() for char in payload_str):
        return f"Payload path must not contain whitespace. Got: {payload_str!r:.100}"
    if not payload_path.is_absolute():
        return f"Payload path must be absolute. Got: {payload_str!r:.100}"
    try:
        resolved = payload_path.resolve()
        root = project_root.resolve()
    except OSError as exc:
        return f"Payload path resolution failed: {exc}. Got: {payload_str!r:.100}"
    try:
        resolved.relative_to(root)
    except ValueError:
        return f"Payload path outside workspace root {str(root)!r}. Got: {payload_str!r:.100}"
    return None


def _load_update_context(
    subcommand: str,
    payload_path: Path,
) -> tuple[dict[str, Any] | None, Path | None, str | None, dict[str, Any] | None]:
    project_root = discover_project_root(Path.cwd())
    if project_root is None:
        return (
            None,
            None,
            None,
            _response(
                "policy_blocked",
                "Cannot determine project root: no .codex/ or .git/ marker "
                "found in ancestors of cwd",
                error_code="policy_blocked",
            ),
        )
    path_error = _validate_payload_path(payload_path, project_root)
    if path_error is not None:
        return (
            None,
            None,
            None,
            _response(
                "policy_blocked",
                path_error,
                error_code="policy_blocked",
            ),
        )

    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return (
            None,
            None,
            None,
            _response(
                "escalate",
                f"Cannot read payload: {exc}",
                error_code="parse_error",
            ),
        )
    if not isinstance(payload, dict):
        return (
            None,
            None,
            None,
            _response(
                "escalate",
                f"Payload is not a JSON object, got {type(payload).__name__}",
                error_code="parse_error",
            ),
        )

    tickets_dir, tickets_error = resolve_tickets_dir(
        payload.get("tickets_dir", "docs/tickets"),
        project_root=project_root,
    )
    if tickets_error is not None or tickets_dir is None:
        return (
            None,
            None,
            None,
            _response(
                "policy_blocked",
                tickets_error or "tickets_dir validation failed",
                error_code="policy_blocked",
            ),
        )

    if subcommand == "execute":
        context, error = load_runner_context(None, "execute", payload_path)
        if error is not None:
            return None, None, None, _engine_response_to_dict(error)
        assert context is not None
        context.payload["tickets_dir"] = str(context.tickets_dir)
        return context.payload, context.tickets_dir, context.request_origin, None

    request_origin = payload.get("hook_request_origin") or payload.get("request_origin") or "user"
    if not isinstance(request_origin, str) or not request_origin:
        return (
            None,
            None,
            None,
            _response(
                "escalate",
                f"Invalid request origin. Got: {request_origin!r:.100}",
                error_code="parse_error",
            ),
        )
    payload["request_origin"] = request_origin
    payload["tickets_dir"] = str(tickets_dir)
    return payload, tickets_dir, request_origin, None


def _json_fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _execute_fingerprint(payload: dict[str, Any]) -> str:
    prepared = {key: payload.get(key) for key in _EXECUTE_FINGERPRINT_KEYS}
    return _json_fingerprint(prepared)


def _placeholder_text(value: Any) -> bool:
    if not isinstance(value, str):
        return True
    normalized = " ".join(value.strip().lower().split())
    return normalized in _PLACEHOLDER_VALUES


def _acceptance_criteria_concrete(criteria: Any) -> bool:
    if not isinstance(criteria, list) or not criteria:
        return False
    return all(isinstance(item, str) and not _placeholder_text(item) for item in criteria)


def _will_clear_refinement(ticket: Any, update: dict[str, Any]) -> bool:
    if ticket.refinement_status != "needs_refinement":
        return False
    if not _SECTION_FIELDS.issubset(update):
        return False
    problem = update["problem"]
    next_action = update["next_action"]
    criteria = update["acceptance_criteria"]
    return (
        not _placeholder_text(problem)
        and not _placeholder_text(next_action)
        and _acceptance_criteria_concrete(criteria)
    )


def _action_and_fields(ticket: Any, update: dict[str, Any]) -> tuple[str, dict[str, Any]]:
    status = update.get("status")
    if status in {"done", "wontfix"}:
        return "close", {"resolution": status}
    if status == "open" and ticket.status in {"done", "wontfix"}:
        return "reopen", {"reopen_reason": update.get("reopen_reason", "")}
    if "reopen_reason" in update and ticket.status in {"done", "wontfix"}:
        return "reopen", {"reopen_reason": update.get("reopen_reason", "")}

    fields = {key: update[key] for key in _METADATA_FIELDS if key in update}
    if "status" in update:
        fields["status"] = update["status"]
    for key in _SECTION_FIELDS:
        if key in update:
            fields[key] = update[key]
    if any(key in fields for key in _SECTION_FIELDS):
        fields["_update_mode"] = "focused_refinement"
    return "update", fields


def _prepare_fields(ticket: Any, update: dict[str, Any]) -> tuple[str, dict[str, Any], bool]:
    action, fields = _action_and_fields(ticket, update)
    clear_refinement = action == "update" and _will_clear_refinement(ticket, update)
    if clear_refinement:
        fields["_clear_refinement_status"] = True
        fields["tags"] = [
            tag for tag in fields.get("tags", ticket.tags) if tag != "needs-refinement"
        ]
    elif action == "update" and "tags" in fields and ticket.refinement_status == "needs_refinement":
        tags = fields["tags"]
        if isinstance(tags, list) and "needs-refinement" not in tags:
            fields["tags"] = [*tags, "needs-refinement"]
        fields["refinement_status"] = "needs_refinement"
    return action, fields, clear_refinement


def _field_changes(ticket: Any, action: str, fields: dict[str, Any]) -> dict[str, Any]:
    if action == "close":
        return {"status": [ticket.status, fields.get("resolution", "done")]}
    if action == "reopen":
        return {"status": [ticket.status, "open"]}
    changes: dict[str, Any] = {}
    for key, value in fields.items():
        if key.startswith("_"):
            continue
        if key in _SECTION_FIELDS:
            continue
        current = ticket.status if key == "status" else ticket.frontmatter.get(key)
        if current != value:
            changes[key] = [current, value]
    return changes


def _section_changes(ticket: Any, fields: dict[str, Any]) -> dict[str, Any]:
    heading_by_key = {
        "problem": "Problem",
        "next_action": "Next Action",
        "acceptance_criteria": "Acceptance Criteria",
    }
    changes: dict[str, Any] = {}
    for key, heading in heading_by_key.items():
        if key not in fields:
            continue
        old = ticket.sections.get(heading, "")
        changes[key] = {"from": old, "to": fields[key]}
    return changes


def _preview(
    ticket: Any,
    action: str,
    fields: dict[str, Any],
    *,
    clear_refinement: bool,
    ready: bool,
) -> dict[str, Any]:
    refinement = "will clear needs-refinement" if clear_refinement else "unchanged"
    return {
        "ticket_id": ticket.id,
        "title": ticket.title,
        "action": action,
        "will_write": ready,
        "field_changes": _field_changes(ticket, action, fields),
        "section_changes": _section_changes(ticket, fields),
        "refinement": refinement,
    }


def _validate_update_payload(update: Any) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    if not isinstance(update, dict):
        return None, _response(
            "need_fields",
            "update must be a JSON object",
            error_code="need_fields",
            data={"missing_fields": ["update"]},
        )
    unsupported = sorted(key for key in update if key not in _ALLOWED_UPDATE_FIELDS)
    if unsupported:
        return None, _response(
            "need_fields",
            f"Unsupported update fields: {', '.join(unsupported)}",
            error_code="unsupported_update_fields",
            data={"unsupported_fields": unsupported},
        )
    return dict(update), None


def _validate_lifecycle_payload(update: dict[str, Any]) -> dict[str, Any] | None:
    status = update.get("status")
    if status in {"done", "wontfix"}:
        unsupported = sorted(key for key in update if key not in _CLOSE_FIELDS)
        if unsupported:
            return _response(
                "need_fields",
                f"Unsupported fields for lifecycle close: {', '.join(unsupported)}",
                error_code="unsupported_update_fields",
                data={"unsupported_fields": unsupported},
            )
    if status == "open" or "reopen_reason" in update:
        unsupported = sorted(key for key in update if key not in _REOPEN_FIELDS)
        if unsupported:
            return _response(
                "need_fields",
                f"Unsupported fields for lifecycle reopen: {', '.join(unsupported)}",
                error_code="unsupported_update_fields",
                data={"unsupported_fields": unsupported},
            )
    return None


def _prepare(payload_path: Path) -> dict[str, Any]:
    payload, tickets_dir, request_origin, error = _load_update_context("prepare", payload_path)
    if error is not None:
        return _with_default_recovery_hint(error)
    assert payload is not None and tickets_dir is not None and request_origin is not None

    update, update_error = _validate_update_payload(payload.get("update"))
    if update_error is not None or update is None:
        return update_error or _response("need_fields", "update fields invalid")
    lifecycle_error = _validate_lifecycle_payload(update)
    if lifecycle_error is not None:
        return lifecycle_error

    ticket_id = payload.get("ticket_id")
    if not isinstance(ticket_id, str) or not ticket_id:
        return _response(
            "need_fields",
            "ticket_id required for update",
            error_code="need_fields",
            data={"missing_fields": ["ticket_id"]},
        )
    ticket = find_ticket_by_id(tickets_dir, ticket_id, include_closed=True)
    if ticket is None:
        return _response(
            "not_found",
            f"No ticket found matching {ticket_id}",
            error_code="not_found",
            ticket_id=ticket_id,
        )

    action, fields, clear_refinement = _prepare_fields(ticket, update)
    current = dict(payload)
    current["action"] = action
    current["args"] = {"ticket_id": ticket_id}
    current["ticket_id"] = ticket_id
    current["fields"] = fields
    current["tickets_dir"] = str(tickets_dir)

    policy_error = _evaluate_workflow_policy(action, ticket_id, fields, tickets_dir)
    if policy_error is not None:
        return _with_default_recovery_hint(_engine_response_to_dict(policy_error))

    for stage in ("classify", "plan", "preflight"):
        response = _engine_response_to_dict(
            dispatch_stage(stage, current, tickets_dir, request_origin)
        )
        if response.get("state") != "ok":
            return _with_default_recovery_hint(response)
        current.update(response.get("data", {}))

    preview = _preview(ticket, action, fields, clear_refinement=clear_refinement, ready=True)
    prepare_artifact = {
        "state": "ready_to_execute",
        "fields_fingerprint": _json_fingerprint(fields),
        "update_fingerprint": _json_fingerprint(update),
        "execute_fingerprint": _execute_fingerprint(current),
        "preview": preview,
        "preview_fingerprint": _json_fingerprint(preview),
    }
    current["update_prepare"] = prepare_artifact
    current["update"] = update

    try:
        _write_payload_atomic(payload_path, current)
    except OSError as exc:
        return _response("escalate", str(exc), error_code="io_error")

    message = "Update preview ready"
    if clear_refinement:
        message += "\nRefinement: will clear needs-refinement"
    return _response("ready_to_execute", message, data={"preview": preview}, ticket_id=ticket_id)


def _execute(payload_path: Path) -> dict[str, Any]:
    payload, tickets_dir, request_origin, error = _load_update_context("execute", payload_path)
    if error is not None:
        return _with_default_recovery_hint(error)
    assert payload is not None and tickets_dir is not None and request_origin is not None

    prepare_artifact = payload.get("update_prepare")
    if (
        not isinstance(prepare_artifact, dict)
        or prepare_artifact.get("state") != "ready_to_execute"
    ):
        return attach_recovery_hint(
            _response(
                "preflight_failed",
                "The saved preview state is no longer usable.",
                error_code="stale_plan",
            ),
            "retry_preview",
        )
    fields = payload.get("fields")
    update = payload.get("update")
    preview = prepare_artifact.get("preview")
    if (
        not isinstance(fields, dict)
        or not isinstance(update, dict)
        or not isinstance(preview, dict)
    ):
        return attach_recovery_hint(
            _response(
                "preflight_failed",
                "The saved preview state is no longer usable.",
                error_code="stale_plan",
            ),
            "retry_preview",
        )
    if prepare_artifact.get("fields_fingerprint") != _json_fingerprint(fields):
        return attach_recovery_hint(
            _response(
                "preflight_failed",
                "The saved preview is no longer current.",
                error_code="stale_plan",
            ),
            "stale_plan",
        )
    if prepare_artifact.get("update_fingerprint") != _json_fingerprint(update):
        return attach_recovery_hint(
            _response(
                "preflight_failed",
                "The saved preview is no longer current.",
                error_code="stale_plan",
            ),
            "stale_plan",
        )
    if prepare_artifact.get("preview_fingerprint") != _json_fingerprint(preview):
        return attach_recovery_hint(
            _response(
                "preflight_failed",
                "The saved preview is no longer current.",
                error_code="stale_plan",
            ),
            "stale_plan",
        )
    if prepare_artifact.get("execute_fingerprint") != _execute_fingerprint(payload):
        return attach_recovery_hint(
            _response(
                "preflight_failed",
                "The saved preview is no longer current.",
                error_code="stale_plan",
            ),
            "stale_plan",
        )

    project_root = discover_project_root(tickets_dir)
    if project_root is None:
        return _with_default_recovery_hint(
            _response(
                "policy_blocked",
                (
                    "Cannot determine project root for payload cleanup: "
                    "no .codex/ or .git/ marker found"
                ),
                error_code="policy_blocked",
            )
        )

    response = _engine_response_to_dict(
        dispatch_stage("execute", payload, tickets_dir, request_origin)
    )
    if response.get("state") == "ok_update":
        response.setdefault("data", {})["preview"] = preview
    if response.get("state") in {"ok_update", "ok_close", "ok_reopen"}:
        try:
            response.setdefault("data", {})["payload_deleted"] = delete_consumed_payload(
                payload_path,
                project_root,
            )
        except (OSError, TicketPayloadPathError) as exc:
            response.setdefault("data", {})["payload_cleanup_error"] = str(exc)
    return _with_default_recovery_hint(response)


def run_update(subcommand: str, payload_path: Path) -> dict[str, Any]:
    """Run the focused ticket update flow and return a response dict."""
    if subcommand == "prepare":
        return _prepare(payload_path)
    if subcommand == "execute":
        return _execute(payload_path)
    return _response(
        "escalate",
        f"Unknown subcommand: {subcommand!r}. Valid: ['execute', 'prepare']",
        error_code="intent_mismatch",
    )


def main(argv: list[str] | None = None) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) != 2:
        print(json.dumps({"error": "Usage: ticket_update.py <prepare|execute> <payload_file>"}))
        return 1
    response = run_update(args[0], Path(args[1]))
    print(json.dumps(response, indent=2))
    ok_states = {"ready_to_execute", "ok_update", "ok_close", "ok_reopen"}
    return 0 if response["state"] in ok_states else 1


if __name__ == "__main__":
    raise SystemExit(main())

#!/usr/bin/env python3
"""Capture-first ticket creation entrypoint."""

from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.ticket_dedup import normalize  # noqa: E402
from scripts.ticket_engine_runner import dispatch_stage, load_runner_context  # noqa: E402
from scripts.ticket_paths import discover_project_root, resolve_tickets_dir  # noqa: E402
from scripts.ticket_payloads import TicketPayloadPathError, delete_consumed_payload  # noqa: E402
from scripts.ticket_read import find_ticket_by_id, list_tickets  # noqa: E402
from scripts.ticket_ux import attach_recovery_hint, recovery_hint_code_for_response  # noqa: E402
from scripts.ticket_validate import (  # noqa: E402
    CAPTURE_INPUT_FIELDS,
    CONTROLLED_CAPTURE_TAGS,
    validate_fields,
)

_RAW_USER_WORDING_KEYS = frozenset(
    {
        "raw_user_text",
        "raw_request",
        "transcript_excerpt",
    }
)
_REQUIRED_CAPTURE_FIELDS = (
    "title",
    "captured_request",
    "problem",
    "next_action",
)
_ALLOWED_CAPTURE_FIELDS = CAPTURE_INPUT_FIELDS
_PROMPT = "Create this ticket? [create / edit / cancel]"
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
_NEGATED_PRIORITY_PATTERNS = (
    r"\b(?:not|no)\s+(?:a\s+)?security\s+(?:issue|incident|bug|vulnerability)\b",
    r"\b(?:not|no)\s+data[- ]loss\b",
    r"\b(?:not|no)\s+(?:a\s+)?credential\s+leak\b",
    r"\b(?:does\s+not|doesn't|not)\s+block\s+release\b",
    r"\b(?:not|no)\s+release[- ]blocking\b",
    r"\b(?:not|no)\s+(?:a\s+)?regression\b",
    r"\b(?:not|no)\s+(?:a\s+)?blocker\b",
)
_CRITICAL_PRIORITY_PATTERNS = (
    r"\bprod(?:uction)?\s+(?:is\s+)?down\b",
    r"\bdata[- ]loss\b",
    r"\bsecurity\s+(?:issue|incident|bug|vulnerability)\b",
    r"\bcredential(?:s)?\s+(?:leak|leaked|exposed)\b",
    r"\bblocks?\s+release\b",
    r"\brelease[- ]blocking\b",
)
_HIGH_PRIORITY_PATTERNS = (
    r"\bblocking\s+me\b",
    r"\bblocker\b",
    r"\bci\s+(?:is\s+)?red\b",
    r"\bcannot\s+ship\b",
    r"\bregression\b",
)
_LOW_PRIORITY_PATTERNS = (
    r"\bcleanup\b",
    r"\bpolish\b",
    r"\bnice[- ]to[- ]have\b",
)


def _response(
    state: str,
    message: str,
    *,
    error_code: str | None = None,
    data: dict[str, Any] | None = None,
    ticket_id: str | None = None,
) -> dict[str, Any]:
    response: dict[str, Any] = {
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


def _load_capture_context(
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
            _response("policy_blocked", path_error, error_code="policy_blocked"),
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


def _raw_wording_path(value: Any, path: str = "capture") -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            key_path = f"{path}.{key}"
            if key in _RAW_USER_WORDING_KEYS:
                return key_path
            found = _raw_wording_path(item, key_path)
            if found is not None:
                return found
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found = _raw_wording_path(item, f"{path}[{index}]")
            if found is not None:
                return found
    return None


def _infer_priority(capture: dict[str, Any]) -> str:
    existing = capture.get("priority")
    if isinstance(existing, str) and existing:
        return existing
    text = " ".join(
        str(capture.get(key, "")) for key in ("title", "captured_request", "problem", "next_action")
    ).lower()
    signal_text = text
    for pattern in _NEGATED_PRIORITY_PATTERNS:
        signal_text = re.sub(pattern, " ", signal_text)
    if any(re.search(pattern, signal_text) for pattern in _CRITICAL_PRIORITY_PATTERNS):
        return "critical"
    if any(re.search(pattern, signal_text) for pattern in _HIGH_PRIORITY_PATTERNS):
        return "high"
    if any(re.search(pattern, signal_text) for pattern in _LOW_PRIORITY_PATTERNS):
        return "low"
    return "medium"


def _is_split_edit(edit_text: str) -> bool:
    lowered = edit_text.lower()
    return "split" in lowered and ("two ticket" in lowered or "two separate" in lowered)


def _apply_edit(capture: dict[str, Any], edit_text: str) -> tuple[dict[str, Any], bool]:
    updated = dict(capture)
    lowered = edit_text.lower()
    if "critical priority" in lowered or "make it critical" in lowered:
        updated["priority"] = "critical"
    elif "high priority" in lowered or "make it high" in lowered:
        updated["priority"] = "high"
    elif "low priority" in lowered or "make it low" in lowered:
        updated["priority"] = "low"
    elif "medium priority" in lowered or "make it medium" in lowered:
        updated["priority"] = "medium"
    elif _is_split_edit(edit_text):
        return updated, True
    else:
        return updated, False
    return updated, True


def _append_edit_history(payload: dict[str, Any], edit_text: str) -> None:
    history = payload.get("edit_history")
    if not isinstance(history, list):
        history = []
    history.append(
        {
            "ts": datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "instruction": edit_text,
        }
    )
    payload["edit_history"] = history


def _capture_fields(
    payload: dict[str, Any],
    *,
    edit_text: str | None,
) -> tuple[dict[str, Any] | None, dict[str, Any] | None]:
    capture = payload.get("capture")
    if not isinstance(capture, dict):
        return None, _response(
            "need_fields",
            "capture must be a JSON object",
            error_code="need_fields",
            data={"missing_fields": ["capture"]},
        )
    raw_path = _raw_wording_path(capture)
    if raw_path is not None:
        return None, _response(
            "need_fields",
            f"capture rejected raw user wording key: {raw_path}",
            error_code="raw_user_wording",
            data={"field": raw_path},
        )

    unsupported = sorted(key for key in capture if key not in _ALLOWED_CAPTURE_FIELDS)
    if unsupported:
        return None, _response(
            "need_fields",
            f"Unsupported capture fields: {', '.join(unsupported)}",
            error_code="unsupported_capture_fields",
            data={"unsupported_fields": unsupported},
        )

    if edit_text:
        capture, edit_applied = _apply_edit(capture, edit_text)
        if not edit_applied:
            return None, _response(
                "need_fields",
                "edit instruction was not applied; update the capture payload and rerun prepare",
                error_code="need_fields",
                data={"edit_applied": False},
            )
        _append_edit_history(payload, edit_text)
        payload["capture"] = capture

    missing = [
        field
        for field in _REQUIRED_CAPTURE_FIELDS
        if not isinstance(capture.get(field), str) or not capture.get(field, "").strip()
    ]
    if missing:
        return None, _response(
            "need_fields",
            f"Missing required capture fields: {', '.join(missing)}",
            error_code="need_fields",
            data={"missing_fields": missing},
        )

    priority = _infer_priority(capture)
    fields = {key: value for key, value in capture.items() if key in _ALLOWED_CAPTURE_FIELDS}
    fields["priority"] = priority
    fields["capture_confidence"] = fields.get("capture_confidence") or "medium"
    fields["capture_source"] = "conversation"
    fields["source"] = {
        "type": "capture",
        "ref": "",
        "session": str(payload.get("session_id", "")),
    }
    if "acceptance_criteria" not in fields:
        if fields.get("refinement_status") == "needs_refinement":
            fields["acceptance_criteria"] = ["Needs refinement"]
        else:
            fields["acceptance_criteria"] = [str(fields["next_action"])]

    tags = fields.get("tags", [])
    if not isinstance(tags, list):
        return None, _response(
            "need_fields",
            "tags must be a list",
            error_code="need_fields",
            data={"validation_errors": ["tags must be a list"]},
        )
    unknown_tags = [
        tag for tag in tags if isinstance(tag, str) and tag not in CONTROLLED_CAPTURE_TAGS
    ]
    if unknown_tags:
        return None, _response(
            "need_fields",
            f"capture tags must be controlled tags: {', '.join(unknown_tags)}",
            error_code="need_fields",
            data={"validation_errors": [f"unsupported capture tag: {tag}" for tag in unknown_tags]},
        )

    validation_errors = validate_fields(fields)
    if validation_errors:
        return None, _response(
            "need_fields",
            f"Field validation failed: {'; '.join(validation_errors)}",
            error_code="need_fields",
            data={"missing_fields": [], "validation_errors": validation_errors},
        )
    return fields, None


def _path_cores(paths: Any) -> set[str]:
    if not isinstance(paths, list):
        return set()
    return {Path(path).name for path in paths if isinstance(path, str) and path}


def _duplicate_from_target(payload: dict[str, Any], tickets_dir: Path) -> Any | None:
    target_ticket_id = payload.get("target_ticket_id")
    if not isinstance(target_ticket_id, str) or not target_ticket_id:
        return None
    return find_ticket_by_id(tickets_dir, target_ticket_id, include_closed=True)


def _duplicate_from_title(fields: dict[str, Any], tickets_dir: Path) -> tuple[Any | None, bool]:
    normalized_title = normalize(str(fields.get("title", "")))
    component = fields.get("component")
    related_cores = _path_cores(fields.get("related_paths"))
    if not normalized_title:
        return None, False
    for ticket in list_tickets(tickets_dir, include_closed=True):
        if normalize(ticket.title) != normalized_title:
            continue
        same_component = isinstance(component, str) and component and ticket.component == component
        same_path = bool(related_cores & _path_cores(ticket.related_paths))
        return ticket, same_component or same_path
    return None, False


def _duplicate_info(
    payload: dict[str, Any],
    fields: dict[str, Any],
    plan_response: dict[str, Any],
    tickets_dir: Path,
) -> dict[str, Any]:
    target_ticket = _duplicate_from_target(payload, tickets_dir)
    title_ticket, title_is_strong = _duplicate_from_title(fields, tickets_dir)
    duplicate_of = plan_response.get("data", {}).get("duplicate_of")
    plan_ticket = (
        find_ticket_by_id(tickets_dir, duplicate_of, include_closed=True)
        if isinstance(duplicate_of, str) and duplicate_of
        else None
    )
    ticket = target_ticket or title_ticket or plan_ticket
    if ticket is None:
        return {
            "label": "none",
            "ticket_id": None,
            "title": "",
            "default_action": "create_anyway",
        }
    default_action = (
        "update_existing" if target_ticket is not None or title_is_strong else "create_anyway"
    )
    return {
        "label": "possible",
        "ticket_id": ticket.id,
        "title": ticket.title,
        "default_action": default_action,
    }


def _exceptional_fields(fields: dict[str, Any]) -> dict[str, Any]:
    exceptional: dict[str, Any] = {}
    confidence = fields.get("capture_confidence", "medium")
    priority = fields.get("priority", "medium")
    if priority != "medium" or confidence == "low":
        exceptional["priority"] = priority
    for key in ("refinement_status", "component", "related_paths"):
        value = fields.get(key)
        if value:
            exceptional[key] = value
    return exceptional


def _preview(fields: dict[str, Any], duplicate: dict[str, Any]) -> dict[str, Any]:
    confidence = str(fields.get("capture_confidence", "medium"))
    preview: dict[str, Any] = {
        "title": fields["title"],
        "problem": fields["problem"],
        "next_action": fields["next_action"],
        "confidence": confidence,
        "duplicate": duplicate,
        "prompt": _PROMPT,
        "exceptional_fields": _exceptional_fields(fields),
    }
    priority = str(fields.get("priority", "medium"))
    if priority != "medium" or confidence == "low":
        preview["priority"] = priority
    return preview


def _json_fingerprint(value: Any) -> str:
    encoded = json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _prepare_fingerprint(fields: dict[str, Any]) -> str:
    return _json_fingerprint(fields)


def _execute_fingerprint(payload: dict[str, Any]) -> str:
    prepared = {key: payload.get(key) for key in _EXECUTE_FINGERPRINT_KEYS}
    return _json_fingerprint(prepared)


def _suggested_next_capture(edit_text: str | None) -> str:
    if edit_text and _is_split_edit(edit_text):
        return "Capture the second requested ticket as a separate follow-up."
    return ""


def _prepare(payload_path: Path, edit_text: str | None) -> dict[str, Any]:
    payload, tickets_dir, request_origin, error = _load_capture_context("prepare", payload_path)
    if error is not None:
        return _with_default_recovery_hint(error)
    assert payload is not None and tickets_dir is not None and request_origin is not None

    fields, field_error = _capture_fields(payload, edit_text=edit_text)
    if field_error is not None or fields is None:
        try:
            _write_payload_atomic(payload_path, payload)
        except OSError as exc:
            return _response("escalate", str(exc), error_code="io_error")
        return field_error or _response(
            "need_fields", "capture fields invalid", error_code="need_fields"
        )

    current = dict(payload)
    current["action"] = "create"
    current["args"] = {}
    current["fields"] = fields
    current["tickets_dir"] = str(tickets_dir)

    classify_response = _engine_response_to_dict(
        dispatch_stage("classify", current, tickets_dir, request_origin)
    )
    if classify_response.get("state") != "ok":
        return _with_default_recovery_hint(classify_response)
    current.update(classify_response.get("data", {}))

    plan_response = _engine_response_to_dict(
        dispatch_stage("plan", current, tickets_dir, request_origin)
    )
    if plan_response.get("state") not in {"ok", "duplicate_candidate"}:
        return _with_default_recovery_hint(plan_response)
    current.update(plan_response.get("data", {}))
    duplicate = _duplicate_info(payload, fields, plan_response, tickets_dir)
    if current.get("duplicate_of"):
        current["dedup_override"] = True

    preflight_response = _engine_response_to_dict(
        dispatch_stage("preflight", current, tickets_dir, request_origin)
    )
    if preflight_response.get("state") != "ok":
        return _with_default_recovery_hint(preflight_response)
    current.update(preflight_response.get("data", {}))

    preview = _preview(fields, duplicate)
    prepare_artifact = {
        "state": "ready_to_execute",
        "fingerprint": _prepare_fingerprint(fields),
        "capture_fingerprint": _json_fingerprint(current["capture"]),
        "execute_fingerprint": _execute_fingerprint(current),
        "preview": preview,
        "preview_fingerprint": _json_fingerprint(preview),
    }
    current["capture_prepare"] = prepare_artifact
    current["capture"] = dict(payload["capture"])
    if "edit_history" in payload:
        current["edit_history"] = payload["edit_history"]
    suggested_next = _suggested_next_capture(edit_text)
    if suggested_next:
        current["suggested_next_capture"] = suggested_next

    try:
        _write_payload_atomic(payload_path, current)
    except OSError as exc:
        return _response("escalate", str(exc), error_code="io_error")

    data: dict[str, Any] = {"preview": preview}
    if suggested_next:
        data["suggested_next_capture"] = suggested_next
    return _response(
        "ready_to_execute",
        "Capture preview ready",
        data=data,
    )


def _execute(payload_path: Path) -> dict[str, Any]:
    payload, tickets_dir, request_origin, error = _load_capture_context("execute", payload_path)
    if error is not None:
        return _with_default_recovery_hint(error)
    assert payload is not None and tickets_dir is not None and request_origin is not None

    prepare_artifact = payload.get("capture_prepare")
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
    if not isinstance(fields, dict):
        return attach_recovery_hint(
            _response(
                "preflight_failed",
                "The saved preview state is no longer usable.",
                error_code="stale_plan",
            ),
            "retry_preview",
        )
    preview = prepare_artifact.get("preview")
    if not isinstance(preview, dict):
        return attach_recovery_hint(
            _response(
                "preflight_failed",
                "The saved preview state is no longer usable.",
                error_code="stale_plan",
            ),
            "retry_preview",
        )
    if prepare_artifact.get("fingerprint") != _prepare_fingerprint(fields):
        return attach_recovery_hint(
            _response(
                "preflight_failed",
                "The saved preview is no longer current.",
                error_code="stale_plan",
            ),
            "stale_plan",
        )
    capture = payload.get("capture")
    if not isinstance(capture, dict) or prepare_artifact.get(
        "capture_fingerprint"
    ) != _json_fingerprint(capture):
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
    payload["fields"] = dict(fields)

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
    if response.get("state") == "ok_create":
        try:
            response.setdefault("data", {})["payload_deleted"] = delete_consumed_payload(
                payload_path,
                project_root,
            )
        except (OSError, TicketPayloadPathError) as exc:
            response.setdefault("data", {})["payload_cleanup_error"] = str(exc)
    return _with_default_recovery_hint(response)


def run_capture(
    subcommand: str,
    payload_path: Path,
    *,
    edit_text: str | None = None,
) -> dict[str, Any]:
    if subcommand == "prepare":
        return _prepare(payload_path, edit_text)
    if subcommand == "execute":
        if edit_text is not None:
            return _response(
                "escalate",
                "execute does not accept --edit",
                error_code="intent_mismatch",
            )
        return _execute(payload_path)
    return _response(
        "escalate",
        f"Unknown capture subcommand: {subcommand!r}",
        error_code="intent_mismatch",
    )


def _exit_code(state: str) -> int:
    if state in {"ready_to_execute", "ok_create"}:
        return 0
    if state == "need_fields":
        return 2
    return 1


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print(
            json.dumps(
                {"error": "Usage: ticket_capture.py prepare|execute <payload_file> [--edit TEXT]"}
            )
        )
        return 1

    subcommand = args[0]
    payload_path = Path(args[1])
    edit_text: str | None = None
    if len(args) > 2:
        if subcommand != "prepare" or len(args) != 4 or args[2] != "--edit":
            print(
                json.dumps(
                    {"error": "Usage: ticket_capture.py prepare <payload_file> [--edit TEXT]"}
                )
            )
            return 1
        edit_text = args[3]

    response = run_capture(subcommand, payload_path, edit_text=edit_text)
    print(json.dumps(response))
    return _exit_code(str(response.get("state", "")))


if __name__ == "__main__":
    raise SystemExit(main())

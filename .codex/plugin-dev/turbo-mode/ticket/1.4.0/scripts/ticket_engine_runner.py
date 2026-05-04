"""Shared entrypoint runner for the ticket engine.

Consolidates boundary logic (payload read, origin enforcement, trust triple,
project root, tickets_dir, dispatch, exit codes) that was previously
duplicated between ticket_engine_user.py and ticket_engine_agent.py.

Entrypoints import and call run() with their hardcoded request_origin.
This module is never invoked directly.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

from scripts.ticket_engine_core import (
    AutonomyConfig,
    EngineResponse,
    engine_classify,
    engine_execute,
    engine_plan,
    engine_preflight,
)
from scripts.ticket_paths import discover_project_root, resolve_tickets_dir
from scripts.ticket_stage_models import (
    ClassifyInput,
    ExecuteInput,
    IngestInput,
    PayloadError,
    PlanInput,
    PreflightInput,
)
from scripts.ticket_trust import collect_trust_triple_errors


def run(
    request_origin: str,
    argv: list[str] | None = None,
    *,
    prog: str,
) -> int:
    """Run the ticket engine entrypoint.

    Args:
        request_origin: Authoritative origin ("user" or "agent").
        argv: Command-line arguments [subcommand, payload_file].
              Defaults to sys.argv[1:].
        prog: Script name for usage messages.

    Returns:
        Exit code: 0 (success), 1 (engine error), 2 (need_fields).
    """
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2:
        print(
            json.dumps({"error": f"Usage: {prog} <subcommand> <payload_file>"}),
            file=sys.stderr,
        )
        return 1

    subcommand = args[0]
    payload_path = Path(args[1])

    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(
            json.dumps({"error": f"Cannot read payload: {exc}"}),
            file=sys.stderr,
        )
        return 1

    # Normalize origin in payload. request_origin argument is authoritative.
    payload["request_origin"] = request_origin

    # Check for hook-injected origin mismatch (all stages).
    hook_origin = payload.get("hook_request_origin")
    if hook_origin is not None and hook_origin != request_origin:
        resp = EngineResponse(
            state="escalate",
            message=f"origin_mismatch: entrypoint={request_origin}, hook={hook_origin}",
            error_code="origin_mismatch",
        )
        print(resp.to_json())
        return 1

    # Execute requires the full trust triple.
    if subcommand in ("execute", "ingest"):
        trust_errors = collect_trust_triple_errors(
            payload.get("hook_injected", False),
            hook_origin,
            payload.get("session_id", ""),
        )
        if trust_errors:
            resp = EngineResponse(
                state="policy_blocked",
                message=f"Execute requires verified hook provenance: {', '.join(trust_errors)}",
                error_code="policy_blocked",
            )
            print(resp.to_json())
            return 1

    project_root = discover_project_root(Path.cwd())
    if project_root is None:
        resp = EngineResponse(
            state="policy_blocked",
            message="Cannot determine project root: no .codex/ or .git/ marker found in ancestors of cwd",
            error_code="policy_blocked",
        )
        print(resp.to_json())
        return 1

    tickets_dir_raw = payload.get("tickets_dir", "docs/tickets")
    tickets_dir, path_error = resolve_tickets_dir(
        tickets_dir_raw, project_root=project_root
    )
    if path_error is not None or tickets_dir is None:
        resp = EngineResponse(
            state="policy_blocked",
            message=path_error or "tickets_dir validation failed",
            error_code="policy_blocked",
        )
        print(resp.to_json())
        return 1

    resp = _dispatch(subcommand, payload, tickets_dir, request_origin)
    print(resp.to_json())
    return _exit_code(resp)


def _exit_code(resp: EngineResponse) -> int:
    """Map EngineResponse to exit code. Single-sourced."""
    # Exit codes: 0=success, 1=engine error, 2=validation failure (need_fields).
    if resp.state in (
        "ok",
        "ok_create",
        "ok_update",
        "ok_close",
        "ok_close_archived",
        "ok_reopen",
    ):
        return 0
    if resp.error_code == "need_fields":
        return 2
    return 1


def _dispatch_ingest(
    inp: IngestInput,
    payload: dict[str, Any],
    tickets_dir: Path,
    request_origin: str,
) -> EngineResponse:
    """Orchestrate envelope ingestion: read -> validate -> map -> plan -> preflight -> execute -> move."""
    from scripts.ticket_envelope import map_envelope_to_fields, move_to_processed, read_envelope

    envelope_path = Path(inp.envelope_path)

    # Containment: envelope_path must resolve inside tickets_dir/.envelopes/
    # and must not be a .processed descendant (prevents replay of archived envelopes).
    envelopes_boundary = (tickets_dir / ".envelopes").resolve()
    try:
        resolved_envelope = envelope_path.resolve()
        resolved_envelope.relative_to(envelopes_boundary)
    except (ValueError, OSError):
        return EngineResponse(
            state="policy_blocked",
            message=f"envelope_path escapes containment boundary {str(envelopes_boundary)!r}. Got: {str(inp.envelope_path)!r:.100}",
            error_code="policy_blocked",
        )
    try:
        resolved_envelope.relative_to(envelopes_boundary / ".processed")
        return EngineResponse(
            state="policy_blocked",
            message=f"envelope_path points to processed envelope (replay rejected). Got: {str(inp.envelope_path)!r:.100}",
            error_code="policy_blocked",
        )
    except (ValueError, OSError):
        pass  # Not inside .processed — expected case.

    # Step 1: Read and validate envelope.
    envelope, errors = read_envelope(envelope_path)
    if envelope is None:
        return EngineResponse(
            state="need_fields",
            message=f"Envelope validation failed: {'; '.join(errors)}",
            error_code="need_fields",
            data={"validation_errors": errors},
        )

    # Step 2: Map envelope fields to engine vocabulary.
    fields = map_envelope_to_fields(envelope)

    # Step 3: Plan — computes dedup fingerprint, scans for duplicates.
    plan_resp = engine_plan(
        intent="create",
        fields=fields,
        session_id=inp.session_id,
        request_origin=request_origin,
        tickets_dir=tickets_dir,
        ticket_id=None,
    )
    if plan_resp.state != "ok":
        return plan_resp

    # Extract plan outputs for preflight.
    plan_data = plan_resp.data or {}
    dedup_fp = plan_data.get("dedup_fingerprint")
    duplicate_of = plan_data.get("duplicate_of")

    # Step 4: Preflight — all policy checks.
    preflight_resp = engine_preflight(
        ticket_id=None,
        action="create",
        session_id=inp.session_id,
        request_origin=request_origin,
        classify_confidence=1.0,
        classify_intent="create",
        dedup_fingerprint=dedup_fp,
        target_fingerprint=None,
        fields=fields,
        duplicate_of=duplicate_of,
        dedup_override=False,
        dependency_override=False,
        hook_injected=inp.hook_injected,
        tickets_dir=tickets_dir,
    )
    if preflight_resp.state != "ok":
        return preflight_resp

    # Step 5: Execute — create the ticket.
    exec_resp = engine_execute(
        action="create",
        ticket_id=None,
        fields=fields,
        session_id=inp.session_id,
        request_origin=request_origin,
        dedup_override=False,
        dependency_override=False,
        tickets_dir=tickets_dir,
        target_fingerprint=None,
        hook_injected=inp.hook_injected,
        hook_request_origin=inp.hook_request_origin,
        classify_intent="create",
        classify_confidence=1.0,
        dedup_fingerprint=dedup_fp,
        duplicate_of=duplicate_of,
    )
    if not exec_resp.state.startswith("ok"):
        return exec_resp

    # Step 6: Move envelope to processed.
    try:
        move_to_processed(envelope_path)
    except OSError as exc:
        # Ticket was created but envelope move failed. Not fatal — report in data.
        exec_resp = EngineResponse(
            state=exec_resp.state,
            message=f"{exec_resp.message}; envelope move failed: {exc}",
            ticket_id=exec_resp.ticket_id,
            data={**(exec_resp.data or {}), "envelope_move_error": str(exc)},
        )

    return exec_resp


def _dispatch(
    subcommand: str,
    payload: dict[str, Any],
    tickets_dir: Path,
    request_origin: str,
) -> EngineResponse:
    try:
        if subcommand == "classify":
            inp = ClassifyInput.from_payload(payload)
            return engine_classify(
                action=inp.action,
                args=inp.args,
                session_id=inp.session_id,
                request_origin=request_origin,
            )
        elif subcommand == "plan":
            inp = PlanInput.from_payload(payload)
            return engine_plan(
                intent=inp.intent,
                fields=inp.fields,
                session_id=inp.session_id,
                request_origin=request_origin,
                tickets_dir=tickets_dir,
                ticket_id=inp.ticket_id,
            )
        elif subcommand == "preflight":
            inp = PreflightInput.from_payload(payload)
            return engine_preflight(
                ticket_id=inp.ticket_id,
                action=inp.action,
                session_id=inp.session_id,
                request_origin=request_origin,
                classify_confidence=inp.classify_confidence,
                classify_intent=inp.classify_intent,
                dedup_fingerprint=inp.dedup_fingerprint,
                target_fingerprint=inp.target_fingerprint,
                fields=inp.fields,
                duplicate_of=inp.duplicate_of,
                dedup_override=inp.dedup_override,
                dependency_override=inp.dependency_override,
                hook_injected=inp.hook_injected,
                tickets_dir=tickets_dir,
            )
        elif subcommand == "execute":
            inp = ExecuteInput.from_payload(payload)
            autonomy_config = (
                AutonomyConfig.from_dict(inp.autonomy_config_data)
                if isinstance(inp.autonomy_config_data, dict)
                else None
            )
            return engine_execute(
                action=inp.action,
                ticket_id=inp.ticket_id,
                fields=inp.fields,
                session_id=inp.session_id,
                request_origin=request_origin,
                dedup_override=inp.dedup_override,
                dependency_override=inp.dependency_override,
                tickets_dir=tickets_dir,
                target_fingerprint=inp.target_fingerprint,
                autonomy_config=autonomy_config,
                hook_injected=inp.hook_injected,
                hook_request_origin=inp.hook_request_origin,
                classify_intent=inp.classify_intent,
                classify_confidence=inp.classify_confidence,
                dedup_fingerprint=inp.dedup_fingerprint,
                duplicate_of=inp.duplicate_of,
            )
        elif subcommand == "ingest":
            inp = IngestInput.from_payload(payload)
            return _dispatch_ingest(inp, payload, tickets_dir, request_origin)
        else:
            return EngineResponse(
                state="escalate",
                message=f"Unknown subcommand: {subcommand!r}",
                error_code="intent_mismatch",
            )
    except PayloadError as exc:
        return EngineResponse(
            state=exc.state,
            message=f"{subcommand} payload validation failed: {exc}",
            error_code=exc.code,
        )

"""Shared entrypoint runner for the ticket engine.

Consolidates boundary logic (payload read, origin enforcement, trust triple,
project root, tickets_dir, dispatch, exit codes) that was previously
duplicated between ticket_engine_user.py and ticket_engine_agent.py.

Entrypoints import and call run() with their hardcoded request_origin.
This module is never invoked directly.
The public guarded engine entrypoints are ticket_engine_user.py and ticket_engine_agent.py.
Direct engine stages are low-level compatibility, debug, and agent-internal paths.
They are not normal user-facing mutation interfaces. Agent-origin direct execute
fails closed outside the runtime-first gateway.
Sunset: remove direct stage dispatch once the Tasks 2-9 source/repo cutover is
merged and no source test requires stage-specific compatibility fixtures.
"""

from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from scripts.ticket_engine_core import (
    AutonomyConfig,
    EngineResponse,
    engine_classify,
    engine_execute,
    engine_plan,
    engine_preflight,
    normalize_target_response,
)
from scripts.ticket_engine_gateway import apply_ingest_create
from scripts.ticket_paths import discover_project_root, resolve_tickets_dir
from scripts.ticket_runtime_readiness import (
    RUNTIME_ACTIVATION_BOOTSTRAP_ENV,
    RUNTIME_PROOF_PATH_ENV,
)
from scripts.ticket_stage_models import (
    ClassifyInput,
    ExecuteInput,
    IngestInput,
    PayloadError,
    PlanInput,
    PreflightInput,
)
from scripts.ticket_trust import collect_trust_triple_errors
from scripts.ticket_ux import attach_engine_recovery_hint, recovery_hint_code_for_response


@dataclass(frozen=True)
class RunnerContext:
    """Validated runner inputs shared by engine and workflow entrypoints."""

    payload: dict[str, Any]
    tickets_dir: Path
    request_origin: str


def load_runner_context(
    request_origin: str | None,
    subcommand: str,
    payload_path: Path,
) -> tuple[RunnerContext | None, EngineResponse | None]:
    """Read payload and apply the existing runner boundary checks."""
    try:
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        return None, EngineResponse(
            state="escalate",
            message=f"Cannot read payload: {exc}",
            error_code="parse_error",
        )

    effective_origin = request_origin or payload.get("hook_request_origin") or "user"
    if not isinstance(effective_origin, str) or not effective_origin:
        return None, EngineResponse(
            state="escalate",
            message=f"Invalid request origin. Got: {effective_origin!r:.100}",
            error_code="parse_error",
        )

    payload["request_origin"] = effective_origin
    hook_origin = payload.get("hook_request_origin")
    if hook_origin is not None and hook_origin != effective_origin:
        if subcommand == "execute" and effective_origin == "agent" and hook_origin == "user":
            # Asymmetric direct-execute exception: current hosts may record user
            # command provenance for ticket_engine_agent.py execute. The reverse
            # mismatch still rejects, and engine_execute must still enforce the
            # direct_execute runtime-readiness gate before writing.
            pass
        elif subcommand == "ingest":
            return None, attach_engine_recovery_hint(
                EngineResponse(
                    state="escalate",
                    message="Ticket setup needs attention before this write can continue.",
                    error_code="origin_mismatch",
                ),
                "trust_setup",
            )
        else:
            return None, EngineResponse(
                state="escalate",
                message=f"origin_mismatch: entrypoint={effective_origin}, hook={hook_origin}",
                error_code="origin_mismatch",
            )

    if subcommand in ("execute", "ingest"):
        trust_errors = collect_trust_triple_errors(
            payload.get("hook_injected", False),
            hook_origin,
            payload.get("session_id", ""),
        )
        if trust_errors:
            return None, attach_engine_recovery_hint(
                EngineResponse(
                    state="policy_blocked",
                    message="Ticket setup needs attention before this write can continue.",
                    error_code="policy_blocked",
                ),
                "trust_setup",
            )

    project_root = discover_project_root(Path.cwd())
    if project_root is None:
        return None, EngineResponse(
            state="policy_blocked",
            message=(
                "Cannot determine project root: no .codex/ or .git/ marker found "
                "in ancestors of cwd"
            ),
            error_code="policy_blocked",
        )

    tickets_dir_raw = payload.get("tickets_dir", "docs/tickets")
    tickets_dir, path_error = resolve_tickets_dir(
        tickets_dir_raw,
        project_root=project_root,
    )
    if path_error is not None or tickets_dir is None:
        return None, EngineResponse(
            state="policy_blocked",
            message=path_error or "tickets_dir validation failed",
            error_code="policy_blocked",
        )

    return RunnerContext(
        payload=payload,
        tickets_dir=tickets_dir,
        request_origin=effective_origin,
    ), None


def dispatch_stage(
    subcommand: str,
    payload: dict[str, Any],
    tickets_dir: Path,
    request_origin: str,
    *,
    runtime_proof_path: Path | None = None,
    allow_activation_bootstrap: bool = False,
) -> EngineResponse:
    """Dispatch one engine stage through the existing stage-model boundary.

    Args:
        subcommand: Engine stage name.
        payload: Loaded payload JSON.
        tickets_dir: Project-local ticket storage directory.
        request_origin: Entrypoint origin selected by the script name.
        runtime_proof_path: Optional execute-only proof override used by the
            runtime activation flow.
        allow_activation_bootstrap: Allows execute to verify the temporary
            activation-in-progress proof. Ignored outside execute.
    """
    return _dispatch(
        subcommand,
        payload,
        tickets_dir,
        request_origin,
        runtime_proof_path=runtime_proof_path,
        allow_activation_bootstrap=allow_activation_bootstrap,
    )


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
    try:
        return _run_impl(request_origin, argv, prog=prog)
    except OSError as exc:
        response = EngineResponse(
            state="escalate",
            message=f"ticket engine runner failed: {type(exc).__name__}: {exc}",
            error_code="io_error",
        )
        print(response.to_json())
        return 1
    except Exception as exc:
        response = EngineResponse(
            state="escalate",
            message=f"ticket engine runner failed: {type(exc).__name__}: {exc}",
            error_code="internal_error",
        )
        print(response.to_json())
        return 1


def _run_impl(
    request_origin: str,
    argv: list[str] | None = None,
    *,
    prog: str,
) -> int:
    args = argv if argv is not None else sys.argv[1:]
    if len(args) < 2:
        print(
            json.dumps({"error": f"Usage: {prog} <subcommand> <payload_file>"}),
            file=sys.stderr,
        )
        return 1

    subcommand = args[0]
    payload_path = Path(args[1])

    context, error = load_runner_context(request_origin, subcommand, payload_path)
    if error is not None:
        if subcommand == "ingest":
            error = _sanitize_user_facing_ingest_response(error)
            print(error.to_json())
            return _exit_code(error)
        if error.error_code == "parse_error" and error.message.startswith("Cannot read payload:"):
            print(json.dumps({"error": error.message}), file=sys.stderr)
            return 1
        print(error.to_json())
        return _exit_code(error)

    assert context is not None
    runtime_proof_path = None
    allow_activation_bootstrap = False
    if subcommand == "execute":
        runtime_proof_raw = os.environ.get(RUNTIME_PROOF_PATH_ENV)
        if runtime_proof_raw:
            runtime_proof_path = Path(runtime_proof_raw)
            allow_activation_bootstrap = os.environ.get(RUNTIME_ACTIVATION_BOOTSTRAP_ENV) == "1"
    resp = dispatch_stage(
        subcommand,
        context.payload,
        context.tickets_dir,
        context.request_origin,
        runtime_proof_path=runtime_proof_path,
        allow_activation_bootstrap=allow_activation_bootstrap,
    )
    if subcommand == "ingest":
        resp = _sanitize_user_facing_ingest_response(resp)
    print(resp.to_json())
    return _exit_code(resp)


def _exit_code(resp: EngineResponse) -> int:
    """Map EngineResponse to exit code. Single-sourced."""
    # Exit codes: 0=success, 1=engine error, 2=validation failure (need_fields).
    if resp.state == "ok":
        return 0
    if resp.error_code == "need_fields":
        return 2
    return 1


def _ingest_need_fields_recovery_code(resp: EngineResponse) -> str:
    data = resp.data if isinstance(resp.data, dict) else {}
    validation_errors = data.get("validation_errors")
    if isinstance(validation_errors, list) and validation_errors:
        return "preflight_failed"
    return "preflight_failed"


def _sanitize_user_facing_ingest_response(resp: EngineResponse) -> EngineResponse:
    hint_code = (
        _ingest_need_fields_recovery_code(resp)
        if resp.error_code == "need_fields"
        else recovery_hint_code_for_response(resp.to_dict())
    )
    if hint_code is None:
        return normalize_target_response(resp)
    if hint_code == "trust_setup":
        resp.message = "Ticket setup needs attention before this write can continue."
    elif hint_code == "policy_blocked":
        resp.message = "Ticket ingest is blocked by Ticket policy."
    elif hint_code == "preflight_failed":
        resp.message = "Ticket checks did not pass."
    elif hint_code == "stale_plan":
        resp.message = "The ticket changed since it was read."
    return normalize_target_response(attach_engine_recovery_hint(resp, hint_code))


def _dispatch_ingest(
    inp: IngestInput,
    payload: dict[str, Any],
    tickets_dir: Path,
    request_origin: str,
) -> EngineResponse:
    """Orchestrate envelope ingestion through the create pipeline."""
    from scripts.ticket_envelope import (
        envelope_id_from_path,
        map_envelope_to_fields,
        move_to_processed,
        processed_path_for_envelope,
        read_envelope,
    )

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
            message="Ticket ingest is blocked by Ticket policy.",
            error_code="policy_blocked",
        )
    try:
        resolved_envelope.relative_to(envelopes_boundary / ".processed")
        return EngineResponse(
            state="policy_blocked",
            message="Ticket ingest is blocked by Ticket policy.",
            error_code="policy_blocked",
        )
    except (ValueError, OSError):
        pass  # Not inside .processed — expected case.

    if resolved_envelope.parent != envelopes_boundary:
        return EngineResponse(
            state="policy_blocked",
            message="Ticket ingest is blocked by Ticket policy.",
            error_code="policy_blocked",
        )

    envelope_id = envelope_id_from_path(envelope_path)
    processed_path = processed_path_for_envelope(envelope_path)
    if processed_path.exists():
        return EngineResponse(
            state="ok",
            message="That Ticket ingest request was already processed; no ticket was created.",
            data={
                "ingest_outcome": "duplicate_replay",
                "envelope_id": envelope_id,
                "processed_path": str(processed_path),
                "incoming_envelope_path": str(envelope_path),
                "ticket_created": False,
            },
        )

    # Step 1: Read and validate envelope.
    envelope, errors = read_envelope(envelope_path)
    if envelope is None:
        return EngineResponse(
            state="need_fields",
            message=f"Envelope validation failed: {'; '.join(errors)}",
            error_code="need_fields",
            data={"validation_errors": errors},
        )

    # Step 2: Map envelope fields to target create fields.
    fields = map_envelope_to_fields(envelope)

    # Step 3: Apply the target create path through the gateway-owned helper.
    exec_resp = apply_ingest_create(
        fields=fields,
        session_id=inp.session_id,
        request_origin=request_origin,
        tickets_dir=tickets_dir,
    )
    if exec_resp.state != "ok":
        data = dict(exec_resp.data or {})
        data.update(
            {
                "ingest_outcome": "duplicate_candidate"
                if exec_resp.error_code == "duplicate_candidate"
                else "blocked",
                "envelope_id": envelope_id,
                "incoming_envelope_path": str(envelope_path),
                "ticket_created": False,
            }
        )
        return EngineResponse(
            state=exec_resp.state,
            message=exec_resp.message,
            error_code=exec_resp.error_code,
            ticket_id=exec_resp.ticket_id,
            data=data,
        )

    # Step 4: Move envelope to processed.
    try:
        move_to_processed(envelope_path)
    except FileExistsError as exc:
        # Ticket was created but another cleanup path already recorded the envelope.
        data = dict(exec_resp.data or {})
        data.update(
            {
                "envelope_move_error": str(exc),
                "ingest_outcome": "created_envelope_move_failed",
                "envelope_id": envelope_id,
                "processed_path": str(processed_path),
                "incoming_envelope_path": str(envelope_path),
                "ticket_created": True,
            }
        )
        return EngineResponse(
            state=exec_resp.state,
            message="Ticket was created, but Ticket could not finish ingest cleanup.",
            ticket_id=exec_resp.ticket_id,
            data=data,
        )
    except OSError as exc:
        data = dict(exec_resp.data or {})
        data.update(
            {
                "envelope_move_error": str(exc),
                "ingest_outcome": "created_envelope_move_failed",
                "envelope_id": envelope_id,
                "processed_path": str(processed_path),
                "incoming_envelope_path": str(envelope_path),
                "ticket_created": True,
            }
        )
        return EngineResponse(
            state="escalate",
            message=(
                "Ticket was created, but Ticket could not finish ingest cleanup; "
                "manual cleanup is required before replay."
            ),
            error_code="io_error",
            ticket_id=exec_resp.ticket_id,
            data=data,
        )

    data = dict(exec_resp.data or {})
    data.update(
        {
            "ingest_outcome": "created",
            "envelope_id": envelope_id,
            "processed_path": str(processed_path_for_envelope(envelope_path)),
            "incoming_envelope_path": str(envelope_path),
            "ticket_created": True,
        }
    )
    return EngineResponse(
        state=exec_resp.state,
        message="Ticket was created.",
        ticket_id=exec_resp.ticket_id,
        data=data,
    )


def _dispatch(
    subcommand: str,
    payload: dict[str, Any],
    tickets_dir: Path,
    request_origin: str,
    *,
    runtime_proof_path: Path | None = None,
    allow_activation_bootstrap: bool = False,
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
            runtime_execute_surface = "direct_execute" if request_origin == "agent" else None
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
                runtime_execute_surface=runtime_execute_surface,
                runtime_proof_path=runtime_proof_path,
                allow_activation_bootstrap=allow_activation_bootstrap,
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
        if subcommand == "ingest":
            return EngineResponse(
                state=exc.state,
                message=(
                    "Ticket checks did not pass."
                    if exc.code in {"need_fields", "parse_error"}
                    else "Ticket ingest is blocked by Ticket policy."
                ),
                error_code=exc.code,
            )
        return EngineResponse(
            state=exc.state,
            message=f"{subcommand} payload validation failed: {exc}",
            error_code=exc.code,
        )

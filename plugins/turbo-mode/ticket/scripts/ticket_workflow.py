#!/usr/bin/env python3
"""Deprecated saved-preview workflow shim.

The old generic Ticket workflow path is unavailable after the ADR 0006 source
cutover. Keep this module only to make stale invocations fail closed.

Sunset: delete this shim once no source test or installed-runtime diagnostic
needs to prove the old workflow command fails closed.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

_DEPRECATED_ERROR_CODE = "deprecated_workflow"


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


def _deprecated_response(surface: str) -> dict[str, Any]:
    return _response(
        "unavailable",
        f"Deprecated Ticket workflow is unavailable: {surface}.",
        error_code=_DEPRECATED_ERROR_CODE,
        data={"surface": surface},
    )


def run_workflow(
    subcommand: str,
    payload_path: Path,
    *extra_args: object,
) -> dict[str, Any]:
    """Return a structured failure for removed workflow commands."""
    del payload_path, extra_args
    if subcommand in {"prepare", "execute", "recover"}:
        return _deprecated_response(f"workflow/{subcommand}")
    return _response(
        "escalate",
        f"Unknown workflow subcommand: {subcommand!r}",
        error_code="intent_mismatch",
    )


def run_recovery(
    payload_path: Path,
    action: str,
    *args: object,
) -> dict[str, Any]:
    """Return a structured failure for removed workflow recovery."""
    return run_workflow("recover", payload_path, action, *args)


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print(json.dumps({"error": "Usage: ticket_workflow.py <subcommand> <payload_file>"}))
        return 1
    response = run_workflow(args[0], Path(args[1]), *args[2:])
    print(json.dumps(response))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

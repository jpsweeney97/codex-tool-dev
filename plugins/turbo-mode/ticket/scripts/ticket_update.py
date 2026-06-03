#!/usr/bin/env python3
"""Deprecated focused-update workflow shim.

The saved-preview update workflow is unavailable after the ADR 0006 source
cutover. Existing tickets are updated through the target engine/gateway paths.

Sunset: delete this shim once no source test or installed-runtime diagnostic
needs to prove the old update command fails closed.
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
        f"Deprecated Ticket update workflow is unavailable: {surface}.",
        error_code=_DEPRECATED_ERROR_CODE,
        data={"surface": surface},
    )


def run_update(subcommand: str, payload_path: Path) -> dict[str, Any]:
    """Return a structured failure for the removed update workflow."""
    del payload_path
    if subcommand in {"prepare", "execute"}:
        return _deprecated_response(f"update/{subcommand}")
    return _response(
        "escalate",
        f"Unknown update subcommand: {subcommand!r}",
        error_code="intent_mismatch",
    )


def autonomy_candidate_from_update_payload(payload_path: Path) -> dict[str, Any]:
    """Expose stale update adapter calls as discussion-only candidates."""
    return _response(
        "discussion_required",
        "Deprecated update adapter cannot mutate tickets automatically.",
        data={
            "possible_candidates": [
                {
                    "ticket_id": None,
                    "action": "update",
                    "reason": (
                        "Deprecated update payload requires manual review: "
                        f"{payload_path.name}"
                    ),
                }
            ]
        },
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) != 2:
        print(json.dumps({"error": "Usage: ticket_update.py <subcommand> <payload_file>"}))
        return 1
    response = run_update(args[0], Path(args[1]))
    print(json.dumps(response, indent=2))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

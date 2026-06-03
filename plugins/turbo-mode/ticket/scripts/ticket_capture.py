#!/usr/bin/env python3
"""Deprecated capture workflow shim.

The old saved-preview capture mutation path is unavailable after the ADR 0006
source cutover. Keep this module only so stale external invocations fail with a
structured response instead of importing removed machinery.

Sunset: delete this shim once no source test or installed-runtime diagnostic
needs to prove the old capture command fails closed.
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
) -> dict[str, Any]:
    response: dict[str, Any] = {"state": state, "message": message, "data": data or {}}
    if error_code is not None:
        response["error_code"] = error_code
    return response


def _deprecated_response(surface: str) -> dict[str, Any]:
    return _response(
        "unavailable",
        f"Deprecated Ticket capture workflow is unavailable: {surface}.",
        error_code=_DEPRECATED_ERROR_CODE,
        data={"surface": surface},
    )


def run_capture(
    subcommand: str,
    payload_path: Path,
    *,
    edit_text: str | None = None,
) -> dict[str, Any]:
    """Return a structured failure for the removed capture workflow."""
    del payload_path, edit_text
    if subcommand in {"prepare", "execute"}:
        return _deprecated_response(f"capture/{subcommand}")
    return _response(
        "escalate",
        f"Unknown capture subcommand: {subcommand!r}",
        error_code="intent_mismatch",
    )


def autonomy_candidate_from_capture_payload(
    payload_path: Path,
    *,
    edit_text: str | None = None,
) -> dict[str, Any]:
    """Expose stale capture adapter calls as discussion-only candidates."""
    del edit_text
    return _response(
        "discussion_required",
        "Deprecated capture adapter cannot create tickets automatically.",
        data={
            "possible_candidates": [
                {
                    "ticket_id": None,
                    "action": "create",
                    "reason": (
                        "Deprecated capture payload requires manual review: "
                        f"{payload_path.name}"
                    ),
                }
            ]
        },
    )


def main(argv: list[str] | None = None) -> int:
    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) < 2:
        print(json.dumps({"error": "Usage: ticket_capture.py <subcommand> <payload_file>"}))
        return 1
    response = run_capture(args[0], Path(args[1]))
    print(json.dumps(response))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

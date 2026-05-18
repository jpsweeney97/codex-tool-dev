"""Shared helpers for execute-stage trust validation."""
from __future__ import annotations


def collect_trust_triple_errors(
    hook_injected: bool,
    hook_request_origin: str | None,
    session_id: str,
) -> list[str]:
    """Return missing execute trust-triple errors in stable order."""
    errors: list[str] = []
    if not hook_injected:
        errors.append("hook_injected=False")
    if hook_request_origin is None:
        errors.append("hook_request_origin missing")
    if not session_id:
        errors.append("session_id empty")
    return errors

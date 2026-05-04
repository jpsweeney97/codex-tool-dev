#!/usr/bin/env python3
"""PreToolUse hook: validates ticket script invocations and injects trust fields.

Decision branches:
- Branch 1: exact engine allowlist -> validate subcommand/payload + inject trust fields.
- Branch 2: exact read-only allowlist (`ticket_read.py`, `ticket_triage.py`) -> allow.
- Branch 2b: exact audit allowlist (`ticket_audit.py`) -> allow for users, deny for agents.
- Branch 3: any other Python invocation targeting `ticket_*.py` -> deny.
- Branch 4: non-ticket Bash commands -> pass through silently (empty JSON).

Payload injection (atomic):
- Injects session_id, hook_injected, hook_request_origin into the payload file.
- Resolves payload path relative to the event cwd and denies paths outside workspace root.
- Uses temp file + fsync + os.replace for atomic writes.
- Denies on any injection failure (unreadable file, invalid JSON, write error).

Exit code always 0 (fail-open on crash — accepted v1.0 limitation).
"""
from __future__ import annotations

import json
import os
import re
import shlex
import sys
import tempfile
from pathlib import Path

VALID_SUBCOMMANDS = frozenset({"classify", "plan", "preflight", "execute", "ingest"})

# Shell metacharacters that indicate command chaining or redirection.
SHELL_METACHAR_RE = re.compile(r"[|;&`$><\n\r]")


def _plugin_root() -> str:
    """Return plugin root directory, with an optional test/development override."""
    return os.environ.get("CODEX_PLUGIN_ROOT", str(Path(__file__).parent.parent))


def _build_allowlist_pattern(plugin_root: str) -> re.Pattern[str]:
    """Build the allowlist regex anchored to the plugin root."""
    escaped = re.escape(plugin_root)
    return re.compile(
        rf"^python3\s+{escaped}/scripts/ticket_engine_(user|agent)\.py\s+(\w+)\s+(.+)$"
    )


def _build_readonly_pattern(plugin_root: str) -> re.Pattern[str]:
    """Build pattern for read-only ticket scripts (no payload injection)."""
    escaped = re.escape(plugin_root)
    return re.compile(
        rf"^python3\s+{escaped}/scripts/ticket_(read|triage)\.py\s+(\w+)\s+(.+)$"
    )


def _build_audit_pattern(plugin_root: str) -> re.Pattern[str]:
    """Build pattern for ticket_audit.py (user-only, no payload injection)."""
    escaped = re.escape(plugin_root)
    return re.compile(
        rf"^python3\s+{escaped}/scripts/ticket_audit\.py\s+(\w+)\s+(.+)$"
    )


# Known ticket script basenames for candidate detection.
_TICKET_SCRIPT_BASENAMES = frozenset({
    "ticket_engine_user.py",
    "ticket_engine_agent.py",
    "ticket_read.py",
    "ticket_triage.py",
    "ticket_audit.py",
})

# Broad pattern for any ticket_*.py script — catches unknown/rogue scripts
# so they route to branch 3 (deny) rather than bypassing the hook entirely.
_TICKET_SCRIPT_RE = re.compile(r"^ticket_\w+\.py$")

# Environment variable assignment tokens.
_ENV_ASSIGNMENT_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=.*$")

# Python-like launcher basenames.
_PYTHON_LAUNCHER_RE = re.compile(r"^python[\d.]*$")

# Python options that consume the following token as an argument.
_PYTHON_OPTIONS_WITH_VALUE = frozenset({"-c", "-m", "-W", "-X"})

# env options that consume the following token as an argument.
_ENV_OPTIONS_WITH_VALUE = frozenset({"-u", "--unset"})

# env split-string options that inject additional argv tokens.
_ENV_SPLIT_STRING_OPTIONS = frozenset({"-S", "--split-string"})


def _expand_env_split_string(tokens: list[str]) -> list[str]:
    """Expand `env -S/--split-string` arguments into normal argv tokens."""
    if not tokens:
        return tokens
    if tokens[0] != "env" and not (tokens[0].endswith("/env") and "/" in tokens[0]):
        return tokens

    expanded = [tokens[0]]
    i = 1
    while i < len(tokens):
        token = tokens[i]
        split_value: str | None = None
        if token in _ENV_SPLIT_STRING_OPTIONS:
            if i + 1 >= len(tokens):
                expanded.append(token)
                break
            split_value = tokens[i + 1]
            i += 2
        elif token.startswith("--split-string="):
            split_value = token.split("=", 1)[1]
            i += 1
        else:
            expanded.append(token)
            i += 1
            continue

        try:
            expanded.extend(shlex.split(split_value))
        except ValueError:
            expanded.append(split_value)

    return expanded


def _is_ticket_candidate(command: str) -> bool:
    """Detect if command is a Python invocation targeting a ticket script.

    Uses shlex.split() for token-based parsing. After locating a Python-like
    launcher, skips common env prefixes and Python flags to find the script
    operand, then checks its basename against known and broad ticket patterns.

    Supports:
    - Direct: python3 script.py
    - Versioned: python3.12 script.py
    - Absolute: /usr/bin/python3 script.py
    - env: env python3 script.py
    - env with vars: env KEY=VAL python3 script.py
    - Leading env assignments: KEY=VAL python3 script.py
    - Python flags before script: python3 -u -O script.py

    Returns True if detected as a ticket script candidate (routes to exact
    allowlist validation in branches 1-3). False means pass-through (branch 4).
    """
    try:
        tokens = shlex.split(command)
    except ValueError:
        # shlex.split() failed (unclosed quote, etc.).
        # If the raw command mentions a known ticket script basename (exact or
        # broad pattern), deny as malformed; otherwise pass through.
        if any(basename in command for basename in _TICKET_SCRIPT_BASENAMES):
            return True
        # Check broad pattern: extract potential basenames and test against regex.
        for word in command.split():
            candidate = word.rsplit("/", 1)[-1] if "/" in word else word
            if _TICKET_SCRIPT_RE.match(candidate):
                return True
        return False

    if not tokens:
        return False

    tokens = _expand_env_split_string(tokens)

    # Find the Python launcher token, skipping:
    # - "env" or absolute-path env (e.g., /usr/bin/env)
    # - Environment variable assignments (KEY=VALUE)
    i = 0

    # Skip env launcher if present.
    if tokens[i] == "env" or (tokens[i].endswith("/env") and "/" in tokens[i]):
        i += 1
        while i < len(tokens):
            token = tokens[i]
            if token in _ENV_OPTIONS_WITH_VALUE:
                i += 2
                continue
            if token.startswith("--unset="):
                i += 1
                continue
            if token.startswith("-"):
                i += 1
                continue
            break

    # Skip environment variable assignments (KEY=VALUE before Python token).
    while i < len(tokens) and _ENV_ASSIGNMENT_RE.match(tokens[i]):
        i += 1

    if i >= len(tokens):
        return False

    # Check if current token is a Python launcher.
    launcher = tokens[i]
    launcher_basename = launcher.rsplit("/", 1)[-1] if "/" in launcher else launcher
    if not _PYTHON_LAUNCHER_RE.match(launcher_basename):
        return False

    # Skip Python flags until the first non-option token, accounting for options
    # that consume a following argument (for example "-m pdb" or "-X dev").
    script_idx = i + 1
    while script_idx < len(tokens):
        token = tokens[script_idx]
        if token in _PYTHON_OPTIONS_WITH_VALUE:
            script_idx += 2
            continue
        if token.startswith("-"):
            script_idx += 1
            continue
        break

    if script_idx >= len(tokens):
        return False

    script_path = tokens[script_idx]
    script_basename = script_path.rsplit("/", 1)[-1] if "/" in script_path else script_path
    return script_basename in _TICKET_SCRIPT_BASENAMES or bool(_TICKET_SCRIPT_RE.match(script_basename))


def _make_allow(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "allow",
            "permissionDecisionReason": reason,
        }
    }


def _make_deny(reason: str) -> dict:
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": reason,
        }
    }


def _inject_payload(
    payload_path: str,
    session_id: str,
    request_origin: str,
) -> str | None:
    """Inject trust fields into the payload file atomically.

    Returns None on success, or an error message string on failure.
    """
    path = Path(payload_path)

    # Read existing payload.
    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return f"Payload unreadable: {exc}"

    # Parse JSON.
    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, ValueError) as exc:
        return f"Payload invalid JSON: {exc}"

    if not isinstance(payload, dict):
        return f"Payload is not a JSON object, got {type(payload).__name__}"

    # Inject trust fields.
    payload["session_id"] = session_id
    payload["hook_injected"] = True
    payload["hook_request_origin"] = request_origin

    # Atomic write: temp file in same directory -> fsync -> os.replace.
    parent = path.parent
    tmp_path: str | None = None
    try:
        fd, tmp_path = tempfile.mkstemp(dir=str(parent), suffix=".tmp")
        try:
            data = json.dumps(payload, indent=2).encode("utf-8")
            os.write(fd, data)
            os.fsync(fd)
        finally:
            os.close(fd)
        os.replace(tmp_path, str(path))
    except OSError as exc:
        # Clean up temp file on failure.
        if tmp_path is not None:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
        return f"Payload write failed: {exc}"

    return None


def _resolve_payload_path(payload_path: str, workspace_root: str) -> tuple[Path | None, str | None]:
    """Resolve payload path and enforce workspace-root containment."""
    if not isinstance(workspace_root, str) or not workspace_root:
        return None, f"Invalid workspace root. Got: {workspace_root!r:.100}"
    try:
        root = Path(workspace_root).resolve()
        candidate = Path(payload_path)
        resolved = candidate.resolve() if candidate.is_absolute() else (root / candidate).resolve()
    except OSError as exc:
        return None, f"Payload path resolution failed: {exc}. Got: {payload_path!r:.100}"
    try:
        resolved.relative_to(root)
    except ValueError:
        return (
            None,
            f"Payload path outside workspace root {str(root)!r}. Got: {payload_path!r:.100}",
        )
    return resolved, None


def _resolve_origin(
    event: dict, *, is_ticket_candidate: bool
) -> tuple[str | None, str | None]:
    """Determine request origin from agent_id field.

    Returns (origin, error):
    - ("user", None): agent_id key missing -> user origin
    - ("agent", None): agent_id is a non-empty string -> agent origin
    - (None, reason): present-but-empty or non-string agent_id on a ticket
      candidate command -> deny with reason
    """
    if "agent_id" not in event:
        return "user", None

    agent_id = event["agent_id"]
    if isinstance(agent_id, str) and agent_id:
        return "agent", None

    if is_ticket_candidate:
        return None, (
            f"Malformed agent_id: expected non-empty string or absent, "
            f"got {type(agent_id).__name__}={agent_id!r:.50}"
        )

    # Non-ticket commands with weird agent_id: pass through (not our concern).
    return "user", None


def main() -> None:
    try:
        event = json.load(sys.stdin)
    except (json.JSONDecodeError, ValueError):
        # Malformed input — fail open.
        print("{}")
        return

    # Non-Bash tools pass through.
    tool_name = event.get("tool_name", "")
    if tool_name != "Bash":
        print("{}")
        return

    tool_input = event.get("tool_input", {})
    command = tool_input.get("command", "")

    # Strip a trailing `2>&1` diagnostic suffix. Detection trims leading
    # whitespace; exact matching does not, so non-canonical forms still deny.
    command_clean = re.sub(r"\s+2>&1\s*$", "", command)
    command_for_detection = command_clean.lstrip()

    # Branch 4: Non-ticket-script invocations pass through (cat, rg, wc, etc.).
    plugin_root = _plugin_root()
    if not _is_ticket_candidate(command_for_detection):
        print("{}")
        return

    # --- From here, command is a candidate ticket script invocation. ---

    # Block shell metacharacters.
    if SHELL_METACHAR_RE.search(command_clean):
        print(json.dumps(_make_deny(
            f"Shell metacharacters detected in ticket engine command. Got: {command!r:.100}"
        )))
        return

    # Branch 1: Engine exact allowlist → validate subcommand/payload + inject.
    engine_pattern = _build_allowlist_pattern(plugin_root)
    engine_match = engine_pattern.match(command_clean)

    if engine_match:
        entrypoint_type = engine_match.group(1)  # "user" or "agent"
        subcommand = engine_match.group(2)
        payload_path = engine_match.group(3)

        # Validate subcommand.
        if subcommand not in VALID_SUBCOMMANDS:
            print(json.dumps(_make_deny(
                f"Unknown subcommand '{subcommand}'. Valid: {sorted(VALID_SUBCOMMANDS)}"
            )))
            return

        # Check for extra arguments (payload_path should not contain whitespace).
        if re.search(r"\s", payload_path):
            print(json.dumps(_make_deny(
                f"Extra arguments after payload path. Got: {command!r:.100}"
            )))
            return

        workspace_root = event.get("cwd", "")
        resolved_path, path_error = _resolve_payload_path(payload_path, workspace_root)
        if path_error is not None or resolved_path is None:
            print(json.dumps(_make_deny(
                f"Payload path validation failed: {path_error or 'unknown error'}"
            )))
            return

        # Inject trust fields into payload.
        session_id = event.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            print(json.dumps(_make_deny(
                f"Malformed session_id: expected non-empty string, got {type(session_id).__name__}={session_id!r:.50}"
            )))
            return
        effective_origin, origin_error = _resolve_origin(event, is_ticket_candidate=True)
        if origin_error is not None:
            print(json.dumps(_make_deny(origin_error)))
            return
        if effective_origin is None:
            print(json.dumps(_make_deny(
                "Origin resolution failed: internal invariant violation"
            )))
            return
        error = _inject_payload(str(resolved_path), session_id, effective_origin)
        if error is not None:
            print(json.dumps(_make_deny(f"Payload injection failed: {error}")))
            return

        print(json.dumps(_make_allow(
            f"Ticket engine {entrypoint_type}/{subcommand} validated and payload injected"
        )))
        return

    # Branch 2: Read-only scripts (ticket_read.py, ticket_triage.py) → allow, no injection.
    readonly_pattern = _build_readonly_pattern(plugin_root)
    readonly_match = readonly_pattern.match(command_clean)
    if readonly_match:
        script_name = readonly_match.group(1)  # "read" or "triage"
        subcommand = readonly_match.group(2)
        print(json.dumps(_make_allow(
            f"Ticket {script_name}/{subcommand} validated (read-only)"
        )))
        return

    # Branch 2b: Audit script (ticket_audit.py) → allow for users, deny for agents.
    audit_pattern = _build_audit_pattern(plugin_root)
    audit_match = audit_pattern.match(command_clean)
    if audit_match:
        origin, origin_error = _resolve_origin(event, is_ticket_candidate=True)
        if origin_error is not None:
            print(json.dumps(_make_deny(origin_error)))
            return
        if origin == "agent":
            print(json.dumps(_make_deny(
                "Ticket audit is user-only — agents cannot invoke audit repair"
            )))
            return
        subcommand = audit_match.group(1)
        print(json.dumps(_make_allow(
            f"Ticket audit/{subcommand} validated (user-only)"
        )))
        return

    # Branch 3: Unrecognized ticket script invocation → deny.
    print(json.dumps(_make_deny(
        f"Command invokes unrecognized ticket script. Got: {command!r:.100}"
    )))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        # Fail open on unhandled exceptions — exit 0 with empty JSON.
        print(
            f"ticket_engine_guard failed open: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print("{}")
        sys.exit(0)

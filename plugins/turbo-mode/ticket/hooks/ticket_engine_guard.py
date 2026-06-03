#!/usr/bin/env python3
"""PreToolUse hook: validates ticket script invocations and injects trust fields.

Decision paths:
- Engine allowlist: validate subcommand/payload and inject trust fields.
- Workflow/capture/update commands: deny as deprecated and unavailable after the
  ADR 0006 source cutover.
- Read-only allowlist: allow safe reads; `ticket_triage.py doctor` validates roots.
- Maintenance allowlist: allow users, deny agents.
- Unknown ticket script invocations: deny.
- Non-ticket Bash commands: pass through silently.

Payload injection (atomic):
- Injects session_id, hook_injected, hook_request_origin into the payload file.
- Requires an absolute payload path and denies paths outside workspace root.
- Uses temp file + fsync + os.replace for atomic writes.
- Denies on any injection failure (unreadable file, invalid JSON, write error).

Exit code always 0; ticket candidates and internal failures fail closed.
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
VALID_ACTIVATION_SMOKE_SUBCOMMANDS = frozenset({"execute"})

# Shell metacharacters that indicate command chaining or redirection.
SHELL_METACHAR_RE = re.compile(r"[|;&`$><\n\r]")


def _plugin_root() -> str:
    """Return plugin root directory, with an optional test/development override."""
    configured_root = os.environ.get("CODEX_PLUGIN_ROOT", str(Path(__file__).parent.parent))
    return str(Path(configured_root).resolve(strict=False))


# Known ticket script basenames for candidate detection.
_TICKET_SCRIPT_BASENAMES = frozenset(
    {
        "ticket_engine_user.py",
        "ticket_engine_agent.py",
        "ticket_engine_activation_smoke.py",
        "ticket_read.py",
        "ticket_triage.py",
        "ticket_audit.py",
        "ticket_workflow.py",
        "ticket_capture.py",
        "ticket_update.py",
        "ticket_review.py",
        "ticket_doctor.py",
    }
)

# Broad pattern for any ticket_*.py script: catches unknown/rogue scripts so
# they route to the deny path rather than bypassing the hook entirely.
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


def _canonical_launcher_script_index(tokens: list[str]) -> int | None:
    """Return the script token index for exact canonical launcher forms."""
    if not tokens:
        return None
    if tokens[0] == "python3":
        script_idx = 1
    elif len(tokens) >= 3 and tokens[:3] == ["uv", "run", "python"]:
        script_idx = 3
    else:
        return None

    if script_idx < len(tokens) and tokens[script_idx] == "-B":
        script_idx += 1
    if script_idx >= len(tokens):
        return None
    return script_idx


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

    Returns True if detected as a ticket script candidate for exact allowlist
    validation. False means pass-through.
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
    if launcher == "uv":
        if tokens[i : i + 3] != ["uv", "run", "python"]:
            return False
        script_idx = i + 3
    else:
        if not _PYTHON_LAUNCHER_RE.match(launcher_basename):
            return False
        script_idx = i + 1

    # Skip Python flags until the first non-option token, accounting for options
    # that consume a following argument (for example "-m pdb" or "-X dev").
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
    return script_basename in _TICKET_SCRIPT_BASENAMES or bool(
        _TICKET_SCRIPT_RE.match(script_basename)
    )


def _make_allow(reason: str) -> dict:
    return {"entries": [{"kind": "feedback", "text": reason}]}


def _make_deny(reason: str) -> dict:
    return {"entries": [{"kind": "stop", "text": reason}]}


def _malformed_session_id_reason(session_id: object) -> str:
    return (
        "Malformed session_id: expected non-empty string, got "
        f"{type(session_id).__name__}={session_id!r:.50}"
    )


def _parse_workflow_invocation(
    command_clean: str, plugin_root: str
) -> tuple[str, str, list[str]] | None:
    """Parse only canonical ticket_workflow.py invocations."""
    try:
        tokens = shlex.split(command_clean)
    except ValueError:
        return None
    if len(tokens) < 3:
        return None
    script_idx = _canonical_launcher_script_index(tokens)
    if script_idx is None:
        return None

    expected_script = str(Path(plugin_root) / "scripts" / "ticket_workflow.py")
    if script_idx >= len(tokens) or tokens[script_idx] != expected_script:
        return None
    if len(tokens) < script_idx + 3:
        return None

    subcommand = tokens[script_idx + 1]
    payload_path = tokens[script_idx + 2]
    if any(char.isspace() for char in payload_path):
        return None
    extra_args = tokens[script_idx + 3 :]
    return subcommand, payload_path, extra_args


def _parse_capture_invocation(
    command_clean: str, plugin_root: str
) -> tuple[str, str, list[str]] | None:
    """Parse only canonical ticket_capture.py invocations."""
    try:
        tokens = shlex.split(command_clean)
    except ValueError:
        return None
    if len(tokens) < 3:
        return None
    script_idx = _canonical_launcher_script_index(tokens)
    if script_idx is None:
        return None

    expected_script = str(Path(plugin_root) / "scripts" / "ticket_capture.py")
    if script_idx >= len(tokens) or tokens[script_idx] != expected_script:
        return None
    if len(tokens) < script_idx + 3:
        return None

    subcommand = tokens[script_idx + 1]
    payload_path = tokens[script_idx + 2]
    if any(char.isspace() for char in payload_path):
        return None
    extra_args = tokens[script_idx + 3 :]
    return subcommand, payload_path, extra_args


def _parse_update_invocation(
    command_clean: str, plugin_root: str
) -> tuple[str, str, list[str]] | None:
    """Parse only canonical ticket_update.py invocations."""
    try:
        tokens = shlex.split(command_clean)
    except ValueError:
        return None
    if len(tokens) < 3:
        return None
    script_idx = _canonical_launcher_script_index(tokens)
    if script_idx is None:
        return None

    expected_script = str(Path(plugin_root) / "scripts" / "ticket_update.py")
    if script_idx >= len(tokens) or tokens[script_idx] != expected_script:
        return None
    if len(tokens) < script_idx + 3:
        return None

    subcommand = tokens[script_idx + 1]
    payload_path = tokens[script_idx + 2]
    if any(char.isspace() for char in payload_path):
        return None
    extra_args = tokens[script_idx + 3 :]
    return subcommand, payload_path, extra_args


def _parse_engine_invocation(
    command_clean: str,
    plugin_root: str,
) -> tuple[str, str, str, list[str]] | None:
    """Parse only canonical engine entrypoint invocations."""
    try:
        tokens = shlex.split(command_clean)
    except ValueError:
        return None
    script_idx = _canonical_launcher_script_index(tokens)
    if script_idx is None or len(tokens) < script_idx + 3:
        return None
    script_path = tokens[script_idx]
    script_name = Path(script_path).name
    if script_name not in {
        "ticket_engine_user.py",
        "ticket_engine_agent.py",
        "ticket_engine_activation_smoke.py",
    }:
        return None
    expected_script = str(Path(plugin_root) / "scripts" / script_name)
    if script_path != expected_script:
        return None
    entrypoint_type = script_name.removeprefix("ticket_engine_").removesuffix(".py")
    return entrypoint_type, tokens[script_idx + 1], tokens[script_idx + 2], tokens[script_idx + 3 :]


def _parse_readonly_invocation(
    command_clean: str,
    plugin_root: str,
) -> tuple[str, str] | None:
    """Parse only canonical read-only ticket script invocations."""
    try:
        tokens = shlex.split(command_clean)
    except ValueError:
        return None
    script_idx = _canonical_launcher_script_index(tokens)
    if script_idx is None or len(tokens) < script_idx + 3:
        return None
    script_path = tokens[script_idx]
    script_name = Path(script_path).name
    allowed = {
        "ticket_read.py": "read",
        "ticket_triage.py": "triage",
        "ticket_review.py": "review",
    }
    if script_name not in allowed:
        return None
    expected_script = str(Path(plugin_root) / "scripts" / script_name)
    if script_path != expected_script:
        return None
    return allowed[script_name], tokens[script_idx + 1]


def _parse_audit_invocation(
    command_clean: str,
    plugin_root: str,
) -> tuple[str, str] | None:
    """Parse only canonical maintenance invocations."""
    try:
        tokens = shlex.split(command_clean)
    except ValueError:
        return None
    script_idx = _canonical_launcher_script_index(tokens)
    if script_idx is None or len(tokens) < script_idx + 3:
        return None
    script_path = tokens[script_idx]
    script_name = Path(script_path).name
    allowed = {
        "ticket_audit.py": "audit",
        "ticket_doctor.py": "doctor",
    }
    if script_name not in allowed:
        return None
    expected_script = str(Path(plugin_root) / "scripts" / script_name)
    if script_path != expected_script:
        return None
    return allowed[script_name], tokens[script_idx + 1]


def _validate_doctor_readonly_invocation(command_clean: str, plugin_root: str) -> str | None:
    """Return an error string when ticket_triage.py doctor uses unsafe roots."""
    try:
        tokens = shlex.split(command_clean)
    except ValueError as exc:
        return f"ticket_triage.py doctor parse failed: {exc}"
    expected_script = str(Path(plugin_root) / "scripts" / "ticket_triage.py")
    script_idx = _canonical_launcher_script_index(tokens)
    if script_idx is None:
        return "ticket_triage.py doctor must use canonical python3 or uv run python launcher"
    if len(tokens) < script_idx + 6:
        return (
            "ticket_triage.py doctor incomplete arguments: expected tickets_dir, "
            "--plugin-root, and --cache-root"
        )
    if tokens[script_idx] != expected_script or tokens[script_idx + 1] != "doctor":
        return "ticket_triage.py doctor must use canonical python3 or uv run python launcher"

    args = tokens[script_idx + 2 :]
    tickets_dir = args[0]
    option_tokens = args[1:]
    if any(char.isspace() for char in tickets_dir):
        return "ticket_triage.py doctor tickets_dir must not contain whitespace"
    values: dict[str, str] = {}
    idx = 0
    while idx < len(option_tokens):
        option = option_tokens[idx]
        if option not in {"--plugin-root", "--cache-root", "--runtime-probe-output"}:
            return f"ticket_triage.py doctor unsupported option: {option}"
        if option in values:
            return f"ticket_triage.py doctor duplicate option: {option}"
        if idx + 1 >= len(option_tokens):
            return f"ticket_triage.py doctor missing value for {option}"
        values[option] = option_tokens[idx + 1]
        idx += 2

    if values.get("--plugin-root") != plugin_root:
        return "ticket_triage.py doctor --plugin-root must equal the running plugin root"
    if values.get("--cache-root") != plugin_root:
        return "ticket_triage.py doctor --cache-root must equal the running plugin root"
    probe = values.get("--runtime-probe-output")
    if probe is not None:
        probe_path = Path(probe).resolve(strict=False)
        temp_root = Path(tempfile.gettempdir()).resolve(strict=False)
        if probe_path.parent != temp_root or not probe_path.name.startswith("ticket-ux-"):
            return (
                "ticket_triage.py doctor --runtime-probe-output must be a "
                f"ticket-ux artifact under {temp_root}"
            )
    return None


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
    """Resolve absolute payload path and enforce workspace-root containment."""
    if not isinstance(workspace_root, str) or not workspace_root:
        return None, f"Invalid workspace root. Got: {workspace_root!r:.100}"
    candidate = Path(payload_path)
    if not candidate.is_absolute():
        return None, f"Payload path must be absolute. Got: {payload_path!r:.100}"
    try:
        root = Path(workspace_root).resolve()
        resolved = candidate.resolve()
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


def _resolve_origin(event: dict, *, is_ticket_candidate: bool) -> tuple[str | None, str | None]:
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
        print(json.dumps(_make_deny("Malformed hook input: expected JSON object on stdin")))
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

    # Non-ticket-script invocations pass through (cat, rg, wc, etc.).
    plugin_root = _plugin_root()
    if not _is_ticket_candidate(command_for_detection):
        print("{}")
        return

    # --- From here, command is a candidate ticket script invocation. ---

    # Block shell metacharacters.
    if SHELL_METACHAR_RE.search(command_clean):
        print(
            json.dumps(
                _make_deny(
                    f"Shell metacharacters detected in ticket engine command. Got: {command!r:.100}"
                )
            )
        )
        return

    if command_clean != command_for_detection:
        print(
            json.dumps(
                _make_deny(f"Command invokes unrecognized ticket script. Got: {command!r:.100}")
            )
        )
        return

    # Engine exact allowlist: validate subcommand/payload and inject.
    engine_invocation = _parse_engine_invocation(command_clean, plugin_root)
    if engine_invocation is not None:
        entrypoint_type, subcommand, payload_path, extra_args = engine_invocation

        # Validate subcommand.
        valid_subcommands = (
            VALID_ACTIVATION_SMOKE_SUBCOMMANDS
            if entrypoint_type == "activation_smoke"
            else VALID_SUBCOMMANDS
        )
        if subcommand not in valid_subcommands:
            print(
                json.dumps(
                    _make_deny(
                        f"Unknown subcommand '{subcommand}'. Valid: {sorted(valid_subcommands)}"
                    )
                )
            )
            return

        # Check for extra arguments (payload_path should not contain whitespace).
        if re.search(r"\s", payload_path) or extra_args:
            print(
                json.dumps(_make_deny(f"Extra arguments after payload path. Got: {command!r:.100}"))
            )
            return

        workspace_root = event.get("cwd", "")
        resolved_path, path_error = _resolve_payload_path(payload_path, workspace_root)
        if path_error is not None or resolved_path is None:
            print(
                json.dumps(
                    _make_deny(f"Payload path validation failed: {path_error or 'unknown error'}")
                )
            )
            return

        # Inject trust fields into payload.
        session_id = event.get("session_id")
        if not isinstance(session_id, str) or not session_id:
            print(json.dumps(_make_deny(_malformed_session_id_reason(session_id))))
            return
        effective_origin, origin_error = _resolve_origin(event, is_ticket_candidate=True)
        if origin_error is not None:
            print(json.dumps(_make_deny(origin_error)))
            return
        if effective_origin is None:
            print(json.dumps(_make_deny("Origin resolution failed: internal invariant violation")))
            return
        error = _inject_payload(str(resolved_path), session_id, effective_origin)
        if error is not None:
            print(json.dumps(_make_deny(f"Payload injection failed: {error}")))
            return

        print(
            json.dumps(
                _make_allow(
                    f"Ticket engine {entrypoint_type}/{subcommand} validated and payload injected"
                )
            )
        )
        return

    workflow_invocation = _parse_workflow_invocation(command_clean, plugin_root)
    if workflow_invocation is not None:
        print(json.dumps(_make_deny("Deprecated Ticket workflow command is unavailable")))
        return

    capture_invocation = _parse_capture_invocation(command_clean, plugin_root)
    if capture_invocation is not None:
        print(json.dumps(_make_deny("Deprecated Ticket capture command is unavailable")))
        return

    update_invocation = _parse_update_invocation(command_clean, plugin_root)
    if update_invocation is not None:
        print(json.dumps(_make_deny("Deprecated Ticket update command is unavailable")))
        return

    # Read-only scripts (ticket_read.py, ticket_triage.py, ticket_review.py).
    # → allow, no injection.
    readonly_invocation = _parse_readonly_invocation(command_clean, plugin_root)
    if readonly_invocation is not None:
        script_name, subcommand = readonly_invocation
        if script_name == "triage" and subcommand == "doctor":
            doctor_error = _validate_doctor_readonly_invocation(command_clean, plugin_root)
            if doctor_error is not None:
                print(json.dumps(_make_deny(doctor_error)))
                return
        print(json.dumps(_make_allow(f"Ticket {script_name}/{subcommand} validated (read-only)")))
        return

    # Maintenance scripts (ticket_audit.py, ticket_doctor.py): allow users, deny agents.
    audit_invocation = _parse_audit_invocation(command_clean, plugin_root)
    if audit_invocation is not None:
        origin, origin_error = _resolve_origin(event, is_ticket_candidate=True)
        if origin_error is not None:
            print(json.dumps(_make_deny(origin_error)))
            return
        if origin == "agent":
            print(
                json.dumps(
                    _make_deny(
                        "Ticket maintenance is user-only — agents cannot invoke "
                        "audit repair or doctor"
                    )
                )
            )
            return
        script_name, subcommand = audit_invocation
        print(json.dumps(_make_allow(f"Ticket {script_name}/{subcommand} validated (user-only)")))
        return

    # Unrecognized ticket script invocation: deny.
    print(
        json.dumps(_make_deny(f"Command invokes unrecognized ticket script. Got: {command!r:.100}"))
    )


def _run_cli() -> int:
    try:
        main()
    except Exception as exc:
        print(
            f"ticket_engine_guard failed closed: {type(exc).__name__}: {exc}",
            file=sys.stderr,
        )
        print(json.dumps(_make_deny(f"guard internal error: {exc!r:.100}")))
    return 0


if __name__ == "__main__":
    sys.exit(_run_cli())

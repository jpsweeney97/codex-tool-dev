"""DeferredWorkEnvelope schema validation, field mapping, and lifecycle.

Envelopes are the bridge between the handoff plugin's /defer skill and the
ticket plugin's creation pipeline. The handoff writes envelopes; the ticket
plugin consumes them through the normal engine pipeline.

Schema version: 1.0
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

_ENVELOPE_VERSION = "1.0"

_REQUIRED_FIELDS = ("envelope_version", "title", "problem", "source", "emitted_at")

_OPTIONAL_FIELDS = (
    "context",
    "prior_investigation",
    "approach",
    "acceptance_criteria",
    "verification",
    "key_files",
    "key_file_paths",
    "suggested_priority",
    "suggested_tags",
    "effort",
)

_ALL_FIELDS = frozenset(_REQUIRED_FIELDS + _OPTIONAL_FIELDS)

_VALID_PRIORITIES = frozenset({"critical", "high", "medium", "low"})

_SOURCE_REQUIRED_KEYS = ("type", "ref", "session")

_KEY_FILE_REQUIRED_KEYS = ("file", "role", "look_for")


def validate_envelope(envelope: dict[str, Any]) -> list[str]:
    """Validate envelope against the DeferredWorkEnvelope schema.

    Returns a list of error messages (empty = valid).
    """
    errors: list[str] = []

    # Unknown fields
    unknown = set(envelope.keys()) - _ALL_FIELDS
    if unknown:
        errors.append(f"Unknown fields: {sorted(unknown)}")

    # Required fields
    for field in _REQUIRED_FIELDS:
        if field not in envelope:
            errors.append(f"Missing required field: {field}")

    # envelope_version
    if "envelope_version" in envelope:
        if envelope["envelope_version"] != _ENVELOPE_VERSION:
            errors.append(
                f"envelope_version must be {_ENVELOPE_VERSION!r}, "
                f"got {envelope['envelope_version']!r}"
            )

    # title, problem: must be non-empty strings
    for field in ("title", "problem"):
        if field in envelope:
            v = envelope[field]
            if not isinstance(v, str) or not v.strip():
                errors.append(f"{field} must be a non-empty string, got {v!r:.80}")

    # emitted_at: must be a non-empty string (ISO 8601)
    if "emitted_at" in envelope:
        v = envelope["emitted_at"]
        if not isinstance(v, str) or not v.strip():
            errors.append(f"emitted_at must be a non-empty string, got {v!r:.80}")

    # source: must be dict with {type, ref, session}
    if "source" in envelope:
        v = envelope["source"]
        if not isinstance(v, dict):
            errors.append(f"source must be a dict, got {type(v).__name__}")
        else:
            for key in _SOURCE_REQUIRED_KEYS:
                if key not in v:
                    errors.append(f"source must contain '{key}' key")
            if not all(isinstance(val, str) for val in v.values()):
                errors.append("source values must all be strings")

    # suggested_priority
    if "suggested_priority" in envelope:
        v = envelope["suggested_priority"]
        if not isinstance(v, str) or v not in _VALID_PRIORITIES:
            errors.append(
                f"suggested_priority must be one of {sorted(_VALID_PRIORITIES)}, "
                f"got {v!r}"
            )

    # suggested_tags: list of strings
    if "suggested_tags" in envelope:
        v = envelope["suggested_tags"]
        if not isinstance(v, list):
            errors.append(f"suggested_tags must be a list, got {type(v).__name__}")
        elif not all(isinstance(item, str) for item in v):
            errors.append("suggested_tags must contain only strings")

    # acceptance_criteria: list of strings
    if "acceptance_criteria" in envelope:
        v = envelope["acceptance_criteria"]
        if not isinstance(v, list):
            errors.append(f"acceptance_criteria must be a list, got {type(v).__name__}")
        elif not all(isinstance(item, str) for item in v):
            errors.append("acceptance_criteria must contain only strings")

    # key_file_paths: list of strings
    if "key_file_paths" in envelope:
        v = envelope["key_file_paths"]
        if not isinstance(v, list):
            errors.append(f"key_file_paths must be a list, got {type(v).__name__}")
        elif not all(isinstance(item, str) for item in v):
            errors.append("key_file_paths must contain only strings")

    # key_files: list of dicts with {file, role, look_for}
    if "key_files" in envelope:
        v = envelope["key_files"]
        if not isinstance(v, list):
            errors.append(f"key_files must be a list, got {type(v).__name__}")
        elif not all(isinstance(item, dict) for item in v):
            errors.append("key_files must contain only dicts")
        else:
            for i, item in enumerate(v):
                for key in _KEY_FILE_REQUIRED_KEYS:
                    if key not in item:
                        errors.append(f"key_files[{i}] must contain '{key}' key")

    # context, prior_investigation, approach, verification: strings
    for field in ("context", "prior_investigation", "approach", "verification"):
        if field in envelope:
            v = envelope[field]
            if not isinstance(v, str):
                errors.append(f"{field} must be a string, got {type(v).__name__}")

    # effort: optional string
    if "effort" in envelope:
        v = envelope["effort"]
        if not isinstance(v, str):
            errors.append(f"effort must be a string, got {type(v).__name__}")

    return errors


def map_envelope_to_fields(envelope: dict[str, Any]) -> dict[str, Any]:
    """Map a validated envelope to the fields dict for engine_execute.

    The consumer synthesizes ticket state — the envelope carries no status.
    Result: status=open, defer.active=true, defer.reason="deferred via envelope".
    """
    fields: dict[str, Any] = {
        "title": envelope["title"],
        "problem": envelope["problem"],
        "source": envelope["source"],
        "priority": envelope.get("suggested_priority", "medium"),
        "tags": envelope.get("suggested_tags", []),
        "defer": {
            "active": True,
            "reason": "deferred via envelope",
            "deferred_at": envelope["emitted_at"],
        },
    }

    # Optional content fields — only include if present
    for field in ("context", "prior_investigation", "approach", "verification"):
        if field in envelope:
            fields[field] = envelope[field]

    if "acceptance_criteria" in envelope:
        fields["acceptance_criteria"] = envelope["acceptance_criteria"]
    if "key_files" in envelope:
        fields["key_files"] = envelope["key_files"]
    if "key_file_paths" in envelope:
        fields["key_file_paths"] = envelope["key_file_paths"]
    if "effort" in envelope:
        fields["effort"] = envelope["effort"]

    return fields


def read_envelope(path: Path) -> tuple[dict[str, Any] | None, list[str]]:
    """Read and validate an envelope JSON file.

    Returns (envelope_dict, errors). On success, errors is empty.
    On failure, envelope is None and errors contains the reasons.
    """
    if not path.exists():
        return None, [f"Envelope not found: {path} does not exist"]

    try:
        raw = path.read_text(encoding="utf-8")
    except OSError as exc:
        return None, [f"Cannot read envelope: {exc}"]

    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        return None, [f"Envelope JSON parse failed: {exc}"]

    if not isinstance(data, dict):
        return None, [f"Envelope must be a JSON object, got {type(data).__name__}"]

    errors = validate_envelope(data)
    if errors:
        return None, errors

    return data, []


def move_to_processed(envelope_path: Path) -> Path:
    """Move a consumed envelope to the .processed/ subdirectory.

    Creates .processed/ if it doesn't exist. Returns the destination path.
    Raises FileExistsError if the destination already exists (prevents
    silent overwrite of previously processed envelopes).
    """
    processed_dir = envelope_path.parent / ".processed"
    processed_dir.mkdir(parents=True, exist_ok=True)
    dest = processed_dir / envelope_path.name
    if dest.exists():
        raise FileExistsError(
            f"move_to_processed failed: {dest} already exists. "
            f"Got: {str(envelope_path)!r:.100}"
        )
    envelope_path.rename(dest)
    return dest

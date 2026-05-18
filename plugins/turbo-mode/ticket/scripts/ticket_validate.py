"""Shared schema validation for dedup inputs and writable ticket fields.

Validates field types and enum membership before dedup fingerprinting,
render_ticket(), or YAML replacement. Rejects invalid inputs; omitted
fields are not errors (defaults are applied by the engine, not the
validator).
"""

from __future__ import annotations

from typing import Any

VALID_PRIORITIES = frozenset({"critical", "high", "medium", "low"})
VALID_STATUSES = frozenset({"open", "in_progress", "blocked", "done", "wontfix"})
VALID_RESOLUTIONS = frozenset({"done", "wontfix"})
VALID_CAPTURE_CONFIDENCE = frozenset({"low", "medium", "high"})
VALID_REFINEMENT_STATUSES = frozenset({"needs_refinement"})
CONTROLLED_CAPTURE_TAGS = frozenset(
    {
        "needs-refinement",
        "bug",
        "feature",
        "docs",
        "test",
        "maintenance",
        "security",
    }
)
CAPTURE_INPUT_FIELDS = frozenset(
    {
        "title",
        "captured_request",
        "problem",
        "next_action",
        "capture_confidence",
        "capture_source",
        "refinement_status",
        "component",
        "related_paths",
        "priority",
        "tags",
        "acceptance_criteria",
    }
)


def _validate_string_field(fields: dict[str, Any], key: str, errors: list[str]) -> None:
    """Append an error when an optional field is present but not a string."""
    if key not in fields:
        return
    value = fields[key]
    if not isinstance(value, str):
        errors.append(f"{key} must be a string, got {type(value).__name__}")


def validate_fields(fields: dict[str, Any]) -> list[str]:
    """Validate writable ticket fields. Returns list of error messages (empty = valid)."""
    errors: list[str] = []

    # --- String fields ---
    for key in (
        "title",
        "problem",
        "reopen_reason",
        "captured_request",
        "next_action",
        "capture_source",
        "component",
    ):
        _validate_string_field(fields, key, errors)

    # --- Enum fields ---
    if "priority" in fields:
        v = fields["priority"]
        if not isinstance(v, str) or v not in VALID_PRIORITIES:
            errors.append(f"priority must be one of {sorted(VALID_PRIORITIES)}, got {v!r}")

    if "status" in fields:
        v = fields["status"]
        if not isinstance(v, str) or v not in VALID_STATUSES:
            errors.append(f"status must be one of {sorted(VALID_STATUSES)}, got {v!r}")

    if "resolution" in fields:
        v = fields["resolution"]
        if not isinstance(v, str) or v not in VALID_RESOLUTIONS:
            errors.append(f"resolution must be one of {sorted(VALID_RESOLUTIONS)}, got {v!r}")

    if "capture_confidence" in fields:
        v = fields["capture_confidence"]
        if not isinstance(v, str) or v not in VALID_CAPTURE_CONFIDENCE:
            errors.append(
                f"capture_confidence must be one of {sorted(VALID_CAPTURE_CONFIDENCE)}, got {v!r}"
            )

    if "refinement_status" in fields:
        v = fields["refinement_status"]
        if not isinstance(v, str) or v not in VALID_REFINEMENT_STATUSES:
            errors.append(f"refinement_status must be 'needs_refinement', got {v!r}")

    # --- List-of-string fields ---
    for key in ("tags", "blocked_by", "blocks", "acceptance_criteria"):
        if key in fields:
            v = fields[key]
            if not isinstance(v, list):
                errors.append(f"{key} must be a list, got {type(v).__name__}")
            elif not all(isinstance(item, str) for item in v):
                errors.append(f"{key} must contain only strings")

    if "related_paths" in fields:
        v = fields["related_paths"]
        if not isinstance(v, list):
            errors.append(f"related_paths must be a list, got {type(v).__name__}")
        elif not all(isinstance(item, str) for item in v):
            errors.append("related_paths must contain only strings")

    if (
        fields.get("refinement_status") != "needs_refinement"
        and "acceptance_criteria" in fields
        and isinstance(fields["acceptance_criteria"], list)
        and any(item == "Needs refinement" for item in fields["acceptance_criteria"])
    ):
        errors.append(
            "acceptance_criteria Needs refinement requires refinement_status=needs_refinement"
        )

    if (
        fields.get("refinement_status") != "needs_refinement"
        and "tags" in fields
        and isinstance(fields["tags"], list)
        and "needs-refinement" in fields["tags"]
    ):
        errors.append("tag needs-refinement requires refinement_status=needs_refinement")

    # --- source: require {type, ref, session} per contract §3 ---
    if "source" in fields:
        v = fields["source"]
        if not isinstance(v, dict):
            errors.append(f"source must be a dict, got {type(v).__name__}")
        else:
            if not all(isinstance(val, str) for val in v.values()):
                errors.append("source values must all be strings")
            for required_key in ("type", "ref", "session"):
                if required_key not in v:
                    errors.append(f"source must contain '{required_key}' key")

    # --- defer: require {active, reason, deferred_at} per contract §3 ---
    if "defer" in fields:
        v = fields["defer"]
        if not isinstance(v, dict):
            errors.append(f"defer must be a dict, got {type(v).__name__}")
        else:
            for required_key in ("active", "reason", "deferred_at"):
                if required_key not in v:
                    errors.append(f"defer must contain '{required_key}' key")

    # --- Structured list fields ---
    if "key_file_paths" in fields:
        v = fields["key_file_paths"]
        if not isinstance(v, list):
            errors.append(f"key_file_paths must be a list, got {type(v).__name__}")
        elif not all(isinstance(item, str) for item in v):
            errors.append("key_file_paths must contain only strings")

    # --- key_files: require {file, role, look_for} per contract §3 ---
    if "key_files" in fields:
        v = fields["key_files"]
        if not isinstance(v, list):
            errors.append(f"key_files must be a list, got {type(v).__name__}")
        elif not all(isinstance(item, dict) for item in v):
            errors.append("key_files must contain only dicts")
        else:
            for i, item in enumerate(v):
                for required_key in ("file", "role", "look_for"):
                    if required_key not in item:
                        errors.append(f"key_files[{i}] must contain '{required_key}' key")

    return errors

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def _json_type(value: object) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, int) and not isinstance(value, bool):
        return "integer"
    if isinstance(value, float):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    return type(value).__name__


def _format_error(operation: str, reason: str, got: object) -> str:
    return f"{operation} failed: {reason}. Got: {got!r:.100}"


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        raise FileNotFoundError(_format_error("read jsonl", "missing file", str(path)))

    rows: list[dict[str, Any]] = []
    for idx, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError as e:
            raise ValueError(
                _format_error("read jsonl", f"invalid json on line {idx}", line[:100])
            ) from e
        if not isinstance(obj, dict):
            raise ValueError(
                _format_error(
                    "read jsonl",
                    f"expected object on line {idx}, got {_json_type(obj)}",
                    line[:100],
                )
            )
        rows.append(obj)
    return rows


def validate_jsonl_against_schema(*, jsonl_path: Path, schema_path: Path) -> list[str]:
    if not schema_path.exists():
        return [_format_error("validate jsonl", "missing schema file", str(schema_path))]
    if not jsonl_path.exists():
        return [_format_error("validate jsonl", "missing jsonl file", str(jsonl_path))]

    try:
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        return [
            _format_error("validate jsonl", "invalid schema json", str(schema_path))
        ]

    def _validate_required(obj: dict[str, Any], required: list[str]) -> list[str]:
        missing = [k for k in required if k not in obj]
        return [f"missing required field {k!r}" for k in missing]

    def _validate_string_field(obj: dict[str, Any], key: str, *, max_len: int | None = None) -> list[str]:
        if key not in obj:
            return []
        value = obj.get(key)
        if not isinstance(value, str):
            return [f"field {key!r} must be string"]
        if not value.strip():
            return [f"field {key!r} must be non-empty"]
        if max_len is not None and len(value) > max_len:
            return [f"field {key!r} too long ({len(value)} > {max_len})"]
        return []

    def _validate_enum_field(obj: dict[str, Any], key: str, allowed: set[str]) -> list[str]:
        if key not in obj:
            return []
        value = obj.get(key)
        if not isinstance(value, str):
            return [f"field {key!r} must be string"]
        if value not in allowed:
            return [f"field {key!r} must be one of {sorted(allowed)!r}"]
        return []

    schema_title = schema.get("title")
    if not isinstance(schema_title, str):
        schema_title = "schema"

    # Prefer jsonschema if available, but fall back to lightweight checks so validation
    # remains usable in constrained environments.
    try:
        from jsonschema import Draft202012Validator  # type: ignore[import-not-found]

        validator = Draft202012Validator(schema)
        failures: list[str] = []
        for idx, obj in enumerate(read_jsonl(jsonl_path), start=1):
            errors = sorted(validator.iter_errors(obj), key=lambda e: list(e.path))
            for err in errors:
                loc = "/".join([str(p) for p in err.path])
                failures.append(
                    f"validate jsonl failed: {jsonl_path.name} line {idx} invalid at {loc or '<root>'}: {err.message}"
                )
        return failures
    except Exception:
        pass

    # Fallback: minimal, schema-specific validation for the eval harness files.
    failures: list[str] = []
    for idx, obj in enumerate(read_jsonl(jsonl_path), start=1):
        if "variants.jsonl" in jsonl_path.name or jsonl_path.name.startswith("variants_"):
            line_failures: list[str] = []
            line_failures.extend(_validate_required(obj, ["brief_id", "variant_id", "variant_key", "options", "sora_prompt"]))
            line_failures.extend(_validate_string_field(obj, "brief_id"))
            line_failures.extend(_validate_string_field(obj, "variant_id"))
            line_failures.extend(_validate_enum_field(obj, "variant_key", {"A", "B", "C", "D"}))
            line_failures.extend(_validate_string_field(obj, "sora_prompt", max_len=2000))

            options = obj.get("options")
            if "options" in obj and not isinstance(options, dict):
                line_failures.append("field 'options' must be object")
            if isinstance(options, dict):
                line_failures.extend(_validate_required(options, ["prompt_density", "coherence_mode", "speaker_binding"]))
                line_failures.extend(
                    _validate_enum_field(options, "prompt_density", {"minimal", "balanced", "max"})
                )
                line_failures.extend(
                    _validate_enum_field(options, "coherence_mode", {"reality_first", "storyboard_first", "hybrid"})
                )
                line_failures.extend(_validate_enum_field(options, "speaker_binding", {"normal", "strict"}))

            for msg in line_failures:
                failures.append(
                    f"validate jsonl failed: {jsonl_path.name} line {idx} ({schema_title}): {msg}"
                )
        else:
            failures.append(
                f"validate jsonl failed: unsupported fallback validation for {jsonl_path.name!r}; "
                "install 'jsonschema' for full validation"
            )
            break
    return failures

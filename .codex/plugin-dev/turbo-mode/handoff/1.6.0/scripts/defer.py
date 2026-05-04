"""Envelope emission logic for /defer skill.

Deterministic: builds DeferredWorkEnvelope JSON, writes to .envelopes/.
LLM extraction happens in the SKILL.md — this script receives candidates.
"""
from __future__ import annotations

import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def _slug(title: str) -> str:
    """Generate a filename slug from a title.

    Lowercase, alphanumeric + hyphens, max 50 chars.
    """
    slug = re.sub(r"[^a-z0-9\s-]", "", title.lower())
    slug = re.sub(r"[\s_]+", "-", slug).strip("-")
    slug = re.sub(r"-+", "-", slug)[:50].rstrip("-")
    return slug


def _prepare_envelope(candidate: dict[str, Any]) -> tuple[str, str]:
    """Validate candidate, build envelope, serialize. Returns (payload_json, stem).

    Raises KeyError for missing required fields, TypeError/ValueError for
    invalid field values. These are candidate-local validation failures.
    """
    for field in ("summary", "problem"):
        value = candidate[field]  # KeyError if missing
        if not isinstance(value, str):
            raise TypeError(f"{field} must be a string, got {type(value).__name__}")
        if not value.strip():
            raise ValueError(f"{field} must be non-empty")

    now = datetime.now(timezone.utc)

    envelope: dict[str, Any] = {
        "envelope_version": "1.0",
        "title": candidate["summary"],
        "problem": candidate["problem"],
        "source": {
            "type": candidate.get("source_type", "ad-hoc"),
            "ref": candidate.get("source_ref", ""),
            "session": candidate.get("session_id", ""),
        },
        "emitted_at": now.isoformat(),
    }

    # Optional fields — only include if present and non-empty.
    if candidate.get("proposed_approach"):
        envelope["approach"] = candidate["proposed_approach"]
    if candidate.get("acceptance_criteria"):
        envelope["acceptance_criteria"] = candidate["acceptance_criteria"]
    envelope["suggested_priority"] = candidate.get("priority") or "medium"
    envelope["effort"] = candidate.get("effort") or "S"
    if candidate.get("files"):
        envelope["key_file_paths"] = candidate["files"]

    # Context composition: branch + source_text folded into context.
    context_parts: list[str] = []
    if candidate.get("branch"):
        context_parts.append(f"Captured on branch `{candidate['branch']}`.")
    if candidate.get("source_text"):
        context_parts.append(f"Evidence anchor:\n> \"{candidate['source_text']}\"")
    if context_parts:
        envelope["context"] = "\n\n".join(context_parts)

    timestamp = now.strftime("%Y-%m-%dT%H%M%SZ")
    stem = f"{timestamp}-{_slug(candidate['summary'])}"
    payload = json.dumps(envelope, indent=2)

    return payload, stem


def _write_envelope_payload(envelopes_dir: Path, stem: str, payload: str) -> Path:
    """Write pre-serialized envelope payload to disk.

    Uses exclusive create mode. Retries with -01 through -99 suffixes.
    Raises FileExistsError after 100 collision attempts (candidate-local).
    Raises OSError on I/O failure (operational — abort batch).
    """
    for attempt in range(100):
        suffix = "" if attempt == 0 else f"-{attempt:02d}"
        path = envelopes_dir / f"{stem}{suffix}.json"
        try:
            with path.open("x", encoding="utf-8") as handle:
                handle.write(payload)
        except FileExistsError:
            continue
        return path

    raise FileExistsError(f"Envelope filename collision after 100 attempts for stem: {stem}")


def emit_envelope(candidate: dict[str, Any], envelopes_dir: Path) -> Path:
    """Write a DeferredWorkEnvelope JSON file. Returns the path.

    Maps /defer candidate fields to envelope schema v1.0. The envelope
    carries no status — the ticket engine consumer synthesizes it.
    """
    envelopes_dir.mkdir(parents=True, exist_ok=True)
    payload, stem = _prepare_envelope(candidate)
    return _write_envelope_payload(envelopes_dir, stem, payload)


def main(argv: list[str] | None = None) -> int:
    """CLI entry point. Reads candidate JSON from stdin, writes envelope files."""
    import argparse

    parser = argparse.ArgumentParser(description="Emit deferred work envelopes")
    parser.add_argument("--tickets-dir", type=Path, default=Path("docs/tickets"))
    args = parser.parse_args(argv)

    try:
        candidates = json.load(sys.stdin)
    except json.JSONDecodeError as exc:
        json.dump(
            {"status": "error", "envelopes": [], "errors": [{"summary": "stdin", "error": f"Invalid JSON input: {exc}"}]},
            sys.stdout,
        )
        return 1

    if not isinstance(candidates, list):
        candidates = [candidates]

    envelopes_dir = args.tickets_dir / ".envelopes"
    try:
        envelopes_dir.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        json.dump(
            {"status": "error", "envelopes": [], "errors": [{"summary": "setup", "error": f"{type(exc).__name__}: {exc}"}]},
            sys.stdout,
        )
        return 1
    created: list[dict[str, str]] = []
    errors: list[dict[str, str]] = []

    for cand in candidates:
        if not isinstance(cand, dict):
            errors.append({
                "summary": "unknown",
                "error": f"Candidate must be a dict, got {type(cand).__name__}",
            })
            continue
        try:
            payload, stem = _prepare_envelope(cand)
        except (KeyError, TypeError, ValueError) as exc:
            errors.append({
                "summary": cand.get("summary", "unknown"),
                "error": f"{type(exc).__name__}: {exc}",
            })
            continue
        try:
            path = _write_envelope_payload(envelopes_dir, stem, payload)
        except FileExistsError as exc:
            errors.append({
                "summary": cand.get("summary", "unknown"),
                "error": f"FileExistsError: {exc}",
            })
            continue
        except OSError as exc:
            errors.append({
                "summary": cand.get("summary", "unknown"),
                "error": f"{type(exc).__name__}: {exc}",
            })
            break
        created.append({"path": str(path)})

    if errors and created:
        json.dump({"status": "partial_success", "envelopes": created, "errors": errors}, sys.stdout)
    elif errors:
        json.dump({"status": "error", "envelopes": [], "errors": errors}, sys.stdout)
    else:
        json.dump({"status": "ok", "envelopes": created}, sys.stdout)
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())

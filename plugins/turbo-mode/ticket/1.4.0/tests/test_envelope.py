"""Tests for DeferredWorkEnvelope schema, validation, and ingestion."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp
from scripts.ticket_engine_core import engine_execute


def _valid_envelope() -> dict:
    """Return a minimal valid envelope."""
    return {
        "envelope_version": "1.0",
        "title": "Fix auth timeout on large payloads",
        "problem": "Auth handler times out for payloads >10MB.",
        "source": {"type": "handoff", "ref": "session-abc", "session": "abc-123"},
        "emitted_at": "2026-03-10T06:00:00Z",
    }


class TestEnvelopeValidation:
    """Tests for validate_envelope()."""

    def test_valid_minimal_envelope(self) -> None:
        from scripts.ticket_envelope import validate_envelope
        errors = validate_envelope(_valid_envelope())
        assert errors == []

    def test_valid_full_envelope(self) -> None:
        from scripts.ticket_envelope import validate_envelope
        envelope = _valid_envelope()
        envelope.update({
            "context": "Found during API refactor.",
            "prior_investigation": "Checked handler.py:45.",
            "approach": "Increase timeout to 30s.",
            "acceptance_criteria": ["Payloads >10MB succeed"],
            "verification": "pytest tests/test_auth.py -v",
            "key_files": [{"file": "handler.py:45", "role": "Timeout logic", "look_for": "timeout constant"}],
            "key_file_paths": ["handler.py"],
            "suggested_priority": "high",
            "suggested_tags": ["auth", "api"],
        })
        errors = validate_envelope(envelope)
        assert errors == []

    def test_missing_required_field_title(self) -> None:
        from scripts.ticket_envelope import validate_envelope
        env = _valid_envelope()
        del env["title"]
        errors = validate_envelope(env)
        assert any("title" in e for e in errors)

    def test_missing_required_field_problem(self) -> None:
        from scripts.ticket_envelope import validate_envelope
        env = _valid_envelope()
        del env["problem"]
        errors = validate_envelope(env)
        assert any("problem" in e for e in errors)

    def test_missing_required_field_source(self) -> None:
        from scripts.ticket_envelope import validate_envelope
        env = _valid_envelope()
        del env["source"]
        errors = validate_envelope(env)
        assert any("source" in e for e in errors)

    def test_missing_required_field_emitted_at(self) -> None:
        from scripts.ticket_envelope import validate_envelope
        env = _valid_envelope()
        del env["emitted_at"]
        errors = validate_envelope(env)
        assert any("emitted_at" in e for e in errors)

    def test_invalid_envelope_version(self) -> None:
        from scripts.ticket_envelope import validate_envelope
        env = _valid_envelope()
        env["envelope_version"] = "2.0"
        errors = validate_envelope(env)
        assert any("envelope_version" in e for e in errors)

    def test_source_missing_required_keys(self) -> None:
        from scripts.ticket_envelope import validate_envelope
        env = _valid_envelope()
        env["source"] = {"type": "handoff"}  # missing ref, session
        errors = validate_envelope(env)
        assert any("ref" in e for e in errors)
        assert any("session" in e for e in errors)

    def test_invalid_suggested_priority(self) -> None:
        from scripts.ticket_envelope import validate_envelope
        env = _valid_envelope()
        env["suggested_priority"] = "urgent"
        errors = validate_envelope(env)
        assert any("suggested_priority" in e for e in errors)

    def test_key_files_missing_required_keys(self) -> None:
        from scripts.ticket_envelope import validate_envelope
        env = _valid_envelope()
        env["key_files"] = [{"file": "foo.py"}]  # missing role, look_for
        errors = validate_envelope(env)
        assert any("role" in e for e in errors)

    def test_unknown_fields_rejected(self) -> None:
        from scripts.ticket_envelope import validate_envelope
        env = _valid_envelope()
        env["unknown_field"] = "surprise"
        errors = validate_envelope(env)
        assert any("unknown" in e.lower() for e in errors)

    def test_effort_accepted_as_optional(self) -> None:
        """effort is a valid optional string field."""
        from scripts.ticket_envelope import validate_envelope

        envelope = _valid_envelope()
        envelope["effort"] = "M"
        errors = validate_envelope(envelope)
        assert errors == []

    def test_effort_non_string_rejected(self) -> None:
        """Non-string effort is rejected."""
        from scripts.ticket_envelope import validate_envelope

        envelope = _valid_envelope()
        envelope["effort"] = 42
        errors = validate_envelope(envelope)
        assert any("effort" in e for e in errors)


class TestEnvelopeToFields:
    """Tests for map_envelope_to_fields()."""

    def test_minimal_envelope_mapping(self) -> None:
        from scripts.ticket_envelope import map_envelope_to_fields
        fields = map_envelope_to_fields(_valid_envelope())

        assert fields["title"] == "Fix auth timeout on large payloads"
        assert fields["problem"] == "Auth handler times out for payloads >10MB."
        assert fields["source"] == {"type": "handoff", "ref": "session-abc", "session": "abc-123"}
        assert fields["priority"] == "medium"  # default
        assert fields["tags"] == []  # default
        assert fields["defer"] == {
            "active": True,
            "reason": "deferred via envelope",
            "deferred_at": "2026-03-10T06:00:00Z",
        }

    def test_full_envelope_mapping(self) -> None:
        from scripts.ticket_envelope import map_envelope_to_fields
        env = _valid_envelope()
        env.update({
            "context": "Found during refactor.",
            "prior_investigation": "Checked handler.py.",
            "approach": "Increase timeout.",
            "acceptance_criteria": ["Large payloads succeed"],
            "verification": "pytest tests/ -v",
            "key_files": [{"file": "handler.py", "role": "Timeout", "look_for": "constant"}],
            "key_file_paths": ["handler.py"],
            "suggested_priority": "high",
            "suggested_tags": ["auth"],
        })
        fields = map_envelope_to_fields(env)

        assert fields["priority"] == "high"
        assert fields["tags"] == ["auth"]
        assert fields["context"] == "Found during refactor."
        assert fields["prior_investigation"] == "Checked handler.py."
        assert fields["approach"] == "Increase timeout."
        assert fields["acceptance_criteria"] == ["Large payloads succeed"]
        assert fields["verification"] == "pytest tests/ -v"
        assert fields["key_files"] == [{"file": "handler.py", "role": "Timeout", "look_for": "constant"}]
        assert fields["key_file_paths"] == ["handler.py"]

    def test_envelope_never_carries_status(self) -> None:
        from scripts.ticket_envelope import map_envelope_to_fields
        fields = map_envelope_to_fields(_valid_envelope())
        assert "status" not in fields, "Consumer synthesizes status; envelope must not carry it"

    def test_effort_passed_through(self) -> None:
        """effort is mapped to fields when present."""
        from scripts.ticket_envelope import map_envelope_to_fields

        envelope = _valid_envelope()
        envelope["effort"] = "XL"
        fields = map_envelope_to_fields(envelope)
        assert fields["effort"] == "XL"

    def test_effort_absent_not_in_fields(self) -> None:
        """effort is not in fields when absent from envelope."""
        from scripts.ticket_envelope import map_envelope_to_fields

        envelope = _valid_envelope()
        fields = map_envelope_to_fields(envelope)
        assert "effort" not in fields


class TestEnvelopeRead:
    """Tests for read_envelope()."""

    def test_read_valid_envelope(self, tmp_path: Path) -> None:
        from scripts.ticket_envelope import read_envelope
        path = tmp_path / "envelope.json"
        path.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

        envelope, errors = read_envelope(path)
        assert errors == []
        assert envelope is not None
        assert envelope["title"] == "Fix auth timeout on large payloads"

    def test_read_invalid_json(self, tmp_path: Path) -> None:
        from scripts.ticket_envelope import read_envelope
        path = tmp_path / "bad.json"
        path.write_text("NOT JSON {{{", encoding="utf-8")

        envelope, errors = read_envelope(path)
        assert envelope is None
        assert any("parse" in e.lower() or "json" in e.lower() for e in errors)

    def test_read_missing_file(self, tmp_path: Path) -> None:
        from scripts.ticket_envelope import read_envelope
        path = tmp_path / "missing.json"

        envelope, errors = read_envelope(path)
        assert envelope is None
        assert any("not found" in e.lower() or "does not exist" in e.lower() for e in errors)

    def test_read_invalid_schema(self, tmp_path: Path) -> None:
        from scripts.ticket_envelope import read_envelope
        path = tmp_path / "bad-schema.json"
        path.write_text(json.dumps({"title": "only title"}), encoding="utf-8")

        envelope, errors = read_envelope(path)
        assert envelope is None
        assert len(errors) > 0


class TestEnvelopeLifecycle:
    """Tests for move_to_processed()."""

    def test_move_creates_processed_dir(self, tmp_path: Path) -> None:
        from scripts.ticket_envelope import move_to_processed
        envelopes_dir = tmp_path / ".envelopes"
        envelopes_dir.mkdir()
        path = envelopes_dir / "2026-03-10T060000Z-fix-auth.json"
        path.write_text("{}", encoding="utf-8")

        dest = move_to_processed(path)

        assert dest.parent == envelopes_dir / ".processed"
        assert dest.name == path.name
        assert dest.exists()
        assert not path.exists()

    def test_move_existing_processed_dir(self, tmp_path: Path) -> None:
        from scripts.ticket_envelope import move_to_processed
        envelopes_dir = tmp_path / ".envelopes"
        processed_dir = envelopes_dir / ".processed"
        processed_dir.mkdir(parents=True)
        path = envelopes_dir / "envelope.json"
        path.write_text("{}", encoding="utf-8")

        dest = move_to_processed(path)
        assert dest.exists()
        assert not path.exists()

    def test_move_rejects_overwrite(self, tmp_path: Path) -> None:
        """Cannot silently overwrite a previously processed envelope."""
        from scripts.ticket_envelope import move_to_processed
        envelopes_dir = tmp_path / ".envelopes"
        processed_dir = envelopes_dir / ".processed"
        processed_dir.mkdir(parents=True)
        existing = processed_dir / "duplicate.json"
        existing.write_text("{}", encoding="utf-8")
        path = envelopes_dir / "duplicate.json"
        path.write_text("{}", encoding="utf-8")

        with pytest.raises(FileExistsError, match="already exists"):
            move_to_processed(path)
        assert path.exists(), "Source should not be removed on failure"


class TestDeferPassThrough:
    """Verify _execute_create passes defer field to render_ticket."""

    def test_create_with_defer_field_persists_in_yaml(self, tmp_tickets: Path) -> None:
        """When fields include defer, the created ticket has defer in frontmatter."""
        import yaml

        problem = "Auth handler times out."
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields={
                "title": "Fix auth timeout",
                "problem": problem,
                "defer": {
                    "active": True,
                    "reason": "deferred via envelope",
                    "deferred_at": "2026-03-10T06:00:00Z",
                },
            },
            session_id="sess-defer-1",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp(problem, []),
        )
        assert resp.state == "ok_create"

        ticket_path = Path(resp.data["ticket_path"])
        content = ticket_path.read_text(encoding="utf-8")

        # Extract YAML block
        import re
        yaml_match = re.search(r"```ya?ml\s*\n(.*?)```", content, re.DOTALL)
        assert yaml_match, "YAML block not found"
        frontmatter = yaml.safe_load(yaml_match.group(1))

        assert frontmatter["defer"]["active"] is True
        assert frontmatter["defer"]["reason"] == "deferred via envelope"
        assert frontmatter["defer"]["deferred_at"] == "2026-03-10T06:00:00Z"


class TestEnvelopeIngestion:
    """End-to-end: envelope file → ticket creation → envelope archived."""

    def test_envelope_to_ticket_full_pipeline(self, tmp_tickets: Path) -> None:
        """Read envelope, map fields, create ticket, move to processed."""
        import re
        import yaml
        from scripts.ticket_envelope import read_envelope, map_envelope_to_fields, move_to_processed

        # Set up envelope
        envelopes_dir = tmp_tickets / ".envelopes"
        envelopes_dir.mkdir()
        envelope_data = _valid_envelope()
        envelope_data["suggested_priority"] = "high"
        envelope_data["suggested_tags"] = ["auth"]
        envelope_data["context"] = "Found during API refactor."
        envelope_path = envelopes_dir / "2026-03-10T060000Z-fix-auth.json"
        envelope_path.write_text(json.dumps(envelope_data), encoding="utf-8")

        # Read and validate
        envelope, errors = read_envelope(envelope_path)
        assert errors == []
        assert envelope is not None

        # Map to engine fields
        fields = map_envelope_to_fields(envelope)

        # Create ticket via engine
        resp = engine_execute(
            action="create",
            ticket_id=None,
            fields=fields,
            session_id="sess-envelope-1",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp(fields["problem"], fields.get("key_file_paths", [])),
        )
        assert resp.state == "ok_create"

        # Verify ticket content
        ticket_path = Path(resp.data["ticket_path"])
        content = ticket_path.read_text(encoding="utf-8")
        yaml_match = re.search(r"```ya?ml\s*\n(.*?)```", content, re.DOTALL)
        assert yaml_match
        frontmatter = yaml.safe_load(yaml_match.group(1))

        assert frontmatter["priority"] == "high"
        assert frontmatter["tags"] == ["auth"]
        assert frontmatter["defer"]["active"] is True
        assert frontmatter["defer"]["reason"] == "deferred via envelope"
        assert frontmatter["source"]["type"] == "handoff"
        assert "## Context" in content
        assert "Found during API refactor." in content

        # Move envelope to processed
        dest = move_to_processed(envelope_path)
        assert dest.exists()
        assert not envelope_path.exists()
        assert dest.parent.name == ".processed"

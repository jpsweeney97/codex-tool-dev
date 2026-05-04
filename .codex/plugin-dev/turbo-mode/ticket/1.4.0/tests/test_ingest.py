"""Tests for the ingest subcommand."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.ticket_engine_runner import run


def _valid_envelope() -> dict:
    """Minimal valid envelope for testing."""
    return {
        "envelope_version": "1.0",
        "title": "Fix timeout in auth handler",
        "problem": "Auth handler times out for payloads >10MB.",
        "source": {"type": "handoff", "ref": "session-abc", "session": "abc-123"},
        "emitted_at": "2026-03-10T12:00:00Z",
    }


def _ensure_project_root(tmp_path: Path) -> None:
    """Create a .git marker so discover_project_root() succeeds."""
    (tmp_path / ".git").mkdir(exist_ok=True)


def _write_envelope(envelope: dict, envelopes_dir: Path) -> Path:
    """Write envelope JSON to the envelopes directory."""
    envelopes_dir.mkdir(parents=True, exist_ok=True)
    path = envelopes_dir / "2026-03-10T120000Z-fix-timeout.json"
    path.write_text(json.dumps(envelope), encoding="utf-8")
    return path


class TestIngestSubcommand:
    def test_happy_path(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ingest reads envelope, creates ticket, moves to processed."""
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        envelopes_dir = tickets_dir / ".envelopes"
        envelope_path = _write_envelope(_valid_envelope(), envelopes_dir)

        payload = {
            "envelope_path": str(envelope_path),
            "tickets_dir": str(tickets_dir),
            "session_id": "test-session",
            "hook_injected": True,
            "hook_request_origin": "user",
        }

        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps(payload))

        exit_code = run(
            "user",
            argv=["ingest", str(payload_file)],
            prog="test",
        )

        assert exit_code == 0
        # Envelope moved to .processed/
        assert not envelope_path.exists()
        processed = envelopes_dir / ".processed" / envelope_path.name
        assert processed.exists()
        # Ticket created
        ticket_files = list(tickets_dir.glob("*.md"))
        assert len(ticket_files) == 1

    def test_invalid_envelope_returns_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ingest with invalid envelope returns error response."""
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        envelopes_dir = tickets_dir / ".envelopes"
        bad_envelope = {"envelope_version": "1.0"}  # Missing required fields
        envelope_path = _write_envelope(bad_envelope, envelopes_dir)

        payload = {
            "envelope_path": str(envelope_path),
            "tickets_dir": str(tickets_dir),
            "session_id": "test-session",
            "hook_injected": True,
            "hook_request_origin": "user",
        }

        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps(payload))

        exit_code = run(
            "user",
            argv=["ingest", str(payload_file)],
            prog="test",
        )

        assert exit_code == 2  # need_fields maps to exit code 2
        # Envelope NOT moved (still in place)
        assert envelope_path.exists()

    def test_missing_envelope_returns_error(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ingest with nonexistent envelope path returns error."""
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        # Path must be inside .envelopes/ to pass containment check.
        envelopes_dir = tickets_dir / ".envelopes"
        envelopes_dir.mkdir(parents=True)

        payload = {
            "envelope_path": str(envelopes_dir / "nonexistent.json"),
            "tickets_dir": str(tickets_dir),
            "session_id": "test-session",
            "hook_injected": True,
            "hook_request_origin": "user",
        }

        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps(payload))

        exit_code = run(
            "user",
            argv=["ingest", str(payload_file)],
            prog="test",
        )

        assert exit_code == 2  # need_fields maps to exit code 2

    def test_dedup_detected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ingest detects duplicate and returns duplicate_candidate state."""
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        envelopes_dir = tickets_dir / ".envelopes"

        # Ingest first envelope — should succeed.
        envelope_path_1 = _write_envelope(_valid_envelope(), envelopes_dir)
        payload = {
            "envelope_path": str(envelope_path_1),
            "tickets_dir": str(tickets_dir),
            "session_id": "test-session",
            "hook_injected": True,
            "hook_request_origin": "user",
        }
        payload_file = tmp_path / "payload1.json"
        payload_file.write_text(json.dumps(payload))
        exit_code = run("user", argv=["ingest", str(payload_file)], prog="test")
        assert exit_code == 0

        # Ingest second envelope with same problem text — should detect duplicate.
        envelope_path_2 = envelopes_dir / "2026-03-10T120001Z-fix-timeout-2.json"
        envelope_path_2.write_text(json.dumps(_valid_envelope()), encoding="utf-8")
        payload2 = {
            "envelope_path": str(envelope_path_2),
            "tickets_dir": str(tickets_dir),
            "session_id": "test-session",
            "hook_injected": True,
            "hook_request_origin": "user",
        }
        payload_file2 = tmp_path / "payload2.json"
        payload_file2.write_text(json.dumps(payload2))
        exit_code2 = run("user", argv=["ingest", str(payload_file2)], prog="test")
        assert exit_code2 == 1  # Duplicate detected, not created

    def test_path_traversal_blocked(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ingest with envelope_path outside tickets_dir/.envelopes is blocked."""
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()

        # Write envelope outside .envelopes boundary.
        outside_path = tmp_path / "evil.json"
        outside_path.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

        payload = {
            "envelope_path": str(outside_path),
            "tickets_dir": str(tickets_dir),
            "session_id": "test-session",
            "hook_injected": True,
            "hook_request_origin": "user",
        }

        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps(payload))

        exit_code = run(
            "user",
            argv=["ingest", str(payload_file)],
            prog="test",
        )

        assert exit_code == 1  # policy_blocked
        assert not list(tickets_dir.glob("*.md"))

    def test_processed_replay_blocked(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Ingest with envelope_path in .processed is blocked (replay prevention)."""
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        processed_dir = tickets_dir / ".envelopes" / ".processed"
        processed_dir.mkdir(parents=True)

        processed_path = processed_dir / "old.json"
        processed_path.write_text(json.dumps(_valid_envelope()), encoding="utf-8")

        payload = {
            "envelope_path": str(processed_path),
            "tickets_dir": str(tickets_dir),
            "session_id": "test-session",
            "hook_injected": True,
            "hook_request_origin": "user",
        }

        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps(payload))

        exit_code = run(
            "user",
            argv=["ingest", str(payload_file)],
            prog="test",
        )

        assert exit_code == 1  # policy_blocked

    def test_ingest_with_effort(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Envelope with effort field creates ticket with effort in frontmatter."""
        _ensure_project_root(tmp_path)
        monkeypatch.chdir(tmp_path)

        tickets_dir = tmp_path / "tickets"
        tickets_dir.mkdir()
        envelopes_dir = tickets_dir / ".envelopes"
        envelope = _valid_envelope()
        envelope["effort"] = "M"
        envelope_path = _write_envelope(envelope, envelopes_dir)

        payload = {
            "envelope_path": str(envelope_path),
            "tickets_dir": str(tickets_dir),
            "session_id": "test-session",
            "hook_injected": True,
            "hook_request_origin": "user",
        }

        payload_file = tmp_path / "payload.json"
        payload_file.write_text(json.dumps(payload))

        exit_code = run(
            "user",
            argv=["ingest", str(payload_file)],
            prog="test",
        )

        assert exit_code == 0
        ticket_files = list(tickets_dir.glob("*.md"))
        assert len(ticket_files) == 1
        content = ticket_files[0].read_text()
        assert "effort:" in content

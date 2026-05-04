"""Tests for defer.py — envelope emission logic."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


def _run_main(input_json: str, tickets_dir: Path) -> tuple[int, dict]:
    """Run main() with given stdin JSON, return (exit_code, parsed_output)."""
    import io

    from scripts.defer import main

    original_stdin, original_stdout = sys.stdin, sys.stdout
    sys.stdin = io.StringIO(input_json)
    buf = io.StringIO()
    sys.stdout = buf
    try:
        code = main(["--tickets-dir", str(tickets_dir)])
    finally:
        sys.stdin, sys.stdout = original_stdin, original_stdout
    return code, json.loads(buf.getvalue())


class TestEmitEnvelope:
    def test_same_second_same_summary_gets_unique_filenames(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Same-second collisions are resolved without overwriting data."""
        import scripts.defer as defer_module

        fixed_now = datetime(2026, 3, 10, 15, 4, 5, tzinfo=timezone.utc)

        class FixedDateTime:
            @classmethod
            def now(cls, tz: timezone | None = None) -> datetime:
                assert tz == timezone.utc
                return fixed_now

        monkeypatch.setattr(defer_module, "datetime", FixedDateTime)

        candidate_one = {
            "summary": "Duplicate summary",
            "problem": "First problem.",
            "source_text": "First source.",
            "proposed_approach": "First approach.",
            "acceptance_criteria": ["First criteria"],
            "priority": "medium",
            "source_type": "ad-hoc",
            "source_ref": "",
            "session_id": "sess-dup-1",
        }
        candidate_two = {
            "summary": "Duplicate summary",
            "problem": "Second problem.",
            "source_text": "Second source.",
            "proposed_approach": "Second approach.",
            "acceptance_criteria": ["Second criteria"],
            "priority": "high",
            "source_type": "ad-hoc",
            "source_ref": "",
            "session_id": "sess-dup-2",
        }

        envelopes_dir = tmp_path / ".envelopes"
        path_one = defer_module.emit_envelope(candidate_one, envelopes_dir)
        path_two = defer_module.emit_envelope(candidate_two, envelopes_dir)

        assert path_one.name == "2026-03-10T150405Z-duplicate-summary.json"
        assert path_two.name == "2026-03-10T150405Z-duplicate-summary-01.json"
        assert path_one != path_two

        data_one = json.loads(path_one.read_text())
        data_two = json.loads(path_two.read_text())
        assert data_one["problem"] == "First problem."
        assert data_two["problem"] == "Second problem."

    def test_non_string_summary_raises_type_error(self, tmp_path: Path) -> None:
        """Non-string summary raises TypeError (caught by main's catch list)."""
        from scripts.defer import emit_envelope

        candidate = {
            "summary": 42,
            "problem": "Some problem.",
        }
        with pytest.raises(TypeError, match="summary must be a string"):
            emit_envelope(candidate, tmp_path / ".envelopes")

    def test_empty_summary_raises_value_error(self, tmp_path: Path) -> None:
        """Whitespace-only summary raises ValueError (caught by main's catch list)."""
        from scripts.defer import emit_envelope

        candidate = {
            "summary": "   ",
            "problem": "Some problem.",
        }
        with pytest.raises(ValueError, match="summary must be non-empty"):
            emit_envelope(candidate, tmp_path / ".envelopes")

    def test_minimal_candidate(self, tmp_path: Path) -> None:
        """Minimal candidate produces valid envelope JSON."""
        from scripts.defer import emit_envelope

        candidate = {
            "summary": "Fix auth timeout",
            "problem": "Auth handler times out for large payloads.",
            "source_text": "Found during review.",
            "proposed_approach": "Increase timeout.",
            "acceptance_criteria": ["Timeout works for 10MB"],
            "priority": "medium",
            "source_type": "ad-hoc",
            "source_ref": "",
            "session_id": "sess-1",
        }
        envelopes_dir = tmp_path / ".envelopes"
        path = emit_envelope(candidate, envelopes_dir)

        assert path.exists()
        assert path.suffix == ".json"
        data = json.loads(path.read_text())
        assert data["envelope_version"] == "1.0"
        assert data["title"] == "Fix auth timeout"
        assert data["problem"] == "Auth handler times out for large payloads."
        assert data["source"]["type"] == "ad-hoc"
        assert data["source"]["session"] == "sess-1"
        assert data["suggested_priority"] == "medium"
        assert data["approach"] == "Increase timeout."
        assert data["acceptance_criteria"] == ["Timeout works for 10MB"]
        assert "emitted_at" in data
        assert "status" not in data

    def test_full_candidate_with_effort_and_files(self, tmp_path: Path) -> None:
        """All candidate fields mapped correctly including effort."""
        from scripts.defer import emit_envelope

        candidate = {
            "summary": "Refactor parser",
            "problem": "Parser is too slow.",
            "source_text": "Profiling showed bottleneck.",
            "proposed_approach": "Use streaming parser.",
            "acceptance_criteria": ["10x faster", "No regressions"],
            "priority": "high",
            "effort": "M",
            "source_type": "pr-review",
            "source_ref": "PR #42",
            "session_id": "sess-2",
            "branch": "feature/parser",
            "files": ["src/parser.py", "src/lexer.py"],
        }
        envelopes_dir = tmp_path / ".envelopes"
        path = emit_envelope(candidate, envelopes_dir)

        data = json.loads(path.read_text())
        assert data["effort"] == "M"
        assert data["key_file_paths"] == ["src/parser.py", "src/lexer.py"]
        assert data["suggested_priority"] == "high"
        assert data["source"]["ref"] == "PR #42"

    def test_context_composition(self, tmp_path: Path) -> None:
        """Branch and source_text composed into context field."""
        from scripts.defer import emit_envelope

        candidate = {
            "summary": "Test context",
            "problem": "Problem text.",
            "source_text": "User said to defer this.",
            "proposed_approach": "TBD.",
            "acceptance_criteria": ["Done"],
            "priority": "low",
            "source_type": "ad-hoc",
            "source_ref": "",
            "session_id": "sess-3",
            "branch": "fix/auth",
        }
        envelopes_dir = tmp_path / ".envelopes"
        path = emit_envelope(candidate, envelopes_dir)

        data = json.loads(path.read_text())
        assert "context" in data
        assert "Captured on branch `fix/auth`" in data["context"]
        assert 'Evidence anchor:' in data["context"]
        assert "User said to defer this." in data["context"]

    def test_no_status_field(self, tmp_path: Path) -> None:
        """Envelope never contains status field."""
        from scripts.defer import emit_envelope

        candidate = {
            "summary": "No status",
            "problem": "Problem.",
            "source_text": "Quote.",
            "proposed_approach": "Fix.",
            "acceptance_criteria": ["Fixed"],
            "priority": "medium",
            "source_type": "ad-hoc",
            "source_ref": "",
            "session_id": "sess-4",
        }
        envelopes_dir = tmp_path / ".envelopes"
        path = emit_envelope(candidate, envelopes_dir)

        data = json.loads(path.read_text())
        assert "status" not in data

    def test_emitted_at_is_iso8601(self, tmp_path: Path) -> None:
        """emitted_at is a valid ISO 8601 timestamp."""
        from scripts.defer import emit_envelope

        candidate = {
            "summary": "Timestamp test",
            "problem": "Problem.",
            "source_text": "Quote.",
            "proposed_approach": "Fix.",
            "acceptance_criteria": ["Fixed"],
            "priority": "medium",
            "source_type": "ad-hoc",
            "source_ref": "",
            "session_id": "sess-5",
        }
        envelopes_dir = tmp_path / ".envelopes"
        path = emit_envelope(candidate, envelopes_dir)

        data = json.loads(path.read_text())
        # Should parse without error
        ts = datetime.fromisoformat(data["emitted_at"])
        assert ts.tzinfo is not None  # Must be timezone-aware

    def test_producer_defaults_applied(self, tmp_path: Path) -> None:
        """Absent priority/effort get SKILL.md-documented defaults."""
        from scripts.defer import emit_envelope

        candidate = {"summary": "Test defaults", "problem": "No priority or effort."}
        path = emit_envelope(candidate, tmp_path / ".envelopes")
        data = json.loads(path.read_text())
        assert data["suggested_priority"] == "medium"
        assert data["effort"] == "S"

    def test_explicit_values_override_defaults(self, tmp_path: Path) -> None:
        """Explicit priority/effort override defaults."""
        from scripts.defer import emit_envelope

        candidate = {
            "summary": "Test override", "problem": "Has values.",
            "priority": "high", "effort": "XL",
        }
        path = emit_envelope(candidate, tmp_path / ".envelopes")
        data = json.loads(path.read_text())
        assert data["suggested_priority"] == "high"
        assert data["effort"] == "XL"


class TestMainEmitsEnvelopes:
    def test_main_output_format(self, tmp_path: Path) -> None:
        """CLI writes envelopes and outputs JSON with 'envelopes' key."""
        candidate = {
            "summary": "CLI test", "problem": "Test problem.",
            "source_text": "Quote.", "proposed_approach": "Fix.",
            "acceptance_criteria": ["Done"], "priority": "medium",
            "source_type": "ad-hoc", "source_ref": "", "session_id": "sess-cli",
        }
        code, output = _run_main(json.dumps([candidate]), tmp_path)
        assert code == 0
        assert output["status"] == "ok"
        assert len(output["envelopes"]) == 1
        assert output["envelopes"][0]["path"].endswith(".json")

    def test_envelopes_written_to_dir(self, tmp_path: Path) -> None:
        """Envelopes are written to .envelopes/ subdirectory."""
        candidate = {
            "summary": "Dir test", "problem": "Problem.",
            "source_text": "Quote.", "proposed_approach": "Fix.",
            "acceptance_criteria": ["Done"], "priority": "low",
            "source_type": "ad-hoc", "source_ref": "", "session_id": "sess-dir",
        }
        _run_main(json.dumps([candidate]), tmp_path)
        envelopes = list((tmp_path / ".envelopes").glob("*.json"))
        assert len(envelopes) == 1

    def test_invalid_json_stdin(self, tmp_path: Path) -> None:
        """Invalid JSON input produces error status."""
        code, output = _run_main("not json{{{", tmp_path)
        assert code == 1
        assert output["status"] == "error"
        assert output["envelopes"] == []
        assert "Invalid JSON input" in output["errors"][0]["error"]

    def test_non_dict_candidate_error(self, tmp_path: Path) -> None:
        """Non-dict items in candidate list produce per-item errors."""
        code, output = _run_main(json.dumps([42, "string"]), tmp_path)
        assert code == 1
        assert output["status"] == "error"
        assert len(output["errors"]) == 2
        assert "Candidate must be a dict" in output["errors"][0]["error"]

    def test_missing_summary_key_error(self, tmp_path: Path) -> None:
        """Candidate missing 'summary' produces KeyError."""
        code, output = _run_main(json.dumps([{"problem": "P"}]), tmp_path)
        assert code == 1
        assert "KeyError" in output["errors"][0]["error"]

    def test_missing_problem_key_error(self, tmp_path: Path) -> None:
        """Candidate missing 'problem' produces KeyError."""
        code, output = _run_main(json.dumps([{"summary": "S"}]), tmp_path)
        assert code == 1
        assert "KeyError" in output["errors"][0]["error"]

    def test_non_string_summary_cli_error(self, tmp_path: Path) -> None:
        """Non-string summary produces TypeError at CLI level."""
        code, output = _run_main(json.dumps([{"summary": 42, "problem": "P"}]), tmp_path)
        assert code == 1
        assert "TypeError" in output["errors"][0]["error"]

    def test_empty_summary_cli_error(self, tmp_path: Path) -> None:
        """Whitespace-only summary produces ValueError at CLI level."""
        code, output = _run_main(json.dumps([{"summary": "   ", "problem": "P"}]), tmp_path)
        assert code == 1
        assert "ValueError" in output["errors"][0]["error"]

    def test_all_errors_batch(self, tmp_path: Path) -> None:
        """All-error batch produces 'error' status."""
        candidates = [{"summary": "A"}, {"summary": "B"}]  # Both missing problem
        code, output = _run_main(json.dumps(candidates), tmp_path)
        assert code == 1
        assert output["status"] == "error"
        assert len(output["errors"]) == 2
        assert output["envelopes"] == []

    def test_partial_success_mixed_batch(self, tmp_path: Path) -> None:
        """Mixed batch (one valid, one bad) produces 'partial_success'."""
        candidates = [
            {"summary": "Good", "problem": "Valid."},
            {"summary": "Bad"},  # Missing problem
        ]
        code, output = _run_main(json.dumps(candidates), tmp_path)
        assert code == 1
        assert output["status"] == "partial_success"
        assert len(output["envelopes"]) == 1
        assert len(output["errors"]) == 1

    def test_single_object_normalization(self, tmp_path: Path) -> None:
        """Bare dict (not list) is normalized to single-item list."""
        candidate = {"summary": "Solo", "problem": "Valid."}
        code, output = _run_main(json.dumps(candidate), tmp_path)
        assert code == 0
        assert output["status"] == "ok"
        assert len(output["envelopes"]) == 1

    def test_single_object_with_error(self, tmp_path: Path) -> None:
        """Bare dict with error produces error status."""
        code, output = _run_main(json.dumps({"summary": "No problem"}), tmp_path)
        assert code == 1
        assert output["status"] == "error"

    def test_collision_exhaustion_continues_batch(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """FileExistsError from collision exhaustion is candidate-local."""
        import scripts.defer as defer_module

        fixed_now = datetime(2026, 3, 10, 15, 0, 0, tzinfo=timezone.utc)

        class FixedDateTime:
            @classmethod
            def now(cls, tz: timezone | None = None) -> datetime:
                return fixed_now

        monkeypatch.setattr(defer_module, "datetime", FixedDateTime)

        envelopes_dir = tmp_path / ".envelopes"
        envelopes_dir.mkdir(parents=True)
        stem = "2026-03-10T150000Z-collide-me"
        (envelopes_dir / f"{stem}.json").write_text("{}")
        for i in range(1, 100):
            (envelopes_dir / f"{stem}-{i:02d}.json").write_text("{}")

        candidates = [
            {"summary": "Collide me", "problem": "Exhausts collisions."},
            {"summary": "Second item", "problem": "Should succeed."},
        ]
        code, output = _run_main(json.dumps(candidates), tmp_path)
        assert output["status"] == "partial_success"
        assert len(output["errors"]) == 1
        assert "FileExistsError" in output["errors"][0]["error"]
        assert len(output["envelopes"]) == 1
        assert code == 1

    def test_tickets_dir_is_file_returns_json_error(self, tmp_path: Path) -> None:
        """When --tickets-dir points to a file, mkdir fails with JSON error contract."""
        bad_dir = tmp_path / "actually-a-file"
        bad_dir.write_text("not a directory")
        candidate = {"summary": "Should not reach", "problem": "Problem."}
        code, output = _run_main(json.dumps([candidate]), bad_dir)
        assert code == 1
        assert output["status"] == "error"
        assert output["envelopes"] == []
        assert len(output["errors"]) == 1
        assert output["errors"][0]["summary"] == "setup"
        assert "NotADirectoryError" in output["errors"][0]["error"]

    def test_write_oserror_aborts_batch(self, tmp_path: Path) -> None:
        """Non-FileExistsError OSError aborts remaining candidates."""
        envelopes_dir = tmp_path / ".envelopes"
        envelopes_dir.mkdir(parents=True)
        envelopes_dir.chmod(0o444)
        try:
            candidates = [
                {"summary": "First", "problem": "Will fail write."},
                {"summary": "Second", "problem": "Should not be attempted."},
            ]
            code, output = _run_main(json.dumps(candidates), tmp_path)
            assert code == 1
            assert output["status"] == "error"
            assert len(output["errors"]) == 1  # Batch aborted after first
            assert "PermissionError" in output["errors"][0]["error"]
        finally:
            envelopes_dir.chmod(0o755)

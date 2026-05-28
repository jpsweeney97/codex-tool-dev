"""Tests for historical audit support after runtime-first re-baseline."""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from scripts.ticket_dedup import dedup_fingerprint as compute_dedup_fp
from scripts.ticket_engine_core import (
    AUDIT_UNAVAILABLE,
    engine_count_session_creates,
    engine_execute,
)

_AUDIT_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "ticket_audit.py"


def _run_audit_cli(*args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_AUDIT_SCRIPT), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        check=False,
    )


class TestAuditRebaseline:
    """Future runtime writes no longer use docs/tickets/.audit/."""

    def test_engine_execute_does_not_create_future_audit_files(
        self, tmp_tickets: Path
    ) -> None:
        response = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "No audit", "problem": "Future writes use Change History."},
            session_id="sess-no-audit",
            request_origin="user",
            dedup_override=False,
            dependency_override=False,
            tickets_dir=tmp_tickets,
            hook_injected=True,
            hook_request_origin="user",
            classify_intent="create",
            classify_confidence=0.95,
            dedup_fingerprint=compute_dedup_fp("Future writes use Change History.", []),
        )

        assert response.state == "ok_create"
        assert not (tmp_tickets / ".audit").exists()

    def test_historical_audit_reader_still_counts_existing_files(
        self, tmp_tickets: Path
    ) -> None:
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_file = tmp_tickets / ".audit" / today / "sess-historical.jsonl"
        audit_file.parent.mkdir(parents=True)
        audit_file.write_text(
            json.dumps(
                {
                    "ts": "2026-05-27T00:00:00+00:00",
                    "action": "attempt_started",
                    "intent": "create",
                    "ticket_id": None,
                    "session_id": "sess-historical",
                    "request_origin": "agent",
                    "autonomy_mode": "auto_audit",
                    "result": None,
                    "changes": None,
                }
            )
            + "\n",
            encoding="utf-8",
        )

        assert engine_count_session_creates("sess-historical", tmp_tickets) == 1


class TestSessionCounting:
    """Tests for engine_count_session_creates."""

    def test_future_engine_creates_are_not_counted_without_historical_audit(
        self, tmp_tickets: Path
    ) -> None:
        problem = "Future writes are tracked outside historical audit."
        response = engine_execute(
            action="create",
            ticket_id=None,
            fields={"title": "Future count", "problem": problem},
            session_id="sess-future-count",
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

        assert response.state == "ok_create"
        assert engine_count_session_creates("sess-future-count", tmp_tickets) == 0

    def test_count_missing_file_returns_zero(self, tmp_tickets: Path) -> None:
        """Non-existent session returns 0."""
        assert engine_count_session_creates("nonexistent-session", tmp_tickets) == 0

    def test_count_corrupt_line_skipped(self, tmp_tickets: Path) -> None:
        """Corrupt JSONL lines are skipped; valid attempt_started entries are still counted."""
        session_id = "sess-count-corrupt"
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{session_id}.jsonl"
        lines = [
            json.dumps(
                {
                    "action": "attempt_started",
                    "intent": "create",
                    "request_origin": "agent",
                    "ts": "t1",
                }
            ),
            "NOT VALID JSON {{{",
            json.dumps(
                {
                    "action": "attempt_started",
                    "intent": "create",
                    "request_origin": "agent",
                    "ts": "t2",
                }
            ),
        ]
        audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert engine_count_session_creates(session_id, tmp_tickets) == 2

    def test_count_ignores_non_create_intents(self, tmp_tickets: Path) -> None:
        """Only attempt_started with intent==create are counted."""
        session_id = "sess-count-intents"
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{session_id}.jsonl"
        lines = [
            json.dumps(
                {
                    "action": "attempt_started",
                    "intent": "create",
                    "request_origin": "agent",
                    "ts": "t1",
                }
            ),
            json.dumps(
                {
                    "action": "attempt_started",
                    "intent": "update",
                    "request_origin": "agent",
                    "ts": "t2",
                }
            ),
            json.dumps(
                {
                    "action": "attempt_started",
                    "intent": "close",
                    "request_origin": "agent",
                    "ts": "t3",
                }
            ),
        ]
        audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert engine_count_session_creates(session_id, tmp_tickets) == 1

    def test_count_permission_error_returns_sentinel(self, tmp_tickets: Path) -> None:
        """Permission error reading audit file returns AUDIT_UNAVAILABLE."""
        import os
        import sys

        if sys.platform == "win32":
            pytest.skip("chmod not effective on Windows")

        session_id = "sess-count-perm"
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{session_id}.jsonl"
        audit_file.write_text(
            json.dumps({"action": "attempt_started", "intent": "create", "request_origin": "agent"})
            + "\n",
            encoding="utf-8",
        )
        try:
            os.chmod(audit_file, 0o000)
            result = engine_count_session_creates(session_id, tmp_tickets)
            assert result is AUDIT_UNAVAILABLE
        finally:
            os.chmod(audit_file, 0o644)

    def test_count_spans_midnight_boundary(self, tmp_tickets: Path) -> None:
        """Session audit files in multiple date directories are summed."""
        session_id = "sess-midnight"
        for day in ("2026-03-03", "2026-03-04"):
            audit_dir = tmp_tickets / ".audit" / day
            audit_dir.mkdir(parents=True, exist_ok=True)
            audit_file = audit_dir / f"{session_id}.jsonl"
            audit_file.write_text(
                json.dumps(
                    {
                        "action": "attempt_started",
                        "intent": "create",
                        "request_origin": "agent",
                        "ts": f"{day}T00:00:00Z",
                    }
                )
                + "\n",
                encoding="utf-8",
            )
        assert engine_count_session_creates(session_id, tmp_tickets) == 2

    def test_count_cross_midnight_split_pair(self, tmp_tickets: Path) -> None:
        """attempt_started on day N + ok_create result on day N+1 counts as 1."""
        session_id = "sess-split-pair"
        day1 = tmp_tickets / ".audit" / "2026-03-08"
        day1.mkdir(parents=True, exist_ok=True)
        (day1 / f"{session_id}.jsonl").write_text(
            json.dumps({"action": "attempt_started", "intent": "create", "request_origin": "agent"})
            + "\n",
            encoding="utf-8",
        )
        day2 = tmp_tickets / ".audit" / "2026-03-09"
        day2.mkdir(parents=True, exist_ok=True)
        (day2 / f"{session_id}.jsonl").write_text(
            json.dumps({"action": "create", "result": "ok_create", "request_origin": "agent"})
            + "\n",
            encoding="utf-8",
        )
        assert engine_count_session_creates(session_id, tmp_tickets) == 1

    def test_count_cross_midnight_failed_create(self, tmp_tickets: Path) -> None:
        """attempt_started on day N + failed result on day N+1 counts as 0."""
        session_id = "sess-split-fail"
        day1 = tmp_tickets / ".audit" / "2026-03-08"
        day1.mkdir(parents=True, exist_ok=True)
        (day1 / f"{session_id}.jsonl").write_text(
            json.dumps({"action": "attempt_started", "intent": "create", "request_origin": "agent"})
            + "\n",
            encoding="utf-8",
        )
        day2 = tmp_tickets / ".audit" / "2026-03-09"
        day2.mkdir(parents=True, exist_ok=True)
        (day2 / f"{session_id}.jsonl").write_text(
            json.dumps({"action": "create", "result": "escalate", "request_origin": "agent"})
            + "\n",
            encoding="utf-8",
        )
        assert engine_count_session_creates(session_id, tmp_tickets) == 0

    def test_count_no_audit_dir_returns_zero(self, tmp_tickets: Path) -> None:
        """Missing .audit directory returns 0."""
        assert engine_count_session_creates("any-session", tmp_tickets) == 0

    def test_path_traversal_sanitized(self, tmp_tickets: Path) -> None:
        """session_id with path separators is sanitized to prevent traversal."""
        malicious_id = "../../etc/passwd"
        safe_id = ".._.._etc_passwd"
        # Create audit file with sanitized name.
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{safe_id}.jsonl"
        audit_file.write_text(
            json.dumps({"action": "attempt_started", "intent": "create", "request_origin": "agent"})
            + "\n",
            encoding="utf-8",
        )
        # Malicious ID should be sanitized and match the safe file.
        assert engine_count_session_creates(malicious_id, tmp_tickets) == 1

    def test_count_mixed_format_sums_both(self, tmp_tickets: Path) -> None:
        """Mixed legacy + new format entries in same session are both counted."""
        session_id = "sess-count-mixed"
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{session_id}.jsonl"
        lines = [
            # Pre-upgrade: legacy ok_create (no attempt_started with intent)
            json.dumps({"action": "create", "result": "ok_create", "request_origin": "agent"}),
            # Post-upgrade: attempt_started with intent + ok_create result
            json.dumps(
                {"action": "attempt_started", "intent": "create", "request_origin": "agent"}
            ),
            json.dumps({"action": "create", "result": "ok_create", "request_origin": "agent"}),
        ]
        audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # 1 legacy + 1 new-format = 2 total
        assert engine_count_session_creates(session_id, tmp_tickets) == 2

    def test_count_mixed_format_legacy_ok_plus_new_gap(self, tmp_tickets: Path) -> None:
        """Legacy ok_create + new-format gap (no result) counts as 2."""
        session_id = "sess-mixed-gap"
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{session_id}.jsonl"
        lines = [
            # Pre-upgrade: legacy ok_create
            json.dumps({"action": "create", "result": "ok_create", "request_origin": "agent"}),
            # Post-upgrade: attempt_started with no result (gap)
            json.dumps(
                {"action": "attempt_started", "intent": "create", "request_origin": "agent"}
            ),
        ]
        audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # 1 legacy + 1 gap = 2 total
        assert engine_count_session_creates(session_id, tmp_tickets) == 2

    def test_count_mixed_format_two_legacy_plus_new_gap(self, tmp_tickets: Path) -> None:
        """Two legacy ok_creates + new-format gap counts as 3."""
        session_id = "sess-mixed-gap-3"
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{session_id}.jsonl"
        lines = [
            # Pre-upgrade: two legacy ok_creates
            json.dumps({"action": "create", "result": "ok_create", "request_origin": "agent"}),
            json.dumps({"action": "create", "result": "ok_create", "request_origin": "agent"}),
            # Post-upgrade: attempt_started with no result (gap)
            json.dumps(
                {"action": "attempt_started", "intent": "create", "request_origin": "agent"}
            ),
        ]
        audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # 2 legacy + 1 gap = 3 total
        assert engine_count_session_creates(session_id, tmp_tickets) == 3

    def test_count_legacy_ok_create_entries(self, tmp_tickets: Path) -> None:
        """Pre-upgrade audit files with ok_create result entries are counted."""
        session_id = "sess-count-legacy"
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{session_id}.jsonl"
        # Old format: no attempt_started with intent, just result entries.
        lines = [
            json.dumps({"action": "create", "result": "ok_create", "request_origin": "agent"}),
            json.dumps({"action": "create", "result": "ok_create", "request_origin": "agent"}),
        ]
        audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        assert engine_count_session_creates(session_id, tmp_tickets) == 2

    def test_count_failed_create_not_counted(self, tmp_tickets: Path) -> None:
        """Failed creates (non-ok result) are subtracted from attempt count."""
        session_id = "sess-count-failed"
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{session_id}.jsonl"
        lines = [
            # Two attempt_started for create
            json.dumps(
                {"action": "attempt_started", "intent": "create", "request_origin": "agent"}
            ),
            json.dumps({"action": "create", "result": "ok_create", "request_origin": "agent"}),
            json.dumps(
                {"action": "attempt_started", "intent": "create", "request_origin": "agent"}
            ),
            # Second create failed
            json.dumps({"action": "create", "result": "escalate", "request_origin": "agent"}),
        ]
        audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # 2 attempts - 1 failure = 1
        assert engine_count_session_creates(session_id, tmp_tickets) == 1

    def test_count_gap_create_counted(self, tmp_tickets: Path) -> None:
        """Gap creates (attempt_started without result) are conservatively counted."""
        session_id = "sess-count-gap"
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{session_id}.jsonl"
        lines = [
            # One successful create
            json.dumps(
                {"action": "attempt_started", "intent": "create", "request_origin": "agent"}
            ),
            json.dumps({"action": "create", "result": "ok_create", "request_origin": "agent"}),
            # One gap create (attempt_started but no result)
            json.dumps(
                {"action": "attempt_started", "intent": "create", "request_origin": "agent"}
            ),
        ]
        audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")
        # 2 attempts - 0 failures = 2 (gap is conservatively counted)
        assert engine_count_session_creates(session_id, tmp_tickets) == 2


class TestAuditRepairCli:
    def test_audit_repair_dry_run_reports_corruption_without_writing(
        self, tmp_tickets: Path
    ) -> None:
        project_root = tmp_tickets.parents[1]
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / "dry-run.jsonl"
        original = (
            json.dumps({"action": "create", "result": "ok_create"}) + "\n" + "NOT VALID JSON\n"
        )
        audit_file.write_text(original, encoding="utf-8")

        result = _run_audit_cli("repair", "docs/tickets", "--dry-run", cwd=project_root)

        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["state"] == "ok"
        assert payload["data"]["files_scanned"] == 1
        assert payload["data"]["corrupt_files"] == 1
        assert payload["data"]["repaired_files"] == []
        assert payload["data"]["backup_paths"] == []
        assert payload["data"]["issues"]
        assert audit_file.read_text(encoding="utf-8") == original
        assert list(audit_dir.glob("*.bak-*")) == []

    def test_audit_repair_creates_backup_and_rewrites_valid_lines(self, tmp_tickets: Path) -> None:
        project_root = tmp_tickets.parents[1]
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / "rewrite.jsonl"
        valid_one = {"action": "create", "result": "ok_create", "ticket_id": "T-1"}
        valid_two = {"action": "update", "result": "ok_update", "ticket_id": "T-1"}
        audit_file.write_text(
            json.dumps(valid_one) + "\n" + "BROKEN LINE\n" + json.dumps(valid_two),
            encoding="utf-8",
        )

        result = _run_audit_cli("repair", "docs/tickets", "--fix", cwd=project_root)

        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["state"] == "ok"
        assert payload["data"]["files_scanned"] == 1
        assert payload["data"]["corrupt_files"] == 1
        assert payload["data"]["repaired_files"] == [str(audit_file)]
        assert len(payload["data"]["backup_paths"]) == 1

        backup_path = Path(payload["data"]["backup_paths"][0])
        assert backup_path.exists()
        assert backup_path.parent == audit_dir
        assert backup_path.name.startswith("rewrite.jsonl.bak-")
        assert backup_path.read_text(encoding="utf-8") == (
            json.dumps(valid_one) + "\n" + "BROKEN LINE\n" + json.dumps(valid_two)
        )

        repaired_text = audit_file.read_text(encoding="utf-8")
        assert repaired_text == json.dumps(valid_one) + "\n" + json.dumps(valid_two) + "\n"
        assert [json.loads(line) for line in repaired_text.splitlines()] == [valid_one, valid_two]

    def test_audit_repair_ignores_clean_files(self, tmp_tickets: Path) -> None:
        project_root = tmp_tickets.parents[1]
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        clean_file = audit_dir / "clean.jsonl"
        clean_text = json.dumps({"action": "create", "result": "ok_create"}) + "\n"
        clean_file.write_text(clean_text, encoding="utf-8")
        ignored_backup = audit_dir / "clean.jsonl.bak-20260306T000000Z"
        ignored_backup.write_text("NOT JSON\n", encoding="utf-8")

        result = _run_audit_cli("repair", "docs/tickets", "--fix", cwd=project_root)

        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["state"] == "ok"
        assert payload["data"]["files_scanned"] == 1
        assert payload["data"]["corrupt_files"] == 0
        assert payload["data"]["repaired_files"] == []
        assert payload["data"]["backup_paths"] == []
        assert payload["data"]["issues"] == []
        assert clean_file.read_text(encoding="utf-8") == clean_text

    def test_audit_repair_drops_trailing_partial_line(self, tmp_tickets: Path) -> None:
        project_root = tmp_tickets.parents[1]
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / "partial.jsonl"
        valid_entry = {"action": "create", "result": "ok_create", "ticket_id": "T-1"}
        audit_file.write_text(
            json.dumps(valid_entry) + "\n" + '{"action": "close"',
            encoding="utf-8",
        )

        result = _run_audit_cli("repair", "docs/tickets", "--fix", cwd=project_root)

        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["state"] == "ok"
        assert payload["data"]["corrupt_files"] == 1
        assert audit_file.read_text(encoding="utf-8") == json.dumps(valid_entry) + "\n"

    def test_audit_repair_default_is_dry_run(self, tmp_tickets: Path) -> None:
        """Calling repair without --fix defaults to dry-run (no file modification)."""
        project_root = tmp_tickets.parents[1]
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / "default-mode.jsonl"
        original = json.dumps({"action": "create", "result": "ok_create"}) + "\n" + "CORRUPT LINE\n"
        audit_file.write_text(original, encoding="utf-8")

        result = _run_audit_cli("repair", "docs/tickets", cwd=project_root)

        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["data"]["corrupt_files"] == 1
        assert payload["data"]["repaired_files"] == [], "Default should be dry-run"
        assert audit_file.read_text(encoding="utf-8") == original, "File should be unchanged"
        assert list(audit_dir.glob("*.bak-*")) == [], "No backup created in dry-run"

    def test_audit_repair_fix_flag_enables_repair(self, tmp_tickets: Path) -> None:
        """--fix flag enables actual file modification."""
        project_root = tmp_tickets.parents[1]
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / "fix-mode.jsonl"
        valid_entry = {"action": "create", "result": "ok_create"}
        audit_file.write_text(json.dumps(valid_entry) + "\n" + "CORRUPT\n", encoding="utf-8")

        result = _run_audit_cli("repair", "docs/tickets", "--fix", cwd=project_root)

        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["data"]["repaired_files"] == [str(audit_file)]
        assert len(payload["data"]["backup_paths"]) == 1
        assert audit_file.read_text(encoding="utf-8") == json.dumps(valid_entry) + "\n"

    def test_audit_repair_empty_file_is_valid(self, tmp_tickets: Path) -> None:
        """Empty audit file is valid — 0 lines, no corruption."""
        project_root = tmp_tickets.parents[1]
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / "empty.jsonl"
        audit_file.write_text("", encoding="utf-8")

        result = _run_audit_cli("repair", "docs/tickets", "--fix", cwd=project_root)

        assert result.returncode == 0
        payload = json.loads(result.stdout)
        assert payload["data"]["files_scanned"] == 1
        assert payload["data"]["corrupt_files"] == 0
        assert payload["data"]["repaired_files"] == []

    def test_audit_repair_permission_error_reported(self, tmp_tickets: Path) -> None:
        """Permission error reading audit file returns error state."""
        import os

        if sys.platform == "win32":
            pytest.skip("chmod not effective on Windows")

        project_root = tmp_tickets.parents[1]
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / "perm.jsonl"
        audit_file.write_text(json.dumps({"action": "create"}) + "\n", encoding="utf-8")
        try:
            os.chmod(audit_file, 0o000)
            result = _run_audit_cli("repair", "docs/tickets", "--fix", cwd=project_root)
            assert result.returncode == 1
            payload = json.loads(result.stdout)
            assert payload["state"] == "error"
            assert "cannot read" in payload["message"]
        finally:
            os.chmod(audit_file, 0o644)


class TestAuditRepairIntegration:
    """End-to-end: corrupt → repair → count."""

    def test_repair_then_count_returns_correct_count(self, tmp_tickets: Path) -> None:
        """After repairing a corrupt audit file, session counting works correctly."""
        session_id = "sess-repair-count"
        today = datetime.now(UTC).strftime("%Y-%m-%d")
        audit_dir = tmp_tickets / ".audit" / today
        audit_dir.mkdir(parents=True, exist_ok=True)
        audit_file = audit_dir / f"{session_id}.jsonl"

        # Write 3 valid create attempts + 2 corrupt lines
        lines = [
            json.dumps(
                {
                    "action": "attempt_started",
                    "intent": "create",
                    "request_origin": "agent",
                    "ts": "t1",
                }
            ),
            json.dumps({"action": "create", "result": "ok_create", "request_origin": "agent"}),
            "NOT JSON AT ALL",
            json.dumps(
                {
                    "action": "attempt_started",
                    "intent": "create",
                    "request_origin": "agent",
                    "ts": "t2",
                }
            ),
            "ANOTHER BAD LINE {{{",
        ]
        audit_file.write_text("\n".join(lines) + "\n", encoding="utf-8")

        # Before repair: count still works (skips corrupt lines)
        assert engine_count_session_creates(session_id, tmp_tickets) == 2

        # Repair
        from scripts.ticket_audit import repair_audit_logs

        response, exit_code = repair_audit_logs(tickets_dir=tmp_tickets, dry_run=False)
        assert exit_code == 0
        assert response["data"]["corrupt_files"] == 1
        assert response["data"]["repaired_files"] == [str(audit_file)]

        # After repair: count is the same, file is clean
        assert engine_count_session_creates(session_id, tmp_tickets) == 2
        repaired_lines = audit_file.read_text(encoding="utf-8").strip().split("\n")
        assert len(repaired_lines) == 3, "Only 3 valid JSON lines should remain"
        for line in repaired_lines:
            json.loads(line)  # All lines should be valid JSON

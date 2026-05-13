from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import scripts.active_writes as active_writes


def test_begin_active_write_persists_operation_state_before_content_generation(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "begin-active-write",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
            "--operation",
            "save",
            "--slug",
            "next-step",
            "--created-at",
            "2026-05-13T16:45:00Z",
            "--field",
            "operation_state_path",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    operation_state_path = Path(result.stdout.strip())
    payload = json.loads(operation_state_path.read_text(encoding="utf-8"))

    assert payload["schema_version"] == 1
    assert payload["project"] == "demo"
    assert payload["operation"] == "save"
    assert payload["status"] == "begun"
    assert payload["run_id"]
    assert payload["transaction_id"]
    assert payload["idempotency_key"]
    assert payload["bound_slug"] == "next-step"
    assert payload["slug_source"] == "caller"
    assert payload["allocated_active_path"] == str(
        tmp_path / ".codex" / "handoffs" / "2026-05-13_16-45_next-step.md"
    )
    assert payload["operation_state_path"] == str(operation_state_path)
    assert payload["lease_id"]
    assert payload["lease_expires_at"]
    assert payload["transaction_watermark"]
    assert payload["state_snapshot_hash"]

    transaction_path = Path(payload["transaction_path"])
    transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
    assert transaction["operation"] == "save"
    assert transaction["status"] == "pending_before_write"
    assert transaction["allocated_active_path"] == payload["allocated_active_path"]
    assert not (
        tmp_path / ".codex" / "handoffs" / ".session-state" / "locks" / "active-write.lock"
    ).exists()


def test_allocate_active_path_cli_returns_collision_safe_primary_path(tmp_path: Path) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    existing = tmp_path / ".codex" / "handoffs" / "2026-05-13_16-45_repeat.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("existing\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "allocate-active-path",
            "--project-root",
            str(tmp_path),
            "--slug",
            "repeat",
            "--created-at",
            "2026-05-13T16:45:00Z",
            "--field",
            "active_path",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == str(
        tmp_path / ".codex" / "handoffs" / "2026-05-13_16-45_repeat-01.md"
    )
    assert existing.read_text(encoding="utf-8") == "existing\n"


def test_write_active_handoff_commits_reserved_output(tmp_path: Path) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    begin = subprocess.run(
        [
            sys.executable,
            str(script),
            "begin-active-write",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
            "--operation",
            "save",
            "--slug",
            "write-phase",
            "--created-at",
            "2026-05-13T16:45:00Z",
            "--field",
            "operation_state_path",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    operation_state_path = Path(begin.stdout.strip())
    content = "---\ntitle: Write phase\n---\n\n# Handoff\n"
    content_path = tmp_path / "content.md"
    content_path.write_text(content, encoding="utf-8")
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "write-active-handoff",
            "--project-root",
            str(tmp_path),
            "--operation-state-path",
            str(operation_state_path),
            "--content-file",
            str(content_path),
            "--content-sha256",
            content_hash,
            "--field",
            "active_path",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert write.returncode == 0, write.stderr
    active_path = Path(write.stdout.strip())
    assert active_path == tmp_path / ".codex" / "handoffs" / "2026-05-13_16-45_write-phase.md"
    assert active_path.read_text(encoding="utf-8") == content
    state = json.loads(operation_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "committed"
    assert state["content_hash"] == content_hash
    assert state["output_sha256"] == content_hash
    transaction = json.loads(Path(state["transaction_path"]).read_text(encoding="utf-8"))
    assert transaction["status"] == "completed"
    assert transaction["active_path"] == str(active_path)
    assert not (
        tmp_path / ".codex" / "handoffs" / ".session-state" / "locks" / "active-write.lock"
    ).exists()


def test_list_active_writes_reports_pending_operation_state_without_mutation(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    begin = subprocess.run(
        [
            sys.executable,
            str(script),
            "begin-active-write",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
            "--operation",
            "summary",
            "--slug",
            "recover-me",
            "--created-at",
            "2026-05-13T16:45:00Z",
            "--field",
            "operation_state_path",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    operation_state_path = Path(begin.stdout.strip())

    listing = subprocess.run(
        [
            sys.executable,
            str(script),
            "list-active-writes",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
            "--operation",
            "summary",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert listing.returncode == 0, listing.stderr
    payload = json.loads(listing.stdout)
    assert payload["total"] == 1
    assert payload["active_writes"][0]["operation_state_path"] == str(operation_state_path)
    assert payload["active_writes"][0]["status"] == "begun"
    assert not Path(payload["active_writes"][0]["allocated_active_path"]).exists()


def test_write_active_handoff_changed_content_retry_preserves_committed_state(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    begin = subprocess.run(
        [
            sys.executable,
            str(script),
            "begin-active-write",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
            "--operation",
            "quicksave",
            "--slug",
            "retry",
            "--created-at",
            "2026-05-13T16:45:00Z",
            "--field",
            "operation_state_path",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    operation_state_path = Path(begin.stdout.strip())
    original = "---\ntitle: Retry\n---\n\n# Original\n"
    original_path = tmp_path / "original.md"
    original_path.write_text(original, encoding="utf-8")
    original_hash = hashlib.sha256(original.encode("utf-8")).hexdigest()
    subprocess.run(
        [
            sys.executable,
            str(script),
            "write-active-handoff",
            "--project-root",
            str(tmp_path),
            "--operation-state-path",
            str(operation_state_path),
            "--content-file",
            str(original_path),
            "--content-sha256",
            original_hash,
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    changed = "---\ntitle: Retry\n---\n\n# Changed\n"
    changed_path = tmp_path / "changed.md"
    changed_path.write_text(changed, encoding="utf-8")
    changed_hash = hashlib.sha256(changed.encode("utf-8")).hexdigest()

    retry = subprocess.run(
        [
            sys.executable,
            str(script),
            "write-active-handoff",
            "--project-root",
            str(tmp_path),
            "--operation-state-path",
            str(operation_state_path),
            "--content-file",
            str(changed_path),
            "--content-sha256",
            changed_hash,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    state = json.loads(operation_state_path.read_text(encoding="utf-8"))
    assert retry.returncode == 1
    assert "content mismatch" in retry.stderr
    assert state["status"] == "committed"
    assert state["content_hash"] == original_hash
    assert Path(state["active_path"]).read_text(encoding="utf-8") == original


def test_abandon_active_write_marks_operation_and_transaction_without_deleting_output(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    begin = subprocess.run(
        [
            sys.executable,
            str(script),
            "begin-active-write",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
            "--operation",
            "save",
            "--slug",
            "abandon-me",
            "--created-at",
            "2026-05-13T16:45:00Z",
            "--field",
            "operation_state_path",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    operation_state_path = Path(begin.stdout.strip())
    state = json.loads(operation_state_path.read_text(encoding="utf-8"))
    reserved_output = Path(state["allocated_active_path"])
    reserved_output.write_text("operator-owned bytes\n", encoding="utf-8")

    abandoned = subprocess.run(
        [
            sys.executable,
            str(script),
            "abandon-active-write",
            "--project-root",
            str(tmp_path),
            "--operation-state-path",
            str(operation_state_path),
            "--reason",
            "operator selected a new save",
            "--field",
            "status",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert abandoned.returncode == 0, abandoned.stderr
    assert abandoned.stdout.strip() == "abandoned"
    updated = json.loads(operation_state_path.read_text(encoding="utf-8"))
    transaction = json.loads(Path(updated["transaction_path"]).read_text(encoding="utf-8"))
    assert updated["status"] == "abandoned"
    assert updated["abandon_reason"] == "operator selected a new save"
    assert transaction["status"] == "abandoned"
    assert reserved_output.read_text(encoding="utf-8") == "operator-owned bytes\n"


def test_active_write_transaction_recover_commits_verified_written_output(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    begin = subprocess.run(
        [
            sys.executable,
            str(script),
            "begin-active-write",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
            "--operation",
            "summary",
            "--slug",
            "recover-written",
            "--created-at",
            "2026-05-13T16:45:00Z",
            "--field",
            "operation_state_path",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    operation_state_path = Path(begin.stdout.strip())
    state = json.loads(operation_state_path.read_text(encoding="utf-8"))
    active_path = Path(state["allocated_active_path"])
    content = "---\ntitle: Recover\n---\n\n# Written\n"
    active_path.write_text(content, encoding="utf-8")
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    state["status"] = "write-pending"
    state["content_hash"] = content_hash
    state["output_sha256"] = content_hash
    operation_state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    recovered = subprocess.run(
        [
            sys.executable,
            str(script),
            "active-write-transaction-recover",
            "--project-root",
            str(tmp_path),
            "--operation-state-path",
            str(operation_state_path),
            "--field",
            "status",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert recovered.returncode == 0, recovered.stderr
    assert recovered.stdout.strip() == "committed"
    updated = json.loads(operation_state_path.read_text(encoding="utf-8"))
    transaction = json.loads(Path(updated["transaction_path"]).read_text(encoding="utf-8"))
    assert updated["status"] == "committed"
    assert updated["active_path"] == str(active_path)
    assert transaction["status"] == "completed"
    assert transaction["active_path"] == str(active_path)


def test_write_active_handoff_clears_snapshotted_primary_state_after_output_write(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    archive = tmp_path / ".codex" / "handoffs" / "archive" / "previous.md"
    archive.parent.mkdir(parents=True)
    archive.write_text("---\ntitle: Previous\n---\n", encoding="utf-8")
    state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    state_dir.mkdir(parents=True)
    state_path = state_dir / "handoff-demo-resume.json"
    state_path.write_text(
        json.dumps({
            "state_path": str(state_path),
            "project": "demo",
            "resume_token": "resume",
            "archive_path": str(archive),
            "created_at": "2026-05-13T16:00:00Z",
        }),
        encoding="utf-8",
    )
    begin = subprocess.run(
        [
            sys.executable,
            str(script),
            "begin-active-write",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
            "--operation",
            "save",
            "--slug",
            "clears-state",
            "--created-at",
            "2026-05-13T16:45:00Z",
            "--field",
            "operation_state_path",
        ],
        check=True,
        capture_output=True,
        text=True,
    )
    operation_state_path = Path(begin.stdout.strip())
    content = "---\ntitle: Clears state\nresumed_from: previous.md\n---\n\n# Handoff\n"
    content_path = tmp_path / "content.md"
    content_path.write_text(content, encoding="utf-8")
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    write = subprocess.run(
        [
            sys.executable,
            str(script),
            "write-active-handoff",
            "--project-root",
            str(tmp_path),
            "--operation-state-path",
            str(operation_state_path),
            "--content-file",
            str(content_path),
            "--content-sha256",
            content_hash,
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert write.returncode == 0, write.stderr
    assert not state_path.exists()
    state = json.loads(operation_state_path.read_text(encoding="utf-8"))
    transaction = json.loads(Path(state["transaction_path"]).read_text(encoding="utf-8"))
    assert state["state_cleanup_action"] == "cleared-primary-state"
    assert state["state_cleanup_path"] == str(state_path)
    assert transaction["state_cleanup_action"] == "cleared-primary-state"


def test_write_active_handoff_cleanup_failure_remains_recoverable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    archive = tmp_path / ".codex" / "handoffs" / "archive" / "previous.md"
    archive.parent.mkdir(parents=True)
    archive.write_text("---\ntitle: Previous\n---\n", encoding="utf-8")
    state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    state_dir.mkdir(parents=True)
    state_path = state_dir / "handoff-demo-resume.json"
    state_path.write_text(
        json.dumps({
            "state_path": str(state_path),
            "project": "demo",
            "resume_token": "resume",
            "archive_path": str(archive),
            "created_at": "2026-05-13T16:00:00Z",
        }),
        encoding="utf-8",
    )
    reservation = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="cleanup-failure",
        created_at="2026-05-13T16:45:00Z",
    )
    content = "---\ntitle: Cleanup failure\n---\n\n# Handoff\n"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    original_subprocess_run = active_writes.subprocess.run

    def fail_trash(*args: object, **kwargs: object) -> object:
        raise subprocess.CalledProcessError(1, ["trash"], stderr="trash failed")

    monkeypatch.setattr(active_writes.subprocess, "run", fail_trash)

    with pytest.raises(active_writes.ActiveWriteError, match="state cleanup failed"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=reservation.operation_state_path,
            content=content,
            content_sha256=content_hash,
        )

    operation_state = json.loads(reservation.operation_state_path.read_text(encoding="utf-8"))
    active_path = Path(operation_state["active_path"])
    transaction = json.loads(Path(operation_state["transaction_path"]).read_text(encoding="utf-8"))
    assert active_path.read_text(encoding="utf-8") == content
    assert state_path.exists()
    assert operation_state["status"] == "cleanup_failed"
    assert operation_state["content_hash"] == content_hash
    assert operation_state["state_cleanup_action"] == "cleanup_failed"
    assert transaction["status"] == "cleanup_failed"

    monkeypatch.setattr(active_writes.subprocess, "run", original_subprocess_run)

    recovered = active_writes.recover_active_write_transaction(
        tmp_path,
        operation_state_path=reservation.operation_state_path,
    )

    committed_state = json.loads(reservation.operation_state_path.read_text(encoding="utf-8"))
    committed_transaction = json.loads(
        Path(committed_state["transaction_path"]).read_text(encoding="utf-8")
    )
    assert recovered["status"] == "committed"
    assert committed_state["status"] == "committed"
    assert committed_state["state_cleanup_action"] == "cleared-primary-state"
    assert committed_transaction["status"] == "completed"
    assert not state_path.exists()


def test_write_active_handoff_rejects_expired_reservation_before_output_write(
    tmp_path: Path,
) -> None:
    reservation = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="summary",
        slug="expired",
        created_at="2026-05-13T16:45:00Z",
    )
    operation_state = json.loads(reservation.operation_state_path.read_text(encoding="utf-8"))
    operation_state["lease_expires_at"] = "2000-01-01T00:00:00+00:00"
    reservation.operation_state_path.write_text(
        json.dumps(operation_state, indent=2),
        encoding="utf-8",
    )
    content = "---\ntitle: Expired\n---\n\n# Handoff\n"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    with pytest.raises(active_writes.ActiveWriteError, match="reservation expired"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=reservation.operation_state_path,
            content=content,
            content_sha256=content_hash,
        )

    updated = json.loads(reservation.operation_state_path.read_text(encoding="utf-8"))
    active_path = Path(updated["allocated_active_path"])
    transaction = json.loads(Path(updated["transaction_path"]).read_text(encoding="utf-8"))
    assert updated["status"] == "reservation_expired"
    assert transaction["status"] == "reservation_expired"
    assert not active_path.exists()


def test_write_active_handoff_rejects_changed_state_snapshot_before_output_write(
    tmp_path: Path,
) -> None:
    reservation = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="state-conflict",
        created_at="2026-05-13T16:45:00Z",
    )
    state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    conflicting_state = state_dir / "handoff-demo-conflict.json"
    conflicting_state.write_text(
        json.dumps({
            "state_path": str(conflicting_state),
            "project": "demo",
            "resume_token": "conflict",
            "archive_path": "/tmp/other.md",
            "created_at": "2026-05-13T16:01:00Z",
        }),
        encoding="utf-8",
    )
    content = "---\ntitle: State conflict\n---\n\n# Handoff\n"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    with pytest.raises(active_writes.ActiveWriteError, match="state snapshot changed"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=reservation.operation_state_path,
            content=content,
            content_sha256=content_hash,
        )

    updated = json.loads(reservation.operation_state_path.read_text(encoding="utf-8"))
    active_path = Path(updated["allocated_active_path"])
    transaction = json.loads(Path(updated["transaction_path"]).read_text(encoding="utf-8"))
    assert updated["status"] == "reservation_conflict"
    assert updated["conflict_reason"] == "state_snapshot_changed"
    assert transaction["status"] == "reservation_conflict"
    assert not active_path.exists()


def test_write_active_handoff_rejects_changed_transaction_watermark_before_output_write(
    tmp_path: Path,
) -> None:
    reservation = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="transaction-conflict",
        created_at="2026-05-13T16:45:00Z",
    )
    conflict_transaction = (
        tmp_path
        / ".codex"
        / "handoffs"
        / ".session-state"
        / "transactions"
        / "external-conflict.json"
    )
    conflict_transaction.write_text(
        json.dumps({
            "transaction_id": "external-conflict",
            "operation": "load",
            "status": "completed",
        }),
        encoding="utf-8",
    )
    content = "---\ntitle: Transaction conflict\n---\n\n# Handoff\n"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()

    with pytest.raises(active_writes.ActiveWriteError, match="transaction watermark changed"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=reservation.operation_state_path,
            content=content,
            content_sha256=content_hash,
        )

    updated = json.loads(reservation.operation_state_path.read_text(encoding="utf-8"))
    active_path = Path(updated["allocated_active_path"])
    transaction = json.loads(Path(updated["transaction_path"]).read_text(encoding="utf-8"))
    assert updated["status"] == "reservation_conflict"
    assert updated["conflict_reason"] == "transaction_watermark_changed"
    assert transaction["status"] == "reservation_conflict"
    assert not active_path.exists()

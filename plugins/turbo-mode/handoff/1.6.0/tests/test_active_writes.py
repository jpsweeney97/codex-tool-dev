from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path


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

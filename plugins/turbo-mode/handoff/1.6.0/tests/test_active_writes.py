from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from pathlib import Path

import pytest
import scripts.active_writes as active_writes
import scripts.session_state as session_state
from scripts.storage_authority import chain_state_recovery_inventory, read_chain_state


@pytest.mark.parametrize(
    ("operation", "expected_slug"),
    [
        ("save", "handoff"),
        ("summary", "summary"),
        ("quicksave", "checkpoint"),
    ],
)
def test_active_writer_flow_cli_runs_begin_generate_write_protocol(
    tmp_path: Path,
    operation: str,
    expected_slug: str,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "active-writer-flow",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
            "--operation",
            operation,
            "--created-at",
            "2026-05-13T16:45:00Z",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    operation_state_path = Path(payload["operation_state_path"])
    active_path = Path(payload["active_path"])
    state = json.loads(operation_state_path.read_text(encoding="utf-8"))

    assert payload["status"] == "completed"
    assert payload["operation"] == operation
    assert payload["bound_slug"] == expected_slug
    assert payload["content_hash"] == state["content_hash"]
    assert active_path == (
        tmp_path / ".codex" / "handoffs" / f"2026-05-13_16-45_{operation}-{expected_slug}.md"
    )
    assert state["status"] == "committed"
    assert active_path.read_text(encoding="utf-8").startswith("---\n")


@pytest.mark.parametrize(
    ("operation", "expected_slug"),
    [
        ("save", "handoff"),
        ("summary", "summary"),
        ("quicksave", "checkpoint"),
    ],
)
def test_active_writer_flow_cli_bridges_legacy_state_and_marks_source_consumed(
    tmp_path: Path,
    operation: str,
    expected_slug: str,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    archive = tmp_path / "docs" / "handoffs" / "archive" / "previous.md"
    archive.parent.mkdir(parents=True)
    archive.write_text("---\ntitle: Previous\n---\n", encoding="utf-8")
    legacy_state = tmp_path / "docs" / "handoffs" / ".session-state" / "handoff-demo-token-b.json"
    legacy_state.parent.mkdir(parents=True)
    legacy_payload = {
        "state_path": str(legacy_state),
        "project": "demo",
        "resume_token": "token-b",
        "archive_path": str(archive),
        "created_at": "2026-05-13T16:00:00Z",
    }
    legacy_state.write_text(json.dumps(legacy_payload, indent=2), encoding="utf-8")
    legacy_bytes = legacy_state.read_bytes()

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "active-writer-flow",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
            "--operation",
            operation,
            "--run-id",
            f"{operation}-bridge-flow",
            "--created-at",
            "2026-05-13T16:45:00Z",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    operation_state_path = Path(payload["operation_state_path"])
    operation_state = json.loads(operation_state_path.read_text(encoding="utf-8"))
    primary_state = (
        tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-token-b.json"
    )
    inventory = chain_state_recovery_inventory(tmp_path, project_name="demo")
    by_path = {
        candidate["project_relative_state_path"]: candidate
        for candidate in inventory["candidates"]
    }

    assert Path(payload["active_path"]) == (
        tmp_path
        / ".codex"
        / "handoffs"
        / f"2026-05-13_16-45_{operation}-{expected_slug}.md"
    )
    assert operation_state["resumed_from_path"] == str(archive)
    assert operation_state["resumed_from_hash"] == hashlib.sha256(archive.read_bytes()).hexdigest()
    assert operation_state["state_cleanup_action"] == "cleared-primary-state"
    assert operation_state["state_cleanup_path"] == str(primary_state)
    assert primary_state.exists() is False
    assert legacy_state.read_bytes() == legacy_bytes
    assert (
        by_path["docs/handoffs/.session-state/handoff-demo-token-b.json"]["marker_status"]
        == "consumed"
    )
    assert read_chain_state(tmp_path, project_name="demo")["status"] == "absent"


def test_active_writer_flow_cli_reuses_same_run_retry(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    command = [
        sys.executable,
        str(script),
        "active-writer-flow",
        "--project-root",
        str(tmp_path),
        "--project",
        "demo",
        "--operation",
        "save",
        "--run-id",
        "stable-flow",
        "--created-at",
        "2026-05-13T16:45:00Z",
    ]
    first = subprocess.run(command, check=True, capture_output=True, text=True)

    second = subprocess.run(command, check=False, capture_output=True, text=True)

    assert second.returncode == 0, second.stderr
    first_payload = json.loads(first.stdout)
    second_payload = json.loads(second.stdout)
    assert second_payload["transaction_id"] == first_payload["transaction_id"]
    assert second_payload["active_path"] == first_payload["active_path"]
    assert second_payload["status"] == "completed"


def test_active_writer_flow_cli_rejects_changed_content_retry(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    command = [
        sys.executable,
        str(script),
        "active-writer-flow",
        "--project-root",
        str(tmp_path),
        "--project",
        "demo",
        "--operation",
        "save",
        "--run-id",
        "stable-flow",
        "--created-at",
        "2026-05-13T16:45:00Z",
    ]
    first = subprocess.run(command, check=True, capture_output=True, text=True)

    changed = subprocess.run(
        [*command, "--content-note", "changed bytes"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert changed.returncode == 1
    assert "content mismatch" in changed.stderr
    first_payload = json.loads(first.stdout)
    state = json.loads(Path(first_payload["operation_state_path"]).read_text(encoding="utf-8"))
    assert state["status"] == "committed"
    assert state["content_hash"] == first_payload["content_hash"]


def test_active_writer_flow_cli_rejects_slug_change_retry(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    command = [
        sys.executable,
        str(script),
        "active-writer-flow",
        "--project-root",
        str(tmp_path),
        "--project",
        "demo",
        "--operation",
        "save",
        "--run-id",
        "stable-flow",
        "--created-at",
        "2026-05-13T16:45:00Z",
    ]
    first = subprocess.run(command, check=True, capture_output=True, text=True)

    changed_slug = subprocess.run(
        [*command, "--slug", "changed-slug"],
        check=False,
        capture_output=True,
        text=True,
    )

    assert changed_slug.returncode == 1
    assert "another slug" in changed_slug.stderr
    first_payload = json.loads(first.stdout)
    state = json.loads(Path(first_payload["operation_state_path"]).read_text(encoding="utf-8"))
    assert state["status"] == "committed"
    assert state["bound_slug"] == "handoff"
    assert state["active_path"] == first_payload["active_path"]


def test_active_writer_flow_cli_recovers_context_loss_from_inventory(
    tmp_path: Path,
) -> None:
    reservation = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="summary",
        slug="resume-me",
        created_at="2026-05-13T16:45:00Z",
    )
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"

    resumed = subprocess.run(
        [
            sys.executable,
            str(script),
            "active-writer-flow",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
            "--operation",
            "summary",
            "--resume-pending",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert resumed.returncode == 0, resumed.stderr
    payload = json.loads(resumed.stdout)
    assert payload["operation_state_path"] == str(reservation.operation_state_path)
    assert payload["transaction_id"] == reservation.transaction_id
    assert payload["status"] == "completed"
    assert reservation.allocated_active_path.exists()


def test_active_writer_flow_cli_fails_on_ambiguous_pending_inventory(
    tmp_path: Path,
) -> None:
    first = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="summary",
        slug="first",
        created_at="2026-05-13T16:45:00Z",
    )
    state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    chain_state = state_dir / "handoff-demo-resume.json"
    chain_state.write_text(
        json.dumps({"project": "demo", "archive_path": "/tmp/archive.md"}),
        encoding="utf-8",
    )
    second = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="summary",
        slug="second",
        created_at="2026-05-13T16:46:00Z",
    )
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"

    resumed = subprocess.run(
        [
            sys.executable,
            str(script),
            "active-writer-flow",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
            "--operation",
            "summary",
            "--resume-pending",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert resumed.returncode == 1
    assert "expected exactly one pending active write" in resumed.stderr
    assert "Traceback" not in resumed.stderr
    assert first.allocated_active_path.exists() is False
    assert second.allocated_active_path.exists() is False


def test_active_writer_flow_cli_cleanup_failure_remains_recoverable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
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
    original_subprocess_run = active_writes.subprocess.run

    def fail_trash(*args: object, **kwargs: object) -> object:
        if not args or not isinstance(args[0], list) or args[0][:1] != ["trash"]:
            return original_subprocess_run(*args, **kwargs)
        raise subprocess.CalledProcessError(1, ["trash"], stderr="trash failed")

    monkeypatch.setattr(active_writes.subprocess, "run", fail_trash)

    result = session_state.main([
        "active-writer-flow",
        "--project-root",
        str(tmp_path),
        "--project",
        "demo",
        "--operation",
        "save",
        "--run-id",
        "flow-cleanup-failure",
        "--created-at",
        "2026-05-13T16:45:00Z",
    ])

    captured = capsys.readouterr()
    assert result == 1
    assert "state cleanup failed" in captured.err
    assert "Traceback" not in captured.err
    operation_state_path = (
        tmp_path
        / ".codex"
        / "handoffs"
        / ".session-state"
        / "active-writes"
        / "demo"
        / "flow-cleanup-failure.json"
    )
    operation_state = json.loads(operation_state_path.read_text(encoding="utf-8"))
    active_path = Path(operation_state["active_path"])
    transaction = json.loads(Path(operation_state["transaction_path"]).read_text(encoding="utf-8"))
    assert active_path.exists()
    assert state_path.exists()
    assert operation_state["status"] == "cleanup_failed"
    assert operation_state["state_cleanup_action"] == "cleanup_failed"
    assert transaction["status"] == "cleanup_failed"

    monkeypatch.setattr(active_writes.subprocess, "run", original_subprocess_run)

    recovered = active_writes.recover_active_write_transaction(
        tmp_path,
        operation_state_path=operation_state_path,
    )

    committed_state = json.loads(operation_state_path.read_text(encoding="utf-8"))
    assert recovered["status"] == "committed"
    assert committed_state["status"] == "committed"
    assert committed_state["recovered_from_status"] == "cleanup_failed"
    assert committed_state["state_cleanup_action"] == "cleared-primary-state"
    assert not state_path.exists()


@pytest.mark.parametrize(
    ("operation", "slug"),
    [
        ("save", "handoff"),
        ("summary", "summary"),
        ("quicksave", "checkpoint"),
    ],
)
def test_active_writer_flow_cli_allocates_collision_safe_paths_through_02(
    tmp_path: Path,
    operation: str,
    slug: str,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    payloads = []
    for index in range(3):
        result = subprocess.run(
            [
                sys.executable,
                str(script),
                "active-writer-flow",
                "--project-root",
                str(tmp_path),
                "--project",
                "demo",
                "--operation",
                operation,
                "--run-id",
                f"{operation}-collision-{index}",
                "--created-at",
                "2026-05-13T16:45:00Z",
            ],
            check=False,
            capture_output=True,
            text=True,
        )
        assert result.returncode == 0, result.stderr
        payloads.append(json.loads(result.stdout))

    active_dir = tmp_path / ".codex" / "handoffs"
    assert [payload["active_path"] for payload in payloads] == [
        str(active_dir / f"2026-05-13_16-45_{operation}-{slug}.md"),
        str(active_dir / f"2026-05-13_16-45_{operation}-{slug}-01.md"),
        str(active_dir / f"2026-05-13_16-45_{operation}-{slug}-02.md"),
    ]
    assert all(Path(payload["active_path"]).exists() for payload in payloads)


def test_active_writer_flow_releases_lock_during_generation_and_reacquires_for_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    lock_path = (
        tmp_path / ".codex" / "handoffs" / ".session-state" / "locks" / "active-write.lock"
    )
    original_generator = session_state._deterministic_active_writer_content
    observed: dict[str, bool] = {}

    def generate_while_competing_lock_exists(
        operation_state: dict[str, object],
        *,
        content_note: str | None = None,
    ) -> str:
        observed["lock_released_during_generation"] = not lock_path.exists()
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        lock_path.write_text(
            json.dumps({
                "lock_id": "competing-writer",
                "project": "demo",
                "operation": "save",
            }),
            encoding="utf-8",
        )
        return original_generator(operation_state, content_note=content_note)

    monkeypatch.setattr(
        session_state,
        "_deterministic_active_writer_content",
        generate_while_competing_lock_exists,
    )

    result = session_state.main([
        "active-writer-flow",
        "--project-root",
        str(tmp_path),
        "--project",
        "demo",
        "--operation",
        "save",
        "--run-id",
        "flow-lock-reacquire",
        "--created-at",
        "2026-05-13T16:45:00Z",
    ])

    captured = capsys.readouterr()
    assert observed["lock_released_during_generation"] is True
    assert result == 1
    assert "lock is already held" in captured.err
    operation_state_path = (
        tmp_path
        / ".codex"
        / "handoffs"
        / ".session-state"
        / "active-writes"
        / "demo"
        / "flow-lock-reacquire.json"
    )
    operation_state = json.loads(operation_state_path.read_text(encoding="utf-8"))
    assert operation_state["status"] == "begun"
    assert Path(operation_state["allocated_active_path"]).exists() is False


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
    assert operation_state_path.name == f"{payload['run_id']}.json"
    assert payload["transaction_id"]
    assert payload["idempotency_key"]
    assert payload["bound_slug"] == "next-step"
    assert payload["slug_source"] == "caller-predeclared"
    assert payload["allocated_active_path"] == str(
        tmp_path / ".codex" / "handoffs" / "2026-05-13_16-45_save-next-step.md"
    )
    assert payload["operation_state_path"] == str(operation_state_path)
    assert payload["lease_id"]
    assert payload["lease_expires_at"]
    assert payload["transaction_watermark"]
    assert payload["state_snapshot_hash"]
    assert payload["recovery_commands"]["continue"]["command"] == (
        "active-write-transaction-recover"
    )
    assert payload["recovery_commands"]["continue"]["args"]["project_root"] == str(tmp_path)
    assert payload["recovery_commands"]["continue"]["args"]["operation_state_path"] == str(
        operation_state_path
    )
    assert payload["recovery_commands"]["retry_write"]["command"] == "write-active-handoff"
    assert payload["recovery_commands"]["abandon"]["command"] == "abandon-active-write"

    transaction_path = Path(payload["transaction_path"])
    transaction = json.loads(transaction_path.read_text(encoding="utf-8"))
    assert transaction["operation"] == "save"
    assert transaction["status"] == "pending_before_write"
    assert transaction["allocated_active_path"] == payload["allocated_active_path"]
    assert not (
        tmp_path / ".codex" / "handoffs" / ".session-state" / "locks" / "active-write.lock"
    ).exists()


def test_begin_active_write_mints_helper_default_slug_before_content_generation(
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
            "summary",
            "--created-at",
            "2026-05-13T16:45:00Z",
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["bound_slug"] == "summary"
    assert payload["slug_source"] == "helper-default"
    assert payload["allocated_active_path"] == str(
        tmp_path / ".codex" / "handoffs" / "2026-05-13_16-45_summary-summary.md"
    )
    assert not Path(payload["allocated_active_path"]).exists()


def test_allocate_active_path_cli_returns_collision_safe_primary_path(tmp_path: Path) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    existing = tmp_path / ".codex" / "handoffs" / "2026-05-13_16-45_save-repeat.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("existing\n", encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "allocate-active-path",
            "--project-root",
            str(tmp_path),
            "--operation",
            "save",
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
        tmp_path / ".codex" / "handoffs" / "2026-05-13_16-45_save-repeat-01.md"
    )
    assert existing.read_text(encoding="utf-8") == "existing\n"


def test_allocate_active_path_treats_dangling_symlink_as_occupied(tmp_path: Path) -> None:
    existing = tmp_path / ".codex" / "handoffs" / "2026-05-13_16-45_save-repeat.md"
    existing.parent.mkdir(parents=True)
    existing.symlink_to(tmp_path / "missing-target.md")

    active_path = active_writes.allocate_active_path(
        tmp_path,
        operation="save",
        slug="repeat",
        created_at="2026-05-13T16:45:00Z",
    )

    assert active_path == tmp_path / ".codex" / "handoffs" / "2026-05-13_16-45_save-repeat-01.md"


def test_allocate_active_path_treats_tracked_missing_path_as_occupied(tmp_path: Path) -> None:
    subprocess.run(["git", "init"], cwd=tmp_path, check=True, capture_output=True, text=True)
    existing = tmp_path / ".codex" / "handoffs" / "2026-05-13_16-45_save-repeat.md"
    existing.parent.mkdir(parents=True)
    existing.write_text("tracked candidate\n", encoding="utf-8")
    subprocess.run(
        ["git", "add", str(existing.relative_to(tmp_path))],
        cwd=tmp_path,
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(["trash", str(existing)], check=True, capture_output=True, text=True)

    active_path = active_writes.allocate_active_path(
        tmp_path,
        operation="save",
        slug="repeat",
        created_at="2026-05-13T16:45:00Z",
    )

    assert active_path == tmp_path / ".codex" / "handoffs" / "2026-05-13_16-45_save-repeat-01.md"


def test_allocate_active_path_rejects_path_like_slug(tmp_path: Path) -> None:
    with pytest.raises(active_writes.ActiveWriteError, match="slug must be a filename segment"):
        active_writes.allocate_active_path(
            tmp_path,
            operation="save",
            slug="../escape",
            created_at="2026-05-13T16:45:00Z",
        )


def test_allocate_active_path_reports_parent_file_conflict(tmp_path: Path) -> None:
    (tmp_path / ".codex").write_text("not a directory\n", encoding="utf-8")

    with pytest.raises(active_writes.ActiveWriteError, match="parent path conflict"):
        active_writes.allocate_active_path(
            tmp_path,
            operation="save",
            slug="conflict",
            created_at="2026-05-13T16:45:00Z",
        )


def test_begin_active_write_reuses_existing_run_id_reservation(tmp_path: Path) -> None:
    first = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="same-run",
        run_id="stable-run",
        created_at="2026-05-13T16:45:00Z",
    )

    second = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="same-run",
        run_id="stable-run",
        created_at="2026-05-13T17:00:00Z",
    )

    assert second.run_id == first.run_id
    assert second.transaction_id == first.transaction_id
    assert second.operation_state_path == first.operation_state_path
    assert second.allocated_active_path == first.allocated_active_path
    transactions = sorted(
        (tmp_path / ".codex" / "handoffs" / ".session-state" / "transactions").glob("*.json")
    )
    assert transactions == [first.transaction_path]


def test_begin_active_write_rejects_slug_change_for_existing_run_id(tmp_path: Path) -> None:
    first = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="first-slug",
        run_id="stable-run",
        created_at="2026-05-13T16:45:00Z",
    )
    before = json.loads(first.operation_state_path.read_text(encoding="utf-8"))

    with pytest.raises(active_writes.ActiveWriteError, match="another slug"):
        active_writes.begin_active_write(
            tmp_path,
            project_name="demo",
            operation="save",
            slug="changed-slug",
            run_id="stable-run",
            created_at="2026-05-13T17:00:00Z",
        )

    after = json.loads(first.operation_state_path.read_text(encoding="utf-8"))
    transactions = sorted(
        (tmp_path / ".codex" / "handoffs" / ".session-state" / "transactions").glob("*.json")
    )
    assert after == before
    assert transactions == [first.transaction_path]


def test_begin_active_write_rejects_second_live_reservation_for_same_state(
    tmp_path: Path,
) -> None:
    first = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="first",
        created_at="2026-05-13T16:45:00Z",
    )

    with pytest.raises(active_writes.ActiveWriteError, match="active write already reserved"):
        active_writes.begin_active_write(
            tmp_path,
            project_name="demo",
            operation="save",
            slug="second",
            created_at="2026-05-13T16:46:00Z",
        )

    transactions = sorted(
        (tmp_path / ".codex" / "handoffs" / ".session-state" / "transactions").glob("*.json")
    )
    assert transactions == [first.transaction_path]
    assert not (tmp_path / ".codex" / "handoffs" / "2026-05-13_16-46_save-second.md").exists()


def test_begin_active_write_rejects_expired_reservation_until_abandoned(
    tmp_path: Path,
) -> None:
    first = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="expired",
        created_at="2026-05-13T16:45:00Z",
        lease_seconds=-1,
    )

    with pytest.raises(active_writes.ActiveWriteError, match="active write already reserved"):
        active_writes.begin_active_write(
            tmp_path,
            project_name="demo",
            operation="save",
            slug="replacement",
            created_at="2026-05-13T16:46:00Z",
        )

    active_writes.abandon_active_write(
        tmp_path,
        operation_state_path=first.operation_state_path,
        reason="operator abandoned expired reservation",
    )
    replacement = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="replacement",
        created_at="2026-05-13T16:46:00Z",
    )

    transactions = sorted(
        (tmp_path / ".codex" / "handoffs" / ".session-state" / "transactions").glob("*.json")
    )
    assert set(transactions) == {first.transaction_path, replacement.transaction_path}
    assert replacement.allocated_active_path == (
        tmp_path / ".codex" / "handoffs" / "2026-05-13_16-46_save-replacement.md"
    )


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
    assert active_path == tmp_path / ".codex" / "handoffs" / "2026-05-13_16-45_save-write-phase.md"
    assert active_path.read_text(encoding="utf-8") == content
    state = json.loads(operation_state_path.read_text(encoding="utf-8"))
    assert state["status"] == "committed"
    assert state["content_hash"] == content_hash
    assert state["output_sha256"] == content_hash
    transaction = json.loads(Path(state["transaction_path"]).read_text(encoding="utf-8"))
    assert transaction["status"] == "completed"
    assert transaction["active_path"] == str(active_path)
    assert transaction["temp_active_path"].startswith(
        str(active_path.parent / f".{active_path.name}.")
    )
    assert transaction["temp_active_path"].endswith(".tmp")
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


def test_write_active_handoff_records_content_generated_before_output_write(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    reservation = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="save",
        slug="generated-before-write",
        created_at="2026-05-13T16:45:00Z",
    )
    content = "---\ntitle: Generated before write\n---\n\n# Handoff\n"
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    original_write_text = Path.write_text

    def fail_active_temp_write(path: Path, *args: object, **kwargs: object) -> int:
        if path.parent == reservation.allocated_active_path.parent and path.name.startswith("."):
            raise OSError("active temp write failed")
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", fail_active_temp_write)

    with pytest.raises(active_writes.ActiveWriteError, match="active output write failed"):
        active_writes.write_active_handoff(
            tmp_path,
            operation_state_path=reservation.operation_state_path,
            content=content,
            content_sha256=content_hash,
        )

    state = json.loads(reservation.operation_state_path.read_text(encoding="utf-8"))
    transaction = json.loads(reservation.transaction_path.read_text(encoding="utf-8"))
    assert state["status"] == "content-generated"
    assert state["content_hash"] == content_hash
    assert transaction["status"] == "content-generated"
    assert transaction["content_hash"] == content_hash


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
    state["status"] = "written_not_confirmed"
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
    assert updated["recovered_from_status"] == "written_not_confirmed"
    assert transaction["status"] == "completed"
    assert transaction["active_path"] == str(active_path)
    assert transaction["recovered_from_status"] == "written_not_confirmed"


def test_active_write_transaction_recover_records_content_mismatch(
    tmp_path: Path,
) -> None:
    reservation = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="summary",
        slug="mismatch",
        created_at="2026-05-13T16:45:00Z",
    )
    expected = "---\ntitle: Expected\n---\n\n# Expected\n"
    expected_hash = hashlib.sha256(expected.encode("utf-8")).hexdigest()
    reservation.allocated_active_path.write_text(
        "---\ntitle: Different\n---\n\n# Different\n",
        encoding="utf-8",
    )
    state = json.loads(reservation.operation_state_path.read_text(encoding="utf-8"))
    state["status"] = "written_not_confirmed"
    state["content_hash"] = expected_hash
    state["output_sha256"] = expected_hash
    reservation.operation_state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    with pytest.raises(active_writes.ActiveWriteError, match="content mismatch"):
        active_writes.recover_active_write_transaction(
            tmp_path,
            operation_state_path=reservation.operation_state_path,
        )

    updated = json.loads(reservation.operation_state_path.read_text(encoding="utf-8"))
    transaction = json.loads(reservation.transaction_path.read_text(encoding="utf-8"))
    assert updated["status"] == "content_mismatch"
    assert transaction["status"] == "content_mismatch"
    assert transaction["active_path"] == str(reservation.allocated_active_path)


def test_active_write_transaction_recover_records_pending_before_write(
    tmp_path: Path,
) -> None:
    reservation = active_writes.begin_active_write(
        tmp_path,
        project_name="demo",
        operation="summary",
        slug="pending",
        created_at="2026-05-13T16:45:00Z",
    )
    state = json.loads(reservation.operation_state_path.read_text(encoding="utf-8"))
    state["status"] = "written_not_confirmed"
    state["content_hash"] = hashlib.sha256(b"missing output").hexdigest()
    state["output_sha256"] = state["content_hash"]
    reservation.operation_state_path.write_text(json.dumps(state, indent=2), encoding="utf-8")

    recovered = active_writes.recover_active_write_transaction(
        tmp_path,
        operation_state_path=reservation.operation_state_path,
    )

    transaction = json.loads(reservation.transaction_path.read_text(encoding="utf-8"))
    assert recovered["status"] == "pending_before_write"
    assert transaction["status"] == "pending_before_write"
    assert transaction["active_path"] == str(reservation.allocated_active_path)


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

from __future__ import annotations

import json
import stat
import subprocess
from pathlib import Path

import pytest
import refresh.lock_state as lock_state_module
from refresh.lock_state import (
    LockOwner,
    RunState,
    acquire_refresh_lock,
    clear_run_state,
    preserve_original_owner_for_recovery,
    read_run_state,
    replace_run_state,
    update_run_state_phase,
    validate_cache_install_allowed,
    validate_hook_disable_allowed,
    validate_recovery_owner_identity,
    validate_recovery_run_state,
    validate_smoke_allowed,
    write_initial_run_state,
)
from refresh.models import RefreshError

RUN_ID = "run-001"
MODE = "guarded-refresh"
SOURCE_COMMIT = "source-commit"
SOURCE_TREE = "source-tree"
EXECUTION_HEAD = "execution-head"
EXECUTION_TREE = "execution-tree"
TOOL_SHA256 = "tool-sha"


def base_state(*, phase: str = "marker-started", **overrides: object) -> RunState:
    values = {
        "run_id": RUN_ID,
        "mode": MODE,
        "source_implementation_commit": SOURCE_COMMIT,
        "source_implementation_tree": SOURCE_TREE,
        "execution_head": EXECUTION_HEAD,
        "execution_tree": EXECUTION_TREE,
        "tool_sha256": TOOL_SHA256,
        "phase": phase,
        **overrides,
    }
    return RunState(**values)


def snapshot_ready_state() -> RunState:
    return base_state(
        phase="snapshot-written",
        pre_snapshot_app_server_launch_authority_sha256="launch-sha",
        original_config_sha256="original-config",
        pre_refresh_cache_manifest_sha256={"handoff": "handoff-pre", "ticket": "ticket-pre"},
        snapshot_path_map={"config": "/tmp/snapshot/config.toml"},
        snapshot_manifest_digest="snapshot-manifest",
        recovery_eligibility="restore-cache-and-config",
    )


def install_ready_state() -> RunState:
    return base_state(
        phase="install-complete",
        pre_snapshot_app_server_launch_authority_sha256="launch-sha",
        pre_install_app_server_target_authority_sha256="target-sha",
        plugin_hooks_start_state="true",
        original_config_sha256="original-config",
        expected_intermediate_config_sha256="disabled-config",
        hook_disabled_config_sha256="disabled-config",
        pre_refresh_cache_manifest_sha256={"handoff": "handoff-pre", "ticket": "ticket-pre"},
        post_install_cache_manifest_sha256={"handoff": "handoff-post", "ticket": "ticket-post"},
        snapshot_path_map={"config": "/tmp/snapshot/config.toml"},
        snapshot_manifest_digest="snapshot-manifest",
        recovery_eligibility="restore-cache-and-config",
    )


def owner(
    *,
    pid: int = 1234,
    observed_process_start: str = "Thu May  7 10:00:00 2026",
) -> LockOwner:
    return LockOwner(
        run_id=RUN_ID,
        mode=MODE,
        source_implementation_commit=SOURCE_COMMIT,
        execution_head=EXECUTION_HEAD,
        tool_sha256=TOOL_SHA256,
        pid=pid,
        parent_pid=99,
        observed_process_start=observed_process_start,
        raw_owner_process_row_sha256="row-sha",
        acquisition_timestamp="2026-05-07T10:00:00Z",
        command_line_sequence=("python3", "refresh.py"),
    )


def test_initial_state_creates_private_root_and_run_state_directory(tmp_path: Path) -> None:
    state = base_state()
    path = write_initial_run_state(tmp_path / "isolated-home/local-only/turbo-mode-refresh", state)
    root = path.parents[1]
    run_state_dir = root / "run-state"
    assert stat.S_IMODE(root.stat().st_mode) == 0o700
    assert stat.S_IMODE(run_state_dir.stat().st_mode) == 0o700
    assert str(path).startswith(str(tmp_path))
    assert not str(path).startswith("/Users/jp/.codex")


def test_lock_owner_and_marker_files_are_private(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(lock_state_module, "_collect_owner_process_row", lambda pid: owner(pid=pid))
    local_only_root = tmp_path / "home/local-only/turbo-mode-refresh"
    with acquire_refresh_lock(
        local_only_root=local_only_root,
        run_id=RUN_ID,
        mode=MODE,
        source_implementation_commit=SOURCE_COMMIT,
        execution_head=EXECUTION_HEAD,
        tool_sha256=TOOL_SHA256,
    ) as active_owner:
        owner_path = local_only_root / "run-state" / f"{RUN_ID}.owner.json"
        assert active_owner.run_id == RUN_ID
        assert stat.S_IMODE(owner_path.stat().st_mode) == 0o600
    marker_path = write_initial_run_state(local_only_root, base_state())
    assert stat.S_IMODE(marker_path.stat().st_mode) == 0o600


def test_nonblocking_lock_acquisition_fails_while_descriptor_holds_lock(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setattr(lock_state_module, "_collect_owner_process_row", lambda pid: owner(pid=pid))
    kwargs = {
        "local_only_root": tmp_path / "home/local-only/turbo-mode-refresh",
        "run_id": RUN_ID,
        "mode": MODE,
        "source_implementation_commit": SOURCE_COMMIT,
        "execution_head": EXECUTION_HEAD,
        "tool_sha256": TOOL_SHA256,
    }
    with acquire_refresh_lock(**kwargs):
        with pytest.raises(RefreshError, match="refresh lock is already held"):
            with acquire_refresh_lock(**kwargs):
                pass


def test_preserve_original_owner_for_recovery_copies_owner_before_recovery_owner(
    tmp_path: Path,
) -> None:
    local_only_root = tmp_path / "home/local-only/turbo-mode-refresh"
    owner_path = local_only_root / "run-state" / f"{RUN_ID}.owner.json"
    lock_state_module.write_owner_file(owner_path, owner())
    recovery_owner_path = local_only_root / "run-state" / f"{RUN_ID}.recovery-owner.json"
    result = preserve_original_owner_for_recovery(local_only_root, RUN_ID, owner_path)
    assert Path(result["preserved_owner_path"]).exists()
    assert Path(result["preserved_owner_path"]).read_text(encoding="utf-8") == owner_path.read_text(
        encoding="utf-8"
    )
    assert not recovery_owner_path.exists()


def test_phase_only_update_rejects_recovery_critical_phase(tmp_path: Path) -> None:
    local_only_root = tmp_path / "home/local-only/turbo-mode-refresh"
    write_initial_run_state(local_only_root, base_state())
    with pytest.raises(RefreshError, match="phase-only update"):
        update_run_state_phase(local_only_root, RUN_ID, "snapshot-written")


def test_phase_only_update_allows_process_checked_phase(tmp_path: Path) -> None:
    local_only_root = tmp_path / "home/local-only/turbo-mode-refresh"
    write_initial_run_state(local_only_root, base_state())
    update_run_state_phase(local_only_root, RUN_ID, "before-snapshot-process-checked")
    assert read_run_state(local_only_root, RUN_ID).phase == "before-snapshot-process-checked"


def test_full_state_replacement_persists_recovery_critical_fields(tmp_path: Path) -> None:
    local_only_root = tmp_path / "home/local-only/turbo-mode-refresh"
    write_initial_run_state(local_only_root, base_state())
    replace_run_state(local_only_root, install_ready_state())
    persisted = read_run_state(local_only_root, RUN_ID)
    assert persisted.pre_snapshot_app_server_launch_authority_sha256 == "launch-sha"
    assert persisted.snapshot_path_map == {"config": "/tmp/snapshot/config.toml"}
    assert persisted.snapshot_manifest_digest == "snapshot-manifest"
    assert persisted.original_config_sha256 == "original-config"
    assert persisted.hook_disabled_config_sha256 == "disabled-config"
    assert persisted.pre_install_app_server_target_authority_sha256 == "target-sha"
    assert persisted.post_install_cache_manifest_sha256 == {
        "handoff": "handoff-post",
        "ticket": "ticket-post",
    }
    assert persisted.recovery_eligibility == "restore-cache-and-config"


def test_hook_disable_requires_snapshot_metadata_and_recovery_eligibility() -> None:
    with pytest.raises(RefreshError, match="snapshot marker"):
        validate_hook_disable_allowed(
            base_state(pre_snapshot_app_server_launch_authority_sha256="launch-sha")
        )
    validate_hook_disable_allowed(snapshot_ready_state())


@pytest.mark.parametrize(
    "validator",
    [validate_hook_disable_allowed, validate_cache_install_allowed, validate_smoke_allowed],
)
def test_mutation_scaffolding_requires_pre_snapshot_launch_authority(validator: object) -> None:
    with pytest.raises(RefreshError, match="pre-snapshot app-server launch authority"):
        validator(base_state())


def test_owner_identity_collected_with_ps_lstart_and_raw_row_sha256(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = subprocess.CompletedProcess(
        ["ps"],
        0,
        stdout=" 4321  123 Thu May  7 10:00:00 2026 python3 refresh.py --guarded-refresh\n",
        stderr="",
    )

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert command == ["ps", "-ww", "-o", "pid=,ppid=,lstart=,command=", "-p", "4321"]
        assert kwargs["capture_output"] is True
        assert kwargs["text"] is True
        assert kwargs["check"] is True
        return completed

    monkeypatch.setattr(lock_state_module.subprocess, "run", fake_run)
    collected = lock_state_module.collect_owner_identity(
        pid=4321,
        run_id=RUN_ID,
        mode=MODE,
        source_implementation_commit=SOURCE_COMMIT,
        execution_head=EXECUTION_HEAD,
        tool_sha256=TOOL_SHA256,
    )
    assert collected.pid == 4321
    assert collected.parent_pid == 123
    assert collected.observed_process_start == "Thu May  7 10:00:00 2026"
    assert collected.raw_owner_process_row_sha256
    assert collected.command_line_sequence == ("python3", "refresh.py", "--guarded-refresh")


def test_recovery_rejects_pid_reuse_with_different_lstart() -> None:
    stale_owner = owner(pid=4321, observed_process_start="Thu May  7 10:00:00 2026")
    current_owner = owner(pid=4321, observed_process_start="Thu May  7 10:30:00 2026")
    with pytest.raises(RefreshError, match="PID reuse"):
        validate_recovery_owner_identity(stale_owner, current_owner)


def test_recovery_rejects_marker_run_id_mismatch() -> None:
    state = base_state(run_id="other-run")
    with pytest.raises(RefreshError, match="run id mismatch"):
        validate_recovery_run_state(state, expected_run_id=RUN_ID)


def test_clear_run_state_removes_marker_file(tmp_path: Path) -> None:
    local_only_root = tmp_path / "home/local-only/turbo-mode-refresh"
    path = write_initial_run_state(local_only_root, base_state())
    clear_run_state(local_only_root, RUN_ID)
    assert not path.exists()


def test_run_state_json_contains_schema_version(tmp_path: Path) -> None:
    local_only_root = tmp_path / "home/local-only/turbo-mode-refresh"
    path = write_initial_run_state(local_only_root, base_state())
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["schema_version"] == "turbo-mode-refresh-run-state-v1"

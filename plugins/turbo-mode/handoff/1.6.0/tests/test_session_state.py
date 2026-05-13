from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.session_state import (
    AmbiguousResumeStateError,
    allocate_archive_path,
    clear_resume_state,
    load_resume_state,
    prune_old_state_files,
    write_resume_state,
)


def test_allocate_archive_path_avoids_overwrite(tmp_path: Path) -> None:
    archive_dir = tmp_path / "archive"
    archive_dir.mkdir()
    source = tmp_path / "2026-05-02_05-26_summary-test.md"
    source.write_text("content", encoding="utf-8")
    (archive_dir / source.name).write_text("old", encoding="utf-8")
    path = allocate_archive_path(source, archive_dir)
    assert path.name == "2026-05-02_05-26_summary-test-01.md"


def test_write_resume_state_uses_temp_file_before_final_rename(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    writes: list[Path] = []
    original_write_text = Path.write_text

    def write_spy(path: Path, *args: object, **kwargs: object) -> int:
        if path.parent == tmp_path:
            writes.append(path)
        return original_write_text(path, *args, **kwargs)

    monkeypatch.setattr(Path, "write_text", write_spy)

    state_path = write_resume_state(tmp_path, "demo", "/tmp/archive.md", "token-a")

    assert writes
    assert writes[0] != state_path
    assert writes[0].parent == state_path.parent
    assert not writes[0].exists()
    assert json.loads(state_path.read_text(encoding="utf-8"))["archive_path"] == "/tmp/archive.md"


def test_load_resume_state_rejects_multiple_pending_states(tmp_path: Path) -> None:
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    write_resume_state(state_dir, "demo", "/tmp/archive-a.md", "token-a")
    write_resume_state(state_dir, "demo", "/tmp/archive-b.md", "token-b")
    with pytest.raises(AmbiguousResumeStateError):
        load_resume_state(state_dir, "demo")


def test_load_resume_state_migrates_legacy_plain_text_state(tmp_path: Path) -> None:
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    legacy = state_dir / "handoff-demo"
    legacy.write_text("/tmp/archive-legacy.md", encoding="utf-8")
    state = load_resume_state(state_dir, "demo")
    assert state is not None
    assert state.archive_path == "/tmp/archive-legacy.md"
    assert state.resume_token
    assert Path(state.state_path).exists()
    assert Path(state.state_path).name.startswith("handoff-demo-")


def test_load_resume_state_ignores_consumed_legacy_marker(tmp_path: Path) -> None:
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    legacy = state_dir / "handoff-demo"
    legacy.write_text("MIGRATED:/tmp/handoff-demo-token.json\n", encoding="utf-8")
    assert load_resume_state(state_dir, "demo") is None


def test_clear_resume_state_removes_file(tmp_path: Path) -> None:
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    state_path = write_resume_state(state_dir, "demo", "/tmp/archive-a.md", "token-a")
    cleared = clear_resume_state(state_dir, str(state_path))
    assert cleared is True
    assert not state_path.exists()


def test_clear_resume_state_also_clears_matching_legacy_bridge(tmp_path: Path) -> None:
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    legacy = state_dir / "handoff-demo"
    legacy.write_text("/tmp/archive-a.md", encoding="utf-8")
    state_path = write_resume_state(state_dir, "demo", "/tmp/archive-a.md", "token-a")
    cleared = clear_resume_state(state_dir, str(state_path))
    assert cleared is True
    assert not state_path.exists()
    assert not legacy.exists()


def test_clear_resume_state_rejects_empty_path(tmp_path: Path) -> None:
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    with pytest.raises(ValueError, match="state path must be non-empty"):
        clear_resume_state(state_dir, "")


def test_clear_resume_state_rejects_directory_path(tmp_path: Path) -> None:
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    with pytest.raises(ValueError, match="state path must point to a file"):
        clear_resume_state(state_dir, str(state_dir))


def test_clear_resume_state_rejects_non_state_filename(tmp_path: Path) -> None:
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    rogue = state_dir / "not-a-state.txt"
    rogue.write_text("bad", encoding="utf-8")
    with pytest.raises(ValueError, match="handoff-\\*"):
        clear_resume_state(state_dir, str(rogue))


def test_clear_resume_state_warns_when_trash_fails(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    state_path = write_resume_state(state_dir, "demo", "/tmp/archive-a.md", "token-a")

    def _fail(*args: object, **kwargs: object) -> object:
        raise subprocess.CalledProcessError(returncode=1, cmd=["trash"], stderr="boom")

    monkeypatch.setattr(subprocess, "run", _fail)
    cleared = clear_resume_state(state_dir, str(state_path))
    assert cleared is False
    assert state_path.exists()
    assert "state cleanup warning" in capsys.readouterr().err


def test_migrated_legacy_marker_prevents_resume_chain_resurrection(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    legacy = state_dir / "handoff-demo"
    legacy.write_text("/tmp/archive-legacy.md", encoding="utf-8")

    def _fail_for_legacy(command: list[str], **kwargs: object) -> object:
        target = command[-1]
        if target.endswith("handoff-demo"):
            raise subprocess.CalledProcessError(returncode=1, cmd=command, stderr="boom")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr(subprocess, "run", _fail_for_legacy)
    state = load_resume_state(state_dir, "demo")
    assert state is not None
    assert legacy.read_text(encoding="utf-8").startswith("MIGRATED:")
    state_again = load_resume_state(state_dir, "demo")
    assert state_again is not None
    assert state_again.state_path == state.state_path


def test_prune_old_state_files_cleans_legacy_state_file(tmp_path: Path) -> None:
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    legacy = state_dir / "handoff-demo"
    legacy.write_text("/tmp/archive-legacy.md", encoding="utf-8")
    old = legacy.stat().st_mtime - (25 * 60 * 60)
    os.utime(legacy, (old, old))
    deleted = prune_old_state_files(state_dir=state_dir)
    assert legacy in deleted


def test_session_state_cli_round_trip(tmp_path: Path) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    source = tmp_path / "handoff.md"
    source.write_text("hello", encoding="utf-8")
    archive_dir = tmp_path / "archive"
    state_dir = tmp_path / ".session-state"

    archive = subprocess.run(
        [
            sys.executable,
            str(script),
            "archive",
            "--source",
            str(source),
            "--archive-dir",
            str(archive_dir),
            "--field",
            "archived_path",
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert archive.returncode == 0, archive.stderr

    write_state = subprocess.run(
        [
            sys.executable,
            str(script),
            "write-state",
            "--state-dir",
            str(state_dir),
            "--project",
            "demo",
            "--archive-path",
            archive.stdout.strip(),
            "--field",
            "state_path",
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert write_state.returncode == 0, write_state.stderr

    read_state = subprocess.run(
        [
            sys.executable,
            str(script),
            "read-state",
            "--state-dir",
            str(state_dir),
            "--project",
            "demo",
            "--field",
            "archive_path",
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert read_state.returncode == 0, read_state.stderr
    assert read_state.stdout.strip() == archive.stdout.strip()

    clear_state = subprocess.run(
        [
            sys.executable,
            str(script),
            "clear-state",
            "--state-dir",
            str(state_dir),
            "--state-path",
            write_state.stdout.strip(),
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert clear_state.returncode == 0, clear_state.stderr


def test_read_state_returns_1_when_absent(tmp_path: Path) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    state_dir = tmp_path / ".session-state"
    state_dir.mkdir()
    read_state = subprocess.run(
        [
            sys.executable,
            str(script),
            "read-state",
            "--state-dir",
            str(state_dir),
            "--project",
            "demo",
            "--field",
            "state_path",
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )
    assert read_state.returncode == 1


def test_chain_state_recovery_inventory_cli_reports_state_identity_without_mutation(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    primary = tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-token-a.json"
    legacy = tmp_path / "docs" / "handoffs" / ".session-state" / "handoff-demo-token-b.json"
    residue = tmp_path / "docs" / "handoffs" / "handoff-demo"
    archive = tmp_path / ".codex" / "handoffs" / "archive" / "previous.md"
    primary.parent.mkdir(parents=True, exist_ok=True)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    residue.parent.mkdir(parents=True, exist_ok=True)
    archive.parent.mkdir(parents=True, exist_ok=True)
    archive.write_text("---\ntitle: Previous\n---\n", encoding="utf-8")
    primary.write_text(
        json.dumps({
            "state_path": str(primary),
            "project": "demo",
            "resume_token": "token-a",
            "archive_path": str(archive),
            "created_at": "2026-05-13T16:00:00Z",
        }),
        encoding="utf-8",
    )
    legacy_payload = {
        "state_path": str(legacy),
        "project": "demo",
        "resume_token": "token-b",
        "archive_path": str(archive),
        "created_at": "2026-05-13T16:01:00Z",
    }
    legacy.write_text(json.dumps(legacy_payload), encoding="utf-8")
    residue.write_text(str(archive), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "chain-state-recovery-inventory",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["project"] == "demo"
    by_path = {
        candidate["project_relative_state_path"]: candidate
        for candidate in payload["candidates"]
    }
    primary_row = by_path[".codex/handoffs/.session-state/handoff-demo-token-a.json"]
    legacy_row = by_path["docs/handoffs/.session-state/handoff-demo-token-b.json"]
    residue_row = by_path["docs/handoffs/handoff-demo"]
    assert primary_row["source_root"] == "primary"
    assert primary_row["storage_location"] == "primary_state"
    assert primary_row["project"] == "demo"
    assert primary_row["resume_token"] == "token-a"
    assert primary_row["detected_format"] == "tokenized-json"
    assert primary_row["validation_status"] == "valid"
    assert legacy_row["source_root"] == "legacy"
    assert legacy_row["storage_location"] == "legacy_state"
    assert legacy_row["resume_token"] == "token-b"
    assert residue_row["storage_location"] == "state_like_residue"
    assert residue_row["detected_format"] == "plain-state"
    assert residue_row["archive_path"] == str(archive)
    assert legacy.read_text(encoding="utf-8") == json.dumps(legacy_payload)
    assert not (tmp_path / ".codex" / "handoffs" / ".session-state" / "markers").exists()


def test_read_chain_state_cli_fails_ambiguous_primary_with_recovery_inventory(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    state_dir = tmp_path / ".codex" / "handoffs" / ".session-state"
    state_dir.mkdir(parents=True, exist_ok=True)
    for token in ("token-a", "token-b"):
        state = state_dir / f"handoff-demo-{token}.json"
        state.write_text(
            json.dumps({
                "state_path": str(state),
                "project": "demo",
                "resume_token": token,
                "archive_path": f"/tmp/{token}.md",
                "created_at": "2026-05-13T16:00:00Z",
            }),
            encoding="utf-8",
        )

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "read-chain-state",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "ambiguous-primary-chain-state"
    assert payload["error"]["recovery_inventory_command"]["command"] == (
        "chain-state-recovery-inventory"
    )
    assert payload["error"]["recovery_choices"] == [
        "continue-chain-state",
        "abandon-primary-chain-state",
        "abort",
    ]
    assert len(payload["candidates"]) == 2
    assert sorted(candidate["resume_token"] for candidate in payload["candidates"]) == [
        "token-a",
        "token-b",
    ]
    assert not (state_dir / "markers").exists()


def test_read_chain_state_cli_rejects_primary_with_unresolved_legacy(
    tmp_path: Path,
) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    primary = tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-token-a.json"
    legacy = tmp_path / "docs" / "handoffs" / ".session-state" / "handoff-demo-token-b.json"
    primary.parent.mkdir(parents=True, exist_ok=True)
    legacy.parent.mkdir(parents=True, exist_ok=True)
    primary.write_text(
        json.dumps({
            "state_path": str(primary),
            "project": "demo",
            "resume_token": "token-a",
            "archive_path": "/tmp/primary.md",
            "created_at": "2026-05-13T16:00:00Z",
        }),
        encoding="utf-8",
    )
    legacy.write_text(
        json.dumps({
            "state_path": str(legacy),
            "project": "demo",
            "resume_token": "token-b",
            "archive_path": "/tmp/legacy.md",
            "created_at": "2026-05-13T16:01:00Z",
        }),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "read-chain-state",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 2
    payload = json.loads(result.stdout)
    assert payload["error"]["code"] == "primary-chain-state-with-unresolved-legacy"
    assert payload["error"]["recovery_choices"] == [
        "mark-chain-state-consumed",
        "abandon-primary-chain-state",
        "abort",
    ]
    assert sorted(candidate["storage_location"] for candidate in payload["candidates"]) == [
        "legacy_state",
        "primary_state",
    ]
    assert not (primary.parent / "markers").exists()


def test_read_chain_state_cli_reads_single_primary_state(tmp_path: Path) -> None:
    script = Path(__file__).parent.parent / "scripts" / "session_state.py"
    primary = tmp_path / ".codex" / "handoffs" / ".session-state" / "handoff-demo-token-a.json"
    primary.parent.mkdir(parents=True, exist_ok=True)
    primary.write_text(
        json.dumps({
            "state_path": str(primary),
            "project": "demo",
            "resume_token": "token-a",
            "archive_path": "/tmp/primary.md",
            "created_at": "2026-05-13T16:00:00Z",
        }),
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(script),
            "read-chain-state",
            "--project-root",
            str(tmp_path),
            "--project",
            "demo",
        ],
        capture_output=True,
        text=True,
        cwd=str(tmp_path),
    )

    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "found"
    assert payload["source"] == "primary"
    assert payload["state"]["project_relative_state_path"] == (
        ".codex/handoffs/.session-state/handoff-demo-token-a.json"
    )
    assert payload["state"]["resume_token"] == "token-a"


def _residue_snapshot(root: Path, patterns: list[str]) -> set[str]:
    return {
        str(match.relative_to(root))
        for pattern in patterns
        for match in root.glob(pattern)
    }


def _plugin_residue_snapshot(plugin_root: Path) -> set[str]:
    return _residue_snapshot(
        plugin_root,
        ["**/__pycache__", "**/*.pyc", ".venv", ".pytest_cache", ".DS_Store"],
    )


def _project_residue_snapshot(project_root: Path) -> set[str]:
    return _residue_snapshot(
        project_root,
        [
            ".codex/plugin-runtimes/handoff-1.6.0",
            ".codex/plugin-runtimes/handoff-1.6.0/.lock",
            "**/__pycache__",
            "**/*.pyc",
        ],
    )


def test_state_shell_snippet_preserves_exit_2(tmp_path: Path) -> None:
    plugin_root = Path(__file__).parent.parent
    plugin_before = _plugin_residue_snapshot(plugin_root)
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True, text=True)
    state_dir = tmp_path / "docs" / "handoffs" / ".session-state"
    state_dir.mkdir(parents=True)
    runtime_env = tmp_path / ".codex" / "plugin-runtimes" / "handoff-1.6.0"
    project_before = _project_residue_snapshot(tmp_path)
    write_resume_state(state_dir, "demo", "/tmp/archive-a.md", "token-a")
    write_resume_state(state_dir, "demo", "/tmp/archive-b.md", "token-b")
    shell = f'''
PLUGIN_ROOT="{plugin_root}"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
READ_STATE_OUTPUT="$(
  PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/session_state.py" read-state --state-dir "{state_dir}" --project demo --field state_path 2>&1
)"
READ_STATE_STATUS=$?
case "$READ_STATE_STATUS" in
  0) STATE_PATH="$READ_STATE_OUTPUT" ;;
  1) STATE_PATH="" ;;
  2) exit 2 ;;
  *) exit "$READ_STATE_STATUS" ;;
esac
'''
    result = subprocess.run(["/bin/zsh", "-lc", shell], cwd=str(tmp_path))
    assert result.returncode == 2
    assert not runtime_env.exists()
    assert _plugin_residue_snapshot(plugin_root) == plugin_before
    assert _project_residue_snapshot(tmp_path) == project_before


def test_state_shell_snippet_skips_clear_when_absent(tmp_path: Path) -> None:
    plugin_root = Path(__file__).parent.parent
    plugin_before = _plugin_residue_snapshot(plugin_root)
    subprocess.run(["git", "init"], cwd=str(tmp_path), check=True, capture_output=True, text=True)
    state_dir = tmp_path / "docs" / "handoffs" / ".session-state"
    state_dir.mkdir(parents=True)
    runtime_env = tmp_path / ".codex" / "plugin-runtimes" / "handoff-1.6.0"
    project_before = _project_residue_snapshot(tmp_path)
    shell = f'''
PLUGIN_ROOT="{plugin_root}"
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
READ_STATE_OUTPUT="$(
  PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/session_state.py" read-state --state-dir "{state_dir}" --project demo --field state_path 2>&1
)"
READ_STATE_STATUS=$?
printf 'READ_STATE_STATUS=%s\\n' "$READ_STATE_STATUS"
case "$READ_STATE_STATUS" in
  0) STATE_PATH="$READ_STATE_OUTPUT" ;;
  1) STATE_PATH="" ;;
  2) printf '%s\\n' "$READ_STATE_OUTPUT" >&2; exit 2 ;;
  *) printf '%s\\n' "$READ_STATE_OUTPUT" >&2; exit "$READ_STATE_STATUS" ;;
esac
if [ -n "$STATE_PATH" ]; then
  PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/session_state.py" clear-state --state-dir "{state_dir}" --state-path "$STATE_PATH"
else
  printf 'CLEAR_SKIPPED\\n'
fi
'''
    result = subprocess.run(["/bin/zsh", "-lc", shell], capture_output=True, text=True, cwd=str(tmp_path))
    assert result.returncode == 0
    assert "READ_STATE_STATUS=1" in result.stdout
    assert "CLEAR_SKIPPED" in result.stdout
    assert not runtime_env.exists()
    assert _plugin_residue_snapshot(plugin_root) == plugin_before
    assert _project_residue_snapshot(tmp_path) == project_before

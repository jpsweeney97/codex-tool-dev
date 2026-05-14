from __future__ import annotations

import json
import os
import shlex
import stat
import subprocess
from pathlib import Path
from typing import Any

import pytest
import refresh.smoke as smoke_module
from refresh.app_server_inventory import REAL_CODEX_HOME
from refresh.models import RefreshError
from refresh.smoke import SmokeCommand, run_standard_smoke


def test_standard_smoke_derives_installed_plugin_roots_from_codex_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / "isolated-codex-home"
    repo_root = tmp_path / "repo"
    local_only = codex_home / "local-only/turbo-mode-refresh/run-1"
    runner = FakeSmokeRunner()
    monkeypatch.setattr(smoke_module.subprocess, "run", runner.run)

    summary = run_standard_smoke(
        local_only_run_root=local_only,
        codex_home=codex_home,
        repo_root=repo_root,
    )

    handoff_root = codex_home / "plugins/cache/turbo-mode/handoff/1.6.0"
    ticket_root = codex_home / "plugins/cache/turbo-mode/ticket/1.4.0"
    assert summary["final_status"] == "passed"
    assert summary["selected_smoke_tier"] == "standard"
    assert str(handoff_root) in "\n".join(runner.command_texts)
    assert str(ticket_root) in "\n".join(runner.command_texts)
    assert "/Users/jp/.codex/plugins/cache" not in "\n".join(runner.command_texts)
    assert "handoff-session-state-archive" in summary["smoke_labels"]
    assert "ticket-audit-repair-dry-run" in summary["smoke_labels"]


def test_standard_smoke_uses_current_handoff_storage_root(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = FakeSmokeRunner()
    monkeypatch.setattr(smoke_module.subprocess, "run", runner.run)

    run_standard_smoke(
        local_only_run_root=tmp_path / "home/local-only/turbo-mode-refresh/run-1",
        codex_home=tmp_path / "home",
        repo_root=tmp_path / "repo",
    )

    command_text = "\n".join(runner.command_texts)
    assert "/.codex/handoffs/archive" in command_text
    assert "/.codex/handoffs/.session-state" in command_text
    assert "/docs/handoffs" not in command_text


def test_isolated_smoke_rejects_real_home_command_paths_before_execution(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    command = SmokeCommand(
        label="leaky-command",
        argv=(
            "python3",
            str(REAL_CODEX_HOME / "plugins/cache/turbo-mode/handoff/1.6.0/scripts/defer.py"),
        ),
        command_string=(
            f"python3 {REAL_CODEX_HOME}/plugins/cache/turbo-mode/handoff/1.6.0/scripts/defer.py"
        ),
    )
    monkeypatch.setattr(smoke_module, "_build_smoke_plan", lambda **kwargs: (command,))
    runner = FakeSmokeRunner()
    monkeypatch.setattr(smoke_module.subprocess, "run", runner.run)

    with pytest.raises(RefreshError, match="live Codex home path"):
        run_standard_smoke(
            local_only_run_root=tmp_path / "home/local-only/turbo-mode-refresh/run-1",
            codex_home=tmp_path / "home",
            repo_root=tmp_path / "repo",
        )

    assert runner.command_texts == []


def test_real_home_smoke_requires_explicit_allow_env(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = FakeSmokeRunner()
    monkeypatch.setattr(smoke_module.subprocess, "run", runner.run)
    monkeypatch.delenv("ALLOW_REAL_CODEX_HOME_SMOKE", raising=False)

    with pytest.raises(RefreshError, match="explicit real-home run context"):
        run_standard_smoke(
            local_only_run_root=tmp_path / "run",
            codex_home=REAL_CODEX_HOME,
            repo_root=tmp_path / "repo",
        )

    assert runner.command_texts == []


def test_minimal_subprocess_env_scrubs_real_home_path_entries(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    fake_real_home = tmp_path / "operator-home/.codex"
    monkeypatch.setattr(smoke_module, "REAL_CODEX_HOME", fake_real_home)
    monkeypatch.setenv(
        "PATH",
        os.pathsep.join(
            [
                "/usr/bin",
                str(fake_real_home / "bin"),
                f"/opt/bin:{fake_real_home}/plugins/cache/turbo-mode/bin",
            ]
        ),
    )

    env = smoke_module._minimal_subprocess_env()

    assert env["PATH"] == os.pathsep.join(["/usr/bin", "/opt/bin"])


def test_defer_smoke_fails_when_stdout_is_not_json(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = FakeSmokeRunner(stdout=b"not json\n")
    monkeypatch.setattr(smoke_module.subprocess, "run", runner.run)

    with pytest.raises(RefreshError, match="defer stdout was not JSON"):
        run_standard_smoke(
            local_only_run_root=tmp_path / "home/local-only/turbo-mode-refresh/run-1",
            codex_home=tmp_path / "home",
            repo_root=tmp_path / "repo",
        )


def test_ticket_update_payload_uses_only_update_supported_fields(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = FakeSmokeRunner()
    monkeypatch.setattr(smoke_module.subprocess, "run", runner.run)

    run_standard_smoke(
        local_only_run_root=tmp_path / "home/local-only/turbo-mode-refresh/run-1",
        codex_home=tmp_path / "home",
        repo_root=tmp_path / "repo",
    )

    update_payload = runner.payloads["ticket-update.json"]
    assert update_payload["fields"] == {"tags": ["smoke", "updated"]}
    assert "acceptance_criteria" not in update_payload["fields"]


def test_raw_outputs_are_private_and_summary_records_only_hashes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = FakeSmokeRunner(
        stdout_by_label={"ticket-list-open": b"RAW-SECRET-PAYLOAD\n"},
        stderr_by_label={"ticket-list-open": b"RAW-SECRET-ERR\n"},
    )
    monkeypatch.setattr(smoke_module.subprocess, "run", runner.run)

    summary = run_standard_smoke(
        local_only_run_root=tmp_path / "home/local-only/turbo-mode-refresh/run-1",
        codex_home=tmp_path / "home",
        repo_root=tmp_path / "repo",
    )

    raw_stdout = summary["raw_stdout_sha256"]
    raw_stderr = summary["raw_stderr_sha256"]
    assert set(raw_stdout) == set(summary["smoke_labels"])
    assert set(raw_stderr) == set(summary["smoke_labels"])
    summary_text = json.dumps(summary, sort_keys=True)
    assert "RAW-SECRET-PAYLOAD" not in summary_text
    assert "RAW-SECRET-ERR" not in summary_text
    for result in summary["results"]:
        stdout_path = Path(result["stdout_path"])
        stderr_path = Path(result["stderr_path"])
        assert stat.S_IMODE(stdout_path.stat().st_mode) == 0o600
        assert stat.S_IMODE(stderr_path.stat().st_mode) == 0o600


def test_nonzero_command_marks_smoke_failed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = FakeSmokeRunner(fail_labels={"ticket-audit-repair-dry-run"})
    monkeypatch.setattr(smoke_module.subprocess, "run", runner.run)

    summary = run_standard_smoke(
        local_only_run_root=tmp_path / "home/local-only/turbo-mode-refresh/run-1",
        codex_home=tmp_path / "home",
        repo_root=tmp_path / "repo",
    )

    assert summary["final_status"] == "failed"
    audit_result = [
        result for result in summary["results"] if result["label"] == "ticket-audit-repair-dry-run"
    ][0]
    assert audit_result["exit_code"] == 2
    assert audit_result["redacted_status"] == "failed"


def test_handoff_clear_state_smoke_uses_recorded_state_path(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = FakeSmokeRunner(require_clear_state_path=True)
    monkeypatch.setattr(smoke_module.subprocess, "run", runner.run)

    summary = run_standard_smoke(
        local_only_run_root=tmp_path / "home/local-only/turbo-mode-refresh/run-1",
        codex_home=tmp_path / "home",
        repo_root=tmp_path / "repo",
    )

    assert summary["final_status"] == "passed"


def test_handoff_clear_state_smoke_allows_cleanup_warning(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    runner = FakeSmokeRunner(require_clear_state_path=True, warn_clear_state_not_removed=True)
    monkeypatch.setattr(smoke_module.subprocess, "run", runner.run)

    summary = run_standard_smoke(
        local_only_run_root=tmp_path / "home/local-only/turbo-mode-refresh/run-1",
        codex_home=tmp_path / "home",
        repo_root=tmp_path / "repo",
    )

    assert summary["final_status"] == "passed"


class FakeSmokeRunner:
    def __init__(
        self,
        *,
        stdout: bytes = b'{"status":"ok"}\n',
        stderr: bytes = b"",
        stdout_by_label: dict[str, bytes] | None = None,
        stderr_by_label: dict[str, bytes] | None = None,
        fail_labels: set[str] | None = None,
        require_clear_state_path: bool = False,
        warn_clear_state_not_removed: bool = False,
    ) -> None:
        self.stdout = stdout
        self.stderr = stderr
        self.stdout_by_label = stdout_by_label or {}
        self.stderr_by_label = stderr_by_label or {}
        self.fail_labels = fail_labels or set()
        self.require_clear_state_path = require_clear_state_path
        self.warn_clear_state_not_removed = warn_clear_state_not_removed
        self.command_texts: list[str] = []
        self.payloads: dict[str, dict[str, Any]] = {}
        self.ticket_id = "T-SMOKE-1"
        self.state_file: Path | None = None

    def run(self, args: list[str], **kwargs: Any) -> subprocess.CompletedProcess[bytes]:
        command_text = shlex.join(args)
        self.command_texts.append(command_text)
        label = _label_from_output_path(kwargs)
        if label in self.fail_labels:
            return subprocess.CompletedProcess(args, 2, b"", b"failed\n")
        cwd = Path(kwargs.get("cwd") or ".")
        env = kwargs.get("env") or {}
        input_bytes = kwargs.get("input")
        stdout = self.stdout
        stderr = self.stderr

        if "session_state.py" in command_text and "archive" in args:
            source = _value_after(args, "--source")
            archive_dir = _value_after(args, "--archive-dir")
            archive_dir.mkdir(parents=True, exist_ok=True)
            archived = archive_dir / source.name
            archived.write_bytes(source.read_bytes())
            source.unlink()
            stdout = f"{archived}\n".encode()
        elif "session_state.py" in command_text and "write-state" in args:
            state_dir = _value_after(args, "--state-dir")
            state_dir.mkdir(parents=True, exist_ok=True)
            self.state_file = state_dir / "handoff-smoke-repo-token.json"
            self.state_file.write_text(
                json.dumps({"archive_path": str(_value_after(args, "--archive-path"))}),
                encoding="utf-8",
            )
            stdout = f"{self.state_file}\n".encode()
        elif "session_state.py" in command_text and "read-state" in args:
            assert self.state_file is not None
            stdout = (
                json.loads(self.state_file.read_text(encoding="utf-8"))["archive_path"].encode()
                + b"\n"
            )
        elif "session_state.py" in command_text and "clear-state" in args:
            if self.require_clear_state_path and "--state-path" not in args:
                return subprocess.CompletedProcess(
                    args,
                    2,
                    b"",
                    b"the following arguments are required: --state-path\n",
                )
            if "--state-path" in args:
                assert self.state_file == _value_after(args, "--state-path")
            if self.warn_clear_state_not_removed:
                return subprocess.CompletedProcess(
                    args,
                    0,
                    b"",
                    b"state cleanup warning: clear-state failed\n",
                )
            if self.state_file is not None:
                self.state_file.unlink()
        elif "defer.py" in command_text:
            envelopes = cwd / "docs/tickets/.envelopes"
            envelopes.mkdir(parents=True, exist_ok=True)
            (envelopes / "smoke.json").write_text("{}", encoding="utf-8")
        elif "ticket_engine_guard.py" in command_text:
            assert input_bytes is not None
            hook_input = json.loads(input_bytes.decode("utf-8"))
            payload_path = Path(shlex.split(hook_input["tool_input"]["command"])[-1])
            payload = json.loads(payload_path.read_text(encoding="utf-8"))
            payload.update(
                {
                    "hook_injected": True,
                    "hook_request_origin": "user",
                    "session_id": "plan06-smoke",
                }
            )
            payload_path.write_text(json.dumps(payload), encoding="utf-8")
            self.payloads[payload_path.name] = payload
            stdout = json.dumps({"hookSpecificOutput": {"permissionDecision": "allow"}}).encode()
        elif "ticket_workflow.py" in command_text and "execute" in args:
            payload = json.loads(Path(args[-1]).read_text(encoding="utf-8"))
            action = payload["action"]
            if action == "create":
                ticket_path = cwd / f"docs/tickets/{self.ticket_id}.md"
                ticket_path.parent.mkdir(parents=True, exist_ok=True)
                ticket_path.write_text("# Smoke ticket\n", encoding="utf-8")
                stdout = json.dumps({"ticket_id": self.ticket_id}).encode()
            else:
                stdout = json.dumps({"ticket_id": self.ticket_id, "status": "ok"}).encode()
        elif "ticket_read.py" in command_text:
            stdout = json.dumps({"ticket_id": self.ticket_id, "status": "ok"}).encode()
        elif "ticket_audit.py" in command_text:
            stdout = json.dumps({"status": "ok", "unrecoverable": 0}).encode()
        elif env.get("CODEX_HOME"):
            stdout = self.stdout
            stderr = self.stderr

        if label in self.stdout_by_label:
            stdout = self.stdout_by_label[label]
        if label in self.stderr_by_label:
            stderr = self.stderr_by_label[label]
        return subprocess.CompletedProcess(args, 0, stdout, stderr)


def _label_from_output_path(kwargs: dict[str, Any]) -> str | None:
    env = kwargs.get("env") or {}
    if "TURBO_MODE_SMOKE_LABEL" in env:
        return str(env["TURBO_MODE_SMOKE_LABEL"])
    stdout = kwargs.get("stdout")
    if hasattr(stdout, "name"):
        name = Path(stdout.name).name
        if name.endswith(".stdout.txt"):
            return name[: -len(".stdout.txt")]
    return None


def _value_after(args: list[str], flag: str) -> Path:
    return Path(args[args.index(flag) + 1])

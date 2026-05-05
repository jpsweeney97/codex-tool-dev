from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path

import pytest
import refresh.app_server_inventory as inventory_module
from refresh.app_server_inventory import (
    EXPECTED_HANDOFF_SKILLS,
    EXPECTED_TICKET_SKILLS,
    CodexRuntimeIdentity,
    InventoryCollectionError,
    build_readonly_inventory_requests,
    collect_codex_runtime_identity,
    collect_readonly_runtime_inventory,
    transcript_bytes,
    validate_readonly_inventory_contract,
)
from refresh.models import RefreshError
from refresh.planner import RefreshPaths


def paths(tmp_path: Path) -> RefreshPaths:
    return RefreshPaths(
        repo_root=tmp_path / "repo",
        codex_home=tmp_path / ".codex",
        marketplace_path=tmp_path / "repo/.agents/plugins/marketplace.json",
        config_path=tmp_path / ".codex/config.toml",
        local_only_root=tmp_path / ".codex/local-only/turbo-mode-refresh",
    )


def identity() -> CodexRuntimeIdentity:
    return CodexRuntimeIdentity(
        codex_version="codex-cli 0.test",
        executable_path="/usr/local/bin/codex",
        executable_sha256="abc",
        executable_hash_unavailable_reason=None,
        server_info={"name": "codex-app-server", "version": "0.test"},
        initialize_capabilities={"experimentalApi": True},
    )


def transcript(refresh_paths: RefreshPaths) -> tuple[dict[str, object], ...]:
    handoff_source = refresh_paths.repo_root / "plugins/turbo-mode/handoff/1.6.0"
    ticket_source = refresh_paths.repo_root / "plugins/turbo-mode/ticket/1.4.0"
    handoff_cache = refresh_paths.codex_home / "plugins/cache/turbo-mode/handoff/1.6.0"
    ticket_cache = refresh_paths.codex_home / "plugins/cache/turbo-mode/ticket/1.4.0"
    return (
        {
            "direction": "recv",
            "body": {
                "id": 0,
                "result": {
                    "serverInfo": {"name": "codex-app-server", "version": "0.test"},
                    "capabilities": {"experimentalApi": True},
                },
            },
        },
        {
            "direction": "recv",
            "body": {"id": 1, "result": {"source": {"path": str(handoff_source)}}},
        },
        {
            "direction": "recv",
            "body": {"id": 2, "result": {"source": {"path": str(ticket_source)}}},
        },
        {
            "direction": "recv",
            "body": {"id": 3, "result": {"plugins": ["handoff@turbo-mode", "ticket@turbo-mode"]}},
        },
        {
            "direction": "recv",
            "body": {
                "id": 4,
                "result": {
                    "skills": [
                        {
                            "name": "handoff:save",
                            "sourcePath": str(handoff_cache / "skills/save/SKILL.md"),
                        },
                        {
                            "name": "handoff:quicksave",
                            "sourcePath": str(handoff_cache / "skills/quicksave/SKILL.md"),
                        },
                        {
                            "name": "handoff:summary",
                            "sourcePath": str(handoff_cache / "skills/summary/SKILL.md"),
                        },
                        {
                            "name": "handoff:load",
                            "sourcePath": str(handoff_cache / "skills/load/SKILL.md"),
                        },
                        {
                            "name": "handoff:search",
                            "sourcePath": str(handoff_cache / "skills/search/SKILL.md"),
                        },
                        {
                            "name": "handoff:defer",
                            "sourcePath": str(handoff_cache / "skills/defer/SKILL.md"),
                        },
                        {
                            "name": "handoff:triage",
                            "sourcePath": str(handoff_cache / "skills/triage/SKILL.md"),
                        },
                        {
                            "name": "handoff:distill",
                            "sourcePath": str(handoff_cache / "skills/distill/SKILL.md"),
                        },
                        {
                            "name": "ticket:ticket",
                            "sourcePath": str(ticket_cache / "skills/ticket/SKILL.md"),
                        },
                        {
                            "name": "ticket:ticket-triage",
                            "sourcePath": str(ticket_cache / "skills/ticket-triage/SKILL.md"),
                        },
                    ]
                },
            },
        },
        {
            "direction": "recv",
            "body": {
                "id": 5,
                "result": {
                    "hooks": [
                        {
                            "pluginId": "ticket@turbo-mode",
                            "eventName": "preToolUse",
                            "matcher": "Bash",
                            "command": f"python3 {ticket_cache}/hooks/ticket_engine_guard.py",
                            "sourcePath": str(ticket_cache / "hooks/hooks.json"),
                        }
                    ]
                },
            },
        },
    )


def test_build_readonly_inventory_requests_never_installs(tmp_path: Path) -> None:
    refresh_paths = paths(tmp_path)

    requests = build_readonly_inventory_requests(refresh_paths, scratch_cwd=tmp_path / "scratch")

    assert [request["method"] for request in requests] == [
        "initialize",
        "initialized",
        "plugin/read",
        "plugin/read",
        "plugin/list",
        "skills/list",
        "hooks/list",
    ]
    assert "plugin/install" not in json.dumps(requests)


def test_validate_readonly_inventory_contract_accepts_aligned_runtime(tmp_path: Path) -> None:
    refresh_paths = paths(tmp_path)
    raw_transcript = transcript(refresh_paths)

    inventory = validate_readonly_inventory_contract(
        raw_transcript,
        paths=refresh_paths,
        identity=identity(),
        request_methods=("initialize", "initialized", "plugin/read"),
    )

    assert inventory.state == "aligned"
    assert inventory.plugin_read_sources["handoff"].endswith("plugins/turbo-mode/handoff/1.6.0")
    assert inventory.ticket_hook["command"].endswith("ticket_engine_guard.py")
    assert inventory.handoff_hooks == ()
    assert inventory.transcript_sha256 == hashlib.sha256(
        transcript_bytes(raw_transcript)
    ).hexdigest()


def test_validate_readonly_inventory_contract_accepts_structural_top_level_plugin_list(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = copy.deepcopy(list(transcript(refresh_paths)))
    raw[3]["body"]["result"] = {
        "plugins": [
            {"id": "handoff@turbo-mode", "source": {"path": "/source/handoff"}},
            {"id": "ticket@turbo-mode", "source": {"path": "/source/ticket"}},
        ]
    }

    inventory = validate_readonly_inventory_contract(
        tuple(raw),
        paths=refresh_paths,
        identity=identity(),
        request_methods=("initialize",),
    )

    assert inventory.plugin_list == ("handoff@turbo-mode", "ticket@turbo-mode")


def test_validate_readonly_inventory_contract_rejects_raw_response_lines(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw.insert(0, {"direction": "recv-raw", "body": "not json"})

    with pytest.raises(RefreshError, match="malformed app-server response stream"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_validate_readonly_inventory_contract_rejects_duplicate_response_ids(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw.insert(1, copy.deepcopy(raw[0]))

    with pytest.raises(RefreshError, match="duplicate app-server response id"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_validate_readonly_inventory_contract_rejects_unexpected_response_ids(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw.insert(1, {"direction": "recv", "body": {"id": 99, "result": {}}})

    with pytest.raises(RefreshError, match="unexpected app-server response id"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_validate_readonly_inventory_contract_rejects_plugin_read_path_in_wrong_field(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = copy.deepcopy(list(transcript(refresh_paths)))
    expected = str(refresh_paths.repo_root / "plugins/turbo-mode/handoff/1.6.0")
    raw[1]["body"]["result"] = {"note": expected}

    with pytest.raises(RefreshError, match="plugin/read missing source path"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_validate_readonly_inventory_contract_rejects_plugin_list_id_in_wrong_field(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = copy.deepcopy(list(transcript(refresh_paths)))
    raw[3]["body"]["result"] = {
        "notes": ["handoff@turbo-mode", "ticket@turbo-mode"],
        "marketplaces": [],
    }

    with pytest.raises(RefreshError, match="plugin/list missing Turbo Mode plugins"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_validate_readonly_inventory_contract_rejects_skill_name_in_wrong_field(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = copy.deepcopy(list(transcript(refresh_paths)))
    cache_prefix = str(refresh_paths.codex_home / "plugins/cache/turbo-mode/handoff/1.6.0/skills")
    ticket_cache_prefix = str(
        refresh_paths.codex_home / "plugins/cache/turbo-mode/ticket/1.4.0/skills"
    )
    raw[4]["body"]["result"] = {
        "notes": list(EXPECTED_HANDOFF_SKILLS + EXPECTED_TICKET_SKILLS),
        "paths": [cache_prefix, ticket_cache_prefix],
        "skills": [],
    }

    with pytest.raises(RefreshError, match="skills/list missing Turbo Mode skills"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_validate_readonly_inventory_contract_rejects_missing_ticket_hook(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw[-1] = {"direction": "recv", "body": {"id": 5, "result": {"hooks": []}}}

    with pytest.raises(RefreshError, match="expected exactly one Ticket hook"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_validate_readonly_inventory_contract_rejects_unexpected_handoff_hook(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    hooks = raw[-1]["body"]["result"]["hooks"]
    hooks.append(
        {
            "pluginId": "handoff@turbo-mode",
            "eventName": "preToolUse",
            "matcher": "Bash",
            "command": "python3 cleanup.py",
        }
    )

    with pytest.raises(RefreshError, match="expected no Handoff hooks"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_validate_readonly_inventory_contract_rejects_missing_skill(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw[4]["body"]["result"]["skills"] = [
        item
        for item in raw[4]["body"]["result"]["skills"]
        if item["name"] != "ticket:ticket-triage"
    ]

    with pytest.raises(RefreshError, match="skills/list missing Turbo Mode skills"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


@pytest.mark.parametrize("response_index", [1, 2])
def test_validate_readonly_inventory_contract_rejects_plugin_read_plugin_dev_paths(
    tmp_path: Path,
    response_index: int,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw[response_index]["body"]["result"]["source"]["path"] = "/tmp/plugin-dev/turbo-mode"

    with pytest.raises(RefreshError, match="plugin/read contains plugin-dev path"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_validate_readonly_inventory_contract_rejects_plugin_list_plugin_dev_path(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw[3]["body"]["result"]["sourcePath"] = "/tmp/plugin-dev/turbo-mode/plugin.json"

    with pytest.raises(RefreshError, match="plugin/list contains plugin-dev path"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_validate_readonly_inventory_contract_rejects_skills_plugin_dev_path(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw[4]["body"]["result"]["skills"][0]["sourcePath"] = "/tmp/plugin-dev/SKILL.md"

    with pytest.raises(RefreshError, match="skills/list contains plugin-dev path"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_validate_readonly_inventory_contract_rejects_wrong_ticket_hook_command(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw[-1]["body"]["result"]["hooks"][0]["command"] = "python3 /wrong/ticket_engine_guard.py"

    with pytest.raises(RefreshError, match="Ticket hook command mismatch"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_validate_readonly_inventory_contract_rejects_wrong_ticket_hook_source_path(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw[-1]["body"]["result"]["hooks"][0]["sourcePath"] = "/wrong/hooks.json"

    with pytest.raises(RefreshError, match="Ticket hook sourcePath mismatch"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_validate_readonly_inventory_contract_rejects_additional_ticket_hook(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = copy.deepcopy(list(transcript(refresh_paths)))
    raw[-1]["body"]["result"]["hooks"].append(
        {
            "pluginId": "ticket@turbo-mode",
            "eventName": "postToolUse",
            "matcher": "Bash",
            "command": "python3 other.py",
            "sourcePath": "/other/hooks.json",
        }
    )

    with pytest.raises(RefreshError, match="expected exactly one Ticket hook"):
        validate_readonly_inventory_contract(
            tuple(raw),
            paths=refresh_paths,
            identity=identity(),
            request_methods=("initialize",),
        )


def test_collect_readonly_runtime_inventory_combines_identity_and_transcript(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)

    inventory, raw_transcript = collect_readonly_runtime_inventory(
        refresh_paths,
        roundtrip=lambda _requests: list(transcript(refresh_paths)),
        identity_collector=identity,
    )

    assert inventory.identity.server_info == {"name": "codex-app-server", "version": "0.test"}
    assert raw_transcript == transcript(refresh_paths)


def test_collect_readonly_runtime_inventory_preserves_transcript_on_validation_failure(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw.pop()

    with pytest.raises(InventoryCollectionError) as exc_info:
        collect_readonly_runtime_inventory(
            refresh_paths,
            roundtrip=lambda _requests: raw,
            identity_collector=identity,
        )

    assert "missing app-server responses" in str(exc_info.value)
    assert exc_info.value.transcript == tuple(raw)


def test_collect_codex_runtime_identity_hashes_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "codex"
    executable.write_bytes(b"codex executable")

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert args[0] == [str(executable), "--version"]
        assert kwargs["text"] is True
        assert kwargs["capture_output"] is True
        assert kwargs["check"] is False
        assert kwargs["timeout"] == 10
        return subprocess.CompletedProcess(args[0], 0, stdout="codex-cli 0.test\n", stderr="")

    monkeypatch.setattr(inventory_module.shutil, "which", lambda _name: str(executable))
    monkeypatch.setattr(inventory_module.subprocess, "run", fake_run)

    runtime_identity = collect_codex_runtime_identity()

    assert runtime_identity.codex_version == "codex-cli 0.test"
    assert runtime_identity.executable_path == str(executable)
    assert runtime_identity.executable_sha256 == hashlib.sha256(b"codex executable").hexdigest()
    assert runtime_identity.executable_hash_unavailable_reason is None
    assert runtime_identity.server_info == {}
    assert runtime_identity.initialize_capabilities == {}


def test_collect_codex_runtime_identity_rejects_missing_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(inventory_module.shutil, "which", lambda _name: None)

    with pytest.raises(RefreshError, match="codex executable not found on PATH"):
        collect_codex_runtime_identity()


def test_collect_codex_runtime_identity_rejects_version_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "codex"
    executable.write_bytes(b"codex executable")

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            [str(executable), "--version"],
            1,
            stdout="",
            stderr="version failed",
        )

    monkeypatch.setattr(inventory_module.shutil, "which", lambda _name: str(executable))
    monkeypatch.setattr(inventory_module.subprocess, "run", fake_run)

    with pytest.raises(RefreshError, match="version failed"):
        collect_codex_runtime_identity()


def test_collect_codex_runtime_identity_rejects_version_timeout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "codex"
    executable.write_bytes(b"codex executable")

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired([str(executable), "--version"], timeout=10)

    monkeypatch.setattr(inventory_module.shutil, "which", lambda _name: str(executable))
    monkeypatch.setattr(inventory_module.subprocess, "run", fake_run)

    with pytest.raises(RefreshError, match="codex --version timed out"):
        collect_codex_runtime_identity()


def test_collect_codex_runtime_identity_records_hash_read_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "codex"
    executable.write_bytes(b"codex executable")

    def fake_run(*_args: object, **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(
            [str(executable), "--version"],
            0,
            stdout="codex-cli 0.test\n",
            stderr="",
        )

    def fail_read_bytes(_path: Path) -> bytes:
        raise OSError("permission denied")

    monkeypatch.setattr(inventory_module.shutil, "which", lambda _name: str(executable))
    monkeypatch.setattr(inventory_module.subprocess, "run", fake_run)
    monkeypatch.setattr(Path, "read_bytes", fail_read_bytes)

    runtime_identity = collect_codex_runtime_identity()

    assert runtime_identity.executable_sha256 is None
    assert runtime_identity.executable_hash_unavailable_reason == "permission denied"

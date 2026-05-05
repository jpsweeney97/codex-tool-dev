from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from refresh.app_server_inventory import (
    CodexRuntimeIdentity,
    build_readonly_inventory_requests,
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


def test_validate_readonly_inventory_contract_rejects_missing_ticket_hook(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw[-1] = {"direction": "recv", "body": {"id": 5, "result": {"hooks": []}}}

    with pytest.raises(RefreshError, match="Ticket Bash preToolUse hook"):
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

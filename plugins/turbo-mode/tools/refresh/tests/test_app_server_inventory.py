from __future__ import annotations

import copy
import hashlib
import json
import os
import shutil
import subprocess
import tempfile
import threading
from datetime import UTC, datetime
from pathlib import Path

import pytest
import refresh.app_server_inventory as inventory_module
from refresh.app_server_inventory import (
    EXPECTED_HANDOFF_SKILLS,
    EXPECTED_TICKET_SKILLS,
    AppServerInstallAuthority,
    AppServerLaunchAuthority,
    AppServerPreInstallTargetAuthority,
    CodexRuntimeIdentity,
    InventoryCollectionError,
    app_server_roundtrip,
    authority_digest,
    build_install_requests,
    build_pre_install_target_authority,
    build_readonly_inventory_requests,
    collect_app_server_launch_authority,
    collect_codex_runtime_identity,
    collect_readonly_runtime_inventory,
    real_codex_home,
    rewrite_ticket_hook_manifest,
    serialize_authority_record,
    transcript_bytes,
    validate_install_responses,
    validate_readonly_inventory_contract,
    write_json_artifact,
)
from refresh.models import RefreshError
from refresh.planner import RefreshPaths

REAL_HOME_TICKET_COMMAND = (
    "python3 /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/"
    "hooks/ticket_engine_guard.py"
)
OTHER_HOME_TICKET_COMMAND = (
    "python3 /private/tmp/other/plugins/cache/turbo-mode/ticket/1.4.0/"
    "hooks/ticket_engine_guard.py"
)
REAL_HOME_TICKET_COMMAND_WITH_ARGS = REAL_HOME_TICKET_COMMAND + " --guard"
REAL_HOME_WRONG_TICKET_COMMAND = (
    "python3 /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/"
    "hooks/not_ticket_engine_guard.py"
)


def test_real_codex_home_derives_from_operator_home(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    operator_home = tmp_path / "operator"
    monkeypatch.setattr(Path, "home", lambda: operator_home)

    assert real_codex_home() == (operator_home / ".codex").resolve(strict=False)


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


def install_transcript(
    refresh_paths: RefreshPaths,
    *,
    installed_root: Path | None = None,
    include_cache_delta: bool = True,
    sparse_success: bool = False,
) -> tuple[dict[str, object], ...]:
    active_installed_root = installed_root or (
        refresh_paths.codex_home / "plugins/cache/turbo-mode"
    )
    if sparse_success:
        handoff_result: dict[str, object] = {
            "appsNeedingAuth": [],
            "authPolicy": "ON_INSTALL",
        }
        ticket_result: dict[str, object] = {
            "appsNeedingAuth": [],
            "authPolicy": "ON_INSTALL",
        }
        return (
            {
                "direction": "recv",
                "body": {
                    "id": 1,
                    "result": handoff_result,
                },
            },
            {
                "direction": "recv",
                "body": {
                    "id": 2,
                    "result": ticket_result,
                },
            },
        )
    handoff_result: dict[str, object] = {
        "pluginName": "handoff",
        "marketplacePath": str(refresh_paths.marketplace_path),
        "remoteMarketplaceName": None,
        "installedPath": str(active_installed_root / "handoff/1.6.0"),
        "status": "installed",
    }
    ticket_result: dict[str, object] = {
        "pluginName": "ticket",
        "marketplacePath": str(refresh_paths.marketplace_path),
        "remoteMarketplaceName": None,
        "installedPath": str(active_installed_root / "ticket/1.4.0"),
        "status": "installed",
    }
    if include_cache_delta:
        handoff_result["cacheDelta"] = {
            "plugin": "handoff",
            "postInstallManifestSha256": "handoff-post",
        }
        ticket_result["cacheDelta"] = {
            "plugin": "ticket",
            "postInstallManifestSha256": "ticket-post",
        }
    return (
        {
            "direction": "recv",
            "body": {
                "id": 1,
                "result": handoff_result,
            },
        },
        {
            "direction": "recv",
            "body": {
                "id": 2,
                "result": ticket_result,
            },
        },
    )


def seed_installed_plugin_roots(installed_root: Path) -> None:
    handoff_root = installed_root / "handoff/1.6.0"
    handoff_root.mkdir(parents=True, exist_ok=True)
    (handoff_root / "plugin.json").write_text(
        '{"name":"handoff","version":"1.6.0"}\n',
        encoding="utf-8",
    )
    (handoff_root / "skills/save/SKILL.md").parent.mkdir(parents=True, exist_ok=True)
    (handoff_root / "skills/save/SKILL.md").write_text("# save\n", encoding="utf-8")

    ticket_root = installed_root / "ticket/1.4.0"
    ticket_root.mkdir(parents=True, exist_ok=True)
    (ticket_root / "plugin.json").write_text(
        '{"name":"ticket","version":"1.4.0"}\n',
        encoding="utf-8",
    )
    (ticket_root / "hooks/ticket_engine_guard.py").parent.mkdir(parents=True, exist_ok=True)
    (ticket_root / "hooks/ticket_engine_guard.py").write_text(
        "#!/usr/bin/env python3\nprint('guard')\n",
        encoding="utf-8",
    )


def launch_authority_for_tests(
    refresh_paths: RefreshPaths,
    *,
    scratch_cwd: Path,
) -> AppServerLaunchAuthority:
    return AppServerLaunchAuthority(
        requested_codex_home=str(refresh_paths.codex_home),
        resolved_config_path=str(refresh_paths.codex_home / "config.toml"),
        resolved_plugin_cache_root=str(refresh_paths.codex_home / "plugins/cache/turbo-mode"),
        resolved_local_only_root=str(refresh_paths.local_only_root),
        binding_mechanism_name="env:CODEX_HOME",
        binding_mechanism_value=str(refresh_paths.codex_home),
        child_environment_delta={"CODEX_HOME": str(refresh_paths.codex_home)},
        child_cwd=str(scratch_cwd),
        executable_path="/usr/local/bin/codex",
        executable_sha256="abc",
        executable_hash_unavailable_reason=None,
        codex_version="codex-cli 0.test",
        initialize_server_info={"name": "codex-app-server", "version": "0.test"},
        initialize_capabilities={"experimentalApi": True},
        initialize_result={"codexHome": str(refresh_paths.codex_home)},
        accepted_response_schema_version="app-server-readonly-inventory-v1",
        candidate_mechanisms_checked=(),
        plugin_read_sources={"handoff": "x", "ticket": "y"},
        skill_paths=(),
        hook_paths=(),
    )


def pre_install_authority_for_tests(
    refresh_paths: RefreshPaths,
    *,
    launch_authority: AppServerLaunchAuthority,
    requested_codex_home: Path | None = None,
    install_destination_root: Path | None = None,
    launch_authority_sha256: str | None = None,
) -> AppServerPreInstallTargetAuthority:
    active_home = requested_codex_home or refresh_paths.codex_home
    active_root = install_destination_root or (active_home / "plugins/cache/turbo-mode")
    return AppServerPreInstallTargetAuthority(
        requested_codex_home=str(active_home),
        install_destination_root=str(active_root),
        resolved_plugin_cache_root=str(active_root),
        binding_mechanism_name="env:CODEX_HOME",
        binding_mechanism_value=str(active_home),
        launch_authority_sha256=launch_authority_sha256 or authority_digest(launch_authority),
        marketplace_path=str(refresh_paths.marketplace_path),
        remote_marketplace_name=None,
        no_real_home_paths=True,
        pre_install_cache_manifest_sha256=inventory_module.cache_manifest_sha256_by_plugin(
            install_destination_root=active_root
        ),
    )


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_sha256_file(path: Path) -> Path:
    digest = sha256_file(path)
    sha_path = path.with_suffix(path.suffix + ".sha256")
    sha_path.write_text(f"{digest}  {path.name}\n", encoding="utf-8")
    sha_path.chmod(0o600)
    return sha_path


def seed_isolated_codex_home(*, repo_root: Path, isolated_home: Path) -> None:
    real_codex_home = Path("/Users/jp/.codex")
    (isolated_home / "plugins/cache/turbo-mode").mkdir(parents=True, exist_ok=True)
    shutil.copytree(
        real_codex_home / "plugins/cache/turbo-mode/handoff/1.6.0",
        isolated_home / "plugins/cache/turbo-mode/handoff/1.6.0",
    )
    shutil.copytree(
        real_codex_home / "plugins/cache/turbo-mode/ticket/1.4.0",
        isolated_home / "plugins/cache/turbo-mode/ticket/1.4.0",
    )
    rewrite_ticket_hook_manifest(
        ticket_plugin_root=isolated_home / "plugins/cache/turbo-mode/ticket/1.4.0"
    )
    (isolated_home / "config.toml").write_text(
        f'[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "{repo_root}"\n'
        "[features]\nplugin_hooks = true\n"
        '[plugins."handoff@turbo-mode"]\nenabled = true\n'
        '[plugins."ticket@turbo-mode"]\nenabled = true\n',
        encoding="utf-8",
    )


def artifact_copy(path: Path, durable_root: Path) -> Path:
    durable_root.mkdir(parents=True, exist_ok=True)
    durable_root.chmod(0o700)
    target = durable_root / path.name
    shutil.copy2(path, target)
    target.chmod(0o600)
    return target


def build_same_child_post_install_requests(
    refresh_paths: RefreshPaths,
    *,
    scratch_cwd: Path,
) -> list[dict[str, object]]:
    requests: list[dict[str, object]] = []
    for request in build_readonly_inventory_requests(refresh_paths, scratch_cwd=scratch_cwd):
        if request.get("method") in {"initialize", "initialized"}:
            continue
        copied = copy.deepcopy(request)
        copied["id"] = int(copied["id"]) + 2
        requests.append(copied)
    return requests


def normalize_same_child_post_install_transcript(
    raw_transcript: tuple[dict[str, object], ...],
) -> tuple[dict[str, object], ...]:
    response_id_map = {0: 0, 3: 1, 4: 2, 5: 3, 6: 4, 7: 5}
    normalized: list[dict[str, object]] = []
    for item in raw_transcript:
        body = item.get("body")
        if item.get("direction") != "recv" or not isinstance(body, dict):
            continue
        response_id = body.get("id")
        if not isinstance(response_id, int) or response_id not in response_id_map:
            continue
        copied = copy.deepcopy(item)
        copied_body = copied["body"]
        assert isinstance(copied_body, dict)
        copied_body["id"] = response_id_map[response_id]
        normalized.append(copied)
    return tuple(normalized)


def blocker_inventory_counts(
    responses: dict[int, dict[str, object]],
) -> tuple[int | None, int | None]:
    skills_result = responses.get(4)
    hooks_result = responses.get(5)
    skills_count = (
        len(inventory_module.skill_records_by_name({"result": skills_result}))
        if isinstance(skills_result, dict)
        else None
    )
    hooks_count = (
        len(inventory_module.hook_records({"result": hooks_result}))
        if isinstance(hooks_result, dict)
        else None
    )
    return skills_count, hooks_count


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


def test_validate_readonly_inventory_contract_accepts_disabled_ticket_hooks(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw[-1] = {"direction": "recv", "body": {"id": 5, "result": {"hooks": []}}}

    inventory = validate_readonly_inventory_contract(
        tuple(raw),
        paths=refresh_paths,
        identity=identity(),
        request_methods=("initialize",),
        ticket_hook_policy="disabled",
    )

    assert inventory.state == "aligned"
    assert inventory.ticket_hook == {}
    assert inventory.reasons == ("ticket-hook-disabled-by-config",)


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
    assert inventory.identity.initialize_result == raw_transcript[0]["body"]["result"]
    assert raw_transcript == transcript(refresh_paths)


def test_collect_readonly_runtime_inventory_binds_roundtrip_and_identity_executable(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    refresh_paths = paths(tmp_path)
    executable = tmp_path / "bin/codex"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"codex executable")
    launched: list[list[str]] = []
    launched_env: list[dict[str, str]] = []
    launched_cwd: list[str | None] = []
    processes: list[object] = []

    class FakeStdin:
        def write(self, _value: str) -> None:
            return None

        def flush(self) -> None:
            return None

    class FakeProcess:
        def __init__(self, cmd: list[str], **kwargs: object) -> None:
            launched.append(cmd)
            launched_env.append(dict(kwargs["env"]))  # type: ignore[arg-type]
            launched_cwd.append(kwargs.get("cwd"))  # type: ignore[arg-type]
            processes.append(self)
            self.stdin = FakeStdin()
            self.stdout = [
                json.dumps(item["body"]) + "\n"
                for item in transcript(refresh_paths)
                if item["direction"] == "recv"
            ]
            self.stderr = []
            self.returncode = None
            self.terminated = False

        def terminate(self) -> None:
            self.terminated = True
            self.returncode = -15

        def wait(self, timeout: int) -> int:
            assert timeout == 5
            return self.returncode

    def fake_run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        assert args[0] == [str(executable), "--version"]
        assert kwargs["timeout"] == 10
        return subprocess.CompletedProcess(args[0], 0, stdout="codex-cli 0.bound\n", stderr="")

    monkeypatch.setattr(inventory_module.shutil, "which", lambda _name: str(executable))
    monkeypatch.setattr(inventory_module.subprocess, "Popen", FakeProcess)
    monkeypatch.setattr(inventory_module.subprocess, "run", fake_run)
    monkeypatch.delenv("CODEX_HOME", raising=False)

    scratch_cwd = tmp_path / "scratch"
    inventory, _raw_transcript = collect_readonly_runtime_inventory(
        refresh_paths,
        scratch_cwd=scratch_cwd,
    )

    assert launched == [[str(executable), "app-server", "--listen", "stdio://"]]
    assert launched_env[0]["CODEX_HOME"] == str(refresh_paths.codex_home)
    assert launched_cwd == [str(scratch_cwd)]
    assert getattr(processes[0], "terminated")
    assert inventory.identity.executable_path == str(executable)
    assert inventory.identity.codex_version == "codex-cli 0.bound"


def test_app_server_roundtrip_runs_after_response_callback_before_next_request(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "bin/codex"
    executable.parent.mkdir(parents=True)
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    events: list[str] = []

    class FakeStdin:
        def write(self, value: str) -> None:
            request = json.loads(value)
            if request.get("id") == 3:
                assert "rewrote-ticket-hook" in events
            events.append(f"send-{request.get('id')}")

        def flush(self) -> None:
            return None

    class FakeProcess:
        def __init__(self, _cmd: list[str], **_kwargs: object) -> None:
            self.stdin = FakeStdin()
            self.stdout = [
                json.dumps({"id": 1, "result": {"ok": True}}) + "\n",
                json.dumps({"id": 2, "result": {"ok": True}}) + "\n",
                json.dumps({"id": 3, "result": {"ok": True}}) + "\n",
            ]
            self.stderr = []
            self.returncode = None

        def terminate(self) -> None:
            self.returncode = -15

        def wait(self, timeout: int) -> int:
            assert timeout == 5
            return self.returncode

    def after_response(
        request: dict[str, object],
        response: dict[str, object],
        _transcript: list[dict[str, object]],
    ) -> None:
        if request.get("id") == 2 and response.get("id") == 2:
            events.append("rewrote-ticket-hook")

    monkeypatch.setattr(inventory_module.subprocess, "Popen", FakeProcess)

    raw_transcript = app_server_roundtrip(
        [
            {"id": 1, "method": "plugin/install"},
            {"id": 2, "method": "plugin/install"},
            {"id": 3, "method": "hooks/list"},
        ],
        executable=str(executable),
        cwd=tmp_path,
        after_response=after_response,
    )

    assert [item["body"]["id"] for item in raw_transcript if item["direction"] == "recv"] == [
        1,
        2,
        3,
    ]
    assert events == ["send-1", "send-2", "rewrote-ticket-hook", "send-3"]


def test_app_server_roundtrip_drains_stderr_while_waiting_for_response(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "bin/codex"
    executable.parent.mkdir(parents=True)
    executable.write_bytes(b"codex executable")
    stderr_drained = threading.Event()

    class FakeStdin:
        def write(self, _value: str) -> None:
            return None

        def flush(self) -> None:
            return None

    class BlockingStdout:
        def __iter__(self):
            assert stderr_drained.wait(timeout=1)
            yield json.dumps({"id": 0, "result": {}}) + "\n"

    class VerboseStderr:
        def __iter__(self):
            for _index in range(1000):
                stderr_drained.set()
                yield "verbose app-server log\n"

    class FakeProcess:
        def __init__(self, _cmd: list[str], **_kwargs: object) -> None:
            self.stdin = FakeStdin()
            self.stdout = BlockingStdout()
            self.stderr = VerboseStderr()
            self.returncode = None

        def terminate(self) -> None:
            self.returncode = -15

        def wait(self, timeout: int) -> int:
            assert timeout == 5
            return self.returncode

    monkeypatch.setattr(inventory_module.subprocess, "Popen", FakeProcess)

    raw_transcript = app_server_roundtrip(
        [{"id": 0, "method": "initialize"}],
        executable=str(executable),
    )

    assert stderr_drained.is_set()
    assert raw_transcript[-1] == {"direction": "recv", "body": {"id": 0, "result": {}}}


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


def test_collect_app_server_launch_authority_records_binding_candidates_and_launch_context(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    sent: dict[str, object] = {}
    raw = list(transcript(refresh_paths))
    raw[0]["body"]["result"]["codexHome"] = str(refresh_paths.codex_home)

    def fake_roundtrip(
        requests: list[dict[str, object]],
        *,
        executable: str | None = None,
        env_overrides: dict[str, str] | None = None,
        cwd: Path | None = None,
    ) -> list[dict[str, object]]:
        sent["requests"] = requests
        sent["executable"] = executable
        sent["env_overrides"] = env_overrides
        sent["cwd"] = cwd
        return raw

    authority, raw_transcript = collect_app_server_launch_authority(
        refresh_paths,
        scratch_cwd=tmp_path / "scratch",
        roundtrip=fake_roundtrip,
        identity_collector=identity,
        app_server_help_text="codex app-server --help includes -c, --config and --listen",
        codex_help_text=(
            "codex exec --help mentions CODEX_HOME and codex --help "
            "includes -c, --config"
        ),
    )

    assert sent["env_overrides"] == {"CODEX_HOME": str(refresh_paths.codex_home)}
    assert sent["cwd"] == tmp_path / "scratch"
    assert authority.requested_codex_home == str(refresh_paths.codex_home)
    assert authority.resolved_config_path == str(refresh_paths.codex_home / "config.toml")
    assert authority.resolved_plugin_cache_root == str(
        refresh_paths.codex_home / "plugins/cache/turbo-mode"
    )
    assert authority.resolved_local_only_root == str(refresh_paths.local_only_root)
    assert authority.binding_mechanism_name == "env:CODEX_HOME"
    assert authority.binding_mechanism_value == str(refresh_paths.codex_home)
    assert authority.initialize_server_info == {"name": "codex-app-server", "version": "0.test"}
    assert authority.accepted_response_schema_version == "app-server-readonly-inventory-v1"
    categories = {candidate.category for candidate in authority.candidate_mechanisms_checked}
    assert categories == {
        "app-server-cli-flag",
        "environment-variable",
        "config-path-option",
        "protocol-field",
        "parent-cli-flag",
    }
    assert raw_transcript == tuple(raw)


def test_collect_app_server_launch_authority_rejects_real_home_resolution_for_isolated_run(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    raw = list(transcript(refresh_paths))
    raw[0]["body"]["result"]["codexHome"] = "/Users/jp/.codex"
    raw[4]["body"]["result"]["skills"][0]["sourcePath"] = (
        "/Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0/skills/save/SKILL.md"
    )

    with pytest.raises(RefreshError, match="requested Codex home binding mismatch"):
        collect_app_server_launch_authority(
            refresh_paths,
            scratch_cwd=tmp_path / "scratch",
            roundtrip=lambda **_kwargs: raw,
            identity_collector=identity,
            app_server_help_text="codex app-server --help includes -c, --config and --listen",
            codex_help_text="codex exec --help mentions CODEX_HOME",
        )


def test_build_install_requests_require_matching_preinstall_authority(tmp_path: Path) -> None:
    refresh_paths = paths(tmp_path)
    launch_authority = AppServerLaunchAuthority(
        requested_codex_home=str(refresh_paths.codex_home),
        resolved_config_path=str(refresh_paths.codex_home / "config.toml"),
        resolved_plugin_cache_root=str(refresh_paths.codex_home / "plugins/cache/turbo-mode"),
        resolved_local_only_root=str(refresh_paths.local_only_root),
        binding_mechanism_name="env:CODEX_HOME",
        binding_mechanism_value=str(refresh_paths.codex_home),
        child_environment_delta={"CODEX_HOME": str(refresh_paths.codex_home)},
        child_cwd=str(tmp_path / "scratch"),
        executable_path="/usr/local/bin/codex",
        executable_sha256="abc",
        executable_hash_unavailable_reason=None,
        codex_version="codex-cli 0.test",
        initialize_server_info={"name": "codex-app-server", "version": "0.test"},
        initialize_capabilities={"experimentalApi": True},
        initialize_result={"codexHome": str(refresh_paths.codex_home)},
        accepted_response_schema_version="app-server-readonly-inventory-v1",
        candidate_mechanisms_checked=(),
        plugin_read_sources={"handoff": "x", "ticket": "y"},
        skill_paths=(),
        hook_paths=(),
    )
    launch_sha256 = authority_digest(launch_authority)
    pre_install_authority = AppServerPreInstallTargetAuthority(
        requested_codex_home=str(refresh_paths.codex_home),
        install_destination_root=str(refresh_paths.codex_home / "plugins/cache/turbo-mode"),
        resolved_plugin_cache_root=str(refresh_paths.codex_home / "plugins/cache/turbo-mode"),
        binding_mechanism_name="env:CODEX_HOME",
        binding_mechanism_value=str(refresh_paths.codex_home),
        launch_authority_sha256=launch_sha256,
        marketplace_path=str(refresh_paths.marketplace_path),
        remote_marketplace_name=None,
        no_real_home_paths=True,
        pre_install_cache_manifest_sha256=inventory_module.cache_manifest_sha256_by_plugin(
            install_destination_root=refresh_paths.codex_home / "plugins/cache/turbo-mode"
        ),
    )

    requests = build_install_requests(
        pre_install_authority=pre_install_authority,
        expected_requested_codex_home=refresh_paths.codex_home,
        expected_launch_authority_sha256=launch_sha256,
        expected_marketplace_path=refresh_paths.marketplace_path,
    )

    assert [request["method"] for request in requests] == ["plugin/install", "plugin/install"]

    with pytest.raises(RefreshError, match="pre-install target authority missing"):
        build_install_requests(
            pre_install_authority=None,
            expected_requested_codex_home=refresh_paths.codex_home,
            expected_launch_authority_sha256=launch_sha256,
            expected_marketplace_path=refresh_paths.marketplace_path,
        )

    with pytest.raises(RefreshError, match="pre-install target authority stale"):
        build_install_requests(
            pre_install_authority=pre_install_authority,
            expected_requested_codex_home=refresh_paths.codex_home,
            expected_launch_authority_sha256="wrong",
            expected_marketplace_path=refresh_paths.marketplace_path,
        )


def test_validate_install_responses_require_post_install_corroboration(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    launch_authority = launch_authority_for_tests(refresh_paths, scratch_cwd=tmp_path / "scratch")
    launch_sha256 = authority_digest(launch_authority)
    pre_install_authority = pre_install_authority_for_tests(
        refresh_paths,
        launch_authority=launch_authority,
    )
    install_requests = build_install_requests(
            pre_install_authority=pre_install_authority,
            expected_requested_codex_home=refresh_paths.codex_home,
            expected_launch_authority_sha256=launch_sha256,
            expected_marketplace_path=refresh_paths.marketplace_path,
        )

    with pytest.raises(RefreshError, match="post-install corroboration missing") as exc_info:
        validate_install_responses(
            transcript=install_transcript(refresh_paths, sparse_success=True),
            launch_authority=launch_authority,
            pre_install_authority=pre_install_authority,
            install_requests=tuple(install_requests),
        )
    assert "same-child" in str(exc_info.value)

    seed_installed_plugin_roots(refresh_paths.codex_home / "plugins/cache/turbo-mode")
    install_authority = validate_install_responses(
        transcript=install_transcript(refresh_paths, sparse_success=True),
        launch_authority=launch_authority,
        pre_install_authority=pre_install_authority,
        install_requests=tuple(install_requests),
        same_child_post_install_transcript=transcript(refresh_paths),
        fresh_child_post_install_transcript=transcript(refresh_paths),
    )

    assert isinstance(install_authority, AppServerInstallAuthority)
    assert install_authority.installed_destination_paths["handoff"].endswith("/handoff/1.6.0")
    assert install_authority.installed_destination_paths["ticket"].endswith("/ticket/1.4.0")
    assert install_authority.accepted_install_response_schema_by_plugin == {
        "handoff": "sparse-success-auth-v1",
        "ticket": "sparse-success-auth-v1",
    }
    assert install_authority.same_child_post_install_corroboration_sha256
    assert install_authority.fresh_child_post_install_corroboration_sha256
    assert install_authority.pre_install_cache_manifest_sha256["handoff"]
    assert install_authority.pre_install_cache_manifest_sha256["ticket"]
    assert install_authority.post_install_cache_manifest_sha256["handoff"]
    assert install_authority.post_install_cache_manifest_sha256["ticket"]
    assert install_authority.cache_manifest_delta_sha256["handoff"]
    assert install_authority.cache_manifest_delta_sha256["ticket"]
    assert (
        install_authority.pre_install_cache_manifest_sha256["handoff"]
        != install_authority.post_install_cache_manifest_sha256["handoff"]
    )
    assert (
        install_authority.pre_install_cache_manifest_sha256["ticket"]
        != install_authority.post_install_cache_manifest_sha256["ticket"]
    )


def test_validate_install_responses_record_noop_pre_and_post_manifests(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    seed_installed_plugin_roots(refresh_paths.codex_home / "plugins/cache/turbo-mode")
    launch_authority = launch_authority_for_tests(refresh_paths, scratch_cwd=tmp_path / "scratch")
    pre_install_authority = pre_install_authority_for_tests(
        refresh_paths,
        launch_authority=launch_authority,
    )
    install_requests = build_install_requests(
        pre_install_authority=pre_install_authority,
        expected_requested_codex_home=refresh_paths.codex_home,
        expected_launch_authority_sha256=authority_digest(launch_authority),
        expected_marketplace_path=refresh_paths.marketplace_path,
    )

    install_authority = validate_install_responses(
        transcript=install_transcript(refresh_paths, sparse_success=True),
        launch_authority=launch_authority,
        pre_install_authority=pre_install_authority,
        install_requests=tuple(install_requests),
        same_child_post_install_transcript=transcript(refresh_paths),
        fresh_child_post_install_transcript=transcript(refresh_paths),
    )

    assert (
        install_authority.pre_install_cache_manifest_sha256["handoff"]
        == install_authority.post_install_cache_manifest_sha256["handoff"]
    )
    assert (
        install_authority.pre_install_cache_manifest_sha256["ticket"]
        == install_authority.post_install_cache_manifest_sha256["ticket"]
    )
    assert install_authority.cache_manifest_delta_sha256["handoff"]
    assert install_authority.cache_manifest_delta_sha256["ticket"]


def test_validate_install_responses_accepts_disabled_same_child_hooks(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    seed_installed_plugin_roots(refresh_paths.codex_home / "plugins/cache/turbo-mode")
    launch_authority = launch_authority_for_tests(refresh_paths, scratch_cwd=tmp_path / "scratch")
    pre_install_authority = pre_install_authority_for_tests(
        refresh_paths,
        launch_authority=launch_authority,
    )
    install_requests = build_install_requests(
        pre_install_authority=pre_install_authority,
        expected_requested_codex_home=refresh_paths.codex_home,
        expected_launch_authority_sha256=authority_digest(launch_authority),
        expected_marketplace_path=refresh_paths.marketplace_path,
    )
    same_child = list(transcript(refresh_paths))
    same_child[-1] = {"direction": "recv", "body": {"id": 5, "result": {"hooks": []}}}

    install_authority = validate_install_responses(
        transcript=install_transcript(refresh_paths, sparse_success=True),
        launch_authority=launch_authority,
        pre_install_authority=pre_install_authority,
        install_requests=tuple(install_requests),
        same_child_post_install_transcript=tuple(same_child),
        fresh_child_post_install_transcript=transcript(refresh_paths),
        same_child_ticket_hook_policy="disabled",
    )

    assert install_authority.same_child_post_install_corroboration_sha256
    assert install_authority.fresh_child_post_install_corroboration_sha256


def test_validate_install_responses_reject_stale_preinstall_authority_digest(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    launch_authority = launch_authority_for_tests(refresh_paths, scratch_cwd=tmp_path / "scratch")
    pre_install_authority = pre_install_authority_for_tests(
        refresh_paths,
        launch_authority=launch_authority,
        launch_authority_sha256="stale-launch-authority",
    )
    seed_installed_plugin_roots(Path(pre_install_authority.install_destination_root))

    with pytest.raises(RefreshError, match="pre-install target authority stale"):
        validate_install_responses(
            transcript=install_transcript(
                refresh_paths,
                installed_root=Path(pre_install_authority.install_destination_root),
                include_cache_delta=False,
            ),
            launch_authority=launch_authority,
            pre_install_authority=pre_install_authority,
            install_requests=(
                {
                    "id": 1,
                    "method": "plugin/install",
                    "params": {
                        "marketplacePath": str(refresh_paths.marketplace_path),
                        "pluginName": "handoff",
                        "remoteMarketplaceName": None,
                    },
                },
                {
                    "id": 2,
                    "method": "plugin/install",
                    "params": {
                        "marketplacePath": str(refresh_paths.marketplace_path),
                        "pluginName": "ticket",
                        "remoteMarketplaceName": None,
                    },
                },
            ),
        )


def test_validate_install_responses_reject_mismatched_preinstall_home_and_root(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    launch_authority = launch_authority_for_tests(refresh_paths, scratch_cwd=tmp_path / "scratch")
    other_home = tmp_path / "other/.codex"
    pre_install_authority = pre_install_authority_for_tests(
        refresh_paths,
        launch_authority=launch_authority,
        requested_codex_home=other_home,
        install_destination_root=other_home / "plugins/cache/turbo-mode",
    )
    install_requests = build_install_requests(
        pre_install_authority=pre_install_authority,
        expected_requested_codex_home=other_home,
        expected_launch_authority_sha256=authority_digest(launch_authority),
        expected_marketplace_path=refresh_paths.marketplace_path,
    )
    seed_installed_plugin_roots(Path(pre_install_authority.install_destination_root))

    with pytest.raises(RefreshError, match="pre-install target authority home mismatch"):
        validate_install_responses(
            transcript=install_transcript(
                refresh_paths,
                installed_root=Path(pre_install_authority.install_destination_root),
                include_cache_delta=False,
            ),
            launch_authority=launch_authority,
            pre_install_authority=pre_install_authority,
            install_requests=tuple(install_requests),
        )


def test_validate_install_responses_reject_mismatched_preinstall_install_root(
    tmp_path: Path,
) -> None:
    refresh_paths = paths(tmp_path)
    launch_authority = launch_authority_for_tests(refresh_paths, scratch_cwd=tmp_path / "scratch")
    wrong_root = refresh_paths.codex_home / "plugins/cache/turbo-mode-shadow"
    pre_install_authority = pre_install_authority_for_tests(
        refresh_paths,
        launch_authority=launch_authority,
        install_destination_root=wrong_root,
    )
    seed_installed_plugin_roots(Path(pre_install_authority.install_destination_root))

    with pytest.raises(RefreshError, match="pre-install target authority install root mismatch"):
        validate_install_responses(
            transcript=install_transcript(
                refresh_paths,
                installed_root=Path(pre_install_authority.install_destination_root),
                include_cache_delta=False,
            ),
            launch_authority=launch_authority,
            pre_install_authority=pre_install_authority,
            install_requests=(
                {
                    "id": 1,
                    "method": "plugin/install",
                    "params": {
                        "marketplacePath": str(refresh_paths.marketplace_path),
                        "pluginName": "handoff",
                        "remoteMarketplaceName": None,
                    },
                },
                {
                    "id": 2,
                    "method": "plugin/install",
                    "params": {
                        "marketplacePath": str(refresh_paths.marketplace_path),
                        "pluginName": "ticket",
                        "remoteMarketplaceName": None,
                    },
                },
            ),
        )


def test_authority_serialization_and_artifact_writes_use_module_helpers(tmp_path: Path) -> None:
    refresh_paths = paths(tmp_path)
    authority = AppServerLaunchAuthority(
        requested_codex_home=str(refresh_paths.codex_home),
        resolved_config_path=str(refresh_paths.codex_home / "config.toml"),
        resolved_plugin_cache_root=str(refresh_paths.codex_home / "plugins/cache/turbo-mode"),
        resolved_local_only_root=str(refresh_paths.local_only_root),
        binding_mechanism_name="env:CODEX_HOME",
        binding_mechanism_value=str(refresh_paths.codex_home),
        child_environment_delta={"CODEX_HOME": str(refresh_paths.codex_home)},
        child_cwd=str(tmp_path / "scratch"),
        executable_path="/usr/local/bin/codex",
        executable_sha256="abc",
        executable_hash_unavailable_reason=None,
        codex_version="codex-cli 0.test",
        initialize_server_info={"name": "codex-app-server", "version": "0.test"},
        initialize_capabilities={"experimentalApi": True},
        initialize_result={"codexHome": str(refresh_paths.codex_home)},
        accepted_response_schema_version="app-server-readonly-inventory-v1",
        candidate_mechanisms_checked=(),
        plugin_read_sources={"handoff": "x", "ticket": "y"},
        skill_paths=(),
        hook_paths=(),
    )

    serialized = serialize_authority_record(authority)
    assert serialized["requested_codex_home"] == str(refresh_paths.codex_home)
    assert authority_digest(authority)

    artifact_path = tmp_path / "authority.json"
    write_json_artifact(artifact_path, serialized)

    assert json.loads(artifact_path.read_text(encoding="utf-8"))["binding_mechanism_name"] == (
        "env:CODEX_HOME"
    )


def test_blocker_inventory_counts_include_nested_data_shapes() -> None:
    responses = {
        4: {
            "data": [
                {
                    "skills": [
                        {"name": "handoff:save", "path": "/tmp/handoff-save"},
                        {"name": "ticket:ticket", "path": "/tmp/ticket"},
                    ]
                }
            ]
        },
        5: {
            "data": [
                {
                    "hooks": [
                        {
                            "pluginId": "ticket@turbo-mode",
                            "command": "python3 /tmp/ticket_engine_guard.py",
                        }
                    ]
                }
            ]
        },
    }

    skills_count, hooks_count = blocker_inventory_counts(responses)

    assert skills_count == 2
    assert hooks_count == 1


def test_rewrite_ticket_hook_manifest_binds_command_to_requested_plugin_root(
    tmp_path: Path,
) -> None:
    plugin_root = tmp_path / ".codex/plugins/cache/turbo-mode/ticket/1.4.0"
    plugin_root.mkdir(parents=True)
    hooks_path = plugin_root / "hooks/hooks.json"
    hooks_path.parent.mkdir(parents=True)
    hooks_path.write_text(
        json.dumps(
            {
                "description": "Ticket engine guard",
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": REAL_HOME_TICKET_COMMAND,
                                    "timeout": 10,
                                }
                            ],
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    rewrite_ticket_hook_manifest(ticket_plugin_root=plugin_root)

    payload = json.loads(hooks_path.read_text(encoding="utf-8"))
    command = payload["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    assert command == f"python3 {plugin_root}/hooks/ticket_engine_guard.py"
    assert "/Users/jp/.codex/" not in command


@pytest.mark.parametrize(
    "command",
    [
        REAL_HOME_TICKET_COMMAND.replace("python3 ", "python ", 1),
        OTHER_HOME_TICKET_COMMAND,
        REAL_HOME_TICKET_COMMAND_WITH_ARGS,
        REAL_HOME_WRONG_TICKET_COMMAND,
    ],
)
def test_rewrite_ticket_hook_manifest_rejects_unexpected_command_shape(
    tmp_path: Path,
    command: str,
) -> None:
    plugin_root = tmp_path / ".codex/plugins/cache/turbo-mode/ticket/1.4.0"
    plugin_root.mkdir(parents=True)
    hooks_path = plugin_root / "hooks/hooks.json"
    hooks_path.parent.mkdir(parents=True)
    hooks_path.write_text(
        json.dumps(
            {
                "description": "Ticket engine guard",
                "hooks": {
                    "PreToolUse": [
                        {
                            "matcher": "Bash",
                            "hooks": [
                                {
                                    "type": "command",
                                    "command": command,
                                    "timeout": 10,
                                }
                            ],
                        }
                    ]
                },
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    with pytest.raises(RefreshError, match="unexpected Ticket hook command"):
        rewrite_ticket_hook_manifest(ticket_plugin_root=plugin_root)


def test_seed_isolated_codex_home_rewrites_ticket_hook_manifest_to_isolated_root(
    tmp_path: Path,
) -> None:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    isolated_home = tmp_path / ".codex"

    seed_isolated_codex_home(repo_root=repo_root, isolated_home=isolated_home)

    hooks_path = isolated_home / "plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json"
    payload = json.loads(hooks_path.read_text(encoding="utf-8"))
    command = payload["hooks"]["PreToolUse"][0]["hooks"][0]["command"]
    expected_command = (
        f"python3 {isolated_home}/plugins/cache/turbo-mode/ticket/1.4.0/"
        "hooks/ticket_engine_guard.py"
    )
    assert command == expected_command


@pytest.mark.skipif(
    os.environ.get("CODEX_REFRESH_RUN_APP_SERVER_AUTHORITY_SPIKE") != "1",
    reason="operator-run Task 1A authority spike only",
)
def test_app_server_authority_spike() -> None:
    repo_root = Path(__file__).resolve().parents[5]
    run_id = "plan06-task1a-authority-spike-" + datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    isolated_base = Path(tempfile.mkdtemp(prefix=f"{run_id}-", dir="/private/tmp"))
    isolated_home = isolated_base / ".codex"
    scratch = isolated_base / "scratch"
    scratch.mkdir(parents=True, exist_ok=True)
    seed_isolated_codex_home(repo_root=repo_root, isolated_home=isolated_home)
    refresh_paths = RefreshPaths(
        repo_root=repo_root,
        codex_home=isolated_home,
        marketplace_path=repo_root / ".agents/plugins/marketplace.json",
        config_path=isolated_home / "config.toml",
        local_only_root=isolated_home / "local-only/turbo-mode-refresh",
    )
    isolated_run_root = refresh_paths.local_only_root / run_id
    isolated_run_root.mkdir(parents=True, exist_ok=True)
    isolated_run_root.chmod(0o700)
    durable_root = Path("/Users/jp/.codex/local-only/turbo-mode-refresh") / run_id
    durable_root.mkdir(parents=True, exist_ok=True)
    durable_root.chmod(0o700)

    readonly_transcript = tuple(
        app_server_roundtrip(
            build_readonly_inventory_requests(refresh_paths, scratch_cwd=scratch),
            env_overrides={"CODEX_HOME": str(isolated_home)},
            cwd=scratch,
        )
    )
    readonly_transcript_path = isolated_run_root / "readonly-discovery.transcript.json"
    write_json_artifact(readonly_transcript_path, readonly_transcript)
    readonly_transcript_sha = write_sha256_file(readonly_transcript_path)
    artifact_copy(readonly_transcript_path, durable_root)
    artifact_copy(readonly_transcript_sha, durable_root)
    blocker_stage = "read-only-home-binding-discovery"
    install_transcript_path: Path | None = None
    same_child_transcript_path: Path | None = None
    fresh_child_transcript_path: Path | None = None

    try:
        launch_authority, _ = collect_app_server_launch_authority(
            refresh_paths,
            scratch_cwd=scratch,
            roundtrip=lambda **_kwargs: list(readonly_transcript),
        )
        launch_authority_path = isolated_run_root / "launch-authority.json"
        write_json_artifact(launch_authority_path, serialize_authority_record(launch_authority))
        launch_authority_sha = write_sha256_file(launch_authority_path)
        artifact_copy(launch_authority_path, durable_root)
        artifact_copy(launch_authority_sha, durable_root)

        pre_install_authority = build_pre_install_target_authority(
            launch_authority=launch_authority,
            marketplace_path=refresh_paths.marketplace_path,
            remote_marketplace_name=None,
            allow_real_codex_home=False,
        )
        pre_install_authority_path = isolated_run_root / "preinstall-target-authority.json"
        write_json_artifact(
            pre_install_authority_path,
            serialize_authority_record(pre_install_authority),
        )
        pre_install_authority_sha = write_sha256_file(pre_install_authority_path)
        artifact_copy(pre_install_authority_path, durable_root)
        artifact_copy(pre_install_authority_sha, durable_root)

        blocker_stage = "pre-install-target-authority"
        install_requests = build_install_requests(
            pre_install_authority=pre_install_authority,
            expected_requested_codex_home=isolated_home,
            expected_launch_authority_sha256=authority_digest(launch_authority),
            expected_marketplace_path=refresh_paths.marketplace_path,
        )
        install_roundtrip_requests = [
            {
                "id": 0,
                "method": "initialize",
                "params": {
                    "clientInfo": {"name": "turbo-mode-installed-refresh", "version": "0"},
                    "capabilities": {"experimentalApi": True},
                },
            },
            {"method": "initialized"},
            *install_requests,
            *build_same_child_post_install_requests(refresh_paths, scratch_cwd=scratch),
        ]
        blocker_stage = "isolated-install-authority"
        install_transcript_path = isolated_run_root / "install.transcript.json"

        def repair_ticket_hook_after_install(
            request: dict[str, object],
            response: dict[str, object],
            _transcript: list[dict[str, object]],
        ) -> None:
            if request.get("id") != 2 or response.get("id") != 2:
                return
            rewrite_ticket_hook_manifest(
                ticket_plugin_root=isolated_home
                / "plugins/cache/turbo-mode/ticket/1.4.0"
            )

        install_transcript_live = tuple(
            app_server_roundtrip(
                install_roundtrip_requests,
                env_overrides={"CODEX_HOME": str(isolated_home)},
                cwd=scratch,
                after_response=repair_ticket_hook_after_install,
            )
        )
        write_json_artifact(install_transcript_path, install_transcript_live)
        install_transcript_sha = write_sha256_file(install_transcript_path)
        artifact_copy(install_transcript_path, durable_root)
        artifact_copy(install_transcript_sha, durable_root)

        same_child_post_install_transcript = normalize_same_child_post_install_transcript(
            install_transcript_live
        )
        same_child_transcript_path = isolated_run_root / "same-child-post-install.transcript.json"
        write_json_artifact(same_child_transcript_path, same_child_post_install_transcript)
        same_child_transcript_sha = write_sha256_file(same_child_transcript_path)
        artifact_copy(same_child_transcript_path, durable_root)
        artifact_copy(same_child_transcript_sha, durable_root)

        fresh_child_post_install_transcript = tuple(
            app_server_roundtrip(
                build_readonly_inventory_requests(refresh_paths, scratch_cwd=scratch),
                env_overrides={"CODEX_HOME": str(isolated_home)},
                cwd=scratch,
            )
        )
        fresh_child_transcript_path = isolated_run_root / "fresh-child-post-install.transcript.json"
        write_json_artifact(fresh_child_transcript_path, fresh_child_post_install_transcript)
        fresh_child_transcript_sha = write_sha256_file(fresh_child_transcript_path)
        artifact_copy(fresh_child_transcript_path, durable_root)
        artifact_copy(fresh_child_transcript_sha, durable_root)

        install_authority = validate_install_responses(
            transcript=install_transcript_live,
            launch_authority=launch_authority,
            pre_install_authority=pre_install_authority,
            install_requests=tuple(install_requests),
            same_child_post_install_transcript=same_child_post_install_transcript,
            fresh_child_post_install_transcript=fresh_child_post_install_transcript,
        )
        install_authority_path = isolated_run_root / "install-authority.json"
        write_json_artifact(install_authority_path, serialize_authority_record(install_authority))
        install_authority_sha = write_sha256_file(install_authority_path)
        artifact_copy(install_authority_path, durable_root)
        artifact_copy(install_authority_sha, durable_root)
    except RefreshError as exc:
        responses = {
            item["body"]["id"]: item["body"]["result"]
            for item in readonly_transcript
            if item.get("direction") == "recv"
            and isinstance(item.get("body"), dict)
            and isinstance(item["body"].get("id"), int)
        }
        skills_count, hooks_count = blocker_inventory_counts(responses)
        blocker = {
            "run_id": run_id,
            "stage": blocker_stage,
            "error": str(exc),
            "isolated_codex_home": str(isolated_home),
            "scratch_cwd": str(scratch),
            "readonly_transcript_path": str(readonly_transcript_path),
            "readonly_transcript_sha256": sha256_file(readonly_transcript_path),
            "initialize_codex_home": responses.get(0, {}).get("codexHome"),
            "skills_count": skills_count,
            "hooks_count": hooks_count,
            "durable_artifact_root": str(durable_root),
        }
        if install_transcript_path is not None and install_transcript_path.exists():
            blocker["install_transcript_path"] = str(install_transcript_path)
            blocker["install_transcript_sha256"] = sha256_file(install_transcript_path)
        if same_child_transcript_path is not None and same_child_transcript_path.exists():
            blocker["same_child_post_install_transcript_path"] = str(same_child_transcript_path)
            blocker["same_child_post_install_transcript_sha256"] = sha256_file(
                same_child_transcript_path
            )
        if fresh_child_transcript_path is not None and fresh_child_transcript_path.exists():
            blocker["fresh_child_post_install_transcript_path"] = str(fresh_child_transcript_path)
            blocker["fresh_child_post_install_transcript_sha256"] = sha256_file(
                fresh_child_transcript_path
            )
        blocker_path = isolated_run_root / "authority-blocker.json"
        write_json_artifact(blocker_path, blocker)
        blocker_sha = write_sha256_file(blocker_path)
        artifact_copy(blocker_path, durable_root)
        artifact_copy(blocker_sha, durable_root)
        pytest.fail(
            f"Task 1A blocked; see {blocker_path} and {durable_root / blocker_path.name}"
        )

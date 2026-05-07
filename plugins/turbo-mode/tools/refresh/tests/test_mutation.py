from __future__ import annotations

import json
import shutil
from pathlib import Path

import pytest
import refresh.mutation as mutation_module
from refresh.app_server_inventory import (
    AppServerInstallAuthority,
    AppServerLaunchAuthority,
    AppServerPreInstallTargetAuthority,
    authority_digest,
)
from refresh.models import RefreshError
from refresh.mutation import (
    MutationContext,
    abort_after_config_mutation,
    create_snapshot_set,
    install_plugins_via_app_server,
    prepare_plugin_hooks_for_guarded_refresh,
    prove_app_server_home_authority,
    restore_config_snapshot,
    rollback_guarded_refresh,
    verify_source_cache_equality,
)

RUN_ID = "mutation-run"
MODE = "guarded-refresh"
SOURCE_COMMIT = "source-commit"
SOURCE_TREE = "source-tree"
EXECUTION_HEAD = "execution-head"
EXECUTION_TREE = "execution-tree"
TOOL_SHA256 = "tool-sha"
DISABLED_CONFIG_TEXT = "[features]\nplugin_hooks = false\n"
LIVE_HOME_SKILL_PATH = (
    "/Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0/skills/save/SKILL.md"
)


def context(tmp_path: Path, *, codex_home: Path | None = None) -> MutationContext:
    active_home = codex_home or (tmp_path / "isolated-home")
    return MutationContext(
        run_id=RUN_ID,
        mode=MODE,
        repo_root=tmp_path / "repo",
        codex_home=active_home,
        local_only_run_root=active_home / "local-only/turbo-mode-refresh" / RUN_ID,
        source_implementation_commit=SOURCE_COMMIT,
        source_implementation_tree=SOURCE_TREE,
        execution_head=EXECUTION_HEAD,
        execution_tree=EXECUTION_TREE,
        tool_sha256=TOOL_SHA256,
    )


def seed_plugins(ctx: MutationContext, *, cache_text: str = "same") -> None:
    for plugin, version in (("handoff", "1.6.0"), ("ticket", "1.4.0")):
        source = ctx.repo_root / f"plugins/turbo-mode/{plugin}/{version}"
        cache = ctx.codex_home / f"plugins/cache/turbo-mode/{plugin}/{version}"
        source.mkdir(parents=True, exist_ok=True)
        cache.mkdir(parents=True, exist_ok=True)
        (source / "plugin.json").write_text(
            json.dumps({"name": plugin, "version": version}) + "\n",
            encoding="utf-8",
        )
        (cache / "plugin.json").write_text(
            json.dumps({"name": plugin, "version": version}) + "\n",
            encoding="utf-8",
        )
        (source / "payload.txt").write_text("same", encoding="utf-8")
        (cache / "payload.txt").write_text(cache_text, encoding="utf-8")
    marketplace = ctx.repo_root / ".agents/plugins/marketplace.json"
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    marketplace.write_text("{}\n", encoding="utf-8")


def seed_config(ctx: MutationContext, text: str = "[features]\nplugin_hooks = true\n") -> None:
    ctx.codex_home.mkdir(parents=True, exist_ok=True)
    (ctx.codex_home / "config.toml").write_text(text, encoding="utf-8")


def launch_authority(ctx: MutationContext) -> AppServerLaunchAuthority:
    return AppServerLaunchAuthority(
        requested_codex_home=str(ctx.codex_home),
        resolved_config_path=str(ctx.codex_home / "config.toml"),
        resolved_plugin_cache_root=str(ctx.codex_home / "plugins/cache/turbo-mode"),
        resolved_local_only_root=str(ctx.codex_home / "local-only/turbo-mode-refresh"),
        binding_mechanism_name="env:CODEX_HOME",
        binding_mechanism_value=str(ctx.codex_home),
        child_environment_delta={"CODEX_HOME": str(ctx.codex_home)},
        child_cwd=str(ctx.local_only_run_root),
        executable_path="/usr/local/bin/codex",
        executable_sha256="codex-sha",
        executable_hash_unavailable_reason=None,
        codex_version="codex-cli 0.test",
        initialize_server_info={"name": "codex-app-server"},
        initialize_capabilities={"experimentalApi": True},
        initialize_result={"codexHome": str(ctx.codex_home)},
        accepted_response_schema_version="app-server-readonly-inventory-v1",
        candidate_mechanisms_checked=(),
        plugin_read_sources={"handoff": str(ctx.repo_root), "ticket": str(ctx.repo_root)},
        skill_paths=(
            str(
                ctx.codex_home
                / "plugins/cache/turbo-mode/handoff/1.6.0/skills/save/SKILL.md"
            ),
        ),
        hook_paths=(
            str(ctx.codex_home / "plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json"),
        ),
    )


def pre_install_authority(
    ctx: MutationContext,
    launch: AppServerLaunchAuthority,
) -> AppServerPreInstallTargetAuthority:
    return AppServerPreInstallTargetAuthority(
        requested_codex_home=str(ctx.codex_home),
        install_destination_root=str(ctx.codex_home / "plugins/cache/turbo-mode"),
        resolved_plugin_cache_root=str(ctx.codex_home / "plugins/cache/turbo-mode"),
        binding_mechanism_name=launch.binding_mechanism_name,
        binding_mechanism_value=launch.binding_mechanism_value,
        launch_authority_sha256=authority_digest(launch),
        marketplace_path=str(ctx.repo_root / ".agents/plugins/marketplace.json"),
        remote_marketplace_name=None,
        no_real_home_paths=not str(ctx.codex_home).startswith("/Users/jp/.codex"),
        pre_install_cache_manifest_sha256={"handoff": "pre-handoff", "ticket": "pre-ticket"},
    )


def install_authority(
    ctx: MutationContext,
    launch: AppServerLaunchAuthority,
) -> AppServerInstallAuthority:
    pre = pre_install_authority(ctx, launch)
    return AppServerInstallAuthority(
        requested_codex_home=str(ctx.codex_home),
        launch_authority_sha256=authority_digest(launch),
        pre_install_target_authority_sha256=authority_digest(pre),
        install_request_sha256={"handoff": "request-handoff", "ticket": "request-ticket"},
        install_response_sha256={"handoff": "response-handoff", "ticket": "response-ticket"},
        same_child_post_install_corroboration_sha256="same-child",
        fresh_child_post_install_corroboration_sha256="fresh-child",
        installed_destination_paths={
            "handoff": str(ctx.codex_home / "plugins/cache/turbo-mode/handoff/1.6.0"),
            "ticket": str(ctx.codex_home / "plugins/cache/turbo-mode/ticket/1.4.0"),
        },
        accepted_install_response_schema_by_plugin={
            "handoff": "sparse-success-auth-v1",
            "ticket": "sparse-success-auth-v1",
        },
        pre_install_cache_manifest_sha256=pre.pre_install_cache_manifest_sha256,
        post_install_cache_manifest_sha256={"handoff": "post-handoff", "ticket": "post-ticket"},
        cache_manifest_delta_sha256={"handoff": "delta-handoff", "ticket": "delta-ticket"},
    )


def test_snapshot_captures_config_and_cache_manifest(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    snapshot = create_snapshot_set(ctx)
    assert (
        snapshot.config_snapshot_path.read_text(encoding="utf-8")
        == "[features]\nplugin_hooks = true\n"
    )
    assert snapshot.config_sha256
    assert snapshot.cache_snapshot_root.exists()
    assert set(snapshot.source_manifest_sha256) == {"handoff", "ticket"}
    assert set(snapshot.pre_refresh_cache_manifest_sha256) == {"handoff", "ticket"}


def test_guarded_hook_disable_only_writes_from_true(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    result = prepare_plugin_hooks_for_guarded_refresh(ctx, plugin_hooks_state="true")
    assert "plugin_hooks = false" in (ctx.codex_home / "config.toml").read_text(encoding="utf-8")
    assert result["plugin_hooks_start_state"] == "true"
    assert result["hook_disabled_config_sha256"] != result["original_config_sha256"]


def test_absent_default_enabled_preserves_config_bytes(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_config(ctx, "[features]\n")
    before = (ctx.codex_home / "config.toml").read_bytes()
    result = prepare_plugin_hooks_for_guarded_refresh(
        ctx,
        plugin_hooks_state="absent-default-enabled",
    )
    assert (ctx.codex_home / "config.toml").read_bytes() == before
    assert result["expected_intermediate_config_sha256"] == result["original_config_sha256"]


@pytest.mark.parametrize("state", ["absent-unproven", "absent-disabled", "false", "malformed"])
def test_unsafe_hook_states_fail_before_cache_mutation(tmp_path: Path, state: str) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    with pytest.raises(RefreshError):
        prepare_plugin_hooks_for_guarded_refresh(ctx, plugin_hooks_state=state)


def test_restore_config_snapshot_rejects_external_change(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    snapshot = create_snapshot_set(ctx)
    (ctx.codex_home / "config.toml").write_text(DISABLED_CONFIG_TEXT, encoding="utf-8")
    with pytest.raises(RefreshError, match="current config SHA256 mismatch"):
        restore_config_snapshot(snapshot, current_expected_sha256="not-current")
    restore_config_snapshot(snapshot, current_expected_sha256=None)
    assert (
        (ctx.codex_home / "config.toml").read_bytes()
        == snapshot.config_snapshot_path.read_bytes()
    )


def test_prove_app_server_home_authority_rejects_real_home_leak(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    authority = launch_authority(ctx)
    leaked = AppServerLaunchAuthority(
        **{
            **authority.__dict__,
            "skill_paths": (LIVE_HOME_SKILL_PATH,),
        }
    )
    monkeypatch.setattr(
        mutation_module,
        "collect_app_server_launch_authority",
        lambda paths: (leaked, ()),
    )
    with pytest.raises(RefreshError, match="live Codex home"):
        prove_app_server_home_authority(ctx)


def test_install_uses_app_server_plugin_install_after_authority_proofs(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    seed_plugins(ctx)
    launch = launch_authority(ctx)
    pre = pre_install_authority(ctx, launch)
    installed = install_authority(ctx, launch)
    order: list[str] = []

    monkeypatch.setattr(
        mutation_module,
        "collect_app_server_launch_authority",
        lambda paths: order.append("launch") or (launch, ()),
    )
    monkeypatch.setattr(
        mutation_module,
        "build_pre_install_target_authority",
        lambda **kwargs: order.append("pre") or pre,
    )

    def fake_roundtrip(**kwargs: object) -> tuple[dict[str, object], ...]:
        order.append("install")
        requests = kwargs["requests"]
        assert [request["method"] for request in requests] == ["plugin/install", "plugin/install"]
        assert [request["params"]["pluginName"] for request in requests] == ["handoff", "ticket"]
        assert all(request["params"]["remoteMarketplaceName"] is None for request in requests)
        return (
            {
                "direction": "recv",
                "body": {
                    "id": 1,
                    "result": {"appsNeedingAuth": [], "authPolicy": "ON_INSTALL"},
                },
            },
            {
                "direction": "recv",
                "body": {
                    "id": 2,
                    "result": {"appsNeedingAuth": [], "authPolicy": "ON_INSTALL"},
                },
            },
        )

    monkeypatch.setattr(mutation_module, "app_server_roundtrip", fake_roundtrip)
    monkeypatch.setattr(
        mutation_module,
        "validate_install_responses",
        lambda **kwargs: order.append("validate") or installed,
    )
    monkeypatch.setattr(
        mutation_module,
        "collect_readonly_runtime_inventory",
        lambda paths: ("inventory", ()),
    )
    result = install_plugins_via_app_server(ctx)
    assert order == ["launch", "pre", "install", "validate"]
    assert result[0]["kind"] == "install-authority"
    assert result[0]["install_authority"]["requested_codex_home"] == str(ctx.codex_home)


def test_real_home_install_requires_durable_snapshot_marker_before_app_server(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path, codex_home=Path("/Users/jp/.codex"))
    called = False

    def fail_if_called(paths: object) -> object:
        nonlocal called
        called = True
        return object()

    monkeypatch.setattr(mutation_module, "collect_app_server_launch_authority", fail_if_called)
    with pytest.raises(RefreshError, match="snapshot marker"):
        install_plugins_via_app_server(ctx)
    assert called is False


def test_install_rejects_stale_pre_install_authority_before_request(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    launch = launch_authority(ctx)
    pre = AppServerPreInstallTargetAuthority(
        **{**pre_install_authority(ctx, launch).__dict__, "launch_authority_sha256": "stale"}
    )
    monkeypatch.setattr(
        mutation_module,
        "collect_app_server_launch_authority",
        lambda paths: (launch, ()),
    )
    monkeypatch.setattr(mutation_module, "build_pre_install_target_authority", lambda **kwargs: pre)
    monkeypatch.setattr(
        mutation_module,
        "app_server_roundtrip",
        lambda **kwargs: pytest.fail("install request should not start"),
    )
    with pytest.raises(RefreshError, match="pre-install target authority stale"):
        install_plugins_via_app_server(ctx)


def test_verify_source_cache_equality_detects_drift(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_plugins(ctx, cache_text="different")
    with pytest.raises(RefreshError, match="source/cache manifest mismatch"):
        verify_source_cache_equality(ctx)
    shutil.copytree(
        ctx.repo_root / "plugins/turbo-mode/handoff/1.6.0",
        ctx.codex_home / "plugins/cache/turbo-mode/handoff/1.6.0",
        dirs_exist_ok=True,
    )
    shutil.copytree(
        ctx.repo_root / "plugins/turbo-mode/ticket/1.4.0",
        ctx.codex_home / "plugins/cache/turbo-mode/ticket/1.4.0",
        dirs_exist_ok=True,
    )
    assert set(verify_source_cache_equality(ctx)) == {"handoff", "ticket"}


def test_rollback_restores_config_and_cache_from_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    snapshot = create_snapshot_set(ctx)
    (ctx.codex_home / "config.toml").write_text(DISABLED_CONFIG_TEXT, encoding="utf-8")
    (ctx.codex_home / "plugins/cache/turbo-mode/handoff/1.6.0/payload.txt").write_text(
        "changed",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        mutation_module,
        "collect_readonly_runtime_inventory",
        lambda paths: ("inventory", ()),
    )
    result = rollback_guarded_refresh(ctx, snapshot, failed_phase="install-complete")
    assert result["final_status"] == "rollback-complete"
    assert "plugin_hooks = true" in (ctx.codex_home / "config.toml").read_text(encoding="utf-8")
    assert (ctx.codex_home / "plugins/cache/turbo-mode/handoff/1.6.0/payload.txt").read_text(
        encoding="utf-8"
    ) == "same"


def test_rollback_rejects_missing_snapshot_manifest(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    snapshot = create_snapshot_set(ctx)
    snapshot.snapshot_manifest_path.unlink()
    with pytest.raises(RefreshError, match="snapshot manifest"):
        rollback_guarded_refresh(ctx, snapshot, failed_phase="install-complete")


def test_abort_after_config_mutation_restores_config_only(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    snapshot = create_snapshot_set(ctx)
    (ctx.codex_home / "config.toml").write_text(DISABLED_CONFIG_TEXT, encoding="utf-8")
    result = abort_after_config_mutation(ctx, snapshot, failed_phase="after-hook-disable")
    assert result["final_status"] == "config-restored"
    assert "plugin_hooks = true" in (ctx.codex_home / "config.toml").read_text(encoding="utf-8")

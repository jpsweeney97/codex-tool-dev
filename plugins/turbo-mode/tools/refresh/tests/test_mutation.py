from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path

import pytest
import refresh.mutation as mutation_module
from refresh.app_server_inventory import (
    AppServerLaunchAuthority,
    AppServerPreInstallTargetAuthority,
    BindingCandidate,
    authority_digest,
)
from refresh.models import RefreshError
from refresh.mutation import (
    MutationContext,
    abort_after_config_mutation,
    create_snapshot_set,
    install_plugins_via_app_server,
    prepare_plugin_hooks_for_guarded_refresh,
    rollback_guarded_refresh,
    verify_source_cache_equality,
    verify_source_execution_identity,
)

RUN_ID = "mutation-run"
SOURCE_COMMIT = "source-commit"
SOURCE_TREE = "source-tree"
EXECUTION_HEAD = "execution-head"
EXECUTION_TREE = "execution-tree"
TOOL_SHA256 = "tool-sha"


def context(tmp_path: Path, *, codex_home: Path | None = None) -> MutationContext:
    active_home = codex_home or (tmp_path / "isolated-home")
    return MutationContext(
        run_id=RUN_ID,
        mode="guarded-refresh",
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
    for plugin, version in (("handoff", "1.7.0"), ("review-family", "0.1.0")):
        source = ctx.repo_root / f"plugins/turbo-mode/{plugin}"
        cache = ctx.codex_home / f"plugins/cache/turbo-mode/{plugin}/{version}"
        source.mkdir(parents=True, exist_ok=True)
        cache.mkdir(parents=True, exist_ok=True)
        (source / ".codex-plugin").mkdir(exist_ok=True)
        (cache / ".codex-plugin").mkdir(exist_ok=True)
        manifest = json.dumps({"name": plugin, "version": version}) + "\n"
        (source / ".codex-plugin/plugin.json").write_text(manifest, encoding="utf-8")
        (cache / ".codex-plugin/plugin.json").write_text(manifest, encoding="utf-8")
        (source / "README.md").write_text("same", encoding="utf-8")
        (cache / "README.md").write_text(cache_text, encoding="utf-8")
    marketplace = ctx.repo_root / ".agents/plugins/marketplace.json"
    marketplace.parent.mkdir(parents=True, exist_ok=True)
    marketplace.write_text(
        json.dumps(
            {
                "name": "turbo-mode",
                "plugins": [
                    {
                        "name": "handoff",
                        "source": {
                            "source": "local",
                            "path": "./plugins/turbo-mode/handoff",
                        },
                    },
                    {
                        "name": "review-family",
                        "source": {
                            "source": "local",
                            "path": "./plugins/turbo-mode/review-family",
                        },
                    },
                ],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def seed_config(ctx: MutationContext, text: str | None = None) -> None:
    ctx.codex_home.mkdir(parents=True, exist_ok=True)
    (ctx.codex_home / "config.toml").write_text(
        text
        or (
            f'[marketplaces.turbo-mode]\nsource_type = "local"\nsource = "{ctx.repo_root}"\n'
            "[features]\nplugin_hooks = true\n"
            '[plugins."handoff@turbo-mode"]\nenabled = true\n'
            '[plugins."review-family@turbo-mode"]\nenabled = true\n'
        ),
        encoding="utf-8",
    )


def launch_authority(ctx: MutationContext) -> AppServerLaunchAuthority:
    return AppServerLaunchAuthority(
        requested_codex_home=str(ctx.codex_home),
        resolved_config_path=str(ctx.codex_home / "config.toml"),
        resolved_plugin_cache_root=str(ctx.codex_home / "plugins/cache"),
        resolved_local_only_root=str(ctx.codex_home / "local-only"),
        binding_mechanism_name="CODEX_HOME",
        binding_mechanism_value=str(ctx.codex_home),
        child_environment_delta={"CODEX_HOME": str(ctx.codex_home)},
        child_cwd=str(ctx.repo_root),
        executable_path="/usr/bin/codex",
        executable_sha256="codex-sha",
        executable_hash_unavailable_reason=None,
        codex_version="codex-cli 0.test",
        initialize_server_info={"name": "codex-app-server"},
        initialize_capabilities={"experimentalApi": True},
        initialize_result={"codexHome": str(ctx.codex_home)},
        accepted_response_schema_version="app-server-readonly-inventory-v1",
        candidate_mechanisms_checked=(
            BindingCandidate(
                category="env",
                name="CODEX_HOME",
                supported=True,
                selected=True,
                observed_value=str(ctx.codex_home),
            ),
        ),
        plugin_read_sources={
            "handoff": str(ctx.repo_root / "plugins/turbo-mode/handoff"),
            "review-family": str(ctx.repo_root / "plugins/turbo-mode/review-family"),
        },
        skill_paths=(),
        hook_paths=(),
    )


def pre_install_authority(ctx: MutationContext, launch: AppServerLaunchAuthority):
    return AppServerPreInstallTargetAuthority(
        requested_codex_home=str(ctx.codex_home),
        install_destination_root=str(ctx.codex_home / "plugins/cache/turbo-mode"),
        resolved_plugin_cache_root=str(ctx.codex_home / "plugins/cache"),
        binding_mechanism_name=launch.binding_mechanism_name,
        binding_mechanism_value=launch.binding_mechanism_value,
        launch_authority_sha256=authority_digest(launch),
        marketplace_path=str(ctx.repo_root / ".agents/plugins/marketplace.json"),
        remote_marketplace_name=None,
        no_real_home_paths=True,
        pre_install_cache_manifest_sha256={
            "handoff": "handoff-pre",
            "review-family": "review-pre",
        },
    )


def test_verify_source_cache_equality_uses_active_plugin_set(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_plugins(ctx)

    equality = verify_source_cache_equality(ctx)

    assert set(equality) == {"handoff", "review-family"}
    assert all(isinstance(value, str) and value for value in equality.values())


def test_verify_source_cache_equality_detects_drift(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_plugins(ctx, cache_text="different")

    with pytest.raises(RefreshError, match="source/cache manifest mismatch"):
        verify_source_cache_equality(ctx)


def test_snapshot_captures_config_and_active_cache_manifests(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)

    snapshot = create_snapshot_set(ctx)

    assert snapshot.config_snapshot_path.exists()
    assert snapshot.snapshot_manifest_path.exists()
    assert set(snapshot.source_manifest_sha256) == {"handoff", "review-family"}
    assert snapshot.pre_refresh_cache_root_exists == {
        "handoff": True,
        "review-family": True,
    }
    assert (
        snapshot.cache_snapshot_root / "handoff/1.7.0/README.md"
    ).read_text(encoding="utf-8") == "same"


def test_snapshot_records_missing_installable_review_family_cache(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    shutil.rmtree(ctx.codex_home / "plugins/cache/turbo-mode/review-family/0.1.0")

    snapshot = create_snapshot_set(ctx)

    assert snapshot.pre_refresh_cache_root_exists == {
        "handoff": True,
        "review-family": False,
    }


def test_prepare_plugin_hooks_disables_true_config_and_rejects_false(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)

    result = prepare_plugin_hooks_for_guarded_refresh(ctx, plugin_hooks_state="true")

    assert result["plugin_hooks_start_state"] == "true"
    assert "plugin_hooks = false" in (ctx.codex_home / "config.toml").read_text(
        encoding="utf-8"
    )
    with pytest.raises(RefreshError, match="unsafe plugin_hooks state"):
        prepare_plugin_hooks_for_guarded_refresh(ctx, plugin_hooks_state="false")


def test_prepare_plugin_hooks_absent_state_leaves_config_unchanged(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_config(ctx, "[features]\n")
    original = (ctx.codex_home / "config.toml").read_text(encoding="utf-8")

    result = prepare_plugin_hooks_for_guarded_refresh(
        ctx,
        plugin_hooks_state="absent-default-enabled",
    )

    assert result["original_config_sha256"] == result["hook_disabled_config_sha256"]
    assert (ctx.codex_home / "config.toml").read_text(encoding="utf-8") == original


def test_abort_after_config_mutation_restores_config_snapshot(tmp_path: Path) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    snapshot = create_snapshot_set(ctx)
    (ctx.codex_home / "config.toml").write_text("[features]\nplugin_hooks = false\n")

    result = abort_after_config_mutation(ctx, snapshot, failed_phase="unit")

    assert result["final_status"] == "config-restored"
    assert "plugin_hooks = true" in (ctx.codex_home / "config.toml").read_text(
        encoding="utf-8"
    )


def test_rollback_restores_config_and_cache_from_snapshot(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    snapshot = create_snapshot_set(ctx)
    (ctx.codex_home / "config.toml").write_text("[features]\nplugin_hooks = false\n")
    (ctx.codex_home / "plugins/cache/turbo-mode/handoff/1.7.0/README.md").write_text(
        "changed",
        encoding="utf-8",
    )
    monkeypatch.setattr(
        mutation_module,
        "collect_readonly_runtime_inventory",
        lambda paths, **kwargs: ("inventory", ()),
    )

    result = rollback_guarded_refresh(ctx, snapshot, failed_phase="unit")

    assert result["final_status"] == "rollback-complete"
    assert "plugin_hooks = true" in (ctx.codex_home / "config.toml").read_text(
        encoding="utf-8"
    )
    assert (
        ctx.codex_home / "plugins/cache/turbo-mode/handoff/1.7.0/README.md"
    ).read_text(encoding="utf-8") == "same"


def test_rollback_restores_missing_review_family_cache_absence(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    review_cache = ctx.codex_home / "plugins/cache/turbo-mode/review-family/0.1.0"
    shutil.rmtree(review_cache)
    snapshot = create_snapshot_set(ctx)
    review_cache.mkdir(parents=True)
    (review_cache / "README.md").write_text("installed", encoding="utf-8")
    observed_allowances: list[tuple[str, ...]] = []

    def fake_inventory(_paths: object, *, allow_missing_plugins: tuple[str, ...] = ()):
        observed_allowances.append(allow_missing_plugins)
        return "inventory", ()

    monkeypatch.setattr(mutation_module, "collect_readonly_runtime_inventory", fake_inventory)

    rollback_guarded_refresh(ctx, snapshot, failed_phase="unit")

    assert not review_cache.exists()
    assert observed_allowances == [("review-family",)]


def test_install_uses_app_server_plugin_install_for_active_plugins(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    launch = launch_authority(ctx)
    pre = pre_install_authority(ctx, launch)
    observed: dict[str, object] = {}

    monkeypatch.setattr(
        mutation_module,
        "prove_app_server_home_authority",
        lambda active_context, **kwargs: launch,
    )
    monkeypatch.setattr(
        mutation_module,
        "build_pre_install_target_authority",
        lambda **kwargs: pre,
    )

    def fake_roundtrip(**kwargs: object) -> tuple[dict[str, object], ...]:
        requests = list(kwargs["requests"])
        observed["methods"] = [request["method"] for request in requests]
        observed["install_plugins"] = [
            request["params"]["pluginName"]
            for request in requests
            if request["method"] == "plugin/install"
        ]
        after_response = kwargs.get("after_response")
        transcript: list[dict[str, object]] = []
        for request in requests:
            if request.get("method") != "plugin/install":
                continue
            response = {
                "direction": "recv",
                "body": {
                    "id": request["id"],
                    "result": {"appsNeedingAuth": [], "authPolicy": "ON_INSTALL"},
                },
            }
            transcript.append(response)
            if callable(after_response):
                after_response(request, response["body"], transcript)
        return tuple(transcript)

    monkeypatch.setattr(mutation_module, "app_server_roundtrip", fake_roundtrip)
    monkeypatch.setattr(
        mutation_module,
        "validate_install_responses",
        lambda **kwargs: {
            "requested_codex_home": str(ctx.codex_home),
            "installed_destination_paths": {},
        },
    )
    monkeypatch.setattr(
        mutation_module,
        "collect_readonly_runtime_inventory",
        lambda paths: ("inventory", ()),
    )

    result = install_plugins_via_app_server(ctx)

    assert observed["methods"] == [
        "initialize",
        "initialized",
        "plugin/install",
        "plugin/install",
        "plugin/read",
        "plugin/list",
        "skills/list",
        "hooks/list",
        "plugin/read",
    ]
    assert observed["install_plugins"] == ["handoff", "review-family"]
    assert result[0]["kind"] == "install-authority"


def test_verify_source_execution_identity_accepts_clean_matching_tree(
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo, check=True)
    (repo / "README.md").write_text("baseline\n", encoding="utf-8")
    subprocess.run(["git", "add", "."], cwd=repo, check=True)
    subprocess.run(["git", "commit", "-qm", "baseline"], cwd=repo, check=True)
    head = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()
    tree = subprocess.run(
        ["git", "rev-parse", f"{head}^{{tree}}"],
        cwd=repo,
        text=True,
        capture_output=True,
        check=True,
    ).stdout.strip()

    proof = verify_source_execution_identity(
        repo_root=repo,
        local_only_run_root=tmp_path / "run",
        source_implementation_commit=head,
        source_implementation_tree=tree,
    )

    assert proof.execution_head == head
    assert proof.execution_tree == tree
    assert proof.allowed_delta_status == "none"
    assert Path(proof.proof_path).exists()


def test_seed_fixture_tracks_current_handoff_layout() -> None:
    fixture = json.loads(
        (Path(__file__).parent / "fixtures" / "isolated_seed_drift.json").read_text(
            encoding="utf-8"
        )
    )

    assert tuple(fixture) == (
        "handoff/1.7.0/turbo_mode_handoff_runtime/project_paths.py",
    )

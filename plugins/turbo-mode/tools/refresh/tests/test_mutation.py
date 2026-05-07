from __future__ import annotations

import hashlib
import json
import shutil
from pathlib import Path

import pytest
import refresh.lock_state as lock_state_module
import refresh.mutation as mutation_module
from refresh.app_server_inventory import (
    AppServerInstallAuthority,
    AppServerLaunchAuthority,
    AppServerPreInstallTargetAuthority,
    authority_digest,
)
from refresh.lock_state import LockOwner, RunState, write_initial_run_state
from refresh.models import RefreshError
from refresh.mutation import (
    GuardedRefreshResult,
    MutationContext,
    abort_after_config_mutation,
    create_snapshot_set,
    install_plugins_via_app_server,
    prepare_plugin_hooks_for_guarded_refresh,
    prove_app_server_home_authority,
    restore_config_snapshot,
    rollback_guarded_refresh,
    run_guarded_refresh_orchestration,
    run_guarded_refresh_recovery,
    verify_source_cache_equality,
    verify_source_execution_identity,
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
RELEVANT_TOOL_PATH = "plugins/turbo-mode/tools/refresh/orchestration.py"
APPROVED_EVIDENCE_PATH = "plugins/turbo-mode/evidence/refresh/notes.md"


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


def init_git_repo(repo_root: Path) -> None:
    import subprocess

    subprocess.run(["git", "init", "-q"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.email", "test@example.com"], cwd=repo_root, check=True)
    subprocess.run(["git", "config", "user.name", "Test User"], cwd=repo_root, check=True)


def git(repo_root: Path, *args: str) -> str:
    import subprocess

    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def write_repo_file(repo_root: Path, rel: str, text: str) -> None:
    path = repo_root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def commit_repo(repo_root: Path, message: str) -> str:
    git(repo_root, "add", ".")
    git(repo_root, "commit", "-qm", message)
    return git(repo_root, "rev-parse", "HEAD")


def source_identity_repo(tmp_path: Path) -> tuple[Path, Path, str, str]:
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    init_git_repo(repo_root)
    write_repo_file(repo_root, "README.md", "baseline\n")
    source_commit = commit_repo(repo_root, "source")
    source_tree = git(repo_root, "rev-parse", f"{source_commit}^{{tree}}")
    local_only_run_root = tmp_path / ".codex/local-only/turbo-mode-refresh/run"
    return repo_root, local_only_run_root, source_commit, source_tree


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


def test_source_identity_rejects_tree_mismatch_before_evidence_or_mutation(
    tmp_path: Path,
) -> None:
    repo_root, local_only_run_root, source_commit, _source_tree = source_identity_repo(tmp_path)

    with pytest.raises(RefreshError, match="source implementation tree mismatch"):
        verify_source_execution_identity(
            repo_root=repo_root,
            local_only_run_root=local_only_run_root,
            source_implementation_commit=source_commit,
            source_implementation_tree="stale-tree",
        )

    assert not local_only_run_root.exists()


def test_source_identity_rejects_non_ancestor_before_delta_allowlist(
    tmp_path: Path,
) -> None:
    repo_root, local_only_run_root, source_commit, source_tree = source_identity_repo(tmp_path)
    git(repo_root, "checkout", "--orphan", "unrelated")
    write_repo_file(repo_root, "README.md", "unrelated\n")
    commit_repo(repo_root, "unrelated")

    with pytest.raises(RefreshError, match="source implementation commit is not an ancestor"):
        verify_source_execution_identity(
            repo_root=repo_root,
            local_only_run_root=local_only_run_root,
            source_implementation_commit=source_commit,
            source_implementation_tree=source_tree,
        )

    assert not local_only_run_root.exists()


def test_source_identity_rejects_disallowed_tracked_delta_before_evidence(
    tmp_path: Path,
) -> None:
    repo_root, local_only_run_root, source_commit, source_tree = source_identity_repo(tmp_path)
    write_repo_file(repo_root, RELEVANT_TOOL_PATH, "print('changed')\n")
    commit_repo(repo_root, "disallowed source delta")

    with pytest.raises(RefreshError, match="disallowed source-to-execution delta"):
        verify_source_execution_identity(
            repo_root=repo_root,
            local_only_run_root=local_only_run_root,
            source_implementation_commit=source_commit,
            source_implementation_tree=source_tree,
        )

    assert not local_only_run_root.exists()


def test_source_identity_allows_docs_evidence_delta_and_records_local_proof(
    tmp_path: Path,
) -> None:
    repo_root, local_only_run_root, source_commit, source_tree = source_identity_repo(tmp_path)
    write_repo_file(repo_root, APPROVED_EVIDENCE_PATH, "operator note\n")
    execution_head = commit_repo(repo_root, "approved evidence delta")
    execution_tree = git(repo_root, "rev-parse", f"{execution_head}^{{tree}}")

    proof = verify_source_execution_identity(
        repo_root=repo_root,
        local_only_run_root=local_only_run_root,
        source_implementation_commit=source_commit,
        source_implementation_tree=source_tree,
    )

    assert proof.source_implementation_commit == source_commit
    assert proof.execution_head == execution_head
    assert proof.execution_tree == execution_tree
    assert proof.changed_paths == (APPROVED_EVIDENCE_PATH,)
    proof_path = local_only_run_root / "source-execution-identity.proof.json"
    assert proof_path.is_file()
    assert APPROVED_EVIDENCE_PATH in proof_path.read_text(encoding="utf-8")


def test_source_identity_rejects_untracked_relevant_file_before_evidence(
    tmp_path: Path,
) -> None:
    repo_root, local_only_run_root, source_commit, source_tree = source_identity_repo(tmp_path)
    write_repo_file(repo_root, RELEVANT_TOOL_PATH, "print('untracked')\n")

    with pytest.raises(RefreshError, match="untracked relevant files"):
        verify_source_execution_identity(
            repo_root=repo_root,
            local_only_run_root=local_only_run_root,
            source_implementation_commit=source_commit,
            source_implementation_tree=source_tree,
        )

    assert not local_only_run_root.exists()


def test_guarded_orchestration_rejects_unexpected_terminal_status_before_process_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)

    monkeypatch.setattr(
        mutation_module,
        "capture_process_gate",
        lambda **kwargs: pytest.fail("process gate should not run"),
    )

    with pytest.raises(RefreshError, match="terminal plan status is not guarded-refresh-required"):
        run_guarded_refresh_orchestration(
            ctx,
            terminal_plan_status="blocked-preflight",
            plugin_hooks_state="true",
            isolated_rehearsal=True,
        )


def test_isolated_guarded_orchestration_runs_core_phases_and_writes_rehearsal_proof(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    from contextlib import contextmanager

    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    launch = launch_authority(ctx)
    labels: list[str] = []
    order: list[str] = []

    @contextmanager
    def fake_lock(**kwargs: object):
        yield {"owner": "test", "run_id": kwargs["run_id"]}

    def fake_process_gate(**kwargs: object) -> dict[str, object]:
        label = str(kwargs["label"])
        labels.append(label)
        return {
            "label": label,
            "blocked_process_count": 0,
            "exclusivity_status": "exclusive_window_observed_by_process_samples",
        }

    monkeypatch.setattr(mutation_module, "acquire_refresh_lock", fake_lock)
    monkeypatch.setattr(mutation_module, "capture_process_gate", fake_process_gate)
    monkeypatch.setattr(
        mutation_module,
        "prove_app_server_home_authority",
        lambda active_context: order.append("authority") or launch,
    )

    def fake_install_plugins(
        _active_context: object,
        **kwargs: object,
    ) -> tuple[dict[str, str]]:
        restore = kwargs["restore_config_before_post_install"]
        assert callable(restore)
        restore()
        order.append("install")
        return ({"kind": "install-authority"},)

    monkeypatch.setattr(
        mutation_module,
        "install_plugins_via_app_server",
        fake_install_plugins,
    )
    monkeypatch.setattr(
        mutation_module,
        "collect_readonly_runtime_inventory",
        lambda paths: order.append("inventory") or ("inventory", ()),
    )
    monkeypatch.setattr(
        mutation_module,
        "run_standard_smoke",
        lambda **kwargs: order.append("smoke") or {"final_status": "passed"},
    )

    result = run_guarded_refresh_orchestration(
        ctx,
        terminal_plan_status="guarded-refresh-required",
        plugin_hooks_state="true",
        isolated_rehearsal=True,
    )

    assert isinstance(result, GuardedRefreshResult)
    assert result.final_status == "MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED"
    assert labels == ["before-snapshot", "after-hook-disable", "before-install", "post-mutation"]
    assert order == ["authority", "install", "inventory", "smoke"]
    assert "plugin_hooks = true" in (ctx.codex_home / "config.toml").read_text(encoding="utf-8")
    assert (ctx.local_only_run_root / "final-status.json").is_file()
    rehearsal_proof = ctx.local_only_run_root / "rehearsal-proof.json"
    assert rehearsal_proof.is_file()
    proof = json.loads(rehearsal_proof.read_text(encoding="utf-8"))
    assert proof["final_status"] == "MUTATION_REHEARSAL_COMPLETE_NON_CERTIFIED"
    assert proof["certification_status"] == "local-only-non-certified"
    assert not (
        ctx.local_only_run_root.parent / "run-state" / f"{ctx.run_id}.marker.json"
    ).exists()


def test_install_plugins_restores_hooks_before_same_child_corroboration(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    seed_plugins(ctx)
    seed_config(ctx, DISABLED_CONFIG_TEXT)
    launch = launch_authority(ctx)
    ticket_hook = ctx.codex_home / "plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json"
    observed: dict[str, object] = {}

    def restore_config() -> None:
        (ctx.codex_home / "config.toml").write_text(
            "[features]\nplugin_hooks = true\n",
            encoding="utf-8",
        )

    def fake_roundtrip(
        requests: list[dict[str, object]],
        **kwargs: object,
    ) -> list[dict[str, object]]:
        after_response = kwargs.get("after_response")
        assert callable(after_response)
        transcript: list[dict[str, object]] = []
        for request in requests:
            transcript.append({"direction": "send", "body": request})
            request_id = request.get("id")
            if request.get("method") == "hooks/list":
                observed["config_at_same_child_hooks_list"] = (
                    ctx.codex_home / "config.toml"
                ).read_text(encoding="utf-8")
                observed["ticket_hook_at_same_child_hooks_list"] = ticket_hook.read_text(
                    encoding="utf-8"
                )
            if request_id is None:
                continue
            response = {"id": request_id, "result": {}}
            if request_id == 2:
                ticket_hook.parent.mkdir(parents=True, exist_ok=True)
                ticket_hook.write_text(
                    json.dumps(
                        {
                            "hooks": {
                                "PreToolUse": [
                                    {
                                        "matcher": "Bash",
                                        "hooks": [
                                            {
                                                "type": "command",
                                                "command": (
                                                    "python3 /Users/jp/.codex/plugins/cache/"
                                                    "turbo-mode/ticket/1.4.0/hooks/"
                                                    "ticket_engine_guard.py"
                                                ),
                                            }
                                        ],
                                    }
                                ]
                            }
                        }
                    )
                    + "\n",
                    encoding="utf-8",
                )
            transcript.append({"direction": "recv", "body": response})
            after_response(request, response, transcript)
        return transcript

    def fake_validate_install_responses(**kwargs: object) -> AppServerInstallAuthority:
        assert kwargs["same_child_ticket_hook_policy"] == "disabled"
        same_child = kwargs["same_child_post_install_transcript"]
        assert isinstance(same_child, tuple)
        response_ids = [
            item["body"]["id"]
            for item in same_child
            if item.get("direction") == "recv" and isinstance(item.get("body"), dict)
        ]
        assert response_ids == [0, 1, 2, 3, 4, 5]
        return install_authority(ctx, launch)

    def fake_prove_app_server_home_authority(
        active_context: object,
        **kwargs: object,
    ) -> AppServerLaunchAuthority:
        observed["launch_ticket_hook_policy"] = kwargs["ticket_hook_policy"]
        return launch

    monkeypatch.setattr(
        mutation_module,
        "prove_app_server_home_authority",
        fake_prove_app_server_home_authority,
    )
    monkeypatch.setattr(mutation_module, "app_server_roundtrip", fake_roundtrip)
    monkeypatch.setattr(
        mutation_module,
        "collect_readonly_runtime_inventory",
        lambda paths: ("fresh-child-inventory", ()),
    )
    monkeypatch.setattr(
        mutation_module,
        "validate_install_responses",
        fake_validate_install_responses,
    )

    install_plugins_via_app_server(
        ctx,
        restore_config_before_post_install=restore_config,
        same_child_ticket_hook_policy="disabled",
    )

    assert observed["launch_ticket_hook_policy"] == "disabled"
    assert observed["config_at_same_child_hooks_list"] == "[features]\nplugin_hooks = true\n"
    assert str(ctx.codex_home) in str(observed["ticket_hook_at_same_child_hooks_list"])
    assert "/Users/jp/.codex/plugins/cache" not in str(
        observed["ticket_hook_at_same_child_hooks_list"]
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
        lambda paths, **kwargs: (leaked, ()),
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
        lambda paths, **kwargs: order.append("launch") or (launch, ()),
    )
    monkeypatch.setattr(
        mutation_module,
        "build_pre_install_target_authority",
        lambda **kwargs: order.append("pre") or pre,
    )

    def fake_roundtrip(**kwargs: object) -> tuple[dict[str, object], ...]:
        order.append("install")
        requests = kwargs["requests"]
        assert [request["method"] for request in requests] == [
            "initialize",
            "initialized",
            "plugin/install",
            "plugin/install",
            "plugin/read",
            "plugin/read",
            "plugin/list",
            "skills/list",
            "hooks/list",
        ]
        install_requests = [
            request for request in requests if request["method"] == "plugin/install"
        ]
        assert [request["params"]["pluginName"] for request in install_requests] == [
            "handoff",
            "ticket",
        ]
        assert all(
            request["params"]["remoteMarketplaceName"] is None
            for request in install_requests
        )
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
        lambda paths, **kwargs: (launch, ()),
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


def write_recovery_marker(
    ctx: MutationContext,
    snapshot,
    *,
    phase: str = "install-complete",
    source_commit: str = SOURCE_COMMIT,
    source_tree: str = SOURCE_TREE,
    execution_head: str = EXECUTION_HEAD,
    execution_tree: str = EXECUTION_TREE,
    tool_sha256: str = TOOL_SHA256,
    expected_intermediate_config_sha256: str | None = None,
) -> None:
    local_only_root = ctx.local_only_run_root.parent
    original_owner = {
        "run_id": ctx.run_id,
        "mode": "guarded-refresh",
        "source_implementation_commit": source_commit,
        "execution_head": execution_head,
        "tool_sha256": tool_sha256,
        "pid": 1234,
        "parent_pid": 99,
        "observed_process_start": "Thu May  7 10:00:00 2026",
        "raw_owner_process_row_sha256": "row-sha",
        "acquisition_timestamp": "2026-05-07T10:00:00Z",
        "command_line_sequence": ["python3", "refresh.py", "--guarded-refresh"],
        "schema_version": "turbo-mode-refresh-lock-owner-v1",
    }
    owner_path = local_only_root / "run-state" / f"{ctx.run_id}.owner.json"
    owner_path.parent.mkdir(parents=True, exist_ok=True)
    owner_path.write_text(json.dumps(original_owner, indent=2, sort_keys=True) + "\n")
    original_owner_sha256 = authority_digest(original_owner)
    write_initial_run_state(
        local_only_root,
        RunState(
            run_id=ctx.run_id,
            mode="guarded-refresh",
            source_implementation_commit=source_commit,
            source_implementation_tree=source_tree,
            execution_head=execution_head,
            execution_tree=execution_tree,
            tool_sha256=tool_sha256,
            original_run_owner_sha256=original_owner_sha256,
            phase=phase,
            pre_snapshot_app_server_launch_authority_sha256="launch-sha",
            original_config_sha256=snapshot.config_sha256,
            expected_intermediate_config_sha256=(
                expected_intermediate_config_sha256 or snapshot.config_sha256
            ),
            hook_disabled_config_sha256=expected_intermediate_config_sha256,
            pre_refresh_cache_manifest_sha256=snapshot.pre_refresh_cache_manifest_sha256,
            snapshot_path_map={
                "config": str(snapshot.config_snapshot_path),
                "cache": str(snapshot.cache_snapshot_root),
                "manifest": str(snapshot.snapshot_manifest_path),
            },
            snapshot_manifest_digest=mutation_module._sha256_file(
                snapshot.snapshot_manifest_path
            ),
            recovery_eligibility="restore-cache-and-config",
        ),
    )


def recovery_owner() -> LockOwner:
    return LockOwner(
        run_id=RUN_ID,
        mode="recover",
        source_implementation_commit=SOURCE_COMMIT,
        execution_head=EXECUTION_HEAD,
        tool_sha256=TOOL_SHA256,
        pid=4321,
        parent_pid=99,
        observed_process_start="Thu May  7 11:00:00 2026",
        raw_owner_process_row_sha256="recovery-row-sha",
        acquisition_timestamp="2026-05-07T11:00:00Z",
        command_line_sequence=("python3", "refresh.py", "--recover", RUN_ID),
    )


def test_recovery_rejects_source_identity_mismatch_before_lock_or_process_gate(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    snapshot = create_snapshot_set(ctx)
    write_recovery_marker(ctx, snapshot, source_commit="marker-source")
    monkeypatch.setattr(
        mutation_module,
        "acquire_refresh_lock",
        lambda **kwargs: pytest.fail("recovery lock should not be acquired"),
    )
    monkeypatch.setattr(
        mutation_module,
        "capture_process_gate",
        lambda **kwargs: pytest.fail("process gate should not run"),
    )

    with pytest.raises(RefreshError, match="source implementation commit mismatch"):
        run_guarded_refresh_recovery(ctx)


def test_recovery_restores_snapshots_runs_inventory_and_clears_marker(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    snapshot = create_snapshot_set(ctx)
    disabled_sha256 = hashlib.sha256(DISABLED_CONFIG_TEXT.encode()).hexdigest()
    write_recovery_marker(
        ctx,
        snapshot,
        expected_intermediate_config_sha256=disabled_sha256,
    )
    (ctx.codex_home / "config.toml").write_text(DISABLED_CONFIG_TEXT, encoding="utf-8")
    (ctx.codex_home / "plugins/cache/turbo-mode/handoff/1.6.0/payload.txt").write_text(
        "changed",
        encoding="utf-8",
    )
    labels: list[str] = []

    def fake_process_gate(**kwargs: object) -> dict[str, object]:
        label = str(kwargs["label"])
        labels.append(label)
        return {"label": label, "blocked_process_count": 0}

    monkeypatch.setattr(mutation_module, "capture_process_gate", fake_process_gate)
    monkeypatch.setattr(
        lock_state_module,
        "_collect_owner_process_row",
        lambda pid: recovery_owner(),
    )
    monkeypatch.setattr(
        mutation_module,
        "collect_readonly_runtime_inventory",
        lambda paths: ("inventory", ({"body": "transcript"},)),
    )

    result = run_guarded_refresh_recovery(ctx)

    assert result.final_status == "RECOVERY_COMPLETE"
    assert labels == ["before-recovery-restore", "post-recovery"]
    assert "plugin_hooks = true" in (ctx.codex_home / "config.toml").read_text(encoding="utf-8")
    assert (ctx.codex_home / "plugins/cache/turbo-mode/handoff/1.6.0/payload.txt").read_text(
        encoding="utf-8"
    ) == "same"
    assert Path(result.final_status_path).is_file()
    assert not (
        ctx.local_only_run_root.parent / "run-state" / f"{ctx.run_id}.marker.json"
    ).exists()
    assert (ctx.local_only_run_root / "recovery/original-owner.json").is_file()
    assert (
        ctx.local_only_run_root.parent / "run-state" / f"{ctx.run_id}.recovery-owner.json"
    ).is_file()


def test_recovery_before_hook_disable_accepts_original_config_without_cache_restore(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    snapshot = create_snapshot_set(ctx)
    write_recovery_marker(ctx, snapshot, phase="snapshot-written")
    cache_payload = ctx.codex_home / "plugins/cache/turbo-mode/handoff/1.6.0/payload.txt"
    cache_payload.write_text("not-restored-before-install\n", encoding="utf-8")
    monkeypatch.setattr(
        lock_state_module,
        "_collect_owner_process_row",
        lambda pid: recovery_owner(),
    )
    monkeypatch.setattr(
        mutation_module,
        "capture_process_gate",
        lambda **kwargs: {"label": kwargs["label"], "blocked_process_count": 0},
    )
    monkeypatch.setattr(
        mutation_module,
        "collect_readonly_runtime_inventory",
        lambda paths: ("inventory", ({"body": "transcript"},)),
    )

    result = run_guarded_refresh_recovery(ctx)

    assert result.final_status == "RECOVERY_COMPLETE"
    assert "plugin_hooks = true" in (ctx.codex_home / "config.toml").read_text(encoding="utf-8")
    assert cache_payload.read_text(encoding="utf-8") == "not-restored-before-install\n"


def test_recovery_fails_closed_when_config_sha_is_externally_changed(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    ctx = context(tmp_path)
    seed_config(ctx)
    seed_plugins(ctx)
    snapshot = create_snapshot_set(ctx)
    write_recovery_marker(ctx, snapshot, expected_intermediate_config_sha256="disabled-sha")
    (ctx.codex_home / "config.toml").write_text("external-change\n", encoding="utf-8")
    monkeypatch.setattr(
        lock_state_module,
        "_collect_owner_process_row",
        lambda pid: recovery_owner(),
    )
    monkeypatch.setattr(
        mutation_module,
        "capture_process_gate",
        lambda **kwargs: {"label": kwargs["label"], "blocked_process_count": 0},
    )
    monkeypatch.setattr(
        mutation_module,
        "collect_readonly_runtime_inventory",
        lambda paths: pytest.fail("inventory should not run"),
    )

    with pytest.raises(RefreshError, match="phase-appropriate expected config SHA256"):
        run_guarded_refresh_recovery(ctx)

    assert (ctx.codex_home / "config.toml").read_text(encoding="utf-8") == "external-change\n"
    assert (
        ctx.local_only_run_root.parent / "run-state" / f"{ctx.run_id}.marker.json"
    ).exists()

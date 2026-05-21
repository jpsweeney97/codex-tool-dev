from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

import scripts.ticket_runtime_readiness as ticket_runtime_readiness

MODULE_SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "ticket_runtime_readiness.py"


def test_missing_runtime_proof_rejects(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / ".git").mkdir(parents=True)

    result = ticket_runtime_readiness.verify_installed_ticket_runtime_readiness_for_execute(
        project_root=project_root
    )

    assert result.passed is False
    assert result.error_code == "proof_missing"


def test_source_checkout_execution_cannot_satisfy_installed_runtime_proof(tmp_path: Path) -> None:
    project_root, _installed_root, _module, _proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )

    result = ticket_runtime_readiness.verify_installed_ticket_runtime_readiness_for_execute(
        project_root=project_root
    )

    assert result.passed is False
    assert result.error_code == "executing_root_mismatch"


def test_valid_installed_runtime_proof_passes_when_executing_root_matches(tmp_path: Path) -> None:
    project_root, _installed_root, module, _proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is True
    assert result.error_code is None


def test_deleted_raw_evidence_rejects(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    hook_events = run_dir / proof["raw_evidence"]["hook_membrane_events"]
    hook_events.unlink()

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "raw_evidence_missing"


def test_stale_proof_rejects(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["expires_at"] = "2026-05-19T00:00:00Z"
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "stale_proof"


def test_hash_mismatches_reject(tmp_path: Path) -> None:
    project_root, installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))

    (installed_root / ".codex-plugin" / "plugin.json").write_text(
        '{"name":"ticket","version":"1.4.0","drift":true}\n',
        encoding="utf-8",
    )
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "plugin_manifest_hash_mismatch"


def test_invalid_scope_rejects(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["activation_scope"]["gated_execute_surfaces"] = ["direct_execute", "capture_execute"]
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "invalid_scope"


def test_forbidden_surface_fields_reject(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["post_activation_gated_smokes"]["surface_results"]["capture_execute"] = {
        "raw_events_sha256": "bad",
    }
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "invalid_scope"


def test_nonce_and_payload_hash_mismatches_reject(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["hook_membrane_proof"]["nonce"] = "different-nonce"
    proof["hook_membrane_proof"]["payload_sha256"] = "different-payload"
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code in {"nonce_mismatch", "payload_hash_mismatch"}


def test_build_activation_candidate_returns_candidate_without_writing_final_proof(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    tickets_dir = project_root / "docs" / "tickets"
    marketplace_path = project_root / ".agents" / "plugins" / "marketplace.json"
    (project_root / ".git").mkdir(parents=True)
    tickets_dir.mkdir(parents=True)
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        ticket_runtime_readiness,
        "collect_installed_runtime_inventory",
        lambda **kwargs: _fake_inventory_result(tmp_path, run_dir=kwargs["run_dir"]),
    )
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "run_activation_smoke",
        lambda **_kwargs: _fake_smoke_result(tmp_path, project_root=project_root),
    )

    result = ticket_runtime_readiness.build_activation_candidate(
        project_root=project_root,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert result.error_code is None
    assert result.proof is not None
    assert result.proof["status"] == "activation_in_progress"
    assert result.proof["activation_scope"]["gated_execute_surfaces"] == ["direct_execute"]
    assert not (project_root / ".codex" / "ticket-runtime-proof.json").exists()


def test_build_activation_candidate_propagates_hook_contract_blocker(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    tickets_dir = project_root / "docs" / "tickets"
    marketplace_path = project_root / ".agents" / "plugins" / "marketplace.json"
    (project_root / ".git").mkdir(parents=True)
    tickets_dir.mkdir(parents=True)
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        ticket_runtime_readiness,
        "collect_installed_runtime_inventory",
        lambda **kwargs: _fake_inventory_result(tmp_path, run_dir=kwargs["run_dir"]),
    )

    def _blocked_smoke(**_kwargs):
        raise ticket_runtime_readiness.RuntimeActivationError(
            "hook_contract_blocked",
            "Installed Ticket hook still emits unsupported output",
        )

    monkeypatch.setattr(ticket_runtime_readiness, "run_activation_smoke", _blocked_smoke)

    result = ticket_runtime_readiness.build_activation_candidate(
        project_root=project_root,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert result.proof is None
    assert result.error_code == "hook_contract_blocked"


def test_activate_runtime_writes_final_proof_after_direct_execute_smoke(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    tickets_dir = project_root / "docs" / "tickets"
    marketplace_path = project_root / ".agents" / "plugins" / "marketplace.json"
    (project_root / ".git").mkdir(parents=True)
    tickets_dir.mkdir(parents=True)
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        ticket_runtime_readiness,
        "collect_installed_runtime_inventory",
        lambda **kwargs: _fake_inventory_result(tmp_path, run_dir=kwargs["run_dir"]),
    )
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "run_activation_smoke",
        lambda **_kwargs: _fake_smoke_result(tmp_path, project_root=project_root),
    )
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "run_post_activation_direct_execute_smoke",
        lambda **kwargs: _fake_post_activation_smoke_result(run_dir=kwargs["run_dir"]),
    )
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "verify_installed_ticket_runtime_readiness_for_execute",
        lambda **_kwargs: ticket_runtime_readiness.RuntimeReadinessVerification(
            passed=True,
            error_code=None,
            message="verified",
        ),
    )

    result = ticket_runtime_readiness.activate_runtime(
        project_root=project_root,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    proof_path = project_root / ".codex" / "ticket-runtime-proof.json"
    assert result.error_code is None
    assert result.proof is not None
    assert result.proof["status"] == "activated"
    assert result.proof["post_activation_gated_smokes"]["status"] == "passed"
    assert proof_path.exists()
    written = json.loads(proof_path.read_text(encoding="utf-8"))
    assert written["status"] == "activated"


def test_activate_runtime_propagates_post_activation_smoke_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    tickets_dir = project_root / "docs" / "tickets"
    marketplace_path = project_root / ".agents" / "plugins" / "marketplace.json"
    (project_root / ".git").mkdir(parents=True)
    tickets_dir.mkdir(parents=True)
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text("{}", encoding="utf-8")

    monkeypatch.setattr(
        ticket_runtime_readiness,
        "collect_installed_runtime_inventory",
        lambda **kwargs: _fake_inventory_result(tmp_path, run_dir=kwargs["run_dir"]),
    )
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "run_activation_smoke",
        lambda **_kwargs: _fake_smoke_result(tmp_path, project_root=project_root),
    )

    def _blocked_post_smoke(**_kwargs):
        raise ticket_runtime_readiness.RuntimeActivationError(
            "runtime_readiness_required",
            "Direct execute smoke did not reach an activated runtime-ready create result",
        )

    monkeypatch.setattr(
        ticket_runtime_readiness,
        "run_post_activation_direct_execute_smoke",
        _blocked_post_smoke,
    )

    result = ticket_runtime_readiness.activate_runtime(
        project_root=project_root,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert result.proof is None
    assert result.error_code == "runtime_readiness_required"
    assert not (project_root / ".codex" / "ticket-runtime-proof.json").exists()


def test_run_activation_smoke_uses_uv_run_python_launcher(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    tickets_dir = project_root / "docs" / "tickets"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    installed_root = tmp_path / "installed"
    tickets_dir.mkdir(parents=True)
    expected_command = (
        f"uv run python -B {installed_root}/scripts/ticket_engine_activation_smoke.py "
        f"execute {run_dir / 'payload.json'}"
    )

    def _fake_turn(**kwargs):
        assert f"Command: {expected_command}" in kwargs["prompt_text"]
        return [
            {
                "direction": "recv",
                "body": {"method": "hook/completed", "params": {"run": {"entries": []}}},
            },
            {
                "direction": "recv",
                "body": {
                    "params": {
                        "item": {
                            "type": "commandExecution",
                            "id": "cmd-1",
                            "command": expected_command,
                        }
                    }
                },
            },
        ]

    monkeypatch.setattr(ticket_runtime_readiness, "_run_app_server_turn", _fake_turn)

    result = ticket_runtime_readiness.run_activation_smoke(
        project_root=project_root,
        tickets_dir=tickets_dir,
        run_dir=run_dir,
        installed_ticket_root=installed_root,
    )

    assert result["hook_membrane_proof"]["command"] == expected_command


def test_run_post_activation_direct_execute_smoke_uses_uv_run_python_launcher(
    tmp_path: Path,
    monkeypatch,
) -> None:
    project_root = tmp_path / "project"
    tickets_dir = project_root / "docs" / "tickets"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    installed_root = tmp_path / "installed"
    proof_path = run_dir / "activated-ticket-runtime-proof.json"
    tickets_dir.mkdir(parents=True)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text("{}", encoding="utf-8")
    ticket_path = run_dir / "post-direct" / "docs" / "tickets" / "2026-05-20-example.md"
    ticket_path.parent.mkdir(parents=True, exist_ok=True)
    ticket_path.write_text("# T-20260520-01: Runtime activation smoke\n", encoding="utf-8")
    expected_command = (
        f"uv run python -B {installed_root}/scripts/ticket_engine_agent.py "
        f"execute {run_dir / 'post-direct' / 'post-direct-payload.json'}"
    )

    def _fake_turn(**kwargs):
        assert f"Command: {expected_command}" in kwargs["prompt_text"]
        return [
            {
                "direction": "recv",
                "body": {
                    "params": {
                        "item": {
                            "type": "commandExecution",
                            "id": "cmd-1",
                            "command": expected_command,
                        }
                    }
                },
            },
            {
                "direction": "recv",
                "body": {
                    "method": "item/commandExecution/outputDelta",
                    "params": {
                        "delta": json.dumps(
                            {
                                "state": "ok_create",
                                "data": {"ticket_path": str(ticket_path)},
                            }
                        )
                    },
                },
            },
        ]

    monkeypatch.setattr(ticket_runtime_readiness, "_run_app_server_turn", _fake_turn)

    result = ticket_runtime_readiness.run_post_activation_direct_execute_smoke(
        project_root=project_root,
        tickets_dir=tickets_dir,
        run_dir=run_dir,
        installed_ticket_root=installed_root,
        proof_path=proof_path,
    )

    actual_command = result["post_activation_gated_smokes"]["surface_results"]["direct_execute"][
        "command"
    ]
    assert actual_command == expected_command


def _fake_inventory_result(tmp_path: Path, *, run_dir: Path) -> dict[str, object]:
    installed_root = tmp_path / "installed-ticket"
    hooks_dir = installed_root / "hooks"
    plugin_manifest = installed_root / ".codex-plugin" / "plugin.json"
    guard_script = hooks_dir / "ticket_engine_guard.py"
    hook_manifest = hooks_dir / "hooks.json"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    plugin_manifest.parent.mkdir(parents=True, exist_ok=True)
    plugin_manifest.write_text('{"name":"ticket","version":"1.4.0"}\n', encoding="utf-8")
    guard_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    hook_manifest.write_text('{"hooks":{"PreToolUse":[]}}\n', encoding="utf-8")
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    transcript = raw_dir / "app-server-inventory-transcript.jsonl"
    transcript.write_text('{"direction":"recv"}\n', encoding="utf-8")
    return {
        "runtime_identity": {
            "codex_version": "codex-cli 0.132.0",
            "executable_path": "/usr/local/bin/codex",
            "executable_sha256": None,
            "executable_hash_unavailable_reason": "not-needed",
            "accepted_response_schema_version": "ticket-app-server-readiness-v1",
            "parser_version": "installed-ticket-runtime-readiness-v1",
        },
        "inventory": {
            "request_methods": [
                "initialize",
                "initialized",
                "plugin/read",
                "plugin/list",
                "skills/list",
                "hooks/list",
            ],
            "marketplace_path": str(tmp_path / "project/.agents/plugins/marketplace.json"),
            "cwd": str(tmp_path / "project"),
            "transcript_sha256": ticket_runtime_readiness.sha256_file(transcript),
            "plugin_read_source_path": str(tmp_path / "project/plugins/turbo-mode/ticket"),
            "installed_runtime_root": str(installed_root),
            "hook": {
                "plugin_id": "ticket@turbo-mode",
                "event_name": "preToolUse",
                "matcher": "Bash",
                "hook_manifest_path": str(hook_manifest),
                "hook_manifest_sha256": ticket_runtime_readiness.sha256_file(hook_manifest),
                "guard_command": f"python3 {guard_script}",
                "guard_script_path": str(guard_script),
                "guard_script_sha256": ticket_runtime_readiness.sha256_file(guard_script),
            },
            "plugin_manifest_path": str(plugin_manifest),
            "plugin_manifest_sha256": ticket_runtime_readiness.sha256_file(plugin_manifest),
        },
        "raw_inventory_transcript": transcript,
        "ticket_plugin": {
            "plugin_id": "ticket@turbo-mode",
            "name": "ticket",
            "version": "1.4.0",
        },
    }


def _fake_smoke_result(tmp_path: Path, *, project_root: Path) -> dict[str, object]:
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload_before = raw_dir / "payload-before.json"
    payload_after = raw_dir / "payload-after.json"
    hook_events = raw_dir / "hook-membrane-events.jsonl"
    engine_stdout = raw_dir / "engine-stdout.json"
    engine_stderr = raw_dir / "engine-stderr.txt"
    post_events = raw_dir / "post-activation-gated-events.jsonl"
    payload_before.write_text('{"tickets_dir":"docs/tickets"}\n', encoding="utf-8")
    payload_after.write_text(
        '{"tickets_dir":"docs/tickets","hook_injected":true}\n', encoding="utf-8"
    )
    hook_events.write_text('{"method":"hook/completed"}\n', encoding="utf-8")
    engine_stdout.write_text('{"state":"ok_create"}\n', encoding="utf-8")
    engine_stderr.write_text("", encoding="utf-8")
    post_events.write_text('{"method":"turn/completed"}\n', encoding="utf-8")
    activation_command = (
        "uv run python -B installed/scripts/ticket_engine_activation_smoke.py "
        "execute payload.json"
    )
    return {
        "run_nonce": "run-1",
        "hook_membrane_proof": {
            "runner": "app_server_turn",
            "status": "passed",
            "command": activation_command,
            "payload_path": str(run_dir / "payload.json"),
            "nonce": "run-1",
            "payload_sha256": ticket_runtime_readiness.sha256_file(payload_before),
            "raw_events_sha256": ticket_runtime_readiness.sha256_file(hook_events),
            "engine_stdout_sha256": ticket_runtime_readiness.sha256_file(engine_stdout),
        },
        "post_activation_gated_smokes": {
            "status": "pending",
            "required_surfaces": ["direct_execute"],
            "surface_results": {
                "direct_execute": {
                    "raw_events_sha256": ticket_runtime_readiness.sha256_file(post_events),
                }
            },
        },
        "raw_evidence": {
            "run_dir": str(run_dir.relative_to(project_root)),
            "hook_membrane_events": str(hook_events.relative_to(run_dir)),
            "post_activation_events": str(post_events.relative_to(run_dir)),
            "payload_before": str(payload_before.relative_to(run_dir)),
            "payload_after": str(payload_after.relative_to(run_dir)),
            "engine_stdout": str(engine_stdout.relative_to(run_dir)),
            "engine_stderr": str(engine_stderr.relative_to(run_dir)),
        },
    }


def _fake_post_activation_smoke_result(*, run_dir: Path) -> dict[str, object]:
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    post_events = raw_dir / "post-activation-gated-events.jsonl"
    post_events.write_text('{"method":"turn/completed"}\n', encoding="utf-8")
    ticket_path = run_dir / "post-direct" / "docs" / "tickets" / "2026-05-20-example.md"
    ticket_path.parent.mkdir(parents=True, exist_ok=True)
    ticket_path.write_text("# T-20260520-01: Runtime activation smoke\n", encoding="utf-8")
    return {
        "post_activation_gated_smokes": {
            "status": "passed",
            "required_surfaces": ["direct_execute"],
            "surface_results": {
                "direct_execute": {
                    "runner": "app_server_turn",
                    "command": (
                        "uv run python -B installed/scripts/ticket_engine_agent.py "
                        "execute payload.json"
                    ),
                    "execute_surface": "direct_execute",
                    "runtime_readiness_required": True,
                    "engine_state": "ok_create",
                    "raw_events_sha256": ticket_runtime_readiness.sha256_file(post_events),
                    "ticket_path": str(ticket_path),
                    "ticket_sha256": ticket_runtime_readiness.sha256_file(ticket_path),
                }
            },
        }
    }


def build_valid_runtime_readiness_fixture(
    tmp_path: Path,
) -> tuple[Path, Path, object, Path]:
    project_root = tmp_path / "project"
    (project_root / ".git").mkdir(parents=True)
    proof_path = project_root / ".codex" / "ticket-runtime-proof.json"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)

    inventory_path = raw_dir / "app-server-inventory-transcript.jsonl"
    hook_events_path = raw_dir / "hook-membrane-events.jsonl"
    post_events_path = raw_dir / "post-activation-gated-events.jsonl"
    payload_before_path = raw_dir / "payload-before.json"
    payload_after_path = raw_dir / "payload-after.json"
    engine_stdout_path = raw_dir / "engine-stdout.json"
    engine_stderr_path = raw_dir / "engine-stderr.txt"

    inventory_path.write_text('{"direction":"recv"}\n', encoding="utf-8")
    hook_events_path.write_text('{"method":"hook/completed"}\n', encoding="utf-8")
    post_events_path.write_text('{"method":"turn/completed"}\n', encoding="utf-8")
    payload_before_path.write_text('{"tickets_dir":"docs/tickets"}\n', encoding="utf-8")
    payload_after_path.write_text(
        '{"tickets_dir":"docs/tickets","hook_injected":true}\n', encoding="utf-8"
    )
    engine_stdout_path.write_text('{"state":"ok_create"}\n', encoding="utf-8")
    engine_stderr_path.write_text("", encoding="utf-8")

    installed_root = tmp_path / "installed-ticket"
    scripts_dir = installed_root / "scripts"
    hooks_dir = installed_root / "hooks"
    plugin_manifest = installed_root / ".codex-plugin" / "plugin.json"
    hook_manifest = hooks_dir / "hooks.json"
    guard_script = hooks_dir / "ticket_engine_guard.py"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    hooks_dir.mkdir(parents=True, exist_ok=True)
    plugin_manifest.parent.mkdir(parents=True, exist_ok=True)

    plugin_manifest.write_text('{"name":"ticket","version":"1.4.0"}\n', encoding="utf-8")
    hook_manifest.write_text('{"hooks":{"PreToolUse":[]}}\n', encoding="utf-8")
    guard_script.write_text("#!/usr/bin/env python3\nprint('guard')\n", encoding="utf-8")

    copied_module_path = scripts_dir / "ticket_runtime_readiness.py"
    shutil.copy2(MODULE_SOURCE, copied_module_path)
    module = load_module(copied_module_path)
    activation_command = (
        "uv run python -B installed/scripts/ticket_engine_activation_smoke.py "
        "execute payload.json"
    )

    proof = {
        "schema_version": "installed_ticket_runtime_readiness-v1",
        "status": "activated",
        "created_at": "2026-05-20T00:00:00Z",
        "expires_at": "2026-05-21T23:59:59Z",
        "run_nonce": "run-1",
        "ticket_plugin": {
            "plugin_id": "ticket@turbo-mode",
            "name": "ticket",
            "version": "1.4.0",
            "installed_cache_root": str(installed_root),
            "plugin_manifest_path": str(plugin_manifest),
            "plugin_manifest_sha256": module.sha256_file(plugin_manifest),
        },
        "runtime_identity": {
            "codex_version": "codex-cli 0.132.0",
            "executable_path": "/usr/local/bin/codex",
            "executable_sha256": None,
            "executable_hash_unavailable_reason": "not needed in tests",
            "accepted_response_schema_version": "ticket-app-server-readiness-v1",
            "parser_version": "installed-ticket-runtime-readiness-v1",
        },
        "inventory": {
            "request_methods": [
                "initialize",
                "initialized",
                "plugin/read",
                "plugin/list",
                "skills/list",
                "hooks/list",
            ],
            "marketplace_path": str(project_root / ".agents" / "plugins" / "marketplace.json"),
            "cwd": str(project_root),
            "transcript_sha256": module.sha256_file(inventory_path),
            "plugin_read_source_path": str(project_root / "plugins" / "turbo-mode" / "ticket"),
            "installed_runtime_root": str(installed_root),
            "hook": {
                "plugin_id": "ticket@turbo-mode",
                "event_name": "preToolUse",
                "matcher": "Bash",
                "hook_manifest_path": str(hook_manifest),
                "hook_manifest_sha256": module.sha256_file(hook_manifest),
                "guard_command": f"python3 {guard_script}",
                "guard_script_path": str(guard_script),
                "guard_script_sha256": module.sha256_file(guard_script),
            },
        },
        "hook_membrane_proof": {
            "runner": "app_server_turn",
            "status": "passed",
            "command": activation_command,
            "payload_path": str(
                project_root / ".codex" / "ticket-runtime-smoke" / "run-1" / "payload.json"
            ),
            "nonce": "run-1",
            "payload_sha256": module.sha256_file(payload_before_path),
            "raw_events_sha256": module.sha256_file(hook_events_path),
            "engine_stdout_sha256": module.sha256_file(engine_stdout_path),
        },
        "post_activation_gated_smokes": {
            "status": "passed",
            "required_surfaces": ["direct_execute"],
            "surface_results": {
                "direct_execute": {
                    "raw_events_sha256": module.sha256_file(post_events_path),
                }
            },
        },
        "activation_scope": {
            "gated_execute_surfaces": ["direct_execute"],
            "certified_entrypoints": ["ticket_engine_agent.py"],
            "certified_policy_lane": "ticket_engine_agent.py execute + autonomy_mode=auto_audit",
            "excluded_mutation_paths": [
                "ingest_dispatch",
                "activation_smoke_bootstrap",
                "ticket_capture.py",
                "ticket_update.py",
                "ticket_workflow.py",
            ],
            "autonomy_mode": "auto_audit",
            "caller_identity_proven": False,
            "hook_request_origin_contract": "provenance_metadata_only_currently_user",
        },
        "raw_evidence": {
            "run_dir": str(run_dir.relative_to(project_root)),
            "app_server_inventory_transcript": str(inventory_path.relative_to(run_dir)),
            "hook_membrane_events": str(hook_events_path.relative_to(run_dir)),
            "post_activation_events": str(post_events_path.relative_to(run_dir)),
            "payload_before": str(payload_before_path.relative_to(run_dir)),
            "payload_after": str(payload_after_path.relative_to(run_dir)),
            "engine_stdout": str(engine_stdout_path.relative_to(run_dir)),
            "engine_stderr": str(engine_stderr_path.relative_to(run_dir)),
        },
    }
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return project_root, installed_root, module, proof_path


def load_module(module_path: Path) -> object:
    spec = importlib.util.spec_from_file_location("installed_ticket_runtime_readiness", module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module

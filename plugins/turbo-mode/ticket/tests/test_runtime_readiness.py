from __future__ import annotations

import importlib.util
import json
import shutil
import sys
from pathlib import Path

from scripts.ticket_runtime_readiness import verify_installed_ticket_runtime_readiness_for_execute


MODULE_SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "ticket_runtime_readiness.py"


def test_missing_runtime_proof_rejects(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / ".git").mkdir(parents=True)

    result = verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "proof_missing"


def test_source_checkout_execution_cannot_satisfy_installed_runtime_proof(tmp_path: Path) -> None:
    project_root, _installed_root, _module, _proof_path = build_valid_runtime_readiness_fixture(tmp_path)

    result = verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "executing_root_mismatch"


def test_valid_installed_runtime_proof_passes_when_executing_root_matches(tmp_path: Path) -> None:
    project_root, _installed_root, module, _proof_path = build_valid_runtime_readiness_fixture(tmp_path)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is True
    assert result.error_code is None


def test_deleted_raw_evidence_rejects(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(tmp_path)
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    hook_events = run_dir / proof["raw_evidence"]["hook_membrane_events"]
    hook_events.unlink()

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "raw_evidence_missing"


def test_stale_proof_rejects(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(tmp_path)
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["expires_at"] = "2026-05-19T00:00:00Z"
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "stale_proof"


def test_hash_mismatches_reject(tmp_path: Path) -> None:
    project_root, installed_root, module, proof_path = build_valid_runtime_readiness_fixture(tmp_path)
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
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(tmp_path)
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["activation_scope"]["gated_execute_surfaces"] = ["direct_execute", "capture_execute"]
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "invalid_scope"


def test_forbidden_surface_fields_reject(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(tmp_path)
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["post_activation_gated_smokes"]["surface_results"]["capture_execute"] = {
        "raw_events_sha256": "bad",
    }
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "invalid_scope"


def test_nonce_and_payload_hash_mismatches_reject(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(tmp_path)
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["hook_membrane_proof"]["nonce"] = "different-nonce"
    proof["hook_membrane_proof"]["payload_sha256"] = "different-payload"
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code in {"nonce_mismatch", "payload_hash_mismatch"}


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
    payload_after_path.write_text('{"tickets_dir":"docs/tickets","hook_injected":true}\n', encoding="utf-8")
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
            "command": "python3 -B installed/scripts/ticket_engine_activation_smoke.py execute payload.json",
            "payload_path": str(project_root / ".codex" / "ticket-runtime-smoke" / "run-1" / "payload.json"),
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

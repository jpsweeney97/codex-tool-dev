from __future__ import annotations

import importlib.util
import json
import os
import queue
import shutil
import subprocess
import sys
from pathlib import Path
from typing import is_typeddict

import pytest
import scripts.ticket_runtime_readiness as ticket_runtime_readiness

MODULE_SOURCE = Path(__file__).resolve().parents[1] / "scripts" / "ticket_runtime_readiness.py"


def _write_proof(proof_path: Path, proof: dict[str, object]) -> None:
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, object]]) -> None:
    path.write_text(
        "".join(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n" for row in rows),
        encoding="utf-8",
    )


def _set_nested(mapping: dict[str, object], path: tuple[str, ...], value: object) -> None:
    target = mapping
    for key in path[:-1]:
        child = target[key]
        assert isinstance(child, dict)
        target = child
    target[path[-1]] = value


def _run_dir_from_result(
    project_root: Path,
    result: ticket_runtime_readiness.ActivationFailure,
) -> Path:
    marker = "Run evidence remains under "
    assert marker in result.message
    evidence_root = result.message.split(marker, 1)[1].strip().rstrip(".")
    run_dir = project_root / evidence_root
    assert run_dir.is_relative_to(project_root)
    return run_dir


def _assert_late_failure_evidence_preserved(project_root: Path, run_dir: Path) -> None:
    assert run_dir.is_relative_to(project_root)
    raw_dir = run_dir / "raw"
    assert (raw_dir / "hook-membrane-events.jsonl").exists()
    assert (raw_dir / "engine-stdout.json").exists()
    assert (raw_dir / "payload-before.json").exists()
    assert (
        run_dir / "post-direct" / "docs" / "tickets" / "2026-05-20-example.md"
    ).exists()


def _hook_manifest_payload(guard_command: str) -> dict[str, object]:
    return {
        "hooks": {
            "PreToolUse": [
                {
                    "matcher": "Bash",
                    "hooks": [
                        {
                            "type": "command",
                            "command": guard_command,
                            "timeout": 10,
                        }
                    ],
                }
            ]
        }
    }


def _hook_completed_row(source_path: Path) -> dict[str, object]:
    return {
        "direction": "recv",
        "body": {
            "method": "hook/completed",
            "params": {
                "run": {
                    "eventName": "preToolUse",
                    "sourcePath": str(source_path),
                    "entries": [{"kind": "feedback", "text": "Ticket command validated"}],
                }
            },
        },
    }


def _command_item_row(command: str, output: dict[str, object]) -> dict[str, object]:
    return {
        "direction": "recv",
        "body": {
            "params": {
                "item": {
                    "type": "commandExecution",
                    "id": "cmd-1",
                    "command": command,
                    "aggregatedOutput": json.dumps(output),
                }
            }
        },
    }


def _fake_pre_activation_gate_result() -> dict[str, object]:
    return {
        "pre_activation_gated_smokes": {
            "status": "passed",
            "required_surfaces": ["direct_execute"],
            "surface_results": {
                "direct_execute": {
                    "runner": "app_server_turn",
                    "command": "uv run python -B installed/scripts/ticket_engine_agent.py",
                    "execute_surface": "direct_execute",
                    "engine_state": "policy_blocked",
                    "error_code": "runtime_readiness_required",
                    "raw_events_sha256": "0" * 64,
                }
            },
        },
        "raw_evidence": {"pre_activation_events": "raw/pre-activation-gated-events.jsonl"},
    }


def _inventory_transcript_rows(
    *,
    project_root: Path,
    hook_manifest: Path,
    guard_command: str,
) -> list[dict[str, object]]:
    return [
        {"direction": "recv", "body": {"id": 0, "result": {"ok": True}}},
        {
            "direction": "recv",
            "body": {
                "id": 1,
                "result": {
                    "source": {"path": str(project_root / "plugins" / "turbo-mode" / "ticket")},
                    "plugin": {"summary": {"version": "1.4.0"}},
                },
            },
        },
        {"direction": "recv", "body": {"id": 2, "result": {"plugins": []}}},
        {"direction": "recv", "body": {"id": 3, "result": {"skills": []}}},
        {
            "direction": "recv",
            "body": {
                "id": 4,
                "result": {
                    "hooks": [
                        {
                            "pluginId": "ticket@turbo-mode",
                            "eventName": "preToolUse",
                            "matcher": "Bash",
                            "command": guard_command,
                            "sourcePath": str(hook_manifest),
                        }
                    ]
                },
            },
        },
    ]


def test_missing_runtime_proof_rejects(tmp_path: Path) -> None:
    project_root = tmp_path / "project"
    (project_root / ".git").mkdir(parents=True)

    result = ticket_runtime_readiness.verify_installed_ticket_runtime_readiness_for_execute(
        project_root=project_root
    )

    assert result.passed is False
    assert result.error_code == "proof_missing"


@pytest.mark.parametrize(
    ("factory", "kwargs"),
    [
        (ticket_runtime_readiness.ReadinessSuccess, {"message": "bad", "passed": False}),
        (
            ticket_runtime_readiness.ReadinessSuccess,
            {"message": "bad", "error_code": "stale_proof"},
        ),
        (ticket_runtime_readiness.ReadinessSuccess, {"message": ""}),
        (
            ticket_runtime_readiness.ReadinessFailure,
            {"error_code": "proof_invalid", "message": "bad", "passed": True},
        ),
        (ticket_runtime_readiness.ReadinessFailure, {"error_code": "", "message": "bad"}),
        (ticket_runtime_readiness.ReadinessFailure, {"error_code": "proof_invalid", "message": ""}),
    ],
)
def test_runtime_readiness_verification_enforces_state_invariants(
    factory,
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="Readiness.* validation failed"):
        factory(**kwargs)


@pytest.mark.parametrize(
    ("factory", "kwargs"),
    [
        (ticket_runtime_readiness.ActivationSuccess, {"proof": None, "message": "bad"}),
        (
            ticket_runtime_readiness.ActivationSuccess,
            {"proof": {}, "error_code": "deterministic_driver_unavailable", "message": "bad"},
        ),
        (ticket_runtime_readiness.ActivationSuccess, {"proof": {}, "message": ""}),
        (
            ticket_runtime_readiness.ActivationFailure,
            {"error_code": "", "message": "bad"},
        ),
        (
            ticket_runtime_readiness.ActivationFailure,
            {"error_code": "deterministic_driver_unavailable", "message": ""},
        ),
        (
            ticket_runtime_readiness.ActivationFailure,
            {"error_code": "deterministic_driver_unavailable", "message": "bad", "proof": {}},
        ),
    ],
)
def test_runtime_activation_build_result_enforces_state_invariants(
    factory,
    kwargs: dict[str, object],
) -> None:
    with pytest.raises(ValueError, match="Activation.* validation failed"):
        factory(**kwargs)


def test_runtime_activation_build_result_uses_passed_discriminator() -> None:
    success = ticket_runtime_readiness.ActivationSuccess(
        proof={"status": "activated"},
        message="ok",
    )
    failure = ticket_runtime_readiness.ActivationFailure(
        error_code="deterministic_driver_unavailable",
        message="blocked",
    )

    assert success.passed is True
    assert success.error_code is None
    assert failure.passed is False
    assert failure.proof is None

    with pytest.raises(ValueError, match="ActivationSuccess validation failed"):
        ticket_runtime_readiness.ActivationSuccess(
            proof={"status": "activated"},
            message="bad",
            passed=False,
        )
    with pytest.raises(ValueError, match="ActivationFailure validation failed"):
        ticket_runtime_readiness.ActivationFailure(
            error_code="deterministic_driver_unavailable",
            message="bad",
            passed=True,
        )


def test_activation_success_proof_is_copied_and_immutable() -> None:
    proof = {
        "status": "activated",
        "activation_scope": {"gated_execute_surfaces": ["direct_execute"]},
    }

    result = ticket_runtime_readiness.ActivationSuccess(proof=proof, message="ok")
    proof["status"] = "mutated"
    activation_scope = proof["activation_scope"]
    assert isinstance(activation_scope, dict)
    gated_surfaces = activation_scope["gated_execute_surfaces"]
    assert isinstance(gated_surfaces, list)
    gated_surfaces.append("ingest")

    assert result.proof["status"] == "activated"
    assert result.proof["activation_scope"]["gated_execute_surfaces"] == ["direct_execute"]
    with pytest.raises(TypeError, match="immutable"):
        result.proof["status"] = "mutated"
    with pytest.raises(TypeError, match="immutable"):
        result.proof["activation_scope"]["gated_execute_surfaces"].append("ingest")


def test_activation_proof_contract_is_modeled_with_typeddicts() -> None:
    assert is_typeddict(ticket_runtime_readiness.ActivationProof)
    assert {
        "schema_version",
        "status",
        "run_nonce",
        "ticket_plugin",
        "runtime_identity",
        "inventory",
        "hook_membrane_proof",
        "activation_scope",
        "raw_evidence",
    } <= ticket_runtime_readiness.ActivationProof.__required_keys__


def test_runtime_activation_error_requires_error_code() -> None:
    with pytest.raises(ValueError, match="RuntimeActivationError validation failed"):
        ticket_runtime_readiness.RuntimeActivationError("", "bad")


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


def test_hook_manifest_path_accepts_resolved_equivalent_path(tmp_path: Path) -> None:
    project_root, installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    linked_root = tmp_path / "installed-ticket-link"
    linked_root.symlink_to(installed_root, target_is_directory=True)
    linked_hook_manifest = linked_root / "hooks" / "hooks.json"
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    inventory_transcript = run_dir / proof["raw_evidence"]["app_server_inventory_transcript"]
    proof["inventory"]["hook"]["hook_manifest_path"] = str(linked_hook_manifest)
    _write_jsonl(
        inventory_transcript,
        _inventory_transcript_rows(
            project_root=project_root,
            hook_manifest=linked_hook_manifest,
            guard_command=proof["inventory"]["hook"]["guard_command"],
        ),
    )
    proof["inventory"]["transcript_sha256"] = module.sha256_file(inventory_transcript)
    _write_proof(proof_path, proof)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is True
    assert result.error_code is None


def test_fixture_payload_hash_matches_payload_evidence(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    payload_before = run_dir / proof["raw_evidence"]["payload_before"]

    assert proof["hook_membrane_proof"]["payload_sha256"] == module.sha256_file(payload_before)


def test_explicit_proof_path_uses_proof_project_root_for_raw_evidence(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    nested_root = project_root / ".codex" / "ticket-runtime-smoke" / "run-1" / "post-direct"
    (nested_root / ".codex").mkdir(parents=True, exist_ok=True)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(
        project_root=nested_root,
        proof_path=proof_path,
    )

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


def test_deleted_pre_activation_raw_evidence_rejects(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    pre_events = run_dir / proof["raw_evidence"]["pre_activation_events"]
    pre_events.unlink()

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "raw_evidence_missing"
    assert str(pre_events) in result.message


def test_missing_executable_sha256_rejects(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["runtime_identity"]["executable_sha256"] = None
    proof["runtime_identity"]["executable_hash_unavailable_reason"] = "PermissionError: denied"
    proof_path.write_text(json.dumps(proof, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "proof_invalid"
    assert "executable_sha256" in result.message
    assert "PermissionError: denied" in result.message


def test_hash_read_oserror_normalizes_to_raw_evidence_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    inventory_path = run_dir / proof["raw_evidence"]["app_server_inventory_transcript"]
    original_sha256_file = module.sha256_file

    def _raise_for_inventory(path: Path) -> str:
        if path == inventory_path:
            raise OSError("inventory transcript unreadable")
        return original_sha256_file(path)

    monkeypatch.setattr(module, "sha256_file", _raise_for_inventory)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "raw_evidence_missing"
    assert str(inventory_path) in result.message


def test_write_json_is_atomic_when_replace_fails(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    path = tmp_path / "proof.json"
    path.write_text('{"status":"old"}\n', encoding="utf-8")

    def _raise_replace(src: str, dst: str) -> None:
        raise OSError(f"replace denied: {dst}")

    monkeypatch.setattr(ticket_runtime_readiness.os, "replace", _raise_replace)

    with pytest.raises(OSError, match="replace denied"):
        ticket_runtime_readiness._write_json(path, {"status": "new"})

    assert path.read_text(encoding="utf-8") == '{"status":"old"}\n'
    assert list(tmp_path.glob("*.tmp")) == []


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


def test_activation_bootstrap_accepts_only_temporary_in_progress_proof(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    post_events = run_dir / proof["raw_evidence"]["post_activation_events"]
    post_events.write_text("", encoding="utf-8")
    proof["status"] = "activation_in_progress"
    proof["post_activation_gated_smokes"] = {
        "status": "pending",
        "required_surfaces": ["direct_execute"],
        "surface_results": {
            "direct_execute": {
                "raw_events_sha256": module.sha256_file(post_events),
            }
        },
    }
    temp_proof_path = run_dir / "activated-ticket-runtime-proof.json"
    _write_proof(temp_proof_path, proof)

    normal = module.verify_installed_ticket_runtime_readiness_for_execute(
        project_root=project_root,
        proof_path=temp_proof_path,
    )
    bootstrap = module.verify_installed_ticket_runtime_readiness_for_execute(
        project_root=project_root,
        proof_path=temp_proof_path,
        allow_activation_bootstrap=True,
    )
    _write_proof(proof_path, proof)
    final_path_bootstrap = module.verify_installed_ticket_runtime_readiness_for_execute(
        project_root=project_root,
        proof_path=proof_path,
        allow_activation_bootstrap=True,
    )

    assert normal.passed is False
    assert normal.error_code == "proof_invalid"
    assert bootstrap.passed is True
    assert final_path_bootstrap.passed is False
    assert final_path_bootstrap.error_code == "proof_invalid"
    assert final_path_bootstrap.message == "Runtime proof is not activated"


@pytest.mark.parametrize(
    ("mutator", "expected_message"),
    [
        (
            lambda proof, paths, module: proof["post_activation_gated_smokes"].update(
                {"status": "pending"}
            ),
            "post-activation smoke has not passed",
        ),
        (
            lambda proof, paths, module: paths["post_events"].write_text("", encoding="utf-8"),
            "Post-activation transcript empty",
        ),
        (
            lambda proof, paths, module: Path(
                proof["post_activation_gated_smokes"]["surface_results"]["direct_execute"][
                    "ticket_path"
                ]
            ).unlink(),
            "Post-activation ticket missing",
        ),
        (
            lambda proof, paths, module: Path(
                proof["post_activation_gated_smokes"]["surface_results"]["direct_execute"][
                    "ticket_path"
                ]
            ).write_text("changed\n", encoding="utf-8"),
            "Post-activation ticket hash mismatch",
        ),
    ],
)
def test_activated_proof_requires_passed_post_activation_evidence(
    tmp_path: Path,
    mutator,
    expected_message: str,
) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    paths = {
        "post_events": run_dir / proof["raw_evidence"]["post_activation_events"],
    }
    mutator(proof, paths, module)
    _write_proof(proof_path, proof)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code in {
        "proof_invalid",
        "raw_evidence_missing",
        "post_activation_transcript_hash_mismatch",
    }
    assert expected_message in result.message


@pytest.mark.parametrize(
    ("mutator", "message"),
    [
        (lambda proof: proof.update({"schema_version": "unexpected"}), "schema_version"),
        (lambda proof: proof.update({"status": "activation_in_progress"}), "not activated"),
        (lambda proof: proof.update({"expires_at": "not-a-timestamp"}), "expires_at"),
        (lambda proof: proof.update({"expires_at": "2026-05-21T23:59:59"}), "expires_at"),
        (
            lambda proof: proof["activation_scope"].pop("gated_execute_surfaces"),
            "activation_scope.gated_execute_surfaces",
        ),
        (lambda proof: proof["raw_evidence"].pop("engine_stdout"), "raw_evidence"),
    ],
)
def test_proof_invalid_variants_reject(
    tmp_path: Path,
    mutator,
    message: str,
) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    mutator(proof)
    _write_proof(proof_path, proof)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "proof_invalid"
    assert message in result.message


def test_malformed_proof_json_rejects_as_proof_invalid(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof_path.write_text("{not-json\n", encoding="utf-8")

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "proof_invalid"


@pytest.mark.parametrize(
    ("proof_path_field", "expected_code"),
    [
        (("ticket_plugin", "plugin_manifest_path"), "plugin_manifest_path_mismatch"),
        (("inventory", "hook", "hook_manifest_path"), "hook_manifest_path_mismatch"),
        (("inventory", "hook", "guard_script_path"), "guard_script_path_mismatch"),
    ],
)
def test_path_mismatches_reject(
    tmp_path: Path,
    proof_path_field: tuple[str, ...],
    expected_code: str,
) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    _set_nested(proof, proof_path_field, str(tmp_path / "wrong-path"))
    _write_proof(proof_path, proof)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == expected_code


@pytest.mark.parametrize(
    ("target", "expected_code"),
    [
        ("plugin_manifest", "plugin_manifest_hash_mismatch"),
        ("hook_manifest", "hook_manifest_hash_mismatch"),
        ("guard_script", "guard_script_hash_mismatch"),
        ("inventory_transcript", "inventory_transcript_hash_mismatch"),
        ("hook_events", "hook_transcript_hash_mismatch"),
        ("post_events", "post_activation_transcript_hash_mismatch"),
        ("payload_before", "payload_hash_mismatch"),
        ("engine_stdout", "engine_stdout_hash_mismatch"),
    ],
)
def test_hash_mismatches_reject(
    tmp_path: Path,
    target: str,
    expected_code: str,
) -> None:
    project_root, installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]

    target_paths = {
        "plugin_manifest": installed_root / ".codex-plugin" / "plugin.json",
        "hook_manifest": Path(proof["inventory"]["hook"]["hook_manifest_path"]),
        "guard_script": Path(proof["inventory"]["hook"]["guard_script_path"]),
        "inventory_transcript": run_dir / proof["raw_evidence"]["app_server_inventory_transcript"],
        "hook_events": run_dir / proof["raw_evidence"]["hook_membrane_events"],
        "post_events": run_dir / proof["raw_evidence"]["post_activation_events"],
        "payload_before": run_dir / proof["raw_evidence"]["payload_before"],
        "engine_stdout": run_dir / proof["raw_evidence"]["engine_stdout"],
    }
    target_paths[target].write_text("changed\n", encoding="utf-8")
    _write_proof(proof_path, proof)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == expected_code


def test_nonce_mismatch_rejects(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["hook_membrane_proof"]["nonce"] = "different-nonce"
    _write_proof(proof_path, proof)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "nonce_mismatch"


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


def test_payload_hash_mismatch_rejects(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    proof["hook_membrane_proof"]["payload_sha256"] = "different-payload"
    _write_proof(proof_path, proof)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "payload_hash_mismatch"


def test_verifier_rederives_pre_activation_gate_from_raw_transcript(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    pre_events = run_dir / proof["raw_evidence"]["pre_activation_events"]
    pre_result = proof["pre_activation_gated_smokes"]["surface_results"]["direct_execute"]
    pre_events.write_text(
        json.dumps(
            _command_item_row(
                pre_result["command"],
                {"state": "policy_blocked", "error_code": "proof_invalid"},
            ),
            sort_keys=True,
            separators=(",", ":"),
        )
        + "\n",
        encoding="utf-8",
    )
    pre_result["raw_events_sha256"] = module.sha256_file(pre_events)
    _write_proof(proof_path, proof)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "proof_invalid"
    assert "runtime_readiness_required" in result.message


def test_verifier_rederives_post_activation_result_from_raw_transcript(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    hook_manifest = Path(proof["inventory"]["hook"]["hook_manifest_path"])
    post_events = run_dir / proof["raw_evidence"]["post_activation_events"]
    post_result = proof["post_activation_gated_smokes"]["surface_results"]["direct_execute"]
    _write_jsonl(
        post_events,
        [
            _hook_completed_row(hook_manifest),
            _command_item_row(
                post_result["command"],
                {"state": "policy_blocked", "error_code": "runtime_readiness_required"},
            ),
        ],
    )
    post_result["raw_events_sha256"] = module.sha256_file(post_events)
    _write_proof(proof_path, proof)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "proof_invalid"
    assert "ok_create" in result.message


def test_verifier_rederives_hook_membrane_completion_from_raw_transcript(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    hook_events = run_dir / proof["raw_evidence"]["hook_membrane_events"]
    _write_jsonl(
        hook_events,
        [
            _command_item_row(
                proof["hook_membrane_proof"]["command"],
                {"state": "ok_create"},
            )
        ],
    )
    proof["hook_membrane_proof"]["raw_events_sha256"] = module.sha256_file(hook_events)
    _write_proof(proof_path, proof)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "proof_invalid"
    assert "hook completion" in result.message


def test_verifier_rederives_activation_engine_stdout_from_raw_file(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    engine_stdout = run_dir / proof["raw_evidence"]["engine_stdout"]
    engine_stdout.write_text('{"state":"policy_blocked"}\n', encoding="utf-8")
    proof["hook_membrane_proof"]["engine_stdout_sha256"] = module.sha256_file(engine_stdout)
    _write_proof(proof_path, proof)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "proof_invalid"
    assert "ok_create" in result.message


def test_verifier_binds_guard_command_to_expected_script(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    hook_manifest = Path(proof["inventory"]["hook"]["hook_manifest_path"])
    inventory_transcript = run_dir / proof["raw_evidence"]["app_server_inventory_transcript"]
    wrong_guard = f"python3 {tmp_path / 'other' / 'ticket_engine_guard.py'}"
    hook_manifest.write_text(
        json.dumps(_hook_manifest_payload(wrong_guard), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    _write_jsonl(
        inventory_transcript,
        _inventory_transcript_rows(
            project_root=project_root,
            hook_manifest=hook_manifest,
            guard_command=wrong_guard,
        ),
    )
    proof["inventory"]["hook"]["guard_command"] = wrong_guard
    proof["inventory"]["hook"]["hook_manifest_sha256"] = module.sha256_file(hook_manifest)
    proof["inventory"]["transcript_sha256"] = module.sha256_file(inventory_transcript)
    _write_proof(proof_path, proof)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "proof_invalid"
    assert "Guard command" in result.message


def test_duplicate_inventory_transcript_response_id_rejects(tmp_path: Path) -> None:
    project_root, _installed_root, module, proof_path = build_valid_runtime_readiness_fixture(
        tmp_path
    )
    proof = json.loads(proof_path.read_text(encoding="utf-8"))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    inventory_transcript = run_dir / proof["raw_evidence"]["app_server_inventory_transcript"]
    rows = [
        json.loads(line)
        for line in inventory_transcript.read_text(encoding="utf-8").splitlines()
    ]
    duplicate = json.loads(json.dumps(rows[1]))
    rows.append(duplicate)
    _write_jsonl(inventory_transcript, rows)
    proof["inventory"]["transcript_sha256"] = module.sha256_file(inventory_transcript)
    _write_proof(proof_path, proof)

    result = module.verify_installed_ticket_runtime_readiness_for_execute(project_root=project_root)

    assert result.passed is False
    assert result.error_code == "proof_invalid"
    assert "duplicate response id 1" in result.message


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
        lambda **kwargs: _fake_smoke_result(
            tmp_path,
            project_root=project_root,
            run_dir=kwargs["run_dir"],
        ),
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


def test_build_activation_candidate_output_verifies_with_real_installed_verifier(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
        lambda **kwargs: _fake_inventory_result(
            tmp_path,
            run_dir=kwargs["run_dir"],
            executable_sha256="0" * 64,
        ),
    )
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "run_activation_smoke",
        lambda **kwargs: _fake_smoke_result(
            tmp_path,
            project_root=project_root,
            run_dir=kwargs["run_dir"],
        ),
    )

    result = ticket_runtime_readiness.build_activation_candidate(
        project_root=project_root,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert result.proof is not None
    proof = json.loads(json.dumps(result.proof))
    run_dir = project_root / proof["raw_evidence"]["run_dir"]
    proof["status"] = "activated"
    installed_root = Path(proof["ticket_plugin"]["installed_cache_root"])
    proof.update(_fake_post_activation_smoke_result(run_dir=run_dir, installed_root=installed_root))
    installed_module_path = installed_root / "scripts" / "ticket_runtime_readiness.py"
    installed_module_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(MODULE_SOURCE, installed_module_path)
    installed_module = load_module(installed_module_path)
    proof_path = project_root / ".codex" / "ticket-runtime-proof.json"
    _write_proof(proof_path, proof)

    verification = installed_module.verify_installed_ticket_runtime_readiness_for_execute(
        project_root=project_root,
        proof_path=proof_path,
    )

    assert verification.passed is True
    assert verification.error_code is None


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
        lambda **kwargs: _fake_smoke_result(
            tmp_path,
            project_root=project_root,
            run_dir=kwargs["run_dir"],
        ),
    )
    def _post_activation_smoke(**kwargs):
        proof = json.loads(kwargs["proof_path"].read_text(encoding="utf-8"))
        assert proof["status"] == "activation_in_progress"
        assert os.environ[ticket_runtime_readiness.RUNTIME_PROOF_PATH_ENV] == str(
            kwargs["proof_path"]
        )
        assert os.environ[ticket_runtime_readiness.RUNTIME_ACTIVATION_BOOTSTRAP_ENV] == "1"
        return _fake_post_activation_smoke_result(run_dir=kwargs["run_dir"])

    monkeypatch.setattr(
        ticket_runtime_readiness,
        "run_post_activation_direct_execute_smoke",
        _post_activation_smoke,
    )
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "verify_installed_ticket_runtime_readiness_for_execute",
        lambda **_kwargs: ticket_runtime_readiness.ReadinessSuccess(
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
    assert not (
        project_root
        / ".codex"
        / "ticket-runtime-smoke"
        / "run-1"
        / "activated-ticket-runtime-proof.json"
    ).exists()


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
        lambda **kwargs: _fake_smoke_result(
            tmp_path,
            project_root=project_root,
            run_dir=kwargs["run_dir"],
        ),
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
    assert not (
        project_root
        / ".codex"
        / "ticket-runtime-smoke"
        / "run-1"
        / "activated-ticket-runtime-proof.json"
    ).exists()


def test_activate_runtime_removes_temp_proof_after_verification_failure(
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
        lambda **kwargs: _fake_smoke_result(
            tmp_path,
            project_root=project_root,
            run_dir=kwargs["run_dir"],
        ),
    )
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "run_post_activation_direct_execute_smoke",
        lambda **kwargs: _fake_post_activation_smoke_result(run_dir=kwargs["run_dir"]),
    )
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "verify_installed_ticket_runtime_readiness_for_execute",
        lambda **_kwargs: ticket_runtime_readiness.ReadinessFailure(
            error_code="payload_hash_mismatch",
            message="Payload hash mismatch",
        ),
    )

    result = ticket_runtime_readiness.activate_runtime(
        project_root=project_root,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert result.proof is None
    assert result.error_code == "payload_hash_mismatch"
    assert "Direct execute smoke already succeeded" in result.message
    assert not (project_root / ".codex" / "ticket-runtime-proof.json").exists()
    run_dir = _run_dir_from_result(project_root, result)
    assert not (run_dir / "activated-ticket-runtime-proof.json").exists()
    _assert_late_failure_evidence_preserved(project_root, run_dir)


def test_activate_runtime_removes_temp_proof_after_verification_exception(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
        lambda **kwargs: _fake_smoke_result(
            tmp_path,
            project_root=project_root,
            run_dir=kwargs["run_dir"],
        ),
    )
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "run_post_activation_direct_execute_smoke",
        lambda **kwargs: _fake_post_activation_smoke_result(run_dir=kwargs["run_dir"]),
    )

    def _raise_oserror(**_kwargs):
        raise OSError("tampered proof path")

    monkeypatch.setattr(
        ticket_runtime_readiness,
        "verify_installed_ticket_runtime_readiness_for_execute",
        _raise_oserror,
    )

    result = ticket_runtime_readiness.activate_runtime(
        project_root=project_root,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert result.proof is None
    assert result.error_code == "deterministic_driver_unavailable"
    assert "Direct execute smoke already succeeded" in result.message
    assert "tampered proof path" in result.message
    assert not (project_root / ".codex" / "ticket-runtime-proof.json").exists()
    run_dir = _run_dir_from_result(project_root, result)
    assert not (run_dir / "activated-ticket-runtime-proof.json").exists()
    _assert_late_failure_evidence_preserved(project_root, run_dir)


def test_activate_runtime_removes_temp_proof_after_final_write_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
        lambda **kwargs: _fake_smoke_result(
            tmp_path,
            project_root=project_root,
            run_dir=kwargs["run_dir"],
        ),
    )
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "run_post_activation_direct_execute_smoke",
        lambda **kwargs: _fake_post_activation_smoke_result(run_dir=kwargs["run_dir"]),
    )
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "verify_installed_ticket_runtime_readiness_for_execute",
        lambda **_kwargs: ticket_runtime_readiness.ReadinessSuccess(
            message="verified",
        ),
    )
    real_write_json = ticket_runtime_readiness._write_json

    def _write_json(path: Path, payload: dict[str, object]) -> None:
        if path.name == "ticket-runtime-proof.json":
            raise OSError("final proof denied")
        real_write_json(path, payload)

    monkeypatch.setattr(ticket_runtime_readiness, "_write_json", _write_json)

    result = ticket_runtime_readiness.activate_runtime(
        project_root=project_root,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert result.proof is None
    assert result.error_code == "deterministic_driver_unavailable"
    assert "Direct execute smoke already succeeded" in result.message
    assert "final proof denied" in result.message
    assert not (project_root / ".codex" / "ticket-runtime-proof.json").exists()
    run_dir = _run_dir_from_result(project_root, result)
    assert not (run_dir / "activated-ticket-runtime-proof.json").exists()
    _assert_late_failure_evidence_preserved(project_root, run_dir)


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
    gate_command_prefix = (
        f"uv run python -B {installed_root}/scripts/ticket_engine_agent.py execute "
    )

    def _fake_turn(**kwargs):
        if f"Command: {expected_command}" not in kwargs["prompt_text"]:
            assert gate_command_prefix in kwargs["prompt_text"]
            return [
                {
                    "direction": "recv",
                    "body": {
                        "params": {
                            "item": {
                                "type": "commandExecution",
                                "id": "cmd-gate",
                                "command": kwargs["prompt_text"]
                                .split("Command: ", 1)[1]
                                .split("\n", 1)[0],
                                "aggregatedOutput": json.dumps(
                                    {
                                        "state": "policy_blocked",
                                        "error_code": "runtime_readiness_required",
                                    }
                                ),
                            }
                        }
                    },
                }
            ]
        return [
            {
                "direction": "recv",
                "body": {
                    "method": "hook/completed",
                    "params": {
                        "run": {
                            "eventName": "preToolUse",
                            "sourcePath": str(installed_root / "hooks" / "hooks.json"),
                            "entries": [],
                        }
                    },
                },
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
            {
                "direction": "recv",
                "body": {
                    "method": "item/commandExecution/outputDelta",
                    "params": {"delta": '{"state":"ok_create"}'},
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
    assert "app_server_stderr" in result["raw_evidence"]
    assert "engine_stderr" not in result["raw_evidence"]


def test_run_activation_smoke_rejects_empty_engine_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    gate_command_prefix = (
        f"uv run python -B {installed_root}/scripts/ticket_engine_agent.py execute "
    )

    def _fake_turn(**kwargs):
        if expected_command not in kwargs["prompt_text"]:
            assert gate_command_prefix in kwargs["prompt_text"]
            return [
                {
                    "direction": "recv",
                    "body": {
                        "params": {
                            "item": {
                                "type": "commandExecution",
                                "id": "cmd-gate",
                                "command": kwargs["prompt_text"]
                                .split("Command: ", 1)[1]
                                .split("\n", 1)[0],
                                "aggregatedOutput": json.dumps(
                                    {
                                        "state": "policy_blocked",
                                        "error_code": "runtime_readiness_required",
                                    }
                                ),
                            }
                        }
                    },
                }
            ]
        return [
            {
                "direction": "recv",
                "body": {
                    "method": "hook/completed",
                    "params": {
                        "run": {
                            "eventName": "preToolUse",
                            "sourcePath": str(installed_root / "hooks" / "hooks.json"),
                            "entries": [],
                        }
                    },
                },
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

    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError) as exc_info:
        ticket_runtime_readiness.run_activation_smoke(
            project_root=project_root,
            tickets_dir=tickets_dir,
            run_dir=run_dir,
            installed_ticket_root=installed_root,
        )

    assert exc_info.value.error_code == "deterministic_driver_unavailable"
    assert "did not emit engine output" in exc_info.value.message


def test_run_activation_smoke_rejects_invalid_engine_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    gate_command_prefix = (
        f"uv run python -B {installed_root}/scripts/ticket_engine_agent.py execute "
    )

    def _fake_turn(**kwargs):
        if expected_command not in kwargs["prompt_text"]:
            assert gate_command_prefix in kwargs["prompt_text"]
            return [
                {
                    "direction": "recv",
                    "body": {
                        "params": {
                            "item": {
                                "type": "commandExecution",
                                "id": "cmd-gate",
                                "command": kwargs["prompt_text"]
                                .split("Command: ", 1)[1]
                                .split("\n", 1)[0],
                                "aggregatedOutput": json.dumps(
                                    {
                                        "state": "policy_blocked",
                                        "error_code": "runtime_readiness_required",
                                    }
                                ),
                            }
                        }
                    },
                }
            ]
        return [
            {
                "direction": "recv",
                "body": {
                    "method": "hook/completed",
                    "params": {
                        "run": {
                            "eventName": "preToolUse",
                            "sourcePath": str(installed_root / "hooks" / "hooks.json"),
                            "entries": [],
                        }
                    },
                },
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
            {
                "direction": "recv",
                "body": {
                    "method": "item/commandExecution/outputDelta",
                    "params": {"delta": "not-json"},
                },
            },
        ]

    monkeypatch.setattr(ticket_runtime_readiness, "_run_app_server_turn", _fake_turn)

    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError) as exc_info:
        ticket_runtime_readiness.run_activation_smoke(
            project_root=project_root,
            tickets_dir=tickets_dir,
            run_dir=run_dir,
            installed_ticket_root=installed_root,
        )

    assert exc_info.value.error_code == "deterministic_driver_unavailable"
    assert "invalid engine output" in exc_info.value.message


def test_run_activation_smoke_ignores_unrelated_hook_completions(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
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
    gate_command_prefix = (
        f"uv run python -B {installed_root}/scripts/ticket_engine_agent.py execute "
    )

    def _fake_turn(**kwargs):
        if expected_command not in kwargs["prompt_text"]:
            assert gate_command_prefix in kwargs["prompt_text"]
            return [
                {
                    "direction": "recv",
                    "body": {
                        "params": {
                            "item": {
                                "type": "commandExecution",
                                "id": "cmd-gate",
                                "command": kwargs["prompt_text"]
                                .split("Command: ", 1)[1]
                                .split("\n", 1)[0],
                                "aggregatedOutput": json.dumps(
                                    {
                                        "state": "policy_blocked",
                                        "error_code": "runtime_readiness_required",
                                    }
                                ),
                            }
                        }
                    },
                }
            ]
        return [
            {
                "direction": "recv",
                "body": {
                    "method": "hook/completed",
                    "params": {
                        "run": {
                            "eventName": "preToolUse",
                            "sourcePath": "/other/plugin/hooks/hooks.json",
                            "entries": [],
                        }
                    },
                },
            },
            {
                "direction": "recv",
                "body": {
                    "method": "hook/completed",
                    "params": {
                        "run": {
                            "eventName": "preToolUse",
                            "sourcePath": str(installed_root / "hooks" / "hooks.json"),
                            "entries": [],
                        }
                    },
                },
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
            {
                "direction": "recv",
                "body": {
                    "method": "item/commandExecution/outputDelta",
                    "params": {"delta": '{"state":"ok_create"}'},
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

    assert result["hook_membrane_proof"]["status"] == "passed"


def test_run_activation_smoke_rejects_malformed_hook_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    tickets_dir = project_root / "docs" / "tickets"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    installed_root = tmp_path / "installed"
    tickets_dir.mkdir(parents=True)
    activation_command = (
        f"uv run python -B {installed_root}/scripts/ticket_engine_activation_smoke.py "
        f"execute {run_dir / 'payload.json'}"
    )

    def _fake_turn(**kwargs):
        assert f"Command: {activation_command}" in kwargs["prompt_text"]
        return [
            {
                "direction": "recv",
                "body": {
                    "method": "hook/completed",
                    "params": {
                        "run": {
                            "eventName": "preToolUse",
                            "sourcePath": str(installed_root / "hooks" / "hooks.json"),
                            "entries": {"bad": "shape"},
                        }
                    },
                },
            },
            {
                "direction": "recv",
                "body": {
                    "params": {
                        "item": {
                            "type": "commandExecution",
                            "id": "cmd-1",
                            "command": activation_command,
                            "aggregatedOutput": json.dumps({"state": "ok_create"}),
                        }
                    }
                },
            },
        ]

    monkeypatch.setattr(ticket_runtime_readiness, "_run_app_server_turn", _fake_turn)
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "run_pre_activation_direct_execute_gate_smoke",
        lambda **_kwargs: {
            "pre_activation_gated_smokes": {
                "status": "passed",
                "required_surfaces": ["direct_execute"],
                "surface_results": {
                    "direct_execute": {
                        "runner": "app_server_turn",
                        "command": "uv run python -B installed/scripts/ticket_engine_agent.py",
                        "execute_surface": "direct_execute",
                        "engine_state": "policy_blocked",
                        "error_code": "runtime_readiness_required",
                        "raw_events_sha256": "0" * 64,
                    }
                },
            },
            "raw_evidence": {"pre_activation_events": "raw/pre-activation-gated-events.jsonl"},
        },
    )

    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError) as exc_info:
        ticket_runtime_readiness.run_activation_smoke(
            project_root=project_root,
            tickets_dir=tickets_dir,
            run_dir=run_dir,
            installed_ticket_root=installed_root,
        )

    assert exc_info.value.error_code == "hook_contract_blocked"


def test_run_activation_smoke_rejects_legacy_hook_specific_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    tickets_dir = project_root / "docs" / "tickets"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    installed_root = tmp_path / "installed"
    tickets_dir.mkdir(parents=True)
    activation_command = (
        f"uv run python -B {installed_root}/scripts/ticket_engine_activation_smoke.py "
        f"execute {run_dir / 'payload.json'}"
    )

    def _fake_turn(**kwargs):
        assert f"Command: {activation_command}" in kwargs["prompt_text"]
        return [
            {
                "direction": "recv",
                "body": {
                    "method": "hook/completed",
                    "params": {
                        "run": {
                            "eventName": "preToolUse",
                            "sourcePath": str(installed_root / "hooks" / "hooks.json"),
                            "hookSpecificOutput": {
                                "permissionDecision": "allow",
                                "permissionDecisionReason": "Ticket command validated",
                            },
                        }
                    },
                },
            },
            _command_item_row(activation_command, {"state": "ok_create"}),
        ]

    monkeypatch.setattr(ticket_runtime_readiness, "_run_app_server_turn", _fake_turn)
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "run_pre_activation_direct_execute_gate_smoke",
        lambda **_kwargs: _fake_pre_activation_gate_result(),
    )

    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError) as exc_info:
        ticket_runtime_readiness.run_activation_smoke(
            project_root=project_root,
            tickets_dir=tickets_dir,
            run_dir=run_dir,
            installed_ticket_root=installed_root,
        )

    assert exc_info.value.error_code == "hook_contract_blocked"
    assert "unsupported" in exc_info.value.message.lower()


def test_run_activation_smoke_rejects_stop_entries(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    tickets_dir = project_root / "docs" / "tickets"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    installed_root = tmp_path / "installed"
    tickets_dir.mkdir(parents=True)
    activation_command = (
        f"uv run python -B {installed_root}/scripts/ticket_engine_activation_smoke.py "
        f"execute {run_dir / 'payload.json'}"
    )

    def _fake_turn(**kwargs):
        assert f"Command: {activation_command}" in kwargs["prompt_text"]
        return [
            {
                "direction": "recv",
                "body": {
                    "method": "hook/completed",
                    "params": {
                        "run": {
                            "eventName": "preToolUse",
                            "sourcePath": str(installed_root / "hooks" / "hooks.json"),
                            "entries": [{"kind": "stop", "text": "Ticket command blocked"}],
                        }
                    },
                },
            },
            _command_item_row(activation_command, {"state": "ok_create"}),
        ]

    monkeypatch.setattr(ticket_runtime_readiness, "_run_app_server_turn", _fake_turn)
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "run_pre_activation_direct_execute_gate_smoke",
        lambda **_kwargs: _fake_pre_activation_gate_result(),
    )

    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError) as exc_info:
        ticket_runtime_readiness.run_activation_smoke(
            project_root=project_root,
            tickets_dir=tickets_dir,
            run_dir=run_dir,
            installed_ticket_root=installed_root,
        )

    assert exc_info.value.error_code == "hook_contract_blocked"
    assert "deny" in exc_info.value.message.lower() or "stop" in exc_info.value.message.lower()


def test_pre_activation_gate_smoke_clears_and_restores_runtime_env(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    installed_root = tmp_path / "installed"
    project_root.mkdir(parents=True)
    monkeypatch.setenv(ticket_runtime_readiness.RUNTIME_PROOF_PATH_ENV, "outer-proof.json")
    monkeypatch.setenv(ticket_runtime_readiness.RUNTIME_ACTIVATION_BOOTSTRAP_ENV, "1")

    def _fake_turn(**kwargs):
        assert os.environ.get(ticket_runtime_readiness.RUNTIME_PROOF_PATH_ENV) is None
        assert os.environ.get(ticket_runtime_readiness.RUNTIME_ACTIVATION_BOOTSTRAP_ENV) is None
        command = kwargs["prompt_text"].split("Command: ", 1)[1].split("\n", 1)[0]
        return [
            _command_item_row(
                command,
                {"state": "policy_blocked", "error_code": "runtime_readiness_required"},
            )
        ]

    monkeypatch.setattr(ticket_runtime_readiness, "_run_app_server_turn", _fake_turn)

    result = ticket_runtime_readiness.run_pre_activation_direct_execute_gate_smoke(
        project_root=project_root,
        run_dir=run_dir,
        installed_ticket_root=installed_root,
    )

    assert result["pre_activation_gated_smokes"]["status"] == "passed"
    assert os.environ[ticket_runtime_readiness.RUNTIME_PROOF_PATH_ENV] == "outer-proof.json"
    assert os.environ[ticket_runtime_readiness.RUNTIME_ACTIVATION_BOOTSTRAP_ENV] == "1"


def test_run_activation_smoke_requires_pre_activation_gate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    tickets_dir = project_root / "docs" / "tickets"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    installed_root = tmp_path / "installed"
    tickets_dir.mkdir(parents=True)
    activation_command = (
        f"uv run python -B {installed_root}/scripts/ticket_engine_activation_smoke.py "
        f"execute {run_dir / 'payload.json'}"
    )
    gate_command_prefix = (
        f"uv run python -B {installed_root}/scripts/ticket_engine_agent.py execute "
    )
    calls: list[str] = []

    def _fake_turn(**kwargs):
        prompt = kwargs["prompt_text"]
        calls.append(prompt)
        if activation_command in prompt:
            return [
                {
                    "direction": "recv",
                    "body": {
                        "method": "hook/completed",
                        "params": {
                            "run": {
                                "eventName": "preToolUse",
                                "sourcePath": str(installed_root / "hooks" / "hooks.json"),
                                "entries": [],
                            }
                        },
                    },
                },
                {
                    "direction": "recv",
                    "body": {
                        "params": {
                            "item": {
                                "type": "commandExecution",
                                "id": "cmd-1",
                                "command": activation_command,
                            }
                        }
                    },
                },
                {
                    "direction": "recv",
                    "body": {
                        "method": "item/commandExecution/outputDelta",
                        "params": {"delta": '{"state":"ok_create"}'},
                    },
                },
            ]
        assert gate_command_prefix in prompt
        return [
            {
                "direction": "recv",
                "body": {
                    "params": {
                        "item": {
                            "type": "commandExecution",
                            "id": "cmd-2",
                            "command": prompt.split("Command: ", 1)[1].split("\n", 1)[0],
                            "aggregatedOutput": json.dumps(
                                {
                                    "state": "ok_create",
                                    "data": {"ticket_path": str(run_dir / "unexpected.md")},
                                }
                            ),
                        }
                    }
                },
            }
        ]

    monkeypatch.setattr(ticket_runtime_readiness, "_run_app_server_turn", _fake_turn)

    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError) as exc_info:
        ticket_runtime_readiness.run_activation_smoke(
            project_root=project_root,
            tickets_dir=tickets_dir,
            run_dir=run_dir,
            installed_ticket_root=installed_root,
        )

    assert len(calls) == 2
    assert exc_info.value.error_code == "engine_gate_required"


def test_run_post_activation_direct_execute_smoke_stages_auto_audit_policy_lane(
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
        payload = json.loads(
            (run_dir / "post-direct" / "post-direct-payload.json").read_text(encoding="utf-8")
        )
        assert payload["autonomy_config"] == {
            "mode": "auto_audit",
            "max_creates": 5,
            "warnings": [],
        }
        assert (run_dir / "post-direct" / ".codex" / "ticket.local.md").read_text(
            encoding="utf-8"
        ) == "---\nautonomy_mode: auto_audit\nmax_creates_per_session: 5\n---\n"
        return [
            {
                "direction": "recv",
                "body": {
                    "method": "hook/completed",
                    "params": {
                        "run": {
                            "eventName": "preToolUse",
                            "sourcePath": str(installed_root / "hooks" / "hooks.json"),
                            "entries": [{"kind": "feedback", "text": "Ticket command validated"}],
                        }
                    },
                },
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

    assert (
        result["post_activation_gated_smokes"]["surface_results"]["direct_execute"]["engine_state"]
        == "ok_create"
    )


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
                    "method": "hook/completed",
                    "params": {
                        "run": {
                            "eventName": "preToolUse",
                            "sourcePath": str(installed_root / "hooks" / "hooks.json"),
                            "entries": [{"kind": "feedback", "text": "Ticket command validated"}],
                        }
                    },
                },
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


def test_run_post_activation_direct_execute_smoke_accepts_aggregated_output(
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
                    "method": "hook/completed",
                    "params": {
                        "run": {
                            "eventName": "preToolUse",
                            "sourcePath": str(installed_root / "hooks" / "hooks.json"),
                            "entries": [{"kind": "feedback", "text": "Ticket command validated"}],
                        }
                    },
                },
            },
            {
                "direction": "recv",
                "body": {
                    "params": {
                        "item": {
                            "type": "commandExecution",
                            "id": "cmd-1",
                            "command": expected_command,
                            "aggregatedOutput": json.dumps(
                                {
                                    "state": "ok_create",
                                    "data": {"ticket_path": str(ticket_path)},
                                }
                            ),
                        }
                    }
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

    assert result["post_activation_gated_smokes"]["surface_results"]["direct_execute"][
        "ticket_path"
    ] == str(ticket_path)


def test_run_post_activation_direct_execute_smoke_requires_allowing_hook_result(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    tickets_dir = project_root / "docs" / "tickets"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    installed_root = tmp_path / "installed"
    proof_path = run_dir / "activated-ticket-runtime-proof.json"
    ticket_path = run_dir / "post-direct" / "docs" / "tickets" / "2026-05-20-example.md"
    tickets_dir.mkdir(parents=True)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text("{}", encoding="utf-8")
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
                    "method": "hook/completed",
                    "params": {
                        "run": {
                            "eventName": "preToolUse",
                            "sourcePath": str(installed_root / "hooks" / "hooks.json"),
                            "entries": [{"kind": "stop", "text": "Ticket command blocked"}],
                        }
                    },
                },
            },
            {
                "direction": "recv",
                "body": {
                    "params": {
                        "item": {
                            "type": "commandExecution",
                            "id": "cmd-1",
                            "command": expected_command,
                            "aggregatedOutput": json.dumps(
                                {
                                    "state": "ok_create",
                                    "data": {"ticket_path": str(ticket_path)},
                                }
                            ),
                        }
                    }
                },
            },
        ]

    monkeypatch.setattr(ticket_runtime_readiness, "_run_app_server_turn", _fake_turn)

    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError) as exc_info:
        ticket_runtime_readiness.run_post_activation_direct_execute_smoke(
            project_root=project_root,
            tickets_dir=tickets_dir,
            run_dir=run_dir,
            installed_ticket_root=installed_root,
            proof_path=proof_path,
        )

    assert exc_info.value.error_code == "hook_contract_blocked"
    assert "allow" in exc_info.value.message.lower()


@pytest.mark.parametrize(
    ("stdout_text", "expected_code", "expected_message", "create_ticket"),
    [
        ("", "deterministic_driver_unavailable", "did not emit engine output", False),
        ("not-json", "deterministic_driver_unavailable", "invalid engine output", False),
        ("[]", "deterministic_driver_unavailable", "non-object engine output", False),
        (
            json.dumps({"state": "policy_blocked"}),
            "runtime_readiness_required",
            "did not reach an activated runtime-ready create result",
            False,
        ),
        (
            json.dumps({"state": "ok_create", "data": {}}),
            "deterministic_driver_unavailable",
            "did not report a created ticket path",
            False,
        ),
        (
            json.dumps(
                {
                    "state": "ok_create",
                    "data": {"ticket_path": "__TICKET_PATH__"},
                }
            ),
            "deterministic_driver_unavailable",
            "ticket missing",
            False,
        ),
    ],
)
def test_run_post_activation_direct_execute_smoke_rejects_bad_engine_output(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    stdout_text: str,
    expected_code: str,
    expected_message: str,
    create_ticket: bool,
) -> None:
    project_root = tmp_path / "project"
    tickets_dir = project_root / "docs" / "tickets"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    installed_root = tmp_path / "installed"
    proof_path = run_dir / "activated-ticket-runtime-proof.json"
    ticket_path = run_dir / "post-direct" / "docs" / "tickets" / "2026-05-20-example.md"
    tickets_dir.mkdir(parents=True)
    proof_path.parent.mkdir(parents=True, exist_ok=True)
    proof_path.write_text("{}", encoding="utf-8")
    if create_ticket:
        ticket_path.parent.mkdir(parents=True, exist_ok=True)
        ticket_path.write_text("# T-20260520-01: Runtime activation smoke\n", encoding="utf-8")
    expected_command = (
        f"uv run python -B {installed_root}/scripts/ticket_engine_agent.py "
        f"execute {run_dir / 'post-direct' / 'post-direct-payload.json'}"
    )
    active_stdout = stdout_text.replace("__TICKET_PATH__", str(ticket_path))

    def _fake_turn(**kwargs):
        assert f"Command: {expected_command}" in kwargs["prompt_text"]
        item: dict[str, object] = {
            "type": "commandExecution",
            "id": "cmd-1",
            "command": expected_command,
        }
        if active_stdout:
            item["aggregatedOutput"] = active_stdout
        return [
            {
                "direction": "recv",
                "body": {
                    "method": "hook/completed",
                    "params": {
                        "run": {
                            "eventName": "preToolUse",
                            "sourcePath": str(installed_root / "hooks" / "hooks.json"),
                            "entries": [{"kind": "feedback", "text": "Ticket command validated"}],
                        }
                    },
                },
            },
            {"direction": "recv", "body": {"params": {"item": item}}},
        ]

    monkeypatch.setattr(ticket_runtime_readiness, "_run_app_server_turn", _fake_turn)

    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError) as exc_info:
        ticket_runtime_readiness.run_post_activation_direct_execute_smoke(
            project_root=project_root,
            tickets_dir=tickets_dir,
            run_dir=run_dir,
            installed_ticket_root=installed_root,
            proof_path=proof_path,
        )

    assert exc_info.value.error_code == expected_code
    assert expected_message in exc_info.value.message


def test_read_message_rejects_malformed_app_server_json() -> None:
    output: queue.Queue[str | None] = queue.Queue()
    transcript: list[dict[str, object]] = []
    output.put("not-json\n")

    with pytest.raises(
        ticket_runtime_readiness.RuntimeActivationError,
        match="Malformed app-server JSON response",
    ):
        ticket_runtime_readiness._read_message(
            output=output,
            transcript=transcript,
            timeout=1.0,
        )

    assert transcript == [{"direction": "recv-raw", "body": "not-json"}]


def test_read_message_rejects_stdout_eof() -> None:
    output: queue.Queue[str | None] = queue.Queue()
    transcript: list[dict[str, object]] = []
    output.put(None)

    with pytest.raises(
        ticket_runtime_readiness.RuntimeActivationError,
        match="app-server stdout closed unexpectedly",
    ):
        ticket_runtime_readiness._read_message(
            output=output,
            transcript=transcript,
            timeout=1.0,
        )


def test_wait_for_response_rejects_app_server_error_response() -> None:
    output: queue.Queue[str | None] = queue.Queue()
    transcript: list[dict[str, object]] = []
    output.put('{"id":4,"error":{"message":"bad request"}}\n')

    with pytest.raises(
        ticket_runtime_readiness.RuntimeActivationError,
        match="app-server returned error for request 4",
    ):
        ticket_runtime_readiness._wait_for_response(
            output=output,
            transcript=transcript,
            expected_id=4,
        )


def test_wait_for_response_rejects_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    output: queue.Queue[str | None] = queue.Queue()
    transcript: list[dict[str, object]] = []
    monkeypatch.setattr(ticket_runtime_readiness, "REQUEST_TIMEOUT_SECONDS", 0.001)

    with pytest.raises(
        ticket_runtime_readiness.RuntimeActivationError,
        match="Timed out waiting for app-server response 9",
    ):
        ticket_runtime_readiness._wait_for_response(
            output=output,
            transcript=transcript,
            expected_id=9,
        )


def test_wait_for_response_rejects_dead_app_server_with_stderr() -> None:
    class DeadProc:
        returncode = 2

        def poll(self) -> int:
            return self.returncode

    output: queue.Queue[str | None] = queue.Queue()
    transcript: list[dict[str, object]] = []

    with pytest.raises(
        ticket_runtime_readiness.RuntimeActivationError,
        match="app-server exited with code 2: fatal stderr",
    ):
        ticket_runtime_readiness._wait_for_response(
            output=output,
            transcript=transcript,
            expected_id=9,
            proc=DeadProc(),
            stderr_lines=["fatal stderr"],
            reader_errors=[],
        )


def test_wait_for_response_rejects_reader_exception() -> None:
    output: queue.Queue[str | None] = queue.Queue()
    transcript: list[dict[str, object]] = []

    with pytest.raises(
        ticket_runtime_readiness.RuntimeActivationError,
        match="app-server reader failed: stdout reader failed",
    ):
        ticket_runtime_readiness._wait_for_response(
            output=output,
            transcript=transcript,
            expected_id=9,
            reader_errors=["stdout reader failed: RuntimeError('broken pipe')"],
        )


def test_app_server_roundtrip_reports_late_reader_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Writer:
        def write(self, _chunk: str) -> int:
            return 1

        def flush(self) -> None:
            return None

    class RaisingIterable:
        def __iter__(self):
            raise RuntimeError("late stderr failure")

    class FakeProc:
        def __init__(self) -> None:
            self.stdin = Writer()
            self.stdout = iter(['{"id":0,"result":{"ok":true}}\n'])
            self.stderr = RaisingIterable()
            self.returncode = None

        def terminate(self) -> None:
            return None

        def wait(self, timeout: int) -> int:
            self.returncode = 0
            return 0

        def kill(self) -> None:
            self.returncode = -9

        def poll(self) -> None:
            return None

    monkeypatch.setattr(
        ticket_runtime_readiness.subprocess,
        "Popen",
        lambda *_args, **_kwargs: FakeProc(),
    )

    with pytest.raises(
        ticket_runtime_readiness.RuntimeActivationError,
        match="app-server reader failed: stderr reader failed",
    ):
        ticket_runtime_readiness._app_server_roundtrip(
            requests=[{"id": 0, "method": "initialize"}],
            cwd=tmp_path,
            executable="codex",
        )


def test_run_app_server_turn_reports_late_reader_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class Writer:
        def write(self, _chunk: str) -> int:
            return 1

        def flush(self) -> None:
            return None

    class RaisingIterable:
        def __iter__(self):
            raise RuntimeError("late stderr failure")

    class FakeProc:
        def __init__(self) -> None:
            self.stdin = Writer()
            self.stdout = iter(
                [
                    '{"id":0,"result":{"ok":true}}\n',
                    '{"id":1,"result":{"thread":{"id":"thread-1"}}}\n',
                    '{"id":2,"result":{"turn":{"id":"turn-1"}}}\n',
                    '{"method":"turn/completed","params":{"turn":{"id":"turn-1"}}}\n',
                ]
            )
            self.stderr = RaisingIterable()
            self.returncode = None

        def terminate(self) -> None:
            return None

        def wait(self, timeout: int) -> int:
            self.returncode = 0
            return 0

        def kill(self) -> None:
            self.returncode = -9

        def poll(self) -> None:
            return None

    monkeypatch.setattr(
        ticket_runtime_readiness.subprocess,
        "Popen",
        lambda *_args, **_kwargs: FakeProc(),
    )

    with pytest.raises(
        ticket_runtime_readiness.RuntimeActivationError,
        match="app-server reader failed: stderr reader failed",
    ):
        ticket_runtime_readiness._run_app_server_turn(
            project_root=tmp_path,
            contained_root=tmp_path,
            prompt_text="run one command",
            executable="codex",
        )


def test_drain_until_turn_completed_requires_turn_id() -> None:
    output: queue.Queue[str | None] = queue.Queue()
    transcript: list[dict[str, object]] = []

    with pytest.raises(
        ticket_runtime_readiness.RuntimeActivationError,
        match="turn/start missing turn id",
    ):
        ticket_runtime_readiness._drain_until_turn_completed(
            output=output,
            transcript=transcript,
            turn_id="",
        )


def test_resolve_executable_sha256_records_oserror_reason(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    executable = tmp_path / "codex"
    executable.write_text("#!/bin/sh\n", encoding="utf-8")
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "_resolve_codex_executable",
        lambda _executable: str(executable),
    )

    def _permission_error(_path: Path) -> str:
        raise PermissionError("denied")

    monkeypatch.setattr(ticket_runtime_readiness, "sha256_file", _permission_error)

    digest, reason = ticket_runtime_readiness._resolve_executable_sha256_with_reason(None)

    assert digest is None
    assert reason == "PermissionError: denied"


def test_unlink_if_exists_reports_cleanup_oserror(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    target = tmp_path / "proof.json"
    target.write_text("{}", encoding="utf-8")

    def _raise_permission_error(_self: Path) -> None:
        raise PermissionError("denied")

    monkeypatch.setattr(Path, "unlink", _raise_permission_error)

    ticket_runtime_readiness._unlink_if_exists(target)

    assert "runtime activation cleanup failed: denied" in capsys.readouterr().err


def test_capture_codex_version_translates_timeout(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ticket_runtime_readiness, "_resolve_codex_executable", lambda _exe: "codex")

    def _timeout(*_args, **kwargs):
        raise subprocess.TimeoutExpired(cmd=["codex", "--version"], timeout=kwargs["timeout"])

    monkeypatch.setattr(ticket_runtime_readiness.subprocess, "run", _timeout)

    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError) as exc_info:
        ticket_runtime_readiness._capture_codex_version(None)

    assert exc_info.value.error_code == "deterministic_driver_unavailable"
    assert "timed out" in exc_info.value.message


def test_capture_codex_version_translates_oserror(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ticket_runtime_readiness, "_resolve_codex_executable", lambda _exe: "codex")

    def _raise_oserror(*_args, **_kwargs):
        raise FileNotFoundError("missing executable")

    monkeypatch.setattr(ticket_runtime_readiness.subprocess, "run", _raise_oserror)

    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError) as exc_info:
        ticket_runtime_readiness._capture_codex_version(None)

    assert exc_info.value.error_code == "deterministic_driver_unavailable"
    assert "missing executable" in exc_info.value.message


def test_build_activation_candidate_reports_missing_codex_cli(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    tickets_dir = project_root / "docs" / "tickets"
    marketplace_path = project_root / ".agents" / "plugins" / "marketplace.json"
    (project_root / ".git").mkdir(parents=True)
    tickets_dir.mkdir(parents=True)
    marketplace_path.parent.mkdir(parents=True, exist_ok=True)
    marketplace_path.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(ticket_runtime_readiness.shutil, "which", lambda _name: None)

    result = ticket_runtime_readiness.build_activation_candidate(
        project_root=project_root,
        tickets_dir=tickets_dir,
        marketplace_path=marketplace_path,
    )

    assert result.proof is None
    assert result.error_code == "deterministic_driver_unavailable"
    assert result.message == "codex executable not found"


def test_collect_installed_runtime_inventory_parses_live_shapes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    marketplace_path = project_root / ".agents" / "plugins" / "marketplace.json"
    installed_root = tmp_path / "installed-ticket"
    hooks_dir = installed_root / "hooks"
    plugin_manifest = installed_root / ".codex-plugin" / "plugin.json"
    hook_manifest = hooks_dir / "hooks.json"
    guard_script = hooks_dir / "ticket_engine_guard.py"
    linked_root = tmp_path / "installed-ticket-link"
    project_root.mkdir(parents=True)
    marketplace_path.parent.mkdir(parents=True)
    marketplace_path.write_text("{}", encoding="utf-8")
    hooks_dir.mkdir(parents=True)
    plugin_manifest.parent.mkdir(parents=True)
    plugin_manifest.write_text('{"name":"ticket"}\n', encoding="utf-8")
    guard_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    guard_command = f"python3 {guard_script}"
    hook_manifest.write_text(
        json.dumps(_hook_manifest_payload(guard_command), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    linked_root.symlink_to(installed_root, target_is_directory=True)
    linked_hook_manifest = linked_root / "hooks" / "hooks.json"
    transcript = [
        {"direction": "recv", "body": {"id": 0, "result": {"ok": True}}},
        {
            "direction": "recv",
            "body": {
                "id": 1,
                "result": {
                    "source": {"path": str(project_root / "plugins" / "turbo-mode" / "ticket")},
                    "plugin": {"summary": {"version": "1.4.0"}},
                },
            },
        },
        {"direction": "recv", "body": {"id": 2, "result": {"plugins": []}}},
        {"direction": "recv", "body": {"id": 3, "result": {"skills": []}}},
        {
            "direction": "recv",
            "body": {
                "id": 4,
                "result": {
                    "hooks": [
                        {
                            "pluginId": "ticket@turbo-mode",
                            "eventName": "preToolUse",
                            "matcher": "Bash",
                            "command": guard_command,
                            "sourcePath": str(linked_hook_manifest),
                        }
                    ]
                },
            },
        },
    ]
    monkeypatch.setattr(ticket_runtime_readiness, "_app_server_roundtrip", lambda **_kw: transcript)
    monkeypatch.setattr(ticket_runtime_readiness, "_capture_codex_version", lambda _exe: "codex 1")
    monkeypatch.setattr(ticket_runtime_readiness, "_resolve_codex_executable", lambda _exe: "codex")
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "_resolve_executable_sha256_with_reason",
        lambda _exe: ("0" * 64, None),
    )

    result = ticket_runtime_readiness.collect_installed_runtime_inventory(
        project_root=project_root,
        marketplace_path=marketplace_path,
        run_dir=run_dir,
        executable="codex",
    )

    assert result["inventory"]["plugin_read_source_path"] == str(
        project_root / "plugins" / "turbo-mode" / "ticket"
    )
    assert result["inventory"]["installed_runtime_root"] == str(installed_root)
    assert result["inventory"]["hook"]["hook_manifest_path"] == str(
        hook_manifest.resolve(strict=False)
    )
    assert result["inventory"]["hook"]["guard_command"] == guard_command


def test_collect_installed_runtime_inventory_rejects_duplicate_response_id(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    marketplace_path = project_root / ".agents" / "plugins" / "marketplace.json"
    installed_root = tmp_path / "installed-ticket"
    hooks_dir = installed_root / "hooks"
    plugin_manifest = installed_root / ".codex-plugin" / "plugin.json"
    hook_manifest = hooks_dir / "hooks.json"
    guard_script = hooks_dir / "ticket_engine_guard.py"
    project_root.mkdir(parents=True)
    marketplace_path.parent.mkdir(parents=True)
    marketplace_path.write_text("{}", encoding="utf-8")
    hooks_dir.mkdir(parents=True)
    plugin_manifest.parent.mkdir(parents=True)
    plugin_manifest.write_text('{"name":"ticket"}\n', encoding="utf-8")
    guard_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    guard_command = f"python3 {guard_script}"
    hook_manifest.write_text(
        json.dumps(_hook_manifest_payload(guard_command), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    transcript = _inventory_transcript_rows(
        project_root=project_root,
        hook_manifest=hook_manifest,
        guard_command=guard_command,
    )
    transcript.append(json.loads(json.dumps(transcript[1])))
    monkeypatch.setattr(ticket_runtime_readiness, "_app_server_roundtrip", lambda **_kw: transcript)
    monkeypatch.setattr(ticket_runtime_readiness, "_capture_codex_version", lambda _exe: "codex 1")
    monkeypatch.setattr(ticket_runtime_readiness, "_resolve_codex_executable", lambda _exe: "codex")
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "_resolve_executable_sha256_with_reason",
        lambda _exe: ("0" * 64, None),
    )

    with pytest.raises(
        ticket_runtime_readiness.RuntimeActivationError,
        match="app-server duplicate response id 1",
    ):
        ticket_runtime_readiness.collect_installed_runtime_inventory(
            project_root=project_root,
            marketplace_path=marketplace_path,
            run_dir=run_dir,
            executable="codex",
        )


def test_collect_installed_runtime_inventory_rejects_non_guard_hook_command(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    project_root = tmp_path / "project"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    marketplace_path = project_root / ".agents" / "plugins" / "marketplace.json"
    installed_root = tmp_path / "installed-ticket"
    hooks_dir = installed_root / "hooks"
    plugin_manifest = installed_root / ".codex-plugin" / "plugin.json"
    hook_manifest = hooks_dir / "hooks.json"
    guard_script = hooks_dir / "ticket_engine_guard.py"
    wrong_command = f"python3 {tmp_path / 'wrong' / 'ticket_engine_guard.py'}"
    project_root.mkdir(parents=True)
    marketplace_path.parent.mkdir(parents=True)
    marketplace_path.write_text("{}", encoding="utf-8")
    hooks_dir.mkdir(parents=True)
    plugin_manifest.parent.mkdir(parents=True)
    plugin_manifest.write_text('{"name":"ticket"}\n', encoding="utf-8")
    guard_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    hook_manifest.write_text(
        json.dumps(_hook_manifest_payload(wrong_command), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    transcript = _inventory_transcript_rows(
        project_root=project_root,
        hook_manifest=hook_manifest,
        guard_command=wrong_command,
    )
    monkeypatch.setattr(ticket_runtime_readiness, "_app_server_roundtrip", lambda **_kw: transcript)
    monkeypatch.setattr(ticket_runtime_readiness, "_capture_codex_version", lambda _exe: "codex 1")
    monkeypatch.setattr(ticket_runtime_readiness, "_resolve_codex_executable", lambda _exe: "codex")
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "_resolve_executable_sha256_with_reason",
        lambda _exe: ("0" * 64, None),
    )

    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError, match="Guard command"):
        ticket_runtime_readiness.collect_installed_runtime_inventory(
            project_root=project_root,
            marketplace_path=marketplace_path,
            run_dir=run_dir,
            executable="codex",
        )


def test_guard_command_parser_requires_canonical_script_as_final_token(tmp_path: Path) -> None:
    guard_script = tmp_path / "ticket" / "hooks" / "ticket_engine_guard.py"
    guard_script.parent.mkdir(parents=True)
    guard_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")

    assert ticket_runtime_readiness._command_invokes_script(
        f"uv run python -B {guard_script}",
        expected_script_path=guard_script,
    )
    assert not ticket_runtime_readiness._command_invokes_script(
        f"python3 {guard_script} ; python3 /tmp/other.py",
        expected_script_path=guard_script,
    )


@pytest.mark.parametrize(
    ("plugin_read_result", "missing_response_id", "expected_message"),
    [
        (
            {
                "source": {"path": "/source/ticket"},
                "plugin": {"summary": {}},
            },
            None,
            "plugin/read missing Ticket version",
        ),
        (
            {
                "source": {"path": "/source/ticket"},
                "plugin": {"summary": {"version": "1.4.0"}},
            },
            2,
            "response 2 missing",
        ),
        (
            {
                "source": {"path": "/source/ticket"},
                "plugin": {"summary": {"version": "1.4.0"}},
            },
            3,
            "response 3 missing",
        ),
    ],
)
def test_collect_installed_runtime_inventory_rejects_missing_version_or_required_responses(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    plugin_read_result: dict[str, object],
    missing_response_id: int | None,
    expected_message: str,
) -> None:
    project_root = tmp_path / "project"
    run_dir = project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    marketplace_path = project_root / ".agents" / "plugins" / "marketplace.json"
    installed_root = tmp_path / "installed-ticket"
    hooks_dir = installed_root / "hooks"
    plugin_manifest = installed_root / ".codex-plugin" / "plugin.json"
    hook_manifest = hooks_dir / "hooks.json"
    guard_script = hooks_dir / "ticket_engine_guard.py"
    project_root.mkdir(parents=True)
    marketplace_path.parent.mkdir(parents=True)
    marketplace_path.write_text("{}", encoding="utf-8")
    hooks_dir.mkdir(parents=True)
    plugin_manifest.parent.mkdir(parents=True)
    plugin_manifest.write_text('{"name":"ticket"}\n', encoding="utf-8")
    guard_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    guard_command = f"python3 {guard_script}"
    hook_manifest.write_text(
        json.dumps(_hook_manifest_payload(guard_command), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    transcript = [
        {"direction": "recv", "body": {"id": 0, "result": {"ok": True}}},
        {"direction": "recv", "body": {"id": 1, "result": plugin_read_result}},
        {"direction": "recv", "body": {"id": 2, "result": {"plugins": []}}},
        {"direction": "recv", "body": {"id": 3, "result": {"skills": []}}},
        {
            "direction": "recv",
            "body": {
                "id": 4,
                "result": {
                    "hooks": [
                        {
                            "pluginId": "ticket@turbo-mode",
                            "eventName": "preToolUse",
                            "matcher": "Bash",
                            "command": guard_command,
                            "sourcePath": str(hook_manifest),
                        }
                    ]
                },
            },
        },
    ]
    if missing_response_id is not None:
        transcript = [
            row for row in transcript if row.get("body", {}).get("id") != missing_response_id
        ]

    monkeypatch.setattr(ticket_runtime_readiness, "_app_server_roundtrip", lambda **_kw: transcript)
    monkeypatch.setattr(ticket_runtime_readiness, "_capture_codex_version", lambda _exe: "codex 1")
    monkeypatch.setattr(ticket_runtime_readiness, "_resolve_codex_executable", lambda _exe: "codex")
    monkeypatch.setattr(
        ticket_runtime_readiness,
        "_resolve_executable_sha256_with_reason",
        lambda _exe: ("0" * 64, None),
    )

    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError, match=expected_message):
        ticket_runtime_readiness.collect_installed_runtime_inventory(
            project_root=project_root,
            marketplace_path=marketplace_path,
            run_dir=run_dir,
            executable="codex",
        )


@pytest.mark.parametrize(
    ("result", "expected"),
    [
        ({"source": {"path": "/source/ticket"}}, "/source/ticket"),
        ({"plugin": {"summary": {"source": {"path": "/summary/ticket"}}}}, "/summary/ticket"),
    ],
)
def test_plugin_read_source_path_parses_supported_shapes(
    result: dict[str, object],
    expected: str,
) -> None:
    assert ticket_runtime_readiness._plugin_read_source_path(result) == expected


def test_plugin_read_source_path_rejects_missing_source() -> None:
    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError, match="source path"):
        ticket_runtime_readiness._plugin_read_source_path({"plugin": {"summary": {}}})


@pytest.mark.parametrize(
    "result",
    [
        {
            "hooks": [
                {
                    "pluginId": "ticket@turbo-mode",
                    "eventName": "preToolUse",
                    "matcher": "Bash",
                    "command": "python3 guard.py",
                    "sourcePath": "/hooks/hooks.json",
                }
            ]
        },
        {
            "data": [
                {
                    "hooks": [
                        {
                            "pluginId": "ticket@turbo-mode",
                            "eventName": "preToolUse",
                            "matcher": "Bash",
                            "command": "python3 guard.py",
                            "sourcePath": "/hooks/hooks.json",
                        }
                    ]
                }
            ]
        },
    ],
)
def test_find_ticket_hook_parses_supported_shapes(result: dict[str, object]) -> None:
    hook = ticket_runtime_readiness._find_ticket_hook(result)

    assert hook == {"command": "python3 guard.py", "sourcePath": "/hooks/hooks.json"}


@pytest.mark.parametrize(
    "result",
    [
        {"hooks": []},
        {
            "hooks": [
                {"pluginId": "ticket@turbo-mode"},
                {"pluginId": "ticket@turbo-mode"},
            ]
        },
        {
            "hooks": [
                {
                    "pluginId": "ticket@turbo-mode",
                    "eventName": "postToolUse",
                    "matcher": "Bash",
                    "command": "python3 guard.py",
                    "sourcePath": "/hooks/hooks.json",
                }
            ]
        },
        {
            "hooks": [
                {
                    "pluginId": "ticket@turbo-mode",
                    "eventName": "preToolUse",
                    "matcher": "Bash",
                }
            ]
        },
    ],
)
def test_find_ticket_hook_rejects_invalid_shapes(result: dict[str, object]) -> None:
    with pytest.raises(ticket_runtime_readiness.RuntimeActivationError):
        ticket_runtime_readiness._find_ticket_hook(result)


def _fake_inventory_result(
    tmp_path: Path,
    *,
    run_dir: Path,
    executable_sha256: str | None = None,
) -> dict[str, object]:
    installed_root = tmp_path / "installed-ticket"
    hooks_dir = installed_root / "hooks"
    plugin_manifest = installed_root / ".codex-plugin" / "plugin.json"
    guard_script = hooks_dir / "ticket_engine_guard.py"
    hook_manifest = hooks_dir / "hooks.json"
    hooks_dir.mkdir(parents=True, exist_ok=True)
    plugin_manifest.parent.mkdir(parents=True, exist_ok=True)
    plugin_manifest.write_text('{"name":"ticket","version":"1.4.0"}\n', encoding="utf-8")
    guard_script.write_text("#!/usr/bin/env python3\n", encoding="utf-8")
    guard_command = f"python3 {guard_script}"
    hook_manifest.write_text(
        json.dumps(_hook_manifest_payload(guard_command), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    transcript = raw_dir / "app-server-inventory-transcript.jsonl"
    _write_jsonl(
        transcript,
        _inventory_transcript_rows(
            project_root=tmp_path / "project",
            hook_manifest=hook_manifest,
            guard_command=guard_command,
        ),
    )
    return {
        "runtime_identity": {
            "codex_version": "codex-cli 0.132.0",
            "executable_path": "/usr/local/bin/codex",
            "executable_sha256": executable_sha256,
            "executable_hash_unavailable_reason": None
            if executable_sha256 is not None
            else "not-needed",
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
                "guard_command": guard_command,
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


def _fake_smoke_result(
    tmp_path: Path,
    *,
    project_root: Path,
    run_dir: Path | None = None,
) -> dict[str, object]:
    run_dir = run_dir or project_root / ".codex" / "ticket-runtime-smoke" / "run-1"
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    payload_before = raw_dir / "payload-before.json"
    payload_after = raw_dir / "payload-after.json"
    hook_events = raw_dir / "hook-membrane-events.jsonl"
    engine_stdout = raw_dir / "engine-stdout.json"
    app_server_stderr = raw_dir / "app-server-stderr.txt"
    pre_events = raw_dir / "pre-activation-gated-events.jsonl"
    post_events = raw_dir / "post-activation-gated-events.jsonl"
    hook_manifest = tmp_path / "installed-ticket" / "hooks" / "hooks.json"
    activation_command = (
        "uv run python -B installed/scripts/ticket_engine_activation_smoke.py execute payload.json"
    )
    pre_command = "uv run python -B installed/scripts/ticket_engine_agent.py execute payload.json"
    payload_before.write_text('{"tickets_dir":"docs/tickets"}\n', encoding="utf-8")
    payload_after.write_text(
        '{"tickets_dir":"docs/tickets","hook_injected":true}\n', encoding="utf-8"
    )
    _write_jsonl(
        hook_events,
        [
            _hook_completed_row(hook_manifest),
            _command_item_row(activation_command, {"state": "ok_create"}),
        ],
    )
    engine_stdout.write_text('{"state":"ok_create"}\n', encoding="utf-8")
    app_server_stderr.write_text("", encoding="utf-8")
    _write_jsonl(
        pre_events,
        [
            _command_item_row(
                pre_command,
                {"state": "policy_blocked", "error_code": "runtime_readiness_required"},
            )
        ],
    )
    post_events.write_text('{"method":"turn/completed"}\n', encoding="utf-8")
    return {
        "run_nonce": run_dir.name,
        "hook_membrane_proof": {
            "runner": "app_server_turn",
            "status": "passed",
            "command": activation_command,
            "payload_path": str(run_dir / "payload.json"),
            "nonce": run_dir.name,
            "payload_sha256": ticket_runtime_readiness.sha256_file(payload_before),
            "raw_events_sha256": ticket_runtime_readiness.sha256_file(hook_events),
            "engine_stdout_sha256": ticket_runtime_readiness.sha256_file(engine_stdout),
        },
        "pre_activation_gated_smokes": {
            "status": "passed",
            "required_surfaces": ["direct_execute"],
            "surface_results": {
                "direct_execute": {
                    "runner": "app_server_turn",
                    "command": pre_command,
                    "execute_surface": "direct_execute",
                    "engine_state": "policy_blocked",
                    "error_code": "runtime_readiness_required",
                    "raw_events_sha256": ticket_runtime_readiness.sha256_file(pre_events),
                }
            },
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
            "pre_activation_events": str(pre_events.relative_to(run_dir)),
            "post_activation_events": str(post_events.relative_to(run_dir)),
            "payload_before": str(payload_before.relative_to(run_dir)),
            "payload_after": str(payload_after.relative_to(run_dir)),
            "engine_stdout": str(engine_stdout.relative_to(run_dir)),
            "app_server_stderr": str(app_server_stderr.relative_to(run_dir)),
        },
    }


def _fake_post_activation_smoke_result(
    *,
    run_dir: Path,
    installed_root: Path | None = None,
) -> dict[str, object]:
    raw_dir = run_dir / "raw"
    raw_dir.mkdir(parents=True, exist_ok=True)
    post_events = raw_dir / "post-activation-gated-events.jsonl"
    active_installed_root = installed_root or run_dir / "installed-ticket"
    hook_manifest = active_installed_root / "hooks" / "hooks.json"
    ticket_path = run_dir / "post-direct" / "docs" / "tickets" / "2026-05-20-example.md"
    ticket_path.parent.mkdir(parents=True, exist_ok=True)
    ticket_path.write_text("# T-20260520-01: Runtime activation smoke\n", encoding="utf-8")
    command = "uv run python -B installed/scripts/ticket_engine_agent.py execute payload.json"
    _write_jsonl(
        post_events,
        [
            _hook_completed_row(hook_manifest),
            _command_item_row(
                command,
                {"state": "ok_create", "data": {"ticket_path": str(ticket_path)}},
            ),
        ],
    )
    return {
        "post_activation_gated_smokes": {
            "status": "passed",
            "required_surfaces": ["direct_execute"],
            "surface_results": {
                "direct_execute": {
                    "runner": "app_server_turn",
                    "command": command,
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
    pre_events_path = raw_dir / "pre-activation-gated-events.jsonl"
    post_events_path = raw_dir / "post-activation-gated-events.jsonl"
    payload_before_path = raw_dir / "payload-before.json"
    payload_after_path = raw_dir / "payload-after.json"
    engine_stdout_path = raw_dir / "engine-stdout.json"
    app_server_stderr_path = raw_dir / "app-server-stderr.txt"
    post_ticket_path = run_dir / "post-direct" / "docs" / "tickets" / "2026-05-20-example.md"

    payload_before_path.write_text('{"tickets_dir":"docs/tickets"}\n', encoding="utf-8")
    payload_after_path.write_text(
        '{"tickets_dir":"docs/tickets","hook_injected":true}\n', encoding="utf-8"
    )
    engine_stdout_path.write_text('{"state":"ok_create"}\n', encoding="utf-8")
    app_server_stderr_path.write_text("", encoding="utf-8")
    post_ticket_path.parent.mkdir(parents=True, exist_ok=True)
    post_ticket_path.write_text("# T-20260520-01: Runtime activation smoke\n", encoding="utf-8")

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
    guard_script.write_text("#!/usr/bin/env python3\nprint('guard')\n", encoding="utf-8")
    guard_command = f"python3 {guard_script}"
    hook_manifest.write_text(
        json.dumps(_hook_manifest_payload(guard_command), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    copied_module_path = scripts_dir / "ticket_runtime_readiness.py"
    shutil.copy2(MODULE_SOURCE, copied_module_path)
    module = load_module(copied_module_path)
    activation_command = (
        "uv run python -B installed/scripts/ticket_engine_activation_smoke.py execute payload.json"
    )
    pre_command = "uv run python -B installed/scripts/ticket_engine_agent.py execute payload.json"
    post_command = pre_command
    _write_jsonl(
        inventory_path,
        _inventory_transcript_rows(
            project_root=project_root,
            hook_manifest=hook_manifest,
            guard_command=guard_command,
        ),
    )
    _write_jsonl(
        hook_events_path,
        [
            _hook_completed_row(hook_manifest),
            _command_item_row(activation_command, {"state": "ok_create"}),
        ],
    )
    _write_jsonl(
        pre_events_path,
        [
            _command_item_row(
                pre_command,
                {"state": "policy_blocked", "error_code": "runtime_readiness_required"},
            )
        ],
    )
    _write_jsonl(
        post_events_path,
        [
            _hook_completed_row(hook_manifest),
            _command_item_row(
                post_command,
                {"state": "ok_create", "data": {"ticket_path": str(post_ticket_path)}},
            ),
        ],
    )

    proof = {
        "schema_version": "installed_ticket_runtime_readiness-v1",
        "status": "activated",
        "created_at": "2026-05-20T00:00:00Z",
        "expires_at": "2099-05-21T23:59:59Z",
        "run_nonce": "run-1",
        "project_root": str(project_root),
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
            "executable_sha256": "0" * 64,
            "executable_hash_unavailable_reason": None,
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
                "guard_command": guard_command,
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
        "pre_activation_gated_smokes": {
            "status": "passed",
            "required_surfaces": ["direct_execute"],
            "surface_results": {
                "direct_execute": {
                    "runner": "app_server_turn",
                    "command": pre_command,
                    "execute_surface": "direct_execute",
                    "engine_state": "policy_blocked",
                    "error_code": "runtime_readiness_required",
                    "raw_events_sha256": module.sha256_file(pre_events_path),
                }
            },
        },
        "post_activation_gated_smokes": {
            "status": "passed",
            "required_surfaces": ["direct_execute"],
            "surface_results": {
                "direct_execute": {
                    "runner": "app_server_turn",
                    "command": post_command,
                    "execute_surface": "direct_execute",
                    "runtime_readiness_required": True,
                    "engine_state": "ok_create",
                    "raw_events_sha256": module.sha256_file(post_events_path),
                    "ticket_path": str(post_ticket_path),
                    "ticket_sha256": module.sha256_file(post_ticket_path),
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
            "pre_activation_events": str(pre_events_path.relative_to(run_dir)),
            "post_activation_events": str(post_events_path.relative_to(run_dir)),
            "payload_before": str(payload_before_path.relative_to(run_dir)),
            "payload_after": str(payload_after_path.relative_to(run_dir)),
            "engine_stdout": str(engine_stdout_path.relative_to(run_dir)),
            "app_server_stderr": str(app_server_stderr_path.relative_to(run_dir)),
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

from __future__ import annotations

import json
from pathlib import Path

import pytest
from turbo_mode_handoff_runtime.installed_host_harness import (
    InstalledHostHarnessError,
    run_source_harness_isolation_proof,
    verify_source_harness_payload,
)

PLUGIN_ROOT = Path(__file__).parent.parent
SOURCE_CHECKOUT_ROOT = PLUGIN_ROOT.parents[3]


def test_source_harness_isolation_proof_uses_test_only_copy_outside_source(
    tmp_path: Path,
) -> None:
    codex_home = tmp_path / "isolated-codex-home"
    host_root = tmp_path / "host-root"

    proof = run_source_harness_isolation_proof(
        source_plugin_root=PLUGIN_ROOT,
        codex_home=codex_home,
        host_root=host_root,
    )

    installed_root = Path(proof["installed_plugin_root"])
    facade_path = Path(proof["resolved_facade_path"])
    skill_doc_path = Path(proof["resolved_skill_doc_path"])
    runtime_module_paths = [Path(path) for path in proof["loaded_runtime_module_files"]]
    facade_command_paths = [Path(path) for path in proof["facade_subprocess_command_paths"]]
    serialized = json.dumps(proof, sort_keys=True)

    assert proof["evidence_label"] == "source-harness-isolation-proof"
    assert proof["install_method"] == "test-only-copy"
    assert proof["install_method_equivalence"] == "not-equivalent-to-installed-cache-refresh"
    assert proof["app_server_installed"] is False
    assert proof["installed_host_behavior_matrix_exercised"] is False
    assert proof["source_checkout_root"] == str(SOURCE_CHECKOUT_ROOT.resolve())
    assert installed_root == (
        codex_home.resolve() / "plugins" / "cache" / "turbo-mode" / "handoff" / "1.6.0"
    )
    assert installed_root.exists()
    assert facade_path == installed_root / "scripts" / "session_state.py"
    assert not facade_path.is_relative_to(SOURCE_CHECKOUT_ROOT.resolve())
    assert not skill_doc_path.is_relative_to(SOURCE_CHECKOUT_ROOT.resolve())
    assert runtime_module_paths
    assert all(path.is_relative_to(installed_root) for path in runtime_module_paths)
    assert all(
        path.is_relative_to(installed_root / "turbo_mode_handoff_runtime")
        for path in runtime_module_paths
    )
    assert all(
        not path.is_relative_to(SOURCE_CHECKOUT_ROOT.resolve())
        for path in runtime_module_paths
    )
    assert facade_command_paths == [installed_root / "scripts" / "session_state.py"]
    assert all(path.is_relative_to(installed_root / "scripts") for path in facade_command_paths)
    assert proof["helper_process_cwd"] == str(host_root.resolve())
    assert not Path(proof["helper_process_cwd"]).is_relative_to(SOURCE_CHECKOUT_ROOT.resolve())
    assert proof["helper_process_pythonpath"] is None
    assert proof["source_checkout_sys_path_entries"] == []
    assert "resolved_helper_path" not in proof
    assert "helper_subprocess_command_paths" not in proof
    assert "loaded_handoff_module_files" not in proof
    assert (
        proof["manifest_identity"]["source_sha256"]
        == proof["manifest_identity"]["installed_sha256"]
    )
    assert proof["manifest_identity"]["name"] == "handoff"
    assert proof["manifest_identity"]["version"] == "1.7.0"
    assert "installed-host behavior proof" not in serialized
    assert "installed host matrix certified" not in serialized
    assert "installed cache certified" not in serialized


def test_source_harness_payload_rejects_source_checkout_helper_leakage(
    tmp_path: Path,
) -> None:
    source_root = SOURCE_CHECKOUT_ROOT.resolve()
    source_plugin = PLUGIN_ROOT.resolve()
    payload = {
        "evidence_label": "source-harness-isolation-proof",
        "install_method": "test-only-copy",
        "install_method_equivalence": "not-equivalent-to-installed-cache-refresh",
        "app_server_installed": False,
        "installed_host_behavior_matrix_exercised": False,
        "source_checkout_root": str(source_root),
        "installed_plugin_root": str(tmp_path / "isolated" / "handoff" / "1.6.0"),
        "resolved_facade_path": str(source_plugin / "scripts" / "session_state.py"),
        "resolved_skill_doc_path": str(source_plugin / "skills" / "save" / "SKILL.md"),
        "facade_subprocess_command_paths": [str(source_plugin / "scripts" / "session_state.py")],
        "helper_process_cwd": str(tmp_path / "host-root"),
        "helper_process_pythonpath": None,
        "helper_process_sys_path": [str(tmp_path / "isolated" / "handoff" / "1.6.0")],
        "source_checkout_sys_path_entries": [],
        "loaded_runtime_module_files": [
            str(source_plugin / "turbo_mode_handoff_runtime" / "session_state.py")
        ],
        "manifest_identity": {
            "name": "handoff",
            "version": "1.7.0",
            "source_sha256": "0" * 64,
            "installed_sha256": "0" * 64,
        },
    }

    with pytest.raises(InstalledHostHarnessError, match="source checkout leakage"):
        verify_source_harness_payload(payload)

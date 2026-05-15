from __future__ import annotations

import importlib
import importlib.util
import subprocess
import sys
import types
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
SCRIPT_DIR = PLUGIN_ROOT / "scripts"

DIRECT_ENTRYPOINTS = (
    "active_writes.py",
    "cleanup.py",
    "defer.py",
    "distill.py",
    "installed_host_harness.py",
    "list_handoffs.py",
    "load_transactions.py",
    "project_paths.py",
    "quality_check.py",
    "search.py",
    "session_state.py",
    "storage_authority.py",
    "triage.py",
)


def test_bootstrap_keeps_plugin_scripts_first_under_shadowed_parent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_parent = tmp_path / "shadow_scripts"
    fake_parent.mkdir()
    (fake_parent / "storage_authority.py").write_text(
        "raise AssertionError('wrong storage_authority loaded from shadowed parent')\n",
        encoding="utf-8",
    )
    for module_name in (
        "scripts._bootstrap",
        "scripts.storage_authority",
        "scripts.storage_primitives",
    ):
        monkeypatch.delitem(sys.modules, module_name, raising=False)
    fake_scripts = types.ModuleType("scripts")
    fake_scripts.__path__ = [str(fake_parent), str(SCRIPT_DIR)]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))

    spec = importlib.util.spec_from_file_location(
        "scripts._bootstrap",
        SCRIPT_DIR / "_bootstrap.py",
    )
    assert spec is not None
    assert spec.loader is not None
    bootstrap = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "scripts._bootstrap", bootstrap)
    spec.loader.exec_module(bootstrap)

    bootstrap.ensure_plugin_scripts_package()
    storage_authority = importlib.import_module("scripts.storage_authority")

    scripts_pkg = sys.modules["scripts"]
    assert list(scripts_pkg.__path__)[0] == str(SCRIPT_DIR)  # type: ignore[attr-defined]
    assert str(SCRIPT_DIR) in str(storage_authority.__file__)
    assert str(fake_parent) in list(scripts_pkg.__path__)  # type: ignore[attr-defined]


def test_bootstrap_is_idempotent_under_repeated_import(monkeypatch) -> None:
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))
    import scripts._bootstrap as bootstrap

    bootstrap.ensure_plugin_scripts_package()
    bootstrap.ensure_plugin_scripts_package()

    scripts_pkg = sys.modules["scripts"]
    paths = list(scripts_pkg.__path__)  # type: ignore[attr-defined]
    assert paths.count(str(SCRIPT_DIR)) == 1
    assert paths[0] == str(SCRIPT_DIR)


def test_direct_script_execution_still_works() -> None:
    completed = subprocess.run(
        [
            sys.executable,
            str(SCRIPT_DIR / "session_state.py"),
            "--help",
        ],
        cwd=PLUGIN_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0
    assert "usage:" in completed.stdout


def test_storage_authority_entrypoint_bootstraps_under_shadowed_parent(
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_parent = tmp_path / "parent_scripts"
    fake_parent.mkdir()
    (fake_parent / "_bootstrap.py").write_text(
        "raise AssertionError('wrong _bootstrap loaded from shadowed parent')\n",
        encoding="utf-8",
    )
    (fake_parent / "storage_primitives.py").write_text(
        "def write_json_atomic(*args, **kwargs): raise AssertionError('wrong storage_primitives')\n"
        "def sha256_regular_file_or_none(*args, **kwargs): raise AssertionError('wrong storage_primitives')\n"
        "def read_json_object(*args, **kwargs): raise AssertionError('wrong storage_primitives')\n",
        encoding="utf-8",
    )
    for module_name in (
        "scripts._bootstrap",
        "scripts.storage_authority",
        "scripts.storage_primitives",
    ):
        monkeypatch.delitem(sys.modules, module_name, raising=False)
    fake_scripts = types.ModuleType("scripts")
    fake_scripts.__path__ = [str(fake_parent), str(SCRIPT_DIR)]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))

    storage_authority = importlib.import_module("scripts.storage_authority")

    scripts_pkg = sys.modules["scripts"]
    assert list(scripts_pkg.__path__)[0] == str(SCRIPT_DIR)  # type: ignore[attr-defined]
    assert str(fake_parent) in list(scripts_pkg.__path__)  # type: ignore[attr-defined]
    assert str(SCRIPT_DIR) in str(storage_authority.__file__)
    assert str(SCRIPT_DIR) in str(sys.modules["scripts.storage_primitives"].__file__)
    assert str(SCRIPT_DIR) in str(sys.modules["scripts._bootstrap"].__file__)


@pytest.mark.parametrize("entrypoint", DIRECT_ENTRYPOINTS)
def test_direct_entrypoints_replace_foreign_cached_bootstrap(
    entrypoint: str,
    tmp_path: Path,
    monkeypatch,
) -> None:
    fake_parent = tmp_path / "foreign_scripts"
    fake_parent.mkdir()
    (fake_parent / "storage_primitives.py").write_text(
        "raise AssertionError('wrong storage_primitives loaded from foreign parent')\n",
        encoding="utf-8",
    )
    for module_name in list(sys.modules):
        if module_name == "scripts" or module_name.startswith("scripts."):
            monkeypatch.delitem(sys.modules, module_name, raising=False)
    fake_scripts = types.ModuleType("scripts")
    fake_scripts.__path__ = [str(fake_parent)]  # type: ignore[attr-defined]
    foreign_bootstrap = types.ModuleType("scripts._bootstrap")
    foreign_bootstrap.__file__ = str(fake_parent / "_bootstrap.py")
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    monkeypatch.setitem(sys.modules, "scripts._bootstrap", foreign_bootstrap)
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))

    module_name = f"_handoff_bootstrap_test_{entrypoint.removesuffix('.py')}"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_DIR / entrypoint)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)

    scripts_pkg = sys.modules["scripts"]
    assert list(scripts_pkg.__path__)[0] == str(SCRIPT_DIR)  # type: ignore[attr-defined]
    assert str(SCRIPT_DIR) in str(sys.modules["scripts._bootstrap"].__file__)

from __future__ import annotations

import ast
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PACKAGE = "turbo_mode_handoff_runtime"
RUNTIME_DIR = PLUGIN_ROOT / RUNTIME_PACKAGE
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"

RUNTIME_MODULES = {
    "active_writes.py",
    "cleanup.py",
    "defer.py",
    "distill.py",
    "handoff_parsing.py",
    "installed_host_harness.py",
    "list_handoffs.py",
    "load_transactions.py",
    "plugin_siblings.py",
    "project_paths.py",
    "provenance.py",
    "quality_check.py",
    "search.py",
    "session_state.py",
    "storage_authority.py",
    "storage_authority_inventory.py",
    "storage_primitives.py",
    "ticket_parsing.py",
    "triage.py",
}


def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_runtime_module_inventory_is_explicit() -> None:
    assert {p.name for p in RUNTIME_DIR.glob("*.py") if p.name != "__init__.py"} == RUNTIME_MODULES


def test_runtime_modules_do_not_import_scripts_namespace() -> None:
    for path in RUNTIME_DIR.glob("*.py"):
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("scripts"), path
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("scripts"), path
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not node.value.startswith("turbo_mode_handoff_runtime."), path


def test_runtime_modules_are_import_only() -> None:
    for path in RUNTIME_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not text.startswith("#!"), path
        assert 'if __name__ == "__main__"' not in text, path

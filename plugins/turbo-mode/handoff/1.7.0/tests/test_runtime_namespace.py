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
    "chain_state.py",
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
    "storage_inspection.py",
    "storage_layout.py",
    "storage_primitives.py",
    "ticket_parsing.py",
    "triage.py",
}

CLI_FACADES = {
    "defer.py",
    "distill.py",
    "list_handoffs.py",
    "load_transactions.py",
    "plugin_siblings.py",
    "search.py",
    "session_state.py",
    "triage.py",
}

STRING_RETURNING_FACADES = {
    "distill.py",
    "list_handoffs.py",
    "search.py",
}

INTEGER_RETURNING_FACADES = CLI_FACADES - STRING_RETURNING_FACADES


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


def test_scripts_directory_contains_only_cli_facades() -> None:
    assert {p.name for p in SCRIPTS_DIR.glob("*.py")} == CLI_FACADES


def test_cli_facades_use_the_approved_template() -> None:
    for path in SCRIPTS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        module = path.stem
        assert text.startswith("#!/usr/bin/env python3\n"), path
        assert "PLUGIN_ROOT = Path(__file__).resolve().parents[1]" in text, path
        assert "sys.path.insert(0, str(PLUGIN_ROOT))" in text, path
        assert f"from {RUNTIME_PACKAGE}.{module} import main" in text, path
        assert 'if __name__ == "__main__":' in text, path
        if path.name in STRING_RETURNING_FACADES:
            assert "print(main())" in text, path
            assert "raise SystemExit(0)" in text, path
            assert "raise SystemExit(main())" not in text, path
        else:
            assert path.name in INTEGER_RETURNING_FACADES
            assert "raise SystemExit(main())" in text, path
            assert "print(main())" not in text, path
        assert "_bootstrap" not in text, path
        assert "globals().update" not in text, path


STDLIB_ONLY_BASE_LAYER = {
    "storage_primitives.py",
    "storage_layout.py",
    "storage_inspection.py",
}


def test_storage_base_layer_has_no_internal_imports() -> None:
    """Enforces the ARCHITECTURE.md / ADR-0002 layering invariant: the
    stdlib-only base layer must not import any turbo_mode_handoff_runtime
    module, by absolute OR relative import. An internal import here
    re-creates the cycle the reseam removed."""
    for name in STDLIB_ONLY_BASE_LAYER:
        tree = _parse(RUNTIME_DIR / name)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                module = node.module or ""
                assert node.level == 0, f"{name}: relative intra-package import"
                assert module != RUNTIME_PACKAGE, name
                assert not module.startswith(f"{RUNTIME_PACKAGE}."), name
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert alias.name != RUNTIME_PACKAGE, name
                    assert not alias.name.startswith(f"{RUNTIME_PACKAGE}."), name

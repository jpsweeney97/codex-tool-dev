from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

REFRESH_PARENT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REFRESH_PARENT))
TOOLS_ROOT = Path(__file__).resolve().parents[3]
SCRATCH_PYCACHE = Path("/private/tmp/codex-tool-dev-pycache")


def _clear_python_cache_residue() -> None:
    for cache_dir in TOOLS_ROOT.rglob("__pycache__"):
        shutil.rmtree(cache_dir)
    for pyc_file in TOOLS_ROOT.rglob("*.pyc"):
        pyc_file.unlink()


@pytest.fixture(autouse=True)
def prevent_refresh_test_bytecode(monkeypatch: pytest.MonkeyPatch):
    sys.dont_write_bytecode = True
    monkeypatch.setenv("PYTHONDONTWRITEBYTECODE", "1")
    monkeypatch.setenv(
        "PYTHONPYCACHEPREFIX",
        os.environ.get("PYTHONPYCACHEPREFIX", str(SCRATCH_PYCACHE)),
    )
    _clear_python_cache_residue()
    yield
    _clear_python_cache_residue()

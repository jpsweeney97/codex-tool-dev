from __future__ import annotations

import re
from pathlib import Path

PLUGIN_ROOT = Path(__file__).parent.parent
TOPOLOGY_DOCS = [
    PLUGIN_ROOT / "README.md",
    PLUGIN_ROOT / "CONTRIBUTING.md",
    PLUGIN_ROOT / "references" / "ARCHITECTURE.md",
]
STALE_TOPOLOGY_PATTERNS = [
    r"`storage_authority\.py`[^.\n]*(owns|handles)[^.\n]*storage layout",
    r"chain-state[^.\n]*(from|in) `storage_authority\.py`",
    r"`storage_authority\.py`[^.\n]*(owns|handles)[^.\n]*chain-state",
]
REQUIRED_TOPOLOGY_CLAIMS = {
    "`storage_primitives.py`": "filesystem primitives, locking protocol, and atomic write helpers",
    "`storage_layout.py`": "storage paths",
    "`storage_inspection.py`": "filesystem and git inspection",
    "`storage_authority.py`": "handoff discovery and selection",
    "`chain_state.py`": "chain-state inventory, diagnostics, read, and lifecycle",
}


def test_topology_docs_do_not_claim_old_storage_authority_ownership() -> None:
    for path in TOPOLOGY_DOCS:
        text = path.read_text(encoding="utf-8")
        for stale_pattern in STALE_TOPOLOGY_PATTERNS:
            assert re.search(stale_pattern, text) is None, path


def test_topology_docs_state_current_runtime_module_owners() -> None:
    for path in TOPOLOGY_DOCS:
        text = path.read_text(encoding="utf-8")
        for module_name, ownership in REQUIRED_TOPOLOGY_CLAIMS.items():
            assert module_name in text, path
            assert ownership in text, path

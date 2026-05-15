from __future__ import annotations

from pathlib import Path

from turbo_mode_handoff_runtime.storage_authority_inventory import build_inventory, check_inventory

PLUGIN_ROOT = Path(__file__).parent.parent
REPO_ROOT = PLUGIN_ROOT.parents[3]
FIXTURE = PLUGIN_ROOT / "tests" / "fixtures" / "storage_authority_inventory.json"


def test_storage_authority_inventory_covers_current_surfaces() -> None:
    inventory = build_inventory(repo_root=REPO_ROOT, plugin_root=PLUGIN_ROOT)

    assert inventory["schema_version"] == "handoff-storage-authority-inventory-v1"
    assert inventory["primary_storage_root"] == "<project_root>/.codex/handoffs/"
    assert inventory["legacy_storage_root"] == "<project_root>/docs/handoffs/"
    assert {row["status"] for row in inventory["rows"]} == {"passed"}

    row_paths = {row["path"] for row in inventory["rows"]}
    assert "README.md" in row_paths
    assert "references/handoff-contract.md" in row_paths
    assert "references/format-reference.md" in row_paths
    assert "scripts/quality_check.py" in row_paths
    assert "plugins/turbo-mode/tools/refresh/smoke.py" in row_paths


def test_storage_authority_inventory_fixture_matches_current_inventory() -> None:
    current = build_inventory(repo_root=REPO_ROOT, plugin_root=PLUGIN_ROOT)
    check_inventory(current, FIXTURE)

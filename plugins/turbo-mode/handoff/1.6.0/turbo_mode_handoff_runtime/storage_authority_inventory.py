"""Generate and check current-facing Handoff storage authority text."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import dataclass
from pathlib import Path

SCHEMA_VERSION = "handoff-storage-authority-inventory-v1"
PRIMARY_STORAGE_ROOT = "<project_root>/.codex/handoffs/"
LEGACY_STORAGE_ROOT = "<project_root>/docs/handoffs/"


@dataclass(frozen=True)
class InventorySpec:
    path: str
    root: str
    required: tuple[str, ...]
    forbidden: tuple[str, ...]


PLUGIN_SPECS = (
    InventorySpec(
        path="README.md",
        root="plugin",
        required=(PRIMARY_STORAGE_ROOT, "handoff-<project>-<resume_token>.json"),
        forbidden=(LEGACY_STORAGE_ROOT, "local-only working memory"),
    ),
    InventorySpec(
        path="CHANGELOG.md",
        root="plugin",
        required=(
            f"Handoff storage moved from `{LEGACY_STORAGE_ROOT}` to `{PRIMARY_STORAGE_ROOT}`",
        ),
        forbidden=(
            f"Handoff storage moved from `{PRIMARY_STORAGE_ROOT}` to `{LEGACY_STORAGE_ROOT}`",
            "local-only working memory",
        ),
    ),
    InventorySpec(
        path="references/handoff-contract.md",
        root="plugin",
        required=(PRIMARY_STORAGE_ROOT, "handoff-<project>-<resume_token>.json"),
        forbidden=(LEGACY_STORAGE_ROOT, "local-only working memory"),
    ),
    InventorySpec(
        path="references/format-reference.md",
        root="plugin",
        required=(PRIMARY_STORAGE_ROOT,),
        forbidden=(LEGACY_STORAGE_ROOT, "local-only working memory"),
    ),
    InventorySpec(
        path="scripts/quality_check.py",
        root="plugin",
        required=("<project_root>/.codex/handoffs/",),
        forbidden=("<project_root>/docs/handoffs/",),
    ),
)

REPO_SPECS = (
    InventorySpec(
        path="plugins/turbo-mode/tools/refresh/smoke.py",
        root="repo",
        required=(".codex/handoffs/archive", ".codex/handoffs/.session-state"),
        forbidden=("docs/handoffs/archive", "docs/handoffs/.session-state"),
    ),
)


def default_repo_root() -> Path:
    """Return the repository root for this source checkout."""
    return Path(__file__).resolve().parents[5]


def default_plugin_root() -> Path:
    """Return the Handoff plugin root for this source checkout."""
    return Path(__file__).resolve().parents[1]


def default_fixture_path(plugin_root: Path) -> Path:
    """Return the generated inventory fixture path."""
    return plugin_root / "tests" / "fixtures" / "storage_authority_inventory.json"


def build_inventory(
    *,
    repo_root: Path | None = None,
    plugin_root: Path | None = None,
) -> dict[str, object]:
    """Build the current storage-authority inventory."""
    resolved_repo_root = (repo_root or default_repo_root()).resolve()
    resolved_plugin_root = (plugin_root or default_plugin_root()).resolve()
    rows = [
        *_rows_for_specs(PLUGIN_SPECS, root=resolved_plugin_root),
        *_rows_for_specs(REPO_SPECS, root=resolved_repo_root),
    ]
    overall_status = "passed" if all(row["status"] == "passed" for row in rows) else "failed"
    return {
        "schema_version": SCHEMA_VERSION,
        "primary_storage_root": PRIMARY_STORAGE_ROOT,
        "legacy_storage_root": LEGACY_STORAGE_ROOT,
        "overall_status": overall_status,
        "rows": rows,
    }


def _rows_for_specs(specs: tuple[InventorySpec, ...], *, root: Path) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    for spec in specs:
        path = root / spec.path
        if not path.exists():
            rows.append(
                {
                    "path": spec.path,
                    "root": spec.root,
                    "status": "failed",
                    "error": "missing",
                    "required": list(spec.required),
                    "forbidden": list(spec.forbidden),
                    "required_missing": list(spec.required),
                    "forbidden_present": [],
                    "sha256": None,
                }
            )
            continue
        text = path.read_text(encoding="utf-8")
        required_missing = [item for item in spec.required if item not in text]
        forbidden_present = [item for item in spec.forbidden if item in text]
        rows.append(
            {
                "path": spec.path,
                "root": spec.root,
                "status": "passed" if not required_missing and not forbidden_present else "failed",
                "required": list(spec.required),
                "forbidden": list(spec.forbidden),
                "required_missing": required_missing,
                "forbidden_present": forbidden_present,
                "sha256": hashlib.sha256(text.encode("utf-8")).hexdigest(),
            }
        )
    return rows


def render_inventory(inventory: dict[str, object]) -> str:
    """Render inventory JSON in a stable form."""
    return json.dumps(inventory, indent=2, sort_keys=True) + "\n"


def check_inventory(current: dict[str, object], fixture_path: Path) -> None:
    """Fail when current inventory is invalid or the fixture has drifted."""
    if current["overall_status"] != "passed":
        failed = [row for row in current["rows"] if row["status"] != "passed"]
        raise ValueError(f"storage_authority_inventory check failed: stale rows. Got: {failed!r}")
    if not fixture_path.exists():
        raise ValueError(
            f"storage_authority_inventory check failed: fixture missing. Got: {str(fixture_path)!r}"
        )
    fixture = fixture_path.read_text(encoding="utf-8")
    rendered = render_inventory(current)
    if fixture != rendered:
        raise ValueError(
            f"storage_authority_inventory check failed: fixture drift. Got: {str(fixture_path)!r}"
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    args = parser.parse_args()

    plugin_root = default_plugin_root()
    fixture_path = default_fixture_path(plugin_root)
    current = build_inventory(repo_root=default_repo_root(), plugin_root=plugin_root)
    try:
        if args.write:
            fixture_path.parent.mkdir(parents=True, exist_ok=True)
            fixture_path.write_text(render_inventory(current), encoding="utf-8")
        check_inventory(current, fixture_path)
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 1
    return 0

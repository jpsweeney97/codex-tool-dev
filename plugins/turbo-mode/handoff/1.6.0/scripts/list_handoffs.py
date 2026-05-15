#!/usr/bin/env python3
"""List active handoff candidates through the shared storage authority."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

def _load_bootstrap_by_path() -> None:
    import importlib.util

    bootstrap_path = Path(__file__).resolve().parent / "_bootstrap.py"
    cached = sys.modules.get("scripts._bootstrap")
    if cached is not None:
        cached_file = getattr(cached, "__file__", None)
        try:
            cached_path = Path(cached_file).resolve() if cached_file is not None else None
        except (OSError, TypeError):
            cached_path = None
        if cached_path == bootstrap_path:
            ensure = getattr(cached, "ensure_plugin_scripts_package", None)
            if callable(ensure):
                ensure()
                return
        sys.modules.pop("scripts._bootstrap", None)
    spec = importlib.util.spec_from_file_location("scripts._bootstrap", bootstrap_path)
    if spec is None or spec.loader is None:
        raise ImportError(
            "handoff bootstrap failed: missing or unloadable _bootstrap.py. "
            f"Got: {str(bootstrap_path)!r:.100}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["scripts._bootstrap"] = module
    spec.loader.exec_module(module)


_load_bootstrap_by_path()
del _load_bootstrap_by_path

from scripts.handoff_parsing import parse_handoff
from scripts.project_paths import get_project_root
from scripts.storage_authority import discover_handoff_inventory, eligible_active_candidates


def list_handoffs(project_root: Path) -> list[dict[str, Any]]:
    """Return active handoff candidates in implicit selection order."""
    inventory = discover_handoff_inventory(project_root, scan_mode="active-selection")
    output: list[dict[str, Any]] = []
    for candidate in eligible_active_candidates(inventory):
        handoff = parse_handoff(candidate.path)
        output.append({
            "path": str(candidate.path),
            "title": handoff.frontmatter.get("title", candidate.path.stem),
            "date": handoff.frontmatter.get("date", ""),
            "type": handoff.frontmatter.get("type", "handoff"),
            "branch": handoff.frontmatter.get("branch", ""),
            "storage_location": candidate.storage_location,
            "artifact_class": candidate.artifact_class,
            "source_git_visibility": candidate.source_git_visibility,
            "source_fs_status": candidate.source_fs_status,
            "document_profile": candidate.document_profile,
            "content_sha256": candidate.content_sha256,
        })
    return output


def main(argv: list[str] | None = None) -> str:
    parser = argparse.ArgumentParser(description="List active handoffs")
    parser.add_argument("--project-root", type=Path, default=None)
    args = parser.parse_args(argv)

    project_root = args.project_root.resolve() if args.project_root else get_project_root()[0]
    handoffs = list_handoffs(project_root)
    return json.dumps({"total": len(handoffs), "handoffs": handoffs}, indent=2)


if __name__ == "__main__":
    print(main())

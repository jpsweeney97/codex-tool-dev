from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def find_sibling_plugin_root(current_plugin_root: Path, sibling_name: str) -> Path:
    candidates = []
    stable_sibling = current_plugin_root.parent / sibling_name
    if _is_plugin_root(stable_sibling):
        candidates.append(stable_sibling)

    versioned_sibling_base = current_plugin_root.parent.parent / sibling_name
    if versioned_sibling_base != stable_sibling and versioned_sibling_base.is_dir():
        candidates.extend(
            candidate
            for candidate in sorted(versioned_sibling_base.iterdir())
            if _is_plugin_root(candidate)
        )

    if len(candidates) != 1:
        searched = f"{stable_sibling} or {versioned_sibling_base}"
        raise RuntimeError(
            f"Expected exactly one installed {sibling_name} version or stable root under "
            f"{searched}, got {len(candidates)}"
        )
    return candidates[0]


def _is_plugin_root(path: Path) -> bool:
    return (
        path.is_dir()
        and (path / ".codex-plugin" / "plugin.json").exists()
    )


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--plugin-root", required=True)
    parser.add_argument("--sibling", required=True)
    parser.add_argument("--field", choices=("plugin_root",), default=None)
    args = parser.parse_args(argv)

    root = find_sibling_plugin_root(Path(args.plugin_root).resolve(), args.sibling)
    payload = {"plugin_root": str(root)}
    if args.field == "plugin_root":
        print(payload["plugin_root"])
        return 0
    json.dump(payload, sys.stdout)
    return 0

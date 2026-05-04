from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def find_sibling_plugin_root(current_plugin_root: Path, sibling_name: str) -> Path:
    marketplace_root = current_plugin_root.parent.parent
    sibling_base = marketplace_root / sibling_name
    versions = sorted(
        candidate
        for candidate in sibling_base.iterdir()
        if candidate.is_dir() and (candidate / ".codex-plugin" / "plugin.json").exists()
    )
    if len(versions) != 1:
        raise RuntimeError(
            f"Expected exactly one installed {sibling_name} version under {sibling_base}, got {len(versions)}"
        )
    return versions[0]


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


if __name__ == "__main__":
    raise SystemExit(main())

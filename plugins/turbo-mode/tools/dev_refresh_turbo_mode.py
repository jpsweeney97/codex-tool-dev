#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True

CURRENT_FILE = Path(__file__).resolve()
TOOLS_ROOT = CURRENT_FILE.parent
sys.path.insert(0, str(TOOLS_ROOT))

from refresh.app_server_inventory import (  # noqa: E402
    app_server_roundtrip,
    authority_digest,
    collect_readonly_runtime_inventory,
    rewrite_ticket_hook_manifest,
    write_json_artifact,
)
from refresh.manifests import build_manifest, diff_manifests  # noqa: E402
from refresh.models import DiffEntry, PluginSpec, RefreshError, fail  # noqa: E402
from refresh.planner import RefreshPaths, build_paths  # noqa: E402

Roundtrip = Callable[..., list[dict[str, object]]]
InventoryCollector = Callable[
    [RefreshPaths],
    tuple[object, tuple[dict[str, object], ...]],
]


def load_marketplace_plugin_names(marketplace_path: Path) -> tuple[str, ...]:
    return tuple(spec.name for spec in load_marketplace_plugin_specs(marketplace_path, None, None))


def load_marketplace_plugin_specs(
    marketplace_path: Path,
    repo_root: Path | None,
    codex_home: Path | None,
) -> tuple[PluginSpec, ...]:
    payload = _read_marketplace(marketplace_path)
    marketplace_name = payload.get("name")
    if marketplace_name != "turbo-mode":
        fail("read dev marketplace", "marketplace name must be turbo-mode", marketplace_name)
    plugins = payload.get("plugins")
    if not isinstance(plugins, list) or not plugins:
        fail("read dev marketplace", "plugins must be a non-empty list", plugins)
    specs: list[PluginSpec] = []
    for record in plugins:
        if not isinstance(record, dict):
            fail("read dev marketplace", "plugin record must be an object", record)
        name = record.get("name")
        if not isinstance(name, str) or not name:
            fail("read dev marketplace", "plugin name must be a non-empty string", name)
        source = record.get("source")
        if not isinstance(source, dict):
            fail("read dev marketplace", "plugin source must be an object", record)
        if source.get("source") != "local":
            fail("read dev marketplace", "plugin source must be local", source)
        source_path = source.get("path")
        if not isinstance(source_path, str) or not source_path.startswith("./"):
            fail("read dev marketplace", "plugin source path must be ./ relative", source_path)
        version = Path(source_path).name
        if repo_root is None or codex_home is None:
            source_root = Path(source_path)
            cache_root = Path("plugins/cache") / marketplace_name / name / version
        else:
            source_root = (repo_root / source_path).resolve(strict=False)
            cache_root = codex_home / "plugins/cache" / marketplace_name / name / version
        specs.append(
            PluginSpec(
                name=name,
                version=version,
                source_root=source_root,
                cache_root=cache_root,
            )
        )
    return tuple(specs)


def build_dev_install_requests(
    *,
    marketplace_path: Path,
    plugin_names: tuple[str, ...],
) -> list[dict[str, object]]:
    if not plugin_names:
        fail("build dev install requests", "plugin names must be non-empty", plugin_names)
    requests: list[dict[str, object]] = [
        {
            "id": 0,
            "method": "initialize",
            "params": {
                "clientInfo": {"name": "turbo-mode-dev-refresh", "version": "0"},
                "capabilities": {"experimentalApi": True},
            },
        },
        {"method": "initialized"},
    ]
    for request_id, plugin_name in enumerate(plugin_names, start=1):
        requests.append(
            {
                "id": request_id,
                "method": "plugin/install",
                "params": {
                    "marketplacePath": str(marketplace_path),
                    "pluginName": plugin_name,
                    "remoteMarketplaceName": None,
                },
            }
        )
    return requests


def run_dev_refresh(
    *,
    repo_root: Path,
    codex_home: Path,
    run_id: str | None = None,
    verify: bool = True,
    roundtrip: Roundtrip | None = None,
    inventory_collector: InventoryCollector | None = None,
) -> dict[str, Any]:
    paths = build_paths(repo_root=repo_root, codex_home=codex_home)
    plugin_specs = load_marketplace_plugin_specs(
        paths.marketplace_path,
        paths.repo_root,
        paths.codex_home,
    )
    plugin_names = tuple(spec.name for spec in plugin_specs)
    active_run_id = run_id or _default_run_id()
    requests = build_dev_install_requests(
        marketplace_path=paths.marketplace_path,
        plugin_names=plugin_names,
    )
    active_roundtrip = roundtrip or app_server_roundtrip
    with tempfile.TemporaryDirectory(prefix="turbo-mode-dev-refresh-") as scratch_dir:
        transcript = tuple(
            active_roundtrip(
                requests,
                env_overrides={"CODEX_HOME": str(paths.codex_home)},
                cwd=Path(scratch_dir),
            )
        )
    _validate_dev_install_transcript(
        transcript=transcript,
        plugin_names=plugin_names,
        codex_home=paths.codex_home,
    )
    _repair_installed_plugin_metadata(codex_home=paths.codex_home, plugin_specs=plugin_specs)
    diffs = _verify_source_cache_equality(plugin_specs)
    runtime_inventory_state = "not-requested"
    runtime_inventory_summary: dict[str, Any] | None = None
    runtime_inventory_transcript_sha256: str | None = None
    if verify:
        collector = inventory_collector or collect_readonly_runtime_inventory
        inventory, inventory_transcript = collector(paths)
        runtime_inventory_state = str(getattr(inventory, "state", "unknown"))
        runtime_inventory_transcript_sha256 = authority_digest(inventory_transcript)
        runtime_inventory_summary = {
            "plugin_read_sources": dict(getattr(inventory, "plugin_read_sources", {})),
            "skills": list(getattr(inventory, "skills", ())),
            "ticket_hook": dict(getattr(inventory, "ticket_hook", {})),
            "handoff_hooks": list(getattr(inventory, "handoff_hooks", ())),
            "transcript_sha256": getattr(inventory, "transcript_sha256", None),
        }
        if runtime_inventory_state != "aligned":
            fail(
                "verify runtime inventory",
                "runtime inventory is not aligned",
                runtime_inventory_state,
            )
    summary_path = paths.local_only_root / active_run_id / "dev-refresh.summary.json"
    summary: dict[str, Any] = {
        "schema_version": "turbo-mode-dev-refresh-v1",
        "lane": "dev-refresh",
        "run_id": active_run_id,
        "repo_root": str(paths.repo_root),
        "codex_home": str(paths.codex_home),
        "marketplace_path": str(paths.marketplace_path),
        "plugins": list(plugin_names),
        "guarded_refresh_used": False,
        "process_gate_used": False,
        "install_request_methods": [str(request.get("method")) for request in requests],
        "install_transcript_sha256": authority_digest(transcript),
        "source_cache_diff_count": len(diffs),
        "source_cache_diffs": [diff.canonical_path for diff in diffs],
        "runtime_inventory_state": runtime_inventory_state,
        "runtime_inventory": runtime_inventory_summary,
        "runtime_inventory_transcript_sha256": runtime_inventory_transcript_sha256,
        "summary_path": str(summary_path),
    }
    write_json_artifact(summary_path, summary)
    return summary


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Fast local-dev refresh of the repo-local turbo-mode marketplace cache."
    )
    parser.add_argument("--repo-root", type=Path, default=Path.cwd())
    parser.add_argument("--codex-home", type=Path, default=Path.home() / ".codex")
    parser.add_argument("--run-id")
    parser.add_argument("--verify", dest="verify", action="store_true", default=True)
    parser.add_argument("--skip-verify", dest="verify", action="store_false")
    parser.add_argument("--json", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        summary = run_dev_refresh(
            repo_root=args.repo_root,
            codex_home=args.codex_home,
            run_id=args.run_id,
            verify=args.verify,
        )
    except (RefreshError, OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 1
    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        print(f"dev refresh summary: {summary['summary_path']}")
    return 0


def _read_marketplace(marketplace_path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(marketplace_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        fail("read dev marketplace", str(exc), str(marketplace_path))
    if not isinstance(payload, dict):
        fail("read dev marketplace", "marketplace payload must be an object", payload)
    return payload


def _validate_dev_install_transcript(
    *,
    transcript: tuple[dict[str, object], ...],
    plugin_names: tuple[str, ...],
    codex_home: Path,
) -> None:
    responses: dict[int, dict[str, object]] = {}
    for item in transcript:
        if item.get("direction") != "recv":
            continue
        body = item.get("body")
        if not isinstance(body, dict):
            fail("validate dev install", "app-server response is not an object", body)
        response_id = body.get("id")
        if response_id is None:
            if isinstance(body.get("method"), str):
                continue
            fail("validate dev install", "app-server response missing id", body)
        if not isinstance(response_id, int):
            fail("validate dev install", "app-server response id is not an integer", response_id)
        if response_id in responses:
            fail("validate dev install", "duplicate app-server response id", response_id)
        if "error" in body:
            fail("validate dev install", "app-server response returned error", body)
        responses[response_id] = body
    expected_ids = set(range(0, len(plugin_names) + 1))
    missing = sorted(expected_ids - set(responses))
    if missing:
        fail("validate dev install", "missing app-server responses", missing)
    initialize_result = responses[0].get("result")
    if isinstance(initialize_result, dict):
        observed_home = initialize_result.get("codexHome")
        if observed_home is not None and observed_home != str(codex_home):
            fail("validate dev install", "requested Codex home binding mismatch", observed_home)
    for request_id, plugin_name in enumerate(plugin_names, start=1):
        result = responses[request_id].get("result")
        if not isinstance(result, dict):
            fail("validate dev install", "install response result missing", plugin_name)
        auth_policy = result.get("authPolicy")
        if not isinstance(auth_policy, str):
            fail("validate dev install", "install response authPolicy is not a string", result)
        apps_needing_auth = result.get("appsNeedingAuth", [])
        if not isinstance(apps_needing_auth, list):
            fail("validate dev install", "install response appsNeedingAuth is not a list", result)


def _repair_installed_plugin_metadata(
    *,
    codex_home: Path,
    plugin_specs: tuple[PluginSpec, ...],
) -> None:
    if "ticket" not in {spec.name for spec in plugin_specs}:
        return
    ticket_spec = next(spec for spec in plugin_specs if spec.name == "ticket")
    ticket_root = codex_home / "plugins/cache/turbo-mode/ticket" / ticket_spec.version
    hooks_path = ticket_root / "hooks/hooks.json"
    if hooks_path.exists():
        rewrite_ticket_hook_manifest(ticket_plugin_root=ticket_root)


def _verify_source_cache_equality(plugin_specs: tuple[PluginSpec, ...]) -> tuple[DiffEntry, ...]:
    diffs: list[DiffEntry] = []
    for spec in plugin_specs:
        if not spec.source_root.exists():
            fail("verify dev refresh", "missing source root", str(spec.source_root))
        if not spec.cache_root.exists():
            fail("verify dev refresh", "missing cache root", str(spec.cache_root))
        source_manifest = build_manifest(spec, root_kind="source")
        cache_manifest = build_manifest(spec, root_kind="cache")
        diffs.extend(diff_manifests(source_manifest, cache_manifest))
    if diffs:
        fail(
            "verify dev refresh",
            "source/cache drift remains after dev refresh",
            [diff.canonical_path for diff in diffs[:10]],
        )
    return tuple(diffs)


def _default_run_id() -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    return f"dev-refresh-{stamp}-{uuid.uuid4().hex[:8]}"


if __name__ == "__main__":
    raise SystemExit(main())

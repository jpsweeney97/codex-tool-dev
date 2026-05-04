from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
import tempfile
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath
from typing import Any

REPO_ROOT = Path("/Users/jp/Projects/active/codex-tool-dev")
PLAN_PATH = Path(
    "/Users/jp/.codex/docs/plans/2026-05-04-turbo-mode-plugin-source-authority-migration-plan.md"
)
CONFIG_PATH = Path("/Users/jp/.codex/config.toml")
MARKETPLACE_PATH = REPO_ROOT / ".agents/plugins/marketplace.json"
SOURCE_ROOTS = [
    REPO_ROOT / "plugins/turbo-mode/handoff/1.6.0",
    REPO_ROOT / "plugins/turbo-mode/ticket/1.4.0",
]
CACHE_ROOTS = [
    Path("/Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0"),
    Path("/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0"),
]
MIGRATION_BASE_HEAD = "f72236b8402cafdcc056ef1b3b4a891a98363873"
MIGRATION_BASE_REF = "main"
MIGRATION_BASE_KIND = "local-clean-main"
EVIDENCE_ROOT = REPO_ROOT / "plugins/turbo-mode/evidence/2026-05-04-source-migration"
LOCAL_ONLY_ROOT = Path("/Users/jp/.codex/local-only/turbo-mode-source-migration")

GENERATED_DIRS = {"__pycache__", ".pytest_cache", ".ruff_cache", ".mypy_cache", ".venv"}
GENERATED_FILES = {".DS_Store"}


class MigrationError(RuntimeError):
    """Raised when a migration validation gate fails."""


def fail(operation: str, reason: str, got: object) -> None:
    raise MigrationError(f"{operation} failed: {reason}. Got: {got!r:.100}")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def read_json_bytes(data: bytes, *, source: str) -> dict[str, Any]:
    try:
        value = json.loads(data.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        fail("parse json", str(exc), source)
    if not isinstance(value, dict):
        fail("parse json", "top-level value is not an object", source)
    return value


def write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run(cmd: Sequence[str], *, cwd: Path = REPO_ROOT, input_text: str | None = None) -> str:
    completed = subprocess.run(
        cmd,
        cwd=cwd,
        input=input_text,
        text=True,
        capture_output=True,
        check=False,
    )
    if completed.returncode != 0:
        fail("run command", completed.stderr.strip() or completed.stdout.strip(), " ".join(cmd))
    return completed.stdout


def repo_head(repo_root: Path = REPO_ROOT) -> str:
    return run(["git", "rev-parse", "--verify", "HEAD"], cwd=repo_root).strip()


def git_blob_sha256(repo_root: Path, rev: str, path: str) -> str:
    data = subprocess.run(
        ["git", "show", f"{rev}:{path}"],
        cwd=repo_root,
        capture_output=True,
        check=False,
    )
    if data.returncode != 0:
        fail("read git blob", data.stderr.decode("utf-8", errors="replace").strip(), path)
    return sha256_bytes(data.stdout)


def worktree_tool_sha256(repo_root: Path, tool_path: str) -> str:
    return sha256_file(repo_root / tool_path)


def committed_tool_sha256(repo_root: Path, tool_path: str) -> str:
    return git_blob_sha256(repo_root, "HEAD", tool_path)


def plan_sha256(plan_path: Path = PLAN_PATH) -> str:
    return sha256_file(plan_path)


def normalize_paths(paths: Iterable[Path]) -> list[str]:
    return [str(path) for path in paths]


def base_run_metadata(
    *,
    run_id: str,
    mode: str,
    tool_path: str,
    tool_sha256: str | None = None,
    repo_root: Path = REPO_ROOT,
    plan_path: Path = PLAN_PATH,
) -> dict[str, Any]:
    return {
        "run_id": run_id,
        "generated_at_utc": datetime.now(UTC).replace(microsecond=0).isoformat(),
        "plan_path": str(plan_path),
        "plan_sha256": plan_sha256(plan_path),
        "repo_root": str(repo_root),
        "repo_head": repo_head(repo_root),
        "migration_base_head": MIGRATION_BASE_HEAD,
        "migration_base_ref": MIGRATION_BASE_REF,
        "migration_base_kind": MIGRATION_BASE_KIND,
        "tool_path": tool_path,
        "tool_sha256": tool_sha256 or worktree_tool_sha256(repo_root, tool_path),
        "mode": mode,
        "source_roots": normalize_paths(SOURCE_ROOTS),
        "cache_roots": normalize_paths(CACHE_ROOTS),
        "config_path": str(CONFIG_PATH),
        "marketplace_path": str(MARKETPLACE_PATH),
    }


def metadata_sidecar_path(path: Path) -> Path:
    return path.with_name(path.name + ".metadata.json")


def should_ignore_generated(rel: Path | PurePosixPath) -> bool:
    parts = set(rel.parts)
    return (
        rel.name in GENERATED_FILES
        or bool(parts & GENERATED_DIRS)
        or ".codex/ticket-tmp" in rel.as_posix()
    )


def file_manifest(root: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for path in sorted(root.rglob("*")):
        if path.is_file():
            rel = path.relative_to(root)
            if not should_ignore_generated(rel):
                result[rel.as_posix()] = sha256_file(path)
    return result


def write_sha256sums(path: Path, manifest: dict[str, str], *, metadata: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    lines = [f"{digest}  {rel}" for rel, digest in sorted(manifest.items())]
    path.write_text("\n".join(lines) + ("\n" if lines else ""), encoding="utf-8")
    write_json(metadata_sidecar_path(path), {"run_metadata": metadata})


def read_sha256sums(path: Path) -> dict[str, str]:
    result: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        digest, rel = line.split(maxsplit=1)
        result[rel.strip()] = digest
    return result


def safe_tar_members(archive: Path) -> list[tarfile.TarInfo]:
    members: list[tarfile.TarInfo] = []
    with tarfile.open(archive, "r:*") as tar:
        for member in tar.getmembers():
            member_path = PurePosixPath(member.name)
            if member_path.is_absolute() or ".." in member_path.parts:
                fail("inspect archive", "unsafe member path", member.name)
            if member.issym() or member.islnk():
                fail("inspect archive", "links are not allowed", member.name)
            members.append(member)
    return members


def extract_safe(archive: Path, scratch_root: Path) -> None:
    safe_tar_members(archive)
    scratch_root.mkdir(parents=True, exist_ok=True)
    scratch_resolved = scratch_root.resolve()
    with tarfile.open(archive, "r:*") as tar:
        for member in tar.getmembers():
            target = (scratch_root / member.name).resolve()
            if target != scratch_resolved and scratch_resolved not in target.parents:
                fail("extract archive", "member escapes scratch root", member.name)
            tar.extract(member, scratch_root)


def copy_exact_files(
    source_root: Path,
    output_root: Path,
    manifest: dict[str, str],
) -> dict[str, str]:
    if output_root.exists():
        shutil.rmtree(output_root)
    output_root.mkdir(parents=True, exist_ok=True)
    for rel in sorted(manifest):
        src = source_root / rel
        dst = output_root / rel
        if not src.is_file():
            fail("copy source", "manifest file missing", str(src))
        dst.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, dst)
    copied = file_manifest(output_root)
    if copied != manifest:
        fail("copy source", "post-copy manifest mismatch", {"expected": manifest, "actual": copied})
    return copied


def local_only_root(run_id: str, phase: str) -> Path:
    root = LOCAL_ONLY_ROOT / run_id / phase
    root.mkdir(parents=True, exist_ok=True)
    return root


@dataclass(frozen=True)
class FaultScenario:
    name: str
    files: tuple[str, ...]


def run_fake_fault_tests(root: Path, scenarios: Sequence[FaultScenario]) -> dict[str, Any]:
    root.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, Any]] = []
    for scenario in scenarios:
        scenario_root = root / scenario.name
        if scenario_root.exists():
            shutil.rmtree(scenario_root)
        scenario_root.mkdir(parents=True)
        created: list[Path] = []
        for rel in scenario.files:
            path = scenario_root / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(scenario.name, encoding="utf-8")
            created.append(path)
        for path in reversed(created):
            if path.exists():
                path.unlink()
        for directory in sorted(scenario_root.rglob("*"), reverse=True):
            if directory.is_dir():
                directory.rmdir()
        clean = not any(scenario_root.iterdir())
        results.append({"scenario": scenario.name, "cleanup_verified": clean})
        if not clean:
            fail("fault test cleanup", "scenario left residue", scenario.name)
    return {"scenarios": results, "count": len(results)}


def parse_common_args(description: str) -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--plan", type=Path, default=PLAN_PATH)
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    return parser


def main_with_errors(fn: Any) -> None:
    try:
        fn()
    except MigrationError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1) from exc


def atomic_lock(path: Path) -> int:
    try:
        return os.open(path, os.O_CREAT | os.O_EXCL | os.O_RDWR)
    except FileExistsError as exc:
        fail("acquire lock", "lock already exists", str(path))
        raise AssertionError from exc


def release_lock(fd: int, path: Path) -> None:
    os.close(fd)
    try:
        path.unlink()
    except FileNotFoundError:
        pass


def make_temp_dir(prefix: str) -> Path:
    return Path(tempfile.mkdtemp(prefix=prefix, dir="/private/tmp"))

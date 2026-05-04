from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

try:
    from scripts.project_paths import get_state_dir
except ModuleNotFoundError:
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.project_paths import get_state_dir  # type: ignore[no-redef]


class AmbiguousResumeStateError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResumeState:
    state_path: str
    project: str
    resume_token: str
    archive_path: str
    created_at: str


_LEGACY_CONSUMED_PREFIX = "MIGRATED:"


def _legacy_state_path(state_dir: Path, project: str) -> Path:
    return state_dir / f"handoff-{project}"


def _trash_path(path: Path, *, context: str) -> bool:
    try:
        subprocess.run(["trash", str(path)], capture_output=True, text=True, timeout=5, check=True)
        return True
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError) as exc:
        print(
            f"state cleanup warning: {context} failed: {exc}. Got: {str(path)!r:.100}",
            file=sys.stderr,
        )
        return False


def _mark_legacy_state_consumed(legacy_path: Path, migrated_state_path: Path) -> None:
    legacy_path.write_text(f"{_LEGACY_CONSUMED_PREFIX}{migrated_state_path}\n", encoding="utf-8")


def _read_legacy_archive_path(legacy_path: Path) -> str | None:
    payload = legacy_path.read_text(encoding="utf-8").strip()
    if not payload:
        raise ValueError(
            f"read-state failed: legacy state file was empty. Got: {str(legacy_path)!r:.100}"
        )
    if payload.startswith(_LEGACY_CONSUMED_PREFIX):
        return None
    return payload


def allocate_archive_path(source_path: Path, archive_dir: Path) -> Path:
    candidate = archive_dir / source_path.name
    if not candidate.exists():
        return candidate
    stem = source_path.stem
    suffix = source_path.suffix
    for index in range(1, 100):
        candidate = archive_dir / f"{stem}-{index:02d}{suffix}"
        if not candidate.exists():
            return candidate
    raise FileExistsError(f"archive allocation failed: collision budget exhausted. Got: {str(source_path)!r:.100}")


def write_resume_state(state_dir: Path, project: str, archive_path: str, resume_token: str | None = None) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    token = resume_token or uuid.uuid4().hex
    state_path = state_dir / f"handoff-{project}-{token}.json"
    payload = ResumeState(
        state_path=str(state_path),
        project=project,
        resume_token=token,
        archive_path=archive_path,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    state_path.write_text(json.dumps(asdict(payload), indent=2), encoding="utf-8")
    return state_path


def list_resume_states(state_dir: Path, project: str) -> list[ResumeState]:
    states: list[ResumeState] = []
    for path in sorted(state_dir.glob(f"handoff-{project}-*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        states.append(ResumeState(**data))
    return states


def migrate_legacy_resume_state(state_dir: Path, project: str) -> ResumeState | None:
    legacy_path = _legacy_state_path(state_dir, project)
    if not legacy_path.exists():
        return None
    archive_path = _read_legacy_archive_path(legacy_path)
    if archive_path is None:
        return None
    state_path = write_resume_state(state_dir, project, archive_path)
    if not _trash_path(legacy_path, context="legacy state migration cleanup"):
        _mark_legacy_state_consumed(legacy_path, state_path)
    payload = json.loads(state_path.read_text(encoding="utf-8"))
    return ResumeState(**payload)


def load_resume_state(state_dir: Path, project: str) -> ResumeState | None:
    states = list_resume_states(state_dir, project)
    if len(states) > 1:
        raise AmbiguousResumeStateError(f"Multiple pending resume states for project {project}: {len(states)}")
    if len(states) == 1:
        return states[0]
    return migrate_legacy_resume_state(state_dir, project)


def clear_resume_state(state_dir: Path, state_path_arg: str) -> bool:
    raw = state_path_arg.strip()
    if not raw:
        raise ValueError("clear-state failed: state path must be non-empty. Got: ''")
    state_path = Path(raw)
    resolved_state_dir = state_dir.resolve()
    resolved_state_path = state_path.resolve()
    if resolved_state_path.exists() and not resolved_state_path.is_file():
        raise ValueError(
            f"clear-state failed: state path must point to a file. Got: {raw!r:.100}"
        )
    if not state_path.name.startswith("handoff-") or state_path.suffix not in ("", ".json"):
        raise ValueError(
            f"clear-state failed: state path must match handoff-* or handoff-*.json. Got: {raw!r:.100}"
        )
    if resolved_state_path.parent != resolved_state_dir:
        raise ValueError(
            f"clear-state failed: state path must stay inside the state dir. Got: {raw!r:.100}"
        )
    if not resolved_state_path.exists():
        return True
    legacy_project: str | None = None
    if resolved_state_path.suffix == ".json":
        payload = json.loads(resolved_state_path.read_text(encoding="utf-8"))
        legacy_project = payload.get("project")

    cleared = _trash_path(resolved_state_path, context="clear-state")
    if legacy_project:
        legacy_path = _legacy_state_path(state_dir, legacy_project)
        if legacy_path.exists():
            legacy_cleared = _trash_path(legacy_path, context="legacy state cleanup after clear-state")
            cleared = cleared and legacy_cleared
    return cleared


def prune_old_state_files(max_age_hours: int = 24, *, state_dir: Path | None = None) -> list[Path]:
    if state_dir is None:
        state_dir = get_state_dir()
    if not state_dir.exists():
        return []
    deleted: list[Path] = []
    cutoff = time.time() - (max_age_hours * 60 * 60)
    for state_file in sorted(path for path in state_dir.iterdir() if path.is_file() and path.name.startswith("handoff-")):
        try:
            if state_file.stat().st_mtime < cutoff and _trash_path(state_file, context="ttl prune"):
                deleted.append(state_file)
        except OSError:
            continue
    return deleted


def _emit(payload: dict[str, object], field: str | None) -> int:
    if field is None:
        json.dump(payload, sys.stdout)
        return 0
    value = payload.get(field)
    if value is None:
        return 1
    print(value)
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    archive_parser = subparsers.add_parser("archive")
    archive_parser.add_argument("--source", required=True)
    archive_parser.add_argument("--archive-dir", required=True)
    archive_parser.add_argument("--field", choices=("archived_path",), default=None)

    write_parser = subparsers.add_parser("write-state")
    write_parser.add_argument("--state-dir", required=True)
    write_parser.add_argument("--project", required=True)
    write_parser.add_argument("--archive-path", required=True)
    write_parser.add_argument("--resume-token", default=None)
    write_parser.add_argument("--field", choices=("state_path",), default=None)

    read_parser = subparsers.add_parser("read-state")
    read_parser.add_argument("--state-dir", required=True)
    read_parser.add_argument("--project", required=True)
    read_parser.add_argument("--field", choices=("state_path", "archive_path", "resume_token"), default=None)

    clear_parser = subparsers.add_parser("clear-state")
    clear_parser.add_argument("--state-dir", required=True)
    clear_parser.add_argument("--state-path", required=True)

    prune_parser = subparsers.add_parser("prune-state")
    prune_parser.add_argument("--state-dir", required=True)
    prune_parser.add_argument("--max-age-hours", type=int, default=24)

    args = parser.parse_args(argv)
    if args.command == "archive":
        source = Path(args.source)
        archive_dir = Path(args.archive_dir)
        archive_dir.mkdir(parents=True, exist_ok=True)
        destination = allocate_archive_path(source, archive_dir)
        source.replace(destination)
        return _emit({"archived_path": str(destination)}, args.field)
    if args.command == "write-state":
        state_path = write_resume_state(Path(args.state_dir), args.project, args.archive_path, args.resume_token)
        return _emit({"state_path": str(state_path)}, args.field)
    if args.command == "read-state":
        try:
            state = load_resume_state(Path(args.state_dir), args.project)
        except (AmbiguousResumeStateError, ValueError) as exc:
            json.dump({"error": str(exc)}, sys.stdout)
            return 2
        if state is None:
            return 1
        return _emit(asdict(state), args.field)
    if args.command == "clear-state":
        clear_resume_state(Path(args.state_dir), args.state_path)
        return 0

    deleted = prune_old_state_files(args.max_age_hours, state_dir=Path(args.state_dir))
    json.dump({"deleted": [str(path) for path in deleted]}, sys.stdout)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

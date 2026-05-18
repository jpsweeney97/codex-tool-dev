"""search.py - Search handoff history for decisions, learnings, and context.

Searches within parsed handoff sections and outputs structured JSON results.
Parsing is provided by handoff_parsing.py; paths by project_paths.py.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from turbo_mode_handoff_runtime.handoff_parsing import parse_handoff
from turbo_mode_handoff_runtime.project_paths import (
    get_handoffs_dir,
    get_legacy_handoffs_dir,
    get_project_name,
    get_project_root,
)
from turbo_mode_handoff_runtime.storage_authority import (
    HandoffCandidate,
    SelectionEligibility,
    StorageLocation,
    discover_handoff_inventory,
    eligible_history_candidates,
)

__all__ = [
    "main",
    "parse_handoff",
    "search_handoff_history",
    "search_handoffs",
]


def search_handoffs(
    handoffs_dir: Path,
    query: str,
    *,
    regex: bool = False,
    skipped: list[dict] | None = None,
    archive_name: str = "archive",
) -> list[dict]:
    """Search handoff files for matching sections.

    Args:
        handoffs_dir: Directory containing handoff .md files (with optional .archive/ subdirectory)
        query: Search string or regex pattern
        regex: If True, treat query as regex (case-sensitive). If False, literal
            case-insensitive match. Users can embed (?i) in their regex for
            case-insensitive regex search.

    Returns:
        List of result dicts sorted by date descending. Each dict contains:
        file, title, date, type, archived, section_heading, section_content
    """
    if not handoffs_dir.exists():
        return []

    # Compile search pattern
    flags = 0 if regex else re.IGNORECASE
    if not regex:
        query = re.escape(query)
    pattern = re.compile(query, flags)
    skipped_sink = skipped if skipped is not None else []

    results: list[dict] = []

    # Collect .md files from top-level and .archive/
    md_files: list[tuple[Path, bool]] = []
    for f in handoffs_dir.glob("*.md"):
        md_files.append((f, False))
    archive_dir = handoffs_dir / archive_name
    if archive_dir.exists():
        for f in archive_dir.glob("*.md"):
            md_files.append((f, True))

    for path, archived in md_files:
        try:
            handoff = parse_handoff(path)
        except (OSError, UnicodeDecodeError) as e:
            skipped_sink.append({"file": path.name, "reason": str(e)})
            continue  # Skip unreadable or malformed files

        for section in handoff.sections:
            search_text = f"{section.heading}\n{section.content}"
            if pattern.search(search_text):
                results.append(
                    {
                        "file": path.name,
                        "title": handoff.frontmatter.get("title", path.stem),
                        "date": handoff.frontmatter.get("date", ""),
                        "type": handoff.frontmatter.get("type", "handoff"),
                        "archived": archived,
                        "section_heading": section.heading,
                        "section_content": section.content,
                    }
                )

    # Sort by date descending
    results.sort(key=lambda r: r["date"], reverse=True)
    return results


def search_handoff_history(
    project_root: Path,
    query: str,
    *,
    regex: bool = False,
    skipped: list[dict] | None = None,
) -> list[dict]:
    """Search read-only history candidates from the shared storage authority."""
    inventory = discover_handoff_inventory(project_root, scan_mode="history-search")
    candidates = eligible_history_candidates(inventory)
    skipped_sink = skipped if skipped is not None else []
    results: list[dict] = []
    for candidate in candidates:
        if candidate.selection_eligibility != SelectionEligibility.ELIGIBLE:
            skipped_sink.append(
                {
                    "file": str(candidate.path),
                    "reason": candidate.skip_reason or candidate.selection_eligibility,
                }
            )
            continue
        results.extend(
            _search_candidate(
                candidate,
                query,
                regex=regex,
                dedup_winner=True,
                skipped=skipped_sink,
            )
        )
    results.sort(key=lambda r: r["date"], reverse=True)
    return results


def _search_candidate(
    candidate: HandoffCandidate,
    query: str,
    *,
    regex: bool,
    dedup_winner: bool,
    skipped: list[dict],
) -> list[dict]:
    flags = 0 if regex else re.IGNORECASE
    pattern_text = query if regex else re.escape(query)
    pattern = re.compile(pattern_text, flags)
    try:
        handoff = parse_handoff(candidate.path)
    except (OSError, UnicodeDecodeError) as exc:
        skipped.append({"file": str(candidate.path), "reason": str(exc)})
        return []

    results: list[dict] = []
    for section in handoff.sections:
        search_text = f"{section.heading}\n{section.content}"
        if pattern.search(search_text):
            results.append(
                {
                    "file": candidate.path.name,
                    "title": handoff.frontmatter.get("title", candidate.path.stem),
                    "date": handoff.frontmatter.get("date", ""),
                    "type": handoff.frontmatter.get("type", "handoff"),
                    "archived": _is_archived(candidate.storage_location),
                    "section_heading": section.heading,
                    "section_content": section.content,
                    "source_path": str(candidate.path),
                    "storage_location": candidate.storage_location,
                    "artifact_class": candidate.artifact_class,
                    "source_git_visibility": candidate.source_git_visibility,
                    "source_fs_status": candidate.source_fs_status,
                    "document_profile": candidate.document_profile,
                    "content_sha256": candidate.content_sha256,
                    "dedup_winner": dedup_winner,
                }
            )
    return results


def _is_archived(location: StorageLocation) -> bool:
    return location in {
        StorageLocation.PRIMARY_ARCHIVE,
        StorageLocation.LEGACY_ARCHIVE,
        StorageLocation.PREVIOUS_PRIMARY_HIDDEN_ARCHIVE,
    }


def main(argv: list[str] | None = None) -> str:
    """CLI entry point. Returns JSON string.

    Args:
        argv: Command-line arguments (defaults to sys.argv[1:] if None).

    Returns:
        JSON string with search results.
    """
    import argparse

    parser = argparse.ArgumentParser(description="Search handoff history")
    parser.add_argument("query", help="Search query (text or regex)")
    parser.add_argument("--regex", action="store_true", help="Treat query as regex")
    parser.add_argument("--project-root", type=Path, default=None)
    parser.add_argument("--handoffs-dir", type=Path, default=None)
    args = parser.parse_args(argv)
    if args.handoffs_dir is None:
        project_root, project_source = (
            (args.project_root.resolve(), "argument")
            if args.project_root is not None
            else get_project_root()
        )
        skipped_files: list[dict] = []
        try:
            results = search_handoff_history(
                project_root,
                args.query,
                regex=args.regex,
                skipped=skipped_files,
            )
        except re.error as e:
            return json.dumps(
                {
                    "query": args.query,
                    "total_matches": 0,
                    "results": [],
                    "skipped": skipped_files,
                    "project_source": project_source,
                    "error": f"Invalid regex: {e}",
                    "legacy_warning": None,
                }
            )
        legacy_warning = None
        if any(result.get("storage_location", "").startswith("legacy_") for result in results):
            legacy_warning = (
                "Found handoffs at legacy location `docs/handoffs/`. "
                "Post-cutover writes use `.codex/handoffs/`; legacy matches are "
                "read-only compatibility input."
            )
        return json.dumps(
            {
                "query": args.query,
                "total_matches": len(results),
                "results": results,
                "skipped": skipped_files,
                "project_source": project_source,
                "error": None,
                "legacy_warning": legacy_warning,
            }
        )

    _, project_source = get_project_name()
    handoffs_dir = args.handoffs_dir or get_handoffs_dir()

    if not handoffs_dir.exists():
        return json.dumps(
            {
                "query": args.query,
                "total_matches": 0,
                "results": [],
                "skipped": [],
                "project_source": project_source,
                "error": f"Handoffs directory not found: {handoffs_dir}",
                "legacy_warning": None,
            }
        )

    skipped_files: list[dict] = []
    try:
        results = search_handoffs(handoffs_dir, args.query, regex=args.regex, skipped=skipped_files)
    except re.error as e:
        return json.dumps(
            {
                "query": args.query,
                "total_matches": 0,
                "results": [],
                "skipped": skipped_files,
                "project_source": project_source,
                "error": f"Invalid regex: {e}",
                "legacy_warning": None,
            }
        )

    # Legacy fallback: check docs/handoffs/ for pre-cutover files.
    legacy_warning = None
    try:
        legacy_dir = get_legacy_handoffs_dir()
        if legacy_dir.exists():
            legacy_results = search_handoffs(
                legacy_dir,
                args.query,
                regex=args.regex,
                skipped=skipped_files,
                archive_name="archive",
            )
            if legacy_results:
                legacy_warning = (
                    "Found handoffs at legacy location `docs/handoffs/`. "
                    "Post-cutover writes use `.codex/handoffs/`; legacy matches are "
                    "read-only compatibility input."
                )
                results.extend(legacy_results)
                results.sort(key=lambda r: r["date"], reverse=True)
    except OSError as exc:
        skipped_files.append({"file": "legacy-discovery", "reason": str(exc)})

    return json.dumps(
        {
            "query": args.query,
            "total_matches": len(results),
            "results": results,
            "skipped": skipped_files,
            "project_source": project_source,
            "error": None,
            "legacy_warning": legacy_warning,
        }
    )

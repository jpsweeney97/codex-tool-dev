#!/usr/bin/env python3
"""search.py - Search handoff history for decisions, learnings, and context.

Searches within parsed handoff sections and outputs structured JSON results.
Parsing is provided by handoff_parsing.py; paths by project_paths.py.
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

# Re-exported for backward compatibility — test_search.py imports these from
# scripts.search. Do not remove without updating downstream imports.
try:
    from scripts.handoff_parsing import HandoffFile, Section, parse_handoff
    from scripts.project_paths import get_handoffs_dir, get_legacy_handoffs_dir, get_project_name
except ModuleNotFoundError:  # Direct execution (python3 scripts/search.py)
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
    from scripts.handoff_parsing import HandoffFile, Section, parse_handoff  # type: ignore[no-redef]
    from scripts.project_paths import get_handoffs_dir, get_legacy_handoffs_dir, get_project_name  # type: ignore[no-redef]


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
        regex: If True, treat query as regex (case-sensitive). If False, literal case-insensitive match.
            Users can embed (?i) in their regex for case-insensitive regex search.

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
                results.append({
                    "file": path.name,
                    "title": handoff.frontmatter.get("title", path.stem),
                    "date": handoff.frontmatter.get("date", ""),
                    "type": handoff.frontmatter.get("type", "handoff"),
                    "archived": archived,
                    "section_heading": section.heading,
                    "section_content": section.content,
                })

    # Sort by date descending
    results.sort(key=lambda r: r["date"], reverse=True)
    return results


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
    args = parser.parse_args(argv)
    _, project_source = get_project_name()

    handoffs_dir = get_handoffs_dir()

    if not handoffs_dir.exists():
        return json.dumps({
            "query": args.query,
            "total_matches": 0,
            "results": [],
            "skipped": [],
            "project_source": project_source,
            "error": f"Handoffs directory not found: {handoffs_dir}",
            "legacy_warning": None,
        })

    skipped_files: list[dict] = []
    try:
        results = search_handoffs(handoffs_dir, args.query, regex=args.regex, skipped=skipped_files)
    except re.error as e:
        return json.dumps({
            "query": args.query,
            "total_matches": 0,
            "results": [],
            "skipped": skipped_files,
            "project_source": project_source,
            "error": f"Invalid regex: {e}",
            "legacy_warning": None,
        })

    # Legacy fallback: check docs/handoffs/ for pre-cutover files.
    legacy_warning = None
    try:
        legacy_dir = get_legacy_handoffs_dir()
        if legacy_dir.exists():
            legacy_results = search_handoffs(
                legacy_dir, args.query, regex=args.regex,
                skipped=skipped_files, archive_name="archive",
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

    return json.dumps({
        "query": args.query,
        "total_matches": len(results),
        "results": results,
        "skipped": skipped_files,
        "project_source": project_source,
        "error": None,
        "legacy_warning": legacy_warning,
    })


if __name__ == "__main__":
    print(main())
    sys.exit(0)

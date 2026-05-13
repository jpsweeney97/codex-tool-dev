#!/usr/bin/env python3
"""Shared control-tool helpers for the Handoff storage reversal plan."""

from __future__ import annotations

import hashlib
import os
import re
import subprocess
from pathlib import Path
from typing import Iterable


ALLOWED_SCOPE_VALUES = {"repo-authority", "local-preflight-summary", "policy-rule"}


class ToolError(Exception):
    """Raised when a control artifact is missing or stale."""


def fail(message: str) -> None:
    raise ToolError(message)


def normalize_text(text: str) -> str:
    return " ".join(text.split())


def sha256_text(text: str) -> str:
    return hashlib.sha256(normalize_text(text).encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        fail(f"read_text failed: {exc}. Got: {str(path)!r}")


def write_text_if_changed(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    current = path.read_text(encoding="utf-8") if path.exists() else None
    if current != text:
        path.write_text(text, encoding="utf-8")


def section_body(text: str, heading: str) -> str:
    pattern = re.compile(rf"^## {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        fail(f"section_body failed: heading not found. Got: {heading!r}")
    next_heading = re.search(r"^## ", text[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.end() : end]


def subsection_body(text: str, heading: str) -> str:
    pattern = re.compile(rf"^### {re.escape(heading)}\s*$", re.MULTILINE)
    match = pattern.search(text)
    if not match:
        fail(f"subsection_body failed: heading not found. Got: {heading!r}")
    next_heading = re.search(r"^#{2,3} ", text[match.end() :], flags=re.MULTILINE)
    end = match.end() + next_heading.start() if next_heading else len(text)
    return text[match.end() : end]


def markdown_bullets(body: str) -> list[str]:
    bullets: list[str] = []
    current: list[str] | None = None
    for line in body.splitlines():
        if line.startswith("- "):
            if current:
                bullets.append(normalize_text(" ".join(current)))
            current = [line[2:].strip()]
        elif current is not None:
            if not line.strip():
                continue
            if line.startswith((" ", "\t")):
                current.append(line.strip())
            else:
                bullets.append(normalize_text(" ".join(current)))
                current = None
    if current:
        bullets.append(normalize_text(" ".join(current)))
    return bullets


def escape_cell(value: object) -> str:
    return str(value).replace("\\", "\\\\").replace("|", "\\|").replace("\n", "<br>")


def split_table_row(line: str) -> list[str]:
    cells: list[str] = []
    current: list[str] = []
    escaped = False
    content = line.strip()
    if content.startswith("|"):
        content = content[1:]
    if content.endswith("|"):
        content = content[:-1]
    for char in content:
        if escaped:
            current.append(char)
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == "|":
            cells.append("".join(current).strip())
            current = []
        else:
            current.append(char)
    cells.append("".join(current).strip())
    return [cell.replace("<br>", "\n") for cell in cells]


def parse_markdown_table(text: str) -> list[dict[str, str]]:
    lines = [line for line in text.splitlines() if line.startswith("|")]
    if len(lines) < 2:
        fail("parse_markdown_table failed: table missing. Got: no markdown table")
    headers = split_table_row(lines[0])
    rows: list[dict[str, str]] = []
    for line in lines[2:]:
        cells = split_table_row(line)
        if len(cells) != len(headers):
            fail(f"parse_markdown_table failed: column mismatch. Got: {line!r}")
        rows.append(dict(zip(headers, cells, strict=True)))
    return rows


def markdown_table(headers: list[str], rows: list[dict[str, object]]) -> str:
    output = ["| " + " | ".join(headers) + " |"]
    output.append("|" + "|".join("---" for _ in headers) + "|")
    for row in rows:
        output.append("| " + " | ".join(escape_cell(row.get(header, "")) for header in headers) + " |")
    return "\n".join(output)


def run_git(project_root: Path, args: list[str], *, check: bool = False) -> subprocess.CompletedProcess[str]:
    completed = subprocess.run(
        ["git", *args],
        cwd=project_root,
        text=True,
        capture_output=True,
        check=False,
    )
    if check and completed.returncode != 0:
        fail(f"git {' '.join(args)} failed: {completed.stderr.strip()}. Got: {completed.returncode!r}")
    return completed


def git_status_class(project_root: Path, rel_path: str) -> str:
    tracked = run_git(project_root, ["ls-files", "--error-unmatch", rel_path])
    if tracked.returncode == 0:
        return "tracked"
    ignored = run_git(project_root, ["check-ignore", "-q", rel_path])
    if ignored.returncode == 0:
        return "ignored"
    return "untracked"


def git_visibility_basis(project_root: Path, rel_path: str) -> str:
    completed = run_git(project_root, ["check-ignore", "-v", rel_path])
    if completed.returncode == 0:
        return completed.stdout.strip()
    return "not ignored by git check-ignore"


def iter_inventory(root: Path) -> list[Path]:
    base = root / "docs" / "handoffs"
    if not base.exists():
        return []
    return sorted(path for path in base.rglob("*"))


def relative_to_root(project_root: Path, path: Path) -> str:
    return path.resolve(strict=False).relative_to(project_root.resolve(strict=False)).as_posix()


def fs_status(path: Path) -> str:
    try:
        if path.is_symlink():
            return "symlink"
        if not path.exists():
            return "missing"
        if path.is_file():
            return "regular-file"
        if path.is_dir():
            return "directory"
        return "non-regular"
    except OSError:
        return "unreadable"


def manifest_hash(paths: Iterable[str]) -> str:
    return hashlib.sha256("\n".join(sorted(paths)).encode("utf-8")).hexdigest()

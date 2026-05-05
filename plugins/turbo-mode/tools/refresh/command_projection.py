from __future__ import annotations

import json
import re
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CommandProjection:
    items: tuple[str, ...]
    parser_warnings: tuple[str, ...]


_FENCE_RE = re.compile(r"^```(?P<lang>[A-Za-z0-9_-]*)\s*$")
_COMMAND_LINE_RE = re.compile(r"^(?:python|python3|uv|codex|ticket_[A-Za-z0-9_-]+|\./)(?:\s|$)")
_SLASH_COMMAND_RE = re.compile(
    r"(?<![\w/])/(?:save|load|ticket|ticket-triage|defer|quicksave|summary|search|triage|distill)\b"
)
_INLINE_CODE_RE = re.compile(r"`([^`\n]+)`")
_JSON_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)

_SHELL_FENCE_LANGUAGES = {"bash", "sh", "shell"}

_SEMANTIC_TRIGGER_RE = re.compile(
    r"\b("
    r"root authority|root[- ]authority|"
    r"permission|permissions|approval|approvals|sandbox|sandboxing|"
    r"prepare|execute|close|reopen|recover|repair|rollback|"
    r"denial|deny|denied|enforcement|enforce|validation|validate|hook|hooks|"
    r"recovery|audit[- ]log|evidence|redaction|redact|certification|certify|"
    r"marketplace|global config|installed cache|runtime inventory|"
    r"maintenance window|process gate|operator exclusivity"
    r")\b",
    re.IGNORECASE,
)


def extract_command_projection(text: str) -> CommandProjection:
    """Extract a deterministic command-shape projection from Markdown text."""
    collector = _ProjectionCollector()
    lines = text.splitlines()
    index = 0
    command_table_columns: tuple[int, ...] = ()

    while index < len(lines):
        line = lines[index]
        fence_match = _FENCE_RE.match(line.strip())
        if fence_match:
            lang = fence_match.group("lang").lower()
            block: list[str] = []
            index += 1
            while index < len(lines) and not lines[index].strip().startswith("```"):
                block.append(lines[index])
                index += 1
            _extract_fenced_block(block, lang=lang, collector=collector)
        else:
            stripped = _strip_markdown_prefix(line)
            if _looks_like_table_row(stripped):
                cells = _parse_table_cells(stripped)
                if all(_is_separator_cell(cell) for cell in cells):
                    pass
                elif table_columns := _command_table_columns(cells):
                    command_table_columns = table_columns
                else:
                    _extract_table_cells(
                        cells,
                        command_columns=command_table_columns,
                        collector=collector,
                    )
            else:
                command_table_columns = ()
                _extract_line(line, collector=collector)
        index += 1

    return CommandProjection(
        items=tuple(collector.items),
        parser_warnings=tuple(collector.parser_warnings),
    )


def has_semantic_policy_trigger(text: str) -> bool:
    """Return True when prose contains refresh-policy sensitive trigger terms."""
    return _SEMANTIC_TRIGGER_RE.search(text) is not None


class _ProjectionCollector:
    def __init__(self) -> None:
        self.items: list[str] = []
        self.parser_warnings: list[str] = []
        self._seen: set[str] = set()

    def add(self, item: str) -> None:
        normalized = _normalize_item(item)
        if normalized and normalized not in self._seen:
            self._seen.add(normalized)
            self.items.append(normalized)

    def warn(self, warning: str) -> None:
        if warning not in self.parser_warnings:
            self.parser_warnings.append(warning)


def _extract_fenced_block(block: list[str], *, lang: str, collector: _ProjectionCollector) -> None:
    block_text = "\n".join(block).strip()
    if lang in _SHELL_FENCE_LANGUAGES:
        for line in block:
            if normalized := _normalize_command_line(line):
                collector.add(normalized)
        return

    json_item = _extract_json_payload(block_text, collector=collector)
    if json_item:
        collector.add(json_item)
        return

    if lang and lang != "json":
        return

    for line in block:
        _extract_line(line, collector=collector)


def _extract_line(line: str, *, collector: _ProjectionCollector) -> None:
    stripped = _strip_markdown_prefix(line)
    if not stripped:
        return

    if "|" in stripped and _looks_like_table_row(stripped):
        _extract_table_cells(_parse_table_cells(stripped), command_columns=(), collector=collector)
        return

    if normalized := _normalize_command_line(stripped):
        collector.add(normalized)
    for inline_code in _INLINE_CODE_RE.findall(stripped):
        if normalized := _normalize_command_line(inline_code):
            collector.add(normalized)
        elif slash_command := _extract_slash_command(inline_code):
            collector.add(slash_command)
    if slash_command := _extract_slash_command(stripped):
        collector.add(slash_command)
    if json_item := _extract_json_payload(stripped, collector=collector):
        collector.add(json_item)


def _extract_table_cells(
    cells: list[str],
    *,
    command_columns: tuple[int, ...],
    collector: _ProjectionCollector,
) -> None:
    if not cells or all(_is_separator_cell(cell) for cell in cells):
        return

    for index, cell in enumerate(cells):
        if index in command_columns:
            collector.add(cell)
        elif _is_projection_item(cell):
            if normalized := _normalize_command_line(cell):
                collector.add(normalized)
            elif slash_command := _extract_slash_command(cell):
                collector.add(slash_command)


def _parse_table_cells(row: str) -> list[str]:
    return [_strip_code(cell.strip()) for cell in row.strip("|").split("|")]


def _command_table_columns(cells: list[str]) -> tuple[int, ...]:
    return tuple(index for index, cell in enumerate(cells) if cell.lower() == "command")


def _normalize_command_line(line: str) -> str:
    stripped = _strip_code(_strip_markdown_prefix(line))
    if not stripped or stripped.startswith("#"):
        return ""
    if _COMMAND_LINE_RE.match(stripped):
        return stripped
    return ""


def _strip_markdown_prefix(line: str) -> str:
    stripped = line.strip()
    stripped = re.sub(r"^(?:[-*+]|\d+\.)\s+", "", stripped)
    stripped = re.sub(r"^>\s*", "", stripped)
    return stripped.strip()


def _strip_code(text: str) -> str:
    stripped = text.strip()
    if len(stripped) >= 2 and stripped.startswith("`") and stripped.endswith("`"):
        return stripped[1:-1].strip()
    return stripped


def _extract_slash_command(text: str) -> str:
    match = _SLASH_COMMAND_RE.search(text)
    return match.group(0) if match else ""


def _extract_json_payload(text: str, *, collector: _ProjectionCollector) -> str:
    candidate = text.strip()
    if not candidate.startswith("{"):
        match = _JSON_OBJECT_RE.search(candidate)
        if not match:
            return ""
        candidate = match.group(0)

    try:
        payload = json.loads(candidate)
    except json.JSONDecodeError:
        if '"request"' in candidate or '"action"' in candidate:
            collector.warn("json-payload-parse-failed")
        return ""

    if not _contains_request_or_action(payload):
        return ""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def _contains_request_or_action(value: Any) -> bool:
    if isinstance(value, dict):
        return any(key in value for key in ("request", "action")) or any(
            _contains_request_or_action(item) for item in value.values()
        )
    if isinstance(value, list):
        return any(_contains_request_or_action(item) for item in value)
    return False


def _looks_like_table_row(line: str) -> bool:
    return line.startswith("|") and line.endswith("|")


def _is_separator_cell(cell: str) -> bool:
    return bool(re.fullmatch(r":?-{3,}:?", cell.strip()))


def _is_projection_item(text: str) -> bool:
    return bool(_normalize_command_line(text) or _extract_slash_command(text))


def _normalize_item(item: str) -> str:
    return " ".join(item.strip().split())

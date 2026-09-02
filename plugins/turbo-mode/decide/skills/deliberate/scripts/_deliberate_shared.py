"""deliberate — shared foundation: errors, read authorization, safe YAML.

Extracted from scripts/deliberate-validate.py under ADR-0001 (contract-data
version 6): the base of the internal dependency graph — everything calls into
it; it calls into no other first-party code. A direct method surface: listed
in validation.method-surfaces and platform-hashed by the orchestrator before
any helper invocation. No PEP 723 header: an imported module, never an
entrypoint — the entrypoint's script environment supplies `yaml`.
"""

from __future__ import annotations

import io
import os
from pathlib import Path
from typing import Any

import yaml


SAFE_TAGS = {
    "tag:yaml.org,2002:map",
    "tag:yaml.org,2002:seq",
    "tag:yaml.org,2002:str",
    "tag:yaml.org,2002:int",
    "tag:yaml.org,2002:float",
    "tag:yaml.org,2002:bool",
    "tag:yaml.org,2002:null",
}


class Refusal(Exception):
    """Refused before any content judgment (exit 2)."""


class ValidationFailure(Exception):
    """Deterministic shape/consistency check failed (exit 1)."""


class StoreReadLoss(Exception):
    """A required run-state item is absent or unreadable (exit 4)."""


def fail(op: str, reason: str, got: object = None) -> ValidationFailure:
    suffix = f" Got: {got!r:.300}" if got is not None else ""
    return ValidationFailure(f"{op} failed: {reason}.{suffix}")


def refuse(op: str, reason: str, got: object = None) -> Refusal:
    suffix = f" Got: {got!r:.300}" if got is not None else ""
    return Refusal(f"{op} refused: {reason}.{suffix}")


# ---------------------------------------------------------------------------
# Read-set enforcement
# ---------------------------------------------------------------------------


class ReadSet:
    """Explicit read authorization: canonicalized roots; reads outside refuse."""

    def __init__(self) -> None:
        self.roots: list[Path] = []

    def allow(self, path: Path) -> Path:
        canonical = Path(os.path.realpath(path))
        self.roots.append(canonical)
        return canonical

    def check(self, path: Path) -> Path:
        canonical = Path(os.path.realpath(path))
        for root in self.roots:
            if canonical == root or root in canonical.parents:
                return canonical
        raise refuse("read", f"path outside the explicit read set: {canonical}")

    def read_bytes(self, path: Path) -> bytes:
        canonical = self.check(path)
        if not canonical.exists():
            raise fail("read", f"path does not exist: {canonical}")
        return canonical.read_bytes()


# ---------------------------------------------------------------------------
# Safe YAML
# ---------------------------------------------------------------------------


def _decode_utf8(raw: bytes, op: str) -> str:
    try:
        return raw.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise fail(op, f"input is not UTF-8: {exc}") from exc


def safe_parse(raw: bytes, *, byte_cap: int, depth_cap: int, op: str) -> Any:
    """Event-checked safe parse: caps first, then anchors/aliases/tags, one doc."""
    if len(raw) > byte_cap:
        raise refuse(op, f"input of {len(raw)} bytes exceeds the {byte_cap}-byte cap")
    text = _decode_utf8(raw, op)
    depth = 0
    documents = 0
    try:
        for event in yaml.parse(io.StringIO(text)):
            if isinstance(event, yaml.DocumentStartEvent):
                documents += 1
                if documents > 1:
                    raise refuse(op, "multiple YAML documents in one input")
            if isinstance(event, yaml.AliasEvent):
                raise refuse(op, "YAML aliases are rejected before expansion")
            anchor = getattr(event, "anchor", None)
            if anchor is not None and not isinstance(event, yaml.AliasEvent):
                raise refuse(op, f"YAML anchors are rejected: &{anchor}")
            tag = getattr(event, "tag", None)
            if tag is not None and tag not in SAFE_TAGS:
                raise refuse(op, f"YAML tag rejected: {tag}")
            if isinstance(event, (yaml.MappingStartEvent, yaml.SequenceStartEvent)):
                depth += 1
                if depth > depth_cap:
                    raise refuse(op, f"nesting exceeds the depth cap of {depth_cap}")
            if isinstance(event, (yaml.MappingEndEvent, yaml.SequenceEndEvent)):
                depth -= 1
    except yaml.YAMLError as exc:
        raise fail(op, f"YAML does not parse: {exc}")
    try:
        return yaml.load(text, Loader=_UniqueKeyLoader)
    except yaml.YAMLError as exc:
        raise fail(op, f"YAML does not parse: {exc}")


class _UniqueKeyLoader(yaml.SafeLoader):
    """Safe loader that rejects duplicate mapping keys instead of taking the last."""


def _construct_unique_mapping(
    loader: _UniqueKeyLoader, node: yaml.MappingNode, deep: bool = False
) -> dict:
    mapping: dict = {}
    for key_node, value_node in node.value:
        key = loader.construct_object(key_node, deep=deep)
        try:
            duplicate = key in mapping
        except TypeError as exc:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found an unhashable mapping key: {key!r}",
                key_node.start_mark,
            ) from exc
        if duplicate:
            raise yaml.constructor.ConstructorError(
                "while constructing a mapping",
                node.start_mark,
                f"found duplicate key: {key!r}",
                key_node.start_mark,
            )
        mapping[key] = loader.construct_object(value_node, deep=deep)
    return mapping


_UniqueKeyLoader.add_constructor(
    yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG,
    _construct_unique_mapping,
)


class _NoAliasDumper(yaml.SafeDumper):
    """Never emit anchors/aliases: dumped documents must re-parse under this
    module's own alias-rejecting safe parser, even when a Python object is
    referenced twice."""

    def ignore_aliases(self, data: object) -> bool:
        return True


def dump_yaml(value: object) -> str:
    return yaml.dump(
        value,
        Dumper=_NoAliasDumper,
        default_flow_style=False,
        sort_keys=False,
        allow_unicode=True,
        width=88,
    )

#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""deliberate — bundled validator, brief renderer, and content-identity helper.

One implementation, invoked identically from Claude Code and Codex via Bash,
for: stage-brief rendering (pre-dispatch packet construction from the run-state
store and the canonical matrix), envelope validation, capsule validation,
run-state item validation and writes, content-identity computation, authored-
rendering comparison for the validation ladder, and the must-block/must-pass
fixture set.

Canonical data: references/contract-data.yaml — loaded at run time, never
copied here. Every check is deterministic shape and consistency only; nothing
here is semantic judgment, and orchestrator judgment never stands in for a
failed check.

Validator boundary (part of the skill contract):
- YAML parsed with a safe event-checked loader: custom tags rejected, anchors
  and aliases rejected before expansion, input past the byte or depth cap
  rejected before parse, exactly one document.
- Schemas bind fixed key sets; unknown keys are rejected, never ignored.
- argv-only invocation; every path argument is a literal path.
- Every read is canonicalized (symlinks resolved) and checked against the
  explicit read set for the command before any byte is read.
- The self-hash bootstrap is non-circular: the orchestrator verifies this
  script's content identifier with the platform hasher (`shasum -a 256` or
  equivalent), never with this script.
- Pre-import boundary: before any first-party import, a two-pass stdlib-only
  census of scripts/ refuses unexpected artifacts fail-closed (ADR-0001) —
  layout rules run on os/sys before any shadowable import, then the narrow
  deferred stdlib set performs a structural zip check (zipfile.is_zipfile,
  after direct shadows are cleared) that catches prefixed archives and refuses
  unreadable inert files; bytecode is
  redirected to a fresh invocation-private cache prefix mechanically verified
  outside the repository (or served skill root when standalone) and retired at
  exit, with repo-, bundle-, scripts-, allowed-data-, symlink-resolved-, and
  case-aliased internal temp roots refused before first-party import; the
  embedded census policy is authenticated by this file's own method-surface
  hash and asserted equal to contract-data.yaml's import-boundary section by a
  release-time test, with _require_boundary_match re-checking it at every load.

Exit codes: 0 pass; 1 validation failure; 2 refusal (unauthorized read,
off-column request, unsupported schema, bound breach, usage); 4 required
run-state item absent (the orchestrator maps this to `store failed: read`).
"""

from __future__ import annotations

import os
import sys

# ---------------------------------------------------------------------------
# Pre-import boundary (ADR-0001 + 2026-07-16 amendment), two passes before any
# first-party import. Pass 1 (the LAYOUT census) uses only `os`/`sys` — modules
# already initialized at interpreter startup, so they cannot be shadowed from
# scripts/ (which is sys.path[0]) — enforces every structural rule, and COLLECTS
# the inert-suffix files. Once pass 1 returns without refusing, no
# .py/.pyc/.so/package/symlink shadow exists under scripts/, so only the narrow
# deferred stdlib imports below may run: atexit/shutil/tempfile create and
# retire a cache prefix mechanically verified outside the repository (or the
# served skill root when standalone), and zipfile performs pass 2's structural
# archive check. Unsafe ambient temp roots refuse before prefix creation; the
# created prefix is resolved and checked again before assignment. Pass 2 runs
# `zipfile.is_zipfile` on the collected inert files — the same detector the
# Gate-2 checker uses (672abb5), so a prefixed/self-extracting zip is caught and
# the two consumers cannot drift on zip detection. Every first-party and other
# import waits until pass 2 returns. The census consumes only the embedded
# policy, authenticated by this entrypoint's own method-surface hash; a
# release-time test asserts that embedding equals the pinned contract section,
# and `_require_boundary_match` re-checks it per invocation as defense-in-depth.
# No pre-import contract parse (a weaker first parse of a pinned surface was
# rejected — ADR-0001 amendment).
# ---------------------------------------------------------------------------
_BOUNDARY_POLICY: dict = {
    "entrypoint": "deliberate-validate.py",
    "module-name-pattern": r"^_deliberate_[a-z][a-z0-9_]*\.py$",
    "allowed-data-dirs": ["fixtures"],
    "forbidden-loader-suffixes": [".pyc", ".pyo", ".pyd", ".pyw", ".so"],
    "archive-suffixes": [".egg", ".whl", ".zip"],
}
_BOUNDARY_FORBIDDEN_SUFFIXES = tuple(
    sorted(
        set(_BOUNDARY_POLICY["forbidden-loader-suffixes"])
        | set(_BOUNDARY_POLICY["archive-suffixes"])
    )
)


def _boundary_refuse(reason: str, got: str) -> None:
    sys.stderr.write(f"import boundary refused: {reason}. Got: {got}\n")
    sys.exit(2)


def _boundary_module_name_conforms(name: str) -> bool:
    """`re`-free rendering of module-name-pattern; agreement is test-pinned."""
    if not name.startswith("_deliberate_") or not name.endswith(".py"):
        return False
    stem = name[len("_deliberate_") : -len(".py")]
    if not stem or stem[0] not in "abcdefghijklmnopqrstuvwxyz":
        return False
    return all(c in "abcdefghijklmnopqrstuvwxyz0123456789_" for c in stem)


def _boundary_layout_census(scripts_dir: str) -> list[str]:
    """ADR-0001 runtime layout census (pass 1): os/sys only, fail-closed.

    Enforces every structural rule and RETURNS the inert-suffix files (no .py,
    no forbidden loader/archive suffix) for the pass-2 content check. Mirrors
    the Gate-2 authoring census (tests/check_import_closure.py) minus
    closure/inventory equality, which stays an authoring-gate concern: a flat
    conforming uninventoried module is inert here because production code
    contains no dynamic-import machinery and the orchestrator platform-hashes
    every method surface before trusting results.
    """
    if os.path.islink(scripts_dir):
        _boundary_refuse(
            "scripts/ itself must be a real directory, not a symlink (ADR-0001)",
            scripts_dir,
        )
    allowed_dirs = set(_BOUNDARY_POLICY["allowed-data-dirs"])
    inert: list[str] = []
    for dirpath, dirnames, filenames in os.walk(scripts_dir, followlinks=False):
        for name in sorted(dirnames):
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                _boundary_refuse(
                    "symlinks are forbidden anywhere under scripts/ (ADR-0001)", path
                )
            if name == "__pycache__":
                _boundary_refuse(
                    "__pycache__ is forbidden under scripts/ (ADR-0001)", path
                )
            top = os.path.relpath(path, scripts_dir).split(os.sep)[0]
            if top not in allowed_dirs:
                _boundary_refuse(
                    "directories under scripts/ are forbidden outside the "
                    f"declared data allowlist {sorted(allowed_dirs)} (ADR-0001)",
                    path,
                )
        for name in sorted(filenames):
            path = os.path.join(dirpath, name)
            if os.path.islink(path):
                _boundary_refuse(
                    "symlinks are forbidden anywhere under scripts/ (ADR-0001)", path
                )
            if name == "__pycache__":
                _boundary_refuse(
                    "__pycache__ is forbidden under scripts/ (ADR-0001)", path
                )
            if not os.path.isfile(path):
                _boundary_refuse("unsupported filesystem object under scripts/", path)
            lower = name.lower()
            if lower.endswith(".py"):
                if dirpath != scripts_dir:
                    _boundary_refuse(
                        "production Python must be flat in scripts/ (ADR-0001)", path
                    )
                if name != _BOUNDARY_POLICY[
                    "entrypoint"
                ] and not _boundary_module_name_conforms(name):
                    _boundary_refuse(
                        "production module name must match _deliberate_<domain>.py "
                        "(ADR-0001 naming rule)",
                        path,
                    )
                continue
            if any(lower.endswith(suffix) for suffix in _BOUNDARY_FORBIDDEN_SUFFIXES):
                _boundary_refuse(
                    "importable non-source artifact is forbidden under scripts/ "
                    "(ADR-0001)",
                    path,
                )
            inert.append(path)
    return inert


_boundary_scripts_dir = os.path.dirname(os.path.abspath(__file__))
_boundary_inert_files = _boundary_layout_census(_boundary_scripts_dir)

import atexit  # noqa: E402 — deferred by design: imports wait for pass 1
import shutil  # noqa: E402
import tempfile  # noqa: E402


def _boundary_protected_root(scripts_dir: str) -> str:
    """Outermost Git root containing the skill, or skill root if standalone."""
    skill_root = os.path.realpath(os.path.dirname(scripts_dir))
    protected_root = skill_root
    cursor = skill_root
    while True:
        if os.path.exists(os.path.join(cursor, ".git")):
            protected_root = cursor
        parent = os.path.dirname(cursor)
        if parent == cursor:
            return protected_root
        cursor = parent


def _boundary_path_is_within(path: str, root: str) -> bool:
    """Containment by filesystem identity; comparison errors are unsafe."""
    real_root = os.path.realpath(root)
    cursor = os.path.realpath(path)
    while True:
        try:
            if os.path.samefile(cursor, real_root):
                return True
        except OSError:
            return True
        parent = os.path.dirname(cursor)
        if parent == cursor:
            return False
        cursor = parent


# Fresh, initially empty (mkdtemp), invocation-private (0o700), under the
# process temp root but mechanically outside the repository (or outside the
# served skill root when no Git root is present), retired at exit, never reused
# across invocations (ADR-0001). A temp root inside the protected source tree —
# directly, through a symlink, or through a case alias — refuses BEFORE prefix
# creation. Containment compares filesystem identity, not path-string casing;
# errors are unsafe. The created prefix is resolved and checked again before
# assignment, closing a symlink swap between selection and creation.
# Redirecting alone is insufficient — pass 1 above is what stops directly-read
# sourceless bytecode.
_boundary_source_root = _boundary_protected_root(_boundary_scripts_dir)
_boundary_temp_root = os.path.realpath(tempfile.gettempdir())
if _boundary_path_is_within(_boundary_temp_root, _boundary_source_root):
    _boundary_refuse(
        "cache temp root must resolve outside the repository or served skill "
        "root (ADR-0001)",
        _boundary_temp_root,
    )
_boundary_cache_prefix = os.path.realpath(
    tempfile.mkdtemp(prefix="deliberate-pycache-", dir=_boundary_temp_root)
)
if _boundary_path_is_within(_boundary_cache_prefix, _boundary_source_root):
    shutil.rmtree(_boundary_cache_prefix, ignore_errors=True)
    _boundary_refuse(
        "created cache prefix must resolve outside the repository or served "
        "skill root (ADR-0001)",
        _boundary_cache_prefix,
    )
sys.pycache_prefix = _boundary_cache_prefix
atexit.register(shutil.rmtree, sys.pycache_prefix, ignore_errors=True)

# Pass 2: pass 1 refused every importable shadow, so importing zipfile (which
# reads archives; zipimport, banned, loads them) cannot resolve to a scripts/
# file. is_zipfile locates the trailing end-of-central-directory record the way
# zipimport does, catching a prefixed/self-extracting zip a magic sniff misses.
# An inert file the census cannot open refuses rather than passing: because
# is_zipfile swallows OSError into False, this pass opens each file itself and
# refuses on an open failure — unverifiable content is unsafe, the same
# errors-are-unsafe posture the containment check above holds. A read-time
# OSError raised inside is_zipfile after a successful open still collapses to
# False; that residual sliver is accepted and shared by both consumers.
import zipfile  # noqa: E402 — safe only after pass 1 cleared every importable shadow

for _inert_path in _boundary_inert_files:
    try:
        with open(_inert_path, "rb") as _inert_handle:
            if zipfile.is_zipfile(_inert_handle):
                _boundary_refuse(
                    "file is a valid zip archive despite an inert suffix (ADR-0001) "
                    "— a disguised or prefixed archive on sys.path imports as code "
                    "through zipimport",
                    _inert_path,
                )
    except OSError:
        _boundary_refuse(
            "inert file under scripts/ could not be read for the structural "
            "archive check (ADR-0001) — unverifiable content is unsafe",
            _inert_path,
        )

import argparse  # noqa: E402
import copy  # noqa: E402
import hashlib  # noqa: E402
import re  # noqa: E402
import stat  # noqa: E402
import subprocess  # noqa: E402
from pathlib import Path  # noqa: E402
from typing import Any  # noqa: E402

from _deliberate_shared import (  # noqa: E402
    ReadSet,
    Refusal,
    StoreReadLoss,
    ValidationFailure,
    _decode_utf8,
    dump_yaml,
    fail,
    refuse,
    safe_parse,
)

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_REFUSE = 2
EXIT_STORE_READ = 4

ENVELOPE_SCHEMA = "deliberate-envelope/v1"
SETUP_SCHEMA = "deliberate-setup/v1"
RUNSTATE_SCHEMA = "deliberate-runstate/v1"
CAPSULE_SCHEMA = "deliberate-capsule/v1"
PINS_NOT_PRODUCED = "not produced: pins not written"


# ---------------------------------------------------------------------------
# Canonical data
# ---------------------------------------------------------------------------


def _contract_string_list(
    op: str, mapping: dict, key: str, *, allow_empty: bool = False
) -> list[str]:
    value = mapping.get(key)
    if not isinstance(value, list) or not all(
        isinstance(entry, str) and entry.strip() for entry in value
    ):
        raise refuse(op, f"{key} must be a list of non-empty strings", value)
    if not allow_empty and not value:
        raise refuse(op, f"{key} must not be empty")
    if len(value) != len(set(value)):
        raise refuse(op, f"{key} must not contain duplicates", value)
    return value


def validate_contract_data(data: object) -> None:
    """Refuse internally inconsistent canonical data before validating a run."""
    op = "contract data"
    top_keys = {
        "contract-data-version",
        "stages",
        "validation",
        "packet-items",
        "bounds",
        "import-boundary",
        "obliged-artifacts",
        "artifact-shapes",
        "record-keys",
        "schemas",
        "stage-brief-template",
        "brief-extras",
    }
    if not isinstance(data, dict) or set(data) != top_keys:
        raise refuse(op, f"top-level keys must be exactly {sorted(top_keys)}", data)
    if data["contract-data-version"] != 6:
        raise refuse(
            op,
            "unsupported contract-data-version",
            data["contract-data-version"],
        )

    stages = _contract_string_list(op, data, "stages")
    validation = data["validation"]
    validation_keys = {
        "provenance-flags",
        "provenance-labels",
        "authority-note-provenance",
        "constituent-names",
        "encounter-kinds",
        "field-modes",
        "closed-field-bases",
        "capsule-carriers",
        "field-order-origins",
        "order-origin-labels",
        "method-pin-frontiers",
        "method-surfaces",
        "directive-action-kinds",
        "capsule-terminal-classes",
        "constituent-exit-terminal-prefix",
        "constituent-exit-stages",
        "insertion-values",
        "prune-bases",
        "recommend-bases",
        "generic-write-kinds",
        "reserved-write-kinds",
        "runstate-writers",
        "failure-terminals",
        "receipt-only-terminals",
        "capsule-forbidden-terminals",
        "echo-contract-fields",
        "capsule-contract-fields",
        "proof-boundary-keys",
    }
    if not isinstance(validation, dict) or set(validation) != validation_keys:
        raise refuse(
            op,
            f"validation keys must be exactly {sorted(validation_keys)}",
            validation,
        )
    list_keys = validation_keys - {
        "order-origin-labels",
        "method-pin-frontiers",
        "capsule-terminal-classes",
        "constituent-exit-terminal-prefix",
        "runstate-writers",
    }
    for key in sorted(list_keys):
        _contract_string_list(op, validation, key)

    origins = set(validation["field-order-origins"])
    labels = validation["order-origin-labels"]
    if (
        not isinstance(labels, dict)
        or set(labels) != origins
        or not all(
            isinstance(label, str) and label.strip() for label in labels.values()
        )
    ):
        raise refuse(
            op,
            "order-origin-labels must map every field-order-origin to non-empty text",
            labels,
        )

    method_frontiers = validation["method-pin-frontiers"]
    if (
        not isinstance(method_frontiers, dict)
        or set(method_frontiers) != {"default", "references/methods.md"}
        or not all(stage in stages for stage in method_frontiers.values())
    ):
        raise refuse(
            op,
            "method-pin-frontiers must map default and references/methods.md to declared stages",
            method_frontiers,
        )

    method_surfaces = validation["method-surfaces"]
    if len(method_surfaces) != len(set(method_surfaces)) or not set(
        method_frontiers
    ) - {"default"} <= set(method_surfaces):
        raise refuse(
            op,
            "method-surfaces must be unique and cover every non-default frontier key",
            method_surfaces,
        )

    if set(validation["constituent-exit-stages"]) - set(stages):
        raise refuse(
            op,
            "constituent-exit-stages must name declared stages",
            validation["constituent-exit-stages"],
        )
    exit_prefix = validation["constituent-exit-terminal-prefix"]
    if not isinstance(exit_prefix, str) or not exit_prefix.strip():
        raise refuse(
            op, "constituent-exit-terminal-prefix must be non-empty", exit_prefix
        )

    terminal_classes = validation["capsule-terminal-classes"]
    if not isinstance(terminal_classes, list) or not terminal_classes:
        raise refuse(
            op, "capsule-terminal-classes must be a non-empty list", terminal_classes
        )
    class_terminals: list[str] = []
    for entry in terminal_classes:
        if not isinstance(entry, dict) or set(entry) != {
            "terminal",
            "match",
            "frontier",
        }:
            raise refuse(
                op,
                "each capsule terminal class must be exactly {terminal, match, frontier}",
                entry,
            )
        if not isinstance(entry["terminal"], str) or not entry["terminal"].strip():
            raise refuse(op, "terminal class name must be non-empty", entry)
        if entry["match"] not in {"exact", "prefix"}:
            raise refuse(op, "terminal class match must be exact or prefix", entry)
        if entry["frontier"] != "complete" and entry["frontier"] not in stages:
            raise refuse(
                op, "terminal class frontier must be `complete` or a stage", entry
            )
        class_terminals.append(entry["terminal"])
    if len(class_terminals) != len(set(class_terminals)):
        raise refuse(op, "terminal class names must be unique", class_terminals)

    bounds = data["bounds"]
    if (
        not isinstance(bounds, dict)
        or not bounds
        or not all(
            isinstance(name, str)
            and isinstance(value, int)
            and not isinstance(value, bool)
            and value > 0
            for name, value in bounds.items()
        )
    ):
        raise refuse(op, "bounds must be a non-empty map of positive integers", bounds)

    items = data["packet-items"]
    if not isinstance(items, list) or not items:
        raise refuse(op, "packet-items must be a non-empty list", items)
    item_keys: list[str] = []
    for item in items:
        if not isinstance(item, dict) or set(item) != {"key", "label", "matrix"}:
            raise refuse(
                op, "each packet item must be exactly {key, label, matrix}", item
            )
        if not isinstance(item["key"], str) or not item["key"].strip():
            raise refuse(op, "packet item key must be non-empty", item["key"])
        if not isinstance(item["label"], str) or not item["label"].strip():
            raise refuse(op, "packet item label must be non-empty", item["label"])
        if not isinstance(item["matrix"], dict) or set(item["matrix"]) != set(stages):
            raise refuse(op, "every packet matrix row must cover every stage", item)
        for cell in item["matrix"].values():
            if not isinstance(cell, dict) or set(cell) not in (
                {"status"},
                {"status", "qualifier"},
            ):
                raise refuse(op, "packet matrix cells have an invalid shape", cell)
            if cell["status"] not in {"include", "withhold"}:
                raise refuse(op, "packet matrix status is invalid", cell["status"])
            if "qualifier" in cell and (
                not isinstance(cell["qualifier"], str) or not cell["qualifier"].strip()
            ):
                raise refuse(op, "packet matrix qualifier must be non-empty", cell)
        item_keys.append(item["key"])
    if len(item_keys) != len(set(item_keys)):
        raise refuse(op, "packet item keys must be unique", item_keys)

    obliged = data["obliged-artifacts"]
    if not isinstance(obliged, dict) or set(obliged) != set(stages):
        raise refuse(op, "obliged-artifacts must cover every stage exactly", obliged)
    for stage, entries in obliged.items():
        if not isinstance(entries, list) or not entries:
            raise refuse(
                op, f"obliged artifacts for {stage} must be non-empty", entries
            )
        keys: list[str] = []
        for entry in entries:
            if not isinstance(entry, dict) or set(entry) != {
                "key",
                "required",
                "shape",
            }:
                raise refuse(op, "obliged artifact row has an invalid shape", entry)
            if entry["required"] not in {"always", "conditional"}:
                raise refuse(op, "obliged artifact required class is invalid", entry)
            keys.append(entry["key"])
        if len(keys) != len(set(keys)):
            raise refuse(op, f"obliged artifact keys for {stage} must be unique", keys)

    record_keys = data["record-keys"]
    if not isinstance(record_keys, list) or not record_keys:
        raise refuse(op, "record-keys must be a non-empty list", record_keys)
    record_names = [
        entry.get("key") for entry in record_keys if isinstance(entry, dict)
    ]
    if len(record_names) != len(record_keys) or len(record_names) != len(
        set(record_names)
    ):
        raise refuse(
            op, "record key rows must be mappings with unique keys", record_keys
        )
    cut_basis = next(
        (entry for entry in record_keys if entry.get("key") == "cut-basis"), None
    )
    declared_bases = set(validation["prune-bases"]) | set(validation["recommend-bases"])
    if (
        not isinstance(cut_basis, dict)
        or set(cut_basis.get("enum", [])) != declared_bases
        or set(validation["prune-bases"]) & set(validation["recommend-bases"])
    ):
        raise refuse(
            op,
            "Prune and Recommend basis sets must be disjoint and exactly equal the cut-basis enum",
            cut_basis,
        )

    schemas = data["schemas"]
    if not isinstance(schemas, dict) or set(schemas) != {
        SETUP_SCHEMA,
        ENVELOPE_SCHEMA,
        RUNSTATE_SCHEMA,
        CAPSULE_SCHEMA,
    }:
        raise refuse(
            op, "schemas must define the four supported document schemas", schemas
        )
    setup = schemas[SETUP_SCHEMA]
    if not isinstance(setup, dict) or set(setup) != {"keys"}:
        raise refuse(op, "setup schema must define keys", setup)
    runstate = schemas[RUNSTATE_SCHEMA]
    if not isinstance(runstate, dict) or set(runstate) != {"keys", "body-keys"}:
        raise refuse(op, "run-state schema must define keys and body-keys", runstate)
    kind_row = next(
        (
            entry
            for entry in runstate["keys"]
            if isinstance(entry, dict) and entry.get("key") == "kind"
        ),
        None,
    )
    schema_kinds = (
        set(kind_row.get("enum", [])) if isinstance(kind_row, dict) else set()
    )
    generic = set(validation["generic-write-kinds"])
    reserved = set(validation["reserved-write-kinds"])
    writers = validation["runstate-writers"]
    if generic & reserved or generic | reserved != schema_kinds:
        raise refuse(
            op,
            "generic and reserved writer kinds must disjointly partition run-state kinds",
            {
                "generic": sorted(generic),
                "reserved": sorted(reserved),
                "schema": sorted(schema_kinds),
            },
        )
    if not isinstance(writers, dict) or set(writers) != schema_kinds:
        raise refuse(
            op, "runstate-writers must cover every run-state kind exactly", writers
        )
    for kind, writer_names in writers.items():
        if (
            not isinstance(writer_names, list)
            or not writer_names
            or not all(isinstance(name, str) and name.strip() for name in writer_names)
            or len(writer_names) != len(set(writer_names))
        ):
            raise refuse(
                op, f"writers for {kind} must be unique non-empty names", writer_names
            )
    if any("write-item" not in writers[kind] for kind in generic) or any(
        "write-item" in writers[kind] for kind in reserved
    ):
        raise refuse(
            op, "generic writer ownership disagrees with generic-write-kinds", writers
        )

    capsule = schemas[CAPSULE_SCHEMA]
    capsule_keys = [
        entry.get("key") for entry in capsule.get("keys", []) if isinstance(entry, dict)
    ]
    if len(capsule_keys) != len(set(capsule_keys)):
        raise refuse(op, "capsule schema keys must be unique", capsule_keys)
    if not set(validation["echo-contract-fields"]).issubset(
        set(validation["capsule-contract-fields"])
    ):
        raise refuse(
            op, "echo-contract-fields must be a subset of capsule-contract-fields"
        )

    boundary = data["import-boundary"]
    boundary_keys = {
        "entrypoint",
        "module-name-pattern",
        "allowed-data-dirs",
        "forbidden-loader-suffixes",
        "archive-suffixes",
        "banned-identifiers",
    }
    if not isinstance(boundary, dict) or set(boundary) != boundary_keys:
        raise refuse(
            op,
            f"import-boundary keys must be exactly {sorted(boundary_keys)}",
            boundary,
        )
    for key in ("entrypoint", "module-name-pattern"):
        if not isinstance(boundary[key], str) or not boundary[key].strip():
            raise refuse(
                op, f"import-boundary {key} must be a non-empty string", boundary[key]
            )
    for key in sorted(boundary_keys - {"entrypoint", "module-name-pattern"}):
        _contract_string_list(op, boundary, key)


class Contract:
    def __init__(self, data: dict, data_path: Path) -> None:
        self.data = data
        self.data_path = data_path
        self.stages: list[str] = data["stages"]
        self.items: list[dict] = data["packet-items"]
        self.bounds: dict = data["bounds"]
        self.obliged: dict = data["obliged-artifacts"]
        self.record_keys: list[dict] = data["record-keys"]
        self.schemas: dict = data["schemas"]
        validation = data["validation"]
        self.provenance_flags = set(validation["provenance-flags"])
        self.provenance_labels = set(validation["provenance-labels"])
        self.authority_note_provenance = set(validation["authority-note-provenance"])
        self.constituent_names = set(validation["constituent-names"])
        self.encounter_kinds = set(validation["encounter-kinds"])
        self.field_modes = set(validation["field-modes"])
        self.closed_field_bases = set(validation["closed-field-bases"])
        self.capsule_carriers = set(validation["capsule-carriers"])
        self.field_order_origins = set(validation["field-order-origins"])
        self.order_origin_labels: dict[str, str] = validation["order-origin-labels"]
        self.method_pin_frontiers: dict[str, str] = validation["method-pin-frontiers"]
        self.method_surfaces: list[str] = validation["method-surfaces"]
        self.directive_action_kinds = set(validation["directive-action-kinds"])
        self.capsule_terminal_classes: list[dict] = validation[
            "capsule-terminal-classes"
        ]
        self.constituent_exit_prefix: str = validation[
            "constituent-exit-terminal-prefix"
        ]
        self.constituent_exit_stages = set(validation["constituent-exit-stages"])
        self.insertion_values = set(validation["insertion-values"])
        self.prune_bases = set(validation["prune-bases"])
        self.recommend_bases = set(validation["recommend-bases"])
        self.generic_write_kinds = set(validation["generic-write-kinds"])
        self.reserved_write_kinds = set(validation["reserved-write-kinds"])
        self.runstate_writers = {
            kind: set(writers)
            for kind, writers in validation["runstate-writers"].items()
        }
        self.failure_terminals = tuple(validation["failure-terminals"])
        self.receipt_only_terminals = tuple(validation["receipt-only-terminals"])
        self.capsule_forbidden_terminals = tuple(
            validation["capsule-forbidden-terminals"]
        )
        self.echo_contract_fields: list[str] = validation["echo-contract-fields"]
        self.capsule_contract_fields: list[str] = validation["capsule-contract-fields"]
        self.proof_boundary_keys = set(validation["proof-boundary-keys"])

    def item(self, key: str) -> dict:
        for entry in self.items:
            if entry["key"] == key:
                return entry
        raise refuse("matrix lookup", f"unknown packet item: {key}")

    def cell(self, item_key: str, stage: str) -> dict:
        return self.item(item_key)["matrix"][stage]

    def include_column(self, stage: str) -> list[dict]:
        return [e for e in self.items if e["matrix"][stage]["status"] == "include"]


def _require_boundary_match(data: dict) -> None:
    """Refuse when the contract's import-boundary differs from the embedded census policy.

    The runtime census (module top) consumes only the embedded values, so this
    comparison is what proves — at every invocation — that the embedded
    rendering matches the authenticated policy source (ADR-0001 amendment):
    the runtime never reads an unpinned policy reference as authority.
    """
    boundary = data["import-boundary"]
    for key, embedded in _BOUNDARY_POLICY.items():
        if boundary[key] != embedded:
            raise refuse(
                "contract data",
                f"import-boundary {key} differs from the entrypoint's embedded "
                "census policy (ADR-0001) — the embedded rendering must match "
                "the authenticated contract",
                boundary[key],
            )


def load_contract(data_path: Path, readset: ReadSet) -> Contract:
    readset.allow(data_path)
    raw = readset.read_bytes(data_path)
    parsed = safe_parse(raw, byte_cap=4 * 1024 * 1024, depth_cap=48, op="contract data")
    validate_contract_data(parsed)
    _require_boundary_match(parsed)
    return Contract(parsed, Path(os.path.realpath(data_path)))


# ---------------------------------------------------------------------------
# Content identity
# ---------------------------------------------------------------------------


def sha256_bytes(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def _is_sha256(value: object) -> bool:
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def _hash_regular_file(
    path: Path, readset: ReadSet, *, byte_cap: int | None = None
) -> tuple[str, int]:
    """Hash one authorized regular file without reading past a declared cap."""
    canonical = readset.check(path)
    digest = hashlib.sha256()
    total = 0
    with canonical.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            total += len(chunk)
            if byte_cap is not None and total > byte_cap:
                raise refuse(
                    "identity",
                    f"content read exceeded the remaining {byte_cap}-byte bound: {path}",
                )
            digest.update(chunk)
    return digest.hexdigest(), total


def _plan_identity_path(path: Path, contract: Contract, readset: ReadSet) -> dict:
    """Expand and size one identity path without reading content bytes."""
    canonical = Path(os.path.realpath(path))
    readset.check(canonical)
    if not canonical.exists():
        raise fail("identity", f"path does not resolve: {path}")
    mode = canonical.stat().st_mode
    if stat.S_ISREG(mode):
        return {
            "path": str(path),
            "kind": "file",
            "files": [(None, canonical)],
            "expanded-bytes": canonical.stat().st_size,
        }
    if stat.S_ISDIR(mode):
        cap = contract.bounds["directory-expansion-max-descendants"]
        entries: list[tuple[str, Path]] = []
        for root, dirs, files in os.walk(canonical, followlinks=False):
            for name in dirs:
                child_dir = Path(root) / name
                rel = child_dir.relative_to(canonical).as_posix()
                if child_dir.is_symlink():
                    raise fail("identity", f"symlinked descendant is unpinnable: {rel}")
            dirs.sort()
            for name in sorted(files):
                child = Path(root) / name
                rel = child.relative_to(canonical).as_posix()
                if child.is_symlink():
                    raise fail("identity", f"symlinked descendant is unpinnable: {rel}")
                if not stat.S_ISREG(child.stat().st_mode):
                    raise fail(
                        "identity", f"non-regular descendant is unpinnable: {rel}"
                    )
                entries.append((rel, child))
        entries.sort(key=lambda pair: pair[0])
        if len(entries) > cap:
            raise refuse(
                "identity",
                f"directory expands to {len(entries)} descendants, past the cap of {cap}: {path}",
            )
        return {
            "path": str(path),
            "kind": "directory",
            "files": entries,
            "expanded-bytes": sum(child.stat().st_size for _, child in entries),
        }
    raise fail(
        "identity",
        f"path is neither a regular file nor a directory — unpinnable: {path}",
    )


def _materialize_identity_plan(
    plan: dict, readset: ReadSet, *, byte_cap: int | None = None
) -> tuple[dict, int]:
    """Hash a pre-sized plan, retaining a streaming cap against growth races."""
    manifest = []
    actual_bytes = 0
    for relpath, child in plan["files"]:
        remaining = None if byte_cap is None else byte_cap - actual_bytes
        content_id, child_bytes = _hash_regular_file(child, readset, byte_cap=remaining)
        actual_bytes += child_bytes
        if relpath is None:
            return {"path": plan["path"], "id": content_id}, actual_bytes
        manifest.append({"relpath": relpath, "id": content_id})
    return {"path": plan["path"], "manifest": manifest}, actual_bytes


def identity_of_path(
    path: Path,
    contract: Contract,
    readset: ReadSet,
    *,
    byte_cap: int | None = None,
) -> tuple[dict, int]:
    """Size before hashing, then return one path's content identity and bytes."""
    plan = _plan_identity_path(path, contract, readset)
    if byte_cap is not None and plan["expanded-bytes"] > byte_cap:
        raise refuse(
            "identity",
            f"identity input expands to {plan['expanded-bytes']} bytes, past the {byte_cap}-byte bound: {path}",
        )
    return _materialize_identity_plan(plan, readset, byte_cap=byte_cap)


def cmd_identity(args: argparse.Namespace) -> int:
    readset = ReadSet()
    contract = load_contract(Path(args.data), readset)
    plans = []
    for raw_path in args.paths:
        path = Path(raw_path)
        readset.allow(path)
        plans.append(_plan_identity_path(path, contract, readset))
    if args.as_in_packet and any(plan["kind"] != "file" for plan in plans):
        raise refuse(
            "identity",
            "--as-in-packet accepts only exact serialized payload files, never directories",
        )
    total_planned = sum(plan["expanded-bytes"] for plan in plans)
    if args.as_evidence:
        cap = contract.bounds["named-evidence-expanded-bytes"]
        bound_name = "named-evidence-expanded-bytes"
    elif args.as_in_packet:
        cap = contract.bounds["in-packet-evidence-bytes"]
        bound_name = "in-packet-evidence-bytes"
    else:
        cap = None
        bound_name = None
    if cap is not None and total_planned > cap:
        raise refuse(
            "identity",
            f"identity set expands to {total_planned} bytes, past the {cap}-byte {bound_name} bound",
        )
    results = []
    total_bytes = 0
    for plan in plans:
        remaining = None if cap is None else cap - total_bytes
        entry, expanded_bytes = _materialize_identity_plan(
            plan, readset, byte_cap=remaining
        )
        total_bytes += expanded_bytes
        if cap is not None:
            entry["bytes"] = expanded_bytes
        results.append(entry)
    sys.stdout.write(dump_yaml({"identities": results, "total-bytes": total_bytes}))
    return EXIT_PASS


# ---------------------------------------------------------------------------
# Run-state store
# ---------------------------------------------------------------------------


def _normalize_proof_store_path(
    op: str,
    body: dict,
    store_root: Path,
) -> dict:
    normalized = copy.deepcopy(body)
    supplied_root = Path(os.path.realpath(normalized["store-path"]))
    if supplied_root != store_root:
        raise fail(op, "store path differs from the live store root")
    normalized["store-path"] = str(store_root)
    return normalized


class Store:
    def __init__(self, root: Path, contract: Contract, readset: ReadSet) -> None:
        self.root = Path(os.path.realpath(root))
        self.contract = contract
        self.readset = readset
        readset.allow(self.root)

    def _files(self) -> list[Path]:
        if not self.root.is_dir():
            raise StoreReadLoss(
                f"store read failed: store root is not a directory: {self.root}"
            )
        return sorted(p for p in self.root.iterdir() if p.suffix == ".yaml")

    def items(self) -> list[dict]:
        out = []
        for path in self._files():
            raw = self.readset.read_bytes(path)
            parsed = safe_parse(
                raw,
                byte_cap=self.contract.bounds["parse-bytes"],
                depth_cap=self.contract.bounds["parse-depth"],
                op=f"run-state item {path.name}",
            )
            validate_runstate_item(parsed, self.contract)
            out.append(parsed)
        out.sort(key=lambda item: item["seq"])
        return out

    def find(self, kind: str, stage: str | None = None) -> list[dict]:
        return [
            i
            for i in self.items()
            if i["kind"] == kind and (stage is None or i.get("stage") == stage)
        ]

    def require(self, kind: str, stage: str | None = None) -> dict:
        found = self.find(kind, stage)
        if not found:
            where = f"{kind}" + (f" for stage {stage}" if stage else "")
            raise StoreReadLoss(
                f"store read failed: required run-state item absent: {where}"
            )
        return found[-1]

    def next_seq(self) -> int:
        existing = self.items()
        return (max(i["seq"] for i in existing) + 1) if existing else 0

    def write(self, item: dict, *, writer: str) -> Path:
        validate_runstate_item(item, self.contract)
        kind = item["kind"]
        allowed_writers = self.contract.runstate_writers.get(kind, set())
        if writer not in allowed_writers:
            raise refuse(
                "store write",
                f"run-state kind {kind!r} is reserved; writer {writer!r} is not one of {sorted(allowed_writers)}",
            )
        if self.find("capsule-progress"):
            raise refuse("store write", "accepted capsule-progress seals the run state")
        if self.find("terminal-state") and kind != "capsule-progress":
            raise refuse(
                "store write",
                "terminal-state seals the run except for one capsule-progress acceptance",
            )
        expected_seq = self.next_seq()
        if item["seq"] != expected_seq:
            raise fail(
                "store write",
                f"item seq must equal the next append position {expected_seq}",
                item["seq"],
            )
        unique_kinds = {
            "echo",
            "decomposition",
            "pins",
            "terminal-claim",
            "proof-inputs",
            "terminal-state",
            "capsule-progress",
            "capsule-import",
            "restart-plan",
        }
        if kind in unique_kinds and self.find(kind):
            raise refuse("store write", f"{kind} already recorded for this run")
        if kind in {"envelope", "brief-render"} and self.find(kind, item["stage"]):
            raise refuse(
                "store write",
                f"{kind} already recorded for stage {item['stage']}",
            )
        if kind == "envelope":
            stage = item["stage"]
            if not self.find("brief-render", stage):
                raise StoreReadLoss(
                    f"store read failed: no recorded brief-render before envelope for stage {stage}"
                )
            owed = validate_envelope_against_store(
                item["body"]["document"], self, self.contract
            )
            if item["body"]["amendments"] != owed:
                raise fail(
                    "store write",
                    "envelope amendments do not equal the store-aware acceptance result",
                    item["body"]["amendments"],
                )
        elif kind == "decomposition":
            echo = self.require("echo")["body"]
            expected = _decomposition_from_echo(echo, self.contract)
            if item["body"] != expected:
                raise fail(
                    "store write",
                    "decomposition differs from the helper-normalized store echo",
                    item["body"],
                )
        elif kind == "pins":
            if not self.find("decomposition"):
                raise StoreReadLoss(
                    "store read failed: pins require a stored setup decomposition"
                )
        elif kind == "terminal-claim":
            _validate_terminal_claim_against_store(item["body"], self)
        elif kind == "proof-inputs":
            pins = self.require("pins")["body"]
            op = "proof inputs" if writer == "record-proof-inputs" else "store write"
            body = _normalize_proof_store_path(op, item["body"], self.root)
            item = copy.deepcopy(item)
            item["body"] = body
            if body["constituent-pins"] != pins["constituents"]:
                raise fail(
                    "store write",
                    "proof-input constituent pins differ from the store pins item",
                )
            if body["method-identity"] != pins["method"]:
                raise fail(
                    "store write",
                    "proof-input method identity differs from the store pins item",
                )
        elif kind == "terminal-state":
            if not self.find("proof-inputs"):
                raise StoreReadLoss(
                    "store read failed: proof-inputs must precede terminal-state"
                )
            terminal_claims = self.find("terminal-claim")
            if (
                terminal_claims
                and terminal_claims[-1]["body"]["terminal"] != item["body"]["terminal"]
            ):
                raise fail(
                    "store write",
                    "terminal-state differs from the stored terminal-claim",
                    item["body"]["terminal"],
                )
        elif kind == "capsule-progress":
            validate_capsule_against_store(item["body"]["capsule"], self, self.contract)
        elif kind == "capsule-import" and self.find("restart-plan"):
            raise refuse(
                "store write", "capsule-import cannot be replaced after restart-plan"
            )
        elif kind == "restart-plan" and not self.find("capsule-import"):
            raise StoreReadLoss(
                "store read failed: restart-plan requires a preceding capsule-import"
            )
        echoes = [i for i in self.items() if i["kind"] == "echo"]
        if item["kind"] == "echo":
            if echoes:
                raise refuse(
                    "store write", "echo item already present; one echo per store"
                )
            if item["seq"] != 0:
                raise refuse(
                    "store write",
                    "the echo item must be seq 0, the store's first write",
                )
        else:
            if not echoes:
                raise StoreReadLoss(
                    "store read failed: no echo item; store was never initialized"
                )
            if item["run"] != echoes[0]["run"]:
                raise fail(
                    "store write",
                    f"run identifier mismatch: item {item['run']!r} vs echo {echoes[0]['run']!r}",
                )
        name = f"{item['seq']:03d}-{item['kind']}"
        if item.get("stage"):
            name += f"-{item['stage']}"
        path = self.root / f"{name}.yaml"
        if path.exists():
            raise fail("store write", f"item file already exists: {path.name}")
        tmp = path.with_suffix(".tmp")
        tmp.write_bytes(dump_yaml(item).encode("utf-8"))
        os.replace(tmp, path)
        return path


def _require_str(op: str, name: str, value: object) -> None:
    if not isinstance(value, str) or not value.strip():
        raise fail(op, f"{name} must be a non-empty string", value)


def _matches_terminal_class(terminal: str, patterns: tuple[str, ...]) -> bool:
    return any(
        terminal.startswith(pattern) if pattern.endswith(":") else terminal == pattern
        for pattern in patterns
    )


def _is_failure_terminal(terminal: str, contract: Contract) -> bool:
    return _matches_terminal_class(terminal, contract.failure_terminals)


def _is_capsule_forbidden_terminal(terminal: str, contract: Contract) -> bool:
    return _matches_terminal_class(
        terminal,
        contract.receipt_only_terminals + contract.capsule_forbidden_terminals,
    )


def _normalize_locator(locator: str) -> str:
    return locator.replace("\\", "/").removeprefix("./")


def _capsule_terminal_frontier(terminal: str, contract: Contract, op: str) -> str:
    """Classify a non-failure capsule-bearing terminal against the canonical
    class table and return its artifact frontier (a stage name, or `complete`).
    A terminal outside every canonical class and the constituent-exit form is
    refused, never accepted as free-form authority."""
    for entry in contract.capsule_terminal_classes:
        name = entry["terminal"]
        matched = (
            terminal.startswith(name)
            if entry["match"] == "prefix"
            else terminal == name
        )
        if matched:
            return entry["frontier"]
    prefix = contract.constituent_exit_prefix
    if terminal.startswith(prefix):
        stage, sep, exit_name = terminal.removeprefix(prefix).partition(":")
        stage = stage.strip()
        if sep != ":" or not exit_name.strip() or stage not in contract.stages:
            raise refuse(
                op,
                f"malformed constituent-exit terminal — expected `{prefix}<stage>: <named exit>`",
            )
        if stage not in contract.constituent_exit_stages:
            raise refuse(
                op,
                f"constituent exit at {stage} has no capsule-bearing state — echo-only branch",
            )
        return stage
    raise refuse(
        op,
        f"terminal {terminal!r} matches no canonical capsule terminal class, failure terminal, or constituent-exit form",
    )


def _require_str_list(op: str, name: str, value: object) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(entry, str) and entry.strip() for entry in value
    ):
        raise fail(op, f"{name} must be a list of non-empty strings", value)
    return value


def _canonical_wording(text: str) -> str:
    """Canonical whitespace form for option wordings: internal whitespace runs
    (newlines included) collapse to one space, ends trimmed. Applied exactly
    once, at identity ingress — init-setup candidates and fresh Generate
    outputs — never at comparison time: every downstream comparison stays
    byte-exact, so whitespace-equivalence can never stand in for identity."""
    return " ".join(text.split())


def _canonicalize_setup_wordings(source: object) -> object:
    """The init-setup ingress rule: candidate wordings and the soft-preference
    entries naming them are canonicalized here, before validation, so duplicate
    detection runs post-normalization and the stored bytes are the identity
    every later surface must match exactly. Malformed shapes pass through for
    the shape checks to reject with their own messages."""
    if not isinstance(source, dict):
        return source
    candidates = source.get("candidates")
    if isinstance(candidates, list):
        for candidate in candidates:
            if isinstance(candidate, dict) and isinstance(
                candidate.get("wording"), str
            ):
                candidate["wording"] = _canonical_wording(candidate["wording"])
    preferences = source.get("soft-preferences")
    if isinstance(preferences, dict) and isinstance(preferences.get("entries"), list):
        for entry in preferences["entries"]:
            if (
                isinstance(entry, dict)
                and isinstance(entry.get("candidate"), str)
                and entry["candidate"] != "absent"
            ):
                entry["candidate"] = _canonical_wording(entry["candidate"])
    return source


def _serialized_bytes(value: object) -> int:
    return len(dump_yaml(value).encode("utf-8"))


def _check_authority_note(op: str, note: object, contract: Contract) -> None:
    if note == "absent":
        return
    if not isinstance(note, dict) or set(note) != {"text", "provenance", "span"}:
        raise fail(
            op,
            "authority-note must be `absent` or exactly {text, provenance, span}",
            note,
        )
    _require_str(op, "authority-note text", note["text"])
    if note["provenance"] not in contract.authority_note_provenance:
        raise fail(
            op,
            f"authority-note provenance must be one of {sorted(contract.authority_note_provenance)}",
            note["provenance"],
        )
    _require_str(op, "authority-note span", note["span"])


def _check_candidates(op: str, candidates: object, contract: Contract) -> None:
    if not isinstance(candidates, list):
        raise fail(op, "candidates must be a list", candidates)
    wordings: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or set(candidate) != {
            "wording",
            "provenance-flag",
            "authority-note",
        }:
            raise fail(
                op,
                "candidates must be exactly {wording, provenance-flag, authority-note}",
                candidate,
            )
        _require_str(op, "candidate wording", candidate["wording"])
        if candidate["provenance-flag"] not in contract.provenance_flags:
            raise fail(
                op,
                f"candidate provenance-flag must be one of {sorted(contract.provenance_flags)}",
                candidate["provenance-flag"],
            )
        _check_authority_note(op, candidate["authority-note"], contract)
        wordings.append(candidate["wording"])
    duplicates = {w for w in wordings if wordings.count(w) > 1}
    if duplicates:
        raise fail(op, f"duplicate candidate wordings rejected: {sorted(duplicates)}")


def _check_composition_provenance(op: str, value: object) -> None:
    if not isinstance(value, dict) or set(value) != {
        "invocation-span",
        "delegation-span",
    }:
        raise fail(
            op,
            "composition-provenance must be exactly {invocation-span, delegation-span}",
            value,
        )
    _require_str(op, "invocation-span", value["invocation-span"])
    _require_str(op, "delegation-span", value["delegation-span"])


def _check_pin_list(
    op: str,
    name: str,
    value: object,
    *,
    allow_no_comparable_identity: bool = False,
    allow_manifest: bool = True,
    require_nonempty: bool = False,
    byte_cap: int | None = None,
) -> int:
    if not isinstance(value, list):
        raise fail(op, f"{name} must be a list", value)
    if require_nonempty and not value:
        raise fail(op, f"{name} must not be empty")
    total_bytes = 0
    for entry in value:
        if not isinstance(entry, dict):
            raise fail(op, f"{name} entries must be mappings", entry)
        keys = set(entry)
        identity_keys = keys
        if byte_cap is not None:
            measured_bytes = entry.get("bytes")
            if (
                isinstance(measured_bytes, bool)
                or not isinstance(measured_bytes, int)
                or measured_bytes < 0
            ):
                raise fail(
                    op,
                    f"{name} entries must carry a non-negative integer bytes measurement",
                    measured_bytes,
                )
            total_bytes += measured_bytes
            identity_keys = keys - {"bytes"}
        if identity_keys in ({"path", "id"}, {"name", "id"}):
            locator = "path" if "path" in entry else "name"
            _require_str(op, f"{name} {locator}", entry[locator])
            identifier = entry["id"]
            if (
                identifier == "no comparable identity"
                and not allow_no_comparable_identity
            ):
                raise fail(
                    op,
                    f"{name} permits `no comparable identity` only for in-packet material",
                    identifier,
                )
            if identifier != "no comparable identity" and not _is_sha256(identifier):
                raise fail(
                    op,
                    f"{name} id must be a 64-hex content identifier or `no comparable identity`",
                    identifier,
                )
            continue
        if identity_keys == {"path", "manifest"}:
            if not allow_manifest:
                raise fail(
                    op, f"{name} accepts exact file identities, not manifests", entry
                )
            _require_str(op, f"{name} path", entry["path"])
            manifest = entry["manifest"]
            if not isinstance(manifest, list):
                raise fail(op, f"{name} manifest must be a list", manifest)
            relpaths: list[str] = []
            for child in manifest:
                if not isinstance(child, dict) or set(child) != {"relpath", "id"}:
                    raise fail(
                        op,
                        f"{name} manifest entries must be exactly {{relpath, id}}",
                        child,
                    )
                _require_str(op, f"{name} manifest relpath", child["relpath"])
                if not _is_sha256(child["id"]):
                    raise fail(
                        op,
                        f"{name} manifest id must be a 64-hex content identifier",
                        child["id"],
                    )
                relpaths.append(child["relpath"])
            if len(relpaths) != len(set(relpaths)):
                raise fail(op, f"{name} manifest contains duplicate relpaths", relpaths)
            continue
        raise fail(
            op,
            f"{name} entries must be exactly {{path, id}}, {{name, id}}, or {{path, manifest}}"
            + (", plus bytes" if byte_cap is not None else ""),
            entry,
        )
    if byte_cap is not None and total_bytes > byte_cap:
        raise refuse(
            op,
            f"{name} measured aggregate of {total_bytes} bytes exceeds the {byte_cap}-byte bound",
        )
    return total_bytes


def _check_method_pin_inventory(
    op: str, name: str, value: object, contract: Contract
) -> None:
    """Require exactly the canonical method-surface inventory: every
    deliberate-owned behavior surface pinned once, nothing extra, nothing
    missing. Locators match canonical surfaces by normalized path suffix."""
    _check_pin_list(op, name, value, require_nonempty=True, allow_manifest=False)
    if not isinstance(value, list):
        raise fail(op, f"{name} must be a list", value)
    unmatched = {surface: surface for surface in contract.method_surfaces}
    for entry in value:
        locator = str(entry.get("path", entry.get("name", "")))
        normalized = _normalize_locator(locator)
        matches = [
            surface
            for surface in contract.method_surfaces
            if normalized == surface or normalized.endswith(f"/{surface}")
        ]
        if not matches:
            raise fail(
                op,
                f"{name} pins an unexpected surface outside the canonical method-surface inventory",
                locator,
            )
        surface = matches[0]
        if surface not in unmatched:
            raise fail(op, f"{name} pins {surface} more than once", locator)
        del unmatched[surface]
    if unmatched:
        raise fail(
            op,
            f"{name} is missing required method surfaces",
            sorted(unmatched),
        )


def _check_amendments(op: str, value: object) -> None:
    if not isinstance(value, list):
        raise fail(op, "amendments must be a list", value)
    for amendment in value:
        if not isinstance(amendment, dict) or set(amendment) != {
            "retrieval",
            "option",
        }:
            raise fail(op, "amendments must be exactly {retrieval, option}", amendment)
        ref = amendment["retrieval"]
        if not isinstance(ref, dict) or set(ref) != {
            "producing-stage",
            "source",
            "retrieved-at",
        }:
            raise fail(
                op,
                "amendment retrieval must be exactly {producing-stage, source, retrieved-at}",
                ref,
            )
        _require_str(op, "amendment option", amendment["option"])


def _check_contract_field_value(
    op: str,
    name: str,
    value: object,
    contract: Contract,
    effective_bounds: dict,
) -> None:
    if name == "frame":
        _require_str(op, name, value)
    elif name == "field-mode":
        if value not in contract.field_modes:
            raise fail(
                op,
                f"field-mode must be one of {sorted(contract.field_modes)}",
                value,
            )
    elif name in {"constraints", "values", "soft-prefs"}:
        if not isinstance(value, list):
            raise fail(op, f"{name} must be a list", value)
    elif name == "stakes":
        _require_str(op, name, value)
    elif name == "evidence-inputs":
        if value is None:
            raise fail(
                op, "evidence-inputs must be present, using an explicit absence value"
            )
        cap = effective_bounds["in-packet-evidence-bytes"]
        size = _serialized_bytes(value)
        if size > cap:
            raise refuse(
                op,
                f"serialized evidence-inputs of {size} bytes exceed the {cap}-byte defense-in-depth bound",
            )
    elif name == "evidence-authorization":
        _require_str(op, name, value)
    elif name == "survivor-budget":
        if isinstance(value, bool) or not isinstance(value, int) or value < 2:
            raise fail(op, "survivor-budget must be an integer of at least two", value)
    elif name == "degradation-permission":
        if not isinstance(value, bool):
            _require_str(op, name, value)
    else:
        raise refuse(op, f"no contract-field validator for {name!r}")


def _check_contract_fields(
    op: str,
    fields: object,
    contract: Contract,
    *,
    effective_bounds: dict | None = None,
) -> dict:
    if not isinstance(fields, dict):
        raise fail(op, "fields must be a mapping", fields)
    expected = set(contract.echo_contract_fields)
    if set(fields) != expected:
        raise fail(
            op,
            f"contract fields must be exactly {sorted(expected)}",
            sorted(fields),
        )
    bounds = effective_bounds if effective_bounds is not None else contract.bounds
    for name in contract.echo_contract_fields:
        entry = fields[name]
        if not isinstance(entry, dict) or set(entry) != {"value", "provenance"}:
            raise fail(op, f"field {name} must be exactly {{value, provenance}}", entry)
        if entry["provenance"] not in contract.provenance_labels:
            raise fail(
                op,
                f"field {name} provenance must be one of {sorted(contract.provenance_labels)}",
                entry["provenance"],
            )
        _check_contract_field_value(op, name, entry["value"], contract, bounds)
    return fields


def _check_setup_source(op: str, source: object, contract: Contract) -> dict:
    """Validate the candidate/soft-preference source shared by echo and decomposition."""
    expected = {"candidates", "soft-preferences", "composition-provenance"}
    if not isinstance(source, dict) or set(source) != expected:
        raise fail(
            op,
            f"setup-source must be exactly {sorted(expected)}",
            source,
        )

    candidates = source["candidates"]
    if not isinstance(candidates, list):
        raise fail(op, "setup-source candidates must be a list", candidates)
    candidate_wordings: list[str] = []
    for candidate in candidates:
        if not isinstance(candidate, dict) or set(candidate) != {
            "wording",
            "provenance-flag",
        }:
            raise fail(
                op,
                "setup-source candidates must be exactly {wording, provenance-flag}",
                candidate,
            )
        _require_str(op, "setup-source candidate wording", candidate["wording"])
        if candidate["provenance-flag"] not in contract.provenance_flags:
            raise fail(
                op,
                f"setup-source candidate provenance-flag must be one of {sorted(contract.provenance_flags)}",
                candidate["provenance-flag"],
            )
        candidate_wordings.append(candidate["wording"])
    duplicates = {
        wording
        for wording in candidate_wordings
        if candidate_wordings.count(wording) > 1
    }
    if duplicates:
        raise fail(
            op,
            f"duplicate setup-source candidate wordings rejected: {sorted(duplicates)}",
        )

    preferences = source["soft-preferences"]
    if not isinstance(preferences, dict) or set(preferences) != {
        "provenance",
        "entries",
    }:
        raise fail(
            op,
            "soft-preferences must be exactly {provenance, entries}",
            preferences,
        )
    if preferences["provenance"] not in contract.provenance_labels:
        raise fail(
            op,
            f"soft-preferences provenance must be one of {sorted(contract.provenance_labels)}",
            preferences["provenance"],
        )
    entries = preferences["entries"]
    if not isinstance(entries, list):
        raise fail(op, "soft-preferences entries must be a list", entries)
    attached: set[str] = set()
    criterion_count = 0
    known_candidates = set(candidate_wordings)
    for entry in entries:
        if not isinstance(entry, dict) or set(entry) != {
            "candidate",
            "criteria",
            "authority-note",
        }:
            raise fail(
                op,
                "soft-preference entries must be exactly {candidate, criteria, authority-note}",
                entry,
            )
        candidate = entry["candidate"]
        criteria = _require_str_list(op, "soft-preference criteria", entry["criteria"])
        criterion_count += len(criteria)
        note = entry["authority-note"]
        if candidate == "absent":
            if note != "absent":
                raise fail(
                    op,
                    "candidate-neutral soft preference must have authority-note `absent`",
                    entry,
                )
            if not criteria:
                raise fail(
                    op,
                    "candidate-neutral soft preference must carry at least one criterion",
                    entry,
                )
            continue
        if candidate not in known_candidates:
            raise fail(
                op,
                "candidate-attached soft preference must name one exact setup candidate wording",
                candidate,
            )
        if candidate in attached:
            raise fail(
                op,
                "a candidate may have only one candidate-attached soft-preference entry",
                candidate,
            )
        attached.add(candidate)
        if note == "absent":
            raise fail(
                op,
                "candidate-attached soft preference requires its complete language in authority-note",
                entry,
            )
        _check_authority_note(op, note, contract)
        normalized_candidate = " ".join(re.findall(r"[\w]+", candidate.casefold()))
        normalized_note = " ".join(re.findall(r"[\w]+", note["text"].casefold()))
        for criterion in criteria:
            normalized_criterion = " ".join(re.findall(r"[\w]+", criterion.casefold()))
            if normalized_candidate and (
                f" {normalized_candidate} " in f" {normalized_criterion} "
            ):
                raise fail(
                    op,
                    "candidate-neutral criterion repeats the attached candidate wording",
                    criterion,
                )
            if normalized_note and (
                f" {normalized_note} " in f" {normalized_criterion} "
            ):
                raise fail(
                    op,
                    "candidate-neutral criterion repeats the candidate-attached authority note",
                    criterion,
                )
    if preferences["provenance"] == "absent" and criterion_count:
        raise fail(
            op,
            "soft-preferences provenance cannot be absent when criteria are present",
        )
    _check_composition_provenance(op, source["composition-provenance"])
    return source


def _soft_preferences_from_source(source: dict) -> list[str]:
    return [
        criterion
        for entry in source["soft-preferences"]["entries"]
        for criterion in entry["criteria"]
    ]


def _candidates_from_source(source: dict) -> list[dict]:
    notes = {
        entry["candidate"]: copy.deepcopy(entry["authority-note"])
        for entry in source["soft-preferences"]["entries"]
        if entry["candidate"] != "absent"
    }
    return [
        {
            "wording": candidate["wording"],
            "provenance-flag": candidate["provenance-flag"],
            "authority-note": notes.get(candidate["wording"], "absent"),
        }
        for candidate in source["candidates"]
    ]


def _decomposition_from_echo(echo: dict, contract: Contract) -> dict:
    source = _check_setup_source("setup normalization", echo["setup-source"], contract)
    fields = echo["fields"]
    return {
        "frame": fields["frame"]["value"],
        "candidates": _candidates_from_source(source),
        "stakes": fields["stakes"]["value"],
        "soft-prefs": _soft_preferences_from_source(source),
        "values": (
            fields["values"]["value"]
            if isinstance(fields["values"]["value"], list)
            else []
        ),
        "composition-provenance": copy.deepcopy(source["composition-provenance"]),
    }


def _setup_source_from_artifacts(
    candidates: list[dict],
    soft_prefs: list[str],
    soft_prefs_provenance: str,
    composition_provenance: dict,
) -> dict:
    """Reconstruct a normalized source for capsule import without inventing attachment."""
    entries = [
        {
            "candidate": "absent",
            "criteria": [preference],
            "authority-note": "absent",
        }
        for preference in soft_prefs
    ]
    entries.extend(
        {
            "candidate": candidate["wording"],
            "criteria": [],
            "authority-note": copy.deepcopy(candidate["authority-note"]),
        }
        for candidate in candidates
        if candidate["authority-note"] != "absent"
    )
    return {
        "candidates": [
            {
                "wording": candidate["wording"],
                "provenance-flag": candidate["provenance-flag"],
            }
            for candidate in candidates
        ],
        "soft-preferences": {
            "provenance": soft_prefs_provenance,
            "entries": entries,
        },
        "composition-provenance": copy.deepcopy(composition_provenance),
    }


def normalize_setup_document(document: object, contract: Contract) -> tuple[dict, dict]:
    """Derive the echo and decomposition from one authored setup document."""
    op = "setup normalization"
    schema = contract.schemas[SETUP_SCHEMA]
    if not isinstance(document, dict):
        raise fail(op, "setup document is not a mapping", document)
    expected = {entry["key"] for entry in schema["keys"]}
    if set(document) != expected:
        raise fail(
            op,
            f"setup document keys must be exactly {sorted(expected)}",
            sorted(document),
        )
    if document["schema"] != SETUP_SCHEMA:
        raise refuse(op, f"unsupported schema version: {document['schema']!r}")
    _require_str(
        op, "invocation-wording-initial", document["invocation-wording-initial"]
    )
    directives = _require_str_list(op, "directives", document["directives"])
    bounds = _check_bounds(op, document["bounds"], contract)
    if len(directives) > bounds["verbatim-directive-history"]:
        raise fail(
            op,
            f"directives exceed the history bound of {bounds['verbatim-directive-history']}",
        )
    collapsed = document["directives-collapsed"]
    if not isinstance(collapsed, list) or not all(
        _is_sha256(entry) for entry in collapsed
    ):
        raise fail(
            op,
            "directives-collapsed must be a list of 64-hex content identifiers",
            collapsed,
        )
    source_id = document["source-capsule-id"]
    if source_id != "none" and not _is_sha256(source_id):
        raise fail(
            op,
            "source-capsule-id must be `none` or a 64-hex identifier",
            source_id,
        )

    source = _check_setup_source(
        op,
        _canonicalize_setup_wordings(
            {
                "candidates": copy.deepcopy(document["candidates"]),
                "soft-preferences": copy.deepcopy(document["soft-preferences"]),
                "composition-provenance": copy.deepcopy(
                    document["composition-provenance"]
                ),
            }
        ),
        contract,
    )
    input_fields = document["fields"]
    expected_input_fields = set(contract.echo_contract_fields) - {"soft-prefs"}
    if not isinstance(input_fields, dict) or set(input_fields) != expected_input_fields:
        raise fail(
            op,
            f"setup fields must be exactly {sorted(expected_input_fields)}",
            sorted(input_fields) if isinstance(input_fields, dict) else input_fields,
        )
    normalized_fields: dict[str, dict] = {}
    for name in contract.echo_contract_fields:
        if name == "soft-prefs":
            normalized_fields[name] = {
                "value": _soft_preferences_from_source(source),
                "provenance": source["soft-preferences"]["provenance"],
            }
            continue
        entry = input_fields[name]
        if not isinstance(entry, dict) or set(entry) != {"value", "provenance"}:
            raise fail(op, f"field {name} must be exactly {{value, provenance}}", entry)
        if entry["provenance"] not in contract.provenance_labels:
            raise fail(
                op,
                f"field {name} provenance must be one of {sorted(contract.provenance_labels)}",
                entry["provenance"],
            )
        _check_contract_field_value(op, name, entry["value"], contract, bounds)
        normalized_fields[name] = copy.deepcopy(entry)

    echo = {
        "invocation-wording-initial": document["invocation-wording-initial"],
        "directives": copy.deepcopy(directives),
        "directives-collapsed": copy.deepcopy(collapsed),
        "fields": normalized_fields,
        "setup-source": source,
        "bounds": copy.deepcopy(bounds),
        "source-capsule-id": source_id,
    }
    _check_body_echo(op, echo, contract)
    decomposition = _decomposition_from_echo(echo, contract)
    _check_body_decomposition(op, decomposition, contract)
    return echo, decomposition


def _check_bounds(op: str, value: object, contract: Contract) -> dict:
    if not isinstance(value, dict) or set(value) != set(contract.bounds):
        raise fail(
            op,
            f"bounds must carry exactly {sorted(contract.bounds)}",
            sorted(value) if isinstance(value, dict) else value,
        )
    for name, bound in value.items():
        if isinstance(bound, bool) or not isinstance(bound, int) or bound <= 0:
            raise fail(op, f"bound {name} must be a positive integer", bound)
    if value != contract.bounds:
        raise refuse(
            op,
            "v1 bounds are immutable and must equal the canonical contract-data bounds",
        )
    return value


def _check_body_echo(op: str, body: dict, contract: Contract) -> None:
    _require_str(op, "invocation-wording-initial", body["invocation-wording-initial"])
    effective_bounds = _check_bounds(op, body["bounds"], contract)
    directives = _require_str_list(op, "directives", body["directives"])
    cap = effective_bounds["verbatim-directive-history"]
    if len(directives) > cap:
        raise fail(op, f"directives exceed the history bound of {cap}", len(directives))
    collapsed = body["directives-collapsed"]
    if not isinstance(collapsed, list) or not all(
        _is_sha256(entry) for entry in collapsed
    ):
        raise fail(
            op,
            "directives-collapsed must be a list of 64-hex content identifiers",
            collapsed,
        )
    _check_contract_fields(
        op,
        body["fields"],
        contract,
        effective_bounds=effective_bounds,
    )
    source = _check_setup_source(op, body["setup-source"], contract)
    expected_soft_prefs = {
        "value": _soft_preferences_from_source(source),
        "provenance": source["soft-preferences"]["provenance"],
    }
    if body["fields"]["soft-prefs"] != expected_soft_prefs:
        raise fail(
            op,
            "echo soft-prefs must be derived exactly from setup-source criteria",
            body["fields"]["soft-prefs"],
        )
    source_id = body["source-capsule-id"]
    if source_id != "none" and not _is_sha256(source_id):
        raise fail(
            op, "source-capsule-id must be `none` or a 64-hex identifier", source_id
        )


def _check_body_decomposition(op: str, body: dict, contract: Contract) -> None:
    _require_str(op, "frame", body["frame"])
    _check_candidates(op, body["candidates"], contract)
    _require_str(op, "stakes", body["stakes"])
    if not isinstance(body["soft-prefs"], list):
        raise fail(op, "soft-prefs must be a list", body["soft-prefs"])
    if not isinstance(body["values"], list):
        raise fail(op, "values must be a list", body["values"])
    _check_composition_provenance(op, body["composition-provenance"])


def _check_body_pins(op: str, body: dict, contract: Contract) -> None:
    constituents = body["constituents"]
    if (
        not isinstance(constituents, dict)
        or set(constituents) != contract.constituent_names
    ):
        raise fail(
            op,
            f"constituents must map exactly {sorted(contract.constituent_names)}",
            constituents,
        )
    for name, pins in constituents.items():
        _check_pin_list(op, f"constituents[{name}]", pins, require_nonempty=True)
    _check_method_pin_inventory(op, "method", body["method"], contract)
    _check_pin_list(
        op,
        "evidence",
        body["evidence"],
        byte_cap=contract.bounds["named-evidence-expanded-bytes"],
    )
    _check_pin_list(
        op,
        "in-packet",
        body["in-packet"],
        allow_no_comparable_identity=True,
        allow_manifest=False,
        byte_cap=contract.bounds["in-packet-evidence-bytes"],
    )


def _check_body_envelope(op: str, body: dict, contract: Contract) -> None:
    validate_envelope_shape(body["document"], contract)
    _check_amendments(op, body["amendments"])


def _check_body_brief_render(op: str, body: dict, contract: Contract) -> None:
    brief_id = body["brief-id"]
    if (
        not isinstance(brief_id, str)
        or len(brief_id) != 64
        or any(c not in "0123456789abcdef" for c in brief_id)
    ):
        raise fail(op, "brief-id must be a 64-hex content identifier", brief_id)


def _check_body_terminal_claim(op: str, body: dict, contract: Contract) -> None:
    _require_str(op, "terminal", body["terminal"])
    _require_str(op, "claim", body["claim"])
    _require_str(op, "survivor", body["survivor"])


def _check_proof_boundary_shape(
    op: str,
    body: object,
    contract: Contract,
    *,
    allow_unproduced_pins: bool = False,
) -> dict:
    if not isinstance(body, dict) or set(body) != contract.proof_boundary_keys:
        raise fail(
            op,
            f"proof boundary keys must be exactly {sorted(contract.proof_boundary_keys)}",
            sorted(body) if isinstance(body, dict) else body,
        )
    pins = body["constituent-pins"]
    method_identity = body["method-identity"]
    missing_pins = _is_not_produced(pins) or _is_not_produced(method_identity)
    if missing_pins:
        if not allow_unproduced_pins:
            raise fail(op, "proof-boundary pin identity cannot be unproduced")
        if not (_is_not_produced(pins) and _is_not_produced(method_identity)):
            raise fail(
                op,
                "proof-boundary constituent and method pins must be produced or unproduced together",
            )
    else:
        if not isinstance(pins, dict) or set(pins) != contract.constituent_names:
            raise fail(
                op,
                f"proof-boundary constituent-pins must map exactly {sorted(contract.constituent_names)}",
                pins,
            )
        for name, pin_list in pins.items():
            _check_pin_list(
                op,
                f"constituent-pins[{name}]",
                pin_list,
                require_nonempty=True,
            )
        _check_method_pin_inventory(
            op, "proof-boundary method-identity", method_identity, contract
        )
    for key in (
        "packet-isolation",
        "read-isolation",
        "evidence-scope-used",
        "containment",
        "store-path",
        "not-proven",
    ):
        _require_str(op, f"proof-boundary {key}", body[key])
    for key in ("effective-models", "collapses"):
        value = body[key]
        if isinstance(value, list):
            _require_str_list(op, f"proof-boundary {key}", value)
        else:
            _require_str(op, f"proof-boundary {key}", value)
    return body


def _check_body_proof_inputs(op: str, body: dict, contract: Contract) -> None:
    _check_proof_boundary_shape(op, body, contract)


def _check_body_terminal_state(op: str, body: dict, contract: Contract) -> None:
    terminal = body["terminal"]
    carrier = body["carrier"]
    _require_str(op, "terminal", terminal)
    if carrier not in contract.capsule_carriers:
        raise fail(
            op,
            f"carrier must be one of {sorted(contract.capsule_carriers)}",
            carrier,
        )
    if terminal.startswith("stage failed:"):
        failed_stage = terminal.removeprefix("stage failed:").strip()
        if failed_stage not in contract.stages or failed_stage == "contest":
            raise fail(
                op,
                "stage-failure terminal must name generate, prune, shape, or recommend",
                failed_stage,
            )
    if _is_capsule_forbidden_terminal(terminal, contract):
        raise refuse(op, f"terminal {terminal!r} cannot own a capsule")
    if carrier == "failure-capsule" and not _is_failure_terminal(terminal, contract):
        raise fail(op, "failure-capsule carrier requires a failure terminal", terminal)
    if carrier == "capsule":
        if _is_failure_terminal(terminal, contract):
            raise fail(
                op, "failure terminal requires the failure-capsule carrier", terminal
            )
        _capsule_terminal_frontier(terminal, contract, op)


def _check_body_capsule_progress(op: str, body: dict, contract: Contract) -> None:
    capsule = body["capsule"]
    if not isinstance(capsule, dict):
        raise fail(op, "capsule-progress must carry the validated capsule mapping")
    validate_capsule_document(capsule, contract)


def _check_body_capsule_import(op: str, body: dict, contract: Contract) -> None:
    capsule = body["capsule"]
    if not isinstance(capsule, dict):
        raise fail(op, "imported capsule must be a mapping", capsule)
    validate_capsule_document(capsule, contract, restart_state=True)


def _parse_directive_action(
    op: str, action: object, contract: Contract
) -> tuple[str, str]:
    """Parse one typed directive action: `accept-seed` or `<kind>: <argument>`."""
    if not isinstance(action, str) or not action.strip():
        raise fail(op, "directive action must be a non-empty string", action)
    kind, sep, argument = action.partition(": ")
    if not sep:
        kind = action
        argument = ""
    if kind not in contract.directive_action_kinds:
        raise fail(op, "unknown directive action kind", action)
    if kind == "accept-seed":
        if argument:
            raise fail(op, "accept-seed takes no argument", action)
    elif not argument:
        raise fail(op, f"directive action {kind} requires `{kind}: <argument>`", action)
    return kind, argument


def _check_directive_bindings(op: str, value: object, contract: Contract) -> None:
    if not isinstance(value, list):
        raise fail(op, "directive bindings must be a list", value)
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != {"directive", "actions"}:
            raise fail(
                op, "directive bindings must be exactly {directive, actions}", entry
            )
        _require_str(op, "directive text", entry["directive"])
        actions = entry["actions"]
        if not isinstance(actions, list) or not actions:
            raise fail(
                op,
                f"directive binds no action — unclassifiable directive: {entry['directive']!r}",
            )
        for action in actions:
            _parse_directive_action(op, action, contract)


def _check_body_restart_plan(op: str, body: dict, contract: Contract) -> None:
    earliest = body["earliest-stage"]
    if earliest != "none" and earliest not in contract.stages:
        raise fail(
            op,
            f"earliest-stage must be `none` or one of {contract.stages}",
            earliest,
        )
    reasons = _require_str_list(op, "restart reasons", body["reasons"])
    if not reasons:
        raise fail(op, "restart reasons must not be empty")
    _check_directive_bindings(op, body["directives"], contract)


_BODY_CHECKS = {
    "echo": _check_body_echo,
    "decomposition": _check_body_decomposition,
    "pins": _check_body_pins,
    "envelope": _check_body_envelope,
    "brief-render": _check_body_brief_render,
    "terminal-claim": _check_body_terminal_claim,
    "proof-inputs": _check_body_proof_inputs,
    "terminal-state": _check_body_terminal_state,
    "capsule-progress": _check_body_capsule_progress,
    "capsule-import": _check_body_capsule_import,
    "restart-plan": _check_body_restart_plan,
}


def validate_runstate_item(item: object, contract: Contract) -> None:
    op = "run-state item validation"
    schema = contract.schemas[RUNSTATE_SCHEMA]
    if not isinstance(item, dict):
        raise fail(op, "item is not a mapping", item)
    keys = {entry["key"] for entry in schema["keys"]}
    unknown = set(item) - keys
    if unknown:
        raise fail(op, f"unknown keys rejected: {sorted(unknown)}")
    for entry in schema["keys"]:
        key = entry["key"]
        if entry.get("required") and key not in item:
            raise fail(op, f"missing required key: {key}")
    if item["schema"] != RUNSTATE_SCHEMA:
        raise refuse(op, f"unsupported schema version: {item['schema']!r}")
    kinds = next(e["enum"] for e in schema["keys"] if e["key"] == "kind")
    if item["kind"] not in kinds:
        raise fail(op, f"unknown kind: {item['kind']!r}")
    _require_str(op, "run", item["run"])
    if (
        isinstance(item["seq"], bool)
        or not isinstance(item["seq"], int)
        or item["seq"] < 0
    ):
        raise fail(op, "seq must be a non-negative integer", item["seq"])
    if item["kind"] in {"envelope", "brief-render"} and not item.get("stage"):
        raise fail(op, f"kind {item['kind']} requires a stage")
    if item.get("stage") is not None and item["stage"] not in contract.stages:
        raise fail(op, f"unknown stage: {item['stage']!r}")
    body = item["body"]
    if not isinstance(body, dict):
        raise fail(op, "body is not a mapping", body)
    expected = set(schema["body-keys"][item["kind"]])
    actual = set(body)
    if actual != expected:
        raise fail(
            op,
            f"body keys for kind {item['kind']} must be exactly {sorted(expected)}",
            sorted(actual),
        )
    _BODY_CHECKS[item["kind"]](f"{op} ({item['kind']})", body, contract)
    if item["kind"] == "envelope" and item["stage"] != body["document"]["stage"]:
        raise fail(
            op,
            "outer envelope stage must equal body.document.stage",
            {"outer": item["stage"], "document": body["document"]["stage"]},
        )


# ---------------------------------------------------------------------------
# Envelope validation
# ---------------------------------------------------------------------------


def _is_not_produced(value: object) -> bool:
    return (
        isinstance(value, str)
        and value.startswith("not produced:")
        and bool(value.removeprefix("not produced:").strip())
    )


def _reject_empty_not_produced(op: str, name: str, value: object) -> None:
    if (
        isinstance(value, str)
        and value.startswith("not produced:")
        and not _is_not_produced(value)
    ):
        raise fail(op, f"{name} not-produced marker requires a non-empty reason", value)


def _check_record_shape(record: object, contract: Contract, op: str) -> dict:
    """Key-set, enum, and evidence-provenance checks shared by stage and
    capsule records. Returns the record as a validated mapping."""
    if not isinstance(record, dict):
        raise fail(op, "record is not a mapping", record)
    spec = {entry["key"]: entry for entry in contract.record_keys}
    unknown = set(record) - set(spec)
    if unknown:
        raise fail(op, f"unknown record keys rejected: {sorted(unknown)}")
    for key, entry in spec.items():
        if entry["required"] and key not in record:
            raise fail(op, f"record missing required key: {key}", record.get("option"))
        if key in record and "enum" in entry and record[key] not in entry["enum"]:
            raise fail(
                op, f"record key {key} must be one of {entry['enum']}", record[key]
            )
        if key in record and key != "evidence-provenance":
            _require_str(op, f"record key {key}", record[key])
    prov = record.get("evidence-provenance")
    if prov is not None:
        if not isinstance(prov, list) or not prov:
            raise fail(
                op,
                "evidence-provenance must be a non-empty list of {source, retrieved-at}",
                prov,
            )
        for ref in prov:
            if not isinstance(ref, dict) or set(ref) != {"source", "retrieved-at"}:
                raise fail(
                    op,
                    "evidence-provenance entries must be exactly {source, retrieved-at}",
                    ref,
                )
            _require_str(op, "evidence-provenance source", ref["source"])
            _require_str(op, "evidence-provenance retrieved-at", ref["retrieved-at"])
    return record


def _check_record(
    record: object, contract: Contract, allowed_wordings: list[str], stage: str
) -> None:
    op = f"record validation ({stage})"
    record = _check_record_shape(record, contract, op)
    if record["status"] != "active":
        raise fail(
            op,
            "a stage-produced record must have status `active`; `revived` is orchestrator historization only",
            record["status"],
        )
    basis = record["cut-basis"]
    if stage == "prune" and basis not in contract.prune_bases:
        raise fail(op, f"cut basis {basis!r} is not a Prune basis")
    if stage == "recommend" and basis not in contract.recommend_bases:
        raise fail(op, f"cut basis {basis!r} is not a Recommend disposition basis")
    if record["option"] not in allowed_wordings:
        raise fail(
            op,
            "record `option` is not byte-identical to any stored original wording — paraphrase rejected",
            record["option"],
        )


def _check_option_list(value: object, op: str, contract: Contract) -> list[dict]:
    if not isinstance(value, list):
        raise fail(op, "option list must be a list", value)
    for opt in value:
        if not isinstance(opt, dict):
            raise fail(op, "option entries must be mappings", opt)
        unknown = set(opt) - {"wording", "provenance", "insertion"}
        if unknown:
            raise fail(op, f"unknown option keys rejected: {sorted(unknown)}")
        if not isinstance(opt.get("wording"), str) or not opt["wording"].strip():
            raise fail(op, "option wording must be a non-empty string", opt)
        if opt.get("provenance") not in contract.provenance_flags:
            raise fail(
                op,
                f"option provenance must be one of {sorted(contract.provenance_flags)}",
                opt.get("provenance"),
            )
        insertion = opt.get("insertion")
        if insertion is not None and insertion not in contract.insertion_values:
            raise fail(
                op,
                f"insertion must be one of {sorted(contract.insertion_values)}",
                insertion,
            )
    wordings = [opt["wording"] for opt in value]
    duplicates = {w for w in wordings if wordings.count(w) > 1}
    if duplicates:
        raise fail(
            op,
            f"duplicate option wordings rejected — the partition must be well-defined: {sorted(duplicates)}",
        )
    return value


def _check_retrievals(value: object, contract: Contract, op: str) -> list[dict]:
    if value == "none":
        return []
    if not isinstance(value, list):
        raise fail(op, "retrievals must be `none` or a list", value)
    cap = contract.bounds["per-stage-retrievals"]
    if len(value) > cap:
        raise fail(
            op, f"retrievals list of {len(value)} exceeds the per-stage cap of {cap}"
        )
    identities: list[tuple[str, str]] = []
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != {
            "source",
            "retrieved-at",
            "fact",
            "concerns",
        }:
            raise fail(
                op,
                "retrieval entries must be exactly {source, retrieved-at, fact, concerns}",
                entry,
            )
        concerns = entry["concerns"]
        if concerns != "candidate-neutral" and (
            not isinstance(concerns, list)
            or not concerns
            or not all(isinstance(c, str) for c in concerns)
        ):
            raise fail(
                op,
                "concerns must be `candidate-neutral` or a non-empty list of candidate wordings",
                concerns,
            )
        for key in ("source", "retrieved-at", "fact"):
            _require_str(op, f"retrieval {key}", entry[key])
        if isinstance(concerns, list):
            _require_str_list(op, "retrieval concerns", concerns)
        identities.append((entry["source"], entry["retrieved-at"]))
    duplicates = {identity for identity in identities if identities.count(identity) > 1}
    if duplicates:
        raise fail(
            op,
            "retrieval source/retrieved-at identities must be unique within one envelope",
            sorted(duplicates),
        )
    return value


def canonicalize_generate_wordings(document: object) -> object:
    """Identity ingress for fresh Generate outputs: canonicalize the wording of
    every generated option before any validation, so duplicate detection runs
    post-normalization and the field is stored in canonical bytes. Non-generated
    options are echoes of already-canonical setup candidates and stay untouched
    for the byte-exact seed check. Every other stage's wordings are downstream
    of ingress and are never normalized. Malformed shapes pass through for the
    shape checks to reject with their own messages."""
    if not isinstance(document, dict) or document.get("stage") != "generate":
        return document
    artifacts = document.get("artifacts")
    if isinstance(artifacts, dict) and isinstance(artifacts.get("field"), list):
        for option in artifacts["field"]:
            if (
                isinstance(option, dict)
                and option.get("provenance") == "generated"
                and isinstance(option.get("wording"), str)
            ):
                option["wording"] = _canonical_wording(option["wording"])
    return document


def validate_envelope_shape(document: object, contract: Contract) -> dict:
    """Schema-shape checks that need no store context."""
    op = "envelope validation"
    schema = contract.schemas[ENVELOPE_SCHEMA]
    if not isinstance(document, dict):
        raise fail(op, "envelope is not a mapping", document)
    keys = {entry["key"] for entry in schema["keys"]}
    unknown = set(document) - keys
    if unknown:
        raise fail(op, f"unknown keys rejected: {sorted(unknown)}")
    missing = keys - set(document)
    if missing:
        raise fail(op, f"missing required keys: {sorted(missing)}")
    if document["schema"] != ENVELOPE_SCHEMA:
        raise refuse(op, f"unsupported schema version: {document['schema']!r}")
    stage = document["stage"]
    if stage not in contract.stages:
        raise fail(op, f"unknown stage: {stage!r}")
    status = document["status"]
    if not isinstance(status, str) or not (
        status == "completed"
        or (status.startswith("failed: ") and status[len("failed: ") :].strip())
        or (status.startswith("exit: ") and status[len("exit: ") :].strip())
    ):
        raise fail(
            op,
            "status must be `completed`, `exit: <named honest exit>`, or `failed: <reason>`",
            status,
        )
    artifacts = document["artifacts"]
    if not isinstance(artifacts, dict):
        raise fail(op, "artifacts must be a mapping", artifacts)
    obliged = contract.obliged[stage]
    expected = {entry["key"] for entry in obliged}
    if set(artifacts) != expected:
        raise fail(
            op,
            f"artifacts must carry exactly the stage's obliged keys {sorted(expected)}",
            sorted(artifacts),
        )
    for entry in obliged:
        value = artifacts[entry["key"]]
        _reject_empty_not_produced(op, entry["key"], value)
        if _is_not_produced(value):
            if status == "completed":
                raise fail(
                    op,
                    f"a completed stage cannot mark an artifact not produced: {entry['key']}",
                )
            continue
        if value == "not applicable":
            if entry["required"] != "conditional":
                raise fail(
                    op,
                    f"only conditional artifacts may be `not applicable`: {entry['key']}",
                )
            continue
        _check_artifact_shape(entry, value, stage, contract)
    if stage == "recommend" and status.startswith("exit: field not ready"):
        # The field-not-ready class requires a seed and no close (the terminal
        # check); enforced here too so the conflicting envelope is rejected at
        # validation instead of stranding an accepted store with no reachable
        # capsule terminal (first observed live 2026-07-18, Codex run 1).
        if _is_produced(artifacts["close"]):
            raise fail(
                op,
                "a `field not ready` exit is close-less: the exit statement is the "
                "envelope status and `close` renders `not produced: field not ready` "
                "— a produced close leaves no reachable capsule terminal",
            )
        if not isinstance(artifacts["provisional-seed"], dict):
            raise fail(
                op,
                "a `field not ready` exit requires the provisional rerun seed in "
                "`provisional-seed`",
            )
    _check_retrievals(document["retrievals"], contract, op)
    encounters = document["encounters"]
    if encounters != "none":
        if not isinstance(encounters, list):
            raise fail(op, "encounters must be `none` or a list", encounters)
        for entry in encounters:
            if not isinstance(entry, dict) or set(entry) != {"kind", "where", "note"}:
                raise fail(
                    op, "encounter entries must be exactly {kind, where, note}", entry
                )
            if entry["kind"] not in contract.encounter_kinds:
                raise fail(
                    op,
                    f"encounter kind must be one of {sorted(contract.encounter_kinds)}",
                    entry["kind"],
                )
            _require_str(op, "encounter where", entry["where"])
            _require_str(op, "encounter note", entry["note"])
    pins = document["pins"]
    if pins != "none":
        if not isinstance(pins, list):
            raise fail(op, "pins must be `none` or a list", pins)
        for entry in pins:
            if not isinstance(entry, dict) or set(entry) != {"surface", "id"}:
                raise fail(op, "pin entries must be exactly {surface, id}", entry)
            _require_str(op, "pin surface", entry["surface"])
            if not _is_sha256(entry["id"]):
                raise fail(
                    op, "pin id must be a 64-hex content identifier", entry["id"]
                )
    if not isinstance(document["model"], str) or not document["model"].strip():
        raise fail(
            op,
            "model must be a non-empty string (`unknown` allowed)",
            document["model"],
        )
    return document


def _check_artifact_shape(
    entry: dict, value: object, stage: str, contract: Contract
) -> None:
    op = f"artifact validation ({stage}.{entry['key']})"
    shape = entry["shape"]
    if shape == "text":
        if not isinstance(value, str) or not value.strip():
            raise fail(op, "text artifact must be a non-empty string", value)
    elif shape == "option-list":
        options = _check_option_list(value, op, contract)
        if stage == "generate" and any("insertion" in option for option in options):
            raise fail(
                op,
                "fresh Generate output must not carry reused-field insertion provenance",
            )
    elif shape == "record-list":
        if not isinstance(value, list):
            raise fail(op, "record list must be a list", value)
        for record in value:
            _check_record_shape(record, contract, op)
        # byte identity and basis ownership are checked with store context in
        # validate_envelope_against_store.
    elif shape == "overflow":
        if not isinstance(value, dict) or set(value) != {"disclosure", "blocked-cuts"}:
            raise fail(op, "overflow must be exactly {disclosure, blocked-cuts}", value)
        if not isinstance(value["blocked-cuts"], list):
            raise fail(op, "blocked-cuts must be a list", value["blocked-cuts"])
        _require_str(op, "overflow disclosure", value["disclosure"])
        for cut in value["blocked-cuts"]:
            if not isinstance(cut, dict) or set(cut) != {
                "option",
                "unpriced-trade",
                "why-blocked",
            }:
                raise fail(
                    op,
                    "blocked-cut entries must be exactly {option, unpriced-trade, why-blocked}",
                    cut,
                )
            for key in ("option", "unpriced-trade", "why-blocked"):
                _require_str(op, f"blocked-cut {key}", cut[key])
    elif shape == "consequence-list":
        if not isinstance(value, list):
            raise fail(op, "consequence list must be a list", value)
        for row in value:
            if not isinstance(row, dict) or set(row) != {
                "option",
                "constraint",
                "consequence",
            }:
                raise fail(
                    op,
                    "consequence entries must be exactly {option, constraint, consequence}",
                    row,
                )
            for key in ("option", "constraint", "consequence"):
                _require_str(op, f"consequence {key}", row[key])
    elif shape == "leans":
        if not isinstance(value, dict) or set(value) != {
            "agent-first-lean",
            "user-visible-lean",
        }:
            raise fail(
                op,
                "registered-leans must be exactly {agent-first-lean, user-visible-lean}",
                value,
            )
        _require_str(op, "agent-first-lean", value["agent-first-lean"])
        _require_str(op, "user-visible-lean", value["user-visible-lean"])
    elif shape == "seed":
        if not isinstance(value, dict) or set(value) != {
            "wording",
            "handle",
            "core-idea",
            "distinct-bet",
        }:
            raise fail(
                op,
                "provisional seed must be exactly {wording, handle, core-idea, distinct-bet}",
                value,
            )
        for key in ("wording", "handle", "core-idea", "distinct-bet"):
            _require_str(op, f"provisional-seed {key}", value[key])
    else:
        raise refuse(op, f"unknown artifact shape in contract data: {shape}")


def _imported_capsule(store: Store) -> dict | None:
    items = store.find("capsule-import")
    return items[-1]["body"]["capsule"] if items else None


def _restart_frontier_index(store: Store) -> int:
    plans = store.find("restart-plan")
    if not plans:
        if store.find("capsule-import"):
            raise StoreReadLoss(
                "store read failed: imported capsule has no restart-plan; imported authority is unavailable"
            )
        return len(store.contract.stages)
    if len(plans) != 1:
        raise StoreReadLoss(
            "store read failed: imported run must carry exactly one restart-plan"
        )
    earliest = plans[-1]["body"]["earliest-stage"]
    return (
        len(store.contract.stages)
        if earliest == "none"
        else store.contract.stages.index(earliest)
    )


def _validate_restart_stage_frontier(stage: str, store: Store, op: str) -> None:
    plans = store.find("restart-plan")
    if not plans:
        if store.find("capsule-import"):
            raise StoreReadLoss(
                "store read failed: imported capsule has no restart-plan; no stage may run"
            )
        return
    if len(plans) != 1:
        raise StoreReadLoss(
            "store read failed: imported run must carry exactly one restart-plan"
        )
    earliest = plans[-1]["body"]["earliest-stage"]
    if earliest == "none":
        raise refuse(op, "restart plan has no stage frontier; no stage may run")
    earliest_index = store.contract.stages.index(earliest)
    stage_index = store.contract.stages.index(stage)
    if stage_index < earliest_index:
        raise refuse(
            op,
            f"restart plan begins at {earliest}; earlier stage {stage} is outside the plan",
        )
    frontier_envelopes = store.find("envelope", earliest)
    frontier_completed = bool(
        frontier_envelopes
        and not frontier_envelopes[-1]["body"]["document"]["status"].startswith(
            "failed: "
        )
    )
    if stage_index > earliest_index and not frontier_completed:
        raise StoreReadLoss(
            f"store read failed: restart frontier {earliest} has no non-failed envelope before {stage}"
        )


def _capsule_value(store: Store, key: str) -> Any:
    """Return a produced imported value; frontier-aware callers decide reuse."""
    capsule = _imported_capsule(store)
    if capsule is None:
        return None
    value = capsule.get(key)
    if _is_not_produced(value) or value == "not applicable":
        return None
    return value


_MISSING = object()


def _effective_stage_artifact(
    store: Store, stage: str, artifact_key: str, capsule_key: str
) -> object:
    """Return a live artifact verbatim, otherwise imported state, never stale fallback."""
    envelopes = store.find("envelope", stage)
    if envelopes:
        document = envelopes[-1]["body"]["document"]
        if document["status"].startswith("failed: "):
            if stage == "contest" and artifact_key == "exclusion-check-line":
                return "exclusion check unavailable"
            return _MISSING
        return copy.deepcopy(document["artifacts"][artifact_key])
    target_index = store.contract.stages.index(stage)
    if _restart_frontier_index(store) <= target_index:
        return _MISSING
    if any(
        store.contract.stages.index(item["stage"]) <= target_index
        for item in store.find("envelope")
    ):
        return _MISSING
    capsule = _imported_capsule(store)
    if capsule is not None:
        return copy.deepcopy(capsule[capsule_key])
    return _MISSING


def _effective_records(store: Store) -> list[dict] | object:
    capsule = _imported_capsule(store)
    imported_records = (
        copy.deepcopy(capsule["records"])
        if capsule is not None and isinstance(capsule["records"], list)
        else []
    )
    live_items = [
        item
        for item in store.find("envelope")
        if not item["body"]["document"]["status"].startswith("failed: ")
    ]
    earliest_live = min(
        (store.contract.stages.index(item["stage"]) for item in live_items),
        default=len(store.contract.stages),
    )
    earliest_live = min(earliest_live, _restart_frontier_index(store))
    prune_index = store.contract.stages.index("prune")
    recommend_index = store.contract.stages.index("recommend")
    if earliest_live <= prune_index:
        imported_records = [
            record for record in imported_records if record["status"] == "revived"
        ]
    elif earliest_live <= recommend_index:
        imported_records = [
            record
            for record in imported_records
            if record["status"] == "revived"
            or record["cut-basis"] not in store.contract.recommend_bases
        ]

    records = imported_records
    prune_authority = bool(
        capsule is not None
        and isinstance(capsule["records"], list)
        and earliest_live > prune_index
    )
    for stage, bases, artifact_key in (
        ("prune", store.contract.prune_bases, "exclusion-records"),
        ("recommend", store.contract.recommend_bases, "disposition-records"),
    ):
        envelopes = store.find("envelope", stage)
        if not envelopes:
            continue
        if envelopes[-1]["body"]["document"]["status"].startswith("failed: "):
            continue
        records = [
            record
            for record in records
            if record["status"] == "revived" or record["cut-basis"] not in bases
        ]
        value = envelopes[-1]["body"]["document"]["artifacts"][artifact_key]
        if stage == "prune":
            prune_authority = isinstance(value, list)
        if isinstance(value, list):
            records.extend(copy.deepcopy(value))
    if not prune_authority and not any(
        item["stage"] == "recommend"
        and isinstance(
            item["body"]["document"]["artifacts"]["disposition-records"], list
        )
        for item in live_items
    ):
        return (
            records
            if any(record["status"] == "revived" for record in records)
            else _MISSING
        )
    return records


def _effective_terminal_claim(store: Store) -> object:
    items = store.find("terminal-claim")
    if items:
        return copy.deepcopy(items[-1]["body"])
    capsule = _imported_capsule(store)
    if capsule is not None:
        contest_index = store.contract.stages.index("contest")
        if _restart_frontier_index(store) < contest_index or any(
            store.contract.stages.index(item["stage"]) < contest_index
            for item in store.find("envelope")
            if not item["body"]["document"]["status"].startswith("failed: ")
        ):
            return _MISSING
        return copy.deepcopy(capsule["terminal-claim"])
    return _MISSING


def _stored_field_order_origin(store: Store) -> str:
    generate = store.find("envelope", "generate")
    if generate:
        document = generate[-1]["body"]["document"]
        if document["status"].startswith("failed: "):
            raise StoreReadLoss(
                "store read failed: failed Generate envelope has no field-order authority"
            )
        value = document["artifacts"]["field"]
        if not isinstance(value, list):
            raise StoreReadLoss(
                "store read failed: Generate ran but holds no validated field order"
            )
        return "generate-produced"
    capsule = _imported_capsule(store)
    if capsule is not None:
        if _restart_frontier_index(store) <= store.contract.stages.index("generate"):
            raise StoreReadLoss(
                "store read failed: imported field-order origin is invalidated until Generate reruns"
            )
        origin = capsule["field-order-origin"]
        if origin not in store.contract.field_order_origins:
            raise StoreReadLoss(
                "store read failed: imported capsule holds no produced field-order-origin"
            )
        return origin
    return "user-supplied"


def _stored_field_wordings(store: Store) -> list[str]:
    """The input field Prune cut from: Generate's validated field, else the
    imported capsule's original field, else the supplied candidate set
    (closed-to-widening)."""
    return [option["wording"] for option in _stored_field(store)]


def _stored_field(store: Store) -> list[dict]:
    """Return the exact option objects that form Prune's current input field."""
    value = _effective_stage_artifact(store, "generate", "field", "original-field")
    if value is not _MISSING:
        if isinstance(value, list):
            return value
        raise StoreReadLoss(
            "store read failed: current Generate source holds no validated field list"
        )
    if _imported_capsule(store) is not None:
        raise StoreReadLoss(
            "store read failed: imported field is invalidated until Generate reruns"
        )
    echo = store.require("echo")["body"]
    if echo["fields"]["field-mode"]["value"] != "closed-to-widening":
        raise StoreReadLoss(
            "store read failed: required run-state item absent: envelope for stage generate"
        )
    decomposition = store.require("decomposition")
    return [
        {"wording": candidate["wording"], "provenance": candidate["provenance-flag"]}
        for candidate in decomposition["body"]["candidates"]
    ]


def _stored_survivors(store: Store) -> list[dict]:
    value = _effective_stage_artifact(store, "prune", "survivors", "survivors")
    if isinstance(value, list):
        return value
    raise StoreReadLoss(
        "store read failed: required run-state item absent: envelope for stage prune"
    )


def _stored_survivor_wordings(store: Store) -> list[str]:
    return [opt["wording"] for opt in _stored_survivors(store)]


def _recommend_excluded_options(store: Store) -> set[str]:
    """Options actively excluded by Recommend: live envelope first, else the
    imported capsule's recommend-basis active records."""
    records = _effective_records(store)
    if records is _MISSING:
        return set()
    return {
        r["option"]
        for r in records
        if r["status"] == "active" and r["cut-basis"] in store.contract.recommend_bases
    }


def _accepted_retrievals(store: Store) -> list[dict]:
    """Every accepted retrieval with its effective concerns (amendments
    applied). Imported-capsule retrievals carry effective concerns already and
    are superseded per producing stage by any re-run envelope."""
    facts: list[dict] = []
    envelope_items = [
        item
        for item in store.find("envelope")
        if not item["body"]["document"]["status"].startswith("failed: ")
    ]
    earliest_live = min(
        (store.contract.stages.index(item["stage"]) for item in envelope_items),
        default=len(store.contract.stages),
    )
    earliest_live = min(earliest_live, _restart_frontier_index(store))
    capsule_retrievals = _capsule_value(store, "retrievals")
    if isinstance(capsule_retrievals, list):
        facts.extend(
            dict(entry)
            for entry in capsule_retrievals
            if store.contract.stages.index(entry["producing-stage"]) < earliest_live
        )
    for item in envelope_items:
        document = item["body"]["document"]
        if document["status"].startswith("failed: "):
            continue
        retrievals = document["retrievals"]
        if retrievals == "none":
            continue
        for entry in retrievals:
            facts.append(
                {
                    "producing-stage": document["stage"],
                    "source": entry["source"],
                    "retrieved-at": entry["retrieved-at"],
                    "fact": entry["fact"],
                    "concerns": entry["concerns"],
                }
            )
    for item in envelope_items:
        if item["body"]["document"]["status"].startswith("failed: "):
            continue
        for amendment in item["body"]["amendments"]:
            ref = amendment["retrieval"]
            for factentry in facts:
                if (
                    factentry["producing-stage"] == ref["producing-stage"]
                    and factentry["source"] == ref["source"]
                    and factentry["retrieved-at"] == ref["retrieved-at"]
                ):
                    base = factentry["concerns"]
                    names = [] if base == "candidate-neutral" else list(base)
                    if amendment["option"] not in names:
                        names.append(amendment["option"])
                    factentry["concerns"] = names
    return facts


def _resolve_citations(document: dict, store: Store) -> list[dict]:
    """Every record citation must resolve to a stored or same-envelope
    retrieval. Returns the concerns amendments acceptance owes."""
    op = "record citation resolution"
    stage = document["stage"]
    stored = _accepted_retrievals(store)
    same_envelope = document["retrievals"]
    local = (
        []
        if same_envelope == "none"
        else [
            {
                "producing-stage": stage,
                "source": e["source"],
                "retrieved-at": e["retrieved-at"],
            }
            for e in same_envelope
        ]
    )
    known = {(f["producing-stage"], f["source"], f["retrieved-at"]) for f in stored}
    known |= {(e["producing-stage"], e["source"], e["retrieved-at"]) for e in local}
    amendments: list[dict] = []
    for key in ("exclusion-records", "disposition-records"):
        records = document["artifacts"].get(key)
        if not isinstance(records, list):
            continue
        for record in records:
            for ref in record.get("evidence-provenance") or []:
                matches = [
                    k
                    for k in known
                    if k[1] == ref["source"] and k[2] == ref["retrieved-at"]
                ]
                if len(matches) != 1:
                    raise fail(
                        op,
                        "evidence-provenance must resolve to exactly one stored or same-envelope retrieval",
                        {"reference": ref, "matches": sorted(matches)},
                    )
                producing = matches[0][0]
                amendments.append(
                    {
                        "retrieval": {
                            "producing-stage": producing,
                            "source": ref["source"],
                            "retrieved-at": ref["retrieved-at"],
                        },
                        "option": record["option"],
                    }
                )
    return amendments


def _is_order_preserving_subsequence(survivors: list[str], field: list[str]) -> bool:
    it = iter(field)
    return all(any(word == candidate for candidate in it) for word in survivors)


def _validate_stage_readiness(stage: str, store: Store, op: str) -> None:
    """Refuse stage jumps and cardinality-invalid comparative stages."""
    mode = store.require("echo")["body"]["fields"]["field-mode"]["value"]
    if stage == "generate":
        if mode == "closed-to-widening":
            raise refuse(op, "Generate is skipped in closed-to-widening mode")
        return
    if stage == "prune":
        _stored_field(store)
        return
    if stage in {"shape", "recommend"}:
        survivors = _stored_survivors(store)
        if len(survivors) < 2:
            raise refuse(
                op,
                f"{stage.capitalize()} requires at least two survivors; zero/one survivor closes without comparative work",
            )
        if stage == "recommend":
            for artifact_key, capsule_key in (
                ("comparison-surface", "surface"),
                ("constraint-consequences", "consequences"),
            ):
                value = _effective_stage_artifact(
                    store, "shape", artifact_key, capsule_key
                )
                if value is _MISSING or not _is_produced(value):
                    raise StoreReadLoss(
                        f"store read failed: Recommend requires accepted Shape artifact {artifact_key}"
                    )
        return
    if stage == "contest":
        _validate_contest_basis(store, op)


def validate_envelope_against_store(
    document: dict, store: Store, contract: Contract
) -> list[dict]:
    """Full acceptance validation; returns the concerns amendments owed."""
    stage = document["stage"]
    _validate_restart_stage_frontier(stage, store, f"envelope validation ({stage})")
    _validate_stage_readiness(stage, store, f"envelope validation ({stage})")
    artifacts = document["artifacts"]
    if stage == "generate":
        field = artifacts.get("field")
        if isinstance(field, list):
            by_wording = {option["wording"]: option for option in field}
            candidates = store.require("decomposition")["body"]["candidates"]
            owed_seeds = [
                candidate
                for candidate in candidates
                if candidate["provenance-flag"] != "generated"
            ]
            missing_or_changed = [
                candidate["wording"]
                for candidate in owed_seeds
                if by_wording.get(candidate["wording"])
                != {
                    "wording": candidate["wording"],
                    "provenance": candidate["provenance-flag"],
                }
            ]
            if missing_or_changed:
                raise fail(
                    "envelope validation (generate)",
                    "every non-generated setup candidate must survive byte-exactly as a collapse-exempt seed",
                    missing_or_changed,
                )
            owed_by_wording = {
                candidate["wording"]: candidate["provenance-flag"]
                for candidate in owed_seeds
            }
            fabricated_authority = [
                option
                for option in field
                if option["provenance"] != "generated"
                and owed_by_wording.get(option["wording"]) != option["provenance"]
            ]
            if fabricated_authority:
                raise fail(
                    "envelope validation (generate)",
                    "Generate may mark only exact setup seeds as non-generated; every new option must be generated",
                    fabricated_authority,
                )
    if stage == "prune":
        op = "envelope validation (prune)"
        field_options = _stored_field(store)
        field = [option["wording"] for option in field_options]
        field_duplicates = {w for w in field if field.count(w) > 1}
        if field_duplicates:
            raise fail(
                op,
                f"duplicate wordings in the stored input field — the partition is ill-defined: {sorted(field_duplicates)}",
            )
        survivors = artifacts.get("survivors")
        if isinstance(survivors, list):
            wordings = [opt["wording"] for opt in survivors]
            if not _is_order_preserving_subsequence(wordings, list(field)):
                raise fail(
                    op,
                    "survivors are not an order-preserving subsequence of the input field — Prune cuts, never reorders",
                    wordings,
                )
            by_wording = {option["wording"]: option for option in field_options}
            changed = [
                option
                for option in survivors
                if option != by_wording.get(option["wording"])
            ]
            if changed:
                raise fail(
                    op,
                    "survivors must preserve each input option object exactly, including provenance and insertion",
                    changed,
                )
        records = artifacts.get("exclusion-records")
        if isinstance(records, list):
            for record in records:
                _check_record(record, contract, field, "prune")
                input_option = next(
                    option
                    for option in field_options
                    if option["wording"] == record["option"]
                )
                if (
                    input_option["provenance"] == "revived"
                    and record["status"] == "active"
                ):
                    raise refuse(
                        op,
                        f"revived option {record['option']!r} is pinned against delegated Prune cuts; route any remaining conflict downstream",
                    )
        if isinstance(survivors, list) and isinstance(records, list):
            survivor_set = {opt["wording"] for opt in survivors}
            record_options = [r["option"] for r in records]
            duplicates = {w for w in record_options if record_options.count(w) > 1}
            if duplicates:
                raise fail(
                    op,
                    f"more than one exclusion record for the same option: {sorted(duplicates)}",
                )
            overlap = survivor_set & set(record_options)
            if overlap:
                raise fail(
                    op,
                    "an option is both a survivor and actively excluded — the partition must be disjoint",
                    sorted(overlap),
                )
            dropped = [
                w for w in field if w not in survivor_set and w not in record_options
            ]
            if dropped:
                raise fail(
                    op,
                    "input option(s) dropped with no exclusion record — every exclusion is ledgered, and the partition must be conserved",
                    dropped,
                )
    if stage == "recommend":
        records = artifacts.get("disposition-records")
        if isinstance(records, list):
            allowed = _stored_survivor_wordings(store)
            for record in records:
                _check_record(record, contract, allowed, "recommend")
    amendments = _resolve_citations(document, store)
    return [] if document["status"].startswith("failed: ") else amendments


def _classified_pin_mismatch_terminal(status: str) -> str | None:
    prefix = "failed: pin mismatch — "
    if not status.startswith(prefix):
        return None
    surface = status.removeprefix(prefix)
    for surface_class, terminal in (
        ("constituent", "constituent drift"),
        ("evidence", "evidence drift"),
        ("method", "method drift"),
    ):
        path_prefix = f"{surface_class}:"
        if (
            surface.startswith(path_prefix)
            and surface.removeprefix(path_prefix).strip()
        ):
            return terminal
    return None


def cmd_validate_envelope(args: argparse.Namespace) -> int:
    readset = ReadSet()
    contract = load_contract(Path(args.data), readset)
    envelope_path = readset.allow(Path(args.envelope))
    raw = readset.read_bytes(envelope_path)
    document = safe_parse(
        raw,
        byte_cap=contract.bounds["parse-bytes"],
        depth_cap=contract.bounds["parse-depth"],
        op="envelope",
    )
    canonicalize_generate_wordings(document)
    validate_envelope_shape(document, contract)
    if args.stage and document["stage"] != args.stage:
        raise fail(
            "envelope validation",
            f"envelope stage {document['stage']!r} does not match the dispatched stage {args.stage!r}",
        )
    store = Store(Path(args.store), contract, readset)
    amendments = validate_envelope_against_store(document, store, contract)
    terminal = _classified_pin_mismatch_terminal(document["status"])
    mapped_terminal = terminal
    if document["status"].startswith("failed: ") and mapped_terminal is None:
        mapped_terminal = (
            "underlying terminal stands; exclusion check unavailable"
            if document["stage"] == "contest"
            else f"stage failed: {document['stage']}"
        )
    if args.accept:
        # one atomic write: the envelope and its owed concerns amendments land
        # in a single item file, so neither is ever visible without the other
        store.write(
            {
                "schema": RUNSTATE_SCHEMA,
                "kind": "envelope",
                "run": store.require("echo")["run"],
                "seq": store.next_seq(),
                "stage": document["stage"],
                "body": {"document": document, "amendments": amendments},
            },
            writer="validate-envelope",
        )
    print(
        f"envelope valid: stage={document['stage']} status={document['status']!r}"
        + (f" terminal={mapped_terminal!r}" if mapped_terminal else "")
        + (
            f" recorded with {len(amendments)} concerns amendment(s)"
            if args.accept
            else ""
        )
    )
    return EXIT_PASS


# ---------------------------------------------------------------------------
# Stage-brief rendering
# ---------------------------------------------------------------------------


def _effective_survivor_share(facts: list[dict], survivors: list[str]) -> list[dict]:
    out = []
    for fact in facts:
        concerns = fact["concerns"]
        if concerns == "candidate-neutral":
            out.append(fact)
        elif isinstance(concerns, list) and all(name in survivors for name in concerns):
            out.append(fact)
    return out


def _method_text(stage: str, contract: Contract, readset: ReadSet) -> str:
    methods_path = contract.data_path.parent / "methods.md"
    readset.allow(methods_path)
    text = readset.read_bytes(methods_path).decode("utf-8")
    start = f"<!-- method:{stage} -->"
    end = f"<!-- /method:{stage} -->"
    if start not in text or end not in text:
        raise fail("method extraction", f"markers for {stage} not found in methods.md")
    return text.split(start, 1)[1].split(end, 1)[0].strip()


def _render_packet_item(
    key: str, stage: str, store: Store, contract: Contract, readset: ReadSet
) -> str | None:
    """Render one packet item's content from byte-exact store items.
    Returns None when a conditional item has nothing to carry."""
    echo_fields = store.require("echo")["body"]["fields"]
    decomposition = store.require("decomposition")["body"]

    def echo_field(name: str) -> object:
        if name not in echo_fields:
            raise StoreReadLoss(f"store read failed: echo field absent: {name}")
        return echo_fields[name]

    if key == "frame":
        return dump_yaml({"frame": decomposition["frame"]})
    if key == "field-mode":
        return dump_yaml({"field-mode": echo_field("field-mode")})
    if key == "constraints":
        return dump_yaml({"constraints": echo_field("constraints")})
    if key == "values":
        return dump_yaml({"values": decomposition["values"]})
    if key == "soft-prefs":
        return dump_yaml({"soft-prefs": decomposition["soft-prefs"]})
    if key == "evidence":
        pins = store.require("pins")["body"]
        return dump_yaml(
            {
                "evidence-inputs": echo_field("evidence-inputs"),
                "evidence-authorization": echo_field("evidence-authorization"),
                "pinned-evidence-identifiers": pins["evidence"],
            }
        )
    if key == "budget":
        return dump_yaml({"survivor-budget": echo_field("survivor-budget")})
    if key == "seeds":
        # every non-`generated` provenance flag rides as a seed: user-seed,
        # revived, accepted, adopted — a user-authorized candidate never
        # silently drops from regeneration
        seeds = [
            c
            for c in decomposition["candidates"]
            if c["provenance-flag"] != "generated"
        ]
        return dump_yaml(
            {
                "seeds": [
                    {"wording": c["wording"], "provenance": c["provenance-flag"]}
                    for c in seeds
                ]
            }
        )
    if key == "field":
        envelopes = store.find("envelope", "generate")
        if envelopes:
            document = envelopes[-1]["body"]["document"]
            if document["status"].startswith("failed: "):
                raise StoreReadLoss(
                    "store read failed: failed Generate envelope has no field authority"
                )
            artifacts = document["artifacts"]
            if not isinstance(artifacts["field"], list):
                raise StoreReadLoss(
                    "store read failed: Generate envelope holds no validated field"
                )
            return dump_yaml(
                {
                    "field": artifacts["field"],
                    "fixed-points-line": artifacts["fixed-points-line"],
                }
            )
        capsule = _imported_capsule(store)
        if capsule is not None:
            imported = _effective_stage_artifact(
                store, "generate", "field", "original-field"
            )
            if not isinstance(imported, list):
                raise StoreReadLoss(
                    "store read failed: imported field is invalidated until Generate reruns"
                )
            return dump_yaml(
                {
                    "field": imported,
                    "fixed-points-line": capsule.get(
                        "generation-boundary", "not produced"
                    ),
                }
            )
        return dump_yaml(
            {
                "field": [
                    {"wording": c["wording"], "provenance": c["provenance-flag"]}
                    for c in decomposition["candidates"]
                ],
                "fixed-points-line": "Generate not run: closed-to-widening",
            }
        )
    if key == "survivors":
        survivors_value = _stored_survivors(store)
        origin = _stored_field_order_origin(store)
        provenance = _order_origin_label(contract, origin)
        return dump_yaml({"survivors": survivors_value, "order-provenance": provenance})
    if key == "authority-notes-survivor":
        survivors = _stored_survivor_wordings(store)
        notes = [
            {"option": c["wording"], "authority-note": c["authority-note"]}
            for c in decomposition["candidates"]
            if c["wording"] in survivors
            and c.get("authority-note") not in (None, "absent")
        ]
        return dump_yaml({"authority-notes": notes})
    if key == "authority-notes-excluded":
        survivors = set(_stored_survivor_wordings(store))
        excluded_by_recommend = _recommend_excluded_options(store)
        notes = [
            {"option": c["wording"], "authority-note": c["authority-note"]}
            for c in decomposition["candidates"]
            if (c["wording"] not in survivors or c["wording"] in excluded_by_recommend)
            and c.get("authority-note") not in (None, "absent")
        ]
        return dump_yaml({"authority-notes": notes})
    if key == "records":
        records = _effective_records(store)
        if records is _MISSING:
            return dump_yaml({"records": []})
        return dump_yaml(
            {"records": [record for record in records if record["status"] == "active"]}
        )
    if key == "retrievals":
        facts = _accepted_retrievals(store)
        cell = contract.cell("retrievals", stage)
        if cell.get("qualifier") == "survivor share":
            facts = _effective_survivor_share(facts, _stored_survivor_wordings(store))
        return dump_yaml({"retrievals": facts})
    if key == "overflow":
        value = _effective_stage_artifact(
            store, "prune", "overflow-disclosure", "overflow"
        )
        if not isinstance(value, dict):
            return None
        # existence and identity only — Prune's per-cut reasoning never crosses
        return dump_yaml(
            {
                "overflow": {
                    "disclosure": value["disclosure"],
                    "blocked-trades": [
                        {
                            "option": cut["option"],
                            "unpriced-trade": cut["unpriced-trade"],
                        }
                        for cut in value["blocked-cuts"]
                    ],
                }
            }
        )
    if key == "consequences":
        value = _effective_stage_artifact(
            store, "shape", "constraint-consequences", "consequences"
        )
        if value is _MISSING or not isinstance(value, list):
            raise StoreReadLoss(
                "store read failed: required run-state item absent: envelope for stage shape"
            )
        return dump_yaml({"constraint-consequences": value})
    if key == "surface":
        value = _effective_stage_artifact(
            store, "shape", "comparison-surface", "surface"
        )
        if not isinstance(value, str) or _is_not_produced(value):
            if stage == "recommend":
                raise StoreReadLoss(
                    "store read failed: required run-state item absent: envelope for stage shape"
                )
            return None
        return dump_yaml({"comparison-surface": value})
    if key == "close":
        value = _effective_stage_artifact(store, "recommend", "close", "close")
        if not isinstance(value, str) or _is_not_produced(value):
            return None
        return dump_yaml({"close": value})
    if key == "terminal-claim":
        value = _effective_terminal_claim(store)
        if isinstance(value, dict):
            return dump_yaml({"terminal-claim": value})
        return None
    if key == "stakes":
        return dump_yaml({"stakes": decomposition["stakes"]})
    if key == "composition-provenance":
        return dump_yaml(
            {"composition-provenance": decomposition["composition-provenance"]}
        )
    if key == "method":
        return _method_text(stage, contract, readset)
    if key == "pin":
        pins = store.require("pins")["body"]
        constituent = {
            "generate": "ideate",
            "shape": "option-shaping",
            "recommend": "making-recommendations",
        }[stage]
        return dump_yaml(
            {"constituent": constituent, "pins": pins["constituents"][constituent]}
        )
    raise refuse("brief render", f"no renderer for packet item {key!r}")


def _validate_terminal_claim_against_store(body: dict, store: Store) -> None:
    op = "terminal-claim validation"
    if _is_failure_terminal(body["terminal"], store.contract):
        raise refuse(op, "failure terminals stop before Contest and cannot own a claim")
    records = _effective_records(store)
    active_records = (
        [record for record in records if record["status"] == "active"]
        if isinstance(records, list)
        else []
    )
    if not active_records:
        raise refuse(
            op, "terminal-claim is valid only when active records make Contest eligible"
        )
    close = _effective_stage_artifact(store, "recommend", "close", "close")
    if close is not _MISSING and _is_produced(close):
        raise fail(op, "a produced close forbids terminal-claim")
    survivors = _stored_survivors(store)
    if len(survivors) == 1:
        if body["survivor"] != survivors[0]["wording"]:
            raise fail(
                op, "one-survivor claim must name that survivor", body["survivor"]
            )
    elif body["survivor"] != "not applicable":
        raise fail(
            op, "claim survivor must be `not applicable` off the one-survivor branch"
        )
    terminal_states = store.find("terminal-state")
    if terminal_states and body["terminal"] != terminal_states[-1]["body"]["terminal"]:
        raise fail(
            op, "claim terminal does not match recorded terminal", body["terminal"]
        )


def _validate_contest_basis(store: Store, op: str = "brief render (contest)") -> None:
    records = _effective_records(store)
    active_records = (
        [record for record in records if record["status"] == "active"]
        if isinstance(records, list)
        else []
    )
    if not active_records:
        raise refuse(
            op, "Contest is ineligible because no active exclusion record exists"
        )
    close = _effective_stage_artifact(store, "recommend", "close", "close")
    claim = _effective_terminal_claim(store)
    close_produced = close is not _MISSING and _is_produced(close)
    claim_produced = isinstance(claim, dict)
    if close_produced and claim_produced:
        raise fail(op, "Contest cannot receive both a close and a terminal-claim")
    if not close_produced and not claim_produced:
        raise StoreReadLoss(
            "store read failed: eligible close-less Contest requires a terminal-claim"
        )
    if claim_produced:
        _validate_terminal_claim_against_store(claim, store)


def render_brief(
    stage: str,
    store: Store,
    contract: Contract,
    readset: ReadSet,
    requested: list[str] | None,
) -> str:
    _validate_restart_stage_frontier(stage, store, "brief render")
    _validate_stage_readiness(stage, store, "brief render")
    column = [entry["key"] for entry in contract.include_column(stage)]
    if requested is not None:
        off_column = [key for key in requested if key not in column]
        if off_column:
            raise refuse(
                "brief render",
                f"off-column packet item(s) requested into the {stage} brief: {off_column} — "
                f"the {stage} column includes only {column}",
            )
        missing = [key for key in column if key not in requested]
        if missing:
            raise refuse(
                "brief render",
                f"partial-column render refused for {stage} — a packet is the complete "
                f"include column, never a subset; missing: {missing}",
            )
    keys = column
    sections = []
    for key in keys:
        content = _render_packet_item(key, stage, store, contract, readset)
        if content is None:
            continue
        sections.append(f"## packet: {key}\n\n{content.rstrip()}\n")
    obliged_lines = []
    for entry in contract.obliged[stage]:
        shape = contract.data["artifact-shapes"][entry["shape"]]
        obliged_lines.append(f"  - `{entry['key']}` ({entry['required']}) — {shape}")
    template = contract.data["stage-brief-template"]
    extras = contract.data["brief-extras"][stage]
    brief = template.format(
        stage=stage,
        packet="\n".join(sections).rstrip(),
        obliged="\n".join(obliged_lines),
        **{
            "retrieval-cap": contract.bounds["per-stage-retrievals"],
            "extras": extras.rstrip(),
        },
    )
    return brief


def cmd_render_brief(args: argparse.Namespace) -> int:
    readset = ReadSet()
    contract = load_contract(Path(args.data), readset)
    if args.stage not in contract.stages:
        raise refuse("brief render", f"unknown stage: {args.stage!r}")
    store = Store(Path(args.store), contract, readset)
    requested = args.items.split(",") if args.items else None
    brief = render_brief(args.stage, store, contract, readset, requested)
    brief_id = sha256_bytes(brief.encode("utf-8"))
    run = store.require("echo")["run"]
    store.write(
        {
            "schema": RUNSTATE_SCHEMA,
            "kind": "brief-render",
            "run": run,
            "seq": store.next_seq(),
            "stage": args.stage,
            "body": {"brief-id": brief_id},
        },
        writer="render-brief",
    )
    sys.stderr.write(f"brief-id: {brief_id} (recorded in run state before dispatch)\n")
    sys.stdout.write(brief)
    return EXIT_PASS


# ---------------------------------------------------------------------------
# Store commands
# ---------------------------------------------------------------------------


def _initialize_setup_store(
    root: Path,
    run: str,
    setup_document: object,
    contract: Contract,
    readset: ReadSet,
) -> Store:
    """Create one store and persist helper-derived echo then decomposition."""
    echo, decomposition = normalize_setup_document(setup_document, contract)
    if root.exists():
        raise refuse(
            "store init",
            f"store path already exists — retire the orphan via `trash` first: {root}",
        )
    parent = Path(os.path.realpath(root.parent))
    readset.allow(parent)
    root.mkdir(mode=0o700)
    store = Store(root, contract, readset)
    store.write(
        {
            "schema": RUNSTATE_SCHEMA,
            "kind": "echo",
            "run": run,
            "seq": 0,
            "body": echo,
        },
        writer="init-setup",
    )
    store.write(
        {
            "schema": RUNSTATE_SCHEMA,
            "kind": "decomposition",
            "run": run,
            "seq": 1,
            "body": decomposition,
        },
        writer="init-setup",
    )
    return store


def cmd_init_setup(args: argparse.Namespace) -> int:
    readset = ReadSet()
    contract = load_contract(Path(args.data), readset)
    root = Path(args.store)
    setup_path = readset.allow(Path(args.setup))
    setup_document = safe_parse(
        readset.read_bytes(setup_path),
        byte_cap=contract.bounds["parse-bytes"],
        depth_cap=contract.bounds["parse-depth"],
        op="setup document",
    )
    _initialize_setup_store(root, args.run, setup_document, contract, readset)
    print(
        f"setup initialized: {root} (echo seq 0, decomposition seq 1, run {args.run})"
    )
    return EXIT_PASS


def cmd_write_item(args: argparse.Namespace) -> int:
    readset = ReadSet()
    contract = load_contract(Path(args.data), readset)
    if args.kind not in contract.generic_write_kinds:
        raise refuse(
            "write-item",
            f"kind {args.kind!r} is reserved for its dedicated command; generic kinds are {sorted(contract.generic_write_kinds)}",
        )
    store = Store(Path(args.store), contract, readset)
    body_path = readset.allow(Path(args.body))
    body = safe_parse(
        readset.read_bytes(body_path),
        byte_cap=contract.bounds["parse-bytes"],
        depth_cap=contract.bounds["parse-depth"],
        op="item body",
    )
    run = store.require("echo")["run"]
    item = {
        "schema": RUNSTATE_SCHEMA,
        "kind": args.kind,
        "run": run,
        "seq": store.next_seq(),
        "body": body,
    }
    if args.stage:
        item["stage"] = args.stage
    path = store.write(item, writer="write-item")
    print(f"item written: {path.name}")
    return EXIT_PASS


def _resolve_proof_inputs_body_path(args: argparse.Namespace) -> Path:
    """Resolve exactly one supported proof-input body spelling."""
    positional = args.body
    named = args.body_option
    if (positional is None) == (named is None):
        raise refuse(
            "proof inputs",
            "supply exactly one body path as positional BODY or --body PATH",
            {"BODY": positional, "--body": named},
        )
    return Path(positional if positional is not None else named)


def cmd_record_proof_inputs(args: argparse.Namespace) -> int:
    resolved_body_path = _resolve_proof_inputs_body_path(args)
    readset = ReadSet()
    contract = load_contract(Path(args.data), readset)
    store = Store(Path(args.store), contract, readset)
    body_path = readset.allow(resolved_body_path)
    body = safe_parse(
        readset.read_bytes(body_path),
        byte_cap=contract.bounds["parse-bytes"],
        depth_cap=contract.bounds["parse-depth"],
        op="proof inputs",
    )
    _check_proof_boundary_shape("proof inputs", body, contract)
    pins = store.require("pins")["body"]
    if body["constituent-pins"] != pins["constituents"]:
        raise fail("proof inputs", "constituent pins differ from the store pins item")
    if body["method-identity"] != pins["method"]:
        raise fail("proof inputs", "method identity differs from the store pins item")
    path = store.write(
        {
            "schema": RUNSTATE_SCHEMA,
            "kind": "proof-inputs",
            "run": store.require("echo")["run"],
            "seq": store.next_seq(),
            "body": body,
        },
        writer="record-proof-inputs",
    )
    print(f"proof inputs recorded: {path.name}")
    return EXIT_PASS


def cmd_record_terminal(args: argparse.Namespace) -> int:
    readset = ReadSet()
    contract = load_contract(Path(args.data), readset)
    store = Store(Path(args.store), contract, readset)
    body = {"terminal": args.terminal, "carrier": args.carrier}
    terminal_claims = store.find("terminal-claim")
    if terminal_claims and terminal_claims[-1]["body"]["terminal"] != args.terminal:
        raise fail(
            "terminal recording",
            "terminal differs from the stored terminal-claim",
            args.terminal,
        )
    path = store.write(
        {
            "schema": RUNSTATE_SCHEMA,
            "kind": "terminal-state",
            "run": store.require("echo")["run"],
            "seq": store.next_seq(),
            "body": body,
        },
        writer="record-terminal",
    )
    print(f"terminal recorded: {path.name} terminal={args.terminal!r}")
    return EXIT_PASS


def cmd_validate_runstate(args: argparse.Namespace) -> int:
    readset = ReadSet()
    contract = load_contract(Path(args.data), readset)
    item_path = readset.allow(Path(args.item))
    parsed = safe_parse(
        readset.read_bytes(item_path),
        byte_cap=contract.bounds["parse-bytes"],
        depth_cap=contract.bounds["parse-depth"],
        op="run-state item",
    )
    validate_runstate_item(parsed, contract)
    print(f"run-state item valid: kind={parsed['kind']} seq={parsed['seq']}")
    return EXIT_PASS


# ---------------------------------------------------------------------------
# Capsule validation
# ---------------------------------------------------------------------------


def _strip_fences(text: str) -> str:
    lines = text.strip().splitlines()
    if lines and lines[0].startswith("```") and lines[-1].startswith("```"):
        return "\n".join(lines[1:-1]) + "\n"
    return text if text.endswith("\n") else text + "\n"


def _check_capsule_record(record: object, contract: Contract) -> None:
    """Capsule records may be `active` or `revived` and carry any declared cut
    basis; the key set and enums still bind exactly."""
    _check_record_shape(record, contract, "capsule record validation")


def _is_produced(value: object) -> bool:
    return not _is_not_produced(value) and value != "not applicable"


def _order_origin_label(contract: Contract, origin: str) -> str:
    return contract.order_origin_labels[origin]


def _check_capsule_retrievals(value: object, contract: Contract, op: str) -> list[dict]:
    if not isinstance(value, list):
        raise fail(op, "retrievals must be a list", value)
    identities: list[tuple[str, str, str]] = []
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != {
            "producing-stage",
            "source",
            "retrieved-at",
            "fact",
            "concerns",
        }:
            raise fail(
                op,
                "capsule retrievals must be exactly {producing-stage, source, retrieved-at, fact, concerns}",
                entry,
            )
        if entry["producing-stage"] not in contract.stages:
            raise fail(
                op, "retrieval producing-stage is unknown", entry["producing-stage"]
            )
        for key in ("source", "retrieved-at", "fact"):
            _require_str(op, f"retrieval {key}", entry[key])
        concerns = entry["concerns"]
        if concerns != "candidate-neutral":
            names = _require_str_list(op, "retrieval concerns", concerns)
            if not names:
                raise fail(op, "retrieval concerns must not be empty", concerns)
            if len(names) != len(set(names)):
                raise fail(op, "retrieval concerns contain duplicates", names)
        identities.append(
            (entry["producing-stage"], entry["source"], entry["retrieved-at"])
        )
    duplicates = {identity for identity in identities if identities.count(identity) > 1}
    if duplicates:
        raise fail(
            op,
            "capsule retrieval identities must be unique",
            sorted(duplicates),
        )
    return value


def _check_recommend_authority_packet(
    value: object,
    *,
    survivors: object,
    overflow: object,
    decomposition: dict,
    field_order_origin: object,
    contract: Contract,
    op: str,
) -> None:
    if _is_not_produced(value):
        return
    expected = {
        "survivors",
        "order-provenance",
        "authority-notes",
        "overflow",
        "stakes",
    }
    if not isinstance(value, dict) or set(value) != expected:
        raise fail(
            op,
            f"recommend-authority-packet must be exactly {sorted(expected)} or `not produced: <reason>`",
            value,
        )
    if not isinstance(survivors, list):
        raise fail(op, "a produced recommend-authority-packet requires survivors")
    _check_option_list(
        value["survivors"], f"{op} (recommend packet survivors)", contract
    )
    if value["survivors"] != survivors:
        raise fail(
            op, "recommend-authority-packet survivors must equal capsule survivors"
        )
    if field_order_origin not in contract.field_order_origins:
        raise fail(
            op, "a produced recommend-authority-packet requires field-order-origin"
        )
    expected_label = _order_origin_label(contract, field_order_origin)
    if value["order-provenance"] != expected_label:
        raise fail(
            op,
            "recommend-authority-packet order-provenance does not match field-order-origin",
            value["order-provenance"],
        )
    notes = value["authority-notes"]
    if not isinstance(notes, list):
        raise fail(
            op, "recommend-authority-packet authority-notes must be a list", notes
        )
    survivor_wordings = {option["wording"] for option in survivors}
    decomposition_notes = {
        candidate["wording"]: candidate["authority-note"]
        for candidate in decomposition["candidates"]
    }
    seen: set[str] = set()
    for note_entry in notes:
        if not isinstance(note_entry, dict) or set(note_entry) != {
            "option",
            "authority-note",
        }:
            raise fail(
                op,
                "recommend authority-note entries must be exactly {option, authority-note}",
                note_entry,
            )
        wording = note_entry["option"]
        _require_str(op, "recommend authority-note option", wording)
        if wording not in survivor_wordings or wording in seen:
            raise fail(
                op,
                "recommend authority-note names a non-survivor or duplicate",
                wording,
            )
        _check_authority_note(op, note_entry["authority-note"], contract)
        if decomposition_notes.get(wording) != note_entry["authority-note"]:
            raise fail(
                op,
                "recommend authority-note does not match setup decomposition",
                wording,
            )
        seen.add(wording)
    expected_notes = [
        {
            "option": option["wording"],
            "authority-note": decomposition_notes[option["wording"]],
        }
        for option in survivors
        if option["wording"] in decomposition_notes
        and decomposition_notes[option["wording"]] != "absent"
    ]
    if notes != expected_notes:
        raise fail(
            op,
            "recommend-authority-packet must carry every non-absent survivor authority note in survivor order",
            {"expected": expected_notes, "actual": notes},
        )
    if value["overflow"] != overflow:
        raise fail(
            op, "recommend-authority-packet overflow must equal capsule overflow"
        )
    _require_str(op, "recommend-authority-packet stakes", value["stakes"])
    if value["stakes"] != decomposition["stakes"]:
        raise fail(
            op, "recommend-authority-packet stakes must equal setup decomposition"
        )


def _validate_capsule_partition(
    field: object,
    survivors: object,
    records: object,
    contract: Contract,
    op: str,
    *,
    allow_partial: bool,
) -> None:
    if not isinstance(field, list):
        if isinstance(survivors, list) or isinstance(records, list):
            raise fail(
                op, "survivors and records cannot exist without an original field"
            )
        return
    if not isinstance(survivors, list) or not isinstance(records, list):
        if allow_partial and _is_not_produced(survivors) and _is_not_produced(records):
            return
        raise fail(
            op, "a produced field partition requires survivors and records lists"
        )
    field_wordings = [option["wording"] for option in field]
    survivor_wordings = [option["wording"] for option in survivors]
    if not _is_order_preserving_subsequence(survivor_wordings, field_wordings):
        raise fail(
            op, "capsule survivors are not an order-preserving field subsequence"
        )
    field_by_wording = {option["wording"]: option for option in field}
    changed_survivors = [
        option
        for option in survivors
        if option != field_by_wording.get(option["wording"])
    ]
    if changed_survivors:
        raise fail(
            op,
            "capsule survivors must preserve field option objects exactly",
            changed_survivors,
        )
    active_records = [record for record in records if record["status"] == "active"]
    active_options = [record["option"] for record in active_records]
    duplicates = {
        option for option in active_options if active_options.count(option) > 1
    }
    if duplicates:
        raise fail(
            op, "more than one active record names the same option", sorted(duplicates)
        )
    stray = [
        record["option"]
        for record in records
        if record["option"] not in field_by_wording
    ]
    if stray:
        raise fail(op, "record option is absent from original-field", stray)
    active_prune = [
        record["option"]
        for record in active_records
        if record["cut-basis"] in contract.prune_bases
    ]
    active_recommend = [
        record["option"]
        for record in active_records
        if record["cut-basis"] in contract.recommend_bases
    ]
    survivor_set = set(survivor_wordings)
    if survivor_set & set(active_prune):
        raise fail(op, "an option is both a survivor and actively Prune-excluded")
    expected_prune = [
        wording for wording in field_wordings if wording not in survivor_set
    ]
    if set(active_prune) != set(expected_prune):
        raise fail(
            op,
            "active Prune records must equal original-field minus survivors",
            {"expected": expected_prune, "actual": active_prune},
        )
    if any(option not in survivor_set for option in active_recommend):
        raise fail(
            op, "active Recommend records must name Prune survivors", active_recommend
        )
    revived_prune = [
        record["option"]
        for record in records
        if record["status"] == "revived" and record["cut-basis"] in contract.prune_bases
    ]
    if any(option not in survivor_set for option in revived_prune):
        raise fail(
            op, "revived Prune records must rejoin the survivor set", revived_prune
        )


def _validate_capsule_terminal_state(
    capsule: dict, contract: Contract, op: str
) -> None:
    terminal = capsule["terminal"]
    if _is_capsule_forbidden_terminal(terminal, contract):
        raise refuse(op, f"terminal {terminal!r} cannot be resumable capsule state")
    failure = _is_failure_terminal(terminal, contract)
    field = capsule["original-field"]
    generation_boundary = capsule["generation-boundary"]
    survivors = capsule["survivors"]
    records = capsule["records"]
    surface = capsule["surface"]
    consequences = capsule["consequences"]
    close = capsule["close"]
    leans = capsule["registered-leans"]
    claim = capsule["terminal-claim"]
    seed = capsule["provisional-seed"]
    exclusion = capsule["exclusion-check"]
    recommend_packet = capsule["recommend-authority-packet"]
    if not failure:
        frontier = _capsule_terminal_frontier(terminal, contract, op)
        stage_outputs = {
            "generate": (
                ("original-field", field),
                ("generation-boundary", generation_boundary),
            ),
            "prune": (
                ("survivors", survivors),
                ("records", records),
                ("overflow", capsule["overflow"]),
            ),
            "shape": (("surface", surface), ("consequences", consequences)),
            "recommend": (
                ("close", close),
                ("registered-leans", leans),
                ("provisional-seed", seed),
                ("recommend-authority-packet", recommend_packet),
            ),
            "contest": (),
        }
        if frontier != "complete":
            frontier_index = contract.stages.index(frontier)
            for stage in contract.stages[frontier_index:]:
                for key, value in stage_outputs[stage]:
                    if _is_produced(value):
                        raise fail(
                            op,
                            f"terminal {terminal!r} forbids {key} — its artifact frontier is {frontier}",
                        )
        if terminal in {
            "options not comparable",
            "no basis yet",
            "only one serious option",
        } and not _is_produced(close):
            raise fail(
                op,
                "a Recommend constituent exit carries its exit statement as the close",
            )
    if _is_produced(field) != _is_produced(generation_boundary):
        raise fail(
            op, "original-field and generation-boundary must be produced together"
        )
    if _is_produced(survivors) != _is_produced(records):
        raise fail(op, "survivors and records must be produced together")
    if _is_produced(survivors) and not _is_produced(field):
        raise fail(op, "survivors cannot be produced before original-field")
    if _is_produced(surface) != _is_produced(consequences):
        raise fail(op, "surface and consequences must be produced together")
    if _is_produced(surface) and not _is_produced(survivors):
        raise fail(op, "Shape artifacts cannot be produced before survivors")
    if any(_is_produced(value) for value in (close, leans, seed)) and not _is_produced(
        surface
    ):
        raise fail(op, "Recommend artifacts cannot be produced before Shape artifacts")
    if _is_produced(close):
        required_close_artifacts = [
            ("original-field", field),
            ("survivors", survivors),
            ("surface", surface),
            ("consequences", consequences),
            ("registered-leans", leans),
        ]
        if not failure:
            required_close_artifacts.append(("exclusion-check", exclusion))
        for key, value in required_close_artifacts:
            if not _is_produced(value):
                raise fail(op, f"a produced close requires {key}")
        if _is_produced(claim):
            raise fail(op, "a produced close forbids terminal-claim")
    active_records = (
        [record for record in records if record["status"] == "active"]
        if isinstance(records, list)
        else []
    )
    if exclusion == "exclusion check unavailable" and (failure or not active_records):
        raise fail(
            op,
            "exclusion check unavailable requires a non-failure terminal with active records that made Contest eligible",
        )
    if active_records and not failure:
        if not _is_produced(exclusion):
            raise fail(
                op,
                "active exclusions on a non-failure terminal require exclusion-check",
            )
        if not _is_produced(close) and not isinstance(claim, dict):
            raise fail(op, "eligible close-less terminal requires terminal-claim")
    if isinstance(claim, dict):
        if claim["terminal"] != terminal:
            raise fail(op, "terminal-claim terminal must equal capsule terminal")
        survivor_count = len(survivors) if isinstance(survivors, list) else 0
        if survivor_count == 1:
            if claim["survivor"] != survivors[0]["wording"]:
                raise fail(op, "one-survivor terminal-claim must name that survivor")
        elif claim["survivor"] != "not applicable":
            raise fail(
                op,
                "terminal-claim survivor must be `not applicable` off the one-survivor branch",
            )
    if terminal == "close rendered":
        if not _is_produced(close):
            raise fail(op, "terminal `close rendered` requires a produced close")
        if _is_produced(seed):
            raise fail(op, "terminal `close rendered` forbids a provisional seed")
    if terminal == "no candidate survives the confirmed cuts":
        if not isinstance(survivors, list) or survivors:
            raise fail(op, "zero-survivor terminal requires an empty survivors list")
    if terminal.startswith("one candidate survives the authorized cuts"):
        if not isinstance(survivors, list) or len(survivors) != 1:
            raise fail(op, "one-survivor terminal requires exactly one survivor")
    if terminal == "survivor budget cannot be met without an unstated value trade":
        if not isinstance(capsule["overflow"], dict):
            raise fail(op, "budget terminal requires a produced overflow disclosure")
    if terminal.startswith("field not ready"):
        if not isinstance(seed, dict) or _is_produced(close):
            raise fail(op, "field-not-ready terminal requires a seed and no close")
    if terminal == "stage failed: contest":
        raise fail(
            op,
            "Contest failure maps to `exclusion check unavailable`, never stage failed",
        )
    if terminal.startswith("stage failed:"):
        failed_stage = terminal.removeprefix("stage failed:").strip()
        if failed_stage not in contract.stages:
            raise fail(
                op, "stage-failure terminal must name one declared stage", failed_stage
            )
        if failed_stage == "contest":
            raise fail(
                op,
                "Contest failure preserves the underlying terminal and records an unavailable exclusion check",
            )
        forbidden_by_stage = {
            "generate": (
                field,
                generation_boundary,
                survivors,
                records,
                surface,
                consequences,
                close,
                leans,
                seed,
                exclusion,
                recommend_packet,
            ),
            "prune": (
                survivors,
                records,
                surface,
                consequences,
                close,
                leans,
                seed,
                exclusion,
                recommend_packet,
            ),
            "shape": (
                surface,
                consequences,
                close,
                leans,
                seed,
                exclusion,
                recommend_packet,
            ),
            "recommend": (close, leans, seed, exclusion),
        }
        if any(_is_produced(value) for value in forbidden_by_stage[failed_stage]):
            raise fail(
                op,
                f"stage failed: {failed_stage} cannot carry artifacts from the failed stage or later",
            )
    if not failure and not _is_produced(field):
        raise fail(op, "a non-failure resumable capsule requires an original field")


def _check_canonical_capsule_wordings(parsed: dict, op: str) -> None:
    """Wording canonical-form gate on every capsule read path: since the
    canonicalization contract landed, every stored wording identity is in
    canonical whitespace form, so a capsule carrying a non-canonical wording
    was minted before the contract (or altered since) and is rejected as
    legacy — never silently reinterpreted, because the completeness terminator
    hashes raw bytes and re-admitting rewritten wordings would mint identities
    no run ever validated."""
    surfaces: list[tuple[str, object]] = []
    field = parsed.get("original-field")
    if isinstance(field, list):
        surfaces.extend(
            ("original-field", option.get("wording"))
            for option in field
            if isinstance(option, dict)
        )
    survivors = parsed.get("survivors")
    if isinstance(survivors, list):
        surfaces.extend(
            ("survivors", option.get("wording"))
            for option in survivors
            if isinstance(option, dict)
        )
    records = parsed.get("records")
    if isinstance(records, list):
        surfaces.extend(
            ("records", record.get("option"))
            for record in records
            if isinstance(record, dict)
        )
    decomposition = parsed.get("setup-decomposition")
    if isinstance(decomposition, dict) and isinstance(
        decomposition.get("candidates"), list
    ):
        surfaces.extend(
            ("setup-decomposition candidates", candidate.get("wording"))
            for candidate in decomposition["candidates"]
            if isinstance(candidate, dict)
        )
    seed = parsed.get("provisional-seed")
    if isinstance(seed, dict):
        surfaces.append(("provisional-seed", seed.get("wording")))
    legacy = [
        {"surface": name, "wording": wording}
        for name, wording in surfaces
        if isinstance(wording, str) and _canonical_wording(wording) != wording
    ]
    if legacy:
        raise fail(
            op,
            "option wording is not in canonical whitespace form — a capsule minted before wording canonicalization is legacy and is rejected, never silently reinterpreted; re-run the deliberation",
            legacy,
        )


def validate_capsule_document(
    parsed: object, contract: Contract, *, restart_state: bool = False
) -> dict:
    """Nested capsule validation: key set, per-key shapes, terminal-artifact
    consistency, and the conservation invariant when field, survivors, and
    records are all real."""
    op = "capsule validation"
    if not isinstance(parsed, dict):
        raise fail(op, "capsule is not a mapping", parsed)
    schema = contract.schemas[CAPSULE_SCHEMA]
    keys = {entry["key"] for entry in schema["keys"]}
    unknown = set(parsed) - keys
    if unknown:
        raise fail(op, f"unknown keys rejected: {sorted(unknown)}")
    missing = keys - set(parsed)
    # the terminator is checked at the text layer; a parsed document handed to
    # the import path has already passed it
    missing.discard("capsule-complete")
    if missing:
        raise fail(op, f"missing required keys: {sorted(missing)}")
    if parsed["schema"] != CAPSULE_SCHEMA:
        raise refuse(
            op,
            f"unsupported capsule schema version — resumes only through a shipped migration: {parsed['schema']!r}",
        )
    _require_str(op, "run", parsed["run"])
    _require_str(op, "terminal", parsed["terminal"])
    if "capsule-complete" in parsed and not _is_sha256(parsed["capsule-complete"]):
        raise fail(op, "capsule-complete must be a 64-hex content identifier")
    for key in (
        "field-order-origin",
        "recommend-authority-packet",
        "original-field",
        "generation-boundary",
        "survivors",
        "overflow",
        "records",
        "retrievals",
        "surface",
        "consequences",
        "close",
        "registered-leans",
        "terminal-claim",
        "exclusion-check",
        "provisional-seed",
        "revival-instructions",
    ):
        _reject_empty_not_produced(op, key, parsed[key])

    contract_map = parsed["effective-contract"]
    if not isinstance(contract_map, dict):
        raise fail(op, "effective-contract must be a mapping", contract_map)
    expected_contract = set(contract.capsule_contract_fields)
    if set(contract_map) != expected_contract:
        raise fail(
            op,
            f"effective-contract keys must be exactly {sorted(expected_contract)}",
            sorted(contract_map),
        )
    fields = {name: contract_map[name] for name in contract.echo_contract_fields}
    effective_bounds = _check_bounds(op, contract_map["bounds"], contract)
    _check_contract_fields(
        op,
        fields,
        contract,
        effective_bounds=effective_bounds,
    )
    identity = contract_map["evidence-identity"]
    method_identity = contract_map["method-identity"]
    unproduced_contract_pins = _is_not_produced(identity) or _is_not_produced(
        method_identity
    )
    if unproduced_contract_pins:
        if parsed["terminal"] != "store failed: write":
            raise fail(
                op,
                "pin-derived effective-contract members may be unproduced only on store failed: write",
            )
        if not (_is_not_produced(identity) and _is_not_produced(method_identity)):
            raise fail(
                op,
                "evidence and method identity must be produced or unproduced together",
            )
    else:
        if not isinstance(identity, dict) or set(identity) != {"named", "in-packet"}:
            raise fail(
                op, "evidence-identity must be exactly {named, in-packet}", identity
            )
        _check_pin_list(
            op,
            "evidence-identity.named",
            identity["named"],
            byte_cap=effective_bounds["named-evidence-expanded-bytes"],
        )
        _check_pin_list(
            op,
            "evidence-identity.in-packet",
            identity["in-packet"],
            allow_no_comparable_identity=True,
            allow_manifest=False,
            byte_cap=effective_bounds["in-packet-evidence-bytes"],
        )
        _check_method_pin_inventory(op, "method-identity", method_identity, contract)
    wording = contract_map["invocation-wording"]
    if not isinstance(wording, dict) or set(wording) != {
        "initial",
        "directives",
        "directives-collapsed",
        "source-capsule-id",
    }:
        raise fail(
            op,
            "invocation-wording must be exactly {initial, directives, directives-collapsed, source-capsule-id}",
            wording,
        )
    _require_str(op, "invocation-wording initial", wording["initial"])
    directives = _require_str_list(
        op, "invocation-wording directives", wording["directives"]
    )
    directive_cap = effective_bounds["verbatim-directive-history"]
    if len(directives) > directive_cap:
        raise fail(
            op,
            f"invocation-wording carries {len(directives)} directives past the bound of {directive_cap}",
        )
    collapsed = wording["directives-collapsed"]
    if not isinstance(collapsed, list) or not all(
        _is_sha256(entry) for entry in collapsed
    ):
        raise fail(
            op,
            "invocation-wording directives-collapsed must be a list of 64-hex content identifiers",
            collapsed,
        )
    source_id = wording["source-capsule-id"]
    if source_id != "none" and not _is_sha256(source_id):
        raise fail(
            op, "source-capsule-id must be `none` or a 64-hex identifier", source_id
        )

    decomposition = parsed["setup-decomposition"]
    if not isinstance(decomposition, dict) or set(decomposition) != {
        "frame",
        "candidates",
        "stakes",
        "soft-preferences",
        "composition-provenance",
    }:
        raise fail(
            op,
            "setup-decomposition must be exactly {frame, candidates, stakes, soft-preferences, composition-provenance}",
            decomposition,
        )
    _require_str(op, "setup-decomposition frame", decomposition["frame"])
    _check_candidates(op, decomposition["candidates"], contract)
    _require_str(op, "setup-decomposition stakes", decomposition["stakes"])
    _check_composition_provenance(op, decomposition["composition-provenance"])
    decomposition_source = _check_setup_source(
        op,
        {
            "candidates": [
                {
                    "wording": candidate["wording"],
                    "provenance-flag": candidate["provenance-flag"],
                }
                for candidate in decomposition["candidates"]
            ],
            "soft-preferences": decomposition["soft-preferences"],
            "composition-provenance": decomposition["composition-provenance"],
        },
        contract,
    )
    if decomposition["candidates"] != _candidates_from_source(decomposition_source):
        raise fail(
            op,
            "setup-decomposition candidates differ from its normalized preference source",
        )
    expected_capsule_soft_prefs = {
        "value": _soft_preferences_from_source(decomposition_source),
        "provenance": decomposition_source["soft-preferences"]["provenance"],
    }
    if contract_map["soft-prefs"] != expected_capsule_soft_prefs:
        raise fail(
            op,
            "effective-contract soft-prefs differ from normalized setup-decomposition criteria",
            contract_map["soft-prefs"],
        )
    if decomposition["frame"] != contract_map["frame"]["value"]:
        raise fail(op, "setup-decomposition frame must equal effective-contract frame")
    if decomposition["stakes"] != contract_map["stakes"]["value"]:
        raise fail(
            op, "setup-decomposition stakes must equal effective-contract stakes"
        )
    field = parsed["original-field"]
    if not _is_not_produced(field):
        _check_option_list(field, f"{op} (original-field)", contract)
    _require_str(op, "generation-boundary", parsed["generation-boundary"])
    field_order_origin = parsed["field-order-origin"]
    if isinstance(field, list):
        if field_order_origin not in contract.field_order_origins:
            raise fail(
                op,
                f"produced original-field requires field-order-origin from {sorted(contract.field_order_origins)}",
                field_order_origin,
            )
        if parsed["generation-boundary"] == "Generate not run: closed-to-widening":
            if field_order_origin != "user-supplied":
                raise fail(
                    op, "closed-to-widening field must have user-supplied order origin"
                )
        elif field_order_origin != "generate-produced":
            raise fail(
                op, "a Generate boundary must have generate-produced order origin"
            )
        field_mode = contract_map["field-mode"]["value"]
        closed_marker = "Generate not run: closed-to-widening"
        if field_mode == "seed-and-widen":
            if parsed["generation-boundary"] == closed_marker:
                raise fail(
                    op,
                    "seed-and-widen cannot carry the closed-to-widening not-run boundary",
                )
            if field_order_origin != "generate-produced":
                raise fail(op, "seed-and-widen requires Generate-produced field order")
            for option in field:
                actual_insertion = option.get("insertion")
                allowed_insertions = (
                    {None, "original-field-position"}
                    if option["provenance"] == "revived"
                    else {None}
                )
                if actual_insertion not in allowed_insertions:
                    raise fail(
                        op,
                        "seed-and-widen insertion provenance is valid only for a revived option rejoining a reused field",
                        option,
                    )
        else:
            generated_options = [
                option for option in field if option["provenance"] == "generated"
            ]
            if generated_options:
                raise fail(
                    op,
                    "closed-to-widening fields cannot carry generated provenance",
                    generated_options,
                )
            if parsed["generation-boundary"] == closed_marker:
                if field_order_origin != "user-supplied":
                    raise fail(
                        op,
                        "a closed field whose Generate stage did not run requires user-supplied order",
                    )
            elif field_order_origin != "generate-produced":
                raise fail(
                    op,
                    "a closed field reusing a prior generated full field must retain Generate-produced order",
                )
            for option in field:
                expected_insertion = {
                    "revived": "original-field-position",
                    "accepted": "appended-by-rule",
                }.get(option["provenance"])
                actual_insertion = option.get("insertion")
                if actual_insertion != expected_insertion:
                    raise fail(
                        op,
                        "closed-field insertion provenance must exist exactly for revived/accepted options",
                        option,
                    )
    elif not _is_not_produced(field_order_origin):
        raise fail(
            op, "missing original-field requires a not-produced field-order-origin"
        )
    survivors = parsed["survivors"]
    if not _is_not_produced(survivors):
        _check_option_list(survivors, f"{op} (survivors)", contract)
    overflow = parsed["overflow"]
    if not (_is_not_produced(overflow) or overflow == "not applicable"):
        _check_artifact_shape(
            {"key": "overflow", "shape": "overflow"}, overflow, "capsule", contract
        )
    records = parsed["records"]
    if not _is_not_produced(records):
        if not isinstance(records, list):
            raise fail(op, "records must be a list", records)
        for record in records:
            _check_capsule_record(record, contract)
    retrievals = parsed["retrievals"]
    if not _is_not_produced(retrievals):
        _check_capsule_retrievals(retrievals, contract, op)
    for key in ("surface", "close", "exclusion-check", "revival-instructions"):
        value = parsed[key]
        if not _is_not_produced(value):
            _require_str(op, key, value)
    consequences = parsed["consequences"]
    if not _is_not_produced(consequences):
        _check_artifact_shape(
            {"key": "consequences", "shape": "consequence-list"},
            consequences,
            "capsule",
            contract,
        )
    claim = parsed["terminal-claim"]
    if not (
        _is_not_produced(claim)
        or (isinstance(claim, dict) and set(claim) == {"terminal", "claim", "survivor"})
    ):
        raise fail(
            op,
            "terminal-claim must be exactly {terminal, claim, survivor} or `not produced: <reason>`",
            claim,
        )
    if isinstance(claim, dict):
        for key in ("terminal", "claim", "survivor"):
            _require_str(op, f"terminal-claim {key}", claim[key])
    leans = parsed["registered-leans"]
    seed = parsed["provisional-seed"]
    recommend_packet = parsed["recommend-authority-packet"]
    recommend_siblings = (parsed["close"], leans, recommend_packet)
    if seed == "not applicable":
        if not all(_is_produced(value) for value in recommend_siblings):
            raise fail(
                op,
                "provisional-seed `not applicable` requires completed Recommend authority",
            )
    elif _is_not_produced(seed):
        if any(_is_produced(value) for value in recommend_siblings):
            raise fail(
                op,
                "completed Recommend authority without a seed requires exact `not applicable`",
            )
    else:
        _check_artifact_shape(
            {"key": "provisional-seed", "shape": "seed"}, seed, "capsule", contract
        )
    if not _is_not_produced(leans):
        _check_artifact_shape(
            {"key": "registered-leans", "shape": "leans"}, leans, "capsule", contract
        )
    if any(
        _is_produced(value) for value in (parsed["close"], leans, seed)
    ) and not _is_produced(recommend_packet):
        raise fail(
            op,
            "a produced Recommend artifact requires recommend-authority-packet",
        )
    _check_recommend_authority_packet(
        recommend_packet,
        survivors=survivors,
        overflow=overflow,
        decomposition=decomposition,
        field_order_origin=field_order_origin,
        contract=contract,
        op=op,
    )
    _check_canonical_capsule_wordings(parsed, op)
    boundary = parsed["proof-boundary"]
    _check_proof_boundary_shape(
        op,
        boundary,
        contract,
        allow_unproduced_pins=parsed["terminal"] == "store failed: write",
    )
    if boundary["method-identity"] != contract_map["method-identity"]:
        raise fail(op, "proof-boundary method-identity must equal effective-contract")
    if _is_not_produced(boundary["constituent-pins"]) != unproduced_contract_pins:
        raise fail(
            op,
            "proof-boundary and effective-contract pin state must be produced or unproduced together",
        )
    if not restart_state:
        _validate_capsule_partition(
            field,
            survivors,
            records,
            contract,
            op,
            allow_partial=_is_failure_terminal(parsed["terminal"], contract),
        )
        _validate_capsule_terminal_state(parsed, contract, op)
    return parsed


def validate_capsule_text(
    text: str, contract: Contract, *, allow_file_capsule: bool = False
) -> dict:
    op = "capsule validation"
    body = _strip_fences(text)
    raw = body.encode("utf-8")
    cap_name = "capsule-file-bytes" if allow_file_capsule else "capsule-bytes"
    cap = contract.bounds[cap_name]
    if len(raw) > cap:
        raise refuse(
            op,
            f"capsule of {len(raw)} bytes exceeds the {cap}-byte {cap_name} bound",
        )
    lines = body.splitlines(keepends=True)
    terminator_index = None
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].startswith("capsule-complete:"):
            terminator_index = index
            break
    if terminator_index is None:
        raise fail(
            op,
            "no completeness terminator — a terminator-less paste is incomplete, never resumed from",
        )
    trailing = "".join(lines[terminator_index + 1 :]).strip()
    if trailing:
        raise fail(op, "capsule-complete must be the final key", trailing)
    declared = lines[terminator_index].split(":", 1)[1].strip()
    prefix = "".join(lines[:terminator_index]).encode("utf-8")
    actual = sha256_bytes(prefix)
    if declared != actual:
        raise fail(
            op,
            f"completeness terminator mismatch — the document is truncated or altered: declared {declared[:12]}…, actual {actual[:12]}…",
        )
    parsed = safe_parse(
        raw, byte_cap=cap, depth_cap=contract.bounds["parse-depth"], op=op
    )
    return validate_capsule_document(parsed, contract)


def _expected_original_field(store: Store) -> object:
    value = _effective_stage_artifact(store, "generate", "field", "original-field")
    if value is not _MISSING:
        return value
    echo = store.require("echo")["body"]
    if echo["fields"]["field-mode"]["value"] == "closed-to-widening":
        return _stored_field(store)
    return _MISSING


def _expected_generation_boundary(store: Store) -> object:
    generate = store.find("envelope", "generate")
    if generate:
        document = generate[-1]["body"]["document"]
        if not document["status"].startswith("failed: "):
            return copy.deepcopy(document["artifacts"]["fixed-points-line"])
        return _MISSING
    capsule = _imported_capsule(store)
    if capsule is not None and _restart_frontier_index(
        store
    ) > store.contract.stages.index("generate"):
        return copy.deepcopy(capsule["generation-boundary"])
    echo = store.require("echo")["body"]
    if echo["fields"]["field-mode"]["value"] == "closed-to-widening":
        return "Generate not run: closed-to-widening"
    return _MISSING


def _compare_capsule_store_value(
    capsule: dict, key: str, expected: object, op: str
) -> None:
    actual = capsule[key]
    if expected is _MISSING:
        if _is_produced(actual):
            raise fail(
                op, f"capsule {key} is produced but no store authority exists", actual
            )
        return
    if actual != expected:
        raise fail(
            op,
            f"capsule {key} differs from byte-exact run-state authority",
            {"capsule": actual, "store": expected},
        )


def validate_capsule_against_store(
    capsule: dict,
    store: Store,
    contract: Contract,
    *,
    allow_unrecorded_write_failure: bool = False,
) -> None:
    """Cross-check every mechanically derivable capsule value against run state."""
    op = "capsule store comparison"
    validate_capsule_document(capsule, contract)
    echo = store.require("echo")["body"]
    if capsule["run"] != store.require("echo")["run"]:
        raise fail(op, "capsule run identifier differs from the store echo")
    terminal_states = store.find("terminal-state")
    if terminal_states:
        state = terminal_states[-1]["body"]
        if capsule["terminal"] != state["terminal"]:
            raise fail(op, "capsule terminal differs from recorded terminal-state")
        expected_carrier = (
            "failure-capsule"
            if _is_failure_terminal(capsule["terminal"], contract)
            else "capsule"
        )
        if state["carrier"] != expected_carrier:
            raise fail(
                op, "recorded terminal-state carrier disagrees with terminal class"
            )
    elif not (
        allow_unrecorded_write_failure and capsule["terminal"] == "store failed: write"
    ):
        raise StoreReadLoss(
            "store read failed: terminal-state absent before capsule validation"
        )

    proof_items = store.find("proof-inputs")
    if proof_items:
        if capsule["proof-boundary"] != proof_items[-1]["body"]:
            raise fail(op, "proof-boundary differs from the recorded proof inputs")
    elif not (
        allow_unrecorded_write_failure and capsule["terminal"] == "store failed: write"
    ):
        raise StoreReadLoss(
            "store read failed: proof-inputs absent before capsule validation"
        )

    capsule_contract = capsule["effective-contract"]
    for name in contract.echo_contract_fields:
        if capsule_contract[name] != echo["fields"][name]:
            raise fail(op, f"effective-contract field {name} differs from store echo")
    if capsule_contract["bounds"] != echo["bounds"]:
        raise fail(op, "effective-contract bounds differ from store echo")
    wording = capsule_contract["invocation-wording"]
    if wording["initial"] != echo["invocation-wording-initial"]:
        raise fail(op, "invocation initial wording differs from store echo")
    if wording["directives"] != echo["directives"]:
        raise fail(op, "invocation directives differ from store echo")
    if wording["directives-collapsed"] != echo["directives-collapsed"]:
        raise fail(op, "collapsed directive history differs from store echo")
    if wording["source-capsule-id"] != echo["source-capsule-id"]:
        raise fail(op, "source-capsule-id differs from store echo")

    decomposition_items = store.find("decomposition")
    if decomposition_items:
        body = decomposition_items[-1]["body"]
    else:
        body = _decomposition_from_echo(echo, contract)
    expected_decomposition = {
        "frame": body["frame"],
        "candidates": body["candidates"],
        "stakes": body["stakes"],
        "soft-preferences": copy.deepcopy(echo["setup-source"]["soft-preferences"]),
        "composition-provenance": body["composition-provenance"],
    }
    if capsule["setup-decomposition"] != expected_decomposition:
        raise fail(op, "setup-decomposition differs from normalized store authority")

    pins_items = store.find("pins")
    if pins_items:
        pins = pins_items[-1]["body"]
        if capsule_contract["evidence-identity"] != {
            "named": pins["evidence"],
            "in-packet": pins["in-packet"],
        }:
            raise fail(op, "evidence identity differs from store pins")
        if capsule_contract["method-identity"] != pins["method"]:
            raise fail(op, "method identity differs from store pins")
        boundary = capsule["proof-boundary"]
        if boundary["constituent-pins"] != pins["constituents"]:
            raise fail(op, "proof-boundary constituent pins differ from store")
        if boundary["method-identity"] != pins["method"]:
            raise fail(op, "proof-boundary method identity differs from store")
    else:
        missing_pin_members = (
            capsule_contract["evidence-identity"],
            capsule_contract["method-identity"],
            capsule["proof-boundary"]["constituent-pins"],
            capsule["proof-boundary"]["method-identity"],
        )
        if not all(_is_not_produced(value) for value in missing_pin_members):
            raise fail(
                op,
                "capsule carries pin-derived state but no pins item exists in the store",
            )
    if capsule["proof-boundary"]["store-path"] != str(store.root):
        raise fail(op, "proof-boundary store-path differs from the live store root")

    field = _expected_original_field(store)
    _compare_capsule_store_value(capsule, "original-field", field, op)
    _compare_capsule_store_value(
        capsule, "generation-boundary", _expected_generation_boundary(store), op
    )
    if not isinstance(field, list):
        expected_origin: object = _MISSING
    else:
        expected_origin = _stored_field_order_origin(store)
    _compare_capsule_store_value(capsule, "field-order-origin", expected_origin, op)

    artifact_map = (
        ("survivors", "prune", "survivors"),
        ("overflow", "prune", "overflow-disclosure"),
        ("surface", "shape", "comparison-surface"),
        ("consequences", "shape", "constraint-consequences"),
        ("close", "recommend", "close"),
        ("registered-leans", "recommend", "registered-leans"),
        ("provisional-seed", "recommend", "provisional-seed"),
        ("exclusion-check", "contest", "exclusion-check-line"),
    )
    for capsule_key, stage, artifact_key in artifact_map:
        expected = _effective_stage_artifact(store, stage, artifact_key, capsule_key)
        _compare_capsule_store_value(capsule, capsule_key, expected, op)

    _compare_capsule_store_value(capsule, "records", _effective_records(store), op)
    has_retrieval_authority = bool(_imported_capsule(store) or store.find("envelope"))
    retrievals: object = (
        _accepted_retrievals(store) if has_retrieval_authority else _MISSING
    )
    _compare_capsule_store_value(capsule, "retrievals", retrievals, op)
    _compare_capsule_store_value(
        capsule, "terminal-claim", _effective_terminal_claim(store), op
    )


def cmd_validate_capsule(args: argparse.Namespace) -> int:
    readset = ReadSet()
    contract = load_contract(Path(args.data), readset)
    capsule_path = readset.allow(Path(args.capsule))
    raw = readset.read_bytes(capsule_path)
    ingest_cap = contract.bounds[
        "capsule-file-bytes" if args.file_capsule else "capsule-bytes"
    ]
    if len(raw) > ingest_cap + 16:  # fences allowance
        raise refuse(
            "capsule validation",
            f"capsule of {len(raw)} bytes exceeds the {ingest_cap}-byte ingest bound",
        )
    parsed = validate_capsule_text(
        _decode_utf8(raw, "capsule validation"),
        contract,
        allow_file_capsule=args.file_capsule,
    )
    if args.accept and not args.store:
        raise refuse("capsule validation", "--accept requires --store")
    if args.store:
        store = Store(Path(args.store), contract, readset)
        validate_capsule_against_store(
            parsed,
            store,
            contract,
            allow_unrecorded_write_failure=not args.accept,
        )
        if args.accept:
            store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "capsule-progress",
                    "run": store.require("echo")["run"],
                    "seq": store.next_seq(),
                    "body": {"capsule": parsed},
                },
                writer="validate-capsule",
            )
    print(f"capsule valid: run={parsed['run']} terminal={parsed['terminal']!r}")
    return EXIT_PASS


# ---------------------------------------------------------------------------
# Capsule import — the executable resume path
# ---------------------------------------------------------------------------


def _earliest_stage_name(contract: Contract, stages: list[str]) -> str:
    stage_frontiers = [stage for stage in stages if stage != "none"]
    return (
        min(stage_frontiers, key=contract.stages.index) if stage_frontiers else "none"
    )


def _implicit_resume_stage(capsule: dict, contract: Contract) -> str | None:
    terminal = capsule["terminal"]
    if capsule["exclusion-check"] == "exclusion check unavailable":
        return "contest"
    if terminal.startswith("stage failed:"):
        stage = terminal.removeprefix("stage failed:").strip()
        return stage if stage in contract.stages else None
    if not _is_failure_terminal(terminal, contract):
        return None
    if not isinstance(capsule["original-field"], list):
        return "generate"
    if not isinstance(capsule["survivors"], list) or not isinstance(
        capsule["records"], list
    ):
        return "prune"
    survivors = capsule["survivors"]
    records = capsule["records"]
    if len(survivors) < 2:
        return (
            "contest"
            if any(record["status"] == "active" for record in records)
            else "none"
        )
    if not _is_produced(capsule["surface"]) or not _is_produced(
        capsule["consequences"]
    ):
        return "shape"
    if not (
        _is_produced(capsule["close"]) or _is_produced(capsule["provisional-seed"])
    ):
        return "recommend"
    if not _is_produced(capsule["exclusion-check"]) and any(
        record["status"] == "active" for record in records
    ):
        return "contest"
    return "none"


def _contract_change_frontiers(
    old_fields: dict, new_fields: dict, contract: Contract
) -> tuple[list[str], list[str]]:
    stages: list[str] = []
    reasons: list[str] = []
    new_mode = new_fields["field-mode"]["value"]
    for name in contract.echo_contract_fields:
        if new_fields[name] == old_fields[name]:
            continue
        reasons.append(f"contract field changed: {name}")
        if name in {
            "frame",
            "values",
            "evidence-inputs",
            "evidence-authorization",
        }:
            stages.append("generate")
        elif name == "field-mode":
            stages.append("generate" if new_mode == "seed-and-widen" else "prune")
        elif name == "constraints":
            stages.append("generate" if new_mode == "seed-and-widen" else "prune")
        elif name == "survivor-budget":
            stages.append("prune")
        elif name in {"soft-prefs", "stakes"}:
            stages.append("shape")
        elif name == "degradation-permission":
            continue
        else:
            raise refuse(
                "capsule import", f"no restart mapping for contract field {name!r}"
            )
    return stages, reasons


def _changed_pin_locators(old: list[dict], new: list[dict]) -> set[str]:
    """Return locators whose exact pin entries changed between identity sets."""
    changed_entries = [entry for entry in old if entry not in new] + [
        entry for entry in new if entry not in old
    ]
    return {
        str(entry.get("path", entry.get("name", "unknown method surface")))
        for entry in changed_entries
    }


def _method_pin_frontier(locator: str, contract: Contract) -> str:
    normalized = locator.replace("\\", "/").removeprefix("./")
    for suffix, stage in contract.method_pin_frontiers.items():
        if suffix == "default":
            continue
        if normalized == suffix or normalized.endswith(f"/{suffix}"):
            return stage
    return contract.method_pin_frontiers["default"]


def _pin_change_frontiers(
    old: dict, new: dict, contract: Contract
) -> tuple[list[str], list[str]]:
    stages: list[str] = []
    reasons: list[str] = []
    constituent_stage = {
        "ideate": "generate",
        "option-shaping": "shape",
        "making-recommendations": "recommend",
    }
    for name, stage in constituent_stage.items():
        if old["constituents"][name] != new["constituents"][name]:
            stages.append(stage)
            reasons.append(f"constituent pin changed: {name}")
    if old["evidence"] != new["evidence"]:
        stages.append("generate")
        reasons.append("named evidence pin changed")
    if old["in-packet"] != new["in-packet"]:
        stages.append("generate")
        reasons.append("in-packet evidence pin changed")
    if any(pin["id"] == "no comparable identity" for pin in new["in-packet"]):
        stages.append("generate")
        reasons.append("in-packet evidence has no comparable identity")
    if old["method"] != new["method"]:
        changed_locators = _changed_pin_locators(old["method"], new["method"])
        if not changed_locators:
            changed_locators = {"unknown method surface"}
        for locator in sorted(changed_locators):
            stage = _method_pin_frontier(locator, contract)
            stages.append(stage)
            reasons.append(f"method pin changed: {locator} -> {stage}")
    return stages, reasons


def _compact_directive_history(echo_body: dict, contract: Contract) -> None:
    """Collapse older directive texts past the verbatim bound to content
    identifiers, oldest first — the executable standing rule, applied before
    any bound check so re-run continuity never dies at the history bound."""
    cap = contract.bounds["verbatim-directive-history"]
    verbatim = list(echo_body["directives"])
    collapsed = list(echo_body["directives-collapsed"])
    while len(verbatim) > cap:
        collapsed.append(sha256_bytes(verbatim.pop(0).encode("utf-8")))
    echo_body["directives"] = verbatim
    echo_body["directives-collapsed"] = collapsed


def _check_import_directive_manifest(
    op: str,
    manifest: list | None,
    new_texts: list[str],
    applied: set[tuple[str, str]],
    contract: Contract,
) -> None:
    """Bind each new raw directive text to its applied actions, both ways:
    orphan text (a directive bound to no applied action) and orphan actions
    (an applied action bound to no directive) refuse before the store is
    staged. Without new texts, flag- and field-derived actions stay legal and
    are recorded by synthesized history entries and the restart plan."""
    if manifest is None:
        if new_texts:
            raise refuse(
                op,
                "new re-run directive texts require a directive manifest binding each text to its classified actions",
            )
        return
    _check_directive_bindings(op, manifest, contract)
    manifest_texts = [entry["directive"] for entry in manifest]
    if manifest_texts != new_texts:
        raise refuse(
            op,
            "directive manifest must list exactly the new directive texts in order",
            {"manifest": manifest_texts, "new": new_texts},
        )
    claimed: set[tuple[str, str]] = set()
    for entry in manifest:
        for action in entry["actions"]:
            parsed = _parse_directive_action(op, action, contract)
            if parsed not in applied:
                raise refuse(
                    op,
                    f"directive {entry['directive']!r} claims an action this import does not apply: {action}",
                )
            claimed.add(parsed)
    orphans = applied - claimed
    if orphans:
        raise refuse(
            op,
            f"applied actions bound to no directive text: {sorted(orphans)}",
        )


def import_capsule_into_store(
    capsule: dict,
    root: Path,
    run: str,
    contract: Contract,
    readset: ReadSet,
    revive: list[str] | None = None,
    constraint_withdrawn: list[str] | None = None,
    accept_seed: bool = False,
    echo_body: dict | None = None,
    invalidate_from: list[str] | None = None,
    field_base: str | None = None,
    closed_field: list[str] | None = None,
    current_pins: dict | None = None,
    directive_manifest: list | None = None,
) -> Store:
    """Create typed import state plus the normalized restart frontier."""
    op = "capsule import"
    capsule = copy.deepcopy(capsule)
    source_capsule_id = capsule.get("capsule-complete", "none")
    capsule.pop("capsule-complete", None)
    revive = revive or []
    constraint_withdrawn = constraint_withdrawn or []
    invalidate_from = invalidate_from or []
    closed_field = closed_field or []
    unknown_frontiers = [
        stage for stage in invalidate_from if stage not in contract.stages
    ]
    if unknown_frontiers:
        raise fail(
            op, "invalidation frontier names an unknown stage", unknown_frontiers
        )
    directives_applied: list[str] = []
    contract_map = capsule["effective-contract"]
    decomposition = capsule["setup-decomposition"]
    identity = contract_map["evidence-identity"]
    prior_pins_missing = _is_not_produced(identity)
    prior_pins = None
    if not prior_pins_missing:
        prior_pins = {
            "constituents": capsule["proof-boundary"]["constituent-pins"],
            "method": contract_map["method-identity"],
            "evidence": identity["named"],
            "in-packet": identity["in-packet"],
        }
    if current_pins is None:
        if prior_pins is None:
            raise fail(
                op,
                "a capsule without prior setup pins requires freshly resolved current pins",
            )
        current_pins = prior_pins
    current_pins = copy.deepcopy(current_pins)
    _check_body_pins(op, current_pins, contract)
    new_directive_texts: list[str] = []
    if echo_body is None:
        fields = {
            name: {
                "value": contract_map[name]["value"],
                "provenance": contract_map[name]["provenance"],
            }
            for name in contract.echo_contract_fields
        }
        echo_body = {
            "invocation-wording-initial": contract_map["invocation-wording"]["initial"],
            "directives": list(contract_map["invocation-wording"]["directives"]),
            "directives-collapsed": list(
                contract_map["invocation-wording"]["directives-collapsed"]
            ),
            "bounds": copy.deepcopy(contract_map["bounds"]),
            "source-capsule-id": source_capsule_id,
            "fields": fields,
            "setup-source": {
                "candidates": [
                    {
                        "wording": candidate["wording"],
                        "provenance-flag": candidate["provenance-flag"],
                    }
                    for candidate in decomposition["candidates"]
                ],
                "soft-preferences": copy.deepcopy(decomposition["soft-preferences"]),
                "composition-provenance": copy.deepcopy(
                    decomposition["composition-provenance"]
                ),
            },
        }
    else:
        echo_body = copy.deepcopy(echo_body)
        prior_wording = contract_map["invocation-wording"]
        if echo_body.get("invocation-wording-initial") != prior_wording["initial"]:
            raise fail(
                op,
                "echo override must preserve the capsule's initial invocation wording",
            )
        if echo_body.get("source-capsule-id") != source_capsule_id:
            raise fail(
                op,
                "echo override source-capsule-id must equal the pasted capsule identifier",
                echo_body.get("source-capsule-id"),
            )
        directives = echo_body.get("directives")
        prior_directives = prior_wording["directives"]
        if (
            not isinstance(directives, list)
            or directives[: len(prior_directives)] != prior_directives
        ):
            raise fail(
                op,
                "echo override must preserve prior directive history as an exact prefix",
                directives,
            )
        if (
            echo_body.get("directives-collapsed")
            != prior_wording["directives-collapsed"]
        ):
            raise fail(
                op,
                "echo override must preserve the collapsed directive history exactly",
                echo_body.get("directives-collapsed"),
            )
        new_directive_texts = [
            str(text) for text in directives[len(prior_directives) :]
        ]
    _compact_directive_history(echo_body, contract)
    _check_body_echo(op, echo_body, contract)
    for label, values in (
        ("revival", revive),
        ("constraint-withdrawn", constraint_withdrawn),
        ("invalidation frontier", invalidate_from),
    ):
        if len(values) != len(set(values)):
            raise fail(op, f"duplicate {label} directives are not allowed", values)
    old_fields = {name: contract_map[name] for name in contract.echo_contract_fields}
    change_stages, change_reasons = _contract_change_frontiers(
        old_fields, echo_body["fields"], contract
    )
    applied_actions: set[tuple[str, str]] = set()
    for name in contract.echo_contract_fields:
        if echo_body["fields"][name] != old_fields[name]:
            applied_actions.add(("contract-field", name))
    for wording in revive:
        applied_actions.add(("revive", wording))
    for wording in constraint_withdrawn:
        applied_actions.add(("withdraw-constraint", wording))
    if accept_seed:
        applied_actions.add(("accept-seed", ""))
    for stage in invalidate_from:
        applied_actions.add(("invalidate-from", stage))
    if field_base is not None:
        applied_actions.add(("field-base", field_base))
    _check_import_directive_manifest(
        op, directive_manifest, new_directive_texts, applied_actions, contract
    )
    if prior_pins is None:
        pin_stages = ["generate"]
        pin_reasons = ["prior setup pins were not produced"]
    else:
        pin_stages, pin_reasons = _pin_change_frontiers(
            prior_pins, current_pins, contract
        )
    constraints_changed = (
        echo_body["fields"]["constraints"] != old_fields["constraints"]
    )
    unused_withdrawals = [
        wording for wording in constraint_withdrawn if wording not in revive
    ]
    if unused_withdrawals:
        raise fail(
            op,
            "constraint-withdrawn may name only an option revived in the same import",
            unused_withdrawals,
        )
    if constraint_withdrawn and not constraints_changed:
        raise refuse(
            op,
            "constraint-withdrawn requires an actual effective-contract constraint change",
        )
    field_mode = echo_body["fields"]["field-mode"]["value"]
    candidates = list(decomposition["candidates"])
    field = capsule.get("original-field")
    prior_mode = old_fields["field-mode"]["value"]
    mode_changed = field_mode != prior_mode
    if not mode_changed and (field_base is not None or closed_field):
        raise fail(
            op,
            "field-base and closed-field are valid only with a field-mode change",
        )
    if mode_changed and field_mode == "closed-to-widening":
        if field_base not in contract.closed_field_bases:
            raise fail(
                op,
                f"landing on closed-to-widening requires field-base from {sorted(contract.closed_field_bases)}",
                field_base,
            )
        if field_base != "new" and closed_field:
            raise fail(op, "closed-field wording is valid only with field-base `new`")
        if field_base == "new":
            if not closed_field:
                raise fail(
                    op, "field-base `new` requires a non-empty closed-field list"
                )
            if len(closed_field) != len(set(closed_field)) or any(
                not isinstance(wording, str) or not wording.strip()
                for wording in closed_field
            ):
                raise fail(
                    op,
                    "closed-field must contain unique non-empty wordings",
                    closed_field,
                )
            field = [
                {"wording": wording, "provenance": "user-seed"}
                for wording in closed_field
            ]
        else:
            if not isinstance(field, list):
                raise fail(op, f"field-base {field_base!r} requires a prior field")
            if field_base == "prior-seeds":
                field = [
                    copy.deepcopy(option)
                    for option in field
                    if option["provenance"] != "generated"
                ]
                for option in field:
                    expected_insertion = {
                        "revived": "original-field-position",
                        "accepted": "appended-by-rule",
                    }.get(option["provenance"])
                    if expected_insertion is None:
                        option.pop("insertion", None)
                    else:
                        option["insertion"] = expected_insertion
                if not field:
                    raise fail(op, "prior-seeds field base resolves to an empty field")
            else:
                for option in field:
                    if option["provenance"] == "generated":
                        option["provenance"] = "adopted"
                        option.pop("insertion", None)
        existing_candidates = {
            candidate["wording"]: candidate for candidate in candidates
        }
        candidates = []
        for option in field:
            candidate = copy.deepcopy(existing_candidates.get(option["wording"]))
            if candidate is None:
                candidate = {
                    "wording": option["wording"],
                    "provenance-flag": option["provenance"],
                    "authority-note": "absent",
                }
            else:
                candidate["provenance-flag"] = option["provenance"]
            candidates.append(candidate)
        capsule["original-field"] = field
        if field_base != "prior-full-field":
            capsule["field-order-origin"] = "user-supplied"
            capsule["generation-boundary"] = "Generate not run: closed-to-widening"
    elif mode_changed:
        if field_base is not None or closed_field:
            raise fail(
                op,
                "landing on seed-and-widen takes the prior candidate set automatically and accepts no field-base",
            )
        if not isinstance(field, list):
            raise fail(op, "seed-and-widen transition requires a prior candidate field")
        existing_candidates = {
            candidate["wording"]: candidate for candidate in candidates
        }
        for option in field:
            provenance = (
                "adopted"
                if option["provenance"] == "generated"
                else option["provenance"]
            )
            candidate = existing_candidates.get(option["wording"])
            if candidate is None:
                candidate = {
                    "wording": option["wording"],
                    "provenance-flag": provenance,
                    "authority-note": "absent",
                }
                candidates.append(candidate)
            else:
                candidate["provenance-flag"] = provenance

    for wording in revive:
        records = capsule.get("records")
        if not isinstance(records, list):
            raise fail(op, "revival directive but the capsule carries no records list")
        matches = [
            r for r in records if r["option"] == wording and r["status"] == "active"
        ]
        if len(matches) != 1:
            raise fail(
                op,
                f"revival target must have exactly one active exclusion record: {wording!r}",
                len(matches),
            )
        record = matches[0]
        if record["cut-basis"] == "constraint" and wording not in constraint_withdrawn:
            raise refuse(
                op,
                f"authority conflict — {wording!r} was cut on a constraint the directive does not withdraw or reprice",
            )
        if not isinstance(field, list):
            raise fail(op, "revival requires a produced original-field")
        field_matches = [option for option in field if option["wording"] == wording]
        if len(field_matches) != 1:
            raise fail(
                op,
                "revival target must occur exactly once in original-field",
                wording,
            )
        record["status"] = "revived"
        field_option = field_matches[0]
        field_option["provenance"] = "revived"
        field_option["insertion"] = "original-field-position"
        candidate_matches = [
            candidate for candidate in candidates if candidate["wording"] == wording
        ]
        if len(candidate_matches) > 1:
            raise fail(
                op, "revival target appears more than once in decomposition", wording
            )
        if candidate_matches:
            candidate_matches[0]["provenance-flag"] = "revived"
        else:
            candidates.append(
                {
                    "wording": wording,
                    "provenance-flag": "revived",
                    "authority-note": "absent",
                }
            )
        survivors = capsule.get("survivors")
        if isinstance(field, list) and isinstance(survivors, list):
            survivor_set = {opt["wording"] for opt in survivors} | {wording}
            capsule["survivors"] = [
                opt for opt in field if opt["wording"] in survivor_set
            ]
        directives_applied.append(f"revive: {wording}")

    candidate_wordings = {c["wording"] for c in candidates}
    if accept_seed:
        seed = capsule.get("provisional-seed")
        if not isinstance(seed, dict) or set(seed) != {
            "wording",
            "handle",
            "core-idea",
            "distinct-bet",
        }:
            raise fail(
                op,
                "seed acceptance directive but the capsule carries no provisional seed",
            )
        for key in ("wording", "handle", "core-idea", "distinct-bet"):
            _require_str(op, f"provisional-seed {key}", seed[key])
        wording = seed["wording"]
        field_wordings = (
            {option["wording"] for option in field}
            if isinstance(field, list)
            else set()
        )
        if wording in candidate_wordings or wording in field_wordings:
            raise fail(
                op,
                "accepted provisional seed collides with an existing candidate",
                wording,
            )
        candidates.append(
            {
                "wording": wording,
                "provenance-flag": "accepted",
                "authority-note": "absent",
            }
        )
        if field_mode == "closed-to-widening":
            if not isinstance(field, list):
                raise fail(op, "closed-field seed acceptance requires original-field")
            field.append(
                {
                    "wording": wording,
                    "provenance": "accepted",
                    "insertion": "appended-by-rule",
                }
            )
            capsule["survivors"] = "not produced: invalidated by accepted seed"
            capsule["overflow"] = "not produced: invalidated by accepted seed"
        capsule["provisional-seed"] = "not produced: accepted on rerun"
        directives_applied.append(f"accept seed: {wording}")

    if mode_changed and field_mode == "seed-and-widen":
        invalidated_field = "not produced: invalidated by field-mode transition"
        capsule["original-field"] = invalidated_field
        capsule["generation-boundary"] = invalidated_field
        capsule["field-order-origin"] = invalidated_field

    if directives_applied and directive_manifest is None:
        echo_body["directives"] = list(echo_body["directives"]) + directives_applied
        _compact_directive_history(echo_body, contract)
    pre_recommend_frontiers = change_stages + pin_stages + list(invalidate_from)
    invalidates_recommend = bool(directives_applied) or any(
        contract.stages.index(stage) <= contract.stages.index("recommend")
        for stage in pre_recommend_frontiers
    )
    if invalidates_recommend:
        capsule["recommend-authority-packet"] = (
            "not produced: invalidated by rerun directive"
        )
        capsule["close"] = "not produced: invalidated by rerun directive"
        capsule["registered-leans"] = "not produced: invalidated by rerun directive"
        capsule["terminal-claim"] = "not produced: invalidated by rerun directive"
        capsule["exclusion-check"] = "not produced: invalidated by rerun directive"
        capsule["provisional-seed"] = "not produced: invalidated by rerun directive"
    if bool(directives_applied) or any(
        contract.stages.index(stage) <= contract.stages.index("shape")
        for stage in pre_recommend_frontiers
    ):
        capsule["surface"] = "not produced: invalidated by rerun directive"
        capsule["consequences"] = "not produced: invalidated by rerun directive"
    decomposition["candidates"] = candidates
    decomposition["frame"] = echo_body["fields"]["frame"]["value"]
    decomposition["stakes"] = echo_body["fields"]["stakes"]["value"]
    soft_prefs = echo_body["fields"]["soft-prefs"]["value"]
    if not isinstance(soft_prefs, list):
        soft_prefs = []
    echo_body["setup-source"] = _setup_source_from_artifacts(
        candidates,
        soft_prefs,
        echo_body["fields"]["soft-prefs"]["provenance"],
        decomposition["composition-provenance"],
    )
    decomposition["soft-preferences"] = copy.deepcopy(
        echo_body["setup-source"]["soft-preferences"]
    )
    _check_body_echo(op, echo_body, contract)
    for name in contract.echo_contract_fields:
        contract_map[name] = copy.deepcopy(echo_body["fields"][name])
    contract_map["bounds"] = copy.deepcopy(echo_body["bounds"])
    contract_map["invocation-wording"] = {
        "initial": echo_body["invocation-wording-initial"],
        "directives": copy.deepcopy(echo_body["directives"]),
        "directives-collapsed": copy.deepcopy(echo_body["directives-collapsed"]),
        "source-capsule-id": echo_body["source-capsule-id"],
    }

    restart_stages = list(change_stages) + pin_stages + list(invalidate_from)
    restart_reasons = (
        list(change_reasons)
        + pin_reasons
        + [f"explicit invalidation frontier: {stage}" for stage in invalidate_from]
    )
    if revive:
        resumed_survivors = capsule.get("survivors")
        resumed_records = capsule.get("records")
        if isinstance(resumed_survivors, list) and len(resumed_survivors) >= 2:
            revival_frontier = "shape"
        elif isinstance(resumed_records, list) and any(
            record["status"] == "active" for record in resumed_records
        ):
            revival_frontier = "contest"
        else:
            revival_frontier = "none"
        restart_stages.append(revival_frontier)
        restart_reasons.extend(f"revived option: {wording}" for wording in revive)
    if accept_seed:
        restart_stages.append("generate" if field_mode == "seed-and-widen" else "prune")
        restart_reasons.append("accepted stored provisional seed")
    implicit_stage = _implicit_resume_stage(capsule, contract)
    if implicit_stage is not None:
        restart_stages.append(implicit_stage)
        restart_reasons.append(f"implicit unfinished-run resume: {implicit_stage}")
    if field_mode == "closed-to-widening" and "generate" in restart_stages:
        restart_stages = [
            "prune" if stage == "generate" else stage for stage in restart_stages
        ]
        restart_reasons.append(
            "Generate-never-ran resolution: closed-to-widening starts at Prune"
        )
    if not restart_reasons:
        raise refuse(
            op,
            "completed capsule has no classified re-run directive or invalidation",
        )
    if directive_manifest is not None:
        plan_directives = copy.deepcopy(directive_manifest)
    else:
        plan_directives = [
            {
                "directive": text,
                "actions": ["accept-seed"]
                if text.startswith("accept seed: ")
                else [text],
            }
            for text in directives_applied
        ]
    restart_plan = {
        "earliest-stage": _earliest_stage_name(contract, restart_stages),
        "reasons": restart_reasons,
        "directives": plan_directives,
    }

    decomposition_body = _decomposition_from_echo(echo_body, contract)
    validate_capsule_document(capsule, contract, restart_state=True)
    import_items = [
        {
            "schema": RUNSTATE_SCHEMA,
            "kind": kind,
            "run": run,
            "seq": seq,
            "body": body,
        }
        for seq, (kind, body) in enumerate(
            (
                ("echo", echo_body),
                ("decomposition", decomposition_body),
                ("pins", current_pins),
                ("capsule-import", {"capsule": capsule}),
                ("restart-plan", restart_plan),
            )
        )
    ]
    for item in import_items:
        validate_runstate_item(item, contract)

    if root.exists():
        raise refuse(
            "store init",
            f"store path already exists — retire the orphan via `trash` first: {root}",
        )
    parent = Path(os.path.realpath(root.parent))
    readset.allow(parent)
    staging = Path(tempfile.mkdtemp(prefix=f".{root.name}.import-", dir=parent))
    os.chmod(staging, 0o700)
    store = Store(staging, contract, readset)
    try:
        for item in import_items:
            store.write(item, writer="import-capsule")
        os.replace(staging, root)
    except OSError as exc:
        try:
            cleanup = subprocess.run(
                ["trash", str(staging)],
                check=False,
                capture_output=True,
                text=True,
            )
        except OSError as cleanup_exc:
            raise fail(
                op,
                f"atomic store publish failed and staging retirement could not invoke trash at {staging}: {cleanup_exc}",
            ) from exc
        if cleanup.returncode != 0:
            raise fail(
                op,
                f"atomic store publish failed and staging retirement via trash also failed at {staging}: {cleanup.stderr.strip() or cleanup.stdout.strip()}",
            ) from exc
        raise fail(
            op,
            f"atomic store publish failed; staging directory retired via trash: {exc}",
        ) from exc
    return Store(root, contract, readset)


def cmd_import_capsule(args: argparse.Namespace) -> int:
    readset = ReadSet()
    contract = load_contract(Path(args.data), readset)
    capsule_path = readset.allow(Path(args.capsule))
    raw = readset.read_bytes(capsule_path)
    ingest_cap = contract.bounds[
        "capsule-file-bytes" if args.file_capsule else "capsule-bytes"
    ]
    if len(raw) > ingest_cap + 16:  # fences allowance
        raise refuse(
            "capsule import",
            f"capsule of {len(raw)} bytes exceeds the {ingest_cap}-byte ingest bound",
        )
    capsule = validate_capsule_text(
        _decode_utf8(raw, "capsule import"),
        contract,
        allow_file_capsule=args.file_capsule,
    )
    echo_body = None
    if args.echo_body:
        echo_path = readset.allow(Path(args.echo_body))
        echo_body = safe_parse(
            readset.read_bytes(echo_path),
            byte_cap=contract.bounds["parse-bytes"],
            depth_cap=contract.bounds["parse-depth"],
            op="echo body",
        )
    pins_path = readset.allow(Path(args.pins_body))
    current_pins = safe_parse(
        readset.read_bytes(pins_path),
        byte_cap=contract.bounds["parse-bytes"],
        depth_cap=contract.bounds["parse-depth"],
        op="current pins",
    )
    closed_field: list[str] = []
    if args.closed_field:
        field_path = readset.allow(Path(args.closed_field))
        parsed_field = safe_parse(
            readset.read_bytes(field_path),
            byte_cap=contract.bounds["parse-bytes"],
            depth_cap=contract.bounds["parse-depth"],
            op="closed field",
        )
        closed_field = _require_str_list(
            "closed field", "closed-field wordings", parsed_field
        )
    directive_manifest = None
    if args.directive_manifest:
        manifest_path = readset.allow(Path(args.directive_manifest))
        parsed_manifest = safe_parse(
            readset.read_bytes(manifest_path),
            byte_cap=contract.bounds["parse-bytes"],
            depth_cap=contract.bounds["parse-depth"],
            op="directive manifest",
        )
        if not isinstance(parsed_manifest, list):
            raise fail(
                "directive manifest", "manifest must be a YAML list", parsed_manifest
            )
        directive_manifest = parsed_manifest
    store = import_capsule_into_store(
        capsule,
        Path(args.store),
        args.run,
        contract,
        readset,
        revive=args.revive,
        constraint_withdrawn=args.constraint_withdrawn,
        accept_seed=args.accept_seed,
        echo_body=echo_body,
        invalidate_from=args.invalidate_from,
        field_base=args.field_base,
        closed_field=closed_field,
        current_pins=current_pins,
        directive_manifest=directive_manifest,
    )
    print(
        f"capsule imported: store={store.root} run={args.run} "
        f"(echo, decomposition, pins, capsule-import, restart-plan written)"
    )
    return EXIT_PASS


# ---------------------------------------------------------------------------
# Authored-rendering generation and comparison
# ---------------------------------------------------------------------------


def gen_matrix(contract: Contract) -> str:
    header = "| Packet item | Generate | Prune | Shape | Recommend | Contest |"
    divider = "| --- | --- | --- | --- | --- | --- |"
    rows = [header, divider]
    for entry in contract.items:
        cells = []
        for stage in contract.stages:
            cell = entry["matrix"][stage]
            mark = "✓" if cell["status"] == "include" else "—"
            if cell.get("qualifier"):
                mark += f" ({cell['qualifier']})"
            cells.append(mark)
        rows.append(
            f"| `{entry['key']}` — {entry['label']} | " + " | ".join(cells) + " |"
        )
    return "\n".join(rows)


def gen_checklist(contract: Contract, stage: str) -> str:
    include, withhold = [], []
    for entry in contract.items:
        cell = entry["matrix"][stage]
        qualifier = f" ({cell['qualifier']})" if cell.get("qualifier") else ""
        if cell["status"] == "include":
            include.append(f"- `{entry['key']}`{qualifier} — {entry['label']}")
        else:
            withhold.append(f"- `{entry['key']}`{qualifier}")
    title = stage.capitalize()
    return (
        f"**{title} — include:**\n\n"
        + "\n".join(include)
        + f"\n\n**{title} — withhold (exhaustive):**\n\n"
        + "\n".join(withhold)
        + "\n\nAn item on neither list is withheld by default; admitting one is a skill edit, never run-time judgment."
    )


def _gen_keys(entries: list[dict]) -> str:
    lines = []
    for entry in entries:
        parts = ["required" if entry.get("required") else "optional"]
        if "const" in entry:
            parts.append(f"constant `{entry['const']}`")
        if "enum" in entry:
            parts.append("one of: " + ", ".join(entry["enum"]))
        line = f"- `{entry['key']}` — " + "; ".join(parts)
        if entry.get("note"):
            line += f". {entry['note']}"
        lines.append(line)
    return "\n".join(lines)


def gen_record_keys(contract: Contract) -> str:
    return _gen_keys(contract.record_keys)


def gen_schema_keys(contract: Contract, schema_name: str) -> str:
    schema = contract.schemas[schema_name]
    out = _gen_keys(schema["keys"])
    if "body-keys" in schema:
        out += "\n\nBody key sets per kind:\n\n"
        out += "\n".join(
            f"- `{kind}`: {', '.join(f'`{key}`' for key in keys)}"
            for kind, keys in schema["body-keys"].items()
        )
    return out


def gen_bounds(contract: Contract) -> str:
    return "\n".join(f"- `{key}`: {value}" for key, value in contract.bounds.items())


GENERATED_BLOCKS = {
    "stage-packets.md": [
        "matrix",
        "checklist-generate",
        "checklist-prune",
        "checklist-shape",
        "checklist-recommend",
        "checklist-contest",
    ],
    "schemas.md": [
        "record-keys",
        "setup-keys",
        "envelope-keys",
        "runstate-keys",
        "capsule-keys",
        "bounds",
    ],
}


def generate_block(name: str, contract: Contract) -> str:
    if name == "matrix":
        return gen_matrix(contract)
    if name.startswith("checklist-"):
        return gen_checklist(contract, name.removeprefix("checklist-"))
    if name == "record-keys":
        return gen_record_keys(contract)
    if name == "setup-keys":
        return gen_schema_keys(contract, SETUP_SCHEMA)
    if name == "envelope-keys":
        return gen_schema_keys(contract, ENVELOPE_SCHEMA)
    if name == "runstate-keys":
        return gen_schema_keys(contract, RUNSTATE_SCHEMA)
    if name == "capsule-keys":
        return gen_schema_keys(contract, CAPSULE_SCHEMA)
    if name == "bounds":
        return gen_bounds(contract)
    raise refuse("rendering generation", f"unknown generated block: {name}")


def cmd_check_renderings(args: argparse.Namespace) -> int:
    readset = ReadSet()
    contract = load_contract(Path(args.data), readset)
    references = contract.data_path.parent
    readset.allow(references)
    drifted = []
    for filename, blocks in GENERATED_BLOCKS.items():
        path = references / filename
        if not path.exists():
            drifted.append(f"{filename}: file missing")
            continue
        text = readset.read_bytes(path).decode("utf-8")
        for block in blocks:
            start = f"<!-- generated:{block} -->"
            end = f"<!-- /generated:{block} -->"
            if start not in text or end not in text:
                drifted.append(f"{filename}: markers for {block} missing")
                continue
            authored = text.split(start, 1)[1].split(end, 1)[0].strip("\n")
            expected = generate_block(block, contract)
            if authored != expected:
                drifted.append(
                    f"{filename}: block {block} drifted from contract-data.yaml"
                )
                if args.write:
                    text = (
                        text.split(start, 1)[0]
                        + start
                        + "\n"
                        + expected
                        + "\n"
                        + end
                        + text.split(end, 1)[1]
                    )
        if args.write:
            path.write_text(text)
    if drifted and not args.write:
        for line in drifted:
            print(f"DRIFT: {line}", file=sys.stderr)
        raise fail(
            "check-renderings",
            f"{len(drifted)} authored rendering(s) drifted from the canonical data file",
        )
    print(
        "renderings rewritten from contract data"
        if args.write
        else "all authored renderings match the canonical data file"
    )
    return EXIT_PASS


# ---------------------------------------------------------------------------
# Fixtures — the must-block/must-pass set
# ---------------------------------------------------------------------------


_FIXTURE_PROVENANCE = {
    "invocation-span": "/deliberate choose a note-sync approach […candidates and authority language elided: see capsule]",
    "delegation-span": "field mode seed-and-widen; candidate selection delegated to the run",
}


def _fixture_method_pins(contract: Contract) -> list[dict]:
    return [{"path": surface, "id": "0" * 64} for surface in contract.method_surfaces]


def _fixture_pins_body(contract: Contract) -> dict:
    return {
        "constituents": {
            "ideate": [{"path": "skills/ideate/SKILL.md", "id": "0" * 64}],
            "option-shaping": [
                {"path": "skills/option-shaping/SKILL.md", "id": "0" * 64}
            ],
            "making-recommendations": [
                {
                    "path": "skills/making-recommendations/SKILL.md",
                    "id": "0" * 64,
                }
            ],
        },
        "method": _fixture_method_pins(contract),
        "evidence": [],
        "in-packet": [],
    }


def _fixture_setup_document(
    contract: Contract, *, transition_seeds: bool = True
) -> dict:
    candidates = [
        {
            "wording": "Option A — file sync over Syncthing",
            "provenance-flag": "user-seed",
        }
    ]
    if transition_seeds:
        candidates.extend(
            [
                {
                    "wording": "Option D — revived idea",
                    "provenance-flag": "revived",
                },
                {
                    "wording": "Option E — accepted idea",
                    "provenance-flag": "accepted",
                },
            ]
        )
    return {
        "schema": SETUP_SCHEMA,
        "invocation-wording-initial": "fixture invocation",
        "directives": [],
        "directives-collapsed": [],
        "fields": {
            "frame": {
                "value": "choose a note-sync approach for a two-person team",
                "provenance": "user-supplied",
            },
            "field-mode": {"value": "seed-and-widen", "provenance": "default"},
            "constraints": {
                "value": [{"constraint": "must run offline", "price": "no cloud sync"}],
                "provenance": "user-supplied",
            },
            "values": {"value": [], "provenance": "absent"},
            "stakes": {"value": "absent", "provenance": "absent"},
            "evidence-inputs": {
                "value": "none supplied",
                "provenance": "absent",
            },
            "evidence-authorization": {
                "value": "supplied evidence inputs and named paths may be inspected by default; no additional sources, web research, or probes are authorized",
                "provenance": "default",
            },
            "survivor-budget": {"value": 4, "provenance": "default"},
            "degradation-permission": {
                "value": "absent",
                "provenance": "absent",
            },
        },
        "candidates": candidates,
        "soft-preferences": {
            "provenance": "inferred",
            "entries": [
                {
                    "candidate": "Option A — file sync over Syncthing",
                    "criteria": ["ongoing operating burden matters"],
                    "authority-note": {
                        "text": "user lean: mentioned twice, called it 'the obvious one'",
                        "provenance": "inferred",
                        "span": "fixture span",
                    },
                }
            ],
        },
        "composition-provenance": dict(_FIXTURE_PROVENANCE),
        "bounds": dict(contract.bounds),
        "source-capsule-id": "none",
    }


def _fixture_store(
    contract: Contract,
    readset: ReadSet,
    root: Path,
    *,
    transition_seeds: bool = True,
) -> Store:
    store = _initialize_setup_store(
        root,
        "fixture-run",
        _fixture_setup_document(contract, transition_seeds=transition_seeds),
        contract,
        readset,
    )
    store.write(
        {
            "schema": RUNSTATE_SCHEMA,
            "kind": "pins",
            "run": "fixture-run",
            "seq": 2,
            "body": _fixture_pins_body(contract),
        },
        writer="write-item",
    )
    return store


def _fixture_record_brief(
    store: Store, stage: str, contract: Contract, readset: ReadSet
) -> str:
    brief = render_brief(stage, store, contract, readset, None)
    store.write(
        {
            "schema": RUNSTATE_SCHEMA,
            "kind": "brief-render",
            "run": store.require("echo")["run"],
            "seq": store.next_seq(),
            "stage": stage,
            "body": {"brief-id": sha256_bytes(brief.encode("utf-8"))},
        },
        writer="render-brief",
    )
    return brief


def _fixture_capsule(contract: Contract) -> dict:
    """A realistic, fully nested completed-run capsule for roundtrip and
    import fixtures."""
    field = [
        {"wording": "Option A — file sync over Syncthing", "provenance": "user-seed"},
        {"wording": "Option B — hosted wiki", "provenance": "generated"},
        {"wording": "Option C — shared git repo", "provenance": "generated"},
    ]
    record_c = {
        "option": "Option C — shared git repo",
        "status": "active",
        "delegation": "field narrowing under the echoed budget",
        "predicate-source": "agent-derived proposition",
        "cut-basis": "dominance",
        "epistemic-status": "fact-established at comparable resolution",
        "reason": "fixture reason",
        "load-bearing-premise": "fixture premise",
        "strongest-case": "fixture strongest case, written before the kill",
        "revive-if": "fixture revival condition",
    }
    contract_values: dict[str, object] = {
        "frame": "choose a note-sync approach for a two-person team",
        "field-mode": "seed-and-widen",
        "constraints": [],
        "values": [],
        "soft-prefs": ["ongoing operating burden matters"],
        "stakes": "absent",
        "evidence-inputs": "none supplied",
        "evidence-authorization": "default inspection only",
        "survivor-budget": 4,
        "degradation-permission": "absent",
    }
    pin = _fixture_method_pins(contract)
    return {
        "schema": CAPSULE_SCHEMA,
        "run": "fixture-capsule-run",
        "terminal": "close rendered",
        "effective-contract": {
            **{
                name: {"value": value, "provenance": "default"}
                for name, value in contract_values.items()
            },
            "evidence-identity": {"named": [], "in-packet": []},
            "method-identity": pin,
            "bounds": dict(contract.bounds),
            "invocation-wording": {
                "initial": "fixture invocation",
                "directives": [],
                "directives-collapsed": [],
                "source-capsule-id": "none",
            },
        },
        "setup-decomposition": {
            "frame": "choose a note-sync approach for a two-person team",
            "candidates": [
                {
                    "wording": "Option A — file sync over Syncthing",
                    "provenance-flag": "user-seed",
                    "authority-note": {
                        "text": "user lean: called it 'the obvious one'",
                        "provenance": "inferred",
                        "span": "fixture span",
                    },
                }
            ],
            "stakes": "absent",
            "soft-preferences": {
                "provenance": "default",
                "entries": [
                    {
                        "candidate": "absent",
                        "criteria": ["ongoing operating burden matters"],
                        "authority-note": "absent",
                    },
                    {
                        "candidate": "Option A — file sync over Syncthing",
                        "criteria": [],
                        "authority-note": {
                            "text": "user lean: called it 'the obvious one'",
                            "provenance": "inferred",
                            "span": "fixture span",
                        },
                    },
                ],
            },
            "composition-provenance": dict(_FIXTURE_PROVENANCE),
        },
        "recommend-authority-packet": {
            "survivors": field[:2],
            "order-provenance": "Generate-produced order — non-evaluative; never evidence of user lean",
            "authority-notes": [
                {
                    "option": "Option A — file sync over Syncthing",
                    "authority-note": {
                        "text": "user lean: called it 'the obvious one'",
                        "provenance": "inferred",
                        "span": "fixture span",
                    },
                }
            ],
            "overflow": "not produced: no overflow disclosed",
            "stakes": "absent",
        },
        "original-field": field,
        "generation-boundary": "Untouched fixed points: none reported",
        "field-order-origin": "generate-produced",
        "survivors": field[:2],
        "overflow": "not produced: no overflow disclosed",
        "records": [record_c],
        "retrievals": [],
        "surface": "fixture comparison surface",
        "consequences": [],
        "close": "clear call: Option A — fixture close",
        "registered-leans": {
            "agent-first-lean": "Option A",
            "user-visible-lean": "Option A",
        },
        "terminal-claim": "not produced: close rendered",
        "exclusion-check": "Exclusion check: no live recorded challenge found",
        "provisional-seed": "not applicable",
        "revival-instructions": "paste this capsule with a revival directive naming the option",
        "proof-boundary": {
            "packet-isolation": "fixture",
            "read-isolation": "packet-field isolation only; evidence-content encounters: none reported",
            "constituent-pins": {
                "ideate": [{"path": "skills/ideate/SKILL.md", "id": "0" * 64}],
                "option-shaping": [
                    {"path": "skills/option-shaping/SKILL.md", "id": "0" * 64}
                ],
                "making-recommendations": [
                    {"path": "skills/making-recommendations/SKILL.md", "id": "0" * 64}
                ],
            },
            "method-identity": pin,
            "effective-models": "unknown",
            "evidence-scope-used": "none",
            "containment": "behavioral",
            "store-path": "fixture",
            "collapses": "none",
            "not-proven": "fixture",
        },
    }


def _fixture_setup_failure_capsule(store: Store, contract: Contract) -> dict:
    """Return an echo-only setup-write failure capsule with no invented pins."""
    echo = store.require("echo")["body"]
    decomposition = _decomposition_from_echo(echo, contract)
    not_produced = "not produced: setup decomposition write failed"
    return {
        "schema": CAPSULE_SCHEMA,
        "run": store.require("echo")["run"],
        "terminal": "store failed: write",
        "effective-contract": {
            **{
                name: copy.deepcopy(echo["fields"][name])
                for name in contract.echo_contract_fields
            },
            "evidence-identity": PINS_NOT_PRODUCED,
            "method-identity": PINS_NOT_PRODUCED,
            "bounds": copy.deepcopy(echo["bounds"]),
            "invocation-wording": {
                "initial": echo["invocation-wording-initial"],
                "directives": copy.deepcopy(echo["directives"]),
                "directives-collapsed": copy.deepcopy(echo["directives-collapsed"]),
                "source-capsule-id": echo["source-capsule-id"],
            },
        },
        "setup-decomposition": {
            "frame": decomposition["frame"],
            "candidates": decomposition["candidates"],
            "stakes": decomposition["stakes"],
            "soft-preferences": copy.deepcopy(echo["setup-source"]["soft-preferences"]),
            "composition-provenance": decomposition["composition-provenance"],
        },
        "field-order-origin": not_produced,
        "recommend-authority-packet": not_produced,
        "original-field": not_produced,
        "generation-boundary": not_produced,
        "survivors": not_produced,
        "overflow": not_produced,
        "records": not_produced,
        "retrievals": not_produced,
        "surface": not_produced,
        "consequences": not_produced,
        "close": not_produced,
        "registered-leans": not_produced,
        "terminal-claim": not_produced,
        "exclusion-check": not_produced,
        "provisional-seed": not_produced,
        "revival-instructions": (
            "Paste this failure capsule unchanged in a new deliberate invocation."
        ),
        "proof-boundary": {
            "packet-isolation": "No stage was dispatched.",
            "read-isolation": "packet-field isolation only; no stage dispatched",
            "constituent-pins": PINS_NOT_PRODUCED,
            "method-identity": PINS_NOT_PRODUCED,
            "effective-models": "No stage was dispatched.",
            "evidence-scope-used": "Setup echo only.",
            "containment": "No stage was dispatched.",
            "store-path": str(store.root),
            "collapses": "none",
            "not-proven": "No stage behavior or isolation is proven.",
        },
    }


def _fixture_failed_envelope(contract: Contract, stage: str) -> dict:
    """Return a shape-valid failed envelope with no produced artifacts."""
    return {
        "schema": ENVELOPE_SCHEMA,
        "stage": stage,
        "status": "failed: fixture failure",
        "artifacts": {
            entry["key"]: "not produced: fixture failure"
            for entry in contract.obliged[stage]
        },
        "retrievals": "none",
        "encounters": "none",
        "pins": "none",
        "model": "unknown",
    }


def _fixture_partial_failure_capsule(contract: Contract, stage: str) -> dict:
    """Return a capsule carrying only artifacts produced before a failed stage."""
    capsule = _fixture_capsule(contract)
    capsule["terminal"] = f"stage failed: {stage}"
    stage_index = contract.stages.index(stage)
    artifact_stage = {
        "original-field": "generate",
        "generation-boundary": "generate",
        "field-order-origin": "generate",
        "survivors": "prune",
        "overflow": "prune",
        "records": "prune",
        "recommend-authority-packet": "recommend",
        "surface": "shape",
        "consequences": "shape",
        "close": "recommend",
        "registered-leans": "recommend",
        "provisional-seed": "recommend",
        "terminal-claim": "contest",
        "exclusion-check": "contest",
    }
    for key, producer in artifact_stage.items():
        if contract.stages.index(producer) >= stage_index:
            capsule[key] = f"not produced: {stage} failed"
    return capsule


def _fixture_one_survivor_capsule(contract: Contract) -> dict:
    """Return a valid close-less terminal whose Contest basis is a claim."""
    capsule = _fixture_capsule(contract)
    field = capsule["original-field"]
    terminal = "one candidate survives the authorized cuts"
    capsule["terminal"] = terminal
    capsule["survivors"] = field[:1]
    capsule["records"] = [
        {
            "option": option["wording"],
            "status": "active",
            "delegation": "field narrowing under the echoed budget",
            "predicate-source": "agent-derived proposition",
            "cut-basis": "dominance",
            "epistemic-status": "fact-established at comparable resolution",
            "reason": "fixture reason",
            "load-bearing-premise": "fixture premise",
            "strongest-case": "fixture strongest case, written before the kill",
            "revive-if": "fixture revival condition",
        }
        for option in field[1:]
    ]
    capsule["recommend-authority-packet"] = "not produced: one-survivor terminal"
    capsule["surface"] = "not produced: one-survivor terminal"
    capsule["consequences"] = "not produced: one-survivor terminal"
    capsule["close"] = "not produced: one-survivor terminal"
    capsule["registered-leans"] = "not produced: one-survivor terminal"
    capsule["provisional-seed"] = "not produced: one-survivor terminal"
    capsule["terminal-claim"] = {
        "terminal": terminal,
        "claim": "the sole survivor is Option A under the confirmed cuts",
        "survivor": field[0]["wording"],
    }
    return capsule


def _fixture_seed_capsule(
    contract: Contract, *, wording: str = "Option Z — local-first CRDT"
) -> dict:
    """Return a valid close-less capsule carrying one provisional seed."""
    capsule = _fixture_capsule(contract)
    terminal = "field not ready: provisional seed available"
    capsule["terminal"] = terminal
    capsule["close"] = "not produced: field not ready"
    capsule["registered-leans"] = "not produced: field not ready"
    capsule["provisional-seed"] = {
        "wording": wording,
        "handle": "local CRDT",
        "core-idea": "merge offline edits with a local replicated data type",
        "distinct-bet": "conflict-free merging is worth the implementation cost",
    }
    capsule["terminal-claim"] = {
        "terminal": terminal,
        "claim": "the current field is not ready without another distinct bet",
        "survivor": "not applicable",
    }
    return capsule


def _capsule_text(document: dict) -> str:
    body = dump_yaml(document)
    return body + f"capsule-complete: {sha256_bytes(body.encode('utf-8'))}\n"


def _expect(name: str, expected: str, function, results: list) -> None:
    """expected: 'block' (Refusal/ValidationFailure) or 'pass'."""
    try:
        function()
        outcome = "pass"
        detail = ""
    except (Refusal, ValidationFailure, StoreReadLoss) as exc:
        outcome = "block"
        detail = str(exc)
    ok = outcome == expected
    results.append((name, expected, outcome, detail, ok))


def cmd_fixtures(args: argparse.Namespace) -> int:
    readset = ReadSet()
    contract = load_contract(Path(args.data), readset)
    fixtures_dir = Path(os.path.realpath(Path(__file__).parent / "fixtures"))
    readset.allow(fixtures_dir)
    results: list = []
    caps = dict(
        byte_cap=contract.bounds["parse-bytes"],
        depth_cap=contract.bounds["parse-depth"],
    )

    def parse_fixture(name: str):
        raw = readset.read_bytes(fixtures_dir / name)
        return safe_parse(raw, **caps, op=name)

    # must block
    _expect(
        "hostile custom tag rejected",
        "block",
        lambda: parse_fixture("must-block/hostile-tag.yaml"),
        results,
    )
    _expect(
        "anchor/alias expansion rejected",
        "block",
        lambda: parse_fixture("must-block/alias-expansion.yaml"),
        results,
    )
    _expect(
        "duplicate top-level YAML key rejected",
        "block",
        lambda: safe_parse(
            b"key: first\nkey: second\n", **caps, op="duplicate top key"
        ),
        results,
    )
    _expect(
        "duplicate nested YAML key rejected",
        "block",
        lambda: safe_parse(
            b"outer:\n  key: first\n  key: second\n",
            **caps,
            op="duplicate nested key",
        ),
        results,
    )
    _expect(
        "over-cap input rejected before parse",
        "block",
        lambda: safe_parse(
            b"key: " + b"a" * contract.bounds["parse-bytes"],
            **caps,
            op="synthesized over-cap",
        ),
        results,
    )
    _expect(
        "over-depth input rejected before parse",
        "block",
        lambda: safe_parse(
            (
                "a: " * 0
                + "[" * (contract.bounds["parse-depth"] + 2)
                + "]" * (contract.bounds["parse-depth"] + 2)
            ).encode(),
            **caps,
            op="synthesized over-depth",
        ),
        results,
    )
    _expect(
        "unknown envelope key rejected",
        "block",
        lambda: validate_envelope_shape(
            parse_fixture("must-block/unknown-key-envelope.yaml"), contract
        ),
        results,
    )
    _expect(
        "read outside the explicit read set refused",
        "block",
        lambda: ReadSet().read_bytes(Path("/etc/passwd")),
        results,
    )

    with tempfile.TemporaryDirectory() as tmp:
        sandbox = Path(tmp)
        readset.allow(sandbox)
        store = _fixture_store(contract, readset, sandbox / "deliberate-run-live")
        _expect(
            "off-column packet item refused (authority notes into prune)",
            "block",
            lambda: render_brief(
                "prune", store, contract, readset, ["field", "authority-notes-survivor"]
            ),
            results,
        )
        _expect(
            "off-column packet item refused (excluded identities into recommend)",
            "block",
            lambda: render_brief(
                "recommend", store, contract, readset, ["authority-notes-excluded"]
            ),
            results,
        )
        _expect(
            "partial-column render refused (frame-only generate brief)",
            "block",
            lambda: render_brief("generate", store, contract, readset, ["frame"]),
            results,
        )
        _expect(
            "in-column generate brief renders",
            "pass",
            lambda: render_brief("generate", store, contract, readset, None),
            results,
        )

        def encounters_carrier_guidance() -> None:
            brief = render_brief("generate", store, contract, readset, None)
            required = (
                "`encounters` has exactly two valid carrier shapes:\n"
                "```yaml\nencounters: none\n```",
                "encounters:\n  - kind: instruction-like\n    where: |-\n"
                "      evidence-inputs\n    note: |-\n"
                "      Treated as an evidence-boundary declaration, not as decision evidence.",
                "Every list entry is a mapping, never a string.",
            )
            missing = [snippet for snippet in required if snippet not in brief]
            if missing:
                raise fail(
                    "fixture",
                    "rendered Generate brief is missing encounters carrier guidance",
                    missing,
                )

        _expect(
            "rendered Generate brief shows both valid encounters carriers",
            "pass",
            encounters_carrier_guidance,
            results,
        )

        def envelope_with_encounters(value: object) -> dict[str, object]:
            envelope = parse_fixture("must-pass/inert-prose-envelope.yaml")
            envelope["encounters"] = value
            return envelope

        _expect(
            "mapping-shaped encounter entry validates",
            "pass",
            lambda: validate_envelope_shape(
                envelope_with_encounters(
                    [
                        {
                            "kind": "instruction-like",
                            "where": "evidence-inputs",
                            "note": "Treated as an evidence-boundary declaration.",
                        }
                    ]
                ),
                contract,
            ),
            results,
        )
        _expect(
            "string encounter entry remains rejected",
            "block",
            lambda: validate_envelope_shape(
                envelope_with_encounters(
                    [
                        "Instruction-like content appeared in evidence-inputs and was treated as data."
                    ]
                ),
                contract,
            ),
            results,
        )

        def pins_carrier_guidance() -> None:
            brief = render_brief("generate", store, contract, readset, None)
            required = (
                "`pins` has exactly two valid carrier shapes:\n"
                "```yaml\npins: none\n```",
                "pins:\n  - surface: /absolute/path/to/loaded/SKILL.md\n"
                "    id: 0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
                "entry is exactly `{surface, id}`. Legacy pin maps",
                "Legacy pin maps using `class`, `path`,\n"
                "`verified`, or any other key are invalid",
            )
            missing = [snippet for snippet in required if snippet not in brief]
            if missing:
                raise fail(
                    "fixture",
                    "rendered Generate brief is missing pins carrier guidance",
                    missing,
                )

        _expect(
            "rendered Generate brief shows both valid pins carriers",
            "pass",
            pins_carrier_guidance,
            results,
        )

        def envelope_with_pins(value: object) -> dict[str, object]:
            envelope = parse_fixture("must-pass/inert-prose-envelope.yaml")
            envelope["pins"] = value
            return envelope

        _expect(
            "mapping-shaped pin entry validates",
            "pass",
            lambda: validate_envelope_shape(
                envelope_with_pins(
                    [
                        {
                            "surface": "/absolute/path/to/loaded/SKILL.md",
                            "id": "0" * 64,
                        }
                    ]
                ),
                contract,
            ),
            results,
        )
        _expect(
            "legacy class-path-verified pin entry remains rejected",
            "block",
            lambda: validate_envelope_shape(
                envelope_with_pins(
                    [
                        {
                            "class": "constituent",
                            "path": "/absolute/path/to/loaded/SKILL.md",
                            "id": "0" * 64,
                            "verified": True,
                        }
                    ]
                ),
                contract,
            ),
            results,
        )

        def seeds_carriage():
            brief = render_brief("generate", store, contract, readset, None)
            if (
                "Option D — revived idea" not in brief
                or "Option E — accepted idea" not in brief
            ):
                raise fail(
                    "fixture",
                    "accepted/revived candidates missing from the rendered seeds item",
                )

        _expect(
            "accepted and revived candidates render as collapse-exempt seeds",
            "pass",
            seeds_carriage,
            results,
        )
        _expect(
            "inert template-looking prose passes",
            "pass",
            lambda: validate_envelope_shape(
                parse_fixture("must-pass/inert-prose-envelope.yaml"), contract
            ),
            results,
        )

        def path_with_spaces():
            spaced = sandbox / "evidence file with spaces.txt"
            spaced.write_text("inert evidence\n")
            local = ReadSet()
            local.allow(spaced)
            return identity_of_path(spaced, contract, local)

        _expect("authorized path with spaces hashes", "pass", path_with_spaces, results)

        def path_with_metacharacters():
            sentinel = sandbox / "PWNED"
            path = sandbox / "evidence ; $(touch PWNED) [x] 'quoted'.txt"
            path.write_text("inert evidence\n")
            local = ReadSet()
            local.allow(path)
            identity, expanded_bytes = identity_of_path(path, contract, local)
            if identity["path"] != str(path) or expanded_bytes != len(
                "inert evidence\n"
            ):
                raise fail(
                    "fixture", "metacharacter path identity changed the literal path"
                )
            if sentinel.exists():
                raise fail("fixture", "metacharacter path text was executed")

        _expect(
            "authorized metacharacter path is treated literally",
            "pass",
            path_with_metacharacters,
            results,
        )

        def aggregate_identity_refuses_before_hashing():
            global _materialize_identity_plan

            cap = contract.bounds["named-evidence-expanded-bytes"]
            first = sandbox / "aggregate-first.bin"
            second = sandbox / "aggregate-second.bin"
            with first.open("wb") as handle:
                handle.truncate(cap // 2 + 1)
            with second.open("wb") as handle:
                handle.truncate(cap // 2 + 1)
            original = _materialize_identity_plan

            def unexpected_hash(*_args, **_kwargs):
                raise AssertionError("aggregate bound was checked only after hashing")

            _materialize_identity_plan = unexpected_hash
            try:
                cmd_identity(
                    argparse.Namespace(
                        data=str(contract.data_path),
                        paths=[str(first), str(second)],
                        as_evidence=True,
                        as_in_packet=False,
                    )
                )
            finally:
                _materialize_identity_plan = original

        _expect(
            "aggregate evidence cap refuses before any content hash",
            "block",
            aggregate_identity_refuses_before_hashing,
            results,
        )

        def in_packet_identity_cap_refuses_before_hashing():
            global _materialize_identity_plan

            cap = contract.bounds["in-packet-evidence-bytes"]
            payload = sandbox / "oversize-in-packet.bin"
            with payload.open("wb") as handle:
                handle.truncate(cap + 1)
            original = _materialize_identity_plan

            def unexpected_hash(*_args, **_kwargs):
                raise AssertionError("in-packet bound was checked only after hashing")

            _materialize_identity_plan = unexpected_hash
            try:
                cmd_identity(
                    argparse.Namespace(
                        data=str(contract.data_path),
                        paths=[str(payload)],
                        as_evidence=False,
                        as_in_packet=True,
                    )
                )
            finally:
                _materialize_identity_plan = original

        _expect(
            "in-packet evidence cap refuses before any content hash",
            "block",
            in_packet_identity_cap_refuses_before_hashing,
            results,
        )

        def split_call_pin_body_over_cap(kind: str, bound_name: str) -> None:
            cap = contract.bounds[bound_name]
            pins = {
                "constituents": {
                    name: [{"path": f"skills/{name}/SKILL.md", "id": "0" * 64}]
                    for name in contract.constituent_names
                },
                "method": _fixture_method_pins(contract),
                "evidence": [],
                "in-packet": [],
            }
            pins[kind] = [
                {
                    "path": f"first-{kind}.bin",
                    "id": "1" * 64,
                    "bytes": cap // 2 + 1,
                },
                {
                    "path": f"second-{kind}.bin",
                    "id": "2" * 64,
                    "bytes": cap // 2 + 1,
                },
            ]
            _check_body_pins("fixture", pins, contract)

        _expect(
            "split identity calls cannot bypass named-evidence aggregate cap",
            "block",
            lambda: split_call_pin_body_over_cap(
                "evidence", "named-evidence-expanded-bytes"
            ),
            results,
        )
        _expect(
            "split identity calls cannot bypass in-packet aggregate cap",
            "block",
            lambda: split_call_pin_body_over_cap(
                "in-packet", "in-packet-evidence-bytes"
            ),
            results,
        )

        def unsized_no_comparable_identity():
            pins = {
                "constituents": {
                    name: [{"path": f"skills/{name}/SKILL.md", "id": "0" * 64}]
                    for name in contract.constituent_names
                },
                "method": _fixture_method_pins(contract),
                "evidence": [],
                "in-packet": [
                    {"name": "opaque attachment", "id": "no comparable identity"}
                ],
            }
            _check_body_pins("fixture", pins, contract)

        _expect(
            "no-comparable in-packet identity still requires a byte measurement",
            "block",
            unsized_no_comparable_identity,
            results,
        )

        def empty_not_produced_reason():
            document = _fixture_failed_envelope(contract, "generate")
            document["artifacts"]["field"] = "not produced:"
            validate_envelope_shape(document, contract)

        _expect(
            "empty not-produced reason rejected",
            "block",
            empty_not_produced_reason,
            results,
        )

        def stale_generate_insertion():
            document = parse_fixture("must-pass/inert-prose-envelope.yaml")
            document["artifacts"]["field"][0]["insertion"] = "original-field-position"
            validate_envelope_shape(document, contract)

        _expect(
            "fresh Generate field rejects stale insertion provenance",
            "block",
            stale_generate_insertion,
            results,
        )

        def generate_drops_collapse_exempt_seed():
            seed_store = _fixture_store(
                contract,
                readset,
                sandbox / "deliberate-generate-seed-live",
                transition_seeds=True,
            )
            document = parse_fixture("must-pass/inert-prose-envelope.yaml")
            validate_envelope_shape(document, contract)
            validate_envelope_against_store(document, seed_store, contract)

        _expect(
            "Generate cannot drop collapse-exempt revived and accepted seeds",
            "block",
            generate_drops_collapse_exempt_seed,
            results,
        )

        # the generate envelope every prune fixture below validates against
        store = _fixture_store(
            contract,
            readset,
            sandbox / "deliberate-prune-live",
            transition_seeds=False,
        )
        _fixture_record_brief(store, "generate", contract, readset)
        store.write(
            {
                "schema": RUNSTATE_SCHEMA,
                "kind": "envelope",
                "run": "fixture-run",
                "seq": store.next_seq(),
                "stage": "generate",
                "body": {
                    "document": parse_fixture("must-pass/inert-prose-envelope.yaml"),
                    "amendments": [],
                },
            },
            writer="validate-envelope",
        )

        def prune_envelope(survivors: list[dict], records: list[dict]) -> dict:
            return {
                "schema": ENVELOPE_SCHEMA,
                "stage": "prune",
                "status": "completed",
                "artifacts": {
                    "survivors": survivors,
                    "exclusion-records": records,
                    "overflow-disclosure": "not applicable",
                },
                "retrievals": "none",
                "encounters": "none",
                "pins": "none",
                "model": "unknown",
            }

        def full_record(option: str, basis: str = "dominance") -> dict:
            return {
                "option": option,
                "status": "active",
                "delegation": "field narrowing under the echoed budget",
                "predicate-source": "agent-derived proposition",
                "cut-basis": basis,
                "epistemic-status": "fact-established at comparable resolution",
                "reason": "fixture reason",
                "load-bearing-premise": "fixture premise",
                "strongest-case": "written before the kill",
                "revive-if": "fixture revival condition",
            }

        option_a = {
            "wording": "Option A — file sync over Syncthing",
            "provenance": "user-seed",
        }
        option_b = {"wording": "Option B — hosted wiki", "provenance": "generated"}

        def check_prune(envelope: dict) -> None:
            validate_envelope_shape(envelope, contract)
            validate_envelope_against_store(envelope, store, contract)

        _expect(
            "reordering prune envelope rejected (order invariant)",
            "block",
            lambda: check_prune(prune_envelope([option_b, option_a], [])),
            results,
        )
        _expect(
            "silent candidate drop rejected (conservation)",
            "block",
            lambda: check_prune(prune_envelope([option_a], [])),
            results,
        )
        _expect(
            "exclusion record for a surviving option rejected (disjointness)",
            "block",
            lambda: check_prune(
                prune_envelope(
                    [option_a, option_b],
                    [full_record("Option A — file sync over Syncthing")],
                )
            ),
            results,
        )
        _expect(
            "conserving prune partition accepted",
            "pass",
            lambda: check_prune(
                prune_envelope([option_a], [full_record("Option B — hosted wiki")])
            ),
            results,
        )

        # wording canonicalization at identity ingress: normalized once at
        # origin, byte-exact everywhere downstream
        wrapped_wording = (
            "Option B — a hosted wiki serving\nthe two-person team with offline\n"
            "mirrors kept in sync"
        )
        canonical_wording = (
            "Option B — a hosted wiki serving the two-person team with offline "
            "mirrors kept in sync"
        )

        def wrapped_generate_canonicalized_then_prune_passes():
            live = _fixture_store(
                contract,
                readset,
                sandbox / "deliberate-canonical-live",
                transition_seeds=False,
            )
            _fixture_record_brief(live, "generate", contract, readset)
            document = parse_fixture("must-pass/inert-prose-envelope.yaml")
            document["artifacts"]["field"][1]["wording"] = wrapped_wording
            canonicalize_generate_wordings(document)
            validate_envelope_shape(document, contract)
            validate_envelope_against_store(document, live, contract)
            stored = document["artifacts"]["field"][1]["wording"]
            if stored != canonical_wording:
                raise fail(
                    "fixture",
                    "generated wording was not canonicalized at Generate ingress",
                    stored,
                )
            live.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "fixture-run",
                    "seq": live.next_seq(),
                    "stage": "generate",
                    "body": {"document": document, "amendments": []},
                },
                writer="validate-envelope",
            )
            prune = prune_envelope(
                [
                    dict(option_a),
                    {"wording": canonical_wording, "provenance": "generated"},
                ],
                [],
            )
            validate_envelope_shape(prune, contract)
            validate_envelope_against_store(prune, live, contract)

        _expect(
            "soft-wrapped generated wording canonicalized at origin, canonical Prune echo accepted",
            "pass",
            wrapped_generate_canonicalized_then_prune_passes,
            results,
        )

        def canonical_field_conservation_stays_exact():
            live = Store(sandbox / "deliberate-canonical-live", contract, readset)
            prune = prune_envelope([dict(option_a)], [])
            validate_envelope_shape(prune, contract)
            validate_envelope_against_store(prune, live, contract)

        _expect(
            "prune partition conservation stays exact on a canonicalized field",
            "block",
            canonical_field_conservation_stays_exact,
            results,
        )

        def generated_post_normalization_collision():
            document = parse_fixture("must-pass/inert-prose-envelope.yaml")
            document["artifacts"]["field"].append(
                {"wording": "Option B —\nhosted wiki", "provenance": "generated"}
            )
            canonicalize_generate_wordings(document)
            validate_envelope_shape(document, contract)

        _expect(
            "generated wordings colliding after normalization rejected",
            "block",
            generated_post_normalization_collision,
            results,
        )

        def setup_post_normalization_collision():
            setup = _fixture_setup_document(contract, transition_seeds=False)
            setup["candidates"].append(
                {
                    "wording": "Option A — file\nsync over Syncthing",
                    "provenance-flag": "user-seed",
                }
            )
            normalize_setup_document(setup, contract)

        _expect(
            "setup candidates colliding after normalization rejected",
            "block",
            setup_post_normalization_collision,
            results,
        )

        def multiline_setup_candidate_canonicalized():
            setup = _fixture_setup_document(contract, transition_seeds=False)
            multiline = "Option A — file\nsync over Syncthing"
            canonical = "Option A — file sync over Syncthing"
            setup["candidates"][0]["wording"] = multiline
            setup["soft-preferences"]["entries"][0]["candidate"] = multiline
            echo, decomposition = normalize_setup_document(setup, contract)
            stored = [c["wording"] for c in decomposition["candidates"]]
            source = echo["setup-source"]
            entry = source["soft-preferences"]["entries"][0]["candidate"]
            if (
                stored != [canonical]
                or [c["wording"] for c in source["candidates"]] != [canonical]
                or entry != canonical
            ):
                raise fail(
                    "fixture",
                    "setup candidate wordings were not canonicalized at init-setup",
                    {"decomposition": stored, "soft-preference": entry},
                )

        _expect(
            "multi-line setup candidate canonicalized at init-setup",
            "pass",
            multiline_setup_candidate_canonicalized,
            results,
        )

        _expect(
            "whitespace-altered downstream survivor rejected, no comparison-time normalization",
            "block",
            lambda: check_prune(
                prune_envelope(
                    [{"wording": "Option B —\nhosted wiki", "provenance": "generated"}],
                    [full_record("Option A — file sync over Syncthing")],
                )
            ),
            results,
        )

        _expect(
            "whitespace-altered record option rejected, paraphrase guard intact",
            "block",
            lambda: check_prune(
                prune_envelope(
                    [dict(option_a)],
                    [full_record("Option B —\nhosted wiki")],
                )
            ),
            results,
        )

        def legacy_capsule_wordings_rejected():
            capsule = _fixture_capsule(contract)
            capsule["original-field"][2]["wording"] = "Option C — shared\ngit repo"
            capsule["records"][0]["option"] = "Option C — shared\ngit repo"
            validate_capsule_document(capsule, contract)

        _expect(
            "legacy capsule with non-canonical wording rejected",
            "block",
            legacy_capsule_wordings_rejected,
            results,
        )

        def import_preserves_canonical_wording():
            capsule = _fixture_capsule(contract)
            validate_capsule_text(_capsule_text(capsule), contract)
            imported = import_capsule_into_store(
                capsule,
                sandbox / "import-canonical-roundtrip",
                "fixture-import-canonical",
                contract,
                readset,
                invalidate_from=["contest"],
            )
            expected = [
                "Option A — file sync over Syncthing",
                "Option B — hosted wiki",
                "Option C — shared git repo",
            ]
            if _stored_field_wordings(imported) != expected:
                raise fail(
                    "fixture",
                    "imported field wordings drifted from the capsule's canonical bytes",
                    _stored_field_wordings(imported),
                )

        _expect(
            "capsule round-trip and import preserve canonical wording byte-exact",
            "pass",
            import_preserves_canonical_wording,
            results,
        )

        def candidate_attached_preference_is_split_and_withheld():
            favorite = (
                "Twelve structured interviews plus a clickable prototype, "
                "with no live workflow use."
            )
            survivor = (
                "Five-team design-partner cohort using a rough working prototype "
                "in a real weekly workflow."
            )
            second_survivor = (
                "Instrument the current manual workaround across three partner "
                "teams without building a new UI."
            )
            lean = (
                "The user currently leans toward Twelve structured interviews plus "
                "a clickable prototype, with no live workflow use because it is easy "
                "to coordinate and should produce clean qualitative synthesis."
            )
            criterion = (
                "Coordination ease and clean qualitative synthesis are soft "
                "comparison criteria."
            )
            setup = _fixture_setup_document(contract, transition_seeds=False)
            setup["fields"]["frame"] = {
                "value": "choose a six-week validation strategy",
                "provenance": "user-supplied",
            }
            setup["candidates"] = [
                {"wording": favorite, "provenance-flag": "user-seed"},
                {"wording": survivor, "provenance-flag": "user-seed"},
                {"wording": second_survivor, "provenance-flag": "user-seed"},
            ]
            setup["soft-preferences"] = {
                "provenance": "user-supplied",
                "entries": [
                    {
                        "candidate": "absent",
                        "criteria": ["Reusable onboarding material is preferred."],
                        "authority-note": "absent",
                    },
                    {
                        "candidate": favorite,
                        "criteria": [criterion],
                        "authority-note": {
                            "text": lean,
                            "provenance": "user-supplied",
                            "span": lean,
                        },
                    },
                ],
            }
            unsplit = copy.deepcopy(setup)
            unsplit["soft-preferences"]["entries"][1]["criteria"] = [lean]
            try:
                normalize_setup_document(unsplit, contract)
            except ValidationFailure:
                pass
            else:
                raise fail(
                    "fixture",
                    "candidate-attached preference was accepted as a neutral criterion",
                )
            lean_store = _initialize_setup_store(
                sandbox / "candidate-attached-preference-store",
                "candidate-attached-preference-run",
                setup,
                contract,
                readset,
            )
            lean_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "pins",
                    "run": "candidate-attached-preference-run",
                    "seq": lean_store.next_seq(),
                    "body": _fixture_pins_body(contract),
                },
                writer="write-item",
            )
            echo = lean_store.require("echo")["body"]
            decomposition = lean_store.require("decomposition")["body"]
            soft_prefs = echo["fields"]["soft-prefs"]["value"]
            if lean in soft_prefs or favorite in dump_yaml(soft_prefs):
                raise fail(
                    "fixture",
                    "candidate-attached preference leaked into normalized soft-prefs",
                )
            favorite_note = next(
                candidate["authority-note"]
                for candidate in decomposition["candidates"]
                if candidate["wording"] == favorite
            )
            if favorite_note["text"] != lean or criterion not in soft_prefs:
                raise fail(
                    "fixture",
                    "setup normalizer did not preserve the authority note and neutral criterion",
                )

            generated = [
                {"wording": favorite, "provenance": "user-seed"},
                {"wording": survivor, "provenance": "user-seed"},
                {"wording": second_survivor, "provenance": "user-seed"},
            ]
            _fixture_record_brief(lean_store, "generate", contract, readset)
            lean_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "candidate-attached-preference-run",
                    "seq": lean_store.next_seq(),
                    "stage": "generate",
                    "body": {
                        "document": {
                            "schema": ENVELOPE_SCHEMA,
                            "stage": "generate",
                            "status": "completed",
                            "artifacts": {
                                "field": generated,
                                "fixed-points-line": "Untouched fixed points: supplied seeds",
                            },
                            "retrievals": "none",
                            "encounters": "none",
                            "pins": "none",
                            "model": "unknown",
                        },
                        "amendments": [],
                    },
                },
                writer="validate-envelope",
            )
            _fixture_record_brief(lean_store, "prune", contract, readset)
            lean_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "candidate-attached-preference-run",
                    "seq": lean_store.next_seq(),
                    "stage": "prune",
                    "body": {
                        "document": prune_envelope(
                            [
                                {"wording": survivor, "provenance": "user-seed"},
                                {
                                    "wording": second_survivor,
                                    "provenance": "user-seed",
                                },
                            ],
                            [full_record(favorite)],
                        ),
                        "amendments": [],
                    },
                },
                writer="validate-envelope",
            )
            _fixture_record_brief(lean_store, "shape", contract, readset)
            lean_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "candidate-attached-preference-run",
                    "seq": lean_store.next_seq(),
                    "stage": "shape",
                    "body": {
                        "document": {
                            "schema": ENVELOPE_SCHEMA,
                            "stage": "shape",
                            "status": "completed",
                            "artifacts": {
                                "comparison-surface": "Compare observed repeat use and setup burden.",
                                "constraint-consequences": [],
                            },
                            "retrievals": "none",
                            "encounters": "none",
                            "pins": "none",
                            "model": "unknown",
                        },
                        "amendments": [],
                    },
                },
                writer="validate-envelope",
            )
            recommend_brief = render_brief(
                "recommend", lean_store, contract, readset, None
            )
            if favorite in recommend_brief or lean in recommend_brief:
                raise fail(
                    "fixture",
                    "excluded candidate identity reached Recommend through setup-controlled state",
                )
            if criterion not in recommend_brief:
                raise fail(
                    "fixture",
                    "candidate-neutral criterion did not reach Recommend",
                )

        _expect(
            "candidate-attached preference splits and excluded identity cannot reach Recommend",
            "pass",
            candidate_attached_preference_is_split_and_withheld,
            results,
        )

        def failed_stage_diagnostics_are_not_authority():
            diagnostic_store = _fixture_store(
                contract,
                readset,
                sandbox / "failed-diagnostic-store",
                transition_seeds=False,
            )
            generate = parse_fixture("must-pass/inert-prose-envelope.yaml")
            _fixture_record_brief(diagnostic_store, "generate", contract, readset)
            diagnostic_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "fixture-run",
                    "seq": diagnostic_store.next_seq(),
                    "stage": "generate",
                    "body": {"document": generate, "amendments": []},
                },
                writer="validate-envelope",
            )
            failed_prune = prune_envelope(
                [option_a], [full_record("Option B — hosted wiki")]
            )
            failed_prune["status"] = "failed: diagnostic partial values"
            _fixture_record_brief(diagnostic_store, "prune", contract, readset)
            diagnostic_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "fixture-run",
                    "seq": diagnostic_store.next_seq(),
                    "stage": "prune",
                    "body": {"document": failed_prune, "amendments": []},
                },
                writer="validate-envelope",
            )
            if (
                _effective_stage_artifact(
                    diagnostic_store, "prune", "survivors", "survivors"
                )
                is not _MISSING
            ):
                raise fail("fixture", "failed Prune survivors became authority")
            if _effective_records(diagnostic_store) is not _MISSING:
                raise fail("fixture", "failed Prune records became authority")
            try:
                render_brief("shape", diagnostic_store, contract, readset, None)
            except StoreReadLoss:
                return
            raise fail("fixture", "Shape rendered from failed-stage diagnostics")

        _expect(
            "failed-stage partial values remain diagnostic only",
            "pass",
            failed_stage_diagnostics_are_not_authority,
            results,
        )

        def duplicate_field_wordings():
            document = parse_fixture("must-pass/inert-prose-envelope.yaml")
            document["artifacts"]["field"] = [option_a, dict(option_a)]
            validate_envelope_shape(document, contract)

        _expect(
            "duplicate field wordings rejected",
            "block",
            duplicate_field_wordings,
            results,
        )

        def arbitrary_status():
            document = prune_envelope([option_a], [])
            document["status"] = "banana"
            document["artifacts"] = {
                key: "not produced: banana" for key in document["artifacts"]
            }
            validate_envelope_shape(document, contract)

        _expect(
            "arbitrary status word rejected (status grammar)",
            "block",
            arbitrary_status,
            results,
        )

        def exit_status():
            document = prune_envelope([option_a], [])
            document["status"] = "exit: authority gap"
            document["artifacts"] = {
                key: "not produced: authority gap" for key in document["artifacts"]
            }
            validate_envelope_shape(document, contract)

        _expect(
            "named-exit status form passes (status grammar)",
            "pass",
            exit_status,
            results,
        )

        def classified_pin_mismatch_mapping():
            expected = {
                "constituent": "constituent drift",
                "evidence": "evidence drift",
                "method": "method drift",
            }
            for surface, terminal in expected.items():
                status = f"failed: pin mismatch — {surface}:/fixture/{surface}"
                if _classified_pin_mismatch_terminal(status) != terminal:
                    raise fail(
                        "fixture", "classified pin mismatch mapped incorrectly", status
                    )
            if (
                _classified_pin_mismatch_terminal("failed: pin mismatch — constituent:")
                is not None
            ):
                raise fail("fixture", "empty pin-mismatch path was classified")

        _expect(
            "classified pin mismatches map to drift terminals",
            "pass",
            classified_pin_mismatch_mapping,
            results,
        )

        def paraphrased_record():
            record = full_record("Option A — Syncthing file sync")  # paraphrase
            _check_record(
                record,
                contract,
                ["Option A — file sync over Syncthing", "Option B — hosted wiki"],
                "prune",
            )

        _expect(
            "paraphrased record option rejected", "block", paraphrased_record, results
        )

        def shape_provenance():
            _fixture_record_brief(store, "prune", contract, readset)
            store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "fixture-run",
                    "seq": store.next_seq(),
                    "stage": "prune",
                    "body": {
                        "document": prune_envelope([option_a, option_b], []),
                        "amendments": [],
                    },
                },
                writer="validate-envelope",
            )
            brief = render_brief("shape", store, contract, readset, None)
            if (
                "## packet: composition-provenance" not in brief
                or "invocation-span" not in brief
            ):
                raise fail(
                    "fixture",
                    "shape brief carries no composition-provenance evidence item",
                )

        _expect(
            "shape brief carries the composition-provenance item",
            "pass",
            shape_provenance,
            results,
        )

        def decomposition_without_provenance():
            validate_runstate_item(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "decomposition",
                    "run": "fixture-run",
                    "seq": 9,
                    "body": {
                        "frame": "fixture",
                        "candidates": [],
                        "stakes": "absent",
                        "soft-prefs": [],
                        "values": [],
                    },
                },
                contract,
            )

        _expect(
            "decomposition without composition-provenance rejected",
            "block",
            decomposition_without_provenance,
            results,
        )

        def garbage_runstate_echo():
            validate_runstate_item(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "echo",
                    "run": None,
                    "seq": 0,
                    "body": {
                        "invocation-wording-initial": ["not", "a", "string"],
                        "directives": 7,
                        "fields": "just-a-scalar",
                    },
                },
                contract,
            )

        _expect(
            "run-state echo with unusable nested state rejected",
            "block",
            garbage_runstate_echo,
            results,
        )

        def pins_item() -> dict:
            body = copy.deepcopy(store.require("pins")["body"])
            return {
                "schema": RUNSTATE_SCHEMA,
                "kind": "pins",
                "run": "fixture-run",
                "seq": 99,
                "body": body,
            }

        def no_comparable_method_pin():
            item = pins_item()
            item["body"]["method"] = [
                {"path": "references/methods.md", "id": "no comparable identity"}
            ]
            validate_runstate_item(item, contract)

        _expect(
            "method pin rejects no-comparable identity",
            "block",
            no_comparable_method_pin,
            results,
        )

        def empty_method_pins():
            item = pins_item()
            item["body"]["method"] = []
            validate_runstate_item(item, contract)

        _expect(
            "empty method pin set rejected",
            "block",
            empty_method_pins,
            results,
        )

        def empty_constituent_pins():
            item = pins_item()
            item["body"]["constituents"]["ideate"] = []
            validate_runstate_item(item, contract)

        _expect(
            "empty constituent pin set rejected",
            "block",
            empty_constituent_pins,
            results,
        )

        _expect(
            "realistic capsule with terminator validates (nested shapes)",
            "pass",
            lambda: validate_capsule_text(
                _capsule_text(_fixture_capsule(contract)), contract
            ),
            results,
        )

        def empty_capsule_retrieval_concerns():
            capsule = _fixture_capsule(contract)
            capsule["retrievals"] = [
                {
                    "producing-stage": "generate",
                    "source": "fixture source",
                    "retrieved-at": "2026-07-14T12:00:00Z",
                    "fact": "fixture fact",
                    "concerns": [],
                }
            ]
            validate_capsule_text(_capsule_text(capsule), contract)

        _expect(
            "capsule retrieval rejects empty concerns",
            "block",
            empty_capsule_retrieval_concerns,
            results,
        )

        def omitted_recommend_authority_packet():
            capsule = _fixture_capsule(contract)
            capsule["recommend-authority-packet"] = "not produced: omitted"
            validate_capsule_text(_capsule_text(capsule), contract)

        _expect(
            "Recommend artifacts require the authority packet",
            "block",
            omitted_recommend_authority_packet,
            results,
        )

        def omitted_survivor_authority_note():
            capsule = _fixture_capsule(contract)
            capsule["recommend-authority-packet"]["authority-notes"] = []
            validate_capsule_text(_capsule_text(capsule), contract)

        _expect(
            "Recommend packet cannot omit a survivor authority note",
            "block",
            omitted_survivor_authority_note,
            results,
        )

        def completed_capsule_relabelled_generate_failure():
            capsule = _fixture_capsule(contract)
            capsule["terminal"] = "stage failed: generate"
            validate_capsule_text(_capsule_text(capsule), contract)

        _expect(
            "completed artifacts cannot be relabelled as Generate failure",
            "block",
            completed_capsule_relabelled_generate_failure,
            results,
        )

        _expect(
            "partial Prune failure capsule is valid recovery state",
            "pass",
            lambda: validate_capsule_text(
                _capsule_text(_fixture_partial_failure_capsule(contract, "prune")),
                contract,
            ),
            results,
        )

        def unknown_stage_terminal():
            capsule = _fixture_partial_failure_capsule(contract, "prune")
            capsule["terminal"] = "stage failed: hallucinated-stage"
            validate_capsule_text(_capsule_text(capsule), contract)

        _expect(
            "stage-failure terminal rejects an unknown stage",
            "block",
            unknown_stage_terminal,
            results,
        )

        def malformed_seed_schema():
            capsule = _fixture_seed_capsule(contract)
            capsule["provisional-seed"].pop("distinct-bet")
            validate_capsule_text(_capsule_text(capsule), contract)

        _expect(
            "provisional seed requires canonical four-field schema",
            "block",
            malformed_seed_schema,
            results,
        )

        def garbage_capsule():
            capsule_keys = [
                entry["key"]
                for entry in contract.schemas[CAPSULE_SCHEMA]["keys"]
                if entry["key"] not in ("schema", "capsule-complete")
            ]
            document = {"schema": CAPSULE_SCHEMA}
            for key in capsule_keys:
                document[key] = "garbage-scalar"
            validate_capsule_text(_capsule_text(document), contract)

        _expect(
            "capsule of arbitrary scalars rejected (nested shapes)",
            "block",
            garbage_capsule,
            results,
        )

        def truncated_capsule():
            document = _fixture_capsule(contract)
            body = dump_yaml(document)
            terminator = sha256_bytes(body.encode("utf-8"))
            truncated = body[len(body) // 2 :]
            validate_capsule_text(
                truncated + f"capsule-complete: {terminator}\n", contract
            )

        _expect(
            "truncated capsule fails the completeness terminator",
            "block",
            truncated_capsule,
            results,
        )

        def import_contest_recovery():
            capsule = _fixture_capsule(contract)
            imported = import_capsule_into_store(
                capsule,
                sandbox / "import-contest",
                "fixture-import-1",
                contract,
                readset,
                invalidate_from=["contest"],
            )
            brief = render_brief("contest", imported, contract, readset, None)
            if (
                "Option C — shared git repo" not in brief
                or "## packet: close" not in brief
            ):
                raise fail(
                    "fixture",
                    "Contest brief from an imported capsule misses the record or close",
                )

        _expect(
            "fresh-store Contest recovery renders from an imported capsule",
            "pass",
            import_contest_recovery,
            results,
        )

        def import_recommend_recovery():
            capsule = _fixture_capsule(contract)
            imported = import_capsule_into_store(
                capsule,
                sandbox / "import-recommend",
                "fixture-import-2",
                contract,
                readset,
                invalidate_from=["recommend"],
            )
            brief = render_brief("recommend", imported, contract, readset, None)
            if (
                "fixture comparison surface" not in brief
                or "## packet: survivors" not in brief
            ):
                raise fail(
                    "fixture",
                    "Recommend brief from an imported capsule misses the surface or survivors",
                )
            try:
                render_brief("shape", imported, contract, readset, None)
            except Refusal:
                pass
            else:
                raise fail("fixture", "restart plan allowed a stage before Recommend")

        _expect(
            "fresh-store Recommend recovery renders from an imported capsule",
            "pass",
            import_recommend_recovery,
            results,
        )

        def recommend_conditional_carrier_guidance():
            capsule = _fixture_capsule(contract)
            imported = import_capsule_into_store(
                capsule,
                sandbox / "recommend-conditional-carriers",
                "fixture-recommend-conditional-carriers",
                contract,
                readset,
                invalidate_from=["recommend"],
            )
            brief = render_brief("recommend", imported, contract, readset, None)
            required = (
                "Both conditional Recommend artifacts remain mandatory keys",
                "```yaml\ndisposition-records: not applicable\n"
                "provisional-seed: not applicable\n```",
                "A `check first`\nclose does not make either key optional.",
            )
            missing = [snippet for snippet in required if snippet not in brief]
            if missing:
                raise fail(
                    "fixture",
                    "rendered Recommend brief is missing conditional carrier guidance",
                    missing,
                )

        _expect(
            "rendered Recommend brief shows explicit conditional empty carriers",
            "pass",
            recommend_conditional_carrier_guidance,
            results,
        )

        def check_first_recommend_envelope():
            validate_envelope_shape(
                {
                    "schema": ENVELOPE_SCHEMA,
                    "stage": "recommend",
                    "status": "completed",
                    "artifacts": {
                        "close": (
                            "check first\n\n"
                            "The Call: run the bounded feasibility gate before choosing."
                        ),
                        "registered-leans": {
                            "agent-first-lean": "Option A",
                            "user-visible-lean": "No reliable visible lean.",
                        },
                        "disposition-records": "not applicable",
                        "provisional-seed": "not applicable",
                    },
                    "retrievals": "none",
                    "encounters": "none",
                    "pins": "none",
                    "model": "unknown",
                },
                contract,
            )

        _expect(
            "check-first Recommend envelope accepts explicit conditional empties",
            "pass",
            check_first_recommend_envelope,
            results,
        )

        def _field_not_ready_envelope(close: object, seed: object) -> None:
            validate_envelope_shape(
                {
                    "schema": ENVELOPE_SCHEMA,
                    "stage": "recommend",
                    "status": "exit: field not ready",
                    "artifacts": {
                        "close": close,
                        "registered-leans": {
                            "agent-first-lean": "Option A",
                            "user-visible-lean": "No reliable visible lean.",
                        },
                        "disposition-records": "not applicable",
                        "provisional-seed": seed,
                    },
                    "retrievals": "none",
                    "encounters": "none",
                    "pins": "none",
                    "model": "unknown",
                },
                contract,
            )

        _provisional_seed = {
            "wording": "Option Z — the cohort seed reshaped to comparable depth",
            "handle": "reshaped cohort",
            "core-idea": "develop the under-shaped seed before comparing",
            "distinct-bet": "the cohort bet deserves a comparably shaped field",
        }

        _expect(
            "field-not-ready exit with a produced close rejected (close-less branch)",
            "block",
            lambda: _field_not_ready_envelope(
                "field not ready\n\nThe cohort seed is materially less shaped.",
                copy.deepcopy(_provisional_seed),
            ),
            results,
        )

        _expect(
            "field-not-ready exit without the provisional seed rejected",
            "block",
            lambda: _field_not_ready_envelope(
                "not produced: field not ready", "not applicable"
            ),
            results,
        )

        _expect(
            "close-less field-not-ready exit with the provisional seed accepted",
            "pass",
            lambda: _field_not_ready_envelope(
                "not produced: field not ready", copy.deepcopy(_provisional_seed)
            ),
            results,
        )

        def completed_recommend_rejects_not_produced_seed():
            capsule = _fixture_capsule(contract)
            capsule["provisional-seed"] = "not produced: none discovered"
            validate_capsule_document(capsule, contract)

        _expect(
            "completed Recommend without a seed requires not-applicable capsule authority",
            "block",
            completed_recommend_rejects_not_produced_seed,
            results,
        )

        def absent_recommend_rejects_not_applicable_seed():
            capsule = _fixture_one_survivor_capsule(contract)
            capsule["provisional-seed"] = "not applicable"
            validate_capsule_document(capsule, contract)

        _expect(
            "absent Recommend rejects not-applicable provisional-seed authority",
            "block",
            absent_recommend_rejects_not_applicable_seed,
            results,
        )

        def store_backed_check_first_capsule_accepts_and_imports():
            source = _fixture_capsule(contract)
            close = (
                "check first\n\n"
                "The Call: run the bounded feasibility gate before choosing."
            )
            leans = {
                "agent-first-lean": "Option A",
                "user-visible-lean": "No reliable visible lean.",
            }
            source["close"] = close
            source["registered-leans"] = copy.deepcopy(leans)
            source["provisional-seed"] = "not applicable"
            validate_capsule_document(source, contract)

            run = "check-first-store-run"
            store = import_capsule_into_store(
                source,
                sandbox / "check-first-store",
                run,
                contract,
                readset,
                invalidate_from=["recommend"],
            )
            invalidated = store.require("capsule-import")["body"]["capsule"]
            if not _is_not_produced(invalidated["provisional-seed"]):
                raise fail(
                    "fixture",
                    "Recommend invalidation did not replace the completed-empty seed carrier",
                    invalidated["provisional-seed"],
                )

            _fixture_record_brief(store, "recommend", contract, readset)
            recommend = {
                "schema": ENVELOPE_SCHEMA,
                "stage": "recommend",
                "status": "completed",
                "artifacts": {
                    "close": close,
                    "registered-leans": copy.deepcopy(leans),
                    "disposition-records": "not applicable",
                    "provisional-seed": "not applicable",
                },
                "retrievals": "none",
                "encounters": "none",
                "pins": "none",
                "model": "unknown",
            }
            store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": run,
                    "seq": store.next_seq(),
                    "stage": "recommend",
                    "body": {"document": recommend, "amendments": []},
                },
                writer="validate-envelope",
            )

            _fixture_record_brief(store, "contest", contract, readset)
            exclusion = "Exclusion check: no live recorded challenge found"
            contest = {
                "schema": ENVELOPE_SCHEMA,
                "stage": "contest",
                "status": "completed",
                "artifacts": {"exclusion-check-line": exclusion},
                "retrievals": "none",
                "encounters": "none",
                "pins": "none",
                "model": "unknown",
            }
            store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": run,
                    "seq": store.next_seq(),
                    "stage": "contest",
                    "body": {"document": contest, "amendments": []},
                },
                writer="validate-envelope",
            )

            capsule = copy.deepcopy(invalidated)
            capsule["run"] = run
            capsule["recommend-authority-packet"] = copy.deepcopy(
                source["recommend-authority-packet"]
            )
            capsule["close"] = close
            capsule["registered-leans"] = copy.deepcopy(leans)
            capsule["provisional-seed"] = "not applicable"
            capsule["exclusion-check"] = exclusion
            capsule["proof-boundary"]["store-path"] = str(store.root)
            store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "proof-inputs",
                    "run": run,
                    "seq": store.next_seq(),
                    "body": copy.deepcopy(capsule["proof-boundary"]),
                },
                writer="record-proof-inputs",
            )
            store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "terminal-state",
                    "run": run,
                    "seq": store.next_seq(),
                    "body": {"terminal": "close rendered", "carrier": "capsule"},
                },
                writer="record-terminal",
            )
            store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "capsule-progress",
                    "run": run,
                    "seq": store.next_seq(),
                    "body": {"capsule": capsule},
                },
                writer="validate-capsule",
            )
            accepted = store.require("capsule-progress")["body"]["capsule"]

            contest_restart = import_capsule_into_store(
                accepted,
                sandbox / "check-first-contest-restart",
                "check-first-contest-restart-run",
                contract,
                readset,
                invalidate_from=["contest"],
            )
            contest_state = contest_restart.require("capsule-import")["body"]["capsule"]
            if contest_state["provisional-seed"] != "not applicable":
                raise fail(
                    "fixture",
                    "Contest-only restart did not preserve completed-empty seed authority",
                    contest_state["provisional-seed"],
                )
            if (
                contest_restart.require("restart-plan")["body"]["earliest-stage"]
                != "contest"
            ):
                raise fail("fixture", "Contest-only restart moved the frontier")

            recommend_restart = import_capsule_into_store(
                accepted,
                sandbox / "check-first-recommend-restart",
                "check-first-recommend-restart-run",
                contract,
                readset,
                invalidate_from=["recommend"],
            )
            recommend_state = recommend_restart.require("capsule-import")["body"][
                "capsule"
            ]
            if not _is_not_produced(recommend_state["provisional-seed"]):
                raise fail(
                    "fixture",
                    "Recommend restart retained completed-empty seed authority",
                    recommend_state["provisional-seed"],
                )
            if (
                recommend_restart.require("restart-plan")["body"]["earliest-stage"]
                != "recommend"
            ):
                raise fail("fixture", "Recommend restart moved the frontier")

        _expect(
            "store-backed check-first capsule accepts and imports exact empty carriers",
            "pass",
            store_backed_check_first_capsule_accepts_and_imports,
            results,
        )

        def close_less_contest_store(root_name: str) -> Store:
            contest_store = _fixture_store(
                contract,
                readset,
                sandbox / root_name,
                transition_seeds=False,
            )
            _fixture_record_brief(contest_store, "generate", contract, readset)
            contest_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "fixture-run",
                    "seq": contest_store.next_seq(),
                    "stage": "generate",
                    "body": {
                        "document": parse_fixture(
                            "must-pass/inert-prose-envelope.yaml"
                        ),
                        "amendments": [],
                    },
                },
                writer="validate-envelope",
            )
            _fixture_record_brief(contest_store, "prune", contract, readset)
            contest_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "fixture-run",
                    "seq": contest_store.next_seq(),
                    "stage": "prune",
                    "body": {
                        "document": prune_envelope(
                            [option_a], [full_record("Option B — hosted wiki")]
                        ),
                        "amendments": [],
                    },
                },
                writer="validate-envelope",
            )
            return contest_store

        _expect(
            "eligible close-less Contest refuses without terminal claim",
            "block",
            lambda: render_brief(
                "contest",
                close_less_contest_store("contest-missing-claim"),
                contract,
                readset,
                None,
            ),
            results,
        )

        def valid_contest_terminal_claim():
            imported = close_less_contest_store("contest-valid-claim")
            imported.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "terminal-claim",
                    "run": "fixture-run",
                    "seq": imported.next_seq(),
                    "body": {
                        "terminal": "one candidate survives the authorized cuts; no comparative recommendation was performed",
                        "claim": "Option A is the sole survivor of the authorized cuts",
                        "survivor": "Option A — file sync over Syncthing",
                    },
                },
                writer="write-item",
            )
            brief = render_brief("contest", imported, contract, readset, None)
            if "## packet: terminal-claim" not in brief:
                raise fail("fixture", "validated terminal claim did not reach Contest")

        _expect(
            "eligible close-less Contest renders with validated terminal claim",
            "pass",
            valid_contest_terminal_claim,
            results,
        )

        def imported_claim_is_contest_only():
            capsule = _fixture_one_survivor_capsule(contract)
            validate_capsule_document(capsule, contract)
            imported = import_capsule_into_store(
                capsule,
                sandbox / "contest-imported-claim",
                "contest-imported-claim-run",
                contract,
                readset,
                invalidate_from=["contest"],
            )
            contest = render_brief("contest", imported, contract, readset, None)
            if "## packet: terminal-claim" not in contest:
                raise fail("fixture", "imported claim missing from Contest")
            recommend_keys = {
                entry["key"] for entry in contract.include_column("recommend")
            }
            if "terminal-claim" in recommend_keys:
                raise fail(
                    "fixture", "terminal-claim is not Contest-only in the matrix"
                )

        _expect(
            "imported terminal claim is visible only to Contest",
            "pass",
            imported_claim_is_contest_only,
            results,
        )

        def seed_collision_refused():
            wording = "Option A — file sync over Syncthing"
            capsule = _fixture_seed_capsule(contract, wording=wording)
            validate_capsule_document(capsule, contract)
            import_capsule_into_store(
                capsule,
                sandbox / "accept-seed-collision",
                "accept-seed-collision-run",
                contract,
                readset,
                accept_seed=True,
            )

        _expect(
            "accepted seed cannot collide with an existing candidate",
            "block",
            seed_collision_refused,
            results,
        )

        def closed_field_seed_acceptance():
            capsule = _fixture_seed_capsule(contract)
            capsule["effective-contract"]["field-mode"]["value"] = "closed-to-widening"
            capsule["generation-boundary"] = "Generate not run: closed-to-widening"
            capsule["field-order-origin"] = "user-supplied"
            for key in ("original-field", "survivors"):
                for option in capsule[key]:
                    if option["provenance"] == "generated":
                        option["provenance"] = "user-seed"
            for option in capsule["recommend-authority-packet"]["survivors"]:
                if option["provenance"] == "generated":
                    option["provenance"] = "user-seed"
            capsule["recommend-authority-packet"]["order-provenance"] = (
                contract.order_origin_labels["user-supplied"]
            )
            validate_capsule_document(capsule, contract)
            imported = import_capsule_into_store(
                capsule,
                sandbox / "accept-seed-closed",
                "accept-seed-closed-run",
                contract,
                readset,
                accept_seed=True,
            )
            state = imported.require("capsule-import")["body"]["capsule"]
            wording = "Option Z — local-first CRDT"
            field_matches = [
                option
                for option in state["original-field"]
                if option["wording"] == wording
            ]
            candidate_matches = [
                candidate
                for candidate in state["setup-decomposition"]["candidates"]
                if candidate["wording"] == wording
            ]
            if field_matches != [
                {
                    "wording": wording,
                    "provenance": "accepted",
                    "insertion": "appended-by-rule",
                }
            ]:
                raise fail(
                    "fixture", "closed-field acceptance did not append canonically"
                )
            if (
                len(candidate_matches) != 1
                or candidate_matches[0]["provenance-flag"] != "accepted"
            ):
                raise fail("fixture", "accepted seed missing from decomposition")

        _expect(
            "closed-field seed acceptance appends with insertion provenance",
            "pass",
            closed_field_seed_acceptance,
            results,
        )

        def seed_and_widen_acceptance():
            capsule = _fixture_seed_capsule(contract)
            validate_capsule_document(capsule, contract)
            original_field = copy.deepcopy(capsule["original-field"])
            imported = import_capsule_into_store(
                capsule,
                sandbox / "accept-seed-widen",
                "accept-seed-widen-run",
                contract,
                readset,
                accept_seed=True,
            )
            state = imported.require("capsule-import")["body"]["capsule"]
            if state["original-field"] != original_field:
                raise fail("fixture", "seed-and-widen acceptance changed reused field")
            matches = [
                candidate
                for candidate in state["setup-decomposition"]["candidates"]
                if candidate["wording"] == "Option Z — local-first CRDT"
            ]
            if len(matches) != 1 or matches[0]["provenance-flag"] != "accepted":
                raise fail("fixture", "seed-and-widen acceptance missed decomposition")

        _expect(
            "seed-and-widen acceptance updates decomposition without field insertion",
            "pass",
            seed_and_widen_acceptance,
            results,
        )

        def revival_preserves_metadata():
            capsule = _fixture_capsule(contract)
            original_record = copy.deepcopy(capsule["records"][0])
            wording = original_record["option"]
            imported = import_capsule_into_store(
                capsule,
                sandbox / "revival-preserves-metadata",
                "revival-preserves-metadata-run",
                contract,
                readset,
                revive=[wording],
            )
            state = imported.require("capsule-import")["body"]["capsule"]
            revived = next(
                record for record in state["records"] if record["option"] == wording
            )
            expected_record = {**original_record, "status": "revived"}
            if revived != expected_record:
                raise fail("fixture", "revival changed record metadata beyond status")
            field_option = next(
                option
                for option in state["original-field"]
                if option["wording"] == wording
            )
            if field_option != {
                "wording": wording,
                "provenance": "revived",
                "insertion": "original-field-position",
            }:
                raise fail("fixture", "revival lost original-position provenance")
            if not any(
                candidate["wording"] == wording
                and candidate["provenance-flag"] == "revived"
                for candidate in state["setup-decomposition"]["candidates"]
            ):
                raise fail("fixture", "revival missing from setup decomposition")

        _expect(
            "revival preserves record metadata and original field position",
            "pass",
            revival_preserves_metadata,
            results,
        )

        def revival_without_original_field():
            capsule = _fixture_capsule(contract)
            wording = capsule["records"][0]["option"]
            capsule["original-field"] = "not produced: missing fixture field"
            import_capsule_into_store(
                capsule,
                sandbox / "revival-missing-field",
                "revival-missing-field-run",
                contract,
                readset,
                revive=[wording],
            )

        _expect(
            "revival refuses when original field is absent",
            "block",
            revival_without_original_field,
            results,
        )

        def upstream_failed_rerun_suppresses_downstream_imports():
            capsule = _fixture_capsule(contract)
            imported = import_capsule_into_store(
                capsule,
                sandbox / "failed-rerun-suppression",
                "failed-rerun-suppression-run",
                contract,
                readset,
                invalidate_from=["generate"],
            )
            document = _fixture_failed_envelope(contract, "generate")
            _fixture_record_brief(imported, "generate", contract, readset)
            imported.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "failed-rerun-suppression-run",
                    "seq": imported.next_seq(),
                    "stage": "generate",
                    "body": {"document": document, "amendments": []},
                },
                writer="validate-envelope",
            )
            values = (
                _effective_stage_artifact(imported, "prune", "survivors", "survivors"),
                _effective_stage_artifact(
                    imported, "shape", "comparison-surface", "surface"
                ),
                _effective_stage_artifact(imported, "recommend", "close", "close"),
                _effective_records(imported),
                _effective_terminal_claim(imported),
            )
            if any(value is not _MISSING for value in values):
                raise fail(
                    "fixture", "upstream failure exposed stale imported artifacts"
                )

        _expect(
            "upstream live failure suppresses all imported downstream artifacts",
            "pass",
            upstream_failed_rerun_suppresses_downstream_imports,
            results,
        )

        setup_failure_authority: dict[str, Store] = {}

        def failed_setup_decomposition_leaves_echo_only():
            root = sandbox / "failed-setup-decomposition"
            setup = _fixture_setup_document(contract, transition_seeds=False)
            real_write = Store.write

            def reject_decomposition(self, item: dict, *, writer: str):
                if item["kind"] == "decomposition":
                    raise fail("store write", "injected decomposition rejection")
                return real_write(self, item, writer=writer)

            Store.write = reject_decomposition
            try:
                try:
                    _initialize_setup_store(
                        root,
                        "failed-setup-run",
                        setup,
                        contract,
                        readset,
                    )
                except ValidationFailure:
                    pass
                else:
                    raise fail(
                        "fixture", "injected decomposition rejection did not fire"
                    )
            finally:
                Store.write = real_write
            failed_store = Store(root, contract, readset)
            kinds = [item["kind"] for item in failed_store.items()]
            if kinds != ["echo"]:
                raise fail(
                    "fixture",
                    "failed setup decomposition left run-state beyond the echo",
                    kinds,
                )
            try:
                failed_store.write(
                    {
                        "schema": RUNSTATE_SCHEMA,
                        "kind": "pins",
                        "run": "failed-setup-run",
                        "seq": failed_store.next_seq(),
                        "body": _fixture_pins_body(contract),
                    },
                    writer="write-item",
                )
            except StoreReadLoss:
                pass
            else:
                raise fail(
                    "fixture",
                    "pins write remained possible after decomposition rejection",
                )
            setup_failure_authority["store"] = failed_store

        _expect(
            "failed setup decomposition leaves only echo and makes pins impossible",
            "pass",
            failed_setup_decomposition_leaves_echo_only,
            results,
        )

        def setup_failure_capsule_excludes_post_failure_state():
            failed_store = setup_failure_authority["store"]
            capsule = _fixture_setup_failure_capsule(failed_store, contract)
            validate_capsule_document(capsule, contract)
            validate_capsule_against_store(
                capsule,
                failed_store,
                contract,
                allow_unrecorded_write_failure=True,
            )
            marker = "post-failure-pin-marker"
            if marker in dump_yaml(capsule):
                raise fail(
                    "fixture", "clean setup-failure capsule retained post-failure state"
                )
            imported = import_capsule_into_store(
                capsule,
                sandbox / "setup-failure-capsule-import",
                "setup-failure-capsule-import-run",
                contract,
                readset,
                current_pins=_fixture_pins_body(contract),
            )
            generate_brief = render_brief("generate", imported, contract, readset, None)
            if "## packet: seeds" not in generate_brief:
                raise fail(
                    "fixture",
                    "echo-only setup failure capsule did not resume at Generate",
                )

            tainted = copy.deepcopy(capsule)
            tainted["effective-contract"]["evidence-identity"] = {
                "named": [{"path": marker, "id": "9" * 64, "bytes": 1}],
                "in-packet": [],
            }
            tainted["effective-contract"]["method-identity"] = _fixture_method_pins(
                contract
            )
            tainted["proof-boundary"]["constituent-pins"] = _fixture_pins_body(
                contract
            )["constituents"]
            tainted["proof-boundary"]["method-identity"] = _fixture_method_pins(
                contract
            )
            validate_capsule_document(tainted, contract)
            try:
                validate_capsule_against_store(
                    tainted,
                    failed_store,
                    contract,
                    allow_unrecorded_write_failure=True,
                )
            except ValidationFailure:
                return
            raise fail(
                "fixture",
                "store comparison accepted pin-derived state written after setup failure",
            )

        _expect(
            "setup failure capsule contains no state after the triggering failure",
            "pass",
            setup_failure_capsule_excludes_post_failure_state,
            results,
        )

        def acceptance_atomicity():
            atomic_store = _fixture_store(contract, readset, sandbox / "atomic-run")
            survivors = [
                option_a,
                {"wording": "Option D — revived idea", "provenance": "revived"},
                {"wording": "Option E — accepted idea", "provenance": "accepted"},
            ]
            generate_document = {
                "schema": ENVELOPE_SCHEMA,
                "stage": "generate",
                "status": "completed",
                "artifacts": {
                    "field": copy.deepcopy(survivors),
                    "fixed-points-line": "Untouched fixed points: fixture",
                },
                "retrievals": "none",
                "encounters": "none",
                "pins": "none",
                "model": "unknown",
            }
            _fixture_record_brief(atomic_store, "generate", contract, readset)
            atomic_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "fixture-run",
                    "seq": atomic_store.next_seq(),
                    "stage": "generate",
                    "body": {"document": generate_document, "amendments": []},
                },
                writer="validate-envelope",
            )
            _fixture_record_brief(atomic_store, "prune", contract, readset)
            item = {
                "schema": RUNSTATE_SCHEMA,
                "kind": "envelope",
                "run": "fixture-run",
                "seq": atomic_store.next_seq(),
                "stage": "prune",
                "body": {
                    "document": prune_envelope(survivors, []),
                    "amendments": [],
                },
            }
            real_replace = os.replace

            def injected_failure(src, dst):
                raise OSError("injected write failure")

            os.replace = injected_failure
            try:
                try:
                    atomic_store.write(item, writer="validate-envelope")
                except OSError:
                    pass
            finally:
                os.replace = real_replace
            if atomic_store.find("envelope", "prune"):
                raise fail(
                    "fixture",
                    "an envelope became visible after a failed acceptance write",
                )
            atomic_store.write(item, writer="validate-envelope")
            if not atomic_store.find("envelope", "prune"):
                raise fail("fixture", "re-accepted envelope did not land")

        _expect(
            "acceptance is atomic under a fault-injected write",
            "pass",
            acceptance_atomicity,
            results,
        )

        def inconsistent_writer_contract():
            data = copy.deepcopy(contract.data)
            data["validation"]["runstate-writers"]["pins"] = ["import-capsule"]
            validate_contract_data(data)

        _expect(
            "contract data rejects generic-writer ownership inconsistency",
            "block",
            inconsistent_writer_contract,
            results,
        )

        def inconsistent_basis_contract():
            data = copy.deepcopy(contract.data)
            data["validation"]["prune-bases"].append(
                data["validation"]["recommend-bases"][0]
            )
            validate_contract_data(data)

        _expect(
            "contract data rejects overlapping stage basis sets",
            "block",
            inconsistent_basis_contract,
            results,
        )

        def generic_writer_cannot_write_reserved_kind():
            reserved_store = _fixture_store(
                contract,
                readset,
                sandbox / "reserved-writer-store",
            )
            reserved_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "proof-inputs",
                    "run": "fixture-run",
                    "seq": reserved_store.next_seq(),
                    "body": copy.deepcopy(_fixture_capsule(contract)["proof-boundary"]),
                },
                writer="write-item",
            )

        _expect(
            "generic write-item cannot write a reserved run-state kind",
            "block",
            generic_writer_cannot_write_reserved_kind,
            results,
        )

        authority: dict[str, object] = {}

        def store_backed_capsule_pass():
            root = sandbox / "capsule-store-authority"
            capsule = _fixture_capsule(contract)
            capsule["terminal"] = "store failed: write"
            capsule["proof-boundary"]["store-path"] = str(Path(os.path.realpath(root)))
            validate_capsule_document(capsule, contract)
            backed_store = import_capsule_into_store(
                capsule,
                root,
                capsule["run"],
                contract,
                readset,
            )
            try:
                render_brief("generate", backed_store, contract, readset, None)
            except Refusal:
                pass
            else:
                raise fail("fixture", "stage rendered under a no-stage restart plan")
            backed_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "proof-inputs",
                    "run": capsule["run"],
                    "seq": backed_store.next_seq(),
                    "body": copy.deepcopy(capsule["proof-boundary"]),
                },
                writer="record-proof-inputs",
            )
            backed_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "terminal-state",
                    "run": capsule["run"],
                    "seq": backed_store.next_seq(),
                    "body": {
                        "terminal": capsule["terminal"],
                        "carrier": "failure-capsule",
                    },
                },
                writer="record-terminal",
            )
            validate_capsule_against_store(capsule, backed_store, contract)
            authority.update(store=backed_store, capsule=capsule)

        _expect(
            "store-backed capsule matches every byte-exact authority",
            "pass",
            store_backed_capsule_pass,
            results,
        )

        def reject_store_mutation(mutator) -> None:
            document = copy.deepcopy(authority["capsule"])
            mutator(document)
            validate_capsule_against_store(
                document,
                authority["store"],
                contract,
            )

        _expect(
            "store-backed capsule rejects close drift",
            "block",
            lambda: reject_store_mutation(
                lambda document: document.__setitem__(
                    "close", "clear call: Option B — drifted close"
                )
            ),
            results,
        )
        _expect(
            "store-backed capsule rejects comparison-surface drift",
            "block",
            lambda: reject_store_mutation(
                lambda document: document.__setitem__(
                    "surface", "drifted comparison surface"
                )
            ),
            results,
        )

        def mutate_record(document: dict) -> None:
            document["records"][0]["reason"] = "drifted record reason"

        _expect(
            "store-backed capsule rejects record drift",
            "block",
            lambda: reject_store_mutation(mutate_record),
            results,
        )

        def mutate_retrievals(document: dict) -> None:
            document["retrievals"] = [
                {
                    "producing-stage": "shape",
                    "source": "fixture source",
                    "retrieved-at": "2026-07-14T12:00:00Z",
                    "fact": "drifted retrieval",
                    "concerns": "candidate-neutral",
                }
            ]

        _expect(
            "store-backed capsule rejects retrieval drift",
            "block",
            lambda: reject_store_mutation(mutate_retrievals),
            results,
        )

        def mutate_leans(document: dict) -> None:
            document["registered-leans"]["agent-first-lean"] = "Option B"

        _expect(
            "store-backed capsule rejects registered-lean drift",
            "block",
            lambda: reject_store_mutation(mutate_leans),
            results,
        )

        def mutate_method_pin(document: dict) -> None:
            pin = [{"path": "references/methods.md", "id": "1" * 64}]
            document["effective-contract"]["method-identity"] = copy.deepcopy(pin)
            document["proof-boundary"]["method-identity"] = pin

        _expect(
            "store-backed capsule rejects pin drift",
            "block",
            lambda: reject_store_mutation(mutate_method_pin),
            results,
        )

        def mutate_decomposition(document: dict) -> None:
            document["setup-decomposition"]["composition-provenance"][
                "invocation-span"
            ] = "drifted invocation span"

        _expect(
            "store-backed capsule rejects decomposition drift",
            "block",
            lambda: reject_store_mutation(mutate_decomposition),
            results,
        )

        _expect(
            "store-backed capsule rejects exclusion-check drift",
            "block",
            lambda: reject_store_mutation(
                lambda document: document.__setitem__(
                    "exclusion-check", "Exclusion check: drifted"
                )
            ),
            results,
        )

        def novel_authority_from_generate(provenance: str, root_name: str) -> None:
            generate_store = _fixture_store(
                contract,
                readset,
                sandbox / root_name,
                transition_seeds=False,
            )
            document = parse_fixture("must-pass/inert-prose-envelope.yaml")
            document["artifacts"]["field"].append(
                {
                    "wording": f"Option X — novel {provenance} claim",
                    "provenance": provenance,
                }
            )
            validate_envelope_shape(document, contract)
            validate_envelope_against_store(document, generate_store, contract)

        _expect(
            "Generate rejects novel option marked accepted",
            "block",
            lambda: novel_authority_from_generate(
                "accepted", "generate-novel-accepted"
            ),
            results,
        )
        _expect(
            "Generate rejects novel option marked user-seed",
            "block",
            lambda: novel_authority_from_generate(
                "user-seed", "generate-novel-user-seed"
            ),
            results,
        )

        def duplicate_retrieval_identity():
            capsule = _fixture_capsule(contract)
            retrieval = {
                "producing-stage": "shape",
                "source": "fixture source",
                "retrieved-at": "2026-07-14T12:00:00Z",
                "fact": "first fixture fact",
                "concerns": "candidate-neutral",
            }
            capsule["retrievals"] = [
                retrieval,
                {**retrieval, "fact": "second fixture fact"},
            ]
            validate_capsule_document(capsule, contract)

        _expect(
            "capsule rejects duplicate retrieval identity",
            "block",
            duplicate_retrieval_identity,
            results,
        )

        def invalid_utf8_is_controlled():
            try:
                safe_parse(b"\xff", **caps, op="invalid UTF-8 fixture")
            except ValidationFailure:
                raise
            except Exception as exc:
                raise AssertionError(
                    f"invalid UTF-8 escaped as {type(exc).__name__}"
                ) from exc

        _expect(
            "invalid UTF-8 is a controlled validation failure",
            "block",
            invalid_utf8_is_controlled,
            results,
        )

        def boolean_runstate_sequence():
            item = pins_item()
            item["seq"] = True
            validate_runstate_item(item, contract)

        _expect(
            "run-state sequence rejects boolean true",
            "block",
            boolean_runstate_sequence,
            results,
        )

        def echo_override(capsule: dict) -> dict:
            contract_map = capsule["effective-contract"]
            return {
                "invocation-wording-initial": contract_map["invocation-wording"][
                    "initial"
                ],
                "directives": list(contract_map["invocation-wording"]["directives"]),
                "directives-collapsed": list(
                    contract_map["invocation-wording"]["directives-collapsed"]
                ),
                "bounds": copy.deepcopy(contract_map["bounds"]),
                "source-capsule-id": "none",
                "fields": {
                    name: copy.deepcopy(contract_map[name])
                    for name in contract.echo_contract_fields
                },
                "setup-source": _setup_source_from_artifacts(
                    capsule["setup-decomposition"]["candidates"],
                    contract_map["soft-prefs"]["value"],
                    contract_map["soft-prefs"]["provenance"],
                    capsule["setup-decomposition"]["composition-provenance"],
                ),
            }

        def changed_frame_restarts_generate():
            capsule = _fixture_capsule(contract)
            override = echo_override(capsule)
            override["fields"]["frame"] = {
                "value": "choose a replacement note-sync approach after a team change",
                "provenance": "user-supplied",
            }
            imported = import_capsule_into_store(
                capsule,
                sandbox / "changed-frame-import",
                "changed-frame-import-run",
                contract,
                readset,
                echo_body=override,
            )
            plan = imported.require("restart-plan")["body"]
            if plan["earliest-stage"] != "generate":
                raise fail("fixture", "frame change did not restart at Generate", plan)
            generate_brief = render_brief("generate", imported, contract, readset, None)
            if override["fields"]["frame"]["value"] not in generate_brief:
                raise fail("fixture", "Generate brief missed the changed frame")
            try:
                render_brief("prune", imported, contract, readset, None)
            except StoreReadLoss:
                pass
            else:
                raise fail(
                    "fixture", "stale Prune field rendered past Generate restart"
                )
            try:
                render_brief("recommend", imported, contract, readset, None)
            except StoreReadLoss:
                return
            raise fail(
                "fixture", "stale Recommend brief rendered past Generate restart"
            )

        _expect(
            "changed frame restarts Generate and blocks stale Recommend",
            "pass",
            changed_frame_restarts_generate,
            results,
        )

        _expect(
            "completed capsule without classified change refuses import",
            "block",
            lambda: import_capsule_into_store(
                _fixture_capsule(contract),
                sandbox / "unclassified-completed-import",
                "unclassified-completed-import-run",
                contract,
                readset,
            ),
            results,
        )

        def constraint_withdrawal_without_change():
            capsule = _fixture_capsule(contract)
            capsule["records"][0]["cut-basis"] = "constraint"
            wording = capsule["records"][0]["option"]
            validate_capsule_document(capsule, contract)
            import_capsule_into_store(
                capsule,
                sandbox / "constraint-withdrawal-no-change",
                "constraint-withdrawal-no-change-run",
                contract,
                readset,
                revive=[wording],
                constraint_withdrawn=[wording],
            )

        _expect(
            "constraint-withdrawn refuses without actual constraint change",
            "block",
            constraint_withdrawal_without_change,
            results,
        )

        def prior_full_field_transition():
            capsule = _fixture_capsule(contract)
            original_boundary = capsule["generation-boundary"]
            override = echo_override(capsule)
            override["fields"]["field-mode"] = {
                "value": "closed-to-widening",
                "provenance": "user-supplied",
            }
            imported = import_capsule_into_store(
                capsule,
                sandbox / "prior-full-field-transition",
                "prior-full-field-transition-run",
                contract,
                readset,
                echo_body=override,
                field_base="prior-full-field",
            )
            state = imported.require("capsule-import")["body"]["capsule"]
            plan = imported.require("restart-plan")["body"]
            if state["field-order-origin"] != "generate-produced":
                raise fail("fixture", "prior full field laundered generated order")
            if state["generation-boundary"] != original_boundary:
                raise fail("fixture", "prior full field lost the Generate boundary")
            converted = [
                option
                for option in state["original-field"]
                if option["wording"]
                in {"Option B — hosted wiki", "Option C — shared git repo"}
            ]
            if len(converted) != 2 or any(
                option["provenance"] != "adopted" or "insertion" in option
                for option in converted
            ):
                raise fail(
                    "fixture",
                    "prior full field did not convert generated options to insertion-free adopted options",
                    converted,
                )
            if plan["earliest-stage"] != "prune":
                raise fail(
                    "fixture", "closed prior full field did not restart at Prune", plan
                )

        _expect(
            "prior-full-field transition preserves origin and restarts Prune",
            "pass",
            prior_full_field_transition,
            results,
        )

        def run_record_proof_inputs_cli(
            data_path: Path,
            store_root: Path,
            body_args: list[str],
        ) -> int:
            parsed = build_parser().parse_args(
                [
                    "record-proof-inputs",
                    "--data",
                    str(data_path),
                    "--store",
                    str(store_root),
                    *body_args,
                ]
            )
            return parsed.func(parsed)

        def proof_inputs_body_forms_write_identical_items():
            shared_root = sandbox / "proof-body-form-store"
            positional_store = _fixture_store(contract, readset, shared_root)
            proof = copy.deepcopy(_fixture_capsule(contract)["proof-boundary"])
            proof["store-path"] = str(positional_store.root)
            proof_path = sandbox / "proof-body-form.yaml"
            proof_path.write_text(dump_yaml(proof))

            run_record_proof_inputs_cli(
                contract.data_path,
                shared_root,
                [str(proof_path)],
            )
            item_name = "003-proof-inputs.yaml"
            positional_bytes = (shared_root / item_name).read_bytes()

            positional_snapshot = sandbox / "proof-body-form-positional"
            shared_root.rename(positional_snapshot)
            _fixture_store(contract, readset, shared_root)
            run_record_proof_inputs_cli(
                contract.data_path,
                shared_root,
                ["--body", str(proof_path)],
            )
            named_bytes = (shared_root / item_name).read_bytes()
            if positional_bytes != named_bytes:
                raise fail(
                    "fixture",
                    "positional and --body proof-input store items differ",
                )

        _expect(
            "positional and --body proof inputs write byte-identical store items",
            "pass",
            proof_inputs_body_forms_write_identical_items,
            results,
        )

        def assert_proof_body_form_refuses_without_store_access(
            label: str,
            body_args: list[str],
        ) -> None:
            untouched_root = sandbox / f"proof-body-{label}-untouched"
            untouched_root.mkdir()
            sentinel = untouched_root / "sentinel.txt"
            sentinel.write_text("unchanged\n")
            before = [
                (path.name, path.read_bytes()) for path in untouched_root.iterdir()
            ]
            try:
                run_record_proof_inputs_cli(
                    sandbox / "must-not-read-contract.yaml",
                    untouched_root,
                    body_args,
                )
            except Refusal as exc:
                if "supply exactly one body path" not in str(exc):
                    raise fail(
                        "fixture",
                        "body-form refusal used the wrong boundary",
                        str(exc),
                    ) from exc
            except (ValidationFailure, StoreReadLoss) as exc:
                raise fail(
                    "fixture",
                    "body-form refusal reached contract or store access",
                    str(exc),
                ) from exc
            else:
                raise fail("fixture", "invalid proof-input body forms were accepted")
            after = [
                (path.name, path.read_bytes()) for path in untouched_root.iterdir()
            ]
            if before != after:
                raise fail(
                    "fixture",
                    "body-form refusal changed the sentinel store",
                    {"before": before, "after": after},
                )

        _expect(
            "record-proof-inputs refuses both body forms before store access",
            "pass",
            lambda: assert_proof_body_form_refuses_without_store_access(
                "both",
                [
                    str(sandbox / "positional-proof.yaml"),
                    "--body",
                    str(sandbox / "named-proof.yaml"),
                ],
            ),
            results,
        )
        _expect(
            "record-proof-inputs refuses neither body form before store access",
            "pass",
            lambda: assert_proof_body_form_refuses_without_store_access(
                "neither",
                [],
            ),
            results,
        )

        def proof_inputs_wrong_store_path():
            proof_store = _fixture_store(
                contract,
                readset,
                sandbox / "proof-path-mismatch",
            )
            proof = copy.deepcopy(_fixture_capsule(contract)["proof-boundary"])
            proof["store-path"] = "/definitely/not/the/live/store"
            proof_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "proof-inputs",
                    "run": "fixture-run",
                    "seq": proof_store.next_seq(),
                    "body": proof,
                },
                writer="record-proof-inputs",
            )

        _expect(
            "direct proof-input write rejects mismatched store path",
            "block",
            proof_inputs_wrong_store_path,
            results,
        )

        def proof_inputs_alias_path_is_canonicalized():
            proof_store = _fixture_store(
                contract,
                readset,
                sandbox / "proof-path-canonical",
            )
            canonical = str(proof_store.root)
            if canonical.startswith("/private/var/"):
                alias = Path("/var") / Path(canonical).relative_to("/private/var")
            else:
                alias = sandbox / "proof-path-alias"
                alias.symlink_to(proof_store.root, target_is_directory=True)
            proof = copy.deepcopy(_fixture_capsule(contract)["proof-boundary"])
            proof["store-path"] = str(alias)
            proof_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "proof-inputs",
                    "run": "fixture-run",
                    "seq": proof_store.next_seq(),
                    "body": proof,
                },
                writer="record-proof-inputs",
            )
            stored_path = proof_store.require("proof-inputs")["body"]["store-path"]
            if stored_path != str(proof_store.root):
                raise fail(
                    "fixture",
                    "proof-input alias was not persisted as the canonical live store root",
                    stored_path,
                )

        _expect(
            "proof-input /var and /private/var aliases persist canonically",
            "pass",
            proof_inputs_alias_path_is_canonicalized,
            results,
        )

        def failed_proof_recording_blocks_terminal_authority():
            proof_store = _fixture_store(
                contract,
                readset,
                sandbox / "proof-failure-terminal-cutoff",
            )
            proof = copy.deepcopy(_fixture_capsule(contract)["proof-boundary"])
            proof["store-path"] = "/definitely/not/the/live/store"
            try:
                proof_store.write(
                    {
                        "schema": RUNSTATE_SCHEMA,
                        "kind": "proof-inputs",
                        "run": "fixture-run",
                        "seq": proof_store.next_seq(),
                        "body": proof,
                    },
                    writer="record-proof-inputs",
                )
            except ValidationFailure:
                pass
            else:
                raise fail("fixture", "invalid proof inputs unexpectedly recorded")
            if proof_store.find("proof-inputs") or proof_store.find("terminal-state"):
                raise fail(
                    "fixture",
                    "failed proof recording left proof or terminal authority",
                )
            try:
                proof_store.write(
                    {
                        "schema": RUNSTATE_SCHEMA,
                        "kind": "terminal-state",
                        "run": "fixture-run",
                        "seq": proof_store.next_seq(),
                        "body": {
                            "terminal": "close rendered",
                            "carrier": "capsule",
                        },
                    },
                    writer="record-terminal",
                )
            except StoreReadLoss:
                pass
            else:
                raise fail(
                    "fixture",
                    "terminal recording remained possible after proof rejection",
                )
            if proof_store.find("proof-inputs") or proof_store.find("terminal-state"):
                raise fail(
                    "fixture",
                    "terminal attempt after proof rejection mutated run-state authority",
                )

        _expect(
            "failed proof recording leaves terminal authority impossible",
            "pass",
            failed_proof_recording_blocks_terminal_authority,
            results,
        )

        def first_helper_failure_forbids_any_second_probe():
            skill_root = Path(os.path.realpath(Path(__file__).parent.parent))
            stage_packets_path = readset.allow(
                skill_root / "references" / "stage-packets.md"
            )
            skill_path = readset.allow(skill_root / "SKILL.md")
            stage_packets = _decode_utf8(
                readset.read_bytes(stage_packets_path),
                "fixture stage-packets guidance",
            )
            skill_text = _decode_utf8(
                readset.read_bytes(skill_path),
                "fixture skill guidance",
            )
            required = (
                "contains exactly one such invocation",
                "do not invoke any later helper command",
                "including a corrected or diagnostic second validation probe",
                "neither may invoke the helper or write run state",
                "a nonzero proof call makes terminal recording forbidden",
                "Run exactly one in each shell or tool call",
                "after the first nonzero result do not invoke any helper command again",
            )
            combined = stage_packets + "\n" + skill_text
            missing = [snippet for snippet in required if snippet not in combined]
            if missing:
                raise fail(
                    "fixture",
                    "fail-fast proof-to-terminal guidance is incomplete",
                    missing,
                )

            for block in re.findall(r"```bash\n(.*?)```", stage_packets, re.DOTALL):
                normalized = block.replace("\\\n", " ")
                mutating = any(
                    token in normalized
                    for token in (
                        " init-setup ",
                        " write-item ",
                        " render-brief ",
                        " validate-envelope ",
                        " record-proof-inputs ",
                        " record-terminal ",
                        " import-capsule ",
                    )
                ) or (" validate-capsule " in normalized and " --accept " in normalized)
                if not mutating:
                    continue
                lines = [line for line in block.splitlines() if line.strip()]
                if not lines or lines[0] != "set -euo pipefail":
                    raise fail(
                        "fixture",
                        "store-mutating guidance block lacks fail-fast shell mode",
                        block,
                    )
                if normalized.count("uv run --script") != 1:
                    raise fail(
                        "fixture",
                        "store-mutating guidance block contains multiple helper calls",
                        block,
                    )
                if (
                    " record-proof-inputs " in normalized
                    and " record-terminal " in normalized
                ):
                    raise fail(
                        "fixture",
                        "proof and terminal recording share one helper-call block",
                        block,
                    )

        _expect(
            "first helper failure forbids any second validator probe",
            "pass",
            first_helper_failure_forbids_any_second_probe,
            results,
        )

        def terminal_state_conflicts_with_claim():
            claim_store = close_less_contest_store("terminal-state-conflict")
            claim_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "terminal-claim",
                    "run": "fixture-run",
                    "seq": claim_store.next_seq(),
                    "body": {
                        "terminal": "one candidate survives the authorized cuts; no comparative recommendation was performed",
                        "claim": "Option A is the sole survivor of the authorized cuts",
                        "survivor": "Option A — file sync over Syncthing",
                    },
                },
                writer="write-item",
            )
            claim_store.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "terminal-state",
                    "run": "fixture-run",
                    "seq": claim_store.next_seq(),
                    "body": {"terminal": "close rendered", "carrier": "capsule"},
                },
                writer="record-terminal",
            )

        _expect(
            "direct terminal-state write rejects stored-claim conflict",
            "block",
            terminal_state_conflicts_with_claim,
            results,
        )

        def capsule_mode_boundary_mismatch():
            capsule = _fixture_capsule(contract)
            capsule["generation-boundary"] = "Generate not run: closed-to-widening"
            capsule["field-order-origin"] = "user-supplied"
            capsule["recommend-authority-packet"]["order-provenance"] = (
                "user-supplied order — may evidence lean"
            )
            validate_capsule_document(capsule, contract)

        _expect(
            "seed-and-widen capsule rejects closed-field boundary laundering",
            "block",
            capsule_mode_boundary_mismatch,
            results,
        )

        def impossible_capsule_insertion():
            capsule = _fixture_capsule(contract)
            capsule["original-field"][1]["insertion"] = "original-field-position"
            validate_capsule_document(capsule, contract)

        _expect(
            "generated capsule option rejects impossible insertion provenance",
            "block",
            impossible_capsule_insertion,
            results,
        )

        def noncanonical_capsule_bounds():
            capsule = _fixture_capsule(contract)
            capsule["effective-contract"]["bounds"]["capsule-bytes"] = 1
            validate_capsule_document(capsule, contract)

        _expect(
            "v1 capsule rejects noncanonical declared bounds",
            "block",
            noncanonical_capsule_bounds,
            results,
        )

        def unavailable_contest_without_eligibility():
            capsule = _fixture_capsule(contract)
            capsule["survivors"] = copy.deepcopy(capsule["original-field"])
            capsule["recommend-authority-packet"]["survivors"] = copy.deepcopy(
                capsule["original-field"]
            )
            capsule["records"] = []
            capsule["exclusion-check"] = "exclusion check unavailable"
            validate_capsule_document(capsule, contract)

        _expect(
            "exclusion-check unavailable refuses when Contest was ineligible",
            "block",
            unavailable_contest_without_eligibility,
            results,
        )

        def envelope_without_recorded_brief():
            no_brief = _fixture_store(
                contract,
                readset,
                sandbox / "envelope-without-brief",
                transition_seeds=False,
            )
            no_brief.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "fixture-run",
                    "seq": no_brief.next_seq(),
                    "stage": "generate",
                    "body": {
                        "document": parse_fixture(
                            "must-pass/inert-prose-envelope.yaml"
                        ),
                        "amendments": [],
                    },
                },
                writer="validate-envelope",
            )

        _expect(
            "envelope acceptance requires its recorded brief render",
            "block",
            envelope_without_recorded_brief,
            results,
        )

        def stage_jump_after_forged_brief():
            jumped = _fixture_store(
                contract,
                readset,
                sandbox / "stage-jump-after-brief",
                transition_seeds=False,
            )
            jumped.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "brief-render",
                    "run": "fixture-run",
                    "seq": jumped.next_seq(),
                    "stage": "shape",
                    "body": {"brief-id": "0" * 64},
                },
                writer="render-brief",
            )
            jumped.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "fixture-run",
                    "seq": jumped.next_seq(),
                    "stage": "shape",
                    "body": {
                        "document": _fixture_failed_envelope(contract, "shape"),
                        "amendments": [],
                    },
                },
                writer="validate-envelope",
            )

        _expect(
            "recorded brief cannot bypass missing stage prerequisites",
            "block",
            stage_jump_after_forged_brief,
            results,
        )

        def envelope_outer_stage_mismatch():
            validate_runstate_item(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": "fixture-run",
                    "seq": 0,
                    "stage": "prune",
                    "body": {
                        "document": parse_fixture(
                            "must-pass/inert-prose-envelope.yaml"
                        ),
                        "amendments": [],
                    },
                },
                contract,
            )

        _expect(
            "run-state envelope outer stage must match its document",
            "block",
            envelope_outer_stage_mismatch,
            results,
        )

        def imported_store_without_restart_plan():
            partial = _fixture_store(
                contract,
                readset,
                sandbox / "import-without-plan",
                transition_seeds=False,
            )
            partial.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "capsule-import",
                    "run": "fixture-run",
                    "seq": partial.next_seq(),
                    "body": {"capsule": _fixture_capsule(contract)},
                },
                writer="import-capsule",
            )
            _restart_frontier_index(partial)

        _expect(
            "imported store without restart plan fails closed",
            "block",
            imported_store_without_restart_plan,
            results,
        )

        def stakes_change_restarts_shape():
            capsule = _fixture_capsule(contract)
            override = echo_override(capsule)
            override["fields"]["stakes"] = {
                "value": "highly reversible pilot",
                "provenance": "user-supplied",
            }
            imported = import_capsule_into_store(
                capsule,
                sandbox / "stakes-change-import",
                "stakes-change-import-run",
                contract,
                readset,
                echo_body=override,
            )
            if imported.require("restart-plan")["body"]["earliest-stage"] != "shape":
                raise fail("fixture", "stakes change did not restart Shape")

        _expect(
            "stakes-only contract change normalizes and restarts Shape",
            "pass",
            stakes_change_restarts_shape,
            results,
        )

        def current_pin_change_restarts_generate():
            capsule = _fixture_capsule(contract)
            current = {
                "constituents": copy.deepcopy(
                    capsule["proof-boundary"]["constituent-pins"]
                ),
                "method": copy.deepcopy(
                    capsule["effective-contract"]["method-identity"]
                ),
                "evidence": [],
                "in-packet": [],
            }
            current["constituents"]["ideate"][0]["id"] = "1" * 64
            imported = import_capsule_into_store(
                capsule,
                sandbox / "current-pin-change",
                "current-pin-change-run",
                contract,
                readset,
                current_pins=current,
            )
            if imported.require("restart-plan")["body"]["earliest-stage"] != "generate":
                raise fail("fixture", "ideate pin change did not restart Generate")

        _expect(
            "freshly re-resolved constituent pin drives restart frontier",
            "pass",
            current_pin_change_restarts_generate,
            results,
        )

        def current_methods_reference_change_restarts_prune():
            capsule = _fixture_capsule(contract)
            current = {
                "constituents": copy.deepcopy(
                    capsule["proof-boundary"]["constituent-pins"]
                ),
                "method": copy.deepcopy(
                    capsule["effective-contract"]["method-identity"]
                ),
                "evidence": [],
                "in-packet": [],
            }
            for pin in current["method"]:
                if pin["path"] == "references/methods.md":
                    pin["id"] = "3" * 64
            imported = import_capsule_into_store(
                capsule,
                sandbox / "current-methods-reference-change",
                "current-methods-reference-change-run",
                contract,
                readset,
                current_pins=current,
            )
            if imported.require("restart-plan")["body"]["earliest-stage"] != "prune":
                raise fail("fixture", "methods.md pin change did not restart Prune")

        _expect(
            "methods reference pin drift restarts Prune",
            "pass",
            current_methods_reference_change_restarts_prune,
            results,
        )

        def current_skill_surface_change_restarts_generate():
            capsule = _fixture_capsule(contract)
            current = {
                "constituents": copy.deepcopy(
                    capsule["proof-boundary"]["constituent-pins"]
                ),
                "method": copy.deepcopy(
                    capsule["effective-contract"]["method-identity"]
                ),
                "evidence": [],
                "in-packet": [],
            }
            for pin in current["method"]:
                if pin["path"] == "SKILL.md":
                    pin["id"] = "5" * 64
            imported = import_capsule_into_store(
                capsule,
                sandbox / "current-skill-surface-change",
                "current-skill-surface-change-run",
                contract,
                readset,
                current_pins=current,
            )
            if imported.require("restart-plan")["body"]["earliest-stage"] != "generate":
                raise fail("fixture", "SKILL.md pin change did not restart Generate")

        _expect(
            "non-method owned-surface pin drift restarts Generate",
            "pass",
            current_skill_surface_change_restarts_generate,
            results,
        )

        def ninth_rerun_compacts_history():
            capsule = _fixture_capsule(contract)
            eight = [f"prior directive {i}" for i in range(1, 9)]
            capsule["effective-contract"]["invocation-wording"]["directives"] = list(
                eight
            )
            validate_capsule_document(copy.deepcopy(capsule), contract)
            override = echo_override(capsule)
            override["fields"]["frame"] = {
                "value": "a changed frame for the ninth run",
                "provenance": "user-supplied",
            }
            override["directives"] = eight + ["change the frame"]
            imported = import_capsule_into_store(
                capsule,
                sandbox / "ninth-rerun-compaction",
                "ninth-rerun-compaction-run",
                contract,
                readset,
                echo_body=override,
                directive_manifest=[
                    {
                        "directive": "change the frame",
                        "actions": ["contract-field: frame"],
                    }
                ],
            )
            echo = imported.require("echo")["body"]
            collapsed_id = sha256_bytes("prior directive 1".encode("utf-8"))
            if (
                len(echo["directives"]) != 8
                or echo["directives"][0] != "prior directive 2"
            ):
                raise fail(
                    "fixture", "ninth re-run did not keep the newest eight verbatim"
                )
            if echo["directives-collapsed"] != [collapsed_id]:
                raise fail(
                    "fixture",
                    "oldest directive text did not collapse to its content identifier",
                )
            if imported.require("restart-plan")["body"]["earliest-stage"] != "generate":
                raise fail(
                    "fixture", "ninth re-run frame change did not restart Generate"
                )
            brief = render_brief("generate", imported, contract, readset, None)
            if collapsed_id in brief or "prior directive 1" in brief:
                raise fail("fixture", "collapsed history leaked into a stage packet")
            stored = imported.require("capsule-import")["body"]["capsule"]
            wording = stored["effective-contract"]["invocation-wording"]
            if wording["directives-collapsed"] != [collapsed_id]:
                raise fail("fixture", "capsule round-trip lost the collapsed history")
            validate_capsule_document(
                copy.deepcopy(stored), contract, restart_state=True
            )

        _expect(
            "ninth re-run compacts history instead of dying at the bound",
            "pass",
            ninth_rerun_compacts_history,
            results,
        )

        def flag_directive_compacts_past_bound():
            capsule = _fixture_capsule(contract)
            eight = [f"prior directive {i}" for i in range(1, 9)]
            capsule["effective-contract"]["invocation-wording"]["directives"] = list(
                eight
            )
            imported = import_capsule_into_store(
                capsule,
                sandbox / "revive-at-eight-compaction",
                "revive-at-eight-compaction-run",
                contract,
                readset,
                revive=["Option C — shared git repo"],
            )
            echo = imported.require("echo")["body"]
            if echo["directives"][-1] != "revive: Option C — shared git repo":
                raise fail("fixture", "revival entry missing from directive history")
            if echo["directives-collapsed"] != [
                sha256_bytes("prior directive 1".encode("utf-8"))
            ]:
                raise fail(
                    "fixture", "flag-derived entry did not compact the oldest text"
                )
            plan = imported.require("restart-plan")["body"]
            if plan["directives"] != [
                {
                    "directive": "revive: Option C — shared git repo",
                    "actions": ["revive: Option C — shared git repo"],
                }
            ]:
                raise fail(
                    "fixture", "synthesized directive binding missing from restart plan"
                )

        _expect(
            "flag-derived directive entry compacts past the bound",
            "pass",
            flag_directive_compacts_past_bound,
            results,
        )

        def missing_method_surface_fails(surface: str):
            capsule = _fixture_capsule(contract)
            for holder in (
                capsule["effective-contract"]["method-identity"],
                capsule["proof-boundary"]["method-identity"],
            ):
                holder[:] = [pin for pin in holder if pin["path"] != surface]
            validate_capsule_document(capsule, contract)

        for surface in contract.method_surfaces:
            _expect(
                f"method identity missing {surface} fails",
                "block",
                (lambda s: lambda: missing_method_surface_fails(s))(surface),
                results,
            )

        def unexpected_method_surface_fails():
            capsule = _fixture_capsule(contract)
            extra = {"path": "references/rogue-surface.md", "id": "6" * 64}
            capsule["effective-contract"]["method-identity"].append(dict(extra))
            capsule["proof-boundary"]["method-identity"].append(dict(extra))
            validate_capsule_document(capsule, contract)

        _expect(
            "method identity rejects a surface outside the canonical inventory",
            "block",
            unexpected_method_surface_fails,
            results,
        )

        def duplicate_method_surface_fails():
            capsule = _fixture_capsule(contract)
            extra = {"path": "elsewhere/SKILL.md", "id": "7" * 64}
            capsule["effective-contract"]["method-identity"].append(dict(extra))
            capsule["proof-boundary"]["method-identity"].append(dict(extra))
            validate_capsule_document(capsule, contract)

        _expect(
            "method identity rejects a duplicate surface pin",
            "block",
            duplicate_method_surface_fails,
            results,
        )

        def mixed_directive_override(capsule: dict) -> dict:
            override = echo_override(capsule)
            override["fields"]["frame"] = {
                "value": "a changed frame",
                "provenance": "user-supplied",
            }
            override["directives"] = list(override["directives"]) + [
                "change the frame",
                "also perform an unclassifiable unrelated action",
            ]
            return override

        def unbound_directive_text_refused():
            capsule = _fixture_capsule(contract)
            import_capsule_into_store(
                capsule,
                sandbox / "unbound-directive-text",
                "unbound-directive-text-run",
                contract,
                readset,
                echo_body=mixed_directive_override(capsule),
                directive_manifest=[
                    {
                        "directive": "change the frame",
                        "actions": ["contract-field: frame"],
                    },
                    {
                        "directive": "also perform an unclassifiable unrelated action",
                        "actions": [],
                    },
                ],
            )

        _expect(
            "unclassifiable directive text refuses before store staging",
            "block",
            unbound_directive_text_refused,
            results,
        )

        def new_texts_without_manifest_refused():
            capsule = _fixture_capsule(contract)
            import_capsule_into_store(
                capsule,
                sandbox / "texts-without-manifest",
                "texts-without-manifest-run",
                contract,
                readset,
                echo_body=mixed_directive_override(capsule),
            )

        _expect(
            "new directive texts without a manifest refuse import",
            "block",
            new_texts_without_manifest_refused,
            results,
        )

        def orphan_applied_action_refused():
            capsule = _fixture_capsule(contract)
            override = echo_override(capsule)
            override["fields"]["frame"] = {
                "value": "a changed frame",
                "provenance": "user-supplied",
            }
            override["fields"]["stakes"] = {
                "value": "highly reversible pilot",
                "provenance": "user-supplied",
            }
            override["directives"] = list(override["directives"]) + ["change the frame"]
            import_capsule_into_store(
                capsule,
                sandbox / "orphan-applied-action",
                "orphan-applied-action-run",
                contract,
                readset,
                echo_body=override,
                directive_manifest=[
                    {
                        "directive": "change the frame",
                        "actions": ["contract-field: frame"],
                    }
                ],
            )

        _expect(
            "applied action bound to no directive text refuses import",
            "block",
            orphan_applied_action_refused,
            results,
        )

        def manifest_claiming_unapplied_action_refused():
            capsule = _fixture_capsule(contract)
            override = echo_override(capsule)
            override["fields"]["frame"] = {
                "value": "a changed frame",
                "provenance": "user-supplied",
            }
            override["directives"] = list(override["directives"]) + ["change the frame"]
            import_capsule_into_store(
                capsule,
                sandbox / "unapplied-action-claim",
                "unapplied-action-claim-run",
                contract,
                readset,
                echo_body=override,
                directive_manifest=[
                    {
                        "directive": "change the frame",
                        "actions": [
                            "contract-field: frame",
                            "revive: Option C — shared git repo",
                        ],
                    }
                ],
            )

        _expect(
            "manifest claiming an unapplied action refuses import",
            "block",
            manifest_claiming_unapplied_action_refused,
            results,
        )

        def total_manifest_binds_text_to_actions():
            capsule = _fixture_capsule(contract)
            override = echo_override(capsule)
            override["fields"]["frame"] = {
                "value": "a changed frame",
                "provenance": "user-supplied",
            }
            directive_text = "change the frame and revive the git option"
            override["directives"] = list(override["directives"]) + [directive_text]
            manifest = [
                {
                    "directive": directive_text,
                    "actions": [
                        "contract-field: frame",
                        "revive: Option C — shared git repo",
                    ],
                }
            ]
            imported = import_capsule_into_store(
                capsule,
                sandbox / "total-manifest",
                "total-manifest-run",
                contract,
                readset,
                revive=["Option C — shared git repo"],
                echo_body=override,
                directive_manifest=manifest,
            )
            echo = imported.require("echo")["body"]
            if echo["directives"][-1] != directive_text:
                raise fail("fixture", "raw directive text missing from history")
            if any(entry.startswith("revive: ") for entry in echo["directives"]):
                raise fail(
                    "fixture",
                    "synthesized entry duplicated a manifest-bound directive",
                )
            plan = imported.require("restart-plan")["body"]
            if plan["directives"] != manifest:
                raise fail("fixture", "restart plan lost the directive manifest")

        _expect(
            "total directive manifest binds text to actions and persists",
            "pass",
            total_manifest_binds_text_to_actions,
            results,
        )

        def completed_relabel_as_free_prose_refused():
            capsule = _fixture_capsule(contract)
            capsule["terminal"] = "one right answer at Generate"
            validate_capsule_document(capsule, contract)

        _expect(
            "free-prose echo-only terminal relabel refuses capsule validation",
            "block",
            completed_relabel_as_free_prose_refused,
            results,
        )

        def prose_outcome_shaping_relabel_refused():
            capsule = _fixture_capsule(contract)
            capsule["terminal"] = "muddy goal — exit naming outcome-shaping"
            validate_capsule_document(capsule, contract)

        _expect(
            "prose muddy-goal terminal relabel refuses capsule validation",
            "block",
            prose_outcome_shaping_relabel_refused,
            results,
        )

        def constituent_exit_at_generate_refused():
            capsule = _fixture_capsule(contract)
            capsule["terminal"] = "constituent exit at generate: one right answer"
            validate_capsule_document(capsule, contract)

        _expect(
            "constituent exit at Generate refuses capsule-bearing state",
            "block",
            constituent_exit_at_generate_refused,
            results,
        )

        def constituent_exit_past_frontier_refused():
            capsule = _fixture_capsule(contract)
            capsule["terminal"] = "constituent exit at shape: comparison collapsed"
            validate_capsule_document(capsule, contract)

        _expect(
            "constituent exit cannot carry artifacts past its stage frontier",
            "block",
            constituent_exit_past_frontier_refused,
            results,
        )

        def constituent_exit_within_frontier_passes():
            capsule = _fixture_capsule(contract)
            terminal = "constituent exit at shape: comparison collapsed"
            capsule["terminal"] = terminal
            for key in (
                "surface",
                "consequences",
                "close",
                "registered-leans",
                "recommend-authority-packet",
                "provisional-seed",
            ):
                capsule[key] = "not produced: constituent exit at Shape"
            capsule["terminal-claim"] = {
                "terminal": terminal,
                "claim": "Shape exited before a comparison surface existed",
                "survivor": "not applicable",
            }
            validate_capsule_document(capsule, contract)

        _expect(
            "constituent exit within its stage frontier validates",
            "pass",
            constituent_exit_within_frontier_passes,
            results,
        )

        def zero_survivor_relabel_with_shape_artifacts_refused():
            capsule = _fixture_capsule(contract)
            capsule["terminal"] = "no candidate survives the confirmed cuts"
            capsule["survivors"] = []
            capsule["records"] = [
                {
                    "option": option["wording"],
                    "status": "active",
                    "delegation": "field narrowing under the echoed budget",
                    "predicate-source": "agent-derived proposition",
                    "cut-basis": "dominance",
                    "epistemic-status": "fact-established at comparable resolution",
                    "reason": "fixture reason",
                    "load-bearing-premise": "fixture premise",
                    "strongest-case": "fixture strongest case, written before the kill",
                    "revive-if": "fixture revival condition",
                }
                for option in capsule["original-field"]
            ]
            capsule["recommend-authority-packet"] = "not produced: zero survivors"
            capsule["close"] = "not produced: zero survivors"
            capsule["registered-leans"] = "not produced: zero survivors"
            capsule["provisional-seed"] = "not produced: zero survivors"
            capsule["terminal-claim"] = {
                "terminal": "no candidate survives the confirmed cuts",
                "claim": "every candidate fell to a confirmed cut",
                "survivor": "not applicable",
            }
            validate_capsule_document(capsule, contract)

        _expect(
            "zero-survivor terminal cannot retain Shape artifacts",
            "block",
            zero_survivor_relabel_with_shape_artifacts_refused,
            results,
        )

        def recommend_exit_requires_exit_close():
            capsule = _fixture_capsule(contract)
            capsule["terminal"] = "options not comparable"
            capsule["close"] = "not produced: constituent exit"
            validate_capsule_document(capsule, contract)

        _expect(
            "Recommend constituent exit requires its exit statement as close",
            "block",
            recommend_exit_requires_exit_close,
            results,
        )

        def record_terminal_refuses_unknown_terminal():
            validate_runstate_item(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "terminal-state",
                    "run": "fixture-run",
                    "seq": 9,
                    "body": {
                        "terminal": "one right answer at Generate",
                        "carrier": "capsule",
                    },
                },
                contract,
            )

        _expect(
            "record-terminal refuses a terminal outside the canonical classes",
            "block",
            record_terminal_refuses_unknown_terminal,
            results,
        )

        def no_comparable_in_packet_restarts_generate():
            capsule = _fixture_capsule(contract)
            marker = {
                "name": "attachment",
                "id": "no comparable identity",
                "bytes": 17,
            }
            capsule["effective-contract"]["evidence-identity"]["in-packet"] = [
                copy.deepcopy(marker)
            ]
            current = {
                "constituents": copy.deepcopy(
                    capsule["proof-boundary"]["constituent-pins"]
                ),
                "method": copy.deepcopy(
                    capsule["effective-contract"]["method-identity"]
                ),
                "evidence": [],
                "in-packet": [marker],
            }
            validate_capsule_document(capsule, contract)
            imported = import_capsule_into_store(
                capsule,
                sandbox / "no-comparable-in-packet",
                "no-comparable-in-packet-run",
                contract,
                readset,
                current_pins=current,
            )
            if imported.require("restart-plan")["body"]["earliest-stage"] != "generate":
                raise fail("fixture", "no-comparable evidence did not restart Generate")

        _expect(
            "no-comparable in-packet identity always restarts Generate",
            "pass",
            no_comparable_in_packet_restarts_generate,
            results,
        )

        def field_mode_transition(base: str, root_name: str) -> None:
            capsule = _fixture_capsule(contract)
            override = echo_override(capsule)
            override["fields"]["field-mode"] = {
                "value": "closed-to-widening",
                "provenance": "user-supplied",
            }
            closed_field = (
                ["Option X — explicit closed candidate"] if base == "new" else []
            )
            imported = import_capsule_into_store(
                capsule,
                sandbox / root_name,
                f"{root_name}-run",
                contract,
                readset,
                echo_body=override,
                field_base=base,
                closed_field=closed_field,
            )
            if imported.require("restart-plan")["body"]["earliest-stage"] != "prune":
                raise fail("fixture", f"{base} did not restart Prune")

        _expect(
            "prior-seeds closed-field transition produces typed restart state",
            "pass",
            lambda: field_mode_transition("prior-seeds", "prior-seeds-transition"),
            results,
        )
        _expect(
            "new closed-field transition produces typed restart state",
            "pass",
            lambda: field_mode_transition("new", "new-field-transition"),
            results,
        )

        def closed_to_seed_transition_restarts_generate():
            capsule = _fixture_capsule(contract)
            capsule["effective-contract"]["field-mode"]["value"] = "closed-to-widening"
            capsule["generation-boundary"] = "Generate not run: closed-to-widening"
            capsule["field-order-origin"] = "user-supplied"
            for key in ("original-field", "survivors"):
                for option in capsule[key]:
                    if option["provenance"] == "generated":
                        option["provenance"] = "user-seed"
            for option in capsule["recommend-authority-packet"]["survivors"]:
                if option["provenance"] == "generated":
                    option["provenance"] = "user-seed"
            capsule["recommend-authority-packet"]["order-provenance"] = (
                contract.order_origin_labels["user-supplied"]
            )
            validate_capsule_document(capsule, contract)
            override = echo_override(capsule)
            override["fields"]["field-mode"] = {
                "value": "seed-and-widen",
                "provenance": "user-supplied",
            }
            imported = import_capsule_into_store(
                capsule,
                sandbox / "closed-to-seed-transition",
                "closed-to-seed-transition-run",
                contract,
                readset,
                echo_body=override,
            )
            if imported.require("restart-plan")["body"]["earliest-stage"] != "generate":
                raise fail("fixture", "closed-to-seed transition missed Generate")
            state = imported.require("capsule-import")["body"]["capsule"]
            if not _is_not_produced(state["original-field"]):
                raise fail("fixture", "closed field survived a Generate restart")
            brief = render_brief("generate", imported, contract, readset, None)
            for wording in (
                "Option A — file sync over Syncthing",
                "Option B — hosted wiki",
                "Option C — shared git repo",
            ):
                if wording not in brief:
                    raise fail(
                        "fixture",
                        "closed-to-seed transition dropped a collapse-exempt seed",
                        wording,
                    )

        _expect(
            "closed-to-seed transition invalidates the field and restarts Generate",
            "pass",
            closed_to_seed_transition_restarts_generate,
            results,
        )

        def import_publish_is_atomic():
            capsule = _fixture_capsule(contract)
            target = sandbox / "faulted-import-target"
            real_replace = os.replace
            calls = 0

            def injected_replace(src, dst):
                nonlocal calls
                calls += 1
                if calls == 3:
                    raise OSError("injected import write failure")
                return real_replace(src, dst)

            os.replace = injected_replace
            try:
                try:
                    import_capsule_into_store(
                        capsule,
                        target,
                        "faulted-import-run",
                        contract,
                        readset,
                        invalidate_from=["contest"],
                    )
                except (OSError, ValidationFailure):
                    pass
            finally:
                os.replace = real_replace
            if target.exists():
                raise fail("fixture", "partial import became visible at target path")
            staging_residue = list(target.parent.glob(f".{target.name}.import-*"))
            if staging_residue:
                raise fail(
                    "fixture", "faulted import left staging residue", staging_residue
                )

        _expect(
            "faulted import never publishes a partial target store",
            "pass",
            import_publish_is_atomic,
            results,
        )

        def terminal_state_seals_store():
            sealed = _fixture_store(
                contract, readset, sandbox / "sealed-store", transition_seeds=False
            )
            proof = copy.deepcopy(_fixture_capsule(contract)["proof-boundary"])
            proof["store-path"] = str(sealed.root)
            sealed.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "proof-inputs",
                    "run": "fixture-run",
                    "seq": sealed.next_seq(),
                    "body": proof,
                },
                writer="record-proof-inputs",
            )
            sealed.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "terminal-state",
                    "run": "fixture-run",
                    "seq": sealed.next_seq(),
                    "body": {"terminal": "close rendered", "carrier": "capsule"},
                },
                writer="record-terminal",
            )
            sealed.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "brief-render",
                    "run": "fixture-run",
                    "seq": sealed.next_seq(),
                    "stage": "generate",
                    "body": {"brief-id": "0" * 64},
                },
                writer="render-brief",
            )

        _expect(
            "terminal-state seals every write except capsule acceptance",
            "block",
            terminal_state_seals_store,
            results,
        )

        def failure_after_recommend_resumes_contest():
            capsule = _fixture_capsule(contract)
            capsule["terminal"] = "capability lost mid-run"
            capsule["exclusion-check"] = "not produced: Contest did not run"
            validate_capsule_document(capsule, contract)
            imported = import_capsule_into_store(
                capsule,
                sandbox / "failure-after-recommend",
                "failure-after-recommend-run",
                contract,
                readset,
            )
            if imported.require("restart-plan")["body"]["earliest-stage"] != "contest":
                raise fail("fixture", "post-Recommend failure did not resume Contest")
            render_brief("contest", imported, contract, readset, None)

        _expect(
            "failure after Recommend preserves close and resumes Contest",
            "pass",
            failure_after_recommend_resumes_contest,
            results,
        )

        def contest_failure_capsule_is_store_backed():
            source = _fixture_one_survivor_capsule(contract)
            root = sandbox / "contest-failure-store"
            run = "contest-failure-run"
            imported = import_capsule_into_store(
                source,
                root,
                run,
                contract,
                readset,
                invalidate_from=["contest"],
            )
            _fixture_record_brief(imported, "contest", contract, readset)
            failed = _fixture_failed_envelope(contract, "contest")
            imported.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "envelope",
                    "run": run,
                    "seq": imported.next_seq(),
                    "stage": "contest",
                    "body": {"document": failed, "amendments": []},
                },
                writer="validate-envelope",
            )
            capsule = copy.deepcopy(
                imported.require("capsule-import")["body"]["capsule"]
            )
            capsule["run"] = run
            capsule["exclusion-check"] = "exclusion check unavailable"
            capsule["proof-boundary"]["store-path"] = str(imported.root)
            imported.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "proof-inputs",
                    "run": run,
                    "seq": imported.next_seq(),
                    "body": copy.deepcopy(capsule["proof-boundary"]),
                },
                writer="record-proof-inputs",
            )
            imported.write(
                {
                    "schema": RUNSTATE_SCHEMA,
                    "kind": "terminal-state",
                    "run": run,
                    "seq": imported.next_seq(),
                    "body": {"terminal": capsule["terminal"], "carrier": "capsule"},
                },
                writer="record-terminal",
            )
            validate_capsule_against_store(capsule, imported, contract)

        _expect(
            "Contest failure capsule derives unavailable check from stored diagnostics",
            "pass",
            contest_failure_capsule_is_store_backed,
            results,
        )

    width = max(len(name) for name, *_ in results)
    failures = 0
    for name, expected, outcome, detail, ok in results:
        marker = "PASS" if ok else "FAIL"
        if not ok:
            failures += 1
        print(f"{marker}  {name:<{width}}  expected={expected} got={outcome}")
        if not ok and detail:
            print(f"      {detail}")
    print(f"\n{len(results) - failures}/{len(results)} fixtures behaved as required")
    if failures:
        raise fail("fixtures", f"{failures} fixture(s) misbehaved")
    return EXIT_PASS


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="deliberate-validate.py",
        description="deliberate bundled validator (see module docstring; exit codes: 0 pass, 1 fail, 2 refusal, 4 store read loss)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser(
        "identity", help="content identifiers for paths (SHA-256, path-kind rules)"
    )
    p.add_argument("--data", required=True)
    identity_bound = p.add_mutually_exclusive_group()
    identity_bound.add_argument(
        "--as-evidence",
        action="store_true",
        help="enforce the named-evidence total expanded-byte bound",
    )
    identity_bound.add_argument(
        "--as-in-packet",
        action="store_true",
        help="enforce the exact stored in-packet payload-byte bound",
    )
    p.add_argument("paths", nargs="+")
    p.set_defaults(func=cmd_identity)

    p = sub.add_parser(
        "init-setup",
        help="normalize one setup document and write echo then decomposition",
    )
    p.add_argument("--data", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--run", required=True)
    p.add_argument(
        "--setup",
        required=True,
        help="path to one deliberate-setup/v1 document",
    )
    p.set_defaults(func=cmd_init_setup)

    p = sub.add_parser("write-item", help="validate and append one run-state item")
    p.add_argument("--data", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--kind", required=True)
    p.add_argument("--stage")
    p.add_argument("body", help="path to a YAML file with the item body")
    p.set_defaults(func=cmd_write_item)

    p = sub.add_parser(
        "record-proof-inputs",
        help="record the exact proof-boundary inputs before capsule acceptance",
        description=(
            "Record the exact proof-boundary inputs before capsule acceptance. "
            "Supply exactly one body path as positional BODY or --body PATH."
        ),
    )
    p.add_argument("--data", required=True)
    p.add_argument("--store", required=True)
    p.add_argument(
        "body",
        nargs="?",
        metavar="BODY",
        help="path to the proof-boundary YAML body (positional form)",
    )
    p.add_argument(
        "--body",
        dest="body_option",
        metavar="PATH",
        help="explicit alias for the proof-boundary YAML body path",
    )
    p.set_defaults(func=cmd_record_proof_inputs)

    p = sub.add_parser(
        "record-terminal",
        help="record the terminal and capsule carrier after assembly fixes the terminal",
    )
    p.add_argument("--data", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--terminal", required=True)
    p.add_argument("--carrier", required=True)
    p.set_defaults(func=cmd_record_terminal)

    p = sub.add_parser(
        "validate-runstate-item", help="validate one run-state item file"
    )
    p.add_argument("--data", required=True)
    p.add_argument("item")
    p.set_defaults(func=cmd_validate_runstate)

    p = sub.add_parser(
        "render-brief", help="render a stage brief from the store per the matrix column"
    )
    p.add_argument("--data", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--stage", required=True)
    p.add_argument(
        "--items",
        help="comma-separated packet items (default: the full include column); off-column requests refuse",
    )
    p.set_defaults(func=cmd_render_brief)

    p = sub.add_parser(
        "validate-envelope", help="validate a returned stage envelope against the store"
    )
    p.add_argument("--data", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--stage", help="the dispatched stage; mismatch fails")
    p.add_argument(
        "--accept",
        action="store_true",
        help="on pass, write the envelope and any concerns amendment to the store",
    )
    p.add_argument("envelope")
    p.set_defaults(func=cmd_validate_envelope)

    p = sub.add_parser(
        "validate-capsule", help="validate a capsule document (fences tolerated)"
    )
    p.add_argument("--data", required=True)
    p.add_argument(
        "--store", help="cross-check terminal-time capsule against run state"
    )
    p.add_argument(
        "--accept",
        action="store_true",
        help="after store-backed validation, record the accepted capsule in run state",
    )
    p.add_argument(
        "--file-capsule",
        action="store_true",
        help="apply the explicit file-capsule byte cap instead of the chat capsule cap",
    )
    p.add_argument("capsule")
    p.set_defaults(func=cmd_validate_capsule)

    p = sub.add_parser(
        "import-capsule",
        help="validate a pasted capsule and create the re-run store with typed restart state",
    )
    p.add_argument("--data", required=True)
    p.add_argument("--store", required=True)
    p.add_argument("--run", required=True)
    p.add_argument("--capsule", required=True)
    p.add_argument(
        "--file-capsule",
        action="store_true",
        help="ingest an explicitly requested file capsule under the larger file cap",
    )
    p.add_argument(
        "--revive",
        action="append",
        default=[],
        help="revival directive: the option wording, repeatable; refuses `authority conflict` "
        "on a constraint-basis record unless --constraint-withdrawn names the same wording",
    )
    p.add_argument(
        "--constraint-withdrawn",
        action="append",
        default=[],
        help="asserts the accompanying contract change withdrew or repriced the constraint that cut this wording",
    )
    p.add_argument(
        "--accept-seed",
        action="store_true",
        help="accept the capsule's one canonical provisional seed as a candidate",
    )
    p.add_argument(
        "--echo-body",
        help="optional YAML file overriding the reconstructed echo body (the effective re-run contract)",
    )
    p.add_argument(
        "--pins-body",
        required=True,
        help="YAML file with the freshly re-resolved constituent, method, evidence, and in-packet pins",
    )
    p.add_argument(
        "--invalidate-from",
        action="append",
        default=[],
        metavar="STAGE",
        help="mechanically mapped source/evidence/method drift frontier; repeatable",
    )
    p.add_argument(
        "--field-base",
        help="required when landing on closed-to-widening: prior-seeds, prior-full-field, or new",
    )
    p.add_argument(
        "--closed-field",
        help="YAML list of exact wordings; required only with --field-base new",
    )
    p.add_argument(
        "--directive-manifest",
        help="YAML list of {directive, actions} binding each new raw directive text "
        "to its applied actions; required whenever --echo-body carries new directive "
        "texts, and total both ways — orphan text and orphan actions refuse",
    )
    p.set_defaults(func=cmd_import_capsule)

    p = sub.add_parser(
        "check-renderings",
        help="compare authored renderings in references/ against the canonical data file",
    )
    p.add_argument("--data", required=True)
    p.add_argument(
        "--write",
        action="store_true",
        help="rewrite generated blocks from the data file",
    )
    p.set_defaults(func=cmd_check_renderings)

    p = sub.add_parser("fixtures", help="run the must-block/must-pass fixture set")
    p.add_argument("--data", required=True)
    p.set_defaults(func=cmd_fixtures)

    return parser


def main(argv: list[str]) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except Refusal as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_REFUSE
    except ValidationFailure as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_FAIL
    except StoreReadLoss as exc:
        print(str(exc), file=sys.stderr)
        return EXIT_STORE_READ


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))

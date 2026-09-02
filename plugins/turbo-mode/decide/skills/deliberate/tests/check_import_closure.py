#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.11"
# dependencies = ["pyyaml"]
# ///
"""Gate-2 authoring check: import closure vs `method-surfaces` vs on-disk files.

Derives three independent sets and requires exact pairwise equality
(ADR-0001, Rollout Boundary, gate 2):

1. the root-inclusive transitive first-party import closure of the
   deliberate validator entrypoint, derived by AST parsing alone;
2. the Python subset of the canonical ``validation.method-surfaces``
   inventory;
3. every production ``.py`` file physically present under ``scripts/``.

Alongside the set comparison, the same run enforces the complete ADR-0001
``scripts/`` layout, fail-closed:

- Production Python is the entrypoint plus flat
  ``scripts/_deliberate_<domain>.py`` regular files only; nested files,
  dotted first-party imports, and names that could shadow a stdlib or
  third-party import are rejected.
- A recursive census rejects every unexpected importable artifact anywhere
  under ``scripts/``: symlinks (file or directory, including symlinked
  packages), ``__pycache__`` entries, bytecode and extension-module files
  (any loader suffix other than flat source), zip-format archives
  (``.zip``/``.egg``/``.whl``, loadable through zipimport) and any other file
  whose bytes form a valid zip archive (a prefixed/self-extracting zip whose
  first bytes are not ``PK``), and directories outside the declared data
  allowlist. Files with no loadable suffix and no zip structure are
  import-inert and permitted.
- A statically imported name with any local presence in ``scripts/`` other
  than its inventoried flat ``.py`` source is rejected rather than
  classified as third-party, so an import can never resolve to sourceless
  bytecode, a package directory, or a symlink.
- Dynamic-import and code-execution machinery is rejected by a positional
  identifier ban: a banned name used as an identifier (``ast.Name``) or as
  an imported module or symbol (``import`` / ``from ... import``) fails the
  check. The ban does not scan attribute names or string literals, so
  ordinary ``re.compile`` or the word "eval" in a docstring is not a false
  positive. Reaching import or exec machinery still requires naming a banned
  identifier or a reflection gadget; the gadget/computed-string residual is
  statically undetectable by design and is backstopped by the census
  guarantee that no loadable artifact sits uninventoried under ``scripts/``.
  Native-code loaders (for example ``ctypes`` loading a shared library) load
  outside the Python-module import graph and outside this gate's boundary.

Non-executing by design: importing the entrypoint or any production module
would execute code before the comparison and cross the authentication
boundary this check guards. Only ``ast.parse`` touches production sources.

Test tooling, deliberately outside `method-surfaces` (ADR-0001 consequence:
test-only harnesses never become authenticated production inputs).

Usage: ``uv run --script check_import_closure.py [skill-root]``; the root
defaults to this file's parent skill directory. Exit 0 on exact agreement,
exit 1 with the failure otherwise.
"""

from __future__ import annotations

import ast
import importlib.machinery
import re
import sys
import zipfile
from pathlib import Path

import yaml

class BoundaryPolicy:
    """Census and ban values from the target's pinned contract-data.yaml.

    The static forbidden-suffix family from the contract is unioned with the
    running interpreter's ``importlib.machinery.all_suffixes()`` — a
    test-side-only extension (production code may not name importlib), so a
    census run on macOS still rejects artifacts another platform loads.
    """

    def __init__(self, raw: object, source: Path) -> None:
        if not isinstance(raw, dict):
            raise SystemExit(
                "import-closure check failed: import-boundary section missing "
                f"or not a mapping in {source}. Got: {raw!r:.100}"
            )
        required = {
            "entrypoint",
            "module-name-pattern",
            "allowed-data-dirs",
            "forbidden-loader-suffixes",
            "archive-suffixes",
            "banned-identifiers",
        }
        if set(raw) != required:
            raise SystemExit(
                "import-closure check failed: import-boundary keys must be "
                f"exactly {sorted(required)} in {source}. Got: {sorted(raw)}"
            )
        for key in ("entrypoint", "module-name-pattern"):
            if not isinstance(raw[key], str) or not raw[key].strip():
                raise SystemExit(
                    f"import-closure check failed: import-boundary {key} must "
                    f"be a non-empty string in {source}. Got: {raw[key]!r:.100}"
                )
        for key in (
            "allowed-data-dirs",
            "forbidden-loader-suffixes",
            "archive-suffixes",
            "banned-identifiers",
        ):
            value = raw[key]
            if (
                not isinstance(value, list)
                or not value
                or not all(isinstance(item, str) and item.strip() for item in value)
            ):
                # A scalar string here would fail open, not closed: frozenset()
                # over a string yields single characters, silently disabling the
                # ban/allowlist it renders (2026-07-16 v6 implementation review).
                raise SystemExit(
                    f"import-closure check failed: import-boundary {key} must "
                    f"be a non-empty list of non-empty strings in {source}. "
                    f"Got: {value!r:.100}"
                )
        self.entrypoint_name: str = raw["entrypoint"]
        try:
            self.module_name = re.compile(raw["module-name-pattern"])
        except re.error as error:
            raise SystemExit(
                "import-closure check failed: import-boundary "
                f"module-name-pattern is not a valid regular expression in "
                f"{source}. Got: {raw['module-name-pattern']!r:.100} ({error})"
            ) from error
        self.allowed_data_dirs = frozenset(raw["allowed-data-dirs"])
        self.banned_identifiers = frozenset(raw["banned-identifiers"])
        static = frozenset(s.lower() for s in raw["forbidden-loader-suffixes"])
        loader_suffixes = frozenset(importlib.machinery.all_suffixes()) | static
        self.artifact_suffixes = tuple(
            sorted(s.lower() for s in loader_suffixes if s != ".py")
        )
        archive_suffixes = tuple(s.lower() for s in raw["archive-suffixes"])
        self.census_forbidden_suffixes = tuple(
            sorted(set(self.artifact_suffixes) | set(archive_suffixes))
        )


def _reject_if_banned(
    name: str, node: ast.AST, source_path: Path, policy: BoundaryPolicy
) -> None:
    """Fail when any dotted segment of ``name`` is banned import/exec machinery."""
    for segment in name.split("."):
        if segment in policy.banned_identifiers:
            line = getattr(node, "lineno", "?")
            raise SystemExit(
                "import-closure check failed: dynamic import machinery is "
                "forbidden in production sources (ADR-0001), because the "
                f"static closure must be authoritative. Got: {segment!r} "
                f"(line {line}) in {source_path}"
            )


def reject_banned_identifiers(
    tree: ast.AST, source_path: Path, policy: BoundaryPolicy
) -> None:
    """Fail on named dynamic-import or code-execution machinery.

    The ban is positional, not textual: it fires on a banned name used as an
    identifier (``ast.Name``, any context) or as an imported module or symbol
    (``import`` / ``from ... import``). It deliberately does not scan attribute
    names or string literals, so ordinary ``re.compile`` or the word "eval" in
    a docstring is not a false positive. Reaching import or exec machinery
    still requires naming a banned identifier — ``__import__``, ``builtins``,
    ``__builtins__``, ``importlib``, ``zipimport``, ``runpy``, ``exec``,
    ``eval``, ``compile`` — or a reflection gadget; the gadget/computed-string
    residual is statically undetectable by design and is backstopped by the
    census guarantee that no loadable artifact sits uninventoried under
    ``scripts/``.
    """
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            if node.id in policy.banned_identifiers:
                raise SystemExit(
                    "import-closure check failed: dynamic import machinery is "
                    "forbidden in production sources (ADR-0001), because the "
                    f"static closure must be authoritative. Got: {node.id!r} "
                    f"(line {node.lineno}) in {source_path}"
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                _reject_if_banned(alias.name, node, source_path, policy)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                _reject_if_banned(node.module, node, source_path, policy)
            for alias in node.names:
                _reject_if_banned(alias.name, node, source_path, policy)


def classify_first_party(
    scripts_dir: Path, top: str, source_path: Path, policy: BoundaryPolicy
) -> bool:
    """True when ``top`` is a flat first-party module; fail on other local forms.

    Script-directory resolution tries every loader form, not just
    ``<top>.py`` — a sourceless ``.pyc``, an extension module, a package
    directory, or a symlink would each execute code the static closure never
    saw. Any such presence is rejected rather than classified.
    """
    flat = scripts_dir / f"{top}.py"
    other_forms = [scripts_dir / top] + [
        scripts_dir / f"{top}{suffix}" for suffix in policy.artifact_suffixes
    ]
    present = [p for p in other_forms if p.is_symlink() or p.exists()]
    if present:
        raise SystemExit(
            "import-closure check failed: a first-party import must resolve "
            "to a flat production source file, never bytecode, a package, or "
            f"a symlink (ADR-0001). Got: {top!r} in {source_path} also "
            f"resolvable to {[str(p) for p in present]}"
        )
    if flat.is_symlink():
        raise SystemExit(
            "import-closure check failed: a production module must be a "
            f"regular file, not a symlink (ADR-0001). Got: {flat}"
        )
    return flat.is_file()


def first_party_import_names(
    source_path: Path, scripts_dir: Path, policy: BoundaryPolicy
) -> set[str]:
    """Return every first-party module name imported anywhere in the file.

    Walks the full AST so conditional and function-scoped imports count:
    any import statement can execute, so any import is closure-relevant.
    Rejects relative imports, dotted first-party imports, dynamic-import
    machinery, and imports resolvable to non-flat-source local artifacts —
    each would let executed code escape the static closure.
    """
    tree = ast.parse(source_path.read_text(encoding="utf-8"))
    reject_banned_identifiers(tree, source_path, policy)
    dotted_names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            dotted_names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                raise SystemExit(
                    "import-closure check failed: relative import is "
                    "unsupported in the script-directory layout. Got: "
                    f"level={node.level} in {source_path}"
                )
            if node.module:
                dotted_names.append(node.module)
    names: set[str] = set()
    for dotted in dotted_names:
        top = dotted.split(".")[0]
        if classify_first_party(scripts_dir, top, source_path, policy):
            if "." in dotted:
                raise SystemExit(
                    "import-closure check failed: dotted import of a "
                    "first-party module is unsupported — production modules "
                    f"are flat files (ADR-0001). Got: {dotted!r} in "
                    f"{source_path}"
                )
            names.add(top)
    return names


def import_closure(entrypoint: Path, policy: BoundaryPolicy) -> set[Path]:
    """Root-inclusive transitive first-party import closure, source-derived."""
    scripts_dir = entrypoint.parent
    closure: set[Path] = set()
    pending = [entrypoint.resolve()]
    while pending:
        current = pending.pop()
        if current in closure:
            continue
        closure.add(current)
        for name in sorted(first_party_import_names(current, scripts_dir, policy)):
            resolved = (scripts_dir / f"{name}.py").resolve()
            if resolved not in closure:
                pending.append(resolved)
    return closure


def _is_zip_archive(path: Path) -> bool:
    """True when the file is a valid zip archive (importable through zipimport).

    Zip archives import as code through zipimport regardless of filename, so a
    disguised-suffix archive (``payload.dat``) added to ``sys.path`` would load
    without naming any banned identifier. Detection is structural, not a
    first-bytes magic check: ``zipfile.is_zipfile`` locates the end-of-central-
    directory record the way zipimport does, so a zip carrying an arbitrary
    prefix (a shell or self-extracting stub, whose first bytes are not ``PK``)
    is still caught — the case a four-byte magic sniff misses. That keeps the
    census guarantee — no loadable Python artifact sits uninventoried under
    ``scripts/`` — actually holding, which is what lets the identifier ban stay
    narrow (attribute names and string literals unscanned). A file that cannot
    be opened refuses rather than passing: because ``is_zipfile`` swallows
    ``OSError`` into ``False``, this check opens the file itself and refuses on
    an open failure — unverifiable content is unsafe, the same posture the
    runtime pass-2 check holds, so the two consumers cannot drift on the
    unreadable edge either. A read-time ``OSError`` raised inside
    ``is_zipfile`` after a successful open still collapses to ``False``; that
    residual sliver is accepted and shared by both consumers.
    """
    try:
        with path.open("rb") as handle:
            return zipfile.is_zipfile(handle)
    except OSError as error:
        raise SystemExit(
            "import-closure check failed: file under scripts/ could not be "
            f"read for the structural archive check. Got: {path} ({error})"
        ) from error


def census_scripts_layout(scripts_dir: Path, policy: BoundaryPolicy) -> set[Path]:
    """Fail-closed census of everything under scripts/; returns production ``.py`` files.

    Rejects every unexpected importable artifact — symlinks, ``__pycache__``,
    bytecode and extension modules, zip-format archives (by suffix and by
    zip structure, so a prefixed/self-extracting zip is caught too),
    directories outside the declared data allowlist, nested or non-conforming
    ``.py`` — whether or not anything imports it. Files with no loadable suffix
    and no zip structure are import-inert and pass.
    """
    if scripts_dir.is_symlink():
        raise SystemExit(
            "import-closure check failed: scripts/ itself must be a real "
            f"directory, not a symlink (ADR-0001). Got: {scripts_dir}"
        )
    files: set[Path] = set()
    for path in sorted(scripts_dir.rglob("*")):
        if path.is_symlink():
            raise SystemExit(
                "import-closure check failed: symlinks are forbidden anywhere "
                "under scripts/ (ADR-0001) — a symlinked module or package "
                f"executes code outside the authenticated tree. Got: {path}"
            )
        if path.name == "__pycache__":
            raise SystemExit(
                "import-closure check failed: __pycache__ is forbidden under "
                "scripts/ (ADR-0001) — cached bytecode executes in place of "
                f"hashed source. Got: {path}"
            )
        if path.is_dir():
            top = path.relative_to(scripts_dir).parts[0]
            if top not in policy.allowed_data_dirs:
                raise SystemExit(
                    "import-closure check failed: directories under scripts/ "
                    "are forbidden outside the declared data allowlist "
                    f"{sorted(policy.allowed_data_dirs)} (ADR-0001) — a directory is "
                    f"an importable package. Got: {path}"
                )
            continue
        if not path.is_file():
            raise SystemExit(
                "import-closure check failed: unsupported filesystem object "
                f"under scripts/. Got: {path}"
            )
        lower_name = path.name.lower()
        if lower_name.endswith(".py"):
            if path.parent != scripts_dir:
                raise SystemExit(
                    "import-closure check failed: production Python must be flat "
                    "in scripts/ — packages and nested files are forbidden "
                    f"(ADR-0001). Got: {path}"
                )
            if path.name != policy.entrypoint_name and not policy.module_name.match(
                path.name
            ):
                raise SystemExit(
                    "import-closure check failed: production module name must "
                    "match _deliberate_<domain>.py (ADR-0001 naming rule). Got: "
                    f"{path}"
                )
            files.add(path.resolve())
            continue
        if any(
            lower_name.endswith(suffix) for suffix in policy.census_forbidden_suffixes
        ):
            raise SystemExit(
                "import-closure check failed: importable non-source artifact "
                "is forbidden under scripts/ (ADR-0001) — bytecode, extension "
                "modules, and zip-format archives execute or import without "
                f"matching any hashed source. Got: {path}"
            )
        if _is_zip_archive(path):
            raise SystemExit(
                "import-closure check failed: file is a valid zip archive "
                "despite an inert suffix (ADR-0001) — a disguised or prefixed "
                "archive on sys.path imports as code through zipimport without "
                f"naming any banned identifier. Got: {path}"
            )
    return files


def inventory_python_surfaces(loaded: object, contract_data: Path) -> set[str]:
    """Python entries of validation.method-surfaces, as skill-relative paths."""
    try:
        surfaces = loaded["validation"]["method-surfaces"]
    except (TypeError, KeyError) as error:
        raise SystemExit(
            "import-closure check failed: validation.method-surfaces absent "
            f"from {contract_data}. Got: {error!r}"
        ) from error
    if not isinstance(surfaces, list) or not surfaces:
        raise SystemExit(
            "import-closure check failed: validation.method-surfaces must be "
            f"a non-empty list. Got: {surfaces!r:.100}"
        )
    return {str(surface) for surface in surfaces if str(surface).endswith(".py")}


def check(skill_root: Path) -> str:
    """Require closure == inventory == on-disk; return the pass message or exit 1."""
    root = skill_root.resolve()
    scripts_dir = root / "scripts"
    contract_data = root / "references" / "contract-data.yaml"
    if not contract_data.is_file():
        raise SystemExit(
            f"import-closure check failed: required file missing. Got: {contract_data}"
        )
    loaded = yaml.safe_load(contract_data.read_text(encoding="utf-8"))
    if not isinstance(loaded, dict):
        raise SystemExit(
            f"import-closure check failed: contract data is not a mapping. Got: {contract_data}"
        )
    policy = BoundaryPolicy(loaded.get("import-boundary"), contract_data)
    entrypoint = scripts_dir / policy.entrypoint_name
    if not entrypoint.is_file():
        raise SystemExit(
            f"import-closure check failed: required file missing. Got: {entrypoint}"
        )
    on_disk = {
        path.relative_to(root).as_posix()
        for path in census_scripts_layout(scripts_dir, policy)
    }
    closure = {
        path.relative_to(root).as_posix()
        for path in import_closure(entrypoint, policy)
    }
    inventory = inventory_python_surfaces(loaded, contract_data)
    if closure != inventory:
        missing = sorted(closure - inventory)
        unlisted = sorted(inventory - closure)
        raise SystemExit(
            "import-closure check failed: source closure and method-surfaces "
            f"Python subset differ. Imported but not inventoried: {missing}; "
            f"inventoried but never imported: {unlisted}"
        )
    if on_disk != inventory:
        present = sorted(on_disk - inventory)
        absent = sorted(inventory - on_disk)
        raise SystemExit(
            "import-closure check failed: on-disk production Python and "
            f"method-surfaces Python subset differ. On disk but not "
            f"inventoried: {present}; inventoried but absent from scripts/: "
            f"{absent}"
        )
    return (
        "import closure, on-disk production files, and method-surfaces "
        f"agree: {len(closure)} Python surface(s)"
    )


if __name__ == "__main__":
    given_root = (
        Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).resolve().parents[1]
    )
    print(check(given_root))

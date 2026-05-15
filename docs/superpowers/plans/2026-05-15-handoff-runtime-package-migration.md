# Handoff Runtime Package Migration Implementation Plan

> **For agentic workers:** Steps use checkbox (`- [ ]`) syntax for tracking. For parallel-capable implementers, superpowers:subagent-driven-development or superpowers:executing-plans may help coordinate multi-task work, but neither is required — any methodical task-by-task execution is valid.

**Goal:** Move Handoff implementation imports out of the ambiguous top-level `scripts.*` namespace into a unique runtime package while preserving existing `scripts/*.py` direct-entrypoint paths.

**Architecture:** Create `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/` as the implementation package. Keep `plugins/turbo-mode/handoff/1.6.0/scripts/*.py` as compatibility wrappers for documented direct script execution and existing subprocess callers. Runtime modules must import only `turbo_mode_handoff_runtime.*`, never `scripts.*`.

**Tech Stack:** Python 3.11+, `uv run pytest`, standard library plus `pyyaml>=6.0` (declared in `pyproject.toml`; `ticket_parsing.py` imports `yaml`), existing Handoff plugin layout under `plugins/turbo-mode/handoff/1.6.0`.

---

## Design Decisions

- Use `turbo_mode_handoff_runtime`, not `handoff_runtime`, so the package name is plugin-scoped and cannot reasonably collide with another plugin's runtime package. Multi-version coexistence of the same plugin in one interpreter is not a supported deployment shape, so no version suffix is required; if that ever changes, the rename is mechanical.
- Keep every existing `scripts/<name>.py` file path that appears in docs, tests, shell snippets, and skill docs. Those files become wrappers.
- **Wrapper import contract scope:** The wrappers guarantee three surfaces: (1) direct file-path execution (`python "$PLUGIN_ROOT/scripts/<name>.py"`), (2) `from scripts.<mod> import <name>` when the plugin's `scripts/` directory is the one on `sys.path` (e.g., pytest with rootdir at `<PLUGIN_ROOT>`, subprocess with `cwd=<PLUGIN_ROOT>`, or installed copy with installed path on `sys.path`), and (3) the current cached/shadowed-`scripts` repair contract for long-lived interpreters where a foreign `scripts` package is already in `sys.modules` but the plugin `scripts/` directory is a valid package path. The wrappers do **not** guarantee `import scripts.<mod>` from the repo root, because the repo's top-level `scripts/__init__.py` shadows the plugin's `scripts/` directory. Tests that exercise `from scripts.*` imports must run in a context where the plugin's `scripts/` takes precedence or where the wrapper bootstrap helper has repaired the package path.
- Preserve a minimal `scripts/_bootstrap.py` wrapper helper. It is no longer an implementation-import bridge, but it remains load-bearing for cached/shadowed `scripts` package repair. Do not delete it unless this compatibility surface is explicitly declared broken and the tests/docs are changed in the same commit.
- **Wrapper exports are explicit, not denylist-based.** Every runtime module must define a top-level literal `__all__ = (...)` tuple of the names intentionally re-exported by its matching wrapper. The wrapper templates must export only those names. Do not use `globals().update(_RUNTIME_MODULE.__dict__)` or a skip-list filter: that makes imported helper modules, accidental globals, and wrapper-local names part of the compatibility surface.
- Do not update installed-cache copies in this plan. This is a source PR. Installed-cache refresh remains a separate release/publication step with its own owner, gate, and evidence artifact; Task 6 records that follow-up explicitly.
- Do not rename user-facing commands, skills, or documented `python "$PLUGIN_ROOT/scripts/<name>.py"` invocations.
- Update the refresh classifier to model `turbo_mode_handoff_runtime/*.py` as a first-class Handoff source surface. Without this, the classifier would silently skip evaluation of runtime module changes during refresh cycles.
- Update the refresh classifier's exact Handoff Gate 5 hash contracts only after the wrapper conversion has produced final wrapper text. Live `HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS` pins source hashes for several current `scripts/*.py` implementation files, and the refresh tests assert those hashes match live files. After wrapper conversion, those contracts must either move to the runtime implementation files, remain on wrappers with new wrapper hashes, or be explicitly retired with a named policy reason. Do not finalize the exact hash map in Task 3b before Task 4 creates the wrapper content it may need to hash.
- **First-refresh ADDED-file handling:** After the source merge, the first installed-cache refresh will see `turbo_mode_handoff_runtime/*.py` files as `DiffKind.ADDED` (present in source, absent from cache). This plan intentionally treats those first-refresh ADDED runtime files as `COVERAGE_GAP`, not merely `GUARDED`, because they represent a new installed-cache import surface rather than a routine implementation change. Task 3b must add an explicit ADDED-runtime classifier rule and tests. Once the runtime package exists in the installed cache, subsequent `CHANGED` runtime files classify as `GUARDED` via `GUARDED_ONLY_PATTERNS`.
- **Runtime modules are import-only.** Do not add `turbo_mode_handoff_runtime/*.py` to `is_executable_or_command_bearing_path`. Runtime modules must have no shebangs and no `if __name__ == "__main__":` blocks — only `scripts/*.py` wrappers are executable entrypoints. Because the source files copied in Task 2 currently include CLI blocks, Task 2 must strip those blocks from the runtime copies and add an AST guard proving they stay absent. The `GUARDED_ONLY_PATTERNS` entry is sufficient for CHANGED runtime files after publication; the explicit ADDED-runtime coverage-gap rule owns first-refresh publication safety.
- Preserve wrapper-import, runtime-import, and direct-file subprocess probes in `installed_host_harness.py`. The installed-copy scenario is the only test that creates a real installed copy and probes import resolution from subprocesses. The wrapper import probe must run before any runtime-package import in a fresh subprocess, and direct-file execution must be probed in a separate subprocess; otherwise a prior runtime import can create false proof for wrapper bootstrapping.
- All commits must land on a feature branch with a green test suite. No commit may knowingly break inventory, wrapper, or classifier tests.
- Out of scope: the ticket plugin (`plugins/turbo-mode/ticket/1.4.0/scripts/`) keeps its current `scripts.ticket_*` layout. The same namespace-ambiguity concern applies there, but this migration is intentionally scoped to handoff. Any ticket migration is a separate plan.

### Lifecycle Design

The dual-layer shape is permanent for Handoff 1.x, not a transitional migration scaffold.

- `turbo_mode_handoff_runtime/` is the long-term implementation namespace for Handoff 1.x.
- `scripts/*.py` wrappers are the long-term compatibility layer for Handoff 1.x because skill docs, subprocess tests, and user-facing direct-file invocations already depend on those file paths.
- Removing or renaming wrappers is out of scope for this migration. It would be a Handoff 2.x breaking-change plan with docs, skill references, subprocess callers, release notes, and refresh classifier contracts updated in the same change.
- Future Handoff 1.x work must add implementation under `turbo_mode_handoff_runtime/` first, then add or update the matching wrapper and `__all__` contract. Do not reintroduce implementation ownership under `scripts/`.

### Post-Merge Blocking Window

After the source PR merges, the first installed-cache publication is expected to be blocked by design until an operator runs the publication lane. The expected read-only planner status for the new runtime package is `coverage-gap-blocked`, not `blocked-preflight`, because `turbo_mode_handoff_runtime/*.py` files are `ADDED` in source/cache diff and represent a new installed-cache import surface.

Ownership and SLA:

- Owner: the migration PR owner remains responsible until the publication follow-up artifact names a replacement owner.
- SLA: the publication follow-up artifact must name an owner and a target execution window no later than the next business day after source merge. If no owner/window is named, the PR is not ready to merge.
- The source PR body must state that installed-cache publication is pending unless the follow-up has already been executed and evidenced.

Bypass lanes:

- `blocked-preflight` is not bypassable. Generated residue, malformed config, abandoned run state, or missing roots must be fixed before publication.
- `coverage-gap-blocked` caused only by first-refresh `added-handoff-runtime-package-path` is the expected manual-publication lane. It does not authorize ordinary `--refresh` or `--guarded-refresh`; it authorizes the follow-up artifact's explicit publication path, such as app-server `plugin/install` or the current repo-approved local-source refresh path, inside the named maintenance window.
- `coverage-gap-blocked` for any reason other than first-refresh runtime-package ADDED files is not bypassable. Repair the classifier coverage or plan before publication.
- After publication, rerun the read-only planner and runtime inventory proof. The blocking window closes only when the installed cache contains `turbo_mode_handoff_runtime/*.py` and app-server/runtime evidence proves the wrapper and runtime surfaces resolve from the installed copy.

### Runtime Import Path Contract

There are three distinct import surfaces with three different contracts. Every verification command must state which one it is exercising.

| Surface | How it must be invoked | Why |
|---|---|---|
| Runtime package (`turbo_mode_handoff_runtime.*`) | `cwd=<PLUGIN_ROOT>` or `PYTHONPATH=<PLUGIN_ROOT>`. Never bare `uv run python -c` from repo root. | Repo root contains its own top-level `scripts/` package (`/Users/jp/Projects/active/codex-tool-dev/scripts/__init__.py`) that shadows the plugin's `scripts/`. The runtime package is not installed; it is path-imported, so the invocation must put `<PLUGIN_ROOT>` on `sys.path` first. |
| Direct script entrypoint (`python "$PLUGIN_ROOT/scripts/<name>.py"`) | Run by file path. Python prepends `scripts/` (the script's own directory) to `sys.path`, **not** `<PLUGIN_ROOT>`. Each wrapper must explicitly insert `<PLUGIN_ROOT>` via `sys.path.insert(0, str(PLUGIN_ROOT))` before importing `turbo_mode_handoff_runtime`. Always pass `PYTHONDONTWRITEBYTECODE=1` to avoid `__pycache__` residue inside the source tree. | This is the documented public entrypoint exercised by skill docs and `test_cli_commands.py`. Verification must match the production invocation shape, including `PYTHONDONTWRITEBYTECODE=1`. The wrapper's `sys.path.insert` is load-bearing — without it, the runtime package is not importable from a direct file invocation. |
| Test imports (`pytest plugins/turbo-mode/handoff/1.6.0/tests`) | Always invoke pytest with its rootdir at `<PLUGIN_ROOT>` so the plugin's `pyproject.toml` and plugin-rooted import behavior apply. | The plugin owns its own `pyproject.toml`; running pytest from the repo root with a path argument still uses the plugin rootdir, but bare `python -c` does not. |

Concrete verification helpers used throughout this plan:

```bash
# Runtime package import check (must run with cwd=<PLUGIN_ROOT> OR PYTHONPATH set):
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plugins/turbo-mode/handoff/1.6.0 \
    uv run python -c "import turbo_mode_handoff_runtime.storage_primitives"

# Direct wrapper smoke (file-path invocation; PLUGIN_ROOT auto-lands on sys.path):
PYTHONDONTWRITEBYTECODE=1 \
    python plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py --help

# Residue check (must not add new source-tree cache files):
find plugins/turbo-mode/handoff/1.6.0 \( -name __pycache__ -o -name '*.pyc' \) -print | sort > /tmp/handoff-residue-before.txt
# ...run smoke...
find plugins/turbo-mode/handoff/1.6.0 \( -name __pycache__ -o -name '*.pyc' \) -print | sort > /tmp/handoff-residue-after.txt
diff /tmp/handoff-residue-before.txt /tmp/handoff-residue-after.txt
```

Optionally set `PYTHONPYCACHEPREFIX="$(mktemp -d)"` for the smoke commands if the local Python version ignores `PYTHONDONTWRITEBYTECODE=1` for any reason; this keeps caches out of the source tree as a belt-and-braces.

## File Structure

**Create:**

- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/__init__.py` - versioned runtime package marker.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py` - implementation currently in `scripts/active_writes.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/cleanup.py` - implementation currently in `scripts/cleanup.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/defer.py` - implementation currently in `scripts/defer.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/distill.py` - implementation currently in `scripts/distill.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/handoff_parsing.py` - implementation currently in `scripts/handoff_parsing.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/installed_host_harness.py` - implementation currently in `scripts/installed_host_harness.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/list_handoffs.py` - implementation currently in `scripts/list_handoffs.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/load_transactions.py` - implementation currently in `scripts/load_transactions.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/plugin_siblings.py` - implementation currently in `scripts/plugin_siblings.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/project_paths.py` - implementation currently in `scripts/project_paths.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/provenance.py` - implementation currently in `scripts/provenance.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/quality_check.py` - implementation currently in `scripts/quality_check.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/search.py` - implementation currently in `scripts/search.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py` - implementation currently in `scripts/session_state.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py` - implementation currently in `scripts/storage_authority.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority_inventory.py` - implementation currently in `scripts/storage_authority_inventory.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py` - implementation currently in `scripts/storage_primitives.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/ticket_parsing.py` - implementation currently in `scripts/ticket_parsing.py`.
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/triage.py` - implementation currently in `scripts/triage.py`.
- `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py` - namespace-collision and guard tests.

**Modify:**

- `plugins/turbo-mode/handoff/1.6.0/scripts/*.py` - convert implementation files into wrappers; keep `scripts/_bootstrap.py` as the minimal wrapper bootstrap helper for cached/shadowed `scripts` package repair.
- `plugins/turbo-mode/handoff/1.6.0/tests/*.py` - change implementation-level imports and monkeypatch targets from `scripts.*` to `turbo_mode_handoff_runtime.*` (rewrite all four AST shapes — `from scripts.<mod>`, `from scripts import <mod>`, `import scripts.<mod>`, `patch("scripts.<mod>…")`). Keep CLI tests that execute `scripts/*.py` and the explicitly preserved wrapper-compatibility tests enumerated in Task 3 Step 1a (notably `test_search_module_reexports_parse_handoff`).
- `plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py` - retarget `POLICY_CODE_COMMENTS` to the runtime files (`turbo_mode_handoff_runtime/cleanup.py`, `turbo_mode_handoff_runtime/project_paths.py`) so the "host-repository policy" policy-text assertions follow the implementation after the wrapper conversion.
- `plugins/turbo-mode/handoff/1.6.0/tests/fixtures/storage_authority_inventory.json` - regenerate after wrapper/doc changes.
- `plugins/turbo-mode/handoff/1.6.0/README.md` - update three sections: (1) the `### Scripts` section header and intro sentence (rename to `### Runtime Package and Script Wrappers`, restate "core logic lives in `turbo_mode_handoff_runtime/`"), (2) the `## Architecture` ASCII diagram to show both the runtime package and the wrappers, (3) the `### Adding a Script` guidance.
- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py` or runtime equivalent - update inventory paths if `quality_check.py` remains a wrapper with changed hash.
- `plugins/turbo-mode/tools/refresh/classifier.py` - add `turbo_mode_handoff_runtime/*.py` to `GUARDED_ONLY_PATTERNS` only (not `is_executable_or_command_bearing_path` — runtime modules are import-only; see Design Decisions), and migrate/rebaseline exact `HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS` entries whose source files move or whose wrapper hashes change.
- `plugins/turbo-mode/tools/refresh/tests/test_classifier.py` - update `_discover_command_surface_paths` to glob runtime package files and update Gate 5 exact-hash assertions after wrapper conversion finalizes the moved implementation surface.
- `plugins/turbo-mode/tools/refresh/tests/fixtures/*.json` - update only if refresh tests fail because they snapshot Handoff source text.

## Task 0: Branch and Status Gate

**Files:** none

- [ ] **Step 1: Record and inspect starting state**

The live checkout may already contain ignored residue or unrelated local work. Do not require a globally clean tree and do not trash caches just to satisfy a preflight. Instead, capture the exact baseline before branching and inspect it for unrelated in-progress work that could be folded into the migration by accident:

```bash
git status --short > /tmp/handoff-runtime-worktree-baseline.txt
git status --short --ignored > /tmp/handoff-runtime-ignored-baseline.txt
cat /tmp/handoff-runtime-worktree-baseline.txt
cat /tmp/handoff-runtime-ignored-baseline.txt
```

Expected: no modified tracked files except this plan if it is being edited in the current session. Ignored entries such as `.venv`, `.pytest_cache`, `.DS_Store`, or `__pycache__` may already exist and are baseline residue, not migration output. If the baseline contains unrelated tracked edits or untracked source/docs that look in-progress, pause and resolve with the user; do not silently fold them into the migration commits.

- [ ] **Step 2: Create a scoped feature branch**

Do not commit directly to `main`. Branch protection may reject it, and even if it does not, intermediate commits that knowingly break tests are not acceptable on the default branch.

```bash
git checkout -b chore/handoff-runtime-package-migration main
```

All subsequent commits in Tasks 1–6 land on this branch. The PR in the final task targets `main`.

- [ ] **Step 3: Decide whether to commit the plan document**

The plan document (`docs/superpowers/plans/2026-05-15-handoff-runtime-package-migration.md`) is a docs artifact, not implementation. It can be:

- Committed as the first commit on the branch (recommended — gives reviewers the design context alongside the code).
- Left untracked if the team prefers plans not to land in the repo.

If committing:

```bash
git add docs/superpowers/plans/2026-05-15-handoff-runtime-package-migration.md
git commit -m "docs: add handoff runtime package migration plan"
```

---

## Task 1: Add Runtime Namespace Guard Tests

**Files:**

- Create: `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`
- Modify: none

- [ ] **Step 0: Reuse the Task 0 dirty-worktree baseline**

The worktree at plan-start is not guaranteed to be empty. Task 0 already captured two baselines:

- `/tmp/handoff-runtime-worktree-baseline.txt` from plain `git status --short`, used for worktree-delta checks.
- `/tmp/handoff-runtime-ignored-baseline.txt` from `git status --short --ignored`, used only when inspecting ignored local residue.

Use matching commands for each comparison. Do not compare plain status output to an ignored-status baseline. If Task 0 was skipped or the shell was restarted, recreate both before editing:

Run:

```bash
git status --short > /tmp/handoff-runtime-worktree-baseline.txt
git status --short --ignored > /tmp/handoff-runtime-ignored-baseline.txt
cat /tmp/handoff-runtime-worktree-baseline.txt
cat /tmp/handoff-runtime-ignored-baseline.txt
```

Do not commit this file; it is a local-only scratch file. If the baseline contains anything that looks like in-progress unrelated work (stash, decide, or commit before continuing), pause and resolve with the user — do not silently fold unrelated edits into the migration commits.

- [ ] **Step 1: Write the failing namespace tests**

Create `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`:

```python
from __future__ import annotations

import ast
import importlib
import sys
import types
from pathlib import Path

import pytest

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PACKAGE = "turbo_mode_handoff_runtime"
RUNTIME_DIR = PLUGIN_ROOT / RUNTIME_PACKAGE
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"

RUNTIME_MODULES = (
    "active_writes",
    "cleanup",
    "defer",
    "distill",
    "handoff_parsing",
    "installed_host_harness",
    "list_handoffs",
    "load_transactions",
    "plugin_siblings",
    "project_paths",
    "provenance",
    "quality_check",
    "search",
    "session_state",
    "storage_authority",
    "storage_authority_inventory",
    "storage_primitives",
    "ticket_parsing",
    "triage",
)

SCRIPT_WRAPPERS = tuple(
    sorted(
        p.name
        for p in SCRIPTS_DIR.glob("*.py")
        if p.name not in {"__init__.py", "_bootstrap.py"}
    )
)

WRAPPER_RESERVED_EXPORT_NAMES = {
    "PLUGIN_ROOT",
    "_RUNTIME_MODULE",
    "_exported_name",
    "_load_wrapper_bootstrap",
    "__all__",
    "importlib",
    "sys",
    "Path",
}


def test_runtime_package_imports_under_foreign_scripts_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_parent = tmp_path / "foreign_scripts"
    fake_parent.mkdir()
    (fake_parent / "storage_primitives.py").write_text(
        "raise AssertionError('foreign scripts package was imported')\n",
        encoding="utf-8",
    )
    for module_name in list(sys.modules):
        if module_name == "scripts" or module_name.startswith("scripts."):
            monkeypatch.delitem(sys.modules, module_name, raising=False)
        if module_name == RUNTIME_PACKAGE or module_name.startswith(f"{RUNTIME_PACKAGE}."):
            monkeypatch.delitem(sys.modules, module_name, raising=False)
    fake_scripts = types.ModuleType("scripts")
    fake_scripts.__path__ = [str(fake_parent)]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))

    module = importlib.import_module(f"{RUNTIME_PACKAGE}.storage_primitives")

    assert str(RUNTIME_DIR) in str(module.__file__)


@pytest.mark.parametrize("module_name", RUNTIME_MODULES)
def test_runtime_modules_do_not_import_scripts_namespace(module_name: str) -> None:
    """Catch all four import shapes plus dynamic importlib string constants.

    Without the string-constant check, a future
    ``importlib.import_module("scripts.session_state")`` would pass the AST
    import-node checks while still binding to the ambiguous namespace at
    runtime.
    """
    source = (RUNTIME_DIR / f"{module_name}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    offenders: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "scripts" or node.module.startswith("scripts."):
                offenders.append(f"line {node.lineno}: from {node.module}")
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "scripts" or alias.name.startswith("scripts."):
                    offenders.append(f"line {node.lineno}: import {alias.name}")
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value == "scripts" or node.value.startswith("scripts."):
                offenders.append(f"line {node.lineno}: string {node.value!r}")
    assert offenders == [], f"runtime module {module_name} references scripts namespace: {offenders}"


def test_runtime_modules_list_is_complete() -> None:
    """RUNTIME_MODULES must list every .py file in the runtime package.

    A new runtime file that is not in the tuple would evade the AST guard and
    import-completeness tests. The script-wrapper inventory test below catches
    the inverse case: a new public script with no matching runtime module.
    """
    actual = {
        p.stem
        for p in RUNTIME_DIR.glob("*.py")
        if p.name != "__init__.py"
    }
    assert actual == set(RUNTIME_MODULES), (
        f"RUNTIME_MODULES drift: missing={actual - set(RUNTIME_MODULES)}, "
        f"stale={set(RUNTIME_MODULES) - actual}"
    )


def test_runtime_modules_match_script_wrapper_inventory() -> None:
    """Every public script wrapper must have one matching runtime module.

    This prevents a new ``scripts/foo.py`` from being left as an implementation
    file with no runtime copy and no wrapper during parallel work.
    """
    wrapper_stems = {Path(name).stem for name in SCRIPT_WRAPPERS}
    assert set(RUNTIME_MODULES) == wrapper_stems, (
        f"runtime/script drift: missing_runtime={wrapper_stems - set(RUNTIME_MODULES)}, "
        f"stale_runtime={set(RUNTIME_MODULES) - wrapper_stems}"
    )


@pytest.mark.parametrize("module_name", RUNTIME_MODULES)
def test_runtime_modules_are_not_direct_entrypoints(module_name: str) -> None:
    """Runtime modules are import-only; wrappers own CLI execution."""
    source = (RUNTIME_DIR / f"{module_name}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assert not source.startswith("#!"), f"{module_name} has a shebang"
    offenders = [
        node.lineno
        for node in ast.walk(tree)
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    ]
    assert offenders == [], f"{module_name} contains __name__ entrypoint guards: {offenders}"


@pytest.mark.parametrize("module_name", RUNTIME_MODULES)
def test_runtime_modules_define_literal_all(module_name: str) -> None:
    """Every runtime module declares the wrapper export surface explicitly."""
    source = (RUNTIME_DIR / f"{module_name}.py").read_text(encoding="utf-8")
    tree = ast.parse(source)
    assignments = [
        node
        for node in tree.body
        if isinstance(node, ast.Assign)
        and any(isinstance(target, ast.Name) and target.id == "__all__" for target in node.targets)
    ]
    assert len(assignments) == 1, f"{module_name} must define exactly one __all__ assignment"
    value = assignments[0].value
    assert isinstance(value, ast.Tuple), f"{module_name} __all__ must be a literal tuple"
    names: list[str] = []
    for element in value.elts:
        assert isinstance(element, ast.Constant) and isinstance(element.value, str), (
            f"{module_name} __all__ must contain only string literals"
        )
        names.append(element.value)
    assert names, f"{module_name} __all__ must not be empty"
    assert names == sorted(set(names)), f"{module_name} __all__ must be sorted and unique"
    reserved = sorted(set(names) & WRAPPER_RESERVED_EXPORT_NAMES)
    assert reserved == [], f"{module_name} __all__ would clobber wrapper locals: {reserved}"


@pytest.mark.parametrize("module_name", RUNTIME_MODULES)
def test_runtime_all_names_resolve(module_name: str, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))
    module = importlib.import_module(f"{RUNTIME_PACKAGE}.{module_name}")
    assert isinstance(module.__all__, tuple), f"{module_name} __all__ must be a tuple"
    missing = [name for name in module.__all__ if not hasattr(module, name)]
    assert missing == [], f"{module_name} __all__ names are missing at runtime: {missing}"


@pytest.mark.parametrize("module_name", RUNTIME_MODULES)
def test_all_runtime_modules_import(
    module_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every runtime module must be importable, not just AST-parseable.

    The AST guard in test_runtime_modules_do_not_import_scripts_namespace
    only parses source text. This test actually imports each module to
    catch runtime errors (missing dependencies, circular imports, syntax
    errors invisible to ast.parse).
    """
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))
    mod = importlib.import_module(f"{RUNTIME_PACKAGE}.{module_name}")
    assert hasattr(mod, "__file__")


```

- [ ] **Step 2: Run test to verify it fails**

Run:

```bash
uv run pytest plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py -q
```

Expected: FAIL because `turbo_mode_handoff_runtime/` does not exist yet.

- [ ] **Step 3: Verify only intended files differ from the baseline**

Run:

```bash
git status --short > /tmp/handoff-runtime-worktree-current.txt
diff /tmp/handoff-runtime-worktree-baseline.txt /tmp/handoff-runtime-worktree-current.txt
```

Expected: the only line that appears in `/tmp/handoff-runtime-worktree-current.txt` but not in the baseline is `?? plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`. Ignored cache/env residue is intentionally absent from this comparison. Any other deltas mean the worker accidentally touched something — investigate before continuing.

Do not commit yet. Keep this red test for Task 2.

## Task 2: Create Runtime Package by Copying Current Implementations

**Files:**

- Create: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/*.py`
- Modify: none outside the new package
- Test: `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`

- [ ] **Step 1: Create the package directory**

Run:

```bash
mkdir -p plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime
```

- [ ] **Step 2: Add package marker**

Create `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/__init__.py`:

```python
"""Runtime implementation package for Turbo Mode Handoff 1.6.0."""
```

- [ ] **Step 3: Copy implementation modules**

Copy these files from `scripts/` to `turbo_mode_handoff_runtime/`:

```bash
cp plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/cleanup.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/cleanup.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/defer.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/defer.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/distill.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/distill.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/handoff_parsing.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/handoff_parsing.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/installed_host_harness.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/installed_host_harness.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/list_handoffs.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/list_handoffs.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/load_transactions.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/plugin_siblings.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/plugin_siblings.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/project_paths.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/project_paths.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/provenance.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/provenance.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/quality_check.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/quality_check.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/search.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/search.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority_inventory.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/storage_primitives.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/ticket_parsing.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/ticket_parsing.py
cp plugins/turbo-mode/handoff/1.6.0/scripts/triage.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/triage.py
```

- [ ] **Step 4: Remove copied bootstrap preloaders and CLI entrypoint blocks from runtime modules**

In the copied runtime files only, remove each local `_load_bootstrap_by_path()` function, the `_load_bootstrap_by_path()` call, and `del _load_bootstrap_by_path`.

Files that currently contain the preloader:

```text
active_writes.py
cleanup.py
defer.py
distill.py
installed_host_harness.py
list_handoffs.py
load_transactions.py
project_paths.py
quality_check.py
search.py
session_state.py
storage_authority.py
triage.py
```

The copied runtime modules should not mention `scripts._bootstrap`.

Also remove shebangs and every `if __name__ == "__main__":` block from the copied runtime files. Several source scripts are direct CLI entrypoints today (`search.py`, `session_state.py`, `triage.py`, `distill.py`, `load_transactions.py`, and others); after migration, only `scripts/*.py` wrappers may keep direct-execution blocks. The runtime copies keep their `main()` functions but must not be directly executable modules.

The guard added in Task 1 (`test_runtime_modules_are_not_direct_entrypoints`) must fail until this cleanup is complete and then stay green.

- [ ] **Step 4b: Define literal runtime `__all__` tuples**

In every copied runtime module, add exactly one top-level literal tuple assignment:

```python
__all__ = (
    "NameOne",
    "name_two",
)
```

The tuple is the wrapper compatibility contract. Include only names intentionally exported by the matching `scripts/<name>.py` wrapper:

- functions, classes, constants, and dataclasses that callers may import from the wrapper;
- explicitly documented compatibility re-exports such as `scripts.search.parse_handoff`;
- explicitly preserved private-helper compatibility exceptions, currently `_acquire_lock` / `_release_lock` where subprocess tests already import them.

Do not generate `__all__` mechanically from every non-underscore module global. Imported modules, imported helper functions, transient constants, and implementation-only names are not automatically public. If a name must remain importable through `scripts.<mod>`, put it in `__all__` deliberately and let `test_runtime_all_names_resolve` prove it exists.

The guard in Task 1 requires each `__all__` value to be a sorted, unique literal tuple of strings and rejects names that would clobber wrapper locals. If that guard fails, fix the tuple instead of weakening the wrapper template.

- [ ] **Step 5: Convert runtime imports (AST-driven, not table-driven)**

Inside `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/`, every `scripts.*` reference must be rewritten. A hand-written table is not sufficient because the live source uses at least four distinct shapes — confirmed by `rg "from scripts|import scripts" plugins/turbo-mode/handoff/1.6.0/scripts` at plan-time:

| Shape | Example (live source) | Where it appears |
|---|---|---|
| `from scripts.<mod> import <name>` | `from scripts.storage_primitives import write_text_atomic_exclusive` (`defer.py:46`) | module-level imports throughout |
| `from scripts import <mod>` | `from scripts import storage_primitives as _storage_primitives` (`active_writes.py:46`), `from scripts import storage_primitives` (`session_state.py:44`) | `active_writes.py`, `session_state.py` |
| Function-scoped `from scripts.<mod> import <name>` | `from scripts.storage_authority import chain_state_recovery_inventory` (`session_state.py:497-654` has ~12 of these) | `session_state.py` deferred imports |
| `TYPE_CHECKING: from scripts.<mod> import <name>` | `from scripts.active_writes import ActiveWriteReservation` (`storage_authority.py:18-19`) | `storage_authority.py` |
| `importlib.import_module("scripts.<mod>")` | string literals in `installed_host_harness.py` | dynamic imports |

Rewrite rule: every `scripts.<x>` token (in any of the shapes above) becomes `turbo_mode_handoff_runtime.<x>` inside files under `turbo_mode_handoff_runtime/`. The `from scripts import <mod>` shape becomes `from turbo_mode_handoff_runtime import <mod>`; preserve `as <alias>` clauses unchanged. The `TYPE_CHECKING` block in `storage_authority.py` retargets the same way and remains under the `if TYPE_CHECKING:` guard.

Generate the live residual list before assuming any rewrite is complete:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plugins/turbo-mode/handoff/1.6.0 \
    uv run python - <<'PY'
import ast
from pathlib import Path
ROOT = Path("plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime")
offenders: list[tuple[str, int, str]] = []
for py in sorted(ROOT.glob("*.py")):
    tree = ast.parse(py.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module == "scripts" or node.module.startswith("scripts."):
                offenders.append((py.name, node.lineno, f"from {node.module}"))
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "scripts" or alias.name.startswith("scripts."):
                    offenders.append((py.name, node.lineno, f"import {alias.name}"))
        elif isinstance(node, ast.Constant) and isinstance(node.value, str):
            if node.value == "scripts" or node.value.startswith("scripts."):
                offenders.append((py.name, node.lineno, f"string {node.value!r}"))
for row in offenders:
    print(*row)
print(f"TOTAL: {len(offenders)}")
PY
```

Expected: `TOTAL: 0`. Any non-zero count names the exact file, line, and shape that still references the ambiguous namespace. Repeat the rewrite and rerun until clean.

Replace the runtime dynamic import strings in `installed_host_harness.py` so the residual sweep above also passes on string constants:

```python
importlib.import_module("turbo_mode_handoff_runtime.session_state")
importlib.import_module("turbo_mode_handoff_runtime.storage_authority")
```

**Installed-host harness proof semantics after migration:** The harness currently proves that `importlib.import_module("scripts.session_state")` resolves to the *installed* copy, not the source checkout. After this rewrite, the harness must prove **three** surfaces, in separate proof lanes:

1. **Wrapper import isolation, wrapper-first:** in a fresh subprocess, import `scripts.session_state` and `scripts.storage_authority` before importing any `turbo_mode_handoff_runtime.*` module. The subprocess must have the installed copy's directory on `sys.path` (not the repo root), so `scripts` resolves to the installed copy's `scripts/` directory. This is consistent with the wrapper import contract scope: `from scripts.*` is only guaranteed when the plugin's `scripts/` takes precedence on `sys.path`.
2. **Runtime import isolation:** in a second fresh subprocess, import `turbo_mode_handoff_runtime.session_state` and `turbo_mode_handoff_runtime.storage_authority` and prove they resolve to the installed copy's runtime package.
3. **Direct-file execution:** in a third subprocess, execute at least `python <installed_plugin>/scripts/session_state.py --help` with `PYTHONDONTWRITEBYTECODE=1` and prove it exits 0. This is the only harness lane that proves file-path execution bootstraps `PLUGIN_ROOT`; importing `scripts.session_state` from a subprocess whose `sys.path` already contains the installed plugin root is not enough.

The `test_direct_wrappers_ignore_foreign_scripts_package` test in `test_bootstrap.py` covers wrapper isolation *in-process* (from the source tree), but it does not cover the installed-copy scenario where both source and installed wrappers compete on `sys.path`. The harness is the only test that creates a real installed copy and probes import resolution from subprocesses. Dropping any of the three probes leaves a surface unverified.

**Limitation:** Neither the harness nor the wrapper tests prove that `import scripts.<mod>` works from the repo root. The repo's top-level `scripts/__init__.py` will shadow the plugin's `scripts/` in that context. This is a known, accepted limitation — the wrapper contract is file-path execution and plugin-rooted imports, not arbitrary `import scripts.*` from any working directory.

Update the harness to run wrapper import before runtime import in a clean subprocess:

```python
wrapper_modules = [
    importlib.import_module("scripts.session_state"),
    importlib.import_module("scripts.storage_authority"),
]
```

Then run the runtime import probe in a separate subprocess:

```python
runtime_modules = [
    importlib.import_module("turbo_mode_handoff_runtime.session_state"),
    importlib.import_module("turbo_mode_handoff_runtime.storage_authority"),
]
```

Emit all three proof lanes in the payload:

```python
"loaded_wrapper_module_files": [
    str(Path(inspect.getfile(module)).resolve())
    for module in wrapper_modules
],
"loaded_runtime_module_files": [
    str(Path(inspect.getfile(module)).resolve())
    for module in runtime_modules
],
"direct_file_entrypoint_results": [
    {
        "script": "scripts/session_state.py",
        "args": ["--help"],
        "returncode": completed.returncode,
        "stdout_contains_usage": "usage:" in completed.stdout,
    }
],
```

The test assertion must verify that **all** loaded module files resolve under `installed_plugin`, not under `source_checkout`, for both import keys. It must also assert every `direct_file_entrypoint_results` row has `returncode == 0` and, for the help smoke, `stdout_contains_usage is True`. Update both the payload field names and the assertions that read `loaded_handoff_module_files` to check the new keys. Do not collapse these probes into one subprocess.

- [ ] **Step 6: Run runtime guard tests**

Run:

```bash
uv run pytest plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py -q
```

Expected: all tests in `test_runtime_namespace.py` pass, including `test_all_runtime_modules_import` (every module imports cleanly) and `test_runtime_modules_list_is_complete` (no drift between the static tuple and the filesystem). Wrapper-specific guards are added later, when the wrappers are introduced.

- [ ] **Step 7: Run focused runtime imports**

The runtime package is path-imported, not installed. The repo root contains its own top-level `scripts/__init__.py` package that would shadow the plugin, and the root `pyproject.toml` does not install the plugin's runtime package. Both conditions mean a bare `uv run python -c "from turbo_mode_handoff_runtime..."` from repo root will fail with `ModuleNotFoundError`. Run the check with `PYTHONPATH` set to the plugin root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plugins/turbo-mode/handoff/1.6.0 \
    uv run python -c "from turbo_mode_handoff_runtime.storage_authority import discover_handoff_inventory; from turbo_mode_handoff_runtime.session_state import main; from turbo_mode_handoff_runtime.storage_primitives import write_json_atomic"
```

Expected: exit 0 with no stdout. This is a belt-and-braces check on top of the `test_all_runtime_modules_import` parametrized test — the pytest test imports every module, while this smoke tests the `PYTHONPATH` invocation shape that matches production.

Then verify the smoke did not add new `__pycache__` or `.pyc` residue inside the source tree. Do not require the repository to start empty; compare before/after snapshots:

```bash
find plugins/turbo-mode/handoff/1.6.0 \( -name __pycache__ -o -name '*.pyc' \) -print | sort > /tmp/handoff-residue-before.txt
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plugins/turbo-mode/handoff/1.6.0 \
    uv run python -c "from turbo_mode_handoff_runtime.storage_authority import discover_handoff_inventory; from turbo_mode_handoff_runtime.session_state import main; from turbo_mode_handoff_runtime.storage_primitives import write_json_atomic"
find plugins/turbo-mode/handoff/1.6.0 \( -name __pycache__ -o -name '*.pyc' \) -print | sort > /tmp/handoff-residue-after.txt
diff /tmp/handoff-residue-before.txt /tmp/handoff-residue-after.txt
```

Expected: no diff output. If new residue appears, `PYTHONDONTWRITEBYTECODE=1` is being ignored; rerun the import command with `PYTHONPYCACHEPREFIX="$(mktemp -d)"` prepended and clean up only the new residue with `trash`.

- [ ] **Step 8: Commit**

The commit gate requires all seven import-completeness, export-surface, and import-only conditions to be green:

1. `test_all_runtime_modules_import` — every module in `RUNTIME_MODULES` imports without error.
2. `test_runtime_modules_list_is_complete` — `RUNTIME_MODULES` matches the actual `*.py` files on disk (no missing, no stale).
3. `test_runtime_modules_match_script_wrapper_inventory` — every public `scripts/*.py` wrapper has exactly one matching runtime module.
4. `test_runtime_modules_do_not_import_scripts_namespace` — no module references the ambiguous `scripts.*` namespace.
5. `test_runtime_modules_are_not_direct_entrypoints` — no runtime module has a shebang or `if __name__ == "__main__":` block.
6. `test_runtime_modules_define_literal_all` — every runtime module declares a sorted, unique literal `__all__` tuple and does not export wrapper-reserved names.
7. `test_runtime_all_names_resolve` — every name in every runtime module's `__all__` exists at runtime.

If any of these fail, do not commit. Fix the issue and rerun Step 6.

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py
git commit -m "chore: add handoff runtime package"
```

## Task 3: Convert Implementation Tests to Runtime Imports While Preserving CLI Coverage

**Files:**

- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/*.py`
- Test: full Handoff test suite

- [ ] **Step 1: Update implementation-level imports (broader than `from scripts.`)**

In `plugins/turbo-mode/handoff/1.6.0/tests/*.py`, the live tree uses the same four shapes as the runtime modules. Rewrite all four:

```text
from scripts.<mod>        -> from turbo_mode_handoff_runtime.<mod>
import scripts.<mod>      -> import turbo_mode_handoff_runtime.<mod>     (preserves "as <alias>" clauses)
from scripts import <mod> -> from turbo_mode_handoff_runtime import <mod>
patch("scripts.<mod>      -> patch("turbo_mode_handoff_runtime.<mod>     (also patch(scripts.<mod>. … )
mocker.patch("scripts.<mod>  ->  mocker.patch("turbo_mode_handoff_runtime.<mod>
monkeypatch.setattr("scripts.<mod>  ->  monkeypatch.setattr("turbo_mode_handoff_runtime.<mod>
```

Generate the live residual list against the test tree before declaring this step done. Reuse the AST sweep from Task 2 Step 5, pointed at `plugins/turbo-mode/handoff/1.6.0/tests`. `TOTAL` must reach zero **except** for the explicitly preserved compatibility tests enumerated in Step 1a.

- [ ] **Step 1a: Preserve documented wrapper-compatibility tests**

These tests intentionally exercise the `scripts.*` surface as the documented public re-export contract. They must keep their `from scripts.…` imports — do not retarget them:

| Test | Surface it locks in | Source today |
|---|---|---|
| `tests/test_search.py::test_search_module_reexports_parse_handoff` | `from scripts.search import parse_handoff` is a documented backward-compat re-export (`scripts/search.py:15` comment marks it as such). | line 20-23 |
| `tests/test_active_writes.py` private-helper imports (`_acquire_lock`, `_release_lock`) | Private-helper re-export through the wrapper, validated by Task 4 Step 1's `test_scripts_wrappers_reexport_private_helpers`. | lines 2080, 2098 |
| `tests/test_load_transactions.py` subprocess private-helper imports (`_acquire_lock`, `_release_lock`) | Subprocess code snippets that import `from scripts.load_transactions import _acquire_lock` and run in a child process with `cwd=plugin_root`. These prove the wrapper re-exports private helpers correctly in the subprocess execution shape, not just the in-process import shape. | lines 1242, 1260 |
| `tests/test_bootstrap.py` — handled separately in Step 2 below | Bootstrap behavior on the `scripts/` side. | n/a |

For these explicit cases, leave the `from scripts.…` imports unchanged in this task. They prove the wrapper still surfaces what the documented contract promises; rewriting them would silently delete that coverage.

Do not change subprocess tests that execute files under `PLUGIN_ROOT / "scripts"`, such as:

```python
str(SCRIPT_DIR / "session_state.py")
f'python "{PLUGIN_ROOT}/scripts/search.py" nonexistent_query_xyz'
f'python "{PLUGIN_ROOT}/scripts/triage.py" --tickets-dir "{tickets}"'
f'python "{PLUGIN_ROOT}/scripts/distill.py" "{handoff}" --learnings "{learnings}"'
```

Those are compatibility checks for the wrappers.

- [ ] **Step 2: Keep bootstrap tests unchanged in this task**

Do not rewrite `plugins/turbo-mode/handoff/1.6.0/tests/test_bootstrap.py` in this task. The `scripts/` files are still implementation files at this point, so the existing bootstrap tests are still valid until Task 4 converts the files to wrappers.

- [ ] **Step 3: Run implementation import tests**

Run:

```bash
uv run pytest plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py plugins/turbo-mode/handoff/1.6.0/tests -q
```

Expected: all pass.

- [ ] **Step 4: Commit**

Run:

```bash
git status --short
git add -- <exact Task 3 test files shown by git status>
git diff --cached --name-only
git commit -m "test: target handoff runtime package imports"
```

## Task 3b: Update Refresh Classifier for Runtime Package Surface

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/classifier.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`
- Test: refresh test suite

The refresh classifier models Handoff executable surfaces through hard-coded pattern tuples (`GUARDED_ONLY_PATTERNS`, `FAST_SAFE_PATTERNS`, `COVERAGE_GAP_PATTERNS`, `SMOKE_BY_PATTERN`) and the function `is_executable_or_command_bearing_path` (which matches `*/scripts/*.py` and `*/hooks/*.py`). After this migration, `turbo_mode_handoff_runtime/*.py` files are first-class Handoff source — changing them can break runtime behavior — but the classifier has no rules for them. The refresh tests that discover command surfaces via `_discover_command_surface_paths()` only glob `scripts/*.py` and `hooks/*.py`.

Without this task, a refresh cycle after the migration would not classify changes to `turbo_mode_handoff_runtime/` as Handoff source changes, silently skipping guard evaluation for runtime files. For `ADDED` files (first refresh after merge), the new runtime package is a new installed-cache import surface. Treat those ADDED runtime files as `COVERAGE_GAP` until publication evidence proves the installed cache contains the package. After the package exists in the installed cache, ordinary `CHANGED` runtime files classify as `GUARDED` via `GUARDED_ONLY_PATTERNS`.

This task does **not** finalize the exact Gate 5 hash-contract migration. Live `classifier.py` has `HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS` entries for Handoff files such as `scripts/active_writes.py`, `scripts/distill.py`, `scripts/installed_host_harness.py`, `scripts/list_handoffs.py`, `scripts/load_transactions.py`, `scripts/project_paths.py`, `scripts/quality_check.py`, `scripts/storage_authority.py`, `scripts/storage_authority_inventory.py`, and `scripts/storage_primitives.py`. Live refresh tests assert each contract's `source_sha256` matches the live file bytes. Those contracts must be finalized in Task 4 after the wrapper files contain their final text; otherwise the plan would ask the worker to hash wrapper content that does not exist yet.

**Classifier evaluation chain context:** The classifier uses a single `if/elif` chain ordered as follows. Understanding this order is essential to writing correct tests:

1. `_handoff_storage_gate5_refresh_contract` → GUARDED
2. `_is_added_executable_path` (ADDED only, calls `is_executable_or_command_bearing_path`) → COVERAGE_GAP
3. `_is_added_non_doc_path` (ADDED only) → COVERAGE_GAP
4. new `_is_added_handoff_runtime_package_path` (ADDED only) → COVERAGE_GAP
5. `_is_executable_doc_surface` → COVERAGE_GAP
6. `_is_handoff_state_helper_direct_python_doc_migration` → GUARDED
7. `_doc_policy_reasons` → COVERAGE_GAP
8. `COVERAGE_GAP_PATTERNS` (path glob) → COVERAGE_GAP
9. `GUARDED_ONLY_PATTERNS` (path glob) → GUARDED
10. `FAST_SAFE_PATTERNS` (path glob) → FAST
11. else fallback (calls `is_executable_or_command_bearing_path`) → COVERAGE_GAP

For `CHANGED` runtime files: steps 2-4 are no-ops (they hard-gate on `DiffKind.ADDED`), so the file falls through to step 9 where `GUARDED_ONLY_PATTERNS` catches it → `GUARDED`. Correct.

For `ADDED` runtime files: step 2 is false because runtime files are not executable, have no shebang, and are not command-bearing; step 3 is false because `_is_added_non_doc_path` is gated to doc-root globs; step 4 catches the new runtime package path → `COVERAGE_GAP`. Correct under this plan. If this expected outcome fails, either the explicit ADDED-runtime helper was not added in the right order or the classifier semantics changed and the plan must be updated before continuing.

- [ ] **Step 1: Add runtime package pattern to `GUARDED_ONLY_PATTERNS` only**

In `plugins/turbo-mode/tools/refresh/classifier.py`:

Add a `GUARDED_ONLY_PATTERNS` entry for runtime package files that carry implementation but have no direct smoke commands (most of them — the existing smoke entries for `scripts/search.py`, `scripts/triage.py`, `scripts/session_state.py` already cover the executable entrypoints):

```python
# Add to GUARDED_ONLY_PATTERNS tuple:
"handoff/1.6.0/turbo_mode_handoff_runtime/*.py",
```

This ensures that a `CHANGED` runtime module triggers the guarded-only classification (diff requires review, but no additional smoke beyond the existing script-level smoke).

**Do NOT add `*/turbo_mode_handoff_runtime/*.py` to `is_executable_or_command_bearing_path`.** Runtime modules are implementation, not command-bearing entrypoints — only `scripts/*.py` wrappers have `if __name__ == "__main__":` blocks. Adding runtime files to `is_executable_or_command_bearing_path` would cause `_is_added_executable_path` (step 2) to fire for `ADDED` runtime files, incorrectly treating import-only implementation modules as direct executable surfaces.

- [ ] **Step 2: Add explicit ADDED-runtime coverage-gap handling**

In `plugins/turbo-mode/tools/refresh/classifier.py`, add a focused helper for first-refresh runtime package files:

```python
def _is_added_handoff_runtime_package_path(path: str, *, kind: DiffKind) -> bool:
    return kind == DiffKind.ADDED and fnmatch.fnmatch(
        path,
        "handoff/1.6.0/turbo_mode_handoff_runtime/*.py",
    )
```

Insert this check in `classify_diff_path` after `_is_added_non_doc_path` and before `_is_executable_doc_surface`:

```python
elif _is_added_handoff_runtime_package_path(path, kind=kind):
    coverage_status = CoverageStatus.COVERAGE_GAP
    reasons.append("added-handoff-runtime-package-path")
```

Rationale: first-refresh ADDED runtime files are a new installed-cache import surface, not routine changed implementation. They should block automatic publication until the follow-up publication gate proves the installed cache contains `turbo_mode_handoff_runtime/*.py`.

- [ ] **Step 2b: Leave exact Gate 5 hash contracts unchanged for now**

Do not migrate `HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS` in Task 3b. The current `scripts/*.py` files still contain implementation text at this point, and Task 4 has not yet produced final wrapper text. Migrating exact hashes here would either pin soon-to-be-stale script files or require guessing wrapper hashes.

Record the current contract keys before moving on so Task 4 can deliberately migrate or retire each one after wrapper conversion:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plugins/turbo-mode/tools uv run python - <<'PY'
from refresh.classifier import HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS
for path in sorted(HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS):
    if path.startswith("handoff/1.6.0/scripts/"):
        print(path)
PY
```

Expected: the command prints the script contracts that Task 4 must reconcile. Do not commit this output; it is a local checklist.

- [ ] **Step 3: Update `_discover_command_surface_paths` in test_classifier**

In `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`, the `_discover_command_surface_paths()` helper globs `scripts/*.py` and `hooks/*.py` to discover all paths that should be classified. It must also glob `turbo_mode_handoff_runtime/*.py`:

```python
# Inside _discover_command_surface_paths(), after the scripts glob:
if (plugin_root / "turbo_mode_handoff_runtime").exists():
    paths.extend(
        f"{prefix}/{path.relative_to(plugin_root).as_posix()}"
        for path in sorted((plugin_root / "turbo_mode_handoff_runtime").glob("*.py"))
    )
```

- [ ] **Step 3b: Add explicit ADDED vs CHANGED classifier outcome tests**

The existing classifier tests may only exercise one diff kind per path. Add parametrized tests that exercise runtime module paths under both `DiffKind.CHANGED` and `DiffKind.ADDED`, asserting the correct outcome for each:

```python
@pytest.mark.parametrize("runtime_module", [
    "turbo_mode_handoff_runtime/storage_primitives.py",
    "turbo_mode_handoff_runtime/session_state.py",
    "turbo_mode_handoff_runtime/search.py",
    "turbo_mode_handoff_runtime/__init__.py",
])
class TestRuntimePackageClassifierOutcomes:
    """Verify classifier behavior for runtime package files under both diff kinds.

    CHANGED files must reach GUARDED_ONLY_PATTERNS (step 8) since the
    ADDED-specific checks (steps 2-3) are no-ops for CHANGED.

    ADDED files are first-refresh publication gaps because the installed cache
    does not yet contain the new runtime package import surface.
    """

    def test_changed_runtime_module_is_guarded(
        self, runtime_module: str, handoff_prefix: str,
    ) -> None:
        path = f"{handoff_prefix}/{runtime_module}"
        result = classify_diff_path(
            path,
            kind=DiffKind.CHANGED,
            source_text="",
            cache_text="",
            executable=False,
        )
        assert result.outcome == PathOutcome.GUARDED_ONLY
        assert result.mutation_mode == MutationMode.GUARDED
        assert result.coverage_status == CoverageStatus.COVERED

    def test_added_runtime_module_is_coverage_gap(
        self, runtime_module: str, handoff_prefix: str,
    ) -> None:
        path = f"{handoff_prefix}/{runtime_module}"
        result = classify_diff_path(
            path,
            kind=DiffKind.ADDED,
            source_text="",
            cache_text="",
            executable=False,
        )
        assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
        assert result.mutation_mode == MutationMode.GUARDED
        assert result.coverage_status == CoverageStatus.COVERAGE_GAP
```

The live test file already imports `classify_diff_path`, `CoverageStatus`, `DiffKind`, `MutationMode`, and `PathOutcome`; use those APIs directly rather than a pseudocode `classify` helper or a nonexistent `Classification` enum. The key requirement is that both diff kinds assert the full outcome tuple — `CHANGED` runtime files are `PathOutcome.GUARDED_ONLY` and covered, while first-refresh `ADDED` runtime files are `PathOutcome.COVERAGE_GAP_FAIL` with `CoverageStatus.COVERAGE_GAP`. Do not prove only mutation mode.

- [ ] **Step 3c: Update static classifier expected-surface tests**

The live classifier test file has both a dynamic discovery helper and a pinned expected list. The `_discover_command_surface_paths` glob update (Step 3) makes runtime files discoverable, but `test_current_source_tree_surfaces_match_pinned_fixture_lists` still compares that dynamic result to `EXPECTED_COMMAND_SURFACE_PATHS`. If the pinned tuple is not updated in the same slice, the refresh suite fails even though the classifier change is otherwise correct.

Update `plugins/turbo-mode/tools/refresh/tests/test_classifier.py::EXPECTED_COMMAND_SURFACE_PATHS` to include every new runtime package file discovered by the updated helper:

```text
handoff/1.6.0/turbo_mode_handoff_runtime/__init__.py
handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py
handoff/1.6.0/turbo_mode_handoff_runtime/cleanup.py
handoff/1.6.0/turbo_mode_handoff_runtime/defer.py
handoff/1.6.0/turbo_mode_handoff_runtime/distill.py
handoff/1.6.0/turbo_mode_handoff_runtime/handoff_parsing.py
handoff/1.6.0/turbo_mode_handoff_runtime/installed_host_harness.py
handoff/1.6.0/turbo_mode_handoff_runtime/list_handoffs.py
handoff/1.6.0/turbo_mode_handoff_runtime/load_transactions.py
handoff/1.6.0/turbo_mode_handoff_runtime/plugin_siblings.py
handoff/1.6.0/turbo_mode_handoff_runtime/project_paths.py
handoff/1.6.0/turbo_mode_handoff_runtime/provenance.py
handoff/1.6.0/turbo_mode_handoff_runtime/quality_check.py
handoff/1.6.0/turbo_mode_handoff_runtime/search.py
handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py
handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py
handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority_inventory.py
handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py
handoff/1.6.0/turbo_mode_handoff_runtime/ticket_parsing.py
handoff/1.6.0/turbo_mode_handoff_runtime/triage.py
```

Keep the tuple sorted consistently with `_discover_command_surface_paths()`.

Search for hard-coded path lists:

```bash
rg -n "EXPECTED_COMMAND_SURFACE_PATHS|turbo_mode_handoff_runtime|expected_classified|expected_surface|EXPECTED_PATHS" \
    plugins/turbo-mode/tools/refresh/tests/test_classifier.py
```

Expected: `EXPECTED_COMMAND_SURFACE_PATHS` is found and updated. Any other expected-surface lists must also include the runtime package files or explicitly document why they intentionally exclude import-only runtime modules.

- [ ] **Step 4: Run refresh tests**

```bash
uv run pytest plugins/turbo-mode/tools/refresh/tests -q
```

Expected: pass, including the new `TestRuntimePackageClassifierOutcomes` tests. If fixture failures mention Handoff source text, regenerate only the named fixtures using the existing refresh fixture workflow; do not hand-edit JSON payloads.

- [ ] **Step 5: Commit**

```bash
git status --short
git add plugins/turbo-mode/tools/refresh/classifier.py
git add -- <exact refresh test/fixture files changed for Task 3b>
git diff --cached --name-only
git commit -m "feat: classify handoff runtime package as guarded source surface

CHANGED runtime files → GUARDED (via GUARDED_ONLY_PATTERNS).
ADDED runtime files → COVERAGE_GAP until installed publication proves the new import surface.
Exact Gate 5 contracts remain for Task 4 after wrapper text exists.
Tests exercise both diff kinds explicitly."
```

---

## Task 4: Replace `scripts/` Implementations with Thin Wrappers

**Files:**

- Modify: all public `plugins/turbo-mode/handoff/1.6.0/scripts/*.py` wrappers
- Modify: `plugins/turbo-mode/handoff/1.6.0/scripts/_bootstrap.py` as the minimal wrapper bootstrap helper
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_bootstrap.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py`
- Modify: `plugins/turbo-mode/tools/refresh/classifier.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`
- Test: CLI, wrapper, and release-metadata tests

- [ ] **Step 0: Audit current CLI block shapes before choosing wrapper templates**

Do not rely on the plan's template assignment as an unevidenced assertion. Before replacing wrappers, run an AST audit over the live `scripts/*.py` files and confirm the current CLI block shape is still trivial:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run python - <<'PY'
import ast
from pathlib import Path

root = Path("plugins/turbo-mode/handoff/1.6.0/scripts")
for path in sorted(root.glob("*.py")):
    if path.name in {"__init__.py", "_bootstrap.py"}:
        continue
    tree = ast.parse(path.read_text(encoding="utf-8"))
    main_defs = [
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == "main"
    ]
    guards = [
        node
        for node in tree.body
        if isinstance(node, ast.If)
        and isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    ]
    print(f"{path.name}: main={len(main_defs)} cli_guards={len(guards)}")
PY
```

Expected audited assignment:

| Wrapper | Current CLI shape | Wrapper template |
|---|---|---|
| `cleanup.py` | `sys.exit(main())`; `main() -> int` | integer-returning CLI |
| `defer.py` | `raise SystemExit(main())`; `main(argv) -> int` | integer-returning CLI |
| `distill.py` | `print(main())` then exit 0; `main(argv) -> str` | string-returning CLI |
| `list_handoffs.py` | `print(main())`; `main(argv) -> str` | string-returning CLI |
| `load_transactions.py` | `raise SystemExit(main())`; `main(argv) -> int` | integer-returning CLI |
| `plugin_siblings.py` | `raise SystemExit(main())`; `main(argv) -> int` | integer-returning CLI |
| `quality_check.py` | `raise SystemExit(main())`; `main() -> int` | integer-returning CLI |
| `search.py` | `print(main())` then exit 0; `main(argv) -> str` | string-returning CLI |
| `session_state.py` | `raise SystemExit(main())`; `main(argv) -> int` | integer-returning CLI |
| `storage_authority_inventory.py` | `raise SystemExit(main())`; `main() -> int` | integer-returning CLI |
| `triage.py` | `raise SystemExit(main())`; `main(argv) -> int` | integer-returning CLI |

All other public scripts are library wrappers and must not contain a `__name__ == "__main__"` block after conversion. If the audit output disagrees with this table, stop and update the template assignment before editing wrappers.

Add a permanent AST guard in `tests/test_runtime_namespace.py` that maps wrapper filenames to one of `library`, `integer-cli`, or `string-cli` and asserts the final wrapper shape. The guard should verify:

- library wrappers have no top-level `__name__ == "__main__"` block;
- integer CLI wrappers have exactly one top-level CLI block whose body is `raise SystemExit(_RUNTIME_MODULE.main())`;
- string CLI wrappers have exactly one top-level CLI block whose body prints `_RUNTIME_MODULE.main()` and then exits 0;
- no wrapper contains `globals().update`.

Use this shape, adjusted only if the pre-conversion audit finds a real mismatch:

```python
WRAPPER_CLI_SHAPES = {
    "active_writes.py": "library",
    "cleanup.py": "integer-cli",
    "defer.py": "integer-cli",
    "distill.py": "string-cli",
    "handoff_parsing.py": "library",
    "installed_host_harness.py": "library",
    "list_handoffs.py": "string-cli",
    "load_transactions.py": "integer-cli",
    "plugin_siblings.py": "integer-cli",
    "project_paths.py": "library",
    "provenance.py": "library",
    "quality_check.py": "integer-cli",
    "search.py": "string-cli",
    "session_state.py": "integer-cli",
    "storage_authority.py": "library",
    "storage_authority_inventory.py": "integer-cli",
    "storage_primitives.py": "library",
    "ticket_parsing.py": "library",
    "triage.py": "integer-cli",
}


def _is_runtime_main_call(node: ast.AST) -> bool:
    return (
        isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "_RUNTIME_MODULE"
        and node.func.attr == "main"
        and node.args == []
        and node.keywords == []
    )


def _is_name_main_guard(node: ast.If) -> bool:
    return (
        isinstance(node.test, ast.Compare)
        and isinstance(node.test.left, ast.Name)
        and node.test.left.id == "__name__"
    )


@pytest.mark.parametrize("script_name", SCRIPT_WRAPPERS)
def test_wrapper_cli_block_shape(script_name: str) -> None:
    source = (SCRIPTS_DIR / script_name).read_text(encoding="utf-8")
    assert "globals().update" not in source
    tree = ast.parse(source)
    guards = [
        node
        for node in tree.body
        if isinstance(node, ast.If) and _is_name_main_guard(node)
    ]
    shape = WRAPPER_CLI_SHAPES[script_name]
    if shape == "library":
        assert guards == []
        return
    assert len(guards) == 1
    body = guards[0].body
    if shape == "integer-cli":
        assert len(body) == 1
        stmt = body[0]
        assert isinstance(stmt, ast.Raise)
        assert isinstance(stmt.exc, ast.Call)
        assert isinstance(stmt.exc.func, ast.Name)
        assert stmt.exc.func.id == "SystemExit"
        assert len(stmt.exc.args) == 1
        assert _is_runtime_main_call(stmt.exc.args[0])
    elif shape == "string-cli":
        assert len(body) == 2
        print_stmt, exit_stmt = body
        assert isinstance(print_stmt, ast.Expr)
        assert isinstance(print_stmt.value, ast.Call)
        assert isinstance(print_stmt.value.func, ast.Name)
        assert print_stmt.value.func.id == "print"
        assert len(print_stmt.value.args) == 1
        assert _is_runtime_main_call(print_stmt.value.args[0])
        assert isinstance(exit_stmt, ast.Raise)
        assert isinstance(exit_stmt.exc, ast.Call)
        assert isinstance(exit_stmt.exc.func, ast.Name)
        assert exit_stmt.exc.func.id == "SystemExit"
        assert len(exit_stmt.exc.args) == 1
        assert isinstance(exit_stmt.exc.args[0], ast.Constant)
        assert exit_stmt.exc.args[0].value == 0
    else:
        raise AssertionError(f"unknown wrapper shape: {shape}")
```

- [ ] **Step 0b: Retarget release-metadata policy-text assertions**

`tests/test_release_metadata.py` weaponizes two `scripts/*.py` files as **policy documentation artifacts**, not just unit-under-test code. It asserts that:

- `"gitignored to avoid tracking ephemeral session artifacts"` and `"local-only working memory"` are **absent** from `scripts/cleanup.py` and `scripts/project_paths.py`
- `"host-repository policy"` **is present** in both files

(See `test_internal_comments_do_not_assert_gitignored_or_local_only_policy` and the `POLICY_CODE_COMMENTS` list.)

Once those two files become generic re-export wrappers in Steps 4-5 below, the "host-repository policy" string will leave the wrappers (the policy text lives in the docstring of the implementation, not in the thin `__all__`-driven wrapper). That assertion will then fail. Fix this before the wrapper conversion so the test stays green throughout:

In `plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py`, retarget `POLICY_CODE_COMMENTS` to the runtime files where the policy text actually lives after migration:

```python
POLICY_CODE_COMMENTS = [
    PLUGIN_ROOT / "turbo_mode_handoff_runtime" / "cleanup.py",
    PLUGIN_ROOT / "turbo_mode_handoff_runtime" / "project_paths.py",
]
```

Rationale: the policy text is a property of the implementation, not the wrapper shim. After Task 2 copied the implementation into `turbo_mode_handoff_runtime/`, the docstrings of `turbo_mode_handoff_runtime/cleanup.py` and `turbo_mode_handoff_runtime/project_paths.py` carry the "host-repository policy" wording (verify before retargeting: `rg -n "host-repository policy" plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/{cleanup,project_paths}.py`). The test should follow the policy, not the file path.

Verify the test still passes against the runtime files immediately after retargeting and before wrapper conversion:

```bash
uv run pytest plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py::test_internal_comments_do_not_assert_gitignored_or_local_only_policy -q
```

Expected: pass.

- [ ] **Step 1: Add wrapper guard and parity tests**

Modify `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`. The file already has `SCRIPTS_DIR` and a dynamic `SCRIPT_WRAPPERS` definition from Task 1; do not add a second definition with the same name. Either keep the dynamic definition or replace it with this explicit tuple, but the file must have exactly one `SCRIPT_WRAPPERS` definition:

```python
SCRIPT_WRAPPERS = (
    "active_writes.py",
    "cleanup.py",
    "defer.py",
    "distill.py",
    "handoff_parsing.py",
    "installed_host_harness.py",
    "list_handoffs.py",
    "load_transactions.py",
    "plugin_siblings.py",
    "project_paths.py",
    "provenance.py",
    "quality_check.py",
    "search.py",
    "session_state.py",
    "storage_authority.py",
    "storage_authority_inventory.py",
    "storage_primitives.py",
    "ticket_parsing.py",
    "triage.py",
)


@pytest.mark.parametrize("script_name", SCRIPT_WRAPPERS)
def test_scripts_wrapper_uses_runtime_package(script_name: str) -> None:
    text = (SCRIPTS_DIR / script_name).read_text(encoding="utf-8")
    assert "turbo_mode_handoff_runtime." in text
    assert "sys.path.insert(0, str(PLUGIN_ROOT))" in text
    assert "globals().update" not in text
    assert "__all__ = _RUNTIME_MODULE.__all__" in text


def test_script_wrapper_list_matches_filesystem() -> None:
    actual = {
        p.name
        for p in SCRIPTS_DIR.glob("*.py")
        if p.name not in {"__init__.py", "_bootstrap.py"}
    }
    assert actual == set(SCRIPT_WRAPPERS), (
        f"SCRIPT_WRAPPERS drift: missing={actual - set(SCRIPT_WRAPPERS)}, "
        f"stale={set(SCRIPT_WRAPPERS) - actual}"
    )


def test_scripts_wrappers_reexport_private_helpers() -> None:
    from scripts.active_writes import _acquire_lock as active_acquire_lock
    from scripts.load_transactions import _acquire_lock as load_acquire_lock

    assert callable(active_acquire_lock)
    assert callable(load_acquire_lock)


def test_scripts_wrappers_reexport_documented_public_symbols() -> None:
    """Lock in public re-exports already promised by the wrapper surface.

    These names appear in skill docs, plan docs, or in-source comments that
    label them as the documented compatibility contract. If a future wrapper
    template stops surfacing one of them, this test must fail.
    """
    # scripts.search re-exports parser symbols (see scripts/search.py header
    # comment "Re-exported for backward compatibility with callers that import
    # parser symbols from scripts.search.").
    from scripts.search import parse_handoff, search_handoffs, main as search_main

    assert callable(parse_handoff)
    assert callable(search_handoffs)
    assert callable(search_main)

    # storage_authority surfaces the documented chain-state and active-write
    # entrypoints used by session_state.py's deferred imports today.
    from scripts.storage_authority import (
        chain_state_recovery_inventory,
        discover_handoff_inventory,
        read_chain_state,
    )

    assert callable(chain_state_recovery_inventory)
    assert callable(discover_handoff_inventory)
    assert callable(read_chain_state)


@pytest.mark.parametrize("script_name", SCRIPT_WRAPPERS)
def test_script_wrapper_exports_runtime_all(
    script_name: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Every wrapper must re-export exactly the runtime module's __all__ API.

    Most implementation tests are retargeted to turbo_mode_handoff_runtime.* in
    Task 3. This parity check keeps the wrapper contract honest: supported
    plugin-rooted imports such as ``from scripts.project_paths import
    get_project_root`` must keep working when the runtime module intentionally
    lists that name in __all__. Accidental imported globals are not public.
    """
    for module_name in list(sys.modules):
        if module_name == "scripts" or module_name.startswith("scripts."):
            monkeypatch.delitem(sys.modules, module_name, raising=False)
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))

    module_stem = script_name.removesuffix(".py")
    runtime_module = importlib.import_module(f"{RUNTIME_PACKAGE}.{module_stem}")
    wrapper_module = importlib.import_module(f"scripts.{module_stem}")
    assert wrapper_module.__all__ == runtime_module.__all__
    missing = sorted(name for name in runtime_module.__all__ if not hasattr(wrapper_module, name))
    assert missing == [], f"wrapper {script_name} missing public exports: {missing}"
```

This parity test intentionally covers the explicit `__all__` surface for every wrapper. Keep the separate private-helper compatibility checks for `_acquire_lock` / `_release_lock` in `active_writes.py` and `load_transactions.py`; those names must appear in the corresponding runtime module's `__all__` because private re-export is a named compatibility exception, not a blanket requirement for all private runtime names.

- [ ] **Step 2: Rewrite bootstrap tests into wrapper compatibility tests**

Modify `plugins/turbo-mode/handoff/1.6.0/tests/test_bootstrap.py` so it asserts wrapper behavior plus the preserved cached/shadowed-`scripts` repair contract. Do not delete the bootstrap compatibility contract silently.

Before adding the direct-wrapper foreign-`scripts` test, replace the stale hand-written `DIRECT_ENTRYPOINTS` tuple with a filesystem-derived wrapper list. This test loads wrappers as modules, so it must cover every public wrapper, not just currently known CLI entrypoints:

```python
WRAPPER_ENTRYPOINTS = tuple(
    sorted(
        path.name
        for path in SCRIPT_DIR.glob("*.py")
        if path.name not in {"__init__.py", "_bootstrap.py"}
    )
)
```

Use this shape for the direct-wrapper foreign-`scripts` test.

**Critical design constraint:** The test must NOT preinsert `PLUGIN_ROOT` into `sys.path` before loading the wrapper. The wrapper's `sys.path.insert(0, str(PLUGIN_ROOT))` is load-bearing — it is the only mechanism that makes `turbo_mode_handoff_runtime` importable when the script is invoked by file path. If the test supplies `PLUGIN_ROOT` itself, a broken wrapper missing the `sys.path.insert` still passes. The test starts with only `scripts/` (the direct-execution natural path) and the foreign scripts dir:

The test must also preserve the existing cached-bootstrap repair proof for every wrapper. A wrapper that imports the runtime package but skips `_load_wrapper_bootstrap()` would pass direct CLI smoke yet fail the long-lived interpreter contract where `sys.modules["scripts"]` is already bound to a foreign package.

```python
@pytest.mark.parametrize("entrypoint", WRAPPER_ENTRYPOINTS)
def test_direct_wrappers_ignore_foreign_scripts_package(
    entrypoint: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Prove the wrapper inserts PLUGIN_ROOT and resolves the runtime package.

    Starts with PLUGIN_ROOT absent from sys.path — only the script's own
    directory (scripts/) is present, matching a real ``python scripts/foo.py``
    invocation.  If the wrapper does not insert PLUGIN_ROOT itself, the import
    of turbo_mode_handoff_runtime will fail.
    """
    fake_parent = tmp_path / "foreign_scripts"
    fake_parent.mkdir()
    (fake_parent / "storage_primitives.py").write_text(
        "raise AssertionError('foreign scripts package was imported')\n",
        encoding="utf-8",
    )
    for module_name in list(sys.modules):
        if module_name == "scripts" or module_name.startswith("scripts."):
            monkeypatch.delitem(sys.modules, module_name, raising=False)
        if module_name == "turbo_mode_handoff_runtime" or module_name.startswith(
            "turbo_mode_handoff_runtime."
        ):
            monkeypatch.delitem(sys.modules, module_name, raising=False)
    fake_scripts = types.ModuleType("scripts")
    fake_scripts.__path__ = [str(fake_parent)]  # type: ignore[attr-defined]
    foreign_bootstrap = types.ModuleType("scripts._bootstrap")
    foreign_bootstrap.__file__ = str(fake_parent / "_bootstrap.py")
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    monkeypatch.setitem(sys.modules, "scripts._bootstrap", foreign_bootstrap)

    # Simulate what Python does for `python scripts/<name>.py`:
    # prepend the script's own directory, NOT the plugin root.
    monkeypatch.syspath_prepend(str(SCRIPT_DIR))

    # Explicitly remove PLUGIN_ROOT from sys.path if present,
    # so the wrapper must add it itself to import the runtime package.
    current_path = [p for p in sys.path if str(PLUGIN_ROOT) != p]
    monkeypatch.setattr(sys, "path", current_path)

    module_name = f"_handoff_wrapper_test_{entrypoint.removesuffix('.py')}"
    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_DIR / entrypoint)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, module_name, module)
    spec.loader.exec_module(module)

    # The wrapper must have inserted PLUGIN_ROOT itself.
    assert str(PLUGIN_ROOT) in sys.path, (
        f"wrapper {entrypoint} did not insert PLUGIN_ROOT into sys.path"
    )
    scripts_pkg = sys.modules["scripts"]
    assert list(scripts_pkg.__path__)[0] == str(SCRIPT_DIR)  # type: ignore[attr-defined]
    assert str(SCRIPT_DIR) in str(sys.modules["scripts._bootstrap"].__file__)

    loaded = [
        value
        for name, value in sys.modules.items()
        if name.startswith("turbo_mode_handoff_runtime.")
    ]
    assert loaded, (
        f"wrapper {entrypoint} did not import any turbo_mode_handoff_runtime modules"
    )
    assert all(
        str(PLUGIN_ROOT / "turbo_mode_handoff_runtime") in str(m.__file__)
        for m in loaded
        if hasattr(m, "__file__")
    )
```

Keep or add a second test that exercises the cached foreign `scripts` package repair path. The important case is a long-lived process where `sys.modules["scripts"]` already points at another package, but the plugin's `scripts/` directory is also a valid package path. After loading the wrapper/bootstrap path, `scripts.__path__` must have `SCRIPT_DIR` first and `import scripts.storage_authority` must resolve to the plugin wrapper, not the foreign package:

```python
def test_wrapper_bootstrap_repairs_cached_foreign_scripts_package(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fake_parent = tmp_path / "foreign_scripts"
    fake_parent.mkdir()
    (fake_parent / "storage_authority.py").write_text(
        "raise AssertionError('wrong storage_authority loaded')\n",
        encoding="utf-8",
    )
    for module_name in list(sys.modules):
        if module_name == "scripts" or module_name.startswith("scripts."):
            monkeypatch.delitem(sys.modules, module_name, raising=False)
    fake_scripts = types.ModuleType("scripts")
    fake_scripts.__path__ = [str(fake_parent), str(SCRIPT_DIR)]  # type: ignore[attr-defined]
    monkeypatch.setitem(sys.modules, "scripts", fake_scripts)
    monkeypatch.syspath_prepend(str(PLUGIN_ROOT))

    spec = importlib.util.spec_from_file_location(
        "scripts._bootstrap",
        SCRIPT_DIR / "_bootstrap.py",
    )
    assert spec is not None
    assert spec.loader is not None
    bootstrap = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "scripts._bootstrap", bootstrap)
    spec.loader.exec_module(bootstrap)

    bootstrap.ensure_plugin_scripts_package()
    storage_authority = importlib.import_module("scripts.storage_authority")

    scripts_pkg = sys.modules["scripts"]
    assert list(scripts_pkg.__path__)[0] == str(SCRIPT_DIR)  # type: ignore[attr-defined]
    assert str(SCRIPT_DIR) in str(storage_authority.__file__)
    assert str(fake_parent) in list(scripts_pkg.__path__)  # type: ignore[attr-defined]
```

- [ ] **Step 3: Run wrapper tests to verify they fail before wrapper conversion**

Run:

```bash
uv run pytest plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py plugins/turbo-mode/handoff/1.6.0/tests/test_bootstrap.py -q
```

Expected: fail because `scripts/` files are still implementation files and do not yet follow the wrapper/runtime shape.

- [ ] **Step 4: Replace library-only scripts with re-export wrappers**

Use this template for scripts with no CLI `main()`. Every wrapper loads `_bootstrap.py` by file path before importing the runtime module; this preserves the cached/shadowed-`scripts` repair contract without making runtime modules depend on `scripts.*`.

```python
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


def _load_wrapper_bootstrap() -> None:
    spec = importlib.util.spec_from_file_location(
        "scripts._bootstrap",
        Path(__file__).resolve().parent / "_bootstrap.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"load wrapper bootstrap failed: missing import spec. Got: {__file__!r:.100}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["scripts._bootstrap"] = module
    spec.loader.exec_module(module)
    module.ensure_plugin_scripts_package()


_load_wrapper_bootstrap()
del _load_wrapper_bootstrap

_RUNTIME_MODULE = importlib.import_module(
    "turbo_mode_handoff_runtime.storage_primitives"
)
if not isinstance(_RUNTIME_MODULE.__all__, tuple):
    raise RuntimeError(
        "load wrapper exports failed: runtime __all__ must be a tuple. "
        f"Got: {_RUNTIME_MODULE.__all__!r:.100}"
    )
__all__ = _RUNTIME_MODULE.__all__
for _exported_name in __all__:
    globals()[_exported_name] = getattr(_RUNTIME_MODULE, _exported_name)
```

Apply the template with the matching runtime module name to:

```text
scripts/active_writes.py
scripts/handoff_parsing.py
scripts/installed_host_harness.py
scripts/project_paths.py
scripts/provenance.py
scripts/storage_authority.py
scripts/storage_primitives.py
scripts/ticket_parsing.py
```

- [ ] **Step 5: Replace integer-returning CLI scripts**

Use this template for scripts whose runtime `main()` returns an integer:

```python
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


def _load_wrapper_bootstrap() -> None:
    spec = importlib.util.spec_from_file_location(
        "scripts._bootstrap",
        Path(__file__).resolve().parent / "_bootstrap.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"load wrapper bootstrap failed: missing import spec. Got: {__file__!r:.100}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["scripts._bootstrap"] = module
    spec.loader.exec_module(module)
    module.ensure_plugin_scripts_package()


_load_wrapper_bootstrap()
del _load_wrapper_bootstrap

_RUNTIME_MODULE = importlib.import_module("turbo_mode_handoff_runtime.cleanup")
if not isinstance(_RUNTIME_MODULE.__all__, tuple):
    raise RuntimeError(
        "load wrapper exports failed: runtime __all__ must be a tuple. "
        f"Got: {_RUNTIME_MODULE.__all__!r:.100}"
    )
__all__ = _RUNTIME_MODULE.__all__
for _exported_name in __all__:
    globals()[_exported_name] = getattr(_RUNTIME_MODULE, _exported_name)


if __name__ == "__main__":
    raise SystemExit(_RUNTIME_MODULE.main())
```

Apply the template with the matching runtime module name to:

```text
scripts/cleanup.py
scripts/defer.py
scripts/load_transactions.py
scripts/plugin_siblings.py
scripts/session_state.py
scripts/storage_authority_inventory.py
scripts/quality_check.py
scripts/triage.py
```

- [ ] **Step 6: Replace string-returning CLI scripts**

Use this template for scripts whose runtime `main()` returns a string that must be printed:

```python
from __future__ import annotations

import importlib
import importlib.util
import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parent.parent
if str(PLUGIN_ROOT) not in sys.path:
    sys.path.insert(0, str(PLUGIN_ROOT))


def _load_wrapper_bootstrap() -> None:
    spec = importlib.util.spec_from_file_location(
        "scripts._bootstrap",
        Path(__file__).resolve().parent / "_bootstrap.py",
    )
    if spec is None or spec.loader is None:
        raise RuntimeError(
            f"load wrapper bootstrap failed: missing import spec. Got: {__file__!r:.100}"
        )
    module = importlib.util.module_from_spec(spec)
    sys.modules["scripts._bootstrap"] = module
    spec.loader.exec_module(module)
    module.ensure_plugin_scripts_package()


_load_wrapper_bootstrap()
del _load_wrapper_bootstrap

_RUNTIME_MODULE = importlib.import_module("turbo_mode_handoff_runtime.search")
if not isinstance(_RUNTIME_MODULE.__all__, tuple):
    raise RuntimeError(
        "load wrapper exports failed: runtime __all__ must be a tuple. "
        f"Got: {_RUNTIME_MODULE.__all__!r:.100}"
    )
__all__ = _RUNTIME_MODULE.__all__
for _exported_name in __all__:
    globals()[_exported_name] = getattr(_RUNTIME_MODULE, _exported_name)


if __name__ == "__main__":
    print(_RUNTIME_MODULE.main())
    raise SystemExit(0)
```

Apply the template with the matching runtime module name to:

```text
scripts/distill.py
scripts/list_handoffs.py
scripts/search.py
```

- [ ] **Step 7: Preserve minimal bootstrap helper**

Keep `plugins/turbo-mode/handoff/1.6.0/scripts/_bootstrap.py`, but narrow its role to wrapper compatibility:

- It may repair `sys.modules["scripts"]` and prepend the plugin `scripts/` directory to `scripts.__path__`.
- It must not import implementation modules.
- It must remain idempotent.
- It must be covered by `test_wrapper_bootstrap_repairs_cached_foreign_scripts_package`.

Do not delete this file in this plan. Deletion would be a breaking compatibility decision and requires a separate explicit plan update.

- [ ] **Step 8: Run wrapper tests**

Run:

```bash
uv run pytest plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py plugins/turbo-mode/handoff/1.6.0/tests/test_bootstrap.py plugins/turbo-mode/handoff/1.6.0/tests/test_cli_commands.py -q
```

Expected: all pass.

- [ ] **Step 9: Update inventory specs and fixture BEFORE committing wrapper conversion**

The storage authority inventory currently expects `scripts/quality_check.py` to contain implementation text. After wrapper conversion, that file is a thin shim and the assertion will fail. Update the inventory in the same commit as the wrapper conversion so no intermediate commit has a red inventory test.

In `turbo_mode_handoff_runtime/storage_authority_inventory.py`, add an `InventorySpec` row for:

```python
InventorySpec(
    path="turbo_mode_handoff_runtime/quality_check.py",
    root="plugin",
    required=("<project_root>/.codex/handoffs/",),
    forbidden=("<project_root>/docs/handoffs/",),
)
```

Keep the existing `scripts/quality_check.py` row only if the wrapper still contains the required storage string. If the wrapper no longer contains it (likely — the generic wrapper template does not), remove the `scripts/quality_check.py` row.

In `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority_inventory.py`, update expectations:

```python
assert "turbo_mode_handoff_runtime/quality_check.py" in row_paths
```

Remove the `assert "scripts/quality_check.py" in row_paths` line if the wrapper row was removed from the inventory specs.

Regenerate the fixture:

```bash
uv run python plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py --write
```

Run inventory tests to confirm green:

```bash
uv run pytest plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority_inventory.py -q
```

Expected: pass.

- [ ] **Step 9b: Finalize exact Gate 5 hash contracts after wrapper conversion**

Now that the `scripts/*.py` wrapper files have their final text, update `plugins/turbo-mode/tools/refresh/classifier.py::HANDOFF_STORAGE_GATE5_REFRESH_CONTRACTS` deliberately:

- Move implementation-sensitive contracts from `handoff/1.6.0/scripts/<name>.py` to `handoff/1.6.0/turbo_mode_handoff_runtime/<name>.py` when the contract is intended to guard implementation behavior, not wrapper boilerplate.
- Keep a contract on `handoff/1.6.0/scripts/<name>.py` only when the wrapper file itself is the policy surface being guarded. In that case, update `source_sha256` to the wrapper file hash and add a short comment naming why wrapper text, not runtime implementation text, is the contract target.
- Do not leave a stale `scripts/<name>.py` implementation hash in place after the file becomes a generic wrapper.
- If any old script contract is intentionally retired, remove it in the same commit and add a focused classifier test or comment naming the replacement coverage (`GUARDED_ONLY_PATTERNS`, direct wrapper tests, runtime namespace guards, installed-host harness probes, or the first-refresh ADDED coverage-gap rule).

Run the exact-hash source check before continuing:

```bash
uv run pytest plugins/turbo-mode/tools/refresh/tests/test_classifier.py::test_handoff_storage_gate5_refresh_contract_source_hash_matches_live_file -q
```

Expected: pass. If it fails, update the contract target path or hash deliberately; do not weaken the test.

- [ ] **Step 10: Update README**

- [ ] **Step 10a: Update the README "Scripts" section header sentence**

In `plugins/turbo-mode/handoff/1.6.0/README.md`, the section currently titled `### Scripts` opens with "Core logic lives in `scripts/`. Skills handle UX and judgment; scripts handle deterministic work." That is no longer true after the migration: core logic lives in `turbo_mode_handoff_runtime/`, and `scripts/` only holds wrappers. Replace the section header and intro with:

````markdown
### Runtime Package and Script Wrappers

Core logic lives in `turbo_mode_handoff_runtime/`. The `scripts/` directory
holds thin compatibility wrappers that re-export from the runtime package so
existing direct invocations like `python "$PLUGIN_ROOT/scripts/<name>.py"`
keep working. Skills handle UX and judgment; the runtime modules handle
deterministic work.

| Module (runtime package) | Wrapper path | Purpose | Called By |
|--------------------------|--------------|---------|-----------|
| `cleanup.py` | `scripts/cleanup.py` | State file TTL cleanup helper | Dormant hook-compatible entry point; not wired into the `1.6.0` plugin manifest |
| `quality_check.py` | `scripts/quality_check.py` | Handoff/checkpoint format validation helper | Dormant hook-compatible entry point; not wired into the `1.6.0` plugin manifest |
| `defer.py` | `scripts/defer.py` | Ticket ID allocation, rendering, writing | `/defer` skill |
| `distill.py` | `scripts/distill.py` | Candidate extraction, dedup, metadata | `/distill` skill |
| `triage.py` | `scripts/triage.py` | Ticket scanning, orphan detection, matching | `/triage` skill |
| `search.py` | `scripts/search.py` | Section-aware handoff search | `/search` skill |
| `handoff_parsing.py` | `scripts/handoff_parsing.py` | Frontmatter and section parsing | Shared by distill, triage, search |
| `ticket_parsing.py` | `scripts/ticket_parsing.py` | Ticket YAML parsing and validation | Shared by defer, triage |
| `project_paths.py` | `scripts/project_paths.py` | Project name and directory resolution | Shared by all runtime modules |
| `provenance.py` | `scripts/provenance.py` | Source tracking and dedup metadata | Shared by defer, distill, triage |
````

- [ ] **Step 10b: Update the README architecture diagram**

The ASCII block under `## Architecture` still shows `├─ Scripts (Deterministic Work) ────────────────────┤`. Replace that block with one that distinguishes the runtime package from its wrappers:

````markdown
```
┌─ Skills (User Entry Points) ──────────────────────┐
│  /save  /quicksave  /load  /defer                  │
│  /search  /distill  /triage                        │
├─ Runtime Package (Deterministic Work) ────────────┤
│  Core:    project_paths, handoff_parsing           │
│  Domain:  defer, distill, triage, search           │
│  Audit:   provenance, ticket_parsing               │
│  Maint:   cleanup                                  │
│  Imports as turbo_mode_handoff_runtime.<mod>       │
├─ scripts/ Wrappers (Direct Entrypoints) ──────────┤
│  scripts/<name>.py re-exports the matching runtime │
│  module so `python $PLUGIN_ROOT/scripts/<name>.py` │
│  keeps working for skill docs and subprocess users │
├─ Hook-Compatible Helpers (Deferred) ───────────────┤
│  cleanup, quality_check (not manifest-wired in 1.6)│
├─ Storage ─────────────────────────────────────────┤
│  Active:  <project_root>/.codex/handoffs/         │
│  Archive: <project_root>/.codex/handoffs/archive/ │
│  State:   .codex/handoffs/.session-state/      │
└─ References ──────────────────────────────────────┘
   handoff-contract.md  format-reference.md
   synthesis-guide.md
```
````

- [ ] **Step 10c: Update the README "Adding a Script" guidance**

Replace the current "Adding a Script" section with:

````markdown
### Adding a Script

Add implementation code under `turbo_mode_handoff_runtime/<name>.py`.
Keep `scripts/<name>.py` as a thin compatibility wrapper so existing direct
script invocations keep working.

Implementation modules must import other Handoff modules through the versioned
runtime package, for example:

```python
from turbo_mode_handoff_runtime.project_paths import get_project_root
```

Do not add new implementation imports from top-level `scripts.*`. That namespace
is reserved for direct-entrypoint wrappers.

For CLI helpers:

- Implement `main(argv=None) -> int` or `main(argv=None) -> str` in the runtime module.
- Use `project_paths.get_project_name()` for project detection.
- Return JSON on stdout, diagnostics on stderr.
- Exit 0 on success, non-zero on failure.
- Add the wrapper to `tests/test_runtime_namespace.py::SCRIPT_WRAPPERS`.
````

- [ ] **Step 11: Run full Handoff and focused refresh suites before committing**

The wrapper conversion, inventory update, README update, and exact Gate 5 contract update must all be green in the same commit. Run the full Handoff suite:

```bash
uv run pytest plugins/turbo-mode/handoff/1.6.0/tests -q
```

Expected: all pass. If any test fails, fix before committing — do not create a red intermediate commit.

Run the focused refresh classifier checks that cover the runtime package path and exact hash contracts:

```bash
uv run pytest plugins/turbo-mode/tools/refresh/tests/test_classifier.py -q
```

Expected: pass. If fixture failures mention Handoff source text, regenerate only the named fixtures using the existing refresh fixture workflow; do not hand-edit JSON payloads.

- [ ] **Step 12: Commit wrapper conversion, inventory, and docs together**

```bash
git status --short
git add -- <exact wrapper files changed under plugins/turbo-mode/handoff/1.6.0/scripts/>
git add -- <exact tests changed for Task 4>
git add plugins/turbo-mode/handoff/1.6.0/README.md
git add plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority_inventory.py
git add plugins/turbo-mode/handoff/1.6.0/tests/fixtures/storage_authority_inventory.json
git add plugins/turbo-mode/tools/refresh/classifier.py
git add plugins/turbo-mode/tools/refresh/tests/test_classifier.py
git add -- <exact refresh fixture files changed by the classifier contract update, if any>
git diff --cached --name-only
git commit -m "refactor: convert handoff scripts to runtime wrappers

Includes inventory spec update, README documentation, and final
Gate 5 contract retargeting so no intermediate commit has a red test suite."
```

## Task 5: Remove Residual `scripts.*` Implementation Dependencies

**Files:**

- Modify: runtime modules, tests, docs, refresh fixtures only where residual checks identify active references
- Test: grep/AST guard, lint, Handoff suite, refresh suite

- [ ] **Step 0: Lint gate for dead imports**

The bootstrap narrowing and import rewriting can leave stale `import` statements that are syntactically valid but never used. Tests will not catch these — they only prove behavior, not import hygiene. Run a targeted lint pass:

```bash
ruff check --select F401 plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/ plugins/turbo-mode/handoff/1.6.0/scripts/
```

Expected: no violations. If any appear, fix them before continuing.

- [ ] **Step 0b: Sweep stale docstrings and comments**

The copied runtime modules may carry prose that still describes the old `scripts.*` architecture. These will not cause test failures but will mislead the next maintainer. Search and fix:

```bash
rg -n "scripts\.\*\|scripts\..*modules\|Import direction is scripts\|import local Handoff" plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
```

For example, `storage_primitives.py` line 4 currently says "Import direction is scripts.* modules -> storage_primitives only." After migration, the correct statement is "Import direction is turbo_mode_handoff_runtime.* modules -> storage_primitives only." Fix any matches.

- [ ] **Step 1: Search residual production references**

Run:

```bash
rg -n "from scripts\\.|import scripts\\.|import_module\\(\"scripts\\.|scripts\\._bootstrap|ensure_plugin_scripts_package" plugins/turbo-mode/handoff/1.6.0
```

Expected allowed matches:

```text
tests that intentionally verify wrapper compatibility and are named in an explicit allowlist
README text that says not to use scripts.* for implementation imports
scripts/*.py wrapper bootstrap boilerplate that loads scripts._bootstrap by file path
scripts/_bootstrap.py implementation of ensure_plugin_scripts_package
```

No runtime module under `turbo_mode_handoff_runtime/` may match. Matches in wrappers are allowed only for the bootstrap boilerplate; wrappers must not import implementation code through `scripts.*`.

Do not hand-wave test matches as "compatibility." Add or preserve a small expected-offender list in `tests/test_runtime_namespace.py` (or an equivalent focused test helper) that names the exact files/functions allowed to reference `scripts.*`, then fail on any unlisted match. The allowlist should include the preserved cases from Task 3 Step 1a and bootstrap-wrapper tests only. A new residual `scripts.*` reference must be either moved to `turbo_mode_handoff_runtime.*` or deliberately added to the allowlist with the compatibility surface it proves.

- [ ] **Step 2: Search repo-wide references**

Run:

```bash
rg -n "from scripts\\.|import scripts\\.|scripts\\._bootstrap|ensure_plugin_scripts_package" plugins/turbo-mode/tools docs/superpowers/plans
```

Expected: historical plan docs and refresh fixtures may match. Do not rewrite historical plan docs. Update refresh fixtures only if their tests compare current source snapshots and fail.

- [ ] **Step 3: Run Handoff tests**

Run:

```bash
uv run pytest plugins/turbo-mode/handoff/1.6.0/tests -q
```

Expected: all pass.

- [ ] **Step 4: Run refresh tests for source-snapshot fallout**

Run:

```bash
uv run pytest plugins/turbo-mode/tools/refresh/tests -q
```

Expected: pass. If fixture failures mention Handoff source text, regenerate only the named fixtures using the existing refresh fixture workflow in that package; do not hand-edit large JSON payloads.

- [ ] **Step 5: Commit**

Run:

```bash
git status --short
git add -- <exact residual-boundary files changed for Task 5>
git diff --cached --name-only
git commit -m "test: enforce handoff runtime namespace boundary"
```

## Task 6: Final Verification and PR Packaging

**Files:**

- Create: `docs/superpowers/plans/2026-05-15-handoff-runtime-package-publication-follow-up.md`
- Modify: none unless verification exposes a real defect

- [ ] **Step 1: Run full focused verification**

Run:

```bash
uv run pytest plugins/turbo-mode/handoff/1.6.0/tests -q
```

Expected: all pass.

Run:

```bash
uv run pytest plugins/turbo-mode/tools/refresh/tests -q
```

Expected: all pass or known unrelated failures documented with exact failure text.

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 2: Run direct CLI smoke commands (residue-safe)**

The plugin's own `test_cli_commands.py` exercises these entrypoints with `PYTHONDONTWRITEBYTECODE=1` and a residue snapshot for a reason: the source tree is the install target, and any `__pycache__` or `.pyc` generated during smoke would land *inside* the directory the PR is supposed to ship. `git diff --check` will not flag those files, and they would corrupt the next refresh or release fingerprint.

Snapshot residue paths before the smoke:

```bash
find plugins/turbo-mode/handoff/1.6.0 \( -name __pycache__ -o -name '*.pyc' \) -print | sort > /tmp/handoff-residue-before.txt
```

Run the smoke commands with byte-code writing suppressed:

```bash
PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py --help
PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/list_handoffs.py --project-root plugins/turbo-mode/handoff/1.6.0
PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/search.py impossible-query-for-runtime-migration-smoke --project-root plugins/turbo-mode/handoff/1.6.0
```

Expected:

- `session_state.py --help` exits 0 with stdout containing `usage:`.
- `list_handoffs.py --project-root …` exits 0 with stdout that is JSON containing a `total` field.
- `search.py impossible-query-… --project-root …` exits 0 with stdout that is JSON containing `"total": 0`.

Snapshot residue paths after the smoke and verify no new files appeared:

```bash
find plugins/turbo-mode/handoff/1.6.0 \( -name __pycache__ -o -name '*.pyc' \) -print | sort > /tmp/handoff-residue-after.txt
diff /tmp/handoff-residue-before.txt /tmp/handoff-residue-after.txt
```

Expected: no diff output. If new entries appear, `PYTHONDONTWRITEBYTECODE=1` is being ignored locally; rerun the smoke prepending `PYTHONPYCACHEPREFIX="$(mktemp -d)"` and clean the new residue with `trash` before continuing. Do **not** commit any of these caches.

- [ ] **Step 3: Inspect final diff boundaries**

Run:

```bash
git diff --stat main...HEAD
```

Expected: changes are limited to Handoff source, Handoff tests/docs/fixtures, and any refresh fixtures proven necessary by tests.

- [ ] **Step 3b: Record installed-cache publication follow-up gate**

This PR is source-only. Before packaging the PR, create the exact follow-up artifact:

```text
docs/superpowers/plans/2026-05-15-handoff-runtime-package-publication-follow-up.md
```

The artifact owns the installed-cache publication step and must include:

- Owner: the person/session responsible for running publication after source merge. This cannot be `TBD`; if the owner changes, update the artifact before merge.
- SLA/window: target publication no later than the next business day after source merge, with an exact date or maintenance window.
- Gate: run the read-only planner first (`plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --plan-refresh --inventory-check --json --run-id <id>`). Stop on `blocked-preflight`. If it reports `coverage-gap-blocked`, continue only when every coverage-gap reason is the expected first-refresh `added-handoff-runtime-package-path`; otherwise stop and repair classifier coverage before publication.
- Publication path: app-server `plugin/install` or the current repo-approved local-source refresh path; do not infer installed truth from source files alone, and do not treat `coverage-gap-blocked` as permission to run ordinary `--refresh` / `--guarded-refresh`.
- Runtime proof: app-server/runtime evidence such as `plugin/read`, `skills/list`, and `hooks/list`, plus a post-publication classifier/readiness check showing the installed cache contains `turbo_mode_handoff_runtime/*.py`.
- Residue policy: before/after residue snapshots, not absolute-empty assumptions.

Stage this follow-up artifact with the final PR-packaging work. Do not claim installed-cache freshness in the PR body unless this follow-up has already been executed and evidenced. If it remains future work, link the follow-up artifact and state that installed-cache publication is pending.

- [ ] **Step 4: Prepare PR body**

Use this PR body:

```markdown
## Summary

- Adds `turbo_mode_handoff_runtime` as the unique Handoff implementation package for the **source tree only**. Installed-cache refresh is intentionally out of scope and remains a separate publication step.
- Records the installed-cache publication follow-up gate in `docs/superpowers/plans/2026-05-15-handoff-runtime-package-publication-follow-up.md`; this PR does not claim installed-cache freshness until app-server/runtime evidence proves it after publication. The first post-merge planner result is expected to be `coverage-gap-blocked` for first-refresh ADDED runtime files, and the follow-up names the owner plus next-business-day publication window.
- Converts `scripts/*.py` into thin compatibility wrappers that re-export only the runtime module's literal `__all__` tuple, preserving every documented direct-entrypoint surface and the `scripts.search.parse_handoff` backward-compat re-export without exporting accidental imported globals.
- Adds AST-driven guard coverage preventing implementation imports from regressing to ambiguous `scripts.*`, including **string-constant detection** for `importlib.import_module("scripts.…")` calls. The guard is a committed test, not a one-off sweep.
- Adds import-completeness and export-surface tests: `test_all_runtime_modules_import` (every module imports cleanly), `test_runtime_modules_list_is_complete` (runtime tuple matches filesystem), `test_runtime_modules_match_script_wrapper_inventory` (public `scripts/*.py` wrappers match runtime modules), `test_runtime_modules_define_literal_all` (literal sorted `__all__`), and `test_runtime_all_names_resolve` (every exported name exists). A new script or runtime file that is not represented on the other side fails the guard.
- Wrapper tests start with `PLUGIN_ROOT` absent from `sys.path`, proving wrappers insert the plugin root themselves. Wrapper import contract is scoped to direct file-path execution and plugin-rooted imports; `import scripts.*` from the repo root is a known unsupported case (shadowed by the repo's top-level `scripts/__init__.py`).
- Updates the refresh classifier (`classifier.py`) to add `turbo_mode_handoff_runtime/*.py` to `GUARDED_ONLY_PATTERNS` for ordinary `CHANGED` runtime files. Does **not** add runtime files to `is_executable_or_command_bearing_path` (they are import-only implementation modules, not command-bearing entrypoints). Classifier tests exercise both diff kinds: `CHANGED` → `GUARDED`, first-refresh `ADDED` runtime files → `COVERAGE_GAP` until installed-cache publication proves the new import surface.
- Retargets `test_release_metadata.py::POLICY_CODE_COMMENTS` at the runtime files so the "host-repository policy" policy-text assertions follow the implementation, not the wrapper shim.
- Updates `installed_host_harness.py` to probe wrapper imports first, runtime imports second, and direct-file execution separately from the installed copy, emitting `loaded_wrapper_module_files`, `loaded_runtime_module_files`, and `direct_file_entrypoint_results`. Wrapper import and direct-file execution use separate fresh subprocesses so runtime import cannot mask a broken wrapper bootstrap.
- Runs `ruff check --select F401` as a lint gate to catch dead imports left behind by the bootstrap narrowing and import rewriting.
- Sweeps stale `scripts.*` architecture claims from runtime module docstrings and comments.

## Test Plan

- `uv run pytest plugins/turbo-mode/handoff/1.6.0/tests -q`
- `uv run pytest plugins/turbo-mode/tools/refresh/tests -q` (including `TestRuntimePackageClassifierOutcomes` for ADDED/CHANGED diff kinds and exact Gate 5 hash contracts)
- `ruff check --select F401 plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/ plugins/turbo-mode/handoff/1.6.0/scripts/`
- `git diff --check`
- Runtime package import smoke (path-imported, not installed):
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plugins/turbo-mode/handoff/1.6.0 uv run python -c "import turbo_mode_handoff_runtime.storage_authority, turbo_mode_handoff_runtime.session_state, turbo_mode_handoff_runtime.storage_primitives"`
- Direct-entrypoint smoke (file-path invocation, residue-safe):
  - `PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py --help`
  - `PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/list_handoffs.py --project-root plugins/turbo-mode/handoff/1.6.0`
  - `PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/search.py impossible-query-for-runtime-migration-smoke --project-root plugins/turbo-mode/handoff/1.6.0`
- Residue snapshot diff before/after the smoke (must be empty).
```

## Self-Review Checklist

- All work landed on `chore/handoff-runtime-package-migration`, not directly on `main`.
- Every commit on the branch has a green Handoff test suite. No commit knowingly breaks inventory, wrapper, or classifier tests.
- Every runtime module imports sibling Handoff code through `turbo_mode_handoff_runtime.*`.
- The committed `test_runtime_modules_do_not_import_scripts_namespace` guard catches all five import shapes: `from scripts.<mod>`, `from scripts import <mod>`, `import scripts.<mod>`, function-scoped deferred imports, and **string constants** used by `importlib.import_module("scripts.…")`. This is not a one-off sweep — the guard runs in CI and prevents regressions from any shape, including dynamic imports.
- `test_runtime_modules_list_is_complete` dynamically discovers `*.py` files in `turbo_mode_handoff_runtime/` and asserts they match the static `RUNTIME_MODULES` tuple. A new runtime file that isn't in the tuple fails this test, preventing it from evading AST guards and import tests.
- `test_all_runtime_modules_import` parametrically imports every module in `RUNTIME_MODULES`, catching runtime errors (missing dependencies, circular imports, syntax invisible to `ast.parse`) that the AST-only guard would miss.
- `test_runtime_modules_define_literal_all` and `test_runtime_all_names_resolve` prove every runtime module owns an explicit sorted literal `__all__` tuple and that every exported name exists. Wrappers export only that tuple; no wrapper uses `globals().update` or denylist-based re-export.
- The AST sweep from Task 2 Step 5 returns `TOTAL: 0` over `turbo_mode_handoff_runtime/`, confirming the runtime is clean.
- The runtime import smoke (`PYTHONPATH=plugins/turbo-mode/handoff/1.6.0 uv run python -c "..."`) succeeds without polluting `sys.path` from repo root, and the repo-root top-level `scripts/__init__.py` package is not shadowing the plugin's runtime package.
- `scripts/*.py` paths still exist for skill docs and subprocess callers.
- `scripts.search.parse_handoff` and the other documented `scripts.*` re-exports still resolve through the wrappers when the plugin's `scripts/` directory is on `sys.path` (pytest rootdir, subprocess with cwd=PLUGIN_ROOT, installed copy). The explicit wrapper-compatibility tests in `tests/test_runtime_namespace.py` and `tests/test_search.py` pass. **Known limitation:** `import scripts.*` from the repo root is not guaranteed — the repo's top-level `scripts/__init__.py` shadows the plugin's `scripts/`.
- The wrapper template assignment was audited before conversion: the 11 executable scripts were mapped to integer-returning or string-returning CLI wrappers, library wrappers were verified to have no CLI block, and the permanent wrapper-shape AST guard rejects drift from those template shapes.
- `test_direct_wrappers_ignore_foreign_scripts_package` starts with `PLUGIN_ROOT` **absent** from `sys.path` and verifies the wrapper itself inserts it. A wrapper missing the `sys.path.insert` line will fail this test.
- `test_load_transactions.py` subprocess snippets that import `from scripts.load_transactions import _acquire_lock` are preserved as wrapper-compatibility coverage — they prove the wrapper re-exports private helpers correctly in the subprocess execution shape. These are explicitly enumerated in the preserved compatibility allowlist alongside `test_active_writes.py`.
- `tests/test_release_metadata.py::POLICY_CODE_COMMENTS` points at `turbo_mode_handoff_runtime/cleanup.py` and `turbo_mode_handoff_runtime/project_paths.py`, and those files contain the "host-repository policy" text the test requires.
- The refresh classifier (`classifier.py`) includes `"handoff/1.6.0/turbo_mode_handoff_runtime/*.py"` in `GUARDED_ONLY_PATTERNS` but does **not** add runtime files to `is_executable_or_command_bearing_path` (they are import-only implementation modules, not command-bearing entrypoints). The classifier test's `_discover_command_surface_paths` globs runtime package files alongside scripts and hooks. `TestRuntimePackageClassifierOutcomes` explicitly tests both diff kinds: `CHANGED` runtime files → `GUARDED` (via `GUARDED_ONLY_PATTERNS`), first-refresh `ADDED` runtime files → `COVERAGE_GAP` (via the explicit ADDED-runtime helper).
- Exact Handoff Gate 5 hash contracts were finalized only after Task 4 produced final wrapper text. Any contract left on `scripts/<name>.py` has an explicit wrapper-policy reason; implementation-sensitive contracts point at `turbo_mode_handoff_runtime/<name>.py`.
- `docs/superpowers/plans/2026-05-15-handoff-runtime-package-publication-follow-up.md` exists, is staged, and names the installed-cache publication owner, next-business-day target window, read-only preflight gate, expected `coverage-gap-blocked` first-refresh lane, publication path, runtime proof requirements, and residue policy. The PR body links it instead of claiming installed-cache freshness from source changes alone.
- The installed-host harness (`installed_host_harness.py`) probes **three** surfaces in fresh subprocesses: `loaded_wrapper_module_files` proves wrapper import isolation before any runtime import, `loaded_runtime_module_files` proves runtime import isolation, and `direct_file_entrypoint_results` proves installed direct-file execution. All loaded files resolve under the installed copy, not the source checkout. The old single-key `loaded_handoff_module_files` is removed.
- `ruff check --select F401` passes on both `turbo_mode_handoff_runtime/` and `scripts/` with zero violations.
- Runtime module docstrings and comments do not contain stale `scripts.*` architecture claims (e.g., `storage_primitives.py` no longer says "Import direction is scripts.* modules -> storage_primitives").
- The README `### Scripts` section is renamed to `### Runtime Package and Script Wrappers` with the runtime/wrapper split, and the `## Architecture` ASCII diagram shows both the runtime package and the wrappers; no remaining README sentence claims "core logic lives in `scripts/`".
- No runtime module imports `scripts._bootstrap`; only wrappers may load the minimal wrapper bootstrap helper by file path.
- `scripts/_bootstrap.py` remains as the minimal cached/shadowed-`scripts` package repair helper, with an explicit compatibility test.
- CLI behavior is preserved for integer-returning and string-returning `main()` scripts.
- The lifecycle section declares the runtime package plus wrapper layer permanent for Handoff 1.x. No Handoff 1.x docs or tests imply the wrappers are temporary migration scaffolding.
- Tests still cover direct script execution by path, and the direct CLI smoke commands ran with `PYTHONDONTWRITEBYTECODE=1`; the residue snapshot diff before/after the smoke is empty.
- The storage authority inventory fixture was regenerated only through `storage_authority_inventory.py --write`. Inventory update is committed in the same commit as wrapper conversion (no red intermediate state).
- Historical plan docs were not rewritten merely because they mention old `scripts.*` design.
- The dirty-worktree baseline captured in Task 1 Step 0 is consistent with the final `git diff --stat main...HEAD`, and the diff is limited to Handoff source, Handoff tests/docs/fixtures, refresh classifier/tests, and any refresh fixtures proven necessary by tests.

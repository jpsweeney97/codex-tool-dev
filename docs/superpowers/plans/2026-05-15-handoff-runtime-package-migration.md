# Handoff Runtime Package Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Move Handoff implementation code out of the ambiguous top-level `scripts.*` namespace into `turbo_mode_handoff_runtime.*`, while preserving only the CLI script paths that current Handoff skills and repo smoke commands execute.

**Architecture:** `turbo_mode_handoff_runtime/` becomes the only implementation package. `scripts/` contains thin executable facades for real command entrypoints only; these facades insert the plugin root into `sys.path`, import the matching runtime `main()`, and exit with its return code. `scripts.*` imports are not a supported library API, and there is no cached/shadowed `scripts` package repair contract.

**Tech Stack:** Python 3.11+, `uv run pytest`, standard library plus `pyyaml>=6.0`, existing Handoff plugin layout under `plugins/turbo-mode/handoff/1.6.0`.

---

## Scope Decisions

- This is a source-tree migration. Do not mutate installed-cache copies in this plan.
- Handoff is still a single-user development plugin, so the migration may intentionally break `scripts.*` imports.
- The only script paths preserved are executable entrypoints used by Handoff skills or repo smoke commands:
  - `scripts/defer.py`
  - `scripts/distill.py`
  - `scripts/list_handoffs.py`
  - `scripts/load_transactions.py`
  - `scripts/plugin_siblings.py`
  - `scripts/search.py`
  - `scripts/session_state.py`
  - `scripts/triage.py`
- Library and development helpers move to runtime-only modules with no `scripts/` facade:
  - `active_writes.py`
  - `cleanup.py`
  - `handoff_parsing.py`
  - `installed_host_harness.py`
  - `project_paths.py`
  - `provenance.py`
  - `quality_check.py`
  - `storage_authority.py`
  - `storage_authority_inventory.py`
  - `storage_primitives.py`
  - `ticket_parsing.py`
- Delete `scripts/_bootstrap.py`. The long-lived-interpreter cached/shadowed `scripts` repair path is out of scope.
- Delete wrapper re-export parity machinery. Runtime modules do not need `__all__` solely to support script wrappers.
- Runtime modules are import-only. They must not have shebangs or `if __name__ == "__main__":` blocks.
- CLI facades are not import-compatible wrappers. They may expose only `main` as an implementation detail and must not re-export runtime symbols.
- Do not keep compatibility tests such as `from scripts.search import parse_handoff`. Rewrite those tests to import from `turbo_mode_handoff_runtime.*`.
- The Ticket plugin is out of scope.

## File Structure

**Create:**

- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/__init__.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/active_writes.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/cleanup.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/defer.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/distill.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/handoff_parsing.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/installed_host_harness.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/list_handoffs.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/load_transactions.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/plugin_siblings.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/project_paths.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/provenance.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/quality_check.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/search.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority_inventory.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/ticket_parsing.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/triage.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`

**Keep as CLI facades:**

- `plugins/turbo-mode/handoff/1.6.0/scripts/defer.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/distill.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/list_handoffs.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/plugin_siblings.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/search.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/triage.py`

**Delete:**

- `plugins/turbo-mode/handoff/1.6.0/scripts/__init__.py` if present
- `plugins/turbo-mode/handoff/1.6.0/scripts/_bootstrap.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/cleanup.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/handoff_parsing.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/installed_host_harness.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/project_paths.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/provenance.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/quality_check.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_primitives.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/ticket_parsing.py`

**Modify:**

- `plugins/turbo-mode/handoff/1.6.0/tests/*.py`
- `plugins/turbo-mode/handoff/1.6.0/README.md`
- `plugins/turbo-mode/handoff/1.6.0/CHANGELOG.md`
- `plugins/turbo-mode/handoff/1.6.0/skills/**/*.md` only if direct script references or wording need alignment
- `plugins/turbo-mode/handoff/1.6.0/tests/fixtures/storage_authority_inventory.json`
- `plugins/turbo-mode/tools/refresh/classifier.py`
- `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`
- `plugins/turbo-mode/tools/refresh/tests/test_planner.py`
- `plugins/turbo-mode/tools/refresh/tests/test_smoke.py` if smoke command labels or paths change
- `plugins/turbo-mode/tools/refresh/tests/fixtures/*.json` only if tests prove fixture drift
- `plugins/turbo-mode/tools/migration/cache_refresh_wrapper.py`
- `plugins/turbo-mode/tools/refresh/smoke.py`

## Approved Facade Templates

Every retained `scripts/<name>.py` file must use one of these shapes, with only the module name changed.

Integer-returning facades use this shape:

```python
#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from turbo_mode_handoff_runtime.session_state import main

if __name__ == "__main__":
    raise SystemExit(main())
```

String-returning facades use this shape so JSON/text output stays on stdout and exits 0:

```python
#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from turbo_mode_handoff_runtime.search import main

if __name__ == "__main__":
    print(main())
    raise SystemExit(0)
```

String-returning facades are `search.py`, `distill.py`, and `list_handoffs.py`. All other approved facades are integer-returning.

Use `sys.path.insert(0, str(PLUGIN_ROOT))`, not `PYTHONPATH`, so callers can keep the existing `python "$PLUGIN_ROOT/scripts/<name>.py"` invocation shape. Do not load `scripts._bootstrap`; it is deleted in this plan.

## Task 0: Branch and Baseline

**Files:** none

- [ ] **Step 1: Capture the starting worktree**

Run:

```bash
git status --short > /tmp/handoff-runtime-worktree-baseline.txt
git status --short --ignored > /tmp/handoff-runtime-ignored-baseline.txt
cat /tmp/handoff-runtime-worktree-baseline.txt
cat /tmp/handoff-runtime-ignored-baseline.txt
```

Expected: no unrelated tracked edits. If unrelated tracked edits exist, pause and resolve ownership before continuing.

- [ ] **Step 2: Establish the implementation branch idempotently**

Run:

```bash
git branch --show-current
git log --oneline -3 -- docs/superpowers/plans/2026-05-15-handoff-runtime-package-migration.md
```

Then use exactly one of these branch actions:

- If already on `chore/handoff-runtime-package-migration`, continue.
- If `chore/handoff-runtime-package-migration` already exists, run:

  ```bash
  git switch chore/handoff-runtime-package-migration
  ```

- If the current branch is the plan-only branch that already contains the latest committed version of this plan, run:

  ```bash
  git switch -c chore/handoff-runtime-package-migration
  ```

- Otherwise, switch to the intended base branch first, then run:

  ```bash
  git switch -c chore/handoff-runtime-package-migration
  ```

Expected: current branch is `chore/handoff-runtime-package-migration`, and the branch contains the latest committed version of this plan. Do not create the implementation branch blindly from an unknown current branch.

- [ ] **Step 3: Commit this rewritten plan if it is uncommitted**

Check whether the plan has uncommitted changes:

```bash
git diff -- docs/superpowers/plans/2026-05-15-handoff-runtime-package-migration.md
git diff --cached -- docs/superpowers/plans/2026-05-15-handoff-runtime-package-migration.md
```

If the plan has uncommitted changes, run:

```bash
git add docs/superpowers/plans/2026-05-15-handoff-runtime-package-migration.md
git commit -m "docs: simplify handoff runtime migration plan"
```

Expected: either the plan was already committed and no docs commit is created, or the plan lands as a docs-only commit. Do not treat a no-op commit as a migration failure.

## Task 1: Add Runtime Namespace Guard Tests

**Files:**

- Create: `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`

- [ ] **Step 1: Write failing namespace and facade-scope tests**

Create `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`:

```python
from __future__ import annotations

import ast
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PACKAGE = "turbo_mode_handoff_runtime"
RUNTIME_DIR = PLUGIN_ROOT / RUNTIME_PACKAGE
SCRIPTS_DIR = PLUGIN_ROOT / "scripts"

RUNTIME_MODULES = {
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
}

def _parse(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def test_runtime_module_inventory_is_explicit() -> None:
    assert {p.name for p in RUNTIME_DIR.glob("*.py") if p.name != "__init__.py"} == RUNTIME_MODULES


def test_runtime_modules_do_not_import_scripts_namespace() -> None:
    for path in RUNTIME_DIR.glob("*.py"):
        tree = _parse(path)
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                assert not (node.module or "").startswith("scripts"), path
            if isinstance(node, ast.Import):
                for alias in node.names:
                    assert not alias.name.startswith("scripts"), path
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                assert not node.value.startswith("scripts."), path


def test_runtime_modules_are_import_only() -> None:
    for path in RUNTIME_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        assert not text.startswith("#!"), path
        assert 'if __name__ == "__main__"' not in text, path
```

- [ ] **Step 2: Run the failing tests**

Run:

```bash
uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_runtime_namespace.py -q
```

Expected: fails because `turbo_mode_handoff_runtime/` does not exist yet.

- [ ] **Step 3: Leave the failing tests uncommitted until Task 2**

Do not commit after this task. The guard tests are intentionally written before the runtime package, but the next commit must stay green. Task 2 commits these tests together with the runtime package once they pass.

Expected: `git status --short` shows the new test file as local work.

## Task 2: Move Implementation into Runtime Package

**Files:**

- Create: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/*.py`
- Modify: runtime copies after copying
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/installed_host_harness.py`

- [ ] **Step 1: Copy current implementation files into the runtime package**

Run:

```bash
mkdir -p plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime
cp plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/cleanup.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/defer.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/distill.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/handoff_parsing.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/installed_host_harness.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/list_handoffs.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/plugin_siblings.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/project_paths.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/provenance.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/quality_check.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/search.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/storage_primitives.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/ticket_parsing.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
cp plugins/turbo-mode/handoff/1.6.0/scripts/triage.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/
touch plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/__init__.py
```

Expected: the runtime directory contains copies of the planned runtime modules only. It must not contain `_bootstrap.py`, because `_bootstrap.py` is a deleted script-package compatibility shim, not a runtime module. Do not commit yet.

- [ ] **Step 2: Remove runtime bootstrap preludes and direct-entrypoint blocks**

In every copied runtime module:

- Delete `_load_bootstrap_by_path()` definitions.
- Delete `_load_bootstrap_by_path()` calls.
- Delete `del _load_bootstrap_by_path`.
- Delete shebang lines.
- Delete `if __name__ == "__main__":` blocks.
- Keep each module's `main()` function when it already has one.

Expected: runtime modules are import-only, but CLI-capable modules still expose `main()`. `turbo_mode_handoff_runtime/_bootstrap.py` must not exist.

- [ ] **Step 3: Rewrite runtime imports**

Replace all runtime imports from `scripts.*` with `turbo_mode_handoff_runtime.*`.

Examples:

```python
from turbo_mode_handoff_runtime.storage_primitives import write_json_atomic
from turbo_mode_handoff_runtime.handoff_parsing import parse_handoff
from turbo_mode_handoff_runtime.project_paths import get_project_root
```

Expected: this command prints no matches inside runtime modules:

```bash
rg -n "from scripts\.|import scripts\.|\"scripts\.|scripts\._bootstrap|ensure_plugin_scripts_package" plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime
```

- [ ] **Step 4: Update installed-host harness proof logic**

`installed_host_harness.py` is not a normal library helper. It is the evidence harness for copied installed-host behavior, so do not leave it as a mechanical import rewrite.

In `turbo_mode_handoff_runtime/installed_host_harness.py`, update `_run_helper_probe()` so it proves the reduced architecture explicitly:

- Runtime import proof imports implementation modules from `turbo_mode_handoff_runtime.*`, not `scripts.*`.
- Facade proof executes installed `scripts/*.py` files by path, not by importing `scripts.*`.
- The proof payload no longer uses the stale `loaded_handoff_module_files` key.
- The proof payload renames facade-specific helper keys, such as `resolved_helper_path` and `helper_subprocess_command_paths`, to facade-specific names.
- The probe string imports `subprocess` before it launches the facade smoke command.

During Tasks 2-3, the executed `scripts/session_state.py` path is still the old script implementation. That is acceptable for the green intermediate commits, but it is not final facade proof. Task 4 reruns `tests/test_installed_host_harness.py` after `scripts/session_state.py` becomes a facade.

Use payload names with architecture-specific meaning:

```python
runtime_modules = [
    importlib.import_module("turbo_mode_handoff_runtime.session_state"),
    importlib.import_module("turbo_mode_handoff_runtime.storage_authority"),
]
session_state_facade_path = installed_plugin / "scripts" / "session_state.py"
```

The probe payload should include:

```python
"resolved_facade_path": str(session_state_facade_path.resolve()),
"loaded_runtime_module_files": [
    str(Path(inspect.getfile(module)).resolve())
    for module in runtime_modules
],
"facade_subprocess_command_paths": [
    str(session_state_facade_path.resolve()),
],
```

The probe should also execute the installed facade path at least once from the isolated host root. For `session_state.py`, use `--help` so the command is read-only:

```python
facade_completed = subprocess.run(
    [sys.executable, str(session_state_facade_path), "--help"],
    cwd=cwd,
    env=os.environ.copy(),
    check=False,
    capture_output=True,
    text=True,
)
if facade_completed.returncode != 0:
    raise SystemExit(facade_completed.stderr)
```

Update `verify_source_harness_payload()` to require:

- `resolved_facade_path` is under installed `scripts/`
- every `loaded_runtime_module_files` path is under installed `turbo_mode_handoff_runtime/`
- every `facade_subprocess_command_paths` path is under installed `scripts/`
- no runtime module path or facade command path resolves inside the source checkout

Expected: the harness now proves installed runtime imports and installed facade execution as separate surfaces. It must not prove `scripts.*` import compatibility.

- [ ] **Step 5: Run the runtime import smoke**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=plugins/turbo-mode/handoff/1.6.0 \
  uv run python - <<'PY'
import importlib

modules = [
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
]
for module in modules:
    importlib.import_module(f"turbo_mode_handoff_runtime.{module}")
PY
```

Expected: exits 0.

- [ ] **Step 6: Run the runtime guard tests**

Run:

```bash
uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_runtime_namespace.py -q
```

Expected: passes. If this fails, fix the runtime package before committing.

- [ ] **Step 7: Commit the runtime package and passing guard tests**

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime \
  plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py
git commit -m "refactor: add handoff runtime package"
```

Expected: commit contains the runtime package plus the runtime namespace guard tests, and the committed Handoff test slice is green.

## Task 3: Rewrite Tests to Runtime Imports

**Files:**

- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/*.py`

- [ ] **Step 1: Rewrite implementation-level imports and patches**

In Handoff tests, replace:

```python
from scripts.session_state import load_resume_state
import scripts.active_writes as active_writes
with patch("scripts.search.get_project_name", ...):
```

with:

```python
from turbo_mode_handoff_runtime.session_state import load_resume_state
import turbo_mode_handoff_runtime.active_writes as active_writes
with patch("turbo_mode_handoff_runtime.search.get_project_name", ...):
```

Apply this to all `from scripts.*`, `import scripts.*`, and `patch("scripts.*")` references that test implementation behavior.

- [ ] **Step 2: Keep bootstrap tests unchanged for this task**

Do not delete `tests/test_bootstrap.py` yet. The old script implementations still exist in this task, so the old bootstrap tests should continue to pass until Task 4 intentionally deletes that compatibility layer.

- [ ] **Step 3: Rewrite import-compatibility tests as runtime tests or delete them**

Delete tests that only assert `scripts.*` import compatibility, including `test_search_module_reexports_parse_handoff`.

If behavior still matters, rewrite it against runtime imports:

```python
from turbo_mode_handoff_runtime.search import parse_handoff


def test_search_runtime_exposes_parse_handoff_for_internal_use() -> None:
    assert callable(parse_handoff)
```

- [ ] **Step 4: Keep direct CLI subprocess tests pointed at scripts for now**

Tests that execute `scripts/session_state.py`, `scripts/load_transactions.py`, `scripts/search.py`, `scripts/triage.py`, `scripts/distill.py`, `scripts/defer.py`, `scripts/list_handoffs.py`, or `scripts/plugin_siblings.py` by path should stay pointed at `scripts/`. Those paths still exist and will become facades in Task 4.

- [ ] **Step 5: Move dev-helper tests to runtime imports only**

For `storage_authority_inventory`, use runtime imports for ordinary tests:

```python
from turbo_mode_handoff_runtime.storage_authority_inventory import (
    build_inventory,
    check_inventory,
)
```

Delete subprocess command-mode coverage for `storage_authority_inventory.py`. It is a runtime-only development helper, not a skill facade, so it must not depend on `python -m` or an `if __name__ == "__main__"` block.

Replace the existing check-mode subprocess test with direct function coverage:

```python
def test_storage_authority_inventory_fixture_matches_current_inventory() -> None:
    current = build_inventory(repo_root=REPO_ROOT, plugin_root=PLUGIN_ROOT)
    check_inventory(current, FIXTURE)
```

- [ ] **Step 6: Update installed-host harness tests for the new proof payload**

In `tests/test_installed_host_harness.py`, import from the runtime package:

```python
from turbo_mode_handoff_runtime.installed_host_harness import (
    InstalledHostHarnessError,
    run_source_harness_isolation_proof,
    verify_source_harness_payload,
)
```

Replace `loaded_handoff_module_files` assertions with runtime/facade-specific assertions:

```python
facade_path = Path(proof["resolved_facade_path"])
runtime_module_paths = [
    Path(path) for path in proof["loaded_runtime_module_files"]
]
facade_command_paths = [
    Path(path) for path in proof["facade_subprocess_command_paths"]
]

assert facade_path == installed_plugin / "scripts" / "session_state.py"
assert runtime_module_paths
assert all(
    installed_plugin / "turbo_mode_handoff_runtime" in path.parents
    for path in runtime_module_paths
)
assert facade_command_paths == [
    installed_plugin / "scripts" / "session_state.py"
]
assert "resolved_helper_path" not in proof
assert "loaded_handoff_module_files" not in proof
```

Update payload-rejection fixtures to use the new keys:

```python
"resolved_facade_path": str(source_plugin / "scripts" / "session_state.py"),
"loaded_runtime_module_files": [
    str(source_plugin / "turbo_mode_handoff_runtime" / "session_state.py")
],
"facade_subprocess_command_paths": [
    str(source_plugin / "scripts" / "session_state.py")
],
```

Expected: tests fail if the harness proves old `scripts.*` imports or keeps stale `resolved_helper_path` / `loaded_handoff_module_files` payload keys.

- [ ] **Step 7: Run focused Handoff tests before deleting old scripts**

Before running tests, prove the test import rewrite is complete enough that Task 4 will not discover stale implementation imports after deleting script modules:

```bash
rg -n "from scripts\.|import scripts\.|patch\(\"scripts\." plugins/turbo-mode/handoff/1.6.0/tests
```

Expected: no matches outside `tests/test_bootstrap.py` and direct CLI path strings such as `"$PLUGIN_ROOT/scripts/session_state.py"`. If implementation-level imports remain in files such as `test_active_writes.py`, `test_defer.py`, `test_distill.py`, `test_search.py`, or `test_triage.py`, rewrite them before committing this task.

Run:

```bash
uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest \
  tests/test_runtime_namespace.py \
  tests/test_cli_commands.py \
  tests/test_skill_docs.py \
  tests/test_session_state.py \
  tests/test_load_transactions.py \
  tests/test_storage_authority_inventory.py \
  tests/test_installed_host_harness.py \
  tests/test_bootstrap.py \
  -q
```

Expected: all selected tests pass with runtime-based implementation tests while old scripts still exist, and the stale-import check above has no unexpected matches.

- [ ] **Step 8: Commit the test migration**

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/tests
git commit -m "test: use handoff runtime imports"
```

Expected: commit contains only test changes. No script files are deleted in this commit, so the suite can stay green.

## Task 4: Replace Scripts with Thin CLI Facades

**Files:**

- Modify: retained `plugins/turbo-mode/handoff/1.6.0/scripts/*.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`
- Delete: library-only files under `plugins/turbo-mode/handoff/1.6.0/scripts/`
- Ensure absent: `plugins/turbo-mode/handoff/1.6.0/scripts/__init__.py`
- Delete: `plugins/turbo-mode/handoff/1.6.0/tests/test_bootstrap.py`

- [ ] **Step 1: Extend namespace tests with the facade inventory**

Add this constant and tests to `tests/test_runtime_namespace.py`:

```python
CLI_FACADES = {
    "defer.py",
    "distill.py",
    "list_handoffs.py",
    "load_transactions.py",
    "plugin_siblings.py",
    "search.py",
    "session_state.py",
    "triage.py",
}

STRING_RETURNING_FACADES = {
    "distill.py",
    "list_handoffs.py",
    "search.py",
}

INTEGER_RETURNING_FACADES = CLI_FACADES - STRING_RETURNING_FACADES


def test_scripts_directory_contains_only_cli_facades() -> None:
    assert {p.name for p in SCRIPTS_DIR.glob("*.py")} == CLI_FACADES


def test_cli_facades_use_the_approved_template() -> None:
    for path in SCRIPTS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        module = path.stem
        assert text.startswith("#!/usr/bin/env python3\n"), path
        assert "PLUGIN_ROOT = Path(__file__).resolve().parents[1]" in text, path
        assert "sys.path.insert(0, str(PLUGIN_ROOT))" in text, path
        assert f"from {RUNTIME_PACKAGE}.{module} import main" in text, path
        assert 'if __name__ == "__main__":' in text, path
        if path.name in STRING_RETURNING_FACADES:
            assert "print(main())" in text, path
            assert "raise SystemExit(0)" in text, path
            assert "raise SystemExit(main())" not in text, path
        else:
            assert path.name in INTEGER_RETURNING_FACADES
            assert "raise SystemExit(main())" in text, path
            assert "print(main())" not in text, path
        assert "_bootstrap" not in text, path
        assert "globals().update" not in text, path
```

Do not commit this test extension until the facade conversion below makes it pass.

- [ ] **Step 2: Replace retained script files with facades**

Use the string-returning facade template for:

```text
distill.py
list_handoffs.py
search.py
```

Use the integer-returning facade template for:

```text
defer.py
load_transactions.py
plugin_siblings.py
session_state.py
triage.py
```

For example, `scripts/search.py` must become:

```python
#!/usr/bin/env python3
from __future__ import annotations

import sys
from pathlib import Path

PLUGIN_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PLUGIN_ROOT))

from turbo_mode_handoff_runtime.search import main

if __name__ == "__main__":
    print(main())
    raise SystemExit(0)
```

- [ ] **Step 3: Delete library-only script files and bootstrap tests**

Run:

```bash
if [ -e plugins/turbo-mode/handoff/1.6.0/scripts/__init__.py ]; then
  trash plugins/turbo-mode/handoff/1.6.0/scripts/__init__.py
fi
trash plugins/turbo-mode/handoff/1.6.0/scripts/_bootstrap.py
trash plugins/turbo-mode/handoff/1.6.0/scripts/active_writes.py
trash plugins/turbo-mode/handoff/1.6.0/scripts/cleanup.py
trash plugins/turbo-mode/handoff/1.6.0/scripts/handoff_parsing.py
trash plugins/turbo-mode/handoff/1.6.0/scripts/installed_host_harness.py
trash plugins/turbo-mode/handoff/1.6.0/scripts/project_paths.py
trash plugins/turbo-mode/handoff/1.6.0/scripts/provenance.py
trash plugins/turbo-mode/handoff/1.6.0/scripts/quality_check.py
trash plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py
trash plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py
trash plugins/turbo-mode/handoff/1.6.0/scripts/storage_primitives.py
trash plugins/turbo-mode/handoff/1.6.0/scripts/ticket_parsing.py
trash plugins/turbo-mode/handoff/1.6.0/tests/test_bootstrap.py
```

Expected: `rg --files plugins/turbo-mode/handoff/1.6.0/scripts` lists only the eight approved facades. There is no `scripts/__init__.py`; `scripts.*` is intentionally not a package import API.

- [ ] **Step 4: Run namespace guard tests**

Run:

```bash
uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_runtime_namespace.py -q
```

Expected: passes.

- [ ] **Step 5: Smoke each facade by direct file execution**

Run the stdlib-only state facade with literal direct Python:

```bash
PYTHONDONTWRITEBYTECODE=1 python plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py --help
```

Run the remaining facades through the plugin project environment so dependency-bearing imports such as PyYAML are tested against the declared plugin dependencies, not the developer's global Python:

```bash
PYTHONDONTWRITEBYTECODE=1 uv run --project plugins/turbo-mode/handoff/1.6.0/pyproject.toml python plugins/turbo-mode/handoff/1.6.0/scripts/load_transactions.py --help
PYTHONDONTWRITEBYTECODE=1 uv run --project plugins/turbo-mode/handoff/1.6.0/pyproject.toml python plugins/turbo-mode/handoff/1.6.0/scripts/list_handoffs.py --help
PYTHONDONTWRITEBYTECODE=1 uv run --project plugins/turbo-mode/handoff/1.6.0/pyproject.toml python plugins/turbo-mode/handoff/1.6.0/scripts/search.py --help
PYTHONDONTWRITEBYTECODE=1 uv run --project plugins/turbo-mode/handoff/1.6.0/pyproject.toml python plugins/turbo-mode/handoff/1.6.0/scripts/triage.py --help
PYTHONDONTWRITEBYTECODE=1 uv run --project plugins/turbo-mode/handoff/1.6.0/pyproject.toml python plugins/turbo-mode/handoff/1.6.0/scripts/distill.py --help
PYTHONDONTWRITEBYTECODE=1 uv run --project plugins/turbo-mode/handoff/1.6.0/pyproject.toml python plugins/turbo-mode/handoff/1.6.0/scripts/defer.py --help
PYTHONDONTWRITEBYTECODE=1 uv run --project plugins/turbo-mode/handoff/1.6.0/pyproject.toml python plugins/turbo-mode/handoff/1.6.0/scripts/plugin_siblings.py --help
```

Expected: each command exits 0 and prints usage/help text. A missing global `yaml` package must not block this source migration.

- [ ] **Step 6: Run Handoff tests after deleting old scripts**

Run:

```bash
uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q
```

Expected: the full Handoff plugin suite passes without `tests/test_bootstrap.py`, and the installed-host harness now exercises the actual facade files produced in this task. Do not commit this task from a narrow subset only; deleted library-only script files affect tests beyond the direct CLI and installed-host harness slice.

- [ ] **Step 7: Commit the facade reduction**

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/scripts \
  plugins/turbo-mode/handoff/1.6.0/tests
git commit -m "refactor: keep only handoff cli facades"
```

Expected: commit replaces script implementations with eight facades, deletes `_bootstrap.py`, and deletes bootstrap compatibility tests after no tests depend on deleted library-only script modules.

## Task 5: Update Handoff Docs and Inventory

**Files:**

- Modify: `plugins/turbo-mode/handoff/1.6.0/README.md`
- Modify: `plugins/turbo-mode/handoff/1.6.0/CHANGELOG.md`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority_inventory.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/fixtures/storage_authority_inventory.json`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py`

- [ ] **Step 1: Update README architecture language**

In `README.md`, replace the old `### Scripts` section with a section named:

```markdown
### Runtime Package and CLI Facades
```

State these facts:

- Core logic lives in `turbo_mode_handoff_runtime/`.
- `scripts/` contains only executable CLI facades for skill-invoked commands.
- `scripts.*` is not a library import API.
- Runtime-only helpers such as `quality_check.py`, `cleanup.py`, and `storage_authority_inventory.py` are not wired into Handoff 1.6.0 skill entrypoints or hooks.

- [ ] **Step 2: Update README command table**

The table must list only the eight approved `scripts/*.py` facades as script entrypoints. Move runtime-only helpers to a separate "Runtime-only helpers" paragraph or table.

- [ ] **Step 3: Update release metadata tests**

In `tests/test_release_metadata.py`, retarget policy-code-comment checks from script paths to runtime paths:

```python
PLUGIN_ROOT / "turbo_mode_handoff_runtime" / "cleanup.py"
PLUGIN_ROOT / "turbo_mode_handoff_runtime" / "project_paths.py"
```

- [ ] **Step 4: Update storage authority inventory specs**

In `turbo_mode_handoff_runtime/storage_authority_inventory.py`, change any `InventorySpec` path for moved runtime-only helpers:

```python
InventorySpec(
    path="turbo_mode_handoff_runtime/quality_check.py",
    root="plugin",
    required=("<project_root>/.codex/handoffs/",),
    forbidden=("<project_root>/docs/handoffs/",),
)
```

Do not preserve `scripts/quality_check.py`; it is deleted.

- [ ] **Step 5: Regenerate or check the inventory fixture**

Run:

```bash
PYTHONPATH=plugins/turbo-mode/handoff/1.6.0 uv run python - <<'PY'
from turbo_mode_handoff_runtime.storage_authority_inventory import (
    build_inventory,
    check_inventory,
    default_fixture_path,
    default_plugin_root,
    default_repo_root,
    render_inventory,
)

plugin_root = default_plugin_root()
fixture_path = default_fixture_path(plugin_root)
current = build_inventory(repo_root=default_repo_root(), plugin_root=plugin_root)
fixture_path.parent.mkdir(parents=True, exist_ok=True)
fixture_path.write_text(render_inventory(current), encoding="utf-8")
check_inventory(current, fixture_path)
PY
```

Expected: the import script exits 0, and the fixture points at runtime paths for runtime-only helpers. Do not use `python -m turbo_mode_handoff_runtime.storage_authority_inventory`; runtime modules are import-only and have no `__main__` block.

- [ ] **Step 6: Run docs and inventory tests**

Run:

```bash
uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest \
  tests/test_skill_docs.py \
  tests/test_release_metadata.py \
  tests/test_storage_authority_inventory.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit docs and inventory updates**

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/README.md \
  plugins/turbo-mode/handoff/1.6.0/CHANGELOG.md \
  plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority_inventory.py \
  plugins/turbo-mode/handoff/1.6.0/tests/fixtures/storage_authority_inventory.json \
  plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py
git commit -m "docs: document handoff runtime package"
```

Expected: commit contains only docs, inventory, and metadata-test updates.

## Task 6: Update Refresh Classifier and Smoke Surfaces

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/classifier.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_planner.py`
- Modify: `plugins/turbo-mode/tools/refresh/smoke.py`
- Modify: `plugins/turbo-mode/tools/migration/cache_refresh_wrapper.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/fixtures/handoff_state_helper_doc_migration.json`
- Modify: other fixtures only if tests prove additional fixture drift

- [ ] **Step 1: Classify runtime modules as Handoff source surface**

In `classifier.py`, add runtime module patterns as guarded implementation source:

```python
GUARDED_ONLY_PATTERNS = (
    "handoff/1.6.0/turbo_mode_handoff_runtime/*.py",
    ...
)
```

Add an explicit rule for first-refresh `ADDED` runtime files to return `COVERAGE_GAP` with a reason such as `added-handoff-runtime-package-path`.

- [ ] **Step 2: Keep CLI facades as executable paths**

The eight approved `scripts/*.py` facades remain command-bearing or smoke-relevant where current classifier logic requires it.

Do not treat runtime package files as executable command-bearing paths.

- [ ] **Step 3: Update exact hash contracts**

For Handoff Gate 5 source hash contracts:

- Move contracts for implementation behavior to `handoff/1.6.0/turbo_mode_handoff_runtime/<name>.py`.
- Keep contracts on `scripts/<name>.py` only when the facade path itself is the policy surface.
- Retire contracts for deleted script paths with a named policy reason in comments or test names.

- [ ] **Step 4: Update refresh smoke commands**

In `plugins/turbo-mode/tools/refresh/smoke.py` and `plugins/turbo-mode/tools/migration/cache_refresh_wrapper.py`, keep skill-facing smoke commands pointed at the eight facades:

```python
state.handoff_plugin / "scripts/session_state.py"
state.handoff_plugin / "scripts/defer.py"
state.handoff_plugin / "scripts/search.py"
state.handoff_plugin / "scripts/triage.py"
```

Do not add smoke commands for runtime-only helper files.

- [ ] **Step 5: Update refresh tests**

Update tests so:

- `turbo_mode_handoff_runtime/*.py` appears in discovered Handoff source surfaces.
- `turbo_mode_handoff_runtime/*.py` is not executable or command-bearing.
- `scripts/active_writes.py`, `scripts/storage_authority.py`, `scripts/quality_check.py`, and other deleted script paths are no longer expected live surfaces.
- first-refresh added runtime package files classify as `coverage-gap-blocked`.
- `handoff_state_helper_doc_migration.json` embedded source/cache text no longer contains implementation-level `from scripts.*` imports that would fail the final stale-reference gate. If the fixture intentionally preserves a historical `scripts.*` reference, add a specific explanatory exception to the final stale-reference expected output instead of relying on the generic docs exception.

- [ ] **Step 6: Run refresh test slice**

Run:

```bash
uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_classifier.py \
  plugins/turbo-mode/tools/refresh/tests/test_planner.py \
  plugins/turbo-mode/tools/refresh/tests/test_smoke.py \
  -q
```

Expected: all selected tests pass.

- [ ] **Step 7: Commit refresh updates**

Run:

```bash
git add plugins/turbo-mode/tools/refresh plugins/turbo-mode/tools/migration/cache_refresh_wrapper.py
git commit -m "refactor: classify handoff runtime package"
```

Expected: commit contains classifier, smoke, migration-wrapper, and necessary fixture updates.

## Task 7: Final Verification and Publication Follow-Up

**Files:**

- Modify: PR body or follow-up artifact only if this branch is published

- [ ] **Step 1: Run stale-reference checks**

Run:

```bash
rg -n "from scripts\.|import scripts\.|\"scripts\.|scripts\._bootstrap|ensure_plugin_scripts_package" plugins/turbo-mode/handoff/1.6.0 plugins/turbo-mode/tools
rg -n "scripts/(active_writes|cleanup|handoff_parsing|installed_host_harness|project_paths|provenance|quality_check|storage_authority|storage_authority_inventory|storage_primitives|ticket_parsing)\\.py" plugins/turbo-mode/handoff/1.6.0 plugins/turbo-mode/tools
```

Expected:

- First command has no matches outside docs explaining the removed contract.
- Second command has no matches except historical changelog text that is explicitly historical.

- [ ] **Step 2: Run the full Handoff plugin suite**

Run:

```bash
uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest
```

Expected: full Handoff suite passes.

- [ ] **Step 3: Run refresh tests affected by Handoff source classification**

Run:

```bash
uv run pytest plugins/turbo-mode/tools/refresh/tests -q
```

Expected: refresh suite passes.

- [ ] **Step 4: Run direct facade smoke in a normal repo cwd**

Run:

```bash
uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_cli_commands.py tests/test_session_state.py::test_session_state_cli_round_trip -q
```

Expected: direct script execution through retained facades passes.

- [ ] **Step 5: Check residue against the baseline**

Run:

```bash
find plugins/turbo-mode/handoff/1.6.0 \( -name __pycache__ -o -name '*.pyc' \) -print | sort
git status --short
```

Expected: no new Python cache residue from the migration; git status shows only intended tracked changes before the final commit.

- [ ] **Step 6: Commit final fixes if needed**

If verification required small fixes, commit them:

```bash
git add plugins/turbo-mode/handoff/1.6.0 plugins/turbo-mode/tools
git commit -m "test: verify handoff runtime migration"
```

Expected: no uncommitted migration changes remain.

- [ ] **Step 7: Record installed-cache publication as a separate follow-up**

The source merge creates new runtime package files that installed-cache publication must copy. The PR body or follow-up artifact must state:

```markdown
Installed-cache publication is pending. After source merge, run the approved Turbo Mode publication lane and prove:

- installed cache contains `handoff/1.6.0/turbo_mode_handoff_runtime/*.py`
- installed cache contains only the eight approved `handoff/1.6.0/scripts/*.py` facades
- installed-host harness proof reports installed `loaded_runtime_module_files` and installed `facade_subprocess_command_paths`
- Handoff skill commands execute from the installed cache
- read-only refresh planner no longer reports first-refresh runtime-package coverage gaps
```

Expected: source work does not claim installed-cache certification until that separate lane runs.

## Definition of Done

- `turbo_mode_handoff_runtime/` exists and owns all Handoff implementation.
- `scripts/` contains exactly eight CLI facades.
- `scripts/_bootstrap.py` is deleted.
- No runtime module imports `scripts.*`.
- No runtime module is directly executable.
- Handoff tests import implementation from `turbo_mode_handoff_runtime.*`.
- Direct subprocess tests cover the retained facades.
- Refresh classifier models runtime package files as first-class Handoff source.
- Runtime package files are not classified as executable command-bearing paths.
- Docs state that `scripts/*.py` are CLI facades only, not an import API.
- Full Handoff and affected refresh tests pass.
- Installed-cache publication remains a separate evidenced follow-up.

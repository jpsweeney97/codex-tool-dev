# Handoff Debt Repair Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the Handoff 1.6.0 tech-debt audit into a green-at-each-step repair sequence for CI coverage, release metadata, contributor docs, marker-prefix correctness, facade cleanup, and a scoped follow-up reseam plan.

**Architecture:** Fix release and contributor hygiene before structural code work. Keep source repair separate from installed-cache/runtime claims. Run the Handoff pytest suite before and after each source-bearing task, then stop before the strategic `storage_authority.py` reseam and write a separate plan for that larger extraction.

**Tech Stack:** Python 3.11+, `uv`, pytest, GitHub Actions, standard-library Handoff runtime modules under `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/`, plugin metadata under `.codex-plugin/plugin.json`, and existing Handoff docs/tests.

---

## Source Audit

Input audit:

- `docs/audits/2026-05-15-handoff-debt.md`

Current live-state corrections made while converting the audit:

- Implementation code now lives under `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/`; old `scripts/*.py` implementation-path references in the audit map to this runtime package.
- The current test inventory is 601 collected tests from:

  ```bash
  PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest --collect-only -q -p no:cacheprovider
  ```

- QW3 is still live but partially repaired already: `/summary` exists in some README/runtime docs, but README still has stale install/dev paths, stale test count, missing `/summary` in user-facing capability/skills/type tables, and stale `--package` usage.
- QW2 is still live: `plugin.json`, `pyproject.toml`, and `uv.lock` still say `1.6.0`, while `CHANGELOG.md` still holds BREAKING runtime/storage changes under `[Unreleased]`.
- QW4 is still live: `LEGACY_CONSUMED_PREFIX = "MIGRATED:"` exists in both `storage_authority.py` and `session_state.py`.
- HL1 is still live: `storage_authority.py` still exports six zero-logic active-write proxy functions.
- QW5/WL13 remains no-action for this plan because `hooks/hooks.json` is intentionally empty for Handoff 1.6.0.

## Scope Decisions

- Source tree only. Do not mutate `/Users/jp/.codex/plugins/cache`, installed plugin state, or live app-server runtime inventory.
- This plan can create source files under `.github/` and `plugins/turbo-mode/handoff/1.6.0/`.
- Do not delete generated residue in `.venv`, `.pytest_cache`, `__pycache__`, or `.DS_Store` unless a later cleanup task explicitly scopes it. Report residue if it blocks a clean closeout.
- Use `trash <path>` for any deletion. Never use `rm`.
- CI setup must land before HL1 or ST1 work, because those tasks alter the storage/runtime boundary.
- The strategic `storage_authority.py` reseam is not implemented in this plan. This plan ends by creating or revising a dedicated reseam plan.

## Decision Gates

Gate A, release lane:

- Default lane: cut Handoff `1.7.0`, because current source contains BREAKING changes under `[Unreleased]`.
- Alternate lane: if release/publish evidence proves the current BREAKING source is genuinely unshipped and should remain pending, stop and write a rollback/pending-release plan instead. Do not silently keep BREAKING source under version `1.6.0`.

Gate B, active-write facade:

- Default lane: remove the active-write proxy facade from `storage_authority.py` and update callers to import from `active_writes.py` directly.
- Alternate lane: if the author explicitly confirms `storage_authority.py` is intended as the public active-write facade, stop and rewrite HL1 as facade enforcement through `__init__.py`/docs/tests instead of deleting the proxies.

Gate C, reseam:

- Stop after QW/HL work is green. Do not begin the large `storage_authority.py` extraction until a dedicated reseam plan exists and is reviewed.

## Branch and Commit Boundaries

Use a branch such as:

```bash
git switch -c chore/handoff-debt-repair
```

If already on a scoped branch, continue there. If on `main`, create the branch before source edits.

Use one commit per task:

1. `ci: add handoff plugin test workflow`
2. `docs: repair handoff README development guidance`
3. `chore: release handoff 1.7.0 metadata`
4. `fix: share handoff legacy consumed marker prefix`
5. `refactor: remove handoff active-write facade`
6. `docs: add handoff contributor architecture docs`
7. `docs: plan handoff storage authority reseam`

## File Structure

Create:

- `.github/workflows/handoff-plugin-tests.yml`
- `.github/CODEOWNERS`
- `plugins/turbo-mode/handoff/1.6.0/CONTRIBUTING.md`
- `plugins/turbo-mode/handoff/1.6.0/references/ARCHITECTURE.md`
- `docs/superpowers/plans/2026-05-15-handoff-storage-authority-reseam.md`

Modify:

- `plugins/turbo-mode/handoff/1.6.0/README.md`
- `plugins/turbo-mode/handoff/1.6.0/CHANGELOG.md`
- `plugins/turbo-mode/handoff/1.6.0/.codex-plugin/plugin.json`
- `plugins/turbo-mode/handoff/1.6.0/pyproject.toml`
- `plugins/turbo-mode/handoff/1.6.0/uv.lock`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py`
- `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_load_transactions.py`

---

## Task 0: Baseline and Branch

**Files:** none

- [ ] **Step 1: Confirm branch and dirty state**

Run:

```bash
git status --short --branch
git rev-parse --short HEAD
git branch --show-current
```

Expected: no unrelated tracked edits. If tracked edits exist, inspect them and preserve them.

- [ ] **Step 2: Create or confirm the implementation branch**

If on `main`, run:

```bash
git switch -c chore/handoff-debt-repair
```

Expected: current branch is not `main`.

- [ ] **Step 3: Capture current Handoff test inventory**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest --collect-only -q -p no:cacheprovider
```

Expected: collection succeeds. Current conversion baseline was `601 tests collected`.

## Task 1: Add CI and Test-Suite Readiness

Audit items: QW1, WL7, WL8, WL9.

**Files:**

- Create: `.github/workflows/handoff-plugin-tests.yml`
- Modify: `plugins/turbo-mode/handoff/1.6.0/pyproject.toml`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_load_transactions.py`

- [ ] **Step 1: Add pytest marker configuration**

Append this section to `plugins/turbo-mode/handoff/1.6.0/pyproject.toml`:

```toml
[tool.pytest.ini_options]
markers = [
    "slow: live subprocess or timing-sensitive filesystem contention tests",
]
```

- [ ] **Step 2: Mark the two live contention tests**

Add one line containing `@pytest.mark.slow` immediately above
`def test_active_write_lock_live_contention_with_subprocess(tmp_path: Path) -> None:`
in `tests/test_active_writes.py`.

Add one line containing `@pytest.mark.slow` immediately above
`def test_load_lock_blocks_concurrent_attempt_before_mutation(tmp_path: Path) -> None:`
in `tests/test_load_transactions.py`.

The functions already import `pytest`; do not add a new dependency for markers.

- [ ] **Step 3: Add the GitHub Actions workflow**

Create `.github/workflows/handoff-plugin-tests.yml`:

```yaml
name: Handoff Plugin Tests

on:
  pull_request:
    paths:
      - ".github/workflows/handoff-plugin-tests.yml"
      - "plugins/turbo-mode/handoff/1.6.0/**"
  push:
    branches:
      - main
    paths:
      - ".github/workflows/handoff-plugin-tests.yml"
      - "plugins/turbo-mode/handoff/1.6.0/**"

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - name: Check out repository
        uses: actions/checkout@v4

      - name: Set up Python
        uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install uv
        run: python -m pip install uv

      - name: Collect Handoff tests
        run: |
          PYTHONDONTWRITEBYTECODE=1 \
          PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
          uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest --collect-only -q -p no:cacheprovider

      - name: Run Handoff tests
        run: |
          PYTHONDONTWRITEBYTECODE=1 \
          PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
          uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
```

If the repository later standardizes on a pinned `uv` setup action, replace the `python -m pip install uv` step in a separate CI-hardening commit.

- [ ] **Step 4: Run focused verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_active_writes.py::test_active_write_lock_live_contention_with_subprocess tests/test_load_transactions.py::test_load_lock_blocks_concurrent_attempt_before_mutation -q -p no:cacheprovider
```

Expected: both tests pass.

- [ ] **Step 5: Run full verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
git diff --check
```

Expected: full suite passes; diff check passes.

- [ ] **Step 6: Commit**

Run:

```bash
git add .github/workflows/handoff-plugin-tests.yml plugins/turbo-mode/handoff/1.6.0/pyproject.toml plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py plugins/turbo-mode/handoff/1.6.0/tests/test_load_transactions.py
git commit -m "ci: add handoff plugin test workflow"
```

## Task 2: Repair README Development Guidance

Audit items: QW3, WL1.

**Files:**

- Modify: `plugins/turbo-mode/handoff/1.6.0/README.md`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py`

- [ ] **Step 1: Add a failing metadata/docs test**

Add this test to `plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py`:

```python
def test_readme_documents_current_summary_and_development_commands() -> None:
    text = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")
    assert "codex plugin install ./plugins/turbo-mode/handoff/1.6.0" in text
    assert "cd plugins/turbo-mode/handoff/1.6.0" in text
    assert "uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest" in text
    assert "pytest --collect-only -q" in text
    assert "/summary" in text
    assert "`handoff`, `checkpoint`, or `summary`" in text
    assert "./packages/plugins/handoff" not in text
    assert "cd packages/plugins/handoff" not in text
    assert "uv run --package handoff-plugin pytest" not in text
    assert "354 tests across 10 test modules" not in text
```

- [ ] **Step 2: Fix install and setup paths**

In `README.md`, replace:

```bash
codex plugin install ./packages/plugins/handoff
```

with:

```bash
codex plugin install ./plugins/turbo-mode/handoff/1.6.0
```

Replace:

```bash
cd packages/plugins/handoff
uv sync
```

with:

```bash
cd plugins/turbo-mode/handoff/1.6.0
uv sync
```

- [ ] **Step 3: Fix user-facing `/summary` docs**

Update the capability table so session save/resume names `/summary`, for example:

```markdown
| **Session save/resume** | `/save`, `/load`, `/quicksave`, `/summary` | Create structured handoff documents capturing session state. Resume later with full context. Quicksave for fast checkpoints and summary for medium-depth session capture. |
```

Add this row to the Skills table:

```markdown
| **summary** | `/summary`, "summary", "summarize" | Medium-depth session summary with project arc context. Writes to `<project_root>/.codex/handoffs/`. |
```

Update the State maintenance row to include `/summary`:

```markdown
| **State maintenance** | `/load`, `/save`, `/quicksave`, `/summary` | Manage chain state files during explicit handoff workflows. |
```

Update the frontmatter type row to:

```markdown
| `type` | Yes | `handoff`, `checkpoint`, or `summary` | Document type |
```

- [ ] **Step 4: Fix cleanup requirement wording**

Replace the current requirement:

```markdown
**Requirements:** Python 3.11+, PyYAML 6.0+, `trash` command (for cleanup).
```

with:

```markdown
**Requirements:** Python 3.11+, PyYAML 6.0+. The optional `trash` command is used for recoverable cleanup when available; cleanup falls back to `unlink` with warnings if `trash` is unavailable or fails.
```

- [ ] **Step 5: Fix test command guidance**

Replace the stale hard-coded count and `--package` command with:

````markdown
To inspect the current test inventory:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest --collect-only -q -p no:cacheprovider
```

To run the suite from the repo root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
```

To run a single module from the plugin directory:

```bash
uv run pytest tests/test_defer.py -q
```
````

- [ ] **Step 6: Run focused verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_release_metadata.py -q -p no:cacheprovider
git diff --check
```

Expected: release metadata tests pass; diff check passes.

- [ ] **Step 7: Commit**

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/README.md plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py
git commit -m "docs: repair handoff README development guidance"
```

## Task 3: Cut Handoff 1.7.0 Source Metadata

Audit item: QW2.

**Files:**

- Modify: `plugins/turbo-mode/handoff/1.6.0/.codex-plugin/plugin.json`
- Modify: `plugins/turbo-mode/handoff/1.6.0/pyproject.toml`
- Modify: `plugins/turbo-mode/handoff/1.6.0/uv.lock`
- Modify: `plugins/turbo-mode/handoff/1.6.0/CHANGELOG.md`
- Modify: `plugins/turbo-mode/handoff/1.6.0/README.md`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py`

- [ ] **Step 1: Apply Gate A**

Confirm the release lane. If no release/publish record proves the BREAKING changes are unshipped, continue with `1.7.0`.

- [ ] **Step 2: Make the metadata test version-driven**

Replace the hard-coded test with:

```python
EXPECTED_VERSION = "1.7.0"


def test_versions_are_aligned() -> None:
    plugin_json = json.loads(
        (PLUGIN_ROOT / ".codex-plugin" / "plugin.json").read_text(encoding="utf-8")
    )
    pyproject = tomllib.loads((PLUGIN_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    assert plugin_json["version"] == EXPECTED_VERSION
    assert pyproject["project"]["version"] == EXPECTED_VERSION
```

Update the changelog header test to:

```python
def test_changelog_has_1_7_0_release_header() -> None:
    text = (PLUGIN_ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert re.search(r"^## \[1\.7\.0\] - 2026-05-15$", text, re.MULTILINE), text
    assert re.search(r"^## \[1\.6\.0\] - \d{4}-\d{2}-\d{2}$", text, re.MULTILINE), text
```

- [ ] **Step 3: Update version surfaces**

Set all three version surfaces to `1.7.0`:

```json
"version": "1.7.0"
```

```toml
version = "1.7.0"
```

Then refresh the lockfile:

```bash
uv lock --directory plugins/turbo-mode/handoff/1.6.0
```

Expected: `plugins/turbo-mode/handoff/1.6.0/uv.lock` updates the `handoff-plugin` package version to `1.7.0`.

- [ ] **Step 4: Stamp the changelog**

In `CHANGELOG.md`, change:

```markdown
## [Unreleased]
```

to:

```markdown
## [Unreleased]

## [1.7.0] - 2026-05-15
```

Keep the existing BREAKING storage/runtime-package entries under `1.7.0`, not under `[Unreleased]`.

- [ ] **Step 5: Update README version-history wording**

Replace:

```markdown
| `CHANGELOG.md` | Version history (1.0.0-1.6.0) |
```

with:

```markdown
| `CHANGELOG.md` | Version history (1.0.0-1.7.0) |
```

- [ ] **Step 6: Run verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_release_metadata.py -q -p no:cacheprovider
git diff --check
```

Expected: metadata tests pass; diff check passes.

- [ ] **Step 7: Commit**

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/.codex-plugin/plugin.json plugins/turbo-mode/handoff/1.6.0/pyproject.toml plugins/turbo-mode/handoff/1.6.0/uv.lock plugins/turbo-mode/handoff/1.6.0/CHANGELOG.md plugins/turbo-mode/handoff/1.6.0/README.md plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py
git commit -m "chore: release handoff 1.7.0 metadata"
```

## Task 4: Share the Legacy Consumed Marker Prefix

Audit item: QW4.

**Files:**

- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py`

- [ ] **Step 1: Add the shared primitive constant**

Add this near the top of `storage_primitives.py`, below timeout constants:

```python
LEGACY_CONSUMED_PREFIX = "MIGRATED:"
```

- [ ] **Step 2: Import the constant in `storage_authority.py`**

Add it to the `storage_primitives` import group:

```python
from turbo_mode_handoff_runtime.storage_primitives import (
    LEGACY_CONSUMED_PREFIX,
    read_json_object as _read_json_object_primitive,
    sha256_regular_file_or_none as _content_sha256,
    write_json_atomic as _write_json_atomic,
)
```

Remove the local assignment:

```python
LEGACY_CONSUMED_PREFIX = "MIGRATED:"
```

- [ ] **Step 3: Import the constant in `session_state.py`**

Add:

```python
from turbo_mode_handoff_runtime.storage_primitives import LEGACY_CONSUMED_PREFIX
```

Replace `_LEGACY_CONSUMED_PREFIX` usages with `LEGACY_CONSUMED_PREFIX`, then delete:

```python
_LEGACY_CONSUMED_PREFIX = "MIGRATED:"
```

- [ ] **Step 4: Add a contract test**

Add this test to `tests/test_session_state.py`:

```python
def test_legacy_consumed_prefix_is_shared_with_storage_authority() -> None:
    from turbo_mode_handoff_runtime import storage_primitives
    from turbo_mode_handoff_runtime.storage_authority import LEGACY_CONSUMED_PREFIX as authority_prefix
    from turbo_mode_handoff_runtime.session_state import LEGACY_CONSUMED_PREFIX as state_prefix

    assert storage_primitives.LEGACY_CONSUMED_PREFIX == "MIGRATED:"
    assert authority_prefix == storage_primitives.LEGACY_CONSUMED_PREFIX
    assert state_prefix == storage_primitives.LEGACY_CONSUMED_PREFIX
```

- [ ] **Step 5: Run verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_session_state.py tests/test_storage_authority.py -q -p no:cacheprovider
git diff --check
```

Expected: targeted suites pass; diff check passes.

- [ ] **Step 6: Commit**

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_primitives.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py
git commit -m "fix: share handoff legacy consumed marker prefix"
```

## Task 5: Remove the Active-Write Proxy Facade

Audit item: HL1.

**Files:**

- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py`

- [ ] **Step 1: Apply Gate B**

Continue only if the intended lane is facade removal. If the facade is intentional API isolation, stop and rewrite this task.

- [ ] **Step 2: Add a negative export test**

Add this to `tests/test_storage_authority.py`:

```python
def test_storage_authority_does_not_export_active_write_facade() -> None:
    import turbo_mode_handoff_runtime.storage_authority as storage_authority

    removed_exports = {
        "begin_active_write",
        "allocate_active_path",
        "write_active_handoff",
        "list_active_writes",
        "abandon_active_write",
        "recover_active_write_transaction",
    }
    for name in removed_exports:
        assert not hasattr(storage_authority, name)
```

- [ ] **Step 3: Update session-state active-write imports**

In `session_state.py`, change active-write command branches to import from `active_writes.py` directly.

Use these import shapes in the relevant branches:

```python
from turbo_mode_handoff_runtime.active_writes import allocate_active_path
```

```python
from turbo_mode_handoff_runtime.active_writes import begin_active_write
```

```python
from turbo_mode_handoff_runtime.active_writes import write_active_handoff
```

```python
from turbo_mode_handoff_runtime.active_writes import list_active_writes
```

```python
from turbo_mode_handoff_runtime.active_writes import abandon_active_write
```

```python
from turbo_mode_handoff_runtime.active_writes import recover_active_write_transaction
```

In the branch that imports multiple active-write helpers, import all of them from `turbo_mode_handoff_runtime.active_writes` instead of `storage_authority`.

- [ ] **Step 4: Delete the proxy functions from `storage_authority.py`**

Remove these functions and the now-unused `TYPE_CHECKING` import/guard:

- `begin_active_write`
- `allocate_active_path`
- `write_active_handoff`
- `list_active_writes`
- `abandon_active_write`
- `recover_active_write_transaction`

Keep chain-state and inventory functions in `storage_authority.py`.

- [ ] **Step 5: Run focused verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_storage_authority.py tests/test_session_state.py tests/test_active_writes.py tests/test_runtime_namespace.py -q -p no:cacheprovider
git diff --check
```

Expected: targeted suites pass; diff check passes.

- [ ] **Step 6: Run full suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
```

Expected: full suite passes.

- [ ] **Step 7: Commit**

Run:

```bash
git add plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py plugins/turbo-mode/handoff/1.6.0/tests/test_runtime_namespace.py plugins/turbo-mode/handoff/1.6.0/tests/test_storage_authority.py plugins/turbo-mode/handoff/1.6.0/tests/test_active_writes.py
git commit -m "refactor: remove handoff active-write facade"
```

## Task 6: Add Contributor and Architecture Scaffolding

Audit items: HL2, WL10, WL11.

**Files:**

- Create: `.github/CODEOWNERS`
- Create: `plugins/turbo-mode/handoff/1.6.0/CONTRIBUTING.md`
- Create: `plugins/turbo-mode/handoff/1.6.0/references/ARCHITECTURE.md`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py`
- Modify: `plugins/turbo-mode/handoff/1.6.0/README.md`
- Modify: `plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py`

- [ ] **Step 1: Add CODEOWNERS**

Create `.github/CODEOWNERS`:

```text
plugins/turbo-mode/handoff/ @jpsweeney97
```

- [ ] **Step 2: Add contributor setup instructions**

Create `plugins/turbo-mode/handoff/1.6.0/CONTRIBUTING.md` with:

````markdown
# Contributing to Handoff

Handoff source lives under `plugins/turbo-mode/handoff/1.6.0/`.

## Source Authority

This checkout is source authority for Handoff source files. It is not proof that the installed Codex runtime or local plugin cache has been refreshed.

## Setup

```bash
cd plugins/turbo-mode/handoff/1.6.0
uv sync
```

## Test

From the repository root:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
```

For release metadata and docs-only changes:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_release_metadata.py tests/test_skill_docs.py -q -p no:cacheprovider
```

## Runtime Boundaries

Implementation modules live in `turbo_mode_handoff_runtime/`.
The `scripts/` directory contains executable CLI facades only. Do not add new `scripts.*` import dependencies.

Installed-runtime claims require runtime inventory. Source tests alone prove source behavior only.
````

- [ ] **Step 3: Add architecture map**

Create `plugins/turbo-mode/handoff/1.6.0/references/ARCHITECTURE.md` with these sections:

````markdown
# Handoff Architecture

## Runtime Package

`turbo_mode_handoff_runtime/` contains the implementation. `scripts/` contains only CLI facades used by skills.

## Storage Layout

`storage_authority.py` owns storage layout, candidate discovery, history selection, and chain-state recovery decisions. Primary handoffs live under `.codex/handoffs/`; controlled legacy discovery covers pre-cutover `docs/handoffs/` history.

## Active Writes

`active_writes.py` owns save, quicksave, and summary active-writer reservations. It uses chain-state read/continue operations from `storage_authority.py`, but active-write command callers import active-write helpers directly.

## Load Transactions

`load_transactions.py` owns `/load` mutations: archive source selection, transaction recovery, state-file writes, and legacy-active consumption.

## Chain State Diagnostics

`ChainStateDiagnosticError` payloads are operator-recovery contracts. Recovery codes should remain stable unless tests, skill docs, and this reference change together.

## Legacy Fallback Exit Condition

Legacy `docs/handoffs/` discovery remains only for pre-cutover history. Remove the fallback in the next major release after supported user repositories have migrated or after a documented migration command proves no legacy history remains.
````

- [ ] **Step 4: Expand module docstrings**

Update `storage_authority.py`'s module docstring to name its owned domains:

```python
"""Storage authority for Handoff runtime paths and state transitions.

This module owns storage layout classification, handoff discovery, history
selection, and chain-state recovery diagnostics. Active-write reservation and
write mechanics live in ``active_writes.py``; callers should import those
helpers directly rather than treating this module as an active-write facade.
"""
```

Add a module docstring to `session_state.py`:

```python
"""CLI command dispatcher for Handoff resume state and chain-state operations.

The module keeps command parsing close to the skill-facing CLI contract. Storage
layout and chain-state recovery decisions live in ``storage_authority.py``;
active-writer operations live in ``active_writes.py``.
"""
```

- [ ] **Step 5: Link contributor docs from README**

Add `CONTRIBUTING.md` and `references/ARCHITECTURE.md` to the README references table.

- [ ] **Step 6: Add docs existence test**

Add this to `tests/test_release_metadata.py`:

```python
def test_contributor_architecture_docs_exist_and_are_linked() -> None:
    contributing = PLUGIN_ROOT / "CONTRIBUTING.md"
    architecture = PLUGIN_ROOT / "references" / "ARCHITECTURE.md"
    readme = (PLUGIN_ROOT / "README.md").read_text(encoding="utf-8")

    assert contributing.exists()
    assert architecture.exists()
    assert "CONTRIBUTING.md" in readme
    assert "references/ARCHITECTURE.md" in readme
```

- [ ] **Step 7: Run verification**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest tests/test_release_metadata.py tests/test_runtime_namespace.py -q -p no:cacheprovider
git diff --check
```

Expected: docs tests pass; diff check passes.

- [ ] **Step 8: Commit**

Run:

```bash
git add .github/CODEOWNERS plugins/turbo-mode/handoff/1.6.0/CONTRIBUTING.md plugins/turbo-mode/handoff/1.6.0/references/ARCHITECTURE.md plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/storage_authority.py plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/session_state.py plugins/turbo-mode/handoff/1.6.0/README.md plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py
git commit -m "docs: add handoff contributor architecture docs"
```

## Task 7: Write the Strategic Reseam Follow-Up Plan

Audit items: ST1, WL3, WL5, WL6, WL10, WL11.

**Files:**

- Create: `docs/superpowers/plans/2026-05-15-handoff-storage-authority-reseam.md`

- [ ] **Step 1: Run pre-plan proof**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
```

Expected: full suite passes after Tasks 1-6.

- [ ] **Step 2: Create the reseam control document**

Create `docs/superpowers/plans/2026-05-15-handoff-storage-authority-reseam.md` with this content:

```markdown
# Handoff Storage Authority Reseam Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Split `storage_authority.py` into testable storage-layout and chain-state units without changing Handoff runtime behavior.

**Architecture:** Extract the lowest-risk layout/path arithmetic first, then chain-state lifecycle helpers. Keep candidate discovery and public CLI contracts green after every commit.

**Tech Stack:** Python 3.11+, standard library, existing Handoff pytest suite.

---

## Required Preconditions

- Handoff CI exists and passes.
- Active-write proxy facade has been removed or intentionally enforced.
- `LEGACY_CONSUMED_PREFIX` is shared from `storage_primitives.py`.
- Contributor architecture docs exist.

## Slice Order

1. Extract `storage_layout.py` with `StorageLayout`, `get_storage_layout()`, and path arithmetic only.
2. Move duplicated path/git/lock helpers only when tests prove the ownership boundary.
3. Extract chain-state marker/selection lifecycle after layout extraction is green.
4. Refactor `write_active_handoff` complexity only inside the active-write ownership boundary.
5. Split `session_state.py main()` only after storage reseam is complete and CLI behavior has regression tests.

## Hard Stops

- Stop if any slice requires installed-cache mutation to prove source behavior.
- Stop if a slice changes JSON payload schemas without updating tests and skill/reference docs in the same commit.
- Stop if a task cannot run the full Handoff suite green before commit.
```

- [ ] **Step 3: Commit**

Run:

```bash
git add docs/superpowers/plans/2026-05-15-handoff-storage-authority-reseam.md
git commit -m "docs: plan handoff storage authority reseam"
```

## Final Verification

After all non-strategic repair commits land, run:

```bash
git status --short --branch
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/handoff/1.6.0 pytest -q -p no:cacheprovider
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime plugins/turbo-mode/handoff/1.6.0/tests
git diff --check
```

Expected:

- Full Handoff suite passes.
- Ruff check passes for changed Python surfaces.
- `git diff --check` passes.
- No installed-runtime or cache-refresh success is claimed.

## Audit Routing Table

| Audit item | Plan routing |
|------------|--------------|
| QW1 / SY-3 | Task 1 |
| QW2 / SY-4 | Task 3 |
| QW3 / SY-5 | Task 2 |
| QW4 / SY-13 | Task 4 |
| QW5 / SY-12 | No action in 1.6.0/1.7.0 unless hook wiring changes |
| HL1 / SY-2 | Task 5 |
| HL2 / SY-8 | Task 6 |
| ST1 / SY-1 | Task 7 follow-up plan |
| WL1 / SY-6 | Task 2 |
| WL3 / SY-9 | Task 7 follow-up plan |
| WL5 / SY-11 | Task 7 follow-up plan |
| WL6 / SY-14 | Task 7 follow-up plan |
| WL7 / SY-16 | Task 1 |
| WL8 / SY-17 | Task 1 |
| WL9 / SY-18 | Task 1 as marker/readiness; deeper coverage belongs in reseam follow-up |
| WL10 / SY-19 | Task 6 and Task 7 |
| WL11 / SY-20 | Task 6 and Task 7 |
| WL12 / SY-15 | Task 6 architecture exit-condition note |
| WL13 / SY-12 | No action unless future hook-enablement wires `quality_check.py` |

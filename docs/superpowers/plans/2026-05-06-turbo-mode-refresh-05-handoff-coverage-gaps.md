# Turbo Mode Refresh 05 Handoff Coverage Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current `coverage-gap-blocked` state for the Handoff 1.6.0 direct-Python state-helper documentation drift with a covered guarded-refresh classification and commit-safe evidence.

**Architecture:** Keep the generic command-bearing documentation policy fail-closed, but add one narrow classifier exception for the already-recertified Handoff state-helper skill-doc migration from `uv run ... session_state.py` to direct `python "$PLUGIN_ROOT/scripts/session_state.py"`. The exception is path-bound, command-delta-bound, and text-contract-bound; it produces guarded coverage with explicit smoke labels instead of fast-safe refresh.

**Tech Stack:** Python 3.11+, `uv run pytest`, `ruff`, existing Turbo Mode refresh planner/classifier/commit-safe evidence tooling.

---

## Source Evidence Read

Read these before implementation:

- `plugins/turbo-mode/evidence/refresh/plan04-live-commit-safe-20260506-005230.summary.json`
- `docs/superpowers/plans/2026-05-06-turbo-mode-refresh-04-commit-safe-evidence.md`
- `plugins/turbo-mode/tools/refresh/classifier.py`
- `plugins/turbo-mode/tools/refresh/command_projection.py`
- `plugins/turbo-mode/tools/refresh/planner.py`
- `plugins/turbo-mode/tools/refresh/commit_safe.py`
- `plugins/turbo-mode/tools/refresh/validation.py`
- `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`
- `plugins/turbo-mode/tools/refresh/tests/test_planner.py`
- `plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py`
- `plugins/turbo-mode/tools/refresh/tests/test_validation.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_skill_docs.py`

Current re-anchor command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  --dry-run \
  --inventory-check \
  --run-id plan05-current-gap-reanchor-20260506 \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --codex-home /Users/jp/.codex \
  --json
```

Current result:

- `terminal_plan_status = "coverage-gap-blocked"`
- `runtime_config.state = "aligned"`
- `app_server_inventory_status = "collected"`
- `residue_issues = []`
- Blocking paths:
  - `handoff/1.6.0/skills/load/SKILL.md`
  - `handoff/1.6.0/skills/quicksave/SKILL.md`
  - `handoff/1.6.0/skills/save/SKILL.md`
  - `handoff/1.6.0/skills/summary/SKILL.md`
- Blocking reason codes for each skill doc:
  - `command-shape-changed`
  - `semantic-policy-trigger`
- Non-blocking guarded drift:
  - `handoff/1.6.0/tests/test_session_state.py`
  - `handoff/1.6.0/tests/test_skill_docs.py`

## Scope

Plan 05 implements:

- a narrow classifier coverage rule for Handoff state-helper skill-doc direct-Python migration;
- test coverage proving that exact Handoff skill-doc migration is guarded covered, not fast safe;
- tests preserving generic fail-closed behavior for other command-bearing or semantic-policy doc drift;
- planner test coverage proving the current six-file Handoff drift becomes `guarded-refresh-required`;
- commit-safe allowlist updates for the new sanitized reason code;
- a non-mutating live smoke showing the current state moves from `coverage-gap-blocked` to `guarded-refresh-required`;
- a commit-safe summary generated only after a clean source implementation commit.

Plan 05 does not implement:

- `--refresh`;
- `--guarded-refresh`;
- installed-cache mutation;
- global config mutation;
- process gates;
- locks;
- rollback or recovery;
- post-refresh cache/config certification.

## Design Choice

Recommended approach: **path-bound guarded exception**.

The direct-Python Handoff state-helper change is already source-recertified by Handoff tests. Treating it as a generic command-bearing Markdown change is too coarse, but globally weakening command-bearing doc policy would be unsafe. The classifier should recognize only this command delta on only these four skill docs and return guarded coverage with explicit smoke labels.

Rejected approach: **make all changed skill docs with Handoff tests covered**.

That would let future command-shape or semantic-policy changes bypass the coverage-gap gate whenever tests happen to exist, even if those tests do not prove the new command contract.

Rejected approach: **copy cache manually despite coverage-gap status**.

That would bypass the source/cache refresh planning safety model and flatten the distinction between source recertification and installed-cache mutation readiness.

## File Structure

Modify:

- `plugins/turbo-mode/tools/refresh/classifier.py`
  - Add path-bound detection for Handoff state-helper direct-Python doc migration.
  - Return `MutationMode.GUARDED`, `CoverageStatus.COVERED`, and `PathOutcome.GUARDED_ONLY` for the exact covered doc migration.
  - Attach smoke labels `handoff-state-helper-docs` and `handoff-session-state-write-read-clear`.

- `plugins/turbo-mode/tools/refresh/commit_safe.py`
  - Add the new sanitized reason code to the commit-safe reason allowlist and projection map.

- `plugins/turbo-mode/tools/refresh/validation.py`
  - Add the same reason code to the commit-safe validation allowlist.

- `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`
  - Add positive tests for the four Handoff state-helper skill docs.
  - Add negative tests proving similar command-shape or semantic-trigger doc changes remain coverage gaps.

- `plugins/turbo-mode/tools/refresh/tests/test_planner.py`
  - Add a current-shape fixture where the four Handoff skill docs and two Handoff tests differ from cache and the result is `guarded-refresh-required`.

- `plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py`
  - Add projection coverage for the new reason code.

- `plugins/turbo-mode/tools/refresh/tests/test_validation.py`
  - Add schema/redaction validation coverage for the new reason code.

- `docs/superpowers/plans/2026-05-06-turbo-mode-refresh-05-handoff-coverage-gaps.md`
  - Record completion evidence after implementation.

Create:

- `plugins/turbo-mode/evidence/refresh/$RUN_ID.summary.json`
  - Generated only during Task 6 after the source implementation commit exists.

Do not modify:

- `plugins/turbo-mode/handoff/1.6.0/skills/load/SKILL.md`
- `plugins/turbo-mode/handoff/1.6.0/skills/quicksave/SKILL.md`
- `plugins/turbo-mode/handoff/1.6.0/skills/save/SKILL.md`
- `plugins/turbo-mode/handoff/1.6.0/skills/summary/SKILL.md`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_skill_docs.py`
- installed cache roots under `/Users/jp/.codex/plugins/cache/turbo-mode/`
- `/Users/jp/.codex/config.toml`

## Task 0: Re-Anchor Current State

**Files:**

- No source edits.

- [ ] **Step 1: Verify branch and clean state**

Run:

```bash
git status --short --branch
git rev-parse HEAD
```

Expected:

- branch is an implementation branch created from `main`;
- status has no unstaged or staged source changes before implementation begins.

- [ ] **Step 2: Re-run current dry-run inventory**

Run:

```bash
RUN_ID="plan05-current-gap-reanchor-$(date -u +%Y%m%d-%H%M%S)"
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  --dry-run \
  --inventory-check \
  --run-id "$RUN_ID" \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --codex-home /Users/jp/.codex \
  --json
```

Expected:

- command exits `0`;
- terminal status is still `coverage-gap-blocked`;
- blocking paths are the four Handoff state-helper skill docs;
- the two Handoff tests are guarded-only;
- runtime config and app-server inventory are aligned;
- no residue issues are present.

Stop if blocking paths differ. Update this plan before implementation if the live drift set is no longer exactly the current Handoff state-helper doc/test drift.

## Task 1: Add Narrow Classifier Coverage

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/classifier.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`

- [ ] **Step 1: Add failing classifier tests**

Add tests that construct old-cache and new-source snippets for these exact paths:

```python
@pytest.mark.parametrize(
    "path",
    [
        "handoff/1.6.0/skills/load/SKILL.md",
        "handoff/1.6.0/skills/quicksave/SKILL.md",
        "handoff/1.6.0/skills/save/SKILL.md",
        "handoff/1.6.0/skills/summary/SKILL.md",
    ],
)
def test_handoff_state_helper_direct_python_doc_migration_is_guarded(path: str) -> None:
    source_text = """
Resolve plugin root before running state helpers. Set `PLUGIN_ROOT` to the plugin version root, three levels above this `SKILL.md`, not the `skills/` directory. The literal `python` command must resolve to Python >=3.11.
Run `PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/session_state.py" read-state --state-dir "$PROJECT_ROOT/docs/handoffs/.session-state" --project "$PROJECT_NAME" --field state_path`.
"""
    cache_text = """
Run `PYTHONDONTWRITEBYTECODE=1 UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff-1.6.0" uv run --project "$PLUGIN_ROOT/pyproject.toml" python "$PLUGIN_ROOT/scripts/session_state.py" read-state --state-dir "$PROJECT_ROOT/docs/handoffs/.session-state" --project "$PROJECT_NAME" --field state_path`.
"""

    result = classify_diff_path(
        path,
        kind=DiffKind.CHANGED,
        source_text=source_text,
        cache_text=cache_text,
        executable=False,
    )

    assert result.outcome == PathOutcome.GUARDED_ONLY
    assert result.mutation_mode == MutationMode.GUARDED
    assert result.coverage_status == CoverageStatus.COVERED
    assert "handoff-state-helper-direct-python-doc-migration" in result.reasons
    assert result.smoke == (
        "handoff-state-helper-docs",
        "handoff-session-state-write-read-clear",
    )
```

Add negative tests:

```python
def test_handoff_state_helper_doc_migration_requires_plugin_root_contract() -> None:
    result = classify_diff_path(
        "handoff/1.6.0/skills/save/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text='PYTHONDONTWRITEBYTECODE=1 python "$PLUGIN_ROOT/scripts/session_state.py"\n',
        cache_text='uv run --project "$PLUGIN_ROOT/pyproject.toml" python "$PLUGIN_ROOT/scripts/session_state.py"\n',
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert "command-shape-changed" in result.reasons


def test_unrelated_handoff_command_doc_change_stays_coverage_gap() -> None:
    result = classify_diff_path(
        "handoff/1.6.0/skills/search/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text="Run `python3 scripts/search.py --new-mode`.\n",
        cache_text="Run `python3 scripts/search.py`.\n",
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert "command-shape-changed" in result.reasons
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_classifier.py \
  -q
```

Expected before implementation: the new positive test fails because the classifier still returns `coverage-gap-fail`.

- [ ] **Step 2: Implement the narrow classifier rule**

Add constants near the existing classifier pattern constants:

```python
HANDOFF_STATE_HELPER_SKILL_DOCS = (
    "handoff/1.6.0/skills/load/SKILL.md",
    "handoff/1.6.0/skills/quicksave/SKILL.md",
    "handoff/1.6.0/skills/save/SKILL.md",
    "handoff/1.6.0/skills/summary/SKILL.md",
)

HANDOFF_STATE_HELPER_DOC_SMOKE = (
    "handoff-state-helper-docs",
    "handoff-session-state-write-read-clear",
)
```

Add a helper:

```python
def _is_handoff_state_helper_direct_python_doc_migration(
    path: str,
    *,
    source_text: str,
    cache_text: str,
) -> bool:
    if path not in HANDOFF_STATE_HELPER_SKILL_DOCS:
        return False
    source_projection = extract_command_projection(source_text)
    cache_projection = extract_command_projection(cache_text)
    if source_projection.parser_warnings or cache_projection.parser_warnings:
        return False
    if not any("uv run --project" in item for item in cache_projection.items):
        return False
    if any("uv run --project" in item for item in source_projection.items):
        return False
    if not any('python "$PLUGIN_ROOT/scripts/session_state.py"' in item for item in source_projection.items):
        return False
    required_source_text = (
        "Resolve plugin root",
        "three levels above this `SKILL.md`",
        "not the `skills/` directory",
        "The literal `python` command must resolve to Python >=3.11.",
    )
    return all(fragment in source_text for fragment in required_source_text)
```

Insert the check after executable-doc-surface handling and before generic `_doc_policy_reasons`:

```python
    elif _is_handoff_state_helper_direct_python_doc_migration(
        path,
        source_text=source_text,
        cache_text=cache_text,
    ):
        mutation_mode = MutationMode.GUARDED
        reasons.append("handoff-state-helper-direct-python-doc-migration")
        smoke = HANDOFF_STATE_HELPER_DOC_SMOKE
```

Run the classifier test again:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_classifier.py \
  -q
```

Expected: pass.

## Task 2: Update Commit-Safe Reason Allowlists

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/commit_safe.py`
- Modify: `plugins/turbo-mode/tools/refresh/validation.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_validation.py`

- [ ] **Step 1: Add failing tests for the new reason code**

Add `handoff-state-helper-direct-python-doc-migration` to commit-safe projection and validation tests where reason-code allowlists are asserted.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py \
  plugins/turbo-mode/tools/refresh/tests/test_validation.py \
  -q
```

Expected before implementation: tests fail on an unrecognized reason code.

- [ ] **Step 2: Add the reason code to allowlists**

In both `commit_safe.py` and `validation.py`, add:

```python
"handoff-state-helper-direct-python-doc-migration",
```

In the commit-safe reason projection map, add:

```python
"handoff-state-helper-direct-python-doc-migration": "handoff-state-helper-direct-python-doc-migration",
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py \
  plugins/turbo-mode/tools/refresh/tests/test_validation.py \
  -q
```

Expected: pass.

## Task 3: Add Planner Coverage For Current Drift

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/tests/test_planner.py`

- [ ] **Step 1: Add failing planner test**

Add a test that writes the current source/cache shape into a temporary repo using existing helpers. The fixture must include:

- four changed Handoff state-helper skill docs matching Task 1;
- changed `handoff/1.6.0/tests/test_session_state.py`;
- changed `handoff/1.6.0/tests/test_skill_docs.py`;
- aligned runtime config and marketplace.

Expected assertions:

```python
assert result.terminal_status == TerminalPlanStatus.GUARDED_REFRESH_REQUIRED
assert result.axes.coverage_state == CoverageState.COVERED
assert result.axes.selected_mutation_mode == SelectedMutationMode.GUARDED_REFRESH
assert [item.outcome for item in result.diff_classification] == [
    PathOutcome.GUARDED_ONLY,
    PathOutcome.GUARDED_ONLY,
    PathOutcome.GUARDED_ONLY,
    PathOutcome.GUARDED_ONLY,
    PathOutcome.GUARDED_ONLY,
    PathOutcome.GUARDED_ONLY,
]
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_planner.py::test_plan_refresh_handoff_state_helper_doc_migration_requires_guarded_refresh \
  -q
```

Expected before Task 1 implementation: fail with `coverage-gap-blocked`.

- [ ] **Step 2: Run the planner test after classifier implementation**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_planner.py::test_plan_refresh_handoff_state_helper_doc_migration_requires_guarded_refresh \
  -q
```

Expected: pass.

## Task 4: Source Verification

**Files:**

- No additional source edits unless verification finds defects.

- [ ] **Step 1: Run focused refresh tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Run Handoff source tests that certify the direct-Python docs**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_skill_docs.py \
  -q
```

Expected: all tests pass.

- [ ] **Step 3: Run ruff**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check \
  plugins/turbo-mode/tools/refresh \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  plugins/turbo-mode/tools/refresh_validate_run_metadata.py \
  plugins/turbo-mode/tools/refresh_validate_redaction.py
```

Expected:

```text
All checks passed!
```

- [ ] **Step 4: Run residue gate**

Run:

```bash
find plugins/turbo-mode/handoff/1.6.0 plugins/turbo-mode/ticket/1.4.0 \
  plugins/turbo-mode/tools/refresh \
  -name __pycache__ -o -name '*.pyc' -o -name .pytest_cache \
  -o -name .ruff_cache -o -name .mypy_cache -o -name .venv -o -name .DS_Store
```

Expected: prints nothing.

## Task 5: Source Implementation Commit

**Files:**

- Stage source, tests, and this plan before live commit-safe evidence generation.

- [ ] **Step 1: Create source implementation commit**

Run:

```bash
git status --short --branch
git add \
  plugins/turbo-mode/tools/refresh/classifier.py \
  plugins/turbo-mode/tools/refresh/commit_safe.py \
  plugins/turbo-mode/tools/refresh/validation.py \
  plugins/turbo-mode/tools/refresh/tests/test_classifier.py \
  plugins/turbo-mode/tools/refresh/tests/test_planner.py \
  plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py \
  plugins/turbo-mode/tools/refresh/tests/test_validation.py \
  docs/superpowers/plans/2026-05-06-turbo-mode-refresh-05-handoff-coverage-gaps.md
git commit -m "Cover Handoff state-helper doc refresh drift"
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

Expected:

- commit succeeds on the Plan 05 branch;
- the commit hash is recorded as `source_implementation_commit`;
- the tree hash is recorded as `source_implementation_tree`;
- no generated commit-safe evidence is included in this commit.

## Task 6: Live Non-Mutating Evidence

**Files:**

- Create: `plugins/turbo-mode/evidence/refresh/$RUN_ID.summary.json`
- Modify: `docs/superpowers/plans/2026-05-06-turbo-mode-refresh-05-handoff-coverage-gaps.md`

- [ ] **Step 1: Run live dry-run without commit-safe summary**

Run:

```bash
RUN_ID="plan05-live-handoff-coverage-dry-run-$(date -u +%Y%m%d-%H%M%S)"
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  --dry-run \
  --inventory-check \
  --run-id "$RUN_ID" \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --codex-home /Users/jp/.codex \
  --json
```

Expected:

- command exits `0`;
- terminal status is `guarded-refresh-required`;
- coverage state is `covered`;
- selected mutation mode is `guarded-refresh`;
- app-server inventory is `collected`;
- runtime config remains `aligned`;
- no installed-cache mutation occurs.

- [ ] **Step 2: Run live dry-run with commit-safe summary**

```bash
RUN_ID="plan05-live-handoff-coverage-$(date -u +%Y%m%d-%H%M%S)"
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  --dry-run \
  --inventory-check \
  --record-summary \
  --run-id "$RUN_ID" \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --codex-home /Users/jp/.codex \
  --json
printf '%s\n' "$RUN_ID" > /private/tmp/plan05-handoff-coverage-run-id.txt
```

Expected:

- command exits `0`;
- terminal status is `guarded-refresh-required`;
- commit-safe summary is written to `plugins/turbo-mode/evidence/refresh/$RUN_ID.summary.json`;
- commit-safe summary records `repo_head = source_implementation_commit`;
- commit-safe summary records `repo_tree = source_implementation_tree`;
- summary omits raw app-server transcript and local-only payloads.

- [ ] **Step 3: Verify summary hash and source binding**

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import hashlib
import json
import subprocess

run_id = Path("/private/tmp/plan05-handoff-coverage-run-id.txt").read_text(encoding="utf-8").strip()
source_commit = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
source_tree = subprocess.check_output(["git", "rev-parse", "HEAD^{tree}"], text=True).strip()
summary_path = Path(f"plugins/turbo-mode/evidence/refresh/{run_id}.summary.json")
payload = json.loads(summary_path.read_text(encoding="utf-8"))
actual_hash = hashlib.sha256(summary_path.read_bytes()).hexdigest()
if payload["repo_head"] != source_commit:
    raise SystemExit(f"repo_head mismatch: {payload['repo_head']} != {source_commit}")
if payload["repo_tree"] != source_tree:
    raise SystemExit(f"repo_tree mismatch: {payload['repo_tree']} != {source_tree}")
if payload["terminal_plan_status"] != "guarded-refresh-required":
    raise SystemExit(f"terminal status mismatch: {payload['terminal_plan_status']}")
print(actual_hash)
PY
```

Expected: prints the commit-safe summary SHA256.

## Task 7: Documentation Closeout Commit

**Files:**

- Modify: `docs/superpowers/plans/2026-05-06-turbo-mode-refresh-05-handoff-coverage-gaps.md`
- Create: `plugins/turbo-mode/evidence/refresh/$RUN_ID.summary.json`

- [ ] **Step 1: Record completion evidence**

Append `## Completion Evidence` to this plan with:

- implementation branch;
- source implementation commit hash and tree hash;
- focused refresh test result;
- Handoff source test result;
- ruff result;
- residue result;
- live dry-run status;
- live commit-safe summary path;
- live commit-safe summary SHA256;
- final terminal status;
- explicit note that `guarded-refresh-required` is not refresh completion;
- explicit note that installed-cache mutation remains outside Plan 05.

- [ ] **Step 2: Create evidence/docs commit**

Run:

```bash
RUN_ID="$(cat /private/tmp/plan05-handoff-coverage-run-id.txt)"
git status --short --branch
git add \
  "plugins/turbo-mode/evidence/refresh/$RUN_ID.summary.json" \
  docs/superpowers/plans/2026-05-06-turbo-mode-refresh-05-handoff-coverage-gaps.md
git commit -m "Record Handoff coverage gap closeout evidence"
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

Expected:

- commit succeeds;
- generated summary remains source-commit-bound to `source_implementation_commit`;
- evidence/docs commit records the closeout but does not mutate installed cache.

## Stop Conditions

Stop before implementation or commit if any of these occur:

- current live drift differs from the four Handoff state-helper skill docs plus two Handoff tests;
- runtime config or app-server inventory is not aligned;
- residue issues are present;
- implementation weakens generic command-bearing doc or semantic-policy trigger handling;
- any unrelated Handoff, Ticket, or migration path becomes covered only because it contains similar prose;
- classifier returns `fast-safe-with-covered-smoke` for the Handoff state-helper doc migration;
- new reason code is not allowed by commit-safe validation;
- live dry-run still reports `coverage-gap-blocked` after source implementation;
- live dry-run reports `refresh-allowed` instead of `guarded-refresh-required`;
- any step runs `--refresh` or `--guarded-refresh`;
- any step copies files into `/Users/jp/.codex/plugins/cache/turbo-mode/`;
- any step edits `/Users/jp/.codex/config.toml`;
- generated residue appears and cleanup is not explicitly approved.

## Self-Review Checklist

- [ ] The plan preserves `coverage-gap-blocked`, `guarded-refresh-required`, and refresh completion as separate states.
- [ ] The plan keeps mutation outside scope.
- [ ] The plan is path-bound to the four Handoff state-helper skill docs.
- [ ] Generic command-bearing docs still fail closed.
- [ ] Semantic-policy docs still fail closed unless they exactly match the recertified Handoff state-helper migration.
- [ ] The Handoff tests remain guarded-only drift and do not become fast-safe.
- [ ] Commit-safe reason allowlists include the new reason code.
- [ ] Verification includes refresh tests, Handoff source tests, ruff, residue scan, live dry-run, and commit-safe evidence.

# Turbo Mode Refresh 05 Handoff Coverage Gaps Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the current `coverage-gap-blocked` state for the Handoff 1.6.0 direct-Python state-helper documentation drift with a covered guarded-refresh classification and commit-safe evidence.

**Architecture:** Keep the generic command-bearing documentation policy fail-closed, but add one narrow classifier exception for the already-recertified Handoff state-helper skill-doc migration from `uv run --project "$PLUGIN_ROOT/pyproject.toml" python "$PLUGIN_ROOT/scripts/session_state.py"` to direct `python "$PLUGIN_ROOT/scripts/session_state.py"`. The exception is path-bound, content-hash-bound, projection-bound, and text-contract-bound in production; it produces guarded coverage with advisory smoke labels instead of fast-safe refresh.

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
- `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
- `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`
- `plugins/turbo-mode/tools/refresh/tests/test_planner.py`
- `plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py`
- `plugins/turbo-mode/tools/refresh/tests/test_validation.py`
- `plugins/turbo-mode/tools/refresh/tests/test_cli.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py`
- `plugins/turbo-mode/handoff/1.6.0/tests/test_skill_docs.py`

Historical re-anchor command that produced the current result:

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

Do not rerun the fixed `plan05-current-gap-reanchor-20260506` run id; that local-only evidence directory may already exist. Use Task 0's timestamped run id for live rechecks.

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
- exact per-path source/cache text-hash fixtures for all six current drift paths, with command-projection fixtures for the four Handoff state-helper skill docs;
- production classifier contracts that compare the expected source/cache hashes and expected source/cache projection item tuples;
- test coverage proving that exact Handoff skill-doc migration is guarded covered, not fast safe;
- tests preserving generic fail-closed behavior for other command-bearing or semantic-policy doc drift, including same-path extra commands, added slash commands, wrong state-helper subcommands, unrelated `uv run --project` matches, and added policy-sensitive prose;
- planner test coverage proving the current six-file Handoff drift becomes `guarded-refresh-required`;
- commit-safe allowlist updates for the new sanitized reason code;
- a Plan 05 commit-safe schema/version label for summaries that include the new reason code;
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

Recommended approach: **path-bound, projection-bound guarded exception**.

The direct-Python Handoff state-helper change is already source-recertified by Handoff tests. Treating it as a generic command-bearing Markdown change is too coarse, but globally weakening command-bearing doc policy would be unsafe. The classifier should recognize only the exact current source/cache text hashes and exact command projections for these four skill docs in production, then return guarded coverage with advisory smoke labels. Any extra command item, changed slash-command surface, wrong state-helper subcommand, parser-semantics change, or added policy-sensitive prose must fall back to `_doc_policy_reasons()`.

Rejected approach: **make all changed skill docs with Handoff tests covered**.

That would let future command-shape or semantic-policy changes bypass the coverage-gap gate whenever tests happen to exist, even if those tests do not prove the new command contract.

Rejected approach: **path-bound fragment checks only**.

That would still let future edits to the four blessed paths add commands or policy-sensitive text while retaining the required fragments. This plan requires exact text hashes and exact command projections before bypassing generic document policy.

Rejected approach: **copy cache manually despite coverage-gap status**.

That would bypass the source/cache refresh planning safety model and flatten the distinction between source recertification and installed-cache mutation readiness.

Commit-safe schema decision: **bump the commit-safe schema label to Plan 05**.

Plan 05 expands the commit-safe reason-code enum with `handoff-state-helper-direct-python-doc-migration`, so summaries containing that reason must not continue to claim the Plan 04 commit-safe schema. Update `COMMIT_SAFE_SCHEMA_VERSION` and `EXPECTED_COMMIT_SAFE_SCHEMA_VERSION` from `turbo-mode-refresh-commit-safe-plan-04` to `turbo-mode-refresh-commit-safe-plan-05`. Pre-Plan05 validators are allowed and expected to reject Plan 05 artifacts. Replay and validation for Plan 05 evidence must run from the recorded source implementation commit, which contains the Plan 05 schema label and enum.

Metadata and redaction validator output schema labels stay unchanged in Plan 05. Their payload shapes and redaction contracts are not being expanded by the new classifier reason code; they validate the Plan 05 commit-safe artifact produced by the source implementation commit. Bump those validator summary schema labels only if Task 2 tests show their payload shape or compatibility contract changes.

Plan 05 evidence content must not retain stale Plan 04 provenance labels. Replace omission/source values such as `outside-plan-04` and `plan-04-cli` with Plan 05 or plan-neutral values, update validation allowlists, and test that newly generated Plan 05 candidate/final/published evidence contains neither stale value. Metadata and redaction summary schema names can remain stable, but their payloads must validate the Plan 05 evidence values.

## File Structure

Modify:

- `plugins/turbo-mode/tools/refresh/classifier.py`
  - Add path-bound, content-hash-bound, projection-bound detection for Handoff state-helper direct-Python doc migration.
  - Return `MutationMode.GUARDED`, `CoverageStatus.COVERED`, and `PathOutcome.GUARDED_ONLY` for the exact covered doc migration.
  - Attach advisory smoke labels `handoff-state-helper-docs` and `handoff-session-state-write-read-clear`.

- `plugins/turbo-mode/tools/refresh/commit_safe.py`
  - Bump `COMMIT_SAFE_SCHEMA_VERSION` to `turbo-mode-refresh-commit-safe-plan-05`.
  - Replace stale Plan 04 omission reason values such as `outside-plan-04` with Plan 05 or plan-neutral values.
  - Expand `RELEVANT_DIRTY_PATHS` to include behavior-affecting Handoff and Ticket source surfaces. Do not add the Plan 05 document path to production dirty-state constants; plan cleanliness is enforced by the Task 6 gate.
  - Add the new sanitized reason code to the commit-safe reason allowlist and projection map.

- `plugins/turbo-mode/tools/refresh/validation.py`
  - Bump `EXPECTED_COMMIT_SAFE_SCHEMA_VERSION` to `turbo-mode-refresh-commit-safe-plan-05`.
  - Update omission/source allowlists for the Plan 05 or plan-neutral evidence values.
  - Expand `ALLOWED_DIRTY_RELEVANT_PATHS` to match `commit_safe.RELEVANT_DIRTY_PATHS`.
  - Add the same reason code to the commit-safe validation allowlist.

- `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
  - Add a `--require-terminal-status` guard that fails before `--record-summary` writes commit-safe evidence when the derived terminal status is not the required value.
  - Replace CLI error wording that says mutation commands are "outside Plan 04" with plan-neutral non-mutating refresh-planning wording.
  - Replace redaction validation `--source plan-04-cli` with a Plan 05 or plan-neutral source value.

- `plugins/turbo-mode/tools/refresh_validate_redaction.py`
  - Update validation allowlists or assertions if stale redaction source-value rejection is enforced in the validator instead of only at CLI generation time.

- `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`
  - Add positive tests for the four Handoff state-helper skill docs.
  - Add exact source/cache SHA256 and command-projection fixtures for the four Handoff state-helper skill docs.
  - Add negative tests proving similar command-shape or semantic-trigger doc changes remain coverage gaps.

- `plugins/turbo-mode/tools/refresh/tests/fixtures/handoff_state_helper_doc_migration.json`
  - Store the shared checked-in source/cache fixture consumed by classifier and planner tests.
  - Include all six current Plan 05 drift paths. The four skill-doc entries carry command projections; the two Handoff test-file entries carry exact source/cache hashes so fallback `unmatched-path` coverage cannot absorb unpinned test drift.

- `plugins/turbo-mode/tools/refresh/tests/test_planner.py`
  - Add a current-shape fixture where the four Handoff skill docs and two Handoff tests differ from cache and the result is `guarded-refresh-required`.
  - Assert exact canonical paths, reason codes, smoke labels, and no extra classifications.
  - Keep the two Handoff test-file rows on the current existing classifier reason `unmatched-path` unless this plan is explicitly revised to add exact test-path classifier contracts.

- `plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py`
  - Add projection coverage for the new reason code.
  - Add coverage proving Plan 05 evidence omits stale `outside-plan-04` values.
  - Add coverage proving dirty Handoff and Ticket source paths are relevant dirty paths.

- `plugins/turbo-mode/tools/refresh/tests/test_validation.py`
  - Add schema/redaction validation coverage for the new reason code.
  - Add validation coverage for Plan 05 omission/source values and stale Plan 04 value rejection.
  - Add metadata-validator coverage proving dirty Handoff and Ticket source paths block replay.
  - Add redaction-validator coverage if stale `plan-04-cli` source-value rejection is enforced in `refresh_validate_redaction.py`.

- `plugins/turbo-mode/tools/refresh/tests/test_cli.py`
  - Update commit-safe schema assertions to `turbo-mode-refresh-commit-safe-plan-05`.
  - Add CLI coverage for `--require-terminal-status`.
  - Update any CLI mutation-command wording assertions that intentionally change from Plan 04 wording.
  - Add CLI coverage proving dirty Handoff and Ticket source paths block summary creation.
  - Add CLI coverage proving generated Plan 05 candidate/final/published evidence contains no `outside-plan-04` or `plan-04-cli`.
  - Add CLI coverage proving the local-only run root, including `redaction.summary.json` and `redaction-final-scan.summary.json`, contains no `plan-04-cli`.

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
- status has no staged changes before implementation begins;
- if plan-review repairs are still uncommitted, the only allowed dirty path is `docs/superpowers/plans/2026-05-06-turbo-mode-refresh-05-handoff-coverage-gaps.md`;
- no source, test, evidence, Handoff, Ticket, installed-cache, config, or marketplace file is dirty before implementation begins.

If any path other than this plan is dirty, stop before implementation. Either commit the plan repair first or carry exactly this plan file as the only dirty path into Task 5, where it is staged with the source implementation commit.

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
- `diff_classification` is exactly the six current Plan 05 paths in order, with no extras;
- the four Handoff state-helper skill docs are `coverage-gap-fail` with reasons `command-shape-changed` and `semantic-policy-trigger`;
- the two Handoff tests are `guarded-only` with reason `unmatched-path`;
- runtime config and app-server inventory are aligned;
- no residue issues are present.

If the rerun returns `blocked-preflight` solely because `residue_issues` reports generated residue under `handoff/1.6.0/scripts/__pycache__`, treat that as transient local contamination, not a new Plan 05 drift baseline. The residue scan is directory-sensitive: an empty generated `__pycache__` directory still blocks preflight after the last `.pyc` file is removed. Trash both the generated `.pyc` file and the now-empty `__pycache__` directory from the installed cache, rerun Step 2 with a fresh `RUN_ID`, and continue only after the exact six-path contract returns. Do not patch the expected `diff_classification` contract for this cleanup-only case.

- [ ] **Step 3: Assert exact live drift contract**

Validate the dry-run JSON against the full Plan 05 drift contract, not just blocking paths. Run this immediately after Step 2, using the `RUN_ID` from Step 2:

```bash
RUN_ID="${RUN_ID:?}" python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

run_id = os.environ["RUN_ID"]
summary_path = Path("/Users/jp/.codex/local-only/turbo-mode-refresh") / run_id / "dry-run.summary.json"
payload = json.loads(summary_path.read_text(encoding="utf-8"))

expected = [
    {
        "path": "handoff/1.6.0/skills/load/SKILL.md",
        "outcome": "coverage-gap-fail",
        "reasons": ["command-shape-changed", "semantic-policy-trigger"],
        "smoke": [],
        "source_sha256": "ccbc7a20aa346d6d65e3861b62fd551d37ec44a43538685bfd09ef14b16b5698",
        "cache_sha256": "6cc5f0c631fb03fa310171ca49fec6d40ec59ab9641a342e194180470749f509",
    },
    {
        "path": "handoff/1.6.0/skills/quicksave/SKILL.md",
        "outcome": "coverage-gap-fail",
        "reasons": ["command-shape-changed", "semantic-policy-trigger"],
        "smoke": [],
        "source_sha256": "ac1430c96316f8fa60971bf20a7d55b98b60e03baac73e91cabbf2995cba56aa",
        "cache_sha256": "644b183f4c68a50511b45854f7a3fd7115bcdc5cea8355f9cfb6ff41265d0c8d",
    },
    {
        "path": "handoff/1.6.0/skills/save/SKILL.md",
        "outcome": "coverage-gap-fail",
        "reasons": ["command-shape-changed", "semantic-policy-trigger"],
        "smoke": [],
        "source_sha256": "377609aefd7bd567c68ee71cbd620b0f03a16bcd4e04dd70a9310cc8132f37ae",
        "cache_sha256": "55b8d897a91ac70e119c7299ca294e6028aeffcd71994d7daa096e2c5cd43d85",
    },
    {
        "path": "handoff/1.6.0/skills/summary/SKILL.md",
        "outcome": "coverage-gap-fail",
        "reasons": ["command-shape-changed", "semantic-policy-trigger"],
        "smoke": [],
        "source_sha256": "108c18afd8cf8716b058dbfc1aee8e6db6007f8828025faa74fac16993c576b0",
        "cache_sha256": "ad8c4b0eca09103c4d396238191d0f424abf9b9ee1d47d3b6126d24628f8d5c0",
    },
    {
        "path": "handoff/1.6.0/tests/test_session_state.py",
        "outcome": "guarded-only",
        "reasons": ["unmatched-path"],
        "smoke": [],
        "source_sha256": "4e980b95ab04f8048cdf56f425b8f3fd2e1a34c8a249afe7882921e92d734621",
        "cache_sha256": "9bb409e61e5dfe0009892dd81bc560c1f9df5b98454970bdc74e3c44eae08a01",
    },
    {
        "path": "handoff/1.6.0/tests/test_skill_docs.py",
        "outcome": "guarded-only",
        "reasons": ["unmatched-path"],
        "smoke": [],
        "source_sha256": "11da6eb53ee939367b98989f81150331d11d7b9a77d46a712597d070dec7a742",
        "cache_sha256": "cc76dd71ec190b37e4bd4395eadd122b052a67bafecad781ba34d3b3c0bc6abf",
    },
]

source_root = Path("/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode")
cache_root = Path("/Users/jp/.codex/plugins/cache/turbo-mode")
items = payload["diff_classification"]
if len(items) != len(expected):
    raise SystemExit(f"diff length mismatch: {len(items)} != {len(expected)}")
for item, spec in zip(items, expected):
    if item["canonical_path"] != spec["path"]:
        raise SystemExit(f"path mismatch: {item['canonical_path']} != {spec['path']}")
    if item["outcome"] != spec["outcome"]:
        raise SystemExit(f"outcome mismatch for {spec['path']}: {item['outcome']}")
    if item["reasons"] != spec["reasons"]:
        raise SystemExit(f"reasons mismatch for {spec['path']}: {item['reasons']}")
    if item["smoke"] != spec["smoke"]:
        raise SystemExit(f"smoke mismatch for {spec['path']}: {item['smoke']}")
    source_hash = hashlib.sha256((source_root / spec["path"]).read_bytes()).hexdigest()
    cache_hash = hashlib.sha256((cache_root / spec["path"]).read_bytes()).hexdigest()
    if source_hash != spec["source_sha256"]:
        raise SystemExit(f"source hash mismatch for {spec['path']}: {source_hash}")
    if cache_hash != spec["cache_sha256"]:
        raise SystemExit(f"cache hash mismatch for {spec['path']}: {cache_hash}")
if payload["terminal_plan_status"] != "coverage-gap-blocked":
    raise SystemExit(f"terminal status mismatch: {payload['terminal_plan_status']}")
if payload["axes"]["runtime_config_state"] != "aligned":
    raise SystemExit(f"runtime config mismatch: {payload['axes']['runtime_config_state']}")
if payload["app_server_inventory_status"] != "collected":
    raise SystemExit(f"inventory status mismatch: {payload['app_server_inventory_status']}")
print("Plan 05 live drift contract verified")
PY
```

Stop if any path, outcome, reason code, smoke label, source hash, cache hash, terminal state, runtime config state, or inventory state differs. Update this plan before implementation if the live drift set is no longer exactly the current Handoff state-helper doc/test drift.

## Task 1: Add Narrow Classifier Coverage

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/classifier.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_classifier.py`
- Create: `plugins/turbo-mode/tools/refresh/tests/fixtures/handoff_state_helper_doc_migration.json`

- [ ] **Step 0: Pin exact source/cache projection fixtures**

Before writing the classifier exception, add an exact checked-in JSON fixture for the current six-path source/cache pair at `plugins/turbo-mode/tools/refresh/tests/fixtures/handoff_state_helper_doc_migration.json`. `test_classifier.py` and `test_planner.py` must consume this same fixture; do not duplicate the bulky source/cache contract in multiple test files. Unit tests must not read live files from `/Users/jp/.codex/plugins/cache/turbo-mode/`.

Generate the exact fixture from current source/cache files with:

```bash
env PYTHONDONTWRITEBYTECODE=1 python - <<'PY'
import hashlib
import json
import sys
from pathlib import Path

sys.path.insert(0, "/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/tools")
from refresh.command_projection import extract_command_projection, has_semantic_policy_trigger

repo = Path("/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode")
cache = Path("/Users/jp/.codex/plugins/cache/turbo-mode")
paths = [
    "handoff/1.6.0/skills/load/SKILL.md",
    "handoff/1.6.0/skills/quicksave/SKILL.md",
    "handoff/1.6.0/skills/save/SKILL.md",
    "handoff/1.6.0/skills/summary/SKILL.md",
    "handoff/1.6.0/tests/test_session_state.py",
    "handoff/1.6.0/tests/test_skill_docs.py",
]
payload = {}
for path in paths:
    source_text = (repo / path).read_text(encoding="utf-8")
    cache_text = (cache / path).read_text(encoding="utf-8")
    source_projection = extract_command_projection(source_text)
    cache_projection = extract_command_projection(cache_text)
    payload[path] = {
        "source_text": source_text,
        "cache_text": cache_text,
        "source_sha256": hashlib.sha256(source_text.encode("utf-8")).hexdigest(),
        "cache_sha256": hashlib.sha256(cache_text.encode("utf-8")).hexdigest(),
        "source_items": source_projection.items,
        "cache_items": cache_projection.items,
        "source_parser_warnings": source_projection.parser_warnings,
        "cache_parser_warnings": cache_projection.parser_warnings,
        "source_semantic_policy_trigger": has_semantic_policy_trigger(source_text),
        "cache_semantic_policy_trigger": has_semantic_policy_trigger(cache_text),
    }
print(json.dumps(payload, indent=2, sort_keys=True))
PY
```

Copy the full generated output into `plugins/turbo-mode/tools/refresh/tests/fixtures/handoff_state_helper_doc_migration.json`. Do not shorten it, normalize it by hand, or replace it with required-fragment checks. The expected hashes for the generated fixture are:

| Path | Source SHA256 | Cache SHA256 |
| --- | --- | --- |
| `handoff/1.6.0/skills/load/SKILL.md` | `ccbc7a20aa346d6d65e3861b62fd551d37ec44a43538685bfd09ef14b16b5698` | `6cc5f0c631fb03fa310171ca49fec6d40ec59ab9641a342e194180470749f509` |
| `handoff/1.6.0/skills/quicksave/SKILL.md` | `ac1430c96316f8fa60971bf20a7d55b98b60e03baac73e91cabbf2995cba56aa` | `644b183f4c68a50511b45854f7a3fd7115bcdc5cea8355f9cfb6ff41265d0c8d` |
| `handoff/1.6.0/skills/save/SKILL.md` | `377609aefd7bd567c68ee71cbd620b0f03a16bcd4e04dd70a9310cc8132f37ae` | `55b8d897a91ac70e119c7299ca294e6028aeffcd71994d7daa096e2c5cd43d85` |
| `handoff/1.6.0/skills/summary/SKILL.md` | `108c18afd8cf8716b058dbfc1aee8e6db6007f8828025faa74fac16993c576b0` | `ad8c4b0eca09103c4d396238191d0f424abf9b9ee1d47d3b6126d24628f8d5c0` |
| `handoff/1.6.0/tests/test_session_state.py` | `4e980b95ab04f8048cdf56f425b8f3fd2e1a34c8a249afe7882921e92d734621` | `9bb409e61e5dfe0009892dd81bc560c1f9df5b98454970bdc74e3c44eae08a01` |
| `handoff/1.6.0/tests/test_skill_docs.py` | `11da6eb53ee939367b98989f81150331d11d7b9a77d46a712597d070dec7a742` | `cc76dd71ec190b37e4bd4395eadd122b052a67bafecad781ba34d3b3c0bc6abf` |

Stop before implementation if any generated `source_sha256` or `cache_sha256` differs from this table, even if the live dry-run still reports the same six drift paths. A hash mismatch means the source/cache evidence boundary changed and this plan must be patched before execution.

Load the fixture in tests through a shared helper, for example:

```python
import json
from pathlib import Path


HANDOFF_STATE_HELPER_DOC_FIXTURES = json.loads(
    (
        Path(__file__).parent
        / "fixtures"
        / "handoff_state_helper_doc_migration.json"
    ).read_text(encoding="utf-8")
)
```

- [ ] **Step 1: Add failing classifier tests**

Add tests that use the exact fixture source/cache text and assert both the projections and the classifier outcome for these exact paths:

Update imports in `test_classifier.py` to include `json`, `CommandProjection`, and `has_semantic_policy_trigger`.

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
    contract = HANDOFF_STATE_HELPER_DOC_FIXTURES[path]
    source_text = contract["source_text"]
    cache_text = contract["cache_text"]

    assert _sha256(source_text) == contract["source_sha256"]
    assert _sha256(cache_text) == contract["cache_sha256"]
    assert extract_command_projection(source_text).items == tuple(contract["source_items"])
    assert extract_command_projection(cache_text).items == tuple(contract["cache_items"])
    assert extract_command_projection(source_text).parser_warnings == tuple(contract["source_parser_warnings"])
    assert extract_command_projection(cache_text).parser_warnings == tuple(contract["cache_parser_warnings"])
    assert contract["source_parser_warnings"] == []
    assert contract["cache_parser_warnings"] == []
    assert has_semantic_policy_trigger(source_text) is contract["source_semantic_policy_trigger"]
    assert has_semantic_policy_trigger(cache_text) is contract["cache_semantic_policy_trigger"]

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
def test_handoff_state_helper_doc_migration_rejects_extra_command_item() -> None:
    contract = HANDOFF_STATE_HELPER_DOC_FIXTURES["handoff/1.6.0/skills/save/SKILL.md"]
    result = classify_diff_path(
        "handoff/1.6.0/skills/save/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=contract["source_text"] + "\nRun `python \"$PLUGIN_ROOT/scripts/session_state.py\" prune-state --state-dir \"$PROJECT_ROOT/docs/handoffs/.session-state\"`.\n",
        cache_text=contract["cache_text"],
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert "command-shape-changed" in result.reasons


def test_handoff_state_helper_doc_migration_rejects_added_slash_command() -> None:
    contract = HANDOFF_STATE_HELPER_DOC_FIXTURES["handoff/1.6.0/skills/load/SKILL.md"]
    result = classify_diff_path(
        "handoff/1.6.0/skills/load/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=contract["source_text"] + "\nUse `/summary` if loading is ambiguous.\n",
        cache_text=contract["cache_text"],
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert "command-shape-changed" in result.reasons


def test_handoff_state_helper_doc_migration_rejects_added_policy_text() -> None:
    contract = HANDOFF_STATE_HELPER_DOC_FIXTURES["handoff/1.6.0/skills/quicksave/SKILL.md"]
    result = classify_diff_path(
        "handoff/1.6.0/skills/quicksave/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=contract["source_text"] + "\nRollback and recovery hooks must be approved by the operator.\n",
        cache_text=contract["cache_text"],
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert "semantic-policy-trigger" in result.reasons


def test_handoff_state_helper_doc_migration_requires_exact_state_helper_command() -> None:
    contract = HANDOFF_STATE_HELPER_DOC_FIXTURES["handoff/1.6.0/skills/summary/SKILL.md"]
    result = classify_diff_path(
        "handoff/1.6.0/skills/summary/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=contract["source_text"].replace("read-state \\", "repair-state \\"),
        cache_text=contract["cache_text"],
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
    assert "command-shape-changed" in result.reasons


def test_unrelated_uv_run_state_helper_doc_change_stays_coverage_gap() -> None:
    result = classify_diff_path(
        "handoff/1.6.0/skills/search/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text='Run `uv run --project "$PLUGIN_ROOT/pyproject.toml" python "$PLUGIN_ROOT/scripts/session_state.py" read-state`.\n',
        cache_text="Run `python3 scripts/search.py`.\n",
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


def test_handoff_state_helper_doc_migration_rejects_projection_parser_warning(monkeypatch: pytest.MonkeyPatch) -> None:
    contract = HANDOFF_STATE_HELPER_DOC_FIXTURES["handoff/1.6.0/skills/save/SKILL.md"]
    original_extract = extract_command_projection

    def warn_for_same_bytes(text: str) -> CommandProjection:
        projection = original_extract(text)
        return CommandProjection(
            items=projection.items,
            parser_warnings=("json-payload-parse-failed",),
        )

    monkeypatch.setattr(
        "refresh.classifier.extract_command_projection",
        warn_for_same_bytes,
    )
    result = classify_diff_path(
        "handoff/1.6.0/skills/save/SKILL.md",
        kind=DiffKind.CHANGED,
        source_text=contract["source_text"],
        cache_text=contract["cache_text"],
        executable=False,
    )

    assert result.outcome == PathOutcome.COVERAGE_GAP_FAIL
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_classifier.py \
  -q
```

Expected before implementation: the new positive test fails because the classifier still returns `coverage-gap-fail`.

- [ ] **Step 2: Implement the narrow classifier rule**

Add `hashlib` and a small frozen contract type near the existing classifier pattern constants:

```python
import hashlib
from dataclasses import dataclass


@dataclass(frozen=True)
class HandoffStateHelperDocContract:
    source_sha256: str
    cache_sha256: str
    source_items: tuple[str, ...]
    cache_items: tuple[str, ...]
    source_parser_warnings: tuple[str, ...]
    cache_parser_warnings: tuple[str, ...]
    source_semantic_policy_trigger: bool
    cache_semantic_policy_trigger: bool


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

The production `HANDOFF_STATE_HELPER_DOC_CONTRACTS` entries must contain concrete `source_items`, `cache_items`, `source_parser_warnings`, and `cache_parser_warnings` tuples for all four paths, copied from the Step 0 fixture output. Do not leave comments, empty tuples, generated-at-runtime reads, or abbreviated placeholders in the implementation.

Add a helper:

```python
def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _is_handoff_state_helper_direct_python_doc_migration(
    path: str,
    *,
    source_text: str,
    cache_text: str,
) -> bool:
    contract = HANDOFF_STATE_HELPER_DOC_CONTRACTS.get(path)
    if contract is None:
        return False
    if _sha256_text(source_text) != contract.source_sha256:
        return False
    if _sha256_text(cache_text) != contract.cache_sha256:
        return False

    source_projection = extract_command_projection(source_text)
    cache_projection = extract_command_projection(cache_text)
    if source_projection.parser_warnings != contract.source_parser_warnings:
        return False
    if cache_projection.parser_warnings != contract.cache_parser_warnings:
        return False
    if source_projection.parser_warnings or cache_projection.parser_warnings:
        return False
    if source_projection.items != contract.source_items:
        return False
    if cache_projection.items != contract.cache_items:
        return False
    if has_semantic_policy_trigger(source_text) is not contract.source_semantic_policy_trigger:
        return False
    if has_semantic_policy_trigger(cache_text) is not contract.cache_semantic_policy_trigger:
        return False
    return True
```

Do not implement this helper with substring checks such as `any("uv run --project" in item ...)`. The production guard must compare both exact source/cache content hashes and exact source/cache command projection tuples. If `extract_command_projection()` later changes parser semantics for the same bytes, the tuple comparison must fail closed instead of silently accepting the old hash pair.

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

## Task 2: Update Commit-Safe Schema And Reason Allowlists

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/commit_safe.py`
- Modify: `plugins/turbo-mode/tools/refresh/validation.py`
- Modify: `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_validation.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_cli.py`

- [ ] **Step 1: Add failing tests for the Plan 05 schema label and new reason code**

Add tests that assert:

- `commit_safe.COMMIT_SAFE_SCHEMA_VERSION == "turbo-mode-refresh-commit-safe-plan-05"`;
- `validation.EXPECTED_COMMIT_SAFE_SCHEMA_VERSION == "turbo-mode-refresh-commit-safe-plan-05"`;
- generated commit-safe summaries for Plan 05 use schema version `turbo-mode-refresh-commit-safe-plan-05`;
- validation accepts `handoff-state-helper-direct-python-doc-migration` only under the Plan 05 commit-safe schema;
- a summary that claims `turbo-mode-refresh-commit-safe-plan-04` while containing `handoff-state-helper-direct-python-doc-migration` is rejected.
- `test_cli.py` expects `turbo-mode-refresh-commit-safe-plan-05` for candidate, final, and published commit-safe summaries.
- `refresh_installed_turbo_mode.py --record-summary --require-terminal-status guarded-refresh-required` does not write a local-only run directory or candidate/final/published commit-safe summary when the derived terminal status differs.
- CLI mutation-command rejection wording is plan-neutral, not "outside Plan 04".
- generated Plan 05 candidate, final, and published summaries do not contain `outside-plan-04` or `plan-04-cli`.
- generated local-only Plan 05 evidence, including `redaction.summary.json`, `redaction-final-scan.summary.json`, and the whole run root, does not contain `plan-04-cli`.
- dirty `plugins/turbo-mode/handoff/1.6.0` and `plugins/turbo-mode/ticket/1.4.0` paths block summary creation and metadata validation replay. The Plan 05 document path is checked by Task 6 Step 3, not production dirty-state constants.

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py \
  plugins/turbo-mode/tools/refresh/tests/test_validation.py \
  plugins/turbo-mode/tools/refresh/tests/test_cli.py \
  -q
```

Expected before implementation: tests fail on the old Plan 04 schema label, unrecognized reason code, missing `--require-terminal-status` support, old mutation-command wording, stale `outside-plan-04` / `plan-04-cli` values, and missing dirty-path enforcement for Handoff and Ticket source paths. This plan remains enforced by the Task 6 Step 3 clean-source gate, not production dirty-state constants.

- [ ] **Step 2: Bump commit-safe schema labels and add the reason code to allowlists**

In `commit_safe.py`, update:

```python
COMMIT_SAFE_SCHEMA_VERSION = "turbo-mode-refresh-commit-safe-plan-05"
```

In `validation.py`, update:

```python
EXPECTED_COMMIT_SAFE_SCHEMA_VERSION = "turbo-mode-refresh-commit-safe-plan-05"
```

In both `commit_safe.py` and `validation.py`, add:

```python
"handoff-state-helper-direct-python-doc-migration",
```

In the commit-safe reason projection map, add:

```python
"handoff-state-helper-direct-python-doc-migration": "handoff-state-helper-direct-python-doc-migration",
```

Do not keep the Plan 04 commit-safe schema label for artifacts that contain the Plan 05 reason code. The local-only source summary schema remains unchanged unless a test proves it also needs a Plan 05 label.

Replace Plan 04 evidence values with Plan 05 or plan-neutral values:

```python
"outside-plan-04" -> "outside-non-mutating-refresh-plan"
"plan-04-cli" -> "plan-05-cli"
```

Update validation allowlists to accept the new values and reject the stale values for Plan 05 artifacts. The exact replacement strings can be renamed if the tests use a clearer Plan 05 or plan-neutral value, but newly generated Plan 05 evidence must not contain `outside-plan-04` or `plan-04-cli`.

Expand the production dirty-state constants in both `commit_safe.py` and `validation.py` to behavior-affecting source surfaces only:

```python
RELEVANT_DIRTY_PATHS = (
    ".agents/plugins/marketplace.json",
    "plugins/turbo-mode/handoff/1.6.0",
    "plugins/turbo-mode/ticket/1.4.0",
    "plugins/turbo-mode/tools/refresh",
    "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py",
    "plugins/turbo-mode/tools/refresh_validate_run_metadata.py",
    "plugins/turbo-mode/tools/refresh_validate_redaction.py",
)
```

Keep `validation.ALLOWED_DIRTY_RELEVANT_PATHS` exactly aligned with `commit_safe.RELEVANT_DIRTY_PATHS`.

Do not include `docs/superpowers/plans/2026-05-06-turbo-mode-refresh-05-handoff-coverage-gaps.md` in these production constants. That file is Plan 05 operator evidence, not a recurring behavior-affecting source surface. Task 6 Step 3 still requires it to be clean before commit-safe evidence is recorded.

In `refresh_installed_turbo_mode.py`, add the required-status guard:

```python
parser.add_argument("--require-terminal-status")
```

Immediately after `result = plan_refresh(...)` is derived, and before `write_local_evidence(...)` or any `--record-summary` path writes local-only, candidate, final, or published summaries, reject mismatches:

```python
if args.require_terminal_status is not None:
    terminal_status = result.terminal_status.value
    if terminal_status != args.require_terminal_status:
        raise RefreshError(
            "required terminal status mismatch: "
            f"expected {args.require_terminal_status!r}, got {terminal_status!r}"
        )
```

Also replace:

```python
parser.error("--refresh and --guarded-refresh are outside Plan 04")
```

with plan-neutral wording:

```python
parser.error("--refresh and --guarded-refresh are outside non-mutating refresh planning")
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py \
  plugins/turbo-mode/tools/refresh/tests/test_validation.py \
  plugins/turbo-mode/tools/refresh/tests/test_cli.py \
  -q
```

Expected: pass.

## Task 3: Add Planner Coverage For Current Drift

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/tests/test_planner.py`

- [ ] **Step 1: Add failing planner test**

Add a test that writes the current source/cache shape into a temporary repo using existing helpers. The fixture must include:

- four changed Handoff state-helper skill docs loaded from `plugins/turbo-mode/tools/refresh/tests/fixtures/handoff_state_helper_doc_migration.json`;
- changed `handoff/1.6.0/tests/test_session_state.py`;
- changed `handoff/1.6.0/tests/test_skill_docs.py`;
- aligned runtime config, marketplace, and app-server inventory.

Do not regenerate or inline a second copy of the Handoff skill-doc fixture in `test_planner.py`; use the same checked-in JSON fixture that `test_classifier.py` consumes.

Invoke `plan_refresh()` with `inventory_check=True` and an aligned inventory collector so the planner can prove runtime alignment instead of downgrading aligned config to `UNCHECKED`:

```python
result = plan_refresh(
    repo_root=repo_root,
    codex_home=codex_home,
    mode="dry-run",
    inventory_check=True,
    inventory_collector=lambda _paths: (aligned_inventory(), ({"direction": "recv"},)),
)
```

Expected assertions:

```python
expected_paths = [
    "handoff/1.6.0/skills/load/SKILL.md",
    "handoff/1.6.0/skills/quicksave/SKILL.md",
    "handoff/1.6.0/skills/save/SKILL.md",
    "handoff/1.6.0/skills/summary/SKILL.md",
    "handoff/1.6.0/tests/test_session_state.py",
    "handoff/1.6.0/tests/test_skill_docs.py",
]

assert result.terminal_status == TerminalPlanStatus.GUARDED_REFRESH_REQUIRED
assert result.axes.coverage_state == CoverageState.COVERED
assert result.axes.selected_mutation_mode == SelectedMutationMode.GUARDED_REFRESH
assert [item.canonical_path for item in result.diff_classification] == expected_paths
assert [item.outcome for item in result.diff_classification] == [
    PathOutcome.GUARDED_ONLY,
    PathOutcome.GUARDED_ONLY,
    PathOutcome.GUARDED_ONLY,
    PathOutcome.GUARDED_ONLY,
    PathOutcome.GUARDED_ONLY,
    PathOutcome.GUARDED_ONLY,
]

for item in result.diff_classification[:4]:
    assert item.reasons == ("handoff-state-helper-direct-python-doc-migration",)
    assert item.smoke == (
        "handoff-state-helper-docs",
        "handoff-session-state-write-read-clear",
    )

for item in result.diff_classification[4:]:
    assert item.reasons == ("unmatched-path",)
    assert item.smoke == ()
```

The two Handoff test-file rows are guarded-only by current fallback behavior, not by `GUARDED_ONLY_PATTERNS`. Do not broaden `GUARDED_ONLY_PATTERNS` or add new classifier policy for those test paths unless this plan is patched with exact path-level classifier tests for that new contract.

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

Expected:

- all refresh tests pass, including `plugins/turbo-mode/tools/refresh/tests/test_cli.py`;
- no test still expects `turbo-mode-refresh-commit-safe-plan-04` for newly generated Plan 05 commit-safe summaries;
- CLI tests prove `--require-terminal-status` prevents `--record-summary` from writing evidence for the wrong terminal status.

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
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  plugins/turbo-mode/tools/refresh_validate_redaction.py \
  plugins/turbo-mode/tools/refresh/tests/test_classifier.py \
  plugins/turbo-mode/tools/refresh/tests/test_planner.py \
  plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py \
  plugins/turbo-mode/tools/refresh/tests/test_validation.py \
  plugins/turbo-mode/tools/refresh/tests/test_cli.py \
  plugins/turbo-mode/tools/refresh/tests/fixtures/handoff_state_helper_doc_migration.json \
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
- No plan edits during Task 6 before the clean-source gate. Completion notes are recorded later in Task 7.

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

- [ ] **Step 2: Assert exact post-implementation drift contract**

Validate the post-implementation dry-run JSON against the full Plan 05 drift contract. Run this immediately after Step 1, using the `RUN_ID` from Step 1:

```bash
RUN_ID="${RUN_ID:?}" python3 - <<'PY'
import hashlib
import json
import os
from pathlib import Path

run_id = os.environ["RUN_ID"]
summary_path = Path("/Users/jp/.codex/local-only/turbo-mode-refresh") / run_id / "dry-run.summary.json"
payload = json.loads(summary_path.read_text(encoding="utf-8"))

expected = [
    {
        "path": "handoff/1.6.0/skills/load/SKILL.md",
        "outcome": "guarded-only",
        "reasons": ["handoff-state-helper-direct-python-doc-migration"],
        "smoke": ["handoff-state-helper-docs", "handoff-session-state-write-read-clear"],
        "source_sha256": "ccbc7a20aa346d6d65e3861b62fd551d37ec44a43538685bfd09ef14b16b5698",
        "cache_sha256": "6cc5f0c631fb03fa310171ca49fec6d40ec59ab9641a342e194180470749f509",
    },
    {
        "path": "handoff/1.6.0/skills/quicksave/SKILL.md",
        "outcome": "guarded-only",
        "reasons": ["handoff-state-helper-direct-python-doc-migration"],
        "smoke": ["handoff-state-helper-docs", "handoff-session-state-write-read-clear"],
        "source_sha256": "ac1430c96316f8fa60971bf20a7d55b98b60e03baac73e91cabbf2995cba56aa",
        "cache_sha256": "644b183f4c68a50511b45854f7a3fd7115bcdc5cea8355f9cfb6ff41265d0c8d",
    },
    {
        "path": "handoff/1.6.0/skills/save/SKILL.md",
        "outcome": "guarded-only",
        "reasons": ["handoff-state-helper-direct-python-doc-migration"],
        "smoke": ["handoff-state-helper-docs", "handoff-session-state-write-read-clear"],
        "source_sha256": "377609aefd7bd567c68ee71cbd620b0f03a16bcd4e04dd70a9310cc8132f37ae",
        "cache_sha256": "55b8d897a91ac70e119c7299ca294e6028aeffcd71994d7daa096e2c5cd43d85",
    },
    {
        "path": "handoff/1.6.0/skills/summary/SKILL.md",
        "outcome": "guarded-only",
        "reasons": ["handoff-state-helper-direct-python-doc-migration"],
        "smoke": ["handoff-state-helper-docs", "handoff-session-state-write-read-clear"],
        "source_sha256": "108c18afd8cf8716b058dbfc1aee8e6db6007f8828025faa74fac16993c576b0",
        "cache_sha256": "ad8c4b0eca09103c4d396238191d0f424abf9b9ee1d47d3b6126d24628f8d5c0",
    },
    {
        "path": "handoff/1.6.0/tests/test_session_state.py",
        "outcome": "guarded-only",
        "reasons": ["unmatched-path"],
        "smoke": [],
        "source_sha256": "4e980b95ab04f8048cdf56f425b8f3fd2e1a34c8a249afe7882921e92d734621",
        "cache_sha256": "9bb409e61e5dfe0009892dd81bc560c1f9df5b98454970bdc74e3c44eae08a01",
    },
    {
        "path": "handoff/1.6.0/tests/test_skill_docs.py",
        "outcome": "guarded-only",
        "reasons": ["unmatched-path"],
        "smoke": [],
        "source_sha256": "11da6eb53ee939367b98989f81150331d11d7b9a77d46a712597d070dec7a742",
        "cache_sha256": "cc76dd71ec190b37e4bd4395eadd122b052a67bafecad781ba34d3b3c0bc6abf",
    },
]

source_root = Path("/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode")
cache_root = Path("/Users/jp/.codex/plugins/cache/turbo-mode")
items = payload["diff_classification"]
if len(items) != len(expected):
    raise SystemExit(f"diff length mismatch: {len(items)} != {len(expected)}")
for item, spec in zip(items, expected):
    if item["canonical_path"] != spec["path"]:
        raise SystemExit(f"path mismatch: {item['canonical_path']} != {spec['path']}")
    if item["outcome"] != spec["outcome"]:
        raise SystemExit(f"outcome mismatch for {spec['path']}: {item['outcome']}")
    if item["reasons"] != spec["reasons"]:
        raise SystemExit(f"reasons mismatch for {spec['path']}: {item['reasons']}")
    if item["smoke"] != spec["smoke"]:
        raise SystemExit(f"smoke mismatch for {spec['path']}: {item['smoke']}")
    source_hash = hashlib.sha256((source_root / spec["path"]).read_bytes()).hexdigest()
    cache_hash = hashlib.sha256((cache_root / spec["path"]).read_bytes()).hexdigest()
    if source_hash != spec["source_sha256"]:
        raise SystemExit(f"source hash mismatch for {spec['path']}: {source_hash}")
    if cache_hash != spec["cache_sha256"]:
        raise SystemExit(f"cache hash mismatch for {spec['path']}: {cache_hash}")
if payload["terminal_plan_status"] != "guarded-refresh-required":
    raise SystemExit(f"terminal status mismatch: {payload['terminal_plan_status']}")
if payload["axes"]["coverage_state"] != "covered":
    raise SystemExit(f"coverage state mismatch: {payload['axes']['coverage_state']}")
if payload["axes"]["selected_mutation_mode"] != "guarded-refresh":
    raise SystemExit(f"mutation mode mismatch: {payload['axes']['selected_mutation_mode']}")
if payload["axes"]["runtime_config_state"] != "aligned":
    raise SystemExit(f"runtime config mismatch: {payload['axes']['runtime_config_state']}")
if payload["app_server_inventory_status"] != "collected":
    raise SystemExit(f"inventory status mismatch: {payload['app_server_inventory_status']}")
print("Plan 05 post-implementation drift contract verified")
PY
```

Expected: prints `Plan 05 post-implementation drift contract verified`.

- [ ] **Step 3: Prove source surfaces are clean immediately before commit-safe evidence**

Run this gate immediately before the `--record-summary` command in Step 4:

```bash
git status --short --branch -- \
  .agents/plugins/marketplace.json \
  plugins/turbo-mode/handoff/1.6.0 \
  plugins/turbo-mode/ticket/1.4.0 \
  plugins/turbo-mode/tools/refresh \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  plugins/turbo-mode/tools/refresh_validate_run_metadata.py \
  plugins/turbo-mode/tools/refresh_validate_redaction.py \
  docs/superpowers/plans/2026-05-06-turbo-mode-refresh-05-handoff-coverage-gaps.md
```

Expected:

- output contains only the branch header;
- no file rows appear under the exact production relevant dirty path set, Handoff source, Ticket source, marketplace metadata, or this plan.

This list must include every path in `commit_safe.RELEVANT_DIRTY_PATHS` and `validation.ALLOWED_DIRTY_RELEVANT_PATHS`, plus this plan as a gate-only surface. Stop if the production relevant dirty path constants change and this gate is not updated in the same source implementation commit.

Stop if any file row appears. The commit-safe summary must not classify dirty Handoff or Ticket source content while recording `repo_head` and `repo_tree` from the previous commit.

- [ ] **Step 4: Run live dry-run with commit-safe summary**

```bash
RUN_ID_FILE="/private/tmp/plan05-handoff-coverage-run-id.txt"
if test -e "$RUN_ID_FILE"; then
  printf 'stale Plan 05 run-id sentinel exists: %s\n' "$RUN_ID_FILE" >&2
  exit 1
fi
RUN_ID="plan05-live-handoff-coverage-$(date -u +%Y%m%d-%H%M%S)"
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  --dry-run \
  --inventory-check \
  --record-summary \
  --require-terminal-status guarded-refresh-required \
  --run-id "$RUN_ID" \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --codex-home /Users/jp/.codex \
  --json && \
printf '%s\n' "$RUN_ID" > "$RUN_ID_FILE"
```

Expected:

- `/private/tmp/plan05-handoff-coverage-run-id.txt` does not exist before the command starts;
- command exits `0`;
- `/private/tmp/plan05-handoff-coverage-run-id.txt` is written only if the dry-run command exits `0`;
- commit-safe evidence is not written if the derived terminal status is anything other than `guarded-refresh-required`;
- terminal status is `guarded-refresh-required`;
- commit-safe summary is written to `plugins/turbo-mode/evidence/refresh/$RUN_ID.summary.json`;
- commit-safe summary records `repo_head = source_implementation_commit`;
- commit-safe summary records `repo_tree = source_implementation_tree`;
- summary omits raw app-server transcript and local-only payloads.
- smoke labels are advisory metadata only in Plan 05; no guarded-refresh smoke executor is implemented or invoked by this task.

- [ ] **Step 5: Verify summary hash, source binding, and exact evidence drift**

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
if payload["run_id"] != run_id:
    raise SystemExit(f"run_id mismatch: {payload['run_id']} != {run_id}")
if payload["repo_head"] != source_commit:
    raise SystemExit(f"repo_head mismatch: {payload['repo_head']} != {source_commit}")
if payload["repo_tree"] != source_tree:
    raise SystemExit(f"repo_tree mismatch: {payload['repo_tree']} != {source_tree}")
if payload["schema_version"] != "turbo-mode-refresh-commit-safe-plan-05":
    raise SystemExit(f"schema_version mismatch: {payload['schema_version']}")
payload_text = json.dumps(payload, sort_keys=True)
for stale_value in ("outside-plan-04", "plan-04-cli"):
    if stale_value in payload_text:
        raise SystemExit(f"stale Plan 04 evidence value present: {stale_value}")
local_only_root = Path(payload["local_only_evidence_root"])
for relative in (
    "redaction.summary.json",
    "redaction-final-scan.summary.json",
):
    path = local_only_root / relative
    if path.exists() and "plan-04-cli" in path.read_text(encoding="utf-8"):
        raise SystemExit(f"stale redaction source label present: {path}")
for path in local_only_root.rglob("*.json"):
    if "plan-04-cli" in path.read_text(encoding="utf-8"):
        raise SystemExit(f"stale redaction source label present in run root: {path}")
if payload["terminal_plan_status"] != "guarded-refresh-required":
    raise SystemExit(f"terminal status mismatch: {payload['terminal_plan_status']}")
expected_diff = [
    {
        "canonical_path": "handoff/1.6.0/skills/load/SKILL.md",
        "outcome": "guarded-only",
        "reason_codes": ["handoff-state-helper-direct-python-doc-migration"],
        "smoke": ["handoff-state-helper-docs", "handoff-session-state-write-read-clear"],
    },
    {
        "canonical_path": "handoff/1.6.0/skills/quicksave/SKILL.md",
        "outcome": "guarded-only",
        "reason_codes": ["handoff-state-helper-direct-python-doc-migration"],
        "smoke": ["handoff-state-helper-docs", "handoff-session-state-write-read-clear"],
    },
    {
        "canonical_path": "handoff/1.6.0/skills/save/SKILL.md",
        "outcome": "guarded-only",
        "reason_codes": ["handoff-state-helper-direct-python-doc-migration"],
        "smoke": ["handoff-state-helper-docs", "handoff-session-state-write-read-clear"],
    },
    {
        "canonical_path": "handoff/1.6.0/skills/summary/SKILL.md",
        "outcome": "guarded-only",
        "reason_codes": ["handoff-state-helper-direct-python-doc-migration"],
        "smoke": ["handoff-state-helper-docs", "handoff-session-state-write-read-clear"],
    },
    {
        "canonical_path": "handoff/1.6.0/tests/test_session_state.py",
        "outcome": "guarded-only",
        "reason_codes": ["unmatched-path"],
        "smoke": [],
    },
    {
        "canonical_path": "handoff/1.6.0/tests/test_skill_docs.py",
        "outcome": "guarded-only",
        "reason_codes": ["unmatched-path"],
        "smoke": [],
    },
]
actual_diff = [
    {
        "canonical_path": item["canonical_path"],
        "outcome": item["outcome"],
        "reason_codes": item["reason_codes"],
        "smoke": item["smoke"],
    }
    for item in payload["diff_classification"]
]
if actual_diff != expected_diff:
    raise SystemExit(f"diff classification mismatch: {actual_diff!r}")
print(actual_hash)
PY
```

Expected: prints the commit-safe summary SHA256 after proving the committed summary still contains exactly the six Plan 05 drift rows and no extras.

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
- live commit-safe summary schema version;
- proof that the live commit-safe summary contains no `outside-plan-04` or `plan-04-cli`;
- proof that local-only redaction evidence and the whole run root contain no `plan-04-cli`;
- final terminal status;
- clean-source gate output from Task 6 Step 3;
- source-commit-bound metadata replay command and result, if Task 7 Step 3 is run after the evidence/docs commit;
- explicit note that commit-safe validation or replay after the evidence/docs commit must be run from, or otherwise bound to, the recorded `source_implementation_commit` and `source_implementation_tree`, not the final evidence/docs commit;
- explicit note that Plan 05 smoke labels are advisory metadata until a later guarded-refresh implementation executes them;
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
- any post-commit validation or replay treats `source_implementation_commit` and `source_implementation_tree` as the commit-safe boundary, even though `HEAD` now points at the evidence/docs commit;
- evidence/docs commit records the closeout but does not mutate installed cache.

- [ ] **Step 3: Replay metadata validation from the source implementation commit**

After the evidence/docs commit, `HEAD` is no longer the commit-safe source boundary. Validate by running the source implementation commit's validator in a detached worktree while pointing it at the committed summary and retained local-only run root:

```bash
RUN_ID="$(cat /private/tmp/plan05-handoff-coverage-run-id.txt)"
SOURCE_IMPLEMENTATION_COMMIT="<source_implementation_commit from Task 5>"
SOURCE_REPLAY_ROOT="/private/tmp/codex-tool-dev-plan05-source-replay-$RUN_ID"
git worktree add --detach "$SOURCE_REPLAY_ROOT" "$SOURCE_IMPLEMENTATION_COMMIT"
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  "$SOURCE_REPLAY_ROOT/plugins/turbo-mode/tools/refresh_validate_run_metadata.py" \
  --run-id "$RUN_ID" \
  --repo-root "$SOURCE_REPLAY_ROOT" \
  --mode final \
  --local-only-root "/Users/jp/.codex/local-only/turbo-mode-refresh/$RUN_ID" \
  --summary "/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/evidence/refresh/$RUN_ID.summary.json" \
  --published-summary-path "/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/evidence/refresh/$RUN_ID.summary.json" \
  --candidate-summary "/Users/jp/.codex/local-only/turbo-mode-refresh/$RUN_ID/commit-safe.candidate.summary.json" \
  --existing-validation-summary "/Users/jp/.codex/local-only/turbo-mode-refresh/$RUN_ID/metadata-validation.summary.json"
```

Expected: command exits `0`. If this replay is skipped, the closeout must explicitly say Task 6 Step 5 was the final validator gate and no post-evidence/docs replay was performed.

## Stop Conditions

Stop before implementation or commit if any of these occur:

- current live drift differs from the four Handoff state-helper skill docs plus two Handoff tests;
- Task 0 Step 3 does not prove the exact six-path `diff_classification` contract: paths, outcomes, reason codes, smoke labels, source hashes, cache hashes, terminal status, runtime config, and inventory state;
- Task 6 Step 2 does not prove the exact post-implementation six-path drift contract before commit-safe evidence generation;
- Task 6 Step 5 does not prove the exact six-row commit-safe summary projection before evidence/docs closeout;
- generated source/cache fixture hashes differ from the expected table for any of the six Plan 05 drift paths;
- runtime config or app-server inventory is not aligned;
- residue issues are present;
- implementation weakens generic command-bearing doc or semantic-policy trigger handling;
- classifier exception is implemented with fragment or substring checks instead of exact source/cache content hashes;
- classifier exception does not compare exact production `source_items` and `cache_items` projection tuples;
- any unrelated Handoff, Ticket, or migration path becomes covered only because it contains similar prose;
- Task 6 clean-source gate prints any file row before `--record-summary`;
- classifier returns `fast-safe-with-covered-smoke` for the Handoff state-helper doc migration;
- Plan 05 commit-safe evidence keeps the Plan 04 commit-safe schema label after adding the new reason code;
- newly generated Plan 05 evidence contains `outside-plan-04` or `plan-04-cli`;
- local-only redaction evidence contains `plan-04-cli`;
- `commit_safe.RELEVANT_DIRTY_PATHS` and `validation.ALLOWED_DIRTY_RELEVANT_PATHS` do not include Handoff source and Ticket source;
- the Plan 05 document path is added to production dirty-state constants instead of remaining a Task 6 gate-only path;
- new reason code is not allowed by commit-safe validation;
- `/private/tmp/plan05-handoff-coverage-run-id.txt` already exists before Task 6 Step 4 starts;
- `/private/tmp/plan05-handoff-coverage-run-id.txt` is written when the Step 4 dry-run fails;
- Task 6 Step 5 summary verification does not prove `payload["run_id"] == run_id`;
- live dry-run still reports `coverage-gap-blocked` after source implementation;
- live dry-run reports `refresh-allowed` instead of `guarded-refresh-required`;
- any step runs `--refresh` or `--guarded-refresh`;
- any step copies files into `/Users/jp/.codex/plugins/cache/turbo-mode/`;
- any step edits `/Users/jp/.codex/config.toml`;
- generated residue appears and cleanup is not explicitly approved.

## Self-Review Checklist

- [ ] The plan preserves `coverage-gap-blocked`, `guarded-refresh-required`, and refresh completion as separate states.
- [ ] Planner-level `guarded-refresh-required` proof includes `inventory_check=True` with an aligned app-server inventory collector.
- [ ] The plan keeps mutation outside scope.
- [ ] The plan is path-bound to the four Handoff state-helper skill docs.
- [ ] The classifier exception is source/cache content-hash-bound and production projection-tuple-bound, with exact command-projection fixtures in tests.
- [ ] The two Handoff test-file drift rows are source/cache-hash-bound by the shared fixture and Task 0 live contract, even though their classifier reason remains `unmatched-path`.
- [ ] Generic command-bearing docs still fail closed.
- [ ] Semantic-policy docs still fail closed unless they exactly match the recertified Handoff state-helper migration.
- [ ] Commit-safe evidence uses `turbo-mode-refresh-commit-safe-plan-05`, and pre-Plan05 validators are allowed to reject Plan 05 artifacts.
- [ ] Plan 05 evidence contains no stale `outside-plan-04` or `plan-04-cli` values.
- [ ] Local-only redaction evidence contains no stale `plan-04-cli` source value.
- [ ] Production commit-safe and validation dirty-state constants include behavior-affecting Handoff source, Ticket source, refresh tooling, and marketplace metadata, but not the Plan 05 document path.
- [ ] Commit-safe evidence is gated by a clean-source check that matches the production dirty-state constants plus the Plan 05 document path as a gate-only surface.
- [ ] Post-evidence/docs validation is either replayed from the source implementation commit or explicitly left at Task 6 as the final validator gate.
- [ ] Plan 05 treats smoke labels as advisory metadata, not executed guarded-refresh smoke.
- [ ] The Handoff tests remain guarded-only drift and do not become fast-safe.
- [ ] Commit-safe reason allowlists include the new reason code.
- [ ] Verification includes refresh tests, Handoff source tests, ruff, residue scan, live dry-run, and commit-safe evidence.

## Completion Evidence

- Implementation branch: `chore/turbo-refresh-plan05-handoff-coverage`
- Source implementation commit: `6ac913e7059be99e14cf0cfdb8925f8736e4dcc0`
- Source implementation tree: `8b89866a7486859bb1632b1794102ea6996798d2`
- Focused refresh test result:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests -q`
  Result: `271 passed in 21.77s`
- Handoff source test result:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py plugins/turbo-mode/handoff/1.6.0/tests/test_skill_docs.py -q`
  Result: `20 passed in 1.85s`
- Ruff result:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/tools/refresh plugins/turbo-mode/tools/refresh_installed_turbo_mode.py plugins/turbo-mode/tools/refresh_validate_run_metadata.py plugins/turbo-mode/tools/refresh_validate_redaction.py`
  Result: `All checks passed!`
- Residue result:
  `find plugins/turbo-mode/handoff/1.6.0 plugins/turbo-mode/ticket/1.4.0 plugins/turbo-mode/tools/refresh -name __pycache__ -o -name '*.pyc' -o -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache -o -name .venv -o -name .DS_Store`
  Result: no output after trashing generated residue under `plugins/turbo-mode/handoff/1.6.0/.pytest_cache`
- Live dry-run status:
  Run id `plan05-live-handoff-coverage-dry-run-20260506-160004`
  Result: `terminal_plan_status = "guarded-refresh-required"`, `coverage_state = "covered"`, `selected_mutation_mode = "guarded-refresh"`, `runtime_config_state = "aligned"`, `app_server_inventory_status = "collected"`
- Live commit-safe summary path:
  [plan05-live-handoff-coverage-20260506-160049.summary.json](/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/evidence/refresh/plan05-live-handoff-coverage-20260506-160049.summary.json)
- Live commit-safe summary SHA256:
  `64e996c2c788961a11012b35bcb60b35d6e5c107751c5ae25196021832656052`
- Live commit-safe summary schema version:
  `turbo-mode-refresh-commit-safe-plan-05`
- Proof that the live commit-safe summary contains no `outside-plan-04` or `plan-04-cli`:
  Task 6 Step 5 scanned the summary payload text and found neither stale Plan 04 value.
- Proof that local-only redaction evidence and the whole run root contain no `plan-04-cli`:
  Task 6 Step 5 scanned `redaction.summary.json`, `redaction-final-scan.summary.json`, and every `*.json` file under `/Users/jp/.codex/local-only/turbo-mode-refresh/plan05-live-handoff-coverage-20260506-160049` and found no `plan-04-cli`.
- Final terminal status:
  `guarded-refresh-required`
- Clean-source gate output from Task 6 Step 3:
  `## chore/turbo-refresh-plan05-handoff-coverage`
- Source-commit-bound metadata replay command:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 "$SOURCE_REPLAY_ROOT/plugins/turbo-mode/tools/refresh_validate_run_metadata.py" --run-id "$RUN_ID" --repo-root "$SOURCE_REPLAY_ROOT" --mode final --local-only-root "/Users/jp/.codex/local-only/turbo-mode-refresh/$RUN_ID" --summary "/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/evidence/refresh/$RUN_ID.summary.json" --published-summary-path "/Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/evidence/refresh/$RUN_ID.summary.json" --candidate-summary "/Users/jp/.codex/local-only/turbo-mode-refresh/$RUN_ID/commit-safe.candidate.summary.json" --existing-validation-summary "/Users/jp/.codex/local-only/turbo-mode-refresh/$RUN_ID/metadata-validation.summary.json"`
- Source-commit-bound metadata replay result:
  This replay is intentionally run after the evidence/docs commit because it must prove validation from the recorded source implementation commit rather than the later evidence/docs `HEAD`. The result is recorded after Task 7 Step 3 completes.
- Source-bound validation note:
  Commit-safe validation and replay after the evidence/docs commit must be run from, or otherwise bound to, `source_implementation_commit = 6ac913e7059be99e14cf0cfdb8925f8736e4dcc0` and `source_implementation_tree = 8b89866a7486859bb1632b1794102ea6996798d2`, not the later evidence/docs commit.
- Smoke-label note:
  Plan 05 smoke labels are advisory metadata only. No guarded-refresh smoke executor is implemented or invoked by this plan.
- Completion-boundary note:
  `guarded-refresh-required` is not refresh completion. It proves that the current six-path drift is covered and guarded, not that installed cache mutation has been executed.
- Mutation-boundary note:
  Installed-cache mutation remains outside Plan 05.

# Ticket Target Status Source Slice Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring Ticket source/tests/docs into the new target status and blocked-ticket shape contract for `idea`, `open`, `blocked`, `done`, and `wontfix`, without claiming installed-runtime proof.

**Architecture:** This is a source/repo implementation slice, not a cache refresh or runtime inventory slice. It updates target ticket validation first, then teaches create/update/close code to preserve blocked-ticket shape, then sweeps status-only source/test/docs drift so the focused and full Ticket suites can pass. The autonomous candidate contract is a separate follow-up slice because it is a shared API migration across evaluator, gateway, discovery, identity, correction/reopen semantics, and integration tests.

**Tech Stack:** Python >=3.11, dataclasses, PyYAML, existing Ticket scripts, pytest, ruff, bytecode-safe `uv run` verification.

---

## Scope Check

This plan covers one coherent source/test/docs slice: target status vocabulary, blocked-ticket file shape, create behavior, direct lifecycle transitions, and status-only source/test/docs drift. It intentionally does not migrate the autonomous candidate contract.

In scope:

- Replace the old target status set `open/in_progress/done/wontfix` with `idea/open/blocked/done/wontfix`.
- Validate target-ticket blocked shape:
  - `status: blocked` requires a non-empty `## Blocked On` section.
  - `status: blocked` may carry `blocked_by`, but every item must be a valid `T-YYYYMMDD-NN` ticket ID.
  - Non-blocked tickets must not carry a `## Blocked On` section.
  - Non-blocked tickets may keep canonical empty `blocked_by: []`, but must not carry non-empty `blocked_by`.
- Let normal create produce `idea`, `open`, or `blocked`, defaulting to `open`.
- Reject normal create with `status: done` or `status: wontfix`.
- Update lifecycle transitions so `idea` is pre-lifecycle, `open` and `blocked` are active states, and terminal states remain `done`/`wontfix`.
- Clear live blocker shape when a blocked ticket moves to `open`, `done`, or `wontfix`.

Out of scope:

- Autonomous candidate contract migration, including `CandidateMutation`, `evaluate_autonomy_intent()`, gateway dispatch, discovery, mutation identity, `correct`, and `reopen`.
- Private operation-log retention, post-write fingerprints, and summary-emission recovery.
- `reconcile_board` discovery, ordering, caps, and compact overflow.
- Installed plugin cache mutation under `/Users/jp/.codex/plugins/cache`.
- Runtime inventory through `plugin/read`, `plugin/list`, `skills/list`, or `hooks/list`.
- Publishing, pushing, or pull request work.

Closeout claim for this plan:

```text
The local source/repo Ticket lane now enforces the new target status vocabulary, validates visible blocked-ticket shape, rejects terminal normal creates, and clears blocker shape on unblocking and terminal writes. Autonomous candidate-contract migration and installed runtime behavior remain unclaimed.
```

Do not use that claim until every verification gate in this plan passes.

## Live Baseline

Baseline from the planning and review-adjudication turns:

- Branch: `chore/ticket-candidate-contract-control-doc`
- Last reviewed docs-only plan commit before this follow-up patch: `077d9f7f`
- Worktree: clean before this follow-up plan patch
- Primary authority: `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
- Known source drift:
  - `plugins/turbo-mode/ticket/scripts/ticket_target_schema.py` still defines `TARGET_STATUSES = ("open", "in_progress", "done", "wontfix")`.
  - `plugins/turbo-mode/ticket/tests/test_target_schema.py` still asserts the old status tuple.
  - `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py` still uses `in_progress` in transition policy and create always renders `status="open"`.
  - `plugins/turbo-mode/ticket/scripts/ticket_parse.py` still treats `in_progress` as canonical parse vocabulary, already includes `blocked`, and lacks `idea` in `CANONICAL_STATUSES`.
  - `plugins/turbo-mode/ticket/scripts/ticket_triage.py` still counts, staleness-checks, and suggests actions around `open/in_progress` instead of `idea/open/blocked`.
  - `plugins/turbo-mode/ticket/scripts/ticket_read.py` still ranks `in_progress` and lacks `idea` and `blocked` ordering.
  - `plugins/turbo-mode/ticket/README.md`, `plugins/turbo-mode/ticket/HANDBOOK.md`, and `plugins/turbo-mode/ticket/tests/test_docs_contract.py` still present or require the old current target status set in user-facing docs, including docs-contract guards that say `blocked` is not a status and blockedness derives from `blocked_by`.
  - `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md`, `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md`, `plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md`, and `plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md` still present the old status vocabulary or old derived-blockedness rule. These files are current-facing docs under `test_docs_contract.py::CURRENT_FACING_DOCS`.
  - `plugins/turbo-mode/ticket/references/ticket-contract.md` currently line-wraps the phrase required by `test_contract_preserves_optional_sections_byte_for_byte`; the pre-existing focused failure is `AssertionError: assert 'Optional sections are preserved byte-for-byte' in text`.
  - `plugins/turbo-mode/ticket/tests/test_capture_contract.py` still has a current target fixture with `status="in_progress"`.
  - `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py` still models candidates as flat `proposed_change` plus internal evidence links. That drift is now explicitly deferred to a separate candidate-contract migration plan.

## File Structure

Modify these files:

- `plugins/turbo-mode/ticket/scripts/ticket_target_schema.py`
  - Owns target-ticket constants and file-level mechanical validation.
  - Add status-specific blocked-shape validation here because every read path already uses this schema gate.

- `plugins/turbo-mode/ticket/tests/test_target_schema.py`
  - Owns direct schema regression coverage.
  - Add the first failing tests for new status vocabulary and blocked-ticket shape.

- `plugins/turbo-mode/ticket/scripts/ticket_validate.py`
  - Owns writable field type and enum checks before planning, rendering, and execution.
  - Add `blocked_on` as a write field and validate `blocked_by` as target IDs, while leaving action-specific create rules to the engine.

- `plugins/turbo-mode/ticket/scripts/ticket_render.py`
  - Owns canonical frontmatter and ticket Markdown rendering.
  - Add `Blocked On` rendering support without changing unrelated optional section order.

- `plugins/turbo-mode/ticket/tests/support/builders.py`
  - Owns test ticket fixtures.
  - Add a `blocked_on` fixture parameter so blocked tests are explicit and readable.
  - Keep `make_ticket()` defaulting normal active fixtures to `open`; preserve legacy `make_gen3_ticket()` `status: in_progress` because migration tests prove legacy parse behavior, not current target validity.

- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
  - Owns plan/preflight/execute policy and direct write behavior.
  - Update create status handling, transition policy, blocked section writes, and blocker cleanup.

- `plugins/turbo-mode/ticket/tests/test_execute.py`
  - Owns direct user execute behavior.
  - Add create/update/close blocked-shape tests and update old `in_progress` expectations.

- `plugins/turbo-mode/ticket/tests/test_engine_policy.py`
  - Owns shared read-only policy evaluator expectations.
  - Add policy-data coverage for `idea`, `blocked`, and invalid legacy `in_progress`.

- `plugins/turbo-mode/ticket/scripts/ticket_parse.py`
  - Owns permissive parse and legacy status normalization.
  - Update `CANONICAL_STATUSES` to the new target set while keeping raw unknown-status pass-through for migration diagnostics.
  - Do not make parse the target-status rejection layer; target schema and write-field validation own rejection.

- `plugins/turbo-mode/ticket/tests/test_parse.py`
  - Owns parse-level target canonical vocabulary plus legacy normalization behavior.
  - Assert `CANONICAL_STATUSES` is `idea/open/blocked/done/wontfix`, target statuses pass through unchanged, and raw `in_progress` remains a legacy/diagnostic pass-through rather than a parse-level rejection.

- `plugins/turbo-mode/ticket/tests/test_validate.py`
  - Owns writable-field validation coverage.
  - Replace old status validation with `idea/open/blocked/done/wontfix` and make `in_progress` invalid.

- `plugins/turbo-mode/ticket/scripts/ticket_triage.py`
  - Owns dashboard counts, stale visibility, and next-action suggestions.
  - Replace `open/in_progress` dashboard buckets with `idea/open/blocked`, keep `idea` visible but not stale/actionable by default, and treat `blocked` as the stuck-work state.

- `plugins/turbo-mode/ticket/tests/test_triage.py`
  - Owns board counts and status grouping expectations.
  - Replace active `in_progress` expectations with `open` or `blocked` according to fixture intent.

- `plugins/turbo-mode/ticket/scripts/ticket_read.py`
  - Owns list/read payload display sort keys.
  - Replace old `open/in_progress/done/wontfix` sort vocabulary with `idea/open/blocked/done/wontfix`, leaving the unknown fallback only for diagnostic invalid-state surfaces.

- `plugins/turbo-mode/ticket/tests/test_read.py`
  - Owns read/list payload expectations.
  - Add or update status sort-key coverage for `idea`, `open`, and `blocked`, and remove current-facing `in_progress` expectations.

- `plugins/turbo-mode/ticket/tests/test_integration.py`
  - Owns end-to-end direct Ticket flows.
  - Replace `open -> in_progress -> done` flows with valid `open`, `open -> blocked`, `blocked -> open`, and close flows.

- `plugins/turbo-mode/ticket/tests/test_entrypoints.py`
  - Owns command-entry status payload examples.
  - Replace normal `in_progress` writes with valid `blocked` writes that include blocker shape, or with `open` where no blocker exists.

- `plugins/turbo-mode/ticket/tests/test_ux.py`
  - Owns user-facing direct-read/write messages.
  - Replace normal `in_progress` fixtures with `open` or mechanically valid `blocked` fixtures.

- `plugins/turbo-mode/ticket/tests/test_blocker_resolution.py`
  - Owns blocker dependency read behavior.
  - Use `blocked` status for blocked-dependency fixtures and include visible blocker shape when target validation is in play.

- `plugins/turbo-mode/ticket/tests/test_capture_contract.py`
  - Owns close-readiness and capture contract boundaries.
  - Replace current target fixtures using `status="in_progress"` with `open` unless the test is intentionally checking blocked behavior.

- `plugins/turbo-mode/ticket/README.md`
  - Owns user-facing plugin status and ticket-shape documentation.
  - Replace current target status prose/tables with `idea/open/blocked/done/wontfix` and visible `Blocked On` semantics.

- `plugins/turbo-mode/ticket/HANDBOOK.md`
  - Owns operator-facing Ticket behavior and command reference.
  - Replace current status prose and command examples with `idea/open/blocked/done/wontfix`; leave old statuses only where explicitly historical or diagnostic.

- `plugins/turbo-mode/ticket/references/ticket-contract.md`
  - Owns source-facing contract prose used by docs-contract tests.
  - Keep optional-section preservation wording on one line so `test_contract_preserves_optional_sections_byte_for_byte` can pass, and update current target status prose only where this slice owns it.

- `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md`
  - Owns capture-skill target shape guidance.
  - Replace the old current status list with `idea/open/blocked/done/wontfix`; describe `status: blocked` plus visible `Blocked On`, optional `blocked_by` ID dependencies, and no persisted reverse `blocks` edge.

- `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md`
  - Owns update-skill target shape guidance.
  - Replace the old current status list with `idea/open/blocked/done/wontfix`; describe `blocked_on` as the write-field adapter for the `Blocked On` section when moving into or out of `blocked`.

- `plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md`
  - Owns read/list/search skill examples.
  - Replace status prose and CLI examples with `idea|open|blocked|done|wontfix`; remove the old statement that `blocked` is only derived from `blocked_by`.

- `plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md`
  - Owns backlog triage skill guidance.
  - Replace old "persisted blocked status is not target schema" language with read/query/reporting guidance over first-class blocked tickets; keep the no-write boundary and the prohibition on persisted reverse `blocks` edges.

- `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
  - Owns static guards for README/HANDBOOK authority claims.
  - Update assertions so docs and SKILL files no longer require `in_progress` as a current status and do require the new blocked-status documentation.
  - Remove or invert the old docs-contract guards that made `blocked` a derived non-status: `OLD_SCHEMA_TERMS` entries `"blocked status"` and ``"`blocked` status"``, the positive assertions for ``"`blocked` is not a status"`` and `"derive reverse `blocks`"`, and the triage-doc assertions that say persisted `blocked` status is not target schema and target blockedness derives from `blocked_by`.

Deferred candidate-contract migration surfaces, not modified in this plan:

- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
- `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`
- `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`
- `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`

Do not create new source modules in this slice. The existing files already define the ownership boundaries, and a new abstraction would hide status-shape changes that should remain visible at the schema, engine, and test boundaries.

## Task 0: Preflight And Authority Check

**Files:**
- Read: `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
- Read: `plugins/turbo-mode/ticket/scripts/ticket_target_schema.py`
- Read: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Read: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`

- [ ] **Step 1: Confirm live branch and worktree**

Run:

```bash
git status --short --branch
git rev-parse --short HEAD
```

Expected:

```text
`git status --short --branch` prints `## chore/ticket-candidate-contract-control-doc` with no dirty file lines, and `git rev-parse --short HEAD` prints the current short commit. Record the commit in closeout instead of hard-coding an older planning-turn SHA.
```

If `git status --short --branch` shows unrelated dirty files, inspect before editing and do not stage them.

- [ ] **Step 2: Re-read the authority snippets**

Run:

```bash
rg -n "Candidate Mutation Contract|Create Idempotency|Status-specific ticket shape|Blocked On|Board Reconciliation Wrapper" docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md
```

Expected:

```text
The command prints the control-doc sections that define target candidate shape, create status limits, blocked-ticket shape, and reconciliation as a later wrapper.
```

- [ ] **Step 3: Confirm current drift before tests**

Run:

```bash
rg -n "in_progress|TARGET_STATUSES|blocked_by|Blocked On|CandidateMutation" plugins/turbo-mode/ticket/scripts/ticket_target_schema.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_target_schema.py
```

Expected:

```text
The command still finds in_progress in target status constants, engine transition tests, or old fixtures before implementation starts.
```

- [ ] **Step 4: Confirm the full-suite baseline is known-red only for docs-contract wording**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected:

```text
The suite may fail before implementation only at `tests/test_docs_contract.py::test_contract_preserves_optional_sections_byte_for_byte`, because `references/ticket-contract.md` line-wraps the literal "Optional sections are preserved byte-for-byte" phrase. Record the exact pass/fail/warning counts. If any other test fails, stop and patch this plan before source implementation. Task 4 fixes this known docs-contract failure; do not claim baseline green before that fix lands.
```

- [ ] **Step 5: Check live project tickets for old status records**

Run:

```bash
rg -n "status:\s*in_progress" docs/tickets
```

Expected:

```text
If this finds live project tickets, record them as a data-compatibility follow-up before implementation. This source slice does not migrate project-local ticket records, but triage/read changes must not hide the fact that old records exist. If it prints no matches, record that there are no current `docs/tickets/` records with `status: in_progress` at execution start.
```

## Task 1: Target Status Constants And Blocked File Shape

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_target_schema.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_target_schema.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_policy.py`

- [ ] **Step 1: Write failing schema tests for the new lifecycle vocabulary**

In `plugins/turbo-mode/ticket/tests/test_target_schema.py`, update `test_target_schema_constants_match_contract_vocabulary` and replace the old blocked-status rejection test with these tests:

```python
def test_target_schema_constants_match_contract_vocabulary() -> None:
    assert TARGET_FRONTMATTER_REQUIRED == ("id", "title", "status", "priority")
    assert TARGET_FRONTMATTER_OPTIONAL == ("tags", "related_paths", "blocked_by")
    assert TARGET_FRONTMATTER_FIELDS == (
        "id",
        "title",
        "status",
        "priority",
        "tags",
        "related_paths",
        "blocked_by",
    )
    assert TARGET_SECTIONS_REQUIRED == ("Problem", "Next Action", "Change History")
    assert TARGET_STATUSES == ("idea", "open", "blocked", "done", "wontfix")
    assert TARGET_PRIORITIES == ("high", "normal", "low")


def test_target_ticket_accepts_idea_status(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: idea\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is True
    assert result.error == ""


def test_target_ticket_rejects_deprecated_in_progress_status(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: in_progress\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "status" in result.error
    assert "in_progress" in result.error
```

Keep the existing priority rejection parametrization, but remove `("status", "blocked")` from it because `blocked` is now valid when the ticket has valid blocked shape. Rename `test_target_ticket_rejects_deprecated_status_and_priority()` to `test_target_ticket_rejects_deprecated_priorities()` so the test name no longer claims it rejects statuses.

- [ ] **Step 2: Write failing schema tests for blocked shape**

Add these tests to `plugins/turbo-mode/ticket/tests/test_target_schema.py` after the status tests:

```python
def test_target_ticket_accepts_blocked_status_with_blocked_on(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: blocked\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: [T-20260508-02]\n"
            "---\n"
        ),
        body=(
            "\n"
            "## Problem\n"
            "Example problem.\n"
            "\n"
            "## Next Action\n"
            "Ask for the missing deploy credentials, then continue implementation.\n"
            "\n"
            "## Blocked On\n"
            "Waiting for deploy credentials from the user.\n"
            "\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is True
    assert result.error == ""


def test_target_ticket_rejects_blocked_status_without_blocked_on(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: blocked\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "Blocked On" in result.error


def test_target_ticket_rejects_blocked_status_with_empty_blocked_on(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: blocked\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: []\n"
            "---\n"
        ),
        body=(
            "\n"
            "## Problem\n"
            "Example problem.\n"
            "\n"
            "## Next Action\n"
            "Ask for the missing deploy credentials, then continue implementation.\n"
            "\n"
            "## Blocked On\n"
            "\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "Blocked On" in result.error


def test_target_ticket_rejects_blocked_on_for_non_blocked_status(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        body=(
            "\n"
            "## Problem\n"
            "Example problem.\n"
            "\n"
            "## Next Action\n"
            "Example next action.\n"
            "\n"
            "## Blocked On\n"
            "This stale blocker section must be removed before the ticket is open.\n"
            "\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "Blocked On" in result.error


def test_target_ticket_rejects_non_empty_blocked_by_for_non_blocked_status(
    tmp_path: Path,
) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: open\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: [T-20260508-02]\n"
            "---\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "blocked_by" in result.error


def test_target_ticket_rejects_invalid_blocked_by_ids(tmp_path: Path) -> None:
    ticket = tmp_path / "T-20260508-01.md"
    _write_target_ticket(
        ticket,
        frontmatter=(
            "---\n"
            "id: T-20260508-01\n"
            "title: Example\n"
            "status: blocked\n"
            "priority: normal\n"
            "tags: []\n"
            "related_paths: []\n"
            "blocked_by: [not-a-ticket-id]\n"
            "---\n"
        ),
        body=(
            "\n"
            "## Problem\n"
            "Example problem.\n"
            "\n"
            "## Next Action\n"
            "Ask for the missing deploy credentials, then continue implementation.\n"
            "\n"
            "## Blocked On\n"
            "Waiting for deploy credentials from the user.\n"
            "\n"
            "## Change History\n"
            "- 2026-06-02T00:00:00Z | migration | Normalized ticket into ADR 0006 schema.\n"
        ),
    )

    result = validate_target_ticket_file(ticket)

    assert result.ok is False
    assert "blocked_by" in result.error
```

- [ ] **Step 3: Add a failing close-policy regression for `idea`**

In `plugins/turbo-mode/ticket/tests/test_engine_policy.py`, add this test near the existing close-policy tests:

```python
def test_close_policy_rejects_idea_as_terminal_source(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "idea.md", id="T-20260503-31", status="idea")
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_close_policy(
        "T-20260503-31",
        ticket,
        {"resolution": "wontfix"},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["current_status"] == "idea"
    assert response.data["valid_recovery_statuses"] == ["open"]
```

This test belongs in Task 1 because adding `idea` to `TARGET_STATUSES` makes `idea` a valid target-file status. Do not leave a commit where direct close policy accepts `idea -> done/wontfix`.

- [ ] **Step 4: Run the target schema and close-policy tests and verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_target_schema.py plugins/turbo-mode/ticket/tests/test_engine_policy.py::test_close_policy_rejects_idea_as_terminal_source -q
```

Expected:

```text
Fails because TARGET_STATUSES still contains in_progress, blocked is not accepted by constants, status-specific Blocked On validation does not exist, and close policy still accepts non-terminal current statuses too broadly.
```

- [ ] **Step 5: Implement target status, blocked-shape validation, and `idea` close rejection**

In `plugins/turbo-mode/ticket/scripts/ticket_target_schema.py`, change the status constant:

```python
TARGET_STATUSES = ("idea", "open", "blocked", "done", "wontfix")
```

Add these helpers below `_validate_required_sections`:

```python
def _section_bodies(body: str) -> dict[str, str]:
    sections = list(_SECTION_RE.finditer(body))
    bodies: dict[str, str] = {}
    for index, match in enumerate(sections):
        heading = match.group(1).strip()
        section_start = match.end()
        section_end = sections[index + 1].start() if index + 1 < len(sections) else len(body)
        bodies.setdefault(heading, body[section_start:section_end].strip())
    return bodies


def _validate_status_specific_shape(frontmatter: dict[str, Any], body: str) -> str:
    status = frontmatter["status"]
    blocked_by = frontmatter.get("blocked_by", [])
    section_bodies = _section_bodies(body)
    blocked_on = section_bodies.get("Blocked On")

    invalid_blocked_by = [ticket_id for ticket_id in blocked_by if not TARGET_ID_RE.fullmatch(ticket_id)]
    if invalid_blocked_by:
        return f"blocked_by entries must be target ticket IDs. Got: {invalid_blocked_by!r:.100}"

    if status == "blocked":
        if not blocked_on:
            return "blocked tickets require non-empty Blocked On section"
        return ""

    if blocked_on is not None:
        return f"Blocked On section is only valid for blocked tickets. Got: {status!r:.100}"
    if blocked_by:
        return f"blocked_by is only valid for blocked tickets. Got: {blocked_by!r:.100}"
    return ""
```

Then call it in `validate_target_ticket_text()` after `history_error`:

```python
    status_shape_error = _validate_status_specific_shape(normalized_frontmatter, body)
    if status_shape_error:
        return TargetTicketValidation(False, ticket_id=ticket_id, error=status_shape_error)
```

In `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`, narrow the close allowlist in `_is_valid_transition()` in the same Task 1 commit:

```python
    if action == "close":
        return current in {"open", "blocked"} and target in ("done", "wontfix")
```

Update close recovery statuses in `_evaluate_close_policy()` immediately after `validation_errors` handling where the live code currently assigns `valid_recovery_statuses`:

```python
    if ticket.status == "idea":
        valid_recovery_statuses = ["open"]
    elif ticket.status in _TERMINAL_STATUSES:
        valid_recovery_statuses = []
    else:
        valid_recovery_statuses = ["done", "wontfix"]
```

This is an atomicity requirement, not an optional cleanup. If the status schema accepts `idea`, close policy and close recovery hints must reject `idea` in the same behavioral commit.

- [ ] **Step 6: Run the schema and close-policy tests and verify pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_target_schema.py plugins/turbo-mode/ticket/tests/test_engine_policy.py::test_close_policy_rejects_idea_as_terminal_source -q
```

Expected:

```text
All selected schema and close-policy tests pass.
```

- [ ] **Step 7: Commit Task 1**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_target_schema.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/tests/test_target_schema.py plugins/turbo-mode/ticket/tests/test_engine_policy.py
git commit -m "fix(ticket): enforce target blocked status schema"
```

Expected:

```text
Commit succeeds with target schema, close-policy guard, and their direct tests staged.
```

## Task 2: Create And Render Valid Idea/Open/Blocked Tickets

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_validate.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_render.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/tests/support/builders.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_execute.py`

- [ ] **Step 1: Add failing create tests for idea, blocked, and terminal-create rejection**

In `plugins/turbo-mode/ticket/tests/test_execute.py`, add these tests inside `class TestCreate`:

```python
    def test_create_can_write_idea_ticket(self, tmp_tickets: Path) -> None:
        response = _create_response(
            tmp_tickets,
            {
                "title": "Park design follow-up",
                "problem": "The design question is real but not actionable yet.",
                "status": "idea",
                "next_action": "Promote when the user chooses the direction.",
            },
        )

        assert response.state == "ok"
        ticket_path = Path(response.data["ticket_path"])
        text = ticket_path.read_text(encoding="utf-8")
        assert "status: idea" in text
        assert "## Blocked On" not in text
        assert validate_target_ticket_file(ticket_path).ok

    def test_create_can_write_blocked_ticket_with_visible_blocker(
        self,
        tmp_tickets: Path,
    ) -> None:
        response = _create_response(
            tmp_tickets,
            {
                "title": "Wait for deployment access",
                "problem": "Deployment validation cannot proceed without access.",
                "status": "blocked",
                "next_action": "Ask for access, then run the deployment smoke.",
                "blocked_on": "Waiting for deployment credentials from the user.",
                "blocked_by": ["T-20260508-02"],
            },
        )

        assert response.state == "ok"
        ticket_path = Path(response.data["ticket_path"])
        text = ticket_path.read_text(encoding="utf-8")
        assert "status: blocked" in text
        assert "blocked_by: [T-20260508-02]" in text
        assert "## Blocked On\nWaiting for deployment credentials from the user." in text
        assert validate_target_ticket_file(ticket_path).ok

    @pytest.mark.parametrize("status", ["done", "wontfix"])
    def test_create_rejects_terminal_statuses(self, tmp_tickets: Path, status: str) -> None:
        response = _create_response(
            tmp_tickets,
            {
                "title": "Terminal create",
                "problem": "Normal create must not create historical terminal records.",
                "status": status,
            },
        )

        assert response.state == "need_fields"
        assert response.error_code == "need_fields"
        assert "create status" in response.message
        assert list(tmp_tickets.glob("*.md")) == []

    def test_create_rejects_blocked_without_visible_blocker(self, tmp_tickets: Path) -> None:
        response = _create_response(
            tmp_tickets,
            {
                "title": "Missing blocker prose",
                "problem": "Blocked tickets need visible blocker truth.",
                "status": "blocked",
            },
        )

        assert response.state == "need_fields"
        assert response.error_code == "need_fields"
        assert "blocked_on" in response.message
        assert list(tmp_tickets.glob("*.md")) == []

    def test_create_rejects_live_blocker_fields_for_open_ticket(self, tmp_tickets: Path) -> None:
        response = _create_response(
            tmp_tickets,
            {
                "title": "Open ticket with stale blocker",
                "problem": "Open tickets must not retain live blocker fields.",
                "blocked_on": "This stale blocker should not be accepted.",
                "blocked_by": ["T-20260508-02"],
            },
        )

        assert response.state == "need_fields"
        assert response.error_code == "need_fields"
        assert "blocked" in response.message
        assert list(tmp_tickets.glob("*.md")) == []
```

- [ ] **Step 2: Run create tests and verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_execute.py::TestCreate -q
```

Expected:

```text
Fails because create ignores status, blocked_on is not a known write field, and render_ticket does not emit Blocked On.
```

- [ ] **Step 3: Teach writable field validation about blocked_on and target IDs**

In `plugins/turbo-mode/ticket/scripts/ticket_validate.py`, import `TARGET_ID_RE`:

```python
from scripts.ticket_target_schema import TARGET_ID_RE, TARGET_PRIORITIES, TARGET_STATUSES
```

Do not add `blocked_on` to the main string-field tuple. Add a dedicated nullable-aware branch after the normal string-field loop:

```python
    if "blocked_on" in fields:
        if fields["blocked_on"] is None:
            pass
        else:
            _validate_string_field(fields, "blocked_on", errors)
```

`blocked_on` is both a normal string input when moving into `blocked` and the section-removal adapter when moving out of `blocked`. Adding it to the shared string-field tuple creates a broken intermediate state where `validate_fields({"blocked_on": None})` fails.

Replace the list validation block for `blocked_by` with this additional check after the existing list-of-string check:

```python
    if "blocked_by" in fields and isinstance(fields["blocked_by"], list):
        invalid_blocked_by = [
            ticket_id
            for ticket_id in fields["blocked_by"]
            if isinstance(ticket_id, str) and TARGET_ID_RE.fullmatch(ticket_id) is None
        ]
        if invalid_blocked_by:
            errors.append(
                f"blocked_by entries must be target ticket IDs, got {invalid_blocked_by!r}"
            )
```

- [ ] **Step 4: Add create status-shape helper in engine core**

In `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`, add this helper near `_CREATE_REQUIRED`:

```python
_CREATE_STATUSES = frozenset({"idea", "open", "blocked"})


def _validate_create_status_shape(fields: dict[str, Any]) -> list[str]:
    status = fields.get("status", "open")
    blocked_on = fields.get("blocked_on")
    blocked_by = fields.get("blocked_by", [])
    errors: list[str] = []

    if status not in _CREATE_STATUSES:
        errors.append("create status must be one of ['blocked', 'idea', 'open']")
    if status == "blocked":
        if not isinstance(blocked_on, str) or not blocked_on.strip():
            errors.append("blocked create requires blocked_on")
    else:
        if blocked_on:
            errors.append("blocked_on is only valid for blocked create")
        if blocked_by:
            errors.append("blocked_by is only valid for blocked create")
    return errors
```

Call it in `_plan_create()` immediately after the required-field check and before `validate_fields(fields)`:

```python
    create_shape_errors = _validate_create_status_shape(fields)
    if create_shape_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(create_shape_errors)}",
            error_code="need_fields",
            data={"missing_fields": [], "validation_errors": create_shape_errors},
        )
```

Call it in `_execute_create()` immediately after the required-field check and before `validate_fields(fields)`:

```python
    create_shape_errors = _validate_create_status_shape(fields)
    if create_shape_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(create_shape_errors)}",
            error_code="need_fields",
            data={"validation_errors": create_shape_errors},
        )
```

- [ ] **Step 5: Render Blocked On and create requested status**

In `plugins/turbo-mode/ticket/scripts/ticket_render.py`, add a parameter to `render_ticket()`:

```python
    blocked_on: str = "",
```

Then render `Blocked On` after `Next Action` and before `Change History`:

```python
    lines.extend(["## Next Action", next_action or "Continue work on this ticket.", ""])
    if blocked_on:
        lines.extend(["## Blocked On", blocked_on, ""])
    lines.extend(["## Change History", change_history_entry, ""])
```

In `_execute_create()` in `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`, compute the status:

```python
    status = fields.get("status", "open")
```

Then pass these values to `render_ticket()`:

```python
            status=status,
            blocked_on=fields.get("blocked_on", ""),
```

- [ ] **Step 6: Update test ticket builder for blocked fixtures**

In `plugins/turbo-mode/ticket/tests/support/builders.py`, add `blocked_on` to `make_ticket()`:

```python
    blocked_on: str = "",
```

Do not interpolate a zero-indented `## Blocked On` string inside the `textwrap.dedent(...)` f-string. That defeats dedent and leaves the whole fixture indented. Build the normal fixture first, then insert the optional section after dedent:

````python
    content = textwrap.dedent(f"""\
        ---
        id: {id}
        title: {title}
        status: {status}
        priority: {priority}
        tags: {tags}
        related_paths: {related_paths}
        blocked_by: {blocked_by}
        {extra_yaml}---

        ## Problem
        {problem}

        ## Next Action
        Continue work on this ticket.

        ## Change History
        - 2026-06-02T00:00:00Z | migration | Test fixture normalized to target schema.

        ## Approach
        Fix the issue.

        ## Acceptance Criteria
        - [ ] Issue resolved

        ## Verification
        ```bash
        echo "verified"
        ```

        ## Key Files
        | File | Role | Look For |
        |------|------|----------|
        | test.py | Test | Test code |
        {extra_sections}
    """)
    if blocked_on:
        marker = "\n## Change History\n"
        content = content.replace(
            marker,
            f"\n## Blocked On\n{blocked_on.strip()}\n{marker}",
            1,
        )
````

The final file must still start with `---` when `blocked_on` is set. Do not keep any pre-dedent helper that injects a raw newline followed by an unindented `## Blocked On` heading.

- [ ] **Step 7: Run create tests and target schema tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_execute.py::TestCreate plugins/turbo-mode/ticket/tests/test_target_schema.py -q
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 8: Commit Task 2**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_validate.py plugins/turbo-mode/ticket/scripts/ticket_render.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/tests/support/builders.py plugins/turbo-mode/ticket/tests/test_execute.py
git commit -m "feat(ticket): create visible blocked and idea tickets"
```

Expected:

```text
Commit succeeds with create/render behavior and direct tests staged.
```

## Task 3: Lifecycle Transitions And Blocker Cleanup

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_validate.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_validate.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_execute.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_policy.py`

- [ ] **Step 1: Add failing direct execute tests for lifecycle transitions**

In `plugins/turbo-mode/ticket/tests/test_execute.py`, update `TestUpdate.test_update_ticket_frontmatter` so it promotes `idea -> open` instead of `open -> in_progress`:

```python
    def test_update_promotes_idea_to_open(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="idea")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"status": "open"},
        )

        assert response.state == "ok"
        content = ticket_path.read_text(encoding="utf-8")
        assert "status: open" in content
        assert "\ndate:" not in content
```

Replace `test_removed_blocked_status_is_rejected_by_schema` with:

```python
    def test_update_blocks_open_ticket_with_visible_blocker(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={
                "status": "blocked",
                "blocked_on": "Waiting for the user to provide credentials.",
                "next_action": "Ask for credentials, then run the smoke test.",
            },
        )

        assert response.state == "ok"
        text = ticket_path.read_text(encoding="utf-8")
        assert "status: blocked" in text
        assert "## Blocked On\nWaiting for the user to provide credentials." in text
        assert validate_target_ticket_file(ticket_path).ok

    def test_update_rejects_blocked_transition_without_blocked_on(
        self,
        tmp_tickets: Path,
    ) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"status": "blocked"},
        )

        assert response.state == "invalid_transition"
        assert response.error_code == "invalid_transition"
        assert "blocked_on" in response.message

    def test_update_rejects_open_to_wontfix_because_terminal_writes_use_close(
        self,
        tmp_tickets: Path,
    ) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="open")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={"status": "wontfix"},
        )

        assert response.state == "invalid_transition"
        assert response.error_code == "invalid_transition"
        assert response.data["current_status"] == "open"
        assert response.data["requested_status"] == "wontfix"
        assert response.data["valid_recovery_statuses"] == ["blocked"]
        assert "use close action" in response.message

    def test_update_unblocks_ticket_and_removes_live_blocker_shape(
        self,
        tmp_tickets: Path,
    ) -> None:
        ticket_path = make_ticket(
            tmp_tickets,
            "ignored.md",
            id="T-20260302-01",
            status="blocked",
            blocked_by=["T-20260302-02"],
            blocked_on="Waiting for the user to provide credentials.",
        )

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="update",
            fields={
                "status": "open",
                "blocked_by": [],
                "blocked_on": None,
                "next_action": "Run the deployment smoke.",
            },
        )

        assert response.state == "ok"
        text = ticket_path.read_text(encoding="utf-8")
        assert "status: open" in text
        assert "blocked_by: []" in text
        assert "## Blocked On" not in text
        assert validate_target_ticket_file(ticket_path).ok
```

In `class TestCloseAndReopen`, change `in_progress` fixtures to `open` or `blocked`, then add:

Any new or changed close-to-`done` fixture must keep a concrete `## Acceptance Criteria` section because `_TARGET_PRECONDITIONS["done"]` still requires it. The examples below close to `wontfix`, so they do not prove the `done` precondition.

```python
    def test_close_rejects_idea_ticket(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(tmp_tickets, "ignored.md", id="T-20260302-01", status="idea")

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="close",
            fields={"resolution": "wontfix"},
        )

        assert response.state == "invalid_transition"
        assert response.error_code == "invalid_transition"
        assert response.data["current_status"] == "idea"
        assert response.data["valid_recovery_statuses"] == ["open"]

    def test_close_blocked_ticket_clears_live_blocker_shape(self, tmp_tickets: Path) -> None:
        ticket_path = make_ticket(
            tmp_tickets,
            "ignored.md",
            id="T-20260302-01",
            status="blocked",
            blocked_by=["T-20260302-02"],
            blocked_on="Waiting for upstream work.",
        )

        response = _execute_existing(
            tmp_tickets,
            ticket_path,
            action="close",
            fields={"resolution": "wontfix"},
        )

        assert response.state == "ok"
        text = ticket_path.read_text(encoding="utf-8")
        assert "status: wontfix" in text
        assert "blocked_by: []" in text
        assert "## Blocked On" not in text
        assert validate_target_ticket_file(ticket_path).ok
```

- [ ] **Step 2: Add validation and policy evaluator tests**

In `plugins/turbo-mode/ticket/tests/test_validate.py`, add this direct guard for section removal input:

```python
    def test_blocked_on_none_is_valid_section_removal_input(self):
        assert validate_fields({"blocked_on": None}) == []
```

This test should already pass if Task 2 implemented `blocked_on` with the dedicated nullable-aware branch. If it fails, Task 2 is incomplete; do not wait until Task 3 to remove `blocked_on` from the shared string-field tuple.

In `plugins/turbo-mode/ticket/tests/test_engine_policy.py`, import `validate_target_ticket_file` from `scripts.ticket_target_schema`, replace `in_progress` fixtures with `open` or `blocked`, then add:

```python
def test_update_blocked_transition_requires_visible_blocker(tmp_tickets: Path) -> None:
    path = make_ticket(tmp_tickets, "open.md", id="T-20260503-29", status="open")
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-29",
        ticket,
        {"status": "blocked"},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["current_status"] == "open"
    assert response.data["requested_status"] == "blocked"
    assert response.data["precondition_code"] == "blocked_on_required"
    assert response.data["precondition_detail"] == {"missing": ["blocked_on"]}


def test_update_allows_blocked_to_open_with_blocker_cleanup(tmp_tickets: Path) -> None:
    path = make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-30",
        status="blocked",
        blocked_by=["T-20260503-31"],
        blocked_on="Waiting for the upstream fix.",
    )
    assert validate_target_ticket_file(path).ok
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-30",
        ticket,
        {"status": "open", "blocked_by": [], "blocked_on": None, "next_action": "Continue."},
        tmp_tickets,
    )

    assert response is None


def test_update_allows_blocked_to_open_without_blocked_by_field_when_already_empty(
    tmp_tickets: Path,
) -> None:
    path = make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-33",
        status="blocked",
        blocked_by=[],
        blocked_on="Waiting for the upstream fix.",
    )
    assert validate_target_ticket_file(path).ok
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-33",
        ticket,
        {"status": "open", "blocked_on": None, "next_action": "Continue."},
        tmp_tickets,
    )

    assert response is None


def test_update_rejects_blocked_to_open_without_clearing_existing_blocked_by(
    tmp_tickets: Path,
) -> None:
    path = make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-34",
        status="blocked",
        blocked_by=["T-20260503-31"],
        blocked_on="Waiting for the upstream fix.",
    )
    assert validate_target_ticket_file(path).ok
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-34",
        ticket,
        {"status": "open", "blocked_on": None, "next_action": "Continue."},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["precondition_code"] == "blocker_cleanup_required"


def test_update_rejects_blocked_to_done_with_close_action_hint(tmp_tickets: Path) -> None:
    path = make_ticket(
        tmp_tickets,
        "blocked.md",
        id="T-20260503-32",
        status="blocked",
        blocked_by=["T-20260503-31"],
        blocked_on="Waiting for the upstream fix.",
    )
    assert validate_target_ticket_file(path).ok
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-32",
        ticket,
        {"status": "done"},
        tmp_tickets,
    )

    assert response is not None
    assert response.state == "invalid_transition"
    assert response.data["valid_recovery_statuses"] == ["open"]
    assert "use close action" in response.message
```

- [ ] **Step 3: Run lifecycle tests and verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_validate.py plugins/turbo-mode/ticket/tests/test_execute.py::TestUpdate plugins/turbo-mode/ticket/tests/test_execute.py::TestCloseAndReopen plugins/turbo-mode/ticket/tests/test_engine_policy.py -q
```

Expected:

```text
Fails because in_progress is still in transition policy, blocked_on is not supported as an update section, blocker-cleanup preconditions are still old, and close does not remove Blocked On. `test_blocked_on_none_is_valid_section_removal_input` should already pass from Task 2; if it fails, fix Task 2's validation shape before continuing.
```

- [ ] **Step 4: Update transition table and blocked preconditions**

In `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`, replace `_VALID_TRANSITIONS` with:

```python
_VALID_TRANSITIONS: dict[str, set[str]] = {
    "idea": {"open"},
    "open": {"blocked"},
    "blocked": {"open"},
    "done": set(),
    "wontfix": set(),
}
```

Replace `_TRANSITION_PRECONDITIONS` with:

```python
_TRANSITION_PRECONDITIONS: dict[tuple[str, str], str] = {
    ("open", "blocked"): "blocked_on_required",
    ("blocked", "open"): "blocker_cleanup_required",
}
```

Remove the old `blocked_by_required` and `blockers_resolved_required` branches in `_check_transition_preconditions_with_detail()` and add:

```python
    if precondition == "blocked_on_required":
        blocked_on = _fields.get("blocked_on")
        if not isinstance(blocked_on, str) or not blocked_on.strip():
            return (
                "Transition to 'blocked' requires blocked_on",
                "blocked_on_required",
                {"missing": ["blocked_on"]},
            )
        return (None, "none", None)

    if precondition == "blocker_cleanup_required":
        blocked_by = _fields.get("blocked_by", ticket.blocked_by)
        blocked_on_present = "blocked_on" in _fields
        if blocked_by != [] or not blocked_on_present or _fields.get("blocked_on") is not None:
            return (
                "Transition to 'open' from blocked requires clearing blocked_by and Blocked On",
                "blocker_cleanup_required",
                {"required": ["blocked_by: []", "blocked_on: null"]},
            )
        return (None, "none", None)
```

The default must be `ticket.blocked_by`, not bare `None` and not unconditional `[]`. Omitted `blocked_by` is valid only when the existing ticket already has no ID blockers; otherwise the caller must send `blocked_by: []` so the frontmatter is actually cleared.

Update `_is_valid_transition()`:

```python
def _is_valid_transition(current: str, target: str, action: str) -> bool:
    """Check if a status transition is valid per the contract."""
    if action == "close":
        return current in {"open", "blocked"} and target in ("done", "wontfix")
    if action == "reopen":
        return current in ("done", "wontfix") and target == "open"
    valid = _VALID_TRANSITIONS.get(current, set())
    return target in valid
```

In `_evaluate_update_policy()`, keep `valid_recovery_statuses` as update-action recovery states only, but add a close-action hint when the requested target is terminal:

```python
        close_hint = (
            " (use close action)"
            if ticket.status in {"open", "blocked"} and new_status in _TERMINAL_STATUSES
            else ""
        )
```

Then build the invalid-transition message with `close_hint` before the existing reopen hint:

```python
                message=f"Cannot transition from {ticket.status} to {new_status} via update"
                + close_hint
                + (" (use reopen action)" if requires_reopen else ""),
```

Verify close recovery statuses in `_evaluate_close_policy()` still match the Task 1 close allowlist. If Task 1 did not already land this hunk, land it here together with `_is_valid_transition()`; do not leave `idea` close validity and recovery hints split across commits:

```python
    if ticket.status == "idea":
        valid_recovery_statuses = ["open"]
    elif ticket.status in _TERMINAL_STATUSES:
        valid_recovery_statuses = []
    else:
        valid_recovery_statuses = ["done", "wontfix"]
```

- [ ] **Step 5: Add Blocked On section update and removal support**

In `plugins/turbo-mode/ticket/scripts/ticket_validate.py`, verify the nullable `blocked_on` branch from Task 2 is still present:

```python
    if "blocked_on" in fields and fields["blocked_on"] is None:
        pass
    else:
        _validate_string_field(fields, "blocked_on", errors)
```

Keep `blocked_on` out of the main string-field tuple unconditionally. Final state: `blocked_on` is validated only by the nullable guard above, so `validate_fields({"blocked_on": None})` returns `[]` and unblock writes can remove the `Blocked On` section.

In `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`, add `blocked_on` to focused section fields:

```python
_UPDATE_FOCUSED_SECTION_FIELDS = frozenset({"problem", "next_action", "acceptance_criteria", "blocked_on"})
```

Add it to `_UPDATE_SECTION_FIELDS`:

```python
        "blocked_on",
```

Add it to `_UPDATE_SECTION_HEADINGS`:

```python
    "blocked_on": "Blocked On",
```

Add `_UPDATE_FOCUSED_SECTION_FIELDS`, `_UPDATE_SECTION_FIELDS`, and `_UPDATE_SECTION_HEADINGS` in the same edit. A partial edit that adds `blocked_on` to the allowed set without adding the heading map is invalid because `_execute_update()` indexes `_UPDATE_SECTION_HEADINGS[key]`.

Change `_focused_section_fields_allowed()` so status-changing blocked writes may target `blocked_on` and `next_action` without pretending to be focused refinement:

```python
def _focused_section_fields_allowed(fields: dict[str, Any], section_fields: list[str]) -> bool:
    """Return True for focused refinement or status-specific blocker section writes."""
    if fields.get("_update_mode") == _UPDATE_FOCUSED_MODE and all(
        field in _UPDATE_FOCUSED_SECTION_FIELDS for field in section_fields
    ):
        return True
    if fields.get("status") in {"blocked", "open"}:
        return all(field in {"blocked_on", "next_action"} for field in section_fields)
    return False
```

Add a section-removal helper:

```python
def _remove_section(text: str, heading: str) -> str:
    pattern = re.compile(
        rf"^## {re.escape(heading)}\n.*?(?=^## |\Z)",
        re.MULTILINE | re.DOTALL,
    )
    updated, _count = pattern.subn("", text, count=1)
    return updated.rstrip() + "\n"
```

Modify `_render_target_ticket_text()` in the `original_text is not None` branch:

```python
        for heading in targeted_headings:
            if heading in sections and sections[heading] is None:
                rendered_text = _remove_section(rendered_text, heading)
            else:
                rendered_text = _replace_or_append_section(
                    rendered_text,
                    heading,
                    str(sections.get(heading, "")),
                )
```

Also guard the full-render branch of `_render_target_ticket_text()` after widening `sections` to `dict[str, str | None]`:

```python
    rendered = ["---", render_frontmatter(_target_frontmatter(frontmatter)).rstrip("\n"), "---", ""]
    emitted: set[str] = set()
    for heading in TARGET_SECTIONS_REQUIRED:
        body = sections.get(heading, "")
        if body is None:
            body = ""
        rendered.extend([f"## {heading}", body.strip(), ""])
        emitted.add(heading)
    for heading, body in sections.items():
        if heading in emitted or body is None:
            continue
        rendered.extend([f"## {heading}", body.strip(), ""])
```

Modify `_render_update_section_value()`:

```python
def _render_update_section_value(key: str, value: Any) -> str | None:
    """Render focused section update values into markdown section content."""
    if value is None:
        return None
    if key == "acceptance_criteria":
        if not isinstance(value, list):
            return ""
        return "\n".join(f"- [ ] {criterion}" for criterion in value)
    return str(value)
```

When assigning section updates in `_execute_update()`, keep `None`:

```python
        rendered = _render_update_section_value(key, fields[key])
        old_rendered = ticket.sections.get(heading, "")
        if rendered is None or old_rendered.strip() != rendered.strip():
            changes["sections_changed"].append(heading)
        sections[heading] = rendered
```

Adjust type hints in `_render_target_ticket_text()` from `dict[str, str]` to `dict[str, str | None]`.

Land `_render_update_section_value()` returning `None`, the `_execute_update()` `rendered is None` guard, `_render_target_ticket_text()` type hints, the original-text removal branch, and the full-render `None` guard together. Splitting these edits creates either `rendered.strip()` on `None` or `body.strip()` on `None`.

- [ ] **Step 6: Clear blocker shape during terminal close**

In `_execute_close()` in `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`, after `data["status"] = resolution`, add:

```python
    if old_status == "blocked":
        previous_blocked_by = data.get("blocked_by", [])
        if previous_blocked_by:
            changes_blocked_by = [previous_blocked_by, []]
        else:
            changes_blocked_by = None
        data["blocked_by"] = []
        sections["Blocked On"] = None
```

Then change `new_text = _render_target_ticket_text(...)` to include the targeted heading:

```python
    targeted_headings = ("Blocked On",) if old_status == "blocked" else ()
    new_text = _render_target_ticket_text(
        data,
        sections,
        original_text=original_text,
        targeted_headings=targeted_headings,
    )
```

Build `changes` before returning:

```python
    changes = {"frontmatter": {"status": [old_status, resolution]}, "sections_changed": []}
    if old_status == "blocked":
        changes["sections_changed"].append("Blocked On")
        if changes_blocked_by is not None:
            changes["frontmatter"]["blocked_by"] = changes_blocked_by
```

- [ ] **Step 7: Run lifecycle tests and verify pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_validate.py plugins/turbo-mode/ticket/tests/test_execute.py::TestUpdate plugins/turbo-mode/ticket/tests/test_execute.py::TestCloseAndReopen plugins/turbo-mode/ticket/tests/test_engine_policy.py plugins/turbo-mode/ticket/tests/test_target_schema.py -q
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_validate.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/tests/test_validate.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_engine_policy.py
git commit -m "feat(ticket): enforce blocked lifecycle shape"
```

Expected:

```text
Commit succeeds with lifecycle policy and tests staged.
```

## Task 4: Status Drift Scan And Source/Docs Verification

**Files:**
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/scripts/ticket_parse.py`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/tests/test_parse.py`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/tests/test_validate.py`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/scripts/ticket_triage.py`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/tests/test_triage.py`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/scripts/ticket_read.py`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/tests/test_read.py`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/tests/test_integration.py`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/tests/test_entrypoints.py`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/tests/test_ux.py`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/tests/test_blocker_resolution.py`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/tests/test_capture_contract.py`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/tests/support/builders.py`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/README.md`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md`
- Modify as status-only drift requires: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- Read-only in this plan: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Read-only in this plan: `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
- Read-only in this plan: `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
- Read-only in this plan: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`

- [ ] **Step 1: Scan for stale normal target-status vocabulary**

Run:

```bash
rg -in "in[_ -]progress" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/references plugins/turbo-mode/ticket/skills plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/CHANGELOG.md
```

Expected:

```text
Before this task, the command may find current-facing target status drift in schema, validation, direct engine tests, parse tests, read/list tests, triage source/tests, integration tests, entrypoint examples, UX tests, blocker tests, capture-contract tests, fixture builders, README, HANDBOOK, SKILL.md files, contract references, and docs-contract assertions. It should also catch prose forms such as "in progress" and "In-progress" in triage wording. It may find unrelated historical strings such as activation_in_progress or activation-in-progress in runtime-readiness proof paths. Only current-facing target-ticket status drift is patched in this plan.
```

- [ ] **Step 2: Patch status-only source, tests, fixtures, and docs**

Apply these status-only replacements. Do not edit candidate-contract tests or runtime/gateway/discovery code in this plan.

```text
plugins/turbo-mode/ticket/scripts/ticket_parse.py:
  Change CANONICAL_STATUSES to frozenset({"idea", "open", "blocked", "done", "wontfix"}).
  Keep normalize_status() permissive: raw "in_progress" should pass through unchanged for legacy diagnostics because target rejection belongs to target schema and write-field validation.
  Remove the `_STATUS_MAP` path that normalizes "implementing" to "in_progress". Either map "implementing" to "open" as a legacy active alias or delete that alias and let raw "implementing" pass through as a diagnostic invalid status, but no normalization path may produce "in_progress".
  Preserve deferred->open diagnostics and do not rewrite make_gen3_ticket-style legacy evidence into "open" during parse.

plugins/turbo-mode/ticket/tests/test_parse.py:
  Import CANONICAL_STATUSES.
  Assert CANONICAL_STATUSES == frozenset({"idea", "open", "blocked", "done", "wontfix"}).
  Replace accepted status loop ("open", "in_progress", "done", "wontfix") with ("idea", "open", "blocked", "done", "wontfix").
  Add a parse-boundary assertion that normalize_status("in_progress") == ("in_progress", None) and name it as legacy diagnostic pass-through, not target acceptance.
  Add a regression proving normalize_status("implementing") does not return "in_progress"; use the implementation choice from ticket_parse.py ("open" if kept as an alias, otherwise "implementing").
  Keep migration tests that prove legacy gen-3 files can still expose status "in_progress" for cutover diagnostics.

plugins/turbo-mode/ticket/tests/test_validate.py:
  Replace accepted status loop ("open", "in_progress", "done", "wontfix") with ("idea", "open", "blocked", "done", "wontfix").
  Replace test_deprecated_blocked_status_rejected() with test_deprecated_in_progress_status_rejected().
  Add or keep a rejection assertion that validate_fields({"status": "in_progress"}) reports an invalid status.
  Keep test_blocked_on_none_is_valid_section_removal_input() from Task 3.

  The replacement status rejection test should be named test_deprecated_in_progress_status_rejected and assert:
    assert any("status" in error for error in validate_fields({"status": "in_progress"}))

plugins/turbo-mode/ticket/scripts/ticket_triage.py:
  Replace counts {"open": 0, "in_progress": 0} with {"idea": 0, "open": 0, "blocked": 0}.
  Keep non-terminal filtering broad enough to include idea/open/blocked.
  Treat stale tickets as open or blocked only; idea tickets are visible parked work and should not be stale by default.
  Remove review_in_progress suggestions.
  Replace the _next_actions high-priority reason "High-priority ticket is open and not in progress" with "High-priority ticket is open and ready to start or assign".
  Suggest blocker resolution from `status == "blocked"` or non-empty `blocked_by`; use reason text "Blocked ticket needs blocker resolution" for `status == "blocked"` and "Ticket has unresolved blocked_by dependencies" for non-empty `blocked_by` on diagnostic old records. Do not mention in-progress work.

plugins/turbo-mode/ticket/tests/test_triage.py:
  Replace active in_progress fixtures with open when the ticket is actionable.
  Replace active in_progress fixtures with blocked plus blocked_by/Blocked On when the test is about stuck work.
  In both-case fixtures that currently combine `status="in_progress"` with non-empty `blocked_by`, use `status="blocked"`, keep target-ID `blocked_by`, and add a non-empty `Blocked On` section through the builder. Do not leave non-empty `blocked_by` on `open` fixtures.
  In `test_status_counts`, invert the old `assert "blocked" not in result["counts"]` expectation; assert the blocked count key is present and populated for blocked fixtures.
  Add or update count assertions for counts["idea"], counts["open"], and counts["blocked"].
  Assert ideas remain visible in active_tickets but do not produce stale or next-action prompts by default.
  Assert blocked tickets appear in blocked counts, stale checks when old enough, and blocker-resolution suggestions.

plugins/turbo-mode/ticket/scripts/ticket_read.py:
  Replace status_rank old values with target order: {"idea": "0", "open": "1", "blocked": "2", "done": "8", "wontfix": "9"}.
  Remove "in_progress" from the normal rank map.
  Keep the unknown fallback for invalid-state diagnostics; do not make read/list silently accept old current target status.

plugins/turbo-mode/ticket/tests/test_read.py:
  Add or update list/read payload ordering coverage for idea, open, blocked, done, and wontfix.
  Remove current-facing expectations that in_progress has a normal sort rank.

plugins/turbo-mode/ticket/tests/test_integration.py:
  Replace "Create -> update to in_progress -> close" with "Create -> update to blocked -> unblock or close".
  For open -> blocked writes, include fields {"status": "blocked", "blocked_on": "Waiting for upstream work."} and blocked_by when the test needs ticket-ID dependency data.
  For unblock writes, include fields {"status": "open", "blocked_by": [], "blocked_on": None, "next_action": "Continue."}.

plugins/turbo-mode/ticket/tests/test_entrypoints.py:
  Replace normal JSON payloads that set {"status": "in_progress"} with {"status": "blocked", "blocked_on": "Waiting for upstream work."} when they test blocked flow, or {"status": "open"} when they test generic status update plumbing.

plugins/turbo-mode/ticket/tests/test_ux.py:
  Replace user-visible in_progress fixtures with open for normal active tickets.
  Use blocked plus visible Blocked On only when the expected UX text is about blocker state.
  In fixtures that currently combine `status="in_progress"` with non-empty `blocked_by`, use `status="blocked"`, keep target-ID `blocked_by`, and pass a non-empty `blocked_on` builder argument.

plugins/turbo-mode/ticket/tests/test_blocker_resolution.py:
  Replace FakeTicket("...", "in_progress") and target fixtures that model blocked work with status "blocked".
  Ensure any real target file with status "blocked" has blocked_by values that are target ticket IDs and a non-empty Blocked On section.
  In fixtures that currently combine `status="in_progress"` with non-empty `blocked_by`, use `status="blocked"`, keep target-ID `blocked_by`, and pass a non-empty `blocked_on` builder argument.

plugins/turbo-mode/ticket/tests/test_capture_contract.py:
  Replace close-readiness current target fixtures using status="in_progress" with status="open".
  If a fixture combines `status="in_progress"` with non-empty `blocked_by`, treat it as blocked work instead: use `status="blocked"` with visible `Blocked On`.
  Keep concrete Acceptance Criteria in any fixture that checks close-readiness for resolution="done"; `done` still requires the target AC precondition.
  Do not change capture-field rejection tests unless their fixture status blocks target validation.

plugins/turbo-mode/ticket/tests/support/builders.py:
  Leave make_ticket() default status as "open"; it is already the desired active default.
  Preserve make_gen3_ticket() status: in_progress as legacy fenced-YAML evidence for migration tests.
  Add a blocked_on parameter when not already added by Task 2, and render ## Blocked On only for a non-empty blocked_on string.
  Keep the Task 2 post-dedent insertion pattern; do not interpolate a zero-indented blocked_on_section inside the textwrap.dedent f-string.

plugins/turbo-mode/ticket/README.md:
  Replace current status prose and schema tables so target statuses are idea, open, blocked, done, and wontfix.
  Document blocked tickets as status: blocked with a non-empty ## Blocked On section and optional blocked_by ticket IDs.
  Delete or invert the old target-shape sentence that says `blocked` is not a status and blockedness derives from `blocked_by`; if reverse blockers are mentioned, state only that there is no persisted reverse `blocks` edge.
  Leave old statuses only in explicitly historical or diagnostic sections.

plugins/turbo-mode/ticket/HANDBOOK.md:
  Replace current status prose, status values, and command examples with idea/open/blocked/done/wontfix.
  Update any --status examples that still list in_progress.
  Delete or invert the old target-shape sentence that says `blocked` is not a status and blockedness derives from `blocked_by`; if reverse blockers are mentioned, state only that there is no persisted reverse `blocks` edge.
  Leave in_progress only in explicitly historical or diagnostic language.

plugins/turbo-mode/ticket/references/ticket-contract.md:
  Keep the exact phrase "Optional sections are preserved byte-for-byte" on one line so test_contract_preserves_optional_sections_byte_for_byte passes.
  Replace any current-facing status list with idea/open/blocked/done/wontfix.
  Document status: blocked plus non-empty Blocked On as the visible blocked-ticket shape; keep blocked_by as optional ticket-ID dependency data, not the source of blockedness.

plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md:
  Replace "Target statuses are `open`, `in_progress`, `done`, and `wontfix`" with "Target statuses are `idea`, `open`, `blocked`, `done`, and `wontfix`".
  Replace "`blocked` is not a status" with "`blocked` is a first-class status and requires a non-empty `Blocked On` section".
  Keep the reverse-edge boundary: there is no persisted reverse `blocks` field; reverse blockers are derived by scanning `blocked_by`.

plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md:
  Replace "Target statuses are `open`, `in_progress`, `done`, and `wontfix`" with "Target statuses are `idea`, `open`, `blocked`, `done`, and `wontfix`".
  Describe `blocked_on` as the writable adapter for the `Blocked On` section when moving `open -> blocked` or clearing blocker shape on `blocked -> open`.
  Replace "`blocked` is not a status" with first-class blocked-ticket shape language, while keeping the no persisted reverse `blocks` field boundary.

plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md:
  Replace target status prose with idea/open/blocked/done/wontfix.
  Update the list example from `--status open|in_progress|done|wontfix` to `--status idea|open|blocked|done|wontfix`.
  Replace the old statement that target blockedness derives from `blocked_by` with first-class `status: blocked` plus visible `Blocked On`; keep `blocked_by` as optional ID dependency data.

plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md:
  Replace "Persisted `blocked` status and reverse `blocks` edges are not target schema; target blockedness derives from `blocked_by`" with prose that says backlog triage reads first-class `status: blocked` tickets, reports `blocked_by` dependency chains, and never writes tickets or persisted reverse `blocks` edges.
  Keep the read/query/reporting-only boundary and capture-prompt-only guidance unchanged except for status vocabulary.

plugins/turbo-mode/ticket/tests/test_docs_contract.py:
  Remove assertions that require `in_progress` in current target docs.
  In OLD_SCHEMA_TERMS, remove "blocked status" and "`blocked` status" because those phrases are valid under the new target model; keep or replace only guards that still prohibit a persisted reverse `blocks` field/edge. Do not delete the confinement guard that intentionally keeps `in_progress` in deprecated/diagnostic sections only.
  Keep or update test_contract_preserves_optional_sections_byte_for_byte so it matches the one-line contract prose above.
  In test_readme_ticket_schema_matches_yaml_contract_boundary(), remove the assertions for "`blocked` is not a status" and "derive reverse `blocks`"; replace them with positive assertions for `blocked`, `status: blocked`, and `Blocked On`.
  In test_ticket_find_skill_contract_is_read_only(), remove the contradictory assertion `assert "`blocked`" not in target`; replace it with positive assertions that read-ticket documents `status: blocked`, `Blocked On`, and the updated `--status idea|open|blocked|done|wontfix` example.
  In test_ticket_review_skill_contract_is_read_only_and_capture_prompt_only(), replace assertions requiring "Persisted `blocked` status and reverse `blocks` edges are not target schema" and "target blockedness derives from `blocked_by`" with assertions that triage remains read/query/reporting-only over first-class blocked tickets and does not write persisted reverse `blocks` edges.
  Keep the new README/HANDBOOK/SKILL prose strings identical to the new assertions; do not assert paraphrases that the docs step does not write.
  Add assertions that README, HANDBOOK, ticket-contract.md, capture-ticket, update-ticket, read-ticket, and ticket-backlog-triage include idea/open/blocked/done/wontfix as current target statuses where they document target shape.
  Add assertions that current docs and SKILL files describe `status: blocked` plus visible `Blocked On` rather than deriving blockedness only from blocked_by.
```

- [ ] **Step 3: Re-run the stale status scan**

Run:

```bash
rg -in "in[_ -]progress" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/references plugins/turbo-mode/ticket/skills plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/CHANGELOG.md
```

Expected:

```text
No remaining hit represents a current-facing target status, normal mutation fixture, ordinary Ticket board status, or current-facing prose phrase like "in progress" / "In-progress". Allowed remaining hits are explicitly historical, diagnostic, or unrelated strings such as activation_in_progress and activation-in-progress. If a hit is ambiguous, either patch it in this task or add a short test/doc comment explaining why it is diagnostic rather than a valid target status.
```

- [ ] **Step 4: Confirm candidate-contract migration stayed deferred**

Run:

```bash
rg -n "CandidateMutation|evaluate_autonomy_intent|build_engine_dispatch|discover_candidate_mutations|make_candidate_mutation_identity|reopen_reason|correction\b|blocker_edit|reprioritize|stale_cleanup|refine" plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py
```

Expected:

```text
The command still finds old candidate-contract vocabulary. That is expected in this plan. Do not patch those hits here; record them in closeout as the required next source slice.
```

- [ ] **Step 5: Run deferred-boundary smoke**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py -q
```

Expected:

```text
The deferred candidate-contract suites still pass. A failure here means the status/read/list changes leaked into the deferred autonomous candidate surface and must be understood before closeout; do not patch candidate-contract source in this plan unless the failure is caused by the status/read/list changes just made.
```

- [ ] **Step 6: Run focused source/docs tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_target_schema.py plugins/turbo-mode/ticket/tests/test_parse.py plugins/turbo-mode/ticket/tests/test_validate.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_engine_policy.py plugins/turbo-mode/ticket/tests/test_triage.py plugins/turbo-mode/ticket/tests/test_read.py plugins/turbo-mode/ticket/tests/test_integration.py plugins/turbo-mode/ticket/tests/test_entrypoints.py plugins/turbo-mode/ticket/tests/test_ux.py plugins/turbo-mode/ticket/tests/test_blocker_resolution.py plugins/turbo-mode/ticket/tests/test_capture_contract.py plugins/turbo-mode/ticket/tests/test_docs_contract.py -q
```

Expected:

```text
All selected status-shape tests pass.
```

- [ ] **Step 7: Run full Ticket suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected:

```text
Full Ticket test suite passes. Record the exact pass count and warning count in closeout.
```

- [ ] **Step 8: Run ruff and diff check**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket

git diff --check
```

Expected:

```text
ruff reports no issues, and git diff --check reports no whitespace errors.
```

- [ ] **Step 9: Inspect final diff before closeout**

Run:

```bash
git diff --stat HEAD
git diff -- plugins/turbo-mode/ticket/scripts/ticket_target_schema.py plugins/turbo-mode/ticket/scripts/ticket_validate.py plugins/turbo-mode/ticket/scripts/ticket_render.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/scripts/ticket_parse.py plugins/turbo-mode/ticket/scripts/ticket_triage.py plugins/turbo-mode/ticket/scripts/ticket_read.py plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/references/ticket-contract.md plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md
```

Expected:

```text
Diff shows only source/test/docs updates for target status and blocked-ticket shape. It does not touch autonomous candidate runtime, installed cache, local runtime state, marketplace metadata, or unrelated handoff artifacts.
```

- [ ] **Step 10: Commit Task 4**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_target_schema.py plugins/turbo-mode/ticket/scripts/ticket_validate.py plugins/turbo-mode/ticket/scripts/ticket_render.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/scripts/ticket_parse.py plugins/turbo-mode/ticket/scripts/ticket_triage.py plugins/turbo-mode/ticket/scripts/ticket_read.py plugins/turbo-mode/ticket/tests/support/builders.py plugins/turbo-mode/ticket/tests/test_target_schema.py plugins/turbo-mode/ticket/tests/test_parse.py plugins/turbo-mode/ticket/tests/test_validate.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_engine_policy.py plugins/turbo-mode/ticket/tests/test_triage.py plugins/turbo-mode/ticket/tests/test_read.py plugins/turbo-mode/ticket/tests/test_integration.py plugins/turbo-mode/ticket/tests/test_entrypoints.py plugins/turbo-mode/ticket/tests/test_ux.py plugins/turbo-mode/ticket/tests/test_blocker_resolution.py plugins/turbo-mode/ticket/tests/test_capture_contract.py plugins/turbo-mode/ticket/tests/test_docs_contract.py plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/references/ticket-contract.md plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md
git commit -m "fix(ticket): align target status source drift"
```

Expected:

```text
Commit succeeds with only the named target status and blocked-ticket shape source/test/docs/SKILL/reference files staged. Candidate-contract runtime files and deferred candidate-contract tests are not staged.
```

## Deferred Follow-Up: Candidate Contract Migration

The next plan must migrate the autonomous candidate contract as a whole-surface API change. It must cover at least these surfaces in one coherent source/test slice:

- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`: `CandidateMutation`, `CandidateTarget`, `_candidate_shape_errors()`, `evaluate_autonomy_intent()`, terminal-action allowlisting, `correct`, `reopen`, fanout, evidence floor, and identity calls.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`: `GatewayMutation` field/section split or an equivalent dispatch boundary, `build_engine_dispatch()`, `_decision_error()`, `_change_history_reason()`, mutation identity recomputation, and gateway application tests.
- `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`: `_candidate_from_mapping()`, `_possible_candidate_from_mapping()`, `_append_path_candidates()`, exact top-level candidate shape, and `test_candidate_discovery.py`.
- `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`: payload fields `target`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`.
- `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`, `test_engine_gateway.py`, `test_autonomy_corrections.py`, `test_mutation_identity.py`, `test_candidate_discovery.py`, and at least one integration path through `evaluate_autonomy_intent()` plus `apply_autonomous_mutation()`.

The follow-up plan must explicitly resolve `reopen`: either migrate it to `evidence_summary` and `status`-targeted shape per the control doc, including `reopen -> blocked`, or state a temporary source-level deferral with failing/xfail-free tests that keep the old behavior out of normal candidate migration claims.

## Deferred Follow-Up: Live Ticket Data Compatibility

This source slice does not migrate project-local `docs/tickets/` records. Task 0 must still scan for `status: in_progress` records before implementation starts and record the result. If old records exist, the follow-up is a ticket-data migration or diagnostic inventory path, not silent dashboard dropping. Normal Ticket product/runtime paths should reject non-normalized active ticket files after this slice; explicit diagnostic inventory paths may still read them to explain what is wrong.

Keep terminal resolution validation separate from target status vocabulary. `VALID_RESOLUTIONS` should remain `done/wontfix` for close actions; future candidate-contract or fingerprinting work must not treat `in_progress` as a terminal resolution or as a normal target status.

## Acceptance Criteria

- `TARGET_STATUSES` is exactly `("idea", "open", "blocked", "done", "wontfix")`.
- `in_progress` is rejected as target status in target schema and write-field validation.
- Parse canonical statuses are `idea/open/blocked/done/wontfix`, while raw `in_progress` remains only a legacy diagnostic pass-through and is not treated as target acceptance.
- Target validation accepts blocked tickets only when `Blocked On` is present and non-empty.
- Target validation rejects `Blocked On` and non-empty `blocked_by` on non-blocked tickets.
- Target validation rejects `blocked_by` entries that are not `T-YYYYMMDD-NN` IDs.
- No parse normalization path maps any input to `in_progress`; raw old statuses remain diagnostic only.
- Create defaults to `open`.
- Create accepts explicit `idea`.
- Create accepts explicit `blocked` only with visible blocker prose.
- Create rejects `done` and `wontfix` in normal mutation flow.
- `idea` can promote only to `open` through `update`.
- `open` can move to `blocked` through `update`; `update` rejects `open -> done` and `open -> wontfix` because terminal writes use `close`.
- `blocked` can move to `open` through `update` or to `done`/`wontfix` through `close`.
- `done` and `wontfix` remain terminal except existing `reopen -> open`.
- Moving from `blocked` to `open`, `done`, or `wontfix` clears non-empty `blocked_by` and removes `Blocked On`.
- Moving from `blocked` to `open` may omit `blocked_by` only when existing `blocked_by` is already empty; if existing `blocked_by` is non-empty, the update must explicitly send `blocked_by: []`.
- Triage counts and read/list ordering expose `idea`, `open`, and `blocked` without normal `in_progress` buckets or ranks.
- The stale-status scan catches `in_progress`, `in progress`, and `In-progress` current-facing drift, with only explicit historical/diagnostic/unrelated hits remaining.
- README, HANDBOOK, ticket-contract.md, relevant SKILL.md files, and docs-contract tests present `idea/open/blocked/done/wontfix` as current target authority and describe visible blocked-ticket shape.
- README/HANDBOOK/SKILL/docs-contract assertions no longer encode the old rule that `blocked` is not a status or that target blockedness derives only from `blocked_by`; docs may still prohibit persisted reverse `blocks` edges.
- Focused tests, full Ticket suite, ruff, and `git diff --check` pass before any completion claim.

## Verification Commands

Run these before closeout:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_target_schema.py plugins/turbo-mode/ticket/tests/test_parse.py plugins/turbo-mode/ticket/tests/test_validate.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_engine_policy.py plugins/turbo-mode/ticket/tests/test_triage.py plugins/turbo-mode/ticket/tests/test_read.py plugins/turbo-mode/ticket/tests/test_integration.py plugins/turbo-mode/ticket/tests/test_entrypoints.py plugins/turbo-mode/ticket/tests/test_ux.py plugins/turbo-mode/ticket/tests/test_blocker_resolution.py plugins/turbo-mode/ticket/tests/test_capture_contract.py plugins/turbo-mode/ticket/tests/test_docs_contract.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket
git diff --check
```

Do not run guarded refresh, cache refresh, plugin install, or live runtime mutation commands in this slice.

## Self-Review

Spec coverage:

- Target status model: covered by Tasks 1, 2, 3, and 4.
- Visible `Blocked On` truth and optional `blocked_by`: covered by Tasks 1, 2, and 3.
- Terminal normal create rejection: covered by Task 2.
- Status-only source/test/docs drift: covered by Task 4.
- Strict nested candidate closure: intentionally excluded because it is a shared API migration across evaluator, gateway, discovery, identity, correction/reopen semantics, and integration tests.
- Operation-log recovery facts: intentionally excluded because they require canonical post-write fingerprint design.
- Reconciliation caps and overflow: intentionally excluded because they are wrapper behavior, not direct target status or blocked-ticket shape behavior.

Placeholder scan:

- This plan contains concrete file paths, code snippets, commands, and expected results.
- No plan step relies on unspecified error handling or generic edge-case language.

Type consistency:

- Target status vocabulary is `idea/open/blocked/done/wontfix` across schema, writable-field validation, direct engine tests, triage/read surfaces, README, HANDBOOK, ticket-contract.md, SKILL.md files, and status-only fixtures.
- Parse keeps a separate legacy-diagnostic boundary: `CANONICAL_STATUSES` matches the target vocabulary, but raw old statuses can still pass through to be rejected or inventoried by downstream target validation.
- `blocked_on` is a write-field adapter for the visible `Blocked On` section. `Blocked On` remains the target-ticket section heading in file content.
- Candidate target shape, mutation identity, `correct`, and `reopen` are deferred. This plan must not claim `CandidateTarget`, `expected_ticket_fingerprint`, or `evidence_summary` runtime support.

## Execution Handoff

Implement this plan only after a fresh live status check. Keep commits task-sized and do not claim installed runtime proof.

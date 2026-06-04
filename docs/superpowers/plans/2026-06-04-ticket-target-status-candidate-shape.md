# Ticket Target Status And Candidate Shape Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring Ticket source/tests into the new target status and candidate-shape contract for `idea`, `open`, `blocked`, `done`, and `wontfix`, without claiming installed-runtime proof.

**Architecture:** This is a source/repo implementation slice, not a cache refresh or runtime inventory slice. It updates target ticket validation first, then teaches create/update/close code to preserve blocked-ticket shape, then tightens autonomous candidate shape so `target` and `proposed_change` are closed and explicit. Operation-log recovery fingerprints and `reconcile_board` batching are separate follow-up slices because they touch retry semantics and wrapper-level result aggregation.

**Tech Stack:** Python >=3.11, dataclasses, PyYAML, existing Ticket scripts, pytest, ruff, bytecode-safe `uv run` verification.

---

## Scope Check

This plan covers one coherent source/test slice.

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
- Replace the flat autonomous candidate shape with explicit `target.fields`, `target.sections`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary` validation.

Out of scope:

- Private operation-log retention, post-write fingerprints, and summary-emission recovery.
- `reconcile_board` discovery, ordering, caps, and compact overflow.
- Installed plugin cache mutation under `/Users/jp/.codex/plugins/cache`.
- Runtime inventory through `plugin/read`, `plugin/list`, `skills/list`, or `hooks/list`.
- Publishing, pushing, or pull request work.

Closeout claim for this plan:

```text
The local source/repo Ticket lane now enforces the new target status vocabulary, validates visible blocked-ticket shape, rejects terminal normal creates, clears blocker shape on unblocking and terminal writes, and validates autonomous candidates against the explicit target/proposed_change contract. Installed runtime remains unclaimed.
```

Do not use that claim until every verification gate in this plan passes.

## Live Baseline

Baseline from the planning turn:

- Branch: `chore/ticket-candidate-contract-control-doc`
- HEAD: `06a0a9ed`
- Worktree: clean before this plan file
- Primary authority: `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
- Known source drift:
  - `plugins/turbo-mode/ticket/scripts/ticket_target_schema.py` still defines `TARGET_STATUSES = ("open", "in_progress", "done", "wontfix")`.
  - `plugins/turbo-mode/ticket/tests/test_target_schema.py` still asserts the old status tuple.
  - `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py` still uses `in_progress` in transition policy and create always renders `status="open"`.
  - `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py` still models candidates as flat `proposed_change` plus internal evidence links.

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

- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
  - Owns plan/preflight/execute policy and direct write behavior.
  - Update create status handling, transition policy, blocked section writes, and blocker cleanup.

- `plugins/turbo-mode/ticket/tests/test_execute.py`
  - Owns direct user execute behavior.
  - Add create/update/close blocked-shape tests and update old `in_progress` expectations.

- `plugins/turbo-mode/ticket/tests/test_engine_policy.py`
  - Owns shared read-only policy evaluator expectations.
  - Add policy-data coverage for `idea`, `blocked`, and invalid legacy `in_progress`.

- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
  - Owns candidate dataclasses, fanout policy, runtime decision selection, and candidate-to-engine dispatch.
  - Add explicit candidate target shape and reject old action aliases as normal candidate actions.

- `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
  - Owns structured candidate extraction from turn context.
  - Parse only the new explicit candidate shape for `candidate_mutations`.

- `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
  - Owns deterministic mutation identity input.
  - Include `target` and `evidence_summary` in the mutation fingerprint.

- `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
  - Owns runtime decision and mapping tests.
  - Update candidate fixtures to use explicit targets and assert closure failures.

- `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`
  - Owns identity payload regression tests.
  - Add target/evidence-summary identity binding.

- `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
  - Owns gateway validation against runtime decisions.
  - Update candidate construction and gateway mutation fields to the explicit candidate shape.

Do not create new source modules in this slice. The existing files already define the ownership boundaries, and a new abstraction would mostly hide contract changes that should remain visible at these boundaries.

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
## chore/ticket-candidate-contract-control-doc
06a0a9ed
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

## Task 1: Target Status Constants And Blocked File Shape

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_target_schema.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_target_schema.py`

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

Keep the existing priority rejection parametrization, but remove `("status", "blocked")` from it because `blocked` is now valid when the ticket has valid blocked shape.

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

- [ ] **Step 3: Run the target schema tests and verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_target_schema.py -q
```

Expected:

```text
Fails because TARGET_STATUSES still contains in_progress, blocked is not accepted by constants, and status-specific Blocked On validation does not exist.
```

- [ ] **Step 4: Implement target status and blocked-shape validation**

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

- [ ] **Step 5: Run the schema tests and verify pass**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_target_schema.py -q
```

Expected:

```text
All tests in test_target_schema.py pass.
```

- [ ] **Step 6: Commit Task 1**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_target_schema.py plugins/turbo-mode/ticket/tests/test_target_schema.py
git commit -m "test(ticket): enforce target blocked status schema"
```

Expected:

```text
Commit succeeds with only target schema and target schema tests staged.
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

Add `blocked_on` to the string-field loop:

```python
        "blocked_on",
```

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

Build a local section string before `content = textwrap.dedent(...)`:

```python
    blocked_on_section = f"\n## Blocked On\n{blocked_on}\n" if blocked_on else ""
```

Insert it between `## Next Action` and `## Change History`:

```python
        ## Next Action
        Continue work on this ticket.
        {blocked_on_section}
        ## Change History
```

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
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
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
        assert "idea" in response.message

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

- [ ] **Step 2: Add failing policy evaluator tests**

In `plugins/turbo-mode/ticket/tests/test_engine_policy.py`, replace `in_progress` fixtures with `open` or `blocked`, then add:

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
    ticket = parse_ticket(path)
    assert ticket is not None

    response = _evaluate_update_policy(
        "T-20260503-30",
        ticket,
        {"status": "open", "blocked_by": [], "blocked_on": None, "next_action": "Continue."},
        tmp_tickets,
    )

    assert response is None


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

- [ ] **Step 3: Run lifecycle tests and verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_execute.py::TestUpdate plugins/turbo-mode/ticket/tests/test_execute.py::TestCloseAndReopen plugins/turbo-mode/ticket/tests/test_engine_policy.py -q
```

Expected:

```text
Fails because in_progress is still in transition policy, blocked_on is not supported as an update section, and close does not remove Blocked On.
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

Remove the old `blocked_by_required` branch in `_check_transition_preconditions_with_detail()` and add:

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
        blocked_by = _fields.get("blocked_by")
        blocked_on_present = "blocked_on" in _fields
        if blocked_by != [] or not blocked_on_present or _fields.get("blocked_on") is not None:
            return (
                "Transition to 'open' from blocked requires clearing blocked_by and Blocked On",
                "blocker_cleanup_required",
                {"required": ["blocked_by: []", "blocked_on: null"]},
            )
        return (None, "none", None)
```

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

Update close recovery statuses:

```python
    if ticket.status == "idea":
        valid_recovery_statuses = ["open"]
    elif ticket.status in _TERMINAL_STATUSES:
        valid_recovery_statuses = []
    else:
        valid_recovery_statuses = ["done", "wontfix"]
```

- [ ] **Step 5: Add Blocked On section update and removal support**

In `plugins/turbo-mode/ticket/scripts/ticket_validate.py`, allow nullable `blocked_on`:

```python
    if "blocked_on" in fields and fields["blocked_on"] is None:
        pass
    else:
        _validate_string_field(fields, "blocked_on", errors)
```

Remove `blocked_on` from the main string-field tuple if Step 3 added it there.

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
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_execute.py::TestUpdate plugins/turbo-mode/ticket/tests/test_execute.py::TestCloseAndReopen plugins/turbo-mode/ticket/tests/test_engine_policy.py plugins/turbo-mode/ticket/tests/test_target_schema.py -q
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 8: Commit Task 3**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_validate.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_engine_policy.py
git commit -m "feat(ticket): enforce blocked lifecycle shape"
```

Expected:

```text
Commit succeeds with lifecycle policy and tests staged.
```

## Task 4: Explicit Candidate Target Shape

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`

- [ ] **Step 1: Add failing runtime tests for candidate target closure**

In `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`, change `_candidate()` to accept explicit target defaults:

```python
def _candidate(
    action: str,
    *,
    ticket_id: str = "T-20260527-01",
    target: dict[str, tuple[str, ...]] | None = None,
    proposed_change: dict[str, object] | None = None,
    evidence_summary: str = "Current turn supports this ticket mutation.",
    evidence: tuple[EvidenceLink, ...] | None = None,
    conflict_reason: str | None = None,
) -> CandidateMutation:
    change = {"priority": "low"} if proposed_change is None else proposed_change
    target_shape = target or {"fields": tuple(change), "sections": ()}
    return CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        target=target_shape,
        proposed_change=change,
        expected_ticket_fingerprint=None,
        evidence_summary=evidence_summary,
        evidence=evidence or _evidence("current_thread_reason"),
        conflict_reason=conflict_reason,
    )
```

Then add:

```python
def test_candidate_requires_target_keys_to_match_proposed_change() -> None:
    candidate = _candidate(
        "update",
        target={"fields": ("priority",), "sections": ("Next Action",)},
        proposed_change={"priority": "low"},
    )

    dispatch = map_candidate_to_engine(candidate)

    assert dispatch.state == "policy_blocked"
    assert dispatch.reason == "candidate_shape_invalid"


def test_candidate_rejects_unknown_target_field() -> None:
    candidate = _candidate(
        "update",
        target={"fields": ("candidate_id",), "sections": ()},
        proposed_change={"candidate_id": "bad"},
    )

    dispatch = map_candidate_to_engine(candidate)

    assert dispatch.state == "policy_blocked"
    assert dispatch.reason == "candidate_shape_invalid"


def test_candidate_allows_optional_section_removal_with_null() -> None:
    candidate = _candidate(
        "update",
        target={"fields": ("status", "blocked_by"), "sections": ("Blocked On", "Next Action")},
        proposed_change={
            "status": "open",
            "blocked_by": [],
            "Blocked On": None,
            "Next Action": "Continue the implementation.",
        },
    )

    dispatch = map_candidate_to_engine(candidate)

    assert dispatch.state == "ok"
    assert dispatch.action == EngineAction.UPDATE
    assert dispatch.fields == {
        "status": "open",
        "blocked_by": [],
        "blocked_on": None,
        "next_action": "Continue the implementation.",
    }
```

- [ ] **Step 2: Add failing identity tests for target and evidence summary**

In `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`, update `_identity()` to pass target and evidence summary:

```python
def _identity(
    *,
    target_fingerprint: str | None = "ticket-state-a",
    target: dict[str, tuple[str, ...]] | None = None,
    evidence_summary: str = "Current turn supports this ticket mutation.",
):
    return make_candidate_mutation_identity(
        thread_id="thread-1",
        turn_id="turn-1",
        ticket_id="T-20260527-01",
        action="update",
        target=target or {"fields": ("priority",), "sections": ()},
        proposed_change={"priority": "high"},
        expected_ticket_fingerprint=target_fingerprint,
        evidence_summary=evidence_summary,
        evidence=(
            {"kind": "current_thread_reason", "ref": "test", "freshness": "fresh"},
        ),
    )
```

Replace `test_candidate_payload_excludes_branch_scope()` with:

```python
def test_candidate_payload_includes_target_and_evidence_summary() -> None:
    payload = candidate_mutation_payload(
        ticket_id="T-20260527-01",
        action="update",
        target={"fields": ("priority",), "sections": ()},
        proposed_change={"priority": "high"},
        expected_ticket_fingerprint="ticket-state-a",
        evidence_summary="Current turn supports this ticket mutation.",
    )

    assert payload == {
        "ticket_id": "T-20260527-01",
        "action": "update",
        "target": {"fields": ["priority"], "sections": []},
        "proposed_change": {"priority": "high"},
        "expected_ticket_fingerprint": "ticket-state-a",
        "evidence_summary": "Current turn supports this ticket mutation.",
    }


def test_target_shape_binds_mutation_identity() -> None:
    first = _identity(target={"fields": ("priority",), "sections": ()})
    second = _identity(target={"fields": (), "sections": ("Next Action",)})

    assert first.mutation_id != second.mutation_id
    assert first.mutation_fingerprint != second.mutation_fingerprint


def test_evidence_summary_binds_mutation_identity() -> None:
    first = _identity(evidence_summary="Priority changed because the user asked.")
    second = _identity(evidence_summary="Priority changed because tests failed.")

    assert first.mutation_id != second.mutation_id
    assert first.mutation_fingerprint != second.mutation_fingerprint
```

- [ ] **Step 3: Run autonomy and identity tests and verify failure**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py -q
```

Expected:

```text
Fails because CandidateMutation has no target, expected_ticket_fingerprint, or evidence_summary fields, and identity helpers do not accept target.
```

- [ ] **Step 4: Add CandidateTarget and candidate-shape validation**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`, import target schema constants:

```python
from scripts.ticket_target_schema import TARGET_FRONTMATTER_FIELDS, validate_target_section_name
```

Add:

```python
_CANDIDATE_ACTIONS = frozenset({"create", "update", "done", "wontfix", "reopen", "correct"})
_CANDIDATE_TARGET_FIELDS = frozenset(TARGET_FRONTMATTER_FIELDS) - {"id"}
_SECTION_FIELD_TO_ENGINE_FIELD = {
    "Problem": "problem",
    "Next Action": "next_action",
    "Blocked On": "blocked_on",
    "Acceptance Criteria": "acceptance_criteria",
}


@dataclass(frozen=True, slots=True)
class CandidateTarget:
    """User-visible target fields and sections named by a candidate."""

    fields: tuple[str, ...]
    sections: tuple[str, ...]

    @classmethod
    def from_mapping(cls, value: Mapping[str, object]) -> CandidateTarget:
        fields = value.get("fields")
        sections = value.get("sections")
        if set(value) != {"fields", "sections"}:
            raise ValueError("target must have exactly fields and sections")
        if not isinstance(fields, (list, tuple)) or not all(isinstance(item, str) for item in fields):
            raise ValueError("target.fields must be a list of strings")
        if not isinstance(sections, (list, tuple)) or not all(isinstance(item, str) for item in sections):
            raise ValueError("target.sections must be a list of strings")
        return cls(tuple(fields), tuple(sections))

    def as_payload(self) -> dict[str, list[str]]:
        return {"fields": list(self.fields), "sections": list(self.sections)}


def _candidate_shape_errors(candidate: CandidateMutation) -> list[str]:
    errors: list[str] = []
    if candidate.action not in _CANDIDATE_ACTIONS:
        errors.append(f"unsupported action: {candidate.action}")
    for field in candidate.target.fields:
        if field not in _CANDIDATE_TARGET_FIELDS:
            errors.append(f"unknown target field: {field}")
    for section in candidate.target.sections:
        if not validate_target_section_name(section):
            errors.append(f"invalid target section: {section}")
    expected_keys = set(candidate.target.fields) | set(candidate.target.sections)
    actual_keys = set(candidate.proposed_change)
    if expected_keys != actual_keys:
        errors.append(
            f"proposed_change keys must match target keys: expected {sorted(expected_keys)!r}, got {sorted(actual_keys)!r}"
        )
    if "\n" in candidate.evidence_summary or not candidate.evidence_summary.strip():
        errors.append("evidence_summary must be one non-empty line")
    if candidate.action == "create":
        if candidate.ticket_id is not None:
            errors.append("create ticket_id must be null")
        if candidate.expected_ticket_fingerprint is not None:
            errors.append("create expected_ticket_fingerprint must be null")
    else:
        if not candidate.ticket_id:
            errors.append(f"{candidate.action} ticket_id is required")
        if not candidate.expected_ticket_fingerprint:
            errors.append(f"{candidate.action} expected_ticket_fingerprint is required")
    return errors
```

Then replace `CandidateMutation` with:

```python
@dataclass(frozen=True, slots=True)
class CandidateMutation:
    """A proposed Ticket mutation candidate."""

    ticket_id: str | None
    action: str
    target: CandidateTarget | Mapping[str, object]
    proposed_change: Mapping[str, object]
    expected_ticket_fingerprint: str | None
    evidence_summary: str
    evidence: tuple[EvidenceLink, ...]
    conflict_reason: str | None = None

    def __post_init__(self) -> None:
        if isinstance(self.target, Mapping):
            object.__setattr__(self, "target", CandidateTarget.from_mapping(self.target))
```

Do not raise in `__post_init__`; runtime policy should return a blocked dispatch/decision rather than making candidate construction a crash path.

- [ ] **Step 5: Map target sections to engine fields**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`, add:

```python
def _engine_fields_from_candidate(candidate: CandidateMutation) -> dict[str, object]:
    fields: dict[str, object] = {}
    for key, value in candidate.proposed_change.items():
        if key in candidate.target.fields:
            fields[key] = value
            continue
        if key in candidate.target.sections:
            engine_key = _SECTION_FIELD_TO_ENGINE_FIELD.get(key)
            if engine_key is None:
                fields[key] = value
            else:
                fields[engine_key] = value
    return fields
```

At the top of `map_candidate_to_engine()`, validate candidate shape:

```python
    shape_errors = _candidate_shape_errors(candidate)
    if shape_errors:
        return EngineDispatch("policy_blocked", None, {}, "candidate_shape_invalid")
    fields = _engine_fields_from_candidate(candidate)
```

Replace the old `fields = dict(candidate.proposed_change)` line with the new helper.

Change the `done` and `wontfix` mapping to use the control-doc shape:

```python
    if candidate.action == "done":
        if fields.get("status") != "done":
            return EngineDispatch("policy_blocked", None, {}, "close_fields_not_allowlisted")
        return EngineDispatch("ok", EngineAction.CLOSE, {"resolution": "done"})
    if candidate.action == "wontfix":
        if fields.get("status") != "wontfix":
            return EngineDispatch("policy_blocked", None, {}, "close_fields_not_allowlisted")
        return EngineDispatch("ok", EngineAction.CLOSE, {"resolution": "wontfix"})
```

Change correction action spelling from `correction` to `correct`:

```python
    if candidate.action == "correct" and fields.get("status") in {"done", "wontfix"}:
        return EngineDispatch("ok", EngineAction.CLOSE, {"resolution": fields["status"]})
```

- [ ] **Step 6: Bind target and evidence summary into mutation identity**

In `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`, change signatures:

```python
def _target_payload(target: Mapping[str, object]) -> dict[str, list[str]]:
    fields = target.get("fields", ())
    sections = target.get("sections", ())
    return {
        "fields": list(fields) if isinstance(fields, (list, tuple)) else [],
        "sections": list(sections) if isinstance(sections, (list, tuple)) else [],
    }


def candidate_mutation_payload(
    *,
    ticket_id: str | None,
    action: str,
    target: Mapping[str, object],
    proposed_change: Mapping[str, object],
    expected_ticket_fingerprint: str | None,
    evidence_summary: str,
) -> dict[str, object]:
    """Return the canonical payload used for mutation identity."""
    return {
        "ticket_id": ticket_id,
        "action": action,
        "target": _target_payload(target),
        "proposed_change": dict(proposed_change),
        "expected_ticket_fingerprint": expected_ticket_fingerprint,
        "evidence_summary": evidence_summary,
    }
```

Then update `make_candidate_mutation_identity()` to accept `target`, `expected_ticket_fingerprint`, and `evidence_summary`, and pass those into `candidate_mutation_payload()`.

In `ticket_autonomy_runtime._identity_for_candidate()`, call:

```python
    return make_candidate_mutation_identity(
        thread_id=thread_id,
        turn_id=turn_id,
        action=candidate.action,
        ticket_id=candidate.ticket_id,
        target=candidate.target.as_payload(),
        proposed_change=candidate.proposed_change,
        expected_ticket_fingerprint=target_fingerprint,
        evidence_summary=candidate.evidence_summary,
        evidence=_evidence_payload(candidate),
    )
```

- [ ] **Step 7: Parse explicit candidate shape in discovery**

In `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`, change `_candidate_from_mapping()` so it requires the new top-level keys:

```python
def _candidate_from_mapping(item: Mapping[str, object]) -> CandidateMutation | None:
    required_keys = {
        "action",
        "ticket_id",
        "target",
        "proposed_change",
        "expected_ticket_fingerprint",
        "evidence_summary",
    }
    if set(item) - (required_keys | {"evidence", "conflict_reason"}):
        return None
    if not required_keys.issubset(item):
        return None
    ticket_id = item.get("ticket_id")
    action = item.get("action")
    target = item.get("target")
    proposed_change = item.get("proposed_change")
    expected_ticket_fingerprint = item.get("expected_ticket_fingerprint")
    evidence_summary = item.get("evidence_summary")
    conflict_reason = item.get("conflict_reason")
    if ticket_id is not None and not isinstance(ticket_id, str):
        return None
    if expected_ticket_fingerprint is not None and not isinstance(expected_ticket_fingerprint, str):
        return None
    if not isinstance(action, str) or not action:
        return None
    if not isinstance(target, Mapping):
        return None
    if not isinstance(proposed_change, Mapping):
        return None
    if not isinstance(evidence_summary, str) or not evidence_summary.strip():
        return None
    evidence = _evidence_from_mapping(item, default_ref=evidence_summary)
    return CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        target=target,
        proposed_change=dict(proposed_change),
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
        evidence=evidence,
        conflict_reason=conflict_reason if isinstance(conflict_reason, str) else None,
    )
```

Remove `_normalize_candidate_change()`. Candidate callers must supply `status` for terminal writes rather than relying on `resolution` adaptation.

- [ ] **Step 8: Update gateway and tests to pass explicit candidate shape**

In `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`, update `build_engine_dispatch()`:

```python
    target = {
        "fields": tuple(dict(mutation.fields)),
        "sections": (),
    }
    candidate = CandidateMutation(
        ticket_id=mutation.ticket_id,
        action=mutation.action,
        target=target,
        proposed_change=dict(mutation.fields),
        expected_ticket_fingerprint=mutation.target_fingerprint,
        evidence_summary="Gateway mutation dispatch.",
        evidence=(),
    )
```

In tests, every `CandidateMutation(...)` construction must include these fields:

```python
target={"fields": tuple(fields), "sections": ()},
expected_ticket_fingerprint=target_fp,
evidence_summary="Current turn supports this ticket mutation.",
```

For create candidates, pass `expected_ticket_fingerprint=None`.

For unblocking candidates, use section names:

```python
target={"fields": ("status", "blocked_by"), "sections": ("Blocked On", "Next Action")},
proposed_change={
    "status": "open",
    "blocked_by": [],
    "Blocked On": None,
    "Next Action": "Continue the implementation.",
},
```

- [ ] **Step 9: Run autonomy, identity, gateway, and correction tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py -q
```

Expected:

```text
All selected tests pass with explicit candidate target shape.
```

- [ ] **Step 10: Commit Task 4**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py
git commit -m "feat(ticket): require explicit candidate target shape"
```

Expected:

```text
Commit succeeds with candidate runtime and tests staged.
```

## Task 5: Static Drift Scans And Focused Verification

**Files:**
- Possibly modify: `plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py`
- Possibly modify: `plugins/turbo-mode/ticket/CHANGELOG.md`
- Possibly modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`

- [ ] **Step 1: Scan for stale status and action vocabulary**

Run:

```bash
rg -n "in_progress|blocker_edit|reprioritize|stale_cleanup|correction\\b|reopen_reason|resolution" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/references plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/CHANGELOG.md
```

Expected:

```text
Remaining hits are either historical legacy fixtures, diagnostic repair references, or close-engine translation details. Any hit in current candidate contract, target schema, normal runtime tests, or user-facing contract prose is source drift and must be patched in this task.
```

- [ ] **Step 2: Add or adjust static drift tests**

If stale vocabulary survives in current-facing docs or runtime surfaces, add a focused static assertion to `plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py`:

```python
def test_current_candidate_contract_uses_target_shape_vocabulary() -> None:
    for path in CURRENT_FACING_DOCS:
        target = _target_sections(_read(path))
        normalized = _normalize(target).lower()
        assert "proposed_change" in normalized
        assert "expected_ticket_fingerprint" in normalized
        assert "evidence_summary" in normalized
        assert "blocker_edit" not in normalized
        assert "reprioritize" not in normalized
        assert "stale_cleanup" not in normalized
        assert "reopen_reason" not in normalized
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py -q
```

Expected:

```text
The static boundary tests pass, or fail only on current-facing stale text that this task then patches.
```

- [ ] **Step 3: Run focused source tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_target_schema.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_engine_policy.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py -q
```

Expected:

```text
All selected tests pass.
```

- [ ] **Step 4: Run full Ticket suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected:

```text
Full Ticket test suite passes. Record the exact pass count and warning count in closeout.
```

- [ ] **Step 5: Run ruff and diff check**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket
git diff --check
```

Expected:

```text
ruff reports no issues, and git diff --check reports no whitespace errors.
```

- [ ] **Step 6: Inspect final diff before closeout**

Run:

```bash
git diff --stat HEAD
git diff -- plugins/turbo-mode/ticket/scripts/ticket_target_schema.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py
```

Expected:

```text
Diff shows only source/test/doc updates for this slice. It does not touch installed cache, local runtime state, or unrelated handoff artifacts.
```

- [ ] **Step 7: Commit final drift/doc cleanup if needed**

If Task 5 changed only docs/static drift tests, commit it separately:

```bash
git add plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py plugins/turbo-mode/ticket/CHANGELOG.md plugins/turbo-mode/ticket/references/ticket-contract.md plugins/turbo-mode/ticket/README.md
git commit -m "docs(ticket): align candidate status source drift"
```

Expected:

```text
Commit succeeds only if Task 5 made additional tracked changes.
```

## Acceptance Criteria

- `TARGET_STATUSES` is exactly `("idea", "open", "blocked", "done", "wontfix")`.
- `in_progress` is rejected as target status in target schema and write-field validation.
- Target validation accepts blocked tickets only when `Blocked On` is present and non-empty.
- Target validation rejects `Blocked On` and non-empty `blocked_by` on non-blocked tickets.
- Target validation rejects `blocked_by` entries that are not `T-YYYYMMDD-NN` IDs.
- Create defaults to `open`.
- Create accepts explicit `idea`.
- Create accepts explicit `blocked` only with visible blocker prose.
- Create rejects `done` and `wontfix` in normal mutation flow.
- `idea` can promote only to `open`.
- `open` can move to `blocked`.
- `blocked` can move to `open`, `done`, or `wontfix`.
- `done` and `wontfix` remain terminal except existing `reopen -> open`.
- Moving from `blocked` to `open`, `done`, or `wontfix` clears non-empty `blocked_by` and removes `Blocked On`.
- Autonomous candidates validate explicit `target.fields` and `target.sections`.
- `proposed_change` keys exactly equal the union of target fields and sections.
- Optional section removal is represented by a targeted section with `None`.
- Mutation identity includes `target`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`.
- Focused tests, full Ticket suite, ruff, and `git diff --check` pass before any completion claim.

## Verification Commands

Run these before closeout:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_target_schema.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_engine_policy.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket
git diff --check
```

Do not run guarded refresh, cache refresh, plugin install, or live runtime mutation commands in this slice.

## Self-Review

Spec coverage:

- Target status model: covered by Tasks 1, 2, and 3.
- Visible `Blocked On` truth and optional `blocked_by`: covered by Tasks 1, 2, and 3.
- Terminal normal create rejection: covered by Task 2.
- Strict nested candidate closure: covered by Task 4.
- Operation-log recovery facts: intentionally excluded because they require canonical post-write fingerprint design.
- Reconciliation caps and overflow: intentionally excluded because they are wrapper behavior, not single-candidate schema behavior.

Placeholder scan:

- This plan contains concrete file paths, code snippets, commands, and expected results.
- No plan step relies on unspecified error handling or generic edge-case language.

Type consistency:

- Candidate target shape uses `CandidateTarget(fields: tuple[str, ...], sections: tuple[str, ...])`.
- External candidate mapping accepts `target={"fields": (...), "sections": (...)}` and normalizes through `CandidateTarget.from_mapping()`.
- Mutation identity uses `expected_ticket_fingerprint`, matching the control doc. Existing internal variable names such as `target_fingerprint` may remain local only where they describe the current ticket fingerprint, but identity payload output must use `expected_ticket_fingerprint`.

## Execution Handoff

Implement this plan only after a fresh live status check. Keep commits task-sized and do not claim installed runtime proof.

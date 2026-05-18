# Ticket Capture-First Redesign Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the backend-shaped Ticket skill surface with a capture-first user experience, making `ticket-capture` the only user-facing creation path and splitting the rest of the plugin into focused intent-based skills.

**Architecture:** Keep the existing ticket engine, validation, rendering, parsing, dedup, and write primitives as the source of truth, but add a purpose-built `ticket_capture.py` orchestration entrypoint for the flagship capture workflow. Persist a narrow set of capture metadata in ticket frontmatter, render capture-created tickets with synthesized sections, and split the skill UX into `ticket-capture`, `ticket-find`, `ticket-update`, `ticket-review`, and explicit-only `ticket-doctor`. Do not preserve the old broad `ticket` skill or command taxonomy.

**Tech Stack:** Python >=3.11, pytest, YAML fenced Markdown tickets, Codex skills, `plugin-eval`, bytecode-safe `uv run` verification.

---

## Decision Freeze

These decisions are the product contract for this redesign. Do not re-open them during implementation unless a live test or source invariant proves they are impossible.

| Area | Frozen decision |
| --- | --- |
| Flagship | `ticket-capture` is the flagship user surface. |
| Creation UX | `ticket-capture` is the only user-facing creation path. The old generic `create` path remains internal only. |
| Skill taxonomy | Ship `ticket-capture`, `ticket-find`, `ticket-update`, `ticket-review`, and `ticket-doctor`. Remove the old broad `ticket` skill entirely. |
| Capture inference | Infer aggressively and ask at most one follow-up only when the ticket would be materially bad: missing title, no actionable problem, no useful next action, ambiguous duplicate, or unsafe write target. |
| Low confidence | Low-confidence capture is allowed without a pre-question when there is at least one actionable next step. No useful next action is the blocker. |
| Placeholder model | Keep `status: open`; represent placeholder quality as metadata: `refinement_status: needs_refinement` plus tag `needs-refinement`. |
| User wording | Never store raw user wording in the ticket body. The agent writes synthesized ticket content. |
| Capture provenance | Persist `capture_confidence`, `capture_source`, optional `refinement_status`, optional `component`, and `related_paths`. |
| Ticket body | Capture-created tickets always render `Captured Request`, `Problem`, `Next Action`, and `Acceptance Criteria`. |
| Acceptance criteria | `Acceptance Criteria: Needs refinement` is allowed only when `refinement_status: needs_refinement` is set. Close/readiness must reject it until replaced. Medium/high confidence captures synthesize 1-3 concrete criteria. |
| Duplicate detection | Always run duplicate detection before preview. Default is create anyway unless the user names a ticket ID or the top candidate matches the same normalized title plus the same core file/component. |
| Confirmation | Every capture write requires explicit confirmation in v1. Fast-write can only be a future opt-in after real usage proves preview quality. |
| Preview | Default preview shows only title, problem, next action, confidence, duplicate, and the create/edit/cancel prompt. Priority appears only when not `medium` or confidence is low. |
| Edit | `edit` is free-form but scoped. It regenerates the preview and records edit history in the payload only, not in the persisted ticket. |
| Multi-ticket capture | Deferred in v1. If the user asks to split, capture the first/clearest ticket and return a suggested second capture prompt after creation. |
| Priority | Default `medium`. `critical` only for explicit production/data-loss/security/release-blocking language. `high` only for explicit blocker/regression/CI-red/cannot-ship language. `low` only for explicit cleanup/polish/nice-to-have language. |
| Tags | Auto-create only small machine-useful tags: `needs-refinement`, `bug`, `feature`, `docs`, `test`, `maintenance`, `security`. Do not invent component tags freely. |
| Paths | Infer `related_paths` only from explicit user text and immediately discussed files in the current turn. Do not scan the whole git diff by default. |
| Component | `component` is optional. Set it only when user-supplied or obvious from explicit paths. |
| Triggering | Allow implicit capture phrases such as "track", "file", "capture", "ticket", and "remember this as follow-up". Do not trigger capture from broad statements like "this is a bug" without an action verb. |
| Update | `ticket-update` supports narrow refinement plus lifecycle/metadata changes with preview. It does not support arbitrary body-section editing in v1. |
| Refinement clearing | Auto-clear `refinement_status` only when acceptance criteria are concrete and problem/next action are no longer placeholders. Preview must say `Refinement: will clear needs-refinement`. |
| Find/review | `ticket-find` groups `needs_refinement` tickets separately. `ticket-review` is read-only and can recommend capture prompts, not write tickets. |
| Doctor | `ticket-doctor` is explicit-only for storage/plugin health and audit repair. Casual "audit tickets" belongs to read-only `ticket-review`. |

## Non-Goals

- Do not mutate `/Users/jp/.codex/plugins/cache`, install plugins, refresh cache, or claim installed-runtime behavior.
- Do not preserve backward compatibility for the old `ticket` skill name or broad `/ticket` UX.
- Do not split into one skill per verb.
- Do not implement multi-ticket capture in v1.
- Do not add arbitrary body editing to `ticket-update` in v1.
- Do not scan the entire git diff to infer capture paths.
- Do not introduce a new lifecycle status for `needs_refinement`.

## Source Files To Read First

Before implementation, re-read these live files. Historical handoffs or this plan are not substitutes for source truth.

- `plugins/turbo-mode/ticket/references/ticket-contract.md`
- `plugins/turbo-mode/ticket/scripts/ticket_render.py`
- `plugins/turbo-mode/ticket/scripts/ticket_parse.py`
- `plugins/turbo-mode/ticket/scripts/ticket_validate.py`
- `plugins/turbo-mode/ticket/scripts/ticket_read.py`
- `plugins/turbo-mode/ticket/scripts/ticket_ux.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- `plugins/turbo-mode/ticket/scripts/ticket_workflow.py`
- `plugins/turbo-mode/ticket/scripts/ticket_dedup.py`
- `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py`
- `plugins/turbo-mode/ticket/skills/ticket/SKILL.md`
- `plugins/turbo-mode/ticket/skills/ticket-triage/SKILL.md`
- `plugins/turbo-mode/ticket/.codex-plugin/plugin.json`

## File Structure

- `docs/superpowers/plans/2026-05-18-ticket-capture-first-redesign.md` - this execution-control plan.
- `plugins/turbo-mode/ticket/references/ticket-contract.md` - update contract version guidance, capture metadata fields, capture-created sections, refinement semantics, and skill taxonomy.
- `plugins/turbo-mode/ticket/scripts/ticket_render.py` - add capture metadata ordering and render support for `Captured Request` and `Next Action`.
- `plugins/turbo-mode/ticket/scripts/ticket_parse.py` - expose capture metadata on `ParsedTicket`.
- `plugins/turbo-mode/ticket/scripts/ticket_validate.py` - validate capture metadata, controlled tags, `related_paths`, and the `Needs refinement` acceptance-criteria rule.
- `plugins/turbo-mode/ticket/scripts/ticket_read.py` - include capture metadata in JSON read output and group refinement tickets for find/review consumers.
- `plugins/turbo-mode/ticket/scripts/ticket_ux.py` - add pure helpers for compact capture preview, refinement readiness, and priority inference labels.
- `plugins/turbo-mode/ticket/scripts/ticket_capture.py` - create purpose-built `prepare` and `execute` entrypoint for capture.
- `plugins/turbo-mode/ticket/scripts/ticket_update.py` - later slice: narrow update/refinement entrypoint with preview.
- `plugins/turbo-mode/ticket/scripts/ticket_review.py` - later slice: read-only review summaries and suggested capture prompts.
- `plugins/turbo-mode/ticket/scripts/ticket_doctor.py` - later slice or wrapper around existing doctor/audit repair behavior.
- `plugins/turbo-mode/ticket/skills/ticket/SKILL.md` - delete; do not keep as alias.
- `plugins/turbo-mode/ticket/skills/ticket-triage/SKILL.md` - replace with `ticket-review` or delete after migration.
- `plugins/turbo-mode/ticket/skills/ticket-capture/SKILL.md` - create flagship capture skill.
- `plugins/turbo-mode/ticket/skills/ticket-find/SKILL.md` - create read/search/list skill.
- `plugins/turbo-mode/ticket/skills/ticket-update/SKILL.md` - create refine/lifecycle/metadata skill.
- `plugins/turbo-mode/ticket/skills/ticket-review/SKILL.md` - create read-only backlog health skill.
- `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md` - create explicit-only maintenance skill.
- `plugins/turbo-mode/ticket/README.md` and `plugins/turbo-mode/ticket/HANDBOOK.md` - update user-facing command model after the split.
- `plugins/turbo-mode/ticket/.codex-plugin/plugin.json` - update prompts and, if still missing, add interface URLs before release-readiness evaluation.
- `plugins/turbo-mode/ticket/tests/test_capture.py` - new capture entrypoint tests.
- `plugins/turbo-mode/ticket/tests/test_capture_contract.py` - new schema/render/parse/read refinement tests.
- Existing tests to update: `test_render.py`, `test_parse.py`, `test_validate.py`, `test_read.py`, `test_ux.py`, `test_docs_contract.py`, `test_entrypoints.py`, `test_workflow.py`, `test_workflow_execute.py`, `test_triage.py`, `test_doctor.py`.

## Verification Harness

Use bytecode-safe commands from the repo instructions.

Focused Ticket tests:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

Changed-path lint:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check <changed-python-paths>
```

Skill/plugin static evaluation after skill split:

```bash
plugin-eval analyze /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/ticket --format markdown
```

Whitespace gate:

```bash
git diff --check
```

## Stop Conditions

- If capture cannot execute through the existing hook provenance and mutation trust model without weakening `ticket_engine_core.py` safety checks, stop and redesign the capture entrypoint around the existing runner instead of bypassing provenance.
- If `Needs refinement` can close as `done`, stop and repair close-readiness before moving on.
- If the skill split causes ambiguous triggers between `ticket-capture`, `ticket-find`, `ticket-update`, or `ticket-review`, stop and narrow descriptions before implementation proceeds.
- If generated residue appears in plugin source paths (`__pycache__`, `.pytest_cache`, `.ruff_cache`, `.plugin-eval`), clean it with `trash` if cleanup is in scope, or report it as a blocker.
- If any task would require installed-cache mutation, stop. That is a separate installed-refresh/certification lane.

## Commit Boundaries

- Commit 1: plan only.
- Commit 2: persisted schema, renderer/parser/validator/read support, close-readiness refinement gate.
- Commit 3: `ticket_capture.py` backend and tests.
- Commit 4: `ticket-capture` skill and docs for the flagship flow.
- Commit 5: `ticket-find`, `ticket-update`, `ticket-review`, `ticket-doctor` skill split and old skill removal.
- Commit 6: later backend refinements for `ticket-update`, `ticket-review`, and `ticket-doctor`.
- Commit 7: plugin-eval/readiness cleanup, manifest prompts/URLs, final docs.

---

### Task 0: Baseline and Plan Authority

**Files:**
- Commit: `docs/superpowers/plans/2026-05-18-ticket-capture-first-redesign.md`

- [ ] **Step 1: Confirm starting branch and status**

```bash
git status --short --branch
```

Expected: branch name recorded; unrelated dirty files are identified before work starts.

- [ ] **Step 2: Run the current Ticket suite before source edits**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected: current baseline captured. If it fails, stop and classify baseline failures before editing source.

- [ ] **Step 3: Commit this plan if the user asks for a committed control document**

```bash
git add docs/superpowers/plans/2026-05-18-ticket-capture-first-redesign.md
git commit -m "docs: plan ticket capture-first redesign"
```

Expected: plan is tracked as execution authority. Do not stage source code with this commit.

---

### Task 1: Persisted Capture Schema and Refinement Contract

**Files:**
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_render.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_parse.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_validate.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_read.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_ux.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Test: `plugins/turbo-mode/ticket/tests/test_capture_contract.py`
- Test: update `plugins/turbo-mode/ticket/tests/test_render.py`
- Test: update `plugins/turbo-mode/ticket/tests/test_parse.py`
- Test: update `plugins/turbo-mode/ticket/tests/test_validate.py`
- Test: update `plugins/turbo-mode/ticket/tests/test_read.py`
- Test: update `plugins/turbo-mode/ticket/tests/test_ux.py`

- [ ] **Step 1: Write failing contract tests**

Create `plugins/turbo-mode/ticket/tests/test_capture_contract.py` with tests equivalent to this shape:

```python
from __future__ import annotations

from pathlib import Path

from scripts.ticket_parse import parse_ticket
from scripts.ticket_render import render_ticket
from scripts.ticket_validate import validate_fields


def test_capture_ticket_renders_required_sections_and_metadata(tmp_path: Path) -> None:
    text = render_ticket(
        id="T-20260518-01",
        title="Capture follow-up for hook guard preview",
        date="2026-05-18",
        status="open",
        priority="medium",
        source={"type": "capture", "ref": "", "session": "session-1"},
        tags=["bug", "needs-refinement"],
        problem="The hook guard preview needs a user-friendly capture path.",
        captured_request="Create a follow-up for improving the hook guard preview.",
        next_action="Clarify the expected preview behavior for hook guard failures.",
        capture_confidence="low",
        capture_source="conversation",
        refinement_status="needs_refinement",
        component="ticket",
        related_paths=["plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py"],
        acceptance_criteria=["Needs refinement"],
    )

    assert "capture_confidence: low" in text
    assert "capture_source: conversation" in text
    assert "refinement_status: needs_refinement" in text
    assert "component: ticket" in text
    assert "related_paths: [plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py]" in text
    assert "## Captured Request\nCreate a follow-up for improving the hook guard preview." in text
    assert "## Problem\nThe hook guard preview needs a user-friendly capture path." in text
    assert "## Next Action\nClarify the expected preview behavior for hook guard failures." in text
    assert "## Acceptance Criteria\n- [ ] Needs refinement" in text

    path = tmp_path / "ticket.md"
    path.write_text(text, encoding="utf-8")
    parsed = parse_ticket(path)
    assert parsed is not None
    assert parsed.capture_confidence == "low"
    assert parsed.capture_source == "conversation"
    assert parsed.refinement_status == "needs_refinement"
    assert parsed.component == "ticket"
    assert parsed.related_paths == ["plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py"]


def test_needs_refinement_acceptance_criteria_requires_refinement_status() -> None:
    errors = validate_fields({
        "title": "Incomplete ticket",
        "problem": "The captured issue is still vague.",
        "acceptance_criteria": ["Needs refinement"],
    })
    assert "acceptance_criteria Needs refinement requires refinement_status=needs_refinement" in errors


def test_capture_metadata_rejects_invalid_values() -> None:
    errors = validate_fields({
        "capture_confidence": "certain",
        "capture_source": 123,
        "refinement_status": "rough",
        "component": ["ticket"],
        "related_paths": "plugins/turbo-mode/ticket",
    })
    assert "capture_confidence must be one of ['high', 'low', 'medium'], got 'certain'" in errors
    assert "capture_source must be a string, got int" in errors
    assert "refinement_status must be 'needs_refinement', got 'rough'" in errors
    assert "component must be a string, got list" in errors
    assert "related_paths must be a list, got str" in errors
```

- [ ] **Step 2: Run the new tests and verify they fail for missing support**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_capture_contract.py -q
```

Expected: failures for missing render arguments, missing `ParsedTicket` attributes, and missing validation errors.

- [ ] **Step 3: Extend validation constants and field checks**

In `scripts/ticket_validate.py`, add constants:

```python
VALID_CAPTURE_CONFIDENCE = frozenset({"low", "medium", "high"})
VALID_REFINEMENT_STATUSES = frozenset({"needs_refinement"})
CONTROLLED_CAPTURE_TAGS = frozenset({
    "needs-refinement",
    "bug",
    "feature",
    "docs",
    "test",
    "maintenance",
    "security",
})
```

Update `validate_fields()` so:

- `captured_request`, `next_action`, `capture_source`, and `component` are optional strings.
- `capture_confidence` is one of `low`, `medium`, `high`.
- `refinement_status`, when present, is exactly `needs_refinement`.
- `related_paths` is `list[str]`.
- `Acceptance Criteria: Needs refinement` is valid only with `refinement_status: needs_refinement`.
- `needs-refinement` tag is valid only with `refinement_status: needs_refinement`.

- [ ] **Step 4: Extend rendering**

In `scripts/ticket_render.py`:

- Add `capture_confidence`, `capture_source`, `refinement_status`, `component`, and `related_paths` to `CANONICAL_FIELD_ORDER` after `source` and before `tags`.
- Add optional `captured_request`, `next_action`, `capture_confidence`, `capture_source`, `refinement_status`, `component`, and `related_paths` parameters to `render_ticket()`.
- Render `## Captured Request` before `## Problem` when `captured_request` is provided.
- Render `## Next Action` after `## Problem` when `next_action` is provided.
- Persist metadata only when present, except `capture_source` for capture-created tickets, which `ticket_capture.py` must always provide as `conversation`.

- [ ] **Step 5: Extend parsing**

In `scripts/ticket_parse.py`:

- Add fields to `ParsedTicket`: `capture_confidence: str = ""`, `capture_source: str = ""`, `refinement_status: str = ""`, `component: str = ""`, `related_paths: list[str] = field(default_factory=list)`.
- Return those fields from `parse_ticket()` using frontmatter defaults.
- Do not require these fields for legacy tickets.

- [ ] **Step 6: Extend read output and refinement grouping primitives**

In `scripts/ticket_read.py`, include the new fields in `_ticket_to_dict()`:

```python
"capture": {
    "confidence": ticket.capture_confidence,
    "source": ticket.capture_source,
    "refinement_status": ticket.refinement_status,
    "component": ticket.component,
    "related_paths": ticket.related_paths,
},
```

Add a pure helper:

```python
def split_refinement_tickets(tickets: list[ParsedTicket]) -> dict[str, list[ParsedTicket]]:
    return {
        "needs_refinement": [ticket for ticket in tickets if ticket.refinement_status == "needs_refinement"],
        "ready": [ticket for ticket in tickets if ticket.refinement_status != "needs_refinement"],
    }
```

- [ ] **Step 7: Add close-readiness rejection for refinement placeholders**

In `scripts/ticket_engine_core.py`, update the `done` precondition path so a ticket with `refinement_status: needs_refinement` or an acceptance criteria section containing only `Needs refinement` cannot transition to `done`.

Expected user-facing message:

```text
Transition to 'done' requires concrete acceptance criteria; ticket still needs refinement
```

Expected `precondition_code`: `missing_acceptance_criteria`.

- [ ] **Step 8: Update contract documentation**

In `references/ticket-contract.md`:

- Add the new optional YAML fields.
- State that `status: open` remains the lifecycle state for placeholders.
- Document the four capture-created body sections.
- Document the close/readiness rejection for `Needs refinement`.
- Document controlled auto-tags and optional `component`.

- [ ] **Step 9: Run focused and full Ticket tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_capture_contract.py tests/test_render.py tests/test_parse.py \
  tests/test_validate.py tests/test_read.py tests/test_ux.py -q
```

Expected: pass.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected: pass.

- [ ] **Step 10: Lint changed Python and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check \
  plugins/turbo-mode/ticket/scripts/ticket_render.py \
  plugins/turbo-mode/ticket/scripts/ticket_parse.py \
  plugins/turbo-mode/ticket/scripts/ticket_validate.py \
  plugins/turbo-mode/ticket/scripts/ticket_read.py \
  plugins/turbo-mode/ticket/scripts/ticket_ux.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/tests/test_capture_contract.py
```

```bash
git diff --check
git add \
  plugins/turbo-mode/ticket/references/ticket-contract.md \
  plugins/turbo-mode/ticket/scripts/ticket_render.py \
  plugins/turbo-mode/ticket/scripts/ticket_parse.py \
  plugins/turbo-mode/ticket/scripts/ticket_validate.py \
  plugins/turbo-mode/ticket/scripts/ticket_read.py \
  plugins/turbo-mode/ticket/scripts/ticket_ux.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/tests/test_capture_contract.py \
  plugins/turbo-mode/ticket/tests/test_render.py \
  plugins/turbo-mode/ticket/tests/test_parse.py \
  plugins/turbo-mode/ticket/tests/test_validate.py \
  plugins/turbo-mode/ticket/tests/test_read.py \
  plugins/turbo-mode/ticket/tests/test_ux.py
git commit -m "feat(ticket): add capture metadata schema"
```

---

### Task 2: Purpose-Built `ticket_capture.py` Backend

**Files:**
- Create: `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- Test: `plugins/turbo-mode/ticket/tests/test_capture.py`
- Modify if needed: `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py`
- Modify if needed: `plugins/turbo-mode/ticket/tests/test_hook.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_entrypoints.py`

- [ ] **Step 1: Write failing capture entrypoint tests**

Create `tests/test_capture.py` with these behavioral cases:

- `prepare` returns compact preview fields and no write.
- `prepare` rejects low-confidence capture with no useful `next_action`.
- `prepare` allows low-confidence capture with `next_action` and `refinement_status: needs_refinement`.
- `prepare` always runs duplicate detection and surfaces `duplicate.default_action`.
- `prepare` defaults duplicate action to `create_anyway` unless strong duplicate rules apply.
- `execute` writes exactly one capture-created ticket after confirmation/provenance.
- `edit` updates payload `edit_history` and regenerates preview without persisting edit history.
- split request returns single-ticket preview plus `suggested_next_capture`, not two writes.

Use payloads with this shape:

```json
{
  "tickets_dir": "/absolute/project/docs/tickets",
  "session_id": "session-1",
  "capture": {
    "title": "Capture follow-up for hook guard preview",
    "captured_request": "Create a follow-up for improving the hook guard preview.",
    "problem": "The hook guard preview needs a user-friendly capture path.",
    "next_action": "Clarify the expected preview behavior for hook guard failures.",
    "capture_confidence": "low",
    "priority": "medium",
    "tags": ["bug", "needs-refinement"],
    "refinement_status": "needs_refinement",
    "component": "ticket",
    "related_paths": ["plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py"],
    "acceptance_criteria": ["Needs refinement"]
  },
  "edit_history": []
}
```

- [ ] **Step 2: Run capture tests and verify they fail for missing entrypoint**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_capture.py -q
```

Expected: import/file-not-found failures for `scripts.ticket_capture`.

- [ ] **Step 3: Implement `ticket_capture.py prepare`**

`ticket_capture.py prepare <PAYLOAD_PATH>` must:

- Load payload JSON.
- Resolve `PROJECT_ROOT` and `TICKETS_DIR` using existing path helpers.
- Validate `capture` fields through `validate_fields()`.
- Enforce no raw user wording fields. Reject keys named `raw_user_text`, `raw_request`, or `transcript_excerpt`.
- Require title, synthesized captured request, problem, and next action.
- Allow `capture_confidence: low` if `next_action` is non-empty.
- Apply priority inference only when priority is absent.
- Apply controlled tags only.
- Run duplicate detection using the existing create planning/dedup behavior.
- Compute strong duplicate default:
  - `update_existing` only when payload includes an explicit `target_ticket_id`, or same normalized title plus same component or related path core.
  - otherwise `create_anyway`.
- Write enriched payload back atomically.
- Return JSON with `state: "ready_to_execute"` and this preview object:

```json
{
  "title": "Capture follow-up for hook guard preview",
  "problem": "The hook guard preview needs a user-friendly capture path.",
  "next_action": "Clarify the expected preview behavior for hook guard failures.",
  "confidence": "low",
  "priority": "medium",
  "duplicate": {
    "label": "none",
    "ticket_id": null,
    "title": "",
    "default_action": "create_anyway"
  },
  "prompt": "Create this ticket? [create / edit / cancel]",
  "exceptional_fields": {
    "priority": "medium",
    "refinement_status": "needs_refinement",
    "related_paths": ["plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py"]
  }
}
```

- [ ] **Step 4: Implement `ticket_capture.py execute`**

`ticket_capture.py execute <PAYLOAD_PATH>` must:

- Require the payload to contain successful prepare artifacts.
- Refuse execution when preview state is stale or missing.
- Dispatch to the existing create engine path rather than writing ticket files directly.
- Preserve existing execute provenance requirements. If the existing runner requires hook-injected metadata, capture must satisfy that path rather than bypass it.
- Persist `source: {type: "capture", ref: "", session: <session_id>}`.
- Persist `capture_source: conversation`.
- Persist no `edit_history`.
- Return `ok_create` with ticket ID and path.

- [ ] **Step 5: Implement edit handling**

`ticket_capture.py prepare <PAYLOAD_PATH> --edit <EDIT_TEXT>` must:

- Append an entry to payload `edit_history` with timestamp and synthesized edit instruction.
- Regenerate `capture` fields from the payload values already written by the skill; the script should not call a model.
- Treat `split this into two tickets` as deferred: set `suggested_next_capture` in response and keep one ticket preview.

- [ ] **Step 6: Update hook allowlist if needed**

If `ticket_engine_guard.py` blocks canonical `ticket_capture.py` calls, add the new entrypoint to the same canonical plugin-root allowlist shape as existing `ticket_*.py` scripts. Add a hook test that:

- canonical `python3 -B <PLUGIN_ROOT>/scripts/ticket_capture.py prepare <PAYLOAD>` is allowed;
- non-canonical `python3 -BB ... ticket_capture.py ...` is denied consistently with existing Ticket behavior.

- [ ] **Step 7: Run focused tests and full Ticket suite**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_capture.py tests/test_hook.py tests/test_entrypoints.py -q
```

Expected: pass.

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected: pass.

- [ ] **Step 8: Lint and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check \
  plugins/turbo-mode/ticket/scripts/ticket_capture.py \
  plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py \
  plugins/turbo-mode/ticket/tests/test_capture.py \
  plugins/turbo-mode/ticket/tests/test_hook.py \
  plugins/turbo-mode/ticket/tests/test_entrypoints.py
```

```bash
git diff --check
git add \
  plugins/turbo-mode/ticket/scripts/ticket_capture.py \
  plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py \
  plugins/turbo-mode/ticket/tests/test_capture.py \
  plugins/turbo-mode/ticket/tests/test_hook.py \
  plugins/turbo-mode/ticket/tests/test_entrypoints.py
git commit -m "feat(ticket): add capture-first backend"
```

---

### Task 3: Flagship `ticket-capture` Skill

**Files:**
- Create: `plugins/turbo-mode/ticket/skills/ticket-capture/SKILL.md`
- Test: update `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- Test: update `plugins/turbo-mode/ticket/tests/test_entrypoints.py`

- [ ] **Step 1: Create the skill file**

Create `skills/ticket-capture/SKILL.md` with this frontmatter shape:

```yaml
---
name: ticket-capture
description: "Create repo-local tickets from natural language capture intent. Use when the user says to track, file, capture, ticket, or remember a bug, feature, follow-up, task, or cleanup item. Infer aggressively, synthesize a compact ticket preview, and require explicit confirmation before writing. Do not trigger from casual statements like 'this is a bug' unless the user also asks to track or file it."
allowed-tools:
  - Bash
  - Write
  - Read
---
```

Body requirements:

- Resolve `PLUGIN_ROOT`, `PROJECT_ROOT`, `TICKETS_DIR`, and absolute `PAYLOAD_PATH`.
- Synthesize `title`, `captured_request`, `problem`, `next_action`, `capture_confidence`, priority, tags, component, related paths, and acceptance criteria.
- Never store raw user wording.
- Ask one follow-up only when no useful next action can be synthesized.
- Run `ticket_capture.py prepare`.
- Show the compact preview exactly:

```text
Capture ticket

Title: <synthesized title>
Problem: <1-2 sentence synthesized problem>
Next action: <single concrete next step>
Confidence: low|medium|high
Duplicate: none | possible T-... "<title>"

Create this ticket? [create / edit / cancel]
```

- Show priority only when not `medium` or confidence is low.
- If user chooses `create`, run `ticket_capture.py execute`.
- If user chooses `edit`, rewrite the payload with the scoped edit and rerun prepare.
- If user asks to split, capture the first/clearest ticket and show a suggested second capture prompt after creation.

- [ ] **Step 2: Add docs-contract tests**

Add tests asserting:

- `ticket-capture` exists.
- The broad old `ticket` skill is not required for creation.
- `ticket-capture` contains the exact compact preview labels.
- It forbids raw user wording.
- It names the explicit confirmation gate.

- [ ] **Step 3: Run docs/entrypoint tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_docs_contract.py tests/test_entrypoints.py -q
```

Expected: pass.

- [ ] **Step 4: Commit the flagship skill**

```bash
git diff --check
git add \
  plugins/turbo-mode/ticket/skills/ticket-capture/SKILL.md \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py \
  plugins/turbo-mode/ticket/tests/test_entrypoints.py
git commit -m "feat(ticket): add ticket-capture skill"
```

---

### Task 4: Split Remaining Skills and Remove Old `ticket`

**Files:**
- Delete: `plugins/turbo-mode/ticket/skills/ticket/SKILL.md`
- Delete or replace: `plugins/turbo-mode/ticket/skills/ticket-triage/SKILL.md`
- Create: `plugins/turbo-mode/ticket/skills/ticket-find/SKILL.md`
- Create: `plugins/turbo-mode/ticket/skills/ticket-update/SKILL.md`
- Create: `plugins/turbo-mode/ticket/skills/ticket-review/SKILL.md`
- Create: `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/.codex-plugin/plugin.json`
- Test: update `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

- [ ] **Step 1: Create `ticket-find`**

Frontmatter description must trigger on read/search/list intent only:

```yaml
name: ticket-find
description: "Read, list, and search repo-local tickets. Use when the user asks to show a ticket, list tickets, find tickets about a topic, show open work, or check close readiness. Read-only; do not create, update, close, reopen, triage, or repair tickets."
allowed-tools:
  - Bash
  - Read
```

Body must call `ticket_read.py list`, `query`, and `check` only. It must group `needs_refinement` tickets separately in ordinary open results.

- [ ] **Step 2: Create `ticket-update`**

Frontmatter description must trigger on existing-ticket refinement, lifecycle, and metadata changes:

```yaml
name: ticket-update
description: "Refine or change existing repo-local tickets. Use when the user asks to update a ticket, mark work in progress, close, reopen, change priority, edit tags, add blockers, set component or related paths, or replace placeholder problem, next action, or acceptance criteria. Requires preview before writing."
allowed-tools:
  - Bash
  - Write
  - Read
```

Body must forbid arbitrary body-section editing in v1 and require preview before writing.

- [ ] **Step 3: Create `ticket-review`**

Frontmatter description must cover backlog health and next-action analysis:

```yaml
name: ticket-review
description: "Review ticket backlog health and recommend next actions. Use when the user asks what needs attention, what to work on next, what is stale or blocked, or asks for ticket backlog triage. Read-only; may suggest capture prompts but must not write tickets."
allowed-tools:
  - Bash
  - Read
```

Body can reuse `ticket_triage.py dashboard` and `audit`, but must not run doctor or repair unless the user explicitly asks for `ticket-doctor`.

- [ ] **Step 4: Create explicit-only `ticket-doctor`**

Frontmatter description must be narrow:

```yaml
name: ticket-doctor
description: "Explicit maintenance for the Ticket plugin. Use only when the user asks to doctor the ticket system, diagnose ticket storage, repair corrupt ticket audit logs, validate ticket plugin health, or run ticket storage/plugin diagnostics."
allowed-tools:
  - Bash
  - Write
  - Read
```

Body must dry-run repair first and ask before mutation.

- [ ] **Step 5: Remove old broad skills**

Delete `skills/ticket/SKILL.md`.

Replace `ticket-triage` with `ticket-review` rather than keeping both. If deletion leaves an empty directory, remove the empty directory with `trash` only if cleanup is explicitly in scope; otherwise leave no tracked files under it.

- [ ] **Step 6: Update plugin prompts and docs**

In `.codex-plugin/plugin.json`, change default prompts to capture-first language:

```json
[
  "Track this follow-up",
  "Find open ticket work",
  "Review ticket backlog health"
]
```

In README/HANDBOOK, describe the five-skill surface and state that generic creation is no longer user-facing.

- [ ] **Step 7: Add docs-contract tests for skill split**

Tests must assert:

- `skills/ticket/SKILL.md` does not exist.
- the five new skill files exist.
- `ticket-doctor` description includes explicit maintenance wording.
- `ticket-review` says read-only and suggests capture prompts rather than writing.
- no skill description advertises old `create/update/close/reopen/list/query/audit repair` as a single surface.

- [ ] **Step 8: Run tests and plugin evaluation**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py -q
```

```bash
plugin-eval analyze /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/ticket --format markdown
```

Expected: tests pass. Evaluation should show reduced invoke pressure for the broad old skill; remaining structural URL failures are handled in Task 7 if still present.

- [ ] **Step 9: Commit split**

```bash
git diff --check
git add \
  plugins/turbo-mode/ticket/skills \
  plugins/turbo-mode/ticket/README.md \
  plugins/turbo-mode/ticket/HANDBOOK.md \
  plugins/turbo-mode/ticket/.codex-plugin/plugin.json \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py
git commit -m "feat(ticket): split skill surface by user intent"
```

---

### Task 5: `ticket-update` Backend Refinement Path

**Files:**
- Create: `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- Test: `plugins/turbo-mode/ticket/tests/test_update_refinement.py`
- Modify if needed: `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_hook.py`

- [ ] **Step 1: Write refinement tests**

Test cases:

- Updating a `needs_refinement` ticket with concrete problem, next action, and concrete acceptance criteria clears `refinement_status`.
- Preview includes `Refinement: will clear needs-refinement`.
- Updating only priority/tags keeps `refinement_status`.
- Arbitrary section edit fields are rejected.
- Close/reopen/lifecycle changes still go through the existing transition policy.

- [ ] **Step 2: Implement `ticket_update.py prepare/execute`**

The entrypoint must support only:

- synthesized problem;
- next action;
- acceptance criteria;
- priority;
- tags;
- component;
- related paths;
- blocked_by/blocks;
- lifecycle status;
- reopen reason.

It must not support arbitrary body section replacement.

- [ ] **Step 3: Reuse existing engine update path**

Do not write ticket files directly. Dispatch through existing update/close/reopen engine paths and preserve hook provenance.

- [ ] **Step 4: Update hook tests if needed**

Canonical `ticket_update.py` commands must be allowed only in the same canonical shape as existing ticket scripts.

- [ ] **Step 5: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_update_refinement.py tests/test_hook.py -q
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

```bash
git diff --check
git add \
  plugins/turbo-mode/ticket/scripts/ticket_update.py \
  plugins/turbo-mode/ticket/tests/test_update_refinement.py \
  plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py \
  plugins/turbo-mode/ticket/tests/test_hook.py
git commit -m "feat(ticket): add focused update refinement flow"
```

---

### Task 6: `ticket-find`, `ticket-review`, and `ticket-doctor` Backends

**Files:**
- Create if needed: `plugins/turbo-mode/ticket/scripts/ticket_review.py`
- Create if needed: `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_read.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_triage.py`
- Test: `plugins/turbo-mode/ticket/tests/test_find_review_doctor.py`
- Test: update `plugins/turbo-mode/ticket/tests/test_triage.py`
- Test: update `plugins/turbo-mode/ticket/tests/test_doctor.py`

- [ ] **Step 1: Add find/review grouping tests**

Tests must prove:

- ordinary open results include `needs_refinement` tickets in a separate group;
- "what should I work on next" does not rank `needs_refinement` tickets as executable work;
- review output may include `suggested_capture_prompts`;
- review never writes ticket files.

- [ ] **Step 2: Add doctor explicitness tests**

Tests must prove:

- doctor diagnostic command is read-only by default;
- audit repair runs dry-run first;
- mutation repair requires explicit confirmation path;
- casual audit/review requests do not route to doctor behavior.

- [ ] **Step 3: Implement minimal backend wrappers**

Prefer thin wrappers over new frameworks:

- `ticket_read.py` remains the read/query authority.
- `ticket_triage.py` can remain the dashboard/audit implementation if `ticket-review` calls it clearly.
- `ticket_doctor.py` should call existing doctor/audit repair behavior and enforce dry-run-first UX.

- [ ] **Step 4: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_find_review_doctor.py tests/test_triage.py tests/test_doctor.py -q
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

```bash
git diff --check
git add \
  plugins/turbo-mode/ticket/scripts/ticket_review.py \
  plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
  plugins/turbo-mode/ticket/scripts/ticket_read.py \
  plugins/turbo-mode/ticket/scripts/ticket_triage.py \
  plugins/turbo-mode/ticket/tests/test_find_review_doctor.py \
  plugins/turbo-mode/ticket/tests/test_triage.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py
git commit -m "feat(ticket): add focused find review and doctor flows"
```

---

### Task 7: Release Readiness, Plugin Eval, and Source-Only Closeout

**Files:**
- Modify: `plugins/turbo-mode/ticket/.codex-plugin/plugin.json`
- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/CHANGELOG.md`
- Test: update docs tests if needed.

- [ ] **Step 1: Fix manifest interface gaps if still present**

Ensure `.codex-plugin/plugin.json` has:

- `interface.websiteURL`
- `interface.privacyPolicyURL`
- `interface.termsOfServiceURL`

Use source-repo URLs or local documented placeholders that match the repository's existing plugin metadata convention. Do not claim installed runtime readiness from this source edit.

- [ ] **Step 2: Update docs**

README and HANDBOOK must:

- lead with `ticket-capture`;
- describe the five-skill surface;
- state creation is capture-first;
- state low-confidence captures are allowed when a next action exists;
- state `needs_refinement` is metadata, not lifecycle status;
- state doctor/repair is explicit-only.

- [ ] **Step 3: Run full verification**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check \
  plugins/turbo-mode/ticket/scripts \
  plugins/turbo-mode/ticket/hooks \
  plugins/turbo-mode/ticket/tests
```

```bash
git diff --check
```

- [ ] **Step 4: Run plugin evaluation**

```bash
plugin-eval analyze /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/ticket --format markdown
```

Expected: structural manifest failures are gone. If budget remains heavy, record the remaining high-cost surfaces; do not claim measured usage without benchmark artifacts.

- [ ] **Step 5: Optional measured usage benchmark**

Only if the user asks for measured usage:

```bash
plugin-eval init-benchmark /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/ticket
plugin-eval benchmark /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/ticket --dry-run
```

Do not leave `.plugin-eval` residue inside the plugin tree unless it is intentionally tracked by a separate benchmark task.

- [ ] **Step 6: Commit final readiness docs**

```bash
git add \
  plugins/turbo-mode/ticket/.codex-plugin/plugin.json \
  plugins/turbo-mode/ticket/README.md \
  plugins/turbo-mode/ticket/HANDBOOK.md \
  plugins/turbo-mode/ticket/CHANGELOG.md \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py
git commit -m "docs(ticket): document capture-first plugin surface"
```

## Final Closeout Requirements

Before claiming the redesign complete:

- Full Ticket pytest suite passes.
- `git diff --check` passes.
- Changed Python paths pass ruff, or any pre-existing lint debt is explicitly separated from this branch's changes.
- `plugin-eval analyze` was run after the skill split and result is reported as static source evaluation only.
- No installed-cache/runtime success is claimed.
- Old `skills/ticket/SKILL.md` is gone.
- `ticket-capture` is the only user-facing creation skill.
- `ticket-doctor` is explicit-only.
- `Needs refinement` cannot close as `done`.

## Self-Review Notes

- Spec coverage: every decision from the drill is pinned in `Decision Freeze` and mapped to a task.
- Placeholder scan: no placeholder-marker or unspecified "add tests" steps remain; each test area names concrete behavior.
- Type consistency: field names are consistently `capture_confidence`, `capture_source`, `refinement_status`, `component`, and `related_paths`.
- Scope control: installed refresh and runtime certification are explicitly out of scope.

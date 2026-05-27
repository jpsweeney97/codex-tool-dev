# Ticket Runtime-First Autonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the source implementation for the runtime-first Ticket autonomy design so Ticket can apply non-destructive autonomous mutations through one engine-owned gateway, record durable pending-summary state, preserve ticket-owned `## Change History`, and return one concise end-of-turn projection.

**Architecture:** Implement the rollout in source-only slices as a hard runtime-first re-baseline, not as a compatibility migration. First classify legacy Ticket autonomy artifacts as keep, rewrite, or remove; then remove or rewrite old `.audit`, YAML-mode, `auto_audit`, `auto_silent`, and `suggest` assumptions that are not part of the new system. After that, add local-only workspace setup, strict config, deterministic IDs, append-only pending-summary events, `## Change History` helpers, host-facing CLI projections, the runtime evaluator, the engine-owned write gateway, recovery, summaries, commit disposition, and finally broader capture/candidate integration. Codex keeps semantic judgment in the turn context; Python enforces deterministic mechanics, write safety, idempotency, and recovery.

**Tech Stack:** Python >=3.11, pytest, dataclasses, strict JSON, append-only JSONL, sibling lock/temp-file writes, existing Ticket engine scripts, bytecode-safe `uv run` verification.

---

## Source Authority

Primary spec:

- `docs/superpowers/specs/2026-05-26-ticket-runtime-first-autonomy-design.md`

Current source baseline:

- Branch at plan creation: `chore/ticket-authority-kernel-slice1`
- HEAD at plan creation: `9453d18 docs: lock ticket autonomy recovery contracts`
- Runtime/cache mutation is out of scope unless a later user request explicitly asks for installed refresh or runtime proof.

Implementation branch:

- Before code work, create an execution branch from this docs baseline, unless the user gives a different branch:

```bash
git switch -c feature/ticket-runtime-first-autonomy-v1
```

- This branch is intentionally created from the docs baseline, not directly
  from `main`, because the plan/spec commits are not assumed to be on `main`
  yet. If the execution lane must satisfy a strict "branch from main" policy,
  stop and first land or rebase the docs baseline instead of dropping these
  control-doc commits.

Hard stops:

- Stop if the branch is not at or after `9453d18` and the spec file differs materially from this plan.
- Stop if `.codex/handoffs/`, `.codex/ticket-workspace/`, `.codex/ticket.local.md`, or pending-summary files appear in staged changes.
- Stop if any task needs to mutate `/Users/jp/.codex/plugins/cache`, personal plugin state, or installed runtime state.
- Stop before widening autonomous writes to delete, archive, or history repair.
- Stop before adding a passive policy registry that is not wired to the actual write path.
- Stop if an old Ticket behavior is being preserved only because an existing test, doc paragraph, or helper still asserts it. Legacy behavior is not a compatibility requirement unless this plan marks it as kept.

Verification command defaults:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
git diff --check
```

Use focused selectors inside each task first. Run the full Ticket suite before the final source closeout.

---

## Re-Baseline Policy

This implementation is a breaking runtime-first re-baseline. It should not
try to reconcile the new Ticket plugin with old `auto_audit`/`.audit` artifacts
that are not necessary components of the new system.

Before editing a legacy surface, classify it as one of:

- **Keep:** required by the runtime-first design. Keep it narrow and document
  the new-system reason.
- **Rewrite:** the file or test remains useful, but old expectations are
  replaced with runtime-first expectations.
- **Remove:** old-system residue with no new-system role. Delete the behavior,
  tests, and current-facing docs instead of adding compatibility shims.

Default dispositions for known legacy surfaces:

| Legacy surface | Disposition | Execution point |
|---|---|---|
| Future `docs/tickets/.audit/` writes from runtime execution | Remove | Task 1 |
| Historical `.audit` reader/doctor support | Keep. This plan may disable future `.audit` writes, but it must preserve read/doctor support for existing historical files until a separate migration patches the spec, contract, and source deliberately. | Task 1 and Task 15 |
| Tests asserting `engine_execute()` creates or appends `.audit/` records | Rewrite/remove | Task 1 |
| YAML frontmatter `.codex/ticket.local.md` config | Remove | Task 2 |
| Modes `suggest`, `auto_audit`, and `auto_silent` as current autonomy modes | Remove | Task 2 |
| Runtime-readiness and integration surfaces that stage `auto_audit`, `auto_silent`, or `suggest` as current runtime behavior | Rewrite/remove | Task 2 |
| Tests asserting missing config defaults to `suggest` or old modes are valid | Rewrite/remove | Task 2 |
| README/HANDBOOK/contract guidance for old setup and active audit behavior | Rewrite/remove | Tasks 1, 2, 7, and 15 |
| Public contract that lists only `capture`, `update`, and `ingest` as high-level mutation surfaces | Rewrite when the host-facing autonomy CLI lands | Task 7 |

Intermediate source commits may remove old `.audit` enforcement before the new
pending-summary gateway exists. That is acceptable because this source branch
has no current Ticket plugin users and runtime readiness is not claimed until
the later gateway, pending-summary, and final closeout gates pass.

Do not add compatibility shims for old autonomy modes, old YAML config, or
active `.audit` writes unless this plan is explicitly revised to mark that
surface as kept.

---

## File Structure

Create these focused runtime modules:

- `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py` - host-facing JSON-in/JSON-out CLI for `pause`, `recover`, `apply-turn`, `doctor-ledger`, and `migrate-change-history`.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py` - strict `.codex/ticket.local.md` JSON config, thread-scoped mode snapshots keyed by `(project_root, thread_id)`, workspace pause marker, local setup, ignored-path checks, and local `.codex/ticket-workspace/AGENTS.md` repair.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py` - canonical JSON serialization, deterministic `evt_`, `mut_`, and `appr_` IDs, and fingerprint helpers.
- `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py` - pending-summary envelope types, validation, append-only JSONL writer, lock/temp-file handling, event-derived state, recovery projections that receive live ticket fingerprints from gateway/CLI callers, summaries, and compaction.
- `plugins/turbo-mode/ticket/scripts/ticket_change_history.py` - `## Change History` parsing, insertion, label validation, and `migrate-change-history` planning/application.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py` - `AutonomyIntent`, hard policy decisions, fanout caps, approval envelopes, and runtime decision objects.
- `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py` - deterministic candidate extraction from structured turn context, explicit ticket mentions, ticket metadata, related paths, diff/test references, and Codex-proposed candidate changes.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py` - engine-owned autonomous write gateway that validates approvals, rechecks pause state, records ledger transitions, writes `## Change History`, and delegates to existing mutation mechanics.
- `plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py` - local ticket-only commit disposition helper that stages only ticket-owned files and never stages local pending-summary state.

Modify these existing source surfaces:

- `.gitignore` - add local-only `.codex/ticket-workspace/` rules when the workspace state path is introduced.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py` - disable future `.audit/` writes, remove legacy autonomy-mode behavior that is not part of the runtime-first system, expose existing low-level mutation dispatch to the autonomous gateway, and keep user-directed ordinary writes explicitly non-autonomous.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py` - preserve low-level compatibility while passing explicit non-autonomous intent for user-directed execute paths.
- `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py` - remove or rewrite old `auto_audit` readiness staging so source readiness evidence cannot preserve removed modes by accident.
- `plugins/turbo-mode/ticket/scripts/ticket_capture.py` - later adapter integration for automatic creation of clear follow-up tickets.
- `plugins/turbo-mode/ticket/scripts/ticket_update.py` - adapter integration for update/lifecycle/refinement mutation candidates.
- `plugins/turbo-mode/ticket/scripts/ticket_review.py` - read-only review remains read-only, but hygiene suggestions can feed structured candidates to `apply-turn` when called from ordinary thread automation.
- `plugins/turbo-mode/ticket/scripts/ticket_doctor.py` - keep maintenance bypasses named, dry-run-first, and explicitly confirmed.
- `plugins/turbo-mode/ticket/references/ticket-contract.md` - keep the contract aligned with source behavior.
- `plugins/turbo-mode/ticket/README.md` and `plugins/turbo-mode/ticket/HANDBOOK.md` - remove active `.audit`, YAML setup, and old mode guidance as each source migration lands.

Create or extend tests:

- `plugins/turbo-mode/ticket/tests/test_autonomy_config.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_ids.py`
- `plugins/turbo-mode/ticket/tests/test_turn_batch.py`
- `plugins/turbo-mode/ticket/tests/test_change_history.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`
- `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`
- `plugins/turbo-mode/ticket/tests/test_ticket_commit_coordinator.py`
- Rewrite or reduce `plugins/turbo-mode/ticket/tests/test_audit.py` so it no longer asserts active `.audit` writes.
- Rewrite or reduce `plugins/turbo-mode/ticket/tests/test_autonomy.py` so it no longer treats `suggest`, `auto_audit`, `auto_silent`, or missing-config defaults as current autonomy behavior.
- Rewrite or reduce `plugins/turbo-mode/ticket/tests/test_autonomy_integration.py` so it no longer proves old `suggest` or `auto_audit` preflight/execute flows as current behavior.
- Rewrite or reduce `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py` so installed-runtime readiness proof no longer stages YAML `auto_audit` config or asserts old-mode payloads.
- Rewrite or reduce every additional test found by the Task 2 old-mode inventory.
  Known live files outside the original narrow Task 2 set include
  `plugins/turbo-mode/ticket/tests/test_execute.py`,
  `plugins/turbo-mode/ticket/tests/test_engine_runner.py`,
  `plugins/turbo-mode/ticket/tests/test_workflow_execute.py`, and
  `plugins/turbo-mode/ticket/tests/test_review_findings.py`.
- Extend or rewrite `plugins/turbo-mode/ticket/tests/test_docs_contract.py` so current-facing docs only describe the new system.
- Extend wrapper and workflow tests only when adapter integration reaches those files.

---

## Shared Data Contracts

Use these exact enum values in production code and tests.

Automation modes:

```python
class AutomationMode(StrEnum):
    DISCUSSION_ONLY = "discussion_only"
    PREVIEW = "preview"
    AGENT_PRIMARY = "agent_primary"
```

Runtime decisions:

```python
class RuntimeDecisionKind(StrEnum):
    APPLY_AUTONOMOUSLY = "apply_autonomously"
    REQUIRE_USER_DISCUSSION = "require_user_discussion"
    SKIP_DUE_TO_CONFLICT = "skip_due_to_conflict"
    DEFER_UNTIL_RETRY_CONDITION = "defer_until_retry_condition"
    PREVIEW_ONLY = "preview_only"
```

Pending-summary event types:

```python
class PendingSummaryEventType(StrEnum):
    MUTATION_ATTEMPT = "mutation_attempt"
    MUTATION_STATUS = "mutation_status"
    SUMMARY_RECEIPT = "summary_receipt"
    COMPACTION_RECEIPT = "compaction_receipt"
    AUTOMATION_PAUSE = "automation_pause"
```

Pending-summary statuses:

```python
class PendingSummaryStatus(StrEnum):
    PENDING = "pending"
    APPROVAL_CONSUMED = "approval_consumed"
    TICKET_WRITTEN = "ticket_written"
    APPLIED = "applied"
    SKIPPED = "skipped"
    DISCUSSION_REQUIRED = "discussion_required"
    DEFERRED = "deferred"
    SUMMARIZED = "summarized"
    CORRECTED = "corrected"
    INACTIVE = "inactive"
    COMPACTED = "compacted"
    PAUSED = "paused"
    FAILED = "failed"
```

Action values:

```python
TICKET_ACTIONS = (
    "create",
    "update",
    "reprioritize",
    "blocker_edit",
    "stale_cleanup",
    "refine",
    "done",
    "wontfix",
    "reopen",
    "archive",
    "delete",
    "history_repair",
    "correction",
)

OPERATIONAL_ACTIONS = ("summarize", "compact", "pause_automation")

TURN_CONTEXT_OPERATIONS = ("apply_ticket_mutations", "pause_automation")
```

Autonomy-to-engine dispatch is gateway-local deterministic mechanics, not a
pending-summary field. The pending-summary `action` remains the Ticket-facing
action above; the gateway maps it before calling the live engine API:

```python
class EngineAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    CLOSE = "close"
    REOPEN = "reopen"


@dataclass(frozen=True, slots=True)
class EngineDispatch:
    engine_action: EngineAction
    fields: Mapping[str, object]
    gateway_authorized_reopen: bool = False
```

Required dispatch map:

| Ticket-facing action | Engine dispatch |
| --- | --- |
| `create` | `EngineAction.CREATE` with create fields unchanged |
| `update`, `reprioritize`, `blocker_edit`, `stale_cleanup`, `refine`, `correction` | `EngineAction.UPDATE` with the targeted metadata/body/Change History fields |
| `done` | `EngineAction.CLOSE` with `fields["resolution"] == "done"` |
| `wontfix` | `EngineAction.CLOSE` with `fields["resolution"] == "wontfix"` |
| `reopen` | `EngineAction.REOPEN` with `fields["reopen_reason"]` and a gateway-authorized reopen path |

The gateway-authorized reopen path must not loosen generic agent-origin
`reopen`. Direct agent engine calls keep the existing defense-in-depth block;
only a gateway call with a validated approval envelope may dispatch autonomous
`reopen`.

Commit dispositions:

```python
class CommitDisposition(StrEnum):
    COMMIT_RECORDED = "commit_recorded"
    COMMIT_BUNDLED_WITH_WORK = "commit_bundled_with_work"
    COMMIT_DEFERRED = "commit_deferred"
```

Change History labels:

```python
class ChangeHistoryLabel(StrEnum):
    AUTO_CREATE = "auto-create"
    AUTO_UPDATE = "auto-update"
    AUTO_BLOCKER = "auto-blocker"
    AUTO_CLOSE = "auto-close"
    AUTO_REOPEN = "auto-reopen"
    CORRECTION = "correction"
    DISCUSSION_APPROVED = "discussion-approved"
```

Host-facing CLI exit codes:

- `0`: valid response; stdout is parseable JSON.
- `1`: operational failure; stdout is JSON when possible.
- `2`: invalid input or contract violation.
- `3`: automation paused or fail-closed condition; stdout is JSON pause output.

Handled no-op responses are not silent. They use exit `0` and this shape:

```json
{"state":"no_change","changed":false,"ticket_updates":null,"discussion_question":null}
```

---

## Task 1: Re-Baseline Legacy `.audit` Surface And Disable Future Writes

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/tests/test_audit.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

- [ ] **Step 1: Inventory and re-baseline legacy audit artifacts**

Run a focused inventory before editing:

```bash
rg -n "\\.audit|ticket_audit|repair-audit|auto_audit" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/references/ticket-contract.md
```

Classify every touched audit surface using the re-baseline policy:

- Future runtime `.audit` writes: **remove**.
- Current-facing docs that present `.audit` as active behavior: **rewrite/remove**.
- Existing tests whose only purpose is to assert active `.audit` creation,
  ordered active audit entries, or active append counts: **rewrite/remove**.
- Historical reader/doctor support: **keep narrowly**. Preserve
  `ticket_audit.py`, `ticket_doctor.py repair-audit`, and engine helpers needed
  to read/count/repair existing historical `.audit/` files. Do not delete or
  bypass this support in Task 1. If the project later wants deletion, create a
  separate migration plan that first patches the primary spec, ticket contract,
  file list, and tests for that migration.

- [ ] **Step 2: Write the failing `.audit` re-baseline tests**

Add focused tests that prove `engine_execute()` no longer creates
`docs/tickets/.audit/` for user or agent requests. Add tests that prove
historical audit support remains read/repair-only.

Before adding new assertions, rewrite or delete the existing assertions in
`test_audit.py` that expect `engine_execute()` to create `.audit/`, append
ordered active audit entries, or append six active entries for three creates.
Those old assertions are legacy residue, not compatibility requirements.

Required assertions:

```python
def test_engine_execute_does_not_create_future_audit_files(tmp_tickets: Path) -> None:
    response = engine_execute(
        action="create",
        ticket_id=None,
        fields={"title": "No audit", "problem": "Future writes use Change History."},
        session_id="sess-no-audit",
        request_origin="user",
        dedup_override=False,
        dependency_override=False,
        tickets_dir=tmp_tickets,
        hook_injected=True,
        hook_request_origin="user",
        classify_intent="create",
        classify_confidence=0.95,
        dedup_fingerprint=compute_dedup_fp("Future writes use Change History.", []),
    )

    assert response.state == "ok_create"
    assert not (tmp_tickets / ".audit").exists()
```

```python
def test_historical_audit_reader_still_counts_existing_files(tmp_tickets: Path) -> None:
    today = datetime.now(UTC).strftime("%Y-%m-%d")
    audit_file = tmp_tickets / ".audit" / today / "sess-historical.jsonl"
    audit_file.parent.mkdir(parents=True)
    audit_file.write_text(
        json.dumps(
            {
                "ts": "2026-05-27T00:00:00+00:00",
                "action": "attempt_started",
                "intent": "create",
                "ticket_id": None,
                "session_id": "sess-historical",
                "request_origin": "agent",
                "autonomy_mode": "auto_audit",
                "result": None,
                "changes": None,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    assert engine_count_session_creates("sess-historical", tmp_tickets) == 1
```

Add docs tests that normalize README/HANDBOOK/contract text and assert:

- Future autonomous writes use `## Change History` plus local pending-summary bookkeeping.
- `.audit` is described as historical or legacy only.
- `ticket_audit.py` and `ticket_doctor.py repair-audit` are described only as
  read/repair tools for existing historical `.audit/` files, not as future
  runtime history surfaces.
- Active `.audit` creation, active full JSONL audit trail language, and old `auto_audit` setup instructions are absent from current-facing guidance except in clearly historical context.

- [ ] **Step 3: Run the failing tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_audit.py tests/test_docs_contract.py -q
```

Expected before implementation: at least the new `.audit` write-disablement test fails because `engine_execute()` still creates `docs/tickets/.audit/YYYY-MM-DD/<session>.jsonl`. No old active-audit assertion should remain as a planned expected failure.

- [ ] **Step 4: Disable future `.audit` writes in source**

Change `ticket_engine_core.py` so normal execution no longer calls `_audit_append()` around dispatch. Preserve `engine_count_session_creates()` and `ticket_audit.py` for historical read/doctor support only.

Implementation shape:

```python
def _audit_append(session_id: str, tickets_dir: Path, entry: dict[str, Any]) -> bool:
    """Historical no-op for future engine writes.

    Existing `.audit` readers and repair tools remain available for historical
    files, but runtime writes moved to Change History plus pending-summary
    bookkeeping.
    """
    return True
```

Then remove the agent fail-closed dependence on result audit writes from
`engine_execute()`. This creates an intermediate source-only state where the
old audit gate is gone before the new gateway lands. That is acceptable for
this no-current-users re-baseline, but do not claim runtime readiness until the
pending-summary gateway and final source closeout pass.

- [ ] **Step 5: Update docs to match the migration**

Patch README/HANDBOOK/contract so current-facing docs say:

- Future autonomous durable history writes to affected tickets' `## Change History`.
- Future local operational state writes to `.codex/ticket-workspace/ticket.pending-summary.jsonl`.
- Existing `docs/tickets/.audit/` files are historical artifacts.
- `ticket_audit.py` and `ticket_doctor.py repair-audit` remain read/repair
  tools for those files only.
- README/HANDBOOK/contract/spec do not expose `.audit` as an active or future
  autonomous history surface.

- [ ] **Step 6: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_audit.py tests/test_docs_contract.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/tests/test_audit.py plugins/turbo-mode/ticket/tests/test_docs_contract.py
git diff --check
git status --short
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/references/ticket-contract.md plugins/turbo-mode/ticket/tests/test_audit.py plugins/turbo-mode/ticket/tests/test_docs_contract.py
git commit -m "fix(ticket): disable future audit writes"
```

---

## Task 2: Add Strict Local Mode And Workspace Setup

**Files:**

- Create: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py`
- Create: `plugins/turbo-mode/ticket/tests/test_autonomy_config.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_integration.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`
- Modify: `.gitignore`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify discovered legacy-mode test files from the inventory below, including
  but not limited to:
  `plugins/turbo-mode/ticket/tests/test_execute.py`,
  `plugins/turbo-mode/ticket/tests/test_engine_runner.py`,
  `plugins/turbo-mode/ticket/tests/test_workflow_execute.py`, and
  `plugins/turbo-mode/ticket/tests/test_review_findings.py`

- [ ] **Step 1: Re-baseline legacy autonomy mode surfaces**

Run this all-tests/all-scripts inventory before editing:

```bash
rg -n \
  -e 'auto_audit' \
  -e 'auto_silent' \
  -e 'autonomy_mode' \
  -e 'max_creates_per_session' \
  -e 'defaults to `suggest`' \
  plugins/turbo-mode/ticket/scripts \
  plugins/turbo-mode/ticket/tests
```

Classify every matching source/test surface as **keep**, **rewrite**, or
**remove** before implementing strict config. The classification must cover
every file with old-mode strings, not only `test_autonomy.py`,
`test_autonomy_integration.py`, and `test_runtime_readiness.py`.

Allowed **keep** categories:

- Negative config fixtures proving old YAML/frontmatter modes are rejected by
  the strict JSON parser.
- Historical `.audit` reader/doctor fixtures that intentionally preserve legacy
  file reading and repair.
- Non-current migration or model fixtures explicitly labeled historical.

Everything else must be rewritten or removed if it treats `suggest`,
`auto_audit`, `auto_silent`, YAML frontmatter config, or
`max_creates_per_session` as current runtime-first behavior.

Rewrite or delete existing assertions in `test_autonomy.py` and every matching
test file from the inventory that treat these as current behavior:

- missing `.codex/ticket.local.md` defaults to `suggest`;
- YAML frontmatter config is accepted;
- `auto_audit` and `auto_silent` are valid modes;
- malformed or unknown old config self-heals to `suggest`;
- old `max_creates_per_session` limits are part of the current autonomy model.

Those tests describe the old plugin. They are not compatibility gates for the
runtime-first plugin. Keep only tests that still exercise non-autonomous engine
compatibility or rewrite them to call the new strict config surface.

In particular, classify these still-live old-mode surfaces under the
re-baseline policy before editing them:

- `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_integration.py`
- `plugins/turbo-mode/ticket/tests/test_execute.py`
- `plugins/turbo-mode/ticket/tests/test_engine_runner.py`
- `plugins/turbo-mode/ticket/tests/test_workflow_execute.py`
- `plugins/turbo-mode/ticket/tests/test_review_findings.py`

Default to rewrite/remove for any current-facing readiness or integration proof
that stages YAML `auto_audit`, asserts `suggest` as the missing-config default,
or treats `auto_silent` as a valid current mode. If a runtime-readiness lane is
kept, it must prove the runtime-first source behavior with strict JSON config
or be explicitly marked historical/non-current. Do not weaken or delete
runtime-readiness evidence to make the old-mode grep pass; replace it with
readiness evidence for `discussion_only`, `preview`, or `agent_primary`, or
defer installed-runtime readiness to an explicit later runtime-proof lane.

- [ ] **Step 2: Write strict config and workspace setup tests**

Test cases:

- Missing `.codex/ticket.local.md` returns a setup-required result with no fallback to old modes.
- Missing or invalid config can be resolved by the guided setup choice contract:
  `automatic` writes `agent_primary`, `ask_first` writes `discussion_only`,
  and `preview` remains manual-only.
- Valid file is exactly `{"schema":"codex.ticket.local.v1","mode":"agent_primary"}` or another allowed mode.
- Unknown keys, Markdown, fenced JSON, YAML frontmatter, comments, old modes `suggest`, `auto_audit`, and `auto_silent` are invalid.
- `write_local_config(project_root, AutomationMode.AGENT_PRIMARY)` rewrites the whole file as strict JSON.
- `write_local_config_from_setup_choice(project_root, SetupChoice.AUTOMATIC)` rewrites the whole file as strict JSON for `agent_primary`.
- `write_local_config_from_setup_choice(project_root, SetupChoice.ASK_FIRST)` rewrites the whole file as strict JSON for `discussion_only`.
- `ensure_ticket_workspace(project_root)` creates `.codex/ticket-workspace/AGENTS.md` with local-only staging guidance.
- `ensure_ticket_workspace(project_root)` verifies `.codex/ticket-workspace/` is ignored.
- `write_workspace_pause(project_root, reason="user_requested")` writes a local pause marker and `is_workspace_paused(project_root)` returns true.
- `pause_workspace_automation(project_root, reason="user_requested")` writes
  the pause marker and rewrites `.codex/ticket.local.md` to strict JSON
  `discussion_only`.
- Mode snapshots are keyed by `(project_root, thread_id)`: the first automatic
  turn for a thread/project reads strict config and writes a local snapshot;
  later turns for the same thread/project use the snapshot even if
  `.codex/ticket.local.md` is edited directly.
- A different `thread_id` in the same project reads the current strict config
  and receives its own mode snapshot.
- Missing or empty `thread_id` is invalid for runtime-first automatic mode
  resolution.
- `test_autonomy.py` contains no current-facing assertions that `suggest`,
  `auto_audit`, `auto_silent`, YAML frontmatter config, or missing-config
  defaults are valid runtime-first behavior.
- `test_autonomy_integration.py` contains no current-facing assertions that
  missing config defaults to `suggest`, that `auto_audit` preflight succeeds,
  or that an automatic execute records active `.audit` state.
- `test_runtime_readiness.py` and `ticket_runtime_readiness.py` contain no
  current-facing readiness setup that writes YAML `auto_audit` config or
  asserts old-mode payloads as runtime-readiness evidence.

Required public surface:

```python
class LocalConfigState(StrEnum):
    VALID = "valid"
    SETUP_REQUIRED = "setup_required"


class SetupChoice(StrEnum):
    AUTOMATIC = "automatic"
    ASK_FIRST = "ask_first"


@dataclass(frozen=True, slots=True)
class LocalConfigResult:
    state: LocalConfigState
    mode: AutomationMode | None
    path: Path
    reason: str | None = None


@dataclass(frozen=True, slots=True)
class ModeSnapshot:
    project_root: Path
    thread_id: str
    mode: AutomationMode
    path: Path


@dataclass(frozen=True, slots=True)
class ResolvedMode:
    state: LocalConfigState
    mode: AutomationMode | None
    source: Literal["snapshot", "config", "setup_required"]
    path: Path | None
    reason: str | None = None


def read_local_config(project_root: Path) -> LocalConfigResult: ...
def write_local_config(project_root: Path, mode: AutomationMode) -> Path: ...
def write_local_config_from_setup_choice(project_root: Path, choice: SetupChoice) -> Path: ...
def ensure_ticket_workspace(project_root: Path) -> Path: ...
def mode_snapshot_key(project_root: Path, thread_id: str) -> str: ...
def read_mode_snapshot(project_root: Path, thread_id: str) -> ModeSnapshot | None: ...
def write_mode_snapshot(project_root: Path, thread_id: str, mode: AutomationMode) -> ModeSnapshot: ...
def resolve_thread_mode(project_root: Path, thread_id: str) -> ResolvedMode: ...
def write_workspace_pause(project_root: Path, *, reason: str) -> Path: ...
def pause_workspace_automation(project_root: Path, *, reason: str) -> Path: ...
def clear_workspace_pause(project_root: Path) -> None: ...
def is_workspace_paused(project_root: Path) -> bool: ...
```

- [ ] **Step 3: Run the failing config tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_config.py tests/test_autonomy.py tests/test_autonomy_integration.py tests/test_runtime_readiness.py tests/test_execute.py tests/test_engine_runner.py tests/test_workflow_execute.py tests/test_review_findings.py -q
```

Expected before implementation: import failure for `scripts.ticket_autonomy_config` and/or failures from legacy config tests that have not yet been rewritten.

- [ ] **Step 4: Implement `ticket_autonomy_config.py` and remove old config behavior**

Implementation requirements:

- Use `json.loads()` on the full file text.
- Require object type, exact keys `schema` and `mode`, schema `codex.ticket.local.v1`, and mode in `discussion_only`, `preview`, `agent_primary`.
- Return setup-required instead of silently choosing a default.
- Accept only setup choices `automatic` and `ask_first`; map them to
  `agent_primary` and `discussion_only` respectively.
- Write JSON compactly with a trailing newline: `{"schema":"codex.ticket.local.v1","mode":"agent_primary"}\n`.
- Store mode snapshots under `.codex/ticket-workspace/mode-snapshots/`. The
  effective key is `(project_root, thread_id)`: the project-local directory
  scopes the project, and each snapshot records the normalized project root and
  thread ID so moved or copied state fails validation instead of silently
  applying to another checkout.
- `resolve_thread_mode(project_root, thread_id)` must return an existing
  snapshot before reading `.codex/ticket.local.md`; only when no snapshot exists
  may it read strict config and write the first snapshot for that
  thread/project.
- Direct edits to `.codex/ticket.local.md` after a mode snapshot exists do not
  affect later turns for the same `(project_root, thread_id)`. A workspace pause
  marker still overrides immediately before any autonomous write.
- Use `.codex/ticket-workspace/pause.json` as the workspace-wide pause marker.
- Remove or bypass the old YAML `read_autonomy_config()` path in
  `ticket_engine_core.py` for current runtime-first behavior. Do not leave
  `suggest`, `auto_audit`, or `auto_silent` as accepted current autonomy modes.
  If a low-level direct-engine compatibility path must remain temporarily,
  mark it explicitly non-autonomous and keep it out of host-facing autonomy
  setup, docs, and final runtime-readiness claims.
- Rewrite `ticket_runtime_readiness.py` so any retained source readiness helper
  stages strict JSON mode config or no autonomy config at all. A retained
  readiness helper must not write `autonomy_mode: auto_audit`,
  `autonomy_mode: auto_silent`, or `autonomy_mode: suggest` to
  `.codex/ticket.local.md`.
- Create `.codex/ticket-workspace/AGENTS.md` with plain local guidance:

```markdown
# Ticket Automation Workspace State

Files in this directory are local Ticket automation bookkeeping.
Do not stage, commit, push, publish, or treat them as project history.
Project truth remains in `docs/tickets/` ticket files and committed `## Change History` entries.
```

- [ ] **Step 5: Add local-only ignore rules**

Patch `.gitignore` narrowly:

```gitignore
.codex/ticket-workspace/
.codex/ticket.local.md
```

Do not add broad `.codex/` ignores.

- [ ] **Step 6: Update current-facing docs**

Update README/HANDBOOK/contract to document strict JSON local config and workspace pause behavior. Remove current-facing YAML-frontmatter setup instructions for old modes.

- [ ] **Step 7: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_config.py tests/test_autonomy.py tests/test_autonomy_integration.py tests/test_runtime_readiness.py tests/test_execute.py tests/test_engine_runner.py tests/test_workflow_execute.py tests/test_review_findings.py tests/test_docs_contract.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py plugins/turbo-mode/ticket/tests/test_autonomy_config.py plugins/turbo-mode/ticket/tests/test_autonomy.py plugins/turbo-mode/ticket/tests/test_autonomy_integration.py plugins/turbo-mode/ticket/tests/test_runtime_readiness.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_engine_runner.py plugins/turbo-mode/ticket/tests/test_workflow_execute.py plugins/turbo-mode/ticket/tests/test_review_findings.py
git diff --check
git status --short
```

Commit:

```bash
git add .gitignore plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py plugins/turbo-mode/ticket/tests/test_autonomy_config.py plugins/turbo-mode/ticket/tests/test_autonomy.py plugins/turbo-mode/ticket/tests/test_autonomy_integration.py plugins/turbo-mode/ticket/tests/test_runtime_readiness.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_engine_runner.py plugins/turbo-mode/ticket/tests/test_workflow_execute.py plugins/turbo-mode/ticket/tests/test_review_findings.py plugins/turbo-mode/ticket/references/ticket-contract.md plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md
git commit -m "feat(ticket): add strict autonomy workspace config"
```

---

## Task 3: Add Deterministic IDs And Fingerprints

**Files:**

- Create: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py`
- Create: `plugins/turbo-mode/ticket/tests/test_autonomy_ids.py`

- [ ] **Step 1: Write ID tests**

Tests must prove:

- Canonical JSON uses sorted keys and compact separators.
- Path-like strings are normalized with `/`.
- `event_id`, `mutation_id`, and `approval_id` use SHA-256, lowercase hex, first 32 hex chars, and prefixes `evt_`, `mut_`, `appr_`.
- Timestamps are accepted in payload validation elsewhere but are not ID inputs.
- Same canonical input reproduces the same ID.
- Changing ticket ID, mutation fingerprint, ticket-state fingerprint, evidence fingerprint, thread-scoped mode, or decision kind changes the relevant ID.

Required public surface:

```python
def canonical_json(value: object) -> str: ...
def sha256_fingerprint(value: object) -> str: ...
def make_mutation_id(*, schema: str, turn_id: str, action: str, ticket_id: str | None, mutation_fingerprint: str, evidence_fingerprint: str) -> str: ...
def make_event_id(*, schema: str, event_type: str, turn_id: str, mutation_id: str | None, status: str, action: str, ticket_id: str | None, payload_fingerprint: str) -> str: ...
def make_approval_id(*, schema: str, ticket_id: str, mutation_id: str, mutation_fingerprint: str, ticket_state_fingerprint: str, evidence_fingerprint: str, current_mode: str, decision: str) -> str: ...
```

- [ ] **Step 2: Run failing tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_ids.py -q
```

- [ ] **Step 3: Implement ID helper**

Use `json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)` and `hashlib.sha256`.

Reject unsupported canonical inputs by raising:

```python
ValueError(f"{operation} failed: {reason}. Got: {value!r:.100}")
```

- [ ] **Step 4: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_ids.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py plugins/turbo-mode/ticket/tests/test_autonomy_ids.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py plugins/turbo-mode/ticket/tests/test_autonomy_ids.py
git commit -m "feat(ticket): add deterministic autonomy ids"
```

---

## Task 4: Add Pending-Summary Envelope Validation

**Files:**

- Create: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Create: `plugins/turbo-mode/ticket/tests/test_turn_batch.py`

- [ ] **Step 1: Write strict envelope validation tests**

Tests must cover:

- Required envelope fields from the spec.
- Required `thread_id` copied from strict turn context. `thread_id` identifies
  the mode snapshot's Codex conversation; `turn_id` still identifies one
  end-of-turn batch.
- No unknown top-level fields.
- Required `repo_context` object with normalized `repo_root`, `worktree_root`,
  `repo_fingerprint`, `branch`, and `head` when git metadata is available.
- Missing `repo_context`, missing available branch/HEAD, or mismatched
  worktree identity is invalid.
- Valid event/status compatibility matrix.
- Finite action, decision, mode, evidence kind, pause reason, and commit disposition values.
- Preview-mode records use `status: "skipped"` with
  `decision: "preview_only"`; `status: "preview_only"` is invalid.
- `reason` is one short line with no newline.
- `details` requirements by event type and status, including:
  - `approval` for `mutation_attempt` with `apply_autonomously`.
  - `approval_id` for `approval_consumed`.
  - `post_write_fingerprint` for `ticket_written`.
  - `question` for `discussion_required`.
  - `retry_condition` for `deferred`.
  - `error_code` for `failed`.
  - `commit_disposition` for `applied` ticket-file writes.

Required public surface:

```python
PENDING_SUMMARY_SCHEMA = "codex.ticket.pending_summary.v1"


@dataclass(frozen=True, slots=True)
class ValidationResult:
    ok: bool
    error: str | None = None


def validate_repo_context(repo_context: Mapping[str, object]) -> ValidationResult: ...
def validate_pending_summary_event(event: Mapping[str, object]) -> ValidationResult: ...
def event_payload_fingerprint(event_without_event_id_and_timestamp: Mapping[str, object]) -> str: ...
```

- [ ] **Step 2: Run failing validation tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_turn_batch.py::test_pending_summary_envelope_requires_strict_fields -q
```

- [ ] **Step 3: Implement envelope validation**

Keep validation deterministic and local to `ticket_turn_batch.py`. Do not use a semantic classifier script. This module validates shapes, finite values, repo/worktree identity, branch/HEAD presence when available, and state compatibility only.

- [ ] **Step 4: Add representative fixtures**

Add test helper functions inside `test_turn_batch.py`:

```python
def valid_repo_context(**overrides: object) -> dict[str, object]: ...
def valid_attempt_event(**overrides: object) -> dict[str, object]: ...
def valid_status_event(status: str, **detail_overrides: object) -> dict[str, object]: ...
```

Keep fixtures in tests, not production.

- [ ] **Step 5: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_turn_batch.py tests/test_autonomy_ids.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/tests/test_turn_batch.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/tests/test_turn_batch.py
git commit -m "feat(ticket): validate pending summary events"
```

---

## Task 5: Add Append-Only Pending-Summary Writer And Recovery Projection

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_turn_batch.py`
- Create: `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`

- [ ] **Step 1: Write writer and recovery tests**

Tests must prove:

- `.codex/ticket-workspace/ticket.pending-summary.jsonl` receives one JSON object per line.
- The writer holds `.codex/ticket-workspace/ticket.pending-summary.lock`.
- Same `event_id` and same canonical non-timestamp content is treated as already recorded.
- Same `event_id` and conflicting non-timestamp content returns a paused bookkeeping result.
- Lock timeout returns a paused bookkeeping result and does not write ticket state.
- Recovery derives states:
  - no attempt
  - `attempt_recorded`
  - `approval_consumed`
  - `ticket_written`
  - `status_recorded`
  - `summary_recorded`
- This task does not decide live ticket-file recovery from current
  fingerprints. `PendingSummaryStore` records and derives event-only state;
  fingerprint recovery projections land in Task 11, where CLI/gateway callers
  can supply live ticket state.

Required public surface:

```python
@dataclass(frozen=True, slots=True)
class AppendResult:
    state: Literal["appended", "already_recorded", "paused"]
    event_id: str
    pause_reason: str | None = None


class PendingSummaryStore:
    def __init__(self, project_root: Path, *, lock_timeout_seconds: float = 2.0) -> None: ...
    def append_event(self, event: Mapping[str, object]) -> AppendResult: ...
    def read_events(self) -> tuple[dict[str, object], ...]: ...
    def derive_mutation_state(self, mutation_id: str) -> str: ...
```

- [ ] **Step 2: Run failing writer tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_turn_batch.py tests/test_autonomy_recovery.py -q
```

- [ ] **Step 3: Implement append-only writer**

Implementation requirements:

- Validate the whole active JSONL before append.
- Append under sibling lock.
- Use deterministic duplicate detection before appending.
- Use temp-file plus `os.replace()` only for compaction or repair flows, not normal append.
- Return a structured pause result instead of raising for expected bookkeeping health failures.

- [ ] **Step 4: Implement recovery derivation**

Represent derived mutation state from events, not from a mutable in-memory flag.
Do not inspect ticket files or compare current ticket fingerprints in this
task. Keep recovery output display-ready but do not let host/runtime parse raw
events directly.

- [ ] **Step 5: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_turn_batch.py tests/test_autonomy_recovery.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
git commit -m "feat(ticket): add durable pending summary ledger"
```

---

## Task 6: Add `## Change History` Helpers And Migration Command Support

**Files:**

- Create: `plugins/turbo-mode/ticket/scripts/ticket_change_history.py`
- Create: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Create: `plugins/turbo-mode/ticket/tests/test_change_history.py`
- Create: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`

- [ ] **Step 1: Write Change History helper and migration CLI tests**

Tests must prove:

- Finite labels only.
- Unknown labels and labels containing aliases are rejected.
- Reason cannot contain `|` or newline.
- Entry format is `- <timestamp> | <label> | <reason>` with optional ` Prior commit: <hash>.`.
- Missing section insertion point is deterministic:
  - after `## Related` when present
  - otherwise before `## Reopen History` when present
  - otherwise at end of file
- Existing `## Change History` receives an appended entry.
- The helper does not write the containing commit hash.
- `migrate-change-history --dry-run` reports candidate files and changes no files.
- `migrate-change-history --apply` inserts missing sections only after explicit apply.

Place helper-level tests in `test_change_history.py`. Create
`test_autonomy_cli.py` in this task for `migrate-change-history` argument and
stdout tests so Task 7 can extend the existing CLI test file.

Required public surface:

```python
@dataclass(frozen=True, slots=True)
class ChangeHistoryEntry:
    timestamp: str
    label: ChangeHistoryLabel
    reason: str
    prior_commit: str | None = None


@dataclass(frozen=True, slots=True)
class PlannedChangeHistoryMigration:
    ticket_path: Path
    before_fingerprint: str
    after_text: str


def render_change_history_entry(entry: ChangeHistoryEntry) -> str: ...
def append_change_history_entry(ticket_text: str, entry: ChangeHistoryEntry) -> str: ...
def plan_change_history_migration(tickets_dir: Path) -> tuple[PlannedChangeHistoryMigration, ...]: ...
```

- [ ] **Step 2: Run failing Change History tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_change_history.py tests/test_autonomy_cli.py -q
```

- [ ] **Step 3: Implement helper and CLI command**

Create `ticket_autonomy.py` in this task with only the `migrate-change-history --project-root <PROJECT_ROOT> --dry-run|--apply` subcommand. Task 7 extends the same file with `pause`, `recover`, `apply-turn`, and `doctor-ledger`.

Keep `ticket_change_history.py` pure with respect to ticket-file writes: it may
parse ticket text, render entries, compute migration plans, and return
`after_text`, but it must not write active ticket files. The only Task 6 file
write for this migration is the named, explicit `ticket_autonomy.py
migrate-change-history --apply` maintenance path, using the planned
`before_fingerprint` to fail closed if the ticket changed after planning.

CLI stdout examples:

```json
{"state":"ok","changed":false,"candidate_count":2,"candidates":["docs/tickets/example.md"]}
```

```json
{"state":"ok","changed":true,"updated_count":2,"updated":["docs/tickets/example.md"]}
```

- [ ] **Step 4: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_change_history.py tests/test_autonomy_cli.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_change_history.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/tests/test_change_history.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_change_history.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/tests/test_change_history.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/references/ticket-contract.md
git commit -m "feat(ticket): add change history runtime support"
```

---

## Task 7: Add Host-Facing Autonomy CLI Projections

**Files:**

- Create or modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- Modify as needed: `plugins/turbo-mode/ticket/README.md`
- Modify as needed: `plugins/turbo-mode/ticket/HANDBOOK.md`

- [ ] **Step 1: Write CLI contract tests**

Tests must prove:

- `pause --project-root <root> --reason user_requested` returns parseable JSON,
  writes the workspace pause marker, rewrites `.codex/ticket.local.md` to
  strict JSON `discussion_only`, verifies the local config file is ignored and
  unstaged, and does not touch ticket files.
- `recover --project-root <root> --turn-id <id>` returns parseable JSON on stdout.
- `apply-turn --project-root <root> --turn-id <id> --context-file <path>` rejects invalid context with exit code `2`, including missing `thread_id`, missing `turn_id`, or a context `turn_id` that does not match the CLI `--turn-id`.
- Missing or invalid local config returns exit code `3` with a setup-required JSON object that offers `automatic` and `ask_first` setup choices.
- `apply-turn --setup-choice automatic` writes strict JSON `agent_primary`, writes the `(project_root, thread_id)` mode snapshot for the context thread, verifies the local config and snapshot files are ignored and unstaged, and continues the same turn without a second confirmation.
- `apply-turn --setup-choice ask_first` writes strict JSON `discussion_only`, writes the `(project_root, thread_id)` mode snapshot for the context thread, verifies the local config and snapshot files are ignored and unstaged, and continues the same turn without a second confirmation.
- `apply-turn --setup-choice preview` is rejected; `preview` remains manual-only strict JSON config.
- Once a mode snapshot exists for `(project_root, thread_id)`, direct edits to
  `.codex/ticket.local.md` do not change later `apply-turn` mode behavior for
  that same thread/project.
- Workspace pause marker returns exit code `3` with pause output.
- No-change handled outcomes return exit code `0` and exactly one parseable
  JSON object with `state: "no_change"`, `changed: false`,
  `ticket_updates: null`, and `discussion_question: null`.
- Host-facing CLI never exposes raw ledger append/consume/mark-summarized commands.
- `doctor-ledger --dry-run` validates ledger health and returns JSON.
- `doctor-ledger --confirm-repair` is the only repair command that can rewrite ledger files.
- The public contract names `ticket_autonomy.py pause`, `recover`,
  `apply-turn`, `doctor-ledger`, and `migrate-change-history` as the
  host-facing autonomy surface, while preserving that ordinary high-level user
  mutation wrappers remain `capture`, `update`, and `ingest`.

Required response shape for explicit user pause:

```json
{
  "state": "paused",
  "pause_reason": "user_requested",
  "message": "Ticket automation paused for this workspace.",
  "ticket_updates": null,
  "discussion_question": null
}
```

Required response shape for paused automation:

```json
{
  "state": "paused",
  "pause_reason": "pending_summary_unhealthy",
  "message": "Ticket automation paused because pending-summary bookkeeping needs cleanup.",
  "ticket_updates": null,
  "discussion_question": null
}
```

- [ ] **Step 2: Run failing CLI tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_cli.py -q
```

- [ ] **Step 3: Implement `pause`, `recover`, `apply-turn`, and `doctor-ledger`**

Implementation requirements:

- Parse args with `argparse`.
- Print one JSON object to stdout for every handled outcome.
- Use stderr only for unexpected tracebacks.
- Exit `0`, `1`, `2`, or `3` according to the shared contract.
- `pause` calls the config helper that writes the workspace pause marker and
  rewrites `.codex/ticket.local.md` to strict JSON `discussion_only` for future
  sessions. It must verify that local config/workspace files are ignored and
  unstaged before returning success.
- `recover` calls `PendingSummaryStore` projections and returns display-ready summaries.
- `apply-turn` validates strict turn context, requires `thread_id` and a
  context `turn_id` matching CLI `--turn-id`, resolves mode from the local
  `(project_root, thread_id)` snapshot, then returns `preview`,
  `discussion_only`, `paused`, or a JSON `no_change` result until gateway
  integration lands in Task 10. It must never use silent stdout as a handled
  no-op signal.
- When config is missing or invalid and `--setup-choice automatic|ask_first` is present, `apply-turn` writes or repairs `.codex/ticket.local.md`, confirms the file is ignored and unstaged, writes the first mode snapshot for `(project_root, thread_id)`, and continues the same command without another confirmation.
- Update `ticket-contract.md` in the same commit. Do not introduce the
  host-facing autonomy CLI in source before the public contract describes it.

- [ ] **Step 4: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_cli.py tests/test_turn_batch.py tests/test_autonomy_config.py tests/test_docs_contract.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/references/ticket-contract.md plugins/turbo-mode/ticket/tests/test_docs_contract.py plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md
git commit -m "feat(ticket): add autonomy cli projections"
```

---

## Task 8: Add Runtime Evaluator And Candidate Discovery

**Files:**

- Create: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Create: `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
- Create: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- Create: `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`

- [ ] **Step 1: Write evaluator tests**

Tests must prove:

- Ordinary update, blocker edit, refinement, done, wontfix, and reopen candidates can route to `apply_autonomously` when mode is `agent_primary`, evidence floor is met, and no conflict exists.
- Delete, archive, and history repair route to `require_user_discussion`.
- `discussion_only` routes autonomous candidates to `require_user_discussion`.
- `preview` routes decisions to `preview_only` and does not authorize writes.
- Conflicting candidates route to `skip_due_to_conflict`.
- Metadata fanout soft cap is 5, blocker/refinement cap is 3, lifecycle done/reopen hard cap is 1 except explicit linked batch of 2, and wontfix has no fanout without explicit shared decision evidence.
- Above-cap candidates get pending-summary records instead of disappearing.
- Approval envelopes bind ticket ID, mutation ID, current mode, decision kind, current ticket-state fingerprint, proposed mutation fingerprint, and evidence fingerprint.
- Approval expiration is no more than 10 minutes.
- Ticket-facing actions map to engine dispatch exactly:
  - `done` becomes engine `close` with `resolution: "done"`.
  - `wontfix` becomes engine `close` with `resolution: "wontfix"`.
  - metadata, blocker, stale cleanup, refinement, and correction actions become engine `update`.
  - `reopen` remains engine `reopen` and requires `reopen_reason`.
- Direct generic agent-origin `reopen` remains policy-blocked outside the
  gateway-approved path.

Required public dataclass shape:

```python
@dataclass(frozen=True, slots=True)
class EvidenceLink:
    kind: str
    ref: str
    freshness: Literal["fresh", "stale"] = "fresh"


@dataclass(frozen=True, slots=True)
class CandidateMutation:
    ticket_id: str | None
    action: str
    proposed_change: Mapping[str, object]
    evidence: tuple[EvidenceLink, ...]
    conflict_reason: str | None = None


@dataclass(frozen=True, slots=True)
class AutonomyIntent:
    action_kind: str
    candidates: tuple[CandidateMutation, ...]
    source_context: Mapping[str, object]
```

- [ ] **Step 2: Write candidate discovery tests**

Tests must prove deterministic extraction from structured turn context:

- Explicit ticket IDs in `candidate_mutations`.
- Explicit ticket IDs mentioned in user request or assistant work summary.
- Related paths matched against ticket `key_file_paths` or `related_paths`.
- Diff/test file references matched to tickets.
- Vague ideas, broad cleanup themes, and "maybe later" route to `require_user_discussion` candidate records when Codex supplied them as possible candidates.

Do not implement a semantic natural-language classifier in Python. Codex supplies judgment-rich candidate hints in turn context; Python extracts deterministic signals and enforces hard rules.

- [ ] **Step 3: Run failing evaluator tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_runtime.py tests/test_candidate_discovery.py -q
```

- [ ] **Step 4: Implement evaluator and discovery helpers**

Keep the evaluator small:

- Hard action exclusions.
- Mode handling.
- Evidence floor checks by action tier.
- Conflict checks.
- Fanout cap handling.
- Approval envelope creation.

Keep discovery deterministic and evidence-shaped:

- Parse strict turn context.
- Read tickets with existing `ticket_read` helpers.
- Match explicit IDs and exact/normalized paths.
- Preserve Codex-supplied candidate reasons without scoring them.

- [ ] **Step 5: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_runtime.py tests/test_candidate_discovery.py tests/test_autonomy_ids.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py
git commit -m "feat(ticket): add autonomy runtime decisions"
```

---

## Task 9: Add Engine-Owned Autonomous Write Gateway

**Files:**

- Create: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Create: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_policy.py`

- [ ] **Step 1: Write gateway tests**

Tests must prove:

- Autonomous write without approval is rejected.
- Forged approval with mismatched ticket ID is rejected.
- Reused approval after `approval_consumed` is rejected unless recovery resumes the same mutation state.
- Expired approval is rejected.
- Gateway rechecks workspace pause marker immediately before consuming approval.
- Gateway rejects a cached `agent_primary` approval when another live thread or
  `ticket_autonomy.py pause` has written the workspace pause marker after the
  thread-scoped mode snapshot was read.
- Pending-summary attempt event is recorded before ticket mutation.
- Pending-summary failure prevents ticket mutation.
- `approval_consumed`, `ticket_written`, and `applied` events are appended in order for a successful automatic update.
- The same automatic mutation writes its `## Change History` entry in the ticket mutation.
- User-directed ordinary writes stay explicitly non-autonomous and do not consume approval.
- Maintenance/doctor bypasses are named and not accepted by the autonomous gateway.
- Gateway dispatch maps Ticket-facing action names to the live engine API before
  mutation:
  - `done` -> `close` plus `resolution: "done"`.
  - `wontfix` -> `close` plus `resolution: "wontfix"`.
  - `reprioritize`, `blocker_edit`, `stale_cleanup`, `refine`, and
    `correction` -> `update`.
  - `reopen` -> `reopen` only through the gateway-authorized path after
    approval validation.
- Direct generic agent-origin `reopen` remains policy-blocked outside the
  gateway-authorized path.

Required public surface:

```python
@dataclass(frozen=True, slots=True)
class GatewayMutation:
    action: str
    ticket_id: str | None
    fields: Mapping[str, object]
    tickets_dir: Path
    target_fingerprint: str | None


def build_engine_dispatch(mutation: GatewayMutation) -> EngineDispatch: ...


def apply_autonomous_mutation(
    *,
    project_root: Path,
    turn_id: str,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
    pending_summary: PendingSummaryStore,
) -> EngineResponse: ...
```

- [ ] **Step 2: Run failing gateway tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_engine_gateway.py -q
```

- [ ] **Step 3: Implement gateway validation and dispatch**

Implementation requirements:

- Validate approval envelope against current inputs.
- Re-read current ticket fingerprint immediately before write.
- Recheck workspace pause marker immediately before consuming approval. If the
  marker exists, return a paused response, leave ticket files unchanged, and do
  not append `approval_consumed` or `ticket_written`.
- Append `mutation_attempt` before write and fail closed if it cannot persist.
- Append `approval_consumed` before entering protected write section.
- Build `EngineDispatch` from `GatewayMutation` before calling
  `ticket_engine_core.py`; never pass Ticket-facing actions such as `done` or
  `wontfix` directly to the engine.
- Apply the existing low-level mutation mechanics through `ticket_engine_core.py`
  using `EngineDispatch.engine_action` and normalized fields.
- Add the smallest explicit gateway-authorized reopen path needed for approved
  autonomous `reopen`; keep direct generic agent-origin `reopen` blocked.
- Append `ticket_written` with expected post-write fingerprint.
- Append terminal `applied`, `skipped`, `discussion_required`, `deferred`, or `failed`.
- For ticket-file writes, include `commit_disposition` details. Until Task 12 lands, use `commit_deferred` with reason `Commit coordinator not yet run for this source slice.`

- [ ] **Step 4: Add bypass-prevention static guard**

Add tests that scan Ticket scripts for direct active-ticket writes outside allowed files. The first allowlist is:

- `ticket_engine_core.py`
- `ticket_engine_gateway.py`
- specific pure text transformation functions in `ticket_change_history.py`
- specific named maintenance/doctor command functions when the tested command is
  dry-run-first or confirm-gated, including only the
  `migrate-change-history --apply` file-write path for Change History migration

The guard should flag future autonomous `.audit` writes while allowing historical `.audit` read/doctor support.

- [ ] **Step 5: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_engine_gateway.py tests/test_engine_policy.py tests/test_audit.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_engine_policy.py
git commit -m "feat(ticket): add autonomous write gateway"
```

---

## Task 10: Wire `apply-turn` Through Discovery, Evaluator, Gateway, And Summary

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- Create: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`

- [ ] **Step 1: Write end-to-end `apply-turn` tests**

Use a strict context file:

```json
{
  "schema": "codex.ticket.turn_context.v1",
  "operation": "apply_ticket_mutations",
  "thread_id": "thread-1",
  "turn_id": "turn-1",
  "user_request": "Mark T-20260527-01 done after tests passed.",
  "assistant_work_summary": "Implemented and verified the requested change.",
  "touched_files": ["plugins/turbo-mode/ticket/scripts/example.py"],
  "verification": [{"command": "uv run pytest example -q", "outcome": "passed"}],
  "git": {
    "repo_root": "/tmp/project",
    "worktree_root": "/tmp/project",
    "repo_fingerprint": "sha256:repo",
    "branch": "feature/example",
    "head": "abc123"
  },
  "candidate_mutations": [
    {
      "ticket_id": "T-20260527-01",
      "action": "done",
      "proposed_change": {"status": "done"},
      "reason": "Verification passed.",
      "evidence": [{"kind": "test", "ref": "uv run pytest example -q"}]
    }
  ]
}
```

Assertions:

- `agent_primary` applies one approved non-destructive mutation.
- `preview` records `decision: "preview_only"` with an allowed pending-summary
  status, leaves ticket state unchanged, and never emits
  `status: "preview_only"`.
- `discussion_only` returns one discussion question and leaves ticket state unchanged.
- Conflicting candidate is skipped without blocking unrelated plausible candidate.
- `thread_id` is required in strict turn context and every pending-summary event
  records that same `thread_id`.
- Runtime-first mode is resolved from a local snapshot keyed by
  `(project_root, thread_id)`: after one `apply-turn` creates the snapshot,
  direct edits to `.codex/ticket.local.md` do not change later turns for that
  same thread/project, while a different `thread_id` reads the current strict
  config and receives a separate snapshot.
- Every pending-summary event copies `repo_context` from the strict turn
  context `git` object, including repo root, worktree root, repo fingerprint,
  branch, and HEAD.
- Approved ticket writes do not append terminal `applied` records before
  `apply_autonomous_mutation()` runs.
- Successful approved writes receive gateway-owned events in order:
  `mutation_attempt`, `approval_consumed`, `ticket_written`, then terminal
  `applied`.
- Summary contains `Applied`, `Skipped`, and `Discussion required` buckets only when non-empty.
- No Ticket changes and no discussion needed returns one parseable JSON no-op
  object, not silent stdout:

```json
{"state":"no_change","changed":false,"ticket_updates":null,"discussion_question":null}
```

- A strict context with `"operation": "pause_automation"` is handled before
  candidate discovery, writes the same workspace pause marker and strict JSON
  `discussion_only` config as `ticket_autonomy.py pause`, returns the explicit
  pause JSON response, and appends no mutation-attempt or ticket-write events.

- [ ] **Step 2: Run failing integration tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_integration_v1.py tests/test_autonomy_cli.py -q
```

- [ ] **Step 3: Implement `apply-turn` orchestration**

`apply-turn` order:

1. Validate context JSON.
2. If context `operation` is `pause_automation`, write the workspace pause
   marker, rewrite `.codex/ticket.local.md` to strict JSON `discussion_only`,
   verify local files are ignored and unstaged, return the explicit pause JSON,
   and stop before candidate discovery.
3. Ensure local workspace setup.
4. Resolve thread-scoped mode from the local snapshot keyed by
   `(project_root, thread_id)`. If no snapshot exists, read strict config and
   write the first snapshot for that thread/project.
5. Check workspace pause marker.
6. Run the event-derived recovery health check from Task 5 and block new
   writes if bookkeeping is unhealthy. For incomplete write states that require
   live ticket fingerprint comparison, return a paused recovery-needed response
   until the full Task 11 projection is available.
7. Discover candidates and evidence.
8. Evaluate candidates.
9. Append pending-summary records itself only for non-write outcomes:
   `skipped`, preview-mode `status: "skipped"` with
   `decision: "preview_only"`, `discussion_required`, `deferred`, and
   non-gateway `failed`.
10. Apply approved mutations through `apply_autonomous_mutation()` and let the
   gateway own `mutation_attempt`, `approval_consumed`, `ticket_written`, and
   terminal write outcomes including `applied`.
11. Render display-ready summary and at most one discussion question.
12. Append summary receipts.

- [ ] **Step 4: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_integration_v1.py tests/test_autonomy_cli.py tests/test_engine_gateway.py tests/test_turn_batch.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py
git commit -m "feat(ticket): apply autonomous turn updates"
```

---

## Task 11: Add Full Recovery Matrix And Compaction

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_turn_batch.py`

- [ ] **Step 1: Write remaining recovery matrix tests**

Tests must prove:

- `attempt_recorded` only retries with the same `mutation_id` when approval inputs still match.
- `approval_consumed` with current ticket state matching the expected
  post-write fingerprint appends missing `ticket_written` and terminal status
  events without rewriting the ticket.
- `approval_consumed` with current ticket state matching the bound pre-write
  fingerprint returns retry-with-same-mutation.
- `approval_consumed` with current ticket state matching neither fingerprint
  returns pause-for-reconciliation.
- `ticket_written` without terminal status appends outcome status when current ticket matches expected post-write fingerprint.
- `status_recorded` without summary emits recovery summary and appends `summary_receipt`.
- `summary_recorded` does not retry mutation.
- Compaction keeps correction-ready detail for no more than 14 days and no more than 500 correction-ready events.
- Compaction writes a temp file, validates it, and atomically replaces active JSONL only after validation succeeds.

Required public surface:

```python
@dataclass(frozen=True, slots=True)
class RecoveryProjection:
    state: Literal[
        "healthy",
        "retry_with_same_mutation",
        "append_missing_ticket_written",
        "append_missing_terminal_status",
        "summary_ready",
        "pause_for_reconciliation",
    ]
    mutation_id: str
    current_ticket_fingerprint: str | None
    expected_pre_write_fingerprint: str | None
    expected_post_write_fingerprint: str | None
    events_to_append: tuple[Mapping[str, object], ...] = ()
    reason: str | None = None


def project_mutation_recovery(
    *,
    store: PendingSummaryStore,
    mutation_id: str,
    current_ticket_fingerprint: str | None,
) -> RecoveryProjection: ...
```

- [ ] **Step 2: Run failing recovery tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_recovery.py tests/test_turn_batch.py -q
```

- [ ] **Step 3: Implement recovery and compaction**

Keep recovery append-only. Do not edit old event lines in normal operation.
`project_mutation_recovery()` must read bound pre-write and expected post-write
fingerprints from pending-summary event payloads, compare them to the
`current_ticket_fingerprint` supplied by `ticket_autonomy.py` or
`ticket_engine_gateway.py`, and return a display-ready projection. If the
needed bound fingerprints are missing, return `pause_for_reconciliation`
instead of guessing.

- [ ] **Step 4: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_recovery.py tests/test_turn_batch.py tests/test_autonomy_cli.py tests/test_engine_gateway.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py plugins/turbo-mode/ticket/tests/test_turn_batch.py
git commit -m "feat(ticket): recover autonomous mutation state"
```

---

## Task 12: Add Ticket Commit Coordinator And Commit Disposition

**Files:**

- Create: `plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py`
- Create: `plugins/turbo-mode/ticket/tests/test_ticket_commit_coordinator.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`

- [ ] **Step 1: Write commit coordinator tests**

Tests must prove:

- Pre-existing staged changes are detected before any `git add` or commit is
  attempted.
- Ticket-only commit stages only touched `docs/tickets/**` files and automation-created ticket-owned durable records.
- Pending-summary files are never staged.
- Unrelated user files are never staged.
- If the index already contains unrelated staged paths, the coordinator returns
  `commit_deferred` with a one-sentence reason and leaves the index unchanged.
- File overlap or ambiguity records `commit_deferred` with one-sentence reason.
- Ticket-only commit messages use:
  - `tickets: update project state`
  - `tickets: capture follow-up work`
- `commit_recorded` includes commit hash.
- `commit_bundled_with_work` is recorded only when a containing commit exists or has an identifier supplied by the caller.
- Missing containing commit uses `commit_deferred`, not `commit_bundled_with_work`.

Required public surface:

```python
@dataclass(frozen=True, slots=True)
class CommitDispositionRecord:
    disposition: CommitDisposition
    commit_hash: str | None = None
    reason: str | None = None


def record_ticket_commit_disposition(
    *,
    project_root: Path,
    touched_ticket_paths: tuple[Path, ...],
    related_commit: str | None = None,
    create_ticket_only_commit: bool,
) -> CommitDispositionRecord: ...
```

- [ ] **Step 2: Run failing commit tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_ticket_commit_coordinator.py -q
```

- [ ] **Step 3: Implement coordinator**

Implementation requirements:

- Use non-interactive git commands.
- Inspect the existing index before staging anything. If any path is already
  staged and is not exactly within the allowed ticket-owned path set for this
  disposition, return `commit_deferred` and do not mutate the index.
- Run changed-ticket parse/schema validation, pending-summary log validation, and `git diff --check`.
- Do not push.
- Do not stage `.codex/ticket-workspace/`.
- Return `commit_deferred` instead of taking unsafe staging action.

- [ ] **Step 4: Integrate disposition into gateway and summaries**

Update `applied` status events and end-of-turn summaries so every ticket-file write includes one commit disposition.

- [ ] **Step 5: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_ticket_commit_coordinator.py tests/test_engine_gateway.py tests/test_autonomy_integration_v1.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py plugins/turbo-mode/ticket/tests/test_ticket_commit_coordinator.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py plugins/turbo-mode/ticket/tests/test_ticket_commit_coordinator.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py
git commit -m "feat(ticket): record ticket commit disposition"
```

---

## Task 13: Integrate Update, Review-Style Hygiene, And Capture Candidates

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_review.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_update_refinement.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_review_findings.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_capture.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`

- [ ] **Step 1: Write adapter tests**

Tests must prove:

- `ticket_update.py` can feed structured update/lifecycle/refinement candidates into `apply-turn` without granting write authority itself.
- `ticket_review.py` stays read-only when invoked directly for review, but ordinary thread automation can convert deterministic hygiene findings into candidate records.
- `ticket_capture.py` can create a candidate for clear actionable follow-up work.
- Vague ideas and "maybe later" capture candidates route to discussion required.
- Wrappers cannot forge an approval envelope or write through the gateway by omitting runtime validation.

- [ ] **Step 2: Run failing adapter tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_update_refinement.py tests/test_review_findings.py tests/test_capture.py tests/test_autonomy_integration_v1.py -q
```

- [ ] **Step 3: Implement adapter hooks**

Adapters may build `AutonomyIntent` context and candidate records. They must not:

- decide approval validity
- write pending-summary records directly
- write active ticket files directly in autonomous mode
- bypass the engine-owned gateway

- [ ] **Step 4: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_update_refinement.py tests/test_review_findings.py tests/test_capture.py tests/test_autonomy_integration_v1.py tests/test_engine_gateway.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_update.py plugins/turbo-mode/ticket/scripts/ticket_review.py plugins/turbo-mode/ticket/scripts/ticket_capture.py plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_update.py plugins/turbo-mode/ticket/scripts/ticket_review.py plugins/turbo-mode/ticket/scripts/ticket_capture.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py plugins/turbo-mode/ticket/tests/test_update_refinement.py plugins/turbo-mode/ticket/tests/test_review_findings.py plugins/turbo-mode/ticket/tests/test_capture.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py
git commit -m "feat(ticket): feed autonomy candidates from ticket adapters"
```

---

## Task 14: Add Correction Flow

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Create: `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`

- [ ] **Step 1: Write correction tests**

Tests must prove:

- User-triggered correction of an ordinary automatic update applies without another approval round when correction detail still exists.
- Wrongly created ticket is corrected by marking it `wontfix` with `correction` history, not by deletion.
- Delete, archive, history repair, rewriting `## Change History`, removing prior entries, and git history edits route to discussion required.
- Expired correction detail makes the runtime inspect current ticket state and lightweight history; if not obvious and low-risk, it asks.

- [ ] **Step 2: Run failing correction tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_corrections.py -q
```

- [ ] **Step 3: Implement correction decisions**

Use pending-summary correction-ready details when retained. Append `correction` `## Change History` entries; never delete or rewrite project history automatically.

- [ ] **Step 4: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_corrections.py tests/test_turn_batch.py tests/test_engine_gateway.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py
git commit -m "feat(ticket): support automatic ticket corrections"
```

---

## Task 15: Final Source Closeout And Static Boundary Proof

**Files:**

- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- Create: `plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py`

- [ ] **Step 1: Add final static boundary tests**

Tests must prove:

- Current-facing docs describe `agent_primary`, `discussion_only`, and `preview`.
- Current-facing docs do not instruct users to configure YAML `auto_audit`,
  `auto_silent`, or `suggest`.
- Future autonomous durable history is `## Change History` plus local pending-summary bookkeeping.
- Installed runtime success is not claimed.
- `ticket_autonomy.py` exposes only Ticket-level CLI commands, not raw ledger mutation commands.
- Pending-summary validation rejects events missing required `repo_context` or
  available branch/HEAD/worktree identity.
- Direct active-ticket write paths outside the gateway or specific named
  maintenance command functions are flagged; whole helper-file allowlists are
  not sufficient proof.
- No source file writes to `docs/tickets/.audit/` for future autonomous behavior.
  Named historical read/doctor maintenance commands may still repair existing
  `.audit/` files, and the static proof must keep that exception explicit.
- Legacy tests no longer assert active `.audit` writes, YAML autonomy config,
  missing-config fallback to `suggest`, valid `auto_audit`, or valid
  `auto_silent` as current runtime-first behavior.
- Runtime-readiness source and tests no longer stage YAML `auto_audit` config
  or assert old-mode payloads as current readiness evidence.
- Test files may contain old-mode strings only in allowed negative or historical
  fixtures identified by the Task 2 inventory. `test_static_autonomy_boundaries.py`
  must distinguish forbidden current-behavior assertions from allowed fixture
  text instead of raw-scanning all tests for any occurrence of the old strings.
  At minimum, fail on tests that assert old modes are valid, old missing-config
  fallback to `suggest` is valid, old `auto_audit`/`auto_silent` policy lanes
  succeed as current behavior, or runtime-readiness proof stages old-mode YAML.
  Permit strings inside tests whose assertions prove those old modes are invalid
  under strict config or inside historical `.audit` reader/doctor fixtures.

- [ ] **Step 2: Run focused docs and guard tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_static_autonomy_boundaries.py tests/test_engine_gateway.py tests/test_autonomy_cli.py -q
rg -n \
  -e 'autonomy_mode: auto_audit' \
  -e 'autonomy_mode: auto_silent' \
  -e 'autonomy_mode: suggest' \
  -e 'defaults to `suggest`' \
  -e 'creates `.audit`' \
  -e 'created automatically on the first agent mutation' \
  plugins/turbo-mode/ticket/README.md \
  plugins/turbo-mode/ticket/HANDBOOK.md \
  plugins/turbo-mode/ticket/references/ticket-contract.md \
  plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py
rg_status=$?
if [ "$rg_status" -eq 0 ]; then
  exit 1
fi
if [ "$rg_status" -gt 1 ]; then
  exit "$rg_status"
fi
```

- [ ] **Step 3: Run full Ticket source verification**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
git diff --check
git status --short
```

- [ ] **Step 4: Inspect local-only residue**

Expected local-only files may exist only under ignored paths:

- `.codex/ticket-workspace/`
- `.codex/ticket.local.md`
- `.pytest_cache/` or `.ruff_cache/` if verification creates them

Do not stage local-only Ticket workspace state. Clean verification residue only when it is inside ignored cache paths and cleanup is in scope.

- [ ] **Step 5: Commit final docs/guard closeout**

```bash
git add plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/references/ticket-contract.md plugins/turbo-mode/ticket/tests/test_docs_contract.py plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py
git commit -m "docs(ticket): document runtime-first autonomy source behavior"
```

If Step 3 already passed and no docs changed in this task, skip this final commit and record that no closeout commit was necessary.

---

## Runtime And Publish Boundaries

Source completion means:

- source files, docs, and tests in this checkout implement the plan;
- focused and full source verification passed;
- no local-only pending-summary or config files are staged;
- installed runtime behavior is not claimed.

Installed runtime proof is separate:

- Do not refresh `/Users/jp/.codex/plugins/cache` during source implementation.
- Do not run guarded refresh as a side effect of this plan.
- After source work is complete, a separate user-approved refresh/proof lane must inspect app-server/runtime inventory before claiming installed behavior.

Publishing is separate:

- Do not push or create a PR unless the user asks.
- If publishing is requested later, review the final diff and verification evidence first.

---

## Final Source Verification

Run after all implementation tasks are complete:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
git diff --check
git status --short --branch
```

Expected closeout statement:

- Source implementation complete.
- Installed runtime not refreshed.
- Installed behavior not claimed.
- Local-only Ticket workspace state not staged.
- Remaining follow-up, if any, is explicit installed-runtime refresh/proof or publication.

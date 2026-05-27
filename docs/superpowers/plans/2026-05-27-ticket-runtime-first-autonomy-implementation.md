# Ticket Runtime-First Autonomy Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the source implementation for the runtime-first Ticket autonomy design so Ticket can apply non-destructive autonomous mutations through one engine-owned gateway, record durable pending-summary state, preserve ticket-owned `## Change History`, and return one concise end-of-turn projection.

**Architecture:** Implement the rollout in source-only slices. First remove future `.audit/` writes and add local-only workspace setup, then add strict config, deterministic IDs, append-only pending-summary events, `## Change History` helpers, host-facing CLI projections, the runtime evaluator, the engine-owned write gateway, recovery, summaries, commit disposition, and finally broader capture/candidate integration. Codex keeps semantic judgment in the turn context; Python enforces deterministic mechanics, write safety, idempotency, and recovery.

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

Hard stops:

- Stop if the branch is not at or after `9453d18` and the spec file differs materially from this plan.
- Stop if `.codex/handoffs/`, `.codex/ticket-workspace/`, `.codex/ticket.local.md`, or pending-summary files appear in staged changes.
- Stop if any task needs to mutate `/Users/jp/.codex/plugins/cache`, personal plugin state, or installed runtime state.
- Stop before widening autonomous writes to delete, archive, or history repair.
- Stop before adding a passive policy registry that is not wired to the actual write path.

Verification command defaults:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
git diff --check
```

Use focused selectors inside each task first. Run the full Ticket suite before the final source closeout.

---

## File Structure

Create these focused runtime modules:

- `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py` - host-facing JSON-in/JSON-out CLI for `recover`, `apply-turn`, `doctor-ledger`, and `migrate-change-history`.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py` - strict `.codex/ticket.local.md` JSON config, workspace pause marker, local setup, ignored-path checks, and local `.codex/ticket-workspace/AGENTS.md` repair.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_ids.py` - canonical JSON serialization, deterministic `evt_`, `mut_`, and `appr_` IDs, and fingerprint helpers.
- `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py` - pending-summary envelope types, validation, append-only JSONL writer, lock/temp-file handling, state derivation, recovery projections, summaries, and compaction.
- `plugins/turbo-mode/ticket/scripts/ticket_change_history.py` - `## Change History` parsing, insertion, label validation, and `migrate-change-history` planning/application.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py` - `AutonomyIntent`, hard policy decisions, fanout caps, approval envelopes, and runtime decision objects.
- `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py` - deterministic candidate extraction from structured turn context, explicit ticket mentions, ticket metadata, related paths, diff/test references, and Codex-proposed candidate changes.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py` - engine-owned autonomous write gateway that validates approvals, rechecks pause state, records ledger transitions, writes `## Change History`, and delegates to existing mutation mechanics.
- `plugins/turbo-mode/ticket/scripts/ticket_commit_coordinator.py` - local ticket-only commit disposition helper that stages only ticket-owned files and never stages local pending-summary state.

Modify these existing source surfaces:

- `.gitignore` - add local-only `.codex/ticket-workspace/` rules when the workspace state path is introduced.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py` - disable future `.audit/` writes, expose existing low-level mutation dispatch to the autonomous gateway, and keep user-directed ordinary writes explicitly non-autonomous.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py` - preserve low-level compatibility while passing explicit non-autonomous intent for user-directed execute paths.
- `plugins/turbo-mode/ticket/scripts/ticket_capture.py` - later adapter integration for automatic creation of clear follow-up tickets.
- `plugins/turbo-mode/ticket/scripts/ticket_update.py` - adapter integration for update/lifecycle/refinement mutation candidates.
- `plugins/turbo-mode/ticket/scripts/ticket_review.py` - read-only review remains read-only, but hygiene suggestions can feed structured candidates to `apply-turn` when called from ordinary thread automation.
- `plugins/turbo-mode/ticket/scripts/ticket_doctor.py` - keep maintenance bypasses named, dry-run-first, and explicitly confirmed.
- `plugins/turbo-mode/ticket/references/ticket-contract.md` - keep the contract aligned with source behavior.
- `plugins/turbo-mode/ticket/README.md` and `plugins/turbo-mode/ticket/HANDBOOK.md` - remove active `.audit` and old mode guidance as each source migration lands.

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
- Extend `plugins/turbo-mode/ticket/tests/test_audit.py`
- Extend `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
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
```

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

---

## Task 1: Disable Future `.audit/` Writes

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/tests/test_audit.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

- [ ] **Step 1: Write the failing `.audit` disablement tests**

Add focused tests that prove `engine_execute()` no longer creates `docs/tickets/.audit/` for user or agent requests, while historical audit read/repair support remains intact.

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

- `.audit` is described as historical or legacy only.
- Future autonomous writes use `## Change History` plus local pending-summary bookkeeping.
- Active `.audit` creation, active full JSONL audit trail language, and old `auto_audit` setup instructions are absent from current-facing guidance except in clearly historical context.

- [ ] **Step 2: Run the failing tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_audit.py tests/test_docs_contract.py -q
```

Expected before implementation: at least the new `.audit` write-disablement test fails because `engine_execute()` still creates `docs/tickets/.audit/YYYY-MM-DD/<session>.jsonl`.

- [ ] **Step 3: Disable future `.audit` writes in source**

Change `ticket_engine_core.py` so normal execution no longer calls `_audit_append()` around dispatch. Preserve `engine_count_session_creates()` and `ticket_audit.py` for historical read/doctor support.

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

Then remove the agent fail-closed dependence on result audit writes from `engine_execute()`. The later gateway tasks restore fail-closed bookkeeping through `ticket.pending-summary.jsonl`, not `.audit`.

- [ ] **Step 4: Update docs to match the migration**

Patch README/HANDBOOK/contract so they say:

- Existing `docs/tickets/.audit/` files are historical artifacts.
- Future autonomous durable history writes to affected tickets' `## Change History`.
- Future local operational state writes to `.codex/ticket-workspace/ticket.pending-summary.jsonl`.
- `ticket_audit.py` and `ticket_doctor.py repair-audit` remain read/repair tools for existing historical audit files only.

- [ ] **Step 5: Verify and commit**

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
- Modify: `.gitignore`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`

- [ ] **Step 1: Write strict config and workspace setup tests**

Test cases:

- Missing `.codex/ticket.local.md` returns a setup-required result with no fallback to old modes.
- Valid file is exactly `{"schema":"codex.ticket.local.v1","mode":"agent_primary"}` or another allowed mode.
- Unknown keys, Markdown, fenced JSON, YAML frontmatter, comments, old modes `suggest`, `auto_audit`, and `auto_silent` are invalid.
- `write_local_config(project_root, AutomationMode.AGENT_PRIMARY)` rewrites the whole file as strict JSON.
- `ensure_ticket_workspace(project_root)` creates `.codex/ticket-workspace/AGENTS.md` with local-only staging guidance.
- `ensure_ticket_workspace(project_root)` verifies `.codex/ticket-workspace/` is ignored.
- `write_workspace_pause(project_root, reason="user_requested")` writes a local pause marker and `is_workspace_paused(project_root)` returns true.

Required public surface:

```python
class LocalConfigState(StrEnum):
    VALID = "valid"
    SETUP_REQUIRED = "setup_required"


@dataclass(frozen=True, slots=True)
class LocalConfigResult:
    state: LocalConfigState
    mode: AutomationMode | None
    path: Path
    reason: str | None = None


def read_local_config(project_root: Path) -> LocalConfigResult: ...
def write_local_config(project_root: Path, mode: AutomationMode) -> Path: ...
def ensure_ticket_workspace(project_root: Path) -> Path: ...
def write_workspace_pause(project_root: Path, *, reason: str) -> Path: ...
def clear_workspace_pause(project_root: Path) -> None: ...
def is_workspace_paused(project_root: Path) -> bool: ...
```

- [ ] **Step 2: Run the failing config tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_config.py -q
```

Expected before implementation: import failure for `scripts.ticket_autonomy_config`.

- [ ] **Step 3: Implement `ticket_autonomy_config.py`**

Implementation requirements:

- Use `json.loads()` on the full file text.
- Require object type, exact keys `schema` and `mode`, schema `codex.ticket.local.v1`, and mode in `discussion_only`, `preview`, `agent_primary`.
- Return setup-required instead of silently choosing a default.
- Write JSON compactly with a trailing newline: `{"schema":"codex.ticket.local.v1","mode":"agent_primary"}\n`.
- Use `.codex/ticket-workspace/pause.json` as the workspace-wide pause marker.
- Create `.codex/ticket-workspace/AGENTS.md` with plain local guidance:

```markdown
# Ticket Automation Workspace State

Files in this directory are local Ticket automation bookkeeping.
Do not stage, commit, push, publish, or treat them as project history.
Project truth remains in `docs/tickets/` ticket files and committed `## Change History` entries.
```

- [ ] **Step 4: Add local-only ignore rules**

Patch `.gitignore` narrowly:

```gitignore
.codex/ticket-workspace/
.codex/ticket.local.md
```

Do not add broad `.codex/` ignores.

- [ ] **Step 5: Update current-facing docs**

Update README/HANDBOOK/contract to document strict JSON local config and workspace pause behavior. Remove current-facing YAML-frontmatter setup instructions for old modes.

- [ ] **Step 6: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_config.py tests/test_docs_contract.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py plugins/turbo-mode/ticket/tests/test_autonomy_config.py
git diff --check
git status --short
```

Commit:

```bash
git add .gitignore plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py plugins/turbo-mode/ticket/tests/test_autonomy_config.py plugins/turbo-mode/ticket/references/ticket-contract.md plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md
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
- Changing ticket ID, mutation fingerprint, ticket-state fingerprint, evidence fingerprint, session mode, or decision kind changes the relevant ID.

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
- No unknown top-level fields.
- Valid event/status compatibility matrix.
- Finite action, decision, mode, evidence kind, pause reason, and commit disposition values.
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


def validate_pending_summary_event(event: Mapping[str, object]) -> ValidationResult: ...
def event_payload_fingerprint(event_without_event_id_and_timestamp: Mapping[str, object]) -> str: ...
```

- [ ] **Step 2: Run failing validation tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_turn_batch.py::test_pending_summary_envelope_requires_strict_fields -q
```

- [ ] **Step 3: Implement envelope validation**

Keep validation deterministic and local to `ticket_turn_batch.py`. Do not use a semantic classifier script. This module validates shapes, finite values, and state compatibility only.

- [ ] **Step 4: Add representative fixtures**

Add test helper functions inside `test_turn_batch.py`:

```python
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
- `approval_consumed` with current post-write fingerprint appends missing `ticket_written` and terminal status without rewriting the ticket.
- `approval_consumed` with current pre-write fingerprint returns retry-with-same-mutation.
- `approval_consumed` with neither fingerprint returns pause-for-reconciliation.

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

Represent derived mutation state from events, not from a mutable in-memory flag. Keep recovery output display-ready but do not let host/runtime parse raw events directly.

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
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`

- [ ] **Step 1: Write Change History tests**

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

Required public surface:

```python
@dataclass(frozen=True, slots=True)
class ChangeHistoryEntry:
    timestamp: str
    label: ChangeHistoryLabel
    reason: str
    prior_commit: str | None = None


def render_change_history_entry(entry: ChangeHistoryEntry) -> str: ...
def append_change_history_entry(ticket_text: str, entry: ChangeHistoryEntry) -> str: ...
def plan_change_history_migration(tickets_dir: Path) -> tuple[Path, ...]: ...
def apply_change_history_migration(tickets_dir: Path) -> tuple[Path, ...]: ...
```

- [ ] **Step 2: Run failing Change History tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_change_history.py -q
```

- [ ] **Step 3: Implement helper and CLI command**

Create `ticket_autonomy.py` in this task with only the `migrate-change-history --project-root <PROJECT_ROOT> --dry-run|--apply` subcommand. Task 7 extends the same file with `recover`, `apply-turn`, and `doctor-ledger`.

CLI stdout examples:

```json
{"state":"ok","changed":false,"candidate_count":2,"candidates":["docs/tickets/example.md"]}
```

```json
{"state":"ok","changed":true,"updated_count":2,"updated":["docs/tickets/example.md"]}
```

- [ ] **Step 4: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_change_history.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_change_history.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/tests/test_change_history.py
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
- Create: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`

- [ ] **Step 1: Write CLI contract tests**

Tests must prove:

- `recover --project-root <root> --turn-id <id>` returns parseable JSON on stdout.
- `apply-turn --project-root <root> --turn-id <id> --context-file <path>` rejects invalid context with exit code `2`.
- Missing or invalid local config returns exit code `3` with a setup-required JSON object.
- Workspace pause marker returns exit code `3` with pause output.
- Host-facing CLI never exposes raw ledger append/consume/mark-summarized commands.
- `doctor-ledger --dry-run` validates ledger health and returns JSON.
- `doctor-ledger --confirm-repair` is the only repair command that can rewrite ledger files.

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

- [ ] **Step 3: Implement `recover`, `apply-turn`, and `doctor-ledger`**

Implementation requirements:

- Parse args with `argparse`.
- Print one JSON object to stdout for every handled outcome.
- Use stderr only for unexpected tracebacks.
- Exit `0`, `1`, `2`, or `3` according to the shared contract.
- `recover` calls `PendingSummaryStore` projections and returns display-ready summaries.
- `apply-turn` validates strict turn context and local config, then returns `preview`, `discussion_only`, `paused`, or an empty no-change result until gateway integration lands in Task 10.

- [ ] **Step 4: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_cli.py tests/test_turn_batch.py tests/test_autonomy_config.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py
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
- Pending-summary attempt event is recorded before ticket mutation.
- Pending-summary failure prevents ticket mutation.
- `approval_consumed`, `ticket_written`, and `applied` events are appended in order for a successful automatic update.
- The same automatic mutation writes its `## Change History` entry in the ticket mutation.
- User-directed ordinary writes stay explicitly non-autonomous and do not consume approval.
- Maintenance/doctor bypasses are named and not accepted by the autonomous gateway.

Required public surface:

```python
@dataclass(frozen=True, slots=True)
class GatewayMutation:
    action: str
    ticket_id: str | None
    fields: Mapping[str, object]
    tickets_dir: Path
    target_fingerprint: str | None


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
- Recheck workspace pause marker immediately before consuming approval.
- Append `mutation_attempt` before write and fail closed if it cannot persist.
- Append `approval_consumed` before entering protected write section.
- Apply the existing low-level mutation mechanics through `ticket_engine_core.py`.
- Append `ticket_written` with expected post-write fingerprint.
- Append terminal `applied`, `skipped`, `discussion_required`, `deferred`, or `failed`.
- For ticket-file writes, include `commit_disposition` details. Until Task 12 lands, use `commit_deferred` with reason `Commit coordinator not yet run for this source slice.`

- [ ] **Step 4: Add bypass-prevention static guard**

Add tests that scan Ticket scripts for direct active-ticket writes outside allowed files. The first allowlist is:

- `ticket_engine_core.py`
- `ticket_engine_gateway.py`
- `ticket_change_history.py`
- explicit maintenance/doctor files when the tested command is dry-run-first or confirm-gated

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
- `preview` records preview-only outcome and leaves ticket state unchanged.
- `discussion_only` returns one discussion question and leaves ticket state unchanged.
- Conflicting candidate is skipped without blocking unrelated plausible candidate.
- Summary contains `Applied`, `Skipped`, and `Discussion required` buckets only when non-empty.
- No output appears when no Ticket changes and no discussion are needed.

- [ ] **Step 2: Run failing integration tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_integration_v1.py tests/test_autonomy_cli.py -q
```

- [ ] **Step 3: Implement `apply-turn` orchestration**

`apply-turn` order:

1. Validate context JSON.
2. Ensure local workspace setup.
3. Read session mode once.
4. Check workspace pause marker.
5. Run recovery projection and block new writes if recovery says bookkeeping is unhealthy.
6. Discover candidates and evidence.
7. Evaluate candidates.
8. Append pending-summary records for applied, skipped, preview-only, discussion-required, and deferred candidates.
9. Apply approved mutations through `apply_autonomous_mutation()`.
10. Render display-ready summary and at most one discussion question.
11. Append summary receipts.

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
- Modify: `plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_turn_batch.py`

- [ ] **Step 1: Write remaining recovery matrix tests**

Tests must prove:

- `attempt_recorded` only retries with the same `mutation_id` when approval inputs still match.
- `ticket_written` without terminal status appends outcome status when current ticket matches expected post-write fingerprint.
- `status_recorded` without summary emits recovery summary and appends `summary_receipt`.
- `summary_recorded` does not retry mutation.
- Compaction keeps correction-ready detail for no more than 14 days and no more than 500 correction-ready events.
- Compaction writes a temp file, validates it, and atomically replaces active JSONL only after validation succeeds.

- [ ] **Step 2: Run failing recovery tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_recovery.py tests/test_turn_batch.py -q
```

- [ ] **Step 3: Implement recovery and compaction**

Keep recovery append-only. Do not edit old event lines in normal operation.

- [ ] **Step 4: Verify and commit**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_autonomy_recovery.py tests/test_turn_batch.py tests/test_autonomy_cli.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py
git diff --check
```

Commit:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/tests/test_autonomy_recovery.py plugins/turbo-mode/ticket/tests/test_turn_batch.py
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

- Ticket-only commit stages only touched `docs/tickets/**` files and automation-created ticket-owned durable records.
- Pending-summary files are never staged.
- Unrelated user files are never staged.
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
- Current-facing docs do not instruct users to configure YAML `auto_audit`.
- Future autonomous durable history is `## Change History` plus local pending-summary bookkeeping.
- Installed runtime success is not claimed.
- `ticket_autonomy.py` exposes only Ticket-level CLI commands, not raw ledger mutation commands.
- Direct active-ticket write paths outside the gateway or named maintenance exceptions are flagged.
- No source file writes to `docs/tickets/.audit/` for future autonomous behavior.

- [ ] **Step 2: Run focused docs and guard tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_static_autonomy_boundaries.py tests/test_engine_gateway.py tests/test_autonomy_cli.py -q
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

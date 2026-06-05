# Ticket Candidate Contract Migration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Expose and enforce the literal Ticket target candidate mutation contract in source so autonomous create/update/close/reopen/correct writes use the same visible-board envelope documented by the May 30 control doc.

**Architecture:** Candidate shape becomes an explicit `action`, `ticket_id`, `target`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary` envelope. Runtime validation owns target-envelope shape and deterministic authorization; the gateway projects target fields/sections into existing engine primitives and records recovery facts. Engine rendering remains the write authority, with a narrow extension for exact level-2 target section updates.

**Tech Stack:** Python 3.11, dataclasses, pytest, existing Ticket scripts under `plugins/turbo-mode/ticket/scripts/`, existing target ticket schema/render/engine helpers.

---

## Evidence Baseline

Live state checked before writing this plan, after the initial plan commit, after
the review hardening patch, after the correction-gate clarification, and after
the source-entrypoint coverage patch:

- Branch/worktree at plan creation: `main...origin/main`, clean normal status,
  `HEAD` at `92cd4bed`.
- Branch/worktree after committing the initial plan: `main...origin/main [ahead 1]`,
  clean normal status, `HEAD` at `38537aa9`.
- Branch/worktree after the review hardening patch: `main...origin/main [ahead 2]`,
  clean normal status, `HEAD` at `69f44342`.
- Branch/worktree after the correction-gate clarification: `main...origin/main [ahead 3]`,
  clean normal status, `HEAD` at `6d7e1579`.
- Branch/worktree after the source-entrypoint coverage patch:
  `main...origin/main [ahead 4]`, clean normal status, `HEAD` at `d52a81ab`.
- Active ticket inventory: seven files under `docs/tickets/`; all use ID-only filenames, frontmatter metadata, target statuses, required sections, no unknown frontmatter keys, and no blocked-shape defects.
- Active ticket statuses: six `open`, one `done`, no `status: in_progress`.
- Historical references: old-looking `T-20260527-001` examples only appear in `docs/superpowers/specs/2026-05-26-ticket-runtime-first-autonomy-design.md`; placeholders such as `T-YYYYMMDD-NN` appear in ADR/control docs and are not active ticket IDs.
- Source gap: `CandidateMutation`, gateway dispatch, discovery, and mutation identity still use flat `proposed_change` plus `target_fingerprint`/evidence-link vocabulary.

This is a source/repo plan only. Do not claim installed runtime proof from this plan or from source tests. Installed proof requires a separate runtime inventory lane.

## File Structure

Modify these files:

- `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
  - Owns `CandidateTarget`, target-shaped `CandidateMutation`, mapping validation, runtime decisions, fanout caps, and `EngineDispatch`.
- `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
  - Converts explicit turn-context candidate mappings into target-shaped `CandidateMutation` objects and stops converting vague/path-only signals into write candidates.
- `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
  - Hashes canonical target candidate content, including `target`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`.
- `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
  - Projects evaluated target candidates through the live `apply-turn` source
    entrypoint and constructs target-shaped `GatewayMutation` requests without
    repopulating expected fingerprints from the old `source_context` side
    channel.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
  - Carries target-shaped `GatewayMutation`, recomputes mutation identity, validates expected fingerprints, projects exact target sections into engine dispatch, and records bounded recovery facts.
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
  - Extends update/close/reopen execution to accept or validate exact target section headings from the gateway without changing legacy direct `engine_execute()` field syntax.
- `plugins/turbo-mode/ticket/scripts/ticket_change_history.py`
  - Removes current `Reopen History` insertion assumptions from normal reopen
    flow and keeps generated `Change History` grammar aligned with the May 30
    control doc.
- `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
  - Separates retained target-candidate action facts from maintenance event
    validation and removes durable decision-kind/evidence-kind/current-mode
    detail requirements from mutation attempt events.
- `plugins/turbo-mode/ticket/scripts/ticket_validate.py`
  - Removes `reopen_reason` from normal target write-field acceptance once `reopen` uses `evidence_summary`.
- `plugins/turbo-mode/ticket/README.md`
- `plugins/turbo-mode/ticket/HANDBOOK.md`
- `plugins/turbo-mode/ticket/references/ticket-contract.md`
- `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md`
- `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md`
  - Update source-availability prose after the live source entrypoint exists. Do not claim installed runtime availability.

Test these files:

- `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`
- `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`
- `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`
- `plugins/turbo-mode/ticket/tests/test_engine_policy.py`
- `plugins/turbo-mode/ticket/tests/test_execute.py`
- `plugins/turbo-mode/ticket/tests/test_integration.py`
- `plugins/turbo-mode/ticket/tests/test_engine_runner.py`
- `plugins/turbo-mode/ticket/tests/test_review_findings.py`
- `plugins/turbo-mode/ticket/tests/test_change_history.py`
- `plugins/turbo-mode/ticket/tests/test_turn_batch.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
- `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

## Contract Decisions

- Migrate `reopen` fully in this slice. The May 30 control doc already states that the human reason belongs in `evidence_summary`, not `reopen_reason`, and that `reopen -> blocked` is valid when the blocked ticket shape is valid.
- Treat `correct` as the user-triggered correction lane for a recent Ticket
  write. A `correct` candidate may dispatch to update, close, or reopen
  according to its target status, but the gateway must admit it only when the
  paired runtime decision is `RuntimeDecisionKind.APPLY_CORRECTION`; that
  decision kind is the approval boundary for `correct -> reopen`.
- Keep full `reconcile_board` implementation out of this slice. This migration may make the future wrapper possible, but it must not implement discovery ordering, caps, overflow, or broad board search.
- Keep operation-log work narrow. This slice may update candidate identity, expected pre-write fingerprint, post-write fingerprint, evidence summary, target fields/sections, and write/summary flags. It must not add semantic ranking, evidence-kind taxonomies, approval-state taxonomies, or private workflow stages.
- Treat the target candidate envelope as exact. Do not accept `conflict_reason`
  as a top-level candidate key, do not store it on target-shaped
  `CandidateMutation`, and do not include it in identity, gateway, result, or
  operation-log payloads. If live discovery sees conflicting evidence, it should
  block before constructing a write candidate or carry a short mechanical pause
  reason outside candidate content.
- Remove vague `possible_candidates` and path-only candidates from write-candidate discovery. They are not target candidate mutations because they do not name a user-visible change. Future `reconcile_board` can reintroduce broad search as a wrapper that emits ordinary target candidates.
- Treat Tasks 1 and 2 as one atomic source commit group. Runtime identity calls
  start using the target-shaped identity helper before `test_autonomy_runtime.py`
  can be green; do not commit Task 1 by itself.
- Treat intermediate task commits as focused-green boundaries, not full-suite
  green boundaries. Do not claim the full Ticket suite is green until Task 7.
  If a task removes source behavior that a focused selector covers, rewrite or
  remove the corresponding tests in that same task. Tests outside the task's
  focused selector remain assigned to their named later task and must not be
  dismissed as unrelated failures.
- Treat `expected_ticket_fingerprint` as candidate content supplied by explicit
  target candidate mappings. `ticket_autonomy.py` must pass
  `decision.candidate.expected_ticket_fingerprint` into `GatewayMutation`; it
  must not synthesize or override that value from `_ticket_state_fingerprints()`
  or `source_context`. The gateway still recomputes the current ticket
  fingerprint immediately before writing and rejects stale candidates.

## Migration Coverage Map

Before implementation, build the rename/blast-radius map from live source. Run
both commands:

```bash
rg -n "target_fingerprint|mutation\.fields|\.evidence|EvidenceLink|\"correction\"|conflict_reason|reopen_reason|Reopen History|evidence_kind|current_mode|\"decision\"|decision\.kind|RuntimeDecisionKind|reprioritize|stale_cleanup|blocker_edit|refine|archive|delete|history_repair|summarize|compact|pause_automation|codex\.ticket\.mutation\.v1" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
rg -n "GatewayMutation\(|CandidateMutation\(" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
```

Assign every hit to one of these dispositions before claiming a task is green:

| Legacy surface | Target disposition | Must be covered in |
|---|---|---|
| `target_fingerprint` in candidate/gateway identity | Rename to `expected_ticket_fingerprint` for target candidate/gateway paths. Legacy direct engine plan/execute surfaces may keep `target_fingerprint` only when the task explicitly labels them outside the target candidate path. Calls to `scripts.ticket_dedup.target_fingerprint` may remain only as the helper that computes a current ticket fingerprint; import it as `compute_target_fingerprint` in changed tests when practical. | Tasks 1-3 and final residue check |
| `mutation.fields` on `GatewayMutation` | Rename to `mutation.proposed_change`, including create dedup and test fakes. | Task 3 |
| `GatewayMutation(...)` construction sites | Rewrite every source/test construction to the target-shaped constructor. `ticket_autonomy.py` is the live apply-turn spine and must be migrated in Task 3, not left to final verification. | Task 3 |
| `CandidateMutation(...)` construction sites | Rewrite every source/test construction to the target-shaped constructor or remove the old test. Construction sites are not covered by vocabulary greps alone. | Tasks 1-5 and final construction-site check |
| `.evidence`, `EvidenceLink`, evidence-kind floors | Replace with one-line `evidence_summary`; remove evidence-kind classification from runtime/discovery/gateway mutation-attempt facts. | Tasks 1, 2, and 5 |
| `"correction"` candidate action | Rename target candidate action to `"correct"` in runtime, gateway, turn-batch validation, tests, and generated history reason. Task 1 owns runtime action groups and `evaluate_autonomy_intent()`; Task 3 owns gateway/source-entrypoint projection; Task 5 owns correction fixtures and operation-log recovery assertions. Keep `RuntimeDecisionKind.APPLY_CORRECTION` only as an internal decision kind. | Tasks 1, 3, 5, and final residue check |
| `conflict_reason` candidate content | Remove from accepted target candidate mappings and from `CandidateMutation`. Conflict evidence may stop candidate construction or produce a short mechanical pause reason outside the target candidate envelope, but it must not enter candidate identity, gateway validation, result data, or mutation-attempt details. | Tasks 1, 2, and final residue check |
| `reprioritize`, `stale_cleanup`, `blocker_edit`, `refine` action literals | These are not target candidate actions. Fold write behavior into ordinary `update` candidates, delete old runtime/gateway/test action branches, and keep `stale_cleanup` only as read-only review-hygiene output that candidate discovery no longer accepts as a write candidate. | Tasks 1, 2, 5, and final residue check |
| `reopen_reason` and `Reopen History` normal write behavior | Move human reason to `evidence_summary`, append ordinary generated `Change History`, and rewrite/remove tests or helpers that preserve `Reopen History` as target behavior. | Task 4 |
| `evidence_kind`, `current_mode`, `"decision"`, and `decision.kind` mutation-attempt details | Remove from target candidate operation-log event details unless a separate operation-log redesign explicitly keeps a bounded mechanical fact allowed by the control doc. Runtime mode inputs may keep `current_mode` only when they are not persisted mutation-attempt details. `RuntimeDecisionKind` values may remain internal branch logic, but must not be persisted in mutation-attempt details or result data. | Task 5 |
| `archive`, `delete`, `history_repair`, `summarize`, `compact`, `pause_automation` action vocabulary | These are not target candidate actions. Keep maintenance vocabulary only in event-type-specific validation or hard discussion guards where the code is not recording a retained candidate action fact. Do not let these values validate a new `mutation_attempt` or `ticket_write` candidate action. | Task 5 and final residue check |
| `codex.ticket.mutation.v1` candidate identity fixtures | Replace candidate-contract identity helpers and fixtures with `codex.ticket.mutation.v2`. Low-level `make_mutation_id()` tests may keep arbitrary v1 schema examples only when they are not candidate-contract fixtures. | Task 2 and final residue check |
| `EngineDispatch.sections` for close/reopen | Do not compute sections and drop them. Either pass them to engine execution or explicitly validate that the engine-owned side effect exactly matches the named target cleanup. | Tasks 3 and 4 |

Tests that encode deprecated architecture must be rewritten or removed in the
same task that removes the behavior. Do not defer them to Task 7 as
"pre-existing unrelated failures."

## Task 0: Preflight And Ticket Inventory Gate

**Files:**
- Read: `docs/tickets/*.md`
- Read: `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
- Read: `docs/superpowers/plans/2026-06-04-ticket-target-status-candidate-shape.md`

- [ ] **Step 1: Confirm clean source state**

Run:

```bash
git status --short --branch
git rev-parse --short HEAD
```

Expected at the last reviewed source baseline before this operation-log and
exact-envelope patch:

```text
## main...origin/main [ahead 4]
d52a81ab
```

If `HEAD` has advanced, run `git diff --stat d52a81ab..HEAD` and re-check the
plan against the new diff before using the expected output as a gate. If the
only diff is this plan, record the live status and continue. If source files
changed, re-check the implementation steps against the new source before
continuing. If normal status is dirty before implementation, inspect the dirty
files and stop unless they are this plan or intentional implementation work for
the active task.

- [ ] **Step 2: Re-run the active ticket inventory**

Run this read-only inventory:

```bash
PYTHONDONTWRITEBYTECODE=1 python - <<'PY'
from pathlib import Path
import re

root = Path.cwd()
tickets_dir = root / "docs" / "tickets"
allowed_fields = {"id", "title", "status", "priority", "tags", "related_paths", "blocked_by"}
allowed_statuses = {"idea", "open", "blocked", "done", "wontfix"}
required_sections = ["Problem", "Next Action", "Change History"]

def parse_scalar(value: str) -> object:
    value = value.strip()
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [part.strip().strip("\"'") for part in inner.split(",")]
    return value.strip("\"'")

for path in sorted(tickets_dir.glob("*.md")):
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        print(path, "metadata=not_frontmatter")
        continue
    end = text.find("\n---", 4)
    frontmatter = {}
    for line in text[4:end].splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            frontmatter[key.strip()] = parse_scalar(value)
    headings = re.findall(r"^##\s+(.+?)\s*$", text[end + 4 :], flags=re.M)
    unknown = sorted(set(frontmatter) - allowed_fields)
    missing = [section for section in required_sections if section not in headings]
    status = frontmatter.get("status")
    blocked_by = frontmatter.get("blocked_by", [])
    invalid = []
    if path.stem != frontmatter.get("id"):
        invalid.append("filename_id_mismatch")
    if status not in allowed_statuses:
        invalid.append(f"bad_status={status!r}")
    if unknown:
        invalid.append(f"unknown_keys={unknown!r}")
    if missing:
        invalid.append(f"missing_sections={missing!r}")
    if status == "blocked" and "Blocked On" not in headings:
        invalid.append("blocked_missing_blocked_on")
    if status != "blocked" and "Blocked On" in headings:
        invalid.append("nonblocked_has_blocked_on")
    if status != "blocked" and blocked_by:
        invalid.append("nonblocked_has_blocked_by")
    if isinstance(blocked_by, list):
        bad_blockers = [item for item in blocked_by if re.fullmatch(r"T-\d{8}-\d{2}", str(item)) is None]
        if bad_blockers:
            invalid.append(f"bad_blocked_by={bad_blockers!r}")
    print(f"{path.relative_to(root)} status={status!r} invalid={invalid!r}")
PY
```

Expected:

```text
docs/tickets/T-20260508-01.md status='done' invalid=[]
docs/tickets/T-20260508-02.md status='open' invalid=[]
docs/tickets/T-20260516-01.md status='open' invalid=[]
docs/tickets/T-20260517-01.md status='open' invalid=[]
docs/tickets/T-20260518-01.md status='open' invalid=[]
docs/tickets/T-20260518-02.md status='open' invalid=[]
docs/tickets/T-20260526-01.md status='open' invalid=[]
```

- [ ] **Step 3: Stop if active ticket inventory is not clean**

If any active ticket line has a non-empty `invalid=[...]`, stop this plan and create a separate diagnostic inventory or ticket-data migration plan. Do not silently repair `docs/tickets/` inside this candidate-contract slice.

- [ ] **Step 4: Run the migration coverage and construction-site greps**

Run both `rg` commands from `Migration Coverage Map` and paste the hit summaries
into the active implementation notes. The output does not need to be clean at
Task 0; each hit needs an assigned task or an explicit "legacy direct
engine/diagnostic surface intentionally kept" disposition before source edits
start. Do not start Task 1 until `ticket_autonomy.py` and every
`GatewayMutation(...)` construction site have an assigned task.

- [ ] **Step 5: Commit Task 0 only if it changed this plan**

Task 0 normally makes no source changes and should not be committed by itself. If Task 0 is only a preflight run, continue to Task 1.

## Task 1: Add Target Candidate Runtime Shape

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- Test: `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`

- [ ] **Step 1: Write failing runtime shape tests**

In `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`, replace the
helper imports and helper constructors with target-shaped versions. Rewrite or
remove every old-contract test that depends on `EvidenceLink`, `evidence=`,
`blocker_edit`, `refine`, `reprioritize`, `stale_cleanup`,
`target_fingerprint`, `"correction"`, `conflict_reason`, or
`reopen_reason`. Keep only tests for target-contract invariants, mechanical
mode/fanout gates, destructive-action discussion gates, and target engine
dispatch. If conflicting evidence is still represented in source, it must block
before `CandidateMutation` construction or live outside candidate content.

Add these tests near the top of the file after `_decisions()`:

```python
from scripts.ticket_autonomy_runtime import (
    AutonomyIntent,
    CandidateMutation,
    CandidateTarget,
    EngineAction,
    RuntimeDecisionKind,
    candidate_mapping_errors,
    candidate_mutation_from_mapping,
    evaluate_autonomy_intent,
    map_candidate_to_engine,
)


def _target(
    *,
    fields: tuple[str, ...] = ("priority",),
    sections: tuple[str, ...] = (),
) -> CandidateTarget:
    return CandidateTarget(fields=fields, sections=sections)


def _candidate(
    action: str,
    *,
    ticket_id: str | None = "T-20260527-01",
    target: CandidateTarget | None = None,
    proposed_change: dict[str, object] | None = None,
    expected_ticket_fingerprint: str | None = "state-T-20260527-01",
    evidence_summary: str = "Current turn justifies this ticket change.",
) -> CandidateMutation:
    return CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        target=target or _target(),
        proposed_change={"priority": "low"} if proposed_change is None else proposed_change,
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
    )


def _intent(*candidates: CandidateMutation, **context: object) -> AutonomyIntent:
    source_context: dict[str, object] = {}
    source_context.update(context)
    return AutonomyIntent(
        action_kind=candidates[0].action if candidates else "update",
        candidates=tuple(candidates),
        source_context=source_context,
    )
```

Add these RED tests:

```python
def test_candidate_mapping_rejects_unknown_top_level_keys() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": []},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": "Priority changed after this turn.",
            "legacy_reason": "old shape",
        }
    )

    assert errors == ["unknown candidate keys: ['legacy_reason']"]


def test_candidate_mapping_rejects_conflict_reason_as_candidate_content() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": []},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": "Priority changed after this turn.",
            "conflict_reason": "conflicting evidence",
        }
    )

    assert errors == ["unknown candidate keys: ['conflict_reason']"]


def test_candidate_mapping_requires_exact_target_closure() -> None:
    errors = candidate_mapping_errors(
        {
            "action": "update",
            "ticket_id": "T-20260527-01",
            "target": {"fields": ["priority"], "sections": ["Next Action"]},
            "proposed_change": {"priority": "high"},
            "expected_ticket_fingerprint": "state-T-20260527-01",
            "evidence_summary": "Priority changed after this turn.",
        }
    )

    assert errors == [
        "proposed_change keys must exactly match target fields and sections; missing ['Next Action']; extra []"
    ]


def test_create_allows_null_ticket_id_and_null_expected_fingerprint() -> None:
    candidate = candidate_mutation_from_mapping(
        {
            "action": "create",
            "ticket_id": None,
            "target": {"fields": ["title", "priority"], "sections": ["Problem", "Next Action"]},
            "proposed_change": {
                "title": "Add retry to publisher",
                "priority": "high",
                "Problem": "Publisher drops transient broker messages.",
                "Next Action": "Add retry around broker publish.",
            },
            "expected_ticket_fingerprint": None,
            "evidence_summary": "The user asked to track the publisher retry follow-up.",
        }
    )

    assert candidate is not None
    assert candidate.ticket_id is None
    assert candidate.target.fields == ("title", "priority")
    assert candidate.target.sections == ("Problem", "Next Action")
    assert candidate.expected_ticket_fingerprint is None


def test_non_create_requires_expected_ticket_fingerprint() -> None:
    decision = _decisions(
        _candidate("update", expected_ticket_fingerprint=None),
    )[0]

    assert decision.kind == RuntimeDecisionKind.TICKET_UPDATE_BLOCKED
    assert decision.reason == "expected_ticket_fingerprint_required"
    assert decision.mutation_id is None


def test_reopen_uses_evidence_summary_not_reopen_reason() -> None:
    rejected = map_candidate_to_engine(
        _candidate(
            "reopen",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "open", "reopen_reason": "Regression recurred."},
        )
    )
    accepted = map_candidate_to_engine(
        _candidate(
            "reopen",
            target=_target(fields=("status",), sections=()),
            proposed_change={"status": "open"},
            evidence_summary="Regression recurred.",
        )
    )

    assert rejected.state == "policy_blocked"
    assert rejected.reason == "target_closure_failed"
    assert accepted.action == EngineAction.REOPEN
    assert accepted.fields == {"status": "open"}
```

- [ ] **Step 2: Run focused runtime tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py -q
```

Expected: fail with import errors for `CandidateTarget`, `candidate_mapping_errors`, or `candidate_mutation_from_mapping`.

- [ ] **Step 3: Implement the target candidate dataclasses and mapping helpers**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`, replace `EvidenceLink` and `CandidateMutation` with this target-shaped model and helper block:

```python
@dataclass(frozen=True, slots=True)
class CandidateTarget:
    """User-visible fields and sections a candidate intends to change."""

    fields: tuple[str, ...] = ()
    sections: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class CandidateMutation:
    """A proposed target Ticket mutation candidate."""

    ticket_id: str | None
    action: str
    target: CandidateTarget
    proposed_change: Mapping[str, object]
    expected_ticket_fingerprint: str | None
    evidence_summary: str
```

Add these constants and helpers near the candidate model:

```python
_TARGET_FRONTMATTER_FIELDS = frozenset(
    {"title", "status", "priority", "tags", "related_paths", "blocked_by"}
)
_ALLOWED_ACTIONS = frozenset({"create", "update", "done", "wontfix", "reopen", "correct"})
_ALLOWED_CANDIDATE_KEYS = frozenset(
    {
        "action",
        "ticket_id",
        "target",
        "proposed_change",
        "expected_ticket_fingerprint",
        "evidence_summary",
    }
)
_FORBIDDEN_TARGET_SECTIONS = frozenset({"Change History"})


def _string_tuple(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, list | tuple):
        return None
    result: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip() or item.strip() != item:
            return None
        result.append(item)
    return tuple(result)


def _target_from_mapping(value: object) -> CandidateTarget | None:
    if not isinstance(value, Mapping):
        return None
    if set(value) != {"fields", "sections"}:
        return None
    fields = _string_tuple(value.get("fields"))
    sections = _string_tuple(value.get("sections"))
    if fields is None or sections is None:
        return None
    return CandidateTarget(fields=fields, sections=sections)


def _line_shaped(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip()) and "\n" not in value and "\r" not in value


def _target_keys(target: CandidateTarget) -> set[str]:
    return set(target.fields) | set(target.sections)


def _candidate_shape_errors(candidate: CandidateMutation) -> list[str]:
    errors: list[str] = []
    if candidate.action not in _ALLOWED_ACTIONS:
        errors.append(f"action must be one of {sorted(_ALLOWED_ACTIONS)!r}")
    if candidate.action == "create":
        if candidate.ticket_id is not None:
            errors.append("ticket_id must be null for create")
        if candidate.expected_ticket_fingerprint is not None:
            errors.append("expected_ticket_fingerprint must be null for create")
    else:
        if not isinstance(candidate.ticket_id, str) or not candidate.ticket_id:
            errors.append(f"ticket_id is required for {candidate.action}")
        if not isinstance(candidate.expected_ticket_fingerprint, str) or not candidate.expected_ticket_fingerprint:
            errors.append("expected_ticket_fingerprint is required for non-create writes")
    invalid_fields = sorted(field for field in candidate.target.fields if field not in _TARGET_FRONTMATTER_FIELDS)
    if invalid_fields:
        errors.append(f"target.fields contains invalid frontmatter fields: {invalid_fields!r}")
    forbidden_sections = sorted(set(candidate.target.sections) & _FORBIDDEN_TARGET_SECTIONS)
    if forbidden_sections:
        errors.append(f"target.sections cannot name kernel-owned sections: {forbidden_sections!r}")
    expected_keys = _target_keys(candidate.target)
    actual_keys = set(candidate.proposed_change)
    if expected_keys != actual_keys:
        missing = sorted(expected_keys - actual_keys)
        extra = sorted(actual_keys - expected_keys)
        errors.append(
            "proposed_change keys must exactly match target fields and sections; "
            f"missing {missing!r}; extra {extra!r}"
        )
    if not _line_shaped(candidate.evidence_summary):
        errors.append("evidence_summary must be a non-empty single line")
    return errors


def candidate_mapping_errors(item: Mapping[str, object]) -> list[str]:
    unknown = sorted(set(item) - _ALLOWED_CANDIDATE_KEYS)
    if unknown:
        return [f"unknown candidate keys: {unknown!r}"]
    target = _target_from_mapping(item.get("target"))
    if target is None:
        return ["target must contain exactly fields and sections lists"]
    proposed_change = item.get("proposed_change")
    if not isinstance(proposed_change, Mapping):
        return ["proposed_change must be an object"]
    candidate = CandidateMutation(
        ticket_id=item.get("ticket_id") if isinstance(item.get("ticket_id"), str) else None,
        action=item.get("action") if isinstance(item.get("action"), str) else "",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=(
            item.get("expected_ticket_fingerprint")
            if isinstance(item.get("expected_ticket_fingerprint"), str)
            else None
        ),
        evidence_summary=(
            item.get("evidence_summary") if isinstance(item.get("evidence_summary"), str) else ""
        ),
    )
    return _candidate_shape_errors(candidate)


def candidate_mutation_from_mapping(item: Mapping[str, object]) -> CandidateMutation | None:
    if candidate_mapping_errors(item):
        return None
    target = _target_from_mapping(item["target"])
    if target is None:
        return None
    proposed_change = item["proposed_change"]
    if not isinstance(proposed_change, Mapping):
        return None
    return CandidateMutation(
        ticket_id=item.get("ticket_id") if isinstance(item.get("ticket_id"), str) else None,
        action=item["action"] if isinstance(item["action"], str) else "",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=(
            item.get("expected_ticket_fingerprint")
            if isinstance(item.get("expected_ticket_fingerprint"), str)
            else None
        ),
        evidence_summary=item["evidence_summary"] if isinstance(item["evidence_summary"], str) else "",
    )
```

- [ ] **Step 4: Update runtime dispatch to enforce target closure and target actions**

Replace `_requires_discussion`, `_close_fields_are_allowlisted`, and the reopen branch of `map_candidate_to_engine()` with target-shape checks:

```python
def _target_shape_valid(candidate: CandidateMutation) -> bool:
    return not _candidate_shape_errors(candidate)


def _close_target_is_valid(candidate: CandidateMutation, resolution: str) -> bool:
    open_close = candidate.target.fields == ("status",) and candidate.target.sections == ()
    blocked_close_cleanup = (
        candidate.target.fields == ("status", "blocked_by")
        and candidate.target.sections == ("Blocked On",)
        and candidate.proposed_change.get("blocked_by") == []
        and candidate.proposed_change.get("Blocked On") is None
    )
    return (
        (open_close or blocked_close_cleanup)
        and candidate.proposed_change.get("status") == resolution
    )


def map_candidate_to_engine(
    candidate: CandidateMutation,
    *,
    gateway_approved: bool = True,
) -> EngineDispatch:
    """Map one target-shaped candidate to deterministic engine dispatch."""
    if not _target_shape_valid(candidate):
        return EngineDispatch("policy_blocked", None, {}, reason="target_closure_failed")
    fields = {
        key: value
        for key, value in candidate.proposed_change.items()
        if key in candidate.target.fields
    }
    sections = {
        key: value
        for key, value in candidate.proposed_change.items()
        if key in candidate.target.sections
    }
    if candidate.action == "done":
        if not _close_target_is_valid(candidate, "done"):
            return EngineDispatch("policy_blocked", None, {}, reason="close_target_not_allowlisted")
        return EngineDispatch("ok", EngineAction.CLOSE, {"resolution": "done"}, sections=sections)
    if candidate.action == "wontfix":
        if not _close_target_is_valid(candidate, "wontfix"):
            return EngineDispatch("policy_blocked", None, {}, reason="close_target_not_allowlisted")
        return EngineDispatch("ok", EngineAction.CLOSE, {"resolution": "wontfix"}, sections=sections)
    if candidate.action == "reopen":
        if not gateway_approved:
            return EngineDispatch("policy_blocked", None, {}, reason="gateway_required")
        if fields.get("status") not in {"open", "blocked"}:
            return EngineDispatch("policy_blocked", None, {}, reason="reopen_status_required")
        return EngineDispatch("ok", EngineAction.REOPEN, fields, sections=sections)
    if candidate.action == "correct":
        if fields.get("status") in {"done", "wontfix"}:
            if not _close_target_is_valid(candidate, fields["status"]):
                return EngineDispatch("policy_blocked", None, {}, reason="close_target_not_allowlisted")
            return EngineDispatch("ok", EngineAction.CLOSE, {"resolution": fields["status"]}, sections=sections)
        if fields.get("status") in {"open", "blocked"}:
            return EngineDispatch("ok", EngineAction.REOPEN, fields, sections=sections)
        return EngineDispatch("ok", EngineAction.UPDATE, fields, sections=sections)
    if candidate.action == "update":
        return EngineDispatch("ok", EngineAction.UPDATE, fields, sections=sections)
    if candidate.action == "create":
        return EngineDispatch("ok", EngineAction.CREATE, fields, sections=sections)
    return EngineDispatch("policy_blocked", None, {}, reason="unsupported_action")
```

Add a runtime dispatch test for blocked close cleanup:

```python
def test_blocked_close_target_names_blocker_cleanup() -> None:
    dispatch = map_candidate_to_engine(
        _candidate(
            "done",
            target=_target(fields=("status", "blocked_by"), sections=("Blocked On",)),
            proposed_change={"status": "done", "blocked_by": [], "Blocked On": None},
        )
    )

    assert dispatch.action == EngineAction.CLOSE
    assert dispatch.fields == {"resolution": "done"}
    assert dispatch.sections == {"Blocked On": None}


def test_correct_close_rejects_mixed_status_and_metadata_target() -> None:
    dispatch = map_candidate_to_engine(
        _candidate(
            "correct",
            target=_target(fields=("status", "priority"), sections=()),
            proposed_change={"status": "done", "priority": "high"},
        )
    )

    assert dispatch.state == "policy_blocked"
    assert dispatch.reason == "close_target_not_allowlisted"
```

Update `EngineDispatch` to carry target sections:

```python
@dataclass(frozen=True, slots=True)
class EngineDispatch:
    """Gateway-local dispatch projection for a candidate."""

    state: str
    action: EngineAction | None
    fields: dict[str, object]
    reason: str | None = None
    sections: dict[str, object] | None = None
```

Use keyword arguments for `reason=` and `sections=` in every new `EngineDispatch(...)` construction. Do not rely on the fourth positional argument after adding `sections`.

- [ ] **Step 5: Update identity calls to use expected fingerprint and evidence summary**

First update the identity helper in `ticket_mutation_identity.py` using Task 2
Step 4's target-shaped helper. This prevents the new runtime
`_identity_for_candidate()` call from raising `TypeError` while Task 1 is still
in progress.

Replace `_identity_for_candidate()` with:

```python
def _identity_for_candidate(
    *,
    candidate: CandidateMutation,
    thread_id: str,
    turn_id: str,
) -> CandidateMutationIdentity:
    return make_candidate_mutation_identity(
        thread_id=thread_id,
        turn_id=turn_id,
        action=candidate.action,
        ticket_id=candidate.ticket_id,
        target=candidate.target,
        proposed_change=candidate.proposed_change,
        expected_ticket_fingerprint=candidate.expected_ticket_fingerprint,
        evidence_summary=candidate.evidence_summary,
    )
```

Update evaluator branches so non-create writes block with reason
`expected_ticket_fingerprint_required` when
`candidate.expected_ticket_fingerprint is None`. Remove calls to
`_target_fingerprint_for_candidate()`, remove evidence-link floors that classify
evidence kinds, and replace any runtime `if candidate.action == "correction"`
branch with `if candidate.action == "correct"` in this task. Keep mode, fanout,
hard destructive-action, and correction-detail mechanical gates. Conflict facts
must not live on `CandidateMutation`; if current source still needs a conflict
boundary, handle it before target candidate construction or as a short
mechanical pause reason outside candidate content.

- [ ] **Step 6: Run focused runtime and identity tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py -q
```

Expected: the runtime and identity helper tests pass after Step 5. If discovery
tests still fail, continue to Task 2 before committing; Task 1 is not a
standalone green boundary.

- [ ] **Step 7: Do not commit Task 1 by itself**

Continue directly to Task 2. Commit the Task 1 and Task 2 files together after
Task 2 Step 6 passes.

## Task 2: Migrate Candidate Discovery And Commit Runtime Identity

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py`
- Test: `plugins/turbo-mode/ticket/tests/test_mutation_identity.py`
- Test: `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`

- [ ] **Step 1: Write or verify target identity tests**

If Task 1 has not already updated
`plugins/turbo-mode/ticket/tests/test_mutation_identity.py`, replace the payload
tests with:

```python
from scripts.ticket_autonomy_runtime import CandidateTarget
from scripts.ticket_mutation_identity import (
    candidate_mutation_payload,
    make_candidate_mutation_identity,
)


def _identity(
    *,
    expected_ticket_fingerprint: str | None = "ticket-state-a",
    evidence_summary: str = "Priority changed after this turn.",
):
    return make_candidate_mutation_identity(
        thread_id="thread-1",
        turn_id="turn-1",
        ticket_id="T-20260527-01",
        action="update",
        target=CandidateTarget(fields=("priority",), sections=()),
        proposed_change={"priority": "high"},
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
    )


def test_expected_fingerprint_binds_mutation_identity() -> None:
    first = _identity(expected_ticket_fingerprint="ticket-state-a")
    second = _identity(expected_ticket_fingerprint="ticket-state-b")

    assert first.mutation_id != second.mutation_id
    assert first.mutation_fingerprint != second.mutation_fingerprint


def test_evidence_summary_binds_mutation_identity() -> None:
    first = _identity(evidence_summary="Priority changed after this turn.")
    second = _identity(evidence_summary="Priority changed after user review.")

    assert first.mutation_id != second.mutation_id
    assert first.mutation_fingerprint != second.mutation_fingerprint


def test_candidate_payload_uses_target_contract_keys() -> None:
    payload = candidate_mutation_payload(
        ticket_id="T-20260527-01",
        action="update",
        target=CandidateTarget(fields=("priority",), sections=("Next Action",)),
        proposed_change={"priority": "high", "Next Action": "Finish the migration."},
        expected_ticket_fingerprint="ticket-state-a",
        evidence_summary="Priority changed after this turn.",
    )

    assert payload == {
        "ticket_id": "T-20260527-01",
        "action": "update",
        "target": {"fields": ["priority"], "sections": ["Next Action"]},
        "proposed_change": {
            "priority": "high",
            "Next Action": "Finish the migration.",
        },
        "expected_ticket_fingerprint": "ticket-state-a",
        "evidence_summary": "Priority changed after this turn.",
    }
```

- [ ] **Step 2: Write failing discovery tests**

In `plugins/turbo-mode/ticket/tests/test_candidate_discovery.py`, update explicit candidate tests:

```python
def test_discovers_explicit_target_candidate_mutations(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "target": {"fields": ["priority"], "sections": []},
                "proposed_change": {"priority": "high"},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Codex identified a clear priority update.",
            }
        ]
    )

    candidates = discover_candidate_mutations(context, tickets_dir)

    assert len(candidates) == 1
    assert candidates[0].ticket_id == "T-20260527-01"
    assert candidates[0].action == "update"
    assert candidates[0].target.fields == ("priority",)
    assert candidates[0].target.sections == ()
    assert candidates[0].proposed_change == {"priority": "high"}
    assert candidates[0].expected_ticket_fingerprint == "state-T-20260527-01"
    assert candidates[0].evidence_summary == "Codex identified a clear priority update."


def test_structured_candidates_reject_deprecated_ticket_change_scope(
    tmp_path: Path,
) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    context = _context(
        candidate_mutations=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "target": {"fields": ["priority"], "sections": []},
                "proposed_change": {"priority": "high"},
                "expected_ticket_fingerprint": "state-T-20260527-01",
                "evidence_summary": "Priority changed.",
                "ticket_change_scope": "unrelated_backlog",
            },
        ]
    )

    assert discover_candidate_mutations(context, tickets_dir) == ()


def test_vague_and_path_only_signals_do_not_create_write_candidates(tmp_path: Path) -> None:
    tickets_dir = tmp_path / "docs" / "tickets"
    _write_ticket(
        tickets_dir,
        ticket_id="T-20260527-01",
        related_paths=["plugins/turbo-mode/ticket/scripts/ticket_update.py"],
    )
    context = _context(
        touched_files=["plugins/turbo-mode/ticket/scripts/ticket_update.py"],
        possible_candidates=[
            {
                "ticket_id": "T-20260527-01",
                "action": "update",
                "reason": "Maybe later cleanup theme is too broad to apply automatically.",
            }
        ],
    )

    assert discover_candidate_mutations(context, tickets_dir) == ()
```

Add one discovery test that `reprioritize`, `stale_cleanup`, `blocker_edit`, and
`refine` mappings are not accepted as target candidate actions. `stale_cleanup`
may remain read-only output from `ticket_review.py`, but
`discover_candidate_mutations()` must not convert `review_hygiene_findings` into
write candidates in this slice.

- [ ] **Step 3: Run identity and discovery tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py -q
```

Expected: before implementation, fail because identity still accepts
`target_fingerprint` and discovery still emits old flat candidates. If Task 1
already migrated identity, the remaining RED should be in discovery only.

- [ ] **Step 4: Update identity helper**

If Task 1 has not already updated the helper, replace
`candidate_mutation_payload()` and `make_candidate_mutation_identity()` in
`ticket_mutation_identity.py` with:

```python
from typing import Protocol


class CandidateTargetLike(Protocol):
    fields: tuple[str, ...]
    sections: tuple[str, ...]


def candidate_mutation_payload(
    *,
    ticket_id: str | None,
    action: str,
    target: CandidateTargetLike,
    proposed_change: Mapping[str, object],
    expected_ticket_fingerprint: str | None,
    evidence_summary: str,
) -> dict[str, object]:
    """Return the canonical target candidate payload used for mutation identity."""
    return {
        "ticket_id": ticket_id,
        "action": action,
        "target": {
            "fields": list(target.fields),
            "sections": list(target.sections),
        },
        "proposed_change": dict(proposed_change),
        "expected_ticket_fingerprint": expected_ticket_fingerprint,
        "evidence_summary": evidence_summary,
    }


def make_candidate_mutation_identity(
    *,
    thread_id: str,
    turn_id: str,
    ticket_id: str | None,
    action: str,
    target: CandidateTargetLike,
    proposed_change: Mapping[str, object],
    expected_ticket_fingerprint: str | None,
    evidence_summary: str,
) -> CandidateMutationIdentity:
    """Calculate deterministic identity for one target candidate mutation."""
    mutation_fingerprint = sha256_fingerprint(
        candidate_mutation_payload(
            ticket_id=ticket_id,
            action=action,
            target=target,
            proposed_change=proposed_change,
            expected_ticket_fingerprint=expected_ticket_fingerprint,
            evidence_summary=evidence_summary,
        )
    )
    evidence_fingerprint = sha256_fingerprint({"evidence_summary": evidence_summary})
    mutation_id = make_mutation_id(
        schema="codex.ticket.mutation.v2",
        thread_id=thread_id,
        turn_id=turn_id,
        action=action,
        ticket_id=ticket_id,
        mutation_fingerprint=mutation_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
    )
    return CandidateMutationIdentity(
        mutation_id=mutation_id,
        mutation_fingerprint=mutation_fingerprint,
        evidence_fingerprint=evidence_fingerprint,
    )
```

- [ ] **Step 5: Update candidate discovery to accept only explicit target candidates**

In `ticket_candidate_discovery.py`:

- Remove `EvidenceLink` import.
- Import `candidate_mutation_from_mapping`.
- Replace `_candidate_from_mapping()` with:

```python
def _candidate_from_mapping(item: Mapping[str, object]) -> CandidateMutation | None:
    return candidate_mutation_from_mapping(item)
```

Replace `_append_structured_candidates()` with:

```python
def _append_structured_candidates(
    candidates: list[CandidateMutation],
    seen: set[tuple[str | None, str, str]],
    turn_context: Mapping[str, object],
) -> None:
    for key in ("candidate_mutations", "update_candidates", "capture_candidates"):
        for item in turn_context.get(key, []):
            if isinstance(item, Mapping):
                candidate = _candidate_from_mapping(item)
                if candidate is not None:
                    _append_candidate(candidates, seen, candidate)
```

Replace `_append_candidate()` with:

```python
def _append_candidate(
    candidates: list[CandidateMutation],
    seen: set[tuple[str | None, str, str]],
    candidate: CandidateMutation,
) -> None:
    key = (candidate.ticket_id, candidate.action, candidate.evidence_summary)
    if key in seen:
        return
    seen.add(key)
    candidates.append(candidate)
```

Remove `_possible_candidate_from_mapping()`, `_path_refs()`, `_append_path_candidates()`, and the call to `_append_path_candidates()` from `discover_candidate_mutations()`. Keep `_ticket_metadata_paths()` only if another local function still uses it; otherwise remove it too.

- [ ] **Step 6: Run runtime, identity, and discovery tests and verify PASS**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py -q
```

Expected: all three files pass.

- [ ] **Step 7: Commit Tasks 1 and 2 together**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_mutation_identity.py plugins/turbo-mode/ticket/scripts/ticket_candidate_discovery.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py
git commit -m "fix(ticket): migrate target candidate runtime and discovery"
```

Expected: commit succeeds with the atomic runtime, identity, and discovery
files staged. Do not split the runtime changes from the identity helper
signature change.

## Task 3: Project Target Candidates Through Gateway, Entrypoint, And Engine

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`
- Test: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Test: `plugins/turbo-mode/ticket/tests/test_engine_policy.py`

- [ ] **Step 1: Write failing gateway tests for target update and create**

In `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`, update helpers to target shape:

```python
from scripts.ticket_autonomy_runtime import (
    AutonomyDecision,
    AutonomyIntent,
    CandidateMutation,
    CandidateTarget,
    RuntimeDecisionKind,
    evaluate_autonomy_intent,
)


def _target(
    *,
    fields: tuple[str, ...] = ("priority",),
    sections: tuple[str, ...] = (),
) -> CandidateTarget:
    return CandidateTarget(fields=fields, sections=sections)


def _decision_for(
    *,
    ticket_id: str,
    action: str = "update",
    target: CandidateTarget | None = None,
    proposed_change: dict[str, object] | None = None,
    expected_ticket_fingerprint: str = "ticket-fp",
    evidence_summary: str = "Current turn justifies this ticket change.",
    turn_id: str = "turn-1",
):
    candidate = CandidateMutation(
        ticket_id=ticket_id,
        action=action,
        target=target or _target(),
        proposed_change=proposed_change or {"priority": "low"},
        expected_ticket_fingerprint=expected_ticket_fingerprint,
        evidence_summary=evidence_summary,
    )
    return evaluate_autonomy_intent(
        AutonomyIntent(
            action_kind=action,
            candidates=(candidate,),
            source_context={},
        ),
        current_mode="agent_primary",
        thread_id="thread-1",
        turn_id=turn_id,
        now=datetime.now(UTC),
    )[0]
```

Replace `_mutation()` with:

```python
def _mutation(
    tickets_dir: Path,
    ticket_path: Path,
    *,
    ticket_id: str = "T-20260527-01",
    action: str = "update",
    target: CandidateTarget | None = None,
    proposed_change: dict[str, object] | None = None,
) -> GatewayMutation:
    expected = target_fingerprint(ticket_path)
    return GatewayMutation(
        action=action,
        ticket_id=ticket_id,
        target=target or _target(),
        proposed_change=proposed_change or {"priority": "low"},
        tickets_dir=tickets_dir,
        expected_ticket_fingerprint=expected,
        evidence_summary="Current turn justifies this ticket change.",
    )
```

Add this exact section update test:

```python
def test_gateway_applies_exact_target_section_update(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01")
    target = CandidateTarget(fields=("priority",), sections=("Next Action",))
    proposed_change = {
        "priority": "low",
        "Next Action": "Finish the target candidate migration.",
    }
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "ok"
    assert "priority: low" in text
    assert "## Next Action\nFinish the target candidate migration." in text
    assert "| codex | Updated ticket from candidate evidence." in text
```

In `plugins/turbo-mode/ticket/tests/test_autonomy_cli.py` and
`plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`, update
apply-turn candidate fixtures to the target envelope. For existing-ticket writes,
fixtures must include `target`, `proposed_change`, `expected_ticket_fingerprint`
computed with `target_fingerprint(ticket_path)`, and `evidence_summary`. For
create, fixtures must use `ticket_id=None`, `expected_ticket_fingerprint=None`,
and target sections such as `Problem` and `Next Action`. Rewrite old
`evidence`/`reason` fixtures in the same task.

Also rewrite standalone positional `GatewayMutation(...)` constructions in
`test_engine_gateway.py`, including create tests and
`test_gateway_dispatch_maps_ticket_actions_and_rejects_archive_smuggling()`.
That dispatch test currently uses `blocker_edit` and `reopen_reason`; rewrite it
to target-shaped `update`, `reopen`, and close-smuggling cases rather than only
updating shared helpers.

- [ ] **Step 2: Run gateway tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_applies_exact_target_section_update plugins/turbo-mode/ticket/tests/test_autonomy_cli.py::test_apply_turn_summarizes_applied_mutation_before_next_turn plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py::test_agent_primary_apply_turn_applies_update_through_gateway -q
```

Expected: fail because `GatewayMutation` has no `target`, `proposed_change`, or
`expected_ticket_fingerprint` fields and `ticket_autonomy.py` still constructs
the old `fields`/`target_fingerprint` gateway shape.

- [ ] **Step 3: Update GatewayMutation and decision validation**

In `ticket_engine_gateway.py`, replace `GatewayMutation` with:

```python
@dataclass(frozen=True, slots=True)
class GatewayMutation:
    """Gateway-owned target candidate mutation request."""

    action: str
    ticket_id: str | None
    target: CandidateTarget
    proposed_change: Mapping[str, object]
    tickets_dir: Path
    expected_ticket_fingerprint: str | None
    evidence_summary: str
```

Update imports from `ticket_autonomy_runtime.py` to include `CandidateTarget`.

Replace `_mutation_fingerprint()` with:

```python
def _mutation_fingerprint(mutation: GatewayMutation) -> str:
    return sha256_fingerprint(
        {
            "ticket_id": mutation.ticket_id,
            "action": mutation.action,
            "target": {
                "fields": list(mutation.target.fields),
                "sections": list(mutation.target.sections),
            },
            "proposed_change": dict(mutation.proposed_change),
            "expected_ticket_fingerprint": mutation.expected_ticket_fingerprint,
            "evidence_summary": mutation.evidence_summary,
        }
    )
```

In `_decision_error()`, replace field comparison and identity recomputation with:

```python
    if mutation.action == "correct":
        if decision.kind != RuntimeDecisionKind.APPLY_CORRECTION:
            return "decision_mismatch"
    elif decision.kind != RuntimeDecisionKind.APPLY_AUTONOMOUSLY:
        return "autonomous_decision_required"
    if decision.mutation_id is None:
        return "mutation_id_required"
    if decision.candidate.ticket_id != mutation.ticket_id:
        return "ticket_mismatch"
    if decision.candidate.action != mutation.action:
        return "action_mismatch"
    if decision.candidate.target != mutation.target:
        return "target_mismatch"
    if dict(decision.candidate.proposed_change) != dict(mutation.proposed_change):
        return "mutation_fingerprint_mismatch"
    if decision.candidate.expected_ticket_fingerprint != mutation.expected_ticket_fingerprint:
        return "expected_ticket_fingerprint_mismatch"
    if decision.candidate.evidence_summary != mutation.evidence_summary:
        return "evidence_summary_mismatch"
    if mutation.action != "create" and mutation.expected_ticket_fingerprint is None:
        return "expected_ticket_fingerprint_required"
    identity = make_candidate_mutation_identity(
        thread_id=thread_id,
        turn_id=turn_id,
        ticket_id=decision.candidate.ticket_id,
        action=decision.candidate.action,
        target=decision.candidate.target,
        proposed_change=decision.candidate.proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint,
        evidence_summary=decision.candidate.evidence_summary,
    )
    if decision.mutation_id != identity.mutation_id:
        return "mutation_id_mismatch"
    return None
```

The `correct` gate above is intentional: `correct -> reopen` is allowed only
after the runtime selected the user-triggered correction decision kind. Also
remove `_candidate_evidence_payload()`. After this step, `_decision_error` must
not read `candidate.evidence`, `mutation.fields`, or `mutation.target_fingerprint`.

- [ ] **Step 4: Update expected fingerprint validation**

Rename `_validate_target_fingerprint()` to
`_validate_expected_ticket_fingerprint()` and replace target-candidate gateway
references to `target_fingerprint` with `expected_ticket_fingerprint`:

```python
def _validate_expected_ticket_fingerprint(mutation: GatewayMutation) -> EngineResponse | None:
    if mutation.action == "create":
        return None
    if not mutation.ticket_id:
        return EngineResponse(
            state="need_fields",
            message=f"ticket_id required for {mutation.action}",
            error_code="need_fields",
        )
    if mutation.expected_ticket_fingerprint is None:
        return _policy_blocked(f"{mutation.action} requires expected_ticket_fingerprint")
    try:
        ticket = find_ticket_by_id(mutation.tickets_dir, mutation.ticket_id)
    except InvalidTicketState as exc:
        return _invalid_state(
            "Ticket state is not target-normalized.",
            ticket_id=mutation.ticket_id,
            data={"reason": str(exc)},
        )
    if ticket is None:
        return _invalid_state(
            message=f"No ticket matching {mutation.ticket_id}",
            ticket_id=mutation.ticket_id,
            error_code="not_found",
        )
    current = compute_target_fingerprint(Path(ticket.path))
    if current != mutation.expected_ticket_fingerprint:
        return _invalid_state(
            message="Stale fingerprint - ticket was modified since validation.",
            ticket_id=mutation.ticket_id,
            error_code="stale_plan",
        )
    return None
```

Call `_validate_expected_ticket_fingerprint()` from `_apply_autonomous_mutation_locked()`.

Update `_expected_pre_write_fingerprint()` in the same step:

```python
def _expected_pre_write_fingerprint(
    *,
    mutation: GatewayMutation,
    decision: AutonomyDecision,
) -> str | None:
    del decision
    return mutation.expected_ticket_fingerprint
```

Do not defer this helper to Task 5. `_fingerprint_details()` is reached before
dispatch during gateway application, so leaving the old attribute read breaks
the first target gateway write.

- [ ] **Step 5: Update apply-turn gateway construction and fingerprint sourcing**

In `plugins/turbo-mode/ticket/scripts/ticket_autonomy.py`, update
`_run_apply_turn_with_mode()` so the live source entrypoint passes target
candidate content through unchanged:

```python
mutation = GatewayMutation(
    action=decision.candidate.action,
    ticket_id=decision.candidate.ticket_id,
    target=decision.candidate.target,
    proposed_change=dict(decision.candidate.proposed_change),
    tickets_dir=tickets_dir,
    expected_ticket_fingerprint=decision.candidate.expected_ticket_fingerprint,
    evidence_summary=decision.candidate.evidence_summary,
)
```

Remove the normal apply-turn `_ticket_state_fingerprints()` collection and the
`source_context={"ticket_state_fingerprints": fingerprints}` injection used only
to populate candidate identity. Do not replace it with another hidden fingerprint
side channel. Missing or stale expected fingerprints are visible candidate or
gateway failures: runtime blocks missing non-create values, and the gateway
recomputes the current target fingerprint immediately before writing.

- [ ] **Step 6: Add exact target-section support to engine update**

In `ticket_engine_core.py`, add this helper near `_UPDATE_SECTION_HEADINGS`.
Target-section update and create rendering must agree for structured target
sections such as `Acceptance Criteria`; do not serialize structured values with
Python `repr`:

```python
def _render_target_section_value(heading: str, value: Any) -> str | None:
    if value is None:
        return None
    if heading == "Acceptance Criteria":
        return _render_update_section_value("acceptance_criteria", value)
    return str(value)
```

Change `_execute_update()` signature to:

```python
def _execute_update(
    ticket_id: str | None,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    *,
    change_history_entry: ChangeHistoryEntry | None = None,
    target_sections: Mapping[str, object] | None = None,
) -> EngineResponse:
```

After the existing `for key in section_fields:` block, add exact target-section updates:

```python
    for heading, value in (target_sections or {}).items():
        if heading == "Change History" or not validate_target_section_name(heading):
            return EngineResponse(
                state="escalate",
                message=f"Update failed: invalid target section {heading!r}",
                ticket_id=ticket_id,
                error_code="intent_mismatch",
            )
        rendered = _render_target_section_value(heading, value)
        old_rendered = ticket.sections.get(heading, "")
        if rendered is None:
            if heading in ticket.sections:
                changes["sections_changed"].append(heading)
        elif old_rendered.strip() != rendered.strip():
            changes["sections_changed"].append(heading)
        sections[heading] = rendered
```

Build targeted headings from both sources:

```python
    targeted_headings = tuple(_UPDATE_SECTION_HEADINGS[key] for key in section_fields) + tuple(
        (target_sections or {}).keys()
    )
```

Ensure `validate_target_section_name` and `Mapping` are imported in `ticket_engine_core.py`.

- [ ] **Step 7: Project gateway dispatch into engine fields and sections**

In `ticket_engine_gateway.py`, replace `build_engine_dispatch()` with:

```python
def build_engine_dispatch(mutation: GatewayMutation) -> EngineDispatch:
    """Build deterministic engine dispatch for a gateway target mutation."""
    candidate = CandidateMutation(
        ticket_id=mutation.ticket_id,
        action=mutation.action,
        target=mutation.target,
        proposed_change=dict(mutation.proposed_change),
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint,
        evidence_summary=mutation.evidence_summary,
    )
    return map_candidate_to_engine(candidate)
```

Update `_execute_dispatch()` calls to pass target sections:

```python
target_sections = dispatch.sections or {}
```

For update:

```python
        return _execute_update(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
            target_sections=target_sections,
        )
```

For close, extend `_execute_close()` with a keyword-only `target_sections`
argument and pass the dispatch sections:

```python
        return _execute_close(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
            target_sections=target_sections,
        )
```

Inside `_execute_close()`, accept only the target cleanup section generated by
the target candidate contract:

```python
    if target_sections:
        if set(target_sections) != {"Blocked On"} or target_sections["Blocked On"] is not None:
            return EngineResponse(
                state="escalate",
                message="Close failed: invalid target section cleanup",
                ticket_id=ticket_id,
                error_code="intent_mismatch",
            )
```

Keep the existing engine-owned blocked-ticket cleanup. This check prevents the
gateway from computing close sections and dropping them silently.

For create, use one shared helper for create dispatch and create dedup. This
prevents `_validate_autonomous_create_dedup()` from reading the removed
`mutation.fields` attribute and prevents create dispatch from using a different
section map than dedup:

```python
def _create_fields_for_engine(mutation: GatewayMutation) -> tuple[dict[str, object], str | None]:
    fields = {
        key: value
        for key, value in mutation.proposed_change.items()
        if key in mutation.target.fields
    }
    section_map = {
        "Problem": "problem",
        "Next Action": "next_action",
        "Blocked On": "blocked_on",
        "Acceptance Criteria": "acceptance_criteria",
    }
    for heading in mutation.target.sections:
        engine_key = section_map.get(heading)
        if engine_key is None:
            return {}, f"Unsupported create target section: {heading}"
        fields[engine_key] = mutation.proposed_change[heading]
    return fields, None
```

Both `_validate_autonomous_create_dedup()` and the create branch of
`_execute_dispatch()` must call this helper. If the helper returns an error,
return `_policy_blocked(error)`.

Add or update a gateway create test that exercises target sections so this does
not wait until production create flow.

For reopen, pass target sections in Task 4 after reopen support lands.

- [ ] **Step 8: Run gateway and source-entrypoint tests and verify PASS**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_applies_exact_target_section_update plugins/turbo-mode/ticket/tests/test_autonomy_cli.py::test_apply_turn_summarizes_applied_mutation_before_next_turn plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py::test_agent_primary_apply_turn_applies_update_through_gateway -q
```

Expected: the gateway section update test and the two apply-turn source
entrypoint tests pass.

- [ ] **Step 9: Commit Task 3**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_engine_policy.py
git commit -m "fix(ticket): project target candidates through gateway"
```

Expected: commit succeeds with gateway, engine, source-entrypoint, and directly
affected tests staged. Do not update source-availability docs in this commit.

## Task 4: Migrate Reopen And Blocked Cleanup Semantics

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_change_history.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_validate.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Test: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Test: `plugins/turbo-mode/ticket/tests/test_engine_policy.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- Test: `plugins/turbo-mode/ticket/tests/test_execute.py`
- Test: `plugins/turbo-mode/ticket/tests/test_integration.py`
- Test: `plugins/turbo-mode/ticket/tests/test_engine_runner.py`
- Test: `plugins/turbo-mode/ticket/tests/test_review_findings.py`
- Test: `plugins/turbo-mode/ticket/tests/test_change_history.py`

- [ ] **Step 1: Write failing reopen gateway tests**

In `test_engine_gateway.py`, add:

```python
def test_gateway_reopens_terminal_ticket_to_blocked_with_visible_blocker_shape(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    blocker = make_ticket(tmp_tickets, "blocker.md", id="T-20260527-02", status="open")
    assert blocker.exists()
    ticket_path = make_ticket(tmp_tickets, "done.md", id="T-20260527-01", status="done")
    target = CandidateTarget(fields=("status", "blocked_by"), sections=("Blocked On",))
    proposed_change = {
        "status": "blocked",
        "blocked_by": ["T-20260527-02"],
        "Blocked On": "Waiting for T-20260527-02.",
    }
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        action="reopen",
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        action="reopen",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
        evidence_summary="The closed work is still blocked by T-20260527-02.",
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "ok"
    assert "status: blocked" in text
    assert "blocked_by:\n- T-20260527-02" in text
    assert "## Blocked On\nWaiting for T-20260527-02." in text
    assert "## Reopen History" not in text
    assert "| codex | Reopened ticket from candidate evidence." in text
```

Add the open reopen variant:

```python
def test_gateway_reopens_terminal_ticket_to_open_without_reopen_reason(
    tmp_tickets: Path,
) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "done.md", id="T-20260527-01", status="done")
    target = CandidateTarget(fields=("status",), sections=())
    proposed_change = {"status": "open"}
    mutation = _mutation(
        tmp_tickets,
        ticket_path,
        action="reopen",
        target=target,
        proposed_change=proposed_change,
    )
    decision = _decision_for(
        ticket_id="T-20260527-01",
        action="reopen",
        target=target,
        proposed_change=proposed_change,
        expected_ticket_fingerprint=mutation.expected_ticket_fingerprint or "",
        evidence_summary="The user asked to reopen the work.",
    )

    response = apply_autonomous_mutation(
        project_root=project_root,
        thread_id="thread-1",
        turn_id="turn-1",
        repo_context=_repo_context(project_root),
        mutation=mutation,
        decision=decision,
        pending_summary=PendingSummaryStore(project_root),
    )

    text = ticket_path.read_text(encoding="utf-8")
    assert response.state == "ok"
    assert "status: open" in text
    assert "## Reopen History" not in text
    assert "reopen_reason" not in text
```

Rewrite or remove existing tests in `test_execute.py`, `test_integration.py`,
`test_engine_runner.py`, `test_review_findings.py`, and
`test_change_history.py` that preserve `reopen_reason` or `Reopen History` as
normal target reopen behavior. Keep tests that verify historical files can still
be parsed or repaired only when they are explicitly diagnostic/migration tests,
not ordinary `reopen` contract tests.

- [ ] **Step 2: Run reopen gateway tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_reopens_terminal_ticket_to_blocked_with_visible_blocker_shape plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_reopens_terminal_ticket_to_open_without_reopen_reason -q
```

Expected: fail because `_execute_reopen()` still requires `reopen_reason` and only writes `status: open`.

- [ ] **Step 3: Remove reopen_reason from target field validation**

In `ticket_validate.py`, remove `"reopen_reason"` from the string-field validation tuple. Keep `reopen_reason` out of normal target writes; the reason is now carried by `evidence_summary` and rendered through generated `Change History`.

Add or update a focused assertion in `test_engine_policy.py`:

```python
def test_validate_fields_rejects_reopen_reason_as_target_write_field() -> None:
    assert "reopen_reason is not a target write field" in validate_fields(
        {"reopen_reason": "Regression recurred."}
    )
```

If `validate_fields()` does not yet reject unknown non-target keys directly, add `reopen_reason` to `DEPRECATED_WRITE_FIELDS` in `ticket_validate.py`.

In `ticket_change_history.py`, remove any helper behavior that inserts or
special-cases `## Reopen History` for ordinary target reopen writes. If
historical `Reopen History` placement helpers remain for migration diagnostics,
label them diagnostic-only and keep their tests out of the normal reopen
contract.

- [ ] **Step 4: Update reopen policy to target status shape**

In `ticket_engine_core.py`, replace `_evaluate_reopen_policy()` with:

```python
def _evaluate_reopen_policy(
    ticket_id: str,
    ticket: ParsedTicket,
    fields: dict[str, Any],
    tickets_dir: Path,
) -> EngineResponse | None:
    """Return the reopen-policy rejection response, or None when reopen may write."""
    target_status = fields.get("status")
    if target_status not in {"open", "blocked"}:
        return EngineResponse(
            state="need_fields",
            message="status must be open or blocked for reopen",
            error_code="need_fields",
            ticket_id=ticket_id,
            data={"missing_fields": ["status"]},
        )

    legacy_block = _check_legacy_gate(ticket)
    if legacy_block is not None:
        return legacy_block

    validation_errors = validate_fields(fields)
    if validation_errors:
        return EngineResponse(
            state="need_fields",
            message=f"Field validation failed: {'; '.join(validation_errors)}",
            error_code="need_fields",
            ticket_id=ticket_id,
            data={"validation_errors": validation_errors},
        )

    if ticket.status not in _TERMINAL_STATUSES:
        return EngineResponse(
            state="invalid_transition",
            message=f"Cannot reopen ticket with status {ticket.status} (must be done or wontfix)",
            ticket_id=ticket_id,
            error_code="invalid_transition",
            data=_transition_policy_data(
                ticket.status,
                target_status,
                valid_recovery_statuses=[],
                requires_reopen=False,
            ),
        )

    if target_status == "blocked":
        blocked_on = fields.get("blocked_on")
        if not isinstance(blocked_on, str) or not blocked_on.strip():
            return EngineResponse(
                state="need_fields",
                message="Transition to 'blocked' requires blocked_on",
                error_code="blocked_on_required",
                ticket_id=ticket_id,
                data={"missing": ["blocked_on"]},
            )

    message, precondition_code, precondition_detail = _check_transition_preconditions_with_detail(
        ticket.status,
        target_status,
        ticket,
        tickets_dir,
        fields=fields,
    )
    if message is not None:
        return EngineResponse(
            state="invalid_transition",
            message=message,
            ticket_id=ticket_id,
            error_code=precondition_code,
            data=_transition_policy_data(
                ticket.status,
                target_status,
                valid_recovery_statuses=[target_status],
                requires_reopen=True,
                precondition_code=precondition_code,
                precondition_detail=precondition_detail,
            ),
        )

    return None
```

Update `_is_valid_transition()` reopen branch to:

```python
    if action == "reopen":
        return current in ("done", "wontfix") and target in {"open", "blocked"}
```

- [ ] **Step 5: Update reopen execution to write target status and sections**

Change `_execute_reopen()` signature to include target sections:

```python
def _execute_reopen(
    ticket_id: str | None,
    fields: dict[str, Any],
    session_id: str,
    request_origin: str,
    tickets_dir: Path,
    *,
    change_history_entry: ChangeHistoryEntry | None = None,
    target_sections: Mapping[str, object] | None = None,
) -> EngineResponse:
```

Replace the old `reopen_reason` body with:

```python
    target_status = fields.get("status")
    if target_status not in {"open", "blocked"}:
        return EngineResponse(
            state="need_fields",
            message="status must be open or blocked for reopen",
            error_code="need_fields",
        )

    ticket, invalid_state = _find_ticket_by_id_for_engine(tickets_dir, ticket_id)
    if invalid_state is not None:
        return invalid_state
    if ticket is None:
        return EngineResponse(
            state="not_found",
            message=f"No ticket matching {ticket_id}",
            ticket_id=ticket_id,
            error_code="not_found",
        )

    policy_fields = dict(fields)
    if target_sections and "Blocked On" in target_sections:
        policy_fields["blocked_on"] = target_sections["Blocked On"]
    policy_error = _evaluate_reopen_policy(ticket_id, ticket, policy_fields, tickets_dir)
    if policy_error is not None:
        return policy_error

    ticket_path = Path(ticket.path)
    original_text = ticket_path.read_text(encoding="utf-8")
    data = dict(ticket.frontmatter)
    sections = dict(ticket.sections)
    old_status = data.get("status", "")
    data["status"] = target_status
    if "blocked_by" in fields:
        data["blocked_by"] = fields["blocked_by"]
    if target_status == "open":
        data["blocked_by"] = []
        sections["Blocked On"] = None
    for heading, value in (target_sections or {}).items():
        if heading == "Change History" or not validate_target_section_name(heading):
            return EngineResponse(
                state="escalate",
                message=f"Reopen failed: invalid target section {heading!r}",
                ticket_id=ticket_id,
                error_code="intent_mismatch",
            )
        sections[heading] = _render_target_section_value(heading, value)
    targeted_headings = tuple((target_sections or {}).keys())
    if target_status == "open":
        targeted_headings = tuple(sorted(set(targeted_headings) | {"Blocked On"}))
    new_text = _render_target_ticket_text(
        data,
        sections,
        original_text=original_text,
        targeted_headings=targeted_headings,
    )
    if change_history_entry is not None:
        new_text = append_change_history_entry(new_text, change_history_entry)
```

Keep the existing invalid-render and write response pattern, but return changes for target status:

```python
    return EngineResponse(
        state="ok",
        message=f"Reopened {ticket_id} as {target_status}",
        ticket_id=ticket_id,
        data={
            "ticket_path": str(ticket_path),
            "changes": {"status": [old_status, target_status]},
        },
    )
```

- [ ] **Step 6: Pass target sections to reopen dispatch**

In `ticket_engine_gateway.py`, update the reopen branch in `_execute_dispatch()`:

```python
    if dispatch.action == EngineAction.REOPEN:
        return _execute_reopen(
            mutation.ticket_id,
            dict(dispatch.fields),
            thread_id,
            "agent",
            mutation.tickets_dir,
            change_history_entry=change_history_entry,
            target_sections=target_sections,
        )
```

- [ ] **Step 7: Run reopen tests and verify PASS**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_reopens_terminal_ticket_to_blocked_with_visible_blocker_shape plugins/turbo-mode/ticket/tests/test_engine_gateway.py::test_gateway_reopens_terminal_ticket_to_open_without_reopen_reason plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py::test_reopen_uses_evidence_summary_not_reopen_reason plugins/turbo-mode/ticket/tests/test_engine_policy.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_integration.py plugins/turbo-mode/ticket/tests/test_engine_runner.py plugins/turbo-mode/ticket/tests/test_review_findings.py plugins/turbo-mode/ticket/tests/test_change_history.py -q
```

Expected: all listed reopen and change-history tests pass. Any failure still
asserting `reopen_reason` or `Reopen History` as normal target behavior belongs
to this task, not to Task 7.

- [ ] **Step 8: Commit Task 4**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_engine_core.py plugins/turbo-mode/ticket/scripts/ticket_change_history.py plugins/turbo-mode/ticket/scripts/ticket_validate.py plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_engine_policy.py plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_integration.py plugins/turbo-mode/ticket/tests/test_engine_runner.py plugins/turbo-mode/ticket/tests/test_review_findings.py plugins/turbo-mode/ticket/tests/test_change_history.py
git commit -m "fix(ticket): migrate target reopen semantics"
```

Expected: commit succeeds with reopen semantics, change-history cleanup, and
the reopen-related tests only.

## Task 5: Migrate Correction And Recovery Facts

**Files:**
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py`
- Test: `plugins/turbo-mode/ticket/tests/test_engine_gateway.py`
- Test: `plugins/turbo-mode/ticket/tests/test_turn_batch.py`
- Test: `plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py`

- [ ] **Step 1: Write failing target correction tests**

In `test_autonomy_corrections.py`, update correction candidates to target shape:

```python
candidate = CandidateMutation(
    ticket_id="T-20260527-01",
    action="correct",
    target=CandidateTarget(fields=("priority",), sections=()),
    proposed_change={"priority": "high"},
    expected_ticket_fingerprint=target_fingerprint(ticket_path),
    evidence_summary="Prior mutation set priority too low.",
)
```

Add this assertion to `test_user_triggered_update_correction_applies_without_new_approval()`:

```python
assert "rewrite_change_history" not in events[0]["details"]
assert "decision" not in events[0]["details"]
assert "current_mode" not in events[0]["details"]
assert "evidence_kind" not in events[0]["details"]
assert events[0]["details"]["target"] == {"fields": ["priority"], "sections": []}
assert events[0]["details"]["evidence_summary"] == "Prior mutation set priority too low."
```

Add this test:

```python
def test_correction_cannot_target_change_history(tmp_tickets: Path) -> None:
    project_root = tmp_tickets.parent.parent
    _declare_ignored_workspace(project_root)
    ticket_path = make_ticket(tmp_tickets, "one.md", id="T-20260527-01", priority="low")
    candidate = CandidateMutation(
        ticket_id="T-20260527-01",
        action="correct",
        target=CandidateTarget(fields=(), sections=("Change History",)),
        proposed_change={"Change History": "caller-owned rewrite"},
        expected_ticket_fingerprint=target_fingerprint(ticket_path),
        evidence_summary="Attempted unsafe correction.",
    )

    decision = _correction_decision(candidate, ticket_path=ticket_path)

    assert decision.kind == RuntimeDecisionKind.REQUIRE_USER_DISCUSSION
    assert decision.reason == "target_closure_failed"
```

- [ ] **Step 2: Run correction tests and verify RED**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py -q
```

Expected: fail because correction helpers, integration fixtures, gateway recovery
details, or turn-batch validation still use the old `correction` action, flat
fields, or persisted decision/current-mode/evidence-kind details.

- [ ] **Step 3: Normalize correction action and unsafe correction checks**

In `ticket_autonomy_runtime.py`:

- Confirm Task 1 already replaced runtime action string `"correction"` with
  target action `"correct"` across runtime checks. Any remaining runtime hit is
  in scope here only if Task 1 missed it; do not leave the old action literal in
  runtime after this task.
- Keep `RuntimeDecisionKind.APPLY_CORRECTION` as the decision kind.
- Remove old target-candidate action literals from runtime action groups:
  `reprioritize`, `stale_cleanup`, `blocker_edit`, and `refine` are not target
  candidate actions. Any retained update behavior must flow through `action:
  "update"` plus explicit target fields or sections.
- Replace the correction branch shape check so it rejects kernel-owned sections through `_candidate_shape_errors()` rather than old proposed-change control keys:

```python
shape_errors = _candidate_shape_errors(candidate)
if shape_errors:
    decisions.append(
        _decision(
            candidate,
            RuntimeDecisionKind.REQUIRE_USER_DISCUSSION,
            reason="target_closure_failed",
            pending_summary_status="discussion_required",
        )
    )
    continue
```

Replace `_correction_detail_available()` with:

```python
def _correction_detail_available(candidate: CandidateMutation) -> bool:
    return _line_shaped(candidate.evidence_summary)
```

In `ticket_engine_gateway.py`:

- Replace the `_decision_error()` correction guard so it accepts target action
  `"correct"` while still requiring `RuntimeDecisionKind.APPLY_CORRECTION`.
- Update `_change_history_reason()` so `action == "correct"` returns the
  generated correction reason. No target candidate path should keep the old
  `"correction"` action literal.

In `ticket_turn_batch.py`, separate retained candidate-action validation from
maintenance event validation:

- Add `_TARGET_MUTATION_ACTIONS = frozenset({"create", "update", "done", "wontfix", "reopen", "correct"})`.
- Use `_TARGET_MUTATION_ACTIONS` for new `mutation_attempt` and `ticket_write`
  candidate action facts.
- Keep `summarize`, `compact`, and `pause_automation` valid only for their
  event-specific maintenance records if current operation-log validation still
  needs them. Prefer an `_EVENT_ACTIONS_BY_TYPE` map over one flat `_ACTIONS`
  set if that makes the boundary executable.
- Do not keep `reprioritize`, `stale_cleanup`, `blocker_edit`, `refine`,
  `archive`, `delete`, `history_repair`, or `"correction"` as valid new
  target candidate actions.
- Keep historical compaction status names only when they describe existing
  stored correction detail rather than new candidate action input.
  `ticket_review.py` may still emit `stale_cleanup` as read-only review-hygiene
  output, but candidate discovery must not accept it as a write candidate.

Add turn-batch tests proving both sides of the split:

- a new `mutation_attempt` or `ticket_write` event rejects
  `reprioritize`, `stale_cleanup`, `blocker_edit`, `refine`, `archive`,
  `delete`, `history_repair`, `summarize`, `compact`, `pause_automation`, and
  `"correction"` as candidate action values;
- existing maintenance event types still accept their own mechanical actions
  where those events are intentionally retained.

- [ ] **Step 4: Record bounded target recovery facts**

In `ticket_engine_gateway.py`, update `_fingerprint_details()` and the
`mutation_attempt` event details so target candidate mutation attempt events
include only bounded target facts. Replace the whole `details={...}` block that
currently adds `current_mode` and `evidence_kind`; do not hide those fields
outside `_fingerprint_details()`.

```python
def _fingerprint_details(
    *,
    mutation: GatewayMutation,
) -> dict[str, object]:
    return {
        "target": {
            "fields": list(mutation.target.fields),
            "sections": list(mutation.target.sections),
        },
        "expected_pre_write_fingerprint": mutation.expected_ticket_fingerprint,
        "evidence_summary": mutation.evidence_summary,
    }
```

Use the helper as the full details value:

```python
details=_fingerprint_details(mutation=mutation)
```

Do not add confidence scores, evidence-kind lists, current-mode labels,
runtime decision kinds, approval states, Handoff metadata, private workflow
stages, or copied ticket content.

- [ ] **Step 5: Run correction and gateway recovery tests and verify PASS**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py -q
```

Expected: all four files pass. Any failure still using `"correction"` as a
target candidate action, narrowing maintenance event validation into candidate
action validation, or expecting `decision`, `evidence_kind`, or `current_mode`
mutation attempt details belongs to this task.

- [ ] **Step 6: Commit Task 5**

Run:

```bash
git add plugins/turbo-mode/ticket/scripts/ticket_autonomy_runtime.py plugins/turbo-mode/ticket/scripts/ticket_engine_gateway.py plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py
git commit -m "fix(ticket): migrate correction recovery facts"
```

Expected: commit succeeds with correction/recovery files and directly affected
operation-log tests only.

## Task 6: Update Source Docs, Skills, And Contract Availability

**Files:**
- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md`
- Test: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

Precondition: do not start Task 6 until the Task 3 source-entrypoint tests and
Task 5 correction/integration tests pass. The docs must not claim that source
exposes a target candidate mutation path while `ticket_autonomy.py` still
constructs old gateway mutations.

- [ ] **Step 1: Write failing docs-contract tests**

In `test_docs_contract.py`, add a source-availability contract test:

```python
def test_ticket_write_docs_no_longer_claim_source_entrypoint_missing() -> None:
    paths = [
        Path("plugins/turbo-mode/ticket/README.md"),
        Path("plugins/turbo-mode/ticket/HANDBOOK.md"),
        Path("plugins/turbo-mode/ticket/references/ticket-contract.md"),
        Path("plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md"),
        Path("plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md"),
    ]
    forbidden = (
        "temporarily unavailable until source exposes",
        "source exposes a live target-candidate entrypoint",
        "until Ticket exposes and documents a live source entrypoint",
    )
    for path in paths:
        text = path.read_text(encoding="utf-8")
        for phrase in forbidden:
            assert phrase not in text, f"{path} still contains {phrase!r}"
```

- [ ] **Step 2: Run docs-contract test and verify RED**

Run after the Task 6 precondition is satisfied:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_docs_contract.py::test_ticket_write_docs_no_longer_claim_source_entrypoint_missing -q
```

Expected: fail on README/HANDBOOK/skills availability wording.

- [ ] **Step 3: Update source docs availability language**

Replace "temporarily unavailable until source exposes a live target-candidate entrypoint" language with source-truthful wording:

```text
Source now exposes the target candidate mutation path. Installed-runtime availability still requires a separate cache refresh and runtime inventory before claiming the active Codex plugin can perform writes.
```

Use this boundary in README/HANDBOOK/contract:

```text
Capture and update skills may describe and route target candidates through the source entrypoint when the installed Ticket runtime matches this source. Do not claim installed write availability from source files alone.
```

In `capture-ticket/SKILL.md` and `update-ticket/SKILL.md`, replace hard "temporarily unavailable" stop text with:

```text
Before mutating, confirm the installed Ticket runtime exposes the target candidate mutation path. If runtime proof is unavailable in the current turn, summarize the intended target candidate and say runtime write proof is missing. Do not write through legacy flat candidate paths.
```

Do not add cache refresh commands to skill procedures.

- [ ] **Step 4: Run docs-contract test and verify PASS**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_docs_contract.py::test_ticket_write_docs_no_longer_claim_source_entrypoint_missing -q
```

Expected: docs-contract test passes, and the Task 3/Task 5 source-entrypoint
tests are still passing in the current checkout.

- [ ] **Step 5: Commit Task 6**

Run:

```bash
git add plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/references/ticket-contract.md plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md plugins/turbo-mode/ticket/tests/test_docs_contract.py
git commit -m "docs(ticket): update target candidate write availability"
```

Expected: commit succeeds with docs/skill availability files only.

## Task 7: Final Source Verification

**Files:**
- Verify all changed source, tests, docs, and skills.

- [ ] **Step 1: Run focused candidate-contract test set**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py plugins/turbo-mode/ticket/tests/test_mutation_identity.py plugins/turbo-mode/ticket/tests/test_candidate_discovery.py plugins/turbo-mode/ticket/tests/test_engine_gateway.py plugins/turbo-mode/ticket/tests/test_autonomy_corrections.py plugins/turbo-mode/ticket/tests/test_engine_policy.py plugins/turbo-mode/ticket/tests/test_execute.py plugins/turbo-mode/ticket/tests/test_integration.py plugins/turbo-mode/ticket/tests/test_engine_runner.py plugins/turbo-mode/ticket/tests/test_review_findings.py plugins/turbo-mode/ticket/tests/test_change_history.py plugins/turbo-mode/ticket/tests/test_turn_batch.py plugins/turbo-mode/ticket/tests/test_autonomy_integration_v1.py plugins/turbo-mode/ticket/tests/test_autonomy_cli.py plugins/turbo-mode/ticket/tests/test_docs_contract.py -q
```

Expected: all selected tests pass.

- [ ] **Step 2: Run target-contract residue and construction-site checks**

Run:

```bash
rg -n "EvidenceLink|\.evidence|\"correction\"|conflict_reason|reopen_reason|Reopen History|evidence_kind|current_mode|\"decision\"|decision\.kind|RuntimeDecisionKind|mutation\.fields|target_fingerprint|reprioritize|stale_cleanup|blocker_edit|refine|archive|delete|history_repair|summarize|compact|pause_automation|codex\.ticket\.mutation\.v1" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
rg -n "GatewayMutation\(|CandidateMutation\(" plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests
```

Expected: every remaining hit is explicitly one of:

- legacy direct engine plan/execute syntax intentionally outside the target
  candidate path;
- calls to `scripts.ticket_dedup.target_fingerprint` used only to compute a
  current ticket fingerprint for `expected_ticket_fingerprint`;
- runtime mode inputs or tests that are not persisted mutation-attempt details;
- internal `RuntimeDecisionKind` branch logic, including
  `RuntimeDecisionKind.APPLY_CORRECTION`, that is not persisted in
  mutation-attempt details or result data;
- historical migration/diagnostic test data labeled as such;
- non-candidate correction-detail storage vocabulary retained for recent
  correction recovery;
- read-only review-hygiene output such as `ticket_review.py` `stale_cleanup`
  that candidate discovery does not accept as a write candidate;
- maintenance event validation for `summarize`, `compact`, or
  `pause_automation`, only where the code validates those event types rather
  than a target candidate action fact;
- low-level `make_mutation_id()` tests that use `codex.ticket.mutation.v1` as
  arbitrary schema input and are not candidate-contract fixtures;
- target-shaped `CandidateMutation(...)` or `GatewayMutation(...)` constructions
  that include the new target envelope fields;
- user-facing text explaining removed/deprecated input.

Any remaining old-shaped target candidate runtime, gateway, discovery, identity,
source-entrypoint, operation-log, or normal reopen/correct test hit must be
fixed before continuing. In particular, no accepted target candidate mapping may
mention `conflict_reason`, no `mutation_attempt` details may persist
`"decision"` or a runtime decision kind, and no new mutation event may validate
maintenance action names as candidate actions.

- [ ] **Step 3: Run full Ticket suite**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected: full Ticket suite passes. If failures appear outside the focused
candidate-contract set, inspect before deciding disposition. Failures involving
the coverage-map legacy surfaces are in scope for this migration unless the
residue check already classified them as intentionally retained.

- [ ] **Step 4: Run lint and diff checks**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket
git diff --check
```

Expected: both commands pass.

- [ ] **Step 5: Check for generated residue**

Run:

```bash
git status --short --ignored
```

Expected: normal status shows only intended committed or staged source changes before commit. Ignored caches such as `.pytest_cache`, `.ruff_cache`, `.venv`, `.codex/handoffs/`, and `.codex/plugin-runtimes/` may exist; do not stage ignored runtime or handoff artifacts.

- [ ] **Step 6: Commit final verification-only doc adjustments if needed**

If verification required only wording or test-selector corrections, commit them:

```bash
git add docs/superpowers/plans/2026-06-05-ticket-candidate-contract-migration.md
git commit -m "docs(ticket): close candidate contract migration plan"
```

Expected: commit succeeds only if this plan changed during execution. If no plan changes occurred, do not create an empty commit.

## Acceptance Criteria

- `CandidateMutation` uses only the target envelope fields: `action`,
  `ticket_id`, `target`, `proposed_change`, `expected_ticket_fingerprint`, and
  `evidence_summary`.
- Unknown top-level candidate keys are rejected before mutation evaluation.
- `conflict_reason` is not accepted as target candidate input and does not enter
  target candidate identity, gateway validation, result data, or operation-log
  details.
- `target` has exactly `fields` and `sections`; `proposed_change` keys exactly equal their union.
- Non-create writes require `expected_ticket_fingerprint`; create requires it to be `None`.
- Mutation identity includes `target`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`.
- Discovery emits only explicit target-shaped candidates and does not turn vague/path-only signals into write candidates.
- `ticket_autonomy.py` constructs target-shaped `GatewayMutation` values from
  `decision.candidate` and does not repopulate expected fingerprints through
  `source_context`.
- Gateway mutation validation compares target, proposed change, expected fingerprint, evidence summary, and mutation identity.
- Gateway validation preserves `mutation_id_required`, `ticket_mismatch`, and
  `mutation_id_mismatch` guards.
- Exact target sections can be updated or removed without caller-owned `Change History` rewrites.
- `reopen` uses target `status` plus `evidence_summary`; `reopen_reason` is rejected as normal target write input.
- `reopen -> blocked` writes valid `Blocked On` and `blocked_by` shape.
- Blocked `done`/`wontfix` candidates name `status`, `blocked_by`, and
  `Blocked On` cleanup, and the gateway does not silently drop the named
  cleanup section.
- `correct` is an ordinary target-shaped mutation and appends generated correction history.
- Operation-log details retain only bounded recovery facts and do not add
  semantic ranking, current-mode labels, evidence taxonomies, runtime decision
  kinds, approval state, or private workflow stages.
- `ticket_turn_batch.py` validates the six target actions for retained
  candidate action facts and keeps maintenance event actions only in
  event-specific validation.
- The final residue check has no unexplained target-candidate hits for old
  identity, evidence, action, correction, reopen, or gateway field names.
- The final construction-site check has no old-shaped `CandidateMutation(...)`
  or `GatewayMutation(...)` calls in scripts or tests.
- Source docs and skills stop claiming source entrypoint absence after the source entrypoint lands, while preserving the source-vs-installed-runtime proof boundary.
- Focused candidate-contract tests, full Ticket suite, ruff, and `git diff --check` pass.

## Out Of Scope

- Installed runtime refresh, cache mutation, or app-server runtime proof.
- `reconcile_board` discovery ordering, caps, overflow, broad ticket search, or wrapper implementation.
- Broad `docs/tickets/` normalization. The current inventory is clean; any future dirty active ticket state gets a separate diagnostic/data migration lane.
- Historical spec example cleanup for old illustrative IDs unless a docs-contract test proves those examples now mislead current behavior.
- Private operation-log redesign beyond candidate identity, expected pre-write fingerprint, post-write fingerprint, evidence summary, target fields/sections, and write/summary completion facts.

## Execution Handoff

Plan complete when this file is committed or intentionally left unstaged for review. Implementation should use either:

1. Subagent-Driven (recommended) - use one focused worker per task with review between task commits.
2. Inline Execution - execute tasks in this session using `superpowers:executing-plans`, with checkpoints after each task commit.

Do not start source edits from this plan without a fresh `git status --short --branch` and `git rev-parse --short HEAD` check.

`Expected:` blocks describe the observable state after completing the named
task. RED expectations must be reproduced before the corresponding GREEN patch.
GREEN expectations must be backed by command output from the current checkout;
do not carry aspirational expected output forward after live code contradicts
it.

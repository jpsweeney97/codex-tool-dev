# Ticket Authority Kernel Slice 1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a source-local, passive Ticket authority kernel that freezes current wrapper-facing mutation semantics without changing runtime behavior, installed cache state, hook behavior, storage, or direct-engine execution.

**Architecture:** Slice 1 creates a pure library module, `plugins/turbo-mode/ticket/scripts/ticket_authority.py`, plus contract prose and permanent tests. The kernel exposes only three Python APIs: `classify_mutation()`, `plan_manifest_lanes()`, and `export_policy_manifest()`. It is registry-backed, source-anchored, grant-free, provenance-free, and not imported by existing Ticket runtime entrypoints.

**Tech Stack:** Python 3.11+, frozen dataclasses, `StrEnum`, typed registry value objects, pytest, AST import guards, Markdown contract docs, bytecode-safe `uv run` verification.

---

## Decision Freeze

These decisions are frozen for Slice 1. If live source behavior contradicts them, stop and report the contradiction before changing runtime behavior.

| Area | Frozen decision |
| --- | --- |
| Proof class | This slice proves `source` only. It does not prove installed runtime behavior, cache state, personal plugin sync, hook inventory, or activation readiness. |
| Runtime behavior | Existing Ticket runtime scripts must not import or enforce `ticket_authority.py` in Slice 1. Runtime behavior stays unchanged. |
| Public APIs | The only public callable authority APIs are `classify_mutation(request, context)`, `plan_manifest_lanes(actions, context_by_mutation_id, raw_shape_by_mutation_id)`, and `export_policy_manifest()`. The public importable contract also includes the carrier, result, enum, value, and exception types required to call those functions and interpret results. |
| CLI and artifact | No CLI, no direct-execution helper, and no checked-in generated manifest artifact are added in Slice 1. |
| Module location | `ticket_authority.py` lives under `plugins/turbo-mode/ticket/scripts/` to match local plugin layout, but it is library-only. |
| Runtime imports | `ticket_authority.py` must not import runtime-heavy Ticket modules such as `ticket_engine_core.py`, `ticket_update.py`, `ticket_capture.py`, `ticket_workflow.py`, `ticket_validate.py`, `ticket_parse.py`, `ticket_read.py`, or `ticket_envelope.py`. It cites runtime source through anchors; it does not import it. |
| Current authority classes | `authority_classes = ["canonical"]`. Future nouns are reserved terms, not current classes. |
| Reserved terms | `intake`, `proposal`, `pending_action`, `scheduler_advisory`, `observation`, and `recordable_autonomously` remain reserved until a later slice gives them real consumers. |
| Supported mutation surfaces | The only valid `MutationSurface` values are `capture`, `update`, and `ingest`. There is no `direct_engine` surface. |
| Direct engine | Direct-engine compatibility is manifest-only under the discrepancy registry. Direct-engine requests are not classifiable and are not lane-plannable. |
| Request origin | `origin`, `request_origin`, hook provenance, grants, consent declarations, and approval evidence are future runtime-envelope metadata, not classifier inputs. |
| Context | Every `classify_mutation()` call requires a `MutationContext`. `MutationContext(current=None)` is the explicit empty context. |
| Current state | `CurrentTicketState` is minimal and fully populated when present: `status`, `refinement_status`, and `tags`. Partial state objects are invalid input. |
| Missing context | Missing or insufficient bounded classifier state is a fail-closed unsupported policy result with `local_disposition=CONTEXT_REQUIRED`, not a new mutation class and not an exception. `CONTEXT_REQUIRED` is only classifier input repair, not runtime preflight or lifecycle readiness. |
| Lifecycle preconditions | Wrapper-recognized lifecycle/status mutations that require blocker, acceptance-criteria, reopen-reason, close-readiness, or ticket-graph state use `local_disposition=PRECONDITION_REQUIRED` on `MutationPolicy`. Concrete business preconditions appear only on `ManifestLane`. |
| Malformed input | Malformed API carriers raise `AuthorityInputError`; valid but unsupported policy shapes return unsupported results. |
| Registry defects | Malformed registries raise `AuthorityRegistryError`; runtime-discovered registry ambiguity raises `AuthorityEvaluationError`, a subclass of `AuthorityRegistryError`. |
| Gates | Authored gate values are `apply_consent`, `user_approval`, and `unsupported`. `mutation_class`, `requires_preview`, `tracked_write_allowed`, and `execution_authorized` are derived projections. |
| Execution authorization | `execution_authorized` is globally `False` in Slice 1. `tracked_write_allowed`, if retained, is a derived synonym and is also globally `False`. `supported=True` never means write permission. |
| Lanes | `LaneKind` represents planner lane outcomes. `create`, `update`, `focused_refinement`, `close`, and `reopen` are runtime mutation shapes. `no_op` and `unsupported` are non-mutating planner outcomes. Unsupported local policies and unsupported lanes always use `lane=UNSUPPORTED`. |
| Ownership | `AuthorityOwner` values are `project`, `wrapper`, `engine`, and `envelope`. There is no `caller` and no `unknown` owner. Use `authority_owner=None` only for unregistered or out-of-jurisdiction denials. |
| Authorship | `caller_writable=True` means the current exact outcome accepts caller-authored target input. Unsupported, context-required, precondition-required, and no-op outcomes always have `caller_writable=False`. |
| Engine-managed | `engine_managed=True` is reserved for engine-owned/rendered fields and implies `authority_owner=ENGINE`. Wrapper/envelope-derived values are not engine-managed. |
| Value lineage | Do not add a public `value_source` enum in Slice 1. Use authored value-flow labels as registry/manifest strings plus `authority_owner`, `caller_writable`, and source anchors. |
| Source anchors | Every evidence-bearing registry row has anchors. Anchor carrier shape is import-validated; anchor truth is validated by tests. |
| Direct-engine discrepancies | Exported discrepancy rows are behavior-proven only. Source-inferred suspected mismatches remain plan/test probes, not manifest rows. Absence of a row is not equivalence proof. |
| Versioning | Manifest exports both `schema_version` and `policy_version`; tests assert exact Slice 1 values. Automatic bump enforcement and manifest snapshots are deferred. |
| Registry authorship | The authority registry is hand-authored from the committed tables in this plan. It must not derive rows from live runtime constants at import time. Tests may compare hand-written expected IDs/content against the registry and manifest, but must not parse this Markdown file as a machine-readable registry source. |
| Active registry boundary | `_DEFAULT_REGISTRY` contains active current-behavior rows only. Probe-gated candidates must not live in `_DEFAULT_REGISTRY`, must not affect classifier/planner/export paths, and must not appear in `export_policy_manifest()` until a later plan patch promotes them after behavior proof. |
| Wrapper surface | Active subject rows are wrapper-surface exact, not lower-engine-capability exact. Wrapper create derivations, engine-rendered outputs, and derived lane effects are separate registry surfaces and never create standalone classifier support. |
| Same-status no-op | Slice 1 `NO_OP` is limited to lifecycle/status same-current candidates decidable from `CurrentTicketState.status`. Same-value metadata or section writes remain ordinary supported wrapper subjects. Candidate no-op rows require behavior probes before they may be exported as current behavior. |
| Raw wrapper shape | `plan_manifest_lanes()` is wrapper-shape-aware by construction. Every planner call requires a per-`mutation_id` `RawShapeDiscriminator`; Slice 1 has no implicit authority-action-only planner mode. |

## Plan Artifact Lifecycle

This file is a durable control artifact. Update and commit it before source implementation. Keep docs/control and implementation as separate semantic commits.

Plan-control commits:

```text
docs(superpowers): revise ticket authority kernel slice 1 plan
docs(superpowers): fix ticket authority slice 1 control rows
docs(superpowers): patch ticket authority raw-shape control
```

Implementation commit:

```text
chore(ticket): add passive authority policy kernel
```

Before implementation starts, the plan-control file and any plan-control fixups must be committed. If this plan remains untracked or modified, implementation must not begin.

Plan-control commits must include only this file. Contract prose, source, and test changes start after the plan-control commits and belong to the implementation lane.

## Branch And Worktree Gate

Run from `/Users/jp/Projects/active/codex-tool-dev`.

```bash
git status --short --branch --untracked-files=all
git rev-parse --abbrev-ref HEAD
git rev-list --left-right --count origin/main...main
git worktree list --porcelain
```

Expected before implementation:

- Branch is `chore/ticket-authority-kernel-slice1`.
- `git rev-list --left-right --count origin/main...main` prints `0 0`, unless the user explicitly approves using the local base.
- Worktree is clean after the plan-control commit.
- No merge, rebase, cherry-pick, revert, or bisect is active.
- No other active lane owns the Ticket contract/kernel/test surfaces.

Hard stops:

- Stop if the plan remains untracked when source implementation would begin.
- Stop if implementation discovers a need to mutate installed cache/runtime state.
- Stop if source behavior contradicts a frozen Slice 1 decision.
- Stop if implementation needs a registry row, exported manifest row, vocabulary, value flow, group rule, group-invalid rule, wrapper derivation, effect, or materialization row that is not tabled in this plan.
- Stop if a behavior-probe-gated candidate row fails its required probe; patch this plan before exporting that row.
- Stop if tests prove a suspected direct-engine discrepancy is not behaviorally real; remove that discrepancy row instead of exporting it.

## Non-Goals

- Do not implement proposal creation.
- Do not implement pending-action journals.
- Do not implement `.codex/ticket-actions/`.
- Do not implement proposal promotion.
- Do not implement scheduler holds, TTLs, caps, or selection suppression.
- Do not add storage under `docs/tickets/` or `.codex/`.
- Do not integrate the authority kernel into runtime entrypoints.
- Do not mutate installed plugin cache, personal plugin state, app-server inventory, hooks, or marketplace files.
- Do not add CLI behavior or a generated manifest artifact.
- Do not use skill prose as the enforcement layer.
- Do not add direct-engine classification.
- Do not export a general wrapper-quirk ledger.
- Do not add query-projection policy APIs in Slice 1. Query/read behavior remains outside mutation classification.

## Source Files To Read First

Read these live files before implementation. This plan is not a substitute for source truth.

- `plugins/turbo-mode/ticket/references/ticket-contract.md`
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- `plugins/turbo-mode/ticket/tests/conftest.py`
- `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- `plugins/turbo-mode/ticket/scripts/ticket_capture.py`
- `plugins/turbo-mode/ticket/scripts/ticket_envelope.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_user.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_agent.py`
- `plugins/turbo-mode/ticket/scripts/ticket_workflow.py`
- `plugins/turbo-mode/ticket/scripts/ticket_stage_models.py`
- `plugins/turbo-mode/ticket/scripts/ticket_validate.py`
- `plugins/turbo-mode/ticket/scripts/ticket_parse.py`

Run these read-only scans before implementation:

```bash
rg --files plugins/turbo-mode/ticket/scripts | rg '/ticket_.*\.py$' | sort
rg -n 'focused_refinement|_validate_lifecycle_payload|_will_clear_refinement|validate_fields|validate_envelope|envelope_version|resolution|archive|reopen_reason|capture_source|capture_confidence|map_envelope_to_fields' plugins/turbo-mode/ticket/scripts plugins/turbo-mode/ticket/tests plugins/turbo-mode/ticket/references/ticket-contract.md
```

Expected:

- The script inventory defines the phase-gate scan scope.
- Focused refinement is confirmed as current wrapper behavior.
- Direct close/reopen extra-field behavior is treated as a probe target, not assumed.

## File Structure

- `docs/superpowers/plans/2026-05-22-ticket-authority-kernel-slice1.md` - this updated source-local control plan.
- `plugins/turbo-mode/ticket/references/ticket-contract.md` - normative authority section, passive rollout status, wrapper/direct-engine boundary, and focused-refinement contract correction.
- `plugins/turbo-mode/ticket/scripts/ticket_authority.py` - new pure library-only authority kernel. No IO, no CLI, no runtime imports.
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py` - contract assertions for passive status, current vocabulary, and wrapper/direct-engine boundary.
- `plugins/turbo-mode/ticket/tests/test_authority_contract.py` - registry, classifier, manifest, value-policy, lane-planning, and exception tests.
- `plugins/turbo-mode/ticket/tests/test_authority_source_anchors.py` - live source-anchor resolution tests.
- `plugins/turbo-mode/ticket/tests/test_authority_direct_engine_discrepancies.py` - comparison behavior probes for exported direct-engine discrepancies.
- `plugins/turbo-mode/ticket/tests/test_authority_slice1_phase_gate.py` - temporary no-integration, purity, no-CLI, no-artifact, and no-tracked-write guards.

## Authority Model

### Public API

Implement exactly these public functions:

```python
def classify_mutation(request: MutationRequest, context: MutationContext) -> MutationPolicy:
    ...


def plan_manifest_lanes(
    actions: Sequence[ManifestAction],
    context_by_mutation_id: Mapping[str, MutationContext],
    raw_shape_by_mutation_id: Mapping[str, RawShapeDiscriminator],
) -> ManifestLanePlan:
    ...


def export_policy_manifest() -> dict[str, Any]:
    ...
```

Public callable API means only those three behavioral functions. Public importable contract means the stable types callers need to construct inputs, inspect outputs, and catch expected exceptions.

Export the public contract with `__all__`:

```python
__all__ = (
    "classify_mutation",
    "plan_manifest_lanes",
    "export_policy_manifest",
    "SubjectPath",
    "CurrentTicketState",
    "MutationContext",
    "RawShapeDiscriminator",
    "MutationRequest",
    "ManifestAction",
    "MutationPolicy",
    "ManifestLane",
    "ManifestLanePlan",
    "MutationSurface",
    "TicketAction",
    "OperationKind",
    "RequiredGate",
    "MutationClass",
    "LaneKind",
    "AuthorityOwner",
    "LocalDisposition",
    "ContextField",
    "RawGroupShapeHint",
    "GroupShapeHint",
    "GroupPrecondition",
    "GroupEffect",
    "RuntimeCheck",
    "TicketAuthorityError",
    "AuthorityInputError",
    "AuthorityRegistryError",
    "AuthorityEvaluationError",
)
```

Do not export public helpers for direct-engine classification, wrapper-payload parsing, grant evaluation, query projection, CLI export, manifest artifact generation, registry construction, registry rows, source-anchor support types, value-policy support types, private ID wrappers, or discrepancy implementation helpers.

### Public Shape Rules

Use this strict public API boundary:

| Field kind | Public dataclass shape | Manifest shape |
| --- | --- | --- |
| Closed semantic categories | `StrEnum` instances | stable strings |
| Collections of closed categories | `tuple[EnumType, ...]` | arrays of strings |
| IDs and trace keys | `str` | strings |
| Paths | `str` or public `SubjectPath` only where explicitly a carrier | strings |
| Open diagnostic codes | `str` | strings |
| Booleans | `bool` | booleans |

Input carrier enum fields require real enum instances. Raw strings raise `AuthorityInputError`. Public result categorical fields return enum instances. Manifest export converts every enum to `.value`, contains no enum objects, and must survive `json.dumps(..., sort_keys=True)`.

Public result IDs and reason codes are plain strings. Private registry builders may validate reason codes through private value objects, but `MutationPolicy.reason_code` and `ManifestLane.reason_code` are `str`.

### Core Dataclasses

`MutationRequest` is the local policy carrier:

```python
@dataclass(frozen=True)
class MutationRequest:
    surface: MutationSurface
    action: TicketAction
    operation: OperationKind
    subject_path: SubjectPath
    value: object | None = None
```

It must not include `origin`, `request_origin`, hook fields, provenance fields, grants, approvals, apply consent, context source, snapshot fingerprint, delta values, or before values.

`MutationContext` carries the classifier state:

```python
@dataclass(frozen=True)
class CurrentTicketState:
    status: str
    refinement_status: str
    tags: tuple[str, ...]


@dataclass(frozen=True)
class MutationContext:
    current: CurrentTicketState | None
```

`CurrentTicketState` fields are mandatory when `current` is present. Partial objects are malformed input and raise `AuthorityInputError`. Slice 1 does not widen current state for metadata equality checks; same-value metadata or section writes are not classified as `NO_OP`.

`SubjectPath` is the public input carrier for the normalized wrapper/envelope policy subject accepted by `MutationRequest`. It validates grammar and public namespace only; it does not validate rule existence or requestability.

```python
@dataclass(frozen=True)
class SubjectPath:
    value: str

    def __post_init__(self) -> None:
        ...

    def __str__(self) -> str:
        return self.value
```

`SubjectPath.__post_init__` raises `AuthorityInputError` for malformed values. Allowed prefixes are:

- `capture.input.`
- `capture.derived.`
- `ingest.envelope.`
- `ingest.derived.`
- `update.frontmatter.`
- `update.focused.`
- `update.lifecycle.`

Each prefix must have at least one segment after it. Segments are dot-separated lowercase identifiers with no blanks, slashes, or uppercase characters. `SubjectPath("capture.input.unknown")` is constructible and classifies through the unregistered-subject fallback. `SubjectPath("capture.derived.source")` is constructible and classifies through a non-requestable diagnostic denial. `SubjectPath("capture.output.source")`, `SubjectPath("capture.input")`, and `SubjectPath("Capture.Input.Title")` raise `AuthorityInputError`.

`SubjectPath` equality and hashing use frozen dataclass value semantics. The public contract promises no ordering and no implicit equality with raw strings.

`SubjectPath` identifies the policy subject, not a persisted ticket path.

```text
subject_path = classifier lookup address for the wrapper/envelope policy subject
output_paths = persisted/materialized ticket paths affected by that subject
effect_paths = derived paths affected only through a lane effect
```

Classifier lookup uses only `subject_path`. `output_paths` and `effect_paths` never create standalone subject support.

Subject-specific invalid payloads, such as malformed tag lists or invalid status targets, are policy denials, not `AuthorityInputError`.

`ManifestAction` is shape-only:

```python
@dataclass(frozen=True)
class ManifestAction:
    action_id: str
    mutation_id: str
    request: MutationRequest
```

It must not carry `origin`, context, provenance, grants, approval, fingerprint, or runtime envelope data. `plan_manifest_lanes()` accepts `context_by_mutation_id: Mapping[str, MutationContext]` and `raw_shape_by_mutation_id: Mapping[str, RawShapeDiscriminator]` separately. Missing or unused context-map keys are malformed planner input and raise `AuthorityInputError`.

`RawShapeDiscriminator` is the planner-only non-authority carrier for exact raw wrapper payload shape:

```python
@dataclass(frozen=True)
class RawShapeDiscriminator:
    mutation_id: str
    surface: MutationSurface
    raw_keys: frozenset[str]
    raw_status_value: object | None
    raw_group_shape_hint: RawGroupShapeHint
```

`RawShapeDiscriminator` is public because planner callers must provide it. It is not an authority action, not a classifier input, and not an exported manifest row. Slice 1 must not expose a public `from_wrapper_payload()` helper; wrapper-payload conversion helpers may exist only as private/test-only helpers.

`raw_keys` are exact wrapper/envelope payload keys, such as `priority`, `reopen_reason`, or `suggested_priority`. They are not `SubjectPath` values and must not contain dotted normalized policy paths. `raw_keys` must be a non-empty `frozenset[str]`; each key must be non-empty and contain no blanks, slashes, dots, or uppercase characters. Carrier validation checks syntax and raw-shape consistency, not active wrapper allowlist membership. Unknown, excluded, or unsupported raw keys are policy-evaluated by the planner so they can produce unsupported lanes.

For each planner mutation group, `raw_keys` is the full raw payload key set. Every raw key must either map to exactly one `ManifestAction` for the same `mutation_id` through a row's `request_raw_key`, or be covered by an active authored raw-shape-only exception. Any unaccounted raw key is malformed planner input and raises `AuthorityInputError`. Every `ManifestAction` whose matched row has `request_raw_key` must have that key present in `raw_keys`.

`raw_status_value` records the raw `status` value when `status` is in `raw_keys`; it must be `None` when `status` is absent. `None` is also allowed as the raw malformed value when the payload explicitly includes `status: null`, so implementation must track status-key presence from `raw_keys`, not from `raw_status_value is None`. The value may be any object so malformed status values can still be planned as policy invalids instead of carrier errors.

`raw_group_shape_hint` is the normalized raw wrapper-compatibility shape. It is derived from raw facts but carried explicitly for deterministic tests. The constructor validates it against `surface`, `raw_keys`, and `raw_status_value`; contradictions raise `AuthorityInputError`. For update payloads, current source-order compatibility is:

```text
raw_status_value in {"done", "wontfix"} -> UPDATE_CLOSE
raw_status_value == "open" or "reopen_reason" in raw_keys -> UPDATE_STATUS_OPEN_EXCLUSIVE
"status" in raw_keys -> UPDATE_STATUS_LIFECYCLE
metadata/focused keys only -> UPDATE_FRONTMATTER or UPDATE_FOCUSED_REFINEMENT
well-formed but unsupported wrapper shape -> UNSUPPORTED_RAW_SHAPE
```

Terminal reopen is not a raw-shape hint. It is selected later from `RawGroupShapeHint.UPDATE_STATUS_OPEN_EXCLUSIVE` plus `MutationContext.current.status`.

`MutationPolicy` includes final local outcome and trace fields:

```python
@dataclass(frozen=True)
class MutationPolicy:
    supported: bool
    authority_class: str
    rule_id: str
    shape_family_id: str
    subject_family_id: str | None
    local_disposition: LocalDisposition
    required_gate: RequiredGate
    mutation_class: MutationClass
    requires_preview: bool
    subject_path: str
    policy_path: str
    lane: LaneKind
    group_shape_hint: GroupShapeHint
    authority_owner: AuthorityOwner | None
    caller_writable: bool
    engine_managed: bool
    tracked_write_allowed: bool
    reason_code: str
    required_context_fields: tuple[ContextField, ...] = ()
```

Do not include `preconditions`, `effects`, `runtime_checks`, `execution_authorized`, or `requires_revalidation` on `MutationPolicy` or local rule rows. Those fields belong only to group rules and `ManifestLane`.

`MutationPolicy.supported` means this single local action is supportable by the classifier without unresolved business-readiness state. It is equivalent to `policy.local_disposition is LocalDisposition.SUPPORTED`. It never means write permission.

`ManifestLane` is the actionable passive planning surface:

```python
@dataclass(frozen=True)
class ManifestLane:
    mutation_id: str
    lane: LaneKind
    supported: bool
    group_rule_id: str
    group_family_id: str
    action_ids: tuple[str, ...]
    action_rule_ids: Mapping[str, str]
    group_invalid_rule_ids: tuple[str, ...]
    invalid_action_ids: tuple[str, ...]
    context_required_action_ids: tuple[str, ...]
    precondition_required_action_ids: tuple[str, ...]
    unsupported_action_ids: tuple[str, ...]
    no_op_action_ids: tuple[str, ...]
    required_gate: RequiredGate
    mutation_class: MutationClass
    requires_preview: bool
    tracked_write_allowed: bool
    execution_authorized: bool
    runtime_checks: tuple[RuntimeCheck, ...]
    preconditions: tuple[GroupPrecondition, ...]
    effects: tuple[GroupEffect, ...]
    requires_revalidation: bool
    reason_code: str
```

`ManifestLane.supported` means the grouped wrapper lane shape is structurally recognized. It never means execution permission. Slice 1 always uses `execution_authorized=False` and `tracked_write_allowed=False`.

`invalid_action_ids`, `context_required_action_ids`, `precondition_required_action_ids`, `unsupported_action_ids`, and `no_op_action_ids` are pairwise disjoint. `invalid_action_ids` contains actions rejected by local `INVALID_VALUE` or group `INVALID_VALUE`. Local invalids are identified by `action_rule_ids[action_id]` pointing to an invalid local rule. Group invalids are identified by `group_invalid_rule_ids`.

`unsupported_action_ids` contains action IDs denied by local unsupported policy, unsupported semantic-target policy, or group/raw-shape compatibility policy. An action can have a locally supported `action_rule_ids[action_id]` and still appear in `unsupported_action_ids` when the selected group rule rejects it in context. `unsupported_action_ids` must never contain action IDs already present in `invalid_action_ids`.

Any lane with `invalid_action_ids` is `supported=False`, `lane=UNSUPPORTED`, `required_gate=UNSUPPORTED`, `execution_authorized=False`, and `tracked_write_allowed=False`.

`ManifestLanePlan` is the minimal planner result wrapper:

```python
@dataclass(frozen=True)
class ManifestLanePlan:
    lanes: tuple[ManifestLane, ...]
```

`ManifestLanePlan` has no `policy_version`, `schema_version`, generated timestamp, registry hash, or global diagnostics in Slice 1. Version and registry metadata live only in `export_policy_manifest()`.

`plan_manifest_lanes(actions=(), context_by_mutation_id={}, raw_shape_by_mutation_id={})` raises `AuthorityInputError`; an empty action sequence is not a wrapper mutation shape. Duplicate `ManifestAction.action_id` values raise `AuthorityInputError`. Missing or unused extra `context_by_mutation_id` entries for any input `mutation_id` are malformed and raise `AuthorityInputError`. Missing or unused extra `raw_shape_by_mutation_id` entries are malformed and raise `AuthorityInputError`.

Lane order is deterministic by first occurrence of `mutation_id` in the input action sequence. Within each lane, `action_ids` preserve input order for that `mutation_id`. Public APIs never expose mutable lane lists.

### Enums

Define closed enums:

```python
class MutationSurface(StrEnum):
    CAPTURE = "capture"
    UPDATE = "update"
    INGEST = "ingest"


class TicketAction(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    CLOSE = "close"
    REOPEN = "reopen"


class OperationKind(StrEnum):
    CREATE = "create"
    SET_FRONTMATTER = "set_frontmatter"
    FOCUSED_REFINEMENT = "focused_refinement"
    CLOSE = "close"
    REOPEN = "reopen"


class RequiredGate(StrEnum):
    APPLY_CONSENT = "apply_consent"
    USER_APPROVAL = "user_approval"
    UNSUPPORTED = "unsupported"


class MutationClass(StrEnum):
    PREVIEW_REQUIRED = "preview_required"
    APPROVAL_REQUIRED = "approval_required"
    UNSUPPORTED = "unsupported"


class LaneKind(StrEnum):
    CREATE = "create"
    UPDATE = "update"
    FOCUSED_REFINEMENT = "focused_refinement"
    CLOSE = "close"
    REOPEN = "reopen"
    NO_OP = "no_op"
    UNSUPPORTED = "unsupported"


class AuthorityOwner(StrEnum):
    PROJECT = "project"
    WRAPPER = "wrapper"
    ENGINE = "engine"
    ENVELOPE = "envelope"


class LocalDisposition(StrEnum):
    SUPPORTED = "supported"
    CONTEXT_REQUIRED = "context_required"
    PRECONDITION_REQUIRED = "precondition_required"
    NO_OP = "no_op"
    UNSUPPORTED = "unsupported"


class ContextField(StrEnum):
    CURRENT_STATUS = "current.status"
    CURRENT_REFINEMENT_STATUS = "current.refinement_status"
    CURRENT_TAGS = "current.tags"


class RawGroupShapeHint(StrEnum):
    CAPTURE_CREATE = "capture_create"
    INGEST_CREATE = "ingest_create"
    UPDATE_FRONTMATTER = "update_frontmatter"
    UPDATE_FOCUSED_REFINEMENT = "update_focused_refinement"
    UPDATE_STATUS_LIFECYCLE = "update_status_lifecycle"
    UPDATE_STATUS_OPEN_EXCLUSIVE = "update_status_open_exclusive"
    UPDATE_CLOSE = "update_close"
    UNSUPPORTED_RAW_SHAPE = "unsupported_raw_shape"


class GroupShapeHint(StrEnum):
    CAPTURE_CREATE = "capture_create"
    INGEST_CREATE = "ingest_create"
    UPDATE_FRONTMATTER = "update_frontmatter"
    UPDATE_FOCUSED_REFINEMENT = "update_focused_refinement"
    UPDATE_STATUS_LIFECYCLE = "update_status_lifecycle"
    UPDATE_STATUS_OPEN_EXCLUSIVE = "update_status_open_exclusive"
    UPDATE_CLOSE = "update_close"
    UPDATE_REOPEN = "update_reopen"
    UNRESOLVED_CONTEXT_REQUIRED = "unresolved_context_required"
    UNSUPPORTED_NO_GROUP_SHAPE = "unsupported_no_group_shape"


class GroupPrecondition(StrEnum):
    BLOCKED_BY_REQUIRED = "blocked_by_required"
    BLOCKERS_RESOLVED_REQUIRED = "blockers_resolved_required"
    CLOSE_READINESS_REQUIRED = "close_readiness_required"
    ACCEPTANCE_CRITERIA_REQUIRED = "acceptance_criteria_required"
    REOPEN_REASON_REQUIRED = "reopen_reason_required"
    FOCUSED_REFINEMENT_MODE_REQUIRED = "focused_refinement_mode_required"


class GroupEffect(StrEnum):
    CREATES_TICKET = "creates_ticket"
    UPDATES_FRONTMATTER = "updates_frontmatter"
    UPDATES_FOCUSED_REFINEMENT_SECTIONS = "updates_focused_refinement_sections"
    CLEARS_REFINEMENT_MARKER = "clears_refinement_marker"
    MAY_AFFECT_CLOSE_READINESS = "may_affect_close_readiness"
    SETS_TERMINAL_STATUS = "sets_terminal_status"
    APPENDS_REOPEN_HISTORY = "appends_reopen_history"
    MAY_MOVE_FROM_CLOSED_TICKETS = "may_move_from_closed_tickets"


class RuntimeCheck(StrEnum):
    PREFLIGHT_REQUIRED = "preflight_required"
    DEDUP_SCAN_REQUIRED = "dedup_scan_required"
    TARGET_FINGERPRINT_REVALIDATION = "target_fingerprint_revalidation"
    INGEST_ENVELOPE_CONTAINMENT_REQUIRED = "ingest_envelope_containment_required"
    INGEST_IDEMPOTENCY_CHECK_REQUIRED = "ingest_idempotency_check_required"
```

Do not define `MutationSurface.DIRECT_ENGINE`, `AuthorityOwner.CALLER`, `AuthorityOwner.UNKNOWN`, or current provenance/grant enums. Do not add `UPDATE_REOPEN`, `UNRESOLVED_CONTEXT_REQUIRED`, or `UNSUPPORTED_NO_GROUP_SHAPE` to `RawGroupShapeHint`; those are semantic planner/classifier states, not raw wrapper shapes.

Derived projections:

```text
required_gate=apply_consent -> mutation_class=preview_required, requires_preview=True
required_gate=user_approval -> mutation_class=approval_required, requires_preview=True
required_gate=unsupported -> mutation_class=unsupported, requires_preview=False
tracked_write_allowed -> always False in Slice 1
execution_authorized -> always False in Slice 1
```

Do not author `mutation_class`, `requires_preview`, `tracked_write_allowed`, or `execution_authorized` independently in registry rows.

### Exceptions And IDs

Use private typed value objects with one shared grammar validator. Public result dataclasses and manifest exports expose canonical ID strings.

```python
class _RegistryId:
    value: str

class _RuleId(_RegistryId): ...
class _ShapeFamilyId(_RegistryId): ...
class _SubjectFamilyId(_RegistryId): ...
class _GroupFamilyId(_RegistryId): ...
class _GroupRuleId(_RegistryId): ...
class _VocabularyId(_RegistryId): ...
class _ValuePolicyId(_RegistryId): ...
class _ValueFlowId(_RegistryId): ...
class _RawShapeExceptionId(_RegistryId): ...
class _MaterializationId(_RegistryId): ...
class _EffectId(_RegistryId): ...
class _DiscrepancyId(_RegistryId): ...
class _ScopeId(_RegistryId): ...
```

ID grammar:

```text
lowercase dot-separated segments
each segment matches [a-z0-9_]+
no blanks, spaces, slashes, uppercase, or prose
```

Use this exception hierarchy:

```python
class TicketAuthorityError(Exception): ...
class AuthorityInputError(TicketAuthorityError): ...
class AuthorityRegistryError(TicketAuthorityError): ...
class AuthorityEvaluationError(AuthorityRegistryError): ...
```

| Failure | Result |
| --- | --- |
| Malformed caller carrier | `AuthorityInputError` |
| Malformed default registry at import/build | `AuthorityRegistryError` |
| Ambiguous or impossible evaluation from a valid request | `AuthorityEvaluationError` |
| Valid request denied by policy | `MutationPolicy` or `ManifestLane` with `supported=False` |
| Valid no-op local request | `MutationPolicy(local_disposition=NO_OP, supported=False)` |
| All-no-op group | `ManifestLane(lane=NO_OP, supported=True, no_op_action_ids=...)` |

## Authored Registry Tables

These tables are the implementation control surface for `_DEFAULT_REGISTRY` and for plan-authored probe candidates. If a row, ID, vocabulary, mapping, or effect appears in exported manifest data or changes classifier/planner output, it must be tabled here.

`_DEFAULT_REGISTRY` is active-only. Probe-gated candidates may be tabled in this plan, but they must live outside `_DEFAULT_REGISTRY` and outside all classifier/planner/export paths until a later plan patch promotes them after behavior proof.

The implementation may use helpers to build rows from these authored entries, but it must not invent anonymous invalid-value, context-required, unsupported, or no-op rows.

### Source Anchor Keys

The registry rows below reference these source anchors. `test_authority_source_anchors.py` must validate runtime-source evidence with file text and AST parsing only; it must not import runtime Ticket modules. Importing `ticket_authority.py` to inspect exported anchors or manifest output is allowed.

| Anchor key | Required anchor target |
| --- | --- |
| `contract.schema` | `plugins/turbo-mode/ticket/references/ticket-contract.md` schema headings and field tables |
| `contract.envelope` | `plugins/turbo-mode/ticket/references/ticket-contract.md` DeferredWorkEnvelope schema and consumer behavior |
| `validate.constants` | AST literals in `plugins/turbo-mode/ticket/scripts/ticket_validate.py`: `VALID_PRIORITIES`, `VALID_STATUSES`, `VALID_RESOLUTIONS`, `VALID_CAPTURE_CONFIDENCE`, `VALID_REFINEMENT_STATUSES`, `CONTROLLED_CAPTURE_TAGS`, `CAPTURE_INPUT_FIELDS` |
| `capture.allowed_fields` | `ticket_capture.py` `_ALLOWED_CAPTURE_FIELDS = CAPTURE_INPUT_FIELDS` and unsupported-field rejection |
| `capture.mapping` | `ticket_capture.py` `_capture_fields()` mapping of capture payload to engine fields |
| `capture.tests` | `test_capture.py` tests for unsupported capture fields, preserved `capture_confidence`, overwritten `capture_source`, and written capture-created ticket fields |
| `envelope.schema` | AST literals in `ticket_envelope.py`: `_REQUIRED_FIELDS`, `_OPTIONAL_FIELDS`, `_ALL_FIELDS`, `_VALID_PRIORITIES` |
| `envelope.mapping` | `ticket_envelope.py` `validate_envelope()` and `map_envelope_to_fields()` |
| `envelope.tests` | `test_envelope.py` tests for envelope validation and mapping |
| `update.allowed_fields` | AST literals in `ticket_update.py`: `_ALLOWED_UPDATE_FIELDS`, `_SECTION_FIELDS`, `_METADATA_FIELDS`, `_CLOSE_FIELDS`, `_REOPEN_FIELDS` |
| `update.mapping` | `ticket_update.py` `_action_and_fields()`, `_prepare_fields()`, and `_validate_lifecycle_payload()` |
| `update.refinement` | `ticket_update.py` `_will_clear_refinement()` and refinement-marker handling in `_prepare_fields()` |
| `update.tests` | `test_update_refinement.py` focused refinement, lifecycle rejection, and needs-refinement marker tests |
| `engine.transitions` | `ticket_engine_core.py` `_VALID_TRANSITIONS`, `_TRANSITION_PRECONDITIONS`, `_TARGET_PRECONDITIONS`, `_is_valid_transition()`, and `_evaluate_update_policy()` |
| `engine.create` | `ticket_engine_core.py` `_execute_create()` and `render_ticket(...)` call |
| `engine.update` | `ticket_engine_core.py` `_execute_update()`, `_classify_update_fields()`, and focused section writes |
| `engine.close` | `ticket_engine_core.py` `_evaluate_close_policy()` and `_execute_close()` |
| `engine.reopen` | `ticket_engine_core.py` `_evaluate_reopen_policy()` and `_execute_reopen()` |

### Shape Families

| shape_family_id | selector | jurisdiction | stop_rule_id | anchors |
| --- | --- | --- | --- | --- |
| `shape.capture.create` | `CAPTURE + CREATE + CREATE` | in jurisdiction | none | `capture.allowed_fields`, `capture.mapping` |
| `shape.ingest.create` | `INGEST + CREATE + CREATE` | in jurisdiction | none | `contract.envelope`, `envelope.mapping` |
| `shape.update.set_frontmatter` | `UPDATE + UPDATE + SET_FRONTMATTER` | in jurisdiction | none | `update.allowed_fields`, `update.mapping` |
| `shape.update.focused_refinement` | `UPDATE + UPDATE + FOCUSED_REFINEMENT` | in jurisdiction | none | `update.allowed_fields`, `update.refinement` |
| `shape.update.close` | `UPDATE + CLOSE + CLOSE` | in jurisdiction | none | `update.mapping`, `engine.close` |
| `shape.update.reopen` | `UPDATE + REOPEN + REOPEN` | in jurisdiction | none | `update.mapping`, `engine.reopen` |
| `shape.unsupported.capture.non_create_mutation` | `CAPTURE + not(CREATE + CREATE) + ANY_SUBJECT` | unsupported shape | `unsupported.capture.non_create_mutation` | `capture.allowed_fields` |
| `shape.unsupported.ingest.non_create_mutation` | `INGEST + not(CREATE + CREATE) + ANY_SUBJECT` | unsupported shape | `unsupported.ingest.non_create_mutation` | `envelope.mapping` |
| `shape.unsupported.update.unsupported_action_operation` | unsupported `UPDATE` combinations | unsupported shape | `unsupported.update.unsupported_action_operation` | `update.allowed_fields`, `update.mapping` |

Wildcard subject handling is allowed only for unsupported shape families. `subject=ANY` must never grant support.

### Vocabularies

| vocabulary_id | values | anchors |
| --- | --- | --- |
| `vocab.status.all` | `open`, `in_progress`, `blocked`, `done`, `wontfix` | `validate.constants`, `contract.schema`, `engine.transitions` |
| `vocab.status.nonterminal` | `open`, `in_progress`, `blocked` | `contract.schema`, `engine.transitions` |
| `vocab.status.terminal` | `done`, `wontfix` | `contract.schema`, `engine.transitions` |
| `vocab.priority` | `critical`, `high`, `medium`, `low` | `validate.constants`, `contract.schema`, `envelope.schema` |
| `vocab.capture_confidence` | `low`, `medium`, `high` | `validate.constants`, `contract.schema` |
| `vocab.refinement_status` | `needs_refinement` | `validate.constants`, `contract.schema` |
| `vocab.capture_control_tags` | `needs-refinement`, `bug`, `feature`, `docs`, `test`, `maintenance`, `security` | `validate.constants`, `contract.schema` |
| `vocab.close_resolution` | `done`, `wontfix` | `validate.constants`, `contract.schema`, `engine.close` |
| `vocab.envelope_version` | `1.0` | `envelope.schema`, `contract.envelope` |

### Value Policies

| value_policy_id | kind | vocabulary/shape | invalid_rule_id | anchors |
| --- | --- | --- | --- | --- |
| `value.none` | `NONE` | no value validation | none | plan-authored |
| `value.overwritten_input_any` | `OVERWRITTEN_INPUT_ANY` | source-indicated accepted raw input of any JSON-compatible shape; wrapper overwrites before lower validation | none | `capture.mapping`; wrapper behavior test required |
| `value.any_string` | `ANY_STRING` | string when present | `invalid.shared.any_string` | `validate.constants`, `envelope.schema` |
| `value.non_empty_string` | `NON_EMPTY_STRING` | non-empty string | `invalid.shared.non_empty_string` | `capture.mapping`, `envelope.schema`, `engine.reopen` |
| `value.envelope_version_1_0` | `EXACT_VALUE` | `vocab.envelope_version` | `invalid.ingest.envelope.envelope_version.value` | `envelope.schema`, `contract.envelope` |
| `value.priority` | `ALLOWED_VOCABULARY` | `vocab.priority` | `invalid.shared.priority` | `validate.constants` |
| `value.capture_confidence` | `ALLOWED_VOCABULARY` | `vocab.capture_confidence` | `invalid.capture.create.capture_confidence.value` | `validate.constants`, `capture.tests` |
| `value.refinement_status` | `ALLOWED_VOCABULARY` | `vocab.refinement_status` | `invalid.capture.create.refinement_status.value` | `validate.constants`, `contract.schema` |
| `value.capture_tags` | `CONTROL_TAG_LIST` | `vocab.capture_control_tags` | `invalid.capture.create.tags.value` | `validate.constants`, `capture.mapping` |
| `value.string_list` | `STRING_LIST` | list of strings | `invalid.shared.string_list` | `validate.constants`, `envelope.schema` |
| `value.path_list` | `PATH_LIST` | list of strings representing paths | `invalid.shared.path_list` | `validate.constants`, `envelope.schema` |
| `value.status_target` | `STATUS_TARGET` | `vocab.status.all` | `invalid.update.lifecycle.status.value` | `validate.constants`, `engine.transitions` |
| `value.close_status_target` | `ALLOWED_VOCABULARY` | `vocab.close_resolution` | `invalid.update.close.status.value` | `validate.constants`, `engine.close` |
| `value.source_object` | `OBJECT_SHAPE` | required keys `type`, `ref`, `session` | `invalid.shared.source_object` | `validate.constants`, `envelope.schema`, `engine.create` |
| `value.defer_object` | `OBJECT_SHAPE` | required keys `active`, `reason`, `deferred_at` | `invalid.ingest.derived.defer.value` | `validate.constants`, `envelope.mapping` |
| `value.key_files` | `OBJECT_SHAPE` | list of objects with `file`, `role`, `look_for` | `invalid.ingest.envelope.key_files.value` | `envelope.schema` |
| `value.acceptance_criteria` | `STRING_LIST` | list of strings | `invalid.shared.acceptance_criteria` | `validate.constants`, `envelope.schema` |
| `value.boolean` | `BOOLEAN` | boolean | `invalid.shared.boolean` | `validate.constants`, `engine.close` |

### Value Flow Policies

`value_policy_id` validates value shape. `value_flow_id` records current wrapper authorship and overwrite/default behavior. Value-flow IDs are manifest-facing strings, not public Python enums.

| value_flow_id | meaning | typical owners | anchors |
| --- | --- | --- | --- |
| `flow.caller_preserved` | caller-supplied value is preserved when present | `PROJECT`, `WRAPPER` | `capture.mapping`, `update.mapping` |
| `flow.caller_preserved_or_wrapper_defaulted_if_missing` | caller-supplied value is preserved; wrapper supplies default only when missing | `WRAPPER` | `capture.mapping`, `capture.tests` |
| `flow.caller_preserved_or_wrapper_inferred_if_missing` | caller-supplied value is preserved; wrapper infers fallback only when missing | `WRAPPER` | `capture.mapping`, `capture.tests` |
| `flow.wrapper_overwrites_constant_conversation` | wrapper accepts an input value and always writes output value `"conversation"` before engine create | `WRAPPER` | `capture.mapping`, `capture.tests` |
| `flow.wrapper_synthesizes_source_object` | wrapper supplies source object from capture session payload before engine create | `WRAPPER` | `capture.mapping` |
| `flow.wrapper_defaults_capture_acceptance_criteria_if_missing` | wrapper supplies default acceptance criteria when capture input omits them | `WRAPPER` | `capture.mapping`, `validate.constants` |
| `flow.wrapper_synthesizes_defer_object` | ingest wrapper supplies defer object from envelope emission data before engine create | `WRAPPER` | `envelope.mapping`, `contract.envelope` |
| `flow.wrapper_defaults_ingest_priority_if_missing` | ingest wrapper supplies priority `medium` when envelope omits suggested priority | `WRAPPER` | `envelope.mapping`, `contract.envelope` |
| `flow.wrapper_defaults_ingest_tags_if_missing` | ingest wrapper supplies empty tag list when envelope omits suggested tags | `WRAPPER` | `envelope.mapping`, `contract.envelope` |
| `flow.envelope_supplied` | validated envelope supplies the value | `ENVELOPE` | `envelope.schema`, `envelope.mapping` |
| `flow.lifecycle_transition` | value requests a lifecycle transition and may require current-ticket state | `PROJECT` | `update.mapping`, `engine.transitions` |
| `flow.no_op_candidate` | candidate same-current status value; behavior probe must pass before export | `PROJECT` | `engine.update` |
| `flow.engine_materialized` | engine renders the output as create/update materialization | `ENGINE` | `engine.create`, `engine.update` |
| `flow.engine_derived_effect` | grouped lane causes an engine-owned derived write/effect | `ENGINE` | `engine.update`, `engine.close`, `engine.reopen` |

Authored row and derivation value-flow assignments:

| row set | value_flow_id |
| --- | --- |
| `supported.capture.create.title`, `supported.capture.create.captured_request`, `supported.capture.create.problem`, `supported.capture.create.next_action`, `supported.capture.create.component`, `supported.capture.create.related_paths`, `supported.capture.create.acceptance_criteria`, `supported.capture.create.refinement_status` | `flow.caller_preserved` |
| `supported.capture.create.capture_confidence` | `flow.caller_preserved_or_wrapper_defaulted_if_missing` |
| `supported.capture.create.priority` | `flow.caller_preserved_or_wrapper_inferred_if_missing` |
| `supported.capture.create.tags` | `flow.caller_preserved` |
| `supported.capture.create.capture_source` | `flow.wrapper_overwrites_constant_conversation`; source-indicated `value.overwritten_input_any`; wrapper behavior proof gate required |
| `derive.capture.create.source` | `flow.wrapper_synthesizes_source_object` |
| `derive.capture.create.acceptance_criteria_default` | `flow.wrapper_defaults_capture_acceptance_criteria_if_missing` |
| `supported.ingest.create.envelope_version`, `supported.ingest.create.title`, `supported.ingest.create.problem`, `supported.ingest.create.source`, `supported.ingest.create.emitted_at`, `supported.ingest.create.context`, `supported.ingest.create.prior_investigation`, `supported.ingest.create.approach`, `supported.ingest.create.acceptance_criteria`, `supported.ingest.create.verification`, `supported.ingest.create.key_files`, `supported.ingest.create.key_file_paths`, `supported.ingest.create.suggested_priority`, `supported.ingest.create.suggested_tags`, `supported.ingest.create.effort` | `flow.envelope_supplied` |
| `derive.ingest.create.defer` | `flow.wrapper_synthesizes_defer_object` |
| `derive.ingest.create.priority_default` | `flow.wrapper_defaults_ingest_priority_if_missing` |
| `derive.ingest.create.tags_default` | `flow.wrapper_defaults_ingest_tags_if_missing` |
| `supported.update.frontmatter.priority`, `supported.update.frontmatter.component`, `supported.update.frontmatter.related_paths`, `supported.update.frontmatter.blocked_by`, `supported.update.frontmatter.blocks`, `supported.update.frontmatter.tags`, `supported.update.focused.problem`, `supported.update.focused.next_action`, `supported.update.focused.acceptance_criteria` | `flow.caller_preserved` |
| `supported.update.lifecycle.status.open_to_in_progress`, `supported.update.lifecycle.status.in_progress_to_open`, `precondition.update.lifecycle.status.to_blocked`, `precondition.update.lifecycle.status.blocked_to_open`, `precondition.update.lifecycle.status.blocked_to_in_progress`, `precondition.update.close.status.done`, `precondition.update.close.status.wontfix`, `precondition.update.reopen.status.open`, `precondition.update.reopen.reopen_reason` | `flow.lifecycle_transition` |
| `noop.candidate.update.lifecycle.status.same_open`, `noop.candidate.update.lifecycle.status.same_in_progress`, `noop.candidate.update.lifecycle.status.same_blocked` | `flow.no_op_candidate` |

### Subject Families

| subject_family_id | shape_family_id | subject_path namespace | fallback_rule_id | anchors |
| --- | --- | --- | --- | --- |
| `subject.capture.create` | `shape.capture.create` | `capture.input.*`, `capture.derived.*` | `unsupported.capture.create.unregistered_subject` | `capture.allowed_fields`, `capture.mapping` |
| `subject.ingest.create` | `shape.ingest.create` | `ingest.envelope.*`, `ingest.derived.*` | `unsupported.ingest.create.unregistered_subject` | `contract.envelope`, `envelope.schema`, `envelope.mapping` |
| `subject.update.frontmatter` | `shape.update.set_frontmatter` | `update.frontmatter.*` | `unsupported.update.frontmatter.unregistered_subject` | `update.allowed_fields`, `engine.update` |
| `subject.update.focused` | `shape.update.focused_refinement` | `update.focused.*` | `unsupported.update.focused.unregistered_subject` | `update.allowed_fields`, `update.refinement`, `engine.update` |
| `subject.update.lifecycle.status` | `shape.update.set_frontmatter` | `update.lifecycle.status` | `unsupported.update.lifecycle.status.unmatched` | `update.mapping`, `engine.transitions` |
| `subject.update.lifecycle.reopen_reason` | `shape.update.reopen` | `update.lifecycle.reopen_reason` | `unsupported.update.reopen.unregistered_subject` | `update.mapping`, `engine.reopen` |
| `subject.update.close.status` | `shape.update.close` | `update.lifecycle.status` with target `done` or `wontfix` | `unsupported.update.close.unregistered_subject` | `update.mapping`, `engine.close` |

### Local Outcome Stages

Ordering is policy:

```text
INVALID_VALUE
CONTEXT_REQUIRED
PRECONDITION_REQUIRED
SPECIFIC_UNSUPPORTED
NO_OP
SUPPORTED
```

Invalid payload repair comes before snapshot repair. Classifier context repair comes before lifecycle precondition deferral. Precondition-required outcomes come before specific denials where readiness must be resolved first. Specific denial carve-outs come before `NO_OP` and broad support. `SUPPORTED` is terminal inside a subject family. At most one outcome may match within the first applicable stage; same-stage overlap raises `AuthorityEvaluationError`.

Every known subject with a value policy has an explicit invalid-value row. Invalid-value rows may be shared only when the same classifier shape, subject family, value policy, and public diagnostic behavior match.

Every context-required outcome is an authored row with stable `rule_id`. Context rows may be shared only when shape family, subject family or declared context family, required context fields, group shape hint, and diagnostic behavior match.

Known semantic carve-outs that outrank broad support are authored `SPECIFIC_UNSUPPORTED` rows. Generic unknown subjects use fallback unsupported rows.

### Request-Subject Rows

These are the only current-behavior request-subject rows that may feed `classify_mutation()` as supported local subjects, plus the invalid/context/specific rows they reference. Active positive rows are caller/envelope request subjects accepted by wrapper syntax, accepted-but-overwritten request subjects, and caller-visible mutation subjects that can be grouped/planned.

Rows with `rule_id` prefix `noop.candidate.` are probe-gated candidates, not active behavior. They are tabled here only to freeze planned IDs and predicates. They must not be included in `_DEFAULT_REGISTRY`, manifest export, classifier output, or planner output until behavior probes pass and a later plan patch promotes them.

Wrapper-synthesized create values with no caller/envelope request key are not active positive rows. They are exported under [Wrapper Create Derivation Registry](#wrapper-create-derivation-registry) and may have matching non-requestable diagnostic denial rows.

| rule_id | subject_family_id | subject_path | request_raw_key | policy_path | output_paths | disposition | owner | caller_writable | value_policy_id | gate | group_shape_hint | refs |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `supported.capture.create.title` | `subject.capture.create` | `capture.input.title` | `title` | `capture.ticket.title` | `frontmatter.title`, `filename.slug` | `SUPPORTED` | `PROJECT` | true | `value.non_empty_string` | `APPLY_CONSENT` | `CAPTURE_CREATE` | `capture.allowed_fields`, `capture.mapping` |
| `supported.capture.create.captured_request` | `subject.capture.create` | `capture.input.captured_request` | `captured_request` | `capture.ticket.captured_request` | `section.captured_request` | `SUPPORTED` | `PROJECT` | true | `value.non_empty_string` | `APPLY_CONSENT` | `CAPTURE_CREATE` | `capture.mapping`, `contract.schema` |
| `supported.capture.create.problem` | `subject.capture.create` | `capture.input.problem` | `problem` | `capture.ticket.problem` | `section.problem` | `SUPPORTED` | `PROJECT` | true | `value.non_empty_string` | `APPLY_CONSENT` | `CAPTURE_CREATE` | `capture.mapping`, `engine.create` |
| `supported.capture.create.next_action` | `subject.capture.create` | `capture.input.next_action` | `next_action` | `capture.ticket.next_action` | `section.next_action` | `SUPPORTED` | `PROJECT` | true | `value.non_empty_string` | `APPLY_CONSENT` | `CAPTURE_CREATE` | `capture.mapping` |
| `supported.capture.create.capture_confidence` | `subject.capture.create` | `capture.input.capture_confidence` | `capture_confidence` | `capture.ticket.capture_confidence` | `frontmatter.capture_confidence` | `SUPPORTED` | `WRAPPER` | true | `value.capture_confidence` | `APPLY_CONSENT` | `CAPTURE_CREATE` | `validate.constants`, `capture.mapping`, `capture.tests` |
| `supported.capture.create.priority` | `subject.capture.create` | `capture.input.priority` | `priority` | `capture.ticket.priority` | `frontmatter.priority` | `SUPPORTED` | `WRAPPER` | true | `value.priority` | `APPLY_CONSENT` | `CAPTURE_CREATE` | `capture.mapping`, `capture.tests` |
| `supported.capture.create.tags` | `subject.capture.create` | `capture.input.tags` | `tags` | `capture.ticket.tags` | `frontmatter.tags` | `SUPPORTED` | `WRAPPER` | true | `value.capture_tags` | `APPLY_CONSENT` | `CAPTURE_CREATE` | `validate.constants`, `capture.mapping` |
| `supported.capture.create.component` | `subject.capture.create` | `capture.input.component` | `component` | `capture.ticket.component` | `frontmatter.component` | `SUPPORTED` | `PROJECT` | true | `value.any_string` | `APPLY_CONSENT` | `CAPTURE_CREATE` | `capture.mapping`, `contract.schema` |
| `supported.capture.create.related_paths` | `subject.capture.create` | `capture.input.related_paths` | `related_paths` | `capture.ticket.related_paths` | `frontmatter.related_paths` | `SUPPORTED` | `PROJECT` | true | `value.path_list` | `APPLY_CONSENT` | `CAPTURE_CREATE` | `capture.mapping`, `contract.schema` |
| `supported.capture.create.acceptance_criteria` | `subject.capture.create` | `capture.input.acceptance_criteria` | `acceptance_criteria` | `capture.ticket.acceptance_criteria` | `section.acceptance_criteria` | `SUPPORTED` | `PROJECT` | true | `value.acceptance_criteria` | `APPLY_CONSENT` | `CAPTURE_CREATE` | `capture.mapping`, `contract.schema` |
| `supported.capture.create.refinement_status` | `subject.capture.create` | `capture.input.refinement_status` | `refinement_status` | `capture.ticket.refinement_status` | `frontmatter.refinement_status` | `SUPPORTED` | `WRAPPER` | true | `value.refinement_status` | `APPLY_CONSENT` | `CAPTURE_CREATE` | `validate.constants`, `capture.mapping` |
| `supported.capture.create.capture_source` | `subject.capture.create` | `capture.input.capture_source` | `capture_source` | `capture.ticket.capture_source` | `frontmatter.capture_source` | `SUPPORTED` | `WRAPPER` | false | `value.overwritten_input_any` | `APPLY_CONSENT` | `CAPTURE_CREATE` | `capture.allowed_fields`, `capture.mapping`, `capture.tests`; wrapper behavior proof gate required |
| `supported.ingest.create.envelope_version` | `subject.ingest.create` | `ingest.envelope.envelope_version` | `envelope_version` | `ingest.envelope.version` | none | `SUPPORTED` | `ENVELOPE` | true | `value.envelope_version_1_0` | `APPLY_CONSENT` | `INGEST_CREATE` | `contract.envelope`, `envelope.schema` |
| `supported.ingest.create.title` | `subject.ingest.create` | `ingest.envelope.title` | `title` | `ingest.ticket.title` | `frontmatter.title`, `filename.slug` | `SUPPORTED` | `ENVELOPE` | true | `value.non_empty_string` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.ingest.create.problem` | `subject.ingest.create` | `ingest.envelope.problem` | `problem` | `ingest.ticket.problem` | `section.problem` | `SUPPORTED` | `ENVELOPE` | true | `value.non_empty_string` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.ingest.create.source` | `subject.ingest.create` | `ingest.envelope.source` | `source` | `ingest.ticket.source` | `frontmatter.source` | `SUPPORTED` | `ENVELOPE` | true | `value.source_object` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.ingest.create.emitted_at` | `subject.ingest.create` | `ingest.envelope.emitted_at` | `emitted_at` | `ingest.defer.deferred_at` | `frontmatter.defer.deferred_at` | `SUPPORTED` | `ENVELOPE` | true | `value.non_empty_string` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.ingest.create.context` | `subject.ingest.create` | `ingest.envelope.context` | `context` | `ingest.ticket.context` | `section.context` | `SUPPORTED` | `ENVELOPE` | true | `value.any_string` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.ingest.create.prior_investigation` | `subject.ingest.create` | `ingest.envelope.prior_investigation` | `prior_investigation` | `ingest.ticket.prior_investigation` | `section.prior_investigation` | `SUPPORTED` | `ENVELOPE` | true | `value.any_string` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.ingest.create.approach` | `subject.ingest.create` | `ingest.envelope.approach` | `approach` | `ingest.ticket.approach` | `section.approach` | `SUPPORTED` | `ENVELOPE` | true | `value.any_string` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.ingest.create.acceptance_criteria` | `subject.ingest.create` | `ingest.envelope.acceptance_criteria` | `acceptance_criteria` | `ingest.ticket.acceptance_criteria` | `section.acceptance_criteria` | `SUPPORTED` | `ENVELOPE` | true | `value.acceptance_criteria` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.ingest.create.verification` | `subject.ingest.create` | `ingest.envelope.verification` | `verification` | `ingest.ticket.verification` | `section.verification` | `SUPPORTED` | `ENVELOPE` | true | `value.any_string` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.ingest.create.key_files` | `subject.ingest.create` | `ingest.envelope.key_files` | `key_files` | `ingest.ticket.key_files` | `section.key_files` | `SUPPORTED` | `ENVELOPE` | true | `value.key_files` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.ingest.create.key_file_paths` | `subject.ingest.create` | `ingest.envelope.key_file_paths` | `key_file_paths` | `ingest.ticket.key_file_paths` | `frontmatter.key_file_paths` | `SUPPORTED` | `ENVELOPE` | true | `value.path_list` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.ingest.create.suggested_priority` | `subject.ingest.create` | `ingest.envelope.suggested_priority` | `suggested_priority` | `ingest.ticket.priority` | `frontmatter.priority` | `SUPPORTED` | `ENVELOPE` | true | `value.priority` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.ingest.create.suggested_tags` | `subject.ingest.create` | `ingest.envelope.suggested_tags` | `suggested_tags` | `ingest.ticket.tags` | `frontmatter.tags` | `SUPPORTED` | `ENVELOPE` | true | `value.string_list` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.ingest.create.effort` | `subject.ingest.create` | `ingest.envelope.effort` | `effort` | `ingest.ticket.effort` | `frontmatter.effort` | `SUPPORTED` | `ENVELOPE` | true | `value.any_string` | `APPLY_CONSENT` | `INGEST_CREATE` | `envelope.schema`, `envelope.mapping` |
| `supported.update.frontmatter.priority` | `subject.update.frontmatter` | `update.frontmatter.priority` | `priority` | `update.ticket.priority` | `frontmatter.priority` | `SUPPORTED` | `PROJECT` | true | `value.priority` | `APPLY_CONSENT` | `UPDATE_FRONTMATTER` | `update.allowed_fields`, `engine.update` |
| `supported.update.frontmatter.component` | `subject.update.frontmatter` | `update.frontmatter.component` | `component` | `update.ticket.component` | `frontmatter.component` | `SUPPORTED` | `PROJECT` | true | `value.any_string` | `APPLY_CONSENT` | `UPDATE_FRONTMATTER` | `update.allowed_fields`, `engine.update` |
| `supported.update.frontmatter.related_paths` | `subject.update.frontmatter` | `update.frontmatter.related_paths` | `related_paths` | `update.ticket.related_paths` | `frontmatter.related_paths` | `SUPPORTED` | `PROJECT` | true | `value.path_list` | `APPLY_CONSENT` | `UPDATE_FRONTMATTER` | `update.allowed_fields`, `engine.update` |
| `supported.update.frontmatter.blocked_by` | `subject.update.frontmatter` | `update.frontmatter.blocked_by` | `blocked_by` | `update.ticket.blocked_by` | `frontmatter.blocked_by` | `SUPPORTED` | `PROJECT` | true | `value.string_list` | `APPLY_CONSENT` | `UPDATE_FRONTMATTER` | `update.allowed_fields`, `engine.update` |
| `supported.update.frontmatter.blocks` | `subject.update.frontmatter` | `update.frontmatter.blocks` | `blocks` | `update.ticket.blocks` | `frontmatter.blocks` | `SUPPORTED` | `PROJECT` | true | `value.string_list` | `APPLY_CONSENT` | `UPDATE_FRONTMATTER` | `update.allowed_fields`, `engine.update` |
| `supported.update.frontmatter.tags` | `subject.update.frontmatter` | `update.frontmatter.tags` | `tags` | `update.ticket.tags` | `frontmatter.tags` | `SUPPORTED` | `PROJECT` | true | `value.string_list` | `APPLY_CONSENT` | `UPDATE_FRONTMATTER` | `update.allowed_fields`, `update.refinement`, `engine.update` |
| `supported.update.focused.problem` | `subject.update.focused` | `update.focused.problem` | `problem` | `update.ticket.problem` | `section.problem` | `SUPPORTED` | `PROJECT` | true | `value.non_empty_string` | `APPLY_CONSENT` | `UPDATE_FOCUSED_REFINEMENT` | `update.allowed_fields`, `update.refinement`, `engine.update` |
| `supported.update.focused.next_action` | `subject.update.focused` | `update.focused.next_action` | `next_action` | `update.ticket.next_action` | `section.next_action` | `SUPPORTED` | `PROJECT` | true | `value.non_empty_string` | `APPLY_CONSENT` | `UPDATE_FOCUSED_REFINEMENT` | `update.allowed_fields`, `engine.update` |
| `supported.update.focused.acceptance_criteria` | `subject.update.focused` | `update.focused.acceptance_criteria` | `acceptance_criteria` | `update.ticket.acceptance_criteria` | `section.acceptance_criteria` | `SUPPORTED` | `PROJECT` | true | `value.acceptance_criteria` | `APPLY_CONSENT` | `UPDATE_FOCUSED_REFINEMENT` | `update.allowed_fields`, `update.refinement`, `engine.update` |
| `supported.update.lifecycle.status.open_to_in_progress` | `subject.update.lifecycle.status` | `update.lifecycle.status` | `status` | `update.ticket.status` | `frontmatter.status` | `SUPPORTED` | `PROJECT` | true | `value.status_target` | `APPLY_CONSENT` | `UPDATE_STATUS_LIFECYCLE` | `engine.transitions` |
| `supported.update.lifecycle.status.in_progress_to_open` | `subject.update.lifecycle.status` | `update.lifecycle.status` | `status` | `update.ticket.status` | `frontmatter.status` | `SUPPORTED` | `PROJECT` | true | `value.status_target` | `APPLY_CONSENT` | `UPDATE_STATUS_OPEN_EXCLUSIVE` | `update.mapping`, `engine.transitions` |
| `precondition.update.lifecycle.status.to_blocked` | `subject.update.lifecycle.status` | `update.lifecycle.status` | `status` | `update.ticket.status` | `frontmatter.status` | `PRECONDITION_REQUIRED` | `PROJECT` | false | `value.status_target` | `UNSUPPORTED` | `UPDATE_STATUS_LIFECYCLE` | `engine.transitions` |
| `precondition.update.lifecycle.status.blocked_to_open` | `subject.update.lifecycle.status` | `update.lifecycle.status` | `status` | `update.ticket.status` | `frontmatter.status` | `PRECONDITION_REQUIRED` | `PROJECT` | false | `value.status_target` | `UNSUPPORTED` | `UPDATE_STATUS_OPEN_EXCLUSIVE` | `update.mapping`, `engine.transitions` |
| `precondition.update.lifecycle.status.blocked_to_in_progress` | `subject.update.lifecycle.status` | `update.lifecycle.status` | `status` | `update.ticket.status` | `frontmatter.status` | `PRECONDITION_REQUIRED` | `PROJECT` | false | `value.status_target` | `UNSUPPORTED` | `UPDATE_STATUS_LIFECYCLE` | `engine.transitions` |
| `noop.candidate.update.lifecycle.status.same_open` | `subject.update.lifecycle.status` | `update.lifecycle.status` | `status` | `update.ticket.status` | none | `NO_OP` | `PROJECT` | false | `value.status_target` | `UNSUPPORTED` | `UPDATE_STATUS_OPEN_EXCLUSIVE` | `update.mapping`, `engine.update`; probe-gated |
| `noop.candidate.update.lifecycle.status.same_in_progress` | `subject.update.lifecycle.status` | `update.lifecycle.status` | `status` | `update.ticket.status` | none | `NO_OP` | `PROJECT` | false | `value.status_target` | `UNSUPPORTED` | `UPDATE_STATUS_LIFECYCLE` | `engine.update`; probe-gated |
| `noop.candidate.update.lifecycle.status.same_blocked` | `subject.update.lifecycle.status` | `update.lifecycle.status` | `status` | `update.ticket.status` | none | `NO_OP` | `PROJECT` | false | `value.status_target` | `UNSUPPORTED` | `UPDATE_STATUS_LIFECYCLE` | `engine.update`; probe-gated |
| `precondition.update.close.status.done` | `subject.update.close.status` | `update.lifecycle.status` | `status` | `update.ticket.close.done` | `frontmatter.status` | `PRECONDITION_REQUIRED` | `PROJECT` | false | `value.close_status_target` | `UNSUPPORTED` | `UPDATE_CLOSE` | `update.mapping`, `engine.close` |
| `precondition.update.close.status.wontfix` | `subject.update.close.status` | `update.lifecycle.status` | `status` | `update.ticket.close.wontfix` | `frontmatter.status` | `PRECONDITION_REQUIRED` | `PROJECT` | false | `value.close_status_target` | `UNSUPPORTED` | `UPDATE_CLOSE` | `update.mapping`, `engine.close` |
| `precondition.update.reopen.status.open` | `subject.update.lifecycle.reopen_reason` | `update.lifecycle.status` | `status` | `update.ticket.reopen.status` | `frontmatter.status` | `PRECONDITION_REQUIRED` | `PROJECT` | false | `value.status_target` | `UNSUPPORTED` | `UPDATE_REOPEN` | `update.mapping`, `engine.reopen` |
| `precondition.update.reopen.reopen_reason` | `subject.update.lifecycle.reopen_reason` | `update.lifecycle.reopen_reason` | `reopen_reason` | `update.ticket.reopen.reason` | none | `PRECONDITION_REQUIRED` | `PROJECT` | false | `value.non_empty_string` | `UNSUPPORTED` | `UPDATE_REOPEN` | `update.mapping`, `engine.reopen` |

Every active request-subject row has `request_raw_key`. Rows with the same surface and `subject_path` must agree on `request_raw_key` unless the row declares an explicit value-dependent exception in the lifecycle match table below. Wrapper-derived rows and create derivations must not claim caller raw keys.

`request_raw_key` is the raw payload key used by `RawShapeDiscriminator.raw_keys`; `subject_path` is the normalized policy subject. The registry may derive private lookup tables from these authored columns, but a separate subject-to-raw-key table is not a second source of truth.

Lifecycle rows use these current-state and value predicates:

| rule_id | raw_group_shape_hint | current_status_condition | value_condition |
| --- | --- | --- | --- |
| `supported.update.lifecycle.status.open_to_in_progress` | `UPDATE_STATUS_LIFECYCLE` | `current.status == "open"` | `value == "in_progress"` |
| `supported.update.lifecycle.status.in_progress_to_open` | `UPDATE_STATUS_OPEN_EXCLUSIVE` | `current.status == "in_progress"` | `value == "open"` |
| `precondition.update.lifecycle.status.to_blocked` | `UPDATE_STATUS_LIFECYCLE` | `current.status in {"open", "in_progress"}` | `value == "blocked"` |
| `precondition.update.lifecycle.status.blocked_to_open` | `UPDATE_STATUS_OPEN_EXCLUSIVE` | `current.status == "blocked"` | `value == "open"` |
| `precondition.update.lifecycle.status.blocked_to_in_progress` | `UPDATE_STATUS_LIFECYCLE` | `current.status == "blocked"` | `value == "in_progress"` |
| `noop.candidate.update.lifecycle.status.same_open` | `UPDATE_STATUS_OPEN_EXCLUSIVE` | `current.status == "open"` | `value == "open"` |
| `noop.candidate.update.lifecycle.status.same_in_progress` | `UPDATE_STATUS_LIFECYCLE` | `current.status == "in_progress"` | `value == "in_progress"` |
| `noop.candidate.update.lifecycle.status.same_blocked` | `UPDATE_STATUS_LIFECYCLE` | `current.status == "blocked"` | `value == "blocked"` |
| `precondition.update.close.status.done` | `UPDATE_CLOSE` | `current.status in {"open", "in_progress", "blocked"}` | `value == "done"` |
| `precondition.update.close.status.wontfix` | `UPDATE_CLOSE` | `current.status in {"open", "in_progress", "blocked"}` | `value == "wontfix"` |
| `precondition.update.reopen.status.open` | `UPDATE_STATUS_OPEN_EXCLUSIVE` | `current.status in {"done", "wontfix"}` | `value == "open"` |
| `precondition.update.reopen.reopen_reason` | `UPDATE_STATUS_OPEN_EXCLUSIVE` | `current.status in {"done", "wontfix"}` | `reopen_reason` is non-empty string |

### Authored Invalid, Context, Unsupported, And No-Op Rows

These rows are exported in `policy["rules"]` and referenced by active subject, family, wrapper-derivation, or value-policy rows.

| rule_id | stage | subject_family_id | match | required_context_fields | disposition | reason_code | group_shape_hint | anchors/tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `invalid.shared.any_string` | `INVALID_VALUE` | shared | value present and not string | none | `UNSUPPORTED` | `invalid_string_value` | `UNSUPPORTED_NO_GROUP_SHAPE` | `validate.constants`, `envelope.schema` |
| `invalid.shared.non_empty_string` | `INVALID_VALUE` | shared | value not non-empty string | none | `UNSUPPORTED` | `invalid_non_empty_string` | `UNSUPPORTED_NO_GROUP_SHAPE` | `capture.mapping`, `envelope.schema` |
| `invalid.shared.priority` | `INVALID_VALUE` | shared | not in `vocab.priority` | none | `UNSUPPORTED` | `invalid_priority_value` | caller row hint | `validate.constants` |
| `invalid.shared.string_list` | `INVALID_VALUE` | shared | not list of strings | none | `UNSUPPORTED` | `invalid_string_list_value` | caller row hint | `validate.constants` |
| `invalid.shared.path_list` | `INVALID_VALUE` | shared | not list of strings | none | `UNSUPPORTED` | `invalid_path_list_value` | caller row hint | `validate.constants`, `envelope.schema` |
| `invalid.shared.source_object` | `INVALID_VALUE` | shared | source is not object with string `type`, `ref`, `session` | none | `UNSUPPORTED` | `invalid_source_object` | caller row hint | `validate.constants`, `envelope.schema` |
| `invalid.shared.acceptance_criteria` | `INVALID_VALUE` | shared | acceptance criteria is not list of strings | none | `UNSUPPORTED` | `invalid_acceptance_criteria` | caller row hint | `validate.constants`, `envelope.schema` |
| `invalid.shared.boolean` | `INVALID_VALUE` | shared | value is not boolean | none | `UNSUPPORTED` | `invalid_boolean_value` | caller row hint | `validate.constants` |
| `invalid.ingest.envelope.envelope_version.value` | `INVALID_VALUE` | `subject.ingest.create` | envelope_version is not exactly `"1.0"` | none | `UNSUPPORTED` | `invalid_envelope_version` | `INGEST_CREATE` | `envelope.schema`, `contract.envelope` |
| `invalid.capture.create.capture_confidence.value` | `INVALID_VALUE` | `subject.capture.create` | not in `vocab.capture_confidence` | none | `UNSUPPORTED` | `invalid_capture_confidence` | `CAPTURE_CREATE` | `validate.constants`, `capture.tests` |
| `invalid.capture.create.refinement_status.value` | `INVALID_VALUE` | `subject.capture.create` | not `needs_refinement` | none | `UNSUPPORTED` | `invalid_refinement_status` | `CAPTURE_CREATE` | `validate.constants` |
| `invalid.capture.create.tags.value` | `INVALID_VALUE` | `subject.capture.create` | tags not list of controlled capture tags | none | `UNSUPPORTED` | `invalid_capture_tags` | `CAPTURE_CREATE` | `validate.constants`, `capture.mapping` |
| `invalid.update.lifecycle.status.value` | `INVALID_VALUE` | `subject.update.lifecycle.status` | not in `vocab.status.all` | none | `UNSUPPORTED` | `invalid_status_target` | `UPDATE_STATUS_LIFECYCLE` | `validate.constants`, `engine.transitions` |
| `invalid.update.close.status.value` | `INVALID_VALUE` | `subject.update.close.status` | not in `vocab.close_resolution` | none | `UNSUPPORTED` | `invalid_close_status_target` | `UPDATE_CLOSE` | `validate.constants`, `engine.close` |
| `invalid.ingest.derived.defer.value` | `INVALID_VALUE` | `subject.ingest.create` | derived defer does not match expected object shape | none | `UNSUPPORTED` | `invalid_derived_defer` | `INGEST_CREATE` | `envelope.mapping` |
| `invalid.ingest.envelope.key_files.value` | `INVALID_VALUE` | `subject.ingest.create` | key_files not list of required-key objects | none | `UNSUPPORTED` | `invalid_key_files` | `INGEST_CREATE` | `envelope.schema` |
| `context.update.lifecycle.status.current_status` | `CONTEXT_REQUIRED` | `subject.update.lifecycle.status` | current status missing | `current.status` | `CONTEXT_REQUIRED` | `context_required_current_status` | `UNRESOLVED_CONTEXT_REQUIRED` | `engine.transitions` |
| `context.update.lifecycle.reopen_reason.current_status` | `CONTEXT_REQUIRED` | `subject.update.lifecycle.reopen_reason` | current status missing | `current.status` | `CONTEXT_REQUIRED` | `context_required_reopen_status` | `UNRESOLVED_CONTEXT_REQUIRED` | `engine.reopen` |
| `context.update.frontmatter.tags.refinement_state` | `CONTEXT_REQUIRED` | `subject.update.frontmatter` | tags value valid but current refinement/tag state missing | `current.refinement_status`, `current.tags` | `CONTEXT_REQUIRED` | `context_required_refinement_tag_state` | `UNRESOLVED_CONTEXT_REQUIRED` | `update.refinement`, `update.tests` |
| `unsupported.update.frontmatter.tags.remove_needs_refinement_standalone` | `SPECIFIC_UNSUPPORTED` | `subject.update.frontmatter` | current refinement active, current tags contain `needs-refinement`, requested tags omit it, and no focused-refinement cleanup group applies | none | `UNSUPPORTED` | `standalone_needs_refinement_tag_removal_not_supported` | `UPDATE_FRONTMATTER` | `update.refinement`, `update.tests` |
| `unsupported.capture.derived.source.not_requestable` | `SPECIFIC_UNSUPPORTED` | `subject.capture.create` | caller targets exported wrapper-derived `capture.derived.source` | none | `UNSUPPORTED` | `subject_not_requestable_wrapper_derived_value` | `UNSUPPORTED_NO_GROUP_SHAPE` | `capture.mapping`, `engine.create` |
| `unsupported.capture.derived.acceptance_criteria_default.not_requestable` | `SPECIFIC_UNSUPPORTED` | `subject.capture.create` | caller targets exported wrapper-derived `capture.derived.acceptance_criteria_default` | none | `UNSUPPORTED` | `subject_not_requestable_wrapper_derived_value` | `UNSUPPORTED_NO_GROUP_SHAPE` | `capture.mapping`, `validate.constants` |
| `unsupported.ingest.derived.defer.not_requestable` | `SPECIFIC_UNSUPPORTED` | `subject.ingest.create` | caller targets exported wrapper-derived `ingest.derived.defer` | none | `UNSUPPORTED` | `subject_not_requestable_wrapper_derived_value` | `UNSUPPORTED_NO_GROUP_SHAPE` | `envelope.mapping`, `contract.envelope` |
| `unsupported.ingest.derived.priority_default.not_requestable` | `SPECIFIC_UNSUPPORTED` | `subject.ingest.create` | caller targets exported wrapper-derived `ingest.derived.priority_default` | none | `UNSUPPORTED` | `subject_not_requestable_wrapper_derived_value` | `UNSUPPORTED_NO_GROUP_SHAPE` | `envelope.mapping`, `contract.envelope` |
| `unsupported.ingest.derived.tags_default.not_requestable` | `SPECIFIC_UNSUPPORTED` | `subject.ingest.create` | caller targets exported wrapper-derived `ingest.derived.tags_default` | none | `UNSUPPORTED` | `subject_not_requestable_wrapper_derived_value` | `UNSUPPORTED_NO_GROUP_SHAPE` | `envelope.mapping`, `contract.envelope` |
| `unsupported.update.close.status.same_terminal` | `SPECIFIC_UNSUPPORTED` | `subject.update.close.status` | current status already equals requested terminal status | none | `UNSUPPORTED` | `status_target_already_current` | `UPDATE_CLOSE` | `engine.close`; behavior test required |
| `unsupported.capture.create.unregistered_subject` | `SPECIFIC_UNSUPPORTED` | `subject.capture.create` | well-formed unknown capture subject | none | `UNSUPPORTED` | `unregistered_subject` | `UNSUPPORTED_NO_GROUP_SHAPE` | `capture.allowed_fields` |
| `unsupported.ingest.create.unregistered_subject` | `SPECIFIC_UNSUPPORTED` | `subject.ingest.create` | well-formed unknown ingest subject | none | `UNSUPPORTED` | `unregistered_subject` | `UNSUPPORTED_NO_GROUP_SHAPE` | `envelope.schema` |
| `unsupported.update.frontmatter.unregistered_subject` | `SPECIFIC_UNSUPPORTED` | `subject.update.frontmatter` | well-formed unknown update frontmatter subject | none | `UNSUPPORTED` | `unregistered_subject` | `UNSUPPORTED_NO_GROUP_SHAPE` | `update.allowed_fields` |
| `unsupported.update.focused.unregistered_subject` | `SPECIFIC_UNSUPPORTED` | `subject.update.focused` | well-formed unknown focused subject | none | `UNSUPPORTED` | `unregistered_subject` | `UNSUPPORTED_NO_GROUP_SHAPE` | `update.allowed_fields` |
| `unsupported.update.lifecycle.status.unmatched` | `SPECIFIC_UNSUPPORTED` | `subject.update.lifecycle.status` | known status subject but no transition row matched | none | `UNSUPPORTED` | `status_transition_not_supported` | `UPDATE_STATUS_LIFECYCLE` | `engine.transitions` |
| `unsupported.update.close.unregistered_subject` | `SPECIFIC_UNSUPPORTED` | `subject.update.close.status` | close shape with non-status subject | none | `UNSUPPORTED` | `unregistered_subject` | `UPDATE_CLOSE` | `update.mapping` |
| `unsupported.update.reopen.unregistered_subject` | `SPECIFIC_UNSUPPORTED` | `subject.update.lifecycle.reopen_reason` | reopen shape with unsupported subject | none | `UNSUPPORTED` | `unregistered_subject` | `UPDATE_REOPEN` | `update.mapping` |
| `unsupported.capture.non_create_mutation` | shape stop | none | capture non-create shape | none | `UNSUPPORTED` | `surface_action_operation_not_supported` | `UNSUPPORTED_NO_GROUP_SHAPE` | `capture.allowed_fields` |
| `unsupported.ingest.non_create_mutation` | shape stop | none | ingest non-create shape | none | `UNSUPPORTED` | `surface_action_operation_not_supported` | `UNSUPPORTED_NO_GROUP_SHAPE` | `envelope.mapping` |
| `unsupported.update.unsupported_action_operation` | shape stop | none | unsupported update action/operation combination | none | `UNSUPPORTED` | `surface_action_operation_not_supported` | `UNSUPPORTED_NO_GROUP_SHAPE` | `update.mapping` |

NO_OP candidate rules are authored plan rows but may not appear in `_DEFAULT_REGISTRY` or exported current-behavior manifest rows until the behavior probes listed in [Behavior Probe Gates](#behavior-probe-gates) pass. If a probe fails, patch this table to the observed unsupported or effect behavior before implementation continues.

### Explicit Out-Of-Surface Exclusions

These exclusions prevent lower-engine capabilities from widening wrapper authority.

| exclusion_id | surface | excluded subject/pattern | reason | anchors/tests |
| --- | --- | --- | --- | --- |
| `exclusion.capture.engine_only_create_fields` | `capture` | `effort`, `key_files`, `key_file_paths`, `context`, `prior_investigation`, `approach`, `verification`, `decisions_made`, `related`, `defer` | engine create can render these, but `ticket_capture.py` does not accept them as capture subjects | `capture.allowed_fields`, `capture.tests` |
| `exclusion.capture.raw_wording_fields` | `capture` | `raw_user_text`, `raw_request`, `transcript_excerpt` at any nested path | wrapper rejects raw wording fields | `capture.allowed_fields`, `capture.tests` |
| `exclusion.update.engine_only_fields` | `update` | `source`, `defer`, `capture_source`, `capture_confidence`, `refinement_status`, `effort`, `key_file_paths`, `key_files`, `context`, `prior_investigation`, `approach`, `verification`, `decisions_made`, `related` | not accepted by `ticket_update.py` current wrapper | `update.allowed_fields`, `engine.update` |
| `exclusion.update.close.archive` | `update` | `archive` under wrapper close payload | wrapper lifecycle close rejects extra fields; any direct-engine archive difference is only a behavior-probe candidate | `update.mapping`, `engine.close`; discrepancy row only if behavior test proves and admission criteria pass |
| `exclusion.update.close.resolution` | `update` | `resolution` under wrapper update payload | wrapper close uses `status=done/wontfix`; direct-engine resolution behavior is not wrapper policy | `update.mapping`, `engine.close` |
| `exclusion.ingest.unknown_envelope_fields` | `ingest` | any envelope field outside `_REQUIRED_FIELDS + _OPTIONAL_FIELDS` | closed envelope schema | `contract.envelope`, `envelope.schema` |

### Wrapper Create Derivation Registry

Wrapper create derivations are pre-engine wrapper decisions. They are part of the exported current-behavior policy surface, but they are not caller/envelope request subjects and must not be returned as supported local subjects by `classify_mutation()`.

Wrapper derivations are exported under `policy["create_derivations"]`. Each exported derivation path that is also a public `SubjectPath` namespace has a matching non-requestable diagnostic denial row in `policy["rules"]`.

Wrapper derivations must not be active supported subjects, engine materialization rows, or lane effects.

| derivation_id | trigger_group_shape | derived_path | trigger | decision_owner | write_owner | caller_requestable | value_policy_id | value_flow_id | manifest_surface | diagnostic_rule_id | anchors/tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `derive.capture.create.source` | `CAPTURE_CREATE` | `frontmatter.source` | every capture create | `WRAPPER` | `ENGINE` | false | `value.source_object` | `flow.wrapper_synthesizes_source_object` | `policy["create_derivations"]` | `unsupported.capture.derived.source.not_requestable` | `capture.mapping`, `engine.create` |
| `derive.capture.create.acceptance_criteria_default` | `CAPTURE_CREATE` | `section.acceptance_criteria` | `capture.input.acceptance_criteria` missing | `WRAPPER` | `ENGINE` | false | `value.acceptance_criteria` | `flow.wrapper_defaults_capture_acceptance_criteria_if_missing` | `policy["create_derivations"]` | `unsupported.capture.derived.acceptance_criteria_default.not_requestable` | `capture.mapping`, `validate.constants` |
| `derive.ingest.create.defer` | `INGEST_CREATE` | `frontmatter.defer` | every ingest create from validated envelope | `WRAPPER` | `ENGINE` | false | `value.defer_object` | `flow.wrapper_synthesizes_defer_object` | `policy["create_derivations"]` | `unsupported.ingest.derived.defer.not_requestable` | `envelope.mapping`, `contract.envelope` |
| `derive.ingest.create.priority_default` | `INGEST_CREATE` | `frontmatter.priority` | `ingest.envelope.suggested_priority` missing | `WRAPPER` | `ENGINE` | false | `value.priority` | `flow.wrapper_defaults_ingest_priority_if_missing` | `policy["create_derivations"]` | `unsupported.ingest.derived.priority_default.not_requestable` | `envelope.mapping`, `contract.envelope` |
| `derive.ingest.create.tags_default` | `INGEST_CREATE` | `frontmatter.tags` | `ingest.envelope.suggested_tags` missing | `WRAPPER` | `ENGINE` | false | `value.string_list` | `flow.wrapper_defaults_ingest_tags_if_missing` | `policy["create_derivations"]` | `unsupported.ingest.derived.tags_default.not_requestable` | `envelope.mapping`, `contract.envelope` |

`derive.capture.create.acceptance_criteria_default` uses this exact current value rule:

```text
if refinement_status == needs_refinement:
  ["Needs refinement"]
else:
  [next_action]
```

### Create Materialization Registry

Engine materialized outputs document created-ticket shape but are not caller request subjects.

| materialization_id | surfaces | materialized_path | authority_owner | caller_writable | engine_managed | value_policy | manifest_surface | anchors/tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `materialize.create.id` | `capture`, `ingest` | `frontmatter.id` | `ENGINE` | false | true | `engine_generated_ticket_id` | `policy["materialization"]` only | `engine.create` |
| `materialize.create.date` | `capture`, `ingest` | `frontmatter.date` | `ENGINE` | false | true | `engine_current_date` | `policy["materialization"]` only | `engine.create`, `contract.schema` |
| `materialize.create.created_at` | `capture`, `ingest` | `frontmatter.created_at` | `ENGINE` | false | true | `engine_current_utc_timestamp` | `policy["materialization"]` only | `engine.create`, `contract.schema` |
| `materialize.create.status_open` | `capture`, `ingest` | `frontmatter.status` | `ENGINE` | false | true | `engine_defaulted_open` | `policy["materialization"]` only | `engine.create`, `contract.schema`, `contract.envelope` |
| `materialize.create.contract_version` | `capture`, `ingest` | `frontmatter.contract_version` | `ENGINE` | false | true | `engine_constant_current_contract` | `policy["materialization"]` only | `engine.create`, `contract.schema` |

### Update And Lifecycle Effect Registry

Derived writes that happen because a grouped lane executes are lane effects, not active subject rows. Rows in this registry must never be returned by `classify_mutation()` as supported subjects and must never create standalone lanes.

| effect_id | trigger_group_shape | effect | effect_paths | requestable | decision_owner | write_owner | value_policy | manifest_surface | anchors/tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `effect.capture.create.creates_ticket` | `CAPTURE_CREATE` | `CREATES_TICKET` | ticket markdown file | false | `WRAPPER` | `ENGINE` | created through engine create | `ManifestLane.effects` | `capture.mapping`, `engine.create` |
| `effect.ingest.create.creates_ticket` | `INGEST_CREATE` | `CREATES_TICKET` | ticket markdown file | false | `WRAPPER` | `ENGINE` | created through ingest pipeline | `ManifestLane.effects` | `envelope.mapping`, `engine.create` |
| `effect.update.frontmatter.updates_frontmatter` | `UPDATE_FRONTMATTER` | `UPDATES_FRONTMATTER` | `frontmatter.priority`, `frontmatter.tags`, `frontmatter.component`, `frontmatter.related_paths`, `frontmatter.blocked_by`, `frontmatter.blocks` | false | `WRAPPER` | `ENGINE` | caller fields after policy | `ManifestLane.effects` | `update.mapping`, `engine.update` |
| `effect.update.focused.updates_sections` | `UPDATE_FOCUSED_REFINEMENT` | `UPDATES_FOCUSED_REFINEMENT_SECTIONS` | `section.problem`, `section.next_action`, `section.acceptance_criteria` | false | `WRAPPER` | `ENGINE` | caller fields after policy | `ManifestLane.effects` | `update.mapping`, `engine.update` |
| `effect.update.focused.metadata_coactions` | `UPDATE_FOCUSED_REFINEMENT` | `UPDATES_FRONTMATTER` | `frontmatter.priority`, `frontmatter.tags`, `frontmatter.component`, `frontmatter.related_paths`, `frontmatter.blocked_by`, `frontmatter.blocks` | false | `WRAPPER` | `ENGINE` | metadata co-actions | `ManifestLane.effects` | `update.mapping`, `engine.update`; behavior test required |
| `effect.update.focused.clears_refinement_marker` | `UPDATE_FOCUSED_REFINEMENT` | `CLEARS_REFINEMENT_MARKER` | `frontmatter.refinement_status`, `frontmatter.tags[needs-refinement]` | false | `WRAPPER` | `ENGINE` | derived when problem, next_action, and acceptance_criteria are concrete | `ManifestLane.effects` | `update.refinement`, `engine.update`, `update.tests` |
| `effect.update.status.sets_nonterminal_status` | `UPDATE_STATUS_LIFECYCLE` | `UPDATES_FRONTMATTER` | `frontmatter.status` | false | `WRAPPER` | `ENGINE` | lifecycle transition | `ManifestLane.effects` | `engine.transitions`, `engine.update` |
| `effect.update.status.may_affect_close_readiness` | `UPDATE_STATUS_LIFECYCLE` | `MAY_AFFECT_CLOSE_READINESS` | ticket graph/readiness state | false | `WRAPPER` | `ENGINE` | derived status readiness effect | `ManifestLane.effects` | `engine.transitions` |
| `effect.update.close.sets_terminal_status` | `UPDATE_CLOSE` | `SETS_TERMINAL_STATUS` | `frontmatter.status` | false | `WRAPPER` | `ENGINE` | close transition | `ManifestLane.effects` | `engine.close` |
| `effect.update.reopen.appends_reopen_history` | `UPDATE_REOPEN` | `APPENDS_REOPEN_HISTORY` | `section.reopen_history` | false | `ENGINE` | `ENGINE` | append timestamped reopen reason with request origin | `ManifestLane.effects` | `engine.reopen`; behavior test `test_reopen_appends_reopen_history_for_terminal_reopen` |
| `effect.update.reopen.may_move_from_closed_tickets` | `UPDATE_REOPEN` | `MAY_MOVE_FROM_CLOSED_TICKETS` | ticket file path | false | `ENGINE` | `ENGINE` | unarchive before status write | `ManifestLane.effects` | `engine.reopen`; behavior test `test_reopen_can_move_terminal_ticket_from_closed_location` |

### Raw Shape Accounting

`RawShapeDiscriminator.raw_keys` is the full wrapper/envelope payload key set for the `mutation_id`. It uses raw payload keys, not `SubjectPath` strings. The planner validates full accounting before lane evaluation:

```text
for each raw key in raw_keys:
  raw key maps to exactly one ManifestAction through request_raw_key
  OR raw key is covered by an active raw-shape-only exception
otherwise:
  AuthorityInputError
```

The inverse is also required: every action whose matched rule has `request_raw_key` must have that raw key in the matching `RawShapeDiscriminator.raw_keys`. This prevents action-only planning from silently dropping raw wrapper syntax.

Allowlist and exclusion checks are planner policy, not `RawShapeDiscriminator` constructor policy. A raw key such as `archive`, `resolution`, or `unknown_field` may be syntactically valid carrier input and then produce an unsupported lane when represented by a `ManifestAction`.

If a raw key is the thing being denied, it must have a `ManifestAction` and appear in `unsupported_action_ids` or `invalid_action_ids` as appropriate. Raw-shape-only exceptions are only for raw keys that discriminate wrapper shape but are not themselves authority-bearing or denyable after behavior proof.

Active raw-shape-only exceptions in Slice 1: none.

Probe-gated candidate exceptions live only in this plan until promoted by a later plan patch. They are not active, not exported, not stored in `_DEFAULT_REGISTRY`, and not usable for full raw-key accounting.

| candidate_exception_id | raw_key | surface | raw_group_shape_hint | condition | promotion requirement | if probe rejects |
| --- | --- | --- | --- | --- | --- | --- |
| `raw_shape_exception.candidate.update.nonterminal_reopen_reason_ignored` | `reopen_reason` | `update` | `UPDATE_STATUS_OPEN_EXCLUSIVE` | current status is nonterminal and wrapper accepts but ignores raw `reopen_reason` | behavior probes prove accepted/ignored behavior; later plan patch promotes to active exception | add denyable unsupported `ManifestAction`/rule for `reopen_reason` instead |

### Group Planning Families And Rules

`mutation_id` is the atomicity boundary. Unsupported or incompatible local actions poison a group except `NO_OP` local actions. If at least one non-no-op action in a group is supported, plan the supported lane and list no-op actions in `no_op_action_ids`. If every action in the group is no-op, emit `lane=NO_OP`.

Group selection uses `RawShapeDiscriminator.raw_group_shape_hint` plus local action rules and `MutationContext.current`. The raw shape chooses wrapper compatibility; semantic lifecycle/reopen splitting happens afterward.

| group_family_id | selection basis | selection rule | fallback_group_rule_id |
| --- | --- | --- | --- |
| `group.capture.create` | `RawGroupShapeHint.CAPTURE_CREATE` | all actions surface `CAPTURE`, action/operation `CREATE`, and local hints `CAPTURE_CREATE` | `group.unsupported.capture.create.fallback` |
| `group.ingest.create` | `RawGroupShapeHint.INGEST_CREATE` | all actions surface `INGEST`, action/operation `CREATE`, and local hints `INGEST_CREATE` | `group.unsupported.ingest.create.fallback` |
| `group.update.frontmatter` | `RawGroupShapeHint.UPDATE_FRONTMATTER` | update metadata subjects only; no focused or lifecycle subjects | `group.unsupported.update.frontmatter.fallback` |
| `group.update.focused_refinement` | `RawGroupShapeHint.UPDATE_FOCUSED_REFINEMENT` | at least one focused subject plus optional compatible metadata co-actions | `group.unsupported.update.focused_refinement.fallback` |
| `group.update.status_lifecycle` | `RawGroupShapeHint.UPDATE_STATUS_LIFECYCLE` | lifecycle status subject not raw-open exclusive, close, or reopen | `group.unsupported.update.status_lifecycle.fallback` |
| `group.update.status_open_exclusive` | `RawGroupShapeHint.UPDATE_STATUS_OPEN_EXCLUSIVE` plus nonterminal current status | requested `status="open"` or `reopen_reason` present at raw wrapper shape | `group.unsupported.update.status_open_exclusive.fallback` |
| `group.update.close` | `RawGroupShapeHint.UPDATE_CLOSE` | wrapper close status target `done` or `wontfix` | `group.unsupported.update.close.fallback` |
| `group.update.reopen` | `RawGroupShapeHint.UPDATE_STATUS_OPEN_EXCLUSIVE` plus terminal current status | terminal reopen semantic group after current status is known | `group.unsupported.update.reopen.fallback` |
| `group.no_op` | local no-op outcomes | all local actions are `NO_OP` after probes pass | `group.unsupported.no_op.fallback` |
| `group.unsupported.raw_shape` | `RawGroupShapeHint.UNSUPPORTED_RAW_SHAPE` | well-formed wrapper input with no supported raw group family | `group.unsupported.raw_shape.fallback` |

| group_rule_id | family | supported | lane | gate | required runtime_checks | preconditions | effects | key conditions |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `group.supported.capture.create` | `group.capture.create` | true | `CREATE` | `APPLY_CONSENT` | `DEDUP_SCAN_REQUIRED`, `PREFLIGHT_REQUIRED` | none | `CREATES_TICKET` | all local actions supported/no-op-free, required create subjects present, and no group invalid rules match |
| `group.unsupported.capture.create.incomplete` | `group.capture.create` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | missing required capture create subjects `title`, `captured_request`, `problem`, or `next_action` |
| `group.unsupported.capture.create.fallback` | `group.capture.create` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | fallback |
| `group.supported.ingest.create` | `group.ingest.create` | true | `CREATE` | `APPLY_CONSENT` | `INGEST_ENVELOPE_CONTAINMENT_REQUIRED`, `INGEST_IDEMPOTENCY_CHECK_REQUIRED`, `DEDUP_SCAN_REQUIRED`, `PREFLIGHT_REQUIRED` | none | `CREATES_TICKET` | all local actions supported and required envelope subjects present |
| `group.unsupported.ingest.create.incomplete` | `group.ingest.create` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | missing required envelope subjects `envelope_version`, `title`, `problem`, `source`, or `emitted_at` |
| `group.unsupported.ingest.create.fallback` | `group.ingest.create` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | fallback |
| `group.supported.update.frontmatter` | `group.update.frontmatter` | true | `UPDATE` | strongest local gate | `TARGET_FINGERPRINT_REVALIDATION`, `PREFLIGHT_REQUIRED` | none | `UPDATES_FRONTMATTER` | metadata subjects only; no lifecycle/focused subjects |
| `group.unsupported.update.frontmatter.contains_unsupported` | `group.update.frontmatter` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | any unsupported local action outside no-op rules |
| `group.unsupported.update.frontmatter.fallback` | `group.update.frontmatter` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | fallback |
| `group.supported.update.focused_refinement` | `group.update.focused_refinement` | true | `FOCUSED_REFINEMENT` | strongest local gate | `TARGET_FINGERPRINT_REVALIDATION`, `PREFLIGHT_REQUIRED` | `FOCUSED_REFINEMENT_MODE_REQUIRED` | `UPDATES_FOCUSED_REFINEMENT_SECTIONS`; plus `UPDATES_FRONTMATTER` when metadata co-actions exist; plus `CLEARS_REFINEMENT_MARKER` when cleanup condition holds | at least one focused subject; co-actions limited to priority, tags, component, related_paths, blocked_by, blocks |
| `group.unsupported.update.focused_refinement.lifecycle_mixed` | `group.update.focused_refinement` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | focused section with status/close/reopen subject |
| `group.unsupported.update.focused_refinement.fallback` | `group.update.focused_refinement` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | fallback |
| `group.supported.update.status_lifecycle` | `group.update.status_lifecycle` | true | `UPDATE` | strongest local gate | `TARGET_FINGERPRINT_REVALIDATION`, `PREFLIGHT_REQUIRED` | none unless local row is precondition-required | `UPDATES_FRONTMATTER`, `MAY_AFFECT_CLOSE_READINESS` | non-open status lifecycle group |
| `group.precondition.update.status.blocked_by_required` | `group.update.status_lifecycle` | true | `UPDATE` | `APPLY_CONSENT` | `TARGET_FINGERPRINT_REVALIDATION`, `PREFLIGHT_REQUIRED` | `BLOCKED_BY_REQUIRED` | `UPDATES_FRONTMATTER`, `MAY_AFFECT_CLOSE_READINESS` | status to `blocked` |
| `group.precondition.update.status.blockers_resolved_required` | `group.update.status_lifecycle` | true | `UPDATE` | `APPLY_CONSENT` | `TARGET_FINGERPRINT_REVALIDATION`, `PREFLIGHT_REQUIRED` | `BLOCKERS_RESOLVED_REQUIRED` | `UPDATES_FRONTMATTER`, `MAY_AFFECT_CLOSE_READINESS` | blocked to `open` or `in_progress` |
| `group.unsupported.update.status_lifecycle.fallback` | `group.update.status_lifecycle` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | fallback |
| `group.supported.update.status_open_exclusive` | `group.update.status_open_exclusive` | true | `UPDATE` | `APPLY_CONSENT` | `TARGET_FINGERPRINT_REVALIDATION`, `PREFLIGHT_REQUIRED` | none or `BLOCKERS_RESOLVED_REQUIRED` depending current status | `UPDATES_FRONTMATTER`, `MAY_AFFECT_CLOSE_READINESS` | raw payload contains `status="open"`; compatible raw subjects are only status and reopen_reason |
| `group.unsupported.update.status_open_exclusive.metadata_mixed` | `group.update.status_open_exclusive` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | `status="open"` plus metadata/focused/direct-engine/unknown subject |
| `group.unsupported.update.status_open_exclusive.fallback` | `group.update.status_open_exclusive` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | fallback |
| `group.precondition.update.close` | `group.update.close` | true | `CLOSE` | `USER_APPROVAL` | `TARGET_FINGERPRINT_REVALIDATION`, `PREFLIGHT_REQUIRED` | `CLOSE_READINESS_REQUIRED`, `ACCEPTANCE_CRITERIA_REQUIRED` as applicable | `SETS_TERMINAL_STATUS`, `MAY_AFFECT_CLOSE_READINESS` | close status shape only |
| `group.unsupported.update.close.extra_fields` | `group.update.close` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | close plus metadata/focused/archive/resolution/unknown subject |
| `group.unsupported.update.close.fallback` | `group.update.close` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | fallback |
| `group.precondition.update.reopen` | `group.update.reopen` | true | `REOPEN` | `USER_APPROVAL` | `TARGET_FINGERPRINT_REVALIDATION`, `PREFLIGHT_REQUIRED` | `REOPEN_REASON_REQUIRED` | `APPENDS_REOPEN_HISTORY`, `MAY_MOVE_FROM_CLOSED_TICKETS` | current status terminal and non-empty reopen reason |
| `group.unsupported.update.reopen.extra_fields` | `group.update.reopen` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | reopen plus metadata/focused/unknown subject |
| `group.unsupported.update.reopen.fallback` | `group.update.reopen` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | fallback |
| `group.supported.no_op` | `group.no_op` | true | `NO_OP` | `UNSUPPORTED` | none | none | none | all action IDs are no-op and probes have proven no semantic write lane |
| `group.unsupported.no_op.fallback` | `group.no_op` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | fallback |
| `group.unsupported.raw_shape.fallback` | `group.unsupported.raw_shape` | false | `UNSUPPORTED` | `UNSUPPORTED` | none | none | none | well-formed raw wrapper shape unsupported by Slice 1 policy; local invalids still preempt first |

#### Group Invalid Rules

Group invalid rules are exported under `policy["group_invalid_rules"]`, not under `policy["group_planning"]["group_rules"]`. Structural group rules answer "what wrapper lane shape is this?"; group invalid rules answer "is this otherwise recognized payload composition malformed or contradictory?"

Group invalid rules are planner/group outcomes only. `classify_mutation()` does not inspect sibling payload fields and must not return these rows for single-action classification. Local support is necessary but not sufficient for grouped support; a group invalid rule may reject a lane whose individual actions all classify as `SUPPORTED`.

Evaluation order:

```text
local per-subject INVALID_VALUE
group cross-field INVALID_VALUE
CONTEXT_REQUIRED
PRECONDITION_REQUIRED
SPECIFIC_UNSUPPORTED
NO_OP
SUPPORTED
```

If any action has local `INVALID_VALUE`, the planner returns those local invalid action IDs and does not evaluate group invalid rules. If local values are individually valid, evaluate every applicable group invalid rule in stable authored order. Group invalid evaluation is exhaustive within the selected group family. `group_invalid_rule_ids` preserves authored group-invalid rule order. `invalid_action_ids` is the stable union of affected action IDs, preserving input action order.

| group_invalid_rule_id | family | affected_request_subject_paths | derived_subject_paths | repair_subject_paths | invalid_action_mapping | condition | reason_code | anchors/tests |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `invalid_group.capture.create.tags.needs_refinement_without_refinement_status` | `group.capture.create` | `capture.input.tags` | none | `capture.input.tags`, `capture.input.refinement_status` | affected `capture.input.tags` action ID | assembled capture fields have `tags` containing `"needs-refinement"` and `refinement_status != "needs_refinement"` | `capture_needs_refinement_tag_requires_refinement_status` | `validate.constants`, `capture.mapping`, `capture.tests` |
| `invalid_group.capture.create.acceptance_criteria.explicit_needs_refinement_without_refinement_status` | `group.capture.create` | `capture.input.acceptance_criteria` | none | `capture.input.acceptance_criteria`, `capture.input.refinement_status` | affected `capture.input.acceptance_criteria` action ID | explicit `capture.input.acceptance_criteria` contains `"Needs refinement"` and `refinement_status != "needs_refinement"` | `capture_needs_refinement_ac_requires_refinement_status` | `validate.constants`, `capture.mapping`, `capture.tests` |
| `invalid_group.capture.create.acceptance_criteria.defaulted_needs_refinement_without_refinement_status` | `group.capture.create` | `capture.input.next_action` | `capture.derived.acceptance_criteria_default` | `capture.input.next_action`, `capture.input.acceptance_criteria`, `capture.input.refinement_status` | affected `capture.input.next_action` action ID | `capture.input.acceptance_criteria` is missing, wrapper derives acceptance criteria from `next_action == "Needs refinement"`, and `refinement_status != "needs_refinement"` | `capture_defaulted_ac_needs_refinement_requires_refinement_status` | `validate.constants`, `capture.mapping`, `capture.tests` |

Capture cross-field invalids reflect `validate_fields(fields)` after `ticket_capture.py` has assembled the full fields dict. `capture.input.tags=["needs-refinement"]` classifies locally as supported when its list values are controlled tags; the capture create lane is denied only if the grouped payload lacks `capture.input.refinement_status="needs_refinement"`.

The two acceptance-criteria rules split caller-owned and wrapper-derived causes. Explicit caller-provided `capture.input.acceptance_criteria=["Needs refinement"]` puts the acceptance-criteria action ID in `invalid_action_ids`. Missing acceptance criteria with `capture.input.next_action == "Needs refinement"` puts the next-action action ID in `invalid_action_ids` and carries `capture.derived.acceptance_criteria_default` only as derivation metadata on the group-invalid rule. Do not invent synthetic action IDs for derivations.

Denial lanes for group invalids keep `group_rule_id` set to the structural group rule, set `group_invalid_rule_ids` to all matching invalid rules, put affected actions in `invalid_action_ids`, leave `unsupported_action_ids=()`, and use `reason_code=group_invalid_payload_composition` when multiple group invalids match.

Unsupported lanes, including context-required lanes, always use `lane=UNSUPPORTED`, `required_gate=UNSUPPORTED`, `mutation_class=UNSUPPORTED`, `tracked_write_allowed=False`, `execution_authorized=False`, and `runtime_checks=()`.

All-no-op lanes use `lane=NO_OP`, `supported=True`, all action IDs in `no_op_action_ids`, empty unsupported/context/precondition IDs, empty runtime checks, empty preconditions, empty effects, `requires_revalidation=False`, `tracked_write_allowed=False`, `execution_authorized=False`, and `reason_code=all_actions_no_op`.

### Status And Reopen Semantics

`status` is always a lifecycle subject with `output_paths=frontmatter.status`; it is never an ordinary `update.frontmatter.status` subject.

Raw wrapper compatibility and semantic lane selection are distinct:

```text
raw compatibility: RawGroupShapeHint.UPDATE_STATUS_OPEN_EXCLUSIVE when status="open" or raw reopen_reason is present
semantic lane split: after current.status is known, terminal current statuses become UPDATE_REOPEN; nonterminal current statuses become UPDATE_STATUS_LIFECYCLE or NO_OP
```

`status="open"` never unlocks metadata or focused co-actions in Slice 1. Current-state splitting changes only lane semantics; it does not change raw wrapper payload compatibility.

`reopen_reason` is a raw wrapper shape discriminator whenever present. It is semantically active only for terminal reopen. Nonterminal `reopen_reason` behavior is probe-gated and has no active `_DEFAULT_REGISTRY` row, active raw-shape-only exception, or exported manifest rule until behavior probes prove whether the wrapper rejects it, accepts and ignores it, or produces another visible outcome.

If probes show nonterminal `reopen_reason` is accepted but ignored, Slice 1 must not model it as supported, unsupported, or no-op authority. The planner classifies/plans only the behavior-participating status action. The behavior may be documented only as a non-authority probe note with behavior-test anchors.

Until probes resolve the case, `_DEFAULT_REGISTRY` must not contain a nonterminal `reopen_reason` rule or raw-shape-only exception. Full raw-key accounting uses active raw-shape-only exceptions only. Therefore a planner call with nonterminal raw `reopen_reason` and no matching `ManifestAction` is malformed until a probe passes and a later plan patch promotes the candidate exception. Direct classifier calls for `update.lifecycle.reopen_reason` remain terminal-reopen or missing-current-context questions only; nonterminal semantics are not frozen in Slice 1.

Status transition outcome matrix:

| requested value/current state | raw compatibility family | local outcome | rule_id | planner lane/group rule |
| --- | --- | --- | --- | --- |
| malformed status value, any current | caller row hint | invalid value | `invalid.update.lifecycle.status.value` or `invalid.update.close.status.value` | unsupported |
| valid status value, missing `current.status` | unresolved | context required | `context.update.lifecycle.status.current_status` | unsupported/context lane |
| `open -> in_progress` | status lifecycle | supported | `supported.update.lifecycle.status.open_to_in_progress` | `group.supported.update.status_lifecycle` |
| `in_progress -> open` | status-open exclusive | supported | `supported.update.lifecycle.status.in_progress_to_open` | `group.supported.update.status_open_exclusive` |
| `open -> blocked` or `in_progress -> blocked` | status lifecycle | precondition required | `precondition.update.lifecycle.status.to_blocked` | `group.precondition.update.status.blocked_by_required` |
| `blocked -> open` | status-open exclusive | precondition required | `precondition.update.lifecycle.status.blocked_to_open` | `group.precondition.update.status.blockers_resolved_required` |
| `blocked -> in_progress` | status lifecycle | precondition required | `precondition.update.lifecycle.status.blocked_to_in_progress` | `group.precondition.update.status.blockers_resolved_required` |
| `open -> open` | status-open exclusive | probe-gated no-op candidate | `noop.candidate.update.lifecycle.status.same_open` | `group.supported.no_op` only after probe; metadata/focused co-actions remain unsupported |
| `in_progress -> in_progress` | status lifecycle | probe-gated no-op candidate | `noop.candidate.update.lifecycle.status.same_in_progress` | `group.supported.no_op` after probe, or mixed real update lane with `no_op_action_ids` |
| `blocked -> blocked` | status lifecycle | probe-gated no-op candidate | `noop.candidate.update.lifecycle.status.same_blocked` | `group.supported.no_op` after probe, or mixed real update lane with `no_op_action_ids` |
| nonterminal current -> `done` or `wontfix` | close | precondition required | `precondition.update.close.status.done` or `precondition.update.close.status.wontfix` | `group.precondition.update.close` |
| terminal current -> same terminal value | close | specific unsupported | `unsupported.update.close.status.same_terminal` | unsupported close-shaped lane |
| terminal current -> `open` | status-open exclusive, then reopen semantic split | precondition required | `precondition.update.reopen.status.open` plus `precondition.update.reopen.reopen_reason` when reason is present | `group.precondition.update.reopen` |
| nonterminal current with `reopen_reason` | reopen-exclusive raw compatibility | probe-gated non-authority handling | none unless probes prove wrapper rejection | no active/exported row; before an active raw-shape-only exception exists, raw-key accounting requires a `reopen_reason` action or raises `AuthorityInputError` |
| terminal current with `reopen_reason` and optional `status="open"` | reopen-exclusive raw compatibility | precondition required | `precondition.update.reopen.reopen_reason`; plus `precondition.update.reopen.status.open` when status is present | `group.precondition.update.reopen` |
| any status transition not listed above | matched lifecycle subject but unsupported transition | specific unsupported | `unsupported.update.lifecycle.status.unmatched` | unsupported |

### Behavior Probe Gates

The following probes are required before source implementation may export the candidate rows they cover. Add them as focused behavior tests in the implementation lane before implementing the final registry rows.

| probe_id | required observed behavior | candidate rows/gates affected |
| --- | --- | --- |
| `probe.same_status.in_progress_only` | current `in_progress`, update `{status: "in_progress"}` prepares/executes as documented; status remains `in_progress`; no transition/precondition failure | `noop.candidate.update.lifecycle.status.same_in_progress`, `group.supported.no_op` |
| `probe.same_status.in_progress_metadata` | current `in_progress`, update `{status: "in_progress", priority: "high"}` writes priority and records status as no-op | mixed no-op aggregation, `group.supported.update.status_lifecycle` |
| `probe.same_status.blocked_only` | current `blocked`, update `{status: "blocked"}` prepares/executes as documented; status remains `blocked` | `noop.candidate.update.lifecycle.status.same_blocked`, `group.supported.no_op` |
| `probe.same_status.blocked_metadata` | current `blocked`, update `{status: "blocked", component: "ticket"}` writes component if live wrapper accepts it and records status as no-op | mixed no-op aggregation |
| `probe.same_status.open_exclusive` | current `open`, update `{status: "open", priority: "high"}` is rejected by raw exclusive status-open compatibility | `group.unsupported.update.status_open_exclusive.metadata_mixed` |
| `probe.same_status.terminal_close_shape` | current `done`, update `{status: "done"}` follows close-shaped terminal rejection, not nonterminal no-op | `unsupported.update.close.status.same_terminal` |
| `probe.focused_metadata_coactions` | focused section plus each compatible metadata subject stays one focused-refinement lane and current wrapper writes the compatible fields | `group.supported.update.focused_refinement`, `effect.update.focused.metadata_coactions` |
| `probe.capture_source.non_string_overwritten` | capture prepare with non-string raw `capture_source` returns ready state and prepared fields contain `capture_source == "conversation"` | `supported.capture.create.capture_source`, `value.overwritten_input_any` |
| `probe.reopen_reason.nonterminal_reason_only` | current nonterminal ticket, update `{reopen_reason: "..."}` observed prepare/execute behavior is documented before any authority row is exported | nonterminal `reopen_reason` remains absent from active/exported rows unless probe proves wrapper rejection |
| `probe.reopen_reason.in_progress_status_reason` | current `in_progress`, update `{status: "in_progress", reopen_reason: "..."}` observed behavior shows whether reason is rejected, ignored, or otherwise visible | no active/exported nonterminal `reopen_reason` row by default |
| `probe.reopen_reason.blocked_status_reason` | current `blocked`, update `{status: "blocked", reopen_reason: "..."}` observed behavior shows whether reason is rejected, ignored, or otherwise visible | no active/exported nonterminal `reopen_reason` row by default |

If a probe contradicts a candidate row, patch the plan-control artifact before source implementation/export continues.

Nonterminal `reopen_reason` probes are not candidate-row admission by default. They are absence-preserving probes: if probes show accepted-but-ignored behavior, keep `reopen_reason` invisible to active classifier/manifest policy and promote only the raw-shape-only exception through a later plan patch. If probes show rejection, patch this plan to add a concrete unsupported action row with behavior-test anchors before exporting it.

### Direct-Engine Discrepancy Registry

Export this typed non-authority scope in every manifest:

```python
"direct_engine_discrepancy_scope": {
    "scope_id": "direct_engine.scope.wrapper_vs_engine_mutations",
    "exhaustiveness_claim": "observed_proven_discrepancies_only",
    "absence_semantics": "absence_is_not_equivalence_proof",
    "comparison_basis": "exported_rows_require_behavior_tests",
    "compared_wrapper_surfaces": ["capture", "update", "ingest"],
    "compared_direct_engine_paths": ["ticket_engine_core"],
    "candidate_operations": ["create", "update", "close", "reopen"],
    "excluded_operations": ["query", "read_projection", "runtime_inventory"],
    "source_anchors": [...],
}
```

`direct_engine_discrepancies={}` is valid and expected by default in Slice 1. Rows are exported only for behavior-proven, high-signal differences that explain an explicit wrapper exclusion or preserve a known future-integration warning. Every row must have treatment `documented_not_wrapper_policy`, wrapper anchors, direct-engine anchors, and a behavior-test anchor that exercises both sides of the same mismatch. Discrepancy row IDs must never appear in classifier or lane outputs.

## Manifest Contract

### Top-Level Shape

`export_policy_manifest()` returns deterministic JSON-serializable data:

```python
{
    "schema_version": "ticket_authority_manifest.v1",
    "policy_version": "ticket_authority_policy.slice1.v1",
    "rollout_status": "passive_source_only",
    "api_contract": {...},
    "policy": {...},
    "direct_engine_discrepancy_scope": {...},
    "direct_engine_discrepancies": {...},
}
```

Version tests assert exact values. Do not add automatic policy-version bump enforcement, snapshots, fingerprints, CLI export, or checked-in artifacts in Slice 1.

### API Contract Section

`api_contract` must state:

- supported mutation surfaces: `capture`, `update`, `ingest`
- excluded surfaces: `direct_engine`
- public APIs: `classify_mutation`, `plan_manifest_lanes`, `export_policy_manifest`
- classifier is diagnostic/local only
- planner is the authoritative passive group policy API and requires raw wrapper shape facts for every mutation group
- no grants, provenance, origin, context source, or snapshot fingerprint inputs
- no CLI
- no generated artifact
- no tracked writes
- no execution authorization
- `supported=True` means structural wrapper-policy support, not permission to write
- runtime checks are descriptive required runtime gates, not proof that checks passed
- direct-engine compatibility is manifest-only

### Policy Section

`policy` exports both ordered family structures and flat lookup maps:

```python
"policy": {
    "authority_classes": ["canonical"],
    "reserved_authority_terms": [...],
    "mutation_surfaces": ["capture", "update", "ingest"],
    "local_dispositions": ["supported", "context_required", "precondition_required", "no_op", "unsupported"],
    "required_gates": ["apply_consent", "user_approval", "unsupported"],
    "mutation_classes": ["preview_required", "approval_required", "unsupported"],
    "lane_kinds": ["create", "update", "focused_refinement", "close", "reopen", "no_op", "unsupported"],
    "raw_group_shape_hints": ["capture_create", "ingest_create", "update_frontmatter", "update_focused_refinement", "update_status_lifecycle", "update_status_open_exclusive", "update_close", "unsupported_raw_shape"],
    "runtime_checks": [...],
    "vocabularies": {
        "<vocabulary_id>": {...}
    },
    "value_policies": {
        "<value_policy_id>": {...}
    },
    "value_flows": {
        "<value_flow_id>": {...}
    },
    "shape_families": [
        {...}
    ],
    "subject_families": [
        {...}
    ],
    "rules": {
        "<rule_id>": {...}
    },
    "group_planning": {
        "families": [
            {...}
        ],
        "group_rules": {
            "<group_rule_id>": {...}
        },
        "gate_order": ["unsupported", "apply_consent", "user_approval"],
        "allowed_mixed_surface_families": [],
        "atomicity_invariants": [...]
    },
    "group_invalid_rules": {
        "<group_invalid_rule_id>": {...}
    },
    "out_of_surface_exclusions": {
        "<exclusion_id>": {...}
    },
    "create_derivations": {
        "<derivation_id>": {...}
    },
    "materialization": {
        "<materialization_id>": {...}
    },
    "effects": {
        "<effect_id>": {...}
    },
}
```

Rules:

- `policy["rules"]` is a mapping keyed by `rule_id`.
- `policy["value_policies"]`, `policy["value_flows"]`, `policy["group_invalid_rules"]`, `policy["out_of_surface_exclusions"]`, `policy["create_derivations"]`, `policy["materialization"]`, and `policy["effects"]` are mappings keyed by their authored IDs.
- `policy["group_planning"]["group_rules"]` is a mapping keyed by `group_rule_id`.
- Ordered structures remain lists where order is policy.
- Mapping keys are sorted for deterministic export.
- Every exported reference resolves in the same manifest.
- Every `rules` row has exactly one `shape_family_id`.
- Every non-shape-stop `rules` row has a `subject_family_id`.
- Every active subject `rules` row with a value policy has `value_policy_id` and `value_flow_id`.
- Every active request-subject `rules` row has `request_raw_key`.
- Every exported wrapper create derivation has a matching non-requestable diagnostic rule unless its path is intentionally not a public `SubjectPath`.
- Shape-level denial rules have `subject_family_id=null`.
- `_DEFAULT_REGISTRY` and manifest export contain active behavior only. Probe-gated candidates, including candidate no-op rows and candidate raw-shape-only exceptions, must not appear in `policy["rules"]`, `policy["group_planning"]`, `policy["group_invalid_rules"]`, `policy["out_of_surface_exclusions"]`, `policy["create_derivations"]`, `policy["materialization"]`, `policy["effects"]`, or any classifier/planner output until promoted by a later plan patch after behavior proof.

### Source Anchors

Use shared `SourceAnchor` schema for ordinary rows:

```python
class SourceAnchorKind(StrEnum):
    SYMBOL = "symbol"
    TEST_NAME = "test_name"
    DOC_HEADING = "doc_heading"
    PATTERN = "pattern"
```

Preference order:

1. `symbol`
2. `test_name`
3. `doc_heading`
4. constrained `pattern`

Pattern anchors are allowed only as constrained escape hatches:

- non-empty
- short
- exact text by default
- not whole paragraphs
- purpose/note required
- live validation expects one match unless explicitly marked otherwise

Import-time anchor validation checks carrier shape only. Test-time anchor validation checks path existence and symbol/test/heading/pattern resolution.

### Direct-Engine Discrepancy Registry

Direct-engine discrepancies are outside classifier and planner control flow.

Export a typed scope object:

```python
"direct_engine_discrepancy_scope": {
    "scope_id": "direct_engine.scope.wrapper_vs_engine_mutations",
    "exhaustiveness_claim": "observed_proven_discrepancies_only",
    "absence_semantics": "absence_is_not_equivalence_proof",
    "comparison_basis": "exported_rows_require_behavior_tests",
    "compared_wrapper_surfaces": ["capture", "update", "ingest"],
    "compared_direct_engine_paths": ["ticket_engine_core"],
    "candidate_operations": ["create", "update", "close", "reopen"],
    "excluded_operations": ["query", "read_projection", "runtime_inventory"],
    "source_anchors": [...],
}
```

Export discrepancy rows as a mapping keyed by `discrepancy_id`:

```python
"direct_engine_discrepancies": {
    "<discrepancy_id>": {
        "discrepancy_id": "...",
        "scope_id": "direct_engine.scope.wrapper_vs_engine_mutations",
        "treatment": "documented_not_wrapper_policy",
        "reason_code": "...",
        "wrapper_summary": "...",
        "direct_engine_summary": "...",
        "wrapper_anchors": [...],
        "direct_engine_anchors": [...],
        "behavior_test_anchors": [...],
    }
}
```

Use private typed `_DiscrepancyId`, private discrepancy-treatment validation, and private reason-code validation. Public result and manifest `reason_code` fields remain strings.

Every exported discrepancy row requires:

- non-empty `wrapper_anchors`
- non-empty `direct_engine_anchors`
- non-empty `behavior_test_anchors`
- at least one behavior test anchor to a comparison test that exercises both sides of the same mismatch

The discrepancy ledger is not an equivalence ledger. It exports only behavior-proven differences. Consumers must not infer that unlisted wrapper/direct-engine pairs are equivalent.

`candidate_operations` lists operations where row-level discrepancies may be recorded. It is not a coverage matrix.

Do not export source-inferred discrepancy rows. If direct close/reopen extra-field tolerance is suspected from source, add a comparison behavior test first. If the test disproves the suspected mismatch, do not add the discrepancy row. Direct-engine-only `resolution` or `archive` behavior may appear only as `documented_not_wrapper_policy` discrepancy inventory; it must not become classifiable or lane-plannable wrapper policy in Slice 1.

Slice 1 does not export a general wrapper-quirk ledger. Accepted-but-ignored wrapper syntax is not an authority-bearing subject. Such behavior may be documented only as a non-authority probe note with behavior-test anchors. It must not create `classify_mutation()` rows, `ManifestLane` effects, active manifest rules, or direct-engine discrepancy rows.

## Implementation Tasks

### Task 0: Branch Gate And Baseline

**Files:**
- Read: repository git state
- Read: source files listed in [Source Files To Read First](#source-files-to-read-first)

- [ ] **Step 1: Run branch and worktree gate**

Run:

```bash
git status --short --branch --untracked-files=all
git rev-parse --abbrev-ref HEAD
git rev-list --left-right --count origin/main...main
git worktree list --porcelain
```

Expected: matches [Branch And Worktree Gate](#branch-and-worktree-gate).

- [ ] **Step 2: Confirm this plan is committed before implementation**

Run:

```bash
git status --short --branch --untracked-files=all
```

Expected: no untracked `docs/superpowers/plans/2026-05-22-ticket-authority-kernel-slice1.md`.

- [ ] **Step 3: Read source anchors**

Read the files listed in [Source Files To Read First](#source-files-to-read-first). Confirm live focused refinement, wrapper lifecycle extra-field rejection, direct-engine close/reopen field handling, and create-time capture/ingest field mapping before writing tests.

### Task 1: Update Contract Prose

**Files:**
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

- [ ] **Step 1: Add passive authority-kernel contract section**

Add contract prose stating:

- Slice 1 authority kernel status is `passive_source_only`.
- Supported high-level mutation surfaces are exactly `capture`, `update`, and `ingest`.
- Direct-engine paths are low-level compatibility/debug/agent-internal paths, not wrapper-facing policy surfaces.
- `request_origin` and hook provenance are runtime metadata, not classifier inputs.
- Authority classification does not authorize writes or evaluate grants.

- [ ] **Step 2: Correct focused-refinement contract language**

Document that focused refinement is a current supported update mode for:

- `problem`
- `next_action`
- `acceptance_criteria`

Document that cleanup of refinement markers is group-level behavior, not a local per-action write authorization.

- [ ] **Step 3: Add docs contract tests**

Extend `tests/test_docs_contract.py` to assert:

- contract contains passive source-only status
- contract names `capture`, `update`, and `ingest` as high-level surfaces
- contract states direct engine is not a classifiable surface
- contract states focused refinement is current supported wrapper behavior
- contract states origin/provenance are not classifier authority inputs
- contract states `supported=True` is structural policy support, not execution permission
- contract states Slice 1 never authorizes execution

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q tests/test_docs_contract.py
```

Expected: PASS.

### Task 2: Add Authority Tests First

**Files:**
- Create: `plugins/turbo-mode/ticket/tests/test_authority_contract.py`
- Create: `plugins/turbo-mode/ticket/tests/test_authority_source_anchors.py`
- Create: `plugins/turbo-mode/ticket/tests/test_authority_direct_engine_discrepancies.py`

- [ ] **Step 1: Add carrier validation tests**

In `tests/test_authority_contract.py`, add tests for:

- raw strings for enum fields raise `AuthorityInputError`
- malformed `SubjectPath` raises `AuthorityInputError`
- `SubjectPath("capture.input.unknown")` constructs and classifies through fallback denial
- `SubjectPath("capture.derived.source")` constructs and classifies through non-requestable denial
- `SubjectPath("capture.output.source")`, `SubjectPath("capture.input")`, and uppercase/blanks/slashes raise `AuthorityInputError`
- partial `CurrentTicketState` raises `AuthorityInputError`
- malformed `RawShapeDiscriminator` raises `AuthorityInputError`
- `RawShapeDiscriminator.raw_keys` uses wrapper keys, not dotted `SubjectPath` values
- contradictory raw shape facts, such as raw `reopen_reason` with `UPDATE_FRONTMATTER`, raise `AuthorityInputError`
- unsupported raw keys can be syntactically valid carrier input and are policy-evaluated by the planner
- malformed `ManifestAction` duplicates raise `AuthorityInputError`
- missing `context_by_mutation_id` entry raises `AuthorityInputError`
- missing `raw_shape_by_mutation_id` entry raises `AuthorityInputError`
- empty planner action input raises `AuthorityInputError`
- unused extra `context_by_mutation_id` or `raw_shape_by_mutation_id` entries raise `AuthorityInputError`
- `ManifestLanePlan.lanes` is a tuple and public APIs never expose mutable lane lists
- well-typed unsupported surface/action/operation returns unsupported policy, not an exception
- `__all__` exports only the public callable entrypoints plus carrier, result, enum, value, and exception types
- registry builders, default registry constants, source-anchor support types, value-policy support types, registry rows, and ID wrapper classes are not public exports
- public result IDs are plain strings, not ID wrapper objects
- public result categorical fields compare to enum members, while `reason_code` compares to a plain string
- classifier results satisfy `policy.supported is (policy.local_disposition is LocalDisposition.SUPPORTED)`

- [ ] **Step 2: Add classifier jurisdiction tests**

Cover:

- `CAPTURE + UPDATE + SET_FRONTMATTER + any_subject` returns `surface_action_operation_not_supported` with `subject_family_id is None`
- `INGEST + UPDATE + SET_FRONTMATTER + any_subject` returns unsupported shape denial
- `UPDATE + UPDATE + SET_FRONTMATTER + unknown subject` returns unregistered-subject denial with non-null `subject_family_id`
- there is no `DIRECT_ENGINE` surface and direct-engine carrier attempts are malformed input

- [ ] **Step 3: Add value/context ordering tests**

Cover:

- `status=123` with `current=None` returns invalid-value rule, not context-required rule
- `status="open"` with `current=None` returns context-required with `required_context_fields=["current.status"]`
- lifecycle/status value with required current status returns `PRECONDITION_REQUIRED`, not `SUPPORTED`, when business readiness must be decided by planner/runtime state
- `PRECONDITION_REQUIRED` outcomes have `supported=False`, `lane=UNSUPPORTED`, and `required_context_fields=()`
- `tags="bug"` returns invalid-value rule
- valid tag value with missing refinement context returns context-required when the family needs current refinement/tag state
- standalone `needs-refinement` tag removal is denied before broad supported tag update
- `ingest.envelope.envelope_version` accepts exactly `"1.0"` and rejects other non-empty strings with `invalid.ingest.envelope.envelope_version.value`

- [ ] **Step 4: Add positive local-policy tests**

Cover representative positive rules:

- capture confidence: classifier returns `supported=True`, `caller_writable=True`, `authority_owner=WRAPPER`; manifest rule row has `value_flow_id=flow.caller_preserved_or_wrapper_defaulted_if_missing`
- capture `capture_source`: classifier returns `supported=True`, `caller_writable=False`, `authority_owner=WRAPPER`, `engine_managed=False`; manifest rule row has `subject_path=capture.input.capture_source`, `request_raw_key=capture_source`, `value_policy_id=value.overwritten_input_any`, and `value_flow_id=flow.wrapper_overwrites_constant_conversation`
- capture `source` and capture acceptance-criteria default: classifier returns non-requestable diagnostic denial for `capture.derived.source` and `capture.derived.acceptance_criteria_default`; manifest exports matching `create_derivations` rows
- ingest envelope-supplied field: `supported=True`, `caller_writable=True`, `authority_owner=ENVELOPE`, `engine_managed=False`
- ingest derived `defer` and default fields: classifier returns non-requestable diagnostic denial; manifest exports matching `create_derivations` rows
- ordinary `priority` update: `required_gate=APPLY_CONSENT`
- lifecycle/status local policy with current status: `local_disposition=PRECONDITION_REQUIRED`, `required_gate=UNSUPPORTED`, `lane=UNSUPPORTED`
- close local policy: `local_disposition=PRECONDITION_REQUIRED`, `group_shape_hint=UPDATE_CLOSE`
- reopen local policy: `local_disposition=PRECONDITION_REQUIRED`, `group_shape_hint=UPDATE_REOPEN`
- focused refinement section update: `lane=FOCUSED_REFINEMENT` only when supported, otherwise unsupported/context-required uses `lane=UNSUPPORTED`

- [ ] **Step 5: Add registry validation tests**

Use malformed test registries to assert:

- duplicate IDs raise `AuthorityRegistryError`
- malformed IDs raise `AuthorityRegistryError`
- supported rule with `subject=ANY` raises `AuthorityRegistryError`
- context-required rule without `required_context_fields` raises `AuthorityRegistryError`
- unsupported/context-required row with `caller_writable=True` raises `AuthorityRegistryError`
- `precondition_required` row with non-empty `required_context_fields` raises `AuthorityRegistryError`
- `precondition_required` row outside lifecycle/status families raises `AuthorityRegistryError`
- `engine_managed=True` with non-engine owner raises `AuthorityRegistryError`
- same-stage overlapping outcomes discovered during evaluation raise `AuthorityEvaluationError`
- known subject-family no-match raises `AuthorityEvaluationError`
- `request_raw_key` exists for every active request-subject row
- repeated `subject_path` rows agree on `request_raw_key` unless covered by a documented lifecycle value-dependent exception
- probe-gated candidates are absent from `_DEFAULT_REGISTRY` and manifest export
- candidate raw-shape-only exceptions are not usable for raw-key accounting

- [ ] **Step 6: Add manifest parity tests**

Assert:

- exact `schema_version` and `policy_version`
- `policy["rules"]` equals the in-memory outcome registry by ID
- `policy["shape_families"]` equals the in-memory shape registry
- `policy["subject_families"]` equals the in-memory subject registry
- `policy["value_policies"]` and `policy["value_flows"]` equal the in-memory authored mappings by ID
- `policy["vocabularies"]` resolves every vocabulary reference
- `policy["group_planning"]["group_rules"]` equals the in-memory group-rule registry
- `policy["group_invalid_rules"]` equals the in-memory group-invalid registry
- `policy["out_of_surface_exclusions"]`, `policy["create_derivations"]`, `policy["materialization"]`, and `policy["effects"]` equal the in-memory authored mappings by ID
- every family outcome ID resolves in the flat maps
- `subject_family_id is None` only for shape-level stop rules
- every non-null `subject_family_id` resolves to exactly one parent `shape_family_id`
- manifest exports `runtime_checks` and `execution_authorized`
- manifest exports enum values as strings and contains no enum objects, dataclass wrappers, or private ID wrappers
- manifest exports `raw_group_shape_hints` and no raw-shape-only exception surface in Slice 1
- manifest output survives `json.dumps(..., sort_keys=True)`
- tests use hand-written expected ID/content sets and do not parse this Markdown plan as a machine-readable registry source
- direct-engine discrepancy scope uses `observed_proven_discrepancies_only` and `absence_is_not_equivalence_proof`
- manifest has no exported wrapper-quirk scope

- [ ] **Step 7: Add group-planning tests**

Cover:

- `mutation_id` groups create atomic lanes
- capture create fields collapse into one `CREATE` lane
- capture `tags=["needs-refinement"]` classifies locally supported but capture create planning without refinement status returns a lane with `invalid_action_ids`, `group_invalid_rule_ids=("invalid_group.capture.create.tags.needs_refinement_without_refinement_status",)`, and no `unsupported_action_ids`
- capture `acceptance_criteria=["Needs refinement"]` classifies locally supported but capture create planning without refinement status returns `invalid_group.capture.create.acceptance_criteria.explicit_needs_refinement_without_refinement_status`
- capture missing `acceptance_criteria` with `next_action="Needs refinement"` and no refinement status returns `invalid_group.capture.create.acceptance_criteria.defaulted_needs_refinement_without_refinement_status`, puts the next-action action ID in `invalid_action_ids`, and exposes `capture.derived.acceptance_criteria_default` only through group-invalid rule metadata
- capture payloads that match multiple group invalid rules report every matching `group_invalid_rule_id` in authored order and the union of affected `invalid_action_ids` in input order
- local invalid values outrank group invalids; group invalid rules are not evaluated when any action has local `INVALID_VALUE`
- raw shape discriminators are required for every planner group; missing, extra, contradictory, or partially accounted raw shape entries raise `AuthorityInputError`
- every raw key is represented by one action or an active raw-shape-only exception; unrepresented ordinary keys raise `AuthorityInputError`
- a locally supported action can appear in `unsupported_action_ids` when a raw-shape group rule rejects it, such as update priority mixed with raw `reopen_reason`
- well-formed `UNSUPPORTED_RAW_SHAPE` produces `group.unsupported.raw_shape.fallback`, not `AuthorityInputError`
- ingest create fields collapse into one `CREATE` lane
- ordinary frontmatter updates collapse into one `UPDATE` lane
- focused refinement plus allowed metadata co-update stays one `FOCUSED_REFINEMENT` lane
- status same-current no-op candidates produce `lane=NO_OP` only after behavior probes pass
- status same-current plus supported metadata produces the real update lane with the status action listed in `no_op_action_ids`
- `status="open"` plus metadata or focused fields is unsupported even when current status is nonterminal
- nonterminal `reopen_reason` has no active/exported authority row or active raw-shape-only exception by default; behavior probes determine whether to add a later unsupported row or promote only a non-authority raw-shape exception
- structurally valid lifecycle/status groups can produce supported lanes with `precondition_required_action_ids`, concrete `preconditions`, `runtime_checks`, `requires_revalidation=True`, and `execution_authorized=False`
- capture/create lanes expose `DEDUP_SCAN_REQUIRED` and `PREFLIGHT_REQUIRED`
- ingest/create lanes expose envelope containment, idempotency, dedup, and preflight runtime checks
- update/focused-refinement/lifecycle lanes expose target-fingerprint and preflight runtime checks
- close plus extra metadata makes the entire group unsupported
- close plus direct-engine-only `archive` makes the entire wrapper group unsupported
- reopen plus extra metadata makes the entire group unsupported
- mixed surfaces are unsupported
- context-required local actions produce `context_required_action_ids`
- precondition-required local actions produce `precondition_required_action_ids`
- unsupported local actions produce `unsupported_action_ids`
- context-required group outcome outranks generic unsupported-local-action outcome for coherent shapes
- valid precondition-required lifecycle lanes do not become unsupported solely because business readiness is unresolved
- explicit group fallback produces an unsupported lane

- [ ] **Step 8: Add source-anchor validation tests**

In `tests/test_authority_source_anchors.py`, validate:

- source-anchor and drift evidence comes from file reads plus AST/text parsing only
- the test module may import `ticket_authority.py` but must not import `ticket_capture.py`, `ticket_update.py`, `ticket_validate.py`, `ticket_engine_core.py`, `ticket_envelope.py`, or other runtime Ticket modules
- every ordinary rule/family/vocabulary/group row has non-empty anchors
- every anchor path exists
- symbol/test/heading/pattern anchors resolve
- constrained pattern anchors are not vague multi-paragraph snippets
- manifest exports the same anchors carried by registry rows
- import-time validation does not read files

- [ ] **Step 9: Add direct-engine comparison tests**

In `tests/test_authority_direct_engine_discrepancies.py`, add comparison tests for any exported direct-engine discrepancy row.

If no discrepancy rows are exported, assert the typed scope is still present, `direct_engine_discrepancies == {}`, and absence is documented as not proving equivalence. Always assert discrepancy IDs never appear in classifier or lane outputs.

For close/reopen extra-field wildcard/class discrepancy rows, add tests that exercise both sides in one named or parametrized comparison test:

```text
wrapper lifecycle update with valid lifecycle payload plus unknown extra field -> rejects extra field
direct engine close/reopen with equivalent valid payload plus unknown extra field -> observed current behavior
```

For `archive`, add a comparison test only if exporting a discrepancy row:

```text
wrapper lifecycle close with archive-like extra field -> rejects extra field
direct engine close with archive=True -> observed current behavior
```

If direct engine rejects the extra field, do not export the discrepancy row. Record the suspected discrepancy as tested away only in test/plan notes, not in the manifest ledger. If direct engine accepts `archive`, export it only as `documented_not_wrapper_policy`.

- [ ] **Step 10: Add wrapper behavior probe tests**

Add focused behavior tests for every probe in [Behavior Probe Gates](#behavior-probe-gates) before promoting any candidate row or source-indicated proof-gated value policy into closeout evidence.

At minimum, add capture wrapper coverage proving:

```text
capture prepare with raw capture_source=123 -> ready_to_execute
prepared payload fields capture_source == "conversation"
```

If this capture probe fails, patch `supported.capture.create.capture_source` away from `value.overwritten_input_any` before implementing or exporting the registry.

### Task 3: Add Pure Authority Kernel

**Files:**
- Create: `plugins/turbo-mode/ticket/scripts/ticket_authority.py`

- [ ] **Step 1: Create library-only module skeleton**

Create `ticket_authority.py` with:

- module docstring stating library-only passive policy
- no shebang
- no `argparse`
- no `if __name__ == "__main__"`
- no direct execution helper
- no runtime Ticket imports
- no filesystem/process imports

- [ ] **Step 2: Add enums, value objects, and exceptions**

Implement the public enums, `RuntimeCheck`, and exceptions defined in this plan. Do not expose `ReasonCode` as a public enum or result type; reason codes are validated private registry strings and exported as strings. Implement private ID wrappers for registry construction only. Public result dataclasses must expose ID fields as `str`.

- [ ] **Step 3: Add dataclasses**

Implement frozen dataclasses for:

- `SubjectPath`
- `CurrentTicketState`
- `MutationContext`
- `RawShapeDiscriminator`
- `MutationRequest`
- `MutationPolicy`
- `ManifestAction`
- `ManifestLane`
- `ManifestLanePlan`
- private source-anchor, vocabulary, value-policy, value-flow, wrapper-derivation, materialization, effect, shape/subject/group/group-invalid/discrepancy registry rows

Keep source-anchor, vocabulary, value-policy, value-flow, wrapper-derivation, materialization, effect, registry row dataclasses, and ID wrapper classes private. Do not include them in `__all__`.

- [ ] **Step 4: Add pure registry builder and validation**

Implement private `_build_default_registry()` and import-time validation through `_DEFAULT_REGISTRY`.

Validation must check:

- ID grammar and uniqueness
- reference resolution
- stage ordering
- same-stage static constraints where possible
- authority-owner invariants
- context-field invariants
- precondition-required invariants
- value-policy serializability
- value-flow references for every active row
- active-only registry boundary; probe-gated candidates are absent from `_DEFAULT_REGISTRY`
- `request_raw_key` on every active request-subject row
- raw-shape-only candidate exceptions are unreachable from `_DEFAULT_REGISTRY`
- wrapper-derivation, materialization, and effect row reference resolution
- every exported wrapper derivation with a public subject path has a matching non-requestable diagnostic denial
- group-invalid rule reference resolution
- source-anchor carrier shape
- direct-engine discrepancy bucket presence
- no supported `subject=ANY`
- group families have exactly one fallback unsupported group rule

- [ ] **Step 5: Add classifier evaluator**

Implement:

```text
validate input carrier
select exactly one ShapeFamily
if unsupported shape, return shape-level stop policy
select exactly one SubjectFamily
evaluate stages in order
return exactly one matching outcome
return `PRECONDITION_REQUIRED` only for lifecycle/status outcomes whose business readiness belongs to planner/runtime state
raise AuthorityEvaluationError for same-stage overlap or known-family no-match
```

- [ ] **Step 6: Add group planner evaluator**

Implement:

```text
validate all planner inputs before producing lanes
classify local actions with context_by_mutation_id
group by mutation_id
validate raw_shape_by_mutation_id coverage and raw-key accounting
select group shape from RawShapeDiscriminator.raw_group_shape_hint plus local group_shape_hint and current context
if local invalid actions exist, return invalid_action_ids without evaluating group invalid rules
evaluate all matching group invalid rules in authored order before context/precondition/support rules
evaluate ordered group outcomes
convert precondition-required local lifecycle/status actions into structurally supported lanes with concrete preconditions
attach required runtime_checks to every structurally supported mutating lane
set execution_authorized=False on every lane
return explicit fallback unsupported lane when no non-fallback outcome matches
raise AuthorityEvaluationError for same-stage overlap
```

- [ ] **Step 7: Add manifest export**

Implement deterministic export with:

- exact top-level versions
- API contract section
- vocabularies mapping
- value policies mapping
- value flows mapping
- raw group shape hints
- shape families list
- subject families list
- flat `rules` mapping
- group planning families list
- flat `group_rules` mapping
- flat `group_invalid_rules` mapping
- out-of-surface exclusions mapping
- wrapper create derivations mapping
- create materialization mapping
- effect registry mapping
- runtime checks
- execution authorization fields
- direct-engine discrepancy scope
- direct-engine discrepancies mapping

Do not write the manifest to disk.

### Task 4: Add Slice 1 Phase-Gate Tests

**Files:**
- Create: `plugins/turbo-mode/ticket/tests/test_authority_slice1_phase_gate.py`

- [ ] **Step 1: Add runtime non-integration guard**

Scan every `plugins/turbo-mode/ticket/scripts/ticket_*.py` file except `ticket_authority.py` with AST and assert no import of:

```text
ticket_authority
scripts.ticket_authority
```

Use this comment above the test:

```python
# Slice 1 phase gate. Remove or replace this in the first behavior-integration
# slice, after adding entrypoint-specific regression coverage.
```

- [ ] **Step 2: Add authority purity guard**

Assert `ticket_authority.py` imports only a small allowlist:

```python
ALLOWED_AUTHORITY_IMPORTS = {
    "__future__",
    "collections.abc",
    "dataclasses",
    "enum",
    "re",
    "typing",
}
```

Assert it does not import modules starting with:

```text
scripts
ticket_
plugins
```

Assert it does not import or call filesystem/process/runtime helpers:

```text
pathlib, os, subprocess, sys, json, yaml, tomllib
open, Path, read_text, write_text, read_bytes, write_bytes,
subprocess.run, subprocess.check_call, subprocess.check_output
```

- [ ] **Step 3: Add no-CLI/no-artifact guard**

Assert:

- no `if __name__ == "__main__"`
- no `argparse`
- no CLI export helper
- no plugin manifest command references `ticket_authority.py`
- no checked-in generated authority manifest file exists

- [ ] **Step 4: Add no-execution-authorization guard**

Assert:

- every exported local rule has `tracked_write_allowed=False`
- every generated representative lane has `tracked_write_allowed=False`
- every generated representative lane has `execution_authorized=False`
- every `supported=True` mutating lane has non-empty `runtime_checks`
- no `runtime_check` appears on `MutationPolicy`
- every `ManifestLanePlan` has no default execution/apply allowance

- [ ] **Step 5: Add current-vocabulary guard**

Assert:

- `recordable_autonomously` is not in current mutation classes
- `none` and `engine_operation` are not current required gates
- future actions are not current ticket actions
- provenance modes are not classifier inputs
- direct engine is not a mutation surface

### Task 5: Verification And Closeout

**Files:**
- Verify changed source, tests, and docs only

- [ ] **Step 1: Run focused tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q \
  tests/test_docs_contract.py \
  tests/test_authority_contract.py \
  tests/test_authority_source_anchors.py \
  tests/test_authority_direct_engine_discrepancies.py \
  tests/test_authority_slice1_phase_gate.py \
  tests/test_capture.py \
  tests/test_envelope.py \
  tests/test_ingest.py \
  tests/test_update_refinement.py
```

Expected: PASS.

- [ ] **Step 2: Run changed-path lint**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check \
  plugins/turbo-mode/ticket/scripts/ticket_authority.py \
  plugins/turbo-mode/ticket/tests/test_authority_contract.py \
  plugins/turbo-mode/ticket/tests/test_authority_source_anchors.py \
  plugins/turbo-mode/ticket/tests/test_authority_direct_engine_discrepancies.py \
  plugins/turbo-mode/ticket/tests/test_authority_slice1_phase_gate.py
```

Expected: PASS.

- [ ] **Step 3: Run whitespace gate**

Run:

```bash
git diff --check
```

Expected: no output.

- [ ] **Step 4: Run passive phase-gate review**

Confirm:

- no runtime Ticket script imports `ticket_authority.py`
- no runtime behavior changed
- no installed cache/runtime state changed
- no generated manifest artifact was added
- no CLI was added
- direct-engine discrepancy rows are behavior-proven

- [ ] **Step 5: Review diff surfaces**

Run:

```bash
git diff --stat
git diff -- docs/superpowers/plans/2026-05-22-ticket-authority-kernel-slice1.md
git diff -- plugins/turbo-mode/ticket/references/ticket-contract.md
git diff -- plugins/turbo-mode/ticket/scripts/ticket_authority.py
git diff -- plugins/turbo-mode/ticket/tests/test_authority_contract.py
git diff -- plugins/turbo-mode/ticket/tests/test_authority_source_anchors.py
git diff -- plugins/turbo-mode/ticket/tests/test_authority_direct_engine_discrepancies.py
git diff -- plugins/turbo-mode/ticket/tests/test_authority_slice1_phase_gate.py
```

Expected: only planned files changed.

## Verification Commands

Minimum implementation verification:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q \
  tests/test_docs_contract.py \
  tests/test_authority_contract.py \
  tests/test_authority_source_anchors.py \
  tests/test_authority_direct_engine_discrepancies.py \
  tests/test_authority_slice1_phase_gate.py \
  tests/test_capture.py \
  tests/test_envelope.py \
  tests/test_ingest.py \
  tests/test_update_refinement.py
```

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check \
  plugins/turbo-mode/ticket/scripts/ticket_authority.py \
  plugins/turbo-mode/ticket/tests/test_authority_contract.py \
  plugins/turbo-mode/ticket/tests/test_authority_source_anchors.py \
  plugins/turbo-mode/ticket/tests/test_authority_direct_engine_discrepancies.py \
  plugins/turbo-mode/ticket/tests/test_authority_slice1_phase_gate.py
```

```bash
git diff --check
```

## Commit Boundaries

Plan-control commits, docs/control only:

```text
docs(superpowers): revise ticket authority kernel slice 1 plan
docs(superpowers): fix ticket authority slice 1 control rows
```

The fixup commit is plan-file only and must land before implementation starts. Do not amend the first plan-control commit after adversarial review has inspected it; preserve the review trail.

Implementation commit:

```text
chore(ticket): add passive authority policy kernel
```

Do not mix installed-runtime evidence, cache refresh, marketplace changes, or hook inventory into either commit.

## Closeout Language

Use this closeout shape if Slice 1 implementation completes:

```text
Implemented the source-local passive Ticket authority kernel.

Proof class:
- source only

Runtime status:
- authority kernel is passive and not imported by Ticket runtime entrypoints
- no installed cache/runtime state was changed
- no CLI or generated manifest artifact was added

Policy status:
- wrapper-facing mutation surfaces are capture/update/ingest only
- direct-engine compatibility remains manifest-only
- no tracked writes are authorized by the kernel
- no execution is authorized by the kernel
- runtime checks and lifecycle preconditions are descriptive metadata only

Verification:
- <list exact commands and PASS results>
```

Do not claim installed runtime proof, cache proof, hook proof, or activation proof from this slice.

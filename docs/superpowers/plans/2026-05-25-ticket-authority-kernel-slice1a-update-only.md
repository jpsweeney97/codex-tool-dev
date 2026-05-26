> **Superseded - Do Not Implement**
>
> This broad Slice 1A update-only plan overclaims whole-surface Ticket update
> authority and is retained as historical context only.
>
> There is no active successor authority-kernel plan in this document family.
> Do not copy registry ownership, public callable names, completeness claims,
> or fixture-first workflows from this file into new work.

# Ticket Update Authority Slice 1A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` (recommended) or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a source-local, passive, post-membrane update authority mirror that freezes current wrapper handling of the decoded inner `payload["update"]` object without changing runtime behavior, installed cache state, hook behavior, trust behavior, direct-engine behavior, or wrapper-envelope/prepare-artifact behavior.

**Architecture:** Slice 1A creates a pure library module, `plugins/turbo-mode/ticket/scripts/ticket_update_authority.py`, plus contract prose, proof-control fixtures, and permanent tests. The public callable surface is update-only and path-first: `plan_update_manifest_for_payload(raw_payload, context)` plans one decoded inner `update` object into one public `path_id` and one coarse `outcome`, and `export_update_policy_manifest()` exports the public path-first resolver manifest for that `policy_version`. Capture, ingest, generic multi-surface APIs, public normalized classifiers, direct-engine discrepancy export, wrapper-envelope planning, prepare/execute artifact planning, and runtime integration are deferred.

**Tech Stack:** Python 3.11+, frozen dataclasses with `slots=True`, small public enums, pytest, AST/text proof-control audits, Markdown contract docs, and bytecode-safe `uv run` verification.

---

## Supersession And Authority

This file is the sole semantic authority for Slice 1A implementation.

- Superseded historical file: `docs/superpowers/plans/2026-05-22-ticket-authority-kernel-slice1.md`
- Implementation authority: `docs/superpowers/plans/2026-05-25-ticket-authority-kernel-slice1a-update-only.md`
- Semantic authority chain:
  - Markdown plan: human-approved semantic authority
  - expected-inventory fixture: executable projection of this plan
  - proof catalog and audits: machine checks over the fixture and wrapper probes
  - `ticket_update_authority.py`: implementation after proof-control passes

If this plan and its expected-inventory fixture disagree, implementation is blocked until both are reconciled. The fixture does not override the plan. The plan does not bypass the fixture.

Revision handshake for plan and proof-control projection:

<!-- slice1a-revision-handshake:start -->
CONTROL_PLAN_REVISION = "ticket-update-authority-slice1a.v8"
<!-- slice1a-revision-handshake:end -->

The expected-inventory fixture owns `EXPECTED_INVENTORY_REVISION`. Proof-control audits may parse exactly this sentinel block to extract `CONTROL_PLAN_REVISION` and must reject any broader Markdown parsing. The expected-inventory fixture and proof-control audits must fail if those values diverge.

---

## Decision Freeze

These decisions are frozen for Slice 1A. If live source behavior or proof work contradicts them, stop and patch the control surface before implementation continues.

| Area | Frozen decision |
| --- | --- |
| Proof class | This slice proves `source` only. It does not prove installed runtime behavior, cache state, personal plugin sync, hook inventory, or activation readiness. |
| Slice shape | Slice 1A is update-only, post-membrane, passive, and non-integrated. It mirrors current wrapper handling of the decoded inner `payload["update"]` object only after entrypoint/trust/runtime-readiness gates have accepted or normalized the request and after wrapper-envelope extraction has produced the inner update object. |
| Entrypoint membrane | `request_origin`, trust-triple validation, runtime-readiness, autonomy policy, session caps, hook certification, and installed-runtime behavior are explicitly out of Slice 1A path coverage. If a required update path cannot be described without those membrane facts, stop and split a later membrane slice. |
| Legacy ticket scope | Slice 1A classifies only current v1.0, non-legacy tickets after the legacy write gate has passed. Legacy-generation write blocking is a ticket-format/write-policy exclusion, not a public Slice 1A path. |
| Wrapper-envelope exclusions | Slice 1A does not model missing outer `payload["update"]`, missing `ticket_id`, ticket lookup/not-found behavior, payload-path or file-loading checks, saved `update_prepare` artifact presence/shape, stale preview or stale fingerprint drift, or target/dedup fingerprint enforcement. Those are wrapper-envelope or prepare/execute-artifact exclusions, not public Slice 1A paths. |
| Runtime behavior | Existing Ticket runtime scripts must not import or enforce `ticket_update_authority.py` in Slice 1A. Runtime behavior stays unchanged. |
| Public module path | Slice 1A implements `plugins/turbo-mode/ticket/scripts/ticket_update_authority.py`. Do not create `ticket_authority.py`, a generic authority facade, or any public generic multi-surface authority shell in this slice. |
| Public callable APIs | The only public callable authority APIs are `plan_update_manifest_for_payload(raw_payload, context)` and `export_update_policy_manifest()`. Slice 1A exposes no public normalized classifier. Any normalized evaluator is private implementation scaffolding. |
| Public surface scope | Slice 1A exposes no public `MutationSurface`, no `surface=` parameter, no `mutation_id`, no caller-supplied grouping identity, and no public direct-engine surface. |
| Deferred surfaces | `capture` and `ingest` are deferred surfaces only. They may appear in plan prose and public manifest scope metadata such as `covered_mutation_surfaces` and `deferred_mutation_surfaces`, but they are not callable authority surfaces and do not have public paths in Slice 1A. |
| Public planner contract | `plan_update_manifest_for_payload()` returns exactly one public `path_id` and one coarse `outcome` per raw update payload. Public planner output must not expose rule IDs, group-rule IDs, raw-shape IDs, private action IDs, evaluator phase IDs, or internal topology. |
| Public manifest contract | `export_update_policy_manifest()` is strictly public and path-first, with exact built-in JSON-serializable carriers, row key closure, and canonical exported-list ordering owned by this plan. It exports normative path/proof data separately from informative top-level `source_anchors[probe_id]` audit locators. It must not export internal evaluator topology, candidate paths, quarantined paths, unresolved probe questions, rule IDs, group-rule IDs, raw-shape IDs, dispatch tables, direct-engine discrepancy sections, public `effects` / `materializations` registries, or path-local `source_anchors`. |
| Public path taxonomy | Public emitted IDs are path-first and scoped to one normalized wrapper-observable behavior path. Public IDs must not begin with mechanism-first terms such as `rule`, `group`, `raw_shape`, or `planner`. |
| Routing ownership | Path-family ownership follows the wrapper-observable routing order: public input validation, raw carrier validation, key-set validation, recognized field validation, lifecycle field-set validation, wrapper action routing, routed-update subrouting, then exactly one public family/path selection. Named families are post-routing projections, not competing raw-shape claimants. After close/reopen routing, any routed `update` payload with caller-present `status` stays lifecycle-owned; co-present metadata, `tags`, or focused-refinement section fields may create lifecycle subpaths but do not transfer ownership to frontmatter or focused-refinement families. |
| Lifecycle completeness unit | Lifecycle completeness is measured by `(current_status, lifecycle_intent_bucket)` for recognized lifecycle field-sets after raw carrier, key-set, recognized-field validation, and wrapper action routing. Named lifecycle families are grouping projections over that matrix, not the sole completeness denominator. |
| Overlap-sensitive cells | The closed overlap-sensitive cell list in this plan is semantic authority. The fixture owns the machine projection. A source-derived audit that finds an undeclared overlap-sensitive candidate hard-stops until a plan-control patch declares it and bumps `CONTROL_PLAN_REVISION`; the fixture must not absorb it first as a passing private row. |
| Private proof-control IDs | Unresolved and quarantined items use private IDs such as `probe_question.update.*` and `quarantine.update.*`. Those IDs must not appear in public planner output, public path inventory, or the public manifest. |
| Public proof obligations | `behavior_proof_ids` and public `proofs[probe_id]` entries are compatibility-significant within one `policy_version`. Public proof entries use a thin closed structured schema and describe wrapper-observable behavior only. |
| Source anchors | `source_anchors[probe_id]` is a top-level public-readable audit-locator map with closed anchor rows and canonical list ordering, not policy identity. Anchor values may name internal helpers or fields as locators, but not as behavior claims. Changing only anchor values requires no `policy_version` bump when behavior claims and canonical `probe.*` obligations are unchanged. |
| Public version gates | Before implementation/export exists, `CONTROL_PLAN_REVISION` carries proof-control and schema-shape churn. Do not finalize public `schema_version` or `policy_version` until the manifest schema, closed overlap-sensitive list, required lifecycle matrix, and pre-kernel proof-control audits are settled. After export exists, schema-only exported shape changes bump `schema_version`; normative behavior/proof changes bump `policy_version`; anchor value drift bumps neither. |
| Direct engine | Slice 1A does not export `direct_engine_discrepancy_scope`, `direct_engine_discrepancies`, or direct-engine observations in exported `source_anchors[probe_id]`. Direct-engine observations may appear only in non-public proof-control notes and must not create a second evidence surface. |
| Public outcome vocabulary | Public `UpdatePathOutcome` is limited to `ACCEPTED`, `NO_OP`, `CONTEXT_REQUIRED`, `PRECONDITION_BLOCKED`, `INVALID_PAYLOAD`, and `UNSUPPORTED_PAYLOAD`. Do not add `ACCEPTED_IGNORED`, `SUPPORTED`, or public `reason_code`. |
| `ACCEPTED` meaning | `ACCEPTED` means an execution-ready wrapper-admitted update path under the supplied context that is not classified as a proof-backed `NO_OP`. It does not mean merely "recognized by the wrapper," and it does not promise a known ordinary metadata or section diff. |
| `NO_OP` meaning | `NO_OP` is allowed only for proof-backed wrapper-observable no-write families. Any engine-owned write, including `contract_version` stamping or equivalent write-path normalization, disqualifies public `NO_OP`. Slice 1A does not classify general same-value metadata or section updates as public `NO_OP`. |
| Outcome precedence | Public path classification precedence is: API misuse -> `AuthorityInputError`; JSON-native raw carrier/value/shape error -> `INVALID_PAYLOAD`; unknown key / unsupported namespace / forbidden key combination -> `UNSUPPORTED_PAYLOAD`; recognized family with missing direct facts -> `CONTEXT_REQUIRED`; recognized family with failed current-state preconditions -> `PRECONDITION_BLOCKED`; execution-ready and not proof-backed-no-op path -> `ACCEPTED`; recognized fully decided no-effect path -> `NO_OP`. |
| Context/precondition boundary | `CONTEXT_REQUIRED` and `PRECONDITION_BLOCKED` are valid only after the payload is JSON-native, the carrier is admissible, the field set is recognized, and recognized fields pass raw type/value validation. Do not soften invalid or unsupported payloads into context or precondition outcomes. |
| Raw payload boundary | Public raw input is broad and validation-owned, but accepts only exact built-in decoded-JSON carrier shapes: `dict`, `list`, and JSON scalar values. Top-level JSON-native non-mapping values are public invalid payloads. Non-JSON-native Python objects, container subclasses, tuples, mappings, sequences, and custom dict-like objects are API misuse and raise `AuthorityInputError`. Non-finite floats (`NaN`, `Infinity`, `-Infinity`) are API misuse anywhere in `raw_payload`; finite floats and arbitrary-size Python `int` values are carrier-valid and field-invalid when the field rejects them. `bool` is a distinct JSON scalar and must never satisfy numeric expectations. |
| Context object | `plan_update_manifest_for_payload()` requires `type(context) is UpdateMutationContext` exactly on every call. `UpdateMutationContext()` is the only representation of "no current-ticket facts supplied." `context=None`, subclasses, duck-typed objects, mappings, and raw-string enum values are invalid input. |
| Missingness invariant | For public collection or mapping facts, `None` means "fact not supplied"; empty tuple or empty mapping means "fact supplied and known empty." Supplied context facts are globally shape-validated but path-sufficient only when the selected path needs them. |
| Current-ticket facts only | Public context accepts only direct current-ticket facts. It must not accept caller-supplied readiness judgments such as `close_ready`, `current_acceptance_state`, `current_blocker_resolution`, or `blockers_resolved`. All readiness and terminality judgments are derived privately inside `ticket_update_authority.py`. |
| Blocker facts | `referenced_ticket_statuses` uses a dedicated public enum with exact referenced statuses plus `MISSING`. `current_blocked_by` is order-insensitive and duplicate-insensitive in public semantics; duplicates are accepted as live-state input and collapse to set semantics for public classification. `referenced_ticket_statuses` is valid only when `current_blocked_by` is supplied; extra keys are `AuthorityInputError`, omitted keys mean "status not supplied," and partial maps are allowed only when the supplied subset already fixes the public blocked result. `ReferencedTicketState.MISSING` means a blocker ID is supplied and known absent; omission means the blocker status is not supplied. `current_blocked_by=()` with `referenced_ticket_statuses={}` is a valid exact empty bundle for any payload. |
| Public planner fields | `UpdateManifestPlan` exposes only `schema_version`, `policy_version`, `path_id`, `outcome`, `ignored_raw_keys`, `invalid_raw_keys`, `unsupported_raw_keys`, `no_op_raw_keys`, `context_required_raw_keys`, `missing_context_fields`, and `precondition_blocked_raw_keys`. Do not add `supported`, `accepted_raw_keys`, `precondition_ids`, or public internal IDs. |
| Manifest readability | Each public manifest path entry includes one concise public `behavior_claim`. It must be one sentence, behavior-only, and path-level. Do not add public rationale, remediation prose, or implementation detail fields. |
| Registry authorship | Exact public `path_id` inventory belongs to the expected-inventory fixture, not this Markdown file. This plan is normative on path families, naming grammar, outcome rules, proof rules, and family boundaries. Tests must not parse this Markdown file as a machine-readable registry source, except for the dedicated revision-handshake sentinel block. |
| Tags refinement marker | Slice 1A must model wrapper-transformed tag updates that keep the `needs-refinement` marker effective when refinement remains active as one collapsed public accepted behavior. When caller-present `status` keeps lifecycle ownership, marker-sensitive tag handling becomes a lifecycle subpath rather than a frontmatter-family transfer. `current_refinement_status_is_needs_refinement` is the discriminator. Do not expose `current_has_needs_refinement_tag` in Slice 1A. |
| Lifecycle mixed-subpath closure | Caller-present non-close/non-reopen `status` keeps lifecycle family ownership for mixed `status + tags` and `status +` focused-refinement section payloads only for target statuses that survive lifecycle validation with those peer fields. `status == "open"` with ordinary metadata, `tags`, or focused-refinement section peers is rejected before routed update ownership and is not part of these lifecycle mixed-subpath cells. The source-real mixed shapes remain closed overlap-sensitive lifecycle subpath cells until probes settle their public subpath identity and required context. |
| Close-as-done precedence | `close_done` family selection follows live gate order: dependency blockers first, invalid transition second, done-readiness third, accepted close last. Public done-readiness blocking is one collapsed `missing_acceptance_criteria` path; exact human-facing wording such as "ticket still needs refinement" versus "acceptance criteria section missing" is proof-level detail, not public path identity. |
| Close-as-done sufficiency | `close_done` uses minimal decisive context. If an earlier gate or one supplied readiness fact already fixes the public path/outcome, later or sibling missing facts do not force `CONTEXT_REQUIRED`. Placeholder-only Acceptance Criteria is derived privately from `current_acceptance_criteria_lines` using live normalization semantics. |
| `blocked_by` lifecycle split | Transition-to-blocked paths distinguish omitted `blocked_by` from explicit caller-supplied `blocked_by`. Omitted `blocked_by` may consult `current_blocked_by`; explicit `blocked_by: []` is a decisive `blocked_by_required` failure path; same-status current `blocked` with caller-present `blocked_by` is a distinct accepted same-status lifecycle subpath from pure status-only same-status `blocked`. |
| Same-status lifecycle paths | Same-status lifecycle cells remain mandatory Slice 1A coverage. They stay private only until required prepare+execute probes settle their wrapper-observable outcome, after which they must promote to public coverage rather than remain a permanent exclusion or blocker. |

### Settled Session Decisions

- Pre-kernel expected-inventory scenarios use fixture-local primitive `context_spec` carriers, not real `UpdateMutationContext` instances. Post-kernel contract tests must instantiate `UpdateMutationContext` from every `context_spec` and fail on drift.
- Legacy-generation write blocking is excluded from Slice 1A. Source-derived audits must track `_check_legacy_gate()` as a proof-backed exclusion.
- Public `NO_OP` means no write at all. Paths that reach engine-owned writes, including `contract_version` stamping, are `ACCEPTED` unless proof shows no write occurs.
- `family.update.focused_refinement` does not advertise public `NO_OP` in this revision. Any true no-write focused-refinement path requires a later plan-control patch plus proof-backed promotion.
- Public blocker detail is collapsed. Missing versus unresolved blocker classes remain proof-relevant but not public path identity unless a later plan revision widens the planner surface.
- Caller-present non-close/non-reopen `status` keeps lifecycle ownership. Marker-sensitive tags and focused-refinement section behavior may require lifecycle subpaths when they change public planner-visible behavior, and those mixed shapes stay closed overlap-sensitive lifecycle subpath cells until probes settle them.
- `status == "open"` with ordinary metadata, `tags`, or focused-refinement section peers is not a routed lifecycle mixed-subpath case. Live lifecycle validation rejects those peer fields before action routing, so Slice 1A mixed lifecycle subpath coverage applies only to source-real target statuses that survive that gate.
- Transition-to-blocked omitted `blocked_by` versus explicit `blocked_by: []` is a public lifecycle path split. Same-status current `blocked` plus caller-present `blocked_by` is a distinct accepted lifecycle subpath from pure status-only same-status `blocked`.

---

## Non-Goals

- Do not create `plugins/turbo-mode/ticket/scripts/ticket_authority.py`.
- Do not add a public normalized classifier such as `classify_update_mutation()`.
- Do not add `capture` or `ingest` public paths, public planner surfaces, or public manifest sections beyond deferred-surface metadata.
- Do not add direct-engine discrepancy export.
- Do not add public internal topology such as rule IDs, group-rule IDs, raw-shape IDs, or evaluator phases.
- Do not integrate the update authority module into runtime entrypoints.
- Do not mutate installed plugin cache, personal plugin state, app-server inventory, hooks, or marketplace files.
- Do not widen public context into parsed ticket objects, ticket paths, section text blobs, frontmatter dictionaries, or ticket graphs.
- Do not expose `current_has_needs_refinement_tag` in `UpdateMutationContext`.
- Do not model general same-value metadata or section equality as public `NO_OP`.
- Do not export public `effects`, `materializations`, `effect_ids`, or `materialization_ids`.
- Do not put `family_id`, overlap-cell IDs, lifecycle matrix IDs, private proof-control IDs, or callable predicates in production registry rows.
- Do not import test-owned fixtures or `plugins/turbo-mode/ticket/tests/` modules from `ticket_update_authority.py`.
- Do not parse this Markdown plan as a machine-readable inventory source, except for the dedicated revision-handshake sentinel block.
- Do not treat wrapper-envelope or prepare/execute-artifact failures as public Slice 1A planner paths.
- Do not put unresolved probe questions or quarantined candidates in the public manifest.

---

## Public Contract

### Module

- Public implementation module: `plugins/turbo-mode/ticket/scripts/ticket_update_authority.py`
- Intentional absence in Slice 1A:
  - `plugins/turbo-mode/ticket/scripts/ticket_authority.py`
  - public generic authority facade
  - public multi-surface `MutationSurface`

### Public Callables

```python
def plan_update_manifest_for_payload(
    raw_payload: object,
    context: UpdateMutationContext,
) -> UpdateManifestPlan:
    ...


def export_update_policy_manifest() -> dict[str, object]:
    ...
```

### Public Planner Scope

`plan_update_manifest_for_payload(raw_payload, context)` is scoped to the decoded inner `payload["update"]` object only.

Excluded wrapper-envelope and prepare/execute-artifact behavior:

- missing or malformed outer `payload["update"]`
- missing `ticket_id`
- ticket lookup and not-found behavior
- payload-path containment, file-loading, or payload-write concerns
- saved `update_prepare` artifact presence or shape
- stale preview, stale fingerprint, or execute-fingerprint drift
- target-fingerprint or dedup-fingerprint enforcement

Those paths are explicitly out of Slice 1A public planner scope.

### Public Errors

- `AuthorityInputError`: malformed public API carrier input, non-JSON-native raw values, invalid context object, or invalid public enum/field shape.
- Error format for public carrier misuse:

```text
"{operation} failed: {reason}. Got: {input!r:.100}"
```

### Public Enums And Dataclasses

```python
class CurrentStatus(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    WONTFIX = "wontfix"


class ReferencedTicketState(StrEnum):
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"
    WONTFIX = "wontfix"
    MISSING = "missing"


class UpdatePathOutcome(StrEnum):
    ACCEPTED = "accepted"
    NO_OP = "no_op"
    CONTEXT_REQUIRED = "context_required"
    PRECONDITION_BLOCKED = "precondition_blocked"
    INVALID_PAYLOAD = "invalid_payload"
    UNSUPPORTED_PAYLOAD = "unsupported_payload"


@dataclass(frozen=True, slots=True)
class UpdateMutationContext:
    current_status: CurrentStatus | None = None
    current_refinement_status_is_needs_refinement: bool | None = None
    current_acceptance_criteria_lines: tuple[str, ...] | None = None
    current_blocked_by: tuple[str, ...] | None = None
    referenced_ticket_statuses: Mapping[str, ReferencedTicketState] | None = None


@dataclass(frozen=True, slots=True)
class UpdateManifestPlan:
    schema_version: str
    policy_version: str
    path_id: str
    outcome: UpdatePathOutcome
    ignored_raw_keys: tuple[str, ...]
    invalid_raw_keys: tuple[str, ...]
    unsupported_raw_keys: tuple[str, ...]
    no_op_raw_keys: tuple[str, ...]
    context_required_raw_keys: tuple[str, ...]
    missing_context_fields: tuple[str, ...]
    precondition_blocked_raw_keys: tuple[str, ...]
```

`ReferencedTicketState.MISSING` is an existence fact for a referenced blocker, not a current ticket lifecycle status.

### Public Raw Input Boundary

Public admissible raw inputs are strictly exact built-in decoded-JSON carrier shapes after decoding of the inner `payload["update"]` object:

- `None`
- `bool`
- `int`
- finite `float`
- `str`
- `list[JSONValue]`
- `dict[str, JSONValue]`

`JSONValue` here is the recursive JSON-native value pseudotype used only to define the admissible public boundary.

Public behavior:

- top-level JSON-native non-mapping value -> public `INVALID_PAYLOAD` path
- exact built-in `dict` with string keys -> planner-owned validation and path classification
- non-string mapping key -> `AuthorityInputError`
- non-JSON-native nested or top-level value -> `AuthorityInputError`
- any non-finite float anywhere in `raw_payload` -> `AuthorityInputError`
- `dict` or `list` subclasses, arbitrary `Mapping` / `Sequence` objects, tuples, dataclasses, and custom Python carrier objects -> `AuthorityInputError`
- Python `int` values are accepted regardless of magnitude, except `bool` remains a distinct JSON scalar
- finite Python `float` values are accepted at the carrier layer and rejected only by field-specific validation when the selected field does not accept numbers
- validators must check `bool` before numeric checks so `True` and `False` never satisfy an integer or float expectation

### Public Context Rules

- `type(context) is UpdateMutationContext` exactly. `None`, subclasses, mappings, and duck-typed lookalikes raise `AuthorityInputError`.
- The recursive JSON-native input rule applies to `raw_payload` only. `UpdateMutationContext` is a separate closed typed Python public API surface with field-specific validation.
- `UpdateMutationContext()` is explicit empty context.
- `None` on a field means "fact not supplied."
- Empty tuple or empty mapping means "fact supplied and known empty."
- `CurrentStatus` and `ReferencedTicketState` fields must be exact enum members. Matching raw strings are invalid.
- `current_status` may be `None` while other well-formed facts are supplied. Context sufficiency is path-sensitive; `current_status` is required only when routing, ownership, or outcome can change based on current status.
- `current_refinement_status_is_needs_refinement` may be `None` or exact `bool`.
- `current_acceptance_criteria_lines` may be `None` or a tuple of non-empty strings. It contains the current Acceptance Criteria section split into lines with line separators removed, omitting blank or whitespace-only lines. For retained lines, preserve observed text exactly, including leading whitespace, bullets, checklist markers, and casing. Blank, whitespace-only, non-string, or non-tuple supplied values raise `AuthorityInputError`, even when the selected payload does not consume close-readiness context. `()` means the planner knows the current Acceptance Criteria content contributes no lines for readiness purposes, whether the section is absent or present but empty/blank. Private close-readiness logic may normalize those preserved lines to detect the placeholder-only `Needs refinement` section, but that derived judgment is not a public context field.
- `current_blocked_by` may be `None` or a tuple of string blocker IDs. Public classification treats blocker IDs as an unordered, duplicate-insensitive set. Duplicate IDs are allowed and collapse privately for public classification. Non-string IDs and nested `None` raise `AuthorityInputError`.
- `referenced_ticket_statuses` may be `None` or a mapping whose keys are strings and whose values are exact `ReferencedTicketState` members. It is valid only when `current_blocked_by` is not `None`.
- If `current_blocked_by is None` and `referenced_ticket_statuses is not None`, raise `AuthorityInputError`.
- If both blocker facts are supplied, `set(referenced_ticket_statuses.keys())` must be a subset of `set(current_blocked_by)`. Extra keys raise `AuthorityInputError`.
- If blocker resolution is required and `current_blocked_by is None`, return `CONTEXT_REQUIRED` for `current_blocked_by`.
- If blocker resolution is required, `current_blocked_by` is supplied, and `referenced_ticket_statuses is None`, return `CONTEXT_REQUIRED` for `referenced_ticket_statuses`.
- If blocker resolution is required and any supplied referenced status is `MISSING`, `OPEN`, `IN_PROGRESS`, or `BLOCKED`, the planner may emit the collapsed dependency-blocked public path without requiring omitted blocker statuses.
- If blocker resolution is required, all supplied referenced statuses are terminal (`DONE` or `WONTFIX`), and some blocker IDs remain unsupplied, return `CONTEXT_REQUIRED` for `referenced_ticket_statuses`.
- `referenced_ticket_statuses={}` with non-empty `current_blocked_by` is valid but insufficient blocker evidence; when blocker resolution matters it yields `CONTEXT_REQUIRED`.
- `current_blocked_by=()` with `referenced_ticket_statuses={}` is a valid exact blocker-status bundle for any payload, even when unused.

---

## Public Outcome And Payload Taxonomy

### Outcome Precedence

1. API misuse -> `AuthorityInputError`
2. JSON-native raw carrier/value/shape error -> `INVALID_PAYLOAD`
3. unknown key / unsupported namespace / forbidden key combination -> `UNSUPPORTED_PAYLOAD`
4. recognized family and recognized field set, but required context facts are missing -> `CONTEXT_REQUIRED`
5. recognized family and recognized field set, context is sufficient, but current-state preconditions fail -> `PRECONDITION_BLOCKED`
6. recognized family and recognized field set, execution-ready and not proof-backed no-op path -> `ACCEPTED`
7. recognized and fully decided no-effect path -> `NO_OP`

### Rejection Split

- `UNSUPPORTED_PAYLOAD`:
  - unknown key
  - unsupported namespace
  - forbidden key combination for a recognized update family
- `INVALID_PAYLOAD`:
  - non-object JSON-native update carrier
  - recognized field with wrong JSON-native type
  - recognized field with invalid value bucket
  - recognized raw shape malformed by JSON-native value/shape

Missing direct facts or failed current-state readiness are never `INVALID_PAYLOAD` or `UNSUPPORTED_PAYLOAD` once the recognized family and field set have been established.

`CONTEXT_REQUIRED` is allowed only when a missing direct fact can change at least one public planner field or exported public manifest claim that Slice 1A treats as compatibility-significant. If the missing fact would change only private detail, internal normalization, or a level of precision the public claim does not expose, do not return `CONTEXT_REQUIRED`; coarsen the public claim instead.

For overlap-sensitive raw shapes, the planner must not emit any public path, including `CONTEXT_REQUIRED`, until executable proof settles routed family ownership and the direct fact or facts that discriminate between competing public families or outcomes. Before that proof exists, the cell stays private as a `probe_question.*` or `quarantine.*` blocker.

### Raw-Key Bucket Invariant

The planner result must not expose `accepted_raw_keys`. Public invariant:

```text
effective_raw_keys =
    caller_present_raw_keys
    - ignored_raw_keys
    - invalid_raw_keys
    - unsupported_raw_keys
    - no_op_raw_keys
    - context_required_raw_keys
    - precondition_blocked_raw_keys
```

`missing_context_fields` is not part of raw-key partition math. It names missing public context facts, not raw payload key disposition.

---

## Routing Ownership And Denominator Discovery

Path ownership follows the wrapper-observable routing order, not family-first raw-shape claiming.

Normative routing sequence:

1. Apply the `AuthorityInputError` boundary for non-JSON-native caller misuse.
2. Validate raw carrier shape.
3. Validate unknown or forbidden key sets.
4. Validate recognized field type and value buckets.
5. Validate lifecycle field-set gates.
6. Route to wrapper action: `close`, `reopen`, or `update`.
7. Within routed `update`, apply update-subrouting:
   - caller-present `status` that survives close/reopen routing owns family selection and routes to `status_target.*`
   - within lifecycle-owned `status_target.*`, ordinary metadata does not transfer ownership and creates distinct lifecycle subpaths only when it changes a public planner field, required context, outcome, raw-key bucket disposition, or path-level behavior claim/proof facet
   - within lifecycle-owned `status_target.*`, active-refinement `tags` behavior and focused-refinement section behavior may create lifecycle subpaths when they change public planner-visible behavior and the selected target status survives lifecycle validation with those peer fields
   - within lifecycle-owned `status_target.blocked`, caller-present `blocked_by` affects lifecycle subpath selection: transition-to-blocked distinguishes omitted `blocked_by` fallback from explicit caller-supplied `blocked_by`, and same-status current `blocked` with caller-present `blocked_by` is distinct from pure status-only same-status
   - when no caller-present `status` remains after close/reopen routing, recognized `tags` accepted ownership requires `current_refinement_status_is_needs_refinement`
   - `None` for that fact is `CONTEXT_REQUIRED` only after proof-backed routing ownership exists
   - `False` routes to ordinary metadata
   - `True` routes to the collapsed marker-sensitive tags family
   - focused refinement versus ordinary metadata without caller-present `status` is decided after action routing
8. Assign exactly one public family and one public `path_id`.

Concrete ownership consequences:

- Any routed `update` payload with caller-present non-close/non-reopen `status` belongs to the target-specific lifecycle family even when ordinary metadata, `tags`, or focused-refinement section fields are co-present.
- Nonterminal `status + reopen_reason` payloads belong to the routed `status_target.*` lifecycle family, with `reopen_reason` in `ignored_raw_keys` only after probes prove that behavior.
- `status == "open"` with ordinary metadata, `tags`, or focused-refinement section fields is rejected by lifecycle validation before routed update ownership and does not enter lifecycle mixed-subpath coverage.
- Nonterminal `status + ordinary metadata` payloads that survive lifecycle validation remain lifecycle-owned and collapse into the same accepted status-target path unless the co-present key changes a public planner field or path-level claim.
- Lifecycle-owned `status + tags` payloads under active refinement use closed overlap-sensitive lifecycle subpath cells until probes settle whether the public path is the ordinary accepted status-target path or a marker-sensitive lifecycle subpath; this applies only to target statuses that survive lifecycle validation with `tags`.
- Lifecycle-owned `status +` focused-refinement section payloads remain lifecycle-owned; focused-refinement family ownership is reserved for routed update payloads without caller-present `status`, and mixed shapes with caller-present `status` remain closed overlap-sensitive lifecycle subpath cells until probes settle their public lifecycle subpath only where those target statuses survive lifecycle validation with section peers.
- For transition-to-blocked lifecycle paths, omitted `blocked_by` may consult `current_blocked_by`, while explicit `blocked_by: []` is a decisive `blocked_by_required` precondition-blocked path with no fallback to current blockers.
- For same-status current `blocked`, caller-present `blocked_by` produces a distinct accepted lifecycle subpath from pure `{"status": "blocked"}`. Value-level blocker-list equality versus mutation remains proof-only subcase detail unless a later plan-control patch widens public path identity.
- Pure nonterminal `{"reopen_reason": "..."}` belongs to `family.update.reopen.nonterminal_reason_ignored`.
- Terminal `{"status": "open"}` belongs to reopen ownership, including the missing-reason rejection path.
- Accepted routed `tags` classification without caller-present `status` requires `current_refinement_status_is_needs_refinement`; Slice 1A does not split preserve versus reinject marker mechanics.

The expected-inventory audit must use source-derived routing census to define the required denominator, but source census alone cannot promote public path ownership or public outcome claims. Every public routed path must have executable wrapper proof. Every routing-overlap cell must either have executable proof that settles its routed family/outcome or remain a private proof-control item that blocks Slice 1A completeness when required.

Source-derived denominator discovery must start from the live update wrapper:

1. derive the raw caller-admitted update field universe from `_ALLOWED_UPDATE_FIELDS` plus `_CLOSE_FIELDS` / `_REOPEN_FIELDS` lifecycle gates
2. include every validator rule reachable from those admitted fields, including reachable cross-field rules
3. exclude validator rules whose triggering fields are not reachable from the update wrapper
4. record those exclusions explicitly so drift is detectable if the wrapper later admits new fields

Validator denominator rules:

- The denominator must include each recognized update field's wrong-type bucket explicitly.
- The denominator must include each recognized update field's reachable invalid-value bucket explicitly.
- Public invalid paths may collapse multiple fields or rules only when live behavior proves the same public outcome, invalid bucket behavior, and caller-facing explanation shape.
- Validator rules for non-update fields such as `capture_confidence`, `source`, `defer`, `key_file_paths`, and `key_files` are explicit exclusions unless a rule is reachable through admitted update fields.
- Wrapper-synthesized internal fields, such as internal `refinement_status` preservation during tag updates, are not raw caller-admitted fields and do not become public manifest subject rows, public write effects, or normative public proof-entry content. Public `behavior_claim` may describe the user-visible effect. Exact internal mechanics may appear only in `source_anchors[probe_id]` as structured informative audit locators, or in non-public proof-control notes.

---

## Lifecycle Completeness Unit

Lifecycle coverage is measured by the matrix of `(current_status, lifecycle_intent_bucket)` for recognized lifecycle field-sets after raw carrier, key-set, recognized-field validation, lifecycle field-set validation, and wrapper action routing.

Required lifecycle intent buckets:

- `status_target.open`
- `status_target.in_progress`
- `status_target.blocked`
- `close_target.done`
- `close_target.wontfix`
- `reopen.by_reason`
- `reopen.status_open.reason_present`
- `reopen.status_open.reason_missing`
- `reopen_reason.nonterminal_ignored`

Same-status matrix cells:

- `(open, status_target.open)`
- `(in_progress, status_target.in_progress)`
- `(blocked, status_target.blocked)`

remain required lifecycle cells. They may stay private only until prepare+execute probes settle their wrapper-observable outcome; closeout requires public promotion rather than permanent private blockage.

Named lifecycle families below are public grouping projections over this matrix. They are not the sole completeness denominator.

Within recognized lifecycle families, current-state-invalid combinations are modeled as `PRECONDITION_BLOCKED` unless the raw payload is invalid or unsupported before lifecycle planning. Missing required raw fields after routed ownership, such as terminal `status=open` without `reopen_reason`, are `INVALID_PAYLOAD` unless executable proof shows a different wrapper-observable outcome.

Family-specific precedence and sufficiency rules:

- `close_done` precedence is fixed: dependency-blocked first, invalid transition second, collapsed done-readiness blocked path third, accepted close last.
- `close_done` uses minimal decisive context. If one supplied readiness fact already fixes the public blocked path, sibling missing facts do not force `CONTEXT_REQUIRED`.
- Private `close_done` readiness must mirror live Acceptance Criteria placeholder normalization so lines that normalize to exactly `["Needs refinement"]` block the same collapsed public path.
- Lifecycle blocker resolution may use decisive partial `referenced_ticket_statuses` maps for the collapsed dependency-blocked public path. Full blocker-status coverage is required only when omitted blocker statuses could still change the public outcome away from blocked.
- `status_target.blocked` distinguishes transition-to-blocked omitted `blocked_by` fallback from explicit caller-supplied `blocked_by`. Explicit empty `blocked_by` is a decisive `PRECONDITION_BLOCKED` path; omitted `blocked_by` may require `current_blocked_by` to classify; explicit non-empty `blocked_by` does not fall back to current blockers.
- `(blocked, status_target.blocked)` plus caller-present `blocked_by` is a distinct accepted same-status lifecycle subpath from pure `{"status": "blocked"}`. Explicit empty versus non-empty same-status blocker lists remain proof subcases unless later proof or plan control requires a wider public split.

The expected-inventory fixture and path-derivation audit must prove:

- every recognized lifecycle matrix cell is covered by exactly one required family or blocked by a named private proof-control item or named closed overlap-sensitive cell
- every valid transition in `_VALID_TRANSITIONS` is represented by one or more required matrix cells
- every recognized terminal or current-state-invalid lifecycle combination resolves to public path coverage or a named private proof-control item or named closed overlap-sensitive cell
- no lifecycle family can claim completeness while omitting a reachable matrix cell

---

## Path Taxonomy And Manifest Rules

### Public Path Naming Rules

Public `path_id` rules:

- Prefix: `path.update.`
- Path-first, not mechanism-first
- One public `path_id` per normalized wrapper-observable behavior path
- Different outcomes for one path family require distinct `path_id` values
- Public `path_id` values must not contain `rule`, `group`, `raw_shape`, `planner`, `family`, or evaluator-phase nouns before the behavior path

Illustrative public path shapes:

- `path.update.frontmatter.priority.accepted`
- `path.update.focused.concrete_refinement.clears_marker`
- `path.update.lifecycle.close_done.precondition_blocked.missing_acceptance_criteria`
- `path.update.lifecycle.status_target_in_progress.accepted.same_status`
- `path.update.lifecycle.status_target_blocked.precondition_blocked.explicit_empty_blocked_by`
- `path.update.lifecycle.status_target_blocked.accepted.same_status_with_blocked_by`
- `path.update.reopen.nonterminal_reason_ignored`

Private proof-control naming:

- `probe_question.update.*`
- `quarantine.update.*`

Those private IDs must never appear in public planner output or public manifest sections.

### Public Manifest Shape

`export_update_policy_manifest()` must export only public, proof-backed, path-first data. Required top-level sections:

```python
{
    "schema_version": "...",
    "policy_version": "...",
    "covered_mutation_surfaces": ["update"],
    "deferred_mutation_surfaces": ["capture", "ingest"],
    "paths": {...},
    "proofs": {...},
    "source_anchors": {...},
}
```

Exported manifest carrier-shape rules:

- `export_update_policy_manifest()` returns exact built-in JSON-serializable carriers only: built-in `dict`, built-in `list`, `str`, `int`, finite `float`, `bool`, or `None`.
- The top-level manifest is a built-in `dict` with exactly the keys shown above.
- `schema_version` and `policy_version` are `str`.
- `covered_mutation_surfaces` is a built-in `list[str]` with value `["update"]`.
- `deferred_mutation_surfaces` is a built-in `list[str]` with value `["capture", "ingest"]`.
- `paths` is a built-in `dict[str, dict[str, object]]` keyed by public `path_id`.
- `proofs` is a built-in `dict[str, dict[str, object]]` keyed by public `probe_id`.
- `source_anchors` is a built-in `dict[str, list[dict[str, object]]]` keyed by public `probe_id`.
- Exported manifest collections must not use tuples, sets, dataclass instances, enum instances, mapping subclasses, sequence subclasses, or custom carrier objects. Production registry rows and test fixtures may use immutable private carriers internally, but public export must convert to this exact shape.
- Exported lists are order-significant and must use the canonical ordering rules below. Fixture parity must compare list order exactly rather than treating exported lists as unordered sets.
- Built-in `dict` key order is not compatibility-significant. Contract parity compares exact key sets and values; implementations may emit deterministic lexical dict insertion order for review hygiene, but dict insertion order is not public policy identity.

Each public path entry in `paths[path_id]` must be a built-in `dict` with exactly:

- `path_id: str`, matching the enclosing `path_id` key
- `outcome: str`, using the public `UpdatePathOutcome` value
- `behavior_claim: str`
- `required_context_fields: list[str]`
- `behavior_proof_ids: list[str]`

Path-entry list ordering rules:

- `required_context_fields` is emitted in public `UpdateMutationContext` declaration order: `current_status`, `current_refinement_status_is_needs_refinement`, `current_acceptance_criteria_lines`, `current_blocked_by`, `referenced_ticket_statuses`.
- `behavior_proof_ids` is emitted in lexical `probe_id` order.
- Duplicate list items are invalid exported schema.

`behavior_claim` rules:

- exactly one sentence
- behavior-only
- no implementation mechanism
- no recovery instruction
- no source reference
- no speculative future wording
- may reference caller-admitted raw update fields, public context names, and stable user-visible ticket concepts or literal values
- must not reference synthesized internal fields, private helper flags, or non-public implementation details
- should prefer user-facing concept wording over raw field names when either is clear

Anything returned by `export_update_policy_manifest()` is public for its `policy_version`.

Each public proof entry in `proofs[probe_id]` must be a built-in `dict` with exactly these normative wrapper-observable fields:

```python
{
    "proof_id": "probe.update...",
    "proof_scope": "<prepare_only|prepare_execute>",
    "observable_facets": [...],
    "required_observed_behavior": "...",
}
```

Proof schema rules:

- `proof_id` must match the enclosing `probe_id` key.
- `proof_scope` is either `prepare_only` or `prepare_execute`.
- `observable_facets` is a built-in `list[str]` of controlled public-observable facet names from: `outcome`, `context_gate`, `precondition_gate`, `bucket_membership`, `wrapper_effect`.
- `observable_facets` is emitted in the controlled vocabulary order above, omitting facets that do not apply.
- `required_observed_behavior` is exactly one sentence describing wrapper-observable behavior only.
- Proof entries may describe raw update shape, required public context facts, stage, public outcome, and public bucket behavior.
- Proof entries must not require internal helper calls, synthesized internal fields, private flags, or private write mechanics as observed behavior.
- Duplicate `observable_facets` items and extra proof-entry keys are invalid exported schema.

Public proof obligations and informative audit locators live in separate manifest sections:

- `proofs[probe_id]` contains compatibility-significant normative proof data.
- `source_anchors[probe_id]` contains informative audit locators for that proof ID.
- `paths[path_id]` references evidence only through `behavior_proof_ids`.

The public manifest must not contain:

- unresolved probe questions
- quarantined candidate paths
- path-local `source_anchors`
- public `effects` sections
- public `materializations` sections
- internal rule IDs
- internal group-rule IDs
- raw-shape IDs
- dispatch tables
- evaluator topology
- direct-engine discrepancy sections

### Public Proof And Anchor Policy

- `behavior_proof_ids` are public and compatibility-significant within `policy_version`.
- `proofs[probe_id]` entries are public and keyed by stable `probe.*` IDs.
- Changing a path's `behavior_proof_ids` or a proof entry's required observed behavior requires a `policy_version` bump.
- `source_anchors[probe_id]` entries are public-readable and informative. They are not behavior claims, not public schema for raw fields, and not a source of additional caller-admitted vocabulary.
- Every public `proofs[probe_id]` entry must have a corresponding non-empty `source_anchors[probe_id]` entry.
- Every `source_anchors[probe_id]` value must be a non-empty built-in `list` of built-in anchor `dict` entries.
- Every `source_anchors[probe_id]` entry must include at least one anchor with role `oracle_test`.
- Supporting implementation-source anchors are allowed but never sufficient on their own.
- `source_anchors[*].role` is a public schema-stable enum with allowed values `oracle_test` and `supporting_source`.
- `source_anchors[probe_id]` lists are emitted in stable anchor order: `oracle_test` anchors before `supporting_source` anchors; within each role, sort by `path`, resolver field name with `test_name` before `symbol`, and resolver value.
- Duplicate anchors with the same `role`, `path`, resolver field name, and resolver value are invalid exported schema. Optional `line` is not part of anchor identity or ordering.
- Each anchor dict must contain exactly `role: str`, `path: str`, exactly one stable resolver field (`symbol: str` or `test_name: str`), and optional `line: int`. Extra anchor keys are invalid exported schema.
- `line: int` is optional best-effort current-location metadata. If `path` and stable resolver succeed but `line` differs from the current resolved location, source-anchor audit reports a non-blocking stale-line warning. Line drift alone does not block implementation and does not require a `policy_version` bump.
- Source-anchor audit fails if `path` resolution fails, the stable resolver fails, role vocabulary is invalid, a public proof lacks anchors, a proof lacks an `oracle_test` anchor, or anchors exist for non-existent/publicly-unreachable proof IDs.
- Changing only `source_anchors[probe_id]` locator values requires no `policy_version` bump when proof entries and path `behavior_proof_ids` are unchanged.
- Changes limited to `source_anchors` schema shape, placement, or role vocabulary require a `schema_version` bump after export exists, not a `policy_version` bump, unless they also change normative proof obligations, `behavior_proof_ids`, or required observed behavior.

Version finalization rules:

- Do not finalize a public `schema_version` during proof-control. Before implementation/export exists, schema-shape churn is carried by `CONTROL_PLAN_REVISION`.
- Do not finalize a public `policy_version` until the closed overlap-sensitive list is fully declared and reconciled with source-derived audit results, every required lifecycle matrix cell is proof-backed public coverage or a plan-scoped exclusion, no required unresolved private proof-control item or blocking overlap-sensitive cell remains, and the pre-kernel proof-control baseline passes.
- Pre-kernel fixtures and tests must not invent release-like public `schema_version` or `policy_version` values. Any internal placeholder for either value must be explicitly marked unfinalized and non-exportable. `schema_version` placeholders must not be treated as exported schema compatibility values until the manifest schema is settled, implementation exists, and the public export is ready to freeze.
- After the exported manifest exists, schema-only exported shape changes bump `schema_version`; normative behavior, public path, required context, `behavior_proof_ids`, or required observed behavior changes bump `policy_version`; anchor value drift bumps neither.

---

## Required Update Path Families

This plan is normative at the path-family level. The expected-inventory fixture owns the exact leaf `path_id` set.

| family_id | required | raw shapes covered | allowed context facts | possible outcomes | proof depth | public path prefix |
| --- | --- | --- | --- | --- | --- | --- |
| `family.update.validation.raw_carrier` | yes | non-object JSON-native update carriers | none | `INVALID_PAYLOAD` | prepare-only | `path.update.validation.raw_carrier.*` |
| `family.update.validation.unknown_or_forbidden_keys` | yes | unknown keys, unsupported namespaces, lifecycle-forbidden peer fields | none | `UNSUPPORTED_PAYLOAD` | prepare-only | `path.update.validation.unsupported.*` |
| `family.update.validation.recognized_field_type_or_value` | yes | recognized update fields with wrong JSON-native type or invalid value bucket | none | `INVALID_PAYLOAD` | prepare-only | `path.update.validation.invalid.*` |
| `family.update.frontmatter.metadata` | yes | routed `update` frontmatter updates without caller-present `status`, excluding wrapper-transformed refinement-marker tag paths | none unless path-specific proof shows otherwise | `ACCEPTED`, `INVALID_PAYLOAD`, `UNSUPPORTED_PAYLOAD` | prepare+execute for accepted | `path.update.frontmatter.*` |
| `family.update.frontmatter.tags_refinement_marker` | yes | routed `update` `tags` updates without caller-present `status` whose public behavior under active refinement keeps the `needs-refinement` marker effective | `current_refinement_status_is_needs_refinement` | `ACCEPTED`, `INVALID_PAYLOAD`, `UNSUPPORTED_PAYLOAD`, `CONTEXT_REQUIRED` when proof-backed routing ownership exists and the discriminator is missing | prepare+execute for accepted | `path.update.frontmatter.tags_refinement_marker.*` |
| `family.update.focused_refinement` | yes | routed `update` focused refinement field families without caller-present `status`, including marker clear behavior tied to focused refinement updates | `current_refinement_status_is_needs_refinement` when required by the public claim | `ACCEPTED`, `INVALID_PAYLOAD`, `UNSUPPORTED_PAYLOAD`, `CONTEXT_REQUIRED` when a proof-backed direct fact is required | prepare+execute for accepted; prepare-only for blocked/error paths | `path.update.focused.*` |
| `family.update.lifecycle.status_target_open` | yes | routed `update` payloads with caller-present `status` targeting `open`, including accepted transitions, blocker-resolved accepted transitions from current `blocked`, same-status accepted paths, nonterminal mixed `status + reopen_reason`, and nonterminal current-state-invalid matrix cells; mixed ordinary metadata, `tags`, and focused-refinement section peers are excluded because live lifecycle validation rejects them before routed update ownership | `current_status`, `current_blocked_by`, `referenced_ticket_statuses` when the matrix cell or lifecycle subpath requires them | `ACCEPTED`, `CONTEXT_REQUIRED`, `PRECONDITION_BLOCKED`, `INVALID_PAYLOAD`, `UNSUPPORTED_PAYLOAD` | prepare+execute for accepted; prepare-only for blocked/error paths | `path.update.lifecycle.status_target_open.*` |
| `family.update.lifecycle.status_target_in_progress` | yes | routed `update` payloads with caller-present `status` targeting `in_progress`, including accepted transitions, blocker-resolved accepted transitions from current `blocked`, same-status accepted paths, nonterminal mixed `status + reopen_reason`, mixed ordinary metadata, active-refinement `tags` lifecycle subpaths, focused-refinement section lifecycle subpaths, and current-state-invalid matrix cells | `current_status`, `current_refinement_status_is_needs_refinement`, `current_blocked_by`, `referenced_ticket_statuses` when the matrix cell or lifecycle subpath requires them | `ACCEPTED`, `CONTEXT_REQUIRED`, `PRECONDITION_BLOCKED`, `INVALID_PAYLOAD`, `UNSUPPORTED_PAYLOAD` | prepare+execute for accepted; prepare-only for blocked/error paths | `path.update.lifecycle.status_target_in_progress.*` |
| `family.update.lifecycle.status_target_blocked` | yes | routed `update` payloads with caller-present `status` targeting `blocked`, including accepted transitions from current `open` or `in_progress`, transition-to-blocked omitted-`blocked_by` fallback paths, transition-to-blocked explicit-empty-`blocked_by` blocked paths, same-status accepted paths, same-status accepted paths with caller-present `blocked_by`, mixed ordinary metadata, active-refinement `tags` lifecycle subpaths, focused-refinement section lifecycle subpaths, nonterminal mixed `status + reopen_reason`, and current-state-invalid matrix cells | `current_status`, `current_refinement_status_is_needs_refinement`, `current_blocked_by` when the matrix cell or lifecycle subpath requires it | `ACCEPTED`, `CONTEXT_REQUIRED`, `PRECONDITION_BLOCKED`, `INVALID_PAYLOAD`, `UNSUPPORTED_PAYLOAD` | prepare+execute for accepted; prepare-only for blocked/error paths | `path.update.lifecycle.status_target_blocked.*` |
| `family.update.lifecycle.close_done` | yes | recognized close-as-done payloads | `current_status`, `current_refinement_status_is_needs_refinement`, `current_acceptance_criteria_lines`, `current_blocked_by`, `referenced_ticket_statuses` | `ACCEPTED`, `CONTEXT_REQUIRED`, `PRECONDITION_BLOCKED`, `INVALID_PAYLOAD`, `UNSUPPORTED_PAYLOAD` | prepare+execute for accepted; prepare-only for blocked/error paths | `path.update.lifecycle.close_done.*` |
| `family.update.lifecycle.close_wontfix` | yes | recognized close-as-wontfix payloads | `current_status` | `ACCEPTED`, `CONTEXT_REQUIRED`, `PRECONDITION_BLOCKED`, `INVALID_PAYLOAD`, `UNSUPPORTED_PAYLOAD` | prepare+execute for accepted; prepare-only for blocked/error paths | `path.update.lifecycle.close_wontfix.*` |
| `family.update.reopen.terminal_by_reason` | yes | routed `reopen` payloads, including terminal `reopen_reason`, terminal `status=open` with reason present, terminal `status=open` with reason missing, and terminal mixed `status + reopen_reason` forms | `current_status` | `ACCEPTED`, `CONTEXT_REQUIRED`, `PRECONDITION_BLOCKED`, `INVALID_PAYLOAD`, `UNSUPPORTED_PAYLOAD` | prepare+execute for accepted; prepare-only for blocked/error paths | `path.update.reopen.terminal_by_reason.*` |
| `family.update.reopen.nonterminal_reason_ignored` | yes | pure nonterminal `reopen_reason` syntax after routing, blocked by the named overlap cell until behavior proof settles the accepted update-route write path | `current_status` | `ACCEPTED` after proof-backed promotion | prepare+execute | `path.update.reopen.nonterminal_reason_ignored.*` |

The expected-inventory fixture must satisfy:

- every fixture `path_id` maps to exactly one `family_id`
- every required family is fully covered by fixture paths or blocked by named private proof-control items or named closed overlap-sensitive cells declared in this plan
- no fixture `path_id` exists for a family omitted from this plan
- `family_id` remains fixture/test-only proof-control metadata and must not appear in production registry rows or public exports

Until executable proof promotes routed ownership, required families may remain incomplete only through named private proof-control items or through named closed overlap-sensitive cells whose `allowed blocking family/families` column lists that exact family. The fixture must not satisfy any family with an ad hoc blocker identity.

---

## Closed Overlap-Sensitive Cells

The following semantic overlap-sensitive cells are closed for this `CONTROL_PLAN_REVISION`. The fixture owns exact machine-readable cell IDs and probe mappings for this set.

| semantic_cell | raw shape | routed ownership question | discriminating fact(s) | required proof family | allowed blocking family/families | blocks completeness |
| --- | --- | --- | --- | --- | --- | --- |
| `overlap.update.tags.refinement_state` | recognized `tags` update | ordinary metadata versus marker-sensitive tags behavior | `current_refinement_status_is_needs_refinement` | `probe.update.tags.refinement_state.*` | `family.update.frontmatter.metadata`; `family.update.frontmatter.tags_refinement_marker` | yes |
| `overlap.update.lifecycle.status_tags.refinement_state` | `{"status": "in_progress" \| "blocked", "tags": ...}` after close/reopen routing | ordinary accepted lifecycle status-target path versus marker-sensitive lifecycle status-target subpath | `current_refinement_status_is_needs_refinement` | `probe.update.lifecycle.status_tags.refinement_state.*` | `family.update.lifecycle.status_target_in_progress`; `family.update.lifecycle.status_target_blocked` | yes |
| `overlap.update.lifecycle.status_focused_refinement.sections` | `{"status": "in_progress" \| "blocked", <focused-refinement section field(s)>}` after close/reopen routing | ordinary accepted lifecycle status-target path versus lifecycle focused-refinement section subpath | none after close/reopen routing | `probe.update.lifecycle.status_focused_refinement.sections.*` | `family.update.lifecycle.status_target_in_progress`; `family.update.lifecycle.status_target_blocked` | yes |
| `overlap.update.reopen.pure_reason_by_status` | pure `{"reopen_reason": "..."}` | terminal reopen versus nonterminal ignored syntax | `current_status` | `probe.update.reopen.pure_reason_by_status.*` | `family.update.reopen.terminal_by_reason`; `family.update.reopen.nonterminal_reason_ignored` | yes |
| `overlap.update.reopen.status_open_reason_present` | `{"status": "open", "reopen_reason": "..."}` | terminal reopen versus routed update status-target behavior | `current_status` | `probe.update.reopen.status_open_reason_present.*` | `family.update.reopen.terminal_by_reason`; `family.update.lifecycle.status_target_open` | yes |
| `overlap.update.reopen.status_open_reason_missing` | `{"status": "open"}` | terminal reopen missing-reason rejection versus nonterminal routed update status-target behavior | `current_status` | `probe.update.reopen.status_open_reason_missing.*` | `family.update.reopen.terminal_by_reason`; `family.update.lifecycle.status_target_open` | yes |
| `overlap.update.reopen.mixed_status_reason_by_status` | `{"status": "in_progress" \| "blocked", "reopen_reason": "..."}` | terminal reopen ownership versus nonterminal routed status-target ownership with `reopen_reason` ignored | `current_status` | `probe.update.reopen.mixed_status_reason_by_status.*` | `family.update.reopen.terminal_by_reason`; `family.update.lifecycle.status_target_in_progress`; `family.update.lifecycle.status_target_blocked` | yes |

Rules:

- The plan owns this closed semantic set. The fixture owns the executable projection.
- The source-derived audit must scan live routing and transformation points and fail closed if it detects an overlap-sensitive candidate not present in this list and not declared by a prior plan-control patch.
- If a new candidate is detected, proof-control hard-stops. The audit may emit a deterministic failure record naming the candidate and source anchors, but the fixture must not gain a committed or passing `probe_question.*` / `quarantine.*` row for that candidate until this plan declares it and `CONTROL_PLAN_REVISION` changes.
- Changes to this list require a `CONTROL_PLAN_REVISION` bump. They require a `policy_version` bump only after export exists and only when public path IDs, outcomes, required context fields, behavior claims, `behavior_proof_ids`, or normative proof obligations change.
- Public `CONTEXT_REQUIRED` paths for these cells require proof-backed routed ownership first.
- The lifecycle-owned `status + tags` and `status +` focused-refinement section cells declared here are overlap-sensitive even though caller-present `status` has already frozen top-level family ownership; these cells settle lifecycle subpath identity, required context, and public behavior claim rather than cross-family ownership transfer.
- A closed overlap-sensitive cell whose `blocks completeness` value is `yes` may block required-family completeness only for the exact family IDs listed in its `allowed blocking family/families` column and only while executable proof has not settled its routed ownership and public outcome.
- Proof-control audit fails if a fixture uses an overlap cell to block an unlisted family, a required family claims overlap-cell blockage from a cell that does not list it, or a `blocks completeness=yes` cell has no allowed-family binding.
- After proof settles the cell, the fixture must promote the affected family to public coverage, convert the blocker through an explicit plan-control patch, or narrow Slice 1A scope through a plan-control patch.

---

## Private Proof-Control Inventory

Private proof-control items are required semantic obligations, not prose TODOs.

| private_id | kind | question | required_probe | promotion rule | removal rule | blocks Slice 1A completeness |
| --- | --- | --- | --- | --- | --- | --- |
| `probe_question.update.lifecycle.same_status.open` | probe question | What does the wrapper do for `{"status": "open"}` on current `open`? | `probe.update.lifecycle.same_status.open` | Promote only after prepare+execute proof settles a public outcome and public `path_id`. | Remove only by proof-backed promotion or plan-control scope narrowing. | yes |
| `probe_question.update.lifecycle.same_status.in_progress` | probe question | What does the wrapper do for `{"status": "in_progress"}` on current `in_progress`? | `probe.update.lifecycle.same_status.in_progress` | same as above | same as above | yes |
| `probe_question.update.lifecycle.same_status.blocked` | probe question | What does the wrapper do for `{"status": "blocked"}` on current `blocked`, with and without current blockers? | `probe.update.lifecycle.same_status.blocked` | same as above | same as above | yes |

Rules:

- Private proof-control IDs must not appear in `export_update_policy_manifest()` or `UpdateManifestPlan.path_id`.
- Closed overlap-sensitive cells are private proof-control obligations until executable proof promotes their public routed ownership.
- A required unresolved private item or required blocking overlap-sensitive cell blocks Slice 1A completeness until:
  1. proof-backed promotion creates public path(s), or
  2. a plan-control patch narrows Slice 1A scope and updates the completeness claim

---

## Expected-Inventory Fixture And Audits

Pre-kernel expected-inventory fixture:

- `plugins/turbo-mode/ticket/tests/support/update_authority_slice1a_expected.py`

This fixture must own:

- `EXPECTED_INVENTORY_REVISION` matching the `CONTROL_PLAN_REVISION` extracted from this plan's dedicated sentinel block
- exact public `path_id` inventory
- exact `path_id -> behavior_proof_ids` mapping
- exact public `proofs[probe_id]` normative entries
- exact exported manifest carrier-shape, row key-closure, and canonical list-order expectations
- exact public `source_anchors[probe_id]` schema, row key-closure, and canonical anchor-order expectations
- exact planner scenario table with at least one reachable scenario per public `path_id`
- proof-gated public manifest section expectations
- required private `probe_question.*` and `quarantine.*` items
- naming grammar and family-to-path mapping projection
- closed overlap-sensitive cell projection, including exact allowed blocker family bindings
- lifecycle matrix cell projection
- reachable validator-rule denominator and explicit exclusion ledger for non-update validator rules

Required pre-kernel audits:

- `plugins/turbo-mode/ticket/tests/test_update_authority_path_derivation.py`
- `plugins/turbo-mode/ticket/tests/test_update_authority_behavior_proof_coverage.py`

Required post-kernel audits:

- `plugins/turbo-mode/ticket/tests/test_update_authority_contract.py`
- `plugins/turbo-mode/ticket/tests/test_update_authority_source_anchors.py`
- `plugins/turbo-mode/ticket/tests/test_update_authority_phase_gate.py`

Audit expectations:

- plan revision and fixture revision match exactly
- the only Markdown content machine-parsed by audits is the dedicated revision-handshake sentinel block
- every public path has canonical proof coverage
- every public path has one `behavior_claim`
- every public `probe_id` has a thin structured proof entry and a non-empty `source_anchors[probe_id]` entry with at least one `oracle_test` anchor
- every manifest `path_id` resolves only public data
- no path entry contains `source_anchors`
- no public `effects`, `materializations`, `effect_ids`, or `materialization_ids` appear in the exported manifest
- no private proof-control ID leaks into public planner output or public manifest
- no internal topology leaks into public planner output or public manifest
- lifecycle matrix coverage is complete for every required `(current_status, lifecycle_intent_bucket)` cell or blocked by a named private proof-control item or named closed overlap-sensitive cell
- same-status private blockers remain temporary only; once required probes settle them, proof-control must promote them to public coverage rather than leave them private
- source-derived routing census defines the denominator, but executable wrapper probes prove every public routed path and every overlap-sensitive routed ownership claim
- source-derived audit hard-stops on any undeclared overlap-sensitive candidate; the fixture must not absorb it before a plan-control patch
- every recognized update field has explicit wrong-type denominator coverage, and every reachable invalid-value validator rule has explicit denominator coverage
- public invalid paths collapse multiple fields or validator rules only when proof shows identical public outcome and bucket behavior
- every public `path_id` has at least one fixture-owned planner scenario that emits it
- every planner scenario asserts the full public planner result surface: `path_id`, `outcome`, all raw-key buckets, `missing_context_fields`, and linked `behavior_proof_ids`
- every planner scenario's linked proof IDs are non-empty and a subset of that path's manifest `behavior_proof_ids`
- for each public path, the union of linked proof IDs across planner scenarios equals the path's manifest `behavior_proof_ids`
- every public `CONTEXT_REQUIRED` scenario has enough resolved-context companion scenarios to prove the adjacent routed ownership and reachable resolved outcome classes

---

## Source Files To Read First

Read these live files before implementation or proof-control work. Historical handoffs, prior reviews, and this plan are not substitutes for current source truth.

- `plugins/turbo-mode/ticket/README.md`
- `plugins/turbo-mode/ticket/HANDBOOK.md`
- `plugins/turbo-mode/ticket/references/ticket-contract.md`
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- `plugins/turbo-mode/ticket/scripts/ticket_update.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- `plugins/turbo-mode/ticket/scripts/ticket_validate.py`
- `plugins/turbo-mode/ticket/scripts/ticket_workflow.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- `plugins/turbo-mode/ticket/tests/test_engine_policy.py`
- `plugins/turbo-mode/ticket/tests/test_execute.py`
- `plugins/turbo-mode/ticket/tests/test_workflow.py`
- `plugins/turbo-mode/ticket/tests/test_update_refinement.py`

Read-only scans before proof-control or implementation:

```bash
rg -n "_ALLOWED_UPDATE_FIELDS|_CLOSE_FIELDS|_REOPEN_FIELDS|_action_and_fields|_prepare_fields|_will_clear_refinement|_validate_lifecycle_payload|validate_fields|_check_legacy_gate|_check_transition_preconditions_with_detail|_normalize_acceptance_criterion|_acceptance_criteria_is_only_needs_refinement|_ticket_still_needs_refinement|_classify_blockers|reopen_reason|needs-refinement|unsupported_update_fields|ticket_id|update_prepare|target_fingerprint|execute_fingerprint|stale_plan" \
  plugins/turbo-mode/ticket/scripts/ticket_update.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/scripts/ticket_validate.py \
  plugins/turbo-mode/ticket/tests/test_engine_policy.py \
  plugins/turbo-mode/ticket/tests/test_execute.py \
  plugins/turbo-mode/ticket/tests/test_workflow.py \
  plugins/turbo-mode/ticket/tests/test_update_refinement.py
```

---

## File Structure

- `docs/superpowers/plans/2026-05-22-ticket-authority-kernel-slice1.md` - superseded historical full-surface plan; not implementation authority.
- `docs/superpowers/plans/2026-05-25-ticket-authority-kernel-slice1a-update-only.md` - Slice 1A semantic authority.
- `plugins/turbo-mode/ticket/scripts/ticket_update_authority.py` - new pure update-only authority module.
- `plugins/turbo-mode/ticket/tests/support/update_authority_slice1a_expected.py` - exact public path inventory and private proof-control projection.
- `plugins/turbo-mode/ticket/tests/test_update_authority_path_derivation.py` - branch census and path-derivation audit.
- `plugins/turbo-mode/ticket/tests/test_update_authority_behavior_proof_coverage.py` - machine-checked path-to-proof coverage audit.
- `plugins/turbo-mode/ticket/tests/test_update_authority_contract.py` - public planner and public manifest contract tests.
- `plugins/turbo-mode/ticket/tests/test_update_authority_source_anchors.py` - live source-anchor resolution tests.
- `plugins/turbo-mode/ticket/tests/test_update_authority_phase_gate.py` - no-integration, no-generic-facade, and public-surface leakage guards.
- `plugins/turbo-mode/ticket/README.md`
- `plugins/turbo-mode/ticket/HANDBOOK.md`
- `plugins/turbo-mode/ticket/references/ticket-contract.md`
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py`

---

## Branch And Worktree Gate

Run from `/Users/jp/Projects/active/codex-tool-dev`.

```bash
git fetch origin main
git status --short --branch --untracked-files=all
git rev-parse --abbrev-ref HEAD
git rev-parse origin/main
git merge-base HEAD origin/main
git rev-list --left-right --count origin/main...HEAD
git merge-base --is-ancestor origin/main HEAD
git worktree list --porcelain
```

Expected before proof-control or implementation:

- branch is `chore/ticket-authority-kernel-slice1` unless a new non-`main` task branch is deliberately recorded
- `git merge-base --is-ancestor origin/main HEAD` exits `0`
- `git rev-list --left-right --count origin/main...HEAD` has left count `0`
- worktree is clean after the plan-control commit
- no merge, rebase, cherry-pick, revert, or bisect is active

Hard stop:

- if `origin/main` has commits not contained in `HEAD`, stop
- if `origin/main` cannot be fetched or resolved, stop unless the plan is patched into a pinned local-base mode

---

## Commit Boundaries

- Plan-control commit:
  - old plan supersession banner
  - new Slice 1A plan
- Pre-kernel proof-control commit:
  - expected-inventory fixture
  - path-derivation audit
  - behavior-proof coverage audit
  - focused wrapper-facing probes needed to settle required public paths
  - must not create `ticket_update_authority.py`
- Implementation commit:
  - `ticket_update_authority.py`
  - public manifest and public planner contract tests
  - source-anchor and phase-gate tests
  - docs contract updates for the new update-only authority mirror

Suggested commit messages:

```text
docs(superpowers): draft ticket update authority slice 1a plan
test(ticket): add update authority proof-control scaffold
chore(ticket): add update authority slice 1a kernel
```

---

## Verification Harness

Pre-kernel proof-control baseline:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q \
  tests/test_engine_policy.py \
  tests/test_execute.py \
  tests/test_workflow.py \
  tests/test_update_refinement.py
```

Pre-kernel proof-control audits:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q \
  tests/test_update_authority_path_derivation.py \
  tests/test_update_authority_behavior_proof_coverage.py
```

Post-kernel verification minimum:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q \
  tests/test_docs_contract.py \
  tests/test_engine_policy.py \
  tests/test_execute.py \
  tests/test_workflow.py \
  tests/test_update_refinement.py \
  tests/test_update_authority_path_derivation.py \
  tests/test_update_authority_behavior_proof_coverage.py \
  tests/test_update_authority_contract.py \
  tests/test_update_authority_source_anchors.py \
  tests/test_update_authority_phase_gate.py
```

Changed-path lint:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check \
  plugins/turbo-mode/ticket/scripts/ticket_update_authority.py \
  plugins/turbo-mode/ticket/tests/support/update_authority_slice1a_expected.py \
  plugins/turbo-mode/ticket/tests/test_update_authority_path_derivation.py \
  plugins/turbo-mode/ticket/tests/test_update_authority_behavior_proof_coverage.py \
  plugins/turbo-mode/ticket/tests/test_update_authority_contract.py \
  plugins/turbo-mode/ticket/tests/test_update_authority_source_anchors.py \
  plugins/turbo-mode/ticket/tests/test_update_authority_phase_gate.py \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py
```

Whitespace gate:

```bash
git diff --check
```

---

## Stop Conditions

- Stop if proof-control or implementation starts treating `capture` or `ingest` as callable Slice 1A authority surfaces.
- Stop if proof-control or implementation creates `ticket_authority.py`, a generic facade, or a public normalized classifier.
- Stop if `ticket_update_authority.py` is created, imported, or edited before the pre-kernel proof-control baseline and audit commands pass.
- Stop if implementation discovers a need to read ticket files, import runtime Ticket modules, or inspect installed runtime state to classify a path.
- Stop if Task 2 implementation performs fresh source-census discovery, wrapper-branch enumeration, semantic inventory expansion, or fallback path invention instead of consuming the settled proof-control projection.
- Stop if `ticket_update_authority.py` imports from `plugins/turbo-mode/ticket/tests/` or from the expected-inventory fixture.
- Stop if production registry rows contain `family_id`, private proof-control IDs, overlap-cell IDs, lifecycle matrix IDs, or callable predicates.
- Stop if implementation tries to export direct-engine discrepancy sections or public internal topology.
- Stop if `source_anchors` appear inside `paths[path_id]` instead of the top-level `source_anchors[probe_id]` map.
- Stop if a public proof lacks a non-empty `source_anchors[probe_id]` entry or lacks at least one `oracle_test` anchor.
- Stop if unresolved probe questions or quarantined candidates appear in the public manifest or public planner output.
- Stop if a required family or blocking overlap-sensitive cell remains private at Slice 1A closeout without formal scope narrowing.
- Stop if an unresolved probe question or unresolved required overlap-sensitive cell blocks a required family. Resume only after proof-backed promotion, an explicit plan-control blocker conversion, or a plan-control scope patch narrows Slice 1A and updates the completeness claim.
- Stop if source-derived audit detects an undeclared overlap-sensitive candidate. Resume only after plan-control patch declares it, bumps `CONTROL_PLAN_REVISION`, and fixture projection updates.
- Stop if implementation needs `ticket.generation`, `contract_version`, migration state, or legacy write-policy facts to classify a public path. Resume only after a separate ticket-format/write-policy slice is defined.
- Stop if implementation needs full current metadata or section-value equality to classify ordinary same-value updates as public `NO_OP`.
- Stop if implementation emits public `NO_OP` for same-status lifecycle paths, pure nonterminal `reopen_reason`, or any path that still reaches an engine write such as `contract_version` stamping.
- Stop if implementation transfers caller-present non-close/non-reopen `status` payloads to `family.update.frontmatter.*` or `family.update.focused_refinement` instead of keeping lifecycle ownership.
- Stop if fixture or implementation collapses transition-to-blocked omitted `blocked_by` fallback with explicit caller-supplied empty `blocked_by`, or collapses same-status current `blocked` plus caller-present `blocked_by` into the pure status-only same-status path without a plan-control patch.
- Stop if a public path family cannot be described without membrane facts such as trust, request origin, or runtime readiness.
- Stop if non-finite floats or non-JSON-native Python objects are being converted into public payload paths instead of `AuthorityInputError`.
- Stop if `context=None`, context subclasses, duck-typed contexts, raw-string enum context values, extra-key `referenced_ticket_statuses`, or malformed AC-line values are treated as missing context instead of API misuse.
- Stop if duplicate `current_blocked_by` IDs are rejected as API misuse, or if decisive partial `referenced_ticket_statuses` maps that already prove the collapsed dependency-blocked public path are rejected as insufficient context.

---

## Closeout Rule

Slice 1A is complete only when every current post-membrane in-scope inner-update-object wrapper behavior path is accounted for by the expected-inventory fixture and machine audits.

Each in-scope path must be exactly one of:

1. proof-backed active public path
2. proof-backed `NO_OP` public path
3. proof-backed `CONTEXT_REQUIRED` public path
4. proof-backed `PRECONDITION_BLOCKED` public path
5. proof-backed `INVALID_PAYLOAD` or `UNSUPPORTED_PAYLOAD` public path
6. proof-backed explicit exclusion from Slice 1A by plan scope

Candidate-only or quarantined status is not a valid closeout state for a required Slice 1A family.

Also do not claim Slice 1A complete unless:

- every public path is dynamically reachable from `plan_update_manifest_for_payload(...)` through at least one fixture-owned planner scenario
- every planner scenario asserts the full public result surface and links to canonical proof IDs
- every public proof has an `oracle_test` anchor
- no closed overlap-sensitive cell remains private or unproven unless a plan-control patch narrows the slice
- public `schema_version` and `policy_version` are finalized only after pre-kernel proof-control settles the manifest schema, overlap list, and lifecycle matrix

---

## Task 0: Plan Authority

**Files:**
- Modify: `docs/superpowers/plans/2026-05-22-ticket-authority-kernel-slice1.md`
- Create: `docs/superpowers/plans/2026-05-25-ticket-authority-kernel-slice1a-update-only.md`

- [ ] **Step 1: Record branch and dirty state**

```bash
git status --short --branch --untracked-files=all
```

Expected: branch and dirty state recorded. Preserve unrelated dirty work.

- [ ] **Step 2: Apply the branch freshness gate**

Run the commands in [Branch And Worktree Gate](#branch-and-worktree-gate).

Expected: `origin/main` is contained in `HEAD`.

- [ ] **Step 3: Commit the control docs before proof-control or implementation**

Stage only the superseded banner and the new Slice 1A plan if the user asks for a committed control surface.

Expected: no proof-control files or implementation files are staged with the plan-control commit.

---

## Task 1: Pre-Kernel Proof-Control Lane

**Files:**
- Create: `plugins/turbo-mode/ticket/tests/support/update_authority_slice1a_expected.py`
- Create: `plugins/turbo-mode/ticket/tests/test_update_authority_path_derivation.py`
- Create: `plugins/turbo-mode/ticket/tests/test_update_authority_behavior_proof_coverage.py`
- Modify: focused wrapper-facing proof tests under `plugins/turbo-mode/ticket/tests/`

- [ ] **Step 1: Add the expected-inventory fixture**

Encode exact public `path_id` inventory, public proof entries, top-level `source_anchors[probe_id]` expectations, private proof-control items, closed overlap-sensitive cell projection, family mapping, lifecycle matrix cell coverage, reachable validator-rule denominator, explicit validator exclusion ledger, per-path planner scenarios, and exact `path_id -> behavior_proof_ids` mapping as the executable projection of this plan.

Every public `path_id` must have at least one canonical planner scenario that emits it. Each scenario must include:

- raw payload
- fixture-local primitive `context_spec`
- expected `path_id`
- expected `outcome`
- expected `ignored_raw_keys`
- expected `invalid_raw_keys`
- expected `unsupported_raw_keys`
- expected `no_op_raw_keys`
- expected `context_required_raw_keys`
- expected `missing_context_fields`
- expected `precondition_blocked_raw_keys`
- non-empty linked `behavior_proof_ids`

`context_spec` is fixture-owned proof-control data, not a production API object. It must use public context field names and enum/value spellings that post-kernel contract tests can round-trip into real `UpdateMutationContext` instances.

- [ ] **Step 2: Add the path-derivation audit**

Build the source-derived routing census and path-derivation audit so every in-scope post-membrane wrapper branch predicate resolves to:

- covered by public path IDs
- excluded by scope
- quarantined conflict
- unresolved probe question

The audit may parse only the dedicated revision-handshake sentinel block from this Markdown plan. It must not scrape path families, path IDs, outcomes, or other semantic registry content from the plan.

The audit must derive the denominator from live update wrapper source, including:

- `_ALLOWED_UPDATE_FIELDS`
- `_CLOSE_FIELDS`
- `_REOPEN_FIELDS`
- `_validate_lifecycle_payload()`
- `_action_and_fields()`
- `_prepare_fields()`
- reachable `validate_fields()` rules for admitted update fields
- `_check_legacy_gate()` as an explicit Slice 1A exclusion boundary rather than a public path source

The audit must hard-stop on undeclared overlap-sensitive candidates. It may report a deterministic failure record, but the fixture must not gain a committed passing private row for that candidate before a plan-control patch declares it.

- [ ] **Step 3: Add the behavior-proof coverage audit**

Fail if any public path lacks canonical proof coverage, any public path violates naming grammar, any unresolved private item leaks into public inventory, any required family is incompletely covered by public paths or named blockers, any overlap-cell blocker is used for a family outside that cell's allowed binding list, any public proof lacks a non-empty `source_anchors[probe_id]` entry with an `oracle_test` anchor, any source-only proof is treated as sufficient, any planner scenario lacks linked proof IDs, or any public `CONTEXT_REQUIRED` scenario lacks resolved-context companion coverage.

- [ ] **Step 4: Settle required probe questions**

Add or tighten wrapper-facing probes, including same-status lifecycle probes, overlap-sensitive routing probes, mixed `status + reopen_reason` probes, transition-to-blocked omitted-versus-explicit-empty `blocked_by` probes, same-status blocked-by probes, and lifecycle-owned `status + tags` / `status + section fields` probes before any public path for those cells enters the expected inventory.

- [ ] **Step 5: Verify proof-control without `ticket_update_authority.py`**

Run the pre-kernel proof-control baseline and audit commands.

Expected: proof-control passes without creating or importing `ticket_update_authority.py`.

---

## Task 2: Implement The Update Authority Module

**Files:**
- Create: `plugins/turbo-mode/ticket/scripts/ticket_update_authority.py`
- Create: `plugins/turbo-mode/ticket/tests/test_update_authority_contract.py`
- Create: `plugins/turbo-mode/ticket/tests/test_update_authority_source_anchors.py`
- Create: `plugins/turbo-mode/ticket/tests/test_update_authority_phase_gate.py`

- [ ] **Step 1: Create the pure update-only module**

Requirements:

- no shebang
- no CLI
- no direct execution helper
- no runtime Ticket imports
- no filesystem, subprocess, or installed-runtime dependency
- no public generic surface scaffolding
- no imports from `plugins/turbo-mode/ticket/tests/`
- no runtime import of `plugins/turbo-mode/ticket/tests/support/update_authority_slice1a_expected.py`
- production registry is data-only and path-first
- production registry rows contain no `family_id`, private proof-control IDs, overlap-cell IDs, lifecycle matrix IDs, or callables

- [ ] **Step 2: Implement the public carrier validation boundary**

Validate:

- exact `UpdateMutationContext` object is required; `context=None`, subclasses, mappings, and duck-typed contexts fail
- exact built-in decoded-JSON raw input boundary
- `bool` is distinct from numeric values
- finite floats and arbitrary-size ints are carrier-valid
- non-finite float rejection
- typed context field contracts
- global context shape validation and path-sensitive context sufficiency
- `current_acceptance_criteria_lines` non-empty logical line contract
- `current_blocked_by` duplicate-insensitive and order-insensitive semantics
- `referenced_ticket_statuses` dependency, subset-key, `MISSING`, and decisive-partial-map rules

- [ ] **Step 3: Implement private derivation and public path selection**

Use private helpers to derive readiness and normalization from direct current-ticket facts, then select exactly one public `path_id` and one public `outcome`.

Task 2 must consume only the settled proof-control projection. It must not perform fresh source-census discovery, wrapper-branch enumeration, semantic inventory expansion, or fallback path invention. If implementation hits a case outside the settled projection, stop and return to plan/proof-control.

- [ ] **Step 4: Export the strict public path-first manifest**

Export only public, proof-backed path data, normative structured proof entries, and top-level informative `source_anchors[probe_id]` locators using the exact built-in JSON-serializable carrier shapes defined above. Do not export unresolved items, path-local anchors, public effects/materializations, or internal topology.

- [ ] **Step 5: Add contract, source-anchor, and phase-gate tests**

Phase-gate expectations:

- no runtime Ticket script imports `ticket_update_authority.py`
- no public generic authority facade exists
- public export contains no internal topology
- public export contains no capture/ingest public paths
- public export contains no path-local `source_anchors`
- every public path is dynamically reachable by at least one fixture-owned planner scenario
- static parity compares only public contract data and exact exported carrier shapes: top-level manifest fields, public path set, per-path `outcome`, `behavior_claim`, `required_context_fields`, `behavior_proof_ids`, public proof set, normative proof entries, row key closure, and canonical exported list order
- dynamic conformance compares the full public planner result surface for every fixture scenario
- contract tests must instantiate real `UpdateMutationContext` values from every fixture `context_spec` and fail on missing keys, extra keys, enum drift, or context-semantics drift
- source-anchor audit is the fixture-backed parity mechanism for exported `source_anchors[probe_id]` list carrier shape, anchor dict key closure, canonical anchor order, role assignment, proof linkage, required `oracle_test` presence, file existence, resolver resolution, and non-blocking stale-line warnings

---

## Task 3: Final Verification And Closeout

**Files:**
- Verify changed docs, tests, and source only

- [ ] **Step 1: Run post-kernel verification**

Run the commands in [Verification Harness](#verification-harness).

Expected: pass.

- [ ] **Step 2: Review diff surfaces**

```bash
git diff --stat
git diff -- docs/superpowers/plans/2026-05-22-ticket-authority-kernel-slice1.md
git diff -- docs/superpowers/plans/2026-05-25-ticket-authority-kernel-slice1a-update-only.md
git diff -- plugins/turbo-mode/ticket/scripts/ticket_update_authority.py
git diff -- plugins/turbo-mode/ticket/tests/support/update_authority_slice1a_expected.py
git diff -- plugins/turbo-mode/ticket/tests/test_update_authority_path_derivation.py
git diff -- plugins/turbo-mode/ticket/tests/test_update_authority_behavior_proof_coverage.py
git diff -- plugins/turbo-mode/ticket/tests/test_update_authority_contract.py
git diff -- plugins/turbo-mode/ticket/tests/test_update_authority_source_anchors.py
git diff -- plugins/turbo-mode/ticket/tests/test_update_authority_phase_gate.py
```

Expected: only planned files changed.

- [ ] **Step 3: Confirm closeout truth**

Do not claim Slice 1A complete unless:

- every required family is proof-backed and public, or formally removed by a plan-control scope patch
- every public path has canonical `probe.*` proof coverage
- same-status lifecycle behavior is publicly proof-backed and promoted from its temporary private probes
- no private proof-control IDs leak into public outputs
- every public path is dynamically reachable through fixture-owned planner scenarios
- every public proof has a non-empty `source_anchors[probe_id]` entry with at least one `oracle_test` anchor
- no closed overlap-sensitive cell remains unresolved unless Slice 1A scope has been formally narrowed
- public `schema_version` and `policy_version` were finalized only after proof-control settled

> **Superseded - Do Not Implement**
>
> This shard-scoped `Slice 1A.1` control plan is retained as historical context
> for the abandoned authority-kernel direction. It is no longer the current
> implementation control surface.
>
> There is no active successor authority-kernel plan in this document family.
> Do not land registries, proofs, or callable surfaces from this file as the
> basis for new work.

# Ticket Update Authority Slice 1A.1 Reopen Reason-Present Control Plan

> **For agentic workers:** Treat this as the current implementation control
> surface for the first promoted Ticket update authority shard. Do not widen
> scope inside this file. Successor shards require their own control patch.

**Goal:** Freeze the first truthful Ticket update authority sub-slice for the
terminal `{"status": "open", "reopen_reason": "..."}` cohort on parseable,
non-legacy tickets whose current status is `done` or `wontfix`.

**Architecture:** `Slice 1A.1` is a shard-scoped sub-slice of the broader
Slice 1A roadmap family. Raw-payload classifier semantics and exact row
semantics live in checked-in canonical JSON registries under
`plugins/turbo-mode/ticket/references/`. Surface membership lives in an exact
additive surface descriptor plus one derived current-surface membership
snapshot. Broad eventual update-authority callables are deferred.

**Tech Stack:** Markdown control doc, checked-in JSON registries, bytecode-safe
pytest later, and no runtime mutation in this docs-only patch.

---

## Supersession And Authority

This file is the current human-approved control authority for `Slice 1A.1`.

- Superseded implementation doc:
  `docs/superpowers/plans/2026-05-25-ticket-authority-kernel-slice1a-update-only.md`
- Historical predecessor:
  `docs/superpowers/plans/2026-05-22-ticket-authority-kernel-slice1.md`
- Active sub-slice ID: `slice1a.1`
- Surface family ID: `ticket_update_authority`

Authority chain:

1. This Markdown file owns scope, vocabulary, change protocol, and active
   surface framing.
2. Classifier registry owns raw-payload syntax, current-status cohort routing,
   and bridge-key resolution for the active candidate.
3. Canonical semantic registries own exact rows:
   - boundary registry
   - join registry
   - disposition registry
   - proof registry
4. Surface descriptor owns only surface lifecycle and canonical row
   membership.
5. Derived current-surface effective membership snapshot is generated,
   non-authoritative, and audit-only.
6. Fixtures, audits, and implementation are downstream projections only.

If this file and any canonical registry disagree, stop implementation and patch
the control surface first. If the surface descriptor and the derived snapshot
disagree, the descriptor wins and the snapshot must be regenerated. No test
fixture, generated snapshot, or later source module may override the control
surface.

Revision handshake:

<!-- slice1a1-revision-handshake:start -->
CONTROL_PLAN_REVISION = "ticket-update-authority-slice1a1.v11"
<!-- slice1a1-revision-handshake:end -->

Every authoritative JSON artifact added in this patch, including the classifier
registry, semantic registries, and surface descriptor, carries the same
`control_plan_revision`. A semantic change to classifier resolution, any
authoritative row, or any surface membership delta requires a control-doc patch
and a `CONTROL_PLAN_REVISION` bump. The derived current-surface snapshot carries
the revision for audit parity only; it is not an authority source.

---

## Active Scope

`Slice 1A.1` is an explicitly shard-scoped sub-slice. Its active scope is only
the promoted candidate cohort:

- `candidate.status_open.reason_present.done_or_wontfix`

Defined terms:

- `syntax_family`: closed raw payload syntax identity before join evaluation.
- `status_routing_cohort`: closed current-status cohort that is equivalent for
  the pre-join routing boundary.
- `bridge_key`: post-routing semantic tuple
  `(routed_action, routed_lifecycle_intent)`.
- `join_unit`: exact post-boundary semantic row keyed by
  `(bridge_key, current_status, required_context_sufficiency_signature)`.

Active shard values:

- `classifier_id = classifier.status_open.reason_present.done_or_wontfix`
- `syntax_family = status_open.reason_present`
- `status_routing_cohort = done_or_wontfix`
- `bridge_key = (reopen, reason_present)`

These values are summary projections from
`plugins/turbo-mode/ticket/references/update_authority_slice1a1_classifier_registry.json`.
If this prose and the classifier registry disagree, stop implementation and
patch the control surface before writing code.

Promoted exact join units:

- `join.reopen.reason_present.done.bt=unused.br=unused.dr=unused`
- `join.reopen.reason_present.wontfix.bt=unused.br=unused.dr=unused`

Active boundary rows:

- `boundary.status_open.reason_present.done_or_wontfix.legacy_generation_write_gate`
- `boundary.status_open.reason_present.done_or_wontfix.ticket_yaml_parseability_gate`

Promoted public accepted path:

- `path.update.reopen.status_open.reason_present.accepted`

Promoted shared execute proof:

- `probe.update.reopen.status_open.reason_present.terminal.execute`

Out of scope for this sub-slice:

- `candidate.status_open.reason_missing.done_or_wontfix`
- nonterminal `status == "open"` cohorts
- `pure_reopen_reason` cohorts
- generic broad update-authority callables
- the broader Slice 1A family completeness claim

This file does **not** claim whole-surface update authority. It owns only the
cohort and rows listed above.

---

## Frozen Decisions

| Area | Frozen decision |
| --- | --- |
| Proof class | `Slice 1A.1` proves `source` only. It does not prove installed runtime behavior, plugin cache state, app-server inventory, or hook activation. |
| Scope frame | `Slice 1A.1` is a shard-scoped sub-slice, not a temporarily narrow whole-surface Slice 1A API. |
| Public callables | `Slice 1A.1` publishes shard-scoped names only: `plan_update_slice1a1_manifest_for_payload(...)` and `export_update_slice1a1_policy_manifest()`. Broad eventual names remain deferred. |
| Exact registries | Raw-payload classifier resolution, boundary rows, join units, dispositions, and proofs are authored exactly in checked-in non-test JSON artifacts. Tests and snapshots are projections only. |
| Surface descriptor | Surface descriptors may reference canonical row IDs only. They must not restate path or probe semantics. |
| Surface snapshot | The current-surface effective membership snapshot is derived, non-authoritative, and never hand-edited. |
| Boundary model | Legacy-generation write policy and ticket YAML parseability are pre-join boundary gates for this cohort. They are not reopen-path semantics and must not appear as join-unit rows. |
| Candidate collapse | The pre-join candidate cohort may collapse `done` and `wontfix` to `done_or_wontfix` for boundary reachability only. |
| Join exactness | Post-boundary join units stay exact on `current_status`. This sub-slice keeps separate join rows for `done` and `wontfix`. |
| Accepted path collapse | The `done` and `wontfix` join rows collapse to one accepted public `path_id` because the stable public contract is the same after boundary screening. |
| Execute route collapse | Archived and non-archived terminal reopen flows collapse to the same public accepted path. Final proof requires wrapper-level archived and non-archived execute witness classes under one shared public proof ID, not separate path IDs or separate public proof IDs. |
| Normative execute semantic | The accepted execute path is defined by ordinary active-ticket discovery without closed-ticket fallback, resulting `status == "open"`, and durable visible recording of the supplied reopen reason. Current helper names are evidence only, not policy identity. |
| Current surface membership | The `slice1a.1` surface includes only the two boundary rows and the two join-unit rows listed above. No sibling cohort rows are active on this surface. |
| Broad negative path | This sub-slice does not activate a surface-live `out_of_subslice_scope` public path because no deferred sibling cohort rows are active on `slice1a.1`. Successor surfaces may introduce that negative contract with exact cohort rows. |
| Surface evolution | Successor shard surfaces must use new surface descriptors. `slice1a.1` becomes a frozen historical surface once a successor ships. |
| Successor references | Formal-exclusion follow-up notes are non-authoritative prose only. This sub-slice reserves no successor slice IDs. |
| Cross-surface IDs | Reuse canonical `path_id` and `probe_id` values across successor surfaces only when the public contract and public proof obligation are unchanged. |

---

## Exact Authority Files

Authoritative classifier registry:

- `plugins/turbo-mode/ticket/references/update_authority_slice1a1_classifier_registry.json`

Authoritative semantic registries:

- `plugins/turbo-mode/ticket/references/update_authority_slice1a1_boundary_registry.json`
- `plugins/turbo-mode/ticket/references/update_authority_slice1a1_join_registry.json`
- `plugins/turbo-mode/ticket/references/update_authority_slice1a1_disposition_registry.json`
- `plugins/turbo-mode/ticket/references/update_authority_slice1a1_proof_registry.json`

Authoritative surface registry:

- `plugins/turbo-mode/ticket/references/update_authority_slice1a1_surface_descriptor.json`

Derived non-authoritative snapshot:

- `plugins/turbo-mode/ticket/references/update_authority_slice1a1_current_surface_effective_membership.json`

All later fixtures, manifests, and tests must derive from these artifacts. No
other file is allowed to act as the classifier, row, or surface-membership source
for `Slice 1A.1`.

---

## Classifier Resolution

`Slice 1A.1` owns one active classifier row:

- `classifier_id`:
  `classifier.status_open.reason_present.done_or_wontfix`
- `candidate_id`:
  `candidate.status_open.reason_present.done_or_wontfix`
- raw payload shape:
  object with exactly `status` and `reopen_reason`
- `status`:
  exactly `open`
- `reopen_reason`:
  present, string-typed, and non-empty
- `context.current_status`:
  `done` or `wontfix`
- resolved `syntax_family`:
  `status_open.reason_present`
- resolved `status_routing_cohort`:
  `done_or_wontfix`
- resolved `bridge_key`:
  `(reopen, reason_present)`

The classifier registry is the only authoritative raw-payload-to-classifier
surface for this shard. Markdown bullets in this section are readable summaries;
audits, fixtures, and implementation must read the JSON registry and fail if it
does not match the control revision.

---

## Canonical Rows

### Boundary Rows

| boundary_row_id | Candidate cohort | Reason code | Terminal ref |
| --- | --- | --- | --- |
| `boundary.status_open.reason_present.done_or_wontfix.legacy_generation_write_gate` | `candidate.status_open.reason_present.done_or_wontfix` | `legacy_generation_write_gate` | `formal_exclusion.legacy_generation_write_gate` |
| `boundary.status_open.reason_present.done_or_wontfix.ticket_yaml_parseability_gate` | `candidate.status_open.reason_present.done_or_wontfix` | `ticket_yaml_parseability_gate` | `formal_exclusion.ticket_yaml_parseability_gate` |

These rows fire before join evaluation. They are cohort-scoped and may not be
reused for sibling cohorts in ordinary shard patches.

### Join Units

| join_unit_id | Bridge key | current_status | Signature | Terminal ref |
| --- | --- | --- | --- | --- |
| `join.reopen.reason_present.done.bt=unused.br=unused.dr=unused` | `(reopen, reason_present)` | `done` | all sufficiency dimensions `unused` | `path.update.reopen.status_open.reason_present.accepted` |
| `join.reopen.reason_present.wontfix.bt=unused.br=unused.dr=unused` | `(reopen, reason_present)` | `wontfix` | all sufficiency dimensions `unused` | `path.update.reopen.status_open.reason_present.accepted` |

### Accepted Public Path

- `path_id`: `path.update.reopen.status_open.reason_present.accepted`
- `outcome`: `accepted`
- `required_context_fields`: `["current_status"]`
- `behavior_proof_ids`:
  `["probe.update.reopen.status_open.reason_present.terminal.execute"]`
- `behavior_claim`:
  `For a parseable non-legacy done or wontfix ticket, terminal {"status":"open","reopen_reason":"..."} is accepted and execution restores the ticket to active open status while durably recording the supplied reopen reason in visible ticket content.`

This path is the only public accepted path owned by `Slice 1A.1`.

---

## Proof Model

Shared public proof row:

- `probe_id`: `probe.update.reopen.status_open.reason_present.terminal.execute`
- `proof_scope`: `prepare_execute`
- `evidence_status`: `incomplete`
- `proof_facet_vocabulary`:
  `["wrapper_prepare_outcome", "reopen_bucket_membership", "wrapper_execute_outcome", "active_ticket_location", "open_status_effect", "visible_reopen_reason"]`
- `observable_facets`:
  `["wrapper_prepare_outcome", "reopen_bucket_membership", "wrapper_execute_outcome", "active_ticket_location", "open_status_effect", "visible_reopen_reason"]`
- `required_observed_behavior`:
  `For a parseable non-legacy done or wontfix ticket, terminal {"status":"open","reopen_reason":"..."} is accepted and execution restores the ticket to active open status while durably recording the supplied reopen reason in visible ticket content.`

Final non-public proof sufficiency rule for this same proof row:

- `required_witness_policy = all_of`
- `required_witness_classes = [archived_wrapper_execute, non_archived_wrapper_execute]`
- each required witness class must cover every facet in
  `observable_facets` using the exact same closed vocabulary
- `current_satisfied_witness_classes = [non_archived_wrapper_execute]`
- `missing_witness_classes = [archived_wrapper_execute]`

Witness class expectations:

- `archived_wrapper_execute`
  - wrapper `prepare` accepts the archived-ticket payload
  - wrapper `execute` returns the accepted reopen outcome
  - ticket is discoverable through ordinary active-ticket discovery without
    closed-ticket fallback
  - discovered ticket has `status == "open"`
  - visible ticket content records the supplied reopen reason
  - archived source path is not left as the live ticket location
- `non_archived_wrapper_execute`
  - wrapper `prepare` accepts the active-ticket payload
  - wrapper `execute` returns the accepted reopen outcome
  - ticket is discoverable through ordinary active-ticket discovery without
    closed-ticket fallback
  - discovered ticket has `status == "open"`
  - visible ticket content records the supplied reopen reason

Current source-local oracle anchors for this sub-slice:

- archived supporting engine oracle:
  `plugins/turbo-mode/ticket/tests/test_review_findings.py::test_reopen_archived_ticket_moves_to_active_dir`
- non-archived wrapper witness:
  `plugins/turbo-mode/ticket/tests/test_update_refinement.py::test_reopen_terminal_ticket_uses_engine_reopen_path`
- supporting source:
  `plugins/turbo-mode/ticket/scripts/ticket_update.py::_action_and_fields`
  `plugins/turbo-mode/ticket/scripts/ticket_update.py::_validate_lifecycle_payload`
  `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py::_evaluate_reopen_policy`
  `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py::_execute_reopen`

These helper names are the current oracle family only. The public contract is
the higher-level discovery and visible-effect semantic above. The archived
engine oracle proves only the closed facets `active_ticket_location` and
`open_status_effect`; it does not satisfy `archived_wrapper_execute` because it
does not cover `wrapper_prepare_outcome`, `reopen_bucket_membership`,
`wrapper_execute_outcome`, or `visible_reopen_reason`. A later proof-control
patch must add that archived wrapper-level oracle before this proof row can be
considered complete.

---

## Surface Model

`Slice 1A.1` owns one surface descriptor row:

- `surface_id = slice1a.1`
- `control_plan_revision = ticket-update-authority-slice1a1.v11`
- `lifecycle = current`
- `kind = shard_subslice`
- `planner_callable = plan_update_slice1a1_manifest_for_payload`
- `manifest_callable = export_update_slice1a1_policy_manifest`

Membership rule:

- authoritative membership = `base_surface_id + added_* - removed_*`
- this first surface has `base_surface_id = null`
- `added_boundary_row_ids` and `added_join_unit_ids` are the only authored
  membership fields
- `effective_*` membership lives only in the generated snapshot

Surface descriptors may not author:

- `path_id` membership lists
- `probe_id` membership lists
- behavior claims
- proof obligations
- witness policies

All path and proof sets for a surface are derived from canonical row
membership.

---

## Public API Scope

`Slice 1A.1` reserves the eventual whole-surface update names but does not ship
them.

Allowed shard-scoped public callables:

`Slice 1A.1` keeps the broader carrier type names `UpdateMutationContext` and
`UpdateManifestPlan` for continuity. This sub-slice does not reopen their
whole-surface schema here; it only narrows which exact rows the shard-scoped
surface may resolve.

```python
def plan_update_slice1a1_manifest_for_payload(
    raw_payload: object,
    context: UpdateMutationContext,
) -> UpdateManifestPlan:
    ...


def export_update_slice1a1_policy_manifest() -> dict[str, object]:
    ...
```

Prohibited in this sub-slice:

- `plan_update_manifest_for_payload(...)`
- `export_update_policy_manifest()`

Out-of-scope sibling cohorts must not be forced through broad whole-surface
names while this sub-slice remains the active control surface.

---

## Work Sequence

Docs/control sequence:

1. This docs-only control patch:
   - supersede the broad `v8` plan
   - create this `Slice 1A.1` control doc
   - land the authoritative classifier registry
   - land authoritative semantic registries and the authoritative surface
     descriptor
   - land the derived current-surface membership snapshot
2. Later proof-control patch:
   - add parity fixtures and audits that resolve only from the authoritative
     classifier registry, semantic registries, and surface descriptor
   - add an audit that derives `current_satisfied_witness_classes` from
     proof-registry witness anchors by requiring exact facet-vocabulary coverage
   - add an archived wrapper-level prepare/execute oracle for visible reopen
     reason recording and active-ticket relocation
3. Later implementation patch:
   - add the shard-scoped callable surface
   - keep runtime behavior unchanged outside the promoted cohort

Stop conditions:

- Stop if a patch needs to add a second active candidate cohort.
- Stop if a patch needs to publish the broad eventual callables.
- Stop if a patch needs to widen `Slice 1A.1` boundary rows beyond
  `candidate.status_open.reason_present.done_or_wontfix`.
- Stop if a patch needs to collapse `done` and `wontfix` at the join-unit
  layer instead of only at the disposition layer.
- Stop if a patch needs to split archived and non-archived execute routes into
  separate public path IDs or separate public proof IDs.
- Stop if a patch needs to hand-edit the derived current-surface membership
  snapshot.

---

## Freeze-Ready 1A.1 Gate

`Slice 1A.2` may not start until `Slice 1A.1` is promotable to a frozen
historical surface.

That gate requires all of these:

1. The authoritative classifier registry, boundary registry, join registry,
   disposition registry, proof registry, and surface descriptor for `1A.1` are
   landed and their parity/audit checks pass together.
2. The shared accepted reopen `probe_id` is proven with both required
   wrapper-level execute witness classes.
3. The `1A.1` control doc contains no stale broad-slice claims.
4. Every active `1A.1` case terminates exactly once through:
   - one boundary row
   - one join-unit disposition
   - or one formal exclusion
5. `path_id`, `probe_id`, witness-class policy, and current surface membership
   are explicit and freeze-ready rather than provisional.

Current verification for this docs/control patch is manual source inspection,
JSON parseability, stale-token scans, whitespace checks, and existing
docs-contract hygiene only. No checked-in proof-control consumer currently reads
the `Slice 1A.1` classifier or proof registries, so do not cite existing pytest
passes as authority-registry parity evidence until that consumer exists.

Only after that gate is green may a successor surface ship and mark
`slice1a.1` as `superseded_frozen`.

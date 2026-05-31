# Ticket Docs Authority Rebaseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ADR 0006 and the May 30 control doc the visible authority for current-facing Ticket docs and docs/static assertions without claiming current source, source-runtime tests, ticket files, installed cache, or live runtime already enforce the target model.

**Architecture:** This is a current-facing docs plus docs/static test authority-boundary patch. Target architecture, current source compatibility, source-runtime behavior tests, cutover inventory, and installed-runtime proof stay separate. Old behavior may be mentioned only as narrow current-source compatibility, cutover input, or historical changelog context.

**Tech Stack:** Markdown docs, Codex `SKILL.md` instruction files, Python `pytest` static docs tests.

---

## Context

ADR 0006 is accepted architecture authority for the Ticket runtime-first
state-kernel rebaseline. The May 30 control doc is the implementation and
cutover control surface.

This slice is docs/static-tests only. It does not satisfy the ADR/control
read-only `docs/tickets/` cutover inventory gate, normalize ticket files,
refresh the installed plugin cache, change runtime source behavior, rewrite
source-runtime expectations, or prove live runtime behavior.

The implementation must prevent old architecture from surviving by relabeling.
Compatibility sections may not become a second contract for the old pipeline.

Runtime/source tests are out of implementation scope for this slice except as
inspection evidence. Tests such as `test_autonomy_runtime.py` and
`test_turn_batch.py` may still assert current-source behavior for approval
objects, durable `preview` mode, pending-summary approval, commit disposition,
and `ticket_change_scope`. Do not rewrite those expectations in this slice.
When docs/static tests mention those surfaces, they must identify them as
current-source compatibility until the source implementation slice changes the
runtime.

This plan has two clocks:

- Target authority clock: ADR 0006 plus the May 30 control doc define the
  post-cutover Ticket model.
- Current source clock: existing command entrypoints and source-runtime tests
  still define what users can run before the runtime/source rebaseline lands.

Every edited doc or static assertion must say which clock it is testing or
describing. Do not make current command payloads look like target authority, and
do not make target sections unusable by deleting current-source command facts
that the present scripts still require.

## Surface Matrix

| Surface | Required Treatment |
|---|---|
| `plugins/turbo-mode/ticket/references/ticket-contract.md` | Add authority boundary; make target post-cutover schema primary; move old schema into narrow cutover/current-source compatibility notes only. |
| `plugins/turbo-mode/ticket/README.md` | Add authority boundary; stop presenting fenced YAML, preview mode, three mutation surfaces, and four-stage pipeline as current product authority. |
| `plugins/turbo-mode/ticket/HANDBOOK.md` | Add authority boundary; keep runnable current commands only as transitional source-operation notes. Remove pipeline diagrams as product architecture. |
| `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md` | Split current-source capture payload/preview commands from the target candidate mutation contract; qualify old priority/component/refinement fields as current source only. |
| `plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md` | Split current-source filters from target status/priority vocabulary; label old filters such as `blocked`, `critical`, and `medium` as current-source compatibility only. |
| `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md` | Split current-source focused update payloads from target candidate mutation writes; qualify `blocks`, `component`, `refinement_status`, `acceptance_criteria`, and preview-first commands as current source only. |
| `plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md` | Inspect and patch stale/blocked-chain wording only where it implies persisted `blocked` status or `blocks` reverse edges as target schema. |
| `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md` | Inspect and patch preview/audit/activation wording only where it implies current target authority. |
| `plugins/turbo-mode/ticket/PRIVACY.md` | Inspect; patch only current-facing contradictions. |
| `plugins/turbo-mode/ticket/TERMS.md` | Inspect; patch only current-facing contradictions. |
| `plugins/turbo-mode/ticket/CHANGELOG.md` | Fix current/unreleased skill-name mismatch to live names. Keep historical entries historical. |
| `plugins/turbo-mode/ticket/.codex-plugin/plugin.json` | Inspect interface text; patch only if it advertises old architecture as current product behavior. |
| `plugins/turbo-mode/ticket/tests/test_docs_contract.py` | Replace old-positive docs assertions with authority-boundary tests. |
| `plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py` | Replace old-positive autonomy docs assertions with authority-boundary tests. |
| `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py` | Inspect only; leave current-source behavior assertions unchanged in this slice. |
| `plugins/turbo-mode/ticket/tests/test_turn_batch.py` | Inspect only; leave pending-summary/runtime validation assertions unchanged in this slice. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py` | Inspect only if needed to label durable `preview` as current-source compatibility; do not edit. |
| `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py` | Inspect only if needed to label pending-summary approval as current-source compatibility; do not edit. |

## Acceptance Rules

- Target schema sections must describe ID-only filenames, YAML frontmatter,
  closed keys `id`, `title`, `status`, `priority`, `tags`, `related_paths`,
  and `blocked_by`, statuses `open`, `in_progress`, `done`, and `wontfix`,
  priorities `high`, `normal`, and `low`, and required `Problem`,
  `Next Action`, and `Change History`.
- Old fields or shapes may appear only in sections explicitly named for current
  source compatibility, legacy cutover input, or historical changelog. Those
  sections must include an ADR/control pointer and must not use old shapes as
  target authority. Normative words such as "must", "supported", or "required"
  are allowed only when the subject is current source behavior, for example
  "current source requires `ticket_update.py prepare` before execute until the
  runtime/source rebaseline replaces this command path."
- Approval language must be split:
  - Banned as target: automatic approval objects for `agent_primary`.
  - Permitted as target: `discussion_only` user-approval facts tied to candidate
    identity.
- Preview language must be split:
  - Banned as target: persistent `preview` mode or durable config.
  - Permitted: diagnostic dry-run/preview and transitional confirmation UX,
    clearly labeled.
- Target candidate mutation sections must expose the control-doc shape:
  `action`, `ticket_id`, `target.fields`, `target.sections`,
  `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`.
  They must state that non-create writes require an expected ticket fingerprint,
  proposed changes may contain only named target fields or sections, Ticket
  computes candidate identity from canonical candidate content plus live target
  fingerprint, and callers do not supply authoritative identity values.
- Target result-envelope sections must expose only the control-doc mechanical
  states: `ok`, `blocked`, `needs_discussion`, `invalid_state`, and
  `no_change`. They must not preserve old semantic response taxonomies as
  target authority.
- Target `Change History` sections must replace controlled labels with the
  control-doc grammar:
  `- <timestamp> | <actor> | <reason>` and optional
  `Corrects: <reference>.` Actor is a source value such as `codex`,
  `user-approved`, or `migration`; it is not a workflow label and must not
  encode action type.
- Four-stage pipeline, prepare/execute wrappers, machine-state taxonomy, commit
  disposition, `ticket_change_scope`, controlled Change History labels, and old
  error-code taxonomy must not appear as current product architecture. If they
  remain documented at all, the section must be named as current-source
  compatibility and must point to ADR 0006 plus the May 30 control doc.
- Frontmatter descriptions, JSON/YAML/code blocks, and command snippets inherit
  the same authority boundary as prose. If a loader-facing frontmatter
  description cannot sit under a heading, keep it operational and avoid target
  architecture claims. If a code block or command snippet shows current-source
  payloads or preview/execute commands, put a sentence immediately before it
  that says it is a current-source command example, not the target
  post-cutover candidate contract.
- The closeout must explicitly say this slice did not perform the read-only
  `docs/tickets/` cutover inventory gate.

## Tasks

### Task 0: Preflight and scope lock

**Files:**

- Inspect: `docs/decisions/0006-ticket-runtime-first-state-kernel.md`
- Inspect: `docs/superpowers/specs/2026-05-30-ticket-runtime-first-state-kernel-control.md`
- Inspect: target files named in the Surface Matrix.

- [ ] Run:

  ```bash
  git status --short --branch
  ```

  Expected: either a clean tracked worktree or unrelated dirty work outside all
  files named in this plan. If any dirty path overlaps the target files, stop and
  inspect the diff before editing. Do not overwrite user work.

- [ ] Re-read ADR 0006 and the May 30 control doc sections for normalized schema,
  candidate mutation contract, result envelope, preview ownership, cutover
  inventory, and `Change History` grammar.
- [ ] Re-read `ticket_capture.py` and `ticket_update.py` only to preserve current
  command usability in skill docs. Treat those scripts as current-source
  compatibility evidence, not target authority.
- [ ] Do not run installed cache refresh, live runtime inventory, ticket
  normalization, or `docs/tickets/` mutation commands in this slice.

### Task 1: Update tests first

**Files:**

- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py`
- Inspect only: `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py`
- Inspect only: `plugins/turbo-mode/ticket/tests/test_turn_batch.py`

- [ ] Classify every existing test in the two modified docs/static files before
  editing it. Use this disposition table; if implementation discovers a test was
  renamed or removed before this plan ran, preserve the same disposition in the
  replacement test.

| Test | Disposition | Required action |
|---|---|---|
| `test_current_facing_docs_pin_runtime_first_modes_without_legacy_yaml_guidance` | target authority | Rewrite so durable modes are exactly `agent_primary` and `discussion_only`; allow `preview` only in diagnostic/transitional sections. |
| `test_current_facing_docs_separate_source_boundary_from_installed_runtime_proof` | evidence-boundary invariant | Keep or adapt; it protects source/installed/runtime lane separation. |
| `test_current_facing_docs_route_future_history_to_ticket_history_and_pending_summary` | target authority | Rewrite to target `Change History` plus private operation-log/pending-summary boundary. |
| `test_runtime_first_closeout_docs_do_not_describe_gateway_as_future_work` | current-source compatibility | Keep only if it checks stale wording; do not make gateway prose target authority. |
| `test_adjacent_current_docs_describe_runtime_first_artifacts` | adjacent docs invariant | Keep or adapt for privacy/terms/changelog truth without broad architecture rewrites. |
| `test_ticket_autonomy_cli_exposes_ticket_level_commands_not_raw_ledger_mutators` | current-source compatibility | Keep only as current-source CLI evidence, not target mutation authority. |
| `test_pending_summary_validation_requires_live_repo_identity_fields` | current-source compatibility | Quarantine or label as current-source source-behavior evidence; do not use the approval fixture as target authority. |
| `test_apply_turn_verifies_repo_context_before_discovery_and_reuses_live_context` | current-source compatibility | Keep only as current-source autonomy behavior evidence. |
| `test_active_ticket_write_sites_are_named_functions_not_helper_file_allowlists` | safety invariant | Keep unless it blocks target docs/static assertions. |
| `test_direct_agent_and_runner_cannot_bypass_gateway_decision_contract` | current-source compatibility | Keep only as current-source direct-execute guard evidence. |
| `test_future_source_does_not_write_audit_logs_except_historical_repair` | target-compatible invariant | Keep; it supports the private-log/no-active-audit boundary. |
| `test_legacy_test_strings_are_only_negative_or_historical_fixtures` | compatibility boundary invariant | Keep or adapt to also cover old state-kernel terms. |
| `test_runtime_readiness_source_does_not_stage_legacy_yaml_autonomy_config` | safety invariant | Keep unless scope changes to runtime-readiness source. |
| `test_readme_states_supported_high_level_mutation_surfaces` | delete/rewrite | Replace with authority-boundary test for target candidate mutation path plus current-source command compatibility. |
| `test_handbook_states_supported_high_level_mutation_surfaces` | delete/rewrite | Replace with authority-boundary test for target candidate mutation path plus current-source command compatibility. |
| `test_contract_states_supported_high_level_mutation_surfaces` | delete/rewrite | Replace with authority-boundary test for target candidate mutation path plus current-source command compatibility. |
| `test_readme_ticket_schema_matches_yaml_contract_boundary` | target authority | Rewrite around ADR 0006 post-cutover schema and section-scoped old-shape negatives. |
| `test_contract_names_host_facing_autonomy_cli_surface` | current-source compatibility | Rewrite or quarantine so host CLI commands are current source, not target public mutation architecture. |
| `test_readme_and_handbook_list_all_host_facing_autonomy_commands` | current-source compatibility | Keep only if docs label commands as current-source or maintenance/diagnostic paths. |
| `test_pr22_repair_closeout_records_test4_and_qualified_review_findings` | unrelated historical invariant | Keep unless changed docs remove the referenced closeout. |
| `test_engine_docs_state_runner_is_not_public_mutation_surface` | current-source compatibility | Keep as source boundary evidence. |
| `test_docs_describe_direct_agent_execute_gateway_boundary` | current-source compatibility | Rewrite if needed so direct execute is not target mutation architecture. |
| `test_contract_separates_core_runtime_and_activation_error_codes` | delete/rewrite | Replace target-facing error taxonomy assertions with target result-envelope assertions; keep old taxonomy only under current-source compatibility if needed. |
| `test_response_envelope_docs_point_to_error_code_taxonomy` | delete/rewrite | Replace with target result-envelope assertion. |
| `test_contract_documents_current_exit_code_mapping` | current-source compatibility | Keep only under current-source command compatibility. |
| `test_handbook_documents_runtime_proof_env_var_scope` | unrelated/source invariant | Keep unless wording conflicts with evidence-lane boundaries. |
| `test_stale_plan_is_only_public_toctou_error_code` | current-source compatibility | Keep only if `stale_plan` remains current-source recovery language, not target result taxonomy. |
| `test_ingest_contract_documents_filename_id_and_indefinite_processed_retention` | unrelated ingest invariant | Keep unless target contract changes ingest docs. |
| `test_project_local_ticket_tmp_payloads_are_ignored` | unrelated hygiene invariant | Keep. |
| `test_ticket_capture_skill_exists` | unrelated split-skill invariant | Keep. |
| `test_old_broad_skill_files_do_not_exist` | unrelated split-skill invariant | Keep. |
| `test_retired_pipeline_guide_is_not_current_source` | target-compatible invariant | Keep; old pipeline guide must not become current authority. |
| `test_task4_split_skill_files_exist` | unrelated split-skill invariant | Keep. |
| `test_ticket_capture_skill_frontmatter_matches_task3_contract` | frontmatter operational trigger | Adapt frontmatter expectations to operational trigger text only; do not encode target architecture in frontmatter. |
| `test_ticket_capture_skill_contains_exact_compact_preview_labels` | current-source compatibility | Keep or adapt as current-source preview UX, not durable target `preview` mode. |
| `test_ticket_capture_skill_forbids_raw_user_wording` | privacy/safety invariant | Keep. |
| `test_ticket_capture_skill_requires_explicit_confirmation_before_writing` | current-source compatibility | Keep as current-source confirmation UX until source rebaseline replaces it. |
| `test_ticket_capture_skill_uses_canonical_prepare_and_execute_commands` | current-source compatibility | Keep with docs labeled as current-source commands. |
| `test_ticket_capture_skill_documents_path_resolution_contract` | operational invariant | Keep. |
| `test_ticket_capture_skill_documents_required_synthesized_fields` | current-source compatibility | Rewrite to label `capture.*` payload fields as current-source, not target candidate fields. |
| `test_ticket_capture_skill_keeps_provenance_hook_owned` | safety invariant | Keep. |
| `test_ticket_capture_skill_documents_deterministic_inference_boundaries` | current-source compatibility | Rewrite to label `medium`, `critical`, and `component` as current-source inference behavior only. |
| `test_ticket_capture_skill_documents_refinement_and_preview_rules` | current-source compatibility | Keep or adapt as current-source preview UX only. |
| `test_ticket_capture_skill_documents_create_edit_cancel_handling` | current-source compatibility | Keep as current-source command UX. |
| `test_ticket_capture_skill_documents_split_deferral_behavior` | operational invariant | Keep unless docs no longer cover split captures. |
| `test_ticket_capture_skill_preserves_hook_guard_boundary` | safety invariant | Keep. |
| `test_user_facing_ticket_skills_prefer_recovery_hint` | current-source compatibility | Keep only as current-source recovery UX, not target result-envelope taxonomy. |
| `test_contract_documents_recovery_hint_schema_and_codes` | delete/rewrite | Replace target-facing code taxonomy assertions; keep recovery hints only in current-source compatibility sections if needed. |
| `test_ticket_capture_skill_owns_creation_without_broad_ticket_skill` | split-skill invariant | Keep. |
| `test_new_split_skills_resolve_plugin_root_three_levels_up` | operational invariant | Keep. |
| `test_ticket_find_skill_contract_is_read_only` | read-only skill invariant | Adapt old filters/refinement text to current-source compatibility. |
| `test_ticket_update_skill_contract_is_preview_first_and_scoped` | current-source compatibility | Rewrite so preview-first focused update payloads are current source only. |
| `test_ticket_update_json_examples_do_not_use_invalid_needs_refinement_tag` | current-source compatibility | Keep only if JSON examples are clearly current-source examples. |
| `test_ticket_review_skill_contract_is_read_only_and_capture_prompt_only` | read-only skill invariant | Keep; patch stale blocked-chain wording if target authority leaks in. |
| `test_ticket_doctor_skill_contract_is_explicit_maintenance_only` | maintenance skill invariant | Keep; patch preview/audit/activation wording only if it claims target authority. |
| `test_ticket_payloads_does_not_expose_boolean_security_gate_helpers` | unrelated source invariant | Keep. |
| `test_doctor_docs_describe_confirmed_stale_payload_cleanup` | maintenance invariant | Keep. |
| `test_handbook_documents_runtime_activation_operator_flow` | current-source maintenance | Keep only as maintenance/source setup guidance. |
| `test_handbook_documents_ticket_triage_doctor_runtime_probe_output` | current-source maintenance | Keep only as diagnostic/source setup guidance. |
| `test_readme_and_handbook_do_not_describe_guard_as_fail_open` | safety invariant | Keep. |
| `test_current_docs_describe_audit_as_historical_only` | target-compatible invariant | Keep; it supports no active `.audit/` authority. |
| `test_handbook_documents_direct_agent_execute_gateway_requirement` | current-source compatibility | Keep only as source direct-execute guard evidence. |
| `test_changelog_announces_activate_runtime_subcommand` | changelog invariant | Keep or adapt to current unreleased wording. |
| `test_claude_instructions_reference_current_turbo_mode_source_roots` | repo instruction invariant | Keep unless unrelated to changed docs. |
| `test_repo_agents_instructions_reference_ticket_public_launcher` | repo instruction invariant | Keep unless unrelated to changed docs. |
| `test_skill_docs_use_project_root_marker_walk_not_git_rev_parse` | operational invariant | Keep. |
| `test_skill_docs_define_project_root_and_tickets_dir_separately` | operational invariant | Keep. |
| `test_current_facing_docs_include_dash_b_launcher_examples` | operational invariant | Keep for current-source commands. |
| `test_launcher_docs_mark_python3_as_legacy_compatibility` | compatibility invariant | Keep. |
| `test_current_facing_docs_do_not_keep_no_flag_plugin_launchers` | operational invariant | Keep. |
| `test_handbook_shell_metacharacter_list_matches_guard_regex` | safety invariant | Keep. |
| `test_handbook_does_not_advertise_stale_test_count_or_version_footer` | docs hygiene invariant | Keep. |
| `test_readme_and_handbook_do_not_advertise_counted_test_inventory` | docs hygiene invariant | Keep. |
| `test_update_skill_uses_focused_update_backend_as_mutation_path` | current-source compatibility | Keep only with current-source command labeling. |
| `test_split_skills_document_check_review_and_doctor_surfaces` | split-skill invariant | Keep. |
| `test_readme_documents_ticket_ux_commands` | current-source compatibility | Keep only if command table labels current-source, diagnostic, or maintenance lanes. |
| `test_readme_classifies_activate_runtime_as_maintenance_not_read_only` | maintenance invariant | Keep. |
| `test_readme_and_handbook_use_source_authority_installed_boundary` | evidence-boundary invariant | Keep. |
| `test_handbook_update_surface_matches_focused_backend` | current-source compatibility | Rewrite so focused backend fields are current-source only. |
| `test_handbook_smoke_uses_capture_preview_with_workspace_payload` | current-source compatibility | Keep only as current-source smoke/preview command guidance. |
| `test_manifest_documents_required_interface_urls` | manifest invariant | Keep. |
| `test_plugin_default_prompts_are_capture_first` | product prompt invariant | Keep unless prompt wording claims target architecture. |
| `test_no_skill_description_advertises_old_single_surface` | frontmatter invariant | Keep/adapt so descriptions stay operational and do not overclaim target architecture. |
| `test_task4_docs_do_not_overclaim_current_placeholder_refinement` | current-source compatibility | Rewrite so placeholder refinement is current-source focused update behavior only. |
| `test_docs_describe_capture_first_five_skill_surface` | current-source compatibility | Rewrite if old schema vocabulary remains; do not make five-skill surface target mutation architecture. |
| `test_contract_preserves_engine_boundary_for_workflow_runner` | current-source compatibility | Keep only if workflow runner is explicitly current-source/debug compatibility. |

- [ ] Replace the three mutation-surface tests with authority-boundary tests:
  `test_readme_states_supported_high_level_mutation_surfaces`,
  `test_handbook_states_supported_high_level_mutation_surfaces`, and
  `test_contract_states_supported_high_level_mutation_surfaces`.
- [ ] Replace `test_readme_ticket_schema_matches_yaml_contract_boundary` with a
  target-schema test that checks the ADR 0006 fields/statuses/priorities and a
  section-scoped negative check against old schema values.
- [ ] Replace old-positive tests that bless autonomy CLI/ledger command
  authority where they preserve approval-object or old pending-summary framing:
  `test_contract_names_host_facing_autonomy_cli_surface`,
  `test_contract_separates_core_runtime_and_activation_error_codes`,
  `test_response_envelope_docs_point_to_error_code_taxonomy`, and
  `test_contract_documents_recovery_hint_schema_and_codes`.
- [ ] Rewrite capture skill tests that require `medium`, `critical`,
  `component`, `refinement_status`, compact preview as target contract, or old
  refinement metadata.
- [ ] Rewrite read/update skill tests that require `refinement_status`,
  preview-first execution, old focused backend fields, `component`, `blocks`,
  or `acceptance_criteria` as target contract.
- [ ] Rewrite handbook tests that require capture preview smoke as target
  workflow, old focused update backend authority, workflow-runner authority, or
  capture-first five-skill language that still embeds old schema vocabulary.
- [ ] Update
  `test_static_autonomy_boundaries.py::test_current_facing_docs_pin_runtime_first_modes_without_legacy_yaml_guidance`
  so durable modes are exactly `agent_primary` and `discussion_only`, with
  `preview` allowed only in diagnostic/transitional sections.
- [ ] Add docs/static assertions for the target candidate mutation contract:
  candidate fields, exact target field/section boundary, fingerprint
  requirement for non-create writes, candidate identity ownership, and unknown
  field rejection.
- [ ] Add docs/static assertions for the target result envelope states:
  `ok`, `blocked`, `needs_discussion`, `invalid_state`, and `no_change`.
- [ ] Add docs/static assertions for the target `Change History` grammar:
  timestamp, actor/source, reason, optional `Corrects:`, no controlled semantic
  labels as post-cutover grammar.
- [ ] Inspect pending-summary fixture assertions that mention `approval` only to
  understand current-source compatibility. Do not edit
  `test_autonomy_runtime.py`, `test_turn_batch.py`, or other runtime/source
  behavior tests in this slice except to add comments only if later explicitly
  requested. The current approval-object, preview-mode, commit-disposition,
  pending-summary, and `ticket_change_scope` assertions remain source
  compatibility evidence until runtime implementation changes them.

Suggested helper structure:

```python
CORE_AUTHORITY_DOCS = (
    PLUGIN_ROOT / "README.md",
    PLUGIN_ROOT / "HANDBOOK.md",
    PLUGIN_ROOT / "references" / "ticket-contract.md",
)
SKILL_AUTHORITY_DOCS = (
    PLUGIN_ROOT / "skills" / "capture-ticket" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "read-ticket" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "update-ticket" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "ticket-backlog-triage" / "SKILL.md",
    PLUGIN_ROOT / "skills" / "ticket-doctor" / "SKILL.md",
)
ADJACENT_DOCS = (
    PLUGIN_ROOT / "PRIVACY.md",
    PLUGIN_ROOT / "TERMS.md",
    PLUGIN_ROOT / "CHANGELOG.md",
    PLUGIN_ROOT / ".codex-plugin" / "plugin.json",
)
```

Suggested test approach:

```python
def _section(text: str, start: str, end: str | None = None) -> str:
    body = text.split(start, maxsplit=1)[1]
    return body if end is None else body.split(end, maxsplit=1)[0]


def _norm(text: str) -> str:
    return " ".join(text.split())
```

Use section-scoped assertions rather than broad word bans. Old terms may remain
in compatibility/cutover/historical sections only when the section points to ADR
0006 and the control doc, and does not make old shapes normative target
authority.

Suggested target section names for docs/static tests:

- `## Authority Boundary`
- `## Target Post-Cutover Ticket Shape`
- `## Target Candidate Mutation Contract`
- `## Target Result Envelope`
- `## Target Change History Grammar`
- `## Current Source Compatibility`
- `## Legacy Cutover Input`
- `## Historical Changelog`

Tests should look inside the matching target sections for target requirements
and inside compatibility/cutover/historical sections for allowed old terms. Do
not test by banning words globally across whole files.

Frontmatter and code-block rules for tests:

- Loader-facing frontmatter descriptions are not section-scoped. Test that they
  describe when to invoke the skill and current operational safety gates only;
  they must not advertise old fields as target schema or preview as a durable
  target mode.
- JSON/YAML examples in `SKILL.md`, README, handbook, or contract files must be
  tested inside their nearest labeled prose boundary. Current-source examples may
  show current payloads such as `capture.*`, `update`, `component`, `blocks`, or
  `acceptance_criteria` only when the preceding prose labels them current-source
  command examples.
- Target examples must use the candidate mutation contract shape, not
  prepare/execute payloads. They must include `target.fields` or
  `target.sections` and must reject unknown target fields.
- Command snippets are current-source, diagnostic, or maintenance evidence. They
  must not be asserted as target mutation architecture unless they call the
  future candidate mutation path described by ADR 0006/control doc.

### Task 2: Patch core docs

**Files:**

- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`

- [ ] Add an authority boundary near the top of each file:
  - ADR 0006 is accepted architecture authority.
  - The May 30 control doc is implementation/cutover control.
  - This source document is not runtime proof.
  - This docs/tests slice does not perform cutover inventory or normalization.
- [ ] Replace "single source of truth" contract wording with "current
  source-facing reference subordinate to ADR 0006/control doc" or equivalent.
- [ ] Make target post-cutover schema primary, qualified as architecture/cutover
  authority rather than current runtime enforcement.
- [ ] Add a target candidate mutation contract section that names `action`,
  `ticket_id`, `target.fields`, `target.sections`, `proposed_change`,
  `expected_ticket_fingerprint`, and `evidence_summary`; states that non-create
  writes require an expected fingerprint; and states that Ticket computes
  candidate identity from canonical candidate content and the live target
  fingerprint.
- [ ] Add a target result envelope section with only `ok`, `blocked`,
  `needs_discussion`, `invalid_state`, and `no_change` as mechanical result
  states.
- [ ] Add a target `Change History` grammar section with
  `- <timestamp> | <actor> | <reason>` and optional
  `Corrects: <reference>.` Make clear that actor/source is not a workflow
  action label.
- [ ] Move old fenced-YAML schema, old statuses/priorities, slug filenames,
  archived closed lifecycle, and old metadata fields into narrow
  compatibility/cutover notes.
- [ ] Replace four-stage/product-pipeline prose with state-kernel and candidate
  mutation prose.
- [ ] Remove pipeline diagrams as product architecture. If a diagram remains, it
  must be labeled current-source compatibility and cannot be under an
  "Architecture" heading without an ADR/control warning.
- [ ] Split approval language into banned automatic approval objects for
  `agent_primary` and permitted `discussion_only` user-approval facts tied to
  candidate identity.
- [ ] Split preview language into diagnostic dry-run/preview versus persistent
  `preview` mode. Persistent `preview` must not be documented as a durable mode.

### Task 3: Patch skill docs

**Files:**

- Modify: `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`

- [ ] Apply local writing-principles guidance for `SKILL.md` edits.
- [ ] Add the same two-part authority split to each changed skill before
  changing examples or field vocabulary:

| Skill | Current-source section must keep usable | Target section must say |
|---|---|---|
| `capture-ticket` | `ticket_capture.py prepare/execute`, compact confirmation preview, current `capture.*` payload fields (`title`, `captured_request`, `problem`, `next_action`, `capture_confidence`, `priority`, `tags`, `component`, `related_paths`, `acceptance_criteria`), and current priority inference (`critical`, `high`, `medium`, `low`). | Target create becomes one candidate mutation through the runtime path; target priorities are `high`, `normal`, and `low`; `component`, `capture_confidence`, `refinement_status`, and `acceptance_criteria` are not target frontmatter fields. |
| `read-ticket` | Current `ticket_read.py` filters may include `blocked`, `critical`, and `medium` if the command still supports them. | Target schema uses statuses `open`, `in_progress`, `done`, `wontfix`; blockedness derives from `blocked_by`; target priorities are `high`, `normal`, `low`. |
| `update-ticket` | `ticket_update.py prepare/execute`, preview confirmation UX, and current focused update fields (`problem`, `next_action`, `acceptance_criteria`, `priority`, `tags`, `component`, `related_paths`, `blocked_by`, `blocks`, `status`, `reopen_reason`). | Target writes are candidate mutations with `target.fields`, `target.sections`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`; `blocks`, `component`, `refinement_status`, and `acceptance_criteria` are not target frontmatter fields. |
| `ticket-backlog-triage` | Current read/query/reporting commands and any stale or blocked-chain reporting needed for existing tickets. | Target triage is read/query/reporting unless it produces candidate mutations for the runtime path; persisted `blocked` status and reverse `blocks` edges are not target schema. |
| `ticket-doctor` | Current explicit maintenance, diagnostics, activation, stale payload cleanup, historical audit repair, and runtime-readiness commands. | Target doctor docs must not make preview, audit logs, activation proof, or cache refresh part of normal target ticket mutation authority. |

- [ ] Add a short authority note where behavior-shaping instructions otherwise
  look like contract authority: ADR 0006/control doc own the target model; current
  command paths are transitional source behavior until implementation/cutover.
- [ ] Keep current backend command examples only when needed for current
  execution, and label them transitional source paths.
- [ ] Remove or qualify old payload fields and examples: `component`, `blocks`,
  `refinement_status`, `acceptance_criteria`, `blocked`, `critical`, `medium`,
  and persistent preview.
- [ ] For `read-ticket`, label `blocked`, `critical`, and `medium` filters as
  current-source compatibility if they remain in command examples.
- [ ] Preserve usable instructions where source still needs current commands, but
  do not present those commands as the target state-kernel contract.

### Task 4: Patch adjacent docs

**Files:**

- Inspect: `plugins/turbo-mode/ticket/PRIVACY.md`
- Inspect: `plugins/turbo-mode/ticket/TERMS.md`
- Modify if needed: `plugins/turbo-mode/ticket/CHANGELOG.md`
- Inspect: `plugins/turbo-mode/ticket/.codex-plugin/plugin.json`

- [ ] Fix the current/unreleased changelog skill-name mismatch to the live names:
  `capture-ticket`, `read-ticket`, `update-ticket`, `ticket-backlog-triage`, and
  `ticket-doctor`.
- [ ] Keep older changelog entries historical. Do not rewrite old release
  history just because it describes past architecture.
- [ ] Patch PRIVACY, TERMS, and manifest only for current-facing old-architecture
  claims. Leave accurate privacy, terms, and historical artifact wording intact.

### Task 5: Verify and close out

**Files:**

- Verify all changed docs/tests.

- [ ] Run focused docs/static tests.
- [ ] Run `ruff check` for the changed test files.
- [ ] Run `git diff --check`.
- [ ] Run a fence checker that fails on unbalanced fences for every changed
  Markdown file.
- [ ] Review `git diff --stat` and confirm no runtime source files,
  source-runtime tests, `docs/tickets/`, installed cache files, or live runtime
  state were changed.
- [ ] Run:

  ```bash
  git status --short --branch
  git diff --stat
  git diff -- docs/superpowers/plans/2026-05-31-ticket-docs-authority-rebaseline.md plugins/turbo-mode/ticket
  ```

  Stop before staging if unrelated dirty work overlaps changed paths, if inspect
  only files changed, or if `docs/tickets/`, installed cache, local runtime
  state, source-runtime tests, or runtime source files changed.
- [ ] Report whether ignored residue remains, especially
  `plugins/turbo-mode/ticket/.venv/` and
  `plugins/turbo-mode/ticket/.pytest_cache/`.
- [ ] State explicitly in closeout that this docs/tests slice did not perform the
  read-only `docs/tickets/` cutover inventory gate, did not normalize tickets,
  did not change runtime/source behavior tests, and did not prove installed or
  live runtime behavior.

## Verification Commands

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_docs_contract.py tests/test_static_autonomy_boundaries.py -q
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/tests/test_docs_contract.py plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py
git diff --check
```

Fence check, passing the changed Markdown files explicitly:

```bash
PYTHONDONTWRITEBYTECODE=1 python -c 'import sys; bad=[]; [bad.append(f"{p}: unbalanced fences") for p in sys.argv[1:] if sum(1 for line in open(p, encoding="utf-8") if line.startswith("```")) % 2]; print("\n".join(bad)); raise SystemExit(1 if bad else 0)' <changed-markdown-files>
```

## Commit Guidance

Make one coherent docs/tests commit after verification passes:

```bash
git add plugins/turbo-mode/ticket/references/ticket-contract.md plugins/turbo-mode/ticket/README.md plugins/turbo-mode/ticket/HANDBOOK.md plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md plugins/turbo-mode/ticket/PRIVACY.md plugins/turbo-mode/ticket/TERMS.md plugins/turbo-mode/ticket/CHANGELOG.md plugins/turbo-mode/ticket/.codex-plugin/plugin.json plugins/turbo-mode/ticket/tests/test_docs_contract.py plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py
git commit -m "docs(ticket): align docs with state-kernel authority"
```

Adjust the `git add` set to include only files actually changed. Do not stage
`plugins/turbo-mode/ticket/skills/` as a directory, inspect-only runtime/source
tests, runtime source, `docs/tickets/`, `.codex/handoffs/`, installed cache, or
ignored residue.

## Assumptions

- No runtime source implementation in this slice.
- No source-runtime test rebaseline in this slice.
- No mutation of `docs/tickets/`.
- No installed cache refresh or live runtime inventory proof.
- Current source compatibility can remain documented only where needed to keep
  existing commands understandable and usable before runtime rebaseline.

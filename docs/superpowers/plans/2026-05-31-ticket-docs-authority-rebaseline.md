# Ticket Docs Authority Rebaseline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` or `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make ADR 0006 and the May 30 control doc the visible authority for current-facing Ticket docs and docs/static assertions without preserving current command usability or claiming current source, source-runtime tests, ticket files, installed cache, or live runtime already enforce the target model.

**Architecture:** This is a current-facing docs plus docs/static test authority-boundary patch. ADR 0006 and the May 30 control doc are the only current-facing target authority. Old behavior may be mentioned only as deprecated source drift, legacy cutover input, historical changelog context, or maintenance/diagnostic material; it is not a parallel operating contract.

**Tech Stack:** Markdown docs, Codex `SKILL.md` instruction files, Python `pytest` static docs tests.

---

## Context

ADR 0006 is accepted architecture authority for the Ticket runtime-first
state-kernel rebaseline. The May 30 control doc is the implementation and
cutover control surface.

This slice is a pre-inventory docs/static-tests rebaseline. It does not satisfy
the ADR/control read-only `docs/tickets/` cutover inventory gate, normalize
ticket files, refresh the installed plugin cache, change runtime source
behavior, rewrite source-runtime expectations, or prove live runtime behavior.

The implementation must prevent old architecture from surviving by relabeling.
Deprecated source-drift sections may not become a second operating contract for
the old pipeline, and current command usability is not a goal.

## Known Source Drift Not Rebased In This Slice

Runtime/source tests are out of implementation scope except as inspection
evidence. Tests such as `test_autonomy_runtime.py` and `test_turn_batch.py` may
still assert old behavior for approval objects, durable `preview` mode,
pending-summary approval, commit disposition, and `ticket_change_scope`. Do not
rewrite those expectations in this slice. When docs/static tests mention those
surfaces, they must identify them as known source drift, not as protected source
behavior.

Active docs and skills should not preserve `ticket_capture.py prepare/execute`,
`ticket_update.py prepare/execute`, current `capture.*`/focused-update payloads,
old priority/status vocabularies, preview-first mutation UX, or old response
taxonomies as usable operating guidance. If target mutation cannot run until the
runtime/source rebaseline lands, default active mutation guidance to
"temporarily unavailable" and point to ADR 0006 plus the May 30 control doc.

## Surface Matrix

| Surface | Required Treatment |
|---|---|
| `plugins/turbo-mode/ticket/references/ticket-contract.md` | Add authority boundary; make target post-cutover schema primary; move old schema into deprecated source-drift, legacy cutover, or historical notes only. |
| `plugins/turbo-mode/ticket/README.md` | Add authority boundary; stop presenting fenced YAML, preview mode, three mutation surfaces, and four-stage pipeline as current product authority. |
| `plugins/turbo-mode/ticket/HANDBOOK.md` | Add authority boundary; remove prepare/execute runbook guidance and pipeline diagrams as product architecture. Old capture/update commands may appear only as deprecated source drift or legacy cutover input, not maintenance/diagnostic runbook guidance. |
| `plugins/turbo-mode/ticket/skills/capture-ticket/SKILL.md` | Do not preserve prepare/execute capture guidance. State that create mutation is temporarily unavailable unless this slice identifies a live source target-candidate entrypoint. |
| `plugins/turbo-mode/ticket/skills/read-ticket/SKILL.md` | Keep read/query guidance only where it does not bless old target schema. Treat filters such as `blocked`, `critical`, and `medium` as deprecated source drift or legacy cutover input, not target vocabulary. |
| `plugins/turbo-mode/ticket/skills/update-ticket/SKILL.md` | Do not preserve prepare/execute update guidance. State that update mutation is temporarily unavailable unless this slice identifies a live source target-candidate entrypoint. |
| `plugins/turbo-mode/ticket/skills/ticket-backlog-triage/SKILL.md` | Inspect and patch stale/blocked-chain wording only where it implies persisted `blocked` status or `blocks` reverse edges as target schema. |
| `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md` | Inspect and patch preview/audit/activation wording only where it implies current target authority. |
| `plugins/turbo-mode/ticket/PRIVACY.md` | Inspect; patch only current-facing contradictions. |
| `plugins/turbo-mode/ticket/TERMS.md` | Inspect; patch only current-facing contradictions. |
| `plugins/turbo-mode/ticket/CHANGELOG.md` | Fix current/unreleased skill-name mismatch to live names. Keep historical entries historical. |
| `plugins/turbo-mode/ticket/.codex-plugin/plugin.json` | Inspect descriptions, capabilities, and default prompts as product surface. Patch if they advertise unavailable writes, old lifecycle execution, or old architecture as current behavior. |
| `plugins/turbo-mode/ticket/tests/test_docs_contract.py` | Replace old-positive docs assertions with authority-boundary tests. |
| `plugins/turbo-mode/ticket/tests/test_static_autonomy_boundaries.py` | Replace old-positive autonomy docs assertions with authority-boundary tests. |
| `plugins/turbo-mode/ticket/tests/test_autonomy_runtime.py` | Inspect only; leave source-runtime behavior assertions unchanged in this slice and name them as known source drift where docs/static tests reference them. |
| `plugins/turbo-mode/ticket/tests/test_turn_batch.py` | Inspect only; leave pending-summary/runtime validation assertions unchanged in this slice. |
| `plugins/turbo-mode/ticket/scripts/ticket_autonomy_config.py` | Inspect only if needed to identify durable `preview` as source drift; do not edit. |
| `plugins/turbo-mode/ticket/scripts/ticket_turn_batch.py` | Inspect only if needed to identify pending-summary approval as source drift; do not edit. |

## Acceptance Rules

- Target schema sections must describe ID-only filenames, YAML frontmatter,
  closed keys `id`, `title`, `status`, `priority`, `tags`, `related_paths`,
  and `blocked_by`, statuses `open`, `in_progress`, `done`, and `wontfix`,
  priorities `high`, `normal`, and `low`, and required `Problem`,
  `Next Action`, and `Change History`.
- Old fields or shapes may appear only in sections explicitly named
  `Deprecated Source Drift`, `Legacy Cutover Input`, `Historical Changelog`, or
  `Maintenance And Diagnostics`. Those sections must include an ADR/control
  pointer and must not use old shapes as target authority or active user
  guidance. Normative words such as "must", "supported", or "required" may
  describe only deprecation/removal, historical accuracy, read-only inventory,
  or maintenance/diagnostic constraints, not ordinary mutation operation.
- `Maintenance And Diagnostics` may cover doctor activation, stale payload
  cleanup, runtime proof, and historical audit repair. It must not contain
  ordinary capture/update `prepare/execute` mutation examples. Those examples may
  appear only in `Deprecated Source Drift` or `Legacy Cutover Input` sections.
- Approval language must be split:
  - Banned as target: automatic approval objects for `agent_primary`.
  - Permitted as target: `discussion_only` user-approval facts tied to candidate
    identity.
- Preview language must be split:
  - Banned as target: persistent `preview` mode or durable config.
  - Permitted: diagnostic dry-run/preview, clearly labeled as maintenance or
    source-drift evidence rather than target mutation UX.
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
  remain documented at all, the section must be named as deprecated source
  drift, legacy cutover input, historical changelog, or maintenance/diagnostic
  material and must point to ADR 0006 plus the May 30 control doc.
- Frontmatter descriptions, JSON/YAML/code blocks, and command snippets inherit
  the same authority boundary as prose. If a loader-facing frontmatter
  description cannot sit under a heading, keep it operational and avoid target
  architecture claims. If a code block or command snippet shows old payloads or
  preview/execute commands, put a sentence immediately before it that says it is
  deprecated source drift, legacy cutover input, historical changelog, or
  maintenance/diagnostic evidence, not active target mutation guidance. Active
  `SKILL.md` mutation sections must say mutation is temporarily unavailable
  unless this slice identifies a live source entrypoint that accepts target
  candidate mutations. If such an entrypoint is found, the skill must name it
  and document the target candidate contract without preserving prepare/execute.
- Manifest interface descriptions, capabilities, and default prompts are product
  surface. If active create/update mutation is unavailable, metadata must not
  invite general ticket writes, autonomous creation, lifecycle execution, or old
  mutation flows. Prompts such as "Track this follow-up" may remain only if the
  implementation finds and names a runnable target-candidate entrypoint; otherwise
  rephrase them to read/query/triage/maintenance behavior or remove them.
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
- [ ] Inspect `ticket_capture.py` and `ticket_update.py` only if a docs/static
  assertion needs exact deprecated-source-drift or legacy-cutover wording.
  Do not use those scripts to preserve command usability in active skill docs.
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
| `test_current_facing_docs_pin_runtime_first_modes_without_legacy_yaml_guidance` | target authority | Rewrite so durable modes are exactly `agent_primary` and `discussion_only`; allow `preview` only in diagnostic, maintenance, or deprecated-source-drift sections. |
| `test_current_facing_docs_separate_source_boundary_from_installed_runtime_proof` | evidence-boundary invariant | Keep or adapt; it protects source/installed/runtime lane separation. |
| `test_current_facing_docs_route_future_history_to_ticket_history_and_pending_summary` | target authority | Rewrite to target `Change History` plus private operation-log/pending-summary boundary. |
| `test_runtime_first_closeout_docs_do_not_describe_gateway_as_future_work` | historical invariant | Keep only if it checks stale closeout wording; do not make gateway prose target authority. |
| `test_adjacent_current_docs_describe_runtime_first_artifacts` | adjacent docs invariant | Keep or adapt for privacy/terms/changelog truth without broad architecture rewrites. |
| `test_ticket_autonomy_cli_exposes_ticket_level_commands_not_raw_ledger_mutators` | deprecated source drift | Delete, invert, or quarantine as source drift; do not keep as target mutation authority. |
| `test_pending_summary_validation_requires_live_repo_identity_fields` | deprecated source drift | Quarantine as source-runtime drift; do not use the approval fixture as target authority. |
| `test_apply_turn_verifies_repo_context_before_discovery_and_reuses_live_context` | deprecated source drift | Delete, invert, or quarantine as source-runtime drift unless it guards an evidence-boundary invariant. |
| `test_active_ticket_write_sites_are_named_functions_not_helper_file_allowlists` | safety invariant | Keep unless it blocks target docs/static assertions. |
| `test_direct_agent_and_runner_cannot_bypass_gateway_decision_contract` | deprecated source drift | Delete, invert, or quarantine as direct-execute source drift; do not make gateway/direct-execute a target contract. |
| `test_future_source_does_not_write_audit_logs_except_historical_repair` | target-compatible invariant | Keep; it supports the private-log/no-active-audit boundary. |
| `test_legacy_test_strings_are_only_negative_or_historical_fixtures` | deprecated-source boundary invariant | Keep or adapt to also cover old state-kernel terms. |
| `test_runtime_readiness_source_does_not_stage_legacy_yaml_autonomy_config` | safety invariant | Keep unless scope changes to runtime-readiness source. |
| `test_readme_states_supported_high_level_mutation_surfaces` | delete/rewrite | Replace with target candidate mutation path test; old capture/update command surfaces may appear only as deprecated source drift or legacy cutover input. |
| `test_handbook_states_supported_high_level_mutation_surfaces` | delete/rewrite | Replace with target candidate mutation path test; do not preserve prepare/execute runbook guidance. |
| `test_contract_states_supported_high_level_mutation_surfaces` | delete/rewrite | Replace with target candidate mutation path test and old-surface negatives. |
| `test_readme_ticket_schema_matches_yaml_contract_boundary` | target authority | Rewrite around ADR 0006 post-cutover schema and section-scoped old-shape negatives. |
| `test_contract_names_host_facing_autonomy_cli_surface` | deprecated source drift | Rewrite or quarantine so host CLI commands are not target public mutation architecture. |
| `test_readme_and_handbook_list_all_host_facing_autonomy_commands` | maintenance/diagnostic only | Delete, invert, or rewrite so command tables are diagnostic/maintenance inventories, not user mutation guidance. |
| `test_pr22_repair_closeout_records_test4_and_qualified_review_findings` | unrelated historical invariant | Keep unless changed docs remove the referenced closeout. |
| `test_engine_docs_state_runner_is_not_public_mutation_surface` | deprecated source drift | Keep only if it remains a negative target-boundary assertion. |
| `test_docs_describe_direct_agent_execute_gateway_boundary` | deprecated source drift | Rewrite so direct execute is source drift or diagnostic evidence, not target mutation architecture. |
| `test_contract_separates_core_runtime_and_activation_error_codes` | delete/rewrite | Replace target-facing error taxonomy assertions with target result-envelope assertions; keep old taxonomy only as deprecated source drift if needed. |
| `test_response_envelope_docs_point_to_error_code_taxonomy` | delete/rewrite | Replace with target result-envelope assertion. |
| `test_contract_documents_current_exit_code_mapping` | maintenance/diagnostic only | Keep only if scoped to maintenance/diagnostic execution, not target mutation authority. |
| `test_handbook_documents_runtime_proof_env_var_scope` | unrelated/source invariant | Keep unless wording conflicts with evidence-lane boundaries. |
| `test_stale_plan_is_only_public_toctou_error_code` | deprecated source drift | Delete or rewrite unless `stale_plan` is clearly source-drift recovery language, not target result taxonomy. |
| `test_ingest_contract_documents_filename_id_and_indefinite_processed_retention` | unrelated ingest invariant | Keep unless target contract changes ingest docs. |
| `test_project_local_ticket_tmp_payloads_are_ignored` | unrelated hygiene invariant | Keep. |
| `test_ticket_capture_skill_exists` | unrelated split-skill invariant | Keep. |
| `test_old_broad_skill_files_do_not_exist` | unrelated split-skill invariant | Keep. |
| `test_retired_pipeline_guide_is_not_current_source` | target-compatible invariant | Keep; old pipeline guide must not become current authority. |
| `test_task4_split_skill_files_exist` | unrelated split-skill invariant | Keep. |
| `test_ticket_capture_skill_frontmatter_matches_task3_contract` | frontmatter operational trigger | Adapt frontmatter expectations to operational trigger text only; do not encode target architecture in frontmatter. |
| `test_ticket_capture_skill_contains_exact_compact_preview_labels` | delete/invert | Remove positive preview-label requirements from active skill docs or invert them to prove preview is not a durable target mode. |
| `test_ticket_capture_skill_forbids_raw_user_wording` | privacy/safety invariant | Keep. |
| `test_ticket_capture_skill_requires_explicit_confirmation_before_writing` | delete/rewrite | Default to temporarily unavailable mutation guidance unless a live source target-candidate entrypoint is found; otherwise replace with target candidate identity plus `discussion_only` approval facts. |
| `test_ticket_capture_skill_uses_canonical_prepare_and_execute_commands` | delete/invert | Remove active prepare/execute guidance; invert if needed to prove the active skill no longer advertises those commands. |
| `test_ticket_capture_skill_documents_path_resolution_contract` | operational invariant | Keep. |
| `test_ticket_capture_skill_documents_required_synthesized_fields` | delete/rewrite | Replace `capture.*` payload requirements with target candidate mutation fields or temporary-unavailable wording. |
| `test_ticket_capture_skill_keeps_provenance_hook_owned` | safety invariant | Keep. |
| `test_ticket_capture_skill_documents_deterministic_inference_boundaries` | delete/rewrite | Remove `medium`, `critical`, and `component` as active guidance; target priorities are `high`, `normal`, and `low`. |
| `test_ticket_capture_skill_documents_refinement_and_preview_rules` | delete/rewrite | Remove refinement/preview rules as active mutation guidance; keep only deprecated drift or target candidate contract. |
| `test_ticket_capture_skill_documents_create_edit_cancel_handling` | delete/rewrite | Remove create/edit/cancel prepare/execute UX as active guidance; default to temporary-unavailable wording unless a live source target-candidate entrypoint is found. |
| `test_ticket_capture_skill_documents_split_deferral_behavior` | operational invariant | Keep unless docs no longer cover split captures. |
| `test_ticket_capture_skill_preserves_hook_guard_boundary` | safety invariant | Keep. |
| `test_user_facing_ticket_skills_prefer_recovery_hint` | deprecated source drift | Delete or rewrite so recovery hints are not target result-envelope taxonomy. |
| `test_contract_documents_recovery_hint_schema_and_codes` | delete/rewrite | Replace target-facing code taxonomy assertions; keep recovery hints only as deprecated source drift if needed. |
| `test_ticket_capture_skill_owns_creation_without_broad_ticket_skill` | split-skill invariant | Keep. |
| `test_new_split_skills_resolve_plugin_root_three_levels_up` | operational invariant | Keep. |
| `test_ticket_find_skill_contract_is_read_only` | read-only skill invariant | Adapt old filters/refinement text to deprecated source drift or legacy cutover input. |
| `test_ticket_update_skill_contract_is_preview_first_and_scoped` | delete/rewrite | Replace preview-first focused update payloads with target candidate mutation assertions or temporary-unavailable wording. |
| `test_ticket_update_json_examples_do_not_use_invalid_needs_refinement_tag` | deprecated source drift | Keep only if old JSON examples are quarantined as drift/cutover examples, not active guidance. |
| `test_ticket_review_skill_contract_is_read_only_and_capture_prompt_only` | read-only skill invariant | Keep; patch stale blocked-chain wording if target authority leaks in. |
| `test_ticket_doctor_skill_contract_is_explicit_maintenance_only` | maintenance skill invariant | Keep; patch preview/audit/activation wording only if it claims target authority. |
| `test_ticket_payloads_does_not_expose_boolean_security_gate_helpers` | unrelated source invariant | Keep. |
| `test_doctor_docs_describe_confirmed_stale_payload_cleanup` | maintenance invariant | Keep. |
| `test_handbook_documents_runtime_activation_operator_flow` | maintenance/diagnostic only | Keep only as maintenance/setup guidance, not target ticket mutation authority. |
| `test_handbook_documents_ticket_triage_doctor_runtime_probe_output` | maintenance/diagnostic only | Keep only as diagnostic/setup guidance. |
| `test_readme_and_handbook_do_not_describe_guard_as_fail_open` | safety invariant | Keep. |
| `test_current_docs_describe_audit_as_historical_only` | target-compatible invariant | Keep; it supports no active `.audit/` authority. |
| `test_handbook_documents_direct_agent_execute_gateway_requirement` | deprecated source drift | Delete, invert, or quarantine as direct-execute source drift. |
| `test_changelog_announces_activate_runtime_subcommand` | changelog invariant | Keep or adapt to current unreleased wording. |
| `test_claude_instructions_reference_current_turbo_mode_source_roots` | repo instruction invariant | Keep unless unrelated to changed docs. |
| `test_repo_agents_instructions_reference_ticket_public_launcher` | repo instruction invariant | Keep unless unrelated to changed docs. |
| `test_skill_docs_use_project_root_marker_walk_not_git_rev_parse` | operational invariant | Keep. |
| `test_skill_docs_define_project_root_and_tickets_dir_separately` | operational invariant | Keep. |
| `test_current_facing_docs_include_dash_b_launcher_examples` | maintenance/diagnostic only | Keep only for maintenance/diagnostic commands. |
| `test_launcher_docs_mark_python3_as_legacy_compatibility` | legacy launcher invariant | Keep. |
| `test_current_facing_docs_do_not_keep_no_flag_plugin_launchers` | operational invariant | Keep. |
| `test_handbook_shell_metacharacter_list_matches_guard_regex` | safety invariant | Keep. |
| `test_handbook_does_not_advertise_stale_test_count_or_version_footer` | docs hygiene invariant | Keep. |
| `test_readme_and_handbook_do_not_advertise_counted_test_inventory` | docs hygiene invariant | Keep. |
| `test_update_skill_uses_focused_update_backend_as_mutation_path` | delete/invert | Remove positive focused-update backend requirements from active skill docs. |
| `test_split_skills_document_check_review_and_doctor_surfaces` | split-skill invariant | Keep. |
| `test_readme_documents_ticket_ux_commands` | maintenance/diagnostic only | Keep only if command tables are diagnostic or maintenance inventories, not mutation guidance. |
| `test_readme_classifies_activate_runtime_as_maintenance_not_read_only` | maintenance invariant | Keep. |
| `test_readme_and_handbook_use_source_authority_installed_boundary` | evidence-boundary invariant | Keep. |
| `test_handbook_update_surface_matches_focused_backend` | delete/rewrite | Remove focused backend fields as active guidance; keep only source-drift/cutover notes if needed. |
| `test_handbook_smoke_uses_capture_preview_with_workspace_payload` | delete/rewrite | Remove capture preview smoke as target or active workflow guidance. |
| `test_manifest_documents_required_interface_urls` | manifest invariant | Keep. |
| `test_plugin_default_prompts_are_capture_first` | product prompt invariant | Keep unless prompt wording claims target architecture. |
| `test_no_skill_description_advertises_old_single_surface` | frontmatter invariant | Keep/adapt so descriptions stay operational and do not overclaim target architecture. |
| `test_task4_docs_do_not_overclaim_current_placeholder_refinement` | delete/rewrite | Remove placeholder refinement as active guidance; keep only deprecated source drift if needed. |
| `test_docs_describe_capture_first_five_skill_surface` | product surface invariant | Rewrite if old schema vocabulary remains; do not make five-skill surface target mutation architecture. |
| `test_contract_preserves_engine_boundary_for_workflow_runner` | deprecated source drift | Keep only if workflow runner is explicitly diagnostic/source-drift evidence. |

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
  `preview` allowed only in diagnostic, maintenance, or deprecated-source-drift
  sections.
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
  understand known source drift. Do not edit
  `test_autonomy_runtime.py`, `test_turn_batch.py`, or other runtime/source
  behavior tests in this slice except to add comments only if later explicitly
  requested. The current approval-object, preview-mode, commit-disposition,
  pending-summary, and `ticket_change_scope` assertions remain known source
  drift until runtime implementation changes them.

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
in deprecated-source-drift, legacy-cutover, historical, or maintenance/diagnostic
sections only when the section points to ADR 0006 and the control doc, and does
not make old shapes normative target authority or active mutation guidance.

Suggested target section names for docs/static tests:

- `## Authority Boundary`
- `## Target Post-Cutover Ticket Shape`
- `## Target Candidate Mutation Contract`
- `## Target Result Envelope`
- `## Target Change History Grammar`
- `## Deprecated Source Drift`
- `## Legacy Cutover Input`
- `## Historical Changelog`
- `## Maintenance And Diagnostics`

Tests should look inside the matching target sections for target requirements
and inside deprecated-source-drift, legacy-cutover, historical, or
maintenance/diagnostic sections for allowed old terms. Do not test by banning
words globally across whole files.

Frontmatter and code-block rules for tests:

- Loader-facing frontmatter descriptions are not section-scoped. Test that they
  describe when to invoke the skill and current operational safety gates only;
  they must not advertise old fields as target schema or preview as a durable
  target mode.
- JSON/YAML examples in `SKILL.md`, README, handbook, or contract files must be
  tested inside their nearest labeled prose boundary. Old payloads such as
  `capture.*`, `update`, `component`, `blocks`, or `acceptance_criteria` may
  appear only when the preceding prose labels them deprecated source drift,
  legacy cutover input, historical changelog, or maintenance/diagnostic
  evidence.
- Target examples must use the candidate mutation contract shape, not
  prepare/execute payloads. They must include `target.fields` or
  `target.sections` and must reject unknown target fields.
- Command snippets are diagnostic or maintenance evidence only when they are not
  ordinary capture/update mutation commands, unless they call the future
  candidate mutation path described by ADR 0006/control doc. Old capture/update
  prepare/execute snippets may appear only as deprecated source drift or legacy
  cutover input. Active mutation docs must not use old prepare/execute snippets
  as user instructions.

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
  archived closed lifecycle, and old metadata fields into narrow deprecated
  source-drift, legacy-cutover, historical, or maintenance/diagnostic notes.
- [ ] Replace four-stage/product-pipeline prose with state-kernel and candidate
  mutation prose.
- [ ] Remove pipeline diagrams as product architecture. If a diagram remains, it
  must be labeled deprecated source drift or legacy cutover input and cannot be
  under an "Architecture" heading without an ADR/control warning.
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
- [ ] Add the same authority boundary to each changed skill before changing
  examples or field vocabulary:

| Skill | Deprecated material may say | Target or active section must say |
|---|---|---|
| `capture-ticket` | Prepare/execute capture, compact confirmation preview, old `capture.*` payload fields (`title`, `captured_request`, `problem`, `next_action`, `capture_confidence`, `priority`, `tags`, `component`, `related_paths`, `acceptance_criteria`), and old priority inference (`critical`, `high`, `medium`, `low`) are deprecated source drift or legacy cutover input only. | Default active create guidance to temporarily unavailable. Document the target candidate mutation contract as runnable only if this slice identifies and names a live source target-candidate entrypoint. Target priorities are `high`, `normal`, and `low`; `component`, `capture_confidence`, `refinement_status`, and `acceptance_criteria` are not target frontmatter fields. |
| `read-ticket` | Old filters such as `blocked`, `critical`, and `medium` are deprecated source drift or legacy cutover input only. | Target schema uses statuses `open`, `in_progress`, `done`, `wontfix`; blockedness derives from `blocked_by`; target priorities are `high`, `normal`, `low`. Read/query guidance may remain when it does not present old schema as target authority. |
| `update-ticket` | Prepare/execute update, preview confirmation UX, and old focused update fields (`problem`, `next_action`, `acceptance_criteria`, `priority`, `tags`, `component`, `related_paths`, `blocked_by`, `blocks`, `status`, `reopen_reason`) are deprecated source drift or legacy cutover input only. | Default active update guidance to temporarily unavailable. Document target writes as runnable only if this slice identifies and names a live source target-candidate entrypoint. Target writes use `target.fields`, `target.sections`, `proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`; `blocks`, `component`, `refinement_status`, and `acceptance_criteria` are not target frontmatter fields. |
| `ticket-backlog-triage` | Old stale, blocked-chain, or command-output wording is deprecated source drift unless used only for read-only inventory. | Target triage is read/query/reporting unless it produces candidate mutations for the runtime path; persisted `blocked` status and reverse `blocks` edges are not target schema. |
| `ticket-doctor` | Explicit maintenance, diagnostics, activation, stale payload cleanup, historical audit repair, and runtime-readiness commands are maintenance/diagnostic material only. | Target doctor docs must not make preview, audit logs, activation proof, or cache refresh part of normal target ticket mutation authority. |

- [ ] Add a short authority note where behavior-shaping instructions otherwise
  look like contract authority: ADR 0006/control doc own the target model; old
  command paths are deprecated source drift, legacy cutover input, historical
  changelog, or maintenance/diagnostic material.
- [ ] Remove old backend command examples from active mutation instructions. Old
  capture/update `prepare/execute` examples may remain only for deprecated
  source drift, legacy cutover inventory, or historical accuracy, and the
  boundary must be labeled immediately before the example. Do not place ordinary
  capture/update mutation examples in maintenance/diagnostic runbooks.
- [ ] Remove or quarantine old payload fields and examples: `component`,
  `blocks`, `refinement_status`, `acceptance_criteria`, `blocked`, `critical`,
  `medium`, and persistent preview.
- [ ] For `capture-ticket` and `update-ticket`, state that mutation is
  temporarily unavailable unless this slice identifies a live source entrypoint
  that accepts the target candidate mutation contract. If such an entrypoint is
  identified, name the exact entrypoint and document the target candidate
  contract. Do not preserve prepare/execute as operational guidance.
- [ ] For `read-ticket`, keep read/query instructions only if they avoid old
  target schema; old `blocked`, `critical`, and `medium` filters may remain only
  as deprecated source drift or legacy cutover input.

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
- [ ] For `.codex-plugin/plugin.json`, inspect `description`,
  `interface.shortDescription`, `interface.longDescription`,
  `interface.capabilities`, and `interface.defaultPrompt`. If active create or
  update mutation is temporarily unavailable, remove or rephrase metadata that
  advertises general writes, autonomous creation, lifecycle execution, or old
  mutation flows. Keep write-like prompts such as `Track this follow-up` only if
  the implementation names a runnable target-candidate entrypoint.

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
- Current command usability is not protected. Old command behavior may remain
  documented only as deprecated source drift, legacy cutover input, historical
  changelog, or maintenance/diagnostic material.

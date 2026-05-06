# Turbo Mode Refresh 04 Commit-Safe Evidence Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a non-mutating commit-safe evidence layer for Turbo Mode refresh dry-run and plan-refresh results.

**Architecture:** Plan 04 consumes the Plan 02 local-only evidence payload and Plan 03 read-only runtime inventory summary, then writes a redacted commit-safe review summary under `plugins/turbo-mode/evidence/refresh/` only when explicitly requested. The summary records hashes, statuses, explicitly sanitized state axes, request methods, runtime identity, and omission reasons; it must not contain raw app-server transcripts, config contents, process lists, local-only failure strings, or mutation-only fake artifacts.

**Tech Stack:** Python 3.11, stdlib `argparse` / `hashlib` / `json` / `pathlib` / `subprocess`, existing `refresh` package modules, `pytest`, `ruff`.

---

## Source Spec Read

Read before executing this plan:

- `docs/superpowers/specs/2026-05-04-turbo-mode-installed-refresh-design.md`
- `docs/superpowers/plans/2026-05-04-turbo-mode-refresh-01-classifier-state-core.md`
- `docs/superpowers/plans/2026-05-05-turbo-mode-refresh-02-non-mutating-cli.md`
- `docs/superpowers/plans/2026-05-05-turbo-mode-refresh-03-readonly-runtime-inventory.md`

Spec boundaries that govern Plan 04:

- Raw app-server transcripts stay local-only.
- Commit-safe summaries may contain hashes, statuses, classifications, allowed paths, runtime identity summaries, and pointers to local-only evidence.
- Commit-safe summaries must not invent post-refresh, smoke, rollback, process-list, or mutation artifacts for phases that were never reached.
- Stale evidence rejection must be explicit.
- Validator digest bootstrap must follow the candidate/final projection algorithm in the source spec, with an explicit Plan 04 addition: validator summaries record both the raw candidate-summary file SHA256 required by the spec and the canonical projected-payload SHA256 used for final-mode replay.
- Dirty-state policy must fail on relevant source, marketplace, or refresh-tool modifications outside committed `HEAD` unless the tool is explicitly creating a post-commit binding artifact.
- Mutation remains outside this plan.

## Plan 04 Spec Amendment: Non-Mutating Schema Subset

Plan 04 is a controlled non-mutating subset of `docs/superpowers/specs/2026-05-04-turbo-mode-installed-refresh-design.md`.
When this section conflicts with the broader source spec, this section governs Plan 04 only.
Do not generalize these amendments to future mutation, rollback, recovery, or app-server install plans.

Intentional deviations from the source spec:

- The source spec's full commit-safe schema includes mutation-phase fields such as `post_refresh_cache_manifest_sha256`, `pre_refresh_config_sha256`, `post_refresh_config_sha256`, `post_refresh_inventory_sha256`, `unexpected_side_effect_scan_sha256`, `post_mutation_process_census_sha256`, `exclusivity_status`, `selected_smoke_tier`, `smoke_summary_sha256`, `process_gate_summary`, and `rollback_or_restore_status`.
  Plan 04 does not create fake values for those fields because `--refresh`, `--guarded-refresh`, process gates, smoke execution, rollback, recovery, and installed-cache/config mutation are outside this slice.
  Instead, Plan 04 records explicit `omission_reasons` for omitted mutation-phase fields.
- The source spec's full schema includes `run_metadata`.
  Plan 04 replaces that broad container with explicit top-level fields plus `current_run_identity` so every commit-safe object can be structurally allowlisted.
- The source spec says commit-safe evidence records request methods, response status summaries, and transcript SHA256.
  Plan 04 records request methods and a stable app-server inventory replay-identity digest, but does not commit response-status summaries or raw Plan 03 `transcript_sha256` because the Plan 03 transcript digest and status-envelope details can change with scratch cwd and raw transcript details that are not durable commit-safe freshness inputs.
  This is a Plan 04-specific amendment, not a statement that transcript digests are never useful in later app-server install or mutation evidence.
- The source spec requires a local-only sensitivity scan for raw local-only artifacts.
  Plan 04 implements that scan in the local-only redaction validator summary and commits only the validator summary digest, not local-only counts, examples, artifact names, transcripts, process listings, or config contents.
- The source spec's stale-evidence rule remains binding, but Plan 04 applies it only to non-mutating inputs: source manifests, installed-cache manifests, repo marketplace metadata, local config metadata, runtime config projection, app-server inventory replay identity, runtime identity fields, local-only summary identity, repo `HEAD`, repo tree, and tool SHA256.

Worker rule: if implementation reveals another source-spec divergence, stop and patch this amendment section before writing code that depends on the divergence.

## Scope

Plan 04 implements:

- `python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --dry-run --record-summary`
- `python3 plugins/turbo-mode/tools/refresh_installed_turbo_mode.py --plan-refresh --record-summary`
- `--record-summary` with or without `--inventory-check`
- commit-safe summaries under `plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.json`
- non-mutating metadata validation for the committed summary and its paired local-only summary
- redaction validation for commit-safe summaries
- local-only sensitivity scanning for raw/local-only artifacts, summarized only in local-only validator output
- digest bootstrap for validator summaries without self-referential hashes
- relevant dirty-state rejection before writing commit-safe summaries
- current-run stale-evidence rejection for source manifests, installed-cache manifests, repo marketplace metadata, local config metadata, runtime config projection, app-server inventory projection, local-only summary identity, repo `HEAD`, repo tree, and tool SHA256
- deterministic sanitized projection from the paired local-only summary to every commit-safe state field
- transactional commit-safe summary publication: the repo-local final path is created only after candidate and final validators pass
- hardened summary output path validation with no clobbering, no symlinks, and no output outside the repo evidence root
- a clean source implementation commit boundary before live commit-safe smoke
- a separate evidence/docs commit boundary for the generated summary and closeout notes
- tests proving raw transcripts and local-only payloads do not enter commit-safe evidence
- tests proving unsafe local-only failure text cannot leak through nested fields such as `axes.reasons`, `runtime_config.reasons`, or `diff_classification[*].reasons`
- tests proving transcript-like, config-like, and path-heavy payloads cannot hide under allowed nested containers such as `current_run_identity`, `dirty_state`, `omission_reasons`, `app_server_server_info`, or `app_server_protocol_capabilities`

Plan 04 does not implement:

- executable `--refresh`
- executable `--guarded-refresh`
- `plugin/install`
- installed-cache mutation
- global config mutation
- process gates
- locks
- run-state markers
- crash recovery
- rollback or restore proof
- post-commit binding of older local-only runs
- evidence retention or prune execution

## Current Base

- Current branch: `main`
- Current base at planning time: `1b5199f`
- Current plan artifact state at planning time: untracked file at `docs/superpowers/plans/2026-05-06-turbo-mode-refresh-04-commit-safe-evidence.md`
- Plan 03 PR #3 is merged.
- Plan 03 branch `feature/turbo-mode-refresh-plan-03-runtime-inventory` has been deleted locally and remotely.
- Live Plan 03 smoke can collect aligned runtime inventory while terminal status remains `coverage-gap-blocked`.

## Commit Boundaries

Plan 04 has two named commit boundaries:

1. **Source implementation commit**
   - Contains implementation source, tests, and the plan document before completion evidence.
   - Must be clean on relevant dirty-state paths before the live `--record-summary` smoke.
   - The live commit-safe summary records this commit's `repo_head` and `repo_tree`.
   - Metadata validators compare against this current `HEAD` during summary generation and final-mode validation.

2. **Evidence/docs commit**
   - Created after the live smoke.
   - Contains the generated commit-safe summary under `plugins/turbo-mode/evidence/refresh/` and the plan's `## Completion Evidence` section.
   - Does not change the source implementation commit that the summary is bound to.
   - Must record the source implementation commit hash and tree hash in the committed completion evidence.
   - Must not try to embed its own final commit hash or tree hash inside the same commit. The evidence/docs commit identity is reported in closeout or PR text after the commit exists, or in a later follow-up metadata commit if a committed record is required.

Plan 04 summaries are **source-commit-bound**, not self-commit-bound. After the evidence/docs commit is created, rerunning the metadata validator from that later `HEAD` against the committed summary is expected to fail unless the validator is run from the recorded source implementation commit. Post-commit rebinding is outside Plan 04.

## Commit-Safe Write Contract

The commit-safe evidence path is publish-only:

- Candidate summaries are written under the local-only run directory, never directly to `plugins/turbo-mode/evidence/refresh/`.
- Final summaries are also assembled under the local-only run directory first.
- The repo-local summary path is created only after candidate validators pass, final validators pass, and final-mode validators verify the existing candidate-mode validator summaries.
- If validation fails, is interrupted, or raises before publish, no file may exist at `plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.json`.
- Repo-local publish must reject existing output paths. Plan 04 does not overwrite or rebind an existing committed summary.

`--summary-output` is not an arbitrary write path. It is only a controlled override for the final repo-local publish destination, and it must resolve under `<repo_root>/plugins/turbo-mode/evidence/refresh/`. It must reject path escape, symlink traversal, existing files, and any output outside that evidence root. Tests should use a temporary git repo and pass a path under that temporary repo's evidence root.

## File Structure

Create:

- `plugins/turbo-mode/tools/refresh/commit_safe.py`
  - Builds the commit-safe non-mutating summary payload.
  - Computes SHA256 digests for local-only summary, source manifest projection, installed-cache manifest projection, repo marketplace metadata, local config metadata, runtime config projection, app-server inventory summary projection, and tool source.
  - Enforces relevant dirty-state before commit-safe summary writes.
  - Builds commit-safe fields from an explicit deterministic projection of the paired local-only summary.
  - Projects `axes`, `runtime_config`, and `diff_classification` through commit-safe helper functions; it never copies those local-only objects wholesale.
  - Converts unsafe local-only failure strings into commit-safe reason codes.
  - Carries explicit omission reasons for mutation-only fields.

- `plugins/turbo-mode/tools/refresh/validation.py`
  - Shared constants-free validation helpers for summary projection, digesting, schema allowlist validation, and redaction scanning.
  - Does not import from `plugins/turbo-mode/tools/migration/`.

- `plugins/turbo-mode/tools/refresh_validate_run_metadata.py`
  - Recomputes current repo/tool/local-summary metadata and validates a commit-safe summary by comparing it to a deterministic projection from the paired local-only summary.
  - Writes a local-only metadata validation summary.

- `plugins/turbo-mode/tools/refresh_validate_redaction.py`
  - Validates the commit-safe schema allowlist, then checks that summaries contain no raw transcript, process-list, config-content, token-like, email-like, or private payload values.
  - Scans local-only raw artifacts for sensitivity findings and writes counts, redacted examples, and affected artifact names only to the local-only redaction validator summary.
  - Writes a local-only redaction validation summary.

- `plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py`
- `plugins/turbo-mode/tools/refresh/tests/test_validation.py`

Modify:

- `plugins/turbo-mode/tools/refresh/evidence.py`
  - Keep local-only transcript behavior unchanged.
  - Continue exporting `SCHEMA_VERSION` for the commit-safe source-schema field.

- `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
  - Add `--record-summary`.
  - Add `--summary-output` for tests and controlled repo-local evidence output only.
  - Print the commit-safe summary path when written.

- `plugins/turbo-mode/tools/refresh/tests/test_evidence.py`
- `plugins/turbo-mode/tools/refresh/tests/test_cli.py`

Do not modify:

- `plugins/turbo-mode/tools/migration/migration_common.py`
- `plugins/turbo-mode/tools/migration/validate_redaction.py`
- installed cache roots under `/Users/jp/.codex/plugins/cache/turbo-mode/`
- `/Users/jp/.codex/config.toml`

## Commit-Safe Summary Contract

Plan 04 commit-safe summary schema:

```json
{
  "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
  "run_id": "run-1",
  "mode": "dry-run",
  "source_local_summary_schema_version": "turbo-mode-refresh-plan-03",
  "repo_head": "40-hex-or-test-value",
  "repo_tree": "40-hex-or-test-value",
  "tool_path": "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py",
  "tool_sha256": "sha256",
  "dirty_state_policy": "fail-relevant-dirty-state",
  "dirty_state": {
    "status": "clean-relevant-paths",
    "relevant_paths_checked": [
      ".agents/plugins/marketplace.json",
      "plugins/turbo-mode/tools/refresh",
      "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py",
      "plugins/turbo-mode/tools/refresh_validate_run_metadata.py",
      "plugins/turbo-mode/tools/refresh_validate_redaction.py"
    ],
    "post_commit_binding": false
  },
  "current_run_identity": {
    "local_summary_schema_version": "turbo-mode-refresh-plan-03",
    "local_summary_run_id": "run-1",
    "local_summary_mode": "dry-run",
    "source_manifest_sha256": "sha256-or-null",
    "source_manifest_unavailable_reason": null,
    "installed_cache_manifest_sha256": "sha256-or-null",
    "installed_cache_manifest_unavailable_reason": null,
    "repo_marketplace_sha256": "sha256-or-null",
    "repo_marketplace_unavailable_reason": null,
    "local_config_metadata_sha256": "sha256-or-null",
    "local_config_metadata_unavailable_reason": null,
    "runtime_config_projection_sha256": "sha256-or-null",
    "runtime_config_projection_unavailable_reason": null,
    "app_server_inventory_summary_sha256": "sha256-or-null",
    "app_server_inventory_freshness": "recomputed-readonly-inventory",
    "runtime_identity": {
      "codex_version": "codex-cli 0.test",
      "codex_executable_path": "/opt/homebrew/bin/codex",
      "codex_executable_sha256": "sha256-or-null",
      "codex_executable_hash_unavailable_reason": null,
      "app_server_server_info": {
        "name": "codex-app-server",
        "version": "0.test"
      },
      "app_server_protocol_capabilities": {
        "experimentalApi": true
      },
      "app_server_parser_version": "refresh-app-server-inventory-1",
      "app_server_response_schema_version": "app-server-readonly-inventory-v1"
    },
    "runtime_identity_freshness": "recomputed-readonly-inventory"
  },
  "local_only_evidence_root": "/Users/jp/.codex/local-only/turbo-mode-refresh/run-1",
  "local_only_summary_sha256": "sha256",
  "terminal_plan_status": "coverage-gap-blocked",
  "final_status": "coverage-gap-blocked",
  "axes": {
    "filesystem_state": "drift",
    "coverage_state": "coverage-gap",
    "runtime_config_state": "aligned",
    "preflight_state": "blocked",
    "selected_mutation_mode": "none",
    "reason_codes": ["app-server-returned-error"],
    "reason_count": 1
  },
  "diff_classification": [
    {
      "canonical_path": "handoff/1.6.0/SKILL.md",
      "mutation_mode": "blocked",
      "coverage_status": "coverage_gap",
      "outcome": "coverage-gap-fail",
      "reason_codes": ["coverage-gap-path"],
      "smoke": []
    }
  ],
  "runtime_config": {
    "state": "aligned",
    "marketplace_state": "aligned",
    "plugin_hooks_state": "true",
    "plugin_enablement_state": {
      "handoff@turbo-mode": "enabled",
      "ticket@turbo-mode": "enabled"
    },
    "reason_codes": [],
    "reason_count": 0
  },
  "app_server_inventory_status": "collected",
  "app_server_inventory_failure_reason_code": null,
  "app_server_inventory_summary_sha256": "sha256-or-null",
  "app_server_request_methods": ["initialize", "initialized", "plugin/read"],
  "codex_version": "codex-cli 0.test",
  "codex_executable_path": "/opt/homebrew/bin/codex",
  "codex_executable_sha256": "sha256-or-null",
  "codex_executable_hash_unavailable_reason": null,
  "app_server_server_info": {
    "name": "codex-app-server",
    "version": "0.test"
  },
  "app_server_protocol_capabilities": {
    "experimentalApi": true
  },
  "app_server_parser_version": "refresh-app-server-inventory-1",
  "app_server_response_schema_version": "app-server-readonly-inventory-v1",
  "metadata_validation_summary_sha256": "sha256-or-null",
  "redaction_validation_summary_sha256": "sha256-or-null",
  "omission_reasons": {
    "raw_app_server_transcript": "local-only",
    "process_gate": "outside-plan-04",
    "post_refresh_cache_manifest": "outside-plan-04",
    "pre_refresh_config_sha256": "outside-plan-04",
    "post_refresh_config_sha256": "outside-plan-04",
    "smoke_summary": "outside-plan-04",
    "rollback_or_restore_status": "outside-plan-04",
    "exclusivity_status": "outside-plan-04"
  }
}
```

`local_only_evidence_root` is an absolute local pointer by design. It is commit-safe because it names where the operator can find raw local-only evidence on this machine; it is not a machine-portable artifact and must not be treated as proof by itself.

The commit-safe summary schema is allowlisted. A valid summary may contain only these top-level keys:

- `schema_version`
- `run_id`
- `mode`
- `source_local_summary_schema_version`
- `repo_head`
- `repo_tree`
- `tool_path`
- `tool_sha256`
- `dirty_state_policy`
- `dirty_state`
- `current_run_identity`
- `local_only_evidence_root`
- `local_only_summary_sha256`
- `terminal_plan_status`
- `final_status`
- `axes`
- `diff_classification`
- `runtime_config`
- `app_server_inventory_status`
- `app_server_inventory_failure_reason_code`
- `app_server_inventory_summary_sha256`
- `app_server_request_methods`
- `codex_version`
- `codex_executable_path`
- `codex_executable_sha256`
- `codex_executable_hash_unavailable_reason`
- `app_server_server_info`
- `app_server_protocol_capabilities`
- `app_server_parser_version`
- `app_server_response_schema_version`
- `metadata_validation_summary_sha256`
- `redaction_validation_summary_sha256`
- `omission_reasons`

Nested projected objects are validated by the metadata validator's deterministic projection comparison. They are not commit-safe merely because they are deterministic. `axes`, `runtime_config`, `diff_classification`, `current_run_identity`, `current_run_identity.runtime_identity`, `dirty_state`, `omission_reasons`, `app_server_server_info`, and `app_server_protocol_capabilities` must be rebuilt through explicit commit-safe projection helpers that copy only allowlisted fields. `axes`, `runtime_config`, and `diff_classification` replace free-form `reasons` strings with allowlisted `reason_codes` plus `reason_count`. Redaction validation must reject unknown top-level containers, unknown nested keys in every allowed object, forbidden nested key names such as `events`, `body`, `requests`, `responses`, and `config`, and sensitive string values. Sensitive-pattern scanning is a second layer, not the primary commit-safe guarantee.

Allowed nested schemas:

- `dirty_state`: `status`, `relevant_paths_checked`, `post_commit_binding`.
- `current_run_identity`: `local_summary_schema_version`, `local_summary_run_id`, `local_summary_mode`, `source_manifest_sha256`, `source_manifest_unavailable_reason`, `installed_cache_manifest_sha256`, `installed_cache_manifest_unavailable_reason`, `repo_marketplace_sha256`, `repo_marketplace_unavailable_reason`, `local_config_metadata_sha256`, `local_config_metadata_unavailable_reason`, `runtime_config_projection_sha256`, `runtime_config_projection_unavailable_reason`, `app_server_inventory_summary_sha256`, `app_server_inventory_freshness`, `runtime_identity`, `runtime_identity_freshness`.
- `current_run_identity.runtime_identity`: `codex_version`, `codex_executable_path`, `codex_executable_sha256`, `codex_executable_hash_unavailable_reason`, `app_server_server_info`, `app_server_protocol_capabilities`, `app_server_parser_version`, `app_server_response_schema_version`.
- `app_server_server_info`: `name`, `version`.
- `app_server_protocol_capabilities`: `experimentalApi`.
- `axes`: `filesystem_state`, `coverage_state`, `runtime_config_state`, `preflight_state`, `selected_mutation_mode`, `reason_codes`, `reason_count`.
- `runtime_config`: `state`, `marketplace_state`, `plugin_hooks_state`, `plugin_enablement_state`, `reason_codes`, `reason_count`.
- `runtime_config.plugin_enablement_state`: exact config plugin ids `handoff@turbo-mode` and `ticket@turbo-mode` mapped to `enabled`, `disabled`, `missing`, or `malformed`. Do not normalize these keys to marketplace names such as `handoff` or `ticket`; Plan 03 local-only runtime config uses the config plugin ids from `EXPECTED_CONFIG_PLUGINS`.
- `diff_classification[*]`: `canonical_path`, `mutation_mode`, `coverage_status`, `outcome`, `reason_codes`, `smoke`.
- `omission_reasons`: only the Plan 04 omission keys shown in the schema example; values must be `local-only` or `outside-plan-04`.

`app_server_server_info` and `app_server_protocol_capabilities` are projections, not raw app-server dictionaries. If the app-server returns additional fields, nested dicts, response summaries, paths, or transcript-like content, the projection must drop them unless this section is amended with a new explicit field and tests.

Structural key allowlists are not enough. Redaction validation must also enforce field-specific value rules: schema/version constants must match exactly, server info strings must be short non-path strings, protocol capability values must have the expected primitive types, dirty-state paths must be the exact relative paths in the relevant dirty-state set, canonical diff paths must be relative plugin paths, app-server request methods must be in the read-only inventory method allowlist, `local_only_evidence_root` must be an absolute path ending in `/local-only/turbo-mode-refresh/<safe-run-id>`, and `codex_executable_path` is the only broad absolute executable path field. Any config-looking string, transcript/status-envelope-looking string, or broad absolute path outside an explicitly allowed path field is a validation failure.

Projection requirements:

- `terminal_plan_status`, `final_status`, sanitized `axes`, sanitized `diff_classification`, sanitized `runtime_config`, `app_server_inventory_status`, `app_server_inventory_failure_reason_code`, `app_server_inventory_summary_sha256`, `app_server_request_methods`, and runtime identity fields must be recomputed from the paired local-only summary or its stable Plan 04 inventory replay-identity projection.
- The metadata validator must compare every projected field, not only file digests.
- The metadata validator must also verify local-only summary identity before projection: `schema_version` equals `turbo-mode-refresh-plan-03`, `run_id` equals the commit-safe `run_id`, and `mode` equals the commit-safe `mode`.
- Stale-evidence rejection is not satisfied by projection alone. Metadata validation must recompute `current_run_identity` from live source/cache/config/runtime inputs at validation time and compare it to the committed summary. For Plan 04 this means:
  - recompute source and installed-cache manifest projection SHA256 values from `build_plugin_specs()` and `build_manifest()` for the current repo/codex-home roots;
  - recompute the repo marketplace file metadata SHA256 without committing its raw contents;
  - recompute local config file metadata SHA256 without committing raw TOML contents;
  - recompute the runtime-config projection SHA256 from `read_runtime_config_state()` output;
  - when source manifests, installed-cache manifests, repo marketplace metadata, local config metadata, or runtime-config projection cannot be recomputed, set the corresponding SHA256 field to `null` and set a matching allowlisted `*_unavailable_reason` value; do not copy exception text;
  - re-run read-only app-server inventory and recompute a stable app-server inventory replay-identity SHA256 when inventory status is `collected`;
  - exclude `transcript_sha256`, raw transcript bytes, request bodies, response bodies, and temporary `scratch_cwd`-dependent values from the replay-identity SHA256;
  - keep the raw Plan 03 `transcript_sha256` local-only; it may help local debugging but is not a stable commit-safe freshness input;
  - record `app_server_inventory_freshness = "recomputed-readonly-inventory"` only when that live re-collection matches;
  - record `app_server_inventory_freshness = "not-requested"`, `"blocked-runtime-config"`, or `"failure-code-only"` for the other states, and do not describe those states as full runtime freshness proof;
  - when app-server inventory status is `collected`, project live runtime identity from the re-collected inventory into `current_run_identity.runtime_identity`;
  - `current_run_identity.runtime_identity` must include only `codex_version`, `codex_executable_path`, `codex_executable_sha256`, `codex_executable_hash_unavailable_reason`, `app_server_server_info`, `app_server_protocol_capabilities`, `app_server_parser_version`, and `app_server_response_schema_version`;
  - `app_server_server_info` must be projected to only `name` and `version` string-or-null fields;
  - `app_server_protocol_capabilities` must be projected to only the supported `experimentalApi` boolean-or-null field for Plan 04;
  - for `collected` inventory, metadata validation must reject stale top-level runtime identity fields even if the structural inventory replay identity still matches;
  - for `not-requested`, `requested-blocked`, and `requested-failed`, set `current_run_identity.runtime_identity = null` and `runtime_identity_freshness` to `"not-requested"`, `"blocked-runtime-config"`, or `"failure-code-only"` respectively; do not claim live runtime identity freshness for those states;
  - reject a local-only summary whose identity fields, projected state fields, or current-run digests do not match the commit-safe summary.
- Inventory states must remain distinct: `not-requested`, `requested-blocked`, `requested-failed`, and `collected` must not collapse into a boolean success/failure field.
- `app_server_inventory_failure_reason_code` is the only commit-safe failure field. The raw Plan 03 `app_server_inventory_failure_reason` string is local-only and must never be projected into commit-safe evidence.
- Allowed `app_server_inventory_failure_reason_code` values are `null`, `runtime-config-preflight-unavailable`, `app-server-stdout-closed`, `app-server-returned-error`, `app-server-timeout`, `app-server-contract-invalid`, `app-server-unavailable`, `refresh-error`, and `unknown-inventory-failure`.
- Reason-code derivation may inspect the local-only failure string only for controlled classifier phrases. It must not copy substrings from the failure string, response object, request object, file path payload, or exception representation.
- `axes.reasons`, `runtime_config.reasons`, and `diff_classification[*].reasons` are forbidden in commit-safe output.
- Allowed nested reason codes are `source-root-missing`, `cache-root-missing`, `generated-residue-present`, `manifest-build-failed`, `runtime-config-parse-failed`, `config-marketplaces-section-missing`, `config-marketplace-missing`, `config-marketplace-source-type-mismatch`, `config-marketplace-source-not-string`, `config-marketplace-source-mismatch`, `config-plugin-hooks-absent`, `config-features-section-malformed`, `config-plugin-hooks-disabled`, `config-plugin-hooks-malformed`, `config-plugins-section-missing`, `config-plugin-enabled-missing`, `config-plugin-enabled-disabled`, `config-plugin-enabled-malformed`, `added-executable-path`, `added-non-doc-path`, `executable-doc-surface`, `command-shape-changed`, `projection-parser-warning`, `semantic-policy-trigger`, `coverage-gap-path`, `guarded-only-path`, `fast-safe-path`, `unmatched-path`, `runtime-config-preflight-unavailable`, `app-server-stdout-closed`, `app-server-returned-error`, `app-server-timeout`, `app-server-contract-invalid`, `app-server-unavailable`, `refresh-error`, and `unknown-reason`.
- Any unrecognized local-only reason string must map to `unknown-reason`. The raw string must not appear anywhere in `json.dumps(commit_safe_payload, sort_keys=True)`.
- Redaction validation must enforce these value allowlists, not only key shapes: every `reason_codes[*]` value must be in `SAFE_REASON_CODES`, every `reason_count` must equal `len(reason_codes)`, every key ending in `_unavailable_reason` at any nesting depth must be in its allowlist, and `app_server_inventory_failure_reason_code` must be in its allowlist.
- Allowed current-run unavailable reason values are `null`, `source-root-unavailable`, `installed-cache-root-unavailable`, `runtime-config-parse-failed`, `path-not-found`, `permission-denied`, `unavailable`, and `hash-unavailable`.
- `codex_executable_hash_unavailable_reason` must be reduced to one of those allowlisted values, usually `hash-unavailable`, before entering either the top-level runtime identity fields or `current_run_identity.runtime_identity`. Do not copy `str(OSError)` or any path-heavy exception text from `collect_codex_runtime_identity()`.

Allowed commit-safe runtime identity fields:

- `codex_version`
- `codex_executable_path`
- `codex_executable_sha256`
- `codex_executable_hash_unavailable_reason`
- `app_server_server_info`
- `app_server_protocol_capabilities`
- `app_server_parser_version`
- `app_server_response_schema_version`

Forbidden commit-safe fields and values:

- `app_server_transcript`
- `raw_transcript`
- `app_server_inventory_failure_reason`
- request or response bodies
- config TOML contents
- process listing contents
- local-only validator raw inputs
- token-like secrets
- email addresses
- fake success payloads for mutation phases not reached

## Implementation Sketch Authority

Code blocks in this plan are implementation sketches for a worker who has little project context. The authoritative requirements are the public function names, CLI shapes, schema fields, projection allowlists, test expectations, commit boundaries, and stop conditions. If a code block conflicts with live source or with the commit-safe projection contract, preserve the contract and adapt the implementation. In particular, never replace the explicit `axes`, `runtime_config`, or `diff_classification` projection helpers with direct copies of local-only objects.

## Task 0: Preflight And Current-State Re-Anchor

**Files:**

- The plan file itself is expected to exist before implementation.

- [ ] **Step 1: Verify branch and worktree**

Run:

```bash
git status --short --branch
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

Expected at plan creation base:

```text
## main...origin/main
1b5199fd062c8ef2b47722e79cc4bfd5f720e0e2
ea745d59687e5ecd6cf2d0f5181280cd12dbd711
```

If `HEAD` has moved, continue only after recording the new base in the implementation closeout.

- [ ] **Step 2: Create the implementation branch before editing source**

If still on `main`, create the implementation branch before any source edits:

```bash
git switch -c feature/turbo-mode-refresh-plan-04-commit-safe-evidence
```

Expected:

- branch is `feature/turbo-mode-refresh-plan-04-commit-safe-evidence`;
- the existing untracked Plan 04 file remains in the worktree;
- no source code edits exist yet.

If the branch already exists, switch to it only after verifying it points at the intended base or recording the divergence in the closeout. Do not implement Plan 04 directly on `main`.

- [ ] **Step 3: Preserve the untracked plan artifact deliberately**

Run:

```bash
git status --short docs/superpowers/plans/2026-05-06-turbo-mode-refresh-04-commit-safe-evidence.md
```

Expected at plan handoff:

```text
?? docs/superpowers/plans/2026-05-06-turbo-mode-refresh-04-commit-safe-evidence.md
```

Keep the plan artifact with the Plan 04 branch. It should be staged with the source implementation commit in its pre-completion-evidence state, then updated again in the separate evidence/docs commit after the completion-evidence section is appended.

- [ ] **Step 4: Run the generated-residue gate**

Run:

```bash
find plugins/turbo-mode/handoff/1.6.0 plugins/turbo-mode/ticket/1.4.0 \
  plugins/turbo-mode/tools/refresh \
  -name __pycache__ -o -name '*.pyc' -o -name .pytest_cache \
  -o -name .ruff_cache -o -name .mypy_cache -o -name .venv -o -name .DS_Store
```

Expected: prints nothing.

If residue appears, stop. Do not proceed until the operator approves moving residue to Trash.

## Task 1: Commit-Safe Summary Builder

**Files:**

- Create: `plugins/turbo-mode/tools/refresh/validation.py`
- Create: `plugins/turbo-mode/tools/refresh/commit_safe.py`
- Modify: `plugins/turbo-mode/tools/refresh/evidence.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py`

- [ ] **Step 1: Create shared validation/json helpers before `commit_safe.py` imports them**

Create `plugins/turbo-mode/tools/refresh/validation.py` with `load_json_object()` and `_json_safe()`, then update `evidence.py` to import `_json_safe` from `validation.py`.

This step must happen before `commit_safe.py` is implemented, because `commit_safe.py` imports `load_json_object`. Task 2 extends this same file with redaction and validator-projection helpers; it does not create `validation.py` from scratch.

- [ ] **Step 2: Write failing tests for non-mutating commit-safe payloads**

Create `plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py` with a local `empty_result()` fixture copied from `test_evidence.py`. Do not import `test_evidence.py`; the tests directory is not a `refresh.tests` package.

Required tests:

```python
from __future__ import annotations

import json
from pathlib import Path

from refresh.commit_safe import build_commit_safe_summary
from refresh.evidence import write_local_evidence
from refresh.models import (
    CoverageState,
    FilesystemState,
    PlanAxes,
    PreflightState,
    RuntimeConfigState,
    SelectedMutationMode,
    TerminalPlanStatus,
)
from refresh.planner import RefreshPaths, RefreshPlanResult


def empty_result(tmp_path: Path) -> RefreshPlanResult:
    paths = RefreshPaths(
        repo_root=tmp_path / "repo",
        codex_home=tmp_path / ".codex",
        marketplace_path=tmp_path / "repo/.agents/plugins/marketplace.json",
        config_path=tmp_path / ".codex/config.toml",
        local_only_root=tmp_path / ".codex/local-only/turbo-mode-refresh",
    )
    axes = PlanAxes(
        filesystem_state=FilesystemState.NO_DRIFT,
        coverage_state=CoverageState.NOT_APPLICABLE,
        runtime_config_state=RuntimeConfigState.UNCHECKED,
        preflight_state=PreflightState.PASSED,
        selected_mutation_mode=SelectedMutationMode.NONE,
    )
    return RefreshPlanResult(
        mode="dry-run",
        paths=paths,
        residue_issues=(),
        diffs=(),
        diff_classification=(),
        runtime_config=None,
        axes=axes,
        terminal_status=TerminalPlanStatus.FILESYSTEM_NO_DRIFT,
    )


def test_commit_safe_summary_omits_raw_transcript_and_records_omissions(
    tmp_path: Path,
) -> None:
    result = empty_result(tmp_path)
    local_summary = write_local_evidence(result, run_id="run-1")

    payload = build_commit_safe_summary(
        result,
        run_id="run-1",
        local_summary_path=local_summary,
        repo_head="abc123",
        repo_tree="def456",
        tool_path=Path("plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"),
        tool_sha256="tool-sha",
        dirty_state={
            "status": "clean-relevant-paths",
            "relevant_paths_checked": [],
            "post_commit_binding": False,
        },
        metadata_validation_summary_sha256=None,
        redaction_validation_summary_sha256=None,
    )

    assert payload["schema_version"] == "turbo-mode-refresh-commit-safe-plan-04"
    assert payload["source_local_summary_schema_version"] == "turbo-mode-refresh-plan-03"
    assert payload["local_only_summary_sha256"]
    assert payload["terminal_plan_status"] == "filesystem-no-drift"
    assert payload["final_status"] == "filesystem-no-drift"
    assert payload["omission_reasons"]["raw_app_server_transcript"] == "local-only"
    assert payload["omission_reasons"]["process_gate"] == "outside-plan-04"
    assert "app_server_transcript" not in json.dumps(payload)
```

Also add an inventory-backed test that proves:

- `app_server_request_methods` is copied from `result.app_server_inventory.request_methods`;
- `app_server_inventory_summary_sha256` is present and hashes the stable replay-identity projection, not the raw transcript SHA;
- `codex_version`, parser version, and accepted schema version are present;
- raw transcript bodies are absent.

Also add requested-failed inventory tests that prove:

- a local-only `app_server_inventory_failure_reason` containing a response-shaped object does not appear in the commit-safe summary;
- a local-only failure reason containing a token-shaped value does not appear in the commit-safe summary and is rejected if any sensitive substring reaches the payload;
- a local-only failure reason containing path-heavy payloads is reduced to an allowed `app_server_inventory_failure_reason_code`;
- `app_server_inventory_failure_reason_code` is one of the allowlisted values and no raw `app_server_inventory_failure_reason` key exists in the commit-safe payload.
- the same malicious failure text does not appear anywhere in `json.dumps(payload, sort_keys=True)`, including under nested `axes`, `runtime_config`, or `diff_classification` containers.

Also add commit-safe nested projection tests that prove:

- `axes` contains only `filesystem_state`, `coverage_state`, `runtime_config_state`, `preflight_state`, `selected_mutation_mode`, `reason_codes`, and `reason_count`;
- `axes` never contains `reasons`;
- app-server and runtime preflight strings in local-only `axes.reasons` are mapped to allowlisted `reason_codes`;
- unknown local-only `axes.reasons` values map to `unknown-reason` and the raw values are absent from `json.dumps(payload, sort_keys=True)`;
- `runtime_config` contains only `state`, `marketplace_state`, `plugin_hooks_state`, `plugin_enablement_state`, `reason_codes`, and `reason_count`;
- `runtime_config` never contains `reasons`;
- local-only `runtime_config.reasons` values are mapped to allowlisted `reason_codes` and raw strings are absent from the payload;
- `diff_classification[*]` contains only `canonical_path`, `mutation_mode`, `coverage_status`, `outcome`, `reason_codes`, and `smoke`;
- `diff_classification[*]` never contains `reasons`;
- local-only `diff_classification[*].reasons` values are mapped to allowlisted `reason_codes`.
- every emitted `reason_codes[*]` value is in `SAFE_REASON_CODES`;
- every emitted `reason_count` equals `len(reason_codes)`.

Also add dirty-state tests that prove:

- a dirty file under `plugins/turbo-mode/tools/refresh/` fails before summary write;
- a dirty `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py` fails before summary write;
- a dirty `plugins/turbo-mode/tools/refresh_validate_run_metadata.py` fails before summary write;
- a dirty `plugins/turbo-mode/tools/refresh_validate_redaction.py` fails before summary write;
- a dirty `.agents/plugins/marketplace.json` fails before summary write;
- an unrelated dirty file does not fail the relevant dirty-state gate;
- an existing local-only run cannot be reused for a new commit-safe summary in Plan 04; post-commit binding is outside this plan and must remain an explicit future feature, not an accidental fallback.

- [ ] **Step 3: Run the failing tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py -q
```

Expected: fail because `refresh.commit_safe` does not exist.

- [ ] **Step 4: Implement `commit_safe.py`**

Create `plugins/turbo-mode/tools/refresh/commit_safe.py` with:

The interfaces, field names, allowlists, and invariants in this block are authoritative. The function bodies are implementation sketches: do not copy them verbatim if the surrounding source has drifted, and do not replace the explicit commit-safe projection helpers with direct copies of local-only objects.

```python
from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from .app_server_inventory import collect_readonly_runtime_inventory
from .evidence import SCHEMA_VERSION as LOCAL_ONLY_SCHEMA_VERSION
from .manifests import build_manifest
from .models import RefreshError
from .planner import (
    RefreshPlanResult,
    build_plugin_specs,
    build_paths,
    read_runtime_config_state,
)
from .validation import load_json_object

COMMIT_SAFE_SCHEMA_VERSION = "turbo-mode-refresh-commit-safe-plan-04"
DIRTY_STATE_POLICY = "fail-relevant-dirty-state"
RELEVANT_DIRTY_PATHS = (
    "plugins/turbo-mode/tools/refresh",
    "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py",
    "plugins/turbo-mode/tools/refresh_validate_run_metadata.py",
    "plugins/turbo-mode/tools/refresh_validate_redaction.py",
    ".agents/plugins/marketplace.json",
)


def sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def sha256_payload(payload: Any) -> str:
    data = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(data).hexdigest()


def sha256_path_metadata(path: Path) -> str | None:
    if not path.exists():
        return None
    stat = path.stat()
    payload = {
        "path": path.as_posix(),
        "file_type": "file" if path.is_file() else "other",
        "mode": stat.st_mode,
        "size": stat.st_size,
        "sha256": sha256_file(path) if path.is_file() else None,
    }
    return sha256_payload(payload)


def digest_or_unavailable(payload_factory: Callable[[], Any]) -> tuple[str | None, str | None]:
    try:
        return sha256_payload(_json_safe(payload_factory())), None
    except (OSError, ValueError, RefreshError) as exc:
        return None, current_identity_unavailable_reason(exc)


def file_metadata_digest_or_unavailable(path: Path) -> tuple[str | None, str | None]:
    try:
        digest = sha256_path_metadata(path)
        if digest is None:
            return None, "path-not-found"
        return digest, None
    except (OSError, ValueError) as exc:
        return None, current_identity_unavailable_reason(exc)


def current_identity_unavailable_reason(exc: BaseException) -> str:
    text = str(exc)
    if "missing source root" in text:
        return "source-root-unavailable"
    if "missing cache root" in text:
        return "installed-cache-root-unavailable"
    if "parse config" in text:
        return "runtime-config-parse-failed"
    if isinstance(exc, FileNotFoundError):
        return "path-not-found"
    if isinstance(exc, PermissionError):
        return "permission-denied"
    return "unavailable"


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {key: _json_safe(item) for key, item in asdict(value).items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value


def ensure_relevant_worktree_clean(repo_root: Path) -> dict[str, Any]:
    dirty_paths = relevant_dirty_paths(repo_root)
    if dirty_paths:
        raise ValueError(f"prepare commit-safe summary failed: relevant dirty state. Got: {dirty_paths!r:.100}")
    return {
        "status": "clean-relevant-paths",
        "relevant_paths_checked": sorted(RELEVANT_DIRTY_PATHS),
        "post_commit_binding": False,
    }


def relevant_dirty_paths(repo_root: Path) -> list[str]:
    completed = subprocess.run(
        ["git", "status", "--porcelain", "--", *RELEVANT_DIRTY_PATHS],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    return [
        line[3:]
        for line in completed.stdout.splitlines()
        if line.strip()
    ]


def build_commit_safe_summary(
    result: RefreshPlanResult,
    *,
    run_id: str,
    local_summary_path: Path,
    repo_head: str,
    repo_tree: str,
    tool_path: Path,
    tool_sha256: str,
    dirty_state: dict[str, Any],
    metadata_validation_summary_sha256: str | None,
    redaction_validation_summary_sha256: str | None,
) -> dict[str, Any]:
    local_summary = load_json_object(local_summary_path)
    current_run_identity = build_current_run_identity(
        result=result,
        run_id=run_id,
        local_summary=local_summary,
    )
    projected = project_commit_safe_fields_from_local_summary(local_summary)
    return {
        "schema_version": COMMIT_SAFE_SCHEMA_VERSION,
        "run_id": run_id,
        "mode": result.mode,
        "source_local_summary_schema_version": LOCAL_ONLY_SCHEMA_VERSION,
        "repo_head": repo_head,
        "repo_tree": repo_tree,
        "tool_path": tool_path.as_posix(),
        "tool_sha256": tool_sha256,
        "dirty_state_policy": DIRTY_STATE_POLICY,
        "dirty_state": dirty_state,
        "current_run_identity": current_run_identity,
        "local_only_evidence_root": str(result.paths.local_only_root / run_id),
        "local_only_summary_sha256": sha256_file(local_summary_path),
        **projected,
        "metadata_validation_summary_sha256": metadata_validation_summary_sha256,
        "redaction_validation_summary_sha256": redaction_validation_summary_sha256,
        "omission_reasons": _commit_safe_omission_reasons(result),
    }


def build_current_run_identity(
    *,
    result: RefreshPlanResult,
    run_id: str,
    local_summary: dict[str, Any],
) -> dict[str, Any]:
    return build_current_run_identity_from_paths(
        repo_root=result.paths.repo_root,
        codex_home=result.paths.codex_home,
        run_id=run_id,
        local_summary=local_summary,
    )


def build_current_run_identity_from_paths(
    *,
    repo_root: Path,
    codex_home: Path,
    run_id: str,
    local_summary: dict[str, Any],
) -> dict[str, Any]:
    paths = build_paths(repo_root=repo_root, codex_home=codex_home)
    specs = build_plugin_specs(
        repo_root=paths.repo_root,
        codex_home=paths.codex_home,
    )
    source_manifest_sha256, source_manifest_reason = digest_or_unavailable(
        lambda: [build_manifest(spec, root_kind="source") for spec in specs]
    )
    cache_manifest_sha256, cache_manifest_reason = digest_or_unavailable(
        lambda: [build_manifest(spec, root_kind="cache") for spec in specs]
    )
    marketplace_sha256, marketplace_reason = file_metadata_digest_or_unavailable(
        paths.marketplace_path
    )
    config_sha256, config_reason = file_metadata_digest_or_unavailable(
        paths.config_path
    )
    runtime_config_sha256, runtime_config_reason = digest_or_unavailable(
        lambda: read_runtime_config_state(
            paths.config_path,
            expected_marketplace_source=paths.repo_root,
        )
    )
    local_inventory = local_summary.get("app_server_inventory") or {}
    runtime_identity = None
    if local_summary.get("app_server_inventory_status") == "collected":
        live_inventory, _live_transcript = collect_readonly_runtime_inventory(paths)
        inventory_summary = _inventory_replay_identity(live_inventory)
        runtime_identity = _runtime_identity_projection(live_inventory.identity)
    else:
        inventory_summary = _inventory_replay_identity_from_local_summary(local_inventory)
    return {
        "local_summary_schema_version": local_summary.get("schema_version"),
        "local_summary_run_id": local_summary.get("run_id"),
        "local_summary_mode": local_summary.get("mode"),
        "source_manifest_sha256": source_manifest_sha256,
        "source_manifest_unavailable_reason": source_manifest_reason,
        "installed_cache_manifest_sha256": cache_manifest_sha256,
        "installed_cache_manifest_unavailable_reason": cache_manifest_reason,
        "repo_marketplace_sha256": marketplace_sha256,
        "repo_marketplace_unavailable_reason": marketplace_reason,
        "local_config_metadata_sha256": config_sha256,
        "local_config_metadata_unavailable_reason": config_reason,
        "runtime_config_projection_sha256": runtime_config_sha256,
        "runtime_config_projection_unavailable_reason": runtime_config_reason,
        "app_server_inventory_summary_sha256": (
            sha256_payload(inventory_summary) if inventory_summary is not None else None
        ),
        "app_server_inventory_freshness": _app_server_inventory_freshness(
            status=local_summary["app_server_inventory_status"],
            inventory_summary=inventory_summary,
        ),
        "runtime_identity": runtime_identity,
        "runtime_identity_freshness": _runtime_identity_freshness(
            status=local_summary["app_server_inventory_status"],
            runtime_identity=runtime_identity,
        ),
    }


def _runtime_identity_projection(identity: Any) -> dict[str, Any]:
    return {
        "codex_version": identity.codex_version,
        "codex_executable_path": identity.executable_path,
        "codex_executable_sha256": identity.executable_sha256,
        "codex_executable_hash_unavailable_reason": _runtime_hash_unavailable_reason_code(
            identity.executable_hash_unavailable_reason
        ),
        "app_server_server_info": _server_info_projection(identity.server_info),
        "app_server_protocol_capabilities": _protocol_capabilities_projection(
            identity.initialize_capabilities
        ),
        "app_server_parser_version": identity.parser_version,
        "app_server_response_schema_version": identity.accepted_response_schema_version,
    }


def _server_info_projection(server_info: object) -> dict[str, str | None]:
    if not isinstance(server_info, dict):
        return {"name": None, "version": None}
    return {
        "name": _optional_string(server_info.get("name")),
        "version": _optional_string(server_info.get("version")),
    }


def _protocol_capabilities_projection(
    capabilities: object,
) -> dict[str, bool | None]:
    if not isinstance(capabilities, dict):
        return {"experimentalApi": None}
    experimental_api = capabilities.get("experimentalApi")
    return {
        "experimentalApi": (
            experimental_api if isinstance(experimental_api, bool) else None
        ),
    }


def _optional_string(value: object) -> str | None:
    return value if isinstance(value, str) else None


def _runtime_hash_unavailable_reason_code(raw_reason: object) -> str | None:
    if raw_reason is None:
        return None
    return "hash-unavailable"


def _runtime_identity_freshness(
    *,
    status: str,
    runtime_identity: dict[str, Any] | None,
) -> str:
    if status == "collected" and runtime_identity is not None:
        return "recomputed-readonly-inventory"
    if status == "not-requested":
        return "not-requested"
    if status == "requested-blocked":
        return "blocked-runtime-config"
    return "failure-code-only"


def _inventory_replay_identity(inventory: Any) -> dict[str, Any] | None:
    if inventory is None:
        return None
    return {
        "state": inventory.state,
        "plugin_read_sources": inventory.plugin_read_sources,
        "plugin_list": list(inventory.plugin_list),
        "skills": list(inventory.skills),
        "ticket_hook": inventory.ticket_hook,
        "handoff_hooks": list(inventory.handoff_hooks),
        "request_methods": list(inventory.request_methods),
        "reasons": list(inventory.reasons),
    }


def _commit_safe_omission_reasons(result: RefreshPlanResult) -> dict[str, str]:
    return {
        "raw_app_server_transcript": "local-only",
        "process_gate": "outside-plan-04",
        "post_refresh_cache_manifest": "outside-plan-04",
        "pre_refresh_config_sha256": "outside-plan-04",
        "post_refresh_config_sha256": "outside-plan-04",
        "smoke_summary": "outside-plan-04",
        "rollback_or_restore_status": "outside-plan-04",
        "exclusivity_status": "outside-plan-04",
    }


SAFE_REASON_CODES = {
    "source-root-missing",
    "cache-root-missing",
    "generated-residue-present",
    "manifest-build-failed",
    "runtime-config-parse-failed",
    "config-marketplaces-section-missing",
    "config-marketplace-missing",
    "config-marketplace-source-type-mismatch",
    "config-marketplace-source-not-string",
    "config-marketplace-source-mismatch",
    "config-plugin-hooks-absent",
    "config-features-section-malformed",
    "config-plugin-hooks-disabled",
    "config-plugin-hooks-malformed",
    "config-plugins-section-missing",
    "config-plugin-enabled-missing",
    "config-plugin-enabled-disabled",
    "config-plugin-enabled-malformed",
    "added-executable-path",
    "added-non-doc-path",
    "executable-doc-surface",
    "command-shape-changed",
    "projection-parser-warning",
    "semantic-policy-trigger",
    "coverage-gap-path",
    "guarded-only-path",
    "fast-safe-path",
    "unmatched-path",
    "runtime-config-preflight-unavailable",
    "app-server-stdout-closed",
    "app-server-returned-error",
    "app-server-timeout",
    "app-server-contract-invalid",
    "app-server-unavailable",
    "refresh-error",
    "unknown-reason",
}


def _commit_safe_axes(axes: dict[str, Any]) -> dict[str, Any]:
    reasons = list(axes.get("reasons") or [])
    return {
        "filesystem_state": axes.get("filesystem_state"),
        "coverage_state": axes.get("coverage_state"),
        "runtime_config_state": axes.get("runtime_config_state"),
        "preflight_state": axes.get("preflight_state"),
        "selected_mutation_mode": axes.get("selected_mutation_mode"),
        "reason_codes": [_reason_code(reason) for reason in reasons],
        "reason_count": len(reasons),
    }


def _commit_safe_runtime_config(config: dict[str, Any] | None) -> dict[str, Any] | None:
    if config is None:
        return None
    reasons = list(config.get("reasons") or [])
    return {
        "state": config.get("state"),
        "marketplace_state": config.get("marketplace_state"),
        "plugin_hooks_state": config.get("plugin_hooks_state"),
        "plugin_enablement_state": dict(config.get("plugin_enablement_state") or {}),
        "reason_codes": [_reason_code(reason) for reason in reasons],
        "reason_count": len(reasons),
    }


def _commit_safe_diff_classification(items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    projected = []
    for item in items:
        reasons = list(item.get("reasons") or [])
        projected.append(
            {
                "canonical_path": item.get("canonical_path"),
                "mutation_mode": item.get("mutation_mode"),
                "coverage_status": item.get("coverage_status"),
                "outcome": item.get("outcome"),
                "reason_codes": [_reason_code(reason) for reason in reasons],
                "smoke": list(item.get("smoke") or []),
            }
        )
    return projected


def _reason_code(reason: object) -> str:
    text = str(reason)
    exact = {
        "generated residue present": "generated-residue-present",
        "runtime config preflight unavailable": "runtime-config-preflight-unavailable",
        "marketplaces section missing": "config-marketplaces-section-missing",
        "turbo-mode marketplace missing": "config-marketplace-missing",
        "turbo-mode marketplace source_type is not local": "config-marketplace-source-type-mismatch",
        "turbo-mode marketplace source is not a string": "config-marketplace-source-not-string",
        "turbo-mode marketplace source mismatch": "config-marketplace-source-mismatch",
        "features.plugin_hooks absent": "config-plugin-hooks-absent",
        "features section is not an object": "config-features-section-malformed",
        "features.plugin_hooks disabled": "config-plugin-hooks-disabled",
        "features.plugin_hooks is not boolean": "config-plugin-hooks-malformed",
        "plugins section missing": "config-plugins-section-missing",
        "added-executable-path": "added-executable-path",
        "added-non-doc-path": "added-non-doc-path",
        "executable-doc-surface": "executable-doc-surface",
        "command-shape-changed": "command-shape-changed",
        "projection-parser-warning": "projection-parser-warning",
        "semantic-policy-trigger": "semantic-policy-trigger",
        "coverage-gap-path": "coverage-gap-path",
        "guarded-only-path": "guarded-only-path",
        "fast-safe-path": "fast-safe-path",
        "unmatched-path": "unmatched-path",
    }
    if text in exact:
        return exact[text]
    if text.startswith("missing source root:"):
        return "source-root-missing"
    if text.startswith("missing cache root:"):
        return "cache-root-missing"
    if "parse config failed" in text:
        return "runtime-config-parse-failed"
    if "build manifest" in text:
        return "manifest-build-failed"
    if ".enabled missing" in text:
        return "config-plugin-enabled-missing"
    if ".enabled disabled" in text:
        return "config-plugin-enabled-disabled"
    if ".enabled is not boolean" in text:
        return "config-plugin-enabled-malformed"
    mapped = _commit_safe_inventory_failure_reason_code(
        status="requested-failed",
        raw_reason=text,
    )
    if mapped is not None and mapped != "unknown-inventory-failure":
        return mapped
    return "unknown-reason"


def project_commit_safe_fields_from_local_summary(
    local_summary: dict[str, Any],
) -> dict[str, Any]:
    """Project every commit-safe state field from local-only evidence."""
    inventory = local_summary.get("app_server_inventory") or {}
    identity = inventory.get("identity") or {}
    inventory_summary = _inventory_replay_identity_from_local_summary(inventory)
    return {
        "terminal_plan_status": local_summary["terminal_plan_status"],
        "final_status": local_summary["terminal_plan_status"],
        "axes": _commit_safe_axes(local_summary["axes"]),
        "diff_classification": _commit_safe_diff_classification(
            list(local_summary["diff_classification"])
        ),
        "runtime_config": _commit_safe_runtime_config(local_summary.get("runtime_config")),
        "app_server_inventory_status": local_summary["app_server_inventory_status"],
        "app_server_inventory_failure_reason_code": _commit_safe_inventory_failure_reason_code(
            status=local_summary["app_server_inventory_status"],
            raw_reason=local_summary.get("app_server_inventory_failure_reason"),
        ),
        "app_server_inventory_summary_sha256": (
            sha256_payload(inventory_summary) if inventory_summary is not None else None
        ),
        "app_server_request_methods": list(inventory.get("request_methods") or []),
        "codex_version": identity.get("codex_version"),
        "codex_executable_path": identity.get("executable_path"),
        "codex_executable_sha256": identity.get("executable_sha256"),
        "codex_executable_hash_unavailable_reason": _runtime_hash_unavailable_reason_code(
            identity.get("executable_hash_unavailable_reason")
        ),
        "app_server_server_info": _server_info_projection(identity.get("server_info")),
        "app_server_protocol_capabilities": _protocol_capabilities_projection(
            identity.get("initialize_capabilities")
        ),
        "app_server_parser_version": identity.get("parser_version"),
        "app_server_response_schema_version": identity.get(
            "accepted_response_schema_version"
        ),
    }


def _commit_safe_inventory_failure_reason_code(
    *,
    status: str,
    raw_reason: object,
) -> str | None:
    if status in {"not-requested", "collected"}:
        return None
    if raw_reason is None:
        return "unknown-inventory-failure"
    text = str(raw_reason)
    if text == "runtime config preflight unavailable":
        return "runtime-config-preflight-unavailable"
    if "stdout closed before response" in text:
        return "app-server-stdout-closed"
    if "response returned error" in text:
        return "app-server-returned-error"
    if "timed out" in text or "timeout" in text:
        return "app-server-timeout"
    if "inventory contract" in text:
        return "app-server-contract-invalid"
    if "app-server" in text or "app server" in text:
        return "app-server-unavailable"
    if "refresh" in text:
        return "refresh-error"
    return "unknown-inventory-failure"


def _app_server_inventory_freshness(
    *,
    status: str,
    inventory_summary: dict[str, Any] | None,
) -> str:
    if status == "collected" and inventory_summary is not None:
        return "recomputed-readonly-inventory"
    if status == "not-requested":
        return "not-requested"
    if status == "requested-blocked":
        return "blocked-runtime-config"
    return "failure-code-only"


def _inventory_replay_identity_from_local_summary(
    inventory: dict[str, Any],
) -> dict[str, Any] | None:
    if not inventory:
        return None
    return {
        "state": inventory.get("state"),
        "plugin_read_sources": inventory.get("plugin_read_sources"),
        "plugin_list": list(inventory.get("plugin_list") or []),
        "skills": list(inventory.get("skills") or []),
        "ticket_hook": inventory.get("ticket_hook"),
        "handoff_hooks": list(inventory.get("handoff_hooks") or []),
        "request_methods": list(inventory.get("request_methods") or []),
        "reasons": list(inventory.get("reasons") or []),
    }
```

The exact projection helper may differ from the sketch above, but it must be the single path used by both the builder and metadata validator.
If `source_manifest_sha256`, `installed_cache_manifest_sha256`, `repo_marketplace_sha256`, `local_config_metadata_sha256`, or `runtime_config_projection_sha256` cannot be recomputed because an input is missing, unreadable, or unparsable, the implementation must set the corresponding digest to `None`, set the matching `*_unavailable_reason` to an allowlisted reason code, and make the metadata validator recompute the same state from current inputs. It must not copy exception text into commit-safe evidence.

- [ ] **Step 5: Run Task 1 tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py -q
```

Expected: pass.

## Task 2: Redaction And Metadata Validation Helpers

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/validation.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_validation.py`

- [ ] **Step 1: Write failing redaction tests**

Create `plugins/turbo-mode/tools/refresh/tests/test_validation.py` with tests for:

```python
from __future__ import annotations

import pytest

from refresh.validation import (
    assert_commit_safe_payload,
    projected_summary_for_validator_digest,
)


def test_commit_safe_redaction_rejects_raw_transcript_key() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "app_server_transcript": [{"body": {"id": 0}}],
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_unknown_raw_payload_shape() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "debug_payload": [{"jsonrpc": "2.0"}],
    }

    with pytest.raises(ValueError, match="unknown key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_token_like_values() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "codex_version": "ghp_abcdefghijklmnopqrstuvwxyz1234567890",
    }

    with pytest.raises(ValueError, match="sensitive value"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_axes_reasons_bypass() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "axes": {
            "filesystem_state": "drift",
            "coverage_state": "coverage-gap",
            "runtime_config_state": "aligned",
            "preflight_state": "blocked",
            "selected_mutation_mode": "none",
            "reasons": ["response returned error: ghp_abcdefghijklmnopqrstuvwxyz1234567890"],
        },
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_unknown_reason_code_value() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "axes": {
            "filesystem_state": "drift",
            "coverage_state": "coverage-gap",
            "runtime_config_state": "aligned",
            "preflight_state": "blocked",
            "selected_mutation_mode": "none",
            "reason_codes": ["/Users/jp/.codex/raw/path/from/exception"],
            "reason_count": 1,
        },
    }

    with pytest.raises(ValueError, match="invalid reason code"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_reason_count_mismatch() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "axes": {
            "filesystem_state": "drift",
            "coverage_state": "coverage-gap",
            "runtime_config_state": "aligned",
            "preflight_state": "blocked",
            "selected_mutation_mode": "none",
            "reason_codes": ["app-server-returned-error"],
            "reason_count": 2,
        },
    }

    with pytest.raises(ValueError, match="reason count mismatch"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_invalid_failure_reason_code() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "app_server_inventory_failure_reason_code": "/private/tmp/raw-failure",
    }

    with pytest.raises(ValueError, match="invalid inventory failure reason code"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_invalid_unavailable_reason() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "current_run_identity": {
            "source_manifest_sha256": None,
            "source_manifest_unavailable_reason": "/private/tmp/raw-error",
        },
    }

    with pytest.raises(ValueError, match="invalid unavailable reason"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_top_level_executable_hash_unavailable_reason() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "codex_executable_hash_unavailable_reason": "[Errno 13] Permission denied: '/Users/jp/.codex/bin/codex'",
    }

    with pytest.raises(ValueError, match="invalid unavailable reason"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_nested_executable_hash_unavailable_reason() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "current_run_identity": {
            "runtime_identity": {
                "codex_executable_hash_unavailable_reason": "[Errno 13] Permission denied: '/Users/jp/.codex/bin/codex'",
            },
        },
    }

    with pytest.raises(ValueError, match="invalid unavailable reason"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_current_run_identity_unknown_key() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "current_run_identity": {
            "local_summary_schema_version": "turbo-mode-refresh-plan-03",
            "transcript_status_summary": {"response": {"body": "raw app-server payload"}},
        },
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_dirty_state_hidden_config_payload() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "dirty_state": {
            "status": "clean-relevant-paths",
            "relevant_paths_checked": ["plugins/turbo-mode/tools/refresh"],
            "post_commit_binding": False,
            "config_shadow": {"token": "not-allowed-even-without-token-shape"},
        },
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_server_info_extra_payload() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "app_server_server_info": {
            "name": "codex-app-server",
            "version": "0.test",
            "response_status": {"id": 0, "result": {"body": "raw"}},
        },
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_capabilities_extra_payload() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "app_server_protocol_capabilities": {
            "experimentalApi": True,
            "workspaceRoots": ["/Users/jp/.codex/raw"],
        },
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_commit_safe_redaction_rejects_omission_reason_extra_key() -> None:
    payload = {
        "schema_version": "turbo-mode-refresh-commit-safe-plan-04",
        "run_id": "run-1",
        "omission_reasons": {
            "raw_app_server_transcript": "local-only",
            "config_contents": "local-only",
        },
    }

    with pytest.raises(ValueError, match="forbidden key"):
        assert_commit_safe_payload(payload)


def test_validator_projection_nulls_validator_digests() -> None:
    payload = {
        "metadata_validation_summary_sha256": "abc",
        "redaction_validation_summary_sha256": "def",
        "run_id": "run-1",
    }

    projected = projected_summary_for_validator_digest(payload)

    assert projected["metadata_validation_summary_sha256"] is None
    assert projected["redaction_validation_summary_sha256"] is None
    assert projected["run_id"] == "run-1"
```

- [ ] **Step 2: Implement validation helpers**

Extend `plugins/turbo-mode/tools/refresh/validation.py` with:

```python
from __future__ import annotations

import copy
import json
import re
from dataclasses import asdict, is_dataclass
from enum import Enum
from pathlib import Path
from typing import Any

COMMIT_SAFE_TOP_LEVEL_KEYS = {
    "schema_version",
    "run_id",
    "mode",
    "source_local_summary_schema_version",
    "repo_head",
    "repo_tree",
    "tool_path",
    "tool_sha256",
    "dirty_state_policy",
    "dirty_state",
    "current_run_identity",
    "local_only_evidence_root",
    "local_only_summary_sha256",
    "terminal_plan_status",
    "final_status",
    "axes",
    "diff_classification",
    "runtime_config",
    "app_server_inventory_status",
    "app_server_inventory_failure_reason_code",
    "app_server_inventory_summary_sha256",
    "app_server_request_methods",
    "codex_version",
    "codex_executable_path",
    "codex_executable_sha256",
    "codex_executable_hash_unavailable_reason",
    "app_server_server_info",
    "app_server_protocol_capabilities",
    "app_server_parser_version",
    "app_server_response_schema_version",
    "metadata_validation_summary_sha256",
    "redaction_validation_summary_sha256",
    "omission_reasons",
}

NESTED_ALLOWED_KEYS = {
    "dirty_state": {
        "status",
        "relevant_paths_checked",
        "post_commit_binding",
    },
    "current_run_identity": {
        "local_summary_schema_version",
        "local_summary_run_id",
        "local_summary_mode",
        "source_manifest_sha256",
        "source_manifest_unavailable_reason",
        "installed_cache_manifest_sha256",
        "installed_cache_manifest_unavailable_reason",
        "repo_marketplace_sha256",
        "repo_marketplace_unavailable_reason",
        "local_config_metadata_sha256",
        "local_config_metadata_unavailable_reason",
        "runtime_config_projection_sha256",
        "runtime_config_projection_unavailable_reason",
        "app_server_inventory_summary_sha256",
        "app_server_inventory_freshness",
        "runtime_identity",
        "runtime_identity_freshness",
    },
    "runtime_identity": {
        "codex_version",
        "codex_executable_path",
        "codex_executable_sha256",
        "codex_executable_hash_unavailable_reason",
        "app_server_server_info",
        "app_server_protocol_capabilities",
        "app_server_parser_version",
        "app_server_response_schema_version",
    },
    "app_server_server_info": {
        "name",
        "version",
    },
    "app_server_protocol_capabilities": {
        "experimentalApi",
    },
    "axes": {
        "filesystem_state",
        "coverage_state",
        "runtime_config_state",
        "preflight_state",
        "selected_mutation_mode",
        "reason_codes",
        "reason_count",
    },
    "runtime_config": {
        "state",
        "marketplace_state",
        "plugin_hooks_state",
        "plugin_enablement_state",
        "reason_codes",
        "reason_count",
    },
    "runtime_config_plugin_enablement_state": {
        "handoff@turbo-mode",
        "ticket@turbo-mode",
    },
    "diff_classification_item": {
        "canonical_path",
        "mutation_mode",
        "coverage_status",
        "outcome",
        "reason_codes",
        "smoke",
    },
    "omission_reasons": {
        "raw_app_server_transcript",
        "process_gate",
        "post_refresh_cache_manifest",
        "pre_refresh_config_sha256",
        "post_refresh_config_sha256",
        "smoke_summary",
        "rollback_or_restore_status",
        "exclusivity_status",
    },
}

ALLOWED_PLUGIN_ENABLEMENT_VALUES = {
    "enabled",
    "disabled",
    "missing",
    "malformed",
}

ALLOWED_OMISSION_REASON_VALUES = {
    "local-only",
    "outside-plan-04",
}

SAFE_REASON_CODES = {
    "source-root-missing",
    "cache-root-missing",
    "generated-residue-present",
    "manifest-build-failed",
    "runtime-config-parse-failed",
    "config-marketplaces-section-missing",
    "config-marketplace-missing",
    "config-marketplace-source-type-mismatch",
    "config-marketplace-source-not-string",
    "config-marketplace-source-mismatch",
    "config-plugin-hooks-absent",
    "config-features-section-malformed",
    "config-plugin-hooks-disabled",
    "config-plugin-hooks-malformed",
    "config-plugins-section-missing",
    "config-plugin-enabled-missing",
    "config-plugin-enabled-disabled",
    "config-plugin-enabled-malformed",
    "added-executable-path",
    "added-non-doc-path",
    "executable-doc-surface",
    "command-shape-changed",
    "projection-parser-warning",
    "semantic-policy-trigger",
    "coverage-gap-path",
    "guarded-only-path",
    "fast-safe-path",
    "unmatched-path",
    "runtime-config-preflight-unavailable",
    "app-server-stdout-closed",
    "app-server-returned-error",
    "app-server-timeout",
    "app-server-contract-invalid",
    "app-server-unavailable",
    "refresh-error",
    "unknown-reason",
}

ALLOWED_INVENTORY_FAILURE_REASON_CODES = {
    None,
    "runtime-config-preflight-unavailable",
    "app-server-stdout-closed",
    "app-server-returned-error",
    "app-server-timeout",
    "app-server-contract-invalid",
    "app-server-unavailable",
    "refresh-error",
    "unknown-inventory-failure",
}

ALLOWED_UNAVAILABLE_REASONS = {
    None,
    "source-root-unavailable",
    "installed-cache-root-unavailable",
    "runtime-config-parse-failed",
    "path-not-found",
    "permission-denied",
    "unavailable",
    "hash-unavailable",
}

FORBIDDEN_KEYS = {
    "app_server_transcript",
    "app_server_inventory_failure_reason",
    "raw_transcript",
    "events",
    "requests",
    "responses",
    "body",
    "config",
    "process_listing",
    "raw_process_listing",
    "config_contents",
    "config_toml",
    "request_bodies",
    "response_bodies",
}

SENSITIVE_PATTERNS = (
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bxox[baprs]-[A-Za-z0-9-]{10,}\b"),
    re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}"),
)

CONFIG_OR_TRANSCRIPT_PATTERNS = (
    re.compile(r"(?i)\bjsonrpc\b"),
    re.compile(r"(?i)\brequest\b.*\bbody\b"),
    re.compile(r"(?i)\bresponse\b.*\bbody\b"),
    re.compile(r"(?m)^\s*\[plugins\]"),
    re.compile(r"(?m)^\s*(source|enabled|command)\s*="),
)

SAFE_SHORT_TEXT = re.compile(r"^[A-Za-z0-9._:@+ -]{0,120}$")
SAFE_RELATIVE_PATH = re.compile(r"^[A-Za-z0-9._@+/=-]{1,240}$")
SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")
BROAD_ABSOLUTE_PATH_PATTERN = re.compile(r"(^|\s)/(Users|private|tmp|var|etc|opt|home)/[^\s'\"]+")

EXPECTED_TOOL_PATH = "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"
EXPECTED_DIRTY_STATE_POLICY = "fail-relevant-dirty-state"
EXPECTED_SOURCE_LOCAL_SUMMARY_SCHEMA_VERSION = "turbo-mode-refresh-plan-03"
EXPECTED_COMMIT_SAFE_SCHEMA_VERSION = "turbo-mode-refresh-commit-safe-plan-04"
ALLOWED_DIRTY_RELEVANT_PATHS = {
    "plugins/turbo-mode/tools/refresh",
    "plugins/turbo-mode/tools/refresh_installed_turbo_mode.py",
    "plugins/turbo-mode/tools/refresh_validate_run_metadata.py",
    "plugins/turbo-mode/tools/refresh_validate_redaction.py",
    ".agents/plugins/marketplace.json",
}
ALLOWED_APP_SERVER_METHODS = {
    "initialize",
    "initialized",
    "plugin/read",
    "plugin/list",
    "skills/list",
    "hooks/list",
}


def load_json_object(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"load json object failed: top-level value is not an object. Got: {str(path)!r:.100}")
    return data


def assert_commit_safe_payload(payload: dict[str, Any]) -> None:
    forbidden_top_level = set(payload) & FORBIDDEN_KEYS
    if forbidden_top_level:
        raise ValueError(f"validate commit-safe payload failed: forbidden key. Got: {sorted(forbidden_top_level)!r:.100}")
    unknown_keys = set(payload) - COMMIT_SAFE_TOP_LEVEL_KEYS
    if unknown_keys:
        raise ValueError(f"validate commit-safe payload failed: unknown key. Got: {sorted(unknown_keys)!r:.100}")
    _assert_nested_commit_safe_shapes(payload)
    _assert_commit_safe_enum_values(payload)
    _walk_payload(payload, path="$", allow_local_only_paths=False)
    _assert_field_values(payload)


def assert_no_sensitive_values(payload: dict[str, Any]) -> None:
    _walk_payload(payload, path="$", allow_local_only_paths=True)


def projected_summary_for_validator_digest(payload: dict[str, Any]) -> dict[str, Any]:
    projected = copy.deepcopy(payload)
    projected["metadata_validation_summary_sha256"] = None
    projected["redaction_validation_summary_sha256"] = None
    return projected


def _assert_nested_commit_safe_shapes(payload: dict[str, Any]) -> None:
    dirty_state = payload.get("dirty_state")
    if isinstance(dirty_state, dict):
        _assert_allowed_keys("dirty_state", dirty_state, NESTED_ALLOWED_KEYS["dirty_state"])
    current_run_identity = payload.get("current_run_identity")
    if isinstance(current_run_identity, dict):
        _assert_allowed_keys(
            "current_run_identity",
            current_run_identity,
            NESTED_ALLOWED_KEYS["current_run_identity"],
        )
        _assert_runtime_identity(current_run_identity.get("runtime_identity"))
    _assert_server_info(payload.get("app_server_server_info"), name="app_server_server_info")
    _assert_protocol_capabilities(
        payload.get("app_server_protocol_capabilities"),
        name="app_server_protocol_capabilities",
    )
    axes = payload.get("axes")
    if isinstance(axes, dict):
        _assert_allowed_keys("axes", axes, NESTED_ALLOWED_KEYS["axes"])
    runtime_config = payload.get("runtime_config")
    if isinstance(runtime_config, dict):
        _assert_allowed_keys(
            "runtime_config",
            runtime_config,
            NESTED_ALLOWED_KEYS["runtime_config"],
        )
        plugin_enablement = runtime_config.get("plugin_enablement_state")
        if isinstance(plugin_enablement, dict):
            _assert_allowed_keys(
                "runtime_config.plugin_enablement_state",
                plugin_enablement,
                NESTED_ALLOWED_KEYS["runtime_config_plugin_enablement_state"],
            )
            invalid = [
                value
                for value in plugin_enablement.values()
                if value not in ALLOWED_PLUGIN_ENABLEMENT_VALUES
            ]
            if invalid:
                raise ValueError(f"validate commit-safe payload failed: invalid plugin enablement value. Got: {invalid!r:.100}")
    diff_classification = payload.get("diff_classification")
    if isinstance(diff_classification, list):
        for item in diff_classification:
            if not isinstance(item, dict):
                raise ValueError(f"validate commit-safe payload failed: diff classification item is not an object. Got: {item!r:.100}")
            _assert_allowed_keys(
                "diff_classification item",
                item,
                NESTED_ALLOWED_KEYS["diff_classification_item"],
            )
    omission_reasons = payload.get("omission_reasons")
    if isinstance(omission_reasons, dict):
        _assert_allowed_keys(
            "omission_reasons",
            omission_reasons,
            NESTED_ALLOWED_KEYS["omission_reasons"],
        )
        invalid = [
            value
            for value in omission_reasons.values()
            if value not in ALLOWED_OMISSION_REASON_VALUES
        ]
        if invalid:
            raise ValueError(f"validate commit-safe payload failed: invalid omission reason. Got: {invalid!r:.100}")


def _assert_runtime_identity(value: Any) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"validate commit-safe payload failed: runtime identity is not an object. Got: {value!r:.100}")
    _assert_allowed_keys("runtime_identity", value, NESTED_ALLOWED_KEYS["runtime_identity"])
    _assert_server_info(value.get("app_server_server_info"), name="runtime_identity.app_server_server_info")
    _assert_protocol_capabilities(
        value.get("app_server_protocol_capabilities"),
        name="runtime_identity.app_server_protocol_capabilities",
    )


def _assert_server_info(value: Any, *, name: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"validate commit-safe payload failed: server info is not an object. Got: {name!r:.100}")
    _assert_allowed_keys(name, value, NESTED_ALLOWED_KEYS["app_server_server_info"])


def _assert_protocol_capabilities(value: Any, *, name: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"validate commit-safe payload failed: protocol capabilities is not an object. Got: {name!r:.100}")
    _assert_allowed_keys(name, value, NESTED_ALLOWED_KEYS["app_server_protocol_capabilities"])


def _assert_field_values(payload: dict[str, Any]) -> None:
    _assert_equals("schema_version", payload.get("schema_version"), EXPECTED_COMMIT_SAFE_SCHEMA_VERSION)
    _assert_equals(
        "source_local_summary_schema_version",
        payload.get("source_local_summary_schema_version"),
        EXPECTED_SOURCE_LOCAL_SUMMARY_SCHEMA_VERSION,
    )
    _assert_equals("dirty_state_policy", payload.get("dirty_state_policy"), EXPECTED_DIRTY_STATE_POLICY)
    _assert_equals("tool_path", payload.get("tool_path"), EXPECTED_TOOL_PATH)
    _assert_local_only_evidence_root(payload.get("local_only_evidence_root"))
    _assert_dirty_state_values(payload.get("dirty_state"))
    _assert_server_info_values(payload.get("app_server_server_info"), path="app_server_server_info")
    _assert_protocol_capability_values(payload.get("app_server_protocol_capabilities"))
    _assert_runtime_identity_values(payload.get("current_run_identity"))
    _assert_request_methods(payload.get("app_server_request_methods"))
    _assert_diff_classification_values(payload.get("diff_classification"))


def _assert_equals(name: str, value: object, expected: object) -> None:
    if value != expected:
        raise ValueError(f"validate commit-safe payload failed: invalid {name}. Got: {value!r:.100}")


def _assert_local_only_evidence_root(value: object) -> None:
    if not isinstance(value, str):
        raise ValueError(f"validate commit-safe payload failed: local-only evidence root is not a string. Got: {value!r:.100}")
    path = Path(value)
    if not path.is_absolute() or "/local-only/turbo-mode-refresh/" not in value:
        raise ValueError(f"validate commit-safe payload failed: invalid local-only evidence root. Got: {value!r:.100}")
    if not SAFE_RUN_ID.fullmatch(path.name):
        raise ValueError(f"validate commit-safe payload failed: invalid run id in local-only evidence root. Got: {path.name!r:.100}")


def _assert_dirty_state_values(value: object) -> None:
    if not isinstance(value, dict):
        raise ValueError(f"validate commit-safe payload failed: dirty_state is not an object. Got: {value!r:.100}")
    if value.get("status") != "clean-relevant-paths":
        raise ValueError(f"validate commit-safe payload failed: invalid dirty state status. Got: {value.get('status')!r:.100}")
    if value.get("post_commit_binding") is not False:
        raise ValueError(f"validate commit-safe payload failed: invalid post_commit_binding. Got: {value.get('post_commit_binding')!r:.100}")
    paths = value.get("relevant_paths_checked")
    if not isinstance(paths, list) or not all(isinstance(item, str) for item in paths):
        raise ValueError(f"validate commit-safe payload failed: invalid dirty relevant paths. Got: {paths!r:.100}")
    unknown = set(paths) - ALLOWED_DIRTY_RELEVANT_PATHS
    if unknown:
        raise ValueError(f"validate commit-safe payload failed: invalid dirty relevant path. Got: {sorted(unknown)!r:.100}")


def _assert_runtime_identity_values(current_run_identity: object) -> None:
    if not isinstance(current_run_identity, dict):
        return
    runtime_identity = current_run_identity.get("runtime_identity")
    if runtime_identity is None:
        return
    if not isinstance(runtime_identity, dict):
        raise ValueError(f"validate commit-safe payload failed: runtime identity is not an object. Got: {runtime_identity!r:.100}")
    _assert_server_info_values(
        runtime_identity.get("app_server_server_info"),
        path="current_run_identity.runtime_identity.app_server_server_info",
    )
    _assert_protocol_capability_values(runtime_identity.get("app_server_protocol_capabilities"))
    executable = runtime_identity.get("codex_executable_path")
    if executable is not None and not _is_allowed_codex_executable_path(executable):
        raise ValueError(f"validate commit-safe payload failed: invalid codex executable path. Got: {executable!r:.100}")


def _assert_server_info_values(value: object, *, path: str) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"validate commit-safe payload failed: server info is not an object. Got: {path!r:.100}")
    for key in ("name", "version"):
        item = value.get(key)
        if item is not None and (not isinstance(item, str) or not SAFE_SHORT_TEXT.fullmatch(item) or "/" in item):
            raise ValueError(f"validate commit-safe payload failed: invalid server info value. Got: {path}.{key}={item!r:.100}")


def _assert_protocol_capability_values(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, dict):
        raise ValueError(f"validate commit-safe payload failed: protocol capabilities is not an object. Got: {value!r:.100}")
    experimental_api = value.get("experimentalApi")
    if experimental_api is not None and not isinstance(experimental_api, bool):
        raise ValueError(f"validate commit-safe payload failed: invalid experimentalApi capability. Got: {experimental_api!r:.100}")


def _assert_request_methods(value: object) -> None:
    if value is None:
        return
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise ValueError(f"validate commit-safe payload failed: request methods must be strings. Got: {value!r:.100}")
    unknown = set(value) - ALLOWED_APP_SERVER_METHODS
    if unknown:
        raise ValueError(f"validate commit-safe payload failed: invalid request method. Got: {sorted(unknown)!r:.100}")


def _assert_diff_classification_values(value: object) -> None:
    if not isinstance(value, list):
        return
    for item in value:
        if not isinstance(item, dict):
            continue
        canonical_path = item.get("canonical_path")
        if not isinstance(canonical_path, str) or canonical_path.startswith("/") or ".." in canonical_path.split("/") or not SAFE_RELATIVE_PATH.fullmatch(canonical_path):
            raise ValueError(f"validate commit-safe payload failed: invalid canonical path. Got: {canonical_path!r:.100}")


def _is_allowed_codex_executable_path(value: object) -> bool:
    if not isinstance(value, str):
        return False
    path = Path(value)
    return path.is_absolute() and path.name == "codex" and "\n" not in value


def _assert_commit_safe_enum_values(payload: dict[str, Any]) -> None:
    failure_code = payload.get("app_server_inventory_failure_reason_code")
    if failure_code not in ALLOWED_INVENTORY_FAILURE_REASON_CODES:
        raise ValueError(f"validate commit-safe payload failed: invalid inventory failure reason code. Got: {failure_code!r:.100}")
    for container_name in ("axes", "runtime_config"):
        container = payload.get(container_name)
        if isinstance(container, dict):
            _assert_reason_codes(container_name, container)
    diff_classification = payload.get("diff_classification")
    if isinstance(diff_classification, list):
        for index, item in enumerate(diff_classification):
            if isinstance(item, dict):
                _assert_reason_codes(f"diff_classification[{index}]", item)
    _assert_unavailable_reasons(payload, path="$")


def _assert_reason_codes(name: str, container: dict[str, Any]) -> None:
    codes = container.get("reason_codes")
    if codes is None:
        return
    if not isinstance(codes, list) or not all(isinstance(code, str) for code in codes):
        raise ValueError(f"validate commit-safe payload failed: reason_codes is not a string list. Got: {name!r:.100}")
    invalid = [code for code in codes if code not in SAFE_REASON_CODES]
    if invalid:
        raise ValueError(f"validate commit-safe payload failed: invalid reason code. Got: {invalid!r:.100}")
    if container.get("reason_count") != len(codes):
        raise ValueError(f"validate commit-safe payload failed: reason count mismatch. Got: {name!r:.100}")


def _assert_unavailable_reasons(value: Any, *, path: str) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            item_path = f"{path}.{key}"
            if key.endswith("_unavailable_reason") and item not in ALLOWED_UNAVAILABLE_REASONS:
                raise ValueError(f"validate commit-safe payload failed: invalid unavailable reason. Got: {item_path}={item!r:.100}")
            _assert_unavailable_reasons(item, path=item_path)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _assert_unavailable_reasons(item, path=f"{path}[{index}]")


def _assert_allowed_keys(name: str, value: dict[str, Any], allowed: set[str]) -> None:
    unknown = set(value) - allowed
    if unknown:
        raise ValueError(f"validate commit-safe payload failed: forbidden key. Got: {name}:{sorted(unknown)!r:.100}")


def _walk_payload(value: Any, *, path: str, allow_local_only_paths: bool) -> None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in FORBIDDEN_KEYS:
                raise ValueError(f"validate commit-safe payload failed: forbidden key. Got: {key!r:.100}")
            _walk_payload(item, path=f"{path}.{key}", allow_local_only_paths=allow_local_only_paths)
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _walk_payload(item, path=f"{path}[{index}]", allow_local_only_paths=allow_local_only_paths)
        return
    if isinstance(value, str):
        for pattern in SENSITIVE_PATTERNS:
            if pattern.search(value):
                raise ValueError(f"validate commit-safe payload failed: sensitive value. Got: {path!r:.100}")
        for pattern in CONFIG_OR_TRANSCRIPT_PATTERNS:
            if pattern.search(value):
                raise ValueError(f"validate commit-safe payload failed: config or transcript shaped value. Got: {path!r:.100}")
        if (
            not allow_local_only_paths
            and _looks_like_broad_absolute_path(value)
            and not _path_value_allowed(path, value)
        ):
            raise ValueError(f"validate commit-safe payload failed: broad absolute path value. Got: {path!r:.100}")


def _looks_like_broad_absolute_path(value: str) -> bool:
    return bool(BROAD_ABSOLUTE_PATH_PATTERN.search(value))


def _path_value_allowed(path: str, value: str) -> bool:
    if path in {"$.local_only_evidence_root"}:
        return "/local-only/turbo-mode-refresh/" in value
    if path.endswith(".codex_executable_path"):
        return _is_allowed_codex_executable_path(value)
    return False


def _json_safe(value: Any) -> Any:
    if value is None:
        return None
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, Path):
        return str(value)
    if is_dataclass(value):
        return {key: _json_safe(item) for key, item in asdict(value).items()}
    if isinstance(value, (tuple, list)):
        return [_json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _json_safe(item) for key, item in value.items()}
    return value
```

- [ ] **Step 3: Run validation tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_validation.py -q
```

Expected: pass.

## Task 3: Validator Scripts

**Files:**

- Create: `plugins/turbo-mode/tools/refresh_validate_run_metadata.py`
- Create: `plugins/turbo-mode/tools/refresh_validate_redaction.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_validation.py`

- [ ] **Step 1: Add tests for validator script behavior**

Extend `test_validation.py` with subprocess tests that:

- write a candidate commit-safe summary with null validator digests;
- write a matching local-only summary;
- run `refresh_validate_redaction.py --mode candidate --validate-own-summary`;
- run `refresh_validate_run_metadata.py --mode candidate`;
- assert both candidate-mode validator summaries are written as JSON objects containing `status = "passed"`;
- assert both candidate-mode validator summaries record `candidate_summary_sha256 = sha256_file(candidate_summary_path)`;
- assert both candidate-mode validator summaries record `validated_payload_projection_sha256 = sha256_payload(projected_summary_for_validator_digest(candidate_payload))`;
- build a final commit-safe summary with validator digest fields set to the SHA256 values of the candidate-mode validator summaries;
- run both validators in `--mode final` with explicit `--existing-validation-summary` arguments;
- assert final-mode validation passes without rewriting the candidate-mode validator summaries;
- assert candidate and final validators can validate local-only candidate/final summary paths while recording the intended repo-local `published_summary_path`;
- assert final-mode validation rejects an existing validator summary with the wrong `schema_version`, `run_id`, `validator_mode`, `status`, or validated summary path;
- assert final-mode metadata validation rejects an existing validator summary with a mismatched source `repo_head`, `repo_tree`, `tool_sha256`, `local_summary_sha256`, `candidate_summary_sha256`, or `validated_payload_projection_sha256`;
- assert metadata validation rejects invalid commit-safe `schema_version`, `source_local_summary_schema_version`, `dirty_state_policy`, `tool_path`, `dirty_state`, and `local_only_evidence_root`;
- assert metadata validation rejects dirty relevant paths when recomputing `dirty_state`;
- assert metadata validation rejects a local-only summary with the wrong `schema_version`, `run_id`, or `mode`;
- assert metadata validation rejects a summary whose `current_run_identity` does not match recomputed source manifest, installed-cache manifest, repo marketplace metadata, local config metadata, runtime config projection, or app-server inventory summary projection;
- assert metadata validation rejects stale source manifest projection SHA256, installed-cache manifest projection SHA256, repo marketplace metadata SHA256, local config metadata SHA256, runtime-config projection SHA256, and app-server inventory projection SHA256 values;
- assert metadata validation rejects stale `codex_version`, stale `codex_executable_path`, stale `codex_executable_sha256`, stale `app_server_server_info`, stale `app_server_protocol_capabilities`, stale `app_server_parser_version`, and stale `app_server_response_schema_version` values when app-server inventory status is `collected`;
- assert metadata validation accepts missing or unreadable source roots only when the commit-safe summary records `source_manifest_sha256 = None` plus an allowlisted `source_manifest_unavailable_reason`, never raw exception text;
- assert metadata validation accepts missing or unreadable installed-cache roots only when the commit-safe summary records `installed_cache_manifest_sha256 = None` plus an allowlisted `installed_cache_manifest_unavailable_reason`, never raw exception text;
- assert metadata validation accepts missing or unparsable runtime config only when the commit-safe summary records `runtime_config_projection_sha256 = None` plus an allowlisted `runtime_config_projection_unavailable_reason`, never raw exception text;
- assert metadata validation for `collected` app-server inventory re-runs read-only inventory and rejects a mismatched runtime identity projection;
- assert metadata validation for `collected` app-server inventory uses a replay-identity projection that excludes `transcript_sha256` and remains stable when Plan 03 uses a fresh temporary `scratch_cwd`;
- assert metadata validation for `requested-failed` app-server inventory records `failure-code-only` freshness and does not claim full runtime freshness proof.
- assert metadata validation rejects a hand-edited commit-safe summary whose `app_server_inventory_summary_sha256` no longer matches the stable inventory replay-identity projection;
- assert redaction rejects a summary containing `app_server_transcript`.
- assert redaction rejects a summary containing raw `app_server_inventory_failure_reason`, response-shaped `body`, token-shaped strings, email addresses, and path-heavy raw exception text.
- assert redaction rejects unknown `reason_codes[*]` values, mismatched `reason_count`, unknown `app_server_inventory_failure_reason_code`, and unknown `*_unavailable_reason` values at any nesting depth.
- assert redaction rejects path-heavy top-level and nested `codex_executable_hash_unavailable_reason` values unless they have been reduced to an allowlisted code such as `hash-unavailable`.
- assert redaction rejects transcript-like or config-like payloads hidden under allowed nested containers with non-forbidden top-level names, including `current_run_identity`, `dirty_state`, `omission_reasons`, `app_server_server_info`, and `app_server_protocol_capabilities`.
- assert redaction rejects marketplace-name plugin keys `handoff` and `ticket` under `runtime_config.plugin_enablement_state`; the allowed keys are the live config plugin ids `handoff@turbo-mode` and `ticket@turbo-mode`.
- assert redaction rejects broad absolute paths or config-looking strings in ordinary string fields such as `app_server_server_info.name`, `app_server_server_info.version`, `dirty_state.relevant_paths_checked`, and `diff_classification[*].canonical_path`, while allowing only the explicitly expected path fields.
- assert redaction candidate and final modes run the local-only sensitivity scanner against local-only summary, candidate summary, final summary when present, metadata validator summary when present, and redaction validator inputs.
- assert local-only sensitivity findings are recorded only in local-only validator summaries as counts, redacted examples, and affected artifact names.
- assert candidate redaction mode fails if expected local-only artifacts are missing or unreadable: `<mode>.summary.json`, `commit-safe.candidate.summary.json`, `metadata-validation.summary.json`, and the app-server transcript when the paired local-only summary says inventory was requested and a transcript should exist.
- assert final redaction mode fails if expected local-only artifacts are missing or unreadable: `<mode>.summary.json`, `commit-safe.candidate.summary.json`, `commit-safe.final.summary.json`, `metadata-validation.summary.json`, `redaction.summary.json`, and the app-server transcript when required by the paired local-only summary.
- assert local-only sensitivity scanning records token/email/key matches, config-shaped strings, transcript/status-envelope-shaped strings, and broad absolute path disclosures. Broad local-only paths are findings, not automatic failures; missing/unreadable expected artifacts are failures.
- assert final redaction mode writes a separate local-only final scan summary, for example `redaction-final-scan.summary.json`, and does not rewrite candidate `redaction.summary.json`.
- assert candidate redaction mode validates its own validator summary payload before writing `status = "passed"` to disk.
- assert validator summary writes fail when the output parent directory does not already exist or is not mode `0700`; validator scripts must not create local-only run parents casually.

Use `sys.executable`, temporary repo roots, and explicit `--summary-output` paths. Do not call the live `/Users/jp/.codex` evidence root in tests.

- [ ] **Step 2: Implement redaction validator script**

Create `plugins/turbo-mode/tools/refresh_validate_redaction.py`.

Required behavior:

- Candidate mode validates the candidate summary and writes one local-only redaction validator summary.
- Candidate mode scans the expected local-only artifacts before writing the validator summary. It must fail if an expected artifact is missing or unreadable.
- Candidate-mode summaries record `validated_payload_projection_sha256 = sha256_payload(projected_summary_for_validator_digest(candidate_payload))`.
- Candidate-mode summaries record `candidate_summary_sha256 = sha256_file(candidate_summary_path)` as the source-spec candidate digest and also record `validated_payload_projection_sha256` as the stable final-mode replay digest.
- Final mode validates the final summary, projects its validator digest fields back to `None`, loads the existing candidate-mode validator summary, and checks:
  - the candidate-mode validator summary has the expected `schema_version`, `run_id`, `validator_mode = "candidate"`, `status = "passed"`, and validated summary path;
  - the candidate-mode validator summary's `candidate_summary_sha256` equals the raw SHA256 of the candidate summary file;
  - the candidate-mode validator summary's `validated_payload_projection_sha256` equals the final summary projection digest;
  - the candidate-mode validator summary's `published_summary_path` equals the final repo-local path being published;
  - `sha256_file(existing_redaction_summary)` equals `final_summary["redaction_validation_summary_sha256"]`.
- Final mode scans expected local-only artifacts before publish, including the paired local-only Plan 03 summary, candidate summary, final summary, existing metadata validator summary, and existing redaction validator summary.
- Final mode writes a separate local-only final scan summary, such as `redaction-final-scan.summary.json`, containing the scan result and the final summary projection digest. This artifact is not referenced by the commit-safe summary and does not rewrite candidate `redaction.summary.json`.
- Local-only sensitivity scanning must write findings only to the local-only redaction validator summary. It must not add counts, examples, artifact names, raw transcripts, process listings, or config excerpts to the commit-safe summary.
- Local-only sensitivity scanning is a required gate for Plan 04 publish. If the scan cannot read an expected local-only artifact, write fails before repo-local publish. Token/email/key findings, config-shaped strings, transcript/status-envelope-shaped strings, and broad absolute path disclosures are recorded as local-only findings; for Plan 04 they are classification evidence rather than automatic publish blockers because the scanned artifacts are intentionally local-only.
- Final mode must not overwrite the candidate-mode validator summary.
- Validator summary output parent directories must already exist with mode `0700`. The script must not create local-only run parents; only the summary file itself is created with mode `0600`.

Required CLI shape:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import stat
import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
REFRESH_PARENT = CURRENT_FILE.parent
sys.path.insert(0, str(REFRESH_PARENT))

from refresh.commit_safe import sha256_file, sha256_payload  # noqa: E402
from refresh.validation import (  # noqa: E402
    BROAD_ABSOLUTE_PATH_PATTERN,
    CONFIG_OR_TRANSCRIPT_PATTERNS,
    SENSITIVE_PATTERNS,
    assert_commit_safe_payload,
    assert_no_sensitive_values,
    load_json_object,
    projected_summary_for_validator_digest,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Turbo Mode refresh redaction.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("candidate", "final"), required=True)
    parser.add_argument("--scope", required=True)
    parser.add_argument("--source", required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--local-only-root", type=Path, required=True)
    parser.add_argument("--published-summary-path", type=Path, required=True)
    parser.add_argument("--candidate-summary", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--existing-validation-summary", type=Path)
    parser.add_argument("--final-scan-output", type=Path)
    parser.add_argument("--validate-own-summary", action="store_true")
    return parser


def validate_candidate(args: argparse.Namespace) -> int:
    payload = load_json_object(args.summary)
    assert_commit_safe_payload(payload)
    sensitivity = scan_local_only_artifacts(args.local_only_root, phase="candidate", mode=str(payload["mode"]))
    summary = {
        "schema_version": "turbo-mode-refresh-redaction-validation-plan-04",
        "run_id": args.run_id,
        "validator_mode": "candidate",
        "scope": args.scope,
        "source": args.source,
        "status": "passed",
        "validated_summary_path": str(args.summary),
        "published_summary_path": str(args.published_summary_path),
        "candidate_summary_sha256": sha256_file(args.summary),
        "validated_payload_projection_sha256": sha256_payload(
            projected_summary_for_validator_digest(payload)
        ),
        "local_only_sensitivity_scan": sensitivity,
    }
    if args.summary_output is None:
        raise ValueError("validate redaction failed: summary output is required in candidate mode. Got: None")
    if args.validate_own_summary:
        assert_no_sensitive_values(summary)
    write_summary(args.summary_output, summary)
    return 0


def validate_final(args: argparse.Namespace) -> int:
    payload = load_json_object(args.summary)
    assert_commit_safe_payload(payload)
    if args.existing_validation_summary is None:
        raise ValueError("validate redaction failed: existing validation summary is required in final mode. Got: None")
    if args.candidate_summary is None:
        raise ValueError("validate redaction failed: candidate summary is required in final mode. Got: None")
    existing = load_json_object(args.existing_validation_summary)
    expected_fields = {
        "schema_version": "turbo-mode-refresh-redaction-validation-plan-04",
        "run_id": args.run_id,
        "validator_mode": "candidate",
        "status": "passed",
        "validated_summary_path": str(args.candidate_summary),
        "published_summary_path": str(args.published_summary_path),
    }
    for key, expected in expected_fields.items():
        if existing.get(key) != expected:
            raise ValueError(f"validate redaction failed: validator summary field mismatch. Got: {key!r:.100}")
    projected_digest = sha256_payload(projected_summary_for_validator_digest(payload))
    if existing.get("validated_payload_projection_sha256") != projected_digest:
        raise ValueError("validate redaction failed: projected summary digest mismatch. Got: validated_payload_projection_sha256")
    if existing.get("candidate_summary_sha256") != sha256_file(args.candidate_summary):
        raise ValueError("validate redaction failed: candidate summary digest mismatch. Got: candidate_summary_sha256")
    if existing.get("published_summary_path") != str(args.published_summary_path):
        raise ValueError("validate redaction failed: published summary path mismatch. Got: published_summary_path")
    if payload.get("redaction_validation_summary_sha256") != sha256_file(args.existing_validation_summary):
        raise ValueError("validate redaction failed: redaction validator digest mismatch. Got: redaction_validation_summary_sha256")
    if existing.get("local_only_sensitivity_scan", {}).get("status") != "completed":
        raise ValueError("validate redaction failed: local-only sensitivity scan missing. Got: local_only_sensitivity_scan")
    if args.final_scan_output is None:
        raise ValueError("validate redaction failed: final scan output is required in final mode. Got: None")
    sensitivity = scan_local_only_artifacts(args.local_only_root, phase="final", mode=str(payload["mode"]))
    final_scan = {
        "schema_version": "turbo-mode-refresh-redaction-final-scan-plan-04",
        "run_id": args.run_id,
        "validator_mode": "final-scan",
        "status": "passed",
        "validated_summary_path": str(args.summary),
        "published_summary_path": str(args.published_summary_path),
        "validated_payload_projection_sha256": projected_digest,
        "local_only_sensitivity_scan": sensitivity,
    }
    assert_no_sensitive_values(final_scan)
    write_summary(args.final_scan_output, final_scan)
    return 0


def scan_local_only_artifacts(root: Path, *, phase: str, mode: str) -> dict[str, object]:
    if not root.is_dir():
        raise ValueError(f"scan local-only artifacts failed: run directory is not a directory. Got: {str(root)!r:.100}")
    artifact_names = expected_local_only_artifacts(root, phase=phase, mode=mode)
    findings: list[dict[str, object]] = []
    for name in artifact_names:
        path = root / name
        if not path.is_file():
            raise ValueError(f"scan local-only artifacts failed: expected artifact missing. Got: {name!r:.100}")
        text = path.read_text(encoding="utf-8", errors="replace")
        examples: list[str] = []
        count = 0
        classes: set[str] = set()
        patterns = (
            ("secret-like", SENSITIVE_PATTERNS),
            ("config-shaped", CONFIG_OR_TRANSCRIPT_PATTERNS),
            ("broad-absolute-path", (BROAD_ABSOLUTE_PATH_PATTERN,)),
        )
        for label, active_patterns in patterns:
            for pattern in active_patterns:
                for match in pattern.finditer(text):
                    count += 1
                    classes.add(label)
                    if len(examples) < 3:
                        examples.append(pattern.sub("[REDACTED]", match.group(0)))
        if count:
            findings.append(
                {
                    "artifact": path.name,
                    "match_count": count,
                    "classes": sorted(classes),
                    "redacted_examples": examples,
                }
            )
    return {
        "status": "completed",
        "phase": phase,
        "artifact_count": len(artifact_names),
        "expected_artifacts": artifact_names,
        "finding_count": sum(int(item["match_count"]) for item in findings),
        "affected_artifacts": [str(item["artifact"]) for item in findings],
        "findings": findings,
    }


def expected_local_only_artifacts(root: Path, *, phase: str, mode: str) -> list[str]:
    base = [
        f"{mode}.summary.json",
        "commit-safe.candidate.summary.json",
        "metadata-validation.summary.json",
    ]
    local_summary = load_json_object(root / f"{mode}.summary.json")
    if _local_summary_requires_transcript(local_summary):
        base.append("app-server-readonly-inventory.transcript.json")
    if phase == "candidate":
        return base
    if phase == "final":
        return [
            *base,
            "commit-safe.final.summary.json",
            "redaction.summary.json",
        ]
    raise ValueError(f"scan local-only artifacts failed: invalid phase. Got: {phase!r:.100}")


def _local_summary_requires_transcript(local_summary: dict[str, object]) -> bool:
    status = local_summary.get("app_server_inventory_status")
    return status in {"collected", "requested-failed"}


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.mode == "candidate":
            return validate_candidate(args)
        return validate_final(args)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def write_summary(path: Path, payload: dict[str, object]) -> None:
    if not path.parent.is_dir():
        raise ValueError(f"write validation summary failed: parent directory does not exist. Got: {str(path.parent)!r:.100}")
    parent_mode = stat.S_IMODE(path.parent.stat().st_mode)
    if parent_mode != 0o700:
        raise PermissionError(f"write validation summary failed: parent directory must be 0700. Got: {oct(parent_mode)!r:.100}")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 3: Implement metadata validator script**

Create `plugins/turbo-mode/tools/refresh_validate_run_metadata.py`.

Required behavior:

- Both modes recompute `repo_head`, `repo_tree`, `tool_sha256`, and the paired local-only summary digest.
- Both modes load the paired local-only summary and recompute the deterministic commit-safe projection.
- Both modes reject the paired local-only summary unless its `schema_version`, `run_id`, and `mode` exactly match the commit-safe summary.
- Both modes reject invalid top-level metadata fields: commit-safe `schema_version`, `source_local_summary_schema_version`, `dirty_state_policy`, recomputed `dirty_state`, `tool_path`, and `local_only_evidence_root`.
- Both modes recompute `current_run_identity` from current source/cache/config/runtime inputs and compare it to the commit-safe summary.
- Validation must compare every projected commit-safe field, including `app_server_inventory_summary_sha256`, not just the file digests.
- Candidate mode writes one local-only metadata validator summary with both `candidate_summary_sha256` and `validated_payload_projection_sha256`.
- Final mode verifies the existing candidate-mode metadata validator summary and does not rewrite it.
- Final mode validates that the existing metadata validator summary is the expected candidate-mode pass for this run, intended published summary path, source `repo_head`, source `repo_tree`, tool digest, local summary digest, raw candidate summary digest, projected-payload digest, and current-run identity digest fields.
- Validator summary output parent directories must already exist with mode `0700`. The script must not create local-only run parents; only the summary file itself is created with mode `0600`.

Required CLI shape:

```python
#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import subprocess
import stat
import sys
from pathlib import Path

CURRENT_FILE = Path(__file__).resolve()
REFRESH_PARENT = CURRENT_FILE.parent
sys.path.insert(0, str(REFRESH_PARENT))

from refresh.commit_safe import (  # noqa: E402
    build_current_run_identity_from_paths,
    project_commit_safe_fields_from_local_summary,
    sha256_file,
    sha256_payload,
)
from refresh.validation import (  # noqa: E402
    ALLOWED_DIRTY_RELEVANT_PATHS,
    EXPECTED_COMMIT_SAFE_SCHEMA_VERSION,
    EXPECTED_DIRTY_STATE_POLICY,
    EXPECTED_SOURCE_LOCAL_SUMMARY_SCHEMA_VERSION,
    EXPECTED_TOOL_PATH,
    assert_commit_safe_payload,
    load_json_object,
    projected_summary_for_validator_digest,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Validate Turbo Mode refresh metadata.")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--repo-root", type=Path, required=True)
    parser.add_argument("--mode", choices=("candidate", "final"), required=True)
    parser.add_argument("--local-only-root", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--published-summary-path", type=Path, required=True)
    parser.add_argument("--candidate-summary", type=Path)
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--existing-validation-summary", type=Path)
    return parser


def validate_metadata_payload(args: argparse.Namespace) -> tuple[dict[str, object], str]:
    payload = load_json_object(args.summary)
    assert_commit_safe_payload(payload)
    if payload.get("run_id") != args.run_id:
        raise ValueError(f"validate run metadata failed: run id mismatch. Got: {payload.get('run_id')!r:.100}")
    local_summary = args.local_only_root / f"{payload['mode']}.summary.json"
    local_payload = load_json_object(local_summary)
    _assert_top_level_metadata_contract(
        args=args,
        payload=payload,
        local_payload=local_payload,
        local_summary=local_summary,
    )
    if payload.get("local_only_summary_sha256") != sha256_file(local_summary):
        raise ValueError("validate run metadata failed: local summary digest mismatch. Got: local_only_summary_sha256")
    if local_payload.get("schema_version") != "turbo-mode-refresh-plan-03":
        raise ValueError(f"validate run metadata failed: local summary schema mismatch. Got: {local_payload.get('schema_version')!r:.100}")
    if local_payload.get("run_id") != args.run_id:
        raise ValueError(f"validate run metadata failed: local summary run id mismatch. Got: {local_payload.get('run_id')!r:.100}")
    if local_payload.get("mode") != payload.get("mode"):
        raise ValueError(f"validate run metadata failed: local summary mode mismatch. Got: {local_payload.get('mode')!r:.100}")
    tool_path = args.repo_root / str(payload["tool_path"])
    if payload.get("tool_sha256") != sha256_file(tool_path):
        raise ValueError("validate run metadata failed: tool digest mismatch. Got: tool_sha256")
    repo_head = git(args.repo_root, "rev-parse", "HEAD")
    repo_tree = git(args.repo_root, "rev-parse", "HEAD^{tree}")
    if payload.get("repo_head") != repo_head:
        raise ValueError(f"validate run metadata failed: repo head mismatch. Got: {payload.get('repo_head')!r:.100}")
    if payload.get("repo_tree") != repo_tree:
        raise ValueError(f"validate run metadata failed: repo tree mismatch. Got: {payload.get('repo_tree')!r:.100}")
    projected_fields = project_commit_safe_fields_from_local_summary(local_payload)
    for key, expected in projected_fields.items():
        if payload.get(key) != expected:
            raise ValueError(f"validate run metadata failed: projected field mismatch. Got: {key!r:.100}")
    current_identity = build_current_run_identity_from_paths(
        repo_root=args.repo_root,
        codex_home=Path(local_payload["codex_home"]),
        run_id=args.run_id,
        local_summary=local_payload,
    )
    if payload.get("current_run_identity") != current_identity:
        raise ValueError("validate run metadata failed: current run identity mismatch. Got: current_run_identity")
    _assert_runtime_identity_fields_match_current(payload, current_identity)
    return payload, sha256_payload(projected_summary_for_validator_digest(payload))


def _assert_top_level_metadata_contract(
    *,
    args: argparse.Namespace,
    payload: dict[str, object],
    local_payload: dict[str, object],
    local_summary: Path,
) -> None:
    expected = {
        "schema_version": EXPECTED_COMMIT_SAFE_SCHEMA_VERSION,
        "source_local_summary_schema_version": EXPECTED_SOURCE_LOCAL_SUMMARY_SCHEMA_VERSION,
        "dirty_state_policy": EXPECTED_DIRTY_STATE_POLICY,
        "tool_path": EXPECTED_TOOL_PATH,
        "local_only_evidence_root": str(args.local_only_root),
    }
    for key, expected_value in expected.items():
        if payload.get(key) != expected_value:
            raise ValueError(f"validate run metadata failed: top-level metadata mismatch. Got: {key!r:.100}")
    if local_payload.get("schema_version") != payload.get("source_local_summary_schema_version"):
        raise ValueError("validate run metadata failed: source local summary schema mismatch. Got: source_local_summary_schema_version")
    if local_summary.parent != args.local_only_root:
        raise ValueError(f"validate run metadata failed: local summary path mismatch. Got: {str(local_summary)!r:.100}")
    _assert_recomputed_dirty_state(args.repo_root, payload.get("dirty_state"))


def _assert_recomputed_dirty_state(repo_root: Path, dirty_state: object) -> None:
    if not isinstance(dirty_state, dict):
        raise ValueError(f"validate run metadata failed: dirty state is not an object. Got: {dirty_state!r:.100}")
    expected_paths = sorted(ALLOWED_DIRTY_RELEVANT_PATHS)
    expected = {
        "status": "clean-relevant-paths",
        "relevant_paths_checked": expected_paths,
        "post_commit_binding": False,
    }
    if dirty_state != expected:
        raise ValueError(f"validate run metadata failed: dirty state mismatch. Got: {dirty_state!r:.100}")
    completed = subprocess.run(
        ["git", "status", "--short", "--", *expected_paths],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    if completed.stdout.strip():
        raise ValueError(f"validate run metadata failed: relevant paths dirty. Got: {completed.stdout.strip()!r:.100}")


def _assert_runtime_identity_fields_match_current(
    payload: dict[str, object],
    current_identity: dict[str, object],
) -> None:
    runtime_identity = current_identity.get("runtime_identity")
    if runtime_identity is None:
        return
    if not isinstance(runtime_identity, dict):
        raise ValueError("validate run metadata failed: runtime identity is not an object. Got: runtime_identity")
    mapping = {
        "codex_version": "codex_version",
        "codex_executable_path": "codex_executable_path",
        "codex_executable_sha256": "codex_executable_sha256",
        "codex_executable_hash_unavailable_reason": "codex_executable_hash_unavailable_reason",
        "app_server_server_info": "app_server_server_info",
        "app_server_protocol_capabilities": "app_server_protocol_capabilities",
        "app_server_parser_version": "app_server_parser_version",
        "app_server_response_schema_version": "app_server_response_schema_version",
    }
    for payload_key, identity_key in mapping.items():
        if payload.get(payload_key) != runtime_identity.get(identity_key):
            raise ValueError(f"validate run metadata failed: runtime identity field mismatch. Got: {payload_key!r:.100}")


def validate_candidate(args: argparse.Namespace) -> int:
    payload, projected_digest = validate_metadata_payload(args)
    summary = {
        "schema_version": "turbo-mode-refresh-metadata-validation-plan-04",
        "run_id": args.run_id,
        "validator_mode": "candidate",
        "status": "passed",
        "summary_path": str(args.summary),
        "published_summary_path": str(args.published_summary_path),
        "candidate_summary_sha256": sha256_file(args.summary),
        "validated_payload_projection_sha256": projected_digest,
        "local_summary_sha256": payload["local_only_summary_sha256"],
        "tool_sha256": payload["tool_sha256"],
        "repo_head": payload["repo_head"],
        "repo_tree": payload["repo_tree"],
        "current_run_identity": payload["current_run_identity"],
    }
    if args.summary_output is None:
        raise ValueError("validate run metadata failed: summary output is required in candidate mode. Got: None")
    write_summary(args.summary_output, summary)
    return 0


def validate_final(args: argparse.Namespace) -> int:
    payload, projected_digest = validate_metadata_payload(args)
    if args.existing_validation_summary is None:
        raise ValueError("validate run metadata failed: existing validation summary is required in final mode. Got: None")
    if args.candidate_summary is None:
        raise ValueError("validate run metadata failed: candidate summary is required in final mode. Got: None")
    existing = load_json_object(args.existing_validation_summary)
    expected_fields = {
        "schema_version": "turbo-mode-refresh-metadata-validation-plan-04",
        "run_id": args.run_id,
        "validator_mode": "candidate",
        "status": "passed",
        "summary_path": str(args.candidate_summary),
        "published_summary_path": str(args.published_summary_path),
        "local_summary_sha256": payload["local_only_summary_sha256"],
        "tool_sha256": payload["tool_sha256"],
        "repo_head": payload["repo_head"],
        "repo_tree": payload["repo_tree"],
        "current_run_identity": payload["current_run_identity"],
    }
    for key, expected in expected_fields.items():
        if existing.get(key) != expected:
            raise ValueError(f"validate run metadata failed: validator summary field mismatch. Got: {key!r:.100}")
    if existing.get("validated_payload_projection_sha256") != projected_digest:
        raise ValueError("validate run metadata failed: projected summary digest mismatch. Got: validated_payload_projection_sha256")
    if existing.get("candidate_summary_sha256") != sha256_file(args.candidate_summary):
        raise ValueError("validate run metadata failed: candidate summary digest mismatch. Got: candidate_summary_sha256")
    if existing.get("published_summary_path") != str(args.published_summary_path):
        raise ValueError("validate run metadata failed: published summary path mismatch. Got: published_summary_path")
    if payload.get("metadata_validation_summary_sha256") != sha256_file(args.existing_validation_summary):
        raise ValueError("validate run metadata failed: metadata validator digest mismatch. Got: metadata_validation_summary_sha256")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.mode == "candidate":
            return validate_candidate(args)
        return validate_final(args)
    except (OSError, ValueError, json.JSONDecodeError, subprocess.CalledProcessError) as exc:
        print(str(exc), file=sys.stderr)
        return 1


def git(repo_root: Path, *args: str) -> str:
    completed = subprocess.run(
        ["git", *args],
        cwd=repo_root,
        text=True,
        capture_output=True,
        check=True,
    )
    return completed.stdout.strip()


def write_summary(path: Path, payload: dict[str, object]) -> None:
    if not path.parent.is_dir():
        raise ValueError(f"write validation summary failed: parent directory does not exist. Got: {str(path.parent)!r:.100}")
    parent_mode = stat.S_IMODE(path.parent.stat().st_mode)
    if parent_mode != 0o700:
        raise PermissionError(f"write validation summary failed: parent directory must be 0700. Got: {oct(parent_mode)!r:.100}")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        json.dump(payload, handle, indent=2, sort_keys=True)
        handle.write("\n")
    os.chmod(path, 0o600)


if __name__ == "__main__":
    raise SystemExit(main())
```

- [ ] **Step 4: Run validator tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_validation.py -q
```

Expected: pass.

## Task 4: CLI `--record-summary`

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_cli.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_cli.py`

- [ ] **Step 1: Write failing CLI tests**

Extend `test_cli.py` with tests proving:

- `--dry-run --record-summary --summary-output <repo>/plugins/turbo-mode/evidence/refresh/run.summary.json` writes the Plan 03 local-only summary and a local-only `commit-safe.candidate.summary.json`, but does not create the repo-local final summary path before Task 5 validation.
- `--plan-refresh --record-summary` writes a local-only candidate summary with `mode = "plan-refresh"` and does not publish repo-local final evidence before Task 5 validation.
- `--record-summary --inventory-check` includes inventory status and request methods but no transcript body.
- `--record-summary --inventory-check` with a requested-failed inventory collector writes an allowlisted `app_server_inventory_failure_reason_code` and omits raw response-shaped, token-shaped, and path-heavy exception text.
- `--record-summary` is rejected with `--refresh` and `--guarded-refresh` because those modes are still outside Plan 04.
- `--record-summary` fails before writing a commit-safe summary when relevant refresh source, CLI source, or marketplace metadata is dirty.
- `--record-summary` does not fail only because an unrelated path is dirty.
- `--record-summary` fails when the requested `RUN_ID` local-only directory already exists; Plan 04 must not rebind old local-only evidence to a new commit-safe summary.
- `--summary-output` rejects absolute paths outside `<repo_root>/plugins/turbo-mode/evidence/refresh/`.
- `--summary-output` rejects `..` path escape, symlink traversal, existing files, and directories.
- CLI tests initialize a temporary git repo, commit the relevant refresh/tool/marketplace paths, and run `--record-summary` from that clean baseline.

Expected candidate summary assertion:

```python
summary = json.loads(candidate_summary_path.read_text(encoding="utf-8"))
assert summary["schema_version"] == "turbo-mode-refresh-commit-safe-plan-04"
assert summary["mode"] == "dry-run"
assert summary["local_only_summary_sha256"]
assert "app_server_transcript" not in json.dumps(summary)
assert "app_server_inventory_failure_reason" not in summary
assert summary["omission_reasons"]["raw_app_server_transcript"] == "local-only"
assert not published_summary_path.exists()
```

- [ ] **Step 2: Add CLI arguments and summary write flow**

Modify `build_parser()`:

```python
parser.add_argument("--record-summary", action="store_true")
parser.add_argument("--summary-output", type=Path)
```

When `args.record_summary` is set, run the relevant dirty-state gate before creating the local-only run directory or commit-safe summary. This prevents a dirty run from consuming an exclusive `RUN_ID` before the commit-safe binding fails:

```python
dirty_state = (
    ensure_relevant_worktree_clean(args.repo_root)
    if args.record_summary
    else None
)
```

After the dirty-state gate passes and local-only evidence is written:

```python
if args.record_summary:
    published_summary_path = resolve_commit_safe_summary_output(
        repo_root=args.repo_root,
        run_id=run_id,
        requested=args.summary_output,
    )
    candidate_summary_path = (
        result.paths.local_only_root / run_id / "commit-safe.candidate.summary.json"
    )
    commit_safe_payload = build_commit_safe_summary(
        result,
        run_id=run_id,
        local_summary_path=evidence_path,
        repo_head=git_rev_parse(args.repo_root, "HEAD"),
        repo_tree=git_rev_parse(args.repo_root, "HEAD^{tree}"),
        tool_path=Path("plugins/turbo-mode/tools/refresh_installed_turbo_mode.py"),
        tool_sha256=sha256_file(CURRENT_FILE),
        dirty_state=dirty_state,
        metadata_validation_summary_sha256=None,
        redaction_validation_summary_sha256=None,
    )
    assert_commit_safe_payload(commit_safe_payload)
    write_json_0600_exclusive(candidate_summary_path, commit_safe_payload)
```

Add helper functions in the CLI or import constants-free helpers:

- `git_rev_parse(repo_root: Path, revision: str) -> str`
- `resolve_commit_safe_summary_output(repo_root: Path, run_id: str, requested: Path | None) -> Path`
- `write_json_0600_exclusive(path: Path, payload: dict[str, object]) -> None`
- `publish_json_0600_exclusive(source_payload_path: Path, final_path: Path) -> None`

`resolve_commit_safe_summary_output()` must:

- default to `<repo_root>/plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.json`;
- require explicit `--summary-output` paths to resolve under `<repo_root>/plugins/turbo-mode/evidence/refresh/`;
- reject path traversal and symlink traversal;
- reject existing files, existing directories, and existing symlinks at the final output path;
- reject final path names that do not end in `.summary.json`.
- validate every existing parent with `lstat()` immediately before publish and use no-follow creation where available (`os.O_NOFOLLOW | os.O_CREAT | os.O_EXCL`) or an equivalent parent-inode check before and after `os.open()`;
- include a regression where the evidence-root parent is replaced with a symlink between path resolution and publish, and require the publish helper to fail without creating the final file.

`write_json_0600_exclusive()` and validator local-only summary writes must use exclusive creation (`O_EXCL`) rather than truncation. `publish_json_0600_exclusive()` must create the final repo-local path only after Task 5 final-mode validation passes; it must not overwrite an existing final path.

The first implementation may write null validator digests. Task 5 wires the two-pass validator digests.

- [ ] **Step 3: Run CLI tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_cli.py -q
```

Expected: pass.

## Task 5: Validator Digest Bootstrap

**Files:**

- Modify: `plugins/turbo-mode/tools/refresh/commit_safe.py`
- Modify: `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py`
- Modify: `plugins/turbo-mode/tools/refresh/tests/test_cli.py`
- Test: `plugins/turbo-mode/tools/refresh/tests/test_cli.py`

- [ ] **Step 1: Add failing tests for final validator digest fields**

Extend CLI tests so `--record-summary` writes:

- local-only `metadata-validation.summary.json`;
- local-only `redaction.summary.json`;
- final commit-safe summary with both validator summary digests non-null;
- validator summaries whose SHA256 values match the final summary fields.
- final-mode validator checks that do not modify either validator summary.
- a regression proving metadata and redaction validator summaries record both the raw candidate summary file digest and the projected candidate/final payload digest, and never use the raw final summary file digest as the replay proof.
- a regression proving candidate summaries are written only under the local-only run directory, not the repo-local final path.
- a regression proving a failing candidate or final validator leaves no file at `plugins/turbo-mode/evidence/refresh/<RUN_ID>.summary.json`.

- [ ] **Step 2: Implement two-pass validation flow**

In the CLI write path:

1. Resolve `published_summary_path` with `resolve_commit_safe_summary_output()`.
2. Build candidate commit-safe summary with both validator digests set to `None`.
3. Write the candidate summary to local-only `"$LOCAL_ONLY_RUN_DIR/commit-safe.candidate.summary.json"` with exclusive creation.
4. Run the metadata validator and redaction validator in candidate mode with explicit arguments:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_validate_run_metadata.py \
  --mode candidate \
  --run-id "$RUN_ID" \
  --repo-root "$REPO_ROOT" \
  --local-only-root "$LOCAL_ONLY_RUN_DIR" \
  --summary "$LOCAL_ONLY_RUN_DIR/commit-safe.candidate.summary.json" \
  --published-summary-path "$PUBLISHED_SUMMARY_PATH" \
  --summary-output "$LOCAL_ONLY_RUN_DIR/metadata-validation.summary.json"

PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_validate_redaction.py \
  --mode candidate \
  --run-id "$RUN_ID" \
  --repo-root "$REPO_ROOT" \
  --scope commit-safe-summary \
  --source plan-04-cli \
  --summary "$LOCAL_ONLY_RUN_DIR/commit-safe.candidate.summary.json" \
  --local-only-root "$LOCAL_ONLY_RUN_DIR" \
  --published-summary-path "$PUBLISHED_SUMMARY_PATH" \
  --summary-output "$LOCAL_ONLY_RUN_DIR/redaction.summary.json" \
  --validate-own-summary
```

5. Compute the SHA256 values of the candidate-mode validator summaries.
6. Build final commit-safe summary with validator digests populated.
7. Write the final summary to local-only `"$LOCAL_ONLY_RUN_DIR/commit-safe.final.summary.json"` with exclusive creation.
8. Re-run validators in final mode with explicit arguments and the existing candidate-mode summaries:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_validate_run_metadata.py \
  --mode final \
  --run-id "$RUN_ID" \
  --repo-root "$REPO_ROOT" \
  --local-only-root "$LOCAL_ONLY_RUN_DIR" \
  --summary "$LOCAL_ONLY_RUN_DIR/commit-safe.final.summary.json" \
  --published-summary-path "$PUBLISHED_SUMMARY_PATH" \
  --candidate-summary "$LOCAL_ONLY_RUN_DIR/commit-safe.candidate.summary.json" \
  --existing-validation-summary "$LOCAL_ONLY_RUN_DIR/metadata-validation.summary.json"

PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_validate_redaction.py \
  --mode final \
  --run-id "$RUN_ID" \
  --repo-root "$REPO_ROOT" \
  --scope commit-safe-summary \
  --source plan-04-cli \
  --summary "$LOCAL_ONLY_RUN_DIR/commit-safe.final.summary.json" \
  --local-only-root "$LOCAL_ONLY_RUN_DIR" \
  --published-summary-path "$PUBLISHED_SUMMARY_PATH" \
  --candidate-summary "$LOCAL_ONLY_RUN_DIR/commit-safe.candidate.summary.json" \
  --existing-validation-summary "$LOCAL_ONLY_RUN_DIR/redaction.summary.json" \
  --final-scan-output "$LOCAL_ONLY_RUN_DIR/redaction-final-scan.summary.json"
```

9. Publish the final summary to `"$PUBLISHED_SUMMARY_PATH"` only after both final-mode validators pass.

Final mode must not rewrite `metadata-validation.summary.json` or `redaction.summary.json`. It only proves that each existing validator summary's projected payload digest equals the final summary with validator digest fields nulled, that each existing validator summary file digest matches the corresponding final summary field, that both validators agreed on the same intended `published_summary_path`, and that `redaction-final-scan.summary.json` durably records the final-mode local-only scan.

If any step before publish fails, do not create the repo-local final summary path. Local-only candidate/final files may remain as failure evidence, but they must stay under `/Users/jp/.codex/local-only/turbo-mode-refresh/<RUN_ID>/` or the test-local equivalent.

If in-process helpers are easier to test than subprocess calls, implement importable validator functions in `validation.py` and keep the script entrypoints as thin wrappers.

- [ ] **Step 3: Run CLI tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_cli.py -q
```

Expected: pass.

## Task 6: Integration Verification And Live Non-Mutating Smoke

**Files:**

- No additional source edits expected unless verification finds defects.

- [ ] **Step 1: Run focused refresh tests**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest \
  plugins/turbo-mode/tools/refresh/tests -q
```

Expected: all tests pass.

- [ ] **Step 2: Run ruff**

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check \
  plugins/turbo-mode/tools/refresh \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  plugins/turbo-mode/tools/refresh_validate_run_metadata.py \
  plugins/turbo-mode/tools/refresh_validate_redaction.py
```

Expected:

```text
All checks passed!
```

- [ ] **Step 3: Run residue gate**

Run:

```bash
find plugins/turbo-mode/handoff/1.6.0 plugins/turbo-mode/ticket/1.4.0 \
  plugins/turbo-mode/tools/refresh \
  -name __pycache__ -o -name '*.pyc' -o -name .pytest_cache \
  -o -name .ruff_cache -o -name .mypy_cache -o -name .venv -o -name .DS_Store
```

Expected: prints nothing.

- [ ] **Step 4: Create the source implementation commit**

Before running the live `--record-summary` smoke, create the source implementation commit. This is required because the dirty-state gate must reject dirty relevant source paths, and the live summary must bind to a clean source commit.

Stage only the implementation source, tests, and the plan document in its pre-completion-evidence state. Do not stage generated commit-safe evidence yet.

Run:

```bash
git status --short --branch
git add \
  plugins/turbo-mode/tools/refresh/commit_safe.py \
  plugins/turbo-mode/tools/refresh/validation.py \
  plugins/turbo-mode/tools/refresh/evidence.py \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  plugins/turbo-mode/tools/refresh_validate_run_metadata.py \
  plugins/turbo-mode/tools/refresh_validate_redaction.py \
  plugins/turbo-mode/tools/refresh/tests/test_commit_safe.py \
  plugins/turbo-mode/tools/refresh/tests/test_validation.py \
  plugins/turbo-mode/tools/refresh/tests/test_evidence.py \
  plugins/turbo-mode/tools/refresh/tests/test_cli.py \
  docs/superpowers/plans/2026-05-06-turbo-mode-refresh-04-commit-safe-evidence.md
git commit -m "Implement Turbo Mode refresh commit-safe evidence"
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

Expected:

- commit succeeds on `feature/turbo-mode-refresh-plan-04-commit-safe-evidence`;
- `git status --short -- plugins/turbo-mode/tools/refresh plugins/turbo-mode/tools/refresh_installed_turbo_mode.py plugins/turbo-mode/tools/refresh_validate_run_metadata.py plugins/turbo-mode/tools/refresh_validate_redaction.py .agents/plugins/marketplace.json` prints nothing;
- record this commit hash as `source_implementation_commit`;
- record this tree hash as `source_implementation_tree`.

If any relevant dirty path remains after the source implementation commit, stop. The live smoke should not run until the source implementation boundary is clean.

- [ ] **Step 5: Run live non-mutating summary smoke against the source implementation commit**

Choose a fresh run id for every live smoke. Do not reuse an existing local-only run directory, because `write_local_evidence()` creates run directories exclusively. Example run id format:

```text
plan04-live-commit-safe-YYYYMMDD-HHMMSS
```

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  --dry-run \
  --inventory-check \
  --record-summary \
  --run-id plan04-live-commit-safe-YYYYMMDD-HHMMSS \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --codex-home /Users/jp/.codex \
  --json
```

Expected:

- command exits `0`;
- local-only summary path is under `/Users/jp/.codex/local-only/turbo-mode-refresh/<fresh-run-id>/`;
- commit-safe summary path is `plugins/turbo-mode/evidence/refresh/<fresh-run-id>.summary.json`;
- commit-safe summary omits raw transcript;
- terminal status may still be `coverage-gap-blocked`.

If terminal status is `coverage-gap-blocked`, classify that as honest live state, not a Plan 04 failure.

After the smoke, verify that the generated commit-safe summary records `repo_head = source_implementation_commit` and `repo_tree = source_implementation_tree`. Do not amend the source implementation commit to include this generated summary; it belongs in the later evidence/docs commit.

## Task 7: Documentation Closeout

**Files:**

- Modify: `docs/superpowers/plans/2026-05-06-turbo-mode-refresh-04-commit-safe-evidence.md`

- [ ] **Step 1: Record completion evidence**

Append a `## Completion Evidence` section to this plan after implementation with:

- implementation branch;
- source implementation commit hash and tree hash;
- focused test result;
- ruff result;
- residue result;
- live smoke path;
- commit-safe summary path;
- commit-safe summary SHA256;
- commit-safe summary `repo_head` and `repo_tree`;
- replay commands for validating from `source_implementation_commit`;
- final terminal status;
- explicit note that mutation remains outside Plan 04.
- explicit note that replay is source-commit-bound and live-environment-bound: it depends on checking out `source_implementation_commit`, retaining the local-only run directory, and keeping or reproducibly restoring installed cache manifests, local config metadata, repo marketplace metadata, Codex executable identity, accepted app-server response schema, and app-server read-only inventory behavior.
- explicit note that if any of those external inputs drift, replay may fail even when the committed summary blob remains byte-for-byte identical to the validated local-only final summary.
- explicit note that the evidence/docs commit hash and tree hash cannot be embedded in this same committed file without changing them, so they will be reported after commit in closeout or PR text.

- [ ] **Step 2: Create the evidence/docs commit**

Stage the generated commit-safe summary and the plan's completion-evidence update. Do not modify implementation source between the source implementation commit and this commit.

Run:

```bash
python3 - <<'PY'
from pathlib import Path
import hashlib

local_final = Path("/Users/jp/.codex/local-only/turbo-mode-refresh/<fresh-run-id>/commit-safe.final.summary.json")
published = Path("plugins/turbo-mode/evidence/refresh/<fresh-run-id>.summary.json")
local_hash = hashlib.sha256(local_final.read_bytes()).hexdigest()
published_hash = hashlib.sha256(published.read_bytes()).hexdigest()
if local_hash != published_hash:
    raise SystemExit(f"published summary hash mismatch: {published_hash} != {local_hash}")
print(published_hash)
PY
git status --short --branch
git add \
  plugins/turbo-mode/evidence/refresh/<fresh-run-id>.summary.json \
  docs/superpowers/plans/2026-05-06-turbo-mode-refresh-04-commit-safe-evidence.md
git commit -m "Record Turbo Mode refresh commit-safe evidence"
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

Expected:

- the pre-commit hash check proves `plugins/turbo-mode/evidence/refresh/<fresh-run-id>.summary.json` is byte-for-byte identical to `/Users/jp/.codex/local-only/turbo-mode-refresh/<fresh-run-id>/commit-safe.final.summary.json`;
- commit succeeds on the same feature branch;
- the completion evidence records the source implementation commit and states where the evidence/docs commit identity will be reported after the commit exists;
- the completion evidence records the commit-safe summary SHA256 from the pre-commit hash check;
- the generated summary remains source-commit-bound to `source_implementation_commit`, not to the evidence/docs commit.

After the commit succeeds, record `git rev-parse HEAD` and `git rev-parse HEAD^{tree}` in the implementation closeout response, PR body, or a later follow-up metadata commit. Do not amend the evidence/docs commit solely to insert its own hash.

Also prove the committed blob is the same bytes that passed local-only final validation:

```bash
python3 - <<'PY'
import hashlib
import subprocess

run_id = "<fresh-run-id>"
expected = "<sha256-from-pre-commit-check>"
blob = subprocess.check_output(
    ["git", "show", f"HEAD:plugins/turbo-mode/evidence/refresh/{run_id}.summary.json"]
)
actual = hashlib.sha256(blob).hexdigest()
if actual != expected:
    raise SystemExit(f"committed summary hash mismatch: {actual} != {expected}")
print(actual)
PY
```

Do not rerun the metadata validator from the evidence/docs commit against the generated summary. That validator intentionally compares against current `HEAD`; after this commit, current `HEAD` is no longer the source implementation commit that the summary records.

The completion evidence must include a replay recipe like:

```bash
git switch main
git rev-parse HEAD
git switch --detach <source_implementation_commit>
mkdir /private/tmp/<fresh-run-id>-redaction-replay
chmod 700 /private/tmp/<fresh-run-id>-redaction-replay
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_validate_run_metadata.py \
  --mode final \
  --run-id <fresh-run-id> \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --local-only-root /Users/jp/.codex/local-only/turbo-mode-refresh/<fresh-run-id> \
  --summary /Users/jp/.codex/local-only/turbo-mode-refresh/<fresh-run-id>/commit-safe.final.summary.json \
  --published-summary-path /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/evidence/refresh/<fresh-run-id>.summary.json \
  --candidate-summary /Users/jp/.codex/local-only/turbo-mode-refresh/<fresh-run-id>/commit-safe.candidate.summary.json \
  --existing-validation-summary /Users/jp/.codex/local-only/turbo-mode-refresh/<fresh-run-id>/metadata-validation.summary.json
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_validate_redaction.py \
  --mode final \
  --run-id <fresh-run-id> \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --scope commit-safe-summary \
  --source plan-04-cli \
  --summary /Users/jp/.codex/local-only/turbo-mode-refresh/<fresh-run-id>/commit-safe.final.summary.json \
  --local-only-root /Users/jp/.codex/local-only/turbo-mode-refresh/<fresh-run-id> \
  --published-summary-path /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/evidence/refresh/<fresh-run-id>.summary.json \
  --candidate-summary /Users/jp/.codex/local-only/turbo-mode-refresh/<fresh-run-id>/commit-safe.candidate.summary.json \
  --existing-validation-summary /Users/jp/.codex/local-only/turbo-mode-refresh/<fresh-run-id>/redaction.summary.json \
  --final-scan-output /private/tmp/<fresh-run-id>-redaction-replay/redaction-final-scan.summary.json
git switch main
```

This replay recipe depends on more than local-only evidence retention. It also depends on checking out `source_implementation_commit` and preserving or reproducibly restoring the installed cache, local config metadata, repo marketplace metadata, Codex executable identity, accepted app-server response schema, and app-server read-only inventory behavior observed by the source-commit smoke. If the local-only run directory is missing, record that replay is unavailable because Plan 04 does not implement evidence retention or portable raw evidence. If any live external input has drifted, record that replay is unavailable or stale because Plan 04 does not implement a historical-validation mode against recorded external digests.

- [ ] **Step 3: Review ignored handoff state**

Run:

```bash
git status --short --ignored docs/handoffs
git status --short --ignored --untracked-files=all docs/handoffs
```

Expected:

- `docs/handoffs/.session-state/` and `docs/handoffs/archive/` may appear as ignored local mechanics.
- No ignored active `docs/handoffs/*.md` outside `.session-state/` or `archive/` should remain unresolved.

## Completion Evidence

Implementation branch:

- `feature/turbo-mode-refresh-plan-04-commit-safe-evidence`

Source implementation boundary:

- Source implementation commit: `ef8dcd945661115508a94bce337a6b99422a053a`
- Source implementation tree: `620d6538e5ec82cc999b7ffd873589e688be0a90`
- The evidence/docs commit hash and tree cannot be embedded in this same committed
  file without changing them. Record that identity in the implementation closeout
  or PR text after the evidence/docs commit exists.

Verification before the patched source implementation commit:

- Focused refresh tests:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run pytest plugins/turbo-mode/tools/refresh/tests -q`
- Result before commit: `245 passed in 16.11s`
- Ruff:
  `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/tools/refresh plugins/turbo-mode/tools/refresh_installed_turbo_mode.py plugins/turbo-mode/tools/refresh_validate_run_metadata.py plugins/turbo-mode/tools/refresh_validate_redaction.py`
- Result: `All checks passed!`
- Source-tree residue gate:
  `find plugins/turbo-mode/handoff/1.6.0 plugins/turbo-mode/ticket/1.4.0 plugins/turbo-mode/tools/refresh -name __pycache__ -o -name '*.pyc' -o -name .pytest_cache -o -name .ruff_cache -o -name .mypy_cache -o -name .venv -o -name .DS_Store`
- Source-tree residue result: printed nothing.

Installed-cache residue cleanup before final live smoke:

- An earlier live smoke with run id `plan04-live-commit-safe-20260506-003319`
  exited `0` but honestly reported `blocked-preflight` because installed-cache
  residue existed at
  `/Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0/scripts/__pycache__/project_paths.cpython-314.pyc`.
- The operator approved moving the installed-cache `__pycache__` residue to Trash.
- Cleanup command:
  `trash /Users/jp/.codex/plugins/cache/turbo-mode/handoff/1.6.0/scripts/__pycache__`
- Installed-cache residue check after cleanup printed nothing.
- The earlier blocked smoke summary remains untracked and is not the intended
  evidence/docs artifact.
- A later run with id `plan04-live-commit-safe-20260506-003701` was superseded
  by the review patch that fixed live inventory re-collection and replay
  bytecode behavior. It is not the intended final evidence/docs artifact.

Live non-mutating summary smoke:

- Run id: `plan04-live-commit-safe-20260506-005230`
- Command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_installed_turbo_mode.py \
  --dry-run \
  --inventory-check \
  --record-summary \
  --run-id plan04-live-commit-safe-20260506-005230 \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --codex-home /Users/jp/.codex \
  --json
```

- Command exit: `0`
- Local-only summary path:
  `/Users/jp/.codex/local-only/turbo-mode-refresh/plan04-live-commit-safe-20260506-005230/dry-run.summary.json`
- Local-only candidate commit-safe summary:
  `/Users/jp/.codex/local-only/turbo-mode-refresh/plan04-live-commit-safe-20260506-005230/commit-safe.candidate.summary.json`
- Local-only final commit-safe summary:
  `/Users/jp/.codex/local-only/turbo-mode-refresh/plan04-live-commit-safe-20260506-005230/commit-safe.final.summary.json`
- Repo-local commit-safe summary:
  `plugins/turbo-mode/evidence/refresh/plan04-live-commit-safe-20260506-005230.summary.json`
- Commit-safe summary SHA256:
  `7d9e4541a01a64d60749dde8fd145becc9c7ea26bda6be77e8dedc8bf5f30071`
- Metadata validator summary SHA256:
  `fd994edabc2c3ab0dd330233513a78bc6b86d1dc84652c42a6076e3a825a593e`
- Redaction validator summary SHA256:
  `20e73afb5f296b3d33d38945187f010894ba9e5456cfa5dd20f45495bdb005fb`
- Commit-safe summary `repo_head`:
  `ef8dcd945661115508a94bce337a6b99422a053a`
- Commit-safe summary `repo_tree`:
  `620d6538e5ec82cc999b7ffd873589e688be0a90`
- Final terminal status: `coverage-gap-blocked`
- App-server inventory status: `collected`
- The local-only final summary and repo-local published summary were verified
  byte-for-byte identical before the evidence/docs commit.

Replay commands from the source implementation commit:

The original feature branch was deleted after merge. Replay from the published
state starts and restores to `main`, then detaches only for the source-bound
validator commands.

```bash
git switch main
git rev-parse HEAD
git switch --detach ef8dcd945661115508a94bce337a6b99422a053a
mkdir /private/tmp/plan04-live-commit-safe-20260506-005230-redaction-replay
chmod 700 /private/tmp/plan04-live-commit-safe-20260506-005230-redaction-replay
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_validate_run_metadata.py \
  --mode final \
  --run-id plan04-live-commit-safe-20260506-005230 \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --local-only-root /Users/jp/.codex/local-only/turbo-mode-refresh/plan04-live-commit-safe-20260506-005230 \
  --summary /Users/jp/.codex/local-only/turbo-mode-refresh/plan04-live-commit-safe-20260506-005230/commit-safe.final.summary.json \
  --published-summary-path /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/evidence/refresh/plan04-live-commit-safe-20260506-005230.summary.json \
  --candidate-summary /Users/jp/.codex/local-only/turbo-mode-refresh/plan04-live-commit-safe-20260506-005230/commit-safe.candidate.summary.json \
  --existing-validation-summary /Users/jp/.codex/local-only/turbo-mode-refresh/plan04-live-commit-safe-20260506-005230/metadata-validation.summary.json
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache python3 \
  plugins/turbo-mode/tools/refresh_validate_redaction.py \
  --mode final \
  --run-id plan04-live-commit-safe-20260506-005230 \
  --repo-root /Users/jp/Projects/active/codex-tool-dev \
  --scope commit-safe-summary \
  --source plan-04-cli \
  --summary /Users/jp/.codex/local-only/turbo-mode-refresh/plan04-live-commit-safe-20260506-005230/commit-safe.final.summary.json \
  --local-only-root /Users/jp/.codex/local-only/turbo-mode-refresh/plan04-live-commit-safe-20260506-005230 \
  --published-summary-path /Users/jp/Projects/active/codex-tool-dev/plugins/turbo-mode/evidence/refresh/plan04-live-commit-safe-20260506-005230.summary.json \
  --candidate-summary /Users/jp/.codex/local-only/turbo-mode-refresh/plan04-live-commit-safe-20260506-005230/commit-safe.candidate.summary.json \
  --existing-validation-summary /Users/jp/.codex/local-only/turbo-mode-refresh/plan04-live-commit-safe-20260506-005230/redaction.summary.json \
  --final-scan-output /private/tmp/plan04-live-commit-safe-20260506-005230-redaction-replay/redaction-final-scan.summary.json
git switch main
```

Replay boundary:

- Replay is source-commit-bound and live-environment-bound.
- Replay depends on checking out
  `ef8dcd945661115508a94bce337a6b99422a053a`.
- Replay depends on retaining
  `/Users/jp/.codex/local-only/turbo-mode-refresh/plan04-live-commit-safe-20260506-005230/`.
- The final redaction replay writes a new local-only scan summary with exclusive
  creation. Its parent directory must already exist with mode `0700`, and the
  `--final-scan-output` path itself must not already exist.
- Replay also depends on preserving or reproducibly restoring installed cache
  manifests, local config metadata, repo marketplace metadata, Codex executable
  identity, accepted app-server response schema, and app-server read-only
  inventory behavior.
- If any of those external inputs drift, replay may fail even when the committed
  summary blob remains byte-for-byte identical to the validated local-only final
  summary.

Scope boundary:

- Mutation remains outside Plan 04.
- Plan 04 does not implement `--refresh`, `--guarded-refresh`,
  app-server `plugin/install`, hook execution proof, process quiescence, locks,
  rollback, recovery, or post-refresh certification.
- `coverage-gap-blocked` is an honest non-green live state, not refresh-ready
  status.

## Stop Conditions

Stop before implementation or commit if any of these occur:

- implementation is still on `main` after Task 0;
- generated residue appears and the operator has not approved cleanup;
- live `HEAD` moves unexpectedly during implementation;
- live `--record-summary` smoke is attempted before the source implementation commit exists;
- implementation discovers another source-spec conflict but does not first patch `## Plan 04 Spec Amendment: Non-Mutating Schema Subset`;
- generated commit-safe evidence is staged into the source implementation commit;
- implementation source changes after the source implementation commit and before the evidence/docs commit;
- completion evidence attempts to contain the evidence/docs commit's own final hash or tree hash;
- candidate commit-safe summary is written directly to the repo-local final summary path;
- `--summary-output` can write outside `plugins/turbo-mode/evidence/refresh/`, follow a symlink, or overwrite an existing path;
- a failed validator run leaves a file at the repo-local final summary path;
- relevant dirty source, marketplace, or refresh-tool files exist before `--record-summary`;
- `--record-summary` requires raw transcript content to satisfy a test;
- commit-safe summary needs config contents, process listing contents, or app-server request/response bodies;
- commit-safe summary contains raw `app_server_inventory_failure_reason` instead of an allowlisted reason code;
- commit-safe summary contains local-only free-form `reasons` under `axes`, `runtime_config`, or `diff_classification`;
- runtime config plugin enablement keys are normalized away from live config plugin ids `handoff@turbo-mode` and `ticket@turbo-mode`;
- commit-safe summary can hide transcript-like, config-like, path-heavy, or response-shaped data under any allowed nested object;
- local-only sensitivity scanning is skipped, cannot read expected local-only artifacts, or writes findings into the commit-safe summary;
- final-mode local-only sensitivity scanning does not write `redaction-final-scan.summary.json`;
- candidate redaction writes `status = "passed"` before validating its own summary payload;
- validator summary writers create missing local-only parent directories or accept parent directories that are not mode `0700`;
- metadata validation cannot reconstruct the commit-safe projection from the paired local-only summary;
- metadata validation does not exact-match commit-safe schema/version, source schema, dirty-state policy, dirty-state payload, tool path, and local-only evidence root;
- metadata validation cannot recompute current-run identity from source/cache/config/runtime inputs;
- collected app-server inventory validation cannot prove top-level runtime identity fields match the live runtime identity inside `current_run_identity`;
- redaction validation does not enforce `reason_codes`, `reason_count`, unavailable-reason, and inventory-failure-code allowlists by value;
- the repo-local published summary SHA256 differs from the local-only `commit-safe.final.summary.json` SHA256 before the evidence/docs commit;
- `git show HEAD:plugins/turbo-mode/evidence/refresh/<run>.summary.json` differs from the validated local-only final summary SHA256 after the evidence/docs commit;
- validator summaries need to be rewritten after final summary digest fields are populated;
- validator logic starts importing migration constants;
- implementation attempts to make `--refresh` or `--guarded-refresh` executable;
- terminal live status is described as green while the tool reports `coverage-gap-blocked`;
- ignored active handoff files outside `.session-state/` or `archive/` are present at closeout.

## Self-Review Checklist

- [ ] The plan preserves source/cache, runtime inventory, local config, terminal status, and evidence-validation facts as separate axes.
- [ ] The plan does not authorize installed-cache or global-config mutation.
- [ ] The plan does not treat local-only raw evidence as commit-safe.
- [ ] The plan records mutation-only artifacts as omitted with reasons, not empty success objects.
- [ ] Commit-safe summaries are rejected when relevant source, marketplace, or refresh-tool paths are dirty.
- [ ] Metadata validation compares a deterministic projection from the paired local-only summary.
- [ ] Metadata validation verifies local-only summary identity and current-run source/cache/config/runtime digests, not projection consistency alone.
- [ ] Metadata validation exact-matches commit-safe schema/version, source schema, dirty-state policy, recomputed dirty-state payload, tool path, and local-only evidence root.
- [ ] Requested-failed app-server inventory evidence is reduced to allowlisted reason codes and cannot leak raw response/request bodies.
- [ ] `runtime_config.plugin_enablement_state` uses live config plugin ids `handoff@turbo-mode` and `ticket@turbo-mode`, not marketplace names.
- [ ] `axes`, `runtime_config`, and `diff_classification` are explicit sanitized projections and do not copy local-only `reasons` strings.
- [ ] Every allowed nested object has a structural schema allowlist, including `current_run_identity`, runtime identity, server info, protocol capabilities, dirty state, and omission reasons.
- [ ] Redaction validation enforces field-specific value rules for server info, capabilities, dirty paths, canonical paths, request methods, local-only root, executable path, config-looking strings, and broad absolute paths.
- [ ] Redaction validation enforces `reason_codes`, `reason_count`, unavailable-reason, and inventory-failure-code value allowlists, not only nested key shapes.
- [ ] Local-only sensitivity scanning runs before publish and records findings only in local-only validator summaries.
- [ ] Local-only sensitivity scanning has explicit expected artifact sets for candidate and final phases and fails on missing or unreadable expected artifacts.
- [ ] Final-mode local-only sensitivity scanning writes a durable `redaction-final-scan.summary.json` without rewriting candidate `redaction.summary.json`.
- [ ] Candidate redaction validates its own summary before writing a `status = "passed"` artifact.
- [ ] Validator summary writers require existing `0700` local-only parent directories and write summary files with `0600`.
- [ ] Metadata validation rejects stale top-level runtime identity fields by comparing them to live `current_run_identity.runtime_identity` for collected inventory.
- [ ] Redaction validation uses a schema allowlist plus recursive sensitive-value scanning.
- [ ] Validator digest bootstrap records the raw candidate-summary digest and the projected-payload digest without a rewrite loop.
- [ ] Live evidence is bound to the source implementation commit, while generated evidence/docs are committed separately.
- [ ] The evidence/docs commit proves the committed summary blob SHA256 matches the validated local-only final summary SHA256.
- [ ] Closeout states that replay depends on the source implementation commit, retained local-only run directory, and unchanged or reproducibly restored installed cache, local config metadata, marketplace metadata, Codex executable identity, accepted response schema, and app-server read-only inventory behavior.
- [ ] The evidence/docs commit identity is reported after that commit exists, not embedded self-referentially in the same commit.
- [ ] Commit-safe summary publication is transactional: no repo-local final file exists unless validation passed.
- [ ] `--summary-output` is constrained to a non-existing path under the repo evidence root.
- [ ] Completion evidence includes source-commit replay commands for metadata and redaction validation.
- [ ] Validator scripts are refresh-specific and do not import source-migration constants.
- [ ] Verification includes tests, ruff, residue scan, and a live non-mutating smoke.

# Ticket Contract v1.0

Single source of truth for the ticket plugin. All components (skills, agents, engine) reference this contract.

## 1. Storage

- Active tickets: `docs/tickets/`
- Archived tickets: `docs/tickets/closed-tickets/`
- Audit trail: `docs/tickets/.audit/YYYY-MM-DD/<session_id>.jsonl`
- Path boundary: hook payload files and all CLI `tickets_dir` arguments must resolve inside workspace/project root
- tickets_dir resolution: CLI entrypoints resolve tickets_dir against a marker-based project root (nearest ancestor containing .codex/ or .git/), not against cwd. Root discovery starts from a resolved path, so symlinked cwd values are canonicalized before marker lookup. Explicit tickets_dir must resolve inside the project root. If no project root is found, the operation is rejected (policy_blocked).
- Naming: `YYYY-MM-DD-<slug>.md`
- Slug: first 6 words of title, kebab-case, `[a-z0-9-]` only, max 60 chars, sequence suffix on collision
- Bootstrap: missing `docs/tickets/` → empty result for reads; create on first write

## 2. ID Allocation

- Format: `T-YYYYMMDD-NN` (date + 2-digit daily sequence, zero-padded)
- Overflow: sequence widens past 2 digits after 99 (e.g., T-20260310-100). Minimum width is 2.
- Collision prevention: scan existing tickets for same-day IDs, allocate next NN
- Legacy IDs preserved permanently: `T-NNN` (Gen 3), `T-[A-F]` (Gen 2), slugs (Gen 1)

## 3. Schema

### Required YAML Fields

| Field | Type | Description |
|-------|------|-------------|
| `id` | string | Ticket ID (T-YYYYMMDD-NN or legacy) |
| `date` | string | Creation date (YYYY-MM-DD) |
| `status` | string | One of: open, in_progress, blocked, done, wontfix |
| `priority` | string | One of: critical, high, medium, low |
| `source` | object | `{type: string, ref: string, session: string}` |
| `contract_version` | string | "1.0" |

### Optional YAML Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `effort` | string | "" | Estimate (XS, S, M, L, XL or free text) |
| `tags` | list[string] | [] | Categorization tags |
| `blocked_by` | list[string] | [] | IDs of blocking tickets |
| `blocks` | list[string] | [] | IDs of tickets this blocks |
| `defer` | object | null | `{active: bool, reason: string, deferred_at: string}` |
| `key_file_paths` | list[string] | [] | File paths for dedup fingerprinting (persisted on create) |
| `created_at` | string | "" | ISO 8601 UTC creation timestamp (engine-written, never caller-set) |
| `capture_confidence` | string | "" | Capture quality hint: low, medium, or high |
| `capture_source` | string | "" | Capture provenance, e.g. `conversation` |
| `refinement_status` | string | "" | Optional placeholder-quality marker; only `needs_refinement` is valid |
| `component` | string | "" | Optional user-facing subsystem/component label |
| `related_paths` | list[string] | [] | Optional paths mentioned by the captured work |

### Section Guidance

Recommended core sections: Problem, Approach, Acceptance Criteria, Verification, Key Files

Runtime note (v1.0): missing sections are advisory warnings/process failures, not hard runtime schema rejections.
Runtime note (v1.0): `update` mutates YAML frontmatter only. Section-backed fields are not writable through the `update` action.
Capture-created tickets support these body sections: Captured Request, Problem, Next Action, Acceptance Criteria.
Capture metadata never stores a raw user wording field; the rendered Captured Request section is a synthesized ticket section, not schema provenance.

### Optional Sections

Captured Request, Next Action, Context, Prior Investigation, Decisions Made, Related, Reopen History

### Section Ordering

Captured Request → Problem → Next Action → Context → Prior Investigation → Approach → Decisions Made → Acceptance Criteria → Verification → Key Files → Related → Reopen History

### Capture Refinement Semantics

- `needs_refinement` is metadata, not a lifecycle status. Placeholder-quality tickets keep `status: open`.
- `Acceptance Criteria: Needs refinement` is allowed only when `refinement_status: needs_refinement` is set.
- A ticket cannot transition to `done` while `refinement_status: needs_refinement` remains set.
- A ticket cannot transition to `done` when the only acceptance criterion is `Needs refinement`, even if the metadata was already cleared.
- Close/readiness reports the precondition as `missing_acceptance_criteria` with the message `Transition to 'done' requires concrete acceptance criteria; ticket still needs refinement`.
- Controlled auto-tags are `needs-refinement`, `bug`, `feature`, `docs`, `test`, `maintenance`, and `security`. These are not the only globally valid tags; the special coupling is that `needs-refinement` requires `refinement_status: needs_refinement`.

## 4. Engine Interface

Canonical script launcher: `uv run python -B <PLUGIN_ROOT>/scripts/<script>.py ...`.
Hook acceptance of `python3` launchers is legacy compatibility only, not the
public contract.

Common response envelope: `{state: string, ticket_id: string|null, message: string, data: object}`

Exit codes: 0 (success), 1 (engine error), 2 (validation failure)
- Error responses include `error_code` at the top level (one of the 12 defined error codes below). Success responses omit `error_code`.
- Exit code 2 maps only to the `need_fields` error code. `invalid_transition` and `parse_error` return exit 1 (engine error); `parse_error` covers both malformed CLI payloads and corrupted stored ticket YAML.

### Supported Mutation Surfaces

Ticket has exactly three supported high-level mutation surfaces: `capture`, `update`, and `ingest`. `capture` and `update` use their preview-first prepare/execute wrappers. `ingest` uses the guarded engine entrypoints to consume a DeferredWorkEnvelope from `docs/tickets/.envelopes/<filename>.json`. Direct engine `classify`/`plan`/`preflight`/`execute` and `ticket_workflow.py prepare`/`execute` remain low-level compatibility, debug, and agent-internal paths. They are not normal user-facing mutation interfaces and must not be documented as the preferred way to create or mutate tickets.

### Recovery Hints

User-facing mutation and recovery surfaces may include `data.recovery_hint`.
When present, it is safe to show directly to a human user. The schema is:

```json
{"code": "stale_plan", "summary": "One user-safe sentence.", "next_step": "One concrete recovery action."}
```

Valid codes are `stale_plan`, `trust_setup`, `retry_preview`,
`cleanup_stale_preview`, `policy_blocked`, `preflight_failed`,
`host_policy_blocked`, `deterministic_driver_unavailable`,
`hook_contract_blocked`, `engine_gate_required`, `runtime_readiness_required`,
`internal_error`, `proof_invalid`, and `stale_proof`.
Low-level direct engine/debug surfaces may remain technical unless their output
bubbles into a user-facing wrapper.

The whole object is transcript-safe. Do not add recovery hint codes that contain
hidden implementation mechanics. `plugin hook setup` is allowed as setup-level
recovery wording for `trust_setup`; hook/provenance field names and command
repair instructions remain internal.

Ingest stdout is a machine-readable JSON envelope. Skills and transcript-facing
workflows must parse it and render only the allowlisted projection: recovery
summary, recovery next step, safe message, ticket ID, duplicate candidate ticket
ID, and user-safe ingest outcome prose. Raw `data` fields such as processed
paths, incoming envelope paths, and envelope provenance are not transcript
fields.

### Subcommands

| Subcommand | Input | Output `data` |
|-----------|-------|---------------|
| classify | action, args, session_id, request_origin | intent, confidence, classify_intent, classify_confidence, resolved_ticket_id |
| plan | intent, fields (including `key_file_paths: list[str]` for dedup), session_id, request_origin | dedup_fingerprint, target_fingerprint, duplicate_of, missing_fields, action_plan |
| preflight | ticket_id, action, optional `fields`, session_id, request_origin, classify_confidence, classify_intent, dedup_fingerprint, target_fingerprint | checks_passed, checks_failed |
| execute | action, ticket_id, fields (including `key_files: list[dict]` for rendering), session_id, request_origin, dedup_override, dependency_override, optional `target_fingerprint` | ticket_path, changes |

**Field disambiguation:**
- `key_file_paths: list[str]` — file paths for dedup fingerprinting only (plan subcommand input)
- `key_files: list[dict[str, str]]` — structured table rows `{file, role, look_for}` for rendering (execute subcommand input)
- If both are present in input, `key_file_paths` is used for dedup. `key_files` is always used for rendering.
- If `key_files` is omitted, create still succeeds but no `## Key Files` section is rendered.
- `fields` in preflight is used for resolution-aware policy checks (for example close `resolution=wontfix` bypasses blocker checks).

The `archive` field in execute close requests controls whether the ticket file is moved to `closed-tickets/`. When `archive: true` and close succeeds, the state is `ok_close_archived` instead of `ok_close`.

### Workflow runner

`ticket_workflow.py prepare`, `ticket_workflow.py execute`, and
`ticket_workflow.py recover` are UX orchestration commands. The workflow runner
does not replace the engine interface. Prepare and execute dispatch through the
same stage-model boundary as `ticket_engine_runner.py`; recover only patches the
payload for supported user-selected recovery actions. Execute keeps the same
provenance requirements: `hook_injected=true`, recorded `hook_request_origin`,
and non-empty `session_id`. Activation readiness does not treat
`hook_request_origin` as caller-identity proof.

### Machine States (15 total: 14 emittable, 1 reserved)

ok, ok_create, ok_update, ok_close, ok_close_archived, ok_reopen, need_fields, duplicate_candidate, preflight_failed, policy_blocked, invalid_transition, dependency_blocked, not_found, escalate, merge_into_existing (reserved)

### Core Engine Error Codes (13)

`need_fields`, `invalid_transition`, `policy_blocked`, `preflight_failed`, `stale_plan`, `duplicate_candidate`, `parse_error`, `io_error`, `internal_error`, `not_found`, `dependency_blocked`, `intent_mismatch`, `origin_mismatch`

### Runtime Readiness Error Codes

Runtime proof verification uses a separate fail-closed code set:

`proof_missing`, `proof_invalid`, `stale_proof`, `nonce_mismatch`, `invalid_scope`,
`executing_root_mismatch`, `plugin_manifest_path_mismatch`,
`plugin_manifest_hash_mismatch`, `hook_manifest_path_mismatch`,
`hook_manifest_hash_mismatch`, `guard_script_path_mismatch`,
`guard_script_hash_mismatch`, `inventory_transcript_hash_mismatch`,
`hook_transcript_hash_mismatch`, `post_activation_transcript_hash_mismatch`,
`payload_hash_mismatch`, `engine_stdout_hash_mismatch`, `raw_evidence_missing`.

### Activation Driver Error Codes

Runtime activation driver failures use:

`host_policy_blocked`, `deterministic_driver_unavailable`, `hook_contract_blocked`,
`engine_gate_required`, `runtime_readiness_required`.

## 5. Autonomy Model

Modes: suggest (default), auto_audit, auto_silent (v1.1 only)

Config: `.codex/ticket.local.md` YAML frontmatter

`request_origin`: "user" (ticket_engine_user.py), "agent" (ticket_engine_agent.py), "unknown" (fail closed)

Current Codex `PreToolUse` input does not expose a stable spawned-agent
identity signal Ticket can certify. `hook_request_origin` is hook-observed
provenance metadata, and entrypoint choice selects the policy lane rather than
proving caller identity.

Hook candidate detection: the guard tokenizes Bash commands with `shlex` and treats Python invocations targeting any `ticket_*.py` basename as ticket candidates. Only canonical plugin-root entrypoints are allowlisted; non-canonical, wrapped, or unknown ticket script invocations are denied. Non-ticket Python commands pass through.

Execute provenance: execute requires verified hook provenance
(`hook_injected=True`, recorded `hook_request_origin`, non-empty session_id) for
all mutations, both user and agent. For the certified direct-execute lane,
`hook_request_origin` remains provenance metadata and the current host may still
report `"user"` even when `ticket_engine_agent.py execute` selected the agent
policy lane. Non-execute stages (classify, plan, preflight) remain directly
runnable without hook metadata. Agent preflight requires session_id for
accurate create-cap simulation but does not require hook_injected.

Execute prerequisites: execute requires prior-stage artifacts:
- classify_intent (must match action)
- classify_confidence (must meet origin-specific threshold: 0.5 for user, 0.65 for agent)
- dedup_fingerprint (create only, must match recomputed value from current fields)
- target_fingerprint (non-create, mandatory — validates ticket unchanged since read)
- autonomy_config (agent only, snapshot from preflight)

Stage-specific missing-confidence behavior: preflight entrypoints coerce absent `classify_confidence` to `0.0` and fail the confidence gate; execute preserves absence as `null` and rejects it as a missing prerequisite.

Agent execute re-reads live `.codex/ticket.local.md` policy and blocks if it diverges from the preflight snapshot.

Activation V1 certifies only `ticket_engine_agent.py execute`. Activation V1
proves installed hook-mediated direct-execute wiring, not host-owned or
spawned-agent identity. `hook_request_origin` is hook-observed provenance
metadata on the current host and may still be reported as `"user"` for the
certified direct-execute lane. `capture`, `update`, and `ticket_workflow.py`
remain outside the activation proof scope alongside `ingest_dispatch` and
`activation_smoke_bootstrap`, and require a separate follow-up before widening
certification. Privileged host diagnostic runs and prompt-driven smokes are
diagnostics only. AgentControl child smoke, when captured, is same-membrane
corroboration only and not identity proof. Normal agent direct execute fails
with `runtime_readiness_required` when the runtime proof is missing, stale, or
mismatched.

Field validation: title, problem, reopen_reason, captured_request, next_action, capture_source, and component must be strings when present. priority, status, resolution, capture_confidence, and refinement_status are validated against contract enums before writes. key_file_paths, related_paths, tags, blocked_by, blocks, and acceptance_criteria must be lists of strings. source must be a dict with string values. key_files must be a list of dicts. defer must be a dict. Invalid inputs are rejected (need_fields), not silently coerced.

Renderer invariant: `acceptance_criteria` is create-time `list[string]` input only. Bare strings are rejected before rendering and are not coerced into a single checklist item.

Known limitation (v1.3): create now uses exclusive file creation with bounded retry to prevent same-path silent overwrite, but concurrent autonomous creates are still not fully serialized. Session create cap enforcement and ID allocation are not lock-based, so parallel subagent execution is not a hard safety boundary.

## 6. Dedup Policy

Fingerprint: `sha256(normalize(problem_text) + "|" + sorted(key_file_paths))`

`normalize()` steps: (1) strip, (2) collapse whitespace, (3) lowercase, (4) remove punctuation except hyphens/underscores, (5) NFC Unicode normalization

Window: 24 hours. Override: `dedup_override: true` with `duplicate_of` identifying the specific duplicate candidate ID.

Defense-in-depth: execute stage repeats duplicate checks for create requests to prevent bypass via direct execute calls.

### Test Vectors

| Input | Expected Normalized |
|-------|-------------------|
| `"  Hello,  World!  "` | `"hello world"` |
| `"Fix: the AUTH bug..."` | `"fix the auth bug"` |
| `"résumé"` | `"résumé"` (NFC) |
| `"  multiple   spaces  \n  newlines  "` | `"multiple spaces newlines"` |
| `"keep-hyphens and_underscores"` | `"keep-hyphens and_underscores"` |

## 7. Status Transitions

| From | To | Preconditions |
|------|----|---------------|
| open | in_progress | none |
| open | blocked | blocked_by non-empty |
| in_progress | open | none |
| in_progress | blocked | blocked_by non-empty |
| in_progress | done | acceptance criteria present; no `refinement_status: needs_refinement`; criteria are concrete |
| blocked | open | all blocked_by resolved (done or wontfix) |
| blocked | in_progress | all blocked_by resolved |
| * | wontfix | none |
| done | open | reopen_reason required, user-only v1.0 |
| wontfix | open | reopen_reason required, user-only v1.0 |

Non-status edits on terminal tickets (done/wontfix) are allowed without reopening.
Missing blocker references are invalid and are not treated as resolved.

### Status Normalization (Legacy)

| Raw | Canonical |
|-----|-----------|
| planning | open |
| implementing | in_progress |
| complete | done |
| closed | done |
| deferred | open (with defer.active: true) |

## 8. Migration

Read-only for legacy formats. Conversion on update (with user confirmation).

### Legacy Generations

| Gen | ID Pattern | Section Renames |
|-----|-----------|----------------|
| 1 | slug | Summary→Problem |
| 2 | T-[A-F] | Summary→Problem |
| 3 | T-NNN | Summary→Problem, Findings→Prior Investigation |
| 4 | T-YYYYMMDD-NN | Proposed Approach→Approach, provenance→source |

### Field Defaults (applied on read)

| Missing Field | Default |
|--------------|---------|
| priority | medium |
| source | {type: "legacy", ref: "", session: ""} |
| effort | "" |
| tags | [] |
| blocked_by/blocks | [] |

## 9. Integration

External consumers read `docs/tickets/*.md` as plain markdown with fenced YAML.
Format uses fenced YAML (```yaml), not YAML frontmatter (---).

## 10. Versioning

`contract_version` in fenced YAML block. Current: "1.0".
Engine reads all versions; writes latest only.

## 11. DeferredWorkEnvelope Schema (v1.0)

Bridge format for deferred work items from the handoff plugin. Envelopes are JSON files consumed by the ticket engine to create deferred tickets.

For v1.0, the envelope id is the envelope filename under `docs/tickets/.envelopes/`. Ticket owns this input contract and uses that id for idempotency.

### Storage

- Incoming: `docs/tickets/.envelopes/<timestamp>-<slug>.json`
- Processed: `docs/tickets/.envelopes/.processed/<filename>`
- Retention: Processed envelopes are retained indefinitely for now as the idempotency ledger and cross-plugin audit trail.

### Required Fields

| Field | Type | Description |
|-------|------|-------------|
| `envelope_version` | string | Must be "1.0" |
| `title` | string | Ticket title |
| `problem` | string | Problem description |
| `source` | object | `{type: string, ref: string, session: string}` |
| `emitted_at` | string | ISO 8601 UTC timestamp when envelope was created |

### Optional Fields

| Field | Type | Default | Description |
|-------|------|---------|-------------|
| `context` | string | "" | Context section content |
| `prior_investigation` | string | "" | Prior investigation section content |
| `approach` | string | "" | Approach section content |
| `acceptance_criteria` | list[string] | [] | Acceptance criteria items |
| `verification` | string | "" | Verification command |
| `key_files` | list[object] | [] | `{file, role, look_for}` table rows |
| `key_file_paths` | list[string] | [] | File paths for dedup fingerprinting |
| `suggested_priority` | string | "medium" | One of: critical, high, medium, low |
| `suggested_tags` | list[string] | [] | Categorization tags |
| `effort` | string | "S" | Effort estimate (freeform) |

### Consumer Behavior

The ticket engine's envelope consumer:
1. Reads and validates the JSON against this schema
2. Maps fields to engine create vocabulary (no `status` — consumer synthesizes `open` with `defer.active: true`)
3. Sets `defer.reason` to `"deferred via envelope"` and `defer.deferred_at` to `emitted_at`
4. Creates ticket through the normal engine pipeline
5. Moves consumed envelope to `.processed/`

Before creating a ticket, ingest checks whether `.processed/<filename>` already exists. If it does, ingest returns a duplicate/replay outcome, preserves the incoming envelope, and creates no ticket. Similar-content envelopes with different filenames go through normal duplicate detection and are not auto-collapsed.

### Invariants

- Envelopes carry no `status` field — the consumer is the sole authority for initial ticket state
- `emitted_at` is required for provenance — it becomes `defer.deferred_at`
- Unknown fields are rejected (closed schema)

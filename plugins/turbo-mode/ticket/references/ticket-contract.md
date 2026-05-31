# Ticket Contract v1.0

Current source-facing reference for the Ticket plugin. ADR 0006 and the May 30
control doc supersede this reference where they conflict.

## Authority Boundary

ADR 0006 is the accepted architecture authority for the Ticket runtime-first
state-kernel rebaseline. The May 30 control doc is the implementation and
cutover control surface. This contract is source-authority documentation, not
installed-runtime proof and not runtime proof. Source edits here do not prove
installed Codex behavior; installed cache, `hooks/list`, `skills/list`, and
live runtime inventory require a separate cache-refresh or runtime-proof lane.
The cache-installed runtime authority is the proof target; a synced personal
plugin copy is staging only, not the proof target. This docs/tests slice does
not perform cutover inventory or normalization and does not mutate
`docs/tickets/`.

Durable runtime modes are `agent_primary` and `discussion_only`.

## Target Post-Cutover Ticket Shape

Post-cutover active tickets use ID-only filenames under
`docs/tickets/T-YYYYMMDD-NN.md`. Ticket content uses YAML frontmatter, followed
by Markdown sections. Closed YAML frontmatter keys are `id`, `title`, `status`,
`priority`, `tags`, `related_paths`, and `blocked_by`.

Target statuses are `open`, `in_progress`, `done`, and `wontfix`. Target
priorities are `high`, `normal`, and `low`. Required sections are `Problem`,
`Next Action`, and `Change History`. Unknown frontmatter keys are invalid.
`blocked` is not a status; blockedness derives from `blocked_by`. Store
`blocked_by` only and derive reverse `blocks` views by scanning tickets.

## Target Candidate Mutation Contract

Ticket accepts one target candidate mutation at a time. The candidate fields
are `action`, `ticket_id`, `target.fields`, `target.sections`,
`proposed_change`, `expected_ticket_fingerprint`, and `evidence_summary`.

`target.fields` and `target.sections` name the exact frontmatter fields or
Markdown sections the candidate proposes to change. `proposed_change` may
contain only those named targets. non-create writes require an expected ticket
fingerprint. Ticket computes candidate identity from canonical candidate
content plus the live target fingerprint; callers do not supply authoritative
identity values. Unknown fields are invalid.

## Target Result Envelope

Target mutation results use only these mechanical states: `ok`, `blocked`,
`needs_discussion`, `invalid_state`, and `no_change`.

Human-facing context belongs in the message and structured facts such as ticket
ID, validation detail, candidate identity, discussion prompt facts, and
post-write fingerprint.

## Target Change History Grammar

Target `Change History` entries use deterministic prose:

```markdown
- <timestamp> | <actor> | <reason>
- <timestamp> | <actor> | <reason> Corrects: <reference>.
```

The actor is a source value such as `codex`, `user-approved`, or `migration`.
The actor is not a workflow label and must not encode action type. `Corrects:
<reference>` is optional.

## Deprecated Source Drift

Deprecated source drift may mention old four-stage, prepare/execute, or
persistent `preview` behavior only as non-target implementation debt. These
surfaces are subordinate to ADR 0006 and the May 30 control doc.

The host-facing autonomy CLI, `direct_execute`, `gateway_required`,
`stale_plan`, `toctou_conflict`, direct `ticket_engine_agent.py execute`, and
the Workflow runner are deprecated or diagnostic source facts, not target
product architecture.

Direct `ticket_engine_agent.py execute` is not an autonomous mutation route in
this source slice. It fails closed with `gateway_required`.

`ticket_autonomy.py apply-turn` and source bookkeeping such as
`.codex/ticket-workspace/ticket.pending-summary.jsonl` are diagnostic source
state here, not target ticket content.

## Legacy Cutover Input

Legacy ticket records may still contain fenced YAML, slug filenames, old
statuses, old priorities, historical fields, and noncanonical sections. Those
records are input to a future read-only cutover inventory and later reviewed
normalization. This contract does not perform that inventory.

## Historical Changelog

Older release notes may describe prior Ticket behavior. Treat those entries as
historical changelog context rather than current authority.

## Maintenance And Diagnostics

Maintenance and diagnostics may use explicit source/cache/runtime probes,
historical audit repair, stale payload cleanup, runtime activation, diagnostic
dry-run or `preview` evidence, and exit-code mapping. They do not define normal
target ticket mutation.

Use `uv run python -B <PLUGIN_ROOT>/scripts/<script>.py ...` for documented
source commands. Any remaining `python3` hook acceptance is legacy
compatibility.

Existing `docs/tickets/.audit/` files are historical artifacts. Recovery hints
such as `data.recovery_hint`, `retry_preview`, `cleanup_stale_preview`, and
`engine_gate_required` are maintenance or deprecated wrapper details, not target
result states.

Exit code diagnostics remain source-maintenance facts. Do not treat old
machine-state or code sets as target authority.

## 1. Storage

- Active tickets: `docs/tickets/`
- Archived tickets: `docs/tickets/closed-tickets/`
- Future autonomous durable history writes to `## Change History` on each
  affected ticket.
- Future local operational state writes to
  `.codex/ticket-workspace/ticket.pending-summary.jsonl`.
- Existing `docs/tickets/.audit/` files are historical artifacts. Future
  `.audit/` writes are disabled; autonomous Ticket durable history must not
  write there unless a later migration explicitly changes this contract.
  `ticket_audit.py` and `ticket_doctor.py repair-audit` are read/repair tools
  for existing historical `.audit/` files only.
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

Autonomous runtime requirement: `## Change History` is required for tickets
created or mutated by the autonomous Ticket flow.
Runtime note (v1.0): missing sections are advisory warnings/process failures,
not hard runtime schema rejections, except that autonomous mutation must fail
closed when `## Change History` cannot carry its required durable fact.
Historical tickets missing `## Change History` are bootstrapped only through the
explicit maintenance command `ticket_autonomy.py migrate-change-history
--dry-run|--apply`. `--dry-run` is non-mutating. `--apply` inserts missing
empty sections only; it does not add entries and does not write the current
commit hash.
Runtime note (v1.0): `update` mutates YAML frontmatter only. Section-backed fields are not writable through the `update` action.
Capture-created tickets support these body sections: Captured Request, Problem, Next Action, Acceptance Criteria.
Capture metadata never stores a raw user wording field; the rendered Captured Request section is a synthesized ticket section, not schema provenance.

### Optional Sections

Captured Request, Next Action, Context, Prior Investigation, Decisions Made, Related, Reopen History

### Section Ordering

Captured Request → Problem → Next Action → Context → Prior Investigation → Approach → Decisions Made → Acceptance Criteria → Verification → Key Files → Related → Change History → Reopen History

### Change History

`## Change History` is a required ticket-owned section for durable lightweight
history facts in the autonomous Ticket contract. Use it for compact entries
that should remain with the ticket, including automatic Ticket updates and
approved corrections.

Entry format:

```markdown
- <timestamp> | <label> | <reason>
- <timestamp> | <label> | <reason> Prior commit: <short-hash>.
```

Rules:

- timestamp is ISO 8601 UTC
- label is one of the controlled labels below
- reason is one short sentence and must not contain raw `|`
- no current commit hash in the same entry
- prior commit hash appears only when referencing an already-created commit is
  genuinely useful
- automatic writers must not create labels outside the controlled set
- unknown labels, compatibility aliases, or ad hoc labels are invalid for new
  automatic entries

Controlled labels:

- `auto-create`: Codex automatically created this ticket for clear follow-up
  work.
- `auto-update`: Codex automatically updated non-lifecycle ticket metadata,
  refinement text, priority, tags, component, or other ordinary fields.
- `auto-blocker`: Codex automatically changed blocker or dependency state.
- `auto-close`: Codex automatically closed the ticket as `done` or `wontfix`.
- `auto-reopen`: Codex automatically reopened the ticket.
- `correction`: Codex corrected or reversed a prior automatic Ticket change.
- `discussion-approved`: Codex applied a change after policy required user
  discussion, such as delete, archive, or history repair. Do not use this label
  for ordinary user-requested Ticket changes that fit an action-specific label.

Keep YAML frontmatter for current ticket metadata, not a growing history log.
Do not store local pending-summary detail or full before/after correction
payloads in `## Change History`.
Do not try to write the containing commit's own hash into the same committed
ticket change. That hash is self-referential and does not exist when the ticket
file is written. The end-of-turn summary may report the created commit hash,
and a later `## Change History` entry may reference an earlier commit hash when
that is genuinely useful.

When an automatic Ticket mutation needs a durable lightweight history fact, the
`## Change History` entry must be written as part of the same ticket-file
mutation. If the automatic flow cannot create or update `## Change History`
cleanly, it must pause or defer the automatic ticket change rather than leave
durable project history incomplete.

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
- Error responses include `error_code` at the top level; public engine responses may emit either core engine or autonomy gate error codes. Success responses omit `error_code`.
- Exit code 2 maps only to the `need_fields` error code. `invalid_transition` and `parse_error` return exit 1 (engine error); `parse_error` covers both malformed CLI payloads and corrupted stored ticket YAML.

### Supported Mutation Surfaces

Ticket has exactly three supported high-level mutation surfaces: `capture`, `update`, and `ingest`. `capture` and `update` use their preview-first prepare/execute wrappers. `ingest` uses the guarded engine entrypoints to consume a DeferredWorkEnvelope from `docs/tickets/.envelopes/<filename>.json`. Direct engine `classify`/`plan`/`preflight`/`execute` and `ticket_workflow.py prepare`/`execute` remain low-level compatibility, debug, and agent-internal paths. They are not normal user-facing mutation interfaces and must not be documented as the preferred way to create or mutate tickets.

### Host-Facing Autonomy Surface

`ticket_autonomy.py pause`, `recover`, `apply-turn`, `doctor-ledger`, and
`migrate-change-history` are the host-facing Ticket autonomy CLI commands.
Ordinary high-level user mutation wrappers remain `capture`, `update`, and
`ingest`. The autonomy CLI does not expose raw ledger mutation commands such as
`append-event`, `consume-approval`, or `mark-summarized`; ledger repair is only
available through `doctor-ledger --confirm-repair`.

`apply-turn --setup-choice` is setup only. If the workspace is paused, the
command must keep returning the paused response unless the host also supplies
`--resume-paused`. The explicit resume path must verify local-state safety and
pending-summary ledger health before clearing the pause marker.

Structured turn-context `candidate_mutations` may include optional
`ticket_change_scope: "current_branch" | "unrelated_backlog"`. Missing or
invalid values normalize to `"current_branch"`. The scope is not ticket content:
it must bind the candidate/gateway mutation fingerprint and the resulting
approval, then flow only to commit disposition. Path-derived and text-derived
candidates always use `"current_branch"`.

Before candidate discovery or new writes, `apply-turn` must compact safe
correction-ready ledger detail and check prior-turn pending-summary recovery
needs. If prior-turn ledger repair is required, it exits 3 with the normal
paused response, `pause_reason: "repair"`, `recoveries`, `repairable_count`,
`reconciliation_count`, and the existing `doctor-ledger --confirm-repair`
discussion question.

`recover` is a projection command. It validates pending-summary state, compacts
old correction-ready detail when safe, reports repairable and reconciliation
counts, and returns `can_proceed: false` whenever prior-turn ledger records need
`doctor-ledger` repair or manual reconciliation before new automatic writes.

`doctor-ledger --dry-run` reports pending-summary health without mutation.
`doctor-ledger --confirm-repair` may append only deterministic recovery events
returned by the Ticket recovery projection. Corrupt/unreadable logs and live
ticket fingerprint mismatches fail closed for manual reconciliation.

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

### Autonomy Gate Error Codes (2)

The autonomy gate code set is: `setup_required`, `gateway_required`.

- `setup_required`: local Ticket automation config is missing or invalid, so automation cannot run.
- `gateway_required`: direct agent writes are blocked; use the runtime-first gateway path instead.

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

Runtime-first modes: `discussion_only`, `preview`, and `agent_primary`.

Config is strict local `.codex/ticket.local.md` JSON:

```json
{"schema":"codex.ticket.local.v1","mode":"agent_primary"}
```

The config file accepts exactly `schema` and `mode`. Missing config, unknown
keys, Markdown, YAML frontmatter, comments, and older mode names are
`setup_required`, not implicit defaults. Guided setup maps `automatic` to
`agent_primary` and `ask_first` to `discussion_only`; `preview` is manual-only
config.

Workspace state lives under ignored `.codex/ticket-workspace/`. Mode snapshots
are scoped to `(project_root, thread_id)`: the first automatic turn in a thread
reads strict config and writes a local snapshot, and later turns reuse that
snapshot even if `.codex/ticket.local.md` changes. `.codex/ticket-workspace/pause.json`
blocks autonomous mode resolution immediately. Production resume requires an
explicit setup choice, removes the pause marker, invalidates project-local mode
snapshots, and rewrites strict JSON config before later automatic writes can run.

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

Direct `ticket_engine_agent.py execute` is not an autonomous mutation route in
the runtime-first design. It fails closed with `gateway_required`. Source
autonomous writes enter through `ticket_autonomy.py apply-turn`, where the
runtime-first gateway validates a gateway-approved decision, writes
ticket-local `## Change History`, and appends pending-summary bookkeeping. This
is a fail-closed source boundary, not installed-runtime proof.

Field validation: title, problem, reopen_reason, captured_request, next_action, capture_source, and component must be strings when present. priority, status, resolution, capture_confidence, and refinement_status are validated against contract enums before writes. key_file_paths, related_paths, tags, blocked_by, blocks, and acceptance_criteria must be lists of strings. source must be a dict with string values. key_files must be a list of dicts. defer must be a dict. Invalid inputs are rejected (need_fields), not silently coerced.

Renderer invariant: `acceptance_criteria` is create-time `list[string]` input only. Bare strings are rejected before rendering and are not coerced into a single checklist item.

Known limitation (v1.3): create now uses exclusive file creation with bounded
retry to prevent same-path silent overwrite. Runtime-first autonomous
serialization belongs to the gateway/pending-summary implementation, not to
legacy direct execute.

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

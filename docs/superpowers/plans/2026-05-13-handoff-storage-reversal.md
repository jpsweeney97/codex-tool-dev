# Handoff Storage Reversal Implementation Control Document

## Status

Draft - patched after scrutiny; pending review before implementation.

This document is the implementation contract for reversing Handoff storage authority from the live source's current `docs/handoffs/` primary policy to `.codex/handoffs/` as the post-cutover write/read target. Until the implementation commit lands, `.codex/handoffs/` is target authority, not current repo truth.

Done means all writers, readers, skill docs, helper scripts, tests, dormant validation helpers or live hooks, refresh classifier logic, refresh smoke, release docs, ignore policy, and stale-text gates move together. A partial reader-only migration is not closeout.

Source implementation remains blocked until this control document is tracked in durable repo history and repo-authority residue policy is recorded without treating machine-local residue as fresh-clone truth. Local implementation execution remains blocked until local preflight evidence enumerates every current `docs/handoffs/handoff-*` residue path with an explicit disposition. Source repair closeout remains blocked until active writer creation is covered by helper APIs and transaction tests. Installed-host certification remains blocked until the host-repo policy matrix below is covered by source-proof installed-plugin smoke.

## Policy Authority Override

This plan is the explicit reviewed artifact required by Plan 06 for changing handoff policy around `docs/handoffs/**`. It names and overrides the instruction conflict for the Handoff plugin storage reversal only.

The conflict is:

- active workspace instructions classify repository handoff files under `docs/handoffs/` and `docs/handoffs/archive/` as durable project artifacts when tracked or intentionally included in durable repo state
- live Handoff `1.6.0` currently uses `docs/handoffs/` for operational session mechanics
- this reversal intentionally moves future Handoff operational session mechanics to `.codex/handoffs/`

This override does not make all `docs/handoffs/**` disposable. The implementation must classify `docs/handoffs/**` into these classes before changing policy or code:

- `tracked-durable-handoff-artifact`: any `git ls-files docs/handoffs` result, or any file explicitly named by a reviewed repo policy as durable. Preserve it; do not delete, untrack, treat it as operational cleanup, or include it in implicit active selection.
- `ignored-legacy-operational-handoff`: ignored active handoff, checkpoint, summary, archive, or state created by the pre-cutover Handoff plugin. Treat it as read-only legacy migration/search/bridge input according to this plan.
- `untracked-legacy-operational-handoff`: untracked `docs/handoffs/*.md` file that validates as a current-contract active handoff, checkpoint, or summary in a host repository where the pre-cutover runtime path was not ignored. Treat it as read-only legacy migration input. This class exists because host tracking policy is not a plugin invariant; valid pre-cutover runtime files must not be stranded merely because the host repo lacked an ignore rule.
- `reviewed-runtime-migration-opt-in`: an exact legacy `docs/handoffs/**` path plus source hash named by a reviewed migration note as safe to treat as runtime migration input. This is the only way a tracked or otherwise durable-looking `docs/handoffs/**` file may enter runtime migration selection.
- `previous-primary-hidden-archive`: historical archive file under `<project_root>/.codex/handoffs/.archive/*.md` from the pre-`docs/handoffs/` storage generation. Treat it as read-only history-search and explicit-path input, copying or reusing a primary archive copy only through the explicit legacy archive transaction path.
- `state-like-residue`: files such as `docs/handoffs/handoff-*.json` or `docs/handoffs/handoff-*` outside `.session-state/`. Inventory them, classify them, and either bridge exactly one valid project state candidate or reject with a diagnostic; never treat them as handoff markdown documents.
- `policy-conflict-artifact`: any artifact whose durable-vs-operational classification is ambiguous. Stop before implementation until it is classified by a reviewed note or plan update.

The intended override is narrow: after cutover, newly written Handoff operational session artifacts go under `.codex/handoffs/`; durable repository documentation under `docs/handoffs/**` remains durable when tracked or intentionally included by repo policy.

Legacy active selection must be class-filtered before timestamp ordering. It may include only `ignored-legacy-operational-handoff`, `untracked-legacy-operational-handoff`, and exact `reviewed-runtime-migration-opt-in` files. It must exclude `tracked-durable-handoff-artifact` and `policy-conflict-artifact` files even when they look like valid current-contract handoff markdown.

## Path Authority

### Current Live Source Before Implementation

This table describes the live source before this plan is implemented.

| Role | Path | Status |
|---|---|---|
| Current active | `<project_root>/docs/handoffs/*.md` | Current live write/read target |
| Current archive | `<project_root>/docs/handoffs/archive/*.md` | Current live archive target |
| Current state | `<project_root>/docs/handoffs/.session-state/handoff-<project>-<resume_token>.json` | Current live chain state |
| Current legacy fallback | `<project_root>/.codex/handoffs/*.md` | Current live legacy fallback in source |
| Current legacy hidden archive fallback | `<project_root>/.codex/handoffs/.archive/*.md` | Current live history-search fallback in source for pre-`docs/handoffs/` archives |

### Target Post-Cutover Authority

This table describes the target after the reversal implementation lands.

| Role | Path | Status |
|---|---|---|
| Primary active | `<project_root>/.codex/handoffs/*.md` | Post-cutover write/read target |
| Primary archive | `<project_root>/.codex/handoffs/archive/*.md` | Post-cutover archive target |
| Primary state | `<project_root>/.codex/handoffs/.session-state/handoff-<project>-<resume_token>.json` | Post-cutover chain state |
| Consumed legacy-active registry | `<project_root>/.codex/handoffs/.session-state/consumed-legacy-active.json` | Post-cutover suppression state for loaded legacy active files |
| Copied legacy-archive registry | `<project_root>/.codex/handoffs/.session-state/copied-legacy-archives.json` | Post-cutover idempotency state for explicit legacy archive loads |
| Legacy active | `<project_root>/docs/handoffs/*.md` | Read-only migration input during cutover only when classified as ignored legacy operational input, untracked legacy operational input, or exact reviewed opt-in; tracked durable docs are excluded from active selection |
| Legacy archive | `<project_root>/docs/handoffs/archive/*.md` | Read-only history-search and explicit-path input; never active-selection input |
| Previous-primary hidden archive | `<project_root>/.codex/handoffs/.archive/*.md` | Read-only history-search and explicit-path input for pre-`docs/handoffs/` archives; never active-selection input |
| Legacy state | `<project_root>/docs/handoffs/.session-state/*` | Read-once bridge input for chain writers; never written; explicit loads rejected |
| State-like residue | `<project_root>/docs/handoffs/handoff-*` and `<project_root>/docs/handoffs/handoff-*.json` | Inventory-only unless exactly one valid project state bridge candidate; every local path requires local-preflight evidence disposition, and only repo-authority facts belong in the tracked ledger |

### Installed Host Repo Policy Matrix

This source repo's `.gitignore` rules are source-repo hygiene only. They cannot prove, enforce, or repair installed-plugin behavior in arbitrary host repositories.

The Handoff plugin must not edit a host repository's `.gitignore`, `.git/info/exclude`, tracked `.codex/**` content, or index state as part of normal save/load/list/search/summary/quicksave operations. Host tracking policy is not a plugin invariant. The plugin invariant is that runtime writes use the post-cutover storage root, preserve containment, avoid overwriting tracked or existing user files, and report enough visibility metadata for the user or closeout evidence to understand the host state.

Post-cutover helper output for mutating operations must include best-effort git visibility fields for every path whose bytes could be moved, copied, written, or suppressed:

- `ignored`: the written runtime path is ignored by the host repo
- `untracked`: the written runtime path is visible as ordinary untracked worktree material
- `tracked-conflict`: the exact target path or collision candidate is tracked and must not be overwritten
- `not-git-repo`: the project root is not inside a git worktree
- `unknown`: git visibility could not be determined; include the diagnostic reason

For target allocation, expose this as `target_git_visibility`. For source-backed operations, also expose `source_git_visibility` before mutation. A source path with `source_git_visibility=tracked-conflict` under `.codex/handoffs/**` is a tracked host file, not safe runtime material. Implicit and explicit primary load must fail closed with `TrackedRuntimeSourceError` or an equivalent typed diagnostic before moving it. Read-only inventory may report that path as `blocked_tracked_runtime_source`; default active selection must not silently choose it. Explicit read-only `/distill <path>` may read it only through explicit-path validation because no handoff source bytes are moved or suppressed.

The installed-plugin smoke matrix must cover these host shapes:

| Host shape | Required behavior |
|---|---|
| No `.codex/` ignore rule | Handoff writes under `.codex/handoffs/`, reports `target_git_visibility=untracked`, and does not claim source-repo ignore proof. |
| Broad `.codex/` ignore rule | Handoff writes under `.codex/handoffs/`, reports `target_git_visibility=ignored`, and does not edit host ignore files. |
| Tracked `.codex/skills/**` with narrow handoff ignore | Handoff writes under `.codex/handoffs/`, `.codex/skills/**` remains tracked or trackable, and the handoff rule does not hide unrelated `.codex` content. |
| Existing tracked `.codex/handoffs/<candidate>.md` or archive collision | Allocation treats the tracked path as occupied, does not overwrite it, and either chooses the next collision-safe path or fails with a typed collision-budget diagnostic. |
| Existing tracked `.codex/handoffs/<active-source>.md` selected for load | Load fails closed before move/archive/state mutation, reports `source_git_visibility=tracked-conflict`, and leaves the tracked source file and index untouched. |
| Non-git project root | Handoff writes under `.codex/handoffs/`, reports `target_git_visibility=not-git-repo`, and skips git ignore checks without weakening path containment. |

Closeout cannot use this repo's `git check-ignore` results as installed-host proof. Source ignore checks prove only this source checkout. Installed-cache certification must include the host matrix above, using the installed skill/helper code path rather than source-only imports.

Installed-host smoke must be source-proof. The smoke must resolve an installed Handoff plugin root, execute helpers from that root, and emit:

- `source_checkout_root`
- `installed_plugin_root`
- `resolved_helper_path`
- `resolved_skill_doc_path`
- realpath comparison proving `resolved_helper_path` and `resolved_skill_doc_path` are outside `source_checkout_root`
- installed plugin version or manifest identity

If the resolved helper or skill doc realpath is inside the source checkout, installed-host certification is invalid even if behavior tests pass. Source-tree pytest may orchestrate the smoke, but the code under test must be imported or executed from the installed plugin root after removing the source checkout from `PYTHONPATH` and import resolution.

### Residue Disposition Artifacts

Preflight residue handling has two separate artifacts with different authority scopes:

1. A tracked repo-authority ledger for clone-global policy and tracked or intentionally durable repo facts.
2. An ignored local-preflight evidence file for this machine's operational residue corpus.

The tracked repo-authority ledger path is:

```text
docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md
```

The repo-authority ledger must include a `scope` column for every row. Allowed values are:

- `repo-authority`: tracked or intentionally durable repo fact that must be true in a fresh clone
- `local-preflight-summary`: summary row that references local evidence by run id, timestamp, count, and evidence hash, but does not claim the local paths exist in fresh clones
- `policy-rule`: durable classification or disposition rule that applies to future implementations

The local-preflight evidence path is ignored runtime evidence under:

```text
.codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json
```

The local-preflight evidence file must enumerate every current path matched by `docs/handoffs/handoff-*` and `docs/handoffs/handoff-*.json` at preflight time. Each row must include:

- lexical path and resolved containment-checked path
- inventory scope: `canonical-checkout`
- git status class: tracked, ignored, untracked, or missing-after-inventory
- raw-byte SHA256 when readable
- detected format: tokenized state JSON, legacy plain state, invalid state-like residue, or non-state residue
- project and resume token when derivable
- disposition: `bridge-once`, `mark-consumed`, `quarantine-ignored-state`, `reject-diagnostic`, `preserve-durable`, or `blocked-policy-conflict`
- rationale and verification command or test that proves the disposition
- scope: `local-preflight`

The tracked repo-authority ledger must not enumerate ignored or untracked machine-local residue paths as if they are fresh-clone project facts. It may reference the local-preflight evidence by hash and count, for example "local preflight run `<id>` saw 1 ignored state-like residue path; see ignored evidence file hash `<sha256>`." That reference is evidence for this checkout only, not durable repo authority.

No local residue path may remain implicit during implementation execution. Implementation must stop if any local-preflight evidence row has `TBD`, no disposition, no scope, or no verification hook. A residue path may be quarantined only under ignored `.codex/handoffs/.session-state/quarantine/` with a transaction record and source hash. Destructive cleanup is out of scope unless a later explicit instruction authorizes it.

Gate 0A for this execution uses the canonical checkout at `/Users/jp/Projects/active/codex-tool-dev` after preserving unrelated P2 work on its own branch and switching the canonical checkout back to `main`. Local-preflight evidence must use `inventory_scope=canonical-checkout`. If a later attempt needs an isolated implementation worktree, stop and revise this plan, the residue ledger, and the local-preflight evidence schema before continuing; do not reuse canonical-checkout evidence for a different topology.

## Cutover Inventory And Bridge

The reversal cannot start by switching writers alone. Before implementation is considered ready, add tests and command evidence for a cutover inventory covering:

- valid primary active files under `.codex/handoffs/*.md`
- legacy active files under `docs/handoffs/*.md` only after artifact-class filtering excludes tracked durable docs and unresolved policy-conflict artifacts
- previous-primary hidden archive files under `.codex/handoffs/.archive/*.md` for history search and explicit archive load compatibility
- pending primary state under `.codex/handoffs/.session-state/*.json`
- pending legacy state under `docs/handoffs/.session-state/*.json`
- top-level state-like residue under `docs/handoffs/handoff-*` and `docs/handoffs/handoff-*.json`
- consumed legacy-active registry state under `.codex/handoffs/.session-state/consumed-legacy-active.json`
- copied legacy-archive registry state under `.codex/handoffs/.session-state/copied-legacy-archives.json`
- ignore behavior for new `.codex/handoffs/` runtime files
- preservation of existing `docs/handoffs/` runtime ignore behavior
- installed-host behavior for no ignore, broad `.codex/` ignore, tracked `.codex/skills/**`, tracked handoff-path collision, tracked primary active source, and non-git project roots
- local-preflight evidence completeness for every top-level `docs/handoffs/handoff-*` path, plus repo-authority ledger scope correctness

During the reversal release, implicit active discovery for `/list-handoffs` and `/load` must consider valid primary active files plus eligible unconsumed legacy active files after artifact-class filtering. A legacy active file is selectable only when it is an ignored legacy operational handoff, an untracked legacy operational handoff, or an exact reviewed runtime migration opt-in. Tracked durable handoff artifacts and policy-conflict artifacts are diagnostic inventory rows, not active candidates. Dedup remains byte-exact, with primary active winning over selectable legacy active. This mixed-root behavior prevents operational active `docs/handoffs/*.md` files from becoming stranded after the first new `.codex/handoffs/*.md` write without consuming durable repository docs.

Implicit `/load` chooses the most recent eligible active candidate from the combined primary-active plus class-filtered legacy-active set after dedup, using the Selection Ordering contract below. If it chooses a primary active file, Primary Load semantics apply. If it chooses a legacy active file, Legacy Load semantics apply.

Fallback-only legacy discovery may be restored only in a later release after an explicit deprecation or migration gate proves legacy active files have been copied, intentionally left behind, or made explicitly path-only. That later gate is out of scope for this implementation.

### Consumed Legacy Active Suppression

Because legacy active files are read-only migration input, successful legacy `/load` must not move or delete `docs/handoffs/*.md`. It must instead make the loaded legacy file stop participating in active-selection workflows.

Use a durable consumed legacy-active registry under `.codex/handoffs/.session-state/consumed-legacy-active.json`. Each consumed entry must include:

- absolute lexical legacy source path
- containment-checked resolved path
- raw-byte SHA256 content hash
- copied primary archive path
- consumed timestamp
- operation that consumed it, for example `legacy-load`

Active-selection scans suppress a legacy active candidate only when the registry contains the same lexical source path and raw-byte content hash. If the legacy file changes bytes later, it is treated as a new active candidate and must be validated again.

A legacy load is not successful unless the copy to primary archive, primary state write, and consumed-registry write all succeed. After a successful legacy load, default `/list-handoffs` and implicit `/load` must not show or select the consumed legacy active file again. History search may still surface the legacy source as historical input with provenance.

### Copied Legacy Archive Registry

Explicit legacy archive loads copy legacy archive content to primary archive storage so new chain state points at `.codex/handoffs/archive/`. This includes both `docs/handoffs/archive/*.md` and previous-primary hidden archive files under `.codex/handoffs/.archive/*.md`. Repeating the same explicit legacy archive load must not create duplicate primary archive copies.

Use a durable copied legacy-archive registry under `.codex/handoffs/.session-state/copied-legacy-archives.json`. Each copied entry must include:

- absolute lexical legacy source path
- containment-checked resolved path
- raw-byte SHA256 source content hash
- copied primary archive path
- raw-byte SHA256 copied archive content hash
- copied timestamp
- operation that copied it, for example `legacy-archive-load`
- recovery status: `complete`, `recovery_required`, or `failed`
- transaction id that created or last repaired the entry

An explicit legacy archive load may reuse an entry only when the lexical source path, resolved path, and source hash match and the copied primary archive path exists with the copied hash. If any of those checks fail, recovery must diagnose the stale or corrupt registry entry before a new copy can be allocated.

### Legacy State Bridge

New chain writers read primary state first. If no primary state exists, they must consume exactly one valid matching legacy state or state-like residue candidate as a one-time bridge for sessions loaded before the upgrade and saved after the upgrade, or fail with the diagnostic rules below.

Bridge lookup is project-scoped, not caller-token-scoped. Chain writers are not required to know a resume token before reading state. The helper computes the project name and finds pending state for that project.

A matching legacy state candidate must be exactly one of:

- a tokenized JSON file named `handoff-<project>-<token>.json`
- an older plain state file named `handoff-<project>`
- a top-level state-like residue file under `docs/handoffs/` that validates as one of the two formats above

State precedence is deterministic:

- If exactly one valid primary state exists, it wins for the current chain. Legacy state candidates must not override it.
- If more than one valid primary state exists for the project, fail with `AmbiguousResumeStateError` or an equivalent typed diagnostic.
- If no valid primary state exists, exactly one valid legacy state or state-like residue candidate may bridge.
- If no valid primary state exists and more than one valid legacy candidate exists, fail with `AmbiguousResumeStateError` or an equivalent typed diagnostic.

Ambiguous state diagnostics must include a concrete operator recovery workflow. The helper surface must provide a read-only state inventory mode, for example `list-chain-state`, that emits every same-project state candidate with lexical path, resolved path, project, resume token when available, archive path, age, source root, payload hash, and validation status. The diagnostic must tell the operator to choose one of these explicit outcomes:

- continue from exactly one candidate by explicit state path or resume token, then write primary state under `.codex/handoffs/.session-state/`
- mark one or more stale candidates consumed with a durable marker and post-clear proof
- abort without mutation

No helper may guess among multiple valid same-project state candidates. A recovery command that marks stale state consumed must run under the project lock, record a transaction, and preserve enough metadata for later audit. Tests must cover the ambiguous diagnostic payload and at least one explicit recovery path.

Primary state winning does not prove same-project legacy state candidates are stale. When exactly one valid primary state exists and any same-project legacy state or state-like residue candidate also exists, chain writers must stop before active output creation unless every legacy candidate already has an explicit durable operator disposition. The diagnostic must include the read-only inventory rows and require the operator to choose one of these outcomes:

- mark specific legacy candidates stale or consumed with an explicit recovery command, transaction record, and post-clear proof
- continue from one explicit legacy candidate after abandoning or clearing the primary state through an explicit recovery command
- preserve the candidates and abort without mutation

`clear-chain-state` must not silently consume, mark, or delete unresolved same-project legacy candidates just because a primary state exists. A recovery command may mark stale candidates only under the project lock, with source hashes and operator-selected paths recorded. If unresolved legacy candidates remain, fail with an actionable diagnostic rather than leaving state that can resurrect after primary cleanup.

If a tokenized payload has `project` or `resume_token` fields, they must match the filename-derived project/token. If a legacy plain state has no token, the helper may mint a new token only after preserving the legacy `archive_path` as the `resumed_from` source for the save/summary/quicksave output. The `archive_path` must be a valid contained handoff path accepted by explicit-path validation, and the state must be inside the 24-hour chain-state TTL unless a test explicitly covers a documented expired-state diagnostic.

A successful bridged save/summary/quicksave must preserve the `resumed_from` link, write new output and any new chain state only under `.codex/handoffs/`, and clear the consumed legacy state file. Cleanup is resurrection-proof only if either deletion succeeds or a durable consumed marker is written using the existing consumed-marker pattern or a successor with equivalent semantics. A bridged writer is not successful unless a post-clear bridge lookup proves the legacy state no longer returns usable state. Malformed, expired, ambiguous, multiply matching, uncleared, or unmarkable legacy state must fail with an actionable diagnostic that names the state path or conflict; it must not silently break or resurrect the chain.

Explicit loads from `docs/handoffs/.session-state/` remain rejected. Legacy state is bridge input only for the save/summary/quicksave chain writer.

### Transaction And Recovery Protocol

Any operation that mutates active files, archive files, state files, consumed registries, copied-source registries, bridge markers, residue quarantine records, or transaction records must run under one project-scoped lock under `.codex/handoffs/.session-state/locks/`. The lock must be acquired with an atomic filesystem primitive such as exclusive file creation or atomic directory creation.

Lock metadata must include project, operation, transaction id, process id if available, hostname if available, created timestamp, and lock timeout. Default lock behavior is fail-fast. If a helper supports waiting, it must require an explicit `--wait-seconds` argument and cap the wait at 30 seconds. A lock older than 30 minutes is stale only after recovery inspects any pending transaction for the same project; stale-lock takeover without recovery is forbidden.

Mutable operations must use same-filesystem temporary files plus atomic rename for active markdown, JSON state, registry, marker, and transaction-log writes. Archive copies must be copied to a temporary file in the target archive directory, verified by byte hash, and then atomically renamed to the allocated archive path.

Every mutating load, active writer, or state operation must be transactional and idempotent, including implicit primary active load, explicit primary active load, explicit primary archive load, implicit legacy active load, explicit legacy active load, explicit legacy archive load, save active write, summary active write, quicksave active write, state write, and state clear.

1. Acquire the project lock.
2. Recompute and validate the selected source path, storage location, and raw-byte hash for source-backed operations; for generated active writes, validate the generated output metadata, allocated active path, and output hash.
3. Write a pending transaction record under `.codex/handoffs/.session-state/transactions/` containing the operation, source path, source hash when applicable, allocated active or archive path when applicable, intended state path when applicable, consumed-registry or copied-source-registry entry when applicable, active output hash when applicable, and operation-specific postconditions.
4. Perform content mutation when applicable:
   - `primary_active`: after source git visibility recheck proves the source is not tracked host content, atomically move the primary active file to the allocated primary archive path.
   - `primary_archive`: do not copy or move archive content; validate the existing archive path and proceed to state write.
   - `legacy_active`: after artifact-class filtering proves the source is eligible runtime migration input, copy to a temporary file in the primary archive directory, verify bytes, and atomically rename to the allocated primary archive path.
   - `legacy_archive`: copy to a temporary file in the primary archive directory, verify bytes, atomically rename to the allocated primary archive path, and record or reuse a copied-source registry entry.
   - `active_write`: write active markdown to a temporary file in the primary active directory, verify bytes, and atomically rename to the allocated primary active path.
5. Write primary state via temporary file and atomic rename only for load or explicit state-write operations. Active writers instead read chain state before writing output and clear or mark that state after active output is verified.
6. Update the consumed legacy-active registry via temporary file and atomic rename only for `legacy_active`; update the copied legacy-archive registry via temporary file and atomic rename only for `legacy_archive`; update active-writer state cleanup markers only for bridged state consumed by `active_write`.
7. Mark the transaction committed or remove the transaction record only after post-conditions prove active or archive output, state, and any required registry agree.
8. Release the lock.

Recovery has two modes:

- `read-only-recovery-inventory`: inspect lock and transaction records, report pending, committed, failed, or inconsistent records, and annotate candidate eligibility. It must not complete, roll back, move, copy, delete, mark consumed, clear state, or write transaction records.
- `mutating-recovery`: run under the project lock and either complete a fully verifiable transaction or fail with an actionable diagnostic that names the transaction record and the inconsistent artifact.

Read-only workflows, including `/list-handoffs`, default and explicit `/distill`, `/search`, `/triage`, and read-only state inventory, may run only `read-only-recovery-inventory` before active selection or history search. If pending or inconsistent transactions affect a candidate, the command must report the blocked candidate and continue with unaffected eligible candidates when that is safe; otherwise it must fail read-only with a diagnostic. It must not repair the transaction as a side effect.

Mutating workflows, including implicit or explicit `/load`, `/save`, `/summary`, `/quicksave`, state clear, consumed-marker repair, copied-registry repair, and explicit operator recovery commands, must run `mutating-recovery` before selecting a source, reading a state bridge, or opening a new transaction. A partial archive copy, active write, or primary move without matching state and required registry entry must not silently create a second archive or active record for the same source/hash. Tests must cover read-only inventory over dirty transactions, interruption after archive mutation, interruption after active write, interruption after state write, duplicate retry, and concurrent attempts for every mutating load storage location and every active writer.

Completed-transaction idempotency is source-hash scoped. Retrying or repeating an explicit legacy archive load for the same lexical source path plus raw-byte hash must reuse the verified primary archive path from `copied-legacy-archives.json` and write state to that path; it must not allocate a fresh primary archive copy each time. If the registry entry exists but the primary archive copy is missing or byte-mismatched, recovery must fail with a typed diagnostic rather than silently creating a second copy outside a repair transaction. Legacy active loads use `consumed-legacy-active.json` for the same source-path plus hash reuse and suppression semantics.

Transaction records must be JSON and include at least:

- `transaction_id`
- `project`
- `operation`
- `status`: `pending`, `committed`, `recovery_required`, or `failed`
- `phase`
- `source_path`, when the transaction reads an existing source path
- `resolved_source_path`, when the transaction reads an existing source path
- `source_sha256`, when the transaction reads existing source bytes
- `allocated_archive_path`, when the transaction writes or reuses an archive output
- `temp_archive_path`, when the transaction writes a temporary archive output
- `allocated_active_path`, when the transaction writes active output
- `temp_active_path`, when the transaction writes temporary active output
- `output_sha256`, when the transaction writes active or archive output
- `active_writer_idempotency_key`, when the transaction writes generated active output
- `state_snapshot_sha256`, when an active writer reads chain state before output
- `resume_source_path`, when an active writer preserves `resumed_from`
- `resume_source_sha256`, when an active writer preserves `resumed_from`
- `caller_run_id` or helper-minted `run_id`, when the transaction writes generated active output
- `state_path`, when the transaction reads, writes, clears, or bridges chain state
- `state_action`: `none`, `read`, `write`, `clear`, or `bridge-clear`
- `registry_path`
- `copy_registry_path`
- `expected_postconditions`
- `created_at`
- `updated_at`
- `lock_path`
- `error`, when recovery or failure occurs

### Active Writer Creation Contract

`/save`, `/summary`, and `/quicksave` are active writers. They must not build `.codex/handoffs/` paths directly in skill prose, shell snippets, or one-off helper code. They must use shared helper APIs that run under the project lock and transaction protocol.

The implementation must provide:

- `begin-active-write`: start a save/summary/quicksave transaction before generated content is accepted. It must run mutating recovery, read primary or bridged chain state, mint or accept a caller-provided run id, allocate and bind the active path, persist the idempotency key and pending transaction record, and return the `run_id`, transaction id, allocated path, state snapshot id, and resumed-from identity to the caller.
- `allocate-active-path`: allocate a collision-safe primary active path under `.codex/handoffs/` from an operation kind, timestamp, and slug. Allocation must use filename timestamp format `YYYY-MM-DD_HH-MM_<kind>-<slug>.md`, treat existing files, directories, symlinks, and tracked exact-path conflicts as occupied, and support at least base, `-01`, and `-02` suffixes before returning collision-budget exhaustion.
- `write-active-handoff`: accept only content tied to a previously returned `run_id`, transaction id, allocated path, state snapshot id, and idempotency key; write active handoff markdown under `.codex/handoffs/` via same-directory temp file and atomic rename, verify the raw-byte hash, preserve `resumed_from` from primary or bridged legacy state, and clear or durably mark consumed chain state only after the active file is proven present.
- `active-write-transaction-recover`: recover or fail pending save/summary/quicksave transactions before any new mutating active write or state bridge lookup. Read-only selection uses `read-only-recovery-inventory` instead.

Generated active writes use an active-writer idempotency key, not a source hash. The key is stable retry identity; it must not include `transaction_id` or generated content hash. Those are transaction fields used to audit and compare attempts, not key components.

The key must include:

- project
- operation: `save`, `summary`, or `quicksave`
- state snapshot id or state hash when chain state was read
- resume source path and hash when `resumed_from` exists
- caller-provided run id when available, otherwise a helper-minted run id emitted and persisted before path allocation or content mutation
- allocated active path after the transaction binds one

Active writer recovery states are:

- `pending_before_write`: no active output exists; recovery may continue the original transaction or fail before allocating a different path.
- `written_not_confirmed`: active output exists at `allocated_active_path` with the recorded hash, but transaction commit was not recorded; recovery must reuse that path and complete or diagnose state cleanup. It must not allocate a second handoff for the same idempotency key.
- `cleanup_failed`: active output exists and state cleanup failed or is unproven; recovery must retry cleanup or fail with an actionable diagnostic naming the active path and state path.
- `content_mismatch`: active output exists at the allocated path but bytes differ from the transaction hash; recovery must fail closed and require operator action.

If a caller retries `/save`, `/summary`, or `/quicksave` after a pending transaction, the helper must discover pending transactions by stable run id, state snapshot, resume source identity, and allocated path when already bound, then run `active-write-transaction-recover` before accepting regenerated content or minting a new transaction id. If the retry matches the same idempotency key and generated content hash, it reuses the existing transaction. If the retry matches the same idempotency key but changed bytes, it fails with `ActiveWriteContentChangedError` or an equivalent typed diagnostic rather than creating a second active handoff. A deliberate second handoff requires a new helper-minted run id after the pending transaction is recovered, failed, or explicitly abandoned.

The caller protocol is:

1. Call `begin-active-write` before asking an LLM or local generator to produce final handoff content.
2. Preserve the returned `run_id`, transaction id, allocated path, state snapshot id, and resumed-from identity in the caller-visible operation state.
3. Generate content for that exact operation identity.
4. Call `write-active-handoff` with the same operation identity and the generated content hash.
5. On retry, pass the original `run_id` and transaction id when known. If they are not known, the helper must discover compatible pending transactions by operation, project, state snapshot, resume source identity, and allocated path; if zero or more than one compatible pending transaction exists, it must fail closed before accepting regenerated content.
6. If a retry matches the same idempotency key and content hash, reuse the existing transaction. If it matches the same idempotency key but content bytes changed, fail with `ActiveWriteContentChangedError` or an equivalent typed diagnostic.

The save/summary/quicksave transaction boundary is:

1. Acquire the project lock.
2. Run mutating recovery for the project.
3. Read primary state or the one-time legacy state bridge.
4. Allocate the primary active output path.
5. Write and verify the active handoff file.
6. Clear primary state and consume or mark any bridged legacy state with post-clear proof.
7. Commit the transaction only after the active file exists, the content hash matches, and state cleanup cannot resurrect.

A save/summary/quicksave operation is not successful if state cleanup fails after the active file write. In that case the transaction must remain recoverable or fail with a diagnostic that names the active path and state path; it must not report a clean save while leaving ambiguous chain state behind.

### Git Ignore And Tracking Policy

This repo already contains tracked `.codex/` content, so `.codex/handoffs/` must be ignored narrowly rather than by ignoring all `.codex/`. This section applies to the source repo only; installed-host behavior is governed by the Installed Host Repo Policy Matrix above.

The implementation must add or preserve ignore rules so these runtime files are ignored:

- `.codex/handoffs/` as a runtime subtree, or an equivalent complete pattern set covering every file below
- `.codex/handoffs/*.md`
- `.codex/handoffs/archive/*.md`
- `.codex/handoffs/archive/.tmp-*`
- `.codex/handoffs/archive/*.tmp`
- `.codex/handoffs/.session-state/`
- `.codex/handoffs/.session-state/**`
- `.codex/handoffs/.session-state/*.json`
- `.codex/handoffs/.session-state/locks/**`
- `.codex/handoffs/.session-state/transactions/**`
- `.codex/handoffs/.session-state/markers/**`
- `.codex/handoffs/.session-state/*.tmp`
- `docs/handoffs/*.md`
- `docs/handoffs/archive/*.md`
- `docs/handoffs/.session-state/*.json`

The same policy must preserve tracked or trackable plugin source such as `.codex/skills/**`. Verification must include positive `git check-ignore -v` checks for the new handoff runtime paths and a negative check proving `.codex/skills/<sample>` is not ignored by the handoff rule.

## Shared Discovery Contract

Add one shared path authority, discovery, and validation module used by `/load`, `/list-handoffs`, `/search`, `/triage`, `/distill`, `/save`, `/summary`, `/quicksave`, state cleanup, and deterministic tests that inspect or write handoff roots.

The shared module must expose writer path APIs for current active, archive, state, legacy state bridge lookup, and cleanup paths. Writers must not independently reconstruct `docs/handoffs/` or `.codex/handoffs/` paths in skill prose or helper scripts.

Instruction-driven skills must call concrete helper CLI or API entrypoints instead of rebuilding path logic with shell globbing, `ls -t`, direct `mkdir`, direct `mv`, direct `cp`, or hardcoded archive/state directories.

The implementation must provide documented helper entrypoints for at least:

- `begin-active-write`: persist a stable active-writer run id, transaction id, state snapshot, resumed-from identity, and allocated path before save/summary/quicksave content generation
- `allocate-active-path`: allocate a collision-safe primary active output path for save/summary/quicksave
- `write-active-handoff`: atomically write primary active output and clear or mark chain state under one transaction
- `active-write-transaction-recover`: recover or diagnose pending active writer transactions
- `select-active`: return the implicit load/distill candidate selected by Scan Mode `active_selection`
- `list-active`: return default `/list-handoffs` output from Scan Mode `active_selection`
- `validate-explicit-path`: validate explicit primary or legacy active/archive paths
- `archive-primary-active`: move primary active input to primary archive and write state
- `copy-legacy-active-to-primary-archive`: copy eligible legacy active input to primary archive, write state, and mark the legacy source consumed
- `copy-legacy-archive-to-primary-archive`: copy or reuse a verified primary archive copy for an explicit legacy archive source without marking the source consumed
- `read-chain-state`: read primary state or the one-time legacy bridge state
- `list-chain-state`: list same-project primary, legacy, and state-like residue candidates for ambiguity diagnostics and operator recovery
- `write-chain-state`: write only primary state
- `clear-chain-state`: clear primary state and consume only the bridged legacy state with post-clear proof; it must not infer that other same-project legacy candidates are stale
- `history-candidates`: return `/search`, `/triage`, and `/summary` arc candidates from Scan Mode `history_search`

`test_skill_docs.py` or an equivalent surface test must prove load/list/distill/save/summary/quicksave docs invoke these helpers and do not retain stale shell-only path implementations.

### Helper Launcher Classes

Skill docs must preserve the current direct-Python chain-state and active-writer contract where it matters:

- Chain-state, active-writer, and archive-mutation helpers must be stdlib-only and runnable as direct Python, for example `python "$PLUGIN_ROOT/scripts/session_state.py" ...` or a successor stdlib-only helper path. These helpers include `allocate-active-path`, `write-active-handoff`, `active-write-transaction-recover`, `archive-primary-active`, `copy-legacy-active-to-primary-archive`, `copy-legacy-archive-to-primary-archive`, `read-chain-state`, `list-chain-state`, `write-chain-state`, and `clear-chain-state`.
- Discovery and history helpers should also be stdlib-only if feasible. If a helper truly needs dependencies, it may use `uv run`, but the plan must name that helper as dependency-bearing and skill-doc tests must prove chain-state helpers did not regress to `uv run`.
- Refresh tooling, tests, and marketplace mutation helpers may use `uv run`; that does not waive the direct-Python contract for chain-state helpers.
- `test_skill_docs.py` must keep or replace the current direct-Python-vs-command-helper distinction deliberately. Removing that distinction without an equivalent launcher-class assertion is a hard stop.

Every candidate result must include typed fields:

- `path`: absolute lexical path
- `resolved_path`: resolved containment-checked path
- `source_root`: enum `primary`, `legacy`, or `previous_primary`
- `storage_location`: enum `primary_active`, `primary_archive`, `legacy_active`, `legacy_archive`, or `previous_primary_hidden_archive`
- `lifecycle`: enum `active` or `archive`
- `artifact_class`: enum `primary-runtime`, `ignored-legacy-operational-handoff`, `untracked-legacy-operational-handoff`, `tracked-durable-handoff-artifact`, `reviewed-runtime-migration-opt-in`, `previous-primary-hidden-archive`, `state-like-residue`, `policy-conflict-artifact`, or `unknown`
- `source_git_visibility`: enum `ignored`, `untracked`, `tracked-conflict`, `not-git-repo`, or `unknown`
- `selection_eligibility`: enum `eligible`, `read-only-only`, `blocked-tracked-source`, `blocked-durable-artifact`, `blocked-policy-conflict`, or `blocked-invalid`
- `content_hash`: byte-exact SHA256 of raw file bytes, computed only after containment and regular-file checks
- `validity`: enum `valid`, `invalid`, `skipped`
- `document_profile`: enum `current_contract` or `historical_archive`
- `invalid_reason`: typed reason for document validation failures
- `skip_reason`: typed reason for filesystem or discovery exclusions

`invalid_reason` is for document validation failures such as missing frontmatter, invalid type, missing required fields, or malformed required sections.

`skip_reason` is for filesystem and discovery exclusions such as hidden file, nested implicit file, symlink, path escape, non-regular file, unreadable file, forbidden state directory, or outside scan scope.

No broad `except Exception: pass` behavior is allowed in discovery paths. Skips must preserve path and reason.

## Scan Modes

The shared module must expose separate scan modes so active lifecycle, history search, explicit-path access, and state bridging cannot drift.

### Active Selection

Used by implicit `/load`, default `/list-handoffs`, and default `/distill`.

Includes:

- primary active: `.codex/handoffs/*.md` when not tracked by the host repo
- unconsumed legacy active during cutover: `docs/handoffs/*.md` only when classed as ignored legacy operational input, untracked legacy operational input, or exact reviewed runtime migration opt-in

Excludes:

- primary archive
- legacy archive
- consumed legacy active entries
- tracked primary runtime source files, except as read-only diagnostics or explicit read-only paths
- tracked durable legacy handoff artifacts
- policy-conflict artifacts
- state directories
- nested, hidden, invalid, unreadable, symlink, path-escape, and non-regular files

### History Search

Used by `/search`, `/triage`, and `/summary` project-arc synthesis.

Includes readable, valid files from:

- primary active
- primary archive
- legacy active
- legacy archive
- previous-primary hidden archive

History search may surface consumed legacy active files and previous-primary hidden archive files as historical records, but output must show provenance and dedup winners. It must not feed consumed legacy active files or previous-primary hidden archive files back into active-selection results.

For `/summary`, history search is read-only project-arc input. Summary arc synthesis must scan primary active, primary archive, legacy active, legacy archive, and previous-primary hidden archive using the same provenance and dedup rules as history search. It must not keep direct `docs/handoffs/archive/` or `.codex/handoffs/.archive/` shell scans after cutover.

History search must preserve useful old archives that predate the current frontmatter contract. Files under archive roots that lack YAML frontmatter may be accepted only in history search with `validity=valid`, `document_profile=historical_archive`, reduced metadata, and provenance showing the source path. Historical archive profile is forbidden for active selection, explicit `/load`, explicit `/distill`, and chain state.

### Explicit Path

Used by `/load <path>`, `/distill <path>`, and any explicit archive read.

Allows contained primary, legacy, or previous-primary hidden archive markdown paths only. It rejects state directories, hidden basenames, symlink escapes, non-regular files, unreadable files, invalid documents, and paths outside the allowed roots.

### State Bridge

Used only by save/summary/quicksave chain writers.

Reads primary state first. If exactly one valid primary state exists and no unresolved same-project legacy candidates exist, primary state wins. If primary state exists and unresolved same-project legacy candidates also exist, the writer fails before active output creation and points to explicit recovery choices. If primary state is absent, it consumes exactly one matching legacy state or state-like residue candidate according to the Legacy State Bridge rules. State bridge results are never handoff candidates and never participate in active selection, history search, or explicit-path handoff loads.

## Validation Rules

Implicit scans include only top-level active files after artifact-class and source-visibility filtering:

- primary: `.codex/handoffs/*.md`
- legacy active during cutover for load/list/distill: `docs/handoffs/*.md` only when ignored legacy operational input, untracked legacy operational input, or exact reviewed runtime migration opt-in

Implicit scans exclude archives, nested files, hidden files, `.session-state/`, symlinks, path escapes, non-regular files, unreadable files, invalid documents, tracked primary runtime source files, tracked durable legacy artifacts, and policy-conflict artifacts.

Invalid primary files produce path-specific diagnostics and do not hide eligible legacy active files.
Tracked primary runtime source files produce `blocked_tracked_runtime_source` diagnostics and do not hide valid eligible candidates. Tracked durable legacy artifacts produce `blocked_durable_artifact` diagnostics and do not participate in active selection unless a reviewed migration opt-in names the exact path and hash.

Hidden-path policy is component-aware:

- the primary root component `.codex` is allowed and must not cause primary handoff paths to be rejected
- `.session-state` is allowed only for state APIs and is rejected for handoff document scans
- hidden basenames such as `.foo.md` are rejected for implicit and explicit handoff document scans
- `.archive` is allowed only for the previous-primary hidden archive root at `.codex/handoffs/.archive/`; it is rejected everywhere else
- hidden directories other than the allowed `.codex` root component, the state API `.session-state` directory, and the previous-primary hidden archive root are skipped with a reason

Explicit paths may target contained files under:

- `<project_root>/.codex/handoffs/*.md`
- `<project_root>/.codex/handoffs/archive/*.md`
- `<project_root>/.codex/handoffs/.archive/*.md`
- `<project_root>/docs/handoffs/*.md`
- `<project_root>/docs/handoffs/archive/*.md`

All explicit paths still enforce containment, regular-file checks, symlink rejection, hidden-file policy, `.session-state/` rejection, readability, and document validity.

Document validity must be defined by the shared validator, not by loose parser tolerance. A file with missing or invalid frontmatter is invalid for active-selection workflows, even if low-level parsing returns empty metadata.

## Selection Ordering

Whenever `/load`, `/list-handoffs`, or `/distill` needs "most recent" active handoffs, recency is defined by the parsed filename timestamp prefix `YYYY-MM-DD_HH-MM_*.md`.

Implicit active candidates without a parseable filename timestamp are invalid with an `invalid_reason` such as `invalid_filename_timestamp`. Filesystem mtime is not an ordering key for load/list/distill selection.

Sort order is:

1. filename timestamp descending
2. source precedence for exact timestamp ties: primary active before legacy active
3. lexical absolute path ascending after containment checks

Frontmatter `created_at` and `date` remain document-validation fields. They do not override the filename timestamp for implicit load/list/distill ordering.

## Behavioral Semantics

### Primary Load

Primary load must:

- Recheck `source_git_visibility` for the selected `.codex/handoffs/<file>.md` before mutation.
- Fail closed without moving, copying, writing state, or updating registries if the source path is tracked by the host repo or git visibility is unknown in a way that prevents proving it is safe runtime material.
- Move `.codex/handoffs/<file>.md` to `.codex/handoffs/archive/<file>.md`, collision-safe.
- Remove the active source file from future implicit discovery.
- Write state under `.codex/handoffs/.session-state/`.
- Set state `archive_path` to the primary archive path.

### Legacy Load

Legacy load must:

- Copy bytes from `docs/handoffs/...` to `.codex/handoffs/archive/<file>.md`, collision-safe.
- Leave the legacy file untouched.
- Write state under `.codex/handoffs/.session-state/`.
- Set state `archive_path` to the copied primary archive path.
- Record the legacy source path and content hash in the consumed legacy-active registry.
- Suppress that exact legacy source path plus content hash from future active-selection scans.
- Never move, delete, archive into, or write state under `docs/handoffs/`.

### Explicit Path Load

Explicit `/load <path>` must use `validate-explicit-path` and then apply behavior by storage location:

- `primary_active`: recheck source git visibility; if tracked, fail closed with no mutation; otherwise move the primary active file to primary archive, write primary state, and remove the active source from future active-selection scans.
- `primary_archive`: write primary state pointing at the existing primary archive path. Do not copy, move, duplicate, or consume anything.
- `legacy_active`: copy to primary archive, write primary state pointing at the copied primary archive, and record consumed legacy-active suppression for that source path plus content hash.
- `legacy_archive`: copy or reuse a verified primary archive copy using `copied-legacy-archives.json`, then write primary state pointing at that primary archive path. Do not record consumed legacy-active suppression, because archive files are not active-selection inputs.
- `previous_primary_hidden_archive`: copy or reuse a verified primary archive copy using `copied-legacy-archives.json`, then write primary state pointing at that primary archive path. Do not record consumed legacy-active suppression, because hidden archive files are not active-selection inputs.

Explicit path load never writes under `docs/handoffs/` or `.codex/handoffs/.archive/`. Historical archive profile files without current frontmatter are not loadable by explicit path unless a separate migration command is added and tested.

Repeated explicit legacy archive loads for the same lexical source path plus raw-byte hash must be completed-transaction idempotent. The second and later loads must reuse the same verified primary archive path from the copied legacy-archive registry and update state to that path; they must not create `-01`, `-02`, or later duplicate primary archive copies solely because the user repeated the same explicit archive load.

### List

Default `/list-handoffs` is active-only.

Default behavior:

- List valid primary active files and eligible unconsumed legacy active files during the reversal release.
- Deduplicate byte-exact duplicates with primary active winning.
- Sort the visible result set by the Selection Ordering contract after dedup.
- Do not let invalid primary files hide eligible legacy active files.
- Include provenance fields for each listed item.

Archive listing is not required unless the implementation adds an explicit mode. If added, the mode must be named and documented, for example:

```bash
/list-handoffs --archive
```

Without an explicit archive mode, archived handoffs are loadable only by explicit path.

### Search And Triage

`/search` and `/triage` use Scan Mode `history_search` and always scan readable primary, legacy, and previous-primary hidden archive roots within their documented scope.

If triage keeps the 30-day cutoff, the contract is: scan primary, legacy, and previous-primary hidden archive roots within the triage lookback window. Tests must prove all history-search roots are subject to the same cutoff.

Dedup is byte-exact raw-byte hash dedup. Precedence is:

1. primary active
2. primary archive
3. legacy active
4. legacy archive
5. previous-primary hidden archive

Duplicate output must show the winning provenance with `path`, `storage_location`, and `source_root`.

Same-tier ties sort by lexical absolute path after containment checks, not by symlink-resolved escape paths.

Skipped invalid files must include the skipped path and reason.

### Distill

Default `/distill` uses the most recent eligible active handoff from the combined primary-active plus class-filtered legacy-active set during the reversal release, after byte-exact dedup with primary active winning and the Selection Ordering contract applied.

`/distill` never runs mutating transaction recovery and never archives, moves, copies, suppresses, or writes handoff files. It reads one selected source handoff and writes only its normal learnings output.

Explicit `/distill <path>` may target allowed primary or legacy active/archive paths, subject to the explicit-path validation rules.

## Required Surfaces

The reversal is not done unless all of these are reconciled:

- `plugins/turbo-mode/handoff/1.6.0/scripts/project_paths.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/search.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/triage.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/distill.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/quality_check.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/cleanup.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/handoff_parsing.py` or the new validator module
- the new shared path authority/helper CLI module, if added separately
- `plugins/turbo-mode/handoff/1.6.0/skills/load/SKILL.md`
- `plugins/turbo-mode/handoff/1.6.0/skills/save/SKILL.md`
- `plugins/turbo-mode/handoff/1.6.0/skills/summary/SKILL.md`
- `plugins/turbo-mode/handoff/1.6.0/skills/quicksave/SKILL.md`
- `plugins/turbo-mode/handoff/1.6.0/skills/search/SKILL.md`
- `plugins/turbo-mode/handoff/1.6.0/skills/distill/SKILL.md`
- `plugins/turbo-mode/handoff/1.6.0/skills/triage/SKILL.md`
- `plugins/turbo-mode/handoff/1.6.0/README.md`
- `plugins/turbo-mode/handoff/1.6.0/CHANGELOG.md`
- `plugins/turbo-mode/handoff/1.6.0/references/handoff-contract.md`
- `plugins/turbo-mode/handoff/1.6.0/references/format-reference.md`
- `plugins/turbo-mode/handoff/1.6.0/.codex-plugin/plugin.json`
- `plugins/turbo-mode/handoff/1.6.0/hooks/hooks.json`
- `.gitignore`
- `docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md`
- Handoff tests, including release metadata and CLI command tests
- installed-host storage smoke tests for the host-repo policy matrix
- Refresh classifier source, fixtures, inventory tests, and smoke tests, including `plugins/turbo-mode/tools/refresh/smoke.py`

`/save`, `/summary`, `/quicksave`, state cleanup, and dormant validation helpers or live quality hooks are explicitly in scope. If `.codex/handoffs/` is primary, these must stop writing or validating `docs/handoffs/` as the current target.

## Validation Helper And Hook Status

For this plan, hook-compatible validation helpers remain source-reconciled but dormant unless the implementation deliberately adds live hook wiring.

If validation remains dormant:

- source helpers and tests must recognize `.codex/handoffs/` as primary
- docs must call them dormant validation helpers, not live quality hooks
- closeout must not claim installed hook behavior

If validation becomes live:

- `hooks/hooks.json` and installed plugin metadata must expose the hook contract
- installed-config evidence must prove the hook is active
- source and installed-cache smoke must exercise the live hook path

## API And CLI Compatibility Ledger

The migration must classify existing script APIs and CLI subcommands as preserved, wrapper-preserved, deprecated with diagnostics, or intentionally removed. Closeout must include the final ledger and tests for each preserved or deprecated surface.

Minimum compatibility surface to classify:

- `plugins/turbo-mode/handoff/1.6.0/scripts/project_paths.py get_project_root`
- `plugins/turbo-mode/handoff/1.6.0/scripts/project_paths.py get_project_name`
- `plugins/turbo-mode/handoff/1.6.0/scripts/project_paths.py get_handoffs_dir`
- `plugins/turbo-mode/handoff/1.6.0/scripts/project_paths.py get_state_dir`
- `plugins/turbo-mode/handoff/1.6.0/scripts/project_paths.py get_legacy_handoffs_dir`
- compatibility surface for the historical `.codex/handoffs/.archive/` fallback used by `search.py` and `triage.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py archive`
- `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py write-state`
- `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py read-state`
- `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py clear-state`
- `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py allocate_archive_path`
- new or wrapped helper surface for `allocate-active-path`
- new or wrapped helper surface for `write-active-handoff`
- new or wrapped helper surface for `copy-legacy-archive-to-primary-archive`
- new or wrapped helper surface for active writer transaction recovery
- new or wrapped helper surface for `list-chain-state`
- `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py` public Python helpers used by tests
- `plugins/turbo-mode/handoff/1.6.0/scripts/search.py search_handoffs`
- `plugins/turbo-mode/handoff/1.6.0/scripts/search.py` previous-primary hidden archive fallback behavior
- `plugins/turbo-mode/handoff/1.6.0/scripts/search.py` re-exported parsing/path helpers used by tests or downstream imports
- `plugins/turbo-mode/handoff/1.6.0/scripts/triage.py generate_report`
- `plugins/turbo-mode/handoff/1.6.0/scripts/triage.py` previous-primary hidden archive fallback behavior
- `plugins/turbo-mode/handoff/1.6.0/scripts/triage.py` CLI fallback and report output shape
- `plugins/turbo-mode/handoff/1.6.0/scripts/distill.py` explicit path handling and CLI output shape
- `plugins/turbo-mode/handoff/1.6.0/scripts/quality_check.py is_handoff_path`
- `plugins/turbo-mode/handoff/1.6.0/scripts/quality_check.py` CLI output and dormant-helper behavior
- `plugins/turbo-mode/handoff/1.6.0/scripts/cleanup.py` state cleanup behavior
- `plugins/turbo-mode/handoff/1.6.0/scripts/handoff_parsing.py` frontmatter and section parsing behavior
- Handoff skill command surfaces for load, save, summary, quicksave, search, distill, and triage
- Refresh smoke labels and helper paths that exercise Handoff archive/state behavior

Existing `session_state.py` subcommands may become wrappers around the new helper entrypoints, but preserved commands must keep documented output fields or emit explicit deprecation diagnostics. The existing `archive` command must not be used as the legacy-active copy path unless its mode is made non-destructive for legacy inputs; legacy copy must go through `copy-legacy-active-to-primary-archive` or an equivalent explicitly named copy mode.

Backward-compatibility tests must lock the intended old surface. Skill-doc tests must be updated deliberately rather than made to pass by removing old assertions without a replacement contract.

## Generated Stale-Text Gate

The stale-text gate must use generated inventory, not a soft preference or narrow manual list.

The inventory source of truth is the generated artifact at `plugins/turbo-mode/handoff/1.6.0/tests/fixtures/storage_authority_inventory.json`.

Generation and verification must be separate commands:

- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py --write` updates the committed artifact.
- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py --check` verifies the committed artifact is current and must not mutate files.

Bootstrap rule: the first implementation pass may create the generator and artifact with `--write`. After the artifact exists, all verification and closeout uses `--check`, and `--check` must be no-write.

The inventory generator must emit the committed or reviewable artifact containing:

- generated authority path list
- blocked pattern list
- explicit historical allowlist entries
- per-path scan results
- failures with path, line, pattern, and reason

The gate passes only when this artifact or result is current with the source tree and has no unallowlisted blocked matches. Verification must include a no-dirty-tree check after `--check` for the inventory artifact and any generated scan outputs.

The stale-text gate must scan runtime warning strings as well as prose.

Allowed stale text examples:

- historical evidence
- older changelog entries
- tests seeding legacy input
- migration docs that label `docs/handoffs/` as legacy

Blocked stale text examples:

- current primary claims for `docs/handoffs/`
- warnings that `.codex/handoffs/` is legacy
- `next save writes to docs/handoffs`
- installed-cache paths as storage authority

## Required Tests

Minimum edge coverage:

- missing primary with valid legacy
- invalid primary with valid legacy
- legacy active exists, then new primary active exists, and default list/load still sees the eligible legacy active candidate during the cutover release
- untracked valid `docs/handoffs/*.md` legacy active in a host repo with no ignore rule remains eligible during cutover and is copied/suppressed without mutating the source
- tracked durable `docs/handoffs/*.md` files are excluded from default active selection unless an exact reviewed runtime migration opt-in names the path and hash
- tracked `.codex/handoffs/*.md` primary source files are reported as blocked and are not moved by implicit or explicit load
- successful legacy load copies to primary archive, writes primary state, writes consumed legacy-active registry, and removes the loaded legacy source from later active-selection list/load results
- changed bytes at the same legacy source path are treated as a new candidate rather than suppressed by path alone
- transaction coverage for read-only recovery inventory over pending transactions, interruption after archive mutation, interruption after active writer output, interruption after state write, duplicate retry, and concurrent attempts for primary active, primary archive, legacy active, legacy archive, save, summary, and quicksave paths
- read-only list/distill/search/triage/state inventory never completes, rolls back, suppresses, clears, marks, or writes transaction recovery artifacts
- save/summary/quicksave active writes call `begin-active-write` before content generation, allocate paths only through `allocate-active-path`, write only under `.codex/handoffs/`, use atomic temp-plus-rename semantics, and clear or mark chain state under the same project lock
- two save/summary/quicksave calls with the same timestamp slug allocate deterministic collision-safe active paths through at least base, `-01`, and `-02`
- save/summary/quicksave fails or enters recoverable transaction state rather than reporting success when active output is written but state cleanup fails
- implicit load chooses the newest valid active candidate from combined primary-active and legacy-active discovery after dedup
- load/list/distill recency uses filename timestamp, not filesystem mtime
- filename timestamp ties prefer primary active over legacy active, then lexical absolute path
- active-selection, history-search, explicit-path, and state-bridge scan modes have separate fixture coverage
- summary arc synthesis uses history-search candidates across primary active, primary archive, legacy active, legacy archive, and previous-primary hidden archive
- explicit `/load <path>` behavior for primary active, primary archive, legacy active, legacy archive, and previous-primary hidden archive
- no-frontmatter archive history is available only through history search with `document_profile=historical_archive`
- unreadable roots
- invalid frontmatter
- hidden files
- nested files
- explicit-path legacy archive behavior, history-search legacy archive behavior, and active-selection exclusion of legacy archives
- previous-primary hidden archive `.codex/handoffs/.archive/*.md` participates in history search and explicit archive load compatibility but never active selection
- repeated explicit previous-primary hidden archive load for the same lexical source path plus raw-byte hash reuses the same verified primary archive path from `copied-legacy-archives.json`
- `.session-state/` rejection
- file symlink escape
- directory symlink escape
- non-regular files
- duplicate hashes across all five history-search precedence tiers
- same-tier path-sort ties
- collision allocation through at least base, `-01`, and `-02`
- collision budget exhaustion
- non-git cwd storage, project naming, state filename, and cleanup
- installed-host smoke for no `.codex/` ignore reports untracked `.codex/handoffs/` runtime files without editing host ignore files
- installed-host smoke for broad `.codex/` ignore reports ignored `.codex/handoffs/` runtime files without using source-repo ignore proof
- installed-host smoke for tracked `.codex/skills/**` with narrow handoff ignore proves `.codex/skills/<sample>` remains tracked or trackable
- installed-host smoke for tracked `.codex/handoffs/<candidate>.md` treats the path as occupied and avoids overwrite
- installed-host smoke for tracked `.codex/handoffs/<active-source>.md` selected for load fails closed before moving the source
- installed-host smoke asserts installed helper and skill-doc realpaths are outside the source checkout before any behavior assertion counts as installed proof
- search/triage provenance output visibly selecting primary over legacy
- pre-upgrade legacy state plus post-upgrade save/summary/quicksave preserves `resumed_from`, writes only under `.codex/handoffs/`, and clears the consumed legacy state
- bridged legacy state cleanup proves a second bridge lookup returns no usable state after deletion or durable consumed marking
- project-scoped state bridge lookup succeeds without caller-provided resume token when exactly one valid project state exists
- valid primary state plus unresolved same-project legacy state fails before active output creation and requires explicit operator-selected recovery
- multiple valid primary state candidates for the same project fail with an ambiguity diagnostic
- multiple valid legacy candidates for the same project fail with an ambiguity diagnostic when no primary state exists
- malformed, expired, ambiguous, or multiply matching legacy state emits an actionable diagnostic
- top-level `docs/handoffs/handoff-*` and `docs/handoffs/handoff-*.json` state-like residue is inventoried, classified, and either validly bridged or diagnostically rejected
- canonical-checkout local-preflight evidence includes the `canonical-checkout` residue scope and one disposition row per current top-level `docs/handoffs/handoff-*` or `docs/handoffs/handoff-*.json` path
- `docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md` uses `scope` values to separate `repo-authority`, `local-preflight-summary`, and `policy-rule` rows and does not list ignored or untracked local residue as fresh-clone truth
- `.codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json` includes one local-preflight disposition row per current `docs/handoffs/handoff-*` and `docs/handoffs/handoff-*.json` path, with no `TBD` dispositions
- explicit legacy archive load repeated for the same lexical source path plus raw-byte hash reuses the same verified primary archive path from `copied-legacy-archives.json`
- copied legacy-archive registry entries include lexical source path, resolved path, source hash, copied archive path, copied hash, timestamp, operation, recovery status, and transaction id
- copied legacy-archive registry corruption or missing copied archive content fails with a recovery diagnostic instead of silently allocating a duplicate copy
- active-writer transaction records include active output fields such as `allocated_active_path`, `temp_active_path`, `output_sha256`, and state cleanup action rather than relying on archive-only fields
- active-writer idempotency keys exclude `transaction_id` and generated content hash, while transaction records keep those values as separate fields
- active-writer retry with the same idempotency key and changed generated bytes fails with a typed diagnostic instead of creating a second active handoff
- active-writer recovery covers `pending_before_write`, `written_not_confirmed`, `cleanup_failed`, and `content_mismatch`
- ambiguous same-project state emits a candidate inventory and supports an explicit operator recovery path without guessing
- `.codex/handoffs/*.md`, `.codex/handoffs/archive/*.md`, and `.codex/handoffs/.session-state/*.json` are ignored
- `.codex/handoffs/.session-state/**`, including locks, transactions, markers, temp files, and recovery records, is ignored
- archive temp files such as `.codex/handoffs/archive/.tmp-*` and `.codex/handoffs/archive/*.tmp` are ignored
- existing `docs/handoffs/*.md`, `docs/handoffs/archive/*.md`, and `docs/handoffs/.session-state/*.json` ignore behavior is preserved
- `.codex/skills/<sample>` is not ignored by the handoff runtime ignore rule
- load/list/distill/save/summary/quicksave docs call helper entrypoints and do not retain stale shell-only path logic
- chain-state helper docs preserve direct-Python launcher class and do not regress to dependency-bearing `uv run`
- compatibility ledger tests cover preserved, wrapper-preserved, and deprecated script APIs/CLI subcommands
- discovery/search/triage tests fail on broad exception swallowing that drops path-specific skip reasons
- dormant validation helper closeout does not claim live hook behavior, or live hook closeout includes installed-config proof

## Required Verification Commands

Source repair closeout must name the exact commands run. Minimum command selectors:

Preflight before implementation:

```bash
git branch --show-current
git status --short
git status --short --untracked-files=all
git status --short --ignored --untracked-files=all docs/handoffs
git ls-files docs/handoffs
find docs/handoffs -mindepth 1 -print | sort
find docs/handoffs -maxdepth 1 -name 'handoff-*' -print | sort
find .codex/handoffs/.archive -maxdepth 1 -name '*.md' -print 2>/dev/null | sort
git check-ignore -v docs/handoffs/.session-state docs/handoffs/archive docs/handoffs/example.md
git status --short -- docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md
git status --short --ignored -- .codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json
```

The implementation branch for this execution is a fresh named implementation branch from current `main` in the canonical checkout, using this repo's `feature/*` branch-prefix policy. Direct implementation on `main` is not allowed. Branch switching is forbidden from a worktree with unrelated modified, deleted, or untracked paths. If `git status --short --untracked-files=all` shows anything outside the reviewed control document, repo-authority residue ledger, and explicitly ignored local-preflight evidence, stop and repair the checkout hygiene or revise this plan before code changes. Do not move, stash, delete, or normalize unrelated user work as part of this plan.

The preflight must classify tracked durable handoff artifacts, ignored legacy operational artifacts, untracked legacy operational artifacts, previous-primary hidden archive artifacts, state-like residue, and policy-conflict artifacts before code changes. Collapsed directory-only status output is not sufficient; path-level inventory from `find` or an equivalent enumerator is required. The control document and repo-authority residue ledger must be tracked or otherwise explicitly recorded as durable implementation authority before source code changes begin. Local residue enumeration belongs in ignored local-preflight evidence and must not be presented as fresh-clone repo truth.

```bash
uv run pytest \
  plugins/turbo-mode/handoff/1.6.0/tests/test_project_paths.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_session_state.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_search.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_triage.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_distill.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_cli_commands.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_release_metadata.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_skill_docs.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_quality_check.py \
  plugins/turbo-mode/handoff/1.6.0/tests/test_cleanup.py
```

Full Handoff package suite:

```bash
uv run pytest plugins/turbo-mode/handoff/1.6.0/tests
```

```bash
uv run pytest \
  plugins/turbo-mode/tools/refresh/tests/test_classifier.py \
  plugins/turbo-mode/tools/refresh/tests/test_planner.py \
  plugins/turbo-mode/tools/refresh/tests/test_smoke.py
```

```bash
uv run python plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py --check
git diff --exit-code -- plugins/turbo-mode/handoff/1.6.0/tests/fixtures/storage_authority_inventory.json
git status --short -- plugins/turbo-mode/handoff/1.6.0/tests/fixtures/storage_authority_inventory.json
```

Implementation-time artifact updates may run `uv run python plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py --write` before committing the generated artifact. Closeout verification must not run `--write`.

The closeout must report that `--check` left `plugins/turbo-mode/handoff/1.6.0/tests/fixtures/storage_authority_inventory.json` and any generated scan output unchanged.

Ignore-policy verification must include:

```bash
git check-ignore -v .codex/handoffs/example.md
git check-ignore -v .codex/handoffs/archive/example.md
git check-ignore -v .codex/handoffs/.session-state/example.json
git check-ignore -v .codex/handoffs/.session-state/locks/example.lock
git check-ignore -v .codex/handoffs/.session-state/transactions/example.json
git check-ignore -v .codex/handoffs/.session-state/markers/example
git check-ignore -v .codex/handoffs/archive/.tmp-example
git check-ignore -v .codex/handoffs/archive/example.tmp
git check-ignore -v docs/handoffs/example.md
git check-ignore -v docs/handoffs/archive/example.md
git check-ignore -v docs/handoffs/.session-state/example.json
```

It must also include a documented negative check proving a `.codex/skills/<sample>` path is not ignored by the new handoff runtime rules. The negative check is expected to exit non-zero; the closeout must report that expected non-match explicitly.

Residue verification must include two checks:

- a repo-authority ledger check that fails if `docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md` lacks a `scope` column or contains ignored/untracked local residue rows as `repo-authority`
- a local-preflight evidence check that compares the current preflight inventory to `.codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json` and fails if any current `docs/handoffs/handoff-*` or `docs/handoffs/handoff-*.json` path lacks a local disposition row

Installed-host matrix verification must include the installed plugin/helper path, not source-only imports. The implementation may add a focused test or smoke command, but closeout must name the exact command. A source-tree pytest selector is allowed only as an orchestrator that resolves and executes the installed plugin code path. Minimum selector if implemented as pytest:

```bash
uv run pytest plugins/turbo-mode/handoff/1.6.0/tests/test_installed_host_repo_storage.py
```

That smoke must create temporary host repos for no `.codex/` ignore, broad `.codex/` ignore, tracked `.codex/skills/**` with narrow handoff ignore, tracked handoff-path collision, tracked primary active source, and non-git project roots. It must assert the helper-reported `target_git_visibility` and `source_git_visibility` values where applicable, and prove no host ignore file or index is edited by Handoff.

The smoke must also assert that the helper and skill-doc realpaths under test are outside the source checkout. A run that imports `plugins/turbo-mode/handoff/1.6.0/scripts/*` from this source tree is source verification, not installed-host verification, and cannot earn `installed host matrix certified` or `installed cache certified`.

## Evidence Status Gates

Closeout must use exactly one label:

- `source repaired`: source, docs, source-repo ignore policy, generated stale-text gate, helper tests, skill-doc surface tests, refresh classifier tests, active-writer transaction tests, and source refresh smoke tests pass; installed-host matrix smoke, installed cache, and live hook behavior are not claimed current.
- `refresh-ready but not mutated`: all `source repaired` gates pass, plus refresh evidence says mutation is ready, but live installed-cache mutation was not run.
- `installed host matrix certified`: all `source repaired` gates pass, installed plugin/helper smoke covers the host-repo policy matrix, and no broader installed-cache certification or live hook claim is made beyond that matrix.
- `installed cache certified`: source/cache equality or approved divergence proof exists, installed cache was refreshed or verified current, installed-host matrix smoke passes, installed-cache smoke passes, the installed skill docs are the docs under test, and any live hook claim has installed-config proof.

## Implementation Order

Use named internal commit gates so the implementation does not become one long unstable branch. Each gate must leave the worktree in a reviewable state or document why verification is intentionally incomplete at that gate.

1. `gate-0a-control-authority-and-ignore-policy`: Create or switch to the fresh `feature/handoff-storage-reversal-main` implementation branch from current `main` in the clean canonical checkout. Run preflight, classify `docs/handoffs/**` artifacts with path-level inventory, commit or otherwise durably record this control document, add the repo-authority residue ledger, and patch the narrow source-repo `.codex/handoffs/**` ignore policy. This gate may edit `.gitignore` and plan artifacts only; it must prove `.codex/handoffs/.session-state/preflight/**` is ignored and `.codex/skills/<sample>` is not ignored before local-preflight evidence is generated.
2. `gate-0b-local-preflight-evidence`: Generate ignored local-preflight residue evidence after the ignore-policy patch is verified, and confirm the evidence file appears only as ignored local runtime evidence.
3. `gate-1a-discovery-contract-tests`: Add cutover inventory, scan-mode, artifact-class filtering, source-visibility filtering, validation, candidate reason, dedup, ordering, and ignore-policy tests before changing reader behavior.
4. `gate-1b-load-transaction-tests`: Add primary active/archive, tracked primary active source fail-closed behavior, legacy active/archive, consumed legacy-active registry, copied legacy-archive registry, read-only recovery inventory, mutating recovery, and explicit load idempotency tests before changing load behavior.
5. `gate-1c-active-writer-tests`: Add save/summary/quicksave begin/write protocol, helper-minted run id persistence, active allocation, atomic write, idempotency key, changed-content retry failure, retry/recovery state, and state cleanup tests before changing writer behavior.
6. `gate-1d-state-bridge-tests`: Add project-scoped legacy-state bridge, state-like residue handling, ambiguous state diagnostic, primary-state-plus-unresolved-legacy fail-closed behavior, and operator recovery tests before changing state bridge behavior.
7. `gate-1e-installed-host-contract-tests`: Add installed-host smoke orchestration tests that resolve installed plugin realpaths outside the source checkout. This gate may stay pending for `source repaired`, but it is mandatory before installed-host certification.
8. `gate-2-shared-helpers`: Add the shared path authority, discovery, validation module, helper CLI entrypoints, active writer APIs, launcher-class assertions, and compatibility ledger.
9. `gate-3-reader-loader-cutover`: Rewire `/load`, `/list-handoffs`, `/search`, `/triage`, and `/distill` to the shared module and helper entrypoints, including explicit legacy archive idempotency.
10. `gate-4-writer-cutover`: Rewire `/save`, `/summary`, `/quicksave`, and cleanup behavior to `allocate-active-path`, `write-active-handoff`, chain-state bridge, and transaction recovery helpers.
11. `gate-5-skill-docs-release-docs`: Reconcile skill docs, dormant validation helpers or live hooks, README, changelog, contract docs, and release metadata with `.codex/handoffs/` as primary.
12. `gate-6-refresh-and-stale-text`: Reconcile refresh classifier source, fixtures, inventory tests, `plugins/turbo-mode/tools/refresh/smoke.py`, the generated stale-text gate, `storage_authority_inventory.json`, and separate `--write`/`--check` inventory commands.
13. `gate-7-source-closeout`: Run source verification and assign the exact evidence status gate.
14. `gate-8-installed-certification`: Only after source repair is proven, decide whether to run installed-cache refresh/certification and the installed-host matrix smoke.

## Hard Stop Conditions

Stop implementation and repair the contract before continuing if any of these occur:

- Preflight does not classify `docs/handoffs/**` artifacts or the branch/worktree state before implementation.
- Preflight relies on collapsed `docs/handoffs/` status output instead of path-level artifact enumeration.
- Implementation proceeds directly on `main` instead of a fresh named implementation branch from current `main`.
- Branch switching or implementation starts from a dirty worktree with unrelated modified, deleted, or untracked paths instead of stopping and repairing checkout hygiene.
- A non-canonical implementation worktree is introduced without first revising this plan, the residue ledger, and the local-preflight evidence schema.
- Source code implementation starts while this control document is still untracked or not otherwise recorded as durable implementation authority.
- Local-preflight evidence is generated before the narrow source-repo `.codex/handoffs/**` ignore policy is patched and verified.
- The tracked residue ledger lists ignored or untracked machine-local residue paths as `repo-authority` fresh-clone facts.
- Any local-preflight `docs/handoffs/handoff-*` or `docs/handoffs/handoff-*.json` path lacks an ignored local-preflight evidence row with scope, explicit disposition, and verification hook.
- The policy-authority override is used to delete, untrack, or reclassify tracked durable handoff artifacts as disposable.
- Default active selection includes tracked durable `docs/handoffs/*.md` artifacts without an exact reviewed runtime migration opt-in path and hash.
- Default active selection excludes valid ignored or untracked legacy operational `docs/handoffs/*.md` files during the cutover release without a documented diagnostic that intentionally blocks them.
- Previous-primary hidden archive files under `.codex/handoffs/.archive/*.md` disappear from history search or explicit archive-load compatibility without a compatibility-ledger decision and tests.
- A tracked `.codex/handoffs/*.md` source file is moved, archived, suppressed, or otherwise mutated by implicit or explicit primary load.
- Source-repo `.gitignore` checks are treated as proof of installed-host behavior.
- Handoff edits a host repo's `.gitignore`, `.git/info/exclude`, tracked `.codex/**` content, or index state during normal save/load/list/search/summary/quicksave behavior.
- Installed-host smoke does not cover no ignore, broad `.codex/` ignore, tracked `.codex/skills/**`, tracked handoff-path collision, tracked primary active source, and non-git project-root cases before claiming installed-host readiness.
- Installed-host smoke imports or executes Handoff helpers from the source checkout, or fails to assert installed helper and skill-doc realpaths outside the source checkout.
- A writer still writes current handoffs or chain state under `docs/handoffs/`.
- Save, summary, or quicksave constructs active output paths outside `allocate-active-path` or writes active markdown outside `write-active-handoff`.
- Save, summary, or quicksave reports success after writing active output while chain-state cleanup remains failed, ambiguous, or recoverable-only.
- Save, summary, or quicksave generates final content before `begin-active-write` has persisted a stable run id, state snapshot, and allocated path.
- Active-writer idempotency key includes `transaction_id` or generated content hash.
- Active-writer retry after partial write can create a second active handoff for the same idempotency key.
- Active-writer retry with the same idempotency key but changed generated bytes proceeds without an explicit `ActiveWriteContentChangedError` or equivalent diagnostic.
- Default `/list-handoffs` or implicit `/load` hides eligible legacy active files during the cutover release just because primary active files exist.
- Default `/list-handoffs`, implicit `/load`, or default `/distill` treats `docs/handoffs/archive/` as active-selection input.
- Read-only `/list-handoffs`, `/distill`, `/search`, `/triage`, or state inventory completes, rolls back, suppresses, clears, or marks a pending transaction instead of only reporting read-only recovery inventory.
- A successful legacy load leaves the loaded legacy active source visible to later active-selection scans without changed bytes.
- A legacy load can produce duplicate primary archive/state records for one source/hash after retry or concurrent load.
- Repeated explicit legacy archive load for the same lexical source path plus raw-byte hash creates duplicate primary archive copies instead of reusing the copied legacy-archive registry.
- Any mutating load/state path bypasses the project lock, transaction record, atomic write, or recovery protocol.
- Any active writer bypasses the project lock, transaction record, atomic write, or recovery protocol.
- A transaction interruption can leave inconsistent active/archive/state/registry artifacts without a recovery diagnostic.
- A legacy load moves, deletes, archives into, or writes state under `docs/handoffs/`.
- A post-upgrade save/summary/quicksave silently loses a valid pre-upgrade `resumed_from` link.
- A state bridge requires a caller-provided resume token rather than preserving current project-scoped pending-state semantics.
- Ambiguous same-project state failure omits a candidate inventory or provides no explicit operator recovery path.
- A primary state winning rule silently consumes, clears, or marks unresolved same-project legacy state candidates without explicit operator-selected recovery.
- State-like residue under `docs/handoffs/handoff-*` is ignored silently instead of being classified.
- State-like residue is diagnostically rejected but left without local-preflight disposition, quarantine plan, consumed marker, or named blocker.
- A bridged legacy state can be read again after a supposedly successful cleanup.
- Source-repo `.codex/handoffs/` runtime files appear as ordinary untracked commit material during source repair closeout. This does not forbid expected installed-host `target_git_visibility=untracked` results in no-ignore host repos.
- Source-repo locks, transactions, markers, temp files, consumed registries, or recovery records under `.codex/handoffs/.session-state/**` appear as ordinary untracked commit material during source repair closeout. This does not forbid expected installed-host `target_git_visibility=untracked` results in no-ignore host repos.
- Existing `docs/handoffs/` runtime files stop being ignored without an explicit tracking-policy decision.
- Discovery drops invalid or skipped candidates without path-specific reason data.
- Discovery/search/triage swallows broad exceptions and drops candidate path diagnostics.
- Search or triage reports deduplicated results without winning provenance.
- Explicit `/load <path>` behavior differs by storage location without tests for every supported storage location.
- No-frontmatter historical archives disappear from history search without a deliberate compatibility decision and test.
- Skill docs retain direct shell globbing, `ls -t`, or hardcoded archive/state path construction instead of calling helper entrypoints.
- Chain-state helpers require `uv run` or third-party dependencies without an explicit launcher-class waiver.
- `/summary` project-arc synthesis keeps direct `docs/handoffs/archive/` scans or misses primary archive history after cutover.
- A preserved public script API or CLI subcommand is removed or silently changes output shape without a compatibility-ledger decision and test.
- `storage_authority_inventory.py --check` mutates files or lacks a corresponding `--write` update path.
- Closeout runs `storage_authority_inventory.py --write` instead of check-only verification.
- A closeout claims live hook behavior when validation helpers remain dormant.
- A closeout report implies installed-cache currency without installed-cache evidence.

## Boundary Ledger

Final implementation commit: TBD

Files modified by implementation:

- TBD

### Verification

TBD

### Evidence Status

TBD

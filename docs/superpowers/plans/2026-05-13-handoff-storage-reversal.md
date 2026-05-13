# Handoff Storage Reversal Implementation Control Document

## Status

Gate 0A/0B prep is committed on `feature/handoff-storage-reversal-main` at `bf83762`. The committed plan authority lineage before this working-tree revision is `4b5f6fc` -> `7effa25` -> `8fd78af` -> `2769186` -> `e9b416a` -> `688335a`. This document must not self-name the commit that contains it: until this revision is committed, it is a working-tree plan patch. Gate 0r must record the current committed plan boundary after this patch is committed and before any source implementation starts. Gate 0r remains open for branch/residue preflight refresh, TTL-sensitive residue reclassification, legacy-active markdown preflight, hard-stop matrix creation, gate proof-map creation, and the execution-economics controls below. Source implementation remains blocked until Gate 0r passes.

For this execution, `feature/handoff-storage-reversal-main` is the canonical implementation branch and checkout topology. Creating a different implementation branch, rebasing onto a different base, or moving execution into an isolated worktree is forbidden unless this plan is patched first; that patch must require regenerating both preflight evidence files from the new topology and updating the ledger/base-commit authority boundary before any Gate 0r evidence may be reused.

This document is the implementation contract for reversing Handoff storage authority from the live source's current `docs/handoffs/` primary policy to `.codex/handoffs/` as the post-cutover write/read target. Until the implementation commit lands, `.codex/handoffs/` is target authority, not current repo truth.

Done means all writers, readers, skill docs, helper scripts, tests, dormant validation helpers or live hooks, refresh classifier logic, refresh smoke, release docs, ignore policy, and stale-text gates move together. A partial reader-only migration is not closeout.

The `bf83762` commit recorded Gate 0A/0B prep evidence for the then-committed contract by tracking this control document and the repo-authority residue ledger, patching source-repo ignore policy, and recording canonical-checkout local preflight evidence for current top-level `docs/handoffs/handoff-*` residue paths. The `4b5f6fc` commit records the original post-review plan authority boundary, and later plan-only corrections through `688335a` record subsequent hardening. Those commits do not complete Gate 0r; Gate 0r remains open for branch/residue preflight refresh, TTL-sensitive local residue reclassification, legacy-active markdown preflight, hard-stop matrix creation, gate proof-map creation, and capacity-budget recording. Source implementation may start only after `gate-0r-review-reanchor-and-preflight-refresh` passes from the current committed plan boundary. Source repair closeout remains blocked until active writer creation is covered by helper APIs and end-to-end skill-flow transaction tests. Installed-host certification remains blocked until the host-repo policy matrix below is covered by source-proof installed-plugin smoke.

## Policy Authority Override

This plan is the explicit reviewed artifact required by Plan 06 for changing handoff policy around `docs/handoffs/**`. It names and overrides the instruction conflict for the Handoff plugin storage reversal only.

The conflict is:

- active workspace instructions classify repository handoff files under `docs/handoffs/` and `docs/handoffs/archive/` as durable project artifacts when tracked or intentionally included in durable repo state
- live Handoff `1.6.0` currently uses `docs/handoffs/` for operational session mechanics
- this reversal intentionally moves future Handoff operational session mechanics to `.codex/handoffs/`

This override does not make all `docs/handoffs/**` disposable. The implementation must classify `docs/handoffs/**` into these classes before changing policy or code:

- `tracked-durable-handoff-artifact`: any `git ls-files docs/handoffs` result, or any file explicitly named by a reviewed repo policy as durable. Preserve it; do not delete, untrack, treat it as operational cleanup, or include it in implicit active selection.
- `ignored-legacy-operational-handoff`: ignored top-level active handoff, checkpoint, or summary markdown under `docs/handoffs/*.md` created by the pre-cutover Handoff plugin and proven by the legacy provenance classifier below. Ignored git visibility is required for this class, but ignored status alone is not origin proof. Valid-looking ignored files without an accepted provenance proof are `policy-conflict-artifact`, not migration input. Archive and state paths must not use this active markdown class.
- `untracked-legacy-operational-handoff`: untracked `docs/handoffs/*.md` file that validates as a current-contract active handoff, checkpoint, or summary and is proven by the legacy provenance classifier below. Untracked git visibility is required for this class, but untracked status alone is not origin proof. Valid-looking untracked files without an accepted provenance proof are `policy-conflict-artifact`, not migration input.
- `legacy-operational-archive`: ignored or untracked archive markdown under `docs/handoffs/archive/*.md` created by the pre-cutover Handoff plugin. Treat it as read-only history-search and explicit-path input; never include it in active selection, never classify it with the legacy active markdown classifier, and preserve tracked or intentionally durable archive files under the tracked-durable rules.
- `legacy-state-bridge-input`: chain-state files under `docs/handoffs/.session-state/**` created by the pre-cutover Handoff plugin. Treat them only as bridge or recovery input under the Legacy State Bridge contract; never treat them as handoff markdown documents or active-selection candidates.
- `reviewed-runtime-migration-opt-in`: an exact legacy `docs/handoffs/**` path plus source hash named by a reviewed migration note as safe to treat as runtime migration input. This is the only way a tracked or otherwise durable-looking `docs/handoffs/**` file may enter runtime migration selection.
- `previous-primary-hidden-archive`: historical archive file under `<project_root>/.codex/handoffs/.archive/*.md` from the pre-`docs/handoffs/` storage generation. Treat it as read-only history-search and explicit-path input, copying or reusing a primary archive copy only through the explicit legacy archive transaction path.
- `state-like-residue`: files such as `docs/handoffs/handoff-*.json` or `docs/handoffs/handoff-*` outside `.session-state/`. Inventory them, classify them, and either bridge exactly one valid project state candidate or reject with a diagnostic; never treat them as handoff markdown documents.
- `non-handoff-filesystem-residue`: unsupported or incidental files under `docs/handoffs/**`, such as `.DS_Store`, local `.gitignore` files, non-markdown top-level files that are not state-like residue, archive non-markdown files, or other entries that are not handoff markdown, archive markdown, state bridge input, reviewed opt-in input, or state-like residue. Inventory them with an explicit out-of-scope disposition; never select, migrate, copy, delete, quarantine, or treat them as proof of handoff runtime provenance.
- `policy-conflict-artifact`: any artifact whose durable-vs-operational classification cannot be proven as eligible runtime migration input. This is a valid blocked disposition when a legacy-active preflight row records the path, hash when readable, missing provenance, `selection_eligibility=blocked-policy-conflict`, and verification hook. Stop before implementation only when a path has no explicit disposition, when the implementation would need to select it implicitly, or when an operator wants it treated as migration input without a reviewed opt-in.

The intended override is narrow: after cutover, newly written Handoff operational session artifacts go under `.codex/handoffs/`; durable repository documentation under `docs/handoffs/**` remains durable when tracked or intentionally included by repo policy.

Legacy active selection must be class-filtered before timestamp ordering. It may include only provenance-backed `ignored-legacy-operational-handoff`, provenance-backed `untracked-legacy-operational-handoff`, and exact `reviewed-runtime-migration-opt-in` files whose `storage_location` is `legacy_active`. It must exclude `tracked-durable-handoff-artifact`, `legacy-operational-archive`, `legacy-state-bridge-input`, `state-like-residue`, `non-handoff-filesystem-residue`, and `policy-conflict-artifact` files even when they look like valid current-contract handoff markdown.

### Legacy Provenance Classifier

Gate 1a must implement the legacy provenance classifier before any ignored or untracked `docs/handoffs/*.md` file may enter active selection. The classifier is allowed to return `ignored-legacy-operational-handoff` or `untracked-legacy-operational-handoff` only when every file-shape check passes and at least one provenance proof passes.

Required file-shape checks:

- The path is a top-level contained `docs/handoffs/*.md` file, not under `archive/`, `.session-state/`, a hidden basename, a symlink, a directory, a non-regular file, or a path escape.
- Git visibility is `ignored` or `untracked`. Tracked files use the tracked-durable or reviewed-opt-in path.
- The raw-byte SHA256 is computed after containment and regular-file checks.
- The filename has a parseable `YYYY-MM-DD_HH-MM_*.md` timestamp.
- The document validates as `current_contract` through the shared handoff validator, with frontmatter `project`, `created_at`, `session_id`, and `type` present or deliberately accepted by a named backward-compatibility rule. Type inference for old files may support validation, but type inference alone is not provenance.

Accepted provenance proofs:

- `plugin-origin-runtime-marker-provenance`: metadata outside ordinary handoff document content proves the file was generated by the pre-cutover Handoff plugin as runtime material. The proof must name the marker field or sidecar source, marker schema version, project, source root, project-relative path, raw-byte SHA256, and the helper or preflight command that verified it. Ordinary document frontmatter fields such as `session_id`, `type`, `project`, `created_at`, `branch`, `commit`, `resumed_from`, and `files` are runtime-shaped signals only; they are not origin proof by themselves because they are part of the normal handoff schema and can appear in copied or user-authored durable documents.
- `legacy-active-preflight-runtime-provenance`: current legacy-active preflight evidence names the exact lexical path, resolved path, project-relative path, raw-byte SHA256, git status class, detected document profile, and one accepted external origin source for this Gate 0r or later branch head. The accepted external origin source must be a plugin-origin marker or sidecar outside ordinary handoff frontmatter, or a reviewed tracked opt-in record naming the same path and hash. A local-preflight row that merely asserts "runtime material" or records runtime-shaped frontmatter is not provenance.
- `reviewed-runtime-migration-opt-in`: a reviewed tracked note names the exact project-relative path, raw-byte SHA256, source root, storage location, reviewer, and reason that this specific artifact is runtime migration input.

Gate 0r may create a tracked reviewed opt-in manifest for current valid-looking legacy active files that lack plugin-origin marker provenance but are intentionally selected for runtime migration. For this execution the manifest path is:

```text
docs/superpowers/plans/2026-05-13-handoff-storage-legacy-active-opt-ins.md
```

The opt-in manifest must be reviewed before Gate 1 source edits, must name each exact project-relative path plus raw-byte SHA256, and must explain why ordinary frontmatter was not accepted as origin proof. Any valid-looking ignored or untracked legacy active file not named in that manifest, not marker-backed, and not otherwise externally proven remains `policy-conflict-artifact` and is excluded from active selection without blocking implementation.

The canonical legacy-active provenance field set is `external_origin_source`, `origin_evidence_fields`, `missing_or_rejected_provenance_fields`, `artifact_class`, and `selection_eligibility`. `legacy_active_preflight.py` must emit exactly this field set for every valid-looking ignored or untracked legacy file; evidence must not emit separate `provenance_basis` or `matched_provenance_fields` aliases. If implementation code uses internal names, it must map deterministically to the evidence schema as `provenance_basis` -> `external_origin_source` and `matched_provenance_fields` -> `origin_evidence_fields` before writing or checking evidence. A file that passes document validation but lacks an accepted provenance proof is `policy-conflict-artifact` with `external_origin_source=none` and `selection_eligibility=blocked-policy-conflict`. Broad parser tolerance, runtime-shaped frontmatter, a plausible filename, ignored git visibility, or untracked git visibility is not enough to treat a file as runtime migration input.

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
| Legacy active | `<project_root>/docs/handoffs/*.md` | Read-only migration input during cutover only when classified as provenance-backed ignored legacy active markdown, provenance-backed untracked legacy active markdown, or exact reviewed opt-in; tracked durable docs and unproven valid-looking ignored or untracked docs are excluded from active selection |
| Legacy archive | `<project_root>/docs/handoffs/archive/*.md` | Read-only history-search and explicit-path input; never active-selection input |
| Previous-primary hidden archive | `<project_root>/.codex/handoffs/.archive/*.md` | Read-only history-search and explicit-path input for pre-`docs/handoffs/` archives; never active-selection input |
| Legacy state | `<project_root>/docs/handoffs/.session-state/*` | Read-once bridge input for chain writers; legacy bytes are never modified, deleted, or trashed by normal writers; suppression is recorded under primary state with durable markers; explicit loads rejected |
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

Git visibility is not filesystem safety. Post-cutover helper output for every path whose bytes could be read, moved, copied, written, suppressed, or used for collision allocation must also include filesystem status fields:

- `target_fs_status` for allocation and write destinations
- `source_fs_status` for source-backed operations

Allowed filesystem status values are `missing`, `regular-file`, `directory`, `symlink`, `non-regular`, `unreadable`, `parent-missing`, `parent-file-conflict`, `path-escape`, and `unknown`. Collision diagnostics must report both git visibility and filesystem status; an existing directory, symlink, unreadable file, non-regular file, or parent-file conflict is occupied or blocked even when git visibility is `untracked` or `unknown`.

For target allocation, expose git status as `target_git_visibility`. For source-backed operations, also expose `source_git_visibility` before mutation. A source path with `source_git_visibility=tracked-conflict` under `.codex/handoffs/**` is a tracked host file, not safe runtime material. Implicit and explicit primary load must fail closed with `TrackedRuntimeSourceError` or an equivalent typed diagnostic before moving it. Read-only inventory may report diagnostic reason `blocked_tracked_runtime_source`, but the machine `selection_eligibility` field for that row must remain `blocked-tracked-source`. Default active selection must not silently choose it. Explicit read-only `/distill <path>` may read it only through explicit-path validation because no handoff source bytes are moved or suppressed.

When a mutating command reports `target_git_visibility=untracked`, the helper JSON and the skill-facing human summary must also include:

- `ignore_rule_applied: false`
- `recommended_ignore_rule: ".codex/handoffs/"`
- a user-visible warning that the plugin intentionally did not edit host ignore policy and the new runtime file may appear in normal `git status`

The warning is required for `/save`, `/summary`, `/quicksave`, and any load or recovery command that writes under `.codex/handoffs/` in a no-ignore host repo. It must be non-mutating guidance only.

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

Installed-host source-proofing must be asserted in the harness, not inferred from command names. Before any installed-host behavior assertion counts, the harness must prove:

- The helper process runs with a temporary current working directory outside the source checkout.
- `PYTHONPATH` is unset or does not include the source checkout, and `sys.path` in the helper process has no source-checkout entry except Python standard library paths.
- Every loaded Handoff module under test reports `__file__` or `inspect.getfile()` under `installed_plugin_root`, never under `source_checkout_root`.
- `resolved_helper_path`, `resolved_skill_doc_path`, and every helper subprocess command path realpath are outside `source_checkout_root` and inside the pinned installed plugin root.
- The installed plugin manifest hash and version match the harness-pinned identity before host behavior is asserted.

If any source-checkout module is present in `sys.modules`, or if import resolution can find the source checkout before the installed root, the run is source verification only and cannot emit `installed-harness-source-proof`, `installed host matrix behavior proved`, `installed host matrix certified`, or `installed cache certified`.

### Installed Host Harness

Installed-host certification requires a first-class harness before any installed-host claim counts. The harness has four distinct evidence labels, and labels must not cross between them:

- `isolated harness layout proof only` is a development-only bootstrap label. It may use a test-only installer to prove the harness can create an isolated layout, but it does not satisfy `source-harness-isolation-proof`, `installed-harness-source-proof`, `installed host matrix behavior proved`, or any installed-cache label.
- `source-harness-isolation-proof` mode is Gate 1f source repair. It may use a test-only installer or fixture plugin root only when the app-server install path is not available inside source tests. It must record that installer as non-equivalent to installed-cache refresh, then prove the harness assertions for cache isolation, manifest identity, realpath separation, helper cwd isolation, import isolation, and source-checkout leak rejection. It must not run or report the Installed Host Repo Policy Matrix as behavior proof, and it must not claim app-server-installed source proof.
- `installed-harness-source-proof` mode is post-source-repair refresh readiness evidence. It must install the Handoff plugin into an isolated `CODEX_HOME` through the guarded-refresh app-server install authority path, then prove installed-root resolution, cache isolation, manifest identity, realpath separation, helper cwd isolation, and import isolation. It must not run or report the Installed Host Repo Policy Matrix as behavior proof.
- `installed-host-behavior-proof` mode is Gate 5 certification. It must install through the guarded-refresh app-server install authority path, create disposable host repos for every Installed Host Repo Policy Matrix row, and run behavior assertions from the installed plugin root. Only this mode may emit `installed-host behavior proof`, `installed host matrix behavior proved`, `installed host matrix certified`, or `installed cache certified`.

The harness must be source-proof and cache-safe:

- Create an isolated temporary `CODEX_HOME` for the smoke unless the operator explicitly requests a real-home guarded refresh. The default harness must not mutate `/Users/jp/.codex`, the user's active plugin cache, global config, host ignore files, or host indexes.
- Install the Handoff plugin into the isolated `CODEX_HOME` through the guarded-refresh app-server install authority path only for `installed-harness-source-proof` or `installed-host-behavior-proof` modes: `plugins/turbo-mode/tools/refresh/app_server_inventory.py` request builders and `plugins/turbo-mode/tools/refresh/mutation.py` install orchestration, invoked through `plugins/turbo-mode/tools/refresh_installed_turbo_mode.py` when the gate is allowed to exercise installed behavior. If Gate 1f uses a test-only installer because the app-server path is not available inside source tests, the evidence label may be no stronger than `source-harness-isolation-proof`, must record the non-equivalent installer, and must not use installed-host behavior or app-server-installed proof language.
- Pin plugin identity from `plugins/turbo-mode/handoff/1.6.0/.codex-plugin/plugin.json`, including `name`, `version`, manifest SHA256, source checkout root, installed plugin root, resolved helper path, resolved skill doc path, and install method.
- In Gate 1f source-harness mode, create only the minimal disposable host or non-git directory needed to prove cwd, realpath, manifest, and import isolation through the isolated root. Do not run host-policy behavior rows or report behavior assertions.
- In installed-harness-source-proof mode, rerun the same source-proof assertions through the app-server-installed isolated root before claiming refresh-ready or installed certification labels.
- In Gate 5 behavior-proof mode, create disposable host repos for each row in the Installed Host Repo Policy Matrix, then run helpers from the installed plugin root with the source checkout removed from `PYTHONPATH` and import resolution. The helper subprocess must emit the source-proof fields above in the same summary as the behavior assertions.
- Record cleanup policy and artifact roots. Temporary host repos may be removed after the summary is written, but the summary must retain enough path, manifest, command, and SHA256 evidence to reproduce the proof. Local-only raw output belongs under the refresh local-only evidence root, not in tracked source docs.

Gate 1f must add this harness in source-test form without mutating the real installed cache. Gate 4 may claim `source repaired` only after Gate 1f has produced `source-harness-isolation-proof`; it must not imply app-server-installed source proof. `refresh-ready but not mutated`, `installed host matrix certified`, and `installed cache certified` require the stricter `installed-harness-source-proof` label from an isolated app-server-installed root. Gate 5 is the earliest point where an installed-host behavior or installed-cache certification label may be claimed, and only evidence produced through the app-server install authority path may use the label `installed-host behavior proof`.

### Residue Disposition Artifacts

Preflight handling has four separate evidence and accounting surfaces with different authority scopes:

1. A tracked repo-authority ledger for clone-global policy and tracked or intentionally durable repo facts.
2. An ignored local-preflight evidence file for this machine's state-like residue corpus.
3. An ignored legacy-active preflight evidence file for this machine's valid-looking `docs/handoffs/*.md` active legacy corpus.
4. Explicit out-of-scope rows for non-handoff filesystem residue under `docs/handoffs/**`, recorded in ignored local-preflight evidence so these paths cannot remain implicit.

The tracked repo-authority ledger path is:

```text
docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md
```

The repo-authority ledger must include a `scope` column for every row. Allowed values are:

- `repo-authority`: tracked or intentionally durable repo fact that must be true in a fresh clone
- `local-preflight-summary`: summary row that references local evidence by run id, timestamp, count, and evidence hash, but does not claim the local paths exist in fresh clones
- `policy-rule`: durable classification or disposition rule that applies to future implementations

The state-like residue local-preflight evidence path is ignored runtime evidence under:

```text
.codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json
```

Gate 0r must add a concrete checker for this evidence and the tracked ledger before source edits:

```bash
python plugins/turbo-mode/tools/handoff_storage_reversal/residue_preflight.py \
  --project-root . \
  --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md \
  --ledger docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md \
  --evidence .codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json \
  --write
```

```bash
python plugins/turbo-mode/tools/handoff_storage_reversal/residue_preflight.py \
  --project-root . \
  --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md \
  --ledger docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md \
  --evidence .codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json \
  --check
```

The checker must be stdlib-only, must not import storage implementation modules, and must enumerate every current path under `docs/handoffs/` with `find docs/handoffs -mindepth 1 -print` semantics or an equivalent contained path walker. `--write` may create or refresh the ignored evidence during Gate 0r. `--check` must be no-write and fail when evidence is missing, stale against current path inventory, missing required fields, contains `TBD`, leaves any `docs/handoffs/**` path without a row, delegated evidence reference, or permitted directory-summary manifest reference for archive/state descendants, leaves any state-like residue row with historical plain `bridge-once`, or grants handoff active-selection eligibility to any row outside the legacy-active checker.

The checker may delegate top-level `docs/handoffs/*.md` active markdown classification to `legacy_active_preflight.py`; delegated rows must name the legacy-active evidence file, evidence SHA256, delegated project-relative path, and delegated artifact class. Delegation is not allowed for state-like residue, `.session-state/**` state bridge inputs, archive paths, previous-primary hidden archives, or non-handoff filesystem residue.

The checker must also validate the tracked residue ledger. It must fail if the ledger lacks a `scope` column, uses values outside `repo-authority`, `local-preflight-summary`, and `policy-rule`, lists ignored or untracked machine-local paths as `repo-authority`, or contains a `policy-rule` row for `docs/handoffs/*.md` active legacy files that omits the current control-document requirement: only provenance-backed ignored legacy active markdown, provenance-backed untracked legacy active markdown, or exact reviewed path-plus-raw-byte-hash opt-in with `storage_location=legacy_active` may enter runtime migration selection. Ledger policy drift is a Gate 0r blocker even when local evidence rows are otherwise complete.

The state-like residue local-preflight evidence file must enumerate every current path matched by `docs/handoffs/handoff-*` and `docs/handoffs/handoff-*.json` at preflight time, plus any non-handoff filesystem residue under `docs/handoffs/**` that is not delegated to another preflight class. It is not legacy active markdown provenance and must not be used to make `docs/handoffs/*.md` handoff documents eligible for active selection. Each state-like row must include:

- lexical path and resolved containment-checked path
- inventory scope: `canonical-checkout`
- git status class: tracked, ignored, untracked, or missing-after-inventory
- raw-byte SHA256 when readable
- detected format: tokenized state JSON, legacy plain state, invalid state-like residue, or non-state residue
- project and resume token when derivable
- disposition: Gate 0r refreshed rows must use `bridge-once-fresh`, `expired-bridge-rejected`, `operator-recovery-only`, `consumed-or-abandoned`, `mark-consumed`, `quarantine-ignored-state`, `reject-diagnostic`, `preserve-durable`, or `blocked-policy-conflict`. Historical Gate 0B evidence may contain plain `bridge-once`, but Gate 1 must not proceed until that row is refreshed or reclassified.
- rationale and verification command or test that proves the disposition
- scope: `local-preflight`

Each non-handoff filesystem residue row must include lexical path, resolved containment-checked path, project-root-relative path, git status class, filesystem status, raw-byte SHA256 when readable, artifact class `non-handoff-filesystem-residue`, disposition `out-of-scope-preserve`, rationale, verification command or delegated evidence reference when applicable, and scope `local-preflight`. These rows are diagnostic accounting only; they must not become active-selection, history-search, explicit-path, state-bridge, migration, or cleanup input.

Rows for legacy archive paths and legacy state scope paths that are not delegated to `legacy_active_preflight.py` must include lexical path, resolved containment-checked path, project-root-relative path, git status class, filesystem status, raw-byte SHA256 when readable, artifact class `legacy-operational-archive`, `legacy-state-bridge-input`, or `non-handoff-filesystem-residue`, disposition `scope-owned-by-history-search`, `scope-owned-by-state-bridge`, or `out-of-scope-preserve`, rationale, verification command, and scope `local-preflight`. Strict per-file rows remain required for top-level `docs/handoffs/*.md` active markdown, top-level state-like residue, and any top-level non-handoff residue. Descendants under churn-prone scope roots such as `docs/handoffs/archive/` and `docs/handoffs/.session-state/` may instead be represented by a directory row that includes descendant count, a sorted manifest hash, manifest generation command, and explicit scope-owned disposition; if the directory row is absent, markdown archive files and state payload files under those roots still need their own rows or explicit skip reasons.

The legacy-active preflight evidence path is ignored runtime evidence under:

```text
.codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json
```

Gate 0r must add a concrete checker for this evidence before source edits:

```bash
python plugins/turbo-mode/tools/handoff_storage_reversal/legacy_active_preflight.py \
  --project-root . \
  --evidence .codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json \
  --write
```

```bash
python plugins/turbo-mode/tools/handoff_storage_reversal/legacy_active_preflight.py \
  --project-root . \
  --evidence .codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json \
  --check
```

The checker must be stdlib-only, must not import storage implementation modules, and must enumerate only current top-level `docs/handoffs/*.md` active markdown paths. It may report `docs/handoffs/archive/**`, `docs/handoffs/.session-state/**`, and top-level `docs/handoffs/handoff-*` state-like residue as explicitly out of legacy-active scope, but it must not classify those paths with `ignored-legacy-operational-handoff` or `untracked-legacy-operational-handoff`. `--write` may create or refresh the ignored evidence during Gate 0r. `--check` must be no-write and fail when the evidence is missing, stale against the current path inventory, missing required fields, contains `TBD`, or grants active-selection eligibility without an accepted external origin source or exact reviewed opt-in.

The legacy-active preflight evidence file must enumerate every current top-level `docs/handoffs/*.md` file, including valid, invalid, ignored, untracked, and tracked paths. It is the only local-preflight source that may support active markdown provenance, and only when it records an accepted external origin source. Each row must include:

- lexical path and resolved containment-checked path
- project-root-relative path
- inventory scope: `canonical-checkout`
- git status class: tracked, ignored, untracked, or missing-after-inventory
- raw-byte SHA256 when readable
- detected document profile: `current_contract`, `historical_archive`, or `invalid`
- document validation status and path-specific validation or skip reason
- external origin source: `plugin-origin-runtime-marker-provenance`, `reviewed-runtime-migration-opt-in`, or `none`
- origin evidence fields required by the selected external origin source, including marker or sidecar schema version when marker-backed, reviewed note path and reviewer when opt-in backed, and the raw-byte SHA256 that ties the evidence to the file
- artifact class and selection eligibility
- missing or rejected provenance fields
- rationale and verification command or test that proves the classification
- scope: `legacy-active-preflight`

If a valid-looking ignored or untracked active markdown row has `external_origin_source=none`, the classifier must emit `policy-conflict-artifact` and `selection_eligibility=blocked-policy-conflict`; it must not infer runtime origin from ignored/untracked git visibility, filename shape, frontmatter, branch/commit metadata, or local operator familiarity.

These row fields are the single source of truth for legacy-active provenance evidence. Any source classifier return object, preflight writer, preflight checker, enforcement test, or downstream consumer must validate against this same schema or an explicit deterministic internal-to-evidence mapping table in this plan; adding a second JSON shape for the same fact is a Gate 0r blocker.

The tracked repo-authority ledger must not enumerate ignored or untracked machine-local residue paths as if they are fresh-clone project facts. It may reference the local-preflight evidence by hash and count, for example "local preflight run `<id>` saw 1 ignored state-like residue path; see ignored evidence file hash `<sha256>`." That reference is evidence for this checkout only, not durable repo authority.

No local residue path or legacy active markdown path may remain implicit during implementation execution. Implementation must stop if any local-preflight or legacy-active preflight evidence row has `TBD`, no disposition or artifact class, no scope, or no verification hook. A residue path may be quarantined only under ignored `.codex/handoffs/.session-state/quarantine/` with a transaction record and source hash. Destructive cleanup is out of scope unless a later explicit instruction authorizes it.

Gate 0A for this execution uses the canonical checkout at `/Users/jp/Projects/active/codex-tool-dev` after preserving unrelated P2 work on its own branch and switching the canonical checkout back to `main`. State-like local-preflight evidence and legacy-active preflight evidence must use `inventory_scope=canonical-checkout`. If a later attempt needs an isolated implementation worktree, stop and revise this plan, the residue ledger, and both preflight evidence schemas before continuing; do not reuse canonical-checkout evidence for a different topology.

## Cutover Inventory And Bridge

The reversal cannot start by switching writers alone. Before source repair is considered ready, add tests and command evidence for a cutover inventory covering:

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
- local-preflight evidence completeness for every `docs/handoffs/**` path, including state-like residue rows, delegated legacy-active markdown rows, legacy archive and state scope rows, non-handoff filesystem residue rows, plus legacy-active preflight classification for every top-level `docs/handoffs/*.md` path and repo-authority ledger scope/policy drift correctness

Installed-host behavior for no ignore, broad `.codex/` ignore, tracked `.codex/skills/**`, tracked handoff-path collision, tracked primary active source, and non-git project roots is Gate 5 certification evidence, not source-repair readiness evidence. It is required only before claiming `installed host matrix behavior proved`, `installed host matrix certified`, or `installed cache certified`.

During the reversal release, implicit active discovery for `/list-handoffs` and `/load` must consider valid primary active files plus eligible unconsumed legacy active files after artifact-class filtering. A legacy active file is selectable only when it is a provenance-backed ignored legacy active markdown file, a provenance-backed untracked legacy active markdown file, or an exact reviewed runtime migration opt-in with `storage_location=legacy_active`. Valid-looking ignored or untracked files without plugin-origin runtime marker provenance, legacy-active preflight evidence tied to an accepted external origin source, or exact reviewed path-plus-hash opt-in are diagnostic `policy-conflict-artifact` rows, not active candidates. Tracked durable handoff artifacts, legacy operational archives, legacy state bridge inputs, state-like residue, and policy-conflict artifacts are diagnostic inventory rows, not active candidates. Dedup remains byte-exact, with primary active winning over selectable legacy active. This mixed-root behavior prevents proven operational active `docs/handoffs/*.md` files from becoming stranded after the first new `.codex/handoffs/*.md` write without consuming durable repository docs.

Implicit `/load` chooses the most recent eligible active candidate from the combined primary-active plus class-filtered legacy-active set after dedup, using the Selection Ordering contract below. If it chooses a primary active file, Primary Load semantics apply. If it chooses a legacy active file, Legacy Load semantics apply.

Fallback-only legacy discovery may be restored only in a later release after an explicit deprecation or migration gate proves legacy active files have been copied, intentionally left behind, or made explicitly path-only. That later gate is out of scope for this implementation.

### Alternative Rejected: One-Time Migration Command

This plan deliberately rejects a default one-time migration command that copies all eligible `docs/handoffs/` runtime files into `.codex/handoffs/` and then makes active selection primary-only.

That alternative would reduce mixed-root active-selection complexity, but it has worse cutover failure modes for this plugin:

- It requires a mutating sweep before ordinary `/load`, `/list-handoffs`, `/distill`, `/save`, `/summary`, or `/quicksave` can be trusted after upgrade.
- It risks copying durable or policy-conflict `docs/handoffs/**` artifacts unless the same artifact-class classifier already exists.
- It creates a large all-at-once transaction surface instead of allowing proven legacy runtime files to remain read-only migration input until selected.
- It can strand users who upgrade with a valid active legacy file but do not run the migration command before the first post-upgrade command.

The accepted tradeoff is one cutover release with mixed primary plus class-filtered legacy active discovery, consumed legacy-active suppression, and explicit provenance diagnostics. A later release may switch to primary-only active selection only after an explicit deprecation gate proves every eligible legacy active file has been consumed, copied, intentionally left behind, or made explicit-path-only.

### Consumed Legacy Active Suppression

Because legacy active files are read-only migration input, successful legacy `/load` must not move or delete `docs/handoffs/*.md`. It must instead make the loaded legacy file stop participating in active-selection workflows.

Use a durable consumed legacy-active registry under `.codex/handoffs/.session-state/consumed-legacy-active.json`. Each consumed entry must include:

- source root enum and storage location
- project-root-relative legacy source path
- raw-byte SHA256 content hash
- absolute lexical legacy source path as evidence
- containment-checked resolved path as evidence
- copied primary archive path
- consumed timestamp
- operation that consumed it, for example `legacy-load`

Active-selection scans suppress a legacy active candidate only when the registry contains the same source root, project-root-relative path, storage location, and raw-byte content hash. Absolute lexical and resolved paths are evidence, not the stable identity key; moving a clone must not resurrect an already consumed same-relative-path same-hash legacy active file. If the legacy file changes bytes later, it is treated as a new active candidate and must be validated again.

A legacy load is not successful unless the copy to primary archive, primary state write, and consumed-registry write all succeed. After a successful legacy load, default `/list-handoffs` and implicit `/load` must not show or select the consumed legacy active file again. History search may still surface the legacy source as historical input with provenance.

### Copied Legacy Archive Registry

Explicit legacy archive loads copy legacy archive content to primary archive storage so new chain state points at `.codex/handoffs/archive/`. This includes both `docs/handoffs/archive/*.md` and previous-primary hidden archive files under `.codex/handoffs/.archive/*.md`. Repeating the same explicit legacy archive load must not create duplicate primary archive copies.

Use a durable copied legacy-archive registry under `.codex/handoffs/.session-state/copied-legacy-archives.json`. Each copied entry must include:

- source root enum and storage location
- project-root-relative legacy source path
- raw-byte SHA256 source content hash
- absolute lexical legacy source path as evidence
- containment-checked resolved path as evidence
- copied primary archive path
- raw-byte SHA256 copied archive content hash
- copied timestamp
- operation that copied it, for example `legacy-archive-load`
- recovery status: `complete`, `recovery_required`, or `failed`
- transaction id that created or last repaired the entry

An explicit legacy archive load may reuse an entry only when the source root, project-root-relative path, storage location, and source hash match and the copied primary archive path exists with the copied hash. Absolute lexical and resolved paths must be re-recorded as current evidence but must not be the only key. If any stable-key or copied-content checks fail, recovery must diagnose the stale or corrupt registry entry before a new copy can be allocated.

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

Ambiguous state diagnostics must include a concrete operator recovery workflow. The helper surface must provide a read-only state inventory mode, for example `list-chain-state`, that emits every same-project state candidate with source root, storage location, project-root-relative state path, lexical path, resolved path, project, resume token when derivable, detected format, archive path, age, payload hash, and validation status. The diagnostic must tell the operator to choose one of these explicit outcomes:

- continue from exactly one candidate by explicit state path or resume token, then write primary state under `.codex/handoffs/.session-state/`
- mark one or more stale candidates consumed with a durable marker and post-marker proof
- abort without mutation

No helper may guess among multiple valid same-project state candidates. A recovery command that marks stale state consumed must run under the project lock, record a transaction, and preserve enough metadata for later audit. Tests must cover the ambiguous diagnostic payload and at least one explicit recovery path.

Legacy and state-like bridge candidates use the same stable identity standard as legacy handoff registries. A state-consumption marker key must include:

- source root enum and storage location
- project-root-relative state path
- project
- resume token when derivable
- detected format: `tokenized-json`, `plain-state`, or `state-like-residue`
- raw-byte SHA256 payload hash

Absolute lexical and resolved paths are marker evidence only. They must not be the only key used for bridge suppression, marker lookup, or consumed-state recovery. Moving or copying a clone must not make a previously consumed same-relative-path same-hash legacy state usable again.

These recovery outcomes map to concrete helper entrypoints. Implementation must not leave operator recovery as prose-only behavior:

- `continue-chain-state`: continue from exactly one explicit primary, legacy, or state-like candidate selected by path or resume token plus expected payload hash. It must validate the candidate's full stable identity, run under the project lock, write or repair primary chain state under `.codex/handoffs/.session-state/`, record the transaction, and preserve `resumed_from` identity when the source is legacy.
- `mark-chain-state-consumed`: mark one or more exact legacy or state-like candidates stale, consumed, duplicate, or abandoned by stable state-candidate identity plus expected payload hash. Lexical path or resume token may be accepted only as a lookup selector; the helper must resolve the selector, validate the full identity, and write a durable marker under `.codex/handoffs/.session-state/markers/` or an equivalent primary-state marker root. It must record the transaction and prove the marked candidate no longer participates in bridge lookup.
- `abandon-primary-chain-state`: abandon or clear one exact primary state path by lexical path plus expected state hash before choosing an explicit legacy candidate. It must run under the project lock, record the reason, preserve enough metadata for audit, and never infer that unrelated legacy candidates are stale.
- `chain-state-recovery-inventory`: emit the read-only inventory used by ambiguity diagnostics, including transaction and marker status, without completing, rolling back, marking, clearing, copying, or writing any artifact.

Primary state winning does not prove same-project legacy state candidates are stale. When exactly one valid primary state exists and any same-project legacy state or state-like residue candidate also exists, chain writers must stop before active output creation unless every legacy candidate already has an explicit durable operator disposition. The diagnostic must include the read-only inventory rows and require the operator to choose one of these outcomes:

- mark specific legacy candidates stale or consumed with an explicit recovery command, transaction record, and post-marker proof
- continue from one explicit legacy candidate after abandoning or clearing the primary state through an explicit recovery command
- preserve the candidates and abort without mutation

`clear-chain-state` must not silently consume, mark, or delete unresolved same-project legacy candidates just because a primary state exists. A recovery command may mark stale candidates only under the project lock, with source hashes and operator-selected paths recorded. If unresolved legacy candidates remain, fail with an actionable diagnostic rather than leaving state that can resurrect after primary cleanup.

If a tokenized payload has `project` or `resume_token` fields, they must match the filename-derived project/token. If a legacy plain state has no token, the helper may mint a new token only after preserving the legacy `archive_path` as the `resumed_from` source for the save/summary/quicksave output. The `archive_path` must be a valid contained handoff path accepted by explicit-path validation, and the state must be inside the 24-hour chain-state TTL unless a test explicitly covers a documented expired-state diagnostic.

Local-preflight evidence rows with `disposition=bridge-once` are not exempt from TTL. Before Gate 1, the current local-preflight evidence must be refreshed or reclassified so every state-like residue row is one of:

- `bridge-once-fresh`: valid project state inside the 24-hour TTL at the refreshed preflight timestamp
- `expired-bridge-rejected`: expired state that must not bridge and must produce the documented expired-state diagnostic
- `operator-recovery-only`: expired or ambiguous state that can be used only through an explicit recovery command naming a selector and expected payload hash, then validating the full stable identity
- `consumed-or-abandoned`: already handled by a durable marker or explicit operator disposition

The current canonical-checkout evidence row created at `2026-05-11T02:46:58.895416+00:00` cannot remain plain `bridge-once` for a `2026-05-13` Gate 1 start unless the preflight is regenerated and proves it is still inside the effective TTL, or the plan adds and verifies an expired-state recovery path.

A successful bridged save/summary/quicksave must preserve the `resumed_from` link, write new output and any new chain state only under `.codex/handoffs/`, and durably suppress the consumed legacy state through a primary-state marker keyed by stable state-candidate identity. Legacy `docs/handoffs/.session-state/**` bytes are not modified, deleted, or trashed by normal bridge cleanup. Cleanup is resurrection-proof only if a durable consumed marker is written using the identity contract above, and a post-marker bridge lookup proves the legacy state no longer returns usable state. Malformed, expired, ambiguous, multiply matching, unsuppressed, or unmarkable legacy state must fail with an actionable diagnostic that names the state path or conflict; it must not silently break or resurrect the chain.

Explicit loads from `docs/handoffs/.session-state/` remain rejected. Legacy state is bridge input only for the save/summary/quicksave chain writer.

### Transaction And Recovery Protocol

Any operation that mutates active files, archive files, state files, consumed registries, copied-source registries, bridge markers, residue quarantine records, or transaction records must run under one project-scoped lock under `.codex/handoffs/.session-state/locks/`. The lock must be acquired with an atomic filesystem primitive such as exclusive file creation or atomic directory creation.

Lock metadata must include project, operation, transaction id, process id if available, hostname if available, created timestamp, and lock timeout. Default lock behavior is fail-fast. If a helper supports waiting, it must require an explicit `--wait-seconds` argument and cap the wait at 30 seconds. A lock older than 30 minutes is stale only after recovery inspects any pending transaction for the same project; stale-lock takeover without recovery is forbidden.

Mutable operations must use same-filesystem temporary files plus atomic rename for active markdown, JSON state, registry, marker, and transaction-log writes. Archive copies must be copied to a temporary file in the target archive directory, verified by byte hash, and then atomically renamed to the allocated archive path.

Every mutating load, active writer, or state operation must be transactional and idempotent, including implicit primary active load, explicit primary active load, explicit primary archive load, implicit legacy active load, explicit legacy active load, explicit legacy archive load, save active write, summary active write, quicksave active write, state write, and state clear.

For load and explicit state operations, the transaction runs in one lock window. For active writers, the sequence below describes the write phase only; `begin-active-write` uses the two-phase reservation protocol in Active Writer Creation Contract and must release the project lock before content generation.

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

Completed-transaction idempotency is source-hash scoped. Retrying or repeating an explicit legacy archive load for the same source root, project-relative source path, storage location, and raw-byte hash must reuse the verified primary archive path from `copied-legacy-archives.json` and write state to that path; it must not allocate a fresh primary archive copy each time. If the registry entry exists but the primary archive copy is missing or byte-mismatched, recovery must fail with a typed diagnostic rather than silently creating a second copy outside a repair transaction. Legacy active loads use `consumed-legacy-active.json` for the same source root, project-relative source path, storage location, and raw-byte hash reuse and suppression semantics.

The active-writer transaction watermark is a per-project chain-mutation watermark, not an mtime, last filename, or partial transaction-log guess. Store it under primary state, for example `.codex/handoffs/.session-state/mutation-watermarks/<project>.json`, with at least:

- `project`
- monotonically increasing `epoch`
- `digest`: SHA256 over the canonical JSON representation of the epoch, last committed chain-affecting transaction id, and the current hashes of chain-affecting state/registry/marker roots
- `last_chain_mutation_transaction_id`
- `updated_at`

The watermark must be read and updated only while holding the project lock. Every committed chain-affecting mutation advances it, including mutating load, active-write commit, state write, state clear, state bridge cleanup, explicit state recovery, cleanup that changes primary or legacy-consumption state, consumed-legacy-active registry changes, copied-legacy-archive registry changes, bridge marker changes, residue quarantine or disposition changes, and transaction recovery that completes, repairs, rolls forward, or marks failed any of those mutations.

Read-only inventory, history search, explicit read-only distill, validation-only scans, source candidate parsing, failed attempts that leave no chain-affecting artifact change, active-writer reservation creation, lease renewal, and abandoned-before-write reservations do not advance the chain-mutation watermark. Those reservation records are still checked separately through `list-active-writes` and reservation conflict rules. If abandonment or recovery touches active output, chain state, registries, markers, quarantine records, or committed transaction status for a chain-affecting operation, it advances the watermark.

`begin-active-write` records the current watermark after any mutating recovery it performs and before releasing the lock. `write-active-handoff` must reread the watermark under lock and fail closed if the epoch or digest differs from the recorded value unless the only changes are the same active-writer reservation records explicitly tied to the same `run_id`, transaction id, and lease id.

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
- `active_writer_lease_id`, when the transaction reserves generated active output
- `active_writer_lease_expires_at`, when the transaction reserves generated active output
- `active_writer_transaction_watermark`, when the transaction reserves generated active output
- `state_snapshot_sha256`, when an active writer reads chain state before output
- `resume_source_path`, when an active writer preserves `resumed_from`
- `resume_source_sha256`, when an active writer preserves `resumed_from`
- `caller_run_id` or helper-minted `run_id`, when the transaction writes generated active output
- `state_path`, when the transaction reads, writes, clears, or bridges chain state
- `state_action`: `none`, `read`, `write`, `clear-primary`, or `bridge-marker`
- `registry_path`
- `copy_registry_path`
- `expected_postconditions`
- `created_at`
- `updated_at`
- `lock_path`
- `error`, when recovery or failure occurs

### Active Writer Creation Contract

`/save`, `/summary`, and `/quicksave` are active writers. They must not build `.codex/handoffs/` paths directly in skill prose, shell snippets, or one-off helper code. They must use shared helper APIs that run under the project lock and transaction protocol.

Active-writer rewire is blocked until the state-bridge dependency is executable. Gate 1d may implement operation-state reservation, idempotency, allocation, write, and retry mechanics with primary-state-only fixtures, but it must not rewire `/save`, `/summary`, or `/quicksave` in skill docs or command surfaces until one of these is true:

- Gate 1d includes the minimal state-bridge read and durable bridge-marker behavior needed by `begin-active-write` and `write-active-handoff`, with the required pre-upgrade legacy-state plus post-upgrade save/summary/quicksave tests.
- Gate 1e has already landed on the same implementation branch, including project-scoped bridge lookup, ambiguity diagnostics, `continue-chain-state`, `mark-chain-state-consumed`, and post-marker bridge suppression proof.

If Gate 1d remains separate from Gate 1e, its closeout label is `active-writer mechanics staged`, not `active writers rewired`. A branch or PR must not claim `/save`, `/summary`, or `/quicksave` behavior is source-repaired while a valid pre-upgrade chain state can still lose `resumed_from`, fail after content generation, or require prose-only recovery.

If Gate 1d closes as staged and Gate 1e lands later, Gate 1g is the named integration gate that makes the staged active-writer mechanics bridge-backed. Gate 1g must run the active-writer operation-state flow against completed bridge/recovery behavior before skill docs, command surfaces, PR text, or closeout labels may say `/save`, `/summary`, or `/quicksave` are rewired.

The implementation must provide:

Active-writer slug and path binding must happen before final content generation without depending on final generated prose. `begin-active-write` must either accept a caller-provided `requested_slug` chosen before final content generation or mint a deterministic helper default slug from the operation kind, for example `handoff`, `summary`, or `checkpoint`. The helper must record `slug_source` as `caller-predeclared` or `helper-default`. The generated markdown title may differ from the filename slug, but generated content must not rename, reallocate, or mutate the bound path. If a retry or regenerated answer attempts to change the slug for the same `run_id` or idempotency key after path binding, the helper must fail closed unless the operator explicitly abandons the active write and starts a new one.

- `begin-active-write`: reserve a save/summary/quicksave transaction before generated content is accepted. It must acquire the project lock, run mutating recovery, read primary or bridged chain state, mint or accept a caller-provided run id, bind `requested_slug` or a helper-default slug, allocate and bind the active path, persist the idempotency key, pending transaction record, operation-state record, reservation lease, state snapshot, slug source, and transaction watermark, then release the lock before content generation. It must return the `run_id`, transaction id, allocated path, bound slug, slug source, state snapshot id, resumed-from identity, operation-state path, lease id, and lease expiry to the caller.
- `allocate-active-path`: allocate a collision-safe primary active path under `.codex/handoffs/` from an operation kind, timestamp, and pre-bound slug. Allocation must use filename timestamp format `YYYY-MM-DD_HH-MM_<kind>-<slug>.md`, treat existing files, directories, symlinks, and tracked exact-path conflicts as occupied, and support at least base, `-01`, and `-02` suffixes before returning collision-budget exhaustion. It must not derive or update the slug from generated title or body content after `begin-active-write` returns.
- `write-active-handoff`: acquire the project lock and accept only content tied to a previously returned `run_id`, transaction id, allocated path, state snapshot id, lease id, and idempotency key. It must validate reservation freshness, state snapshot identity, transaction watermark, and no conflicting chain mutation before writing. It writes active handoff markdown under `.codex/handoffs/` via same-directory temp file and atomic rename, verifies the raw-byte hash, preserves `resumed_from` from primary or bridged legacy state, and clears or durably marks consumed chain state only after the active file is proven present.
- `active-write-transaction-recover`: recover or fail pending save/summary/quicksave transactions before any new mutating active write or state bridge lookup. Read-only selection uses `read-only-recovery-inventory` instead.

Generated active writes use an active-writer idempotency key, not a source hash. The key is stable retry identity; it must not include `transaction_id` or generated content hash. Those are transaction fields used to audit and compare attempts, not key components.

The key must include:

- project
- operation: `save`, `summary`, or `quicksave`
- state snapshot id or state hash when chain state was read
- resume source path and hash when `resumed_from` exists
- caller-provided run id when available, otherwise a helper-minted run id emitted and persisted before path allocation or content mutation
- slug source and bound slug
- allocated active path after the transaction binds one

Active writer recovery states are:

- `pending_before_write`: no active output exists; recovery may continue the original transaction or fail before allocating a different path.
- `written_not_confirmed`: active output exists at `allocated_active_path` with the recorded hash, but transaction commit was not recorded; recovery must reuse that path and complete or diagnose state cleanup. It must not allocate a second handoff for the same idempotency key.
- `cleanup_failed`: active output exists and state cleanup failed or is unproven; recovery must retry cleanup or fail with an actionable diagnostic naming the active path and state path.
- `content_mismatch`: active output exists at the allocated path but bytes differ from the transaction hash; recovery must fail closed and require operator action.

If a caller retries `/save`, `/summary`, or `/quicksave` after a pending transaction, the helper must discover pending transactions by stable run id, state snapshot, resume source identity, and allocated path when already bound, then run `active-write-transaction-recover` before accepting regenerated content or minting a new transaction id. If the retry matches the same idempotency key and generated content hash, it reuses the existing transaction. If the retry matches the same idempotency key but changed bytes, it fails with `ActiveWriteContentChangedError` or an equivalent typed diagnostic rather than creating a second active handoff. A deliberate second handoff requires a new helper-minted run id after the pending transaction is recovered, failed, or explicitly abandoned.

The caller protocol is:

1. Call `begin-active-write` before asking an LLM or local generator to produce final handoff content.
2. Preserve the returned `run_id`, transaction id, allocated path, bound slug, slug source, state snapshot id, and resumed-from identity in the caller-visible operation state.
3. Generate content for that exact operation identity. Do not regenerate the filename slug from the final title or body after `begin-active-write` has returned.
4. Call `write-active-handoff` with the same operation identity and the generated content hash.
5. On retry, pass the original `run_id` and transaction id when known. If they are not known, the helper must discover compatible pending transactions by operation, project, state snapshot, resume source identity, and allocated path; if zero or more than one compatible pending transaction exists, it must fail closed before accepting regenerated content.
6. If a retry matches the same idempotency key and content hash, reuse the existing transaction. If it matches the same idempotency key but content bytes changed, fail with `ActiveWriteContentChangedError` or an equivalent typed diagnostic.

The implementation must make this protocol executable, not only documented. Gate 1d must add either a deterministic command-level wrapper, for example `active-writer-flow`, or a two-call helper test harness that runs the same sequence the skills will use: `begin-active-write`, deterministic content generation bound to the returned operation identity and bound slug, `write-active-handoff`, retry with the same `run_id`, retry with changed bytes, retry that attempts to change the slug after path binding, context-loss recovery through `list-active-writes`, and cleanup-failure recovery. Skill-doc tests must execute this flow end-to-end for `/save`, `/summary`, and `/quicksave`; static scans for helper names are insufficient.

The operation state cannot rely on LLM memory or skill prose alone. `begin-active-write` must persist an active-writer operation-state record before content generation under a primary state root such as `.codex/handoffs/.session-state/active-writes/<project>/<run_id>.json`. The exact path may vary, but it must be returned by the helper and included in the transaction record.

The active-writer operation-state record must include at least:

- schema version
- project
- operation: `save`, `summary`, or `quicksave`
- `run_id`
- transaction id
- idempotency key
- allocated active path
- state snapshot id and hash
- resumed-from path and hash when present
- bound slug and slug source
- operation-state path
- lease id
- lease acquired timestamp
- lease expiry timestamp
- transaction watermark at reservation time
- status: `begun`, `content-generated`, `write-pending`, `committed`, `abandoned`, or `recovery-required`
- content hash once generation is accepted
- created and updated timestamps
- recovery commands or helper arguments needed to continue, retry, or abandon

Skill docs must copy the helper-returned operation identity into the visible workflow before final content generation. After context compaction, retry, interruption, or a regenerated answer, the skill must first call `active-write-transaction-recover` or `list-active-writes` for the project and operation. If exactly one compatible pending operation exists, the skill may continue only by passing the persisted `run_id`, transaction id, state snapshot id, allocated path, and content hash. If no compatible operation exists, it may start a new `begin-active-write`. If more than one compatible operation exists, it must fail closed and show the recovery inventory. If generated bytes differ for the same idempotency key, the helper must require explicit `abandon-active-write` or equivalent operator-selected recovery before a new handoff can be created.

The project lock must not be held across LLM or local content generation. Active writers use a two-phase reservation protocol:

1. `begin-active-write` acquires the project lock.
2. It runs mutating recovery and refuses to reserve a new active write while another non-expired compatible reservation exists for the same project and chain state.
3. It reads chain state, records the state snapshot hash, transaction watermark, resumed-from identity, allocated active path, idempotency key, operation-state path, lease id, and lease expiry.
4. It writes the pending transaction and operation-state reservation, then releases the project lock before content generation.
5. The caller generates content without holding the project lock.
6. `write-active-handoff` reacquires the project lock.
7. It reruns mutating recovery, reloads the operation-state record, validates the lease, and proves the recorded state snapshot and transaction watermark have not been invalidated by a conflicting load, save, summary, quicksave, explicit state recovery, or cleanup mutation.
8. If the reservation is fresh and no conflicting mutation exists, it writes output, performs state cleanup, commits the transaction, and marks the operation-state committed.
9. If the lease expired, the state snapshot changed, the transaction watermark changed in a conflicting way, or another operation already committed against the same chain state, it fails closed with `ActiveWriteReservationConflictError` or an equivalent typed diagnostic before accepting or writing regenerated content.

The default reservation lease is 30 minutes. A helper may support explicit lease renewal only while holding the project lock and only when the state snapshot and transaction watermark still match. Expired reservations are recoverable inventory, not permission to allocate a second active path silently. Operator recovery may abandon an expired reservation or continue it only after the helper proves no conflicting mutation has committed since the reservation watermark.

`abandon-active-write` must run under the project lock, mark the operation-state and transaction record abandoned with path and hash evidence, and leave already-written active output untouched unless a separate reviewed recovery command proves removal is safe. Abandonment must not clear or mark chain state unless the transaction's recorded postconditions prove the active output was never written or the state cleanup already completed.

The save/summary/quicksave transaction boundary is split into reservation and write phases:

1. Reservation phase: acquire the project lock, run mutating recovery for the project, read primary state or the one-time legacy state bridge, allocate the primary active output path, persist the transaction and operation-state reservation, and release the lock before content generation.
2. Write phase: reacquire the project lock, validate lease freshness, state snapshot, transaction watermark, idempotency key, and content hash, write and verify the active handoff file, clear primary state and consume or mark any bridged legacy state with post-marker proof, then commit the transaction only after the active file exists, the content hash matches, and state cleanup cannot resurrect.

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

Create `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py` as the stable public facade for storage authority used by `/load`, `/list-handoffs`, `/search`, `/triage`, `/distill`, `/save`, `/summary`, `/quicksave`, state cleanup, and deterministic tests that inspect or write handoff roots.

`storage_authority.py` must expose writer path APIs for current active, archive, state, legacy state bridge lookup, and cleanup paths. Writers must not independently reconstruct `docs/handoffs/` or `.codex/handoffs/` paths in skill prose or helper scripts.

Keep `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py` as the canonical direct-Python CLI facade. It must import `storage_authority.py` and expose the helper subcommands named below with kebab-case CLI names. Do not add a separate helper CLI module in this implementation. If a separate CLI module appears necessary, stop and patch this control document first.

`storage_authority.py` may and should delegate to internal modules so the facade does not become the bottleneck for every slice. Allowed internal modules include the equivalent of `storage_paths`, `storage_discovery`, `storage_git`, `storage_transactions`, `storage_state_bridge`, `storage_active_writes`, and `storage_registries`, either as sibling `scripts/*.py` files or as a package with direct-Python import tests. Callers outside the storage layer must import the facade or call `session_state.py`; they must not bind to internal modules. Each vertical gate below owns the internal module slice it needs.

Keep `plugins/turbo-mode/handoff/1.6.0/scripts/handoff_parsing.py` as the document frontmatter and section parser. Storage path validation, candidate validation, git visibility, registry validation, and transaction validation belong behind the `storage_authority.py` facade, not in reader or writer scripts.

Instruction-driven skills must call concrete helper CLI or API entrypoints instead of rebuilding path logic with shell globbing, `ls -t`, direct `mkdir`, direct `mv`, direct `cp`, or hardcoded archive/state directories.

The implementation must provide documented helper entrypoints for at least:

- `begin-active-write`: persist a stable active-writer run id, transaction id, state snapshot, resumed-from identity, and allocated path before save/summary/quicksave content generation
- `allocate-active-path`: allocate a collision-safe primary active output path for save/summary/quicksave
- `write-active-handoff`: atomically write primary active output and clear or mark chain state under one transaction
- `active-write-transaction-recover`: recover or diagnose pending active writer transactions
- `list-active-writes`: emit persisted active-writer operation-state records for recovery without mutating active files, state files, or transactions
- `abandon-active-write`: mark one explicit active-writer operation abandoned under lock with transaction and operation-state evidence
- `select-active`: return the implicit load/distill candidate selected by Scan Mode `active_selection`
- `list-active`: return default `/list-handoffs` output from Scan Mode `active_selection`
- `validate-explicit-path`: validate explicit primary or legacy active/archive paths
- `archive-primary-active`: move primary active input to primary archive and write state
- `copy-legacy-active-to-primary-archive`: copy eligible legacy active input to primary archive, write state, and mark the legacy source consumed
- `copy-legacy-archive-to-primary-archive`: copy or reuse a verified primary archive copy for an explicit legacy archive source without marking the source consumed
- `read-chain-state`: read primary state or the one-time legacy bridge state
- `list-chain-state`: list same-project primary, legacy, and state-like residue candidates for ambiguity diagnostics and operator recovery
- `continue-chain-state`: continue from one explicit state candidate and write or repair primary chain state under a transaction
- `mark-chain-state-consumed`: mark exact legacy or state-like chain candidates consumed or stale by stable state-candidate identity plus expected payload hash; path or resume token may be accepted only as selectors
- `abandon-primary-chain-state`: abandon one exact primary state path by path plus hash before an explicit legacy continuation
- `chain-state-recovery-inventory`: emit read-only chain-state recovery inventory without side effects
- `write-chain-state`: write only primary state
- `clear-chain-state`: clear primary state and consume only the bridged legacy state with post-marker proof; it must not infer that other same-project legacy candidates are stale or modify legacy state bytes
- `read-only-recovery-inventory`: inspect lock and transaction records without completing, rolling back, marking, clearing, copying, moving, or writing recovery artifacts
- `recover-transaction`: complete a named fully verifiable pending transaction under the project lock, or fail with a typed diagnostic
- `repair-consumed-legacy-active-registry`: repair or diagnose consumed legacy-active registry corruption under an explicit operator-selected transaction
- `repair-copied-legacy-archive-registry`: repair or diagnose copied legacy-archive registry corruption under an explicit operator-selected transaction
- `history-candidates`: return `/search`, `/triage`, and `/summary` arc candidates from Scan Mode `history_search`

`test_skill_docs.py` or an equivalent surface test must prove load/list/distill/save/summary/quicksave docs invoke these helpers and do not retain stale shell-only path implementations. Save/summary/quicksave doc rewires are allowed only after the Active Writer Creation Contract's state-bridge dependency rule is satisfied.

### Helper Launcher Classes

Skill docs must preserve the current direct-Python chain-state and active-writer contract where it matters:

- Chain-state, active-writer, archive-mutation, registry-repair, transaction-recovery, and explicit-path validation helpers must be stdlib-only and runnable as direct Python, for example `python "$PLUGIN_ROOT/scripts/session_state.py" ...` or a successor stdlib-only helper path. These helpers include `begin-active-write`, `allocate-active-path`, `write-active-handoff`, `list-active-writes`, `active-write-transaction-recover`, `abandon-active-write`, `archive-primary-active`, `copy-legacy-active-to-primary-archive`, `copy-legacy-archive-to-primary-archive`, `validate-explicit-path`, `read-chain-state`, `list-chain-state`, `continue-chain-state`, `mark-chain-state-consumed`, `abandon-primary-chain-state`, `chain-state-recovery-inventory`, `write-chain-state`, `clear-chain-state`, `read-only-recovery-inventory`, `recover-transaction`, `repair-consumed-legacy-active-registry`, and `repair-copied-legacy-archive-registry`.
- Discovery and history helpers should also be stdlib-only if feasible. If a helper truly needs dependencies, it may use `uv run`, but the plan must name that helper as dependency-bearing and skill-doc tests must prove chain-state helpers did not regress to `uv run`.
- Refresh tooling, tests, and marketplace mutation helpers may use `uv run`; that does not waive the direct-Python contract for chain-state helpers.
- `test_skill_docs.py` must keep or replace the current direct-Python-vs-command-helper distinction deliberately. Removing that distinction without an equivalent launcher-class assertion is a hard stop.

Every candidate result must include typed fields:

- `path`: absolute lexical path
- `resolved_path`: resolved containment-checked path
- `project_relative_path`: source path relative to the detected project root when containment allows one
- `source_root`: enum `primary`, `legacy`, or `previous_primary`
- `storage_location`: enum `primary_active`, `primary_archive`, `legacy_active`, `legacy_archive`, or `previous_primary_hidden_archive`
- `lifecycle`: enum `active` or `archive`
- `artifact_class`: enum `primary-runtime`, `ignored-legacy-operational-handoff`, `untracked-legacy-operational-handoff`, `legacy-operational-archive`, `legacy-state-bridge-input`, `tracked-durable-handoff-artifact`, `reviewed-runtime-migration-opt-in`, `previous-primary-hidden-archive`, `state-like-residue`, `non-handoff-filesystem-residue`, `policy-conflict-artifact`, or `unknown`
- `source_git_visibility`: enum `ignored`, `untracked`, `tracked-conflict`, `not-git-repo`, or `unknown`
- `source_fs_status`: enum `missing`, `regular-file`, `directory`, `symlink`, `non-regular`, `unreadable`, `parent-missing`, `parent-file-conflict`, `path-escape`, or `unknown`
- `selection_eligibility`: enum `eligible`, `read-only-only`, `blocked-tracked-source`, `blocked-durable-artifact`, `blocked-policy-conflict`, or `blocked-invalid`
- `content_hash`: byte-exact SHA256 of raw file bytes, computed only after containment and regular-file checks
- `validity`: enum `valid`, `invalid`, `skipped`
- `document_profile`: enum `current_contract` or `historical_archive`
- `invalid_reason`: typed reason for document validation failures
- `skip_reason`: typed reason for filesystem or discovery exclusions

`invalid_reason` is for document validation failures such as missing frontmatter, invalid type, missing required fields, or malformed required sections.

`skip_reason` is for filesystem and discovery exclusions such as hidden file, nested implicit file, symlink, path escape, non-regular file, unreadable file, forbidden state directory, or outside scan scope.

`selection_eligibility` values are hyphenated machine values. Underscore strings such as `blocked_tracked_runtime_source` and `blocked_durable_artifact` are diagnostic reason codes only; helpers, preflight evidence, proof maps, and tests must not emit them as `selection_eligibility` values.

`non-handoff-filesystem-residue` rows must use `selection_eligibility=blocked-invalid` when they are projected into candidate-style diagnostics. They are inventory/accounting rows, not candidate rows, and must carry a skip reason such as `non_handoff_filesystem_residue` instead of being silently dropped.

No broad `except Exception: pass` behavior is allowed in discovery paths. Skips must preserve path and reason.

## Scan Modes

The shared module must expose separate scan modes so active lifecycle, history search, explicit-path access, and state bridging cannot drift.

### Active Selection

Used by implicit `/load`, default `/list-handoffs`, and default `/distill`.

Includes:

- primary active: `.codex/handoffs/*.md` when not tracked by the host repo
- unconsumed legacy active during cutover: `docs/handoffs/*.md` only when classed as provenance-backed ignored legacy active markdown, provenance-backed untracked legacy active markdown, or exact reviewed runtime migration opt-in

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

Summary arc context is a separate snapshot from chain-state transaction safety. If `/summary` uses history-search candidates before content generation, it must either persist a candidate-set manifest with source root, project-relative path, raw-byte hash, provenance, and manifest hash, then bind that manifest id into the active-writer operation state, or explicitly mark the arc context as `best_effort_not_snapshot_bound` in the generated summary and closeout evidence. A transactionally valid summary must not be misreported as semantically snapshot-bound unless the candidate-set manifest was recorded and revalidated.

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
- legacy active during cutover for load/list/distill: `docs/handoffs/*.md` only when provenance-backed ignored legacy active markdown, provenance-backed untracked legacy active markdown, or exact reviewed runtime migration opt-in

Implicit scans exclude archives, nested files, hidden files, `.session-state/`, symlinks, path escapes, non-regular files, unreadable files, invalid documents, tracked primary runtime source files, tracked durable legacy artifacts, and policy-conflict artifacts.

Invalid primary files produce path-specific diagnostics and do not hide eligible legacy active files.
Tracked primary runtime source files produce `blocked_tracked_runtime_source` diagnostic reasons with `selection_eligibility=blocked-tracked-source` and do not hide valid eligible candidates. Tracked durable legacy artifacts produce `blocked_durable_artifact` diagnostic reasons with `selection_eligibility=blocked-durable-artifact` and do not participate in active selection unless a reviewed migration opt-in names the exact path and hash.

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

Repeated explicit legacy archive loads for the same source root, project-relative source path, storage location, and raw-byte hash must be completed-transaction idempotent. The second and later loads must reuse the same verified primary archive path from the copied legacy-archive registry and update state to that path; they must not create `-01`, `-02`, or later duplicate primary archive copies solely because the user repeated the same explicit archive load.

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

`/search` and `/triage` use Scan Mode `history_search` and always scan readable primary, legacy, and previous-primary hidden archive roots within their documented scope, except when a command is explicitly in single-root diagnostic mode.

Single-root diagnostic mode is allowed only for deprecated compatibility surfaces such as `/triage --handoffs-dir <path>`. In that mode the command scans exactly the named root and its archive child, must not infer or combine primary, legacy, or previous-primary roots, and must emit:

- `override_mode=explicit_handoffs_root`
- `roots_scanned`
- `roots_intentionally_skipped`
- a diagnostic pointing operators to `--project-root` for normal split-root discovery

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
- `plugins/turbo-mode/handoff/1.6.0/scripts/handoff_parsing.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py`
- internal storage authority modules added behind the `storage_authority.py` facade, such as `storage_paths.py`, `storage_discovery.py`, `storage_git.py`, `storage_transactions.py`, `storage_state_bridge.py`, `storage_active_writes.py`, and `storage_registries.py`
- control tooling scripts added for this plan outside the shipped Handoff plugin runtime tree, including `plugins/turbo-mode/tools/handoff_storage_reversal/hard_stop_matrix.py`, `plugins/turbo-mode/tools/handoff_storage_reversal/gate_proof_map.py`, `plugins/turbo-mode/tools/handoff_storage_reversal/residue_preflight.py`, and `plugins/turbo-mode/tools/handoff_storage_reversal/legacy_active_preflight.py`
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
- isolated installed-host harness source tests for source-proof installed realpath and cache-isolation behavior
- installed-host storage smoke tests for the host-repo policy matrix, required only before `installed host matrix certified` or `installed cache certified`
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

These compatibility decisions are fixed for implementation. Closeout must include tests for every preserved, wrapper-preserved, and deprecated-with-diagnostic surface below.

For `session_state.py` wrapper-preserved state commands, the old `--state-dir "$PROJECT_ROOT/docs/handoffs/.session-state"` argument is a stale-caller compatibility input, not a post-cutover write authority. Helpers must resolve the project root from either the provided `--state-dir` suffix or an explicit project-root argument if one is added. After cutover:

- `write-state`, `clear-state`, and `prune-state` must reject a provided legacy `docs/handoffs/.session-state` directory with a typed diagnostic such as `StaleStateDirError` before writing, clearing, marking, pruning, or trashing anything under `docs/handoffs/`.
- `read-state` may use a provided legacy `docs/handoffs/.session-state` directory only as legacy bridge input after computing the primary state root under `.codex/handoffs/.session-state`; it must not migrate by writing JSON state under `docs/handoffs/`.
- A provided primary `.codex/handoffs/.session-state` directory remains accepted for compatibility, but the helper must still validate containment and project identity.
- Stale skill docs or external callers that pass the old legacy state directory must be covered by tests so the failure or bridge behavior is explicit rather than silently preserving the old write root.

| Surface | Decision | Required behavior |
|---|---|---|
| `project_paths.py get_project_root` | preserved | Keep return type and fallback behavior unchanged. |
| `project_paths.py get_project_name` | preserved | Keep return type and fallback behavior unchanged. |
| `project_paths.py get_handoffs_dir` | wrapper-preserved | Return the post-cutover primary active root, `<project_root>/.codex/handoffs`, by delegating to `storage_authority.py`. |
| `project_paths.py get_archive_dir` | wrapper-preserved | Return the post-cutover primary archive root, `<project_root>/.codex/handoffs/archive`, by delegating to `storage_authority.py`. |
| `project_paths.py get_state_dir` | wrapper-preserved | Return the post-cutover primary state root, `<project_root>/.codex/handoffs/.session-state`, by delegating to `storage_authority.py`. |
| `project_paths.py get_legacy_handoffs_dir` | wrapper-preserved | Return the legacy active root, `<project_root>/docs/handoffs`, during the cutover release. Previous-primary hidden archive access must use `storage_authority.py`, not this function. |
| Historical `.codex/handoffs/.archive/` fallback | preserved | Implement only through `storage_authority.py` history-search and explicit-path modes; never active selection. |
| `session_state.py archive` CLI | wrapper-preserved | Preserve `--field archived_path` output with narrowed source-class behavior. It may archive primary active inputs only. It must reject legacy active, legacy archive, and previous-primary hidden archive inputs with a diagnostic naming the correct copy helper. |
| `session_state.py write-state` CLI | wrapper-preserved | Preserve `--field state_path`; write only primary state under `.codex/handoffs/.session-state`; reject stale legacy `--state-dir` values before mutation. |
| `session_state.py read-state` CLI | wrapper-preserved | Preserve `--field state_path`, `archive_path`, and `resume_token`; read primary state first, then exactly one valid project-scoped legacy bridge candidate; treat stale legacy `--state-dir` only as bridge input and never as a write target. |
| `session_state.py clear-state` CLI | wrapper-preserved | Preserve exit contract; clear or durably consume only the state path selected by the current chain under the project lock; reject stale legacy `--state-dir` values before mutation unless an explicit recovery helper selected a legacy candidate. |
| `session_state.py prune-state` CLI | wrapper-preserved | Preserve pruning behavior, but target only primary state; reject stale legacy `--state-dir` values unless an explicit recovery command names legacy state. |
| `session_state.py allocate_archive_path` Python API | wrapper-preserved | Delegate to `storage_authority.py`; preserve collision suffix behavior for primary archive allocation. |
| New active writer helpers | added | Add `begin-active-write`, `allocate-active-path`, `write-active-handoff`, `list-active-writes`, `active-write-transaction-recover`, and `abandon-active-write` as functions in `storage_authority.py` and CLI subcommands in `session_state.py`. |
| New legacy copy helpers | added | Add `copy-legacy-active-to-primary-archive` and `copy-legacy-archive-to-primary-archive` as functions in `storage_authority.py` and CLI subcommands in `session_state.py`. |
| New chain inventory helpers | added | Add `list-chain-state` as a function in `storage_authority.py` and a CLI subcommand in `session_state.py`. |
| Existing `session_state.py` public Python helpers used by tests | wrapper-preserved | Keep importable names or provide explicit wrapper functions with the same names and documented diagnostics when old semantics are unsafe. |
| `search.py search_handoffs` | wrapper-preserved | Keep callable API and result shape while adding provenance fields and delegating candidate discovery to `storage_authority.py`. |
| `search.py` previous-primary hidden archive fallback | preserved | Keep history-search compatibility through `storage_authority.py`; no active-selection use. |
| `search.py` re-exported parsing/path helpers used by tests | wrapper-preserved | Keep imports stable or update tests and downstream callers in the same gate with explicit compatibility notes. |
| `triage.py generate_report` | wrapper-preserved | Keep callable API and report shape while adding provenance fields and delegating candidate discovery to `storage_authority.py`. |
| `triage.py` previous-primary hidden archive fallback | preserved | Keep history-search compatibility through `storage_authority.py`; no active-selection use. |
| `triage.py` CLI fallback and report output shape | wrapper-preserved | Preserve CLI success/error shape and add path-specific skip diagnostics. |
| `triage.py --project-root` CLI | added | Add explicit project-root override for normal primary plus legacy discovery. This is the supported operator path for debugging broken auto-discovery. |
| `triage.py --handoffs-dir` CLI | deprecated with diagnostic | Treat as explicit single-root diagnostic mode only. It scans exactly the named root and its archive child, emits `override_mode=explicit_handoffs_root`, and must not silently combine that root with primary or legacy roots inferred from cwd. The diagnostic must point operators to `--project-root` for normal split-root discovery. |
| `distill.py` explicit path handling and CLI output shape | wrapper-preserved | Preserve CLI output shape; validate explicit paths through `storage_authority.py`. |
| `quality_check.py is_handoff_path` | wrapper-preserved | Recognize primary active/archive/state and eligible legacy runtime paths according to scan mode; do not treat durable tracked docs as active runtime files. |
| `quality_check.py` CLI and dormant-helper behavior | wrapper-preserved | Keep helper dormant unless live hook wiring is added with installed-config proof. |
| `cleanup.py` state cleanup behavior | wrapper-preserved | Cleanup primary state through `storage_authority.py`; legacy recovery requires explicit operator-selected recovery command. |
| `handoff_parsing.py` frontmatter and section parsing | preserved | Keep document parsing behavior independent from storage authority. |
| Handoff skill command surfaces for load, save, summary, quicksave, search, distill, and triage | preserved | Keep user-facing commands, but replace embedded path mechanics with helper CLI calls. |
| Refresh smoke labels and helper paths that exercise Handoff archive/state behavior | wrapper-preserved | Keep existing labels unless the refresh classifier ledger records an explicit rename; update helper paths to source/installed storage authority where appropriate. |

Backward-compatibility tests must lock the intended old surface. Skill-doc tests must be updated deliberately rather than made to pass by removing old assertions without a replacement contract.

## Generated Stale-Text Gate

The stale-text gate must use generated inventory, not a soft preference or narrow manual list.

The inventory source of truth is the generated artifact at `plugins/turbo-mode/handoff/1.6.0/tests/fixtures/storage_authority_inventory.json`.

Generation and verification must be separate commands:

- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py --write` updates the committed artifact.
- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority_inventory.py --check` verifies the committed artifact is current and must not mutate files.

Bootstrap rule: the first implementation pass may create the generator and artifact with `--write`. After the artifact exists, all verification and closeout uses `--check`, and `--check` must be no-write.

Gate 0r proof-map coverage for this section is a bootstrap requirement, not final generated-row coverage. Before `storage_authority_inventory.py` and `storage_authority_inventory.json` exist, the proof map must include a stale-text bootstrap row that assigns creation of the generator, fixture artifact, and no-write check contract to Gate 3. After Gate 3 creates the generator and artifact, Gate 3 must rerun `gate_proof_map.py --write` or an equivalent reviewed update so the proof map contains the generated stale-text requirement rows, then `gate_proof_map.py --check` must verify those rows. Gate 0r must not pretend to cover generated stale-text rows before the generator can emit them.

The inventory generator must emit the committed or reviewable artifact containing:

- generated authority path list
- blocked pattern list
- explicit historical allowlist entries
- per-path scan results
- failures with path, line, pattern, and reason

The gate passes only when this artifact or result is current with the source tree and has no unallowlisted blocked matches. Verification must include a no-dirty-tree check after `--check` for the inventory artifact and any generated scan outputs.

The stale-text gate must scan runtime warning strings as well as prose.

Because the hard-stop matrix and gate proof map scripts live outside the shipped Handoff plugin runtime tree, the generated inventory must not classify `hard_stop_matrix.py` and `gate_proof_map.py` as runtime helper entrypoints or installed plugin command surfaces. Refresh classifier and stale-text checks must still include these control-tooling files when they scan source-tree storage-authority text, but skill docs and installed-host harnesses must not treat them as ordinary Handoff user workflow helpers.

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

Minimum source-repair coverage:

- missing primary with valid legacy
- invalid primary with valid legacy
- legacy active exists, then new primary active exists, and default list/load still sees the eligible legacy active candidate during the cutover release
- ignored or untracked valid `docs/handoffs/*.md` legacy active files remain eligible during cutover only when plugin-origin runtime marker provenance, legacy-active preflight evidence tied to an accepted external origin source, or exact reviewed path-plus-hash opt-in proves they are runtime material; valid-looking ignored or untracked files without that proof become `policy-conflict-artifact`
- ignored or untracked valid `docs/handoffs/*.md` files with only ordinary runtime-shaped frontmatter fields such as `session_id`, `type`, `project`, `created_at`, `branch`, `commit`, `resumed_from`, or `files` become `policy-conflict-artifact` unless another accepted provenance proof exists
- valid-looking ignored or untracked `docs/handoffs/*.md` files with explicit `policy-conflict-artifact` rejection rows are excluded from active selection without blocking implementation, as long as the implementation does not need to select them implicitly
- reviewed legacy-active opt-in manifest rows enable runtime migration only for exact project-relative path plus raw-byte hash matches; path mismatch, hash mismatch, or missing reviewer/reason keeps the file blocked as `policy-conflict-artifact`
- tracked durable `docs/handoffs/*.md` files are excluded from default active selection unless an exact reviewed runtime migration opt-in names the path and hash
- tracked `.codex/handoffs/*.md` primary source files are reported as blocked and are not moved by implicit or explicit load
- successful legacy load copies to primary archive, writes primary state, writes consumed legacy-active registry, and removes the loaded legacy source from later active-selection list/load results
- changed bytes at the same legacy source path are treated as a new candidate rather than suppressed by path alone
- every source-backed candidate and target allocation reports filesystem status separately from git visibility, including directory, symlink, non-regular, unreadable, and parent-file-conflict cases
- transaction coverage for read-only recovery inventory over pending transactions, interruption after archive mutation, interruption after active writer output, interruption after state write, duplicate retry, and concurrent attempts for primary active, primary archive, legacy active, legacy archive, save, summary, and quicksave paths
- read-only list/distill/search/triage/state inventory never completes, rolls back, suppresses, clears, marks, or writes transaction recovery artifacts
- save/summary/quicksave active writes call `begin-active-write` before content generation, allocate paths only through `allocate-active-path`, write only under `.codex/handoffs/`, use atomic temp-plus-rename semantics, and clear or mark chain state under the same project lock
- save/summary/quicksave skill-flow tests execute the complete begin/generate/write/retry protocol with persisted operation identity instead of only statically scanning skill docs for helper names
- two save/summary/quicksave calls with the same timestamp slug allocate deterministic collision-safe active paths through at least base, `-01`, and `-02`
- save/summary/quicksave fails or enters recoverable transaction state rather than reporting success when active output is written but state cleanup fails
- implicit load chooses the newest valid active candidate from combined primary-active and legacy-active discovery after dedup
- load/list/distill recency uses filename timestamp, not filesystem mtime
- filename timestamp ties prefer primary active over legacy active, then lexical absolute path
- active-selection, history-search, explicit-path, and state-bridge scan modes have separate fixture coverage
- summary arc synthesis uses history-search candidates across primary active, primary archive, legacy active, legacy archive, and previous-primary hidden archive, and either records a candidate-set manifest hash in operation state or labels the arc context `best_effort_not_snapshot_bound`
- explicit `/load <path>` behavior for primary active, primary archive, legacy active, legacy archive, and previous-primary hidden archive
- no-frontmatter archive history is available only through history search with `document_profile=historical_archive`
- unreadable roots
- invalid frontmatter
- hidden files
- nested files
- explicit-path legacy archive behavior, history-search legacy archive behavior, and active-selection exclusion of legacy archives
- previous-primary hidden archive `.codex/handoffs/.archive/*.md` participates in history search and explicit archive load compatibility but never active selection
- repeated explicit previous-primary hidden archive load for the same source root, project-relative source path, storage location, and raw-byte hash reuses the same verified primary archive path from `copied-legacy-archives.json`
- `.session-state/` rejection
- file symlink escape
- directory symlink escape
- non-regular files
- duplicate hashes across all five history-search precedence tiers
- same-tier path-sort ties
- collision allocation through at least base, `-01`, and `-02`
- collision budget exhaustion
- non-git cwd storage, project naming, state filename, and cleanup
- search/triage provenance output visibly selecting primary over legacy
- pre-upgrade legacy state plus post-upgrade save/summary/quicksave preserves `resumed_from`, writes only under `.codex/handoffs/`, and suppresses the consumed legacy state through a primary-state marker without modifying legacy bytes
- bridged legacy state cleanup proves a second bridge lookup returns no usable state after durable consumed marking
- bridged legacy state suppression markers use source root, storage location, project-root-relative state path, project, resume token when derivable, detected format, and raw-byte payload hash as the stable key, with absolute paths as evidence only
- bridge lookup suppression survives a clone move or copied project root when the legacy state has the same project-relative path and payload hash
- project-scoped state bridge lookup succeeds without caller-provided resume token when exactly one valid project state exists
- valid primary state plus unresolved same-project legacy state fails before active output creation and requires explicit operator-selected recovery
- multiple valid primary state candidates for the same project fail with an ambiguity diagnostic
- multiple valid legacy candidates for the same project fail with an ambiguity diagnostic when no primary state exists
- malformed, expired, ambiguous, or multiply matching legacy state emits an actionable diagnostic
- top-level `docs/handoffs/handoff-*` and `docs/handoffs/handoff-*.json` state-like residue is inventoried, classified, and either validly bridged or diagnostically rejected
- canonical-checkout local-preflight evidence includes the `canonical-checkout` residue scope and explicit accounting for every current `docs/handoffs/**` path, either as a state-like residue row, a non-handoff filesystem residue row, a legacy state/archive scope row, a permitted archive/state directory-summary manifest reference, or a delegated legacy-active markdown row tied to the legacy-active evidence hash
- legacy-active preflight evidence includes one classification row per current top-level `docs/handoffs/*.md` path and blocks valid-looking ignored or untracked markdown with no accepted external origin source as `policy-conflict-artifact`
- `docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md` uses `scope` values to separate `repo-authority`, `local-preflight-summary`, and `policy-rule` rows, does not list ignored or untracked local residue as fresh-clone truth, and keeps the `docs/handoffs/*.md` policy-rule row aligned with the current provenance-backed eligibility contract
- `.codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json` includes one local-preflight disposition row per current `docs/handoffs/handoff-*` and `docs/handoffs/handoff-*.json` path, plus an explicit row, delegated evidence reference, or permitted archive/state directory-summary manifest reference for every other current `docs/handoffs/**` path, with no `TBD` dispositions or artifact classes
- `.codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json` includes one legacy-active preflight row per current top-level `docs/handoffs/*.md` path, with no `TBD` artifact classes or provenance fields
- explicit legacy archive load repeated for the same source root, project-relative path, storage location, and raw-byte hash reuses the same verified primary archive path from `copied-legacy-archives.json`
- copied legacy-archive registry entries include source root, storage location, project-relative source path, source hash, lexical source path evidence, resolved path evidence, copied archive path, copied hash, timestamp, operation, recovery status, and transaction id
- copied legacy-archive registry corruption or missing copied archive content fails with a recovery diagnostic instead of silently allocating a duplicate copy
- active-writer transaction records include active output fields such as `allocated_active_path`, `temp_active_path`, `output_sha256`, and state cleanup action rather than relying on archive-only fields
- active-writer idempotency keys exclude `transaction_id` and generated content hash, while transaction records keep those values as separate fields
- active-writer retry with the same idempotency key and changed generated bytes fails with a typed diagnostic instead of creating a second active handoff
- active-writer recovery covers `pending_before_write`, `written_not_confirmed`, `cleanup_failed`, and `content_mismatch`
- active-writer tests prove the project lock is released during content generation and reacquired by `write-active-handoff`
- active-writer tests cover reservation lease expiry, lease renewal if implemented, conflicting state mutation after reservation, transaction watermark mismatch, and abandonment of expired reservations
- active-writer tests cover caller-predeclared slug binding, helper-default slug binding, and a retry that attempts to change the slug after path binding and fails closed
- stale `session_state.py --state-dir "$PROJECT_ROOT/docs/handoffs/.session-state"` callers cannot write, clear, prune, or migrate state under `docs/handoffs/`; `read-state` may use that path only as legacy bridge input after primary state-root resolution
- ambiguous same-project state emits a candidate inventory and supports an explicit operator recovery path without guessing
- `.codex/handoffs/*.md`, `.codex/handoffs/archive/*.md`, and `.codex/handoffs/.session-state/*.json` are ignored
- `.codex/handoffs/.session-state/**`, including locks, transactions, markers, temp files, and recovery records, is ignored
- archive temp files such as `.codex/handoffs/archive/.tmp-*` and `.codex/handoffs/archive/*.tmp` are ignored
- existing `docs/handoffs/*.md`, `docs/handoffs/archive/*.md`, and `docs/handoffs/.session-state/*.json` ignore behavior is preserved
- `.codex/skills/<sample>` is not ignored by the handoff runtime ignore rule
- load/list/distill/save/summary/quicksave docs call helper entrypoints and do not retain stale shell-only path logic
- chain-state helper docs preserve direct-Python launcher class and do not regress to dependency-bearing `uv run`
- compatibility ledger tests cover preserved, wrapper-preserved, and deprecated script APIs/CLI subcommands
- `/triage --handoffs-dir` tests cover explicit single-root diagnostic mode, including `override_mode`, `roots_scanned`, `roots_intentionally_skipped`, and the diagnostic pointing operators to `--project-root`
- discovery/search/triage tests fail on broad exception swallowing that drops path-specific skip reasons
- dormant validation helper closeout does not claim live hook behavior, or live hook closeout includes installed-config proof

Installed-host certification coverage is separate from `source repaired`. These behavior tests are mandatory before claiming the primitive proof label `installed host matrix behavior proved` or the composite labels `installed host matrix certified` and `installed cache certified`. Gate 1f must add `source-harness-isolation-proof` coverage for path resolution and cache isolation, but app-server-installed harness proof and the full installed-host behavior matrix may remain `not-claimed` when the closeout label is only `source repaired`:

- installed-host smoke for no `.codex/` ignore reports untracked `.codex/handoffs/` runtime files without editing host ignore files
- installed-host smoke for broad `.codex/` ignore reports ignored `.codex/handoffs/` runtime files without using source-repo ignore proof
- installed-host smoke for tracked `.codex/skills/**` with narrow handoff ignore proves `.codex/skills/<sample>` remains tracked or trackable
- installed-host smoke for tracked `.codex/handoffs/<candidate>.md` treats the path as occupied and avoids overwrite
- installed-host smoke for tracked `.codex/handoffs/<active-source>.md` selected for load fails closed before moving the source
- installed-host smoke asserts `target_fs_status` and `source_fs_status` alongside `target_git_visibility` and `source_git_visibility` for no-ignore writes, tracked collision, tracked active source, non-git roots, and at least one directory or symlink collision
- installed-host smoke asserts installed helper and skill-doc realpaths are outside the source checkout before any behavior assertion counts as installed proof

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
git status --short --ignored -- .codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json
```

The implementation branch for this execution is `feature/handoff-storage-reversal-main` in the canonical checkout, using this repo's `feature/*` branch-prefix policy. Direct implementation on `main` is not allowed. Creating a new implementation branch from `main`, switching to a different branch base, or using a different worktree topology is not allowed under the current Gate 0r evidence contract; if execution intentionally changes topology later, stop and patch this plan first to require regenerated state-like local-preflight evidence, regenerated legacy-active preflight evidence, refreshed ledger/proof-map base-commit authority, and a new Gate 0r branch/status record before any old evidence is reused. Branch switching is forbidden from a worktree with unrelated modified, deleted, or untracked paths. If `git status --short --untracked-files=all` shows anything outside the reviewed control document, repo-authority residue ledger, explicitly ignored state-like local-preflight evidence, and explicitly ignored legacy-active preflight evidence, stop and repair the checkout hygiene or revise this plan before code changes. During Gate 0r only, the permitted tracked authority-edit set also includes the optional reviewed legacy-active opt-in manifest, `docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md`, `docs/superpowers/plans/2026-05-13-handoff-storage-gate-proof-map.md`, and the source-tree control tooling scripts named by this plan under `plugins/turbo-mode/tools/handoff_storage_reversal/`. Those files are plan/control surfaces, not Handoff runtime implementation surfaces, and Gate 0r is green only after they are committed and ordinary status is clean. Gate 1 runtime implementation must not rely on the Gate 0r authority-edit allowlist. Do not move, stash, delete, or normalize unrelated user work as part of this plan.

The preflight must classify tracked durable handoff artifacts, provenance-backed ignored legacy active markdown artifacts, provenance-backed untracked legacy active markdown artifacts, legacy operational archives, legacy state bridge inputs, previous-primary hidden archive artifacts, state-like residue, and policy-conflict artifacts before code changes. Collapsed directory-only status output is not sufficient; path-level inventory from `find` or an equivalent enumerator is required. The control document and repo-authority residue ledger must be tracked or otherwise explicitly recorded as durable implementation authority before source code changes begin. Local state-like residue enumeration belongs in ignored state-like local-preflight evidence, legacy active markdown classification belongs in ignored legacy-active preflight evidence, and neither may be presented as fresh-clone repo truth.

Repeat this preflight at the start of every mutating behavior gate, not only Gate 0r. The closeout for Gates 1c, 1d, 1e, 1g, and 4 must name the preflight timestamp, branch head, state-like local-preflight evidence hash, legacy-active preflight evidence hash, and TTL classification result used for that gate.

Gate 0r control-map verification:

```bash
python plugins/turbo-mode/tools/handoff_storage_reversal/hard_stop_matrix.py \
  --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md \
  --matrix docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md \
  --check
python plugins/turbo-mode/tools/handoff_storage_reversal/gate_proof_map.py \
  --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md \
  --hard-stop-matrix docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md \
  --map docs/superpowers/plans/2026-05-13-handoff-storage-gate-proof-map.md \
  --check
python plugins/turbo-mode/tools/handoff_storage_reversal/residue_preflight.py \
  --project-root . \
  --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md \
  --ledger docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md \
  --evidence .codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json \
  --check
python plugins/turbo-mode/tools/handoff_storage_reversal/legacy_active_preflight.py \
  --project-root . \
  --evidence .codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json \
  --check
git ls-files --error-unmatch plugins/turbo-mode/tools/handoff_storage_reversal/hard_stop_matrix.py
git ls-files --error-unmatch plugins/turbo-mode/tools/handoff_storage_reversal/gate_proof_map.py
git ls-files --error-unmatch plugins/turbo-mode/tools/handoff_storage_reversal/residue_preflight.py
git ls-files --error-unmatch plugins/turbo-mode/tools/handoff_storage_reversal/legacy_active_preflight.py
git ls-files --error-unmatch docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md
git ls-files --error-unmatch docs/superpowers/plans/2026-05-13-handoff-storage-gate-proof-map.md
git diff --exit-code -- docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md
git diff --exit-code -- docs/superpowers/plans/2026-05-13-handoff-storage-gate-proof-map.md
git status --short -- docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md docs/superpowers/plans/2026-05-13-handoff-storage-gate-proof-map.md
```

The proof map must be a separate tracked file for this execution. Do not embed it in this document unless this plan is patched first to define an equivalent generated/check-mode parser for embedded rows. Gate 0r closeout must run the proof-map check and prove that every Required Tests bullet, every Hard Stop Conditions row from the checked hard-stop matrix, every Installed Host Repo Policy Matrix row, every Compatibility Ledger row with decision `preserved`, `added`, `wrapper-preserved`, or `deprecated with diagnostic`, and the stale-text bootstrap requirement each have an enforcing gate and proof command or artifact. After Gate 3 creates the stale-text generator and fixture artifact, Gate 3 closeout must update and check the proof map so every generated stale-text requirement row is mapped before source closeout can claim `refresh surfaces reconciled`.

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

Residue and legacy-active verification must include three checks:

- a repo-authority ledger check through `residue_preflight.py --check` that fails if `docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md` lacks a `scope` column, contains ignored/untracked local residue rows as `repo-authority`, or carries stale `docs/handoffs/*.md` policy-rule text that omits the provenance-backed ignored/untracked or exact reviewed opt-in eligibility requirement
- a local-preflight evidence check through `residue_preflight.py --check` that compares the current `docs/handoffs/**` inventory to `.codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json` and fails if any current path lacks a state-like disposition row, a non-handoff filesystem residue row, a legacy state/archive scope row, or a delegated legacy-active evidence reference
- a legacy-active preflight evidence check through `legacy_active_preflight.py --check` that compares current top-level `docs/handoffs/*.md` inventory to `.codex/handoffs/.session-state/preflight/handoff-storage-legacy-active-preflight.json` and fails if any current active markdown path lacks an artifact class, selection eligibility, raw-byte hash when readable, and accepted external origin source or explicit `policy-conflict-artifact` rejection

Installed-host matrix verification is not part of the `source repaired` closeout command floor. When Gate 5 is in scope, or when any closeout claims `installed host matrix behavior proved`, `installed host matrix certified`, or `installed cache certified`, verification must include the installed plugin/helper path, not source-only imports. The implementation may add a focused test or smoke command, but closeout must name the exact command. A source-tree pytest selector is allowed only as an orchestrator that resolves and executes the installed plugin code path. Minimum selector if implemented as pytest:

```bash
uv run pytest plugins/turbo-mode/handoff/1.6.0/tests/test_installed_host_repo_storage.py
```

That smoke must create temporary host repos for no `.codex/` ignore, broad `.codex/` ignore, tracked `.codex/skills/**` with narrow handoff ignore, tracked handoff-path collision, tracked primary active source, and non-git project roots. It must assert the helper-reported `target_git_visibility` and `source_git_visibility` values where applicable, and prove no host ignore file or index is edited by Handoff.

The smoke must also assert that the helper and skill-doc realpaths under test are outside the source checkout. A run that imports `plugins/turbo-mode/handoff/1.6.0/scripts/*` from this source tree is source verification, not installed-host verification, and cannot earn `installed host matrix certified` or `installed cache certified`.

## Evidence Status Gates

Closeout must record narrow proof labels before assigning a composite status. The proof labels are:

- `source storage repaired`: source helper APIs, storage discovery, filesystem/git diagnostics, transactions, registries, active writers, state bridge, recovery, source-repo ignore policy, and source tests pass.
- `skill docs reconciled`: Handoff skill docs and release docs invoke the helper protocol and contain no current-facing stale storage authority text.
- `refresh surfaces reconciled`: refresh classifier, fixtures, inventory, stale-text gate, and source refresh smoke agree with `.codex/handoffs/` as primary.
- `source-harness-isolation-proof`: source tests prove the installed-host harness assertions for isolated layout, manifest identity, realpath separation, helper cwd isolation, import isolation, and source-checkout leak rejection without mutating the real installed cache. A test-only installer or fixture plugin root may satisfy this label only when it records the non-equivalent install method and avoids app-server-installed proof language.
- `installed-harness-source-proof`: isolated harness source tests install the Handoff plugin through the guarded-refresh app-server install authority path into an isolated `CODEX_HOME`, then prove installed-root resolution, cache isolation, manifest identity, realpath separation, helper cwd isolation, and import isolation; no installed-host behavior matrix or installed-cache currency is claimed. Test-only installer layout proof does not satisfy this label.
- `installed host matrix behavior proved`: installed plugin/helper smoke covers the host-repo policy matrix through the app-server install authority path.
- `installed cache current`: source/cache equality or approved divergence proof exists, installed cache was refreshed or verified current, installed-cache smoke passes, the installed skill docs are the docs under test, and any live hook claim has installed-config proof.

After those proof labels are recorded, closeout must use exactly one composite publication label:

- `source repaired`: requires `source storage repaired`, `skill docs reconciled`, `refresh surfaces reconciled`, `source-harness-isolation-proof`, hard-stop matrix proof, and source refresh smoke. It explicitly does not claim app-server-installed harness proof, installed-host matrix behavior, installed-cache currency, or live hook behavior.
- `refresh-ready but not mutated`: all `source repaired` requirements pass, `installed-harness-source-proof` passes, and refresh evidence says mutation is ready, but live installed-cache mutation was not run.
- `installed host matrix certified`: all `refresh-ready but not mutated` requirements pass, `installed host matrix behavior proved` passes, and no broader installed-cache certification or live hook claim is made beyond that matrix.
- `installed cache certified`: all preceding requirements pass, plus `installed cache current` passes.

## Implementation Order

Use named vertical commit gates so the implementation does not become one long unstable branch. A gate may go red locally while it is being implemented, but the gate boundary must be green and reviewable. Do not merge or hand off a gate that only adds tests for future code. Each gate must include its own tests, implementation, compatibility notes, and focused verification.

Gate 0r freshness is not inherited by later behavior-changing gates. Before every gate or PR that starts mutating runtime behavior, rewires active writers or load semantics, changes state/registry handling, or claims source closeout, rerun branch/residue/TTL preflight from the current branch head. At minimum this applies to Gates 1c, 1d, 1e, 1g, 4, and any split PR that touches their owned surfaces. If the preflight discovers new residue, expired TTL evidence, dirty unrelated worktree state, or a changed branch base, the gate stops until the local-preflight evidence and this plan's disposition rules are refreshed.

1. `gate-0a-control-authority-and-ignore-policy` - historical prep at `bf83762`: Created `feature/handoff-storage-reversal-main` from current `main`, recorded this control document and the repo-authority residue ledger, and patched the narrow source-repo `.codex/handoffs/**` ignore policy.
2. `gate-0b-local-preflight-evidence` - historical prep at `bf83762`: Generated ignored canonical-checkout local-preflight evidence at `.codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json`; evidence hash was `335e8b2fc615167d92168c7afb011da58753c3c2c010da5e0a5f3f37b7c85e12`.
3. `gate-0r-review-reanchor-and-preflight-refresh`: During Gate 0r, reviewed tracked plan, ledger, optional legacy-active opt-in manifest, preflight, hard-stop matrix, proof-map, or source-tree control-tooling script edits named by this plan may exist in the worktree while they are being prepared. Gate 0r is green only after those tracked authority edits are committed, `git status --short --untracked-files=all` is clean, expected ignored local runtime evidence is verified separately with `git status --short --ignored --untracked-files=all <paths>`, branch/residue preflight has been rerun, TTL-sensitive `bridge-once` evidence has been refreshed or reclassified, `residue_preflight.py --check` proves every current `docs/handoffs/**` path has a state-like disposition row, non-handoff filesystem residue row, legacy state/archive scope row, permitted archive/state directory-summary manifest reference, or delegated legacy-active evidence reference and proves the repo-authority ledger has no stale policy-rule drift, `legacy_active_preflight.py --check` proves legacy-active preflight evidence has classified every current top-level `docs/handoffs/*.md` path, any legacy-active opt-in manifest rows are tracked and reviewed with exact path-plus-hash matching, the hard-stop closeout matrix is tracked and passes `hard_stop_matrix.py --check`, and the proof map is tracked and passes `gate_proof_map.py --check` against that hard-stop matrix for all Gate 0r row sources including the stale-text bootstrap requirement. Source code implementation remains blocked until this gate is green.
4. `gate-1a-discovery-read-only-slice`: Add the `storage_authority.py` facade plus internal path/discovery/git modules needed for read-only inventory. Add and pass tests for cutover inventory, scan-mode separation, artifact-class filtering, git visibility filtering, candidate validation, skip reasons, dedup, ordering, source-repo ignore policy, and the ban on broad exception swallowing in search/triage discovery. Rewire only read-only discovery call sites that this gate can leave green.
5. `gate-1b-reader-history-slice`: Rewire `/list-handoffs`, default and explicit `/distill`, `/search`, and `/triage` history search to the shared read-only discovery facade. Add and pass provenance, dedup-winner, historical-archive, `--project-root`, deprecated `--handoffs-dir`, and no-side-effect recovery-inventory tests. This gate must not add mutating load behavior.
6. `gate-1c-load-transaction-slice`: Add transaction, registry, lock, atomic archive copy/move, and recovery primitives needed for load. Add and pass tests for primary active/archive load, tracked primary active source fail-closed behavior, legacy active/archive load, consumed legacy-active registry, copied legacy-archive registry, read-only recovery inventory, mutating recovery, explicit load idempotency, interruption, and concurrent retry. Rewire `/load` only after these tests pass.
7. `gate-1d-active-writer-operation-state-slice`: Add active-writer operation-state persistence, `begin-active-write`, `allocate-active-path`, `write-active-handoff`, `list-active-writes`, `active-write-transaction-recover`, and `abandon-active-write`. Add and pass tests for helper-minted run id persistence, visible operation identity, context-compaction/retry recovery, active allocation, atomic write, idempotency key, changed-content retry failure, partial write recovery, and state cleanup. Rewire `/save`, `/summary`, and `/quicksave` only after the operation-state contract is green and the Active Writer Creation Contract's state-bridge dependency rule is satisfied; otherwise Gate 1d may close only as `active-writer mechanics staged`.
8. `gate-1e-state-bridge-and-recovery-slice`: Add project-scoped legacy-state bridge and operator recovery commands. Add and pass tests for state-like residue handling, TTL expiry diagnostics, ambiguous state diagnostics, primary-state-plus-unresolved-legacy fail-closed behavior, bridge cleanup proof, `continue-chain-state`, `mark-chain-state-consumed`, `abandon-primary-chain-state`, and `chain-state-recovery-inventory`.
9. `gate-1f-installed-host-harness-slice`: Add the isolated installed-host harness and source-harness isolation tests that prove the harness catches source-checkout leakage and resolves helper realpaths outside the source checkout under an isolated root. This gate is part of source repair before Gate 4 and may pass with test-only or fixture install coverage when it records the non-equivalent install method and avoids app-server-installed, installed-host matrix, or installed-cache certification claims.
10. `gate-1g-active-writer-bridge-integration-slice`: Required whenever Gate 1d closed as `active-writer mechanics staged` before Gate 1e landed. Re-run active-writer begin/generate/write/retry flows against the completed state bridge, prove pre-upgrade legacy state plus post-upgrade save/summary/quicksave preserves `resumed_from`, prove cleanup suppression markers prevent bridge resurrection, and only then allow `/save`, `/summary`, or `/quicksave` skill-doc rewires or `active writers rewired` source claims. If Gate 1d already included the minimal state bridge and all bridge-backed active-writer tests, Gate 1g may close as an explicit no-op with proof-map rows pointing to the Gate 1d evidence.
11. `gate-2-skill-docs-release-docs`: Reconcile skill docs, dormant validation helpers or live hooks, README, changelog, contract docs, release metadata, and helper launcher-class assertions with `.codex/handoffs/` as primary.
12. `gate-3-refresh-and-stale-text`: Reconcile refresh classifier source, fixtures, inventory tests, `plugins/turbo-mode/tools/refresh/smoke.py`, the generated stale-text gate, storage authority inventory artifacts, and separate `--write`/`--check` inventory commands. This gate must replace the Gate 0r stale-text bootstrap proof-map row with generated stale-text requirement rows, then run `gate_proof_map.py --check` before claiming refresh surfaces are reconciled.
13. `gate-4-source-closeout`: Run source verification, prove every hard-stop matrix row, and assign exactly one evidence status gate.
14. `gate-5-installed-certification`: Only after source repair is proven, decide whether to run installed-cache refresh/certification and the installed-host matrix smoke.

Preferred PR split:

- Discovery/read-only PR: Gates 0r, 1a, and 1b.
- Load/archive transaction PR: Gate 1c.
- Active writers/state recovery PR: Gates 1d, 1e, and 1g, unless Gate 1d is large enough to split alone.
- Installed-host harness source PR: Gate 1f, with no real installed-cache mutation or app-server-installed proof claim unless explicitly run as a later refresh-readiness gate.
- Docs/refresh/stale-text PR: Gates 2 and 3, after Gate 1f is reviewed or explicitly merged first.
- Source closeout PR or closeout commit: Gate 4, only after required Gates 1a-1g and Gates 2-3 are green.
- Installed-host certification maintenance run: Gate 5 only if installed-host behavior certification or real installed-cache mutation is in scope.

WIP cap: keep at most one non-green implementation gate open on a branch. If a gate starts pulling in the next slice to pass, stop and split or patch this implementation order before continuing.

### Gate Proof Map

Gate 0r must create a tracked proof map before Gate 1 source edits. For this execution the proof map must live in:

```text
docs/superpowers/plans/2026-05-13-handoff-storage-gate-proof-map.md
```

The proof map is the execution-economics control for this reversal. During Gate 0r it must assign every Required Tests bullet, every Hard Stop Conditions row, every Installed Host Repo Policy Matrix row, every Compatibility Ledger row with decision `preserved`, `added`, `wrapper-preserved`, or `deprecated with diagnostic`, and the stale-text bootstrap requirement to an enforcing gate. Generated stale-text rows become proof-map inputs only after Gate 3 creates `storage_authority_inventory.py` and `storage_authority_inventory.json`; Gate 3 must then refresh and check the proof map so those generated rows are mapped before source closeout.

The proof map must be generated or mechanically checked from this control document. A hand-copied proof map is not sufficient. Gate 0r must add `plugins/turbo-mode/tools/handoff_storage_reversal/gate_proof_map.py` as source-tree control tooling outside the shipped Handoff plugin runtime tree. The script must be stdlib-only, must not import storage implementation modules, and must support:

```bash
python plugins/turbo-mode/tools/handoff_storage_reversal/gate_proof_map.py \
  --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md \
  --hard-stop-matrix docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md \
  --map docs/superpowers/plans/2026-05-13-handoff-storage-gate-proof-map.md \
  --write
```

```bash
python plugins/turbo-mode/tools/handoff_storage_reversal/gate_proof_map.py \
  --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md \
  --hard-stop-matrix docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md \
  --map docs/superpowers/plans/2026-05-13-handoff-storage-gate-proof-map.md \
  --check
```

`--write` may create or refresh the tracked proof map during Gate 0r. `--check` must be no-write, fail if any required source row is missing from the proof map, fail if mapped text hashes diverge, fail if hard-stop `HS-###` IDs or hashes do not match the checked hard-stop matrix, and leave `git diff --exit-code -- docs/superpowers/plans/2026-05-13-handoff-storage-gate-proof-map.md` clean. The script must parse the required rows from the headings that define them, use the supplied hard-stop matrix as the source of truth for hard-stop IDs and hashes, assign stable IDs in source order for all non-hard-stop requirements, normalize each requirement with a documented whitespace rule, and store a SHA256 over the normalized exact requirement text. It must emit per-gate row counts and fail if any gate exceeds the explicit proof-map row budget in the Gate Capacity Model without a mapped split trigger or plan patch.

The proof map must include these columns:

| Column | Requirement |
|---|---|
| `requirement_id` | Stable ID for the mapped requirement. Hard stops use the `HS-###` IDs from the hard-stop matrix. Other requirements use stable prefixes such as `RT-###`, `CL-###`, `IH-###`, `ST-BOOTSTRAP`, or generated `ST-###`. |
| `source_reference` | File, heading, and line or checksum-addressable text for the requirement. |
| `requirement_sha256` | SHA256 over the normalized exact requirement text emitted by `gate_proof_map.py`. |
| `first_enforcing_gate` | Earliest gate that must make the requirement true. |
| `proof_owner` | `storage-discovery`, `reader-history`, `load-transaction`, `active-writer`, `state-recovery`, `installed-harness`, `skill-docs`, `refresh`, or `closeout`. |
| `proof_command_or_artifact` | Exact selector, smoke command, generated inventory, ledger check, or manual-review artifact that proves the requirement. |
| `split_trigger` | Gate-local threshold that forces a split before continuing. |
| `status` | `pending`, `proved`, `not-claimed`, or `blocked`. |

Gate briefs and PR descriptions must reference the relevant proof-map rows. If one gate owns more rows than its Gate Capacity Model budget can credibly review, the gate stops before implementation and this plan must be split or patched. A green pytest selector is not enough when proof-map rows remain pending, missing, hash-divergent, over budget without split disposition, or lacking a concrete command or artifact.

### Gate Capacity Model

Each gate must start with a short gate brief in the PR description or closeout note naming the owner role, owned file set, expected test count, proof-map row budget, and split triggers. These budgets are planning controls, not permission to skip necessary files; exceeding one requires stopping to split the gate or patch this document.

| Gate | Owner role | Expected owned files | Expected new or changed tests | Max proof-map rows | Stop or split trigger |
|---|---|---:|---:|---:|---|
| 1a discovery read-only | storage discovery owner | 6-10 | 20-35 cases | 40 | More than 12 files, any load/writer mutation, or unresolved broad exception swallowing. |
| 1b reader/history | read-only surface owner | 5-9 | 15-30 cases | 28 | More than 10 files, any archive/state mutation, or stale direct root scans left in search/triage/summary. |
| 1c load transactions | load transaction owner | 8-14 | 30-50 cases | 45 | More than 16 files, active-writer code required to pass, or registry/transaction recovery not reviewable in one diff. |
| 1d active writers | active-writer owner | 8-14 | 30-50 cases | 45 | More than 16 files, state-bridge recovery dominates the diff, or skill-flow wrapper cannot be executed end-to-end. |
| 1e state bridge/recovery | state recovery owner | 6-10 | 20-35 cases | 40 | More than 12 files, deletion of legacy state proposed, or operator recovery remains prose-only. |
| 1f installed harness source | installed harness owner | 4-8 | 10-20 cases | 24 | More than 10 files, real `/Users/jp/.codex` mutation needed, source-harness isolation proof relies on ordinary source imports, or any app-server-installed proof claim relies on a test-only installer. |
| 1g active-writer bridge integration | active-writer/state integration owner | 3-6 | 10-20 cases | 18 | Any new broad storage primitive, skill-doc rewire before bridge-backed flow passes, or unresolved staged-vs-rewired label ambiguity. |
| 2 skill/release docs | skill docs owner | 8-14 | 8-15 surface assertions | 30 | More than 16 files or docs claim behavior not yet proven by source gates. |
| 3 refresh/stale text | refresh owner | 6-12 | 15-30 cases | 34 | More than 14 files, inventory generator mutates during `--check`, or refresh labels blur source and installed-cache proof. |
| 4 source closeout | closeout owner | 2-5 evidence/control files | hard-stop matrix plus command evidence | 30 | Any unproved hard stop, any manual-review row without named reviewer evidence, or any composite label with missing primitive proof labels. |
| 5 installed certification | installed certification owner | 2-6 harness, smoke, and evidence files | 6-12 host matrix cases | 18 | Any real `/Users/jp/.codex` mutation without explicit operator request, source-checkout import leakage, app-server install authority unavailable for claimed installed proof, host ignore/index mutation, or expansion beyond the Installed Host Repo Policy Matrix. |

Gate 5 rows may remain `not-claimed` in the proof map during source-repair closeout only when the composite label is no stronger than `source repaired` and the row records that installed-host behavior, installed-cache currency, and real installed-cache mutation are explicitly excluded. Once any closeout claims `refresh-ready but not mutated`, `installed host matrix certified`, or `installed cache certified`, the relevant Gate 5 proof-map rows are no longer budget-exempt and must obey the Gate 5 budget and split trigger above.

## Hard Stop Conditions

Stop implementation and repair the contract before continuing if any of these occur:

- Preflight does not classify `docs/handoffs/**` artifacts or the branch/worktree state before implementation.
- Preflight relies on collapsed `docs/handoffs/` status output instead of path-level artifact enumeration.
- A mutating behavior gate starts from stale Gate 0r evidence instead of rerunning branch/residue/TTL preflight from the current branch head.
- Implementation proceeds directly on `main`, creates a different implementation branch, switches to a different base, or moves to a different worktree topology instead of continuing on `feature/handoff-storage-reversal-main` under the current Gate 0r evidence contract.
- Branch switching or implementation starts from a dirty worktree with unrelated modified, deleted, or untracked paths instead of stopping and repairing checkout hygiene.
- A non-canonical implementation worktree is introduced without first revising this plan, the residue ledger, and the local-preflight plus legacy-active preflight evidence schemas.
- Source code implementation starts while this control document is still untracked or not otherwise recorded as durable implementation authority.
- Gate 1 source edits start before the hard-stop closeout matrix and gate proof map are tracked, checked, and anchored to the current committed plan boundary.
- Gate 1 source edits start before `gate_proof_map.py --check` proves full coverage for Required Tests, Hard Stops, Installed Host Matrix rows, Compatibility Ledger rows, the stale-text bootstrap requirement, and per-gate proof-map row budgets. After Gate 3 creates the generated stale-text artifact, source closeout starts before `gate_proof_map.py --check` proves the generated stale-text rows are mapped.
- Local-preflight evidence is generated before the narrow source-repo `.codex/handoffs/**` ignore policy is patched and verified.
- The tracked residue ledger lists ignored or untracked machine-local residue paths as `repo-authority` fresh-clone facts.
- Any local-preflight `docs/handoffs/handoff-*` or `docs/handoffs/handoff-*.json` path lacks an ignored local-preflight evidence row with scope, explicit disposition, and verification hook.
- Any current `docs/handoffs/**` path is absent from `residue_preflight.py --check` output, including paths delegated to legacy-active preflight, archive/state scope rows, state-like residue rows, and non-handoff filesystem residue rows.
- The tracked residue ledger contains stale `docs/handoffs/*.md` policy-rule text that omits the current provenance-backed ignored/untracked or exact reviewed path-plus-hash opt-in eligibility requirement.
- Any top-level `docs/handoffs/*.md` path lacks an ignored legacy-active preflight evidence row with artifact class, selection eligibility, raw-byte hash when readable, and accepted external origin source or explicit `policy-conflict-artifact` rejection.
- A reviewed legacy-active opt-in manifest is used without being tracked, reviewed, and tied to exact project-relative path plus raw-byte hash rows before Gate 1 source edits.
- The policy-authority override is used to delete, untrack, or reclassify tracked durable handoff artifacts as disposable.
- Default active selection includes tracked durable `docs/handoffs/*.md` artifacts without an exact reviewed runtime migration opt-in path and hash.
- Default active selection includes valid-looking ignored or untracked `docs/handoffs/*.md` files without plugin-origin runtime marker provenance, legacy-active preflight evidence tied to an accepted external origin source, or exact reviewed runtime migration opt-in path and hash.
- Default active selection treats a reviewed runtime migration opt-in as matching when the project-relative path or raw-byte hash differs from the manifest row.
- Implementation stops solely because a valid-looking legacy active file has an explicit `policy-conflict-artifact` rejection row and no workflow needs to select it implicitly.
- Default active selection treats ordinary handoff frontmatter fields such as `session_id`, `type`, `project`, `created_at`, `branch`, `commit`, `resumed_from`, or `files` as sufficient runtime provenance for an ignored or untracked legacy file.
- Default active selection excludes valid provenance-backed ignored or provenance-backed untracked legacy active markdown files during the cutover release without a documented diagnostic that intentionally blocks them.
- Previous-primary hidden archive files under `.codex/handoffs/.archive/*.md` disappear from history search or explicit archive-load compatibility without a compatibility-ledger decision and tests.
- A tracked `.codex/handoffs/*.md` source file is moved, archived, suppressed, or otherwise mutated by implicit or explicit primary load.
- A source-backed operation or target allocation reports only git visibility and omits filesystem status for directory, symlink, non-regular, unreadable, path-escape, or parent-file-conflict cases.
- Source-repo `.gitignore` checks are treated as proof of installed-host behavior.
- Handoff edits a host repo's `.gitignore`, `.git/info/exclude`, tracked `.codex/**` content, or index state during normal save/load/list/search/summary/quicksave behavior.
- Installed-host smoke does not cover no ignore, broad `.codex/` ignore, tracked `.codex/skills/**`, tracked handoff-path collision, tracked primary active source, and non-git project-root cases before claiming installed-host readiness.
- Installed-host smoke imports or executes Handoff helpers from the source checkout, or fails to assert installed helper and skill-doc realpaths outside the source checkout.
- Gate 1f source-harness output reports Installed Host Repo Policy Matrix behavior as proved, certified, app-server-installed, or installed-host behavior proof instead of limiting itself to isolated-root layout, cache isolation, manifest identity, realpath separation, cwd isolation, import isolation, and source-checkout leak rejection.
- A writer still writes current handoffs or chain state under `docs/handoffs/`.
- Save, summary, or quicksave constructs active output paths outside `allocate-active-path` or writes active markdown outside `write-active-handoff`.
- Save, summary, or quicksave is rewired before the state-bridge dependency is executable through either Gate 1d's minimal bridge implementation or completed Gate 1e state bridge/recovery.
- Save, summary, or quicksave reports success after writing active output while chain-state cleanup remains failed, ambiguous, or recoverable-only.
- Save, summary, or quicksave generates final content before `begin-active-write` has persisted a stable run id, state snapshot, and allocated path.
- Save, summary, or quicksave derives or changes the active filename slug from generated title/body content after `begin-active-write` has bound the active path.
- Save, summary, or quicksave skill-flow tests only static-scan helper names and do not execute the begin/generate/write/retry protocol with persisted operation identity.
- `begin-active-write` holds the project lock across LLM or local content generation instead of releasing it after durable reservation.
- `write-active-handoff` proceeds after an expired lease, conflicting chain mutation, state snapshot mismatch, transaction watermark mismatch, or ambiguous reservation match.
- Active-writer idempotency key includes `transaction_id` or generated content hash.
- Active-writer retry for the same `run_id` or idempotency key can change the bound slug or allocated active path without explicit operator-selected abandonment.
- Active-writer retry after partial write can create a second active handoff for the same idempotency key.
- Active-writer retry with the same idempotency key but changed generated bytes proceeds without an explicit `ActiveWriteContentChangedError` or equivalent diagnostic.
- Default `/list-handoffs` or implicit `/load` hides eligible legacy active files during the cutover release just because primary active files exist.
- Default `/list-handoffs`, implicit `/load`, or default `/distill` treats `docs/handoffs/archive/` as active-selection input.
- Read-only `/list-handoffs`, `/distill`, `/search`, `/triage`, or state inventory completes, rolls back, suppresses, clears, or marks a pending transaction instead of only reporting read-only recovery inventory.
- A successful legacy load leaves the loaded legacy active source visible to later active-selection scans without changed bytes.
- A legacy load can produce duplicate primary archive/state records for one source/hash after retry or concurrent load.
- Repeated explicit legacy archive load for the same source root, project-relative source path, storage location, and raw-byte hash creates duplicate primary archive copies instead of reusing the copied legacy-archive registry.
- Consumed or copied legacy registries use absolute paths as the only stable identity key instead of source root, project-relative source path, storage location, and raw-byte hash.
- Any mutating load/state path bypasses the project lock, transaction record, atomic write, or recovery protocol.
- Any active writer bypasses the project lock, transaction record, atomic write, or recovery protocol.
- A transaction interruption can leave inconsistent active/archive/state/registry artifacts without a recovery diagnostic.
- A legacy load moves, deletes, archives into, or writes state under `docs/handoffs/`.
- A post-upgrade save/summary/quicksave silently loses a valid pre-upgrade `resumed_from` link.
- A state bridge requires a caller-provided resume token rather than preserving current project-scoped pending-state semantics.
- Ambiguous same-project state failure omits a candidate inventory or provides no explicit operator recovery path.
- A primary state winning rule silently consumes, clears, or marks unresolved same-project legacy state candidates without explicit operator-selected recovery.
- A legacy-state or state-like-residue suppression marker uses absolute lexical path as the only stable key instead of source root, storage location, project-root-relative state path, project, resume token when derivable, detected format, and raw-byte payload hash.
- State-like residue under `docs/handoffs/handoff-*` is ignored silently instead of being classified.
- State-like residue is diagnostically rejected but left without local-preflight disposition, quarantine plan, consumed marker, or named blocker.
- A bridged legacy state can be read again after a supposedly successful cleanup, including after the project root is moved or copied with the same project-relative state path and payload hash.
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
- `/summary` claims snapshot-bound project-arc synthesis without recording and revalidating a candidate-set manifest hash, or fails to label the arc context `best_effort_not_snapshot_bound`.
- A preserved public script API or CLI subcommand is removed or silently changes output shape without a compatibility-ledger decision and test.
- `storage_authority_inventory.py --check` mutates files or lacks a corresponding `--write` update path.
- `gate_proof_map.py --check` mutates files, omits any required source row class, or allows proof-map rows to drift from the current plan text without failing.
- `gate_proof_map.py --check` validates hard-stop rows without cross-checking the supplied hard-stop matrix IDs and hashes.
- `residue_preflight.py --check` mutates files, omits any current `docs/handoffs/**` path, accepts historical plain `bridge-once` evidence after Gate 0r, grants migration eligibility outside delegated legacy-active proof, or fails to reject stale residue-ledger policy-rule drift.
- `legacy_active_preflight.py --check` mutates files, omits any current top-level active markdown path, classifies archive/state paths as legacy active markdown, or grants active-selection eligibility without accepted external origin proof or exact reviewed opt-in.
- `write-state`, `clear-state`, or `prune-state` accepts stale `--state-dir "$PROJECT_ROOT/docs/handoffs/.session-state"` as a post-cutover mutation target instead of rejecting it before mutation.
- Closeout runs `storage_authority_inventory.py --write` instead of check-only verification.
- A closeout claims live hook behavior when validation helpers remain dormant.
- A closeout report implies installed-cache currency without installed-cache evidence.

## Hard Stop Closeout Matrix

Gate 0r must create or update a closeout matrix before source code implementation starts. For this execution, the matrix must live in the separate tracked file `docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md`. Embedding the matrix in this document is not allowed unless a later plan patch also updates the `hard_stop_matrix.py` contract, Gate 0r verification commands, and tracked-file requirements before the embedded form is used.

The matrix must be generated or mechanically checked from the Hard Stop Conditions bullet list. A hand-copied matrix is not sufficient. Gate 0r must add `plugins/turbo-mode/tools/handoff_storage_reversal/hard_stop_matrix.py` as source-tree control tooling outside the shipped Handoff plugin runtime tree. The script must be stdlib-only, must not import storage implementation modules, and must support:

```bash
python plugins/turbo-mode/tools/handoff_storage_reversal/hard_stop_matrix.py \
  --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md \
  --matrix docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md \
  --write
```

```bash
python plugins/turbo-mode/tools/handoff_storage_reversal/hard_stop_matrix.py \
  --plan docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md \
  --matrix docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md \
  --check
```

`--write` may create or refresh the tracked matrix during Gate 0r. `--check` must be no-write, fail if the Hard Stop Conditions bullet list and matrix diverge, and leave `git diff --exit-code -- docs/superpowers/plans/2026-05-13-handoff-storage-hard-stop-closeout.md` clean. The script must parse only the bullets under `## Hard Stop Conditions`, assign stable `HS-###` IDs in bullet order, normalize each bullet with a documented whitespace rule, and store `stop_condition_sha256` as SHA256 over the normalized exact stop text. If a bullet is inserted, removed, or changed, `--check` must fail until the matrix is regenerated and reviewed.

Closeout must run the generator in check mode and prove the committed matrix is current. `manual-review` is exceptional: every manual row must name the reviewer evidence artifact and explain why no test, smoke, static scan, ledger check, generated inventory, or helper diagnostic can prove the stop.

The matrix must include one row for every bullet in Hard Stop Conditions with these columns:

| Column | Requirement |
|---|---|
| `stop_id` | Stable identifier, for example `HS-001`, matching the hard-stop bullet order. |
| `stop_condition` | Exact or checksum-addressable hard-stop text. |
| `stop_condition_sha256` | SHA256 over the normalized exact stop text emitted by `hard_stop_matrix.py`. |
| `authority_owner` | `plan`, `source`, `skill-docs`, `refresh`, `installed-host`, or `closeout`. |
| `enforcing_gate` | The first implementation gate that can prove the stop cannot occur. |
| `proof_type` | `unit-test`, `integration-test`, `smoke`, `static-scan`, `ledger-check`, `manual-review`, or `not-claimed`. |
| `proof_command_or_artifact` | Exact pytest selector, script command, smoke summary, generated inventory, or reviewer checklist item. |
| `closeout_status` | `pending`, `proved`, `not-claimed`, or `blocked`. |

Closeout cannot claim `source repaired` unless every hard-stop row is `proved` or `not-claimed` with an evidence-status label that explicitly excludes that surface. `manual-review` rows are allowed only under the exceptional rule above. A summary statement that tests passed is not a substitute for this matrix.

## Boundary Ledger

Gate 0A/0B prep commit: `bf83762 chore: prepare handoff storage reversal gate 0a`

Post-review plan authority commits:

- `4b5f6fc docs: reanchor handoff storage reversal plan`
- `7effa25 docs: tighten handoff reversal execution semantics`
- `8fd78af docs: define handoff mutation watermark`
- `2769186 docs: harden handoff storage reversal plan`
- `e9b416a docs: stabilize handoff state markers`
- `688335a docs: clarify state marker helper identity`

Before this working-tree patch, `688335a` is the latest clean committed authority boundary observed for this branch. The commit containing this patch supersedes that boundary only after it is committed on this branch with a clean worktree. Do not try to self-name a commit hash inside the commit that creates it; Gate 0r closeout must record the actual committed `HEAD`, branch name, and `git status --short --untracked-files=all` result before source implementation begins.

Final source implementation commit: filled during `gate-4-source-closeout` after source repair verification passes.

Files modified by Gate 0A/0B prep:

- `.gitignore`
- `docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md`
- `docs/superpowers/plans/2026-05-13-handoff-storage-residue-ledger.md`

Files expected for source implementation gates:

- `plugins/turbo-mode/handoff/1.6.0/scripts/storage_authority.py`
- internal storage authority modules named in Required Surfaces
- `plugins/turbo-mode/handoff/1.6.0/scripts/project_paths.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/session_state.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/search.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/triage.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/distill.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/quality_check.py`
- `plugins/turbo-mode/handoff/1.6.0/scripts/cleanup.py`
- Handoff skill docs, release docs, tests, refresh classifier/source smoke files, and generated storage authority inventory artifacts named in Required Surfaces.

### Verification

Historical Gate 0A/0B verification run before `bf83762`:

- `git status --short --branch --untracked-files=all` showed clean `feature/handoff-storage-reversal-main`.
- `git diff --check` and `git diff --cached --check` passed before the Gate 0A commit.
- `git diff --name-status main..HEAD` showed only `.gitignore`, this control document, and the residue ledger.
- `python -m json.tool .codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json` passed.
- `git check-ignore -v .codex/handoffs/example.md` and the preflight evidence path were positive.
- `git check-ignore -v .codex/skills/adversarial-review/SKILL.md` returned the expected non-match.

Gate 0r verification remains open until branch hygiene, ignored-evidence visibility, residue preflight, legacy-active markdown preflight, TTL classification, gate proof-map creation, and the hard-stop matrix check are rerun from the current committed plan boundary.

### Evidence Status

Gate 0A/0B prep exists historically at `bf83762`. The post-review plan authority lineage before this working-tree patch is `4b5f6fc` -> `7effa25` -> `8fd78af` -> `2769186` -> `e9b416a` -> `688335a`, with later clean committed plan corrections superseding that lineage only after commit. No primitive proof label or composite publication label exists until the corresponding later gates run and record fresh verification.

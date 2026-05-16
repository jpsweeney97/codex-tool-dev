# Handoff Architecture

## Runtime Package

`turbo_mode_handoff_runtime/` contains the implementation. `scripts/` contains only CLI facades used by skills.

## Storage Layout

Runtime ownership map (layering order, lowest first):

- `storage_primitives.py`: filesystem primitives, locking protocol, and atomic write helpers. Stdlib-only base layer with no internal imports.
- `storage_layout.py`: storage paths.
- `storage_inspection.py`: filesystem and git inspection helpers.
- `storage_authority.py`: handoff discovery and selection authority.
- `chain_state.py`: chain-state inventory, diagnostics, read, and lifecycle.
- `scripts/`: executable CLI facades only.

Layering invariant: imports flow one way, lowest to highest. The base layer is three independent, stdlib-only modules with no internal imports — `storage_primitives`, `storage_layout`, and `storage_inspection` (they are peers; none imports another). Above them: `storage_authority` → `chain_state` → `active_writes` → `session_state`/`load_transactions` → domain modules. No base-layer module may import any `turbo_mode_handoff_runtime` module (by absolute or relative import); doing so re-creates the cross-module import cycle the storage reseam removed and is prohibited. This is enforced mechanically by `tests/test_runtime_namespace.py::test_storage_base_layer_has_no_internal_imports`.

### Active-write status-domain partition

The active-write lifecycle persists two record kinds with **distinct,
non-mergeable** status vocabularies, typed in `active_writes.py` as
`ActiveWriteOperationStateStatus` and `ActiveWriteTransactionStatus`:

- **operation-state records** (`.../active-writes/<project>/<run>.json`):
  terminal `committed`; also exclusively `begun`, `unreadable`.
- **transaction records** (`.../transactions/<txn>.json`): terminal
  `completed`.

`committed` (operation-state) and `completed` (transaction) are the
discriminating pair. Merging the two vocabularies would re-introduce the
PR #15 prune-bug class. The invariant is enforced at runtime by
`tests/test_active_write_lifecycle_matrix.py`, which spies the single
atomic-write chokepoint and asserts the partition on every write
(transients included) across the lifecycle/recovery matrix; the Literal
aliases are the static-analysis handle and an advisory non-blocking
pyright CI step is the cheap precision surface.
`session_state.TERMINAL_TRANSACTION_STATUSES` is a cross-domain TTL-prune
terminal set, kept aligned via a test-layer check (no `session_state` →
`active_writes` module import — that would invert this layering).

Tripwires: (i) any write putting `completed` or `unreadable` into an
operation-state file or `committed`/`begun`/`unreadable` into a transaction
file falsifies the model — stop and triage. (ii) >~3 new pyright suppressions to land the
`transaction_status` annotation → drop to runtime-gate-only + tracked
ticket. (iii) Make pyright blocking only if a low-noise prototype holds
and status/payload bugs recur beyond PR #15.

`storage_authority_inventory.py` is a non-wired dev/CI helper (not part of the runtime load path): it builds and checks the storage-authority documentation-coverage fixture. See CONTRIBUTING.md for how to regenerate that fixture after a storage-authority doc change.

Primary handoffs live under `.codex/handoffs/`; controlled legacy discovery covers pre-cutover `docs/handoffs/` history.

## Locking Model

`storage_primitives.py` owns the shared project lock used by every mutating
operation. This describes the mechanism as implemented (the storage reseam did
not change lock behavior; rationale below is read from the code, not a separate
decision record).

- **Mutual exclusion is the lock file itself.** `acquire_lock` calls
  `os.open(path, O_CREAT | O_EXCL | O_WRONLY)`. `O_EXCL` makes "create the lock
  file" an atomic filesystem operation, so exactly one caller wins the race; no
  external lock dependency is needed (stdlib-only, consistent with the
  `storage_primitives` base-layer constraint). Lock metadata
  (`project`, `operation`, `transaction_id`/`lock_id`, `pid`, `hostname`,
  `created_at`, `timeout_seconds`) is written and `fsync`-ed, then read back and
  verified (`lock_id == transaction_id`) to reject torn or racing writes.
- **Caller-specific diagnostics via `LockPolicy`.** The shared mechanism takes a
  `LockPolicy(operation_label, lock_kind, error_factory)` so `active_writes` and
  `load_transactions` reuse one lock implementation while raising their own
  operation-specific error types — this is why the lock code lives once in the
  base layer.
- **Stale-lock recovery is itself locked.** `_try_recover_stale_lock` creates a
  second `<lock>.recovery` claim file, again with `O_CREAT | O_EXCL`, so only
  one recoverer acts at a time; the claim is always removed in a `finally`.
- **Timeouts.** `_LOCK_TIMEOUT_SECONDS = 1800` (30 min) is the age past which a
  held lock is eligible for recovery. `_CLAIM_TIMEOUT_SECONDS = 60` only feeds
  the operator hint that distinguishes a "live recoverer" from a "likely stale"
  recovery claim.
- **Fail-closed across hosts and on corruption.** A lock younger than its
  timeout is treated as genuinely held (no recovery). A stale lock is reclaimed
  only when it originated on the **same host** (`socket.gethostname()`); a stale
  lock from a different host, or unreadable/malformed lock metadata, raises and
  requires manual operator review rather than guessing — losing a handoff is
  worse than refusing to proceed. Recovery diagnostics tell the operator the
  exact `trash <path>` remedy.

These are operator-recovery contracts: changing timeout values, the same-host
recovery rule, or the read-back verification changes durability guarantees and
must be made deliberately, with `tests/test_storage_primitives.py` updated in
the same change.

## Active Writes

`active_writes.py` owns save, quicksave, and summary active-writer reservations. It uses chain-state read/continue operations from `chain_state.py`, but active-write command callers import active-write helpers directly.

## Load Transactions

`load_transactions.py` owns `/load` mutations: archive source selection, transaction recovery, state-file writes, and legacy-active consumption.

## Chain State Diagnostics

`ChainStateDiagnosticError` payloads are operator-recovery contracts. Every payload
carries an `error.code`; ambiguity payloads also carry `recovery_choices` and the
candidate inventory, and marker payloads carry the offending `marker_path`. Pick the
recovery from the payload — never force past a diagnostic.

| `error.code` | When it fires | Operator recovery |
|---|---|---|
| `primary-chain-state-not-consumable` | `mark-chain-state-consumed` selected a primary-state candidate (only legacy / state-like may be consumed) | Re-run `chain-state-recovery-inventory`; select a legacy or state-like candidate, or `abort`. |
| `chain-state-candidate-invalid` | The selected candidate's `validation_status` is not `valid` (or not `valid`/`expired` where the op allows expired) | Candidate is invalid/corrupt — re-run recovery inventory and select a valid candidate, or `abort`. |
| `chain-state-payload-hash-mismatch` | Selected candidate `payload_sha256` ≠ the expected resume-payload hash | State/payload divergence — do not force; `abort` and re-run `/load` recovery inventory. |
| `chain-state-candidate-not-primary` | `abandon-primary-chain-state` selected a non-primary candidate | Select the primary candidate, or use the operation appropriate to a legacy candidate. |
| `ambiguous-primary-chain-state` | More than one valid primary chain state exists | Choose one of `continue-chain-state`, `abandon-primary-chain-state`, `abort` (from `recovery_choices`). |
| `primary-chain-state-with-unresolved-legacy` | One valid primary plus unresolved legacy candidate(s) | Choose one of `mark-chain-state-consumed`, `abandon-primary-chain-state`, `abort`. |
| `ambiguous-legacy-chain-state` | More than one valid legacy chain state exists | Choose one of `continue-chain-state`, `mark-chain-state-consumed`, `abort`. |
| `expired-chain-state` | Only expired chain state(s) remain | Explicit operator recovery from the payload's `recovery_choices`; re-run inventory or `abort` if not resumable. |
| `chain-state-selector-ambiguous` | The supplied selector did not resolve to exactly one candidate | Run `chain-state-recovery-inventory` to list candidates, re-select, or `abort`. |
| `chain-state-marker-unreadable` | A chain-state marker file raised `OSError`/`JSONDecodeError` on read | Inspect `marker_path`; if corrupt, `trash <marker_path>` and re-run the operation. |
| `chain-state-marker-malformed` | A chain-state marker parsed but is not a JSON object | Inspect `marker_path`; if malformed, `trash <marker_path>` and re-run the operation. |

Recovery codes should remain stable unless tests, skill docs, and this reference change together.

## Legacy Fallback Exit Condition

Legacy `docs/handoffs/` discovery remains only for pre-cutover history. Remove the fallback in the next major release after supported user repositories have migrated or after a documented migration command proves no legacy history remains.

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

Layering invariant: imports flow one way, lowest to highest — `storage_primitives` → `storage_layout`/`storage_inspection` → `storage_authority` → `chain_state` → `active_writes` → `session_state`/`load_transactions` → domain modules. `storage_primitives.py` is the zero-internal-import foundation (highest fan-in in the runtime): it must not import any `turbo_mode_handoff_runtime` module. Adding such an import would re-create the cross-module import cycle the storage reseam removed and is prohibited.

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

# Handoff Architecture

## Runtime Package

`turbo_mode_handoff_runtime/` contains the implementation. `scripts/` contains only CLI facades used by skills.

## Storage Layout

Runtime ownership map:

- `storage_layout.py`: storage paths.
- `storage_inspection.py`: filesystem and git inspection helpers.
- `storage_authority.py`: handoff discovery and selection authority.
- `chain_state.py`: chain-state inventory, diagnostics, read, and lifecycle.
- `scripts/`: executable CLI facades only.

Primary handoffs live under `.codex/handoffs/`; controlled legacy discovery covers pre-cutover `docs/handoffs/` history.

## Active Writes

`active_writes.py` owns save, quicksave, and summary active-writer reservations. It uses chain-state read/continue operations from `chain_state.py`, but active-write command callers import active-write helpers directly.

## Load Transactions

`load_transactions.py` owns `/load` mutations: archive source selection, transaction recovery, state-file writes, and legacy-active consumption.

## Chain State Diagnostics

`ChainStateDiagnosticError` payloads are operator-recovery contracts. Recovery codes should remain stable unless tests, skill docs, and this reference change together.

## Legacy Fallback Exit Condition

Legacy `docs/handoffs/` discovery remains only for pre-cutover history. Remove the fallback in the next major release after supported user repositories have migrated or after a documented migration command proves no legacy history remains.

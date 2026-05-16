# ADR 0002 — Runtime module extraction and the stdlib-only base-layer seam

- **Status:** Accepted (back-fill record; module move shipped in handoff 1.7.0; storage reseam landed 2026-05-15, plan `docs/superpowers/plans/2026-05-15-handoff-storage-authority-reseam.md`)
- **Scope:** `plugins/turbo-mode/handoff/1.6.0/turbo_mode_handoff_runtime/`

## Context

Implementation logic originally lived under `scripts/*`, mixing executable
entrypoints with importable library code, and `storage_authority.py` had grown
into a multi-responsibility module (~1733 lines) owning layout arithmetic,
filesystem/git inspection, chain-state lifecycle, and discovery together. This
blocked isolated testing and made the import graph cycle-prone.

## Decision

1. Move implementation modules into `turbo_mode_handoff_runtime/*`; reduce
   `scripts/` to eight thin CLI facades only; `scripts.*` is no longer a
   supported import namespace (BREAKING, 1.7.0 CHANGELOG).
2. Reseam `storage_authority.py` by **hard moves, not compatibility re-export
   facades**: extract `storage_layout.py` (path arithmetic), `storage_inspection.py`
   (fs/git helpers), `chain_state.py` (chain-state inventory/diagnostics/lifecycle);
   residual `storage_authority.py` keeps handoff discovery, candidate
   classification, and active/history eligibility.
3. `storage_primitives.py` is the stdlib-only, zero-internal-import base layer.
   Imports flow one way (primitives → layout/inspection → authority → chain_state
   → active_writes → session_state/load_transactions → domain).

## Consequences

- The pre-reseam `storage_authority ↔ active_writes` cycle is eliminated; modules
  are independently testable.
- The layering invariant is enforced socially via `references/ARCHITECTURE.md` /
  `CONTRIBUTING.md` and mechanically via `tests/test_architecture_docs.py` and
  `tests/test_runtime_namespace.py`. Adding any internal import to
  `storage_primitives.py` re-creates the cycle and is prohibited.
- Hard moves mean no transitional shim debt; downstream importers were updated in
  the same change.

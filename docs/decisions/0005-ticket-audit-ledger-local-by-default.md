# ADR 0005 — Ticket plugin `.audit/` ledger is host-local, not version-controlled

- **Status:** Accepted (2026-05-16)
- **Scope:** This repository's version-control policy for the Ticket 1.4.0 audit trail (`docs/tickets/.audit/`)

## Context

The Ticket 1.4.0 plugin writes an append-only JSONL audit ledger at
`docs/tickets/.audit/YYYY-MM-DD/<session_id>.jsonl`, created automatically on
agent mutations. The plugin contract (`references/ticket-contract.md` §9) names
only `docs/tickets/*.md` as the durable consumer surface; the ledger is mutation
provenance, not the contract. ADR 0001 established that the plugin "does not add
gitignore rules, stage, or auto-commit; host-repo tracking policy remains
external" — so this decision is explicitly the host repo's to make. The ledger
was sitting untracked but un-ignored: visible in `git status` and one careless
`git add` from accidental commit. Commit `88d6860` already left it "untracked
per repo convention", but that convention was informal and unenforced.

## Decision

Add `docs/tickets/.audit/` to `.gitignore` as a labeled block parallel to the
existing handoff-runtime block. The ticket `.md` files remain the tracked
durable project state; the audit ledger is treated as host-local plugin
runtime/forensic state, mirroring how handoff `.session-state/` and `archive/`
are already ignored (`.gitignore`; ADR 0001).

## Consequences

- The ledger no longer appears in `git status` and cannot be swept in by
  `git add -A`; the prior informal convention is now repo-enforced.
- Audit history is session-scoped and not shared across clones. Acceptable: the
  only enforcement it powers (session create cap) is current-session only,
  triage's audit window defaults to 7 days, and "no audit data" is documented as
  expected for user-only workflows.
- Transient writer artifacts (e.g., the 2026-05-08 double-logging) are not
  enshrined in permanent history; the plugin's corruption-repair tooling remains
  the recovery path for the local ledger.
- Adjacent runtime paths `docs/tickets/.envelopes/` (+ `.processed/`) and
  `.codex/ticket-tmp/` are the same class of state; aligning their ignore policy
  is recommended follow-up, out of scope here.
- Reversible: delete the `.gitignore` line to resume tracking. Nothing is
  currently tracked, so no history rewrite is involved.

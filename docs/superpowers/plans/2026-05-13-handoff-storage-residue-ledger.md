# Handoff Storage Residue Ledger

## Status

Gate 0A ledger for `docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md`.

This ledger records clone-global policy and repo-authority facts only. Machine-local residue paths are summarized by run id, count, and evidence hash; they are not listed here as fresh-clone project facts.

## Scope Values

Allowed `scope` values:

- `repo-authority`: tracked or intentionally durable repo fact that must be true in a fresh clone
- `local-preflight-summary`: summary row that references local evidence by run id, timestamp, count, and evidence hash
- `policy-rule`: durable classification or disposition rule that applies to future implementations

## Ledger

| scope | subject | classification | evidence_basis | disposition |
|---|---|---|---|---|
| `repo-authority` | Canonical implementation branch base commit | Fresh implementation branch `feature/handoff-storage-reversal-main` was created from `main` at `9a3cf5deb1dcb64ea2be1aa535673afdfe856e47`. | `git rev-parse HEAD main origin/main` in `/Users/jp/Projects/active/codex-tool-dev` returned the same commit before Gate 0A edits. | Use this commit as the Gate 0A source boundary before code changes. |
| `repo-authority` | Tracked `docs/handoffs/**` corpus | `git ls-files docs/handoffs` returned 0 tracked paths in the canonical checkout. | `git ls-files docs/handoffs \| wc -l` returned `0`. | No tracked durable handoff artifact is enumerated by this ledger at Gate 0A. |
| `policy-rule` | `docs/handoffs/*.md` active legacy files | During cutover, valid ignored or untracked legacy operational handoffs are eligible migration input; tracked durable files remain excluded unless exact reviewed opt-in names path and hash. | Control document policy classes and active-selection rules. | Implement class-filtered active selection before timestamp ordering. |
| `policy-rule` | `.codex/handoffs/.archive/*.md` previous-primary hidden archives | Previous-primary hidden archives are history-search and explicit archive-load compatibility input, never active-selection input. | Control document path authority, scan modes, and compatibility ledger. | Preserve or explicitly deprecate with compatibility-ledger tests; do not silently drop. |
| `policy-rule` | Source repo `.codex/handoffs/**` runtime files | Runtime files under `.codex/handoffs/` are ignored narrowly in this source repo. | `.gitignore` Gate 0A patch plus `git check-ignore -v .codex/handoffs/example.md`. | Keep `.codex/skills/**` trackable; do not ignore all `.codex/**`. |
| `policy-rule` | Existing `docs/handoffs/**` runtime ignore policy | Existing source-repo ignore behavior for `docs/handoffs/*.md`, `docs/handoffs/archive/`, and `docs/handoffs/.session-state/` is preserved. | `.gitignore` existing rules and positive `git check-ignore -v` checks. | Preserve current operational handoff ignore behavior unless a later explicit tracking-policy decision changes it. |
| `local-preflight-summary` | Canonical-checkout residue inventory | Local preflight run `handoff-storage-reversal-preflight-20260513T050621Z` saw 1 canonical-checkout top-level `docs/handoffs/handoff-*` residue path. | Ignored evidence file `.codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json`; SHA256 `335e8b2fc615167d92168c7afb011da58753c3c2c010da5e0a5f3f37b7c85e12`. | Treat this as machine-local evidence only. Implementation must keep the ignored evidence file available during Gate 0B verification and must not present the canonical-checkout residue path as fresh-clone repo truth. |

## Guardrails

- Do not list ignored or untracked local residue paths as `repo-authority`.
- Do not delete, untrack, or normalize `docs/handoffs/**` artifacts from this ledger.
- Do not treat source-repo `.gitignore` checks as installed-host behavior proof.

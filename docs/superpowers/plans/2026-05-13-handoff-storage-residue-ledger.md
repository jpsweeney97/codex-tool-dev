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
| `policy-rule` | `docs/handoffs/*.md` active legacy files | During cutover, only provenance-backed ignored legacy active markdown, provenance-backed untracked legacy active markdown, or exact reviewed runtime migration opt-in rows naming `storage_location=legacy_active`, project-relative path, and raw-byte SHA256 are eligible migration input. Ignored or untracked git visibility, valid handoff shape, runtime-shaped frontmatter, filename timestamp, branch/commit metadata, or operator familiarity is not origin proof. Tracked durable files remain excluded unless an exact reviewed opt-in names the path and hash. | Control document policy classes, legacy provenance classifier, legacy-active preflight contract, and active-selection rules. | Implement class-filtered active selection before timestamp ordering; reject valid-looking ignored or untracked files without accepted external origin proof as `policy-conflict-artifact` with `selection_eligibility=blocked-policy-conflict`. |
| `policy-rule` | `.codex/handoffs/.archive/*.md` previous-primary hidden archives | Previous-primary hidden archives are history-search and explicit archive-load compatibility input, never active-selection input. | Control document path authority, scan modes, and compatibility ledger. | Preserve or explicitly deprecate with compatibility-ledger tests; do not silently drop. |
| `policy-rule` | Source repo `.codex/handoffs/**` runtime files | Runtime files under `.codex/handoffs/` are ignored narrowly in this source repo. | `.gitignore` Gate 0A patch plus `git check-ignore -v .codex/handoffs/example.md`. | Keep `.codex/skills/**` trackable; do not ignore all `.codex/**`. |
| `policy-rule` | Existing `docs/handoffs/**` runtime ignore policy | Existing source-repo ignore behavior for `docs/handoffs/*.md`, `docs/handoffs/archive/`, and `docs/handoffs/.session-state/` is preserved. | `.gitignore` existing rules and positive `git check-ignore -v` checks. | Preserve current operational handoff ignore behavior unless a later explicit tracking-policy decision changes it. |
| `local-preflight-summary` | Canonical-checkout residue inventory | Gate 0r local preflight run `handoff-storage-residue-preflight-20260513T162242Z` saw 107 current `docs/handoffs/**` paths and recorded 6 canonical-checkout local-preflight rows, including delegated legacy-active markdown rows and archive/state directory manifest rows. | Ignored evidence file `.codex/handoffs/.session-state/preflight/handoff-storage-residue-local-preflight.json`; SHA256 `cd10dcb86cb436736785b35c5fac1162d54139252510660b61b4a51b4892f852`. Legacy-active delegated evidence SHA256 `6a6e470c61b568a3836b5547fe38d254e016f08fabc46b0699898bb16ec7d886`. | Treat this as machine-local evidence only. Implementation must keep the ignored evidence files available during Gate 0r verification and must not present local `docs/handoffs/**` residue paths as fresh-clone repo truth. |

## Guardrails

- Do not list ignored or untracked local residue paths as `repo-authority`.
- Do not delete, untrack, or normalize `docs/handoffs/**` artifacts from this ledger.
- Do not treat source-repo `.gitignore` checks as installed-host behavior proof.

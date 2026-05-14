# Handoff Storage Gate 5 Decision

Decision record for Gate 5 of `docs/superpowers/plans/2026-05-13-handoff-storage-reversal.md`.

## Decision

Gate 5 installed-host certification is not in scope for this source-repair closeout.

The publication label remains `source repaired`. The following labels remain explicitly not claimed:

- `refresh-ready but not mutated`
- `installed-harness-source-proof`
- `installed host matrix behavior proved`
- `installed host matrix certified`
- `installed cache certified`

## Basis

Gate 5 requires the guarded-refresh app-server install authority path before any installed-host behavior or installed-cache certification label can be claimed. No real `/Users/jp/.codex` installed-cache mutation was requested, and the default harness path must not mutate the real active plugin cache.

An isolated rehearsal probe was attempted from source-closeout HEAD `b337e0c29641acd4189231a622a8181faccff7ca` with source tree `d80b844b3f4a452a3c5fb13645807eb80685fc9e`.

The current isolated seed path stopped before app-server launch:

```text
seed isolated rehearsal home failed: source seed fixture hash mismatch. Got: 'handoff/1.6.0/skills/load/SKILL.md'
```

A direct isolated `--plan-refresh --inventory-check` against a fresh empty `CODEX_HOME` produced `terminal_plan_status: blocked-preflight` with missing isolated cache roots and config. That is not certification evidence.

Because the app-server-installed isolated root was not produced, no installed-host matrix behavior assertions were run. Source-tree pytest remains valid only for the already-recorded `source-harness-isolation-proof` label.

## Follow-up Required For Stronger Labels

To claim `refresh-ready but not mutated` or any installed-host/cache label later, a separate Gate 5 run must first repair or replace the stale isolated rehearsal seed contract, then install Handoff through guarded-refresh app-server authority into an isolated `CODEX_HOME`.

Only after that installed-root source proof passes may the run execute the Installed Host Repo Policy Matrix:

- no `.codex/` ignore rule
- broad `.codex/` ignore rule
- tracked `.codex/skills/**` with narrow handoff ignore
- tracked handoff-path allocation collision
- tracked primary active source selected for load
- non-git project root

The run must continue to prove helper and skill-doc realpaths outside the source checkout before any behavior assertion counts as installed-host proof.

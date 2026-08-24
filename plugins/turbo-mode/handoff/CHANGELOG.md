# Changelog

All notable changes to the Handoff plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/). This changelog begins at 3.2.1; earlier versions predate the file and are not reconstructed here.

## 3.3.0 - 2026-08-23

### Changed

- Project-root resolution (all four skills, README, and the repo-side consistency canary, in lockstep): inside a git repository the root is now the repository's main working tree — the first path listed by `git worktree list` — instead of `git rev-parse --show-toplevel`, so all linked worktrees of one repository share one handoff pile. Previously a session in a linked worktree got its own invisible pile: `/load` and `/search` falsely reported no handoffs while the main checkout held the full pile, and a `/save` in a disposable worktree was silently deleted by `git worktree remove` when the pile was gitignored (loss path empirically confirmed during the 2026-08-23 gap review). Bare-repository worktree setups, which have no main checkout, keep the old per-worktree behavior via an explicit fallback. Behavior change, hence the minor bump.
- `search-handoffs`: both `rg` templates now pass the query as `-e '<query>'` in single quotes, with an escaping rule for embedded single quotes. The old double-quoted bare-positional form errored on queries starting with `-` (parsed as a flag) and shell-expanded `$` inside queries, producing silent false negatives; both failures were reproduced during the gap review.
- `throughline`: a drift-triggered rebuild whose source count went down must now report the count delta with a dedicated `Drift:` reply line instead of silently rebuilding — a vanished source's condensed history is dropped from the rebuilt document, and that cost is now surfaced at the moment it is incurred.
- `load-handoff`: implicit selection now specifies parsed-timestamp ordering (never raw string order), a `YYYY-MM-DD_*` candidate-shape filter, and a tie-break preferring the highest `-2`/`-3` collision suffix, closing the gap between the claimed "deterministic selection" and the underdetermined ordering; when the branch-matched pick is not the newest handoff overall, the newer non-matching handoff must be named in the reality check.
- `save-handoff`: trigger example `wrap this up` reworded to `wrap up this session` so the example no longer collides with the description's own final-closeout exclusion in standalone installs.

### Added

- Documented the manual archiving convention consumed by `throughline` and `load-handoff` but previously stated nowhere: old handoffs may be moved by hand into `<handoffs-dir>/archive/` (flat, one named level), staying searchable, throughline-visible, and explicitly loadable; archive rather than delete, because deleting a source drops its condensed history from the next throughline rebuild. New Archiving section in `references/handoff-format.md`, plus pointer sentences in README Storage and `save-handoff`.

### Fixed

- Reader enumerations for the legacy `.claude/handoffs/` and `.codex/handoffs/` directories (README Storage, `save-handoff` Boundaries) now name `throughline` as the third reader; the old text predated throughline and implied the legacy directories could be dropped without affecting its source set.
- README write-procedure step 3 no longer overstates the write guarantee: it now carries the skill's conditional form (exclusive-create when the runtime offers one, otherwise a pre-write existence check).
- Dual-runtime invocation tokens at user-facing suggestion sites: `/throughline`, `/save`, and `/load <path>` suggestions and the bounded-batch reply template now name the `$` form alongside the `/` form, and the README skill table lists both, so Codex sessions are no longer told to run Claude-only tokens.

## 3.2.2 - 2026-08-23

### Changed

- `throughline`: raised the size budget from ~32KB (~8k tokens) to ~64KB (~16k tokens), on both budget surfaces (`SKILL.md` Synthesis and `references/throughline-format.md` Size). The 32KB cap — introduced in 3.2.0 after the live throughline hit 98KB — was under active pressure (this repo's throughline sat at 31.5KB with 232 handoffs folded, forcing history compression on every refresh), and the 2026-07-03 methodology critique recorded that no measured failure anchored 32 specifically. 64KB doubles headroom while staying well below the 98KB size that motivated the original cap; load-handoff's full-read-per-session cost rises to ~16k tokens, judged acceptable. Compression rules and oldest-first order are unchanged.

## 3.2.1 - 2026-07-09

### Added

- `save-handoff`: added a secret-redaction discipline to `## What To Capture` — never transcribe API keys, passwords, tokens, connection strings, or personally identifiable information into a handoff; reference them by name or location instead. Handoffs are written to `.agents/handoffs/` and may be committed under host-repository policy, so a secret written into one can leak. Folded from mattpocock upstream (charter case-(d)) and routed through `agent-facing-design` (verdict: context-with-safe-default, not machinery — justified by the credential-exposure damage class, single-sourced to the writing skill, deliberately absent from `load-handoff` which never writes). Behavior forward-tested (Sonnet 5, secrets embedded in the session context, redaction never instructed): zero secrets transcribed verbatim, all non-secret facts preserved.

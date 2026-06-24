# Changelog

All notable changes to the Git Cycle plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 1.2.0 - 2026-06-23

### Added

- `release-cut`: new skill that cuts a release for one versioned unit. It derives the next semver from the **real landed change class** — reading the diff for an under-tagged breaking change rather than trusting `feat:`/`fix:` commit labels — bumps the authoritative manifest (`plugin.json` / `package.json` / `pyproject.toml` / `Cargo.toml`, **never a git tag**), and writes a dated Keep-a-Changelog section keyed to the same version in lockstep. It **stages** the bump and stops: the commit that lands the work carries it, and the outward publish train (cache republish, mirror, push) is named but fired only on explicit authority. Fills the SHIP-lane gap `pr-description` deliberately carved out (version/changelog/release notes route here). Mixed skill — the change-class call is the judgment; the manifest↔CHANGELOG lockstep, presence-ordered manifest resolution, and multi-unit guard are mechanical, reported read-only by the bundled `release-cut-facts.sh` (the script reports facts; the agent decides).

## 1.1.0 - 2026-06-20

### Added

- `pr-description`: new skill authoring a reviewer-oriented PR title and body from the branch diff, the governing intent (ticket/plan/spec), and the **real** verification record (`closeout-check`'s Verification Run / Proof Boundary, or actual command output), opening or updating the PR only on explicit authority. Fills the family's SHIP-lane gap — nothing previously authored a PR body or opened a PR (`gh-pr-review-loop` responds to an *existing* PR; `merge-branch` is the no-PR path). The "how-verified" content is sourced from the real record, never fabricated. Default stops at the draft; publishing via `gh pr create`/`gh pr edit` is gated behind explicit authorization, matching the family's address-locally vs publish split.

## 1.0.1 - 2026-06-17

### Changed

- `closeout-check`: genericized the Proof Boundary proof-discipline sentence — dropped the `.agents`-specific "local skills in `skills/`" framing so the rule reads portably in any repo where this skill runs. No behavior added; the proof-class distinction is unchanged (refs #13).
- `git-hygiene`: the config reference now documents `branchProtection`'s commit-gating use (the repo-defined protected set that blocks commits onto a protected or default branch), not only deletion-protection. Doc-alignment only; runtime was already safety-strengthening (refs #16).

## 1.0.0 - 2026-06-17

### Added

- Initial packaging of six in-production git-lifecycle skills (`git-hygiene`, `closeout-check`, `merge-branch`, `exiting-worktrees`, `gh-address-comments`, `gh-pr-review-loop`) as one coherent dual-runtime plugin. Version 1.0.0 reflects established skills, not new ones; the only behavior changes shipped separately ahead of packaging were the git-hygiene protected-resolution convergence and revert marker (issues #9/#10) and the `exiting-worktrees` native-git dual-runtime port. No shared reference file: safety conventions stay inline in each skill, drift-guarded by `scripts/check-protected-set.sh`.

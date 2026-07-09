# Changelog

All notable changes to the Git Cycle plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 1.4.0 - 2026-07-09

### Added

- `resolve-conflicts`: new skill owning the faithful resolution of an in-progress merge/rebase/cherry-pick/revert conflict and finishing the operation — a lane no sibling held (`merge-branch` is fast-forward-only and stops the moment a conflict appears, `exiting-worktrees` refuses to resolve conflicts inside a worktree, `git-hygiene` aborts on any in-progress operation, `keep-green` covers lint/test-green after a change with no conflict surface). Admitted as third-party material (mattpocock upstream) re-authored through the house transform (charter case-(d)): it reconstructs each side's intent before resolving — preventing a mechanically-resolved conflict that compiles yet silently drops one side's behavior or invents a third — keeps the protected-branch floor in the finish step, and treats `--abort` as a deliberate abandon rather than a blanket never-rule. Reciprocal routing edges added into `merge-branch` and `exiting-worktrees`; the new file joins the `check-protected-set.sh` drift canary. Behavior forward-tested (Sonnet 5) against a constructed real conflict where the discriminating rule (a loyalty discount) was protected only by its commit message: both sides' intent preserved, nothing invented, finished as a clean merge commit.

## 1.3.0 - 2026-06-25

### Added

- `closeout-check`: its change-caused repair step (Blocking Failures) now delegates a multi-failure fix→re-run loop to the new `keep-green` skill, which carries bounded anti-thrash stop conditions (retry cap, same-failure and oscillation detection, escalation of cause-unknown failures to `diagnose`) that closeout-check's previously-unbounded repair loop lacked. closeout-check still owns the done-verdict and the single final commit; `keep-green` makes neither, so the work-product boundary is unchanged. `keep-green` is a new dual-runtime skill in `skills/` (not part of this plugin); this entry records only the closeout-check delegation pointer.

## 1.2.2 - 2026-06-25

### Fixed

- `merge-branch`: Step 2 now checks whether the target/base branch is behind its existing upstream before landing, closing a gap where the skill stacked the source's commits onto a stale base (local `<target>` then silently diverges from its remote, surfacing later as a non-fast-forward push). A context-free cross-model evaluation found the skill's "do not fetch" posture suppressed the base-freshness check a bare model performs (10/10 stale-base landings with the skill loaded vs 0/10 without). The fix is one read-only command — `git rev-list --count <target>..<target>@{u}` — that reads the on-disk remote-tracking ref only: it runs no `git fetch` and changes no refs, so the deliberate remote-free, no-push contract (and the existing lines forbidding fetch) is preserved unchanged. A behind-count stops for the user's decision (never auto-fetch/pull/update); no upstream or an absent tracking ref is a one-line skip, not a stop. Known limit, disclosed in-skill: the count reflects the last fetch, so it catches a base known to be behind an already-fetched ref, not one that has moved on the remote since — closing that fully would require the network fetch this contract forbids.

## 1.2.1 - 2026-06-24

### Changed

- `release-cut`: the change-class step now asks **two** ordered forcing questions instead of one. The original question guards only the major boundary (an under-tagged breaking change hidden by a `fix:` label); a second question now guards the minor↔patch boundary — "does this let a user do something they could not do before, or does it only document/normalize/fix an existing capability?" — defaulting docs-of-existing-behavior edits to patch. Closes a gap where changes that *look* additive (e.g. adding already-supported invocation tokens to a description) were over-bumped to minor. Validated before/after on five real plugin releases (×{Opus,Haiku}×3 trials): the targeted over-bump case rose from 67%→100% correct and an ambiguous additive-prose case from 17%→100%, while two genuine-new-skill guard cases held at 100% (no over-correction).

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

# Changelog

All notable changes to the Git Cycle plugin are documented in this file.

Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

## 1.5.4 - 2026-07-17

### Fixed

- README skill inventory reconciled with the live plugin: the arc list said "Seven skills" and omitted `resolve-conflicts`, `worktree-task-cycle`, and `release-cut`; it now says ten and describes all of them. Docs-only — no skill body changed. Drift surfaced by a sealed-probe finding in the 2026-07-17 cross-model methodology adjudication and host-verified against the frozen corpus before repair.

## 1.5.3 - 2026-07-17

### Fixed

- `worktree-task-cycle` helper: lease-root symlink fail-open (JP's 2026-07-17 second Gate-B readiness review; pinned by regression tests proven red against the extracted 1.5.2 helper before the fix). `discover`'s 1.5.2 store-integrity gate proved `skill-worktree/` and `skill-worktree/validations/` are real non-symlink directories but never `skill-worktree/leases/`; its later `leases.is_dir()` followed a planted symlink, so a live symlink at the lease root let a normal `lease-acquire` create the lease directory and `owner.json` outside the git state store while printing `RESULT: ok` (exit 0), and a dangling lease-root symlink refused with the untruthful classification "no skill-worktree store". `topo.leases` now joins the same `discover`-time non-symlink invariant, closing the owned state chain: every state-root component — `skill-worktree/`, `leases/`, and `validations/` — must be a real directory under the resolved git common dir, enforced before any mutation on every verb, with the planted symlink preserved as evidence and the outside target left unchanged (live) or uncreated (dangling); the refusal message now names lease and record state. Two regression pins (live + dangling) assert the gate's own phrases rather than a bare "symlink" substring — pytest embeds the test name in the store path it prints, so a substring assert would self-satisfy; the guard-excision mutant is killed by both pins, and the ordinary real-lease-root control is the existing acquire/release test. Lease acquisition/release logic, record handling, and state routing are byte-untouched: the diff touches only the shared `discover` invariant.

## 1.5.2 - 2026-07-17

### Fixed

- `worktree-task-cycle` helper: validation-record symlink fail-open (JP's 2026-07-17 Gate-B readiness review; each defect pinned by a regression test proven red against the extracted 1.5.1 helper before the fix):
  - a symlink at a validation-record path — dangling or live — now classifies as `symlink` (lstat-based, never followed) and every consumer fails closed: `record-validation` refuses before mutation with the symlink and its target preserved as evidence (1.5.1 classified a dangling symlink as absent and wrote the record through it, creating a file outside the validation store while printing `RESULT: ok`; a live symlink to a valid same-branch record was superseded through the link, rewriting the aliased outside target); `land` refuses (`READY-INVALID`) instead of authorizing an integration off an aliased record; `delete-branch` refuses before the branch mutation, leaving branch, link, and target untouched for user adjudication.
  - `record-validation`'s existing-record dispatch is restructured default-deny: only a readable matching record (supersede) or true absence proceeds to the write; any other status refuses with the status named truthfully.
  - the record write opens with `O_NOFOLLOW`, enforcing the no-symlink rule at the write itself rather than only at the pre-check. Deliberate side effect: any `open()` failure at the record path (not only a raced-in link) now refuses with the reason labeled (exit 2) instead of tracebacking (exit 1); nothing is written on any failure path.
  - a hardlinked record (link count > 1) refuses before the write: the `O_TRUNC` supersede would rewrite the shared inode's bytes reachable outside the store, and `O_NOFOLLOW` cannot detect hardlinks. Read paths deliberately still classify a hardlinked record `ok` — shared-inode bytes are genuine store content, so a read cannot be aliased into lying; disclosed as a ridden design question.
  - a non-regular file (FIFO, socket, directory) at a record path classifies `unreadable` and refuses instead of blocking at open — 1.5.1 hung indefinitely on a planted FIFO, worst under `land` where the hang held the integration lease.
  - `discover` proves the store chain — `skill-worktree/` and `skill-worktree/validations/` — is real, non-symlink directories under the resolved git common dir before any verb proceeds (previously a symlinked validations root or store parent aliased every record path outside the store). Lease machinery is otherwise byte-untouched; the leases directory's own symlink handling is a disclosed open item.

## 1.5.1 - 2026-07-17

### Fixed

- `worktree-task-cycle` helper repairs from the 2026-07-17 execution-fidelity review (four contract violations plus one recovery-routing defect; each pinned by a regression test proven red against the 1.5.0 helper before the fix):
  - `land` can no longer report `RESULT: ok` while the integration lease remains: a cleanup failure — or a lease dir still present after cleanup — exits nonzero with the landed-but-unreleased state labeled (the ff-only merge that already completed is reported truthfully, never re-claimed as clean success).
  - `record-validation` refuses an unreadable existing record (exit 2) instead of overwriting it; the unreadable bytes are preserved as adjudication evidence.
  - `inspect` now enforces the `--base` pin the skill body already promised: a `--base` that does not match the primary checkout's live branch refuses instead of classifying satellite state (previously the same parked satellite read `PARKED` with the correct base and `PARKED-ORPHAN` with a wrong one, both exit 0).
  - `land`'s integration-lease SELF re-entry requires the full scope match — satellite, branch, **and purpose**; a same-session lease with a different purpose refuses as DIFFERENT scope instead of admitting the merge.
  - `inspect` maps an active task branch under a foreign or unverifiable lease to `STATE: LEASE-ORPHANED` (owner adjudication first), placed ahead of the containment split: it covers both the uncontained case (previously `COMMITTED-UNLANDED`, whose recovery route began with a lease-acquire guaranteed to refuse) and the contained crash-between-land-and-park case (previously `LANDED-UNPARKED`/`CONTAINED-UNPARKED`, whose park route was equally guaranteed to refuse).

## 1.5.0 - 2026-07-17

### Added

- `worktree-task-cycle`: durable owner of the persistent-satellite task lifecycle (per `docs/specs/2026-07-16-skill-worktree-system.md` in the source repo) — activate a fresh task branch from the verified integration branch in a parked, locked satellite worktree; bind validation to the exact tip SHA; land fast-forward through the primary checkout; re-park with proofs; classify interrupted states from git facts. All guard machinery is single-sourced in the skill's `scripts/worktree_cycle.py` (stdlib-only Python): guarded verbs `inspect`, `lease-acquire`, `lease-release`, `activate`, `record-validation`, `land`, `park`, `delete-branch`; session-scoped cooperative leases with staged-atomic acquisition; ff-only merge of the validated SHA; fail-closed labeled output; destructive recovery is never auto-chosen.

### Changed

- `merge-branch`: routing boundary added — a source branch cut in a persistent, locked satellite worktree belongs to `worktree-task-cycle` where available (new Do-Not-Use bullet plus one sentence at the step-2 target-checked-out-elsewhere stop).
- `exiting-worktrees`: routing boundary plus protective floor — a `locked` worktree with a parked-skill-workspace reason is never removed through this skill; description Do-not-use extended and a Pre-Exit Checklist step-1 stop added.
- Plugin manifest description, longDescription, and defaultPrompt name the new satellite-lifecycle capability.

## 1.4.2 - 2026-07-13

### Changed

- Conciseness campaign (2026-07-13 audit dispositions), obligation-preserving refactor. `exiting-worktrees`: each twice-stated edge case single-homed (no-op tool contract in Scope, native commands in the baseline section, branch survival at Exit Procedure step 3, one CWD rationale statement); Edge Cases table pruned 9 → 4 rows with an ownership note, every deleted row's command surviving at its named owning step (2,274 → 2,105 body words; no reference offload — duplication, not payload, was the driver). `gh-address-comments`: the never-push/resolve/re-review invariant single-homed in Boundaries with binding-site pointers. `pr-description` and `release-cut`: Boundaries compressed to one redirect line per sibling; `release-cut` keeps the cutting-is-not-deciding-readiness authority line. No trigger or protected-set changes; frontmatter untouched; `check-protected-set.sh` green. Publish deferred until explicitly authorized; the Codex cache stays at 1.4.1 (`--check` NOT-INSTALLED remains the expected state).

## 1.4.1 - 2026-07-12

### Removed

- `exiting-worktrees`: removed the "Why This Skill Exists" rationale section from the skill body; the Pre-Exit Checklist carries the same obligations operationally. No behavior change.

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

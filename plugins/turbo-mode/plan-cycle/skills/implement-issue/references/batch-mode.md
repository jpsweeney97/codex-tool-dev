# Batch Mode

Several independent ready issues at once: one subagent per issue, each in its own isolated worktree on its own working branch cut from the integration branch's verified tip, each running the single-issue contract in `SKILL.md` and stopping at one commit. The coordinator runs from the attended top-level session only — never from a subagent, hook, or scheduled context. There is no numeric cap; the independence test below is the limit. If that test leaves one issue, there is no batch: work it under `SKILL.md` as a single issue and name the rest. A batch holds issues only: a reference that resolves to a pull request is named as a separate single-issue invocation under Pull Request Mode.

Repo instructions about where work happens and how it lands govern this file. When they require a particular worktree lifecycle for the files in scope, there is no batch: name the instruction and work one issue as `SKILL.md` says. When they route landing through pull requests, the batch runs Landing step 1 only and then hands each branch to the repo's PR lane; the closeout question then drops the push and the issue closures (the PR lane owns them) and keeps the cleanup and the findings.

## Independence, tested before dispatch

Run the same test `execute-plan` applies to concurrent tasks — neither depends on the other and they change no file in common — across every pair in the candidate set, with one relaxation for shared files. The relaxation exists because each implementer has its own worktree: a shared file risks a conflict at landing, not interference while the implementers run.

- Dependencies: every candidate's blockers are closed (Verify It Is Workable), and no candidate's body relies on a change another candidate makes.
- Files: for each issue, list the files it names, the files that define the symbols it names (grep for them), and the files the repo's conventions make every change touch (a changelog, a manifest version, a lockfile, an index or registry). Two candidates with no file in common are independent. When two share a file in regions that do not overlap, put both implementers' placements (the section or anchor each change goes in) in both briefs. When the regions overlap or cannot be told apart, serialize that pair: the newer issue waits for a later invocation.

Name the batch with each issue's predicted files and any placement you pinned, and the candidates left out with the reason for each (blocked, serialized, prior work without a resume decision, pull request, ready-for-human).

## Dispatch

Before recording anything, confirm the integration branch the way `merge-branch` does where it is available: the branch the user named, else the repo's instructions, else the remote default, else a single obvious local default branch; if more than one candidate remains, ask. It exists locally, the primary checkout has it checked out (`git branch --show-current` prints it) and is clean, and it is not behind its upstream (`git rev-list --count <integration>..<integration>@{u}` reads 0; if the command errors because the branch has no upstream, skip this check, as `merge-branch` does; if it reads more than 0, stop and report — do not fetch or pull). Then record its tip: every brief cuts from that commit, and it is the reset point Landing step 4 offers the user if the combined proving run fails.

One subagent per issue, each in an isolated worktree. Implementers inherit the session model unless the user names one for the batch; do not hard-code a model. Because each implementer has its own worktree, it cannot change another's files, so `execute-plan`'s one-at-a-time build rule for a shared tree does not apply.

Each brief is self-contained — the implementer starts with no context — and carries:

- the instruction to run this skill on exactly that one reference (`/implement-issue` or `$implement-issue`; `plan-cycle:implement-issue` where plugin skills are namespaced), so its Verify, Implement, and Prove rules govern the work;
- the issue reference to fetch, and the repo's instruction file and proving command;
- the working branch to create and the commit to cut it from, as `git checkout -b <branch> <integration-tip-sha>` inside the worktree. The isolation tooling may start the worktree from the remote default branch rather than your integration branch, so the implementer never branches from the worktree's starting HEAD;
- the identifier scan's conclusion for this issue, stated so no question remains ("no prior work; the only match is triage annotation `<sha>`"); when the scan found prior work beyond a triage annotation, the user's resume-or-fresh decision, asked before dispatch. A candidate with prior work and no decision stays out of the batch;
- any placement pinned for a shared file, for this issue and for the sibling that shares the file;
- the commit trailer the repo expects, stated as a shape the implementer completes with its own model name where the trailer names one;
- the rule for a proving command that uses a resource outside the tree (a fixed port, a local database, a container): ask you before running it, as `execute-plan` requires;
- the stop rule: one commit when the work is done, with nothing else left modified or untracked in the worktree, or no commit and the reason when it stops early; no merge, rebase, push, pull request, or tracker mutation; report and stop;
- the report shape: the status word (`DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, or `BLOCKED`, as `execute-plan` defines them); branch and commit; worktree path; per-criterion evidence (the command and its output, or `not verified` with the reason); the proving command's exact output tail; each deviation from the issue body with its reason; out-of-scope findings, one sentence each with a path, or `none`.

An implementer that ends without its commit has reported why. When the issue, its brief, or the live tree settles its question, answer it: continue the same implementer with the answer where the runtime lets you message a finished subagent (its worktree and any uncommitted edits stay in place); otherwise dispatch a new implementer whose brief names the existing branch and worktree as the resume target and restates the scan conclusion. Never re-dispatch unchanged. A question they do not settle — missing scope, a resume decision, a protected branch — goes to the user: that issue leaves this batch, and its route-back proposal, including what to do with its worktree, branch, and any uncommitted edits, joins the closeout question.

## Landing

Local landing is the coordinator's and does not wait for the closeout answer. If any check below fails for a branch, exclude that branch and report it; if a check on the integration branch or the primary checkout fails, stop and land nothing further.

1. For each branch: confirm it descends from the recorded tip (`git merge-base --is-ancestor <recorded-tip> <branch>`; a failure means it was cut from the wrong base) and that its worktree is clean (`git -C <worktree> status --porcelain` prints nothing). Read its diff against the integration branch (`git diff <integration>...<branch>`, three dots) and check the implementer's factual claims — especially its deviations — against the live tree.
2. Re-run the integration-branch checks from Dispatch: checked out in the primary, clean, not behind its upstream.
3. Land branches that touch nothing shared first. For each branch: rebase it onto the integration branch inside its own worktree (`git -C <worktree> rebase <integration>`), because a branch checked out in a worktree cannot be rebased from the primary checkout, which is also why `merge-branch`'s fast path excludes it; on a conflict, run `resolve-conflicts` where available with every one of its commands executed in that worktree (working directory set to it, or `git -C <worktree>` throughout), never from the primary checkout. After the rebase, confirm the branch is strictly ahead (`git rev-list --count <integration>..<branch>` is greater than 0 and not lower than before the rebase; a drop means the rebase skipped a commit already on the integration branch, and `ff-only` would report success while landing nothing). Then `git merge --ff-only <branch>` from the primary checkout, and confirm the branch is now contained in the integration branch.
4. Run the proving command once on the combined tip and read its output. If it fails, stop and do not go on to the closeout question; reset nothing yourself. Find the commit that broke it by running the proving command at the recorded tip and then at each landed commit in order, each built fresh from `git archive <sha>` into a scratch folder (the first bullet of `execute-plan`'s Checks For Particular Cases), never in a worktree that may hold stale build products. Report the failing output, that commit, and the recorded pre-batch tip, which the user may choose to reset to instead of keeping the rest.

## Closeout

Collect every implementer's out-of-scope findings into one list. Then ask once, as one batched question covering all of the following, and do nothing outward before the answer:

- push the integration branch, listing every commit it would send and marking the ones that predate the batch: `git log <integration>@{u}..<integration>`; when the branch has no upstream but a remote exists, name the remote branch it would go to and list `git log <integration> --not --remotes=<remote>`; when the repo has no remote, leave push out of the question and say why. Say that any fix-now commits approved in the same answer are pushed with these;
- close each issue with the comment shown in full: its landed commit, its per-criterion evidence summary, and each deviation from the issue body with its reason;
- remove the landed implementers' worktrees with `git worktree remove <path>`, never `--force` (`exiting-worktrees` where available; on a refusal, list the files and keep that worktree), and delete the branches the isolation tooling created for them with `git branch -d`, never `-D`, once every landed branch is contained in the integration branch (the per-issue working branches follow the repo's own hygiene practice, `git-hygiene` where available);
- for the collected findings, one of: file them through `triage`, or fix them now, each as its own commit on a working branch, proven by the proving command and landed the same way;
- the route-back proposal for each issue that left the batch.

Once answered, carry out only the items the user approved, in this order: fix-now findings first (implement, prove, land); then the push, listing in the report the fix-now commits it carried; then the issue closures; then the worktree and branch removals; then the route-back proposals.

Report per issue: reference, branch, landed commit, per-criterion evidence as the implementer reported it with each claim you rechecked marked, deviations; then the combined proving output tail and the findings list with their routing.

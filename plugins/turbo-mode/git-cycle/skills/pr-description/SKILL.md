---
name: pr-description
description: "Use when drafting a pull-request title and body — synthesizing the branch diff, the governing intent (ticket, plan, or spec), and the real verification record into a reviewer-oriented description, then opening or updating the PR only on explicit authority. Do not use to respond to existing review comments (`gh-address-comments`/`gh-pr-review-loop`), land a branch without a PR (`merge-branch`), judge whether work is done (`closeout-check`), or author a tracker issue or PRD (`to-issues`/`to-prd` when available)."
---

# PR Description

Author the title and body of a pull request from what the change **actually** is: the diff, the intent behind it, and the real record of how it was verified. The draft is the deliverable; opening or updating the PR is a separate step you take only when explicitly authorized.

**The judgment is the skill — and its sharpest edge is not inventing.** A reviewer reads the body to decide what to look at and what to trust. The failure that matters is a body that reads well but claims something the change did not do: a "how verified" section listing checks no one ran, a "why" reverse-engineered from the code instead of the real motivation. Anchor every line to evidence you can point at; where you cannot, say so — do not fill it in.

## 1. Gather the real evidence — supplied or found, never invented

Three sources, each grounded:

- **The diff** — what actually changed. Read it (`git diff <base>...<head>`, the commit range, or the supplied patch), not just the commit subjects. Commit messages hint at intent; they do not substitute for reading what the code does.
- **The governing intent** — why the change exists: the ticket, plan, spec, design doc, issue, or the user's stated goal. Take it as supplied, or find it (linked issue, branch name, handoff). If the only "why" available is the diff itself, say the intent is unstated rather than reverse-engineering a rationale that sounds right.
- **The verification record** — how it was actually checked. Source this from the real record: `closeout-check`'s Verification Run and Proof Boundary, the actual command output you ran or were given, CI results. If nothing was verified, the body says so — testing pending, or the section omitted. Never write a plausible "how tested" you cannot back.

## 2. Draft the body — reviewer-oriented, every claim traceable

Write for the reviewer's decision: what changed, why, what to look at first, what is risky, how to tell it works. A useful default shape — adapt it to the change, do not fill it in to feel complete:

- **Summary** — what this PR does, in one or two lines a reviewer can act on.
- **What changed** — the substantive changes, grouped by concern and keyed to the diff. Skip the mechanical noise.
- **Why** — the governing intent. Link the ticket or spec rather than restating it.
- **How verified** — only checks that were actually run, sourced from the real record (`closeout-check`'s Verification Run, command output, CI). If nothing was verified, say testing is pending or omit the section — never a plausible how-tested you cannot back.
- **Risk / review focus** — what a reviewer should scrutinize, what could break, what is explicitly out of scope.

The shape is yours; the honesty is not. The sharp test for every line: **can I point to where this comes from — the diff, the intent, or the verification record?** If not, it does not go in the body. A short, true body beats a thorough, partly-fabricated one.

## 3. Publish only on explicit authority

Default: produce the draft and stop. The user copies it, edits it, or tells you to open the PR. Drafting is not publishing.

Create or update the PR — `gh pr create --body`, `gh pr edit --body`, or the GitHub app — **only when the user explicitly authorizes opening or updating the PR.** A PR is outward-facing: it notifies reviewers, may trigger CI, and is visible immediately.

When authorized to open or update:

- Confirm the head branch is pushed and is the intended PR head; confirm the base branch — do not assume `main`, read `origin/HEAD` or ask.
- Use the drafted title and body verbatim unless the user revises them.
- Do not also push branch commits, resolve threads, or request review — those belong to the landing and review-response lanes.

## Boundaries

In scope: authoring a PR title and body from the diff, the intent, and the real verification record; opening or updating the PR on explicit authority.

Out of scope — route instead:

- responding to **existing** review comments on an open PR → `gh-address-comments` (local, no publish) or `gh-pr-review-loop` (`/gh-pr-review-loop` or `$gh-pr-review-loop`, the full publish lifecycle).
- landing a branch **without** a PR → `merge-branch`.
- deciding whether the work is **done** and committing it → `closeout-check`, whose verification record this skill consumes.
- deriving a version bump, changelog, or release notes → `release-cut`.
- authoring a tracker issue or PRD → `to-issues` / `to-prd` when available.
- reviewing a completed change against its spec → `review-family:implementation-review` when available.

The branch, commit, and push lifecycle stays with the normal git discipline; publish nothing beyond the authorized PR open or update unless explicitly asked.

## Output

Deliver the draft, then stop unless publishing was authorized:

1. **Title** — one line.
2. **Body** — the reviewer-oriented description.
3. **Sourcing note** — what the body is grounded in (diff range, intent source, verification record) and what it could **not** source (intent unstated, verification incomplete) — the same honesty the body carries.
4. **PR action** — `drafted (not published)` by default; the created or updated PR URL only when opening or updating was explicitly authorized.

---
name: pr-description
description: "Use when drafting a pull-request title and body — synthesizing the branch diff, the governing intent (ticket, plan, or spec), and the real verification record into a reviewer-oriented description, then opening or updating the PR only on explicit authority. Do not use to respond to existing review comments (`gh-address-comments`/`gh-pr-review-loop`), land a branch without a PR (`merge-branch`), judge whether work is done (`closeout-check`), or author a tracker issue or PRD (`to-issues`/`to-prd` when available)."
---

# PR Description

Draft a pull-request title and body from the branch diff, the stated intent behind the change, and the checks that actually ran.

- **Draft and stop.** The draft is the deliverable. The user copies it, edits it, or tells you to open the PR.
- **Open or update the PR only when the user explicitly authorizes it** (`gh pr create --body`, `gh pr edit --body`, or the GitHub app). A PR notifies reviewers, may start CI, and is visible at once. When authorized, use the drafted title and body verbatim unless the user revises them, and do not also push branch commits, resolve threads, or request review.
- **Never assume `main` as the base.** Confirm the head branch is pushed and is the intended PR head, then read the base from `origin/HEAD` or ask.

Close with the PR action: `drafted (not published)`, or the PR URL when opening or updating was authorized.

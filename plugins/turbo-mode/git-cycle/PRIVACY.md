# Git Cycle Plugin Privacy Notice

This document describes the Git Cycle plugin source package in this
repository. It does not certify what any installed Codex runtime or plugin cache
currently loads.

The Git Cycle plugin provides git-lifecycle instructions (local hygiene,
closeout, branch landing, worktree exit, and GitHub pull-request review
response). It does not create background files, maintain persistent plugin
storage, register hooks, run services, or intentionally transmit repository
content to a separate service.

Git Cycle requests may cause the runtime to inspect local repository files, git
state, branch and worktree layout, GitHub pull-request context, pasted text, or
other artifacts the user asks it to act on. Outputs may include file paths,
quoted snippets, diff and commit summaries, branch names, recommended repairs,
and next-step notes.

Codex, Claude, account handling, model requests, telemetry, synchronization,
GitHub access, and any host application behavior are governed outside this local
plugin document.

Review changes and findings before sharing, committing, or publishing them,
especially when they may include private project details, file paths, customer
data, credentials, or other sensitive information.

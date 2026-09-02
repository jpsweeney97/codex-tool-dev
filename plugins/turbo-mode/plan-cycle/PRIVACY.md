# Plan Cycle Plugin Privacy Notice

This document describes the Plan Cycle plugin source package in this repository. It does not certify what any installed Codex runtime or plugin cache currently loads.

The Plan Cycle plugin provides instructions for taking a settled spec through to executed work: publishing PRDs and implementation issues to the project issue tracker (`to-prd`, `to-issues`), mapping acceptance checks (`acceptance-map`), writing and executing implementation plans (`implementation-planning`, `execute-plan`, `plan-queue`), working and triaging tracker issues (`implement-issue`, `triage`), and reconciling artifacts after intent changes (`spec-drift-reconcile`). It does not create background files, register hooks, run services, or intentionally transmit content to a separate service by itself.

Plan Cycle requests may cause the runtime to read local repository files, git state, conversation context, and issue-tracker content, and to write the artifacts each skill documents: PRDs, issues, labels, comments, sub-issue and dependency links, and closures in the configured issue tracker; local Markdown acceptance maps and plan files; `PLAN-*.md` queue files at the repository root; `.out-of-scope/` records for rejected requests; and code changes on a working branch with local commits and, for an authorized queue plan, a local fast-forward merge. Content posted to the issue tracker leaves this machine and is visible to whoever can read that tracker. It carries whatever the conversation and repository supplied, so it may include file paths, quoted snippets, diffs, findings, and decisions.

Codex, Claude, account handling, model requests, telemetry, synchronization, and any host application behavior are governed outside this local plugin document.

Review a PRD, issue, comment, or plan before approving its publication, especially when it may include private project details, file paths, customer data, credentials, or other sensitive information.

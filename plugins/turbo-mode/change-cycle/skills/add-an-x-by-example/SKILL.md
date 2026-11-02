---
name: add-an-x-by-example
description: "Use when the task is to add another instance of a category this repo already has — an endpoint, CLI command, event type, migration, error code, config key — and sibling instances exist in git history. Derives the empirical touchpoint checklist from the commits that added the last few siblings, then closes with a mandatory completeness diff of your change against it. Do not use when the category has no existing siblings, to surface what habitually co-changes with an existing file under edit (`co-change-radar`), to map acceptance checks from a settled spec (`acceptance-map`), or for whole-repo orientation (`explain-codebase`)."
---

# Add An X By Example

The repo already defines what adding an X requires — empirically, in the commits that added the last few Xs. Reading sibling *files* cannot reveal the registration constellation — the barrel export, the docs table, the i18n entry, the test-helper enum — because a file shows what it is, not what had to change around it when it arrived. The union of files the siblings' *add-commits* touched shows exactly that, including the sites neither grep nor compile errors surface. This converts the compiles-but-never-registered failure into a pre-implementation check.

Invocation: `/add-an-x-by-example` or `$add-an-x-by-example`; also fires when the task is adding another instance of a category with existing instances — an endpoint, CLI command, event type, migration, error code, config key, skill.

## Derive the checklist

1. Locate one to three sibling files — the most recent instances of the category, preferring ones that arrived as focused changes.
2. Find each sibling's add-commit: `git log --diff-filter=A --format='%H %s' -- <sibling-path>` (add `--follow` if the file may have been renamed since).
3. `git show --name-status <sha>` for each add-commit.
4. The derived checklist is the union of files touched across 2–3 add-commits, pruned of obvious drive-by noise (lockfile churn, unrelated fixes riding along). A file touched by two or more siblings is a strong touchpoint; a single-sibling file is a candidate — keep it, marked as such, rather than silently dropping it.
5. Show the checklist before implementing: each path, which siblings touched it, and — where non-obvious — what the touch was for (`docs/commands.md — each sibling added a row to the command table`).

When the history cannot answer — the siblings arrived in one squashed 500-file import, the clone is shallow, the category is too young for a focused add-commit — say so, fall back to reading the sibling files, and mark the checklist as derived from that weaker basis. Never slide silently from "history is noisy" to "no checklist".

## Implement against it

Ordinary implementation with the checklist in hand. The checklist is a completeness surface, not a plan: it says which files the operation touches, not in what order or how.

## Close with the completeness diff — mandatory

At the end, diff your change's file list (`git diff --name-only` plus untracked additions) against the derived checklist, and account for every mismatch in one line each:

```text
Checklist derived from 3 add-commits (abc1234, def5678, 0112358):
  src/commands/<x>.ts    — 3/3 siblings — touched
  src/commands/index.ts  — 3/3 siblings — touched
  docs/commands.md       — 3/3 siblings — GAP: each sibling added a row; adding it now
  i18n/en.json           — 2/3 siblings — GAP: not applicable — <x> has no user-facing strings
Off-checklist: src/commands/<x>.test.ts — no sibling equivalent; siblings predate the test convention
```

Every checklist gap gets a disposition: adding it now, not applicable because <reason>, or intentionally divergent because <reason>. Every off-checklist file your change touches gets a line naming why the siblings did not need it. A run that derives the checklist and does not close with this diff has not run this skill — the diff is what turns archaeology into a check.

## Boundaries

- The checklist comes from commit history, not stated intent — no spec or PRD is presumed. Turning a settled spec into observable acceptance checks is `acceptance-map`.
- One operation's recipe, not orientation. Understanding an unfamiliar repo as a whole is `explain-codebase`.
- Not a plan and not a review: it produces no task ordering and renders no verdict beyond the completeness diff. When the addition needs real design first, run the owning design lane and use this as the completeness check after.

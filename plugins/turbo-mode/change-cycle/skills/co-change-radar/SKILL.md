---
name: co-change-radar
description: "Use before a non-trivial edit to a tracked file, and again before declaring a multi-file change complete: mines the file's own commit history for habitual co-change partners and forces a one-line disposition for every flagged partner the diff does not touch — the docs table, fixture, or parallel enum that grep, imports, and LSP cannot see. Do not use when adding a new instance of an existing category from sibling add-commits (`add-an-x-by-example`), or to map consumers of a declared interface change (`contract-change-propagation`)."
---

# Co-Change Radar

Some coupling has no interface. The docs table, the fixture, the parallel enum, the generated snapshot, the config that always moves with this module — grep, imports, and LSP are structurally blind to all of it, because the link is convention, not reference. The repo's commit history records it anyway: files that habitually change together keep needing to change together. Before an edit, mine that record and surface every habitual partner your diff does not touch — so the coupling gets a decision instead of a regression.

Invocation: `/co-change-radar` or `$co-change-radar`; also fires unprompted before a non-trivial edit to a tracked file, and again before declaring a multi-file change complete.

## 1. Mine the partners

1. Take the file's recent commits and their complete file lists: `git log -n 30 --format='%H' --name-only --full-diff -- <file>`. The path selects commits; `--full-diff` keeps the other changed paths visible for pruning and counting.
2. Prune bulk commits before counting — a commit touching more than ~20 files is a refactor sweep, a format pass, or lockfile churn, and its co-occurrences are noise, not habit. Say how many were pruned.
3. Count co-occurrences across the surviving commits. Flag a partner when it co-changed in **≥40% of those commits and at least 3 times**. Tune the gate when the repo's evidence warrants, but never remove it: an ungated partner list decays the radar into ceremony on every edit.
4. When fewer than ~5 focused commits touch the file — young file, shallow clone, squash-heavy history — say so, fall back to naming likely partners from reading the tree, and mark the result as derived from that weaker basis. Never slide silently from "history is thin" to "no check".

## 2. Disposition every flagged partner — mandatory

For each flagged partner absent from the current diff, either update it within the authorized scope, explain in one line why this particular change does not need it, or report it as needed but unresolved with the reason it remains open (for example, deferred, blocked, or outside scope). A check-only invocation reports needed changes without making them:

```text
Co-change partners of src/routes.py (12 focused commits kept, 3 bulk pruned):
  docs/api.md                 10/12  in diff? no  — needed but unresolved: param table needs updating; user deferred docs changes
  tests/fixtures/routes.json   8/12  in diff? no  — not needed: internal rename, response shape unchanged
  src/schema.py                6/12  in diff? yes
```

Before declaring a multi-file change complete, re-run the check against the full diff: partners of the files you actually edited, minus the files the final diff touches. A run that mines the partners and does not close with a per-partner disposition has not run this skill — the disposition line is what turns a hit-rate into a check.

## Boundaries

- Edit-time, not add-time: adding another instance of a category the repo already has draws on the siblings' add-commits — that is `add-an-x-by-example`. Same evidence source, different question: it asks what adding an X requires; this asks what moves with a file you are changing.
- No interface required: mapping the consumers of a declared interface change — API, function signature, schema, config key, event payload — is `contract-change-propagation`. This fires on ordinary edits and finds the coupling that has no interface at all.
- A radar, not a verdict: the output is the partner table and its dispositions. It neither authorizes additional edits nor decides whether the overall task is complete. Reporting a needed but unresolved partner satisfies this check's disclosure requirement without resolving that work.

---
name: acceptance-map
description: "Use when the user wants to turn an already-settled PRD, plan, issue, design, or concrete review finding into a durable map of observable acceptance checks before implementation, with a default local artifact and commit lifecycle. Do not use for implementation, issue/PRD creation, broad review/status, test execution, or final closeout."
---

# Acceptance Map

Turn an accepted or mostly-settled source artifact into observable checks before implementation starts.

This skill creates a proof-first bridge artifact: useful enough for an implementing agent to build toward, but optimized for the later reader who must decide whether the outcome was satisfied.

It is not an implementation plan, issue creator, review pass, TDD loop, status brief, or closeout workflow.

## Core Contract

By default, create or update a durable Markdown acceptance map and commit that artifact lifecycle locally.

The map is a derived companion unless the user explicitly promotes it or the source artifact names it as controlling. It must not quietly override the PRD, plan, issue, design, review finding, or repo authority it maps from.

When implementation usefulness conflicts with proof clarity, proof clarity wins.

## Trigger Boundaries

Use this skill when the user asks to:

- turn a PRD, plan, issue, design, or review finding into acceptance checks
- define observable acceptance criteria before implementation
- make an artifact verifiable or ready for TDD, implementation planning, review, or closeout
- map outcomes, non-goals, evidence, and verification ideas into a reusable Markdown artifact

Review findings are first-class sources only when they are concrete and actionable. Review-derived checks prove that the finding is resolved; they must not expand the finding into unrelated redesign, product scope, or cleanup.

Do not use this skill for:

- creating PRDs; use `to-prd`
- creating implementation issues; use `to-issues`
- sequencing existing findings into a strategic plan; suggest the user run `/next-steps` or `$next-steps` (explicit-invoke only)
- implementation, tests-first development, or debugging
- final verification or commit closeout after implementation; use `closeout-check`
- broad status orientation, baseline authority resolution, review, or audit

If the user asks for issues, finish the acceptance map first, then hand off to `to-issues` using the map as source input.

## Source Handling

Inspect the source artifact before writing. Use nearby context only when needed to understand outcome, authority, non-goals, evidence, or ambiguity.

Valid source inputs include:

- local Markdown PRDs, plans, issues, design docs, specs, ADRs, or review notes
- pasted or conversational source material
- issue, PR, or review finding text when available in the current context or through an explicitly requested connector path
- multiple source artifacts when they clearly describe one acceptance target

If one primary local source file controls the map, use that as the source. If the map combines multiple sources and no repo convention gives it a home, ask one path question before writing.

If source material has bounded ambiguity, write the map and mark affected checks as `decision needed`, `proposed`, or `blocked by source ambiguity`.

Stop before writing when ambiguity controls the core outcome, audience, success meaning, acceptance authority, or implementation boundary enough that most of the map would be speculative or the intended outcome could invert.

Do not silently resolve product, policy, compatibility, ownership, or scope decisions.

## Acceptance Checks

Every core acceptance check must have a source basis. Do not include truly source-free ideas in the core acceptance set.

Use these basis labels:

- `source-backed`: explicitly stated by the source
- `inferred`: necessary to prove an explicit source outcome
- `decision needed`: plausible, but source ambiguity or human judgment blocks acceptance authority

An inferred check still needs a source pointer to the material it interprets and a short reason why the inference is necessary to prove the source outcome.

For review-derived checks, point to the review finding and include the finding's evidence anchor when available. If a finding is vague, speculative, preference-based, or lacks enough evidence to define acceptance authority, mark the relevant check `decision needed` or stop when most of the map would be speculative.

Source-free ideas may appear only in an optional `Suggested Extra Checks` section when they are materially useful or the user asks for them. They are non-authoritative and must not be used as closeout requirements unless later accepted into the source artifact or explicitly promoted by the user.

## Default Artifact Shape

Use an index table for navigation, but make one section per acceptance check the real artifact.

Default shape:

```markdown
# Acceptance Map: <title>

Source: <path, issue, PRD, design, or review finding set>
Authority: Derived companion unless explicitly promoted
Outcome: <plain-language outcome>

## Check Index

| ID | Acceptance Check | Basis | Decision Gap |
| -- | ---------------- | ----- | ------------ |
| A1 | <short check> | source-backed | none |
| A2 | <short check> | decision needed | <question> |

## Acceptance Checks

### A1. <short check name>

Passes when:
<observable outcome>

Evidence to inspect:
<artifact, behavior, UI/API state, docs state, test result, command output>

Verification ideas:
<tests, commands, manual inspection, smoke check>

Source basis:
- Basis: <source-backed | inferred | decision needed>
- Source: <source pointer>
- Reasoning: <only for inferred or decision-needed checks>

Non-goals:
<nearby thing this check should not expand into, if useful>

Implementation notes:
<only hints needed to make the check buildable, not a plan>

## Decision Needed

<questions that block acceptance authority or implementation/closeout certainty>

## Suggested Extra Checks

<optional, non-authoritative, omitted when empty>
```

Omit optional sections when they would be empty. Keep implementation notes minimal; this artifact sets proof targets, not build steps.

## Output Path

When the user supplies an output path, use it.

When there is one primary local source file and no output path, write beside the source as:

```text
<source-stem>.acceptance-map.md
```

Use an explicit or obvious repo convention instead when one exists, such as `docs/acceptance/`, `docs/specs/acceptance/`, or a source document that names an acceptance-map location.

If the source is remote, pasted, conversational, or multi-source and no path can be inferred safely, ask one path question before writing.

## Source Backlink

When the primary source is a local editable Markdown file, update it automatically with a small link to the acceptance map.

Keep the backlink minimal. Prefer an existing related section when obvious; otherwise add a short line near the top or near the source's planning/proof metadata:

```markdown
Acceptance map: [<map filename>](<relative path>)
```

For remote, generated, read-only, non-Markdown, pasted, or conversational sources, do not mutate the source. Report the backlink or reference the user could add instead.

## Updating Existing Maps

When rerun for the same source, update the existing acceptance map in place if the map is clearly linked to that source and all touched paths are clean before editing.

Do not promise preservation of manual sections or user-authored edits. If the existing map appears manually edited, contains unclear custom sections, has a different source, or has uncommitted changes before the run, stop and ask before updating.

## Dirty Worktree And Commit Policy

Automatic local commit is part of the default lifecycle.

Before writing, confirm the output path and any source-backlink path belong to one Git worktree where a local commit can be created. If no Git repository is available, or if the commit lifecycle is not safe for the target path, stop and ask before creating an uncommitted artifact.

Also confirm the worktree is on a non-protected working branch before writing. Treat repo-defined protected branches first; if the repo defines none, treat `main`, `master`, `develop`, and `release/*` as protected. If the checked-out branch is protected or the repo's default branch, stop and ask whether to branch first (or hand off to `git-hygiene` or `merge-branch`) — do not write an artifact that the default commit lifecycle cannot then commit.

A dirty worktree does not automatically block the skill. Proceed only when:

- no relevant paths are already staged
- the source file to backlink is clean before editing
- the target acceptance-map path is new or clean before writing
- unrelated dirty files do not overlap the source file, map path, or artifact lifecycle
- the commit can stage exact paths only

Stop and ask when any touched path has pre-existing staged or unstaged changes, when exact staging would mix acceptance-map changes with unrelated user work, or when output-path ownership is unclear.

Stage only the acceptance map and the local Markdown source backlink when one was safely added. Do not stage unrelated dirty files. Use the default commit message:

```text
docs: add acceptance map for <source-stem>
```

For in-place updates, use:

```text
docs: update acceptance map for <source-stem>
```

Do not push, open PRs, update issues, resolve comments, merge branches, delete files, or sync remote state.

## Artifact Checks

Before the automatic local commit, verify the artifact lifecycle only:

- acceptance map file exists at the chosen path
- source path or source reference is recorded
- every core acceptance check has a source basis
- local Markdown source backlink was added when applicable
- backlink target resolves for local Markdown sources
- Markdown structure is sane enough to read
- `git diff --check` passes for touched files

Do not run repo-wide tests, implementation checks, builds, or runtime validation. This skill runs before implementation; those checks belong to TDD, implementation, review, or closeout.

If artifact checks fail and the fix is narrow and local to the acceptance-map lifecycle, fix and rerun them. Otherwise stop without committing and report the blocker.

## Final Response

Report:

- map path written or updated
- source backlink added, skipped, or suggested
- commit hash and message
- source basis summary, including any `decision needed` checks
- artifact checks run
- proof boundary: artifact lifecycle verified, implementation not verified
- next useful workflow: `to-issues`, `tdd`, or implementation planning to build against the map, then `review-family:implementation-review` (when available) to verify the result against it; `closeout-check` later for done-ness

If the skill stops before writing or committing, report the exact ambiguity, dirty-path conflict, artifact-check failure, or path decision needed.

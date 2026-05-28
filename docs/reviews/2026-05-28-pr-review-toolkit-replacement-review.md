# PR Review Toolkit Replacement Review

Reviewed source:
`/Users/jp/cloned-repos/pr-review-toolkit/`

Target use:
Codex-facing PR review support for this repository's plugin, skill, agent, and
command development workflows.

## Summary

`pr-review-toolkit` is a Claude Code plugin-shaped bundle of prompts. It does
not contain an executable review engine, deterministic orchestration code,
tests, or a Git repository history. Its value is the set of review lenses it
gives Claude Code: general code quality, tests, comments, error handling, type
design, and simplification.

The right replacement shape is a lightweight plugin only as a distribution
container. The review behavior itself should be judgment-centered: a primary
review command or skill gathers PR context, exposes useful review lenses, and
lets Codex decide which lenses apply. The replacement should avoid becoming a
plugin-owned workflow engine with routed stages, status taxonomies, confidence
pipelines, or semantic classifiers.

## What The Existing Toolkit Is

The directory contains nine files:

- `README.md`
- `.claude-plugin/plugin.json`
- `commands/review-pr.md`
- `agents/code-reviewer.md`
- `agents/pr-test-analyzer.md`
- `agents/silent-failure-hunter.md`
- `agents/comment-analyzer.md`
- `agents/type-design-analyzer.md`
- `agents/code-simplifier.md`

The directory itself is not a Git repository. There is no `.git` metadata, no
branch state, no test suite, no package lockfile, and no runtime code. The
toolkit is therefore best understood as prompt packaging for Claude Code, not as
a program.

## Components And Intent

### Plugin Manifest

`.claude-plugin/plugin.json` declares:

- name: `pr-review-toolkit`
- version: `1.0.0`
- description: comprehensive PR review agents for comments, tests, error
  handling, type design, code quality, and simplification
- author metadata

The manifest's aim is packaging and discovery only. It does not define behavior
or runtime contracts.

### README

`README.md` describes the plugin as a collection of six expert review agents. It
presents usage patterns for individual agent review, comprehensive PR review,
proactive review, confidence scoring, output formats, and workflow integration.

The README's aim is to teach users how to invoke the review lenses. It frames
the toolkit as useful before committing, before creating a PR, during PR review,
and after fixes.

### Slash Command: `commands/review-pr.md`

`commands/review-pr.md` is the central Claude Code slash command. Its
frontmatter allows `Bash`, `Glob`, `Grep`, `Read`, and `Task`.

The command aims to:

- determine review scope from user arguments
- inspect changed files with `git diff --name-only`
- check for an existing PR with `gh pr view`
- map changed files to applicable review aspects
- launch review agents sequentially or in parallel
- aggregate agent results into critical issues, important issues, suggestions,
  strengths, and recommended actions

This file is the closest thing to orchestration in the toolkit. It is still
prompt text, but it describes a workflow with aspects, applicability rules,
agent-launch strategy, and an aggregation format.

### `code-reviewer`

`agents/code-reviewer.md` is the general review lens. It aims to review code
against project guidance, especially `CLAUDE.md`, and to catch real bugs,
style violations, and significant code-quality issues.

Its approach:

- default to unstaged changes from `git diff`
- focus on explicit project rules and high-confidence bugs
- score issues from 0 to 100
- report only confidence >= 80
- group findings as critical or important

This is the strongest general-purpose reviewer in the bundle because it has an
explicit false-positive filter.

### `pr-test-analyzer`

`agents/pr-test-analyzer.md` is the test coverage lens. It aims to assess
whether a PR's tests cover meaningful behavior rather than line coverage.

Its approach:

- inspect changed functionality and accompanying tests
- look for critical behavioral gaps, edge cases, negative cases, async behavior,
  and error paths
- rate suggested tests from 1 to 10 by criticality
- separate critical gaps, important improvements, brittle tests, and positive
  observations

This is a useful lens, but its ratings should remain local reasoning aids, not
pipeline state.

### `silent-failure-hunter`

`agents/silent-failure-hunter.md` is the error-handling lens. It aims to find
silent failures, inadequate logging, broad catch blocks, hidden fallbacks, and
poor user-facing error messages.

Its approach:

- locate try/catch or equivalent error-handling code
- inspect logging quality, user feedback, catch specificity, fallback behavior,
  and error propagation
- flag hidden failures such as empty catch blocks, log-and-continue behavior,
  default returns on errors, fallback chains, and optional chaining that hides
  expected work
- report location, severity, hidden errors, user impact, recommendation, and
  example fix

This lens is valuable but over-personalized to one original codebase. It names
specific logging APIs such as `logForDebugging`, `logError`, `logEvent`, and
`constants/errorIds.ts`.

### `comment-analyzer`

`agents/comment-analyzer.md` is the documentation accuracy lens. It aims to
protect against comment rot and misleading documentation.

Its approach:

- cross-check comment claims against implementation
- check documented parameters, return types, edge cases, side effects, and
  performance claims
- flag redundant comments, misleading comments, ambiguous language, outdated
  references, and stale TODOs
- provide advisory findings only

This is a clean judgment-supporting agent because it explicitly says it should
not modify code.

### `type-design-analyzer`

`agents/type-design-analyzer.md` is the type-design lens. It aims to evaluate
whether new or changed types express and enforce useful invariants.

Its approach:

- identify implicit and explicit invariants
- rate encapsulation, invariant expression, invariant usefulness, and invariant
  enforcement from 1 to 10
- flag exposed mutable internals, documentation-only invariants, weak
  construction validation, and inconsistent mutation guards
- suggest pragmatic improvements

This is useful for domain modeling and API design, but it should remain a lens.
The replacement should not persist or pipeline the numeric scores.

### `code-simplifier`

`agents/code-simplifier.md` is a refactoring lens. It aims to simplify recently
modified code for clarity, consistency, and maintainability while preserving
behavior.

Its approach:

- inspect recently modified code
- remove unnecessary complexity and redundant abstractions
- improve names and structure
- prefer explicit code over compact cleverness
- apply project standards from `CLAUDE.md`
- operate autonomously and proactively after code changes

This agent is different from the others because it is not purely review-only.
It is a mutation/refinement agent. In a PR review replacement, this should be
separate from the review command or fenced behind an explicit user request.

## Existing Strengths

- The toolkit is small and understandable.
- The six lenses map to real review concerns that Codex can use.
- Most value is in prose prompts, not hidden code.
- The review concerns are mostly content-shaped: a human reviewer also cares
  about comments, tests, error handling, type design, and code quality.
- The strongest agents emphasize evidence, file/line references, and actionable
  output.
- `comment-analyzer` is explicitly advisory, which matches review-only
  boundaries.
- `code-reviewer` has a useful high-confidence reporting threshold.

## Weaknesses

### 1. The central command leans toward workflow machinery

`commands/review-pr.md` describes review aspects, applicability rules,
sequential and parallel execution modes, and aggregation categories. That is not
yet heavy, but it is the growth direction this repository's development tenet
warns about.

Codex can inspect a diff and decide which lenses apply. A command that
pre-decides the route risks replacing Codex judgment with prompt-level workflow
machinery.

### 2. PR scope detection is underpowered

The command's default scope detection uses `git diff --name-only` and optionally
`gh pr view`.

That can miss or flatten important PR review context:

- staged changes
- committed branch changes relative to a merge base
- the actual GitHub PR diff
- inline review comments
- unresolved review threads
- current-head versus stale review comments
- branch protection and CI state

For this repository's review practice, current-head review truth often requires
thread-aware review comment inspection, not only a flat PR view.

### 3. It mixes review with mutation

`code-simplifier` is useful after review, but it is not a review-only agent. It
states that it can operate autonomously and refine code immediately.

A replacement PR review command should not invoke mutation-oriented behavior by
default. Review and fix/refactor lanes should remain distinct.

### 4. Some prompts are overfit to an original project

Several agents assume `CLAUDE.md`. The silent-failure lens also assumes
project-specific logging functions and error ID conventions.

A replacement should use local instruction surfaces generically:

- `AGENTS.md`
- `CLAUDE.md`
- repo-local style docs
- plugin or skill README files
- explicit user-provided review scope

Project-specific examples should be presented as examples, not as universal
requirements.

### 5. Numeric scoring can become accidental ontology

The toolkit uses confidence scores, criticality ratings, and type-design scores.
These are acceptable as local explanatory aids inside a review report. They
become over-fit if they are persisted, pipelined, aggregated mechanically, or
used by downstream tooling as contract fields.

The replacement should prefer prose severity backed by evidence over durable
score fields.

### 6. It has no deterministic helper boundary

The toolkit does not separate deterministic mechanics from judgment. It relies
on Claude Code prompt instructions to run `git` and `gh` commands correctly.

For a replacement, deterministic helper code may be valuable for:

- collecting merge-base diffs
- retrieving unresolved GitHub review threads
- separating current-head comments from stale comments
- formatting a compact evidence packet

That helper code should stop before semantic review decisions.

### 7. It has no explicit evidence boundary

The command does not force the review report to distinguish:

- source diff
- PR metadata
- review threads
- CI/check results
- local tests run during the session
- assumptions or unavailable evidence

This repository's review culture depends on knowing what proof class a claim
comes from.

## Tenet Evaluation

### Test 1: Whose failure is it?

The review lenses mostly pass. If Codex misunderstands a comment, test gap, or
error path, the work product suffers because the review finding is wrong.

The command's aspect routing is weaker. If Codex misclassifies a PR as needing
or not needing a specific aspect, the work may suffer, but the taxonomy itself
is not the work product. It exists mainly to drive the plugin's own workflow.

### Test 2: Tooling or thinking?

The thinking surface is valuable: comments, tests, error handling, types, code
quality, simplification. These are review concepts a human reader understands.

The tooling risk appears when those lenses become command arguments,
applicability rules, launch modes, aggregation categories, or durable scores.
The replacement should keep the lenses and remove the feeling that the plugin is
the customer.

### Test 3: Could Codex do this work inline?

Yes for most semantic decisions:

- which lenses apply
- whether a finding is severe
- whether a test gap matters
- whether a comment is misleading
- whether a type invariant is useful
- whether code should be simplified

Therefore, the replacement should keep those decisions in Codex prose. Scripts
or command logic should only gather deterministic context.

### Test 4: Full-surface check

The existing toolkit is small enough that it has not collapsed under its own
ontology. The redesign signal is the command's posture: "determine applicable
reviews, launch agents, aggregate results" is more workflow-shaped than
context-shaped.

The replacement should be explicitly designed as a review-lens pack before it
grows into a review pipeline.

## Recommended Replacement Shape

Build a lightweight plugin as an installable distribution container, not as a
workflow engine.

The plugin should package:

1. A primary PR review command or skill.
2. Optional specialist review agents.
3. Optional deterministic helper scripts for evidence collection.
4. Minimal README and manifest metadata.

The plugin should not own:

- semantic routing
- persisted workflow stages
- status enums
- confidence pipelines
- machine-enforced severity scoring
- mandatory N-stage review flow
- automatic mutation after review

## Proposed Components

### 1. Primary Review Command Or Skill

Purpose:
Give Codex a concise, evidence-first review procedure.

Recommended posture:

> Gather PR context, choose relevant review lenses, use agents when useful,
> report evidence-backed findings first.

Core instructions:

- inspect local instructions before reviewing
- identify the review target: local diff, branch-vs-base diff, PR number, or
  explicit file set
- collect source and PR context
- inspect unresolved review threads when reviewing an existing PR
- choose applicable lenses based on the actual changes
- lead with findings, risks, regressions, and missing proof
- keep mutation out of the review unless the user explicitly asks for fixes

Avoid:

- fixed stage gates
- mandatory all-lens review
- command-owned aspect routing
- durable score fields
- aggregation that hides evidence

### 2. Review Lenses As Agents

Keep agents as optional specialists. A good starting set:

- general code review
- test coverage review
- error-handling and silent-failure review
- comment and documentation accuracy review
- type/API/invariant design review
- simplification/refactor review, but only as an explicit post-review action

Agent descriptions should say when the agent is useful and what evidence it
needs. They should not imply that every PR must pass through every lens.

### 3. Deterministic Evidence Helper

A helper script is justified if it only gathers or formats evidence. It should
not decide review meaning.

Acceptable helper responsibilities:

- detect repository root
- compute merge base
- list changed files
- retrieve PR metadata
- retrieve unresolved review threads
- distinguish stale review comments from current-head comments when the data is
  available
- produce a compact evidence packet for Codex to read

Avoid helper responsibilities:

- classify changes into review categories
- decide whether a finding is valid
- rank severity
- decide whether to block merge
- choose which agent must run

### 4. Findings-First Output Contract

The replacement should use a stable human-readable review shape:

```markdown
## Findings

### [Severity] Short finding title

- Evidence: file path, line, diff hunk, thread, or command output
- Impact: concrete user, runtime, maintainability, or review risk
- Recommendation: smallest credible fix or decision

## Missing Proof

- Evidence that was unavailable or not checked

## Notes

- Non-blocking observations, if any
```

This supports human review without creating internal pipeline fields.

## Recommended Review Lenses

The replacement should expose lenses as judgment prompts, not as workflow
stages:

- Correctness and regressions
- Project instruction conformance
- Test coverage quality
- Silent failures and error handling
- API/type/invariant design
- Comment/documentation accuracy
- Security and trust boundary risks when relevant
- Simplicity and maintainability
- Evidence gaps and stale review-thread risks

Codex should decide which lenses apply and explain that choice when it matters.

## Suggested Non-Goals

- Do not build a PR review state machine.
- Do not persist per-agent scores.
- Do not make a script classify changes into review types.
- Do not auto-run all agents for every PR.
- Do not auto-fix review findings.
- Do not conflate PR review with branch cleanup, merge, or publication.
- Do not treat `gh pr view` as sufficient for all review-thread truth.

## Replacement Readiness Recommendation

Use a plugin if installation and bundling are important. Keep the plugin thin.

The replacement should be described as an installable review-lens pack:

> A Codex-facing PR review support plugin that packages concise review lenses
> and deterministic evidence collection, while leaving semantic review judgment
> to Codex.

That shape preserves the useful part of `pr-review-toolkit`: focused review
perspectives. It avoids the weak part: a central prompt that wants to become a
review workflow engine.

## Concrete Next Design Move

Draft the replacement around one primary artifact first:

`commands/review-pr.md` or `skills/pr-review/SKILL.md`

That artifact should contain:

- a short purpose statement
- evidence collection checklist
- review-lens menu
- findings-first output contract
- hard boundary between review and mutation
- explicit instruction to inspect PR review threads when a PR exists

Only after that reads cleanly should the specialist agents be added. If the
primary artifact feels forced to encode routing logic, that is the signal to
remove routing and return to judgment-supporting prose.

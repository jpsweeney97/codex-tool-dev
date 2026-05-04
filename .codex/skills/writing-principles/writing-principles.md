# Writing Principles for Instruction Documents

This guide applies to Claude Code authoring instruction documents. The principles optimize for deterministic behavior, efficient parsing, and correct interpretation.

This guide does not apply to user-facing documentation, conversational responses, code comments, or creative writing (see Limitations).

## Table of Contents

- [Execution Algorithm (Canonical)](#execution-algorithm-canonical)
- [Applying This Document](#applying-this-document)
  - [Boundaries (#5)](#boundaries-5)
  - [Failure Modes (#6)](#failure-modes-6)
  - [Defaults (#7)](#defaults-7)
    - [Tie-Breaker: "Preserves More Information"](#tie-breaker-preserves-more-information)
- [Calibration](#calibration)
  - [Document Risk Assessment](#document-risk-assessment)
  - [Rigor Levels](#rigor-levels)
  - [Authoring vs. Review](#authoring-vs-review)
- [Quick Reference](#quick-reference)
- [When Principles Conflict](#when-principles-conflict)
  - [Priority Hierarchy](#priority-hierarchy)
  - [Irreconcilable Conflicts](#irreconcilable-conflicts)
  - [Missing Context](#missing-context)
  - [Conflicting Instructions in Target Document](#conflicting-instructions-in-target-document)
- [Principles](#principles)
  - [1. Be Specific](#1-be-specific)
  - [2. Define Terms](#2-define-terms)
  - [3. Show Examples](#3-show-examples)
  - [4. Verify Interpretation](#4-verify-interpretation)
  - [5. State Boundaries](#5-state-boundaries)
  - [6. Specify Failure Modes](#6-specify-failure-modes)
  - [7. Specify Defaults](#7-specify-defaults)
  - [8. Declare Preconditions](#8-declare-preconditions)
  - [9. Close Loopholes](#9-close-loopholes)
  - [10. Front-Load](#10-front-load)
  - [11. Group Related](#11-group-related)
  - [12. Keep Parallel](#12-keep-parallel)
  - [13. Specify Outcomes](#13-specify-outcomes)
  - [14. Economy](#14-economy)
- [Grading Scale](#grading-scale)
- [Document-Type Notes](#document-type-notes)
- [Self-Check Procedure](#self-check-procedure)
- [Limitations](#limitations)
- [Appendix: Failure Mode Index](#appendix-failure-mode-index)

> **Intended audience:** Claude, not humans. This document teaches Claude to author instruction documents that Claude will interpret. Humans may read this document to understand or modify Claude's instruction-writing behavior, but the principles optimize for machine parsing—deterministic interpretation, unambiguous scope, explicit failure handling—rather than human readability conventions.

Instruction documents are Markdown files Claude interprets as behavioral directives:

| Type           | Location                                   | Purpose                                      |
| -------------- | ------------------------------------------ | -------------------------------------------- |
| CLAUDE.md      | Project root, `~/.claude/`, subdirectories | Project context, user preferences, workflows |
| Skill files    | `**/skills/**/SKILL.md`                    | Task-specific procedures and constraints     |
| Subagent files | `**/agents/*.md`                           | Scoped instructions for delegated tasks      |

Apply these principles when writing or reviewing instruction documents. See "Applying This Document" below for this document's own boundaries, defaults, preconditions, and authority.

---

## Execution Algorithm (Canonical)

Use this procedure when authoring or reviewing instruction documents with these principles.

1. **Verify preconditions:** Target document exists (or clear spec), and you are in instruction-authoring/review mode (not conversation mode). If not met, stop and request the missing input.
2. **Identify target type:** CLAUDE.md vs SKILL.md vs subagent instructions. If ambiguous, treat as SKILL.md (most constrained) and flag ambiguity.
3. **Establish scope first:** Ensure the target document states Boundaries (#5) before other edits.
4. **Run Self-Check passes:** Apply the Self-Check (Pass 1–10). Record violations with principle name + location.
5. **Fix in detection order:** Self-Check passes are priority-ordered—detection and fix order are aligned. Fix violations in the order found: Passes 1–3 (#1–#4), then Passes 4–5 (#5–#8), then Pass 6 (#9), then Pass 7 (#10–#12), then Pass 8 (#13), then Pass 9 (#14).
6. **Re-run until convergence:** Repeat steps 4–5 until violations stabilize or you reach 5 passes. If not converged by pass 5, stop and document unresolved violations.
7. **Output format:** Provide: (a) patch/diff, (b) brief rationale, (c) trade-offs using the Trade-off documentation format.

---

## Applying This Document

This section applies the execution-context principles to this document itself.

### Boundaries (#5)

**In scope:** Markdown files Claude interprets as behavioral directives—CLAUDE.md files, skill files (SKILL.md), subagent files. These are instruction documents.

**Out of scope:** User-facing documentation, conversational responses, code comments, creative writing. See Limitations section for rationale.

**Mutable:** Target instruction documents being authored or reviewed.

**Read-only:** This document (Writing Principles). Do not modify these principles during application; flag conflicts for human review instead.

### Failure Modes (#6)

| Failure                                                     | Response                                                                             |
| ----------------------------------------------------------- | ------------------------------------------------------------------------------------ |
| Principles conflict irreconcilably                          | Document trade-off, choose option preserving more information, mark for human review |
| Self-check doesn't converge after 5 passes                  | Document unresolved violations and stop; structural problem requires human review    |
| Target document contains genuinely conflicting instructions | Flag for human resolution; do not resolve by choosing one instruction                |
| Missing context to apply a principle                        | Flag gap, select default behavior by risk level (#7), mark as incomplete             |

### Defaults (#7)

**Document-wide default:** If no principle explicitly addresses a situation encountered during authoring or review, flag the gap and proceed with the interpretation that preserves more information. Ambiguity is worse than verbosity.

**Superseded by:** Any explicit principle guidance. If a principle addresses the situation, follow the principle rather than this default.

**If uncertain whether a principle applies:** Apply it. Over-application is correctable; under-application may miss important issues.

#### Tie-Breaker: "Preserves More Information"

Interpret "preserves more information" as "keeps more executable constraints and verifiable intent," not "adds more words."

When choosing between two edits:

- Prefer the option that retains or adds: explicit file paths, commands, version constraints, scopes, authority, checks, failure behavior, and success criteria.
- Prefer the option that removes: filler, repetition, rhetorical emphasis, and non-executable context.
- If still tied, choose the option that is more observable (Claude can verify it happened).
- If still tied after observability, prefer the shorter option—equal information in fewer words is strictly better.

### Preconditions (#8)

**Requires:**

- Target document exists or clear specification for document to create
- Sufficient context to hold target document and these principles
- Claude is in authoring or review mode (not conversational response mode)

**Check:**

- Target document: Verify file exists or specification is provided
- Context: If response truncation occurs or Claude reports context limits during review, flag and consider chunked review
- Mode: Verify task is authoring/reviewing instruction documents, not other writing

**If preconditions not met:**

- Target missing: Request target document or specification before proceeding
- Context insufficient: Propose chunked approach; do not attempt incomplete review
- Wrong mode: Clarify that these principles apply only to instruction documents

### Outcomes (#13)

**Success criteria for applying this document:**

| Criterion                         | Verification                                                                        |
| --------------------------------- | ----------------------------------------------------------------------------------- |
| Target document passes Self-Check | All 10 passes completed; no Priority 1-3 violations remain                          |
| Self-Check converged              | Completed in ≤5 passes; no oscillation detected                                     |
| Trade-offs documented             | Any accepted violations have explicit documentation per format in Iteration section |
| Gaps flagged                      | Any situations not covered by principles are marked, not silently handled           |

---

## Calibration

This section determines how much of this document to apply.

### Document Risk Assessment

| Factor              | Low                  | Medium                | High                       |
| ------------------- | -------------------- | --------------------- | -------------------------- |
| Scope               | Personal preferences | Project defaults      | Multi-agent workflows      |
| Reversibility       | Easy to change       | Requires coordination | Affects downstream systems |
| Ambiguity tolerance | High (preferences)   | Medium (conventions)  | Low (procedures)           |
| Typical length      | <50 lines            | 50-150 lines          | >150 lines                 |

**Risk level = highest factor.** A 30-line file with irreversible effects is High, not Low.

**Examples:**

| Document                                         | Key Factor                                | Risk Level |
| ------------------------------------------------ | ----------------------------------------- | ---------- |
| Personal shell aliases, no downstream consumers  | Low scope, high reversibility             | Low        |
| Project CLAUDE.md setting test commands          | Medium scope, easy to change              | Medium     |
| Multi-agent orchestration skill with file writes | Multi-agent scope, low reversibility      | High       |
| 20-line preferences file that sets `rm` behavior | Irreversible effects despite short length | High       |

### Rigor Levels

| Risk   | Read through                               | Self-Check                                  | Iteration limit |
| ------ | ------------------------------------------ | ------------------------------------------- | --------------- |
| Low    | Quick Reference only                       | Passes 1-3 (items 1-15), single pass        | 1               |
| Medium | Quick Reference + When Principles Conflict | Passes 1-6 (items 1-34), up to 2 passes     | 2               |
| High   | Full document                              | All passes (items 1-53), up to 5 iterations | 5               |

**Trade-off (Low risk):** Low-risk documents skip boundary, precondition, loophole, structural, outcome, and economy checks (Passes 4–9) as a trade-off for reduced ceremony. A preferences file missing a loophole closure is annoying; a multi-agent workflow missing one causes repeated failures.

**Default if uncertain:** Medium.

### Authoring vs. Review

| Mode      | Approach                                                                                                                       |
| --------- | ------------------------------------------------------------------------------------------------------------------------------ |
| Authoring | Draft using principles as active reference (Quick Reference table open). After drafting, apply Self-Check at calibrated rigor. |
| Review    | Apply Self-Check at calibrated rigor; reference principle sections only for violations found                                   |

---

## Quick Reference

| #   | Principle             | Core Rule                                                   | Red Flag                                                  |
| --- | --------------------- | ----------------------------------------------------------- | --------------------------------------------------------- |
| 1   | Be Specific           | Replace vague language with concrete values                 | Vague pronouns, hedge words, unspecified quantities       |
| 2   | Define Terms          | Explain jargon and acronyms on first use                    | Unexplained acronyms, assumed project knowledge           |
| 3   | Show Examples         | Illustrate rules with concrete instances                    | Rules without demonstration, abstract patterns            |
| 4   | Verify Interpretation | Include confirmation checkpoints for high-risk instructions | No verification for ambiguous scope, irreversible actions |
| 5   | State Boundaries      | Explicitly declare scope and mutability                     | Implicit "obvious" scope, unstated read-only              |
| 6   | Specify Failure Modes | Define behavior when preconditions fail                     | Happy-path-only instructions, vague error handling        |
| 7   | Specify Defaults      | State behavior when no instruction applies                  | Implicit defaults, unhandled case improvisation           |
| 8   | Declare Preconditions | State requirements and verification before execution        | Assumed working directory, tools, or state                |
| 9   | Close Loopholes       | Anticipate and block creative misinterpretations            | Rules without rationale, unaddressed edge cases           |
| 10  | Front-Load            | Put critical information first                              | Commands buried after context                             |
| 11  | Group Related         | Keep conditions near consequences                           | Cross-references, scattered related content               |
| 12  | Keep Parallel         | Match structure across similar content                      | Mixed voice in lists, inconsistent hierarchy              |
| 13  | Specify Outcomes      | Define observable success criteria                          | "Ensure it works," process without verification           |
| 14  | Economy               | Remove words that don't advance meaning; use active voice   | Filler phrases, passive voice, double negatives           |

**Numbering:** Principle numbers reflect conflict priority (lower = higher priority). Two orderings serve different purposes: (1) conflict resolution follows principle number (lower number = higher priority), (2) Self-Check pass order matches fix priority (highest priority detected and fixed first). During authoring, apply all principles.

---

## When Principles Conflict

### Priority Hierarchy

| Priority | Principles                                                                                           | Rationale                                                            |
| -------- | ---------------------------------------------------------------------------------------------------- | -------------------------------------------------------------------- |
| 1        | Be Specific (#1), Define Terms (#2), Show Examples (#3), Verify Interpretation (#4)                  | Ambiguity and misinterpretation cause wrong behavior                 |
| 2        | State Boundaries (#5), Specify Failure Modes (#6), Specify Defaults (#7), Declare Preconditions (#8) | Improvisation in ambiguous execution context is worse than verbosity |
| 3        | Close Loopholes (#9)                                                                                 | Misinterpretation harder to detect than fix                          |
| 4        | Front-Load (#10), Group Related (#11), Keep Parallel (#12)                                           | Parsing errors cascade                                               |
| 5        | Specify Outcomes (#13)                                                                               | Verification gaps are recoverable                                    |
| 6        | Economy (#14)                                                                                        | Trim only after all else assured                                     |

**Within-tier ordering:** Principles within the same priority tier are co-equal. If two same-tier principles appear to conflict, first check whether both can be satisfied (they usually can—Priority 1 principles are complementary). If genuinely irreconcilable, choose the resolution that preserves more information.

When in doubt: if cutting a word creates ambiguity or removes important context, keep the word.

### Irreconcilable Conflicts

If you cannot satisfy a principle without violating another of equal or higher priority:

1. State the conflict explicitly in your output
2. Choose the option that preserves more information (ambiguity is worse than verbosity)
3. Mark the compromise for human review

### Missing Context

If you lack context to satisfy a principle (e.g., cannot be specific because information is missing):

1. Flag the gap: "Specificity requires [X]; not available"
2. Select default behavior by risk level (#7):
   - High risk: stop and request clarification
   - Medium risk: no-op (do not change state), log what is missing, then ask
   - Low risk: proceed with the nearest similar pattern and document the assumption
3. Mark as incomplete (missing context is a correctness risk)

### Conflicting Instructions in Target Document

If the target document contains instructions that genuinely conflict:

1. Flag for human resolution—this is an intent problem, not a writing problem
2. Do not resolve by choosing one instruction over another

Default behavior: Flag the gap and apply the document's stated default (see Specify Defaults). If no default is stated, use risk-level defaults (#7). Never silently improvise. Never spin indefinitely.

---

## Principles

### 1. Be Specific

Replace vague language with concrete nouns, verbs, values, and conditions.

Ambiguity forces guessing. Specificity enables deterministic action (same input produces same behavior).

| Before                        | After                                           | Violation            |
| ----------------------------- | ----------------------------------------------- | -------------------- |
| "Update the config file"      | "Update `.claude/settings.json`"                | Vague noun           |
| "Run the tests"               | "Run `uv run pytest tests/`"                    | Missing command      |
| "It processes the data"       | "The parser extracts timestamps from log lines" | Vague pronoun + verb |
| "Handle errors appropriately" | "Log errors to stderr, retry once, then raise"  | Vague action         |
| "Wait for the process"        | "Wait 30 seconds or until exit code received"   | Vague duration       |
| "If something goes wrong"     | "If `response.status >= 400`"                   | Vague condition      |

**Common violations:**

- Vague pronouns: "it," "this," "that" without clear antecedent
- Hedge words: "appropriate," "proper," "suitable," "relevant"
- Unspecified quantities: "a few," "some," "many," "a while"
- Abstract verbs: "handle," "process," "manage," "deal with"

---

### 2. Define Terms

Explain jargon, acronyms, and project-specific vocabulary on first use.

Undefined terms force Claude to guess meaning or request clarification.

| Before                                      | After                                                                               | Violation              |
| ------------------------------------------- | ----------------------------------------------------------------------------------- | ---------------------- |
| "Use the DTR pattern here"                  | "Use the DTR (Discover-Transform-Report) pattern here"                              | Undefined acronym      |
| "This follows our standard escalation flow" | "This follows the escalation flow: warn → retry → fail → alert"                     | Assumed knowledge      |
| "Apply the factory pattern"                 | "Apply the factory pattern (centralized object creation via `createX()` functions)" | Jargon without context |

**Common violations:**

- Acronyms without expansion on first use
- Project-specific terms used without definition
- Using different terms for the same concept

---

### 3. Show Examples

Illustrate abstract guidance with concrete instances. Don't state rules without demonstration.

Examples disambiguate. They show edge cases and expected output.

| Before                             | After                                                                                                                                                                        | Violation                                          |
| ---------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | -------------------------------------------------- |
| "Structure responses for the user" | "Structure responses as: observation → action → result. Example: 'Found 3 failing tests → Fixed null check in `auth.ts:42` → All tests pass.'"                               | Abstract pattern without shape                     |
| "Errors should degrade gracefully" | "Graceful degradation: if Redis unavailable, fall back to in-memory cache, log warning, continue. Not: crash or silently drop data."                                         | Behavior rule without positive + negative instance |
| "Match the existing code style"    | "Match style: if surrounding code uses `snake_case`, use `snake_case`. If it uses early returns, use early returns. Don't impose preferences."                               | Subjective guidance without anchoring              |
| "Use appropriate log levels"       | "Log levels: ERROR (requires human action), WARN (degraded but functional), INFO (state changes), DEBUG (troubleshooting). Example: failed auth → ERROR; cache miss → DEBUG" | Category system without calibration                |

**Common violations:**

- Rules stated without concrete illustrations
- Patterns described abstractly without showing structure
- Categories defined without examples of each
- Expected formats described but not demonstrated

---

### 4. Verify Interpretation

For high-risk instructions, include checkpoints where Claude confirms understanding before acting.

Misinterpretation that executes successfully is worse than execution failure—#6 never fires when Claude confidently does the wrong thing. Verification checkpoints catch interpretation errors upstream.

| Before                                   | After                                                                                                                                                                  | Verification Added          |
| ---------------------------------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------- |
| "Refactor the auth module to use JWT"    | "Refactor auth to use JWT. Before modifying files, confirm: you will change `src/auth/session.ts` to use `jsonwebtoken`, replacing the current cookie-based sessions." | Interpretation confirmation |
| "Delete unused imports"                  | "Delete unused imports. Before deleting, list the imports you will remove and wait for confirmation."                                                                  | Action preview              |
| "Update the API to match the new schema" | "Update API to match new schema. Before proceeding, state which endpoints you will modify and what changes each requires."                                             | Scope confirmation          |

**When to add verification checkpoints:**

| Factor               | Add Checkpoint                              | Skip Checkpoint                     |
| -------------------- | ------------------------------------------- | ----------------------------------- |
| Reversibility        | Hard to undo (deletions, overwrites)        | Easy to undo (additive changes)     |
| Scope ambiguity      | Instruction could apply to multiple targets | Target is explicit and unambiguous  |
| Domain specificity   | Terms have project-specific meanings        | Standard terminology                |
| Consequence severity | Errors affect production, security, data    | Errors contained to dev environment |

**Pattern:** "Before [action], confirm: [observable state proving correct interpretation]."

#### High-Risk Trigger List (Checkpoint Required)

Treat the instruction as high-risk and require a checkpoint if any of the following are true:

- Irreversible or lossy actions (delete/overwrite, destructive migrations)
- Writes outside the repo workspace or to privileged paths
- Deploy/release, production changes, billing-impacting actions
- Changes involving secrets, credentials, authn/authz, or security boundaries
- Network calls (API requests, downloads) where the target is not explicitly specified
- Large/ambiguous scope ("the codebase", "the API", "the docs") without file/path constraints

#### Checkpoint Template

Use a fixed template so the checkpoint is not satisfied by vague "confirm understanding" language:

- `Checkpoint: restate plan in 1–3 bullets.`
- `Checkpoint: list affected files/paths (or "none").`
- `Checkpoint: list commands to run (or "none").`
- `Checkpoint: confirm required approvals (user confirmation required: yes/no).`
- `Proceed only after: explicit user confirmation when required.`

**Common violations:**

- High-risk operations without interpretation confirmation
- Ambiguous scope without target enumeration
- Domain-specific terms without verification of Claude's understanding
- "Proceed with your best judgment" for irreversible actions

---

### 5. State Boundaries

Explicitly declare what's in scope vs. out, what's mutable vs. read-only, what resources are accessible.

Implicit boundaries get tested. Explicit boundaries don't.

| Before                           | After                                                                                         | Boundary Added        |
| -------------------------------- | --------------------------------------------------------------------------------------------- | --------------------- |
| "Fix the bug in the auth module" | "Fix the bug in `src/auth/`. Do not modify `src/auth/legacy/` (deprecated, read-only)."       | Mutable vs. read-only |
| "Update the tests"               | "Update tests in `tests/unit/`. Integration tests (`tests/integration/`) are out of scope."   | In/out scope          |
| "Refactor the API handlers"      | "Refactor handlers in `src/api/v2/`. Do not change `src/api/v1/` (frozen for compatibility)." | Version boundaries    |
| "Clean up the codebase"          | "Clean up files you modified in this PR. Do not clean up unrelated files."                    | Task scope            |

**Pattern:** State inclusion AND exclusion.

| Weak (inclusion only)   | Strong (inclusion + exclusion)                                         |
| ----------------------- | ---------------------------------------------------------------------- |
| "Edit files in `src/`"  | "Edit files in `src/`. Do not edit `src/generated/` or `src/vendor/`." |
| "You can read any file" | "You can read any file. Write access limited to `src/` and `tests/`."  |

**Common violations:**

- Assuming scope is "obvious" from context
- Stating what's allowed without stating what's forbidden
- Implicit read-only files (legacy, generated, vendored)
- Unbounded "clean up" or "improve" instructions

---

### 6. Specify Failure Modes

For each instruction with preconditions, define behavior when those preconditions aren't met.

Without explicit failure handling, Claude improvises. Improvisation is unpredictable.

| Before                     | After                                                                                         | Failure Mode Covered |
| -------------------------- | --------------------------------------------------------------------------------------------- | -------------------- |
| "Read config from `.env`"  | "Read config from `.env`. If missing, check `.env.example`. If neither exists, stop and ask." | Missing file         |
| "Run `npm test`"           | "Run `npm test`. If tests fail, report failures and stop—do not proceed to commit."           | Command failure      |
| "Parse the JSON response"  | "Parse the JSON response. If malformed, log the raw response and raise `ParseError`."         | Invalid input        |
| "Fetch user from database" | "Fetch user by ID. If not found, return `None`—do not create a placeholder user."             | Missing data         |

**Pattern:** "If [precondition fails], then [specific action]."

| Failure Type             | Explicit Handling Required                 |
| ------------------------ | ------------------------------------------ |
| Missing file/resource    | What to check next, when to stop           |
| Command exits non-zero   | Whether to retry, continue, or abort       |
| Invalid/malformed input  | How to report, whether to attempt recovery |
| Network/external failure | Retry policy, fallback behavior            |
| Ambiguous state          | When to ask vs. when to assume             |

**Common violations:**

- Instructions assuming happy path only
- "Handle errors appropriately" (undefined behavior)
- "Gracefully degrade" (undefined degradation)
- Missing retry/abort policies
- No guidance for partial success

---

### 7. Specify Defaults

State what Claude does when no explicit instruction covers the current situation.

Without a stated default, Claude improvises. Improvisation is unpredictable and may violate unstated intent.

| Before                            | After                                                                                                                                   | Default Added             |
| --------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------- | ------------------------- |
| (no guidance for unhandled cases) | "Default: continue with existing patterns. Superseded by: explicit instruction for novel cases."                                        | Continuation behavior     |
| "Follow project conventions"      | "Follow project conventions. Default: if convention unclear, match nearest similar code. Superseded by: explicit style instruction."    | Ambiguity fallback        |
| "Handle edge cases appropriately" | "Handle edge cases per explicit rules. Default: if no rule exists, log warning and skip. Superseded by: explicit handling instruction." | Unspecified case behavior |

**Pattern:** "Default: [action when no instruction applies]. Superseded by: [explicit instruction type that takes precedence]."

#### Default Safety by Risk Level

Defaults must be selected based on risk. Do not use "continue" defaults for high-risk situations.

| Risk Level | Default Behavior (Required)                                            |
| ---------- | ---------------------------------------------------------------------- |
| High       | "Default: stop and request clarification."                             |
| Medium     | "Default: no-op (do not change state), log what is missing, then ask." |
| Low        | "Default: continue with nearest similar pattern; document assumption." |

If uncertain about risk level: treat as High.

| Default Type      | When to Use                                      | Example                                                                   |
| ----------------- | ------------------------------------------------ | ------------------------------------------------------------------------- |
| Continue          | Behavior should persist until explicitly changed | "Default: maintain current formatting style"                              |
| Stop and ask      | Ambiguity risk is high                           | "Default: if scope unclear, stop and request clarification"               |
| Fallback action   | Safe degradation exists                          | "Default: if preferred tool unavailable, use standard library equivalent" |
| Skip with logging | Non-critical, observable                         | "Default: if optional check fails, log and continue"                      |

**Placement:** State document-wide defaults early (after scope/boundaries). State instruction-specific defaults inline with the instruction they modify.

**Common violations:**

- Instructions assuming complete coverage (no default needed)
- "Handle appropriately" without specifying what "appropriate" means when nothing applies
- Implicit defaults that require inferring author intent
- Defaults that aren't observable (Claude can't verify it applied the right default)

---

### 8. Declare Preconditions

State what must be true before execution begins. Include a verification step.

Unstated preconditions force Claude to discover requirements at execution time—after partial work may have occurred. Explicit preconditions enable upstream checking.

| Before                 | After                                                                                                                      | Precondition Surfaced |
| ---------------------- | -------------------------------------------------------------------------------------------------------------------------- | --------------------- |
| "Run `npm test`"       | "Requires: in repo root (`package.json` exists). Check: `test -f package.json`. Run `npm test`."                           | Working directory     |
| "Deploy to staging"    | "Requires: user has approved deploy. Check: confirm with user that deploy is approved. Deploy to staging."                 | Human approval        |
| "Merge feature branch" | "Requires: no merge conflicts. Check: `git merge --no-commit feature && git merge --abort` exits 0. Merge feature branch." | Git state             |

**Pattern:** "Requires: [state]. Check: [verification]. [instruction]."

| Check Type   | Form                                           | Example                             |
| ------------ | ---------------------------------------------- | ----------------------------------- |
| Programmatic | Command that exits 0 / returns expected output | `Check: test -f .env`               |
| Confirmation | Explicit user confirmation                     | `Check: confirm with user that [X]` |
| Reference    | Prior verification still valid                 | `Check: CI shows green for HEAD`    |

**If you cannot specify a check:** The precondition is likely underspecified. Make it concrete enough to verify, or flag it as requiring human review.

#### Version and Freshness Requirements

External resources (tools, APIs, paths) may change between authoring and execution. Specify version constraints when behavior depends on specific versions.

**Executable vs. pseudocode examples:** Examples in this document are illustrative. Do not assume a command is executable across environments unless explicitly labeled as executable. In instruction documents, commands must be executable in the intended environment; if environment-specific, specify OS/shell/tooling.

| Before                           | After                                                                                                        | Requirement Added |
| -------------------------------- | ------------------------------------------------------------------------------------------------------------ | ----------------- |
| "Run `pytest`"                   | "Requires: pytest ≥7.0. Check: `pytest --version` shows 7.x or higher."                                      | Minimum version   |
| "Use the OpenAI API"             | "Requires: OpenAI API v1. Check: endpoint returns `api_version: v1` in response headers."                    | API version       |
| "Read config from `config.yaml`" | "Requires: `config.yaml` last modified within 24 hours. Check (pseudocode): mtime(config.yaml) > now-86400." | Freshness         |

**Version patterns:**

| Constraint | Pattern                                           | When to Use                                    |
| ---------- | ------------------------------------------------- | ---------------------------------------------- |
| Exact      | `Requires: [tool] [version]`                      | Breaking changes between versions              |
| Minimum    | `Requires: [tool] ≥[version]`                     | Feature depends on version-specific capability |
| Range      | `Requires: [tool] [min]-[max]`                    | Known incompatibilities above max              |
| Freshness  | `Requires: [resource] modified within [duration]` | Dynamic resources that may stale               |

**If version/resource check fails:**

| Situation                   | Recommended Handling                                                                                                       |
| --------------------------- | -------------------------------------------------------------------------------------------------------------------------- |
| Wrong version installed     | Stop and report; do not attempt with wrong version                                                                         |
| Tool/resource not installed | Stop and report; do not attempt to install unless explicitly instructed                                                    |
| Version unknown/uncheckable | Warn in output ("version not verified"), proceed, note uncertainty in any outputs that depend on version-specific behavior |
| Resource stale              | Check for fresher source; if unavailable, stop and report                                                                  |

**Common violations:**

_Unstated preconditions:_

- Assumed working directory: "Run `pytest tests/`" — which directory?
- Assumed tool availability: "Format with `black .`" — is black installed?
- Assumed prior completion: "Deploy the build" — was build successful?
- Assumed environment state: "Source the env file" — which file? Does it exist?
- Assumed permissions: "Write results to `/var/log/`" — write access?

_Unverifiable preconditions:_

- Precondition without check: "Requires: clean git state" — how to verify?
- Vague check: "Check: ensure environment is ready" — not executable
- Subjective check: "Check: code is well-tested" — no objective verification

_Incomplete preconditions:_

- Check without failure path: stated precondition but no "if not met" guidance
- Compound precondition, single check: "Requires: Node 18+ and npm 9+" with one version check
- Transitive precondition unstated: "Requires: tests pass" — but tests require dependencies...

_Version-related violations:_

- Version-sensitive instructions without version constraints
- "Latest version" without specifying minimum acceptable version
- Freshness-dependent resources without staleness checks
- Version checks that can't fail (always proceed regardless of version)
- Instructions depending on other instruction documents without version/freshness constraints (e.g., "This skill assumes CLAUDE.md uses v2 workflow format" without verification)

---

### 9. Close Loopholes

Anticipate creative interpretations that satisfy the letter but violate intent. State intent, not just mechanics.

Claude finds interpretations you didn't consider. Rules without rationale invite creative compliance.

| Before                                    | After                                                                                                                                                   | Loophole Closed                            |
| ----------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------- | ------------------------------------------ |
| "Run tests before committing"             | "Run tests before committing. If tests fail, fix before committing—do not commit with failing tests to 'fix later.'"                                    | "Fix later" rationalization                |
| "Do not modify files outside task scope"  | "Do not modify files outside task scope. 'Improving' or 'cleaning up' nearby code counts as outside scope."                                             | "While I'm here" rationalization           |
| "Ask before making architectural changes" | "Ask before making architectural changes. Adding new patterns, abstractions, or dependencies counts as architectural—even if the code change is small." | "It's just a small change" rationalization |
| "Keep commits focused"                    | "Keep commits focused on one logical change. 'Related' changes go in separate commits—refactoring, formatting, and feature work are not one commit."    | "It's all related" rationalization         |

**Technique:** Name the rationalization, then close it.

| Rationalization           | Closure Pattern                                                   |
| ------------------------- | ----------------------------------------------------------------- |
| "I'll fix it later"       | "Do X now. Do not defer with intent to return."                   |
| "While I'm here"          | "Changes to Y are out of scope even if you notice opportunities." |
| "It's basically the same" | "A and B are distinct. Treat A as X, treat B as Y."               |
| "This is an edge case"    | "Edge cases require explicit handling, not implicit assumption."  |
| "The user probably meant" | "If ambiguous, ask. Do not infer intent beyond what's stated."    |

#### Loophole Patterns and Countermeasures

| Loophole Pattern          | Example Failure                                     | Countermeasure (Write This)                                                       |
| ------------------------- | --------------------------------------------------- | --------------------------------------------------------------------------------- |
| Scope creep               | "Update docs" → edits unrelated docs                | "Edit only: `docs/foo.md`. Do not edit: `docs/legacy/`."                          |
| Minimal compliance        | "Add tests" → adds a trivial assertion              | "Add tests covering: [cases]. Success: [command] shows these scenarios pass."     |
| Tool substitution         | "Format code" → uses a different formatter          | "Format with `ruff format`. Do not use other formatters unless instructed."       |
| Silent partial completion | First command fails → stops without reporting state | "On failure: stop and report what ran, what changed, and the exact error output." |
| Hidden side effects       | Writes outside repo or modifies global config       | "Do not write outside repo. If necessary, request explicit confirmation first."   |
| Ambiguous target          | "Fix the API" → edits v1 instead of v2              | "Only modify `src/api/v2/`. Do not modify `src/api/v1/`."                         |

#### Countermeasure Pattern

- Specify scope (inclusion + exclusion).
- Specify an observable success condition.
- Specify failure handling (what to do if blocked).

**Limitation:** Named loopholes are heuristic, not exhaustive. New loophole patterns emerge from novel instruction types. Treat this principle as defense-in-depth—it reduces the attack surface but does not eliminate it.

**Common violations:**

- Rules without stated rationale (invites "creative" compliance)
- Prohibitions without named exceptions (ambiguous boundaries)
- Instructions assuming good-faith interpretation (Claude optimizes for compliance, not intent)
- Vague scope words: "reasonable," "appropriate," "as needed"

---

### 10. Front-Load

Put the most important information first. Lead with conclusions, not context.

Claude processes sequentially. Buried info gets deprioritized.

| Before                                                                                                              | After                                                                    | Violation             |
| ------------------------------------------------------------------------------------------------------------------- | ------------------------------------------------------------------------ | --------------------- |
| "When you're working on features and need to test, and the CI is slow, you can run `pytest -x` to fail fast"        | "`pytest -x` fails fast. Use when CI is slow."                           | Buried command        |
| "Given the complexity of our auth system, and considering backwards compatibility, the recommended approach is JWT" | "Use JWT for auth. Rationale: backwards compatible, handles complexity." | Conclusion at end     |
| "There are several options: A, B, C. We recommend C."                                                               | "Use option C. (Alternatives: A, B)"                                     | Recommendation buried |

**Common violations:**

- Commands appearing after lengthy context
- Recommendations at the end of paragraphs
- Important caveats buried in later sections
- "Background" sections before actionable content

---

### 11. Group Related

Keep related information together. Place conditions near consequences.

Physical distance reflects logical distance. Scattered info requires reassembly.

| Before                                                                            | After                                                          | Violation                            |
| --------------------------------------------------------------------------------- | -------------------------------------------------------------- | ------------------------------------ |
| "Run tests. (See Environment section for prerequisites.)"                         | "Requires Node 18+. Run tests with `npm test`."                | Cross-reference instead of proximity |
| "Y applies when X is true."                                                       | "When X is true, Y applies."                                   | Condition after consequence          |
| "Step 1 in Setup section... Step 2 in Config section... Step 3 in Deploy section" | "Setup: 1. Install dependencies. 2. Configure env. 3. Deploy." | Fragmented sequence                  |

**Common violations:**

- Forward references: "see below," "as described later"
- Conditions separated from their consequences
- Related commands in different sections
- Prerequisites listed after the steps that need them

---

### 12. Keep Parallel

Use consistent structure for similar content. Match voice, format, and hierarchy.

Inconsistent patterns create parsing overhead (Claude must reconcile conflicting formats) and ambiguity.

| Before                                                                  | After                                        | Violation            |
| ----------------------------------------------------------------------- | -------------------------------------------- | -------------------- |
| "Run tests", "You should lint the code", "Formatting is done with ruff" | "Run tests", "Lint code", "Format with ruff" | Mixed voice          |
| Bullet list → numbered list → bullet list for similar items             | Consistent format throughout                 | Format inconsistency |
| `## Setup`, `### Configuration`, `## Testing`                           | Consistent heading levels for peer sections  | Hierarchy mismatch   |

**Common violations:**

- Mixed imperative and declarative in the same list
- Inconsistent heading levels for peer sections
- Varying formats for similar content (tables vs. lists vs. prose)
- Terminology shifts: using different words for the same concept

---

### 13. Specify Outcomes

Define observable success criteria. How does Claude verify correct execution?

If Claude can't verify success, it can't know it succeeded. Process completion ≠ outcome achievement.

| Before                     | After                                                                                | Outcome Added           |
| -------------------------- | ------------------------------------------------------------------------------------ | ----------------------- |
| "Fix the failing test"     | "Fix the failing test. Success: `npm test` exits 0, test output shows 0 failures."   | Observable verification |
| "Update the config"        | "Update `.env` with new API key. Success: `grep API_KEY .env` shows the new value."  | Verifiable state        |
| "Deploy the service"       | "Deploy to staging. Success: `curl https://staging.example.com/health` returns 200." | External verification   |
| "Refactor for performance" | "Refactor the query. Success: benchmark shows <100ms p95 latency (was >500ms)."      | Measurable improvement  |

**Pattern:** "Success: [observable condition]"

| Weak (process)         | Strong (outcome)                                                                        |
| ---------------------- | --------------------------------------------------------------------------------------- |
| "Run the migration"    | "Run the migration. Success: `SELECT COUNT(*) FROM users` matches pre-migration count." |
| "Install dependencies" | "Install dependencies. Success: `npm ls` shows no missing peer dependencies."           |
| "Build the project"    | "Build the project. Success: `dist/` contains `index.js` and `index.d.ts`."             |

**Common violations:**

- "Ensure it works" (unverifiable)
- "Verify correct behavior" (undefined behavior)
- "Test thoroughly" (undefined coverage)
- Process described without success criteria
- Success criteria that can't be checked (internal state, subjective quality)

---

### 14. Economy

Remove words that don't advance meaning. Use active voice and imperatives.

Every unnecessary word dilutes signal and consumes context window. Passive constructions and negative framing add words without adding meaning.

#### Cut Filler

| Before                                              | After             | Violation           |
| --------------------------------------------------- | ----------------- | ------------------- |
| "It is important to note that you should run tests" | "Run tests"       | Filler phrase       |
| "Please make sure to always remember to"            | (delete entirely) | Politeness noise    |
| "completely finished and done"                      | "finished"        | Redundant modifiers |

#### Use Active Voice

| Before                                  | After                         | Violation       |
| --------------------------------------- | ----------------------------- | --------------- |
| "Tests should be run before committing" | "Run tests before committing" | Passive voice   |
| "It is recommended that you consider"   | "Use"                         | Hedged passive  |
| "The handler should log errors"         | "The handler logs errors"     | Modal weakening |

#### Use Affirmative Framing

| Before                                  | After                    | Violation            |
| --------------------------------------- | ------------------------ | -------------------- |
| "Do not fail to include error handling" | "Include error handling" | Double negative      |
| "Never skip validation"                 | "Always validate"        | Negative instruction |

**Exception:** Prohibitions are clearest as negatives.

| Negative (preferred)    | Affirmative inverse (weaker)              |
| ----------------------- | ----------------------------------------- |
| "NEVER run `rm -rf`"    | "Always use `trash` or targeted deletion" |
| "Do NOT commit secrets" | "Commit only non-sensitive files"         |

**Common violations:**

- Filler phrases: "it is important to note," "please remember to," "make sure to"
- Redundant modifiers: "completely," "fully," "very," "really"
- Politeness noise: "please," "kindly," "if you wouldn't mind"
- Passive constructions: "should be," "is expected to," "will be"
- Double negatives: "do not fail to," "never skip," "don't forget to"
- Modal hedging: "should," "might," "could," "may want to"

#### When to Relax Economy

Relax Economy only when cutting words would create ambiguity or lose information necessary for correct interpretation. If a word can be removed without changing meaning, remove it.

Legitimate relaxations:

| Pattern               | Scope                                                                | Not This                                |
| --------------------- | -------------------------------------------------------------------- | --------------------------------------- |
| First-use definitions | First occurrence of term in document; subsequent uses follow Economy | "Let me explain again what X means"     |
| Critical prohibitions | Data loss, security exposure, irreversible state changes             | Style preferences, workflow suggestions |
| Nested conditions     | 3+ levels deep, or conditions with side effects                      | Simple if/then                          |

Illegitimate rationalizations:

- "This is complex" → Complexity alone doesn't justify verbosity; only ambiguity does
- "This is important" → Importance doesn't require repetition; emphasis does
- "Claude might not understand" → If a fresh session wouldn't understand, the instruction is ambiguous (fix that); if it would, extra words don't help

---

## Grading Scale

| Grade | Criteria                                |
| ----- | --------------------------------------- |
| A     | All 14 principles followed consistently |
| B     | Minor violations in 1-2 principles      |
| C     | Noticeable issues in 3-4 principles     |
| D     | Significant issues in 5-8 principles    |
| F     | Pervasive violations (9+ principles)    |

**Counting rule:** A principle counts as "violated" if any instance remains after Pass 3 of the Self-Check. Multiple instances do not change the number of violated principles, but should be cited.

**Severity matters within grades.** A single violated principle with document-wide impact (e.g., missing failure modes for all instructions) is more severe than violations in three principles affecting isolated sentences. Use violation count for the letter grade; note severity and scope in the accompanying citations.

Cite violations with principle name and location:

- "Be Specific: vague reference at line 45 ('the config file')"
- "Economy: filler phrase at line 12 ('it is important to note')"
- "Close Loopholes: rule without rationale at line 78"
- "Specify Outcomes: no success criteria at line 92"

---

## Document-Type Notes

Principles apply universally. These notes highlight structural and writing differences.

### CLAUDE.md

Reference documents for project context. May include tables, environment setup, workflow docs. Longer documents acceptable when density remains high.

| Practice     | Guidance                                                                                     |
| ------------ | -------------------------------------------------------------------------------------------- |
| Structure    | Random access, not linear reading                                                            |
| Format       | Tables for 3+ parallel items                                                                 |
| Placement    | Most-queried info (commands, paths) in dedicated sections                                    |
| Boundaries   | State which directories/files are relevant to this project                                   |
| Verification | Checkpoints for project-specific workflows or destructive operations                         |
| Length       | No hard limit; split into linked sub-documents if exceeding 300 lines with declining density |
| Avoid        | Prose paragraphs for reference data                                                          |

### Skill Files

Procedural workflows with phases and gates. Heavy use of checklists, rationalization tables, red flag lists. Progressive disclosure (main content first, reference material last or in separate files): SKILL.md under 500 lines.

| Practice      | Guidance                                                                              |
| ------------- | ------------------------------------------------------------------------------------- |
| Voice         | Second person imperative ("Run X", "Verify Y")                                        |
| Gates         | Explicit: "Do not proceed until [condition]"                                          |
| Outcomes      | Each phase has observable success criteria                                            |
| Failure modes | Each gate has explicit failure handling                                               |
| Loopholes     | Name common rationalizations, then close them                                         |
| Boundaries    | State what's in/out of scope for the skill                                            |
| Verification  | Gates are verification checkpoints; each phase should confirm scope before proceeding |
| Structure     | Front-load workflow; reference material last or in separate files                     |

### Subagent Files

Shortest format. Four required sections: Purpose, Task Instructions, Constraints, Output Format. Agents run in isolated context with no parent conversation access.

| Practice      | Guidance                                                                                           |
| ------------- | -------------------------------------------------------------------------------------------------- |
| Tone          | Brief a contractor who knows nothing                                                               |
| Boundaries    | Essential—agent has no parent context to infer scope                                               |
| Constraints   | State both directions ("Do X. Do not do Y.")                                                       |
| Outcomes      | Define exact output structure (agent can't verify otherwise)                                       |
| Failure modes | Define what to report when task can't be completed                                                 |
| Verification  | Include confirmation step before irreversible actions; agent cannot recover from misinterpretation |
| Examples      | Include when format is non-obvious                                                                 |
| Length        | Under 100 lines preferred; agents have minimal context budget                                      |

---

## Self-Check Procedure

Before submitting, verify in order. Passes are ordered by fix priority—highest-priority principles are checked first.

**Pass-to-principle mapping:**

| Pass | Focus                            | Principles      | Priority |
| ---- | -------------------------------- | --------------- | -------- |
| 1    | Specificity                      | #1              | 1        |
| 2    | Terms and Examples               | #2, #3          | 1        |
| 3    | Verification and Authority       | #4              | 1        |
| 4    | Boundaries                       | #5              | 2        |
| 5    | Preconditions, Failure, Defaults | #6, #7, #8      | 2        |
| 6    | Loopholes                        | #9              | 3        |
| 7    | Structure and Front-Loading      | #10, #11, #12   | 4        |
| 8    | Outcomes                         | #13             | 5        |
| 9    | Economy                          | #14             | 6        |
| 10   | Coherence                        | (cross-cutting) | —        |

### Pass 1: Specificity

1. Flag every "it," "this," "that"—replace with concrete referent
2. Flag vague nouns: "the file," "the config," "the system"
3. Flag vague verbs: "handle," "process," "manage," "deal with"
4. Verify all commands are copy-paste ready with actual paths/values

### Pass 2: Terms and Examples

5. Check that jargon and acronyms are defined on first use
6. Verify abstract rules have concrete examples
7. Check that categories are defined with examples of each

### Pass 3: Verification and Authority

8. Identify instructions with high-risk factors (irreversible, ambiguous scope, domain-specific)
9. Verify each has an interpretation checkpoint or explicit confirmation step
10. Check that checkpoints specify observable state, not just "confirm understanding"
11. Flag instructions that could plausibly appear in multiple document types
12. For overlapping instructions, verify authority relationship is stated (overrides, defers to, scoped to)
13. Flag skill files—verify they state relationship to CLAUDE.md for overlapping concerns
14. Flag CLAUDE.md files—verify they state deference patterns for skills and subagents
15. Verify scope limitations are explicit, not assumed from document location

### Pass 4: Boundaries

16. Check that scope is explicit (what's in, what's out)
17. Verify mutable vs. read-only distinctions where relevant
18. Confirm resource access limits are stated

### Pass 5: Preconditions, Failure Modes, and Defaults

19. Flag instructions with preconditions but no failure handling
20. Verify "if X fails, then Y" patterns for critical operations
21. Check that error handling is specific, not "handle appropriately"
22. Flag instructions that reference files, commands, or state without directory/environment context
23. Flag instructions that depend on prior steps—verify those steps have success criteria
24. For each "Requires:" statement, verify a "Check:" is specified
25. Verify each check is executable (command, confirmation prompt, or reference)
26. Verify compound preconditions have individual checks for each component
27. Flag instructions that don't specify default behavior for unhandled cases
28. Verify defaults are observable (Claude can confirm which default was applied)
29. Flag instructions referencing tools or APIs without version constraints
30. For dynamic resources (configs, APIs, generated files), verify freshness requirements are stated
31. Verify version checks have explicit failure handling

### Pass 6: Loopholes

32. Identify rules without stated rationale
33. Check prohibitions for named rationalizations and closures
34. Flag scope words: "reasonable," "appropriate," "as needed"—make concrete

### Pass 7: Structure and Front-Loading

35. Confirm critical information appears early, not buried
36. Verify conditions appear before their consequences
37. Check that related information is grouped, not scattered
38. Verify parallel structure in lists (all imperative or all declarative)
39. Check heading hierarchy is consistent across peer sections
40. Confirm terminology is used consistently throughout

### Pass 8: Outcomes

41. Flag instructions without observable success criteria
42. Verify outcomes are actually verifiable (command output, state change, measurable value)
43. Check that "ensure," "verify," "confirm" have concrete definitions

### Pass 9: Economy

44. Search for filler phrases: "it is important to," "please note," "make sure to," "remember to"
45. Search for redundant modifiers: "completely," "fully," "very," "really"
46. Identify any sentence that can be cut without losing meaning
47. Check for information stated twice in different words
48. Convert passive constructions to active ("should be run" → "run")
49. Convert negative instructions to affirmative where possible

### Pass 10: Coherence

50. Read the document end-to-end: do sections contradict each other?
51. Would a fresh Claude session understand and follow these instructions without clarification?
52. Are there any loopholes you'd exploit if asked to comply minimally?
53. After completing all passes, verify convergence: if edits are reversing previous edits or the same violations recur, diagnose per Convergence section before continuing

### Iteration

If violations found:

1. Fix highest-priority violations first (Priority 1 before Priority 2, etc.)
2. Re-run Self-Check from Pass 1
3. If a violation cannot be fixed without creating higher-priority violations, document the trade-off and mark for review

**Stopping condition:** No Priority 1-3 violations remain, or all remaining violations are documented trade-offs.

### Convergence

The self-check should converge within 2-3 passes. Non-convergence indicates a problem to diagnose, not a reason to continue indefinitely.

**Maximum passes: 5.** If violations remain after pass 5, document remaining violations as unresolved and stop. Continuing beyond 5 passes indicates a structural problem requiring human review, not more iteration.

**Expected behavior:**

| Pass | Typical Outcome                                              |
| ---- | ------------------------------------------------------------ |
| 1    | Most violations identified and fixed                         |
| 2    | Residual violations from fixes; some new violations possible |
| 3    | Should stabilize; few or no new violations                   |
| 4+   | If still finding violations, diagnose before continuing      |

**Detecting non-convergence:** If you are making edits that reverse previous edits, or if the same violations reappear after being fixed, stop and diagnose rather than continuing.

**If violations persist or recur:**

1. **Check for oscillation:** Are the same edits being made and unmade?
   - Most common: Economy removes words ↔ Specificity adds them back
   - Resolution: The word adds information (keep it) or doesn't (remove it). Economy only removes words that don't advance meaning.

2. **Check for over-application:** Is a principle being applied beyond its scope?
   - Economy should not remove words that add information
   - Specificity should not add detail beyond what's needed for unambiguous interpretation
   - Resolution: Calibrate to "necessary and sufficient," not "maximal application"

3. **Check for genuine conflict:** Does the target document contain instructions that genuinely conflict?
   - Resolution: Flag for human review—this is an intent problem in the target document, not a writing-principles problem

**Important:** "Flag and stop" is for genuinely intractable cases after diagnosis—not for avoiding difficult fixes. If diagnosis reveals a fixable problem (oscillation due to misapplied Economy, over-application of Specificity), fix it and continue rather than flagging.

**Convergence failure types:**

| Type              | Signal                                               | Resolution                                                            |
| ----------------- | ---------------------------------------------------- | --------------------------------------------------------------------- |
| Oscillation       | Same change made and reversed across passes          | Determine which state preserves more information; that state wins     |
| Over-application  | Principle applied where not needed                   | Restrict to cases where principle's rationale applies                 |
| Genuine conflict  | Target document's instructions contradict each other | Flag for human resolution; do not resolve by choosing one instruction |
| Unstable priority | Fixing P2 creates P1 violation repeatedly            | Prioritize P1; accept P2 violation as documented trade-off            |

**Trade-off documentation format:**

> "[Principle X] violation at [location]: [description]. Cannot fix without creating [Principle Y] violation. Accepted because [Y has higher priority / preserves more information / other rationale]."

---

## Limitations

These principles apply to instruction documents. They do not apply to:

| Context                   | Reason                                          |
| ------------------------- | ----------------------------------------------- |
| User-facing documentation | Humans benefit from softer tone, more context   |
| Conversational responses  | Dynamic dialogue has different constraints      |
| Code comments             | Brevity matters but different conventions apply |
| Creative writing          | Economy can undermine voice and style           |

**Known gaps (future work):**

- Full worked examples per document type (CLAUDE.md, SKILL.md, subagent). Current examples are sentence-level; a complete annotated document per type would better demonstrate principle interaction.
- Modular architecture for context-window-constrained environments. This document is designed as a monolith; a core-plus-extensions split (core always loaded, extensions loaded per calibration level) would reduce token cost per application.
- Versioning scheme for tracking which revision of these principles was used to author a given document.

---

## Appendix: Failure Mode Index

Maps failure modes to preventing principles for gap analysis.

| Failure Mode                           | Preventing Principles                    | Notes                            |
| -------------------------------------- | ---------------------------------------- | -------------------------------- |
| Ambiguity causing wrong behavior       | #1 (Specific), #2 (Terms), #3 (Examples) | Priority 1 cluster               |
| Misinterpretation of high-risk actions | #4 (Verify Interpretation)               | Checkpoint pattern               |
| Scope creep / boundary violation       | #5 (Boundaries)                          | Inclusion + exclusion            |
| Improvised error handling              | #6 (Failure Modes)                       | Explicit failure paths           |
| Undefined default behavior             | #7 (Defaults)                            | Global fallback                  |
| Runtime precondition discovery         | #8 (Preconditions)                       | Requires/Check pattern           |
| Version drift / resource staleness     | #8 (Preconditions)                       | Version and Freshness subsection |
| Creative non-compliance                | #9 (Loopholes)                           | Name and close rationalizations  |
| Deprioritized information              | #10 (Front-Load)                         | Lead with conclusions            |
| Scattered reassembly                   | #11 (Group Related)                      | Physical = logical distance      |
| Parsing overhead                       | #12 (Parallel)                           | Consistent structure             |
| Unverifiable success                   | #13 (Outcomes)                           | Observable criteria              |
| Signal dilution / context waste        | #14 (Economy)                            | Remove non-advancing words       |

**Using this index:** If reviewing a document and uncertain which principles apply, identify the failure mode you're trying to prevent, then consult the corresponding principles.

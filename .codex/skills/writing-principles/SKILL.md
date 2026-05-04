---
name: writing-principles
description: Enforces writing principles for instruction documents (SKILL.md, skill supporting files, subagents, CLAUDE.md). Use when writing, reviewing, or editing any file in **/skills/**/*.md, **/agents/*.md, or **/CLAUDE.md. Triggers on skill creation, skill file updates, CLAUDE.md changes, subagent authoring, or instruction document review.
---

# Writing Principles

Enforce consistent quality in instruction documents by applying the 14 writing principles.

## Scope

This skill applies when you write, review, or edit:

- `**/skills/**/*.md` — Skill files and supporting documentation
- `**/agents/*.md` — Subagent instruction files
- `**/CLAUDE.md` — Project and user instruction files

## Workflow

1. **Recognize** — Identify you're working on an instruction document
2. **Calibrate** — Assess document risk level (Low/Medium/High)
3. **Apply** — Use principles while writing or editing
4. **Verify** — Run self-check passes appropriate to risk level
   - **Gate:** Do not claim work complete until self-check passes run at calibrated rigor level
5. **Report** — List violations found and ask for guidance before fixing
   - **Gate:** Do not fix violations until user provides direction

## Risk Calibration

Assess risk level before writing. **Risk level = highest factor.**

| Factor              | Low                  | Medium                | High                       |
| ------------------- | -------------------- | --------------------- | -------------------------- |
| Scope               | Personal preferences | Project defaults      | Multi-agent workflows      |
| Reversibility       | Easy to change       | Requires coordination | Affects downstream systems |
| Ambiguity tolerance | High (preferences)   | Medium (conventions)  | Low (procedures)           |
| Typical length      | <50 lines            | 50-150 lines          | >150 lines                 |

**If uncertain: treat as Medium.**

### Rigor by Risk Level

| Risk   | Self-Check Passes              | Iteration Limit |
| ------ | ------------------------------ | --------------- |
| Low    | Passes 1-3 (items 1-15)        | 1               |
| Medium | Passes 1-7 (items 1-27)        | 2               |
| High   | All passes (items 1-52)        | 5               |

## Principles Quick Reference

Apply while writing. Lower number = higher priority in conflicts.

| #   | Principle             | Core Rule                                                       | Red Flag                                                  |
| --- | --------------------- | --------------------------------------------------------------- | --------------------------------------------------------- |
| 1   | Be Specific           | Replace vague language with concrete values                     | Vague pronouns, hedge words, unspecified quantities       |
| 2   | Define Terms          | Explain jargon and acronyms on first use                        | Unexplained acronyms, assumed project knowledge           |
| 3   | Show Examples         | Illustrate rules with concrete instances                        | Rules without demonstration, abstract patterns            |
| 4   | Verify Interpretation | Include confirmation checkpoints for high-risk instructions     | No verification for ambiguous scope, irreversible actions |
| 5   | State Boundaries      | Explicitly declare scope and mutability                         | Implicit "obvious" scope, unstated read-only              |
| 6   | Specify Failure Modes | Define behavior when preconditions fail                         | Happy-path-only instructions, vague error handling        |
| 7   | Specify Defaults      | State behavior when no instruction applies                      | Implicit defaults, unhandled case improvisation           |
| 8   | Declare Preconditions | State requirements and verification before execution            | Assumed working directory, tools, or state                |
| 9   | Close Loopholes       | Anticipate and block creative misinterpretations                | Rules without rationale, unaddressed edge cases           |
| 10  | Front-Load            | Put critical information first                                  | Commands buried after context                             |
| 11  | Group Related         | Keep conditions near consequences                               | Cross-references, scattered related content               |
| 12  | Keep Parallel         | Match structure across similar content                          | Mixed voice in lists, inconsistent hierarchy              |
| 13  | Specify Outcomes      | Define observable success criteria                              | "Ensure it works," process without verification           |
| 14  | Economy               | Remove words that don't advance meaning; use active voice       | Filler phrases, passive voice, double negatives           |

For full principle details, examples, and self-check procedure: [writing-principles.md](writing-principles.md)

## Self-Check Procedure

After writing or editing, run passes appropriate to risk level.

### Pass Overview

| Pass | Focus                            | Items | Priority |
| ---- | -------------------------------- | ----- | -------- |
| 1    | Specificity                      | 1-4   | 1        |
| 2    | Terms and Examples               | 5-7   | 1        |
| 3    | Verification and Authority       | 8-15  | 1        |
| 4    | Boundaries                       | 16-18 | 2        |
| 5    | Preconditions, Failure, Defaults | 19-31 | 2        |
| 6    | Loopholes                        | 32-34 | 3        |
| 7    | Structure and Front-Loading      | 35-40 | 4        |
| 8    | Outcomes                         | 41-43 | 5        |
| 9    | Economy                          | 44-49 | 6        |
| 10   | Coherence                        | 50-53 | —        |

**Low risk:** Passes 1-3 only (Priority 1)
**Medium risk:** Passes 1-6 (Priority 1-3)
**High risk:** All passes

For the full 53-item checklist: [writing-principles.md](writing-principles.md#self-check-procedure)

### Reporting Violations

After completing the self-check:

1. List each violation with principle name and location
2. Format: `"[Principle #X]: [description] at [location]"`
3. Ask for guidance before making fixes

Do not auto-fix. Wait for user direction.

## Red Flags

These thoughts mean STOP — you're rationalizing skipping the principles:

| Thought | Reality |
| ------- | ------- |
| "This is a small edit" | Small edits compound. Apply principles. |
| "The document is already good" | Run the self-check anyway. |
| "I know these principles" | Knowing ≠ applying. Run the check. |
| "This will slow things down" | Violations cause rework. Take the time. |
| "The user is in a hurry" | Fast and wrong wastes more time. |
| "It's just a supporting file" | Supporting files are instruction documents too. |

## Failure Mode Index

Maps failure modes to preventing principles. Use for gap analysis.

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

## Composability

This skill composes with other instruction-document skills through parallel ownership.

### Domain Separation

| Skill | Domain | Responsibility |
| ----- | ------ | -------------- |
| `creating-skills` | Process | Dialogue, design, structure, use cases |
| `claude-md-improver` | Auditing | Scanning, evaluating, updating CLAUDE.md files |
| `writing-principles` | Quality | Principle adherence, writing clarity, verification |

### How Composition Works

When multiple skills are active:

1. **Each skill's instructions are in context simultaneously**
2. **Apply all relevant guidance while working** — Use creating-skills' process AND this skill's principles during drafting
3. **Neither skill blocks the other** — Process completion and quality verification are independent concerns
4. **Run this skill's self-check before considering any instruction document complete**

### Example: Creating a New Skill

With both `creating-skills` and `writing-principles` active:

- `creating-skills` drives the dialogue and drafting process
- `writing-principles` influences each drafted section (principles internalized)
- After drafting completes, run self-check appropriate to risk level
- Report violations and ask for guidance

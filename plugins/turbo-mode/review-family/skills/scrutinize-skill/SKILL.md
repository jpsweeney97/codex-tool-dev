---
name: scrutinize-skill
description: Use when the target of an adversarial review is a Codex skill, skill directory, SKILL.md, agents/openai.yaml, skill reference, example, or proposed skill contract, including explicit `review-family:scrutinize-skill`, `$scrutinize-skill`, or natural-language requests such as "scrutinize this skill". Review behavior quality, user experience, instruction clarity, composability, and overlap with the available skill set. Do not use for routine skill editing, implementation, general artifact review, or completed-code review.
---

# Scrutinize Skill

Review a Codex skill as a behavior contract. Ask whether the skill will make
Codex behave well after it triggers, not only whether the bundle is structurally
valid.

## Review-Family Routing

Explicit review-family invocation wins. The plugin-scoped form is
`review-family:scrutinize-skill`; `$scrutinize-skill` is accepted shorthand when
skill mentions are available in the current surface. When the review target is a
Codex skill or skill-support file, this skill also wins over generic
`scrutinize`, even if the user used natural-language scrutiny wording.

- Use this skill for adversarial review of a Codex skill, skill directory,
  `SKILL.md`, `agents/openai.yaml`, behavior-shaping reference, example, or
  proposed skill contract. This skill wins over `scrutinize` for Codex skill
  behavior-contract review.
- Use `scrutinize` for broad natural-language adversarial artifact critique,
  formal stress tests, and execution-readiness reviews when this skill was not
  invoked.
- Use `implementation-review` for completed code or artifacts against a
  plan/spec, and `system-design-review` for architecture or system-boundary
  review.
- Use `review-reviewer` for supplied-review adjudication or pasted-claim checks,
  and `request-claude-pr-review` for drafting a Claude PR-review prompt.
- If this skill is not the right review-family target, name the better skill
  and switch only when invocation rules allow it; otherwise ask one routing
  question.

## Scope

Primary question: will the right skill behave poorly once triggered?

Review these failure modes first:

- the skill gives weak next-step guidance after triggering
- muddled instructions make Codex improvise important behavior
- the user experience is awkward, heavy, vague, or missing closure
- the skill silently becomes another workflow instead of handing off
- overlapping skills make routing unclear, duplicate, or fragmented
- validation claims prove structure while implying behavior

Out of scope: routine skill editing, implementation, source sync, installed
runtime proof, broad plugin audits, completed-code review, and marketplace
publishing unless the user explicitly asks for that separate work.

## Evidence Floor

Inspect the exact target before judging it.

If the target is a file inside a skill bundle, such as `SKILL.md`,
`agents/*.yaml`, `agents/*.md`, `references/*`, `examples/*`, or another
behavior-shaping file, treat the containing skill directory as the target unless
the user explicitly narrows the request to that file only.

For an existing skill bundle, inspect:

- `SKILL.md`
- `agents/*.yaml` or `agents/*.md` when present
- behavior-shaping files directly referenced by the skill
- examples or references only when they affect invocation, instructions,
  evidence rules, expected output, validation, or handoff behavior

For a proposed skill contract, state which normal bundle surfaces do not exist
yet and review the available contract as proposed behavior.

Compare overlap against the whole available skill set. Start with skill names
and descriptions, then read only likely overlaps deeply enough to decide which
skill should win, whether routing needs clarification, or whether skills should
merge or split. Do not bulk-read unrelated skills just to appear exhaustive.
For source-bundle reviews, default to session-visible skill descriptions plus a
source sibling scan. Add installed cache or runtime inventory only when the user
asks about downstream installed or loaded behavior, or when the overlap claim
depends on that proof class.
Report the overlap coverage and skill-set source used: session-visible skill
descriptions, source sibling scan, installed cache scan, or runtime inventory.
Include likely overlaps deep-read, and mark omitted or unavailable skill surfaces
`unverified`. If the source is not runtime inventory, do not imply loaded-skill
state.

Separate proof classes:

- `structural`: parseable frontmatter, valid YAML, expected files, references
  that exist
- `behavioral`: realistic dry runs, examples, or reasoning that shows Codex
  will behave correctly when the skill is triggered
- `runtime`: installed plugin or loaded skill state observed through the active
  runtime

Do not claim runtime installation, activation, hook behavior, marketplace sync,
or loaded-skill state from source files, cache files, or marketplace metadata
alone.

## Workflow

1. **Target And Surface** - Name the exact target, inspected files, missing
   surfaces, and unread material that could change the review.
2. **Behavior Read** - Summarize in plain language what Codex is supposed to do
   once the skill triggers.
3. **Execution Quality** - Review first move, context reading, defaults, stop
   conditions, handoffs, output shape, and failure handling.
4. **UX Review** - Review user friction, clarity, pacing, question shape, user
   effort, challenge level, and closure.
5. **Composability And Overlap** - Identify overlapping skills and classify each
   material overlap as `target wins`, `other skill wins`,
   `routing clarification needed`, `merge candidate`, `split candidate`, or
   `no material overlap`.
6. **Validation And Proof** - Separate structural checks from behavior proof and
   name any false-confidence claims.
7. **Verdict** - Use `Reject`, `Major revision`, `Minor revision`, or
   `Defensible`.

## Output

Use this order:

1. `Target And Surface`
2. `Behavior Read`
3. `Critical Failures`
4. `UX And Execution Risks`
5. `Composability And Overlap`
6. `Validation And Proof Gaps`
7. `Required Changes`
8. `Verdict`

Lead findings with user-visible behavior: wrong amount of friction, unclear
first move, poor handoff, generic output, missing stop condition, false proof,
or ambiguous overlap.

If a required section has no concrete finding, write `None found` and move on;
do not fill it with generic observations.

Each finding must include a compact evidence pointer: file/line, command output,
observed behavior, or `unverified` with the exact missing check. Do not make
location-free findings when the target is file-backed.

Use `Bounded Review Scope` before `Target And Surface` when the target or skill
set comparison is too large to inspect completely in one pass. In bounded mode,
state the reviewed subset, mark omitted surfaces `unverified`, name the next
slice needed, and do not use `Defensible` for the full target.

## Guardrails

- Stay read-only. Do not edit files, stage, commit, push, delete, sync,
  publish, install, refresh plugin caches, or mutate runtime state unless the
  user explicitly asks for that separate action after the review.
- Do not mentally repair weak instructions. Review the behavior contract that
  exists, not the one the author probably intended.
- Do not pad with generic writing advice. Every finding must identify a concrete
  failure path or user-visible weakness.
- If overlap with a non-review-family skill matters, read enough of that skill
  to justify the routing or merge/split recommendation before making it
  verdict-driving.

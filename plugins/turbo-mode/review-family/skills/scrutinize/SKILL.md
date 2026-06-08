---
name: scrutinize
description: Use when the user explicitly asks for adversarial review of a plan, design, draft, argument, decision, code change, or broad artifact. Trigger on "scrutinize", "be brutal", "tear this apart", "assume this is wrong", or "reject until proven otherwise". Do not use for Codex skill targets, completed implementation-against-plan review, routine review, collaborative editing, or balanced feedback.
---

# Scrutinize

Stance: reject until evidence earns a better verdict. Review the exact target; read referenced files before severity-calibrated judgment.

## Review-Family Routing

Explicit review-family invocation wins, including namespaced plugin forms such
as `review-family:scrutinize`.

That generic invocation does not override target-type handoff: use
`scrutinize-skill`, `implementation-review`, or `system-design-review` when the
target belongs to one of those lanes.

- Use this skill for natural-language adversarial review requests such as
  "scrutinize", "be brutal", "tear this apart", "assume this is wrong", or
  "reject until proven otherwise" when no narrower explicit skill applies.
- Use `scrutinize-skill` when the target is a Codex skill, skill directory,
  `SKILL.md`, `agents/openai.yaml`, skill reference, example, or proposed skill
  contract, even when the user says "scrutinize" instead of invoking
  `scrutinize-skill`.
- Use `implementation-review` for completed code or artifacts against a
  plan/spec, even when the user asks for an adversarial implementation pass.
- Use `system-design-review` for architecture tradeoffs, boundaries, data
  authority, reliability, ownership, and next probes.
- Use explicit-only skills only when invoked: `adversarial-review` for
  proposal stress tests, `pragmatic-review` for execution-readiness blockers,
  `review-reviewer` for supplied-review adjudication, and
  `review-claude-claims` for itemized pasted-claim validation.
- Use `request-claude-pr-review` when the user wants a prompt for Claude Code,
  not a review performed by Codex.
- If this skill is not the right review-family target, name the better skill
  and switch only when invocation rules allow it; otherwise ask one routing
  question.

## Workflow

1. State `Target And Evidence` before judging: exact target, inspected files or
   sources, skipped or unread material, proof class, and whether runtime or
   current-state evidence was checked. Ask one targeted question if the target or
   evidence boundary is unclear.
2. If the target is a Codex skill, skill directory, `SKILL.md`,
   `agents/openai.yaml`, skill reference, example, or proposed skill contract,
   use `scrutinize-skill` instead of this generic workflow. Do not ask whether
   the user wants the dedicated lane unless the target could reasonably be
   reviewed as something other than a skill behavior contract.
3. Premise check: is this solving the right problem?
4. `Pass 1`: contradictions, omissions, weak assumptions, practical failures.
5. `Pass 2`: second-order effects, edge cases, hidden dependencies, ideal-condition assumptions.
6. Apply relevant adversarial lenses internally; replace weak ones. Report
   perspectives only when they materially changed findings, severity, or required
   changes.
7. Group root causes, then verdict: `Reject`, `Major revision`, `Minor revision`, or `Defensible`.

## Guardrails

- Multiple artifacts: choose or split by named target.
- Incomplete target: review existing material and treat gaps as risks.
- Skill bundle scope: do not stop at `SKILL.md`; cite where main instructions, agent metadata, and material references agree or conflict. Do not bulk-review irrelevant assets, generated runs, or examples unless they affect invocation, instructions, evidence, or expected outputs. State skipped-file and materiality tradeoffs explicitly.
- Review-only default: do not edit files, stage, commit, push, delete, sync, publish, or implement fixes during scrutiny unless the user explicitly asks for that separate action after the review.
- Mixed critique and implementation: finish scrutiny first, stop after the verdict, and wait for explicit follow-through before changing artifacts.
- Bounded review mode: when the target is too large to inspect completely in one pass, state the reviewed subset before findings, review the highest-risk surface first, mark omitted areas `unverified`, give the next slice needed for a complete review, and do not use `Defensible` for the full target.
- Evidence: cite file/line, output, source, or observed behavior for concrete claims; label inference or uninspectable behavior as uncertainty.
- Citation calibration: target-internal contradictions may be reported from the target alone. Any `Critical`, `High-Risk`, or final verdict that depends on an external citation must read the cited resource; otherwise downgrade the claim to `uncalibrated / citation not inspected`.
- Do not mentally repair broken logic or pad with weak objections.

## Output

Default sections: `Target And Evidence`, `Premise Check`, `Critical Failures`, `High-Risk Assumptions`, `Real-World Breakpoints`, `Hidden Dependencies`, `Patterns And Root Causes`, `Required Changes`, `Verdict`. Add `Adversarial Perspectives` only when a lens materially changed findings, severity, or required changes. Add `Bounded Review Scope` before `Target And Evidence` when bounded review mode is used and write `Verdict: Partial review only` if the requested scope was not fully inspected.

Use relevant lenses: plan logistics, writing evidence, code correctness/security/failure modes/tests, strategy assumptions/incentives/tradeoffs. Read `references/review-format.md` only for complex targets, full structured reviews, or repeated severity/citation formatting.

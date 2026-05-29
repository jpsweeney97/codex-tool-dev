---
name: implementation-review
description: >
  Use when reviewing completed code against a plan or spec after planned work:
  "review my implementation", "review my work", "check this against the
  plan/spec", or "did I miss anything". Run an adversarial, evidence-first
  implementation review. Do NOT use for initial code writing, planning,
  architecture discussion, or general code questions.
---

# Adversarial Implementation Review

Review completed work against a plan or spec by trying to prove it wrong. Act as a reviewer building an evidence case, not a collaborator making the code look acceptable.

## Review-Family Routing

Explicit review-family invocation wins, including namespaced plugin forms such
as `review-family:implementation-review`.

- Use this skill for completed code, generated artifacts, PRs, diffs, or commit
  ranges that claim to satisfy a plan, spec, ticket, handoff, or explicit
  requirements.
- This skill wins over `scrutinize`, `adversarial-review`, and
  `pragmatic-review` when the central question is whether an implementation
  satisfies its governing requirements.
- Use `system-design-review` for architecture tradeoffs before implementation,
  `scrutinize` for broad adversarial artifact critique, and `pragmatic-review`
  only for explicit execution-readiness or proof-gate reviews.
- Use `review-reviewer` for explicit supplied-review adjudication,
  `review-claude-claims` for explicit itemized pasted-claim validation, and
  `request-claude-pr-review` for drafting a Claude PR-review prompt.
- If this skill is not the right review-family target, name the better skill
  and switch only when invocation rules allow it; otherwise ask one routing
  question.

## Preconditions And Boundaries

Requires:

- `Spec / plan`: intended behavior, requirements, and constraints.
  - Check: identify the exact source path, ticket, PR description, commit note, handoff, or user-provided text. If only the implementation or an implementation summary is available, the spec is missing.
- `Implementation`: code or artifacts that claim to satisfy the spec.
  - Check: identify the exact PR, commit range, diff, changed files, generated artifacts, or explicit paths under review, and confirm they are readable.
- `Scope boundary`: changed files, PR diff, commit range, or explicit target.
  - Check: record the selected scope authority from the order below. When the target is in a git repository, record repo root, base/ref, current branch, and `HEAD` when applicable.

If the spec or implementation is missing, stop and ask for it. Do not infer the spec from the implementation.

If scope is missing, use the first available authority in this order:

1. Explicit user target: named files, artifacts, PR, commit, commit range, or review boundary from the current request.
2. PR metadata: PR base/head refs and changed files.
3. Commit range: explicit `base..head`, recorded with current `HEAD`.
4. Branch-vs-base diff: current branch against its declared base, recorded with repo root, base ref, and `HEAD`.
5. Local working tree: staged, unstaged, and untracked files, recorded with repo root and `HEAD`.

Treat unchanged files as context unless the selected authority includes them. Do not use an author summary as the scope authority when a PR, diff, commit range, or explicit path is available. If no scope authority exists, stop and ask for the review target.

Read-only boundary: do not edit files, stage changes, commit, push, delete, migrate data, deploy, or run destructive commands unless the user explicitly asks for that separate action.

Verification boundary: run only safe, relevant commands. If a useful command may mutate state outside normal test/build artifacts, ask first and list the claim that remains unverified if skipped.

Higher-priority safety, destructive-action, and `.agents/AGENTS.md` root-cause-analysis checkpoints still apply; if a checkpoint blocks deeper investigation, mark the affected claim `unverified` and state which checkpoint blocked it.

## Stance

- Treat the implementation as unproven until code evidence shows it satisfies the spec.
- Try to falsify each requirement before you allow yourself to say it is satisfied.
- Separate `observed`, `inferred`, and `unverified` statements.
- Refuse to mentally repair broken logic. Review the code that exists, not the code the author probably meant.
- Prefer direct language. Say `this violates the spec because ...`, not `you may want to consider ...`.
- Allow zero findings only after the evidence gate passes.

## Mandatory Workflow

Follow the steps in order. Do not jump to the verdict.

### 1. Build Ledgers

Create two inventories:

- `Requirements ledger`: every explicit requirement from the plan or spec.
- `Changed-area ledger`: every changed file, function, class, endpoint, command, or user flow.

For each requirement, record an ID, spec source, status, code evidence, and falsification attempt. Use only `satisfied`, `violated`, `unverified`, or `not-applicable`. Mark `not-applicable` only when the requirement is truly outside scope, and explain why.

For each changed file or flow, record an ID, changed area, linked requirements, failure modes checked, evidence, and residual risk.

### 2. Falsify Requirements

For every requirement in the ledger:

1. State the easiest way this requirement could be violated
2. Inspect the relevant code path line by line
3. Record the best evidence for and against compliance
4. Assign the status based on evidence, not intuition

Burden of proof:

- `satisfied`: spec evidence and code evidence exist, and the falsification attempt failed.
- `violated`: code contradicts the requirement, omits it, or satisfies only a weaker version.
- `unverified`: available evidence cannot prove correctness.
- `not-applicable`: the requirement is real but outside the declared scope.

Do not treat passing tests, naming, comments, or apparent intent as enough to mark `satisfied` without code evidence.

### 3. Attack Changed Areas

For each changed area, check relevant failure modes: input validation, control flow, state/concurrency, trust boundaries, operational behavior, and consistency with existing patterns.

Record the strongest failure story checked for each area, even when it does not produce a finding.

### 4. Challenge The Plan

Check whether the plan/spec is ambiguous, unsafe, or incomplete. Record plan findings separately from implementation findings. If the spec is ambiguous, use the most conservative reasonable interpretation and state it.

### 5. Record Verification

Record commands, manual checks, probes, skipped verification, skip reasons, and claims left `unverified`. Passing tests support claims; they do not replace spec and code evidence.

### 6. Write Findings

Write findings only after ledgers, failure-mode checks, plan challenge, and verification record exist.

Each finding must include type (`implementation`, `plan`, or `unverified`), severity, spec expectation, observed behavior, evidence, consequence, and fix or investigation.

## Bounded Review Mode

Use bounded review mode when the spec, diff, or runtime surface is too large for one complete pass.

In bounded mode:

1. State the reviewed subset before findings.
2. Review the highest-risk requirements and changed areas first.
3. Mark omitted requirements, files, flows, and runtime checks as `unverified`.
4. Do not return `Ship` or a zero-findings verdict.
5. Give the next slice required for a complete verdict.

Bounded mode is not a shortcut to ignore inconvenient scope.

## Evidence And Severity

Evidence rules:

- Correctness claim: cite spec source and code location.
- Violation claim: cite code location and failure mechanism.
- Inference: label it and cite the observation behind it.
- Unknown: label it `unverified`.

Never use intent, comments, naming, test existence, prior trust, or similar code as substitutes for evidence.

Use only these severities:

- `blocker`: violates a material requirement, creates security/data-loss/runtime failure, or leaves a material requirement unverified.
- `should-fix`: violates a requirement or important plan constraint with bounded blast radius.
- `note`: non-blocking issue that does not change the verdict but should be tracked.

Escalate across auth, data integrity, destructive actions, billing, migration, release, or cross-user boundaries. Do not use `nit`, `minor`, or `style` for spec violations.

## Verdict Taxonomy

Use only these verdicts:

- `Blocked`: at least one `blocker`; any material requirement is `violated`; any material requirement is `unverified` in a full review; destructive, security, data-loss, migration, release, or cross-user behavior lacks required evidence; or the evidence gate failed.
- `Partial review only`: bounded review mode was used; the requested scope was not fully inspected; omitted requirements, changed areas, runtime checks, or dependencies remain; or the review was stopped by a higher-priority checkpoint.
- `Ship`: zero blockers; no material requirement is `violated` or `unverified`; the evidence gate and zero-findings gate pass; the strongest realistic counterexamples were attempted and documented; and verification gaps are either non-material or explicitly accepted as residual risk.

If more than one verdict could apply, choose the first matching verdict in this order: `Blocked`, `Partial review only`, `Ship`.

## Output Format

Return findings first, then evidence.

Required sections:

1. `Implementation Review: [target]`
2. `Findings` — implementation, plan, and unverified findings, severity-ordered. If none, say `No findings`.
3. `Review Scope` — spec/plan, code, and boundary reviewed.
4. `Requirements Ledger` — ID, requirement, status, spec source, code evidence, falsification attempt.
5. `Changed-Area Ledger` — ID, area, linked requirements, failure modes, evidence, residual risk.
6. `Verification Performed / Not Performed`
7. `Unverified Areas`
8. `Verdict` — blocker count, verdict, highest-risk area, strongest failed attack attempt, plan gaps.

Each finding must include location, finding type, spec expectation, observed behavior, evidence, consequence, and fix or investigation.

If using bounded review mode, add `Bounded Review Scope` before `Findings` and use `Verdict: Partial review only`.

Read [examples](examples/review-findings.md) only when you need a concrete findings-first template or examples of strong and weak findings.

## Evidence Gate

Do not issue a final verdict until every item passes:

- [ ] List every explicit requirement from the spec or plan in the Requirements Ledger
- [ ] Account for every changed file or changed flow in the Changed-Area Ledger
- [ ] Record a status for every requirement
- [ ] Cite spec evidence and code evidence for every `satisfied` requirement
- [ ] Record at least one falsification attempt for every changed area
- [ ] Record verification performed and verification not performed
- [ ] Mark every hidden dependency or unexecuted runtime assumption as `unverified`
- [ ] Tie every implementation finding to a requirement or failure mode
- [ ] Tie every plan finding to an ambiguity, unsafe instruction, or incomplete requirement
- [ ] Use only `blocker`, `should-fix`, or `note` severity
- [ ] State the blocker count, even if zero

Apply this additional gate before returning `Ship` or a zero-findings review:

- [ ] No material requirement is `violated`
- [ ] No material requirement is `unverified`
- [ ] The strongest realistic counterexamples were attempted and documented
- [ ] The review contains no reassurance language such as `looks good`, `seems fine`, or `probably correct`

If any gate item fails, continue reviewing. Do not soften the verdict to compensate.

## Red Flags And Troubleshooting

Stop and re-review if any of these happen:

- You want to summarize before you have built the ledger
- You marked `satisfied` because the intent was obvious
- You used tests as the primary proof of correctness
- You found only plan-level issues and no implementation-level checks
- You skipped failure-mode analysis because the code was small
- You wrote a clean verdict without documenting failed attack attempts
- You are tempted to say `LGTM`, `looks solid`, or `well implemented`

If scope is too large, use bounded review mode. If the spec is ambiguous, record a plan finding and review against the conservative interpretation. If verification was not run, list the skipped check and mark affected claims `unverified`. If behavior depends on an uninspectable library, service, or runtime, mark the affected branch `unverified` unless the calling code handles bad behavior. If you wrote the original plan, spend extra attention on omitted edge cases and vague acceptance criteria.

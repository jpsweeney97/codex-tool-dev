---
name: implementation-review
description: "Use when reviewing completed code, generated artifacts, PRs, diffs, or commit ranges against a governing plan, spec, ticket, handoff, or explicit requirements. Do not use for initial code writing, planning, architecture discussion, general code questions, first-pass artifact scrutiny, or review of agent skill contracts."
---

# Adversarial Implementation Review

Review completed work against a plan or spec by trying to prove it wrong. Act as a reviewer building an evidence case, not a collaborator making the code look acceptable.

## Review-Family Routing

Explicit review-family invocation (including namespaced forms such as `review-family:implementation-review`) wins. This skill wins — including over `scrutinize` — when the central question is whether completed code, generated artifacts, a PR, diff, or commit range satisfies its governing plan, spec, ticket, handoff, or explicit requirements:

- Architecture tradeoffs before implementation → `system-design-review`; broad adversarial critique or execution-readiness review before implementation → `scrutinize`.
- Agent skill or skill-support target → `scrutinize-skill`.
- Explicit supplied-review adjudication or pasted-claim checks → `review-reviewer`.
- Otherwise-wrong lane: name the better skill; if invocation rules bar switching, ask one routing question.

## Preconditions And Boundaries

Requires:

- `Spec / plan`: intended behavior, requirements, and constraints.
  - Check: identify the exact source path, ticket, PR description, commit note, handoff, acceptance map, or user-provided text. If only the implementation or an implementation summary is available, the spec is missing.
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

Read-only boundary: do not edit files, stage, commit, push, delete, sync, publish, or implement fixes unless the user explicitly asks for that separate action; the same gate covers migrating data, deploying, and running destructive commands.

Verification boundary: run only safe, relevant commands. If a useful command may mutate state outside normal test/build artifacts, ask first and list the claim that remains unverified if skipped.

Higher-priority safety, destructive-action, and repo-instruction checkpoints still apply; if a checkpoint blocks deeper investigation, mark the affected claim `unverified` and state which checkpoint blocked it.

## Stance

- Treat the implementation as unproven until code evidence shows it satisfies the spec.
- Try to falsify each requirement before you allow yourself to say it is satisfied.
- Separate `observed`, `inferred`, and `unverified` statements.
- Refuse to mentally repair broken logic. Review the code that exists, not the code the author probably meant.
- Prefer direct language. Say `this violates the spec because ...`, not `you may want to consider ...`.
- Allow zero findings only after the evidence gate passes.

## Mandatory Workflow

Follow the steps in order. Do not jump to the verdict.

Before building the ledgers, size and shape the target: an oversized or bundled diff — or a pass the caller narrowed to part of the change — may call for Bounded Review Mode or a `Split required` verdict (below) rather than a full pass.

### 1. Build Ledgers

Create two inventories:

- `Requirements ledger`: every explicit requirement from the plan or spec. When the spec is an `acceptance-map` artifact, each acceptance check is a ready-made requirement — carry its check ID into the ledger and treat its `Passes when` clause as the satisfaction criterion.
- `Changed-area ledger`: every changed file, function, class, endpoint, command, or user flow.

For each requirement, record an ID, spec source, status, code evidence, and falsification attempt. Use only `satisfied`, `violated`, `unverified`, or `not-applicable`. Mark `not-applicable` only when the change under review — the whole change, not only the reviewed slice — does not reach the requirement, and explain why; a requirement the change implements or touches in files outside a caller-narrowed slice is `unverified`, not `not-applicable`.

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
- `not-applicable`: the requirement is real but the change under review — the whole change, not only the reviewed slice — does not reach it. A requirement the change implements or touches in files outside a caller-narrowed slice is `unverified`.

Do not treat passing tests, naming, comments, or apparent intent as enough to mark `satisfied` without code evidence.

### 3. Attack Changed Areas

For each changed area, check the base failure modes: input validation, control flow, state/concurrency, trust boundaries, operational behavior, and consistency with existing patterns.

Then run the surface lenses wherever the change touches their surfaces. Read [references/review-lenses.md](references/review-lenses.md) at this step, before running any lens — it carries each lens's full protocol, boundaries, and refutation guards; this index only names the lenses and their trigger surfaces:

- `Error suppression`: empty or broad catches, swallowed errors, failure-masking defaults or fallbacks.
- `Test adequacy`: tests changed or new behavior needs them — judged by a surviving mutation, not coverage.
- `Comment and docstring accuracy`: comments or docstrings changed or describe changed code.
- `Resource caps`: the change parses, decompresses, fetches, or loops over attacker-influenced input.
- `Performance`: the change adds per-row I/O, an unbounded fetch or materialization, or super-linear work under ordinary load.
- `SQL and data access`: the change builds or alters a query, ORM call, raw SQL, or schema migration.
- `Concurrency`: the change introduces or alters shared mutable state, locks, async coordination, or check-then-act.
- `Retry-safety and idempotency`: the change adds or alters a state-changing endpoint or a side effect behind a retry.
- `Accessibility`: the change adds or alters rendered UI.
- `Supply-chain provenance`: an agent-authored diff introduces a new external dependency.
- `Orphaned code`: the change replaces or removes a code path.

Record the strongest failure story checked for each area, even when it does not produce a finding.

The surface lenses add depth on the surfaces they name; they never replace the base failure-mode pass or the open hunt for the bespoke, business-logic, or auth-specific bug. A clean sweep of every triggered lens does not discharge a changed area — the strongest failure story for it may be one no lens names.

Apply the evidence burden to findings, not only to compliance: raise a finding only when code evidence shows the failure is real. Do not raise findings for:

- Code that superficially resembles a bug but is correct on inspection — confirm the failure actually occurs before flagging it.
- Issues a linter, typechecker, compiler, or CI run would catch — missing or wrong imports, type errors, formatting — unless a requirement explicitly demands them. Assume those checks run separately; do not reproduce them here. (Whether a *new, agent-introduced* dependency belongs at all — distinct from whether it resolves — is the supply-chain provenance check above, not this exclusion. A replaced code path's now-unreferenced route, config key, component, or constant — objects lint cannot see — is the orphaned-code lens, likewise not this exclusion.)
- Repo-instruction violations explicitly silenced in the code, such as a lint-ignore comment that names the rule.

For a security-relevant finding, name the attacker who controls the input and the victim who is harmed:

- Refute it when the only victim is the attacker acting on their own machine or data; keep it when a legitimate user or tenant can reach other users, tenants, shared infrastructure, or server-side resources.
- Do not apply that attacker-equals-victim refutation to SSRF or other outbound-network sinks, to data-exposure findings, or to agent capability gates — permission hooks, command allow/denylists, workspace path jails — where the model is the attacker and the user is the victim.
- Hold a finding whose sink sits outside the changed lines to a stricter bar: name the specific changed line that enables it, or drop it.

### 4. Challenge The Plan

Check whether the plan/spec is ambiguous, unsafe, or incomplete. Record plan findings separately from implementation findings. If the spec is ambiguous, use the most conservative reasonable interpretation and state it.

### 5. Record Verification

Record commands, manual checks, probes, skipped verification, skip reasons, and claims left `unverified`. Passing tests support claims; they do not replace spec and code evidence.

### 6. Write Findings

Write findings only after ledgers, failure-mode checks, plan challenge, and verification record exist.

Each finding records its type (`implementation`, `plan`, or `unverified`) and severity, plus the full field set defined under Output Format.

## Bounded Review Mode

Use bounded review mode when the spec, diff, or runtime surface is too large for one complete pass. In bounded mode, state the reviewed subset before findings, review the highest-risk surface first, mark omitted areas `unverified`, give the next slice needed for a complete review, and do not issue a full-clearance verdict for the full target (do not return `Ship` or a zero-findings verdict; here the omitted areas include requirements, files, flows, and runtime checks). A review whose scope was narrowed externally — a file set narrower than the change, an assigned lens or panel seat, or sampled coverage — is also a bounded review: state the subset, scope the verdict to it, and leave `Ship` unissued.

When a target is too large for one pass, judge *why* before choosing the verdict. A coherent change that is merely large — reviewable in slices that each clear on their own — gets the highest-risk slice now and a `Partial review only` verdict naming the next slice. Reserve a `Split required` verdict (see Verdict Taxonomy) for a target that bundles genuinely independent concerns whose interleaving defeats reliable review as a unit — a diff mixing a refactor, a behavior change, and a migration, or one large only because several separable changes shipped together. Then decline full clearance and name the concrete seams that divide it into independently-reviewable units, each cut along a real boundary of concern, requirement, risk surface, or dependency layer — not an arbitrary size or file slice of one cohesive change. This judges shape, not a line count: a uniform codemod, a rename, or one cohesive feature is a single reviewable unit however large and stays `Partial review only`. Name seams only when you can find real ones; a too-large change you cannot cut along distinct concerns stays `Partial review only`. Verdict choice in bounded mode follows the precedence order under Verdict Taxonomy.

Bounded mode is not a shortcut to ignore inconvenient scope.

## Evidence And Severity

Evidence rules:

- Correctness claim: cite spec source and code location.
- Violation claim: cite code location and failure mechanism.
- Inference: label it and cite the observation behind it.
- Unknown: label it `unverified`.

Never use intent, comments, naming, test existence, prior trust, or similar code as substitutes for evidence.

Use only these severities:

- `blocker`: violates a material requirement, creates security/data-loss/runtime failure, or leaves a material requirement unverified — except a requirement unverified only because bounded review mode omitted it from the reviewed subset, which carries `unverified` status (in the ledger and `Unverified Areas`), not a `blocker` finding.
- `should-fix`: violates a requirement or important plan constraint with bounded blast radius.
- `note`: non-blocking issue that does not change the verdict but should be tracked.

Escalate across auth, data integrity, destructive actions, billing, migration, release, or cross-user boundaries. Do not use `nit`, `minor`, or `style` for spec violations.

## Verdict Taxonomy

Use only these verdicts:

- `Blocked`: at least one `blocker`; any material requirement is `violated`; any material requirement is `unverified` in a full review; destructive, security, data-loss, migration, release, or cross-user behavior lacks required evidence; or the evidence gate failed.
- `Partial review only`: bounded review mode was used; the requested scope was not fully inspected; omitted requirements, changed areas, runtime checks, or dependencies remain; or the review was stopped by a higher-priority checkpoint.
- `Split required`: the change bundles genuinely independent concerns whose interleaving defeats reliable review as a unit, and you named concrete split seams cut along real boundaries — concern, requirement, risk surface, or dependency layer — not size slices of one cohesive change. Distinct from `Partial review only` — that is a coherent target inspected incompletely this pass (the next slice continues the same review); `Split required` is a mis-shaped target where no clearance verdict is trustworthy until the author restructures it (split along the named seams, then re-review). Use only when you can name the seams; a merely-large but cohesive change stays `Partial review only`.
- `Ship`: zero blockers; no material requirement is `violated` or `unverified`; the evidence gate and zero-findings gate pass; the strongest realistic counterexamples were attempted and documented; and verification gaps are either non-material or explicitly accepted as residual risk.

If more than one verdict could apply, choose the first matching verdict in this order: `Blocked`, `Split required`, `Partial review only`, `Ship` — a `blocker` found in the reviewed slice of a bounded pass renders `Blocked`, scoped to the slice, and is never hidden behind an incomplete-pass label.

## Re-Review

The verdicts above create second passes — `Blocked` → fix → second pass, `Split required` → restructure → re-review per split unit — and a requested second look after fixes is the same shape. A re-review is a fresh evidence pass over the live artifact, not an audit of the fix description.

- Verify claimed fixes against the live artifact and its diff, never against the description of them.
- Treat prior findings and prior ledger rows as hypotheses to re-earn, not conclusions to defend. A `satisfied` row carried forward from an earlier pass keeps its status only after its code evidence is re-verified against the live artifact: a fix can move or invalidate the lines the row cites, and a spec-derived ledger looks complete either way. A carried-forward row whose evidence no longer holds reverts to `unverified` until re-earned.
- Hunt for defects the fix introduced, not only compliance with the earlier findings; credit exactly what held.

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
8. `Verdict` — blocker count, verdict, highest-risk area, strongest failed attack attempt, plan gaps. When the verdict is `Split required`, list the named split seams.

Each finding must include location, finding type (`implementation`, `plan`, or `unverified`), severity, spec expectation, observed behavior, evidence, consequence, and fix or investigation.

If using bounded review mode, add `Bounded Review Scope` before `Findings` and choose the verdict by the precedence order — `Verdict: Partial review only` unless an in-slice `blocker` renders `Blocked`, scoped to the reviewed slice, or the target is mis-shaped for review and you named the split seams (`Verdict: Split required`).

Read [examples](examples/review-findings.md) only when you need a concrete findings-first template or examples of strong and weak findings.

When a `note`, `should-fix`, or `blocker` finding should become a tracked issue rather than only living in this review, name `/triage` or `$triage` as the lane to file it — one issue per finding, classified there — and stop; implementation-review stays read-only and does not open issues itself.

## Evidence Gate

Do not issue a final verdict until every item passes. Each item names the section that owns it; the owning section's full rule governs:

- [ ] Ledgers complete per step 1: every explicit requirement listed with a status, every changed file or flow accounted for
- [ ] Every `satisfied` status carries the spec-plus-code evidence step 2's burden of proof demands — carried-forward rows re-earned against the live artifact per Re-Review
- [ ] Every changed area records a falsification attempt — step 3's strongest failure story
- [ ] Verification performed and not performed recorded per step 5
- [ ] Every hidden dependency or unexecuted runtime assumption marked `unverified`
- [ ] Every finding tied to its source: implementation findings to a requirement or failure mode, plan findings to a step-4 ambiguity, unsafe instruction, or incomplete requirement
- [ ] Severity and blocker-count discipline hold per Evidence And Severity and Output Format: the three severities only, blocker count stated even if zero

Apply this additional gate before returning `Ship` or a zero-findings full-clearance review — not a bounded `Partial review only` or `Split required` verdict, which carry the bounded-mode discipline instead. The `Ship` conditions themselves live in Verdict Taxonomy; verify them there, plus one check of the review prose itself:

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
- You ran the surface lenses, found nothing, and wrote a clean verdict — without the open base-failure-mode attack and the bespoke-, business-logic-, or auth-bug hunt on the logic no lens names
- You are tempted to say `LGTM`, `looks solid`, or `well implemented`

If scope is too large or the caller narrowed it to part of the change, use bounded review mode. If the spec is ambiguous, record a plan finding and review against the conservative interpretation. If verification was not run, list the skipped check and mark affected claims `unverified`. If behavior depends on an uninspectable library, service, or runtime, mark the affected branch `unverified` unless the calling code handles bad behavior. If you wrote the plan or the implementation, disclose it in `Review Scope` and spend extra attention on omitted edge cases and vague acceptance criteria.

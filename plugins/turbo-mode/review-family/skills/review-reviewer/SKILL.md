---
name: review-reviewer
description: >
  Use only when the user explicitly invokes `$review-reviewer` to review,
  adjudicate, or avoid rubber-stamping a supplied review, including PR review
  feedback. Infer the original target from the review and immediate context,
  read that target fresh, then produce independent issues, verdicts on each
  review claim, missed issues, verification gaps, and an aggregate review
  judgment. Do not use for first-pass artifact reviews, generic scrutiny,
  implementation reviews, basic claim extraction, natural-language review
  requests, or follow-up fixes.
---

# Review Reviewer

Adjudicate another review without rubber-stamping it. Treat the supplied review
as allegations to test, not as authority or as an enemy to defeat.

## Boundaries

- Explicit-only: use this skill only when invoked as `$review-reviewer`. Do not
  silently route natural-language requests here while `agents/openai.yaml` has
  `allow_implicit_invocation: false`.
- Required input: the supplied review. Do not require the user to also provide a
  target path, PR, spec, or artifact; infer the target from the review and
  immediate conversation context.
- Non-trigger: ordinary critiques, first-pass reviews, implementation reviews,
  "scrutinize this", "be adversarial", "check whether this review is right"
  without `$review-reviewer`, basic claim extraction, or implementation follow-up
  without a supplied review to adjudicate.
- Relationship to `$review-claude-claims`: use this skill for second-pass
  review adjudication plus bounded independent target assessment. Use narrower
  claim-review skills only when the user asks for itemized claim validation
  against a current snapshot without the broader review-reviewer packet.
- Default to read-only. You may inspect files, diffs, git metadata, PR metadata,
  docs, and run bounded non-mutating checks directly tied to the inferred
  target, a disputed claim, or a bounded independent or missed issue. Do not
  edit files, stage, commit, push, delete, install dependencies, sync state,
  create tickets, run broad test suites, or implement fixes unless the user
  explicitly widens scope after the adjudication.
- Stop after the adjudication packet by default. Include terse dispositions and
  next actions, but do not continue into fixes.

## Review-Family Routing

Explicit review-family invocation wins, including namespaced plugin forms such
as `review-family:review-reviewer`.

- Use this skill only when explicitly invoked to adjudicate a supplied review,
  including PR review feedback, and to produce an independent bounded target
  assessment plus verdicts on the review's claims.
- Use `review-claude-claims` instead for narrower itemized claim validation
  against a current snapshot without the broader independent assessment and
  review-judgment packet.
- Use `implementation-review` for completed code against a plan/spec,
  `scrutinize` for first-pass adversarial artifact critique,
  `system-design-review` for architecture tradeoffs, and
  `request-claude-pr-review` for drafting a Claude PR-review prompt.
- If the user asks in natural language whether a review is right without
  invoking this skill, do not silently run the full packet; answer normally or
  ask whether they want `$review-reviewer`.

## Anti-Anchoring Workflow

1. If no review text was supplied, output `missing-review`, ask for the review,
   and stop. Do not infer a review from surrounding chatter.
2. Run a target-resolution prepass over the supplied review. Record locator
   facts only: file paths, PR numbers, review or comment URLs, branch names,
   commit SHAs, doc titles, issue IDs, quoted headings, artifact names, or
   explicit target descriptions. Put those locator facts in `Target Provenance`
   before writing any claim assessment. This is an anchoring mitigation, not a
   pristine blind read: the review has been seen, so independence must be shown
   through target-first evidence and recorded sequencing.
3. Use immediate conversation context, attached files, current repo/branch, and
   explicitly mentioned PRs or paths only as locator evidence. If more than one
   plausible target remains, output `needs-target` rather than guessing.
4. Resolve and read the inferred target fresh. For PR reviews, bounded context
   fetches are allowed when the review points to a PR, review, or comment:
   relevant PR metadata, diff hunks, review comments, thread resolution state,
   and commit SHAs needed for provenance. Do not broaden into full CI triage,
   full PR review, or implementation.
5. Record target provenance, including multiple targets when present. For PRs,
   use a dual boundary when recoverable: the review snapshot for truth verdicts
   and the current PR head for disposition. If the original review snapshot is
   unavailable after available non-mutating recovery checks, historical truth
   claims cannot be `confirmed` or `challenged` from current state alone; mark
   them `needs-verification` and limit any current-state finding to disposition.
   Minimum PR recovery checks: review/comment URL or ID, review timestamp, cited
   commit SHA, PR head/base refs at review time, diff hunk or outdated-thread
   metadata, branch names, and local git history or PR metadata when available.
   Record which checks were attempted.
6. Set a bounded review scope before the independent assessment. If the target is
   broad, inspect only the resolved target surface, locator-touched files or
   hunks, governing requirement sections, and directly adjacent failure modes.
   State the bound in `Target Provenance` and do not imply a complete target or
   PR review unless the inspected scope actually supports that.
7. Form and write the independent assessment before adjudicating the review.
   Include independent issues or state `no independent issues found`, plus the
   basis read.
8. Return to the review. Normalize compound review items into the smallest
   meaningful factual, severity, or remedy claims. Preserve the parent review
   item and assign stable IDs such as `R1`, `R1.a`, and `R1.b`.
9. Adjudicate each normalized claim against inspected evidence. Deliberately
   hunt for high-signal missed issues only in concrete adjacent surfaces:
   claim-touched files or hunks, governing requirement sections, and directly
   adjacent failure modes. Do not inspect unrelated PR files, broaden into full
   PR review, or expand beyond the inferred target unless the user asks.

## Failure Modes

- `needs-target`: target inference failed or found multiple plausible targets.
  List locator facts found and do not adjudicate evidence-dependent claims.
- `missing-review`: no supplied review is present. Ask for the review text and
  stop instead of inferring a review from previous discussion.
- `target-inaccessible`: the target is identifiable but inaccessible. List the
  target locator and attempted read paths or checks. Only review-internal claims
  that can be settled from the supplied review text itself may receive a truth
  verdict. Target-dependent truth claims backed only by reviewer quotations stay
  `needs-verification`; the quote can identify the claim, but it is not artifact
  evidence.
- `anchoring breach`: normal locator exposure is not a breach. If you evaluated,
  summarized, ranked, or adjudicated substantive review claims before reading
  the target, disclose this in `Target Provenance`, still perform the independent
  assessment, and lower confidence in any `Missed Issues` claim. Do not claim a
  fully fresh read.
- If target resolution or target access fails, `Review Judgment` must be
  `under-evidenced`. Do not call the review reliable without independent target
  access.

## Evidence Rules

Evidence lanes:

- `artifact evidence`: the reviewed artifact itself.
- `authority evidence`: governing specs, docs, requirements, or policies the
  artifact cites or is governed by.
- `live evidence`: current code, tests, runtime behavior, repo state, PR state,
  or command output.

Authority order:

- For truth verdicts on PR review claims, prefer the original review snapshot
  when recoverable. If it is not recoverable, historical truth claims are
  `needs-verification`; current state may only support a current disposition.
- For disposition, prefer current PR head or current target state.
- Then use governing specs and docs, then local code/tests/runtime evidence,
  then reviewer quotations as lowest authority unless independently verified.
- When sources conflict, name the conflict and do not upgrade a claim past what
  inspected evidence supports.
- Reviewer quotations can establish what the review claimed, but they cannot
  confirm target-dependent truth without independent artifact, authority, or
  live evidence.

Each claim verdict needs a compact evidence pointer: file/path and line when
available, PR/comment/commit/diff hunk when relevant, command output summary, or
named doc/section for non-code artifacts. If no evidence pointer can be given,
the claim should usually be `needs-verification`, unless it is challenged
because the cited evidence is absent or inaccessible.

## Verdicts And Dispositions

Truth verdict says whether the review claim held at its proper evidence
boundary, usually the original review snapshot for PR comments:

- `confirmed`: the material claim and implied consequence both hold on inspected
  evidence.
- `challenged`: the core fact is wrong, the severity is materially inflated, the
  recommendation does not follow at the truth boundary, or the cited evidence is
  absent or contradicted.
- `needs-verification`: available evidence cannot settle the claim; name the
  exact check or artifact access that would.

Staleness is not itself a truth verdict. If a claim was true at the review
snapshot but no longer applies at current head, keep the truth verdict
`confirmed` and use disposition such as `reject` or `defer` with a stale/current
note. If the review snapshot is unavailable and only current state is known, use
`needs-verification` for historical truth and let current evidence inform only
the disposition.

Disposition says what to do next:

- `act`: address the confirmed issue now.
- `defer`: real issue, but outside the current review scope or not urgent here.
- `reject`: do not act on this review claim.
- `verify-first`: perform the named check before accepting or rejecting it.

Include one terse action sentence with each disposition, such as `act: patch the
spec contradiction`, `reject: no change; review overstates the consequence`,
`verify-first: inspect PR diff against the cited requirement`, or `defer: real
but outside this review's scope`.

For independent and missed issues, use severity separately from disposition:

- `blocker`: likely to break a material requirement, release, data integrity,
  security boundary, or user-visible behavior in the reviewed scope.
- `should-fix`: real issue with bounded impact or meaningful maintenance risk.
- `note`: true observation that does not require immediate action.

## Output

Use this fixed compact packet, in order:

### Target Provenance

- Inferred target(s), source of inference, resolved path/PR/branch/doc, current
  commit or timestamp when available, dirty-state or drift notes when relevant.
- For PRs, include `review snapshot` and `current snapshot` when recoverable.
  If a review snapshot is unavailable, list the snapshot recovery checks
  attempted before using that fallback.
- Include locator facts recorded before target reading, an anti-anchoring note,
  and `Bounded Review Scope` when the target is broader than the inspected
  surface.
- For multiple targets, list `Target A`, `Target B`, etc. Each claim verdict
  should carry its target ID.
- Include `needs-target`, `missing-review`, `target-inaccessible`, or
  `anchoring breach` when applicable.

### Independent Assessment

- Basis read: target artifact(s), authority docs, and live evidence inspected.
- Independent issues found before review adjudication, with evidence pointers,
  severity, and disposition; or `no independent issues found`.

### Review Claim Verdicts

For each normalized claim:

- `ID`: stable parent/child ID such as `R1` or `R1.a`.
- `Target`: target ID or target name.
- `Source`: short pointer to the original review item, avoiding long quotes.
- `Claim`: concise paraphrase without changing scope.
- `Truth Verdict`: `confirmed`, `challenged`, or `needs-verification`.
- `Evidence`: compact evidence pointer and evidence lane.
- `Reasoning`: why the evidence supports the verdict, including whether the
  concern is valid but overstated.
- `Disposition`: `act`, `defer`, `reject`, or `verify-first` plus one terse
  action sentence.

### Missed Issues

High-signal issues the supplied review missed, bounded to the inferred target(s)
and inspected evidence lanes. Include evidence pointers, severity, and
disposition. If none, say so.

### Verification Gaps

Claims, evidence lanes, target snapshots, or authority docs that could not be
settled, with the exact check or access needed.

### Review Judgment

Use one label:

- `reliable`: mostly correct, well-calibrated, and materially complete for the
  inspected target and evidence lanes.
- `partially reliable`: useful but mixed, incomplete, stale in places, or
  unevenly calibrated.
- `overreaching`: repeatedly overstates facts, severity, scope, or remedies.
- `underpowered`: misses important risks, lacks evidence, or avoids necessary
  verification.
- `under-evidenced`: target resolution or access failed, or the evidence base is
  too thin for a reliability judgment.

Add a short rationale covering framing, severity calibration, and coverage.

### Recommended Next Step

One concise next action. Do not provide a detailed implementation plan unless
the user explicitly asks for follow-through.

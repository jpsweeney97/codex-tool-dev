---
name: review-reviewer
description: >
  Use only when the user explicitly invokes `/review-reviewer` or
  `$review-reviewer` to review,
  adjudicate, avoid rubber-stamping a supplied review, or check pasted review
  claims against current evidence. For full review adjudication, infer the
  original target from the review and immediate context, read that target fresh,
  then produce independent issues, verdicts on each review claim, missed issues,
  verification gaps, and an aggregate review judgment. For "check these claims"
  requests, run a Current Claim Check against the current target snapshot. Do
  not use for first-pass artifact reviews, generic scrutiny, implementation
  reviews, basic claim extraction without evidence checking, natural-language
  review requests, or follow-up fixes.
---

# Review Reviewer

Adjudicate another review without rubber-stamping it. Treat the supplied review
as allegations to test, not as authority or as an enemy to defeat.

## Boundaries

- Explicit-only: use this skill only when invoked as `/review-reviewer` or
  `$review-reviewer`. Do not
  silently route natural-language requests here while `agents/openai.yaml` has
  `allow_implicit_invocation: false`.
- Required input: the supplied review, review claims, or pasted claims. Do not
  require the user to also provide a target path, PR, spec, or artifact; infer
  the target from the review, claims, and immediate conversation context when
  possible.
- Non-trigger: ordinary critiques, first-pass reviews, implementation reviews,
  "scrutinize this", "be adversarial", "check whether this review is right"
  without `/review-reviewer` or `$review-reviewer`, basic claim extraction
  without evidence checking,
  or implementation follow-up without a supplied review or claim set to
  adjudicate.
- Packet selection: use full review adjudication when the user asks whether a
  supplied review was reliable, complete, overreaching, underpowered, or
  historically correct. Use Current Claim Check when the user asks to check these
  claims, check review claims, or validate pasted claims item by item against
  current evidence before acting.
- Default to read-only. You may inspect files, diffs, git metadata, PR metadata,
  docs, and run bounded non-mutating checks directly tied to the inferred
  target, a disputed claim, or a bounded independent or missed issue. Do not
  edit files, stage, commit, push, delete, install dependencies, sync state,
  create tickets, run broad test suites, or implement fixes unless the user
  explicitly widens scope after the adjudication.
- Stop after the selected review packet by default. Include terse dispositions and
  next actions, but do not continue into fixes.

## Review-Family Routing

Explicit review-family invocation wins, including namespaced plugin forms such
as `review-family:review-reviewer`.

- Use this skill only when explicitly invoked to adjudicate a supplied review or
  to check pasted review claims against target evidence.
- Run Current Claim Check instead of the full adjudication packet when the user
  asks to check these claims, check review claims, or validate pasted claims item
  by item against current repo, source, PR, doc, or runtime evidence before
  acting.
- Run full review adjudication when the user asks whether the supplied review
  itself was reliable, complete, overreaching, underpowered, stale, historically
  correct, or missing issues.
- Use `implementation-review` for completed code against a plan/spec,
  `scrutinize` for first-pass adversarial artifact critique,
  `system-design-review` for architecture tradeoffs.
- If the user asks in natural language whether a review is right without
  invoking this skill, do not silently run the full packet; answer normally or
  ask whether they want `/review-reviewer` or `$review-reviewer`.

## Full Review Adjudication Workflow

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

## Current Claim Check

Use this packet when `/review-reviewer` or `$review-reviewer` is invoked with a
request to check pasted
claims item by item against current evidence.

Current Claim Check answers: are these claims true enough to act on now? It does
not decide whether a supplied review was historically correct, complete,
reliable, overreaching, or underpowered.

Use the current target snapshot only: current repo, branch, `HEAD`, dirty state,
PR head or diff, named artifact, docs, tests, runtime evidence, and material
evidence gaps. Do not recover or adjudicate an older review snapshot unless the
user asks for full review adjudication. If a claim depends on unavailable
historical state, classify it `Unverified` and name the recovery check.

Workflow:

1. Record `Current Target Snapshot`: `cwd`, repo root or non-repo status, branch,
   `HEAD`, dirty state, PR/diff/base when applicable, named artifact, and
   evidence gaps.
2. Split pasted review text into discrete claims. Give each claim a stable ID
   and preserve a short source locator or short excerpt. Break compound claims
   apart when one part could be true and another false.
3. For each claim, inspect the smallest relevant evidence set: code, tests,
   docs, configs, generated artifacts, PR metadata, command output, runtime
   behavior, or local contracts.
4. Classify each claim as `Valid`, `Invalid`, `Partially valid`, or
   `Unverified`. Do not upgrade a claim past `Unverified` without direct
   evidence.
5. Separately assign severity and disposition. Truth classification does not by
   itself decide priority or implementation scope.
6. End with action buckets: `Act on now`, `Do not act on`, `Needs verification`,
   and `Deferred`.

Current Claim Check classifications are current-snapshot claim labels, not
historical review-truth verdicts. `Valid` roughly corresponds to `confirmed`,
`Invalid` to `challenged`, and `Unverified` to `needs-verification`. Use
`Partially valid` when a real issue exists but the claim overstates scope,
severity, mechanism, or remedy.

Classifications:

- `Valid`: supported by code, tests, docs, contracts, runtime evidence, or PR
  metadata at the current target snapshot.
- `Invalid`: contradicted by the current implementation, tests, docs, contracts,
  runtime evidence, PR metadata, or explicit repo policy.
- `Partially valid`: identifies a real concern, but overstates severity,
  misstates the mechanism, targets the wrong scope, or proposes the wrong fix.
- `Unverified`: plausible, but available evidence is insufficient; needs a
  targeted check before implementation.

For Current Claim Check, use the same severity labels as full adjudication:
`blocker`, `should-fix`, and `note`. Use `none` for `Invalid` claims unless a
separate follow-up is needed.

Disposition says what to do next:

- `act`: address the valid claim now.
- `narrow`: address only the true or in-scope part of a partially valid claim.
- `reject`: do not act on this claim.
- `verify-first`: perform the named check before accepting or rejecting it.
- `defer`: real issue, but outside the current scope or not urgent here.

## Failure Modes

- `needs-target`: target inference failed or found multiple plausible targets.
  List locator facts found and do not adjudicate evidence-dependent claims.
- `missing-review`: no supplied review or claim text is present. Ask for the
  review or claims and stop instead of inferring them from previous discussion.
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
  `under-evidenced` for full review adjudication. Do not call the review reliable
  without independent target access. For Current Claim Check, list the target
  access failure in `Current Target Snapshot`, classify target-dependent claims
  `Unverified`, and put them in `Needs verification`.

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
because the cited evidence is absent or inaccessible. For Current Claim Check,
use `Unverified` instead of `needs-verification`.

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
- `narrow`: address only the true or in-scope part of an overstated current
  claim.
- `defer`: real issue, but outside the current review scope or not urgent here.
- `reject`: do not act on this review claim.
- `verify-first`: perform the named check before accepting or rejecting it.

Include one terse action sentence with each disposition, such as `act: patch the
spec contradiction`, `reject: no change; review overstates the consequence`,
`verify-first: inspect PR diff against the cited requirement`, `narrow: patch
only the in-scope failure`, or `defer: real but outside this review's scope`.

For independent and missed issues, use severity separately from disposition:

- `blocker`: likely to break a material requirement, release, data integrity,
  security boundary, or user-visible behavior in the reviewed scope.
- `should-fix`: real issue with bounded impact or meaningful maintenance risk.
- `note`: true observation that does not require immediate action.

## Full Review Adjudication Output

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
- `Disposition`: `act`, `narrow`, `defer`, `reject`, or `verify-first` plus one terse
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

## Current Claim Check Output

Use this packet instead of `Full Review Adjudication Output` for Current Claim
Check:

### Current Target Snapshot

- `cwd`, repo root or non-repo status, branch, `HEAD`, dirty state, PR/diff/base
  when applicable, named artifact, and evidence gaps.

### Claim Check

For each claim, include:

- `Claim ID`: stable identifier.
- `Source`: short source locator or short excerpt from the pasted claims.
- `Claim`: concise restatement without changing scope.
- `Classification`: `Valid`, `Invalid`, `Partially valid`, or `Unverified`.
- `Severity`: `blocker`, `should-fix`, `note`, or `none`.
- `Evidence`: file/line references, command output summary, PR metadata, runtime
  evidence, docs/contracts, or the reason evidence is missing.
- `Reasoning`: why the evidence supports that classification.
- `Disposition`: `act`, `narrow`, `reject`, `verify-first`, or `defer` with one
  terse action sentence.

### Act On Now

`Valid` or `Partially valid` claims with `blocker` or `should-fix` severity and
`act` or `narrow` disposition.

### Do Not Act On

Claims classified `Invalid`.

### Needs Verification

Claims classified `Unverified`, with the specific check required.

### Deferred

True or partially true claims intentionally outside current scope.

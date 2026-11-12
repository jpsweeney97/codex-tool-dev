---
name: scrutinize
description: "Use when the user explicitly asks for adversarial review, scrutiny, a formal stress test, or a pragmatic or execution-readiness review of a plan, design, draft, argument, decision, code change, handoff, spec, or broad artifact. Do not use for agent skill targets, completed implementation-against-plan review, supplied-review adjudication, architecture-specific system design review, routine review, collaborative editing, or balanced feedback."
---

# Scrutinize

Stance: reject until evidence earns a better verdict. Review the exact target; read referenced files before severity-calibrated judgment.

## Review-Family Routing

Explicit review-family invocation (including namespaced forms such as `review-family:scrutinize`) wins, but a generic invocation does not override target-type handoff to `scrutinize-skill`, `implementation-review`, or `system-design-review`. This skill wins natural-language adversarial requests — "scrutinize", "be brutal", "tear this apart", "reject until proven otherwise" — and execution-readiness reviews, when no narrower target-type lane applies:

- Agent skill or skill-support target → `scrutinize-skill`, even when the user said "scrutinize" (target shapes listed in the Workflow).
- Completed code or artifact against a plan/spec → `implementation-review`, even for an adversarial implementation pass.
- Architecture or system-design lens → `system-design-review`.
- Supplied-review adjudication or pasted-claim checks → `review-reviewer`.
- Otherwise-wrong lane: name the better skill; if invocation rules bar switching, ask one routing question.

## The Review

Lead the reply with the verdict. Then give the findings that carry it, most severe first, each with its evidence and the change it requires. State what you inspected, what you skipped, and the anchor the verdict binds to (commit, version, or date — the datum by which a later reader can tell whether the artifact has changed). Check the premise first: is this solving the right problem? Report a lens, an assumption, or a failure story only when it changed a finding, a severity, or the verdict.

When the user's terminal question is execution readiness — whether the target is ready to execute, build from, implement, or roll out — end with a readiness verdict instead (below).

For a formal stress test — on the user's ask, or for a target that is high-stakes, irreversible, or publication-bound — also show the verdict-driving assumptions, each tagged `validated`, `plausible`, `wishful`, or `unverified`; the most likely failure path and the most damaging quiet one; and a confidence boundary in prose: what was checked, what remains unverified, and what evidence would change the verdict.

## Verdicts

Normal scrutiny verdicts are exactly one of `Reject`, `Major revision`, `Minor revision`, `Defensible`, or `Partial review only`, with severity labels `Critical`, `High`, `Medium`, or `Low`; a canonical token may carry a scoping gloss ("Defensible, not yet optimal"). `Partial review only` means bounded review mode was used: the reviewed subset was judged, the full target was not. If more than one verdict could apply, choose the first matching in this order: `Reject`, `Major revision`, `Partial review only`, `Minor revision`, `Defensible` — a disqualifying finding in the reviewed slice renders its verdict, scoped to the slice, and is never hidden behind an incomplete-pass label. A verdict reports this pass's search, not a certified property of the artifact: `Defensible` and `Ready to Execute` are clearance verdicts, and a clearance verdict claims serious search was exhausted without a disqualifying find — it does not certify soundness, and it expires when the artifact changes. When the target survives scrutiny, say why it survives, then focus on residual risks and failure scenarios; note strengths briefly only after exhausting serious attempts to find weaknesses. When the reviewer rather than the user chose the register — readiness vocabulary, a formal stress test, or declining one on a trigger-matching target — say so in a clause.

On re-scrutiny of a revised target: re-read the live artifact fresh; verify claimed fixes against the artifact and its diff, never the description of them; treat prior findings as hypotheses to re-earn, not conclusions to defend; hunt for new defects, not only compliance with your own required changes; and credit exactly what held. When a valid re-scrutiny finding opens a new structural repair class, mainly polices machinery earlier repairs added, or would change the target's category, name `recheck-investment` (where available) as the next move before prescribing another hardening cycle: this review owns whether the finding is real; that check owns only whether continued investment needs renewed human authorization.

For execution-readiness reviews, replace the normal scrutiny verdict with `Execution Readiness Verdict` and exactly one of:

- `Ready to Execute`
- `Patch Before Implementation`
- `Not Executable Yet`
- `Partial Review Only`

Use `Ready to Execute` only when inspected evidence supports the required proof class and no material readiness blocker remains. Use `Partial Review Only` for bounded passes that cannot inspect the full readiness surface. If more than one readiness verdict could apply, choose the first matching in this order: `Not Executable Yet`, `Patch Before Implementation`, `Partial Review Only`, `Ready to Execute` — a disqualifying blocker found in a bounded pass renders `Not Executable Yet`, and a patchable in-slice gap renders `Patch Before Implementation`, each scoped to the reviewed subset with the uninspected readiness surface named.

## Guardrails

- Review-only default: do not edit files, stage, commit, push, delete, sync, publish, or implement fixes unless the user explicitly asks for that separate action after the review.
- Mixed critique and implementation: finish scrutiny first, stop after the verdict, and wait for explicit follow-through before changing artifacts.
- Self-authored target: if you authored the target — this session or otherwise — disclose it, and treat your own absence claims (`none`, no residual risk, a clearance verdict) with declared extra skepticism.
- Bounded review mode: when the target is too large to inspect completely in one pass, state the reviewed subset before findings, review the highest-risk surface first, mark omitted areas `unverified`, give the next slice needed for a complete review, and do not issue a full-clearance verdict for the full target (do not use `Defensible` or `Ready to Execute`). A review whose scope was narrowed externally — a caller-restricted scope, an assigned lens or panel seat, or sampled coverage — is also a bounded review: state the subset, scope the verdict to it, and leave full-clearance tokens unissued. Verdict choice in bounded mode follows the precedence order defined with each enum.
- Evidence: cite file/line, output, source, or observed behavior for concrete claims; label inference or uninspectable behavior as uncertainty.
- Citation calibration: target-internal contradictions may be reported from the target alone. Any `Critical`, `High`/`High-Risk`, or verdict-driving claim — including the final verdict — that depends on an external citation must read the cited resource; otherwise downgrade the claim to `uncalibrated / citation not inspected`.
- Do not mentally repair broken logic or pad with weak objections.

When required changes or readiness blockers should become tracked issues rather than a chat-only review, name `/triage` or `$triage` as the lane to file them — one issue per finding, classified there — and stop; scrutinize stays review-only and does not open issues itself.

When scrutiny rejects a *position, decision, or argument* — a contested stance, not a code or plan defect — name `steelman` or `$steelman` to build the strongest honest case for it before the user discards it; scrutinize attacks and never advocates.

---
name: keep-green
description: "Use when a change you just made broke lint or tests and you want it driven back to green without thrashing: bounded fix attempts, same-failure and oscillation detection, and escalation of cause-unknown failures. Stops at green — no commit, no done-verdict (closeout-check), not test-first new behavior (tdd), not diagnosing intermittent or cross-component bugs (diagnose)."
---

# Keep Green

Drive a just-made change back to a green lint+test gate through a bounded fix→re-run loop that repairs only what the change broke and leaves pre-existing red reported-not-touched. It stays this small because every stop is a safe handoff (the invariant below): cause-unknown failures escalate to `diagnose`, and the green stop hands to `closeout-check`.

Assumes a change was just made on a branch where edits are already permitted; keep-green inherits, never manages, the repo's branch floor. Invocation: `/keep-green` or `$keep-green`.

## Freeze the gate

Resolve the exact lint+test command once — caller input first, else repo convention (`AGENTS.md` or `CLAUDE.md` documented commands, a Makefile, package scripts, CI). Name it, and run it unchanged every iteration; comparability across runs is load-bearing. Green = lint and test both exit clean on a full run.

If the gate cannot execute or yields no parseable pass/fail (a collection or config error), stop and report — a loop needs a working measure of green.

## The signature

A failure's signature is its test/lint **identity** plus its **normalized error class or message**, with run-to-run noise stripped (timestamps, durations, absolute or temp paths, memory addresses, seeds). Deliberately **not** keyed on `file:line` — a line shift would otherwise read a recurring failure as new. This one definition powers every stop below; keep normalization light.

## The loop

Seed by running the gate; if it is already green, stop with success and zero fixes. While red:

1. Form a confident, change-linked hypothesis for a target failure. If you have none, escalate — blind guessing is itself thrashing.
2. Make the smallest in-scope fix for one root cause (a formatter or autofix bulk-clear counts as one cause).
3. Re-run the full gate.
4. Update the ledger of signatures seen and cleared, and branch on the stops below.

## Stop conditions

These firm refusals are the value.

- **Success** — no in-scope failures remain → stop, hand to `closeout-check`. Report `green` if the full gate is clean; report `in-scope-green` if the in-scope work is done but pre-existing out-of-scope red still fails the full gate.
- **Stall** — a default of 2 consecutive iterations clear no targeted signature, or a targeted signature is seen failing a 3rd time → stop, report STALLED.
- **Same-failure** — a targeted signature survives its own fix (reappears unchanged) → strike (feeds stall).
- **Oscillation** — a previously-cleared signature reappears → strike (feeds stall).
- **Escalate** — any failure with no confident change-linked hypothesis, or that is intermittent/flaky or cross-component → hand to `diagnose` with the ledger; do not investigate inline.

Progress is signature-clearing, never a count. An iteration progresses if at least one targeted signature is now gone; failures newly **unmasked** by a fix do not count against it. Never gate on the size of the red set — "fix one, unmask three" is normal convergence, not thrash. The cap bites on consecutive non-progress, not on total attempts: a change that legitimately broke eight things may take eight clearing iterations. The default cap is a judgment value, overridable at invocation.

## The invariant that licenses a tight loop

GREEN means "lint and test pass on this tree now," confirmed on a full gate run — never "the work is done." Every stop is a safe handoff: no stop stages, commits, creates a branch, masks a failure, or declares the work done — keep-green edits the working tree only, reports the signal, and leaves declaring the work done and landing it to `closeout-check`. Being wrong about a stop therefore costs only an early, evidence-rich handoff — never a bad outcome — which is exactly why the loop can be aggressive and the cap value is non-critical.

## Scope discipline

In-scope = failures attributable to the changed files or behavior. Out-of-scope — pre-existing red, unrelated subsystems, flaky tests — is recorded and surfaced, never fixed. Resolve a genuine "did this predate my change?" ambiguity with one baseline check (the failing test on `HEAD` or a stash) only when the answer changes what you do, not as a per-iteration gate.

## Never cheat the gate

Never reach green by disabling, skipping, deleting, or loosening a test, assertion, or lint rule, or by stripping the change's intent. Updating an assertion to match behavior the change **intentionally** altered is legitimate; neutering a test to dodge a real regression is not. If green is reachable only by defeating the signal, that is a stop-and-report, not a fix.

## Output

Report a labelled packet so a consumer can act on it:

```markdown
Outcome: green | in-scope-green | stalled | escalated
Gate: <the exact lint+test command>
Cleared: <signatures fixed>
Still red: <remaining + which stop fired>
Escalated: <failures handed to diagnose + why>
Out of scope: <pre-existing/unrelated red left untouched>
Files touched: <paths>
Boundary: no commit, no done-verdict
Next move: closeout-check | diagnose <handle> | user decision
```

The signature ledger is the breadcrumb that gives `diagnose` a warm start.

## Fence

- Done-verdict and the single final commit → `closeout-check`; it (and `execute-plan`, `migration-campaign`) can delegate bounded back-to-green repair here before landing.
- Authoring a test to specify new behavior → `tdd`; keep-green never writes one, and reports coverage a fix exposed as missing as a follow-up.
- Mysterious, intermittent, or cross-component failures → `diagnose`, via the Escalate stop with the ledger.

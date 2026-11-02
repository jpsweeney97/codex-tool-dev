---
name: characterization-tests
description: "Use when working code has no tests and a refactor, upgrade, or migration is about to touch it: author a characterization net (golden-master/approval tests) that pins what the code actually does now — bugs included, flagged — taming nondeterminism first, then prove the net works by making a deliberate mutation fail it. Pins current behavior, not correctness. Not for test-first new behavior (tdd), auditing an existing suite (test-trust-audit when available), or doing the refactor itself."
---

# Characterization Tests

The safety net you weave BEFORE changing untested code: pin what it actually does now, prove the net catches change, hand over green. The change itself is someone else's move. Invocation: `/characterization-tests` or `$characterization-tests`.

A pass over one seam of working, untested code that authors a behavior-snapshot net (characterization / golden-master / approval tests): tame nondeterminism first, capture the code's observed behavior as the expected values — bugs included, flagged — run the net green, then prove it detects change by making a deliberate, reverted mutation fail it. The deliverable is the green net plus its proven trigger; the refactor, upgrade, or migration it protects happens after, in its own lane.

## Shape — the pass

- **Pin the seam.** The outermost stable boundary the upcoming change will preserve: a public function, a CLI invocation, an HTTP handler, a file-in/file-out transform. Pin at the seam, not private helpers — a net over internals freezes the implementation and blocks exactly the refactor it exists to enable.
- **Tame nondeterminism FIRST.** Before any capture, find and control what varies between identical runs: timestamps, UUIDs and random IDs, hash/dict ordering, float formatting, locale, concurrency interleaving. Inject clocks and seeds where the seam allows; otherwise normalize outputs in the capture harness (strip or replace the volatile fields). A net captured before taming flakes forever after.
- **Choose inputs by branch, not bulk.** A handful of inputs that reach different branches and edges — empty, boundary, malformed, the weird-but-real production case — beats hundreds of near-duplicates. Name why each input is in the net.
- **Capture actual behavior as expected.** Run the current code; its observed output becomes the assertion — inline expected values or approval/golden files, preferring small, reviewable goldens (a giant unreviewable snapshot is a rubber stamp, not a contract). Where current output looks WRONG, pin it anyway and flag it as a finding — fixing it now changes behavior mid-netting and defeats the net; the fix is follow-up work after the net and the change land. Label the tests as characterization in their names or comments ("pins current behavior, not correctness") so a future reader doesn't mistake a pinned bug for a spec.
- **Run green.** The whole net passes against the unmodified current code.
- **Prove the net — the mutation check, mandatory.** With a clean tree, introduce ONE deliberate behavior change at the seam's implementation — flip a comparison, move a boundary — run the net, and require at least one failure. Revert and PROVE restoration (`git diff --exit-code` on product code; the net files legitimately differ), then require the net green again. Repeat for 2–3 distinct mutations when the seam has distinct behavior regions. A net never seen to fail is decoration. Never commit a mutation; restore on every exit path, including a runner failure mid-proof.

## Output and handover

The committed net — tests, any golden files, the capture harness — plus a short handover: the seam pinned; the inputs and why each is there; the nondeterminism controls applied; pinned-bug findings flagged for follow-up; the mutations that proved the net and what each caught; and the honest boundary — the net detects changes in the behaviors it pins, nothing more. No "behavior fully covered" claim, ever.

## Modes and scope

- One seam per run. Pointed at a whole legacy module, pin the seam the imminent change will cross and say what was left unpinned.
- Tests only. This skill never performs the refactor, upgrade, or migration it enables — hand that to `simplify-code` or the change's own lane, with the net standing as its tripwire.

## Fences

- New behavior, with expectations from an independent source of truth → `tdd`. Characterization deliberately inverts that rule for existing behavior: the running code is the only authority, and the net asserts "unchanged", never "correct" — execution-derived expectations are the point here, not the tautology `tdd` forbids.
- Auditing an existing suite's honesty → `test-trust-audit` where available; once this net lands, that audit is how a later reader checks it hasn't rotted.
- Proving one change once → `verify` / `behavior-smoke-test` where available; this leaves a durable net.
- Mapping INTENDED behavior from a settled spec → `acceptance-map`; this pins ACTUAL behavior from execution, bugs included.

## Done when

- The seam is named and pinned at the boundary the change preserves, not at internals.
- Every nondeterminism source is dispositioned — injected or normalized — before the first capture.
- Every input in the net has a stated reason.
- The net is green against unmodified current code.
- At least one deliberate mutation was observed to fail the net, restoration was proven, and the net is green again.
- Pinned bugs are flagged as findings for follow-up, never fixed mid-netting.
- The handover states the honest boundary; no product-code change survives; nothing pushed.

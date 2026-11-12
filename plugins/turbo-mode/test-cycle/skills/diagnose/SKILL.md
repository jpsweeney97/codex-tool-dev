---
name: diagnose
description: "Use when the user asks to diagnose or debug a problem whose cause is unclear, intermittent, hard to reproduce, resistant to a fix, or spread across components — a software bug, a performance regression, or a non-software target: a household, hardware, appliance, tool, workflow, or AI-behavior problem. Do not use for straightforward implementation, known fixes, quick lookups, obvious single-test failures, code review, post-fix architecture improvement, or medical symptoms; once a code cause is known, locking the fix in test-first belongs to `tdd`."
---

# Diagnose

A discipline for hard problems whose cause is unclear. The target is usually a software bug; the same discipline diagnoses a non-software target — a household, hardware, appliance, tool, workflow, or AI-behavior problem — with the adjustments under Non-software targets.

When the target is a codebase, use the project's domain glossary to get a clear mental model of the relevant modules, and check ADRs in the area you're touching.

## Redact

This skill has you show commands, outputs, and captured artifacts. Redact every secret first: write `<REDACTED>` in its place. Build loops against env vars, so the credential stays in the environment rather than in what you show. Captured artifacts carry auth headers — quote only the lines that carry the signal. If the redacted output is not enough to diagnose the bug, say so and ask the user rather than un-redacting.

## Non-software targets

When the target is not software you cannot run the probes yourself: you direct the diagnosis, and the user is the hands and senses. Every probe is something you write exactly — a question, an observation to make, a test to perform — and the user carries it out and reports back. Write probes for a person's hands, eyes, and ears, not for a machine. Never imply you observed something that was not reported, and say plainly what you have not seen. Evidence arrives however chat allows: descriptions, photos, screenshots, recordings, pasted text, links. Batch independent questions into one message and make each answerable cold.

**Safety boundary.** Hazardous systems — mains electrical beyond plug-level swaps, gas, structural elements, work at height, vehicle safety systems, pressure vessels, suspected mold or asbestos — get diagnosed only to the point of observation, then referred to a professional. Never direct a probe that risks injury. Name the cost of any destructive, irreversible, or expensive probe before asking for it, and get explicit agreement. Medical symptoms in people or animals are out of scope: refer to a clinician or vet.

**Triage — match depth to the problem.** Three calls before the phases:

1. *Lookup or investigation?* If the symptom names a known failure mode with a canonical answer — a compatibility question, a documented limitation, a common fault with an established fix — search, answer, and stop; do not unfold the phases. If the user wants an artifact's quality reviewed rather than an observed failure explained, that is a review, not a diagnosis.
2. *How repeatable?* Repeatable (fails on demand) affords iteration. Semi-repeatable (often, but not on command) affords iteration at a cost. One-shot or costly (every retry drills another hole) must lean on reconstruction and cheap probes. This sets which probes are affordable.
3. *First attempt, or already resisted?* For a first-touch problem, run light: one batched diagnostic interview covering the symptom and how to reproduce it, then ranked hypotheses with the cheapest probe attached. Once any fix has failed — before this conversation or during it — the hard gates apply in full: no hypothesising without an evidence channel, no fix without a discriminating probe implicating the cause, one change at a time, each change verified against the pinned symptom before the next.

Read [references/hands-on-probes.md](references/hands-on-probes.md) for the cost-ranked probe ladder, the physical-world intermittency cause-classes, one-shot reconstruction, and the recurrence tell. The sections below say where a non-software target differs.

## Reproduce first

Do not hypothesise or fix until you have a repeatable way to make the failure show: a failing test, a script against the running system, a CLI call with a fixture, a replayed trace, or, for an intermittent failure, a loop that raises the failure rate until it can be worked against. Confirm that it shows the failure the user described, not a different one nearby, and shrink it to the smallest case that still fails. When a human must act in the loop, drive them with `scripts/hitl-loop.template.sh`.

For a non-software target the repeatable signal is an evidence channel the user operates: a quick trigger plus a crisp, observable pass or fail they can repeat and report. Pin the symptom precisely: a screw that pulls out, spins in place, or snaps is three different problems with three different causes.

When you cannot build a repeatable reproduction, stop and say so. List what you tried, and ask the user for access to an environment that reproduces it, a redacted captured artifact, or permission to add temporary instrumentation; for a non-software target, hands-on time, a captured artifact, or agreement to a costlier probe. Do not move on to hypotheses without it.

## Find the cause

State each hypothesis with the prediction it makes, and change one variable at a time. Show the ranked hypotheses to the user before testing when they are present: they often know something that re-ranks the list. Tag any temporary debug logging with a unique prefix so one search removes it.

## Fix

Fix where the bad value or wrong behavior starts, not where the symptom showed. Once the cause is known, locking the fix in test-first belongs to `/tdd` (or `$tdd`): hand it the minimised reproduction. For a non-software target, verify against the original pinned symptom: the user restores the full scenario and reports. For a one-shot problem, name the earliest observable sign that it is back.

If a fix fails, return to the hypotheses with the new evidence instead of stacking another change on top. When about three fixes have failed, especially when each one reveals a new problem somewhere else, the frame is wrong: for code, the architecture; for a non-software target, a different problem category, access or expertise the chat lacks, or a professional's job. Stop and raise that with the user before attempting a fourth.

## Before declaring done

- The original reproduction no longer fails.
- Temporary instrumentation and throwaway prototypes are removed (`trash`, never `rm`).
- The confirmed cause is stated in the commit or PR message. For a non-software target, everything changed for diagnosis is restored and the cause is recorded where the user keeps such notes.
- Search for the same defect elsewhere: `bug-epidemiology` (where available) hunts copies, the same API misused in other places, and parallel implementations with the same flaw.

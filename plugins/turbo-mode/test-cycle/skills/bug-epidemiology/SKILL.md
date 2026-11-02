---
name: bug-epidemiology
description: "Use at the moment a bug's cause is confirmed — after `diagnose` or any ad hoc fix, before closeout — to hunt the defect's twins: reduce it to a structural signature, probe at escalating abstraction, and render a confirmed/cleared co-instance table. Do not use to find the original cause (`diagnose`), to verify or regression-test the original fix, for a repo-wide debt sweep (`tech-debt-scan`), or to sweep a many-site change — beyond three trivial twins the decided change routes to `migration-campaign` or files via `triage`."
---

# Bug Epidemiology

A confirmed defect is almost never a unit — it is a sample from a population: copy-paste clones, the same API misused the same way elsewhere, a parallel implementation with the parallel flaw. The ticket closes the moment the user's instance is fixed, so nobody ever commissions the twin hunt. This skill fires in the gap after cause-is-known and treats the bug as patient zero, hunting co-instances before the session declares victory on n=1.

Invocation: `/bug-epidemiology` or `$bug-epidemiology`; also fires unprompted at its seam — the bug's cause has just been confirmed (after `diagnose`, or after any ad hoc fix), the fix is decided or applied, and closeout is next.

## 1. Reduce the defect to a signature

State the structural pattern minus its incidental identifiers — not `getUserProfile drops err at line 40` but `callback err param ignored`; not `parseEventDate compares naive to aware` but `tz-naive datetime compared to aware`. Other examples: `TOCTOU between stat and open`; `collection mutated while iterated`; `unescaped user string interpolated into query`. The signature is what a twin shares with patient zero; names, paths, and literals are what it does not. If the signature cannot be stated without the incidental identifiers, the cause is not confirmed yet — that is still `diagnose`'s work, not this skill's.

## 2. Compose 2–3 probes at escalating abstraction

1. **Exact idiom** — grep for the near-verbatim pattern: catches copy-paste clones.
2. **Structural** — `ast-grep` or `semgrep` when already present in the environment; otherwise a looser grep tolerant of renames, argument order, and whitespace. Do not install tools for this; degrade and say which rung actually ran.
3. **Population** — enumerate every place the signature *could* live and sweep it: all call sites of the same API, all implementations of the same interface, all descendants of the same copied template.

## 3. Run, rank, read

Run the probes and merge the hits. Rank by structural similarity to the confirmed instance, then read the top hits and give each a verdict: **confirmed** (the flaw is present — one line of evidence) or **cleared** (the pattern is present, the flaw is not — one line of why). Hits you do not read stay **unread**. An unread hit is never a cleared hit; the honesty of the table is the whole product.

## 4. Render the table and route

```text
Co-instances of: <signature>   (patient zero: <file:line>)
  <file:line>  confirmed  <one-line evidence>
  <file:line>  cleared    <one-line reason>
  <file:line>  unread     <why reading stopped here>
Probes run: <exact grep | structural (tool) | population sweep of <api/interface>>
Routing: <inline fix | migration-campaign | triage | closeout report>
```

Routing is part of the contract, in both directions:

- **Three or fewer confirmed twins, each trivially fixed by the same decided change**: fix them inline, under the same verification as patient zero.
- **More than three, or any non-trivial twin**: the cap is a hold, not a formality — do not keep fixing sites past it in this run, even under a receiving lane's discipline. Hand the decided change plus this table to `migration-campaign` (where available) — the table is exactly the site inventory that lane consumes — or file the population via `triage` (or `$triage`); where neither exists, leave the table in the closeout report for the user to route. The sweep itself starts only on the user's word.
- **Unread hits at closeout**: name them, and when the population is plausibly still infected, file the follow-up rather than letting the unread rows evaporate.

## Boundaries

- Upstream seam: `diagnose` ends when the cause is known; this begins there and never hunts the original cause.
- Not verification of the original fix and not its regression test — those belong to the fix's own flow (`tdd`, or `diagnose` Phase 5).
- Not a repo-wide health sweep: every probe stays scoped to this signature's plausible population. A scored debt audit is `tech-debt-scan`.

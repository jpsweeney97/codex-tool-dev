---
name: worktree-task-cycle
description: "Use when working a task through its full lifecycle in a persistent, locked satellite worktree — a parked permanent skill workspace — including landing into the primary checkout, or when such a satellite is in an unknown or interrupted state. Do not use for ordinary branch landing (`merge-branch`), disposable worktree exit (`exiting-worktrees`), or creating or retiring satellites."
---

# Worktree Task Cycle

One task through one persistent satellite: activate a fresh branch from the verified integration branch, validate against the exact tip, land fast-forward through the primary checkout, re-park. The directory is the skill's permanent workspace; the branch is the task.

## The model

- The primary checkout is permanently the integration lane and the only delivery source. Satellites are never a delivery source: no sync/link, plugin publish, mirror update, push, or PR from a satellite, ever.
- A persistent satellite is a registered worktree that is not the primary and is `locked` with the canonical reason `parked skill workspace (permanent)`. Locked with any other reason: hard stop, surface the facts.
- The integration branch (`--base`) comes from the repo's own instructions, never guessed or defaulted, and must equal the branch the primary has checked out (the helper enforces this).

## The helper

All guard machinery is single-sourced in `scripts/worktree_cycle.py` in this skill's own directory — invoke it by its full installed path. It prints labeled lines (`FACT:` / `PROOF:` / `POLICY:` / `STATE:` / `REFUSE:`, closing `RESULT: ok|refused`); branch on those, not on prose. Exit 0 = verb completed with all proofs green; exit 2 = refusal with the reason labeled; exit 1 = unexpected error. Do not re-implement or approximate any guard in shell; if the helper refuses, the refusal is the answer — never improvise around it.

## Attended, top-level sessions only

Run every verb from the top-level attended session. Never dispatch lifecycle verbs to subagents: subagents inherit the parent's session identity, so the lease cannot tell them apart and serialization silently breaks. Refuse destructive recovery when no human reads the transcript.

## Nominal lifecycle

```text
inspect → lease-acquire → activate → (do the work; commit) →
repo validation obligations → record-validation → land → park → delete-branch
```

1. `inspect <sat> --base <b>` — classify before touching anything.
2. `lease-acquire <sat> --branch <name> --purpose <p>` — scoped worktree lease.
3. `activate <sat> --branch <name> --base <b>` — PARKED proofs, free-name check, fresh branch from the explicit base ref.
4. Do the task's work in the satellite; commit. Branch naming follows the repo's conventions (the helper enforces only repo-global uniqueness). The done-judgment before recording belongs to `closeout-check`.
5. Run the repo's own validation obligations for the changed surfaces (red ladder → fix, or `keep-green` where available).
6. `record-validation <sat> --ladder "<what ran>"` — binds the record to the exact tip.
7. `land <sat> --branch <name> --base <b>` — acquires and releases the integration lease internally; full recheck; ff-only merge of the validated SHA through the primary; ancestry proof. On `STATE: STALE-BASE`: rebase in the satellite, revalidate (steps 5–6, new tip), re-run land.
8. `park <sat> --base <b>` — containment proof, detach, PARKED proofs, releases the worktree lease.
9. `delete-branch <sat> --branch <name> --base <b>` — ancestry-proven `-d`; trashes the validation record.

## Recovery

Run `inspect` and route on `STATE:`:

| STATE | route |
|---|---|
| ACTIVE-CONFLICT | `resolve-conflicts`, then full revalidation |
| IN-FLIGHT | uncommitted work; adjudicate with the user — never park or delete a dirty tree |
| READY | resume at land |
| READY-INVALID | fix (or `keep-green` where available), revalidate; barred from land |
| COMMITTED-UNLANDED | re-acquire the lease, then land (freshness catches staleness) |
| LANDED-UNPARKED | resume at park |
| CONTAINED-UNPARKED | loss-free, but provenance unproven — state the ambiguity to the user, then park |
| PARKED-UNDELETED | delete-branch; a `-d` refusal after its proofs is an evidence contradiction — stop |
| PARKED-ORPHAN | surface `git log <base>..HEAD`; the user adjudicates adopt / rescue ref / explicit discard |
| LEASE-ORPHANED | surface the owner facts; only the user may authorize the break (agent runs `trash` on the lease dir, authorization quoted); then reconstruct |
| UNMAPPABLE | hard stop; present the raw facts to the user |

Not in the table: `STATE: PARKED` is the nominal healthy state — nothing to recover; begin the lifecycle at lease-acquire. `STATE: PRIMARY` means you anchored `inspect` at the primary checkout — re-run it against the satellite path. After a failed activation (or any PARKED satellite still holding your own lease), release the lease with `lease-release <sat> --base <b>`; a mid-task release is refused by design.

## Boundaries

- Destructive escapes are user-authorized only, run by you in the visible transcript quoting the user's words: breaking a foreign or orphaned lease (`trash`), abandoning an unmerged task (`-D` after explicit user say-so). The helper never implements them.
- Never `git worktree remove` a satellite, at any force level. Satellite creation and retirement are the owning repo's decisions, executed only on the user's explicit instruction outside this skill.
- Post-landing rollback is a new revert task through this same lifecycle, never a ref reset.
- No push, publish, sync, mirror, or PR from any step.

## Routing

- Ordinary branch landing in a single checkout → `merge-branch`.
- Disposable worktree exit after landing → `exiting-worktrees`.
- In-progress merge/rebase conflicts → `resolve-conflicts`.
- Done-judgment and final-commit shaping → `closeout-check`.

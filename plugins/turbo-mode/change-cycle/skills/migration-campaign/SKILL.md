---
name: migration-campaign
description: "Use when applying one mechanical change — a codemod, rename, config-key or path/namespace change, or framework/API call-site bump — uniformly across many sites, and you need to drive it to complete, verified application: partition into shards, pilot the riskiest first, track every site in a durable burndown, and verify each shard before marking it done. Do not use to decide what the change should be or map its blast radius (`contract-change-propagation`), to execute a plan of distinct bespoke tasks (`execute-plan`), or to slice a feature vertically into tracker issues (`to-issues`)."
---

# Migration Campaign

Drive one mechanical change — the *same* edit repeated across many sites — to **complete, verified** application: every site found, every site either changed-and-verified or consciously skipped, nothing silently half-done.

**The discipline is the skill.** Applying a codemod is easy; *not losing a site and not over-matching one* is the work. A site that looks like a match can be out of scope — a token syntactically right but semantically wrong (a `.codex/handoffs/` path should move, but a bare `.codex` home directory must not) — and a site the search never reached stays on the old contract forever. The burndown and the verify-before-done gate exist so "done" means verified-done, never edited-and-assumed.

## 1. Pin the change and the site universe — supplied, not invented

Work from a **defined, mechanical** transformation: a codemod or rewrite rule, a rename (`old → new`), a config-key or path/namespace change, a framework/API call-site update — one shape repeated. Often the change and a candidate consumer list arrive from `contract-change-propagation` or a plan; take them as input.

Do **not** decide *what* to change here. If each site needs different bespoke logic, or the change is still a design question, this is the wrong lane (see Boundaries). Then enumerate the candidate sites more than one way — symbol, import path, string key, config lookup, generated code, other packages — knowing the list is candidates to confirm, not proof of completeness.

## 2. Partition into shards

Split the site universe into shards that can each be applied and verified **independently** — by directory, package, module, CODEOWNERS, or risk. A good shard is small enough to verify in one pass and revert on its own. The shard list is the spine of the burndown.

## 3. Pilot one shard first — prove the recipe before fanning out

Apply the change to a single shard — the riskiest or most representative — and verify it fully before touching any other. The pilot proves two recipes at once: the *transformation* (does the edit do the right thing?) and the *verification* (what command or read actually confirms a site is correct?). A pilot that surfaces an over-match, or a site the rule mangles, has just saved you from making the same mistake N times. Do not fan out until the pilot is verified — green *and* over-match-clean, not green alone.

## 4. Maintain the durable burndown

Keep one living list of every site/shard with an explicit status each — e.g. *pending / applied / verified / done*, plus *skipped* (confirmed out-of-scope, such as an over-match, or deliberately deferred — with a reason), *unverified* (a candidate you could neither confirm changed nor rule out — open residual risk, not a clean skip), and *reverted*.

This list is the contract: never let a site fall off it, and never declare the campaign complete while any site is unaccounted-for or merely applied-but-unverified. For a single sitting, the harness task list is enough; when the campaign spans sessions or hands off, persist it (a checklist file, or `to-issues` when each shard should be a tracked issue). The form is yours; the completeness is not.

## 5. Apply and verify each shard — discriminate over-matches

Per shard: apply the change, then **verify before marking it done** — run the build/test/lint the pilot established, plus a targeted check that the edit hit the real sites and only those. The sharp question for every match: **is this a real site, or a token that merely looks like one?** A find-and-replace will happily change a string that is syntactically a match but semantically out of scope, and that edit looks done. When a match is confirmed out of scope, mark it **skipped** with a reason — a correct non-change. But when you can neither confirm the change landed nor rule the site out, mark it **unverified**, never **skipped**: burying an unprovable candidate in a clean status is the silent half-done this skill exists to prevent. Do not apply on faith, and do not close on faith. On resume after an interruption, re-check any *applied*-but-unverified site's actual state before re-applying: a non-idempotent transform double-applies silently, and the burndown records claimed state — the tree is the truth.

Checkpoint each verified shard on its own — a per-shard commit makes one shard revertable without losing the rest — on a working branch, never a protected one.

## 6. Sequence, compat, and hand-off

- **Sequence** — order shards to fit the change: safest-first to build confidence, or riskiest-first to fail fast. Where a producer must ship before a consumer can migrate, or a site lives in a repo you do not control, name that constraint and sequence around it.
- **Compat layer** — where a shim, dual-write, or adapter lets sites migrate gradually instead of in lockstep, say so as advice, not a mandate.
- **Hand-off** — this skill drives the application and owns the burndown. The branch/merge/push/PR lifecycle stays with the normal git discipline (`git-cycle` skills when available); publish nothing unless explicitly asked. If the work should live as tracked issues, hand the shard list to `to-issues`.

## Boundaries

In scope: applying one mechanical change across many sites with a pilot, a durable burndown, and per-shard verification.

Out of scope — route instead:

- deciding *what* to change, or mapping an interface change's blast radius and consumers → `contract-change-propagation`.
- executing a plan of **distinct, bespoke tasks**, each a different edit → `execute-plan`.
- slicing a feature **vertically** into grabbable tracker issues → `to-issues`; a campaign shards **horizontally** — one change, many like sites.
- a single-target cleanup or refactor → `simplify-code`; a debt audit or backlog → `tech-debt-scan`.

Applies edits to the working tree on a working branch, and stops there. Do not commit to a protected branch, push, open a PR, or publish unless the user explicitly asks. The change is mechanical and supplied — never invent it, and never mark a site done you have not verified.

## Output

Deliver as you go, not only at the end:

1. **Plan** — the change, the shard list, the pilot choice, and the verification recipe.
2. **Burndown** — the status of every shard (done / skipped+reason / unverified / reverted), in-flight ones still pending.
3. **Completion** — the campaign is done only when every site is either verified-done or confirmed-skipped; any **unverified** site keeps the campaign open. State what your search could not reach (other repos, runtime-only paths, external callers) and every unverified site as the residual risk. If sites remain, say which and why.

---
name: contract-change-propagation
description: "Use when you have a proposed or in-progress change to a shared interface — an API, function signature, schema, data format, config key, or event payload — and need to map its blast radius before it lands: classify each delta as breaking, additive, or behavior-preserving, enumerate the consumers, and recommend a versioning, deprecation, and rollout sequence. Do not use to review an already-completed change (`implementation-review`), review architecture or design quality (`system-design-review`), apply the rollout across many sites, or slice a plan into tracker issues (`to-issues`)."
---

# Contract-Change Propagation

Map the blast radius of an interface change **before** it lands: which consumers break, which keep working, and in what order to roll it out.

**The judgment is the skill.** Deciding that a delta is breaking, and naming the consumer that `rg` cannot see, is the work. The search is only evidence — it finds static call sites; it cannot find a reflective lookup, a payload already serialized to disk, or a client in another repo. Treat every consumer list as candidates to confirm, never a proof of completeness.

## 1. Pin the change — supplied, not invented

Work from a concrete definition of the change, supplied as any of: a diff or patch; two versions of the file or spec; a git ref-range (`old..new`); two API/schema documents (OpenAPI, GraphQL, protobuf, JSON Schema, SQL DDL); or a precise verbal description (`rename getUser(id) to getUser(id, opts)`).

If the change is not yet pinned to specific elements, ask for one of these forms or extract it from a named diff — do **not** guess what the change is. Read the codebase freely to find consumers; never fabricate the change itself.

## 2. Classify every delta

For each changed element, decide exactly one:

- **Breaking** — an existing correct consumer can stop compiling, throw, or silently misbehave. Removed or renamed symbol; changed signature, type, or required field; narrowed accepted input; changed or widened output a consumer parses; changed default, error, status code, ordering, nullability, or units; tightened auth; removed enum value.
- **Additive** — new capability that leaves existing consumers correct. New optional parameter with a safe default; new endpoint, field, or method; newly accepted input; new enum value *only if* consumers have a default branch.
- **Behavior-preserving** — refactor, rename-with-shim, or internal change no consumer can observe.

State a one-line rationale per delta. The sharp question for each: **what is the worst thing a current consumer could be doing that this delta breaks?** If you can name such a consumer, it is breaking — additive-looking changes are often breaking once you picture a real caller (a new required field breaks every existing writer; a new enum value breaks an exhaustive switch). Decide and justify; do not score.

## 3. Enumerate consumers

Find who depends on each breaking element. Search more than one way — a single `rg` for the symbol name misses most real consumers:

- **Static call sites and imports** — the symbol, the import path, the route, the field name.
- **Indirect or string-keyed** — reflection, dynamic dispatch, dependency injection, string keys, config lookups, generated code.
- **Serialized or persisted** — data already written to disk, sitting in a queue or cache, or in flight that encodes the old shape.
- **Cross-boundary** — other repos, external API clients, downstream services, published packages, and the docs or examples that teach the old contract.

List each consumer with its location (`path:line` where static) and how it was found. Then state, explicitly, what your search **could not reach** (other repos, runtime-only paths, external callers). That honest gap is part of the deliverable: a consumer list presented as complete when it is not causes the exact breakage this skill exists to prevent.

## 4. Recommend versioning and rollout sequence

- **Version** — map the highest-severity delta to a semver bump (any breaking → major; additive-only → minor; behavior-preserving → patch), or to this project's release convention if it differs. Flag any breaking delta hiding under a non-breaking version.
- **Sequence** — prefer the safe order: ship additive first → migrate consumers off the old path → deprecate with a window → remove. But name the constraint that forces a different order here — a consumer you cannot migrate before the producer ships, an impossible dual-write, a consumer in a repo you do not control — and sequence around it. Where a compat layer (shim, overload, dual-write, adapter) makes the change non-breaking, say so, as advice not a mandate.
- **Hand off** — this skill produces the plan; it does not execute it. If the rollout spans many sites, hand the confirmed consumer list to a sharded-execution lane (`migration-campaign`) or to `to-issues` to track the work — otherwise carry it out under a sharded plan you drive.

## Boundaries

In scope: classifying an interface delta, enumerating consumers, and recommending a versioning/deprecation/rollout plan for a **proposed** change.

Out of scope — route instead:

- reviewing an **already-completed** change against a plan → `implementation-review`.
- architecture or design quality, boundaries, tradeoffs → `system-design-review`.
- **applying** the change across shards with burndown tracking → `migration-campaign`; this skill stops at the plan and never applies the change.
- slicing the plan into grabbable issues → `to-issues`.

Read-only and judgment-only. Read code and the supplied change freely; do **not** edit files, apply the migration, stage, commit, or publish unless the user explicitly asks for that as a separate step. The `rg` sweep is evidence for your judgment, not an authority — never present it as an exhaustive consumer list.

## Output

Deliver concisely:

1. **Change summary** — the elements that changed.
2. **Classification** — each delta: breaking / additive / behavior-preserving, with a one-line rationale.
3. **Consumers** — per breaking delta, the located consumers (`path:line`) and what the search could not reach.
4. **Plan** — version bump, rollout sequence, any compat-layer option, and the hand-off.

If nothing breaks, say so plainly and stop — an additive-only change needs a version note, not a campaign.

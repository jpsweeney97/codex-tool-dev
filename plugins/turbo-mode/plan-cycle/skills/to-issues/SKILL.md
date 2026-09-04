---
name: to-issues
description: "Use when the user wants to convert an existing plan, spec, PRD, or approved design into independently grabbable implementation issues and publish them to the project issue tracker. Do not use for creating the PRD/spec, implementation, issue triage, status orientation, recommendations, or next-step planning without issue publication."
---

# To Issues

Break a plan into independently-grabbable issues using vertical slices (tracer bullets).

The issue tracker and triage label vocabulary should have been provided to you. If they are missing, ask the user to run `/setup-matt-pocock-skills` where that user-invoked skill is available; otherwise ask the smallest setup question needed before publishing.

## Side Effects And Proof Boundary

This skill publishes approved slices to the configured issue tracker. Do not publish until the user has approved the slice breakdown or explicitly asked to use an already-approved breakdown.

After publishing, report the created issue identifiers or URLs, parent links, labels applied, source artifact used, and proof boundary. Issue publication proves the tracker artifacts were created; it does not prove implementation, acceptance satisfaction, or tracker state beyond the actions performed.

## Process

### 1. Gather context

Work from whatever is already in the conversation context. If the user passes an issue reference (issue number, URL, or path) as an argument, fetch it from the issue tracker and read its full body and comments.

### 2. Explore the codebase (optional)

If you have not already explored the codebase, do so to understand the current state of the code. Issue titles and descriptions should use the project's domain glossary vocabulary, and respect ADRs in the area you're touching.

Look for opportunities to prefactor the code to make the implementation easier. "Make the change easy, then make the easy change."

### 3. Draft vertical slices

Break the plan into **tracer bullet** issues. Each issue is a thin vertical slice that cuts through ALL integration layers end-to-end, NOT a horizontal slice of one layer.

Slices may be 'HITL' or 'AFK'. HITL slices require human interaction, such as an architectural decision or a design review. AFK slices can be implemented and merged without human interaction. Prefer AFK over HITL where possible.

<vertical-slice-rules>
- Each slice delivers a narrow but COMPLETE path through every layer (schema, API, UI, tests)
- A completed slice is demoable or verifiable on its own
- Each slice is sized to fit in a single fresh context window
- Prefer many thin slices over few thick ones
- Any prefactoring should be done first </vertical-slice-rules>

**Wide refactors are the exception to vertical slicing.** One mechanical change whose blast radius fans across the whole codebase (a column rename, a shared-symbol retype) cannot pass its checks as a vertical slice — don't force it into a tracer bullet. Where available, route it to `/migration-campaign` or `$migration-campaign` for site-by-site application, `contract-change-propagation` to map the blast radius first, and `migration-safety` for a live schema or data change. When a needed companion is unavailable, publish the wide refactor as one `ready-for-human` issue and state which missing specialist route made an automatic split unsafe. Slice the *rest* of the work here as normal.

### 4. Quiz the user

Present the proposed breakdown as a numbered list. For each slice, show:

- **Title**: short descriptive name
- **Type**: HITL / AFK
- **Category**: bug / enhancement
- **Blocked by**: which other slices (if any) must complete first
- **User stories covered**: which user stories this addresses (if the source material has them)

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Are the dependency relationships correct?
- Should any slices be merged or split further?
- Are the correct slices marked as HITL and AFK?

Iterate until the user approves the breakdown.

### 5. Publish the issues to the issue tracker

For each approved slice, publish a new issue to the issue tracker. Use the issue body template below. Apply exactly one approved category role (`bug` or `enhancement`) and the state role that matches the slice's Type: `ready-for-agent` for AFK slices, `ready-for-human` for HITL slices. Do not stamp every slice `ready-for-agent` — an HITL slice mislabeled that way can be grabbed by an autonomous agent that cannot do its human-in-the-loop work. These canonical roles map to the tracker's label strings through the triage label vocabulary. Read each published issue back and confirm that it carries exactly one category and one state role.

Publish one issue at a time in dependency order (blockers first), recording each identifier as it is created so every dependency edge can reference a real item. Before creating a slice on a later or resumed run, check for an existing issue with the same title under the parent; label and link that issue instead of creating a duplicate. Where the tracker exposes relationships natively — GitHub does — link each slice to its source issue as a sub-issue of the parent and record each "Blocked by" as a native issue dependency. Fall back to the text `Parent` / `Blocked by` fields only when the tracker has no native equivalent. On failure or interruption, stop and report created identifiers separately from the slices that remain.

<issue-template>
## Parent

A reference to the parent issue on the issue tracker (if the source was an existing issue, otherwise omit this section).

## What to build

A concise description of this vertical slice. Describe the end-to-end behavior, not layer-by-layer implementation.

Avoid specific file paths or code snippets — they go stale fast. Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it here and note briefly that it came from a prototype. Trim to the decision-rich parts — not a working demo, just the important bits.

## Acceptance criteria

- [ ] One checkbox per externally observable outcome — a check someone could verify by exercising the slice (behavior, output, or state), not an implementation step.

## Blocked by

- A reference to the blocking ticket (if any)

Or "None - can start immediately" if no blockers.

</issue-template>

Do NOT close or modify any parent issue.

After publishing, name the next lane and stop: the `ready-for-agent` issues are now `implement-issue`'s to pick up (one issue per fresh session), and the `ready-for-human` issues await a human. Do not implement them yourself unless the user asks.

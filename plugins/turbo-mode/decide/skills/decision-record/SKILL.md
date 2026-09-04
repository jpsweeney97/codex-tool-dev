---
name: decision-record
description: "Use when a decision is already made and you want it captured as a durable numbered ADR in `docs/adr/`, from any source — a live conversation, transcript, PR thread, or chat — including when it reverses an earlier decision, setting that older ADR's status to `superseded by NNNN` so the two never silently disagree. Not for making or ranking the decision (`making-recommendations`, `design-exploration`), an ADR offered while grilling a plan (`grill-with-docs`), an incident retrospective (`postmortem`), or landing research findings (`research-capture`)."
---

# Decision Record

Capture an already-made decision into the existing `docs/adr/` ADR format, and maintain the one piece of genealogy nothing else owns: on a reversal, point the old record at its replacement so the two never silently disagree. Invocation: `/decision-record` or `$decision-record`.

A decision record is an immutable, addressable historical fact. The skill owns exactly the two jobs nothing else owns — capturing a settled decision on demand from any source, and the single genealogy operation of pointing a superseded record at the decision that replaced it. It never rewrites a past decision's substance, and it never forks the ADR format.

## Confirm a decision exists; right-size, never veto

First, a decision must actually be settled: a choice, its rationale, and the rejected alternatives. If the source shows deliberation but no settled choice, stop and route to the deciding skills (`making-recommendations` / `design-exploration` / `ideate`) — do not fabricate a decision out of discussion. This is the load-bearing non-use boundary: decision-record captures a decision, it does not produce one.

The format's three-part gate (hard to reverse + surprising without context + a real trade-off) is a right-size prompt here, not a veto — the user already asked to record. If the decision is easily reversible or unsurprising, offer the lighter option ("an ADR may be overkill — a one-line note instead?") and defer to the user's choice. Provoke the "is this worth an ADR?" thought; never override the explicit request.

## Capture faithfully from any source

Read the whole source first — the live conversation, a pasted transcript, a PR thread, a chat — and reconstruct three things: the actual choice, the *real* rationale (including unflattering or contingent ones, like "we were out of runway" or "the partner contract forced it"), and the alternatives genuinely considered. Do not retrofit a tidy technical justification onto a messy real decision. Where the source records the choice but not the why, write what is present and flag "rationale not stated in source" rather than invent one; with no real alternatives, omit the optional Considered Options rather than fabricate. Date the record by when the decision was made when the source carries it (a PR merge, a message timestamp), else today. When capture is from an external artifact, one light `Source:` phrase is allowed as ordinary prose; for live capture the ADR itself is the record — add nothing.

## Reuse the ADR format, never fork it

Point to the existing format; restate none of it. The body links `../../references/ADR-FORMAT.md` as the single source of the template, the `proposed | accepted | deprecated | superseded by ADR-NNNN` status vocabulary, the scan-highest-and-increment numbering, the lazy `docs/adr/` creation, and the three-part worth-recording gate — the same file `grill-with-docs` and `improve-codebase-architecture` consume. decision-record adds only what that file lacks: standalone capture from any source, and the genealogy maintenance below. Its output is indistinguishable from any other ADR in the directory — no parallel dialect.

The format file ships in this plugin's shared `references/` directory, linked above. `grill-with-docs` and `improve-codebase-architecture` read the same file through the alias at `skills/grill-with-docs/ADR-FORMAT.md` in the source repo, and `grill-with-docs`'s maintenance note names both consumers. A change to the format is a `decide` release: edit the canonical here, never a copy.

## The genealogy mechanism (the job nothing else owns)

- **Detect — explicit-or-confirm, never auto-flip on inference.** An explicit "this supersedes our decision about X" resolves to a specific ADR number (confirm it resolved correctly). Otherwise, during the numbering scan you are already doing, read the existing ADR titles (they are tiny) and the body of any same-subject match, and judge whether this decision reverses, replaces, or retires it; surface a candidate and confirm before any change. A wrong supersession corrupts the genealogy worse than a missing one. No similarity classifier — the corpus is small and the user is in the loop.
- **Set the old record's status — adding it if absent.** This is the load-bearing edit. A freshly captured, in-force decision is statusless (accepted by convention, exactly as grill-with-docs's ADRs are), so the normal superseded record has no Status line to flip — you **add** a `Status: superseded by ADR-NNNN` frontmatter block above its title, or change an existing Status line if one is there. Inserting that Status block is the one structural addition that does not count as touching the body. Use `deprecated` instead when the old decision is abandoned with no successor.
- **Change a status only when the old decision no longer holds.** If the old decision still stands and the new one merely builds on it, do **not** touch its status — name the relationship in the new record's prose, and, where the repo's convention appends dated amendment sections to older records, in one such section on the old record (see the mutation boundary below). ADR-FORMAT carries no "amends" or "refines" verb, so anything short of a reversal stays a prose cross-reference, never a status change. Over-flipping a still-valid record corrupts the genealogy as badly as under-flipping.
- **The new record names the old one in ordinary prose** — "This supersedes ADR-0003, which chose X; we now do Y because Z." No structured reciprocal field; the back-link rides the 1-to-3 sentences the format already asks for.
- **Chains preserve history.** If 0003 was superseded by 0007 and now 0011 supersedes 0007, set 0007 to `superseded by 0011`; never re-point 0003. The walkable chain 0003 → 0007 → 0011 is the genealogy.
- **Report what you did, claim no more.** Name which records you scanned (by title and status on the subject) and which you changed; do **not** claim the corpus now holds no contradiction — a reversal phrased in different words months apart can slip a title scan. Promise only the edit you actually made. That honesty is the point: a missed supersession stays visible for the user to catch, instead of hiding behind a false all-clear.

Mutation boundary: a settled record's body — its reasoning — is never rewritten; only its `Status` is ever changed, and only to record supersession or deprecation. One addition sits inside that boundary: where the repo's own ADR convention carries dated amendment or addendum sections on older records (detect it as you detect the rest of the format), a dated section pointing at the new record may be added where that convention places such sections — the existing text is never edited, before or after it, and without such a convention the cross-reference stays in the new record's prose. The one exception to the no-rewrite rule: a record that *misrepresents the original decision* may be corrected to be accurate (mark it `Corrected <date>`), never as a back-door to launder a reversal — a changed decision is always a new superseding record.

## Output path, multi-context, and re-run

Write to `docs/adr/NNNN-slug.md`, created lazily. Default to the repo-root `docs/adr/`; in a `CONTEXT-MAP.md` repo, reuse grill-with-docs's documented layout (system-wide `docs/adr/` versus a context's `src/<ctx>/docs/adr/`) and place a plainly context-scoped decision in that context's directory, asking one placement question only when genuinely ambiguous. Numbering is per-directory: scan that `docs/adr/` for the highest number and increment. Defer to an ADR home set in `AGENTS.md` / `CLAUDE.md` if one exists — and match any existing ADR convention (location, markup, numbering, headings) per the detection rule in `ADR-FORMAT.md` before applying these defaults. grill-with-docs writes the same `NNNN-slug.md` files into the same directory, so the two share the corpus and the numbering namespace natively — read the existing files, whoever wrote them, for both numbering and supersession detection.

Re-run is non-destructive: if the same decision is already recorded, report the existing ADR without creating a duplicate. Change it only under the mutation boundary above; if no permitted change applies, leave it unchanged. A genuine change to the decision follows the supersession path; a new decision gets a new number. A dirty target file or a slug collision → ask one path question; never ask on a clean re-run.

## Write safety and commit

Before the first write, run `git status`; the genealogy edit touches an existing file, so surface unrelated dirty state on the new path or the record you are about to change instead of writing over it. After writing and verifying, create a default local commit: stage only the ADR file(s), message `docs(adr): record NNNN <slug>` (or `… supersede MMMM`, or `… deprecate MMMM`). On a protected or default branch, or when unrelated dirty state makes staging ambiguous, write the file(s) and skip the commit, saying so — defer branch and worktree safety to the repo's protected-branch floor and `git-cycle`; do not re-inline that apparatus. Never push, open a PR, or publish.

## Workflow

1. Read the full source; confirm a decision is actually settled (else route out).
2. Reconstruct the choice, the real rationale, and the genuine alternatives; mark provenance and date.
3. Scan `docs/adr/` for the next number and for any record this decision supersedes; confirm a candidate before changing it.
4. Write the new ADR in ADR-FORMAT shape at the next number, naming any superseded record in prose.
5. On a supersession, set the old record's `Status` to `superseded by ADR-NNNN` (adding the block if absent), or `deprecated` if abandoned.
6. Re-read both ends against Done when; commit; report what was scanned, written, and changed.

## Done when

- The decision is captured as one ADR at the next sequential number, in the reused format.
- The real rationale and the genuine alternatives are recorded faithfully, or their absence is flagged.
- Any superseded record's `Status` points forward to the new number (added if it had none), and the new record names it in prose.
- The report states which records were scanned and which were changed — and claims no corpus-wide guarantee.

## Fence

- An ADR offered as a by-product mid-grilling → `grill-with-docs` (it writes the same `docs/adr/` files, no genealogy); standalone capture from any source, and all supersession maintenance, → decision-record.
- An incident retrospective with dated action items → `postmortem`; this captures a decision, not an incident.
- Findings with provenance → `research-capture`; this lands a decision.
- A source showing deliberation but no settled choice routes to the deciding skills per "Confirm a decision exists" above.

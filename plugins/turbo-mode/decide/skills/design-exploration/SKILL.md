---
name: design-exploration
description: "Use when the user wants to explore and settle a design before implementation: shaping a clear-enough outcome into compared approaches and an approved design or spec. Do not use for clarifying a still-muddy outcome (`outcome-shaping`), choosing between already-comparable options (`making-recommendations`), pressure-testing an existing plan or design (`grill-me`), implementation, prototyping, or PRD/issue publication."
---

# Design Exploration

Turn a clear-enough outcome into an approved design through collaborative exploration. This lane owns the generative middle between outcome clarification and planning: proposing approaches, developing the chosen one into a design, and getting explicit approval before any implementation lane takes over.

## Trigger Boundaries

- Use when the desired outcome is clear enough to design against and the user wants approaches explored or a design shaped.
- If the outcome itself is still muddy, name `outcome-shaping` and ask before switching.
- If serious comparable options already exist and the user wants a choice, name `making-recommendations`.
- If the user wants an adversarial stress test of an existing design, name `grill-me` or the relevant review lane.
- If a design question is genuinely uncertain in a way only running code can answer, offer `prototype` for that question and fold its answer back into the design. The tell is your own sentence "only real data, a real run, or the actual files can answer this" — that sentence is the offer moment, not a note to move past.
- This lane does not implement. Do not write production code, scaffold projects, or invoke an implementation lane before the user approves a design. "Simple" requests still get a design; it can be a few sentences, but it gets presented and approved.

## Core Workflow

1. Explore project context first: relevant files, docs, ADRs, the domain glossary, recent commits. Ground the design in code reality. When exploration is delegated to subagents, have each return the most load-bearing files and read those files yourself before designing; do not design from subagent summaries alone.
2. Scope check before detail: if the request spans multiple independent subsystems, say so and decompose into sub-projects before refining anything. Three tells that a request genuinely bundles independently testable capabilities: it names distinct capabilities with their own consumers or data; acceptance criteria cluster into groups that could ship and be verified separately; one capability could be cut or replaced without rewriting the others' requirements. Test any proposed split with the cycle test: dependency arrows point one way — if two sub-projects each need the other, they are one sub-project. Design the first sub-project; each gets its own design cycle.
3. Clarify what materially shapes the design. Batch independent questions into one ask; sequence only when an answer changes the next question.
4. Propose the genuinely different approaches that actually exist — usually 2-3 — with trade-offs. Lead with a recommendation and why, as a labeled lean rather than a settled verdict: give the strongest rival its honest case in a sentence or two (what would have to be true for it to win), and when the pick turns on a trade the user owns — values, product meaning, risk appetite — pose it priced instead of settling it silently. Do not invent weak alternatives to fill the count: when only one serious approach exists, present it as exactly that and say what would make a real rival worth developing; when no approach is serious enough to develop, or the user rejects the field, widening is `ideate`.
5. Develop the chosen approach into a design presented in sections scaled to their complexity: architecture, components and boundaries, data flow, error handling, testing. Check in at the decisions the user might correct — named plainly, batched — not only with one approval ask at the end of a long draft; a fluent finished artifact invites assent, a named decision invites correction.
6. Design for isolation: units with one clear purpose and well-defined interfaces, understandable without reading their internals. Remove features the outcome does not need.
7. Self-review before handoff: placeholders, internal contradictions, requirements readable two ways, scope still fit for a single plan. Fix inline.

## Existing Codebases

Follow existing patterns. Include targeted improvements only where an existing problem directly affects the design at hand. Do not propose unrelated refactoring.

## Approval And Handoff

The design is approved only when the user says so. An instruction to build on the design — scaffold it, implement it, start the next lane — is not approval by itself: it is the approval moment arriving early, so confirm the design in one line and ask, rather than starting to build. On a hard-to-reverse design, offer one round of pressure before settling (`grill-me` or the relevant review lane): an approval that survived pressure settles more than assent to a fluent draft. On approval, name the next lane and ask: `implementation-planning` for an executable plan doc, `to-prd` or `to-issues` for tracker publication, or conversational closure when nothing downstream is needed.

When you hand off, carry a compact warm-handoff capsule so the next lane starts from the settled design instead of re-deriving it: the approved approach in brief, what was deliberately deferred or left open, the binding constraints the next lane must respect, how settled each load-bearing decision actually is — contested and corrected during the cycle, or accepted as offered — and the named next lane. Keep it compact and skip any beat with no real content; a few sentences or a short structured note, whichever fits the design — chat-first like the design itself, written to a doc only when the user approves that step. A saved spec or a generic session handoff does not replace these beats; carry them wherever the design goes. When the next lane is `implementation-planning`, the capsule orients; it does not replace the full design that lane reads in full.

## Artifacts

Chat-first by default. Write a design doc only when the user asks or approves; place it per repo convention, asking one path question if no convention is clear. Do not commit automatically.

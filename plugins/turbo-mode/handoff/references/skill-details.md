# Handoff Skill Details

Deferred detail for Handoff skill controllers. Load the relevant section only when the compact `SKILL.md` file needs examples, templates, or troubleshooting.

## Save

Use `/save` for session boundaries where future Codex needs full reasoning, decisions, file context, and resumption state. The output should include the required handoff sections from `format-reference.md`, decision reasoning, codebase knowledge with references, risks, gotchas, open questions, and next steps.

Avoid trivial handoffs, single-sentence decisions, bare file lists, paraphrased user preferences when verbatim wording matters, and chat reproduction of the saved artifact. If the body looks thin, re-check implicit decisions, explored files, rejected approaches, and the conversation arc before writing. If the saved content is materially incomplete, create a replacement handoff rather than editing committed active-writer output in place.

Troubleshooting: if the file is not created, inspect the active-writer error, operation-state JSON, write permissions under `.codex/handoffs/`, and project-root detection. If content misses key decisions, create a new handoff with fuller context.

## Summary

Use `/summary` for moderate sessions with decisions, exploration, codebase learning, or project-arc context. Required content: Goal, Session Narrative, Decisions, Changes, Codebase Knowledge, Learnings, Next Steps, and Project Arc. Target roughly 120-250 body lines. Project Arc should answer where the project stands now, what is ahead, load-bearing prior decisions, accumulated understanding, drift risks, and downstream impacts.

Avoid using summary for complex sessions that need `/save`, skipping arc context gathering, turning Project Arc into a digest of prior handoffs, exceeding summary depth when `/save` is the better fit, or reproducing content in chat.

Troubleshooting: if the file is not created, inspect the active-writer output and write permissions. If the body exceeds 250 lines, decide whether the session actually warranted `/save`.

## Quicksave

Use `/quicksave` for context pressure and quick state capture. Required content: Current Task, In Progress, Active Files, Next Action, and Verification Snapshot. Optional content: Don't Retry, Key Finding, and Decisions. Target roughly 22-55 body lines.

Avoid session narrative, full decision analysis, codebase dumps, or reproducing checkpoint content in chat. If the checkpoint exceeds roughly 80 lines, consider `/save`.

Troubleshooting: if the file is not created, inspect project detection and active-writer output. Missing `resumed_from` can happen when state expired or the previous session crashed before writing state.

## Load

Primary runtime storage:
- Active handoffs: `<project_root>/.codex/handoffs/`
- Archive: `<project_root>/.codex/handoffs/archive/`
- Resume state: `<project_root>/.codex/handoffs/.session-state/handoff-<project>-<resume_token>.json`
- Load transactions: `<project_root>/.codex/handoffs/.session-state/transactions/`

Legacy read compatibility may include reviewed active inputs from `docs/handoffs/*.md`, explicit legacy archive inputs from `docs/handoffs/archive/*.md`, and hidden primary archives from `.codex/handoffs/.archive/*.md`. Legacy sources are not deleted by load.

Avoid auto-injecting handoffs, suggesting old handoffs without user request, loading the synthesis guide, modifying handoff content, or hand-editing resume state.

Troubleshooting: if no handoff is found, run `/list-handoffs`, check primary storage, or load an explicit archive path. If a pending transaction is recovered, continue from the returned archive before starting another load. If transaction state is corrupt, report the path and require operator repair before retrying.

## Defer

Candidate fields: `summary`, `problem`, `source_text`, `proposed_approach`, `acceptance_criteria`, `priority`, `source_type`, `source_ref`, `branch`, `session_id`, `effort`, and `files`. `summary` and `problem` are required by the envelope contract. Use imperative summaries under 80 characters when possible.

High-confidence signals include explicit deferral language, review findings marked as deferred or design debt, TODO/FIXME references discussed in the conversation, and unresolved items from consultations. Medium-confidence signals include conditional actions and open questions that imply future work. Low-confidence observations without action go in Possible Misses only.

Present candidates in a table and full detail blocks before asking for confirmation. Accept `all`, explicit numbers, edits, or `none`. On ingest: Parse Ticket ingest JSON stdout and render only recovery summaries, next steps, safe messages, ticket IDs, duplicate candidate ticket IDs, and user-safe ingest outcome prose. Do not report Ticket ingest payload paths, processed envelope paths, incoming envelope paths, or envelope provenance in the human transcript.

Failure handling: stop on `defer.py` error; ingest successful envelopes on partial success; treat Ticket resolver ambiguity as a release blocker; report duplicate candidates as already tracked.

## Distill

Source mapping: Decisions preserve choice, driver, alternatives, trade-offs, and confidence; Learnings preserve mechanism, evidence, implication, and caveat; Codebase Knowledge preserves patterns and conventions; Gotchas preserve pitfalls and workarounds. Synthesize into Phase 0 paragraphs of roughly 6-8 sentences, max 10.

Statuses: `EXACT_DUP_SOURCE` and `EXACT_DUP_CONTENT` are terminal auto-skips; `UPDATED_SOURCE` prompts replace/keep decisions; `NEW` requires synthesis and confirmation. Semantic dedup is advisory; the user decides.

Append format:

```markdown
### YYYY-MM-DD [tag1, tag2]

<synthesized paragraph>
<!-- distill-meta {"content_sha256": "<from candidate>", "distilled_at": "YYYY-MM-DD", "source_anchor": "<from candidate>", "source_uid": "<from candidate>", "v": 1} -->
```

If replacing a promoted entry, warn that replacement invalidates the promotion unless the user chooses replace plus keep promoted metadata.

## Triage

Report open tickets grouped by priority and age. Report orphaned handoff items requiring manual review before matched informational items. Include match coverage counts for `uid_match`, `id_ref`, `manual_review`, and `skipped_prose`.

Match strategies: `uid_match` joins handoff `session_id` to Ticket provenance, `id_ref` detects explicit ticket IDs in handoff text, and `manual_review` means no deterministic match. UID match only works for tickets created from handoff-derived contexts; PR review, Codex, and ad-hoc tickets route to manual review by design.

Offer orphan actions: create selected tickets through `/defer`, mark already tracked, mark not actionable, or skip all. Triage itself is read-only.

## Search

Literal search is case-insensitive. Regex search is case-sensitive unless the pattern includes `(?i)`. For 1-5 results, show each matching section. For 6 or more, show a summary table and the three most recent full results, then ask whether to show the rest.

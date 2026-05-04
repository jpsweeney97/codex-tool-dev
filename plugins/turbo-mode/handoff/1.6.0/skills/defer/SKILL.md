---
name: defer
description: Extract deferred work items from conversation and create tracking tickets. Use when user says "/defer", "defer these", "track these for later", "create tickets for remaining items", or at end of session when open items remain. Scans conversation for explicit deferrals, review findings, open questions, and TODO/FIXME mentions, then creates ticket files in docs/tickets/.
argument-hint: "[optional filter or scope]"
allowed-tools:
  - Bash
  - Read
  - Write
  - Glob
  - Grep
---

# Defer

Extract deferred work items from conversation context and create tracking tickets in `docs/tickets/`. The `defer.py` script emits DeferredWorkEnvelope JSON files, and the ticket engine's `ingest` subcommand consumes them through the full pipeline (dedup, preflight, execute). This skill handles judgment: extraction, evidence anchoring, candidate presentation, and user confirmation.

**Model:** Best-effort assistant. LLM extraction is inherently imperfect. Present candidates with evidence anchors so the user can verify. False positives are caught by confirmation; false negatives are mitigated by the "Possible Misses" section and explicit coverage disclaimer.

## Setup (run once per skill invocation)

**Step 1 - Resolve plugin root:**
Set `PLUGIN_ROOT` to the plugin root directory three levels above this `SKILL.md`, not the `skills/` directory.
Use a literal absolute value such as `PLUGIN_ROOT="/absolute/path/to/handoff/1.6.0"`.
For example, if the skill file is `/absolute/path/to/handoff/1.6.0/skills/defer/SKILL.md`, then `PLUGIN_ROOT` is `/absolute/path/to/handoff/1.6.0`.
When executing commands, use the absolute path for `PLUGIN_ROOT`; do not `cd` into the plugin directory.

## Inputs

| Input | Behavior |
|-------|----------|
| `/defer` | Scan full conversation context for deferred work items |
| `/defer <filter>` | Scope extraction to `<filter>` (e.g., a topic, file path, or review category) |

## Procedure

### Step 1: Analyze conversation for deferred work

Scan the conversation for deferred items using hybrid extraction:

**Hint-scoped signals** (high confidence):
- Explicit deferral language: "defer", "out of scope", "follow-up", "not blocking", "address later", "separate PR", "post-merge", "Phase 1"
- Items explicitly marked "not in this PR" or "future work"

**Deterministic signals** (high confidence):
- Review findings categorized as suggestions/deferred/design-debt
- Codex unresolved items from cross-model consultations
- Items noted but not acted on

**Contextual signals** (medium confidence):
- Conditional actions: "if X happens, then Y", "when corpus grows"
- TODO/FIXME mentions in code or discussion
- Open questions that imply future work

**Actionability filter:** Each candidate MUST have an identifiable action (fix, add, remove, refactor, investigate). Observations without clear actions are NOT tickets -- report them in "Possible Misses" instead.

**Evidence anchor:** Each candidate MUST include a quoted excerpt from the conversation where the item was identified.

If user provided a `<filter>`, restrict extraction to conversation segments matching the filter.

### Step 2: Build candidate list

For each candidate, extract:

| Field | Description | Extract | Code contract |
|-------|-------------|---------|---------------|
| `summary` | One-line title (imperative voice, under 80 chars) | Always | **Required** — KeyError if missing |
| `problem` | What needs to be done and why | Always | **Required** — KeyError if missing |
| `source_text` | Quoted conversation excerpt (evidence anchor) | Always | Optional — omitted if absent |
| `proposed_approach` | Suggested implementation path | Always | Optional — omitted if absent |
| `acceptance_criteria` | Observable completion conditions (list of strings) | Always | Optional — omitted if absent |
| `priority` | `critical`, `high`, `medium`, or `low` | Always | Optional — defaults to `medium` |
| `source_type` | One of: `pr-review`, `codex`, `handoff`, `summary`, `ad-hoc` | Infer from context | Optional — defaults to `ad-hoc` |
| `source_ref` | Human-readable source (e.g., PR number, handoff filename) | If available | Optional — defaults to `""` |
| `branch` | Current git branch | Auto-detect | Optional — omitted if absent |
| `session_id` | Session ID from handoff frontmatter | If available | Optional — defaults to `""` |
| `effort` | `XS`, `S`, `M`, `L`, `XL` | Always | Optional — defaults to `S` |
| `files` | Affected file paths | If identifiable | Optional — omitted if absent |

### Step 3: Present candidates for confirmation

Display a summary table:

```
| # | Summary | Priority | Source Type | Evidence |
|---|---------|----------|-------------|----------|
| 1 | <summary> | <priority> | <source_type> | "<quoted excerpt...>" |
```

Below the table, for each candidate show the full detail:

```
### Candidate N: <summary>
**Priority:** <priority> | **Effort:** <effort> | **Source:** <source_type>
**Problem:** <problem>
**Proposed approach:** <proposed_approach>
**Acceptance criteria:**
- <criterion 1>
- <criterion 2>
**Evidence:** "<source_text>"
**Files:** <files or "none identified">
```

**After all candidates**, include:

```
### Possible Misses

Conversation segments that *might* contain deferred items but did not meet the actionability filter:
- <segment description and location>
- (or "None identified")

> This is a best-effort extraction. Review the conversation if completeness matters.
```

Ask the user to confirm which candidates to create. Accept:
- "all" or "create all" -- confirm all candidates
- Specific numbers: "1, 3, 5" or "create 1 and 3"
- "none" or "skip" -- abort without creating tickets
- Edits: "change priority of 2 to high" (apply edit, re-present that candidate)

**NEVER create tickets without user confirmation.**

### Step 4: Create tickets via envelope pipeline

Two-phase flow: emit envelopes, then ingest each through the ticket engine.

**Phase 1 — Emit envelopes:**

For each confirmed candidate, construct a JSON object matching the schema in Step 2. Pipe the array to `defer.py`:

```bash
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PYTHONDONTWRITEBYTECODE=1 \
UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff-1.6.0" \
uv run --project "$PLUGIN_ROOT/pyproject.toml" python "$PLUGIN_ROOT/scripts/defer.py" --tickets-dir "$PROJECT_ROOT/docs/tickets" <<'JSON'
<candidates_json>
JSON
```

Where:
- `<candidates_json>` is the JSON array of confirmed candidates
- `<project_root>` is the absolute path from `git rev-parse --show-toplevel`

Parse the JSON response from stdout:

| `status` | Meaning | Action |
|----------|---------|--------|
| `ok` | All envelopes emitted | Proceed to Phase 2 |
| `partial_success` | Some envelopes emitted, some failed | Report errors. Ingest what succeeded. |
| `error` | All envelopes failed | Report errors and STOP |

**Phase 2 — Ingest envelopes:**

For each envelope path from the Phase 1 `envelopes` array, create a payload file and call the ticket engine's `ingest` subcommand:

```bash
PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
PYTHONDONTWRITEBYTECODE=1 \
UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff-1.6.0" \
uv run --project "$PLUGIN_ROOT/pyproject.toml" python "$PLUGIN_ROOT/scripts/plugin_siblings.py" --plugin-root "$PLUGIN_ROOT" --sibling ticket --field plugin_root
```

Copy the printed absolute Ticket plugin root and substitute it literally into the next command. Do not use command substitution, `uv run`, a relative payload path, or a `/tmp` payload path in the ingest command.

If `plugin_siblings.py` reports more than one installed Ticket version, fail closed and treat that condition as a release blocker. Do not guess which Ticket root to use.

```bash
mkdir -p "$PROJECT_ROOT/.codex/ticket-tmp"
cat > "$PROJECT_ROOT/.codex/ticket-tmp/payload-ingest-<timestamp>-<suffix>.json" <<'JSON'
{"envelope_path": "<envelope_path_from_defer.py>", "tickets_dir": "docs/tickets"}
JSON
```

```bash
python3 /absolute/ticket/root/scripts/ticket_engine_user.py ingest "$PROJECT_ROOT/.codex/ticket-tmp/payload-ingest-<timestamp>-<suffix>.json"
```

Parse the JSON response for each ingest call. The response contains `state`, `message`, and `ticket_id` on success.

### Step 5: Commit created files

Stage created ticket files and processed envelopes by explicit path (NEVER `git add .`):

```bash
git add docs/tickets/<file1>.md docs/tickets/<file2>.md docs/tickets/.envelopes/.processed/<envelope1>.json docs/tickets/.envelopes/.processed/<envelope2>.json
git commit -m "chore(tickets): defer N items from <source_type>"
```

Where `<source_type>` is the most common `source_type` among confirmed candidates. If mixed, use `mixed`.

**If commit fails:** Report `partial_success` with the list of created file paths and recovery command:
```
git add <paths> && git commit -m "chore(tickets): defer N items from <source_type>"
```

### Step 6: Report results

Summarize: number of tickets created, file paths, ticket IDs, and envelope provenance. Example:

```
Created 3 tickets via envelope pipeline:
- T-20260228-01: docs/tickets/2026-02-28-T-20260228-01-add-retry-logic.md
- T-20260228-02: docs/tickets/2026-02-28-T-20260228-02-refactor-parser.md
- T-20260228-03: docs/tickets/2026-02-28-T-20260228-03-investigate-timeout.md
Envelopes processed: docs/tickets/.envelopes/.processed/
Committed on branch feature/my-feature.
```

## Extraction Heuristics

| Signal Type | Example Patterns | Confidence | Evidence Anchor |
|-------------|-----------------|------------|-----------------|
| Explicit deferral | "defer to follow-up", "out of scope for this PR" | High | Quote the deferral statement |
| Review categorization | "suggestion", "not blocking", "design debt" | High | Quote the finding |
| TODO/FIXME in code | `TODO(user): handle edge case` | High | Quote the comment with file path |
| Open question (unresolved) | "open question: should we..." | Medium | Quote the question |
| Conditional action | "if X happens, then Y", "when corpus grows" | Medium | Quote the condition |
| Risk without mitigation | "risk: could OOM with large input" | Medium | Quote the risk statement |
| Observation without action | "this could be improved" | Low | Report in Possible Misses only |

Items at Low confidence are NOT candidates -- they appear in Possible Misses only.

## Failure Modes

| Failure | Recovery |
|---------|----------|
| No deferred items found | Report "No deferred items identified in this conversation" and STOP |
| User confirms 0 candidates | Report "Nothing to defer" and STOP |
| `defer.py` returns `error` | Display error details and STOP |
| `defer.py` returns `partial_success` | Report created files and errors. Commit what succeeded. |
| Ticket ID collision | Ticket engine handles this (dedup detection) |
| `docs/tickets/` does not exist | `defer.py` creates the `.envelopes/` directory; ticket engine creates `docs/tickets/` |
| Ingest returns `duplicate_candidate` | Report as "already tracked" and skip. Not an error. |
| Git commit fails | Report created file paths and manual recovery command |
| Script path does not resolve | Resolve paths relative to this skill's directory |
| Ticket plugin not installed | Phase 2 resolver fails. Report envelopes emitted but not ingested. |

## Scope

**This skill DOES:**
- Extract deferred work candidates from conversation context
- Present candidates with evidence anchors for user confirmation
- Create ticket files in `docs/tickets/` via `defer.py`
- Commit created ticket files

**This skill does NOT:**
- Triage or prioritize existing tickets (use `/triage`)
- Modify existing ticket files
- Auto-defer at session end (user must invoke explicitly)
- Inject into `/save` workflow
- Share an "already-extracted" registry with `/distill`
- Run without user confirmation

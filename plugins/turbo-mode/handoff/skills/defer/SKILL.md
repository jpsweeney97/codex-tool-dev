---
name: defer
description: Extract deferred work items from conversation and create tracking tickets. Use when user says "/defer", "defer these", "track these for later", "create tickets for remaining items", or at end of session when open items remain. Scans conversation for explicit deferrals, review findings, open questions, and TODO/FIXME mentions, then creates ticket files in docs/tickets/.
---

# Defer

Extract deferred work candidates from conversation context, confirm them with the user, emit envelopes, and ingest confirmed items through the Ticket plugin.

Read [skill-details.md](../../references/skill-details.md) only when you need extraction examples, candidate field details, failure modes, or reporting templates.

## Use

- Use for `/defer`, `/defer <filter>`, "defer these", "track these for later", or "create tickets for remaining items".
- Each candidate must have an identifiable action and a quoted evidence anchor from the conversation.
- Observations without clear action go in "Possible Misses"; they are not tickets.
- NEVER create tickets without user confirmation.

## Setup

Resolve plugin root before running helpers. Set `PLUGIN_ROOT` to the plugin root directory three levels above this `SKILL.md`, not the `skills/` directory. Use a literal absolute value such as `PLUGIN_ROOT="/absolute/path/to/handoff"`. When executing commands, use the absolute path for `PLUGIN_ROOT`; do not `cd` into the plugin directory.

## Procedure

1. Scan conversation context for explicit deferrals, review findings categorized as deferred/design debt, TODO/FIXME items discussed, open questions, and conditional follow-ups. Apply any user-provided filter.
2. Present all actionable candidates with summary, problem, proposed approach, acceptance criteria, priority, effort, source type, files, and evidence. Include "Possible Misses" for ambiguous non-actions.
3. Ask the user which candidates to create. Accept "all", specific numbers, edits, or "none".
4. Emit envelopes for confirmed candidates:

   ```bash
   PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
   PYTHONDONTWRITEBYTECODE=1 \
   UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff" \
   uv run --project "$PLUGIN_ROOT/pyproject.toml" python "$PLUGIN_ROOT/scripts/defer.py" --tickets-dir "$PROJECT_ROOT/docs/tickets" <<'JSON'
   <candidates_json>
   JSON
   ```

   Parse stdout. If `status` is `error`, report details and STOP. If `partial_success`, ingest emitted envelopes and report failures.

5. Resolve the Ticket plugin root:

   ```bash
   PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
   PYTHONDONTWRITEBYTECODE=1 \
   UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff" \
   uv run --project "$PLUGIN_ROOT/pyproject.toml" python "$PLUGIN_ROOT/scripts/plugin_siblings.py" --plugin-root "$PLUGIN_ROOT" --sibling ticket --field plugin_root
   ```

   Copy the printed absolute Ticket plugin root literally. If more than one installed Ticket version is reported, fail closed and do not guess. Do not use a relative payload path or `/tmp` payload path.

6. For each envelope, create a payload file under `$PROJECT_ROOT/.codex/ticket-tmp/`, then ingest it:

   ```bash
   mkdir -p "$PROJECT_ROOT/.codex/ticket-tmp"
   # Write {"envelope_path": "<envelope_path_from_defer.py>", "tickets_dir": "docs/tickets"}.
   python3 /absolute/ticket/root/scripts/ticket_engine_user.py ingest "$PROJECT_ROOT/.codex/ticket-tmp/payload-ingest-<timestamp>-<suffix>.json"
   ```

## Ticket Ingest Transcript Boundary

When Ticket ingest returns `data.recovery_hint`, show the recovery summary and next step before any lower-level message. Do not report Ticket ingest payload paths, processed envelope paths, incoming envelope paths, or envelope provenance in the human transcript.

Parse Ticket ingest JSON stdout and render only recovery summaries, next steps, safe messages, ticket IDs, duplicate candidate ticket IDs, and user-safe ingest outcome prose.

Report ticket IDs, duplicate candidates, and user-safe partial-failure summaries. For `created_envelope_move_failed`, say the ticket was created but ingest cleanup could not finish; suggest Ticket diagnostics before retrying cleanup. Never paste the raw Ticket ingest JSON into the human transcript.

7. Stage created ticket files and processed envelopes by explicit path only. Never use `git add .`.
8. Report ticket IDs, duplicate candidates, user-safe ingest outcomes, and any skipped duplicate candidates.

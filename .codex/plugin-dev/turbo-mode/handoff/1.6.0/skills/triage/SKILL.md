---
name: triage
description: Review open tickets and detect orphaned handoff items that need tracking. Use when user says "/triage", "what's in the backlog", "review deferred items", "any open tickets", or at session start for project orientation.
argument-hint: "[optional --tickets-dir or --handoffs-dir override]"
allowed-tools:
  - Bash
  - Read
---

# Triage

Read open tickets and scan recent handoffs for orphaned items (Open Questions/Risks with no matching ticket). Read-only analysis -- does not modify tickets. Ticket creation is via `/defer`.

## Inputs

| Input | Behavior |
|-------|----------|
| `/triage` | Full report: open tickets + orphan scan with default directories |
| `/triage --tickets-dir <path>` | Override tickets directory (default: `docs/tickets/`) |
| `/triage --handoffs-dir <path>` | Override handoffs directory (default: auto-detected from project) |

## Procedure

### Step 1: Run triage.py

```bash
python ../../scripts/triage.py --tickets-dir "<project_root>/docs/tickets"
```

Where `<project_root>` is the absolute path from `git rev-parse --show-toplevel`.

Note: handoff scanning is limited to files modified within the last 30 days. Older handoffs are excluded from the orphan scan.

If the user provided directory overrides, pass them as `--tickets-dir` and/or `--handoffs-dir` arguments.

Capture the JSON output from stdout.

### Step 2: Parse the JSON report

The report contains five keys:

| Key | Type | Contents |
|-----|------|----------|
| `open_tickets` | `list[dict]` | Tickets with `status` not in (`done`, `wontfix`). Each has: `id`, `date`, `priority`, `status_raw`, `status_normalized`, `normalization_confidence`, `summary` (filename stem), `path` |
| `orphaned_items` | `list[dict]` | Items with `match_type: manual_review`. Each has: `match_type`, `matched_ticket` (null), `item` (dict with `text`, `section`, `session_id`, `handoff`) |
| `matched_items` | `list[dict]` | Items matched via `uid_match` or `id_ref`. Each has: `match_type`, `matched_ticket` (ticket ID), `item` (same nested dict) |
| `match_counts` | `dict` | Counts per strategy: `uid_match`, `id_ref`, `manual_review` |
| `skipped_prose_count` | `int` | Prose paragraphs skipped (not list items) |

### Step 3: Present open tickets

Group by priority (critical > high > medium > low), then by age (oldest first within each group).

```
## Open Tickets

### Critical
| ID | Date | Summary | Status | Confidence |
|----|------|---------|--------|------------|

### High
| ID | Date | Summary | Status | Confidence |
|----|------|---------|--------|------------|

(... medium, low ...)
```

If a priority group has no tickets, omit it.

If no open tickets exist, report: "No open tickets found in `<tickets_dir>`."

### Step 4: Present orphaned items

Show `manual_review` items first (these need user action), then `uid_match`/`id_ref` items as informational confirmation.

```
## Orphaned Handoff Items (Manual Review Required)

| # | Handoff | Section | Item | Match Status |
|---|---------|---------|------|-------------|
| 1 | <item.handoff> | <item.section> | <item.text> | manual_review |

## Matched Items (Informational)

| Handoff | Section | Item | Match Type | Ticket |
|---------|---------|------|-----------|--------|
| <item.handoff> | <item.section> | <item.text> | <match_type> | <matched_ticket> |
```

If no orphaned items exist, report: "No orphaned handoff items detected."

### Step 5: Report match-path observability

Always display match counts for transparency:

```
## Match Coverage

| Strategy | Count |
|----------|-------|
| uid_match | N |
| id_ref | N |
| manual_review | N |
| skipped_prose | N |
```

Explain what each means:
- **uid_match**: Session ID joined handoff to ticket (strongest signal)
- **id_ref**: Handoff text references a ticket ID directly
- **manual_review**: No deterministic match found -- user decides
- **skipped_prose**: Non-list paragraphs in Open Questions/Risks sections (out of scope for Phase 0 extraction)

### Step 6: Offer user actions for orphaned items

For each orphaned item (manual_review), offer:

- **"Create ticket"** or specific numbers (e.g., "create 1, 3") -- invoke `/defer` to create a ticket for that item
- **"Already tracked"** -- skip, no state change
- **"Not actionable"** -- skip, no state change
- **"Skip all"** -- dismiss all orphaned items

NEVER create tickets without user confirmation.

## Failure Modes

| Failure | Recovery |
|---------|----------|
| `triage.py` exits non-zero | Display stderr and STOP |
| No tickets directory exists | Report "No tickets found at `<path>`" and STOP |
| No handoffs directory exists | Skip orphan scan, report tickets only |
| Malformed ticket YAML | `triage.py` skips the ticket. If all tickets are malformed, report the warnings. |
| Handoff parsing fails | `triage.py` skips the handoff. Report if total skipped is high. |
| Script path does not resolve | Resolve `../../scripts/triage.py` relative to this skill's directory |
| JSON parse failure from stdout | Check stderr for Python errors. Report and STOP. |

## Match Strategies (Reference)

Three deterministic strategies in priority order:

1. **uid_match** -- handoff `session_id` matched against ticket `provenance.source_session` (YAML field, primary) or `defer-meta.source_session` (comment, fallback). Only works for tickets created via `/defer` from a handoff context.
2. **id_ref** -- handoff text contains a ticket ID matching regex patterns: `T-\d{8}-\d{2,}` (new format, 2+ digit sequence), `T-\d{3}` (legacy numeric), `T-[A-F]` (legacy alpha), `handoff-[\w-]+` (legacy noun, supports hyphens).
3. **manual_review** -- no deterministic match. Presented to user for manual classification.

**Source-type coverage limitation:** UID match only works for tickets created from handoff-derived contexts. Tickets with `source_type: pr-review`, `codex`, or `ad-hoc` route to `manual_review` by design.

## Scope

**This skill DOES:**
- Read open tickets and present them grouped by priority and age
- Scan recent handoffs for orphaned Open Questions and Risks
- Match handoff items against existing tickets using deterministic strategies
- Report match-path observability counts
- Offer user actions for orphaned items (create ticket via `/defer`, skip)

**This skill does NOT:**
- Modify existing ticket files (read-only)
- Write actions (reprioritize, close, wontfix) -- Phase 1
- Detect staleness -- Phase 1
- Persist triage state between sessions -- Phase 1
- Use lexical scoring for orphan matching -- Phase 1
- Auto-inject at session start (explicit `/triage` only)

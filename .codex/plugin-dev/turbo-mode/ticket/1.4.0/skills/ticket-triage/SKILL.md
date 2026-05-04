---
name: ticket-triage
description: "Analyze ticket health, detect stale tickets, blocked dependency chains, and audit activity. Use when the user says 'triage tickets', 'what's in the backlog', 'show ticket health', 'any stale tickets', 'ticket dashboard', 'what tickets are blocked', 'what should I work on next', 'what's outstanding', or 'catch me up on the project'. Also use at session start when the user wants project orientation, or whenever they want any kind of health check or overview of the ticket system."
allowed-tools:
  - Bash
  - Read
---

# /ticket-triage

Read-only ticket health analysis. Runs dashboard + audit, then adds opinionated recommendations. No mutations.

---

## Setup (run once)

**Resolve plugin root:**
Set `PLUGIN_ROOT` to the plugin root directory two levels above this `SKILL.md`.
When executing commands, use the absolute path for `PLUGIN_ROOT`; do not pass an environment variable or relative path.

**Resolve tickets directory:**
```bash
git rev-parse --show-toplevel
```
Append `/docs/tickets`. Store as `TICKETS_DIR`.

---

## Procedure

### Step 1: Run dashboard
```bash
python3 <PLUGIN_ROOT>/scripts/ticket_triage.py dashboard <TICKETS_DIR>
```

Response fields: `counts` (open/in_progress/blocked), `total`, `stale` (list), `blocked_chains` (list), `size_warnings` (list).

### Step 2: Run audit
```bash
python3 <PLUGIN_ROOT>/scripts/ticket_triage.py audit <TICKETS_DIR>
```

Covers the last 7 days by default. Response fields: `total_entries`, `sessions` (unique session count), `by_action` (dict of action → count, e.g. `{"create": 2, "update": 5}`), `by_result` (dict), `skipped_lines`, `read_errors`.

### Step 3: Format report

Present a structured summary:

```
## Ticket Health

**Active:** X total (open: N, in_progress: N, blocked: N)

**Stale (no activity > 7 days — script default):**
- T-YYYYMMDD-NN (status: open) — last date: YYYY-MM-DD

**Blocked chains:**
- T-YYYYMMDD-NN blocked by T-YYYYMMDD-MM (root blocker)

**Recent activity (last 7 days):**
- N creates, N updates, N closes  (from `by_action` dict)
```

Omit sections with no entries.

### Step 4: Add analysis

Base all analysis on the dashboard and audit script outputs only — do not read individual ticket files. The dashboard and audit data is the authoritative source; reading files directly risks inconsistency with the script's own aggregation logic.

Add opinionated recommendations beyond what the data shows:

- **Priority mismatches:** High-priority tickets in_progress while critical tickets are open
- **Stale in_progress:** Tickets in_progress for >7 days with no audit activity
- **Resolvable blocks:** Blocked tickets whose blockers are done or wontfix
- **Closable wontfix candidates:** Open tickets with no recent activity and low priority
- **Suggested next actions:** Order by impact ("unblock T-X by resolving T-Y first")

---

## Output Contract

Both scripts return `{"state": "ok", "data": {...}}` on stdout. Exit 0 on success, 1 on error.

If exit code is 1 (no JSON on stdout): report the stderr output and stop — do not attempt to parse.

If `TICKETS_DIR` does not exist: the dashboard still exits 0 with empty counts. Report "No tickets found" if `total` is 0.

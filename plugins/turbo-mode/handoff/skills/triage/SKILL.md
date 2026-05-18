---
name: triage
description: Review open tickets and detect orphaned handoff items that need tracking. Use when user says "/triage", "what's in the backlog", "review deferred items", "any open tickets", or at session start for project orientation.
allowed-tools:
  - Bash
  - Read
---

# Triage

Read open tickets and scan recent handoffs for orphaned Open Questions/Risks. This is read-only analysis; ticket creation goes through `/defer`.

Read [skill-details.md](../../references/skill-details.md) only when you need output table templates, match-strategy details, or troubleshooting.

## Use

- Use for `/triage`, "what's in the backlog", "review deferred items", "any open tickets", or project-orientation backlog review.
- Do not modify ticket files.
- Do not create tickets directly; offer `/defer` for confirmed orphaned items.

## Setup

Resolve plugin root before running helpers. Set `PLUGIN_ROOT` to the plugin root directory three levels above this `SKILL.md`, not the `skills/` directory. Use a literal absolute value such as `PLUGIN_ROOT="/absolute/path/to/handoff"`. When executing commands, use the absolute path for `PLUGIN_ROOT`; do not `cd` into the plugin directory.

## Procedure

1. Run triage:

   ```bash
   PROJECT_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
   PYTHONDONTWRITEBYTECODE=1 \
   UV_PROJECT_ENVIRONMENT="$PROJECT_ROOT/.codex/plugin-runtimes/handoff" \
   uv run --project "$PLUGIN_ROOT/pyproject.toml" python "$PLUGIN_ROOT/scripts/triage.py" --tickets-dir "<project_root>/docs/tickets"
   ```

   Use the absolute project root from `git rev-parse --show-toplevel`. Handoff scanning is limited to files modified within the last 30 days. If the user provided `--tickets-dir` or `--handoffs-dir`, pass the override through.

2. Parse stdout JSON. If the script exits non-zero, display stderr and STOP.
3. Present open tickets grouped by priority (`critical`, `high`, `medium`, `low`) and age. Omit empty priority groups. If none exist, report "No open tickets found in `<tickets_dir>`."
4. Present `manual_review` orphaned items first. Then present `uid_match` and `id_ref` matched items as informational.
5. Always report match coverage counts for `uid_match`, `id_ref`, `manual_review`, and `skipped_prose`.
6. Offer actions for orphaned items: create ticket for selected items through `/defer`, already tracked, not actionable, or skip all. Never create tickets without user confirmation.

## Failure Modes

- `triage.py` exits non-zero: display stderr and STOP.
- No tickets directory exists: report "No tickets found at `<path>`" and STOP.
- No handoffs directory exists: skip orphan scan and report tickets only.
- Malformed tickets or handoffs are skipped by the script; report high skipped counts.
- JSON parse failure from stdout: check stderr for Python errors, report, and STOP.

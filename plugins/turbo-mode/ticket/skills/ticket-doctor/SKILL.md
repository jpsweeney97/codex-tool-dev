---
name: ticket-doctor
description: "Run explicit Ticket plugin maintenance. Use when the user explicitly asks to doctor the ticket system, diagnose ticket storage, repair corrupt ticket audit logs, validate ticket plugin health, or run ticket storage/plugin diagnostics. Do not use for casual audit, review, or triage."
allowed-tools:
  - Bash
  - Write
  - Read
---

# Ticket Doctor

Run explicit maintenance and diagnostics for ticket storage or plugin health.
Do not trigger on casual audit, review, triage, or backlog-health language.

## Authority Boundary

ADR 0006 is the accepted architecture authority for the Ticket runtime-first
state-kernel rebaseline. The May 30 control doc is the implementation and
cutover control surface. This skill is source-authority guidance, not
installed-runtime proof and not runtime proof. This docs/tests slice does not
perform cutover inventory or normalization.

Explicit maintenance, diagnostics, activation, stale payload cleanup,
historical audit repair, and runtime-readiness commands are maintenance and
diagnostic material only. They are not normal target ticket mutation authority.
Preview, audit logs, activation proof, and cache refresh are not part of
ordinary target capture or update mutation.

## Setup

Resolve paths before running commands:

- `PLUGIN_ROOT`: plugin root three levels above this `SKILL.md`.
- `PROJECT_ROOT`: nearest ancestor of the current working directory that
  contains `.codex`, `.git/`, or a `.git` file.
- `TICKETS_DIR`: `<PROJECT_ROOT>/docs/tickets`; never derive it from
  `PLUGIN_ROOT`.

Use a user-provided `CACHE_ROOT` only when diagnosing source/cache parity. Do
not invent an installed cache path.

## Diagnostics

For static plugin and storage diagnostics, run:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py diagnose <TICKETS_DIR> --plugin-root <PLUGIN_ROOT> --cache-root <CACHE_ROOT> [--runtime-probe-output <PATH>]
```

Report the diagnostic result as source/cache/storage evidence. Do not describe
it as live runtime proof.

`diagnose` reports stale `.codex/ticket-tmp/` payloads older than 24 hours
without mutating them. Pass `--runtime-probe-output <PATH>` only when you want
the diagnose command to write a read-only runtime probe artifact under a
caller-chosen temp path for later inspection.

## Runtime Activation

Activation is `direct_execute only`. Use it only when the user explicitly asks
to activate or validate the installed Ticket runtime for the certified
direct-execute lane.

Activation is maintenance and diagnostic material only. It does not make cache
refresh, activation proof, or live runtime inventory part of normal target
ticket mutation authority.

Activation is user-origin only. Do not run this command as an agent. Present
the command below to the user and report that a user-owned shell must run it:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py activate-runtime <TICKETS_DIR> --marketplace-path <MARKETPLACE_PATH>
```

For live installed activation, `<PLUGIN_ROOT>` must be the cache-installed
runtime authority currently exposed by `hooks/list` and `skills/list`. Treat
the synced personal plugin copy as staging only, not the proof target.

Report direct-execute-only scope. Do not describe activation as caller-identity
proof, and do not widen it to `capture`, `update`, or `ticket_workflow.py`.

`TICKET_RUNTIME_PROOF_PATH` and `TICKET_RUNTIME_ACTIVATION_BOOTSTRAP=1` are
internal activation/test overrides used by the explicit activation flow. Do not
ask the user to set them for normal operator use.

If activation blocks, report the blocker code first:

- `host_policy_blocked`
- `deterministic_driver_unavailable`
- `hook_contract_blocked`
- `engine_gate_required`
- `runtime_readiness_required`
- `proof_invalid`
- `stale_proof`

## Recovery Hints

When a backend response includes `data.recovery_hint`, show the recovery summary and next step before any lower-level message. Do not expose payload paths, envelope paths, canonical command repair, raw temp/workspace paths, or hook/provenance fields in the transcript.

- `cleanup_stale_preview`: say old abandoned Ticket preview state can be cleaned
  up after review. This is maintenance and diagnostic legacy-source cleanup,
  not target preview-mode authority. Do not clean anything until the user
  explicitly approves the confirmed cleanup command.

## Audit Repair

Audit repair covers historical audit artifacts only. It does not create active
target mutation history.

Always dry-run audit repair first:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py repair-audit <TICKETS_DIR>
```

Show the dry-run result and ask before any mutation. If the user explicitly
approves repair, run:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py repair-audit <TICKETS_DIR> --confirm-repair
```

Stop on parse, path, permission, or backup errors. Report the failing command
and do not try alternate repair paths unless the user asks.

## Stale Payload Cleanup

Always run diagnostics first. Show the stale `.codex/ticket-tmp/` payloads
report and ask before any cleanup mutation. If the user explicitly approves
stale payload cleanup, run:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py clean-stale-payloads <TICKETS_DIR> --confirm-clean-stale-payloads
```

The unconfirmed command is:

```bash
uv run python -B <PLUGIN_ROOT>/scripts/ticket_doctor.py clean-stale-payloads <TICKETS_DIR>
```

Short form: `ticket_doctor.py clean-stale-payloads <TICKETS_DIR>`.

Cleanup is limited to stale JSON payloads under
`<PROJECT_ROOT>/.codex/ticket-tmp/` and uses a 24 hours TTL. The confirmation
flag is `--confirm-clean-stale-payloads`.

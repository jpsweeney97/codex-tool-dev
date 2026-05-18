# Ticket Plugin Privacy Notice

This document describes the Ticket plugin source package in this repository. It
does not certify what any installed Codex runtime or plugin cache currently
loads.

The Ticket plugin stores repo-local tickets, capture metadata, and audit logs in
the active project, normally under `docs/tickets/` and
`docs/tickets/.audit/`. Ticket payloads may include titles, problem summaries,
next actions, tags, priorities, related paths, and other ticket metadata entered
or approved during a Codex session.

The local plugin source does not intentionally transmit ticket contents or audit
logs to a separate service. Codex, OpenAI account handling, model requests,
telemetry, synchronization, and any host application behavior are governed
outside this local plugin document.

Review ticket content before writing it, especially when a ticket may contain
private project details, file paths, customer data, credentials, or other
sensitive information.

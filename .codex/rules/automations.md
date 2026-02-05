# Rules: Automations

These rules are **blocking**. Read them before creating or editing any file under `.codex/automations/`.

## Templates only in repo

- The repo stores **templates**, not runtime automation ids or run-state.
- Promotion generates installable TOML files under `/Users/jp/.codex/automations/<id>/automation.toml`.

## Prompt requirements

- The automation `prompt` describes the task only.
- Do not embed schedule or workspace details in the prompt.

## Scheduling constraints

- Use UI-compatible RRULEs only (weekly schedules or hourly interval schedules).
- Keep schedules simple and predictable.


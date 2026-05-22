# Ticket Runtime Readiness Activation Branch Closeout

## Status

Finalized on 2026-05-22 for the source, tests, and docs follow-up repair slice
on this branch. This closeout records the verification evidence for the follow-up
repairs and does not by itself claim installed-cache refresh or fresh
installed-runtime activation.

Branch: `fix/ticket-runtime-readiness-activation-v1`
PR: `#21` <https://github.com/jpsweeney97/codex-tool-dev/pull/21> (open against
`main`)

## Runtime Evidence Note

On 2026-05-21, a contained live app-server capture against installed
`codex-cli 0.133.0` recorded the actual `PreToolUse` stdin for both a root turn
and a thread-spawned subagent turn.

The subagent evidence path was:

- parent turn completed a `spawnAgent` collab tool call
- spawned child thread ran exactly `printf 'SUBAGENT_PRETOOL_CAPTURE\n'`
- the child command traversed the configured `PreToolUse` Bash hook
- captured child hook stdin omitted both `agent_id` and `agent_type`

The captured child `PreToolUse` input keys were:

```text
cwd
hook_event_name
model
permission_mode
session_id
tool_input
tool_name
tool_use_id
transcript_path
turn_id
```

Conclusion for this branch: `hook_request_origin="agent"` is not the current
expected live proof path on installed `codex-cli 0.133.0`. The current expected
host path remains missing `agent_id` -> `hook_request_origin="user"`.

## Evidence Boundary

This is installed-runtime observation evidence for `0.133.0`, not a permanent
Codex hook contract and not proof of caller identity. The raw JSONL transcript
and hook stdin dump were local scratch evidence, not source artifacts. The
branch should preserve the conclusion and proof shape, not commit raw runtime
transcripts.

If a later Codex version adds `agent_id` or `agent_type` to normal
`PreToolUse` inputs for thread-spawned subagents, rebaseline the proof
expectation instead of treating this note as a durable negative contract.

## Verification Performed

Focused follow-up verification on 2026-05-22:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest tests/test_runtime_readiness.py tests/test_doctor.py tests/test_workflow_cli.py tests/test_docs_contract.py -q`
  - Result: `231 passed in 4.35s`

Full Ticket verification on 2026-05-22:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run --directory plugins/turbo-mode/ticket pytest -q`
  - Result: `1173 passed, 3 warnings in 25.32s`
  - Warning summary: malformed-input fixture warnings from `tests/test_read.py`
    and `tests/test_workflow.py`; no failing assertions

Changed-path lint and patch hygiene on 2026-05-22:

- `PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache uv run ruff check plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py plugins/turbo-mode/ticket/scripts/ticket_workflow.py plugins/turbo-mode/ticket/tests/test_runtime_readiness.py plugins/turbo-mode/ticket/tests/test_doctor.py plugins/turbo-mode/ticket/tests/test_workflow_cli.py plugins/turbo-mode/ticket/tests/test_docs_contract.py`
  - Result: `All checks passed`
- `git diff --check`
  - Result: passed with no whitespace or merge-marker errors

## Source Boundary

This follow-up slice updates source, tests, and docs only:

- `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- `plugins/turbo-mode/ticket/scripts/ticket_workflow.py`
- Ticket docs and doc-contract tests for launcher, maintenance classification,
  audit backend wording, and triage doctor signature

This slice did not refresh `/Users/jp/.codex/plugins/cache`, did not sync the
personal plugin copy, and did not rerun live installed-runtime certification.
The installed-runtime observations captured earlier in this closeout remain the
authority for the branch's host-behavior note.

## PR Package

PR `#21` remains the publication package for this branch at the time of this
closeout:

- Title: `Ticket runtime readiness activation v1`
- URL: <https://github.com/jpsweeney97/codex-tool-dev/pull/21>
- State: `OPEN`

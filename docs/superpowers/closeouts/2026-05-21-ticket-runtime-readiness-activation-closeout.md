# Ticket Runtime Readiness Activation Branch Closeout

## Status

In progress. This closeout captures branch-level evidence as the development
branch approaches final verification and PR packaging. It does not by itself
claim final branch completion, installed-cache refresh, or installed-runtime
activation.

Branch: `fix/ticket-runtime-readiness-activation-v1`

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

## Final Closeout Pending

Before this closeout can become the final branch closeout, record:

- final focused Ticket verification
- full Ticket verification or an explicit reason it was not run
- changed-path lint and `git diff --check`
- source-vs-installed-cache boundary for this branch
- PR package link or merge/close decision

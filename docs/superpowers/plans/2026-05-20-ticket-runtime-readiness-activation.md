# Ticket Runtime Readiness Activation V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement the source side of activation-capable installed Ticket runtime readiness for the documented live direct-execute mutation lane only: canonical Ticket mutation commands routed through `ticket_engine_agent.py execute` under `autonomy_mode: auto_audit`, and only on hosts that can actually run the pinned app-server policy. Installed activation is a separate approval-gated proof outcome after an explicit cache refresh; source completion alone must close as `source repaired, installed runtime not activated`.

**Architecture:** Split the work into three explicit layers. First, prove the host can run the required contained `workspaceWrite` app-server turn and that the host exposes a deterministic command-driving path; if either prerequisite fails, stop before Ticket-owned implementation. Second, build Ticket-owned `installed_ticket_runtime_readiness` proof production around live app-server inventory and a direct-execute-only `hook_membrane_proof`; AgentControl child traversal is installed-activation corroboration only when a concrete harness exists. Third, gate only the documented direct-execute mutation lane. This plan proves installed hook-mediated wiring and installed-runtime identity. It does not prove caller identity, consumer migration outside this repo, or future capture/update agent-wrapper flows.

**Tech Stack:** Python >=3.11, pytest, Codex CLI `app-server` JSON-RPC, project-local `.codex` proof artifacts, bytecode-safe `uv run` verification.

---

## Decision Freeze

### Hook Role Reframing

Activation readiness proves installed hook-mediated mutation wiring, not caller
identity. Current Codex does not expose spawned-agent identity in `PreToolUse`;
therefore agent identity must not be a readiness prerequisite unless the Codex
hook contract changes.

Implications:

- `agent_id` is not a readiness prerequisite.
- `hook_request_origin` is provenance metadata, not a security-grade caller
  identity claim.
- Current Codex 0.132 hook stdin does not expose a stable spawned-agent
  identity field, even for AgentControl-spawned child turns.
- The readiness proof must accept current installed-runtime observations such as
  `hook_request_origin="user"` for the certified direct-execute lane.
- AgentControl child smoke is optional installed-activation corroboration in V1.
  It proves only that child Bash execution traversed the same installed hook
  membrane, and it is not a source-local readiness gate.

### Trust Boundary

Activation V1 proves installed hook-mediated wiring, not host-owned agent
identity.

Current Codex hook input on this machine exposes hook-observed provenance such as
`session_id` and `hook_request_origin`, but it does not expose a trustworthy
host-owned "this was spawned by agent X" signal. Therefore:

- Treat `hook_request_origin` as observed membrane provenance.
- Keep `ticket_engine_agent.py` as the policy-selecting entrypoint for the
  certified `direct_execute` lane.
- For the certified V1 direct-execute path, remove the current
  `hook_request_origin == request_origin` hard gate in the runner/core path so
  the installed host's observed `hook_request_origin="user"` metadata can reach
  the runtime-readiness gate without being misclassified as caller identity.
- Do not claim that activation proves host-owned agent identity or
  spawned-agent identity.
- State this boundary plainly in docs and error messaging.

### Scope Freeze

Activation V1 covers only the live documented direct-execute mutation lane in
`plugins/turbo-mode/ticket/README.md`:

- Certified execute surface: `ticket_engine_agent.py execute`
- Certified readiness surface name: `direct_execute`
- Certified policy lane: `ticket_engine_agent.py execute` plus
  `autonomy_mode: auto_audit`
- Certified proof claim: installed hook membrane plus direct-execute closeout,
  not caller identity

Out of scope for this plan:

- `ticket_capture_agent.py`
- `ticket_update_agent.py`
- wrapper prepare/execute same-thread fingerprint proof
- caller-identity proof
- real consuming-project caller migration outside this repo

If capture/update agent wrappers become real supported consumers later, capture
that as a separate follow-up ticket before widening the proof schema or engine
gate.

### Activation Preconditions

This plan is not executable past Task 0 unless Gates A and B are true on the
target host. Gate C is a diagnostic baseline: its current failure must be
captured before implementation, and installed activation cannot succeed until
the post-refresh Gate C check passes.

1. A contained `workspaceWrite` app-server turn can execute the installed Ticket
   prerequisite probe command without failing early with
   `sandbox-exec: sandbox_apply: Operation not permitted`.
2. The host exposes a deterministic app-server command-driving path for exactly
   one existing contained Bash command and the resulting raw `commandExecution` and
   `hook/completed` evidence.
3. The installed Ticket hook output diagnostic status is captured against the
   currently observed unsupported `permissionDecision` warning/failure path.

If Gate A or Gate B is false, stop before Ticket-owned source implementation.
If Gate C fails, record it as `hook_contract_needs_source_repair` and continue
only into Task 2 source repair. Do not treat `dangerFullAccess`, prompt-only
model turns, or AgentControl availability as an activation fallback.

Use two different command classes in this plan:

- **Prerequisite probe command:** an already-installed, already-hook-allowlisted
  contained execute command used only for Gates A/B substrate checks:

```bash
python3 -B <INSTALLED_TICKET_ROOT>/scripts/ticket_engine_agent.py execute <PAYLOAD_PATH>
```

  This probe exists in the current installed cache and is already allowlisted by
  the live hook. Gates A/B use it only to prove host turn viability and
  deterministic transcript capture. Engine-layer outcomes after hook traversal,
  including current `origin_mismatch`, `policy_blocked`, or future
  `runtime_readiness_required`, do not fail Gates A/B by themselves.

- **Canonical activation-smoke command:** the new dedicated command introduced in
  Task 2:

```bash
python3 -B <INSTALLED_TICKET_ROOT>/scripts/ticket_engine_activation_smoke.py execute <PAYLOAD_PATH>
```

  This command does not exist in the installed cache and is not hook-allowlisted
  at plan start. Task 2 must first prove it source-locally by adding the file,
  adding hook allowlist coverage, and passing focused tests. The first live
  installed proof of this canonical command happens only after explicit refresh
  in Task 6.

### Proof Class

`<PROJECT_ROOT>/.codex/ticket-runtime-proof.json` is the persisted
`installed_ticket_runtime_readiness` index for activation closeout. It is not:

- source proof
- cache-copy proof
- docs-readiness proof
- host-identity proof
- consumer-migration proof

The file is not authoritative by itself. The gate must re-hash and revalidate
the bound installed root, hook manifest, guard command, guard script hash,
plugin manifest hash, app-server inventory transcript, hook membrane
transcript, canonical command, payload hash/nonce, and execute result before
trusting the closeout. If `agentcontrol_hook_traversal_smoke` is present with
`status="captured"`, the gate must also revalidate its raw transcript and hook
identity bindings. Handwritten or copied JSON without matching evidence must
fail closed.

The proof must fail closed if raw evidence is missing, stale, mismatched, or no
longer points at the live installed runtime.

### Proof Scope

Activation closeout must set:

```json
{
  "activation_scope": {
    "gated_execute_surfaces": ["direct_execute"],
    "certified_entrypoints": ["ticket_engine_agent.py"],
    "certified_policy_lane": "ticket_engine_agent.py execute + autonomy_mode=auto_audit",
    "excluded_mutation_paths": [
      "ingest_dispatch",
      "activation_smoke_bootstrap",
      "ticket_capture.py",
      "ticket_update.py",
      "ticket_workflow.py"
    ],
    "autonomy_mode": "auto_audit",
    "caller_identity_proven": false,
    "hook_request_origin_contract": "provenance_metadata_only_currently_user"
  }
}
```

Anything broader is a different plan.

## Prerequisite Gates

Run these gates before Ticket-owned implementation. If any gate fails, the
result is a blocker report, not partial activation work.

The only source edit allowed before the Gate A/B outcome is adding or repairing
the narrow local-runtime artifact ignore policy, the disposable Gate B driver,
and the driver's focused refresh-tooling tests:

- `.gitignore`
- `plugins/turbo-mode/tools/refresh/app_server_turn_driver.py`
- `plugins/turbo-mode/tools/refresh/tests/test_app_server_turn_driver.py`

That setup is not Ticket-owned implementation. It must not import Ticket runtime
code, write `.codex/ticket-runtime-proof.json`, mutate
`/Users/jp/.codex/plugins/cache`, change Ticket source files, or become the
long-term activation producer. If the disposable driver cannot be made to produce
the required transcript within those limits, stop with
`deterministic_driver_unavailable`.

### Local Runtime Artifact Policy

Before any command writes Ticket runtime proof or smoke artifacts, prove the
project-local artifact paths are ignored by narrow `.gitignore` rules:

```bash
git check-ignore -v .codex/ticket-runtime-proof.json
git check-ignore -v .codex/ticket-runtime-smoke-preflight/app-server-driver-preflight.jsonl
git check-ignore -v .codex/ticket-runtime-smoke/example/raw/app-server-transcript.jsonl
```

Accepted policy:

- `.codex/ticket-runtime-proof.json`
- `.codex/ticket-runtime-smoke-preflight/`
- `.codex/ticket-runtime-smoke/`

If any check fails, patch `.gitignore` with only those narrow rules before
running Gate A/B. Do not add a broad `.codex/` ignore rule. The proof file and
raw transcripts are local runtime evidence, not source artifacts, and must never
appear as ordinary untracked commit material during this plan.

### Gate A: Host `workspaceWrite` Viability

Required evidence:

- A fresh contained app-server smoke against a disposable project root under
  `<PROJECT_ROOT>/.codex/ticket-runtime-smoke-preflight/`
- Pinned `approvalPolicy="never"`
- Explicit `runtimeWorkspaceRoots=[<contained_root>]`
- Pinned `sandboxPolicy={"type": "workspaceWrite", "writableRoots":
  [<contained_root>]}` or the exact current schema-equivalent
- A contained payload and the already-installed prerequisite probe command:

```bash
python3 -B <INSTALLED_TICKET_ROOT>/scripts/ticket_engine_agent.py execute <PAYLOAD_PATH>
```

Pass condition:

- The prerequisite probe command reaches command execution and the installed
  Ticket hook under that pinned policy.
- Post-hook engine-layer failure is acceptable for this gate as long as the
  raw transcript proves the contained command turn and hook traversal.

Fail condition:

- Early host-policy failure such as
  `sandbox-exec: sandbox_apply: Operation not permitted`

Failure handling:

- Stop with `host_policy_blocked`.
- Do not start implementation tasks.
- Do not reinterpret `dangerFullAccess` success as activation readiness.

### Gate B: Deterministic App-Server Driver

Required evidence:

- The Task 0 disposable driver at
  `plugins/turbo-mode/tools/refresh/app_server_turn_driver.py`.
- That helper is allowed before Ticket-owned implementation starts. Its only job
  is to open `codex app-server --listen stdio://`, send the exact turn-driving
  JSON-RPC sequence for this gate, and write the raw transcript. It must not
  import Ticket runtime code, write `.codex/ticket-runtime-proof.json`, mutate
  `/Users/jp/.codex/plugins/cache`, mutate `/Users/jp/.codex/config.toml`, or
  become the long-term Ticket-owned activation producer.
- Its own file writes may land only under
  `<PROJECT_ROOT>/.codex/ticket-runtime-smoke-preflight/`, including the JSONL
  transcript and disposable contained payloads for this preflight.
- The driver must send `thread/start.params.ephemeral=true` when the regenerated
  app-server schema supports that field. The transcript must show whether the
  app-server accepted the field.
- If the current app-server still persists thread/turn state outside the
  project-local preflight directory despite `ephemeral=true`, the driver must
  classify that separately as `app_server_state_scope=runtime_local_diagnostic`
  in the preflight summary. Do not describe Gate B as "project-local-only writes"
  in that case; the project-local-only claim applies only to driver-owned
  artifacts.
- Task 2 may replace the disposable helper with Ticket-owned runtime-readiness
  code after Gates A/B pass.
- A non-prompted JSON-RPC session to
  `codex app-server --listen stdio://` that writes
  `<PROJECT_ROOT>/.codex/ticket-runtime-smoke-preflight/app-server-driver-preflight.jsonl`
  using raw rows shaped exactly as
  `{"direction": "send"|"recv", "body": ...}`.
- The driver command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run python plugins/turbo-mode/tools/refresh/app_server_turn_driver.py \
  --project-root /Users/jp/Projects/active/codex-tool-dev \
  --contained-root /Users/jp/Projects/active/codex-tool-dev/.codex/ticket-runtime-smoke-preflight/contained \
  --installed-ticket-root /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0 \
  --marketplace-path /Users/jp/Projects/active/codex-tool-dev/.agents/plugins/marketplace.json \
  --out /Users/jp/Projects/active/codex-tool-dev/.codex/ticket-runtime-smoke-preflight/app-server-driver-preflight.jsonl
```

- The exact JSON-RPC method sequence sent by the driver:
  `initialize`, `initialized`, `thread/start`, `turn/start`.
- That transcript must prove one contained turn for the already-installed
  prerequisite probe command:

```bash
python3 -B <INSTALLED_TICKET_ROOT>/scripts/ticket_engine_agent.py execute <PAYLOAD_PATH>
```

- Accepted pass transcript contents:
  - `send` rows for `initialize`, `initialized`, `thread/start`, and
    `turn/start`
  - the `thread/start` send row includes `params.ephemeral=true` when supported
    by the regenerated schema, or the transcript records why that field was not
    available
  - exactly one host `commandExecution` item for the probe command
  - exactly one same-turn installed Ticket `hook/completed` notification
  - no `item/commandExecution/requestApproval`,
    `item/fileChange/requestApproval`, or
    `item/permissions/requestApproval`
- The existing readonly inventory helper at
  `plugins/turbo-mode/tools/refresh/app_server_inventory.py` is not sufficient
  for Gate B by itself because it does not drive a turn command.
- The new canonical activation-smoke command is intentionally excluded from Gate
  B because it does not exist or become hook-allowlisted until Task 2.

Pass condition:

- `plugins/turbo-mode/tools/refresh/app_server_turn_driver.py` produces that
  exact preflight transcript non-interactively before Ticket-owned
  implementation starts.

Fail condition:

- The named driver cannot produce that exact transcript non-interactively, or
  the only available primary path is prompt-driven / AgentControl-mediated.

Failure handling:

- Stop with `deterministic_driver_unavailable`.
- AgentControl child traversal evidence may still be captured later as optional
  installed-activation corroboration, but it does not satisfy Gate B by itself.

### Gate C: Installed Hook Output Diagnostic Baseline

Required evidence:

- The installed Ticket hook completion is accepted by app-server with
  `status == "completed"` and without unsupported hook output warnings.

Diagnostic fail condition:

- The installed hook still emits
  `PreToolUse hook returned unsupported permissionDecision: allow`
  or any equivalent unsupported-output warning/failure shape.

Failure handling:

- Record `hook_contract_needs_source_repair`.
- Continue into Task 2 because Task 2 owns the source hook-contract repair and
  source-local proof.
- Do not claim live installed activation until the post-refresh installed check
  in Task 6 proves the repaired hook contract on the installed cache copy.

## Hook Output Contract

Task 2 must replace the current unsupported
`hookSpecificOutput.permissionDecision` stdout contract with a live-proven
app-server-supported command-hook stdout contract before any installed
activation claim.

Authority source:

```bash
codex app-server generate-json-schema --experimental --out /private/tmp/codex-app-schema
```

The generated schema is notification-shape evidence, not by itself sufficient
proof of the command-hook stdout control API. The relevant generated
notification shape is `ServerNotification.json` /
`v2/HookCompletedNotification.json`: `HookRunSummary.entries` is an array of
`HookOutputEntry` objects shaped as `{"kind": "...", "text": "..."}`, and
`HookOutputEntryKind` is one of `warning`, `stop`, `feedback`, `context`, or
`error`.

Before rewriting `ticket_engine_guard.py`, Task 2 must add a source-local
app-server hook-output probe or focused integration test that drives both an
allowed command and a blocked command through `codex app-server` and proves the
stdout shape actually has the intended control effect. If the live app-server
contract does not honor the candidate shapes below, stop before the guard
rewrite and patch this section from live evidence first.

Candidate target stdout shapes, subject to the live proof above:

- Pass-through non-ticket Bash command:

```json
{}
```

- Allow after successful Ticket validation/injection:

```json
{}
```

- Deny/stop for a blocked Ticket command:

```json
{"entries":[{"kind":"stop","text":"<human-readable reason>"}]}
```

- Hook-internal error that should surface without using the unsupported legacy
  decision fields:

```json
{"entries":[{"kind":"error","text":"<human-readable reason>"}]}
```

Required transcript checks:

- Allowed pass-through and allowed Ticket commands produce `hook/completed` with
  `status == "completed"`.
- Allowed pass-through and allowed Ticket commands produce no hook output entries
  unless Task 2 deliberately adds `feedback` or `context` entries and proves they
  are accepted without warnings.
- Allowed pass-through and allowed Ticket commands do not emit
  `hookSpecificOutput`, `permissionDecision`, or unsupported-output warnings.
- Blocked Ticket commands produce a `hook/completed` record with
  `status == "stopped"` whose entries include exactly one
  `{"kind":"stop","text": ...}` item, and the guarded Bash command must not
  execute.
- If regenerated schema contradicts this contract, stop before Task 2 hook
  repair and patch this section from the regenerated schema evidence first.
- If regenerated schema matches the notification shape but the live hook-output
  probe proves a different stdout control API, follow the live command-hook
  behavior and patch this plan before changing the guard.

## Non-Goals

- Do not mutate `/Users/jp/.codex/plugins/cache`.
- Do not run guarded refresh, plugin install, personal-plugin sync, or
  marketplace edits.
- Do not broaden activation to `ticket_capture.py`, `ticket_update.py`, or
  `ticket_workflow.py`.
- Do not add `ticket_capture_agent.py` or `ticket_update_agent.py`.
- Do not add a public payload field or CLI flag that selects `execute_surface`.
- Do not use AgentControl child traversal smoke as a substitute for host-policy
  proof or deterministic primary-driver proof.
- Do not use prompt-driven app-server turns as blocking proof input.
- Do not use `dangerFullAccess` as activation fallback.
- Do not claim real consuming-project migration outside this repo.
- Do not claim host-owned agent identity.
- Do not gate ingest or read-only commands.

## Source Files To Read First

Before implementation, re-read these live files:

- `.gitignore`
- `docs/tickets/2026-05-18-activation-capable-ticket-runtime-readiness.md`
- `docs/superpowers/plans/2026-05-18-ticket-autonomy-ingest-contract-hardening.md`
- `plugins/turbo-mode/ticket/README.md`
- `plugins/turbo-mode/ticket/.codex-plugin/plugin.json`
- `plugins/turbo-mode/ticket/hooks/hooks.json`
- `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py`
- `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
- `plugins/turbo-mode/ticket/scripts/ticket_triage.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_agent.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- `plugins/turbo-mode/ticket/scripts/ticket_stage_models.py`
- `plugins/turbo-mode/ticket/scripts/ticket_trust.py`
- `plugins/turbo-mode/ticket/HANDBOOK.md`
- `plugins/turbo-mode/ticket/references/ticket-contract.md`
- `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`
- `plugins/turbo-mode/tools/refresh/app_server_inventory.py`
- `plugins/turbo-mode/tools/refresh/tests/test_app_server_inventory.py`

## File Structure

- `docs/superpowers/plans/2026-05-20-ticket-runtime-readiness-activation.md`
  - this control document
- `.gitignore`
  - narrow project-local ignores for Ticket runtime proof and smoke artifacts;
    must not hide unrelated `.codex/**` content
- `plugins/turbo-mode/tools/refresh/app_server_turn_driver.py`
  - disposable Task 0 diagnostic helper for Gate B only; Task 2 may replace it
    with Ticket-owned runtime-readiness code
- `plugins/turbo-mode/tools/refresh/tests/test_app_server_turn_driver.py`
  - focused tests for the disposable driver request sequence, transcript shape,
    write boundary, and no Ticket-runtime import/proof-write behavior
- `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
  - new Ticket-owned runtime inventory, direct-execute smoke, proof writer, and
    verifier
- `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
  - add `activate-runtime` and structured blocker reporting
- `plugins/turbo-mode/ticket/scripts/ticket_triage.py`
  - keep `diagnose` read-only; optionally inspect proof status without writing it
- `plugins/turbo-mode/ticket/scripts/ticket_engine_activation_smoke.py`
  - dedicated bootstrap entrypoint for contained activation smoke only
- `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
  - add direct-execute-only runtime-readiness gate for agent `auto_audit`
- `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
  - pass internal proof-binding context for the direct execute path only
- `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py`
  - align output contract with app-server and allow canonical activation-smoke
    command through the normal membrane
- `plugins/turbo-mode/ticket/references/ticket-contract.md`
  - document trust boundary, proof class, direct-execute-only scope, and
  diagnostic-only evidence
- `plugins/turbo-mode/ticket/README.md`
  - document that live activation V1 certifies only `ticket_engine_agent.py`
- `plugins/turbo-mode/ticket/HANDBOOK.md`
  - keep operator-facing trust and activation language consistent with README
    and `ticket-contract.md`
- `plugins/turbo-mode/ticket/scripts/ticket_ux.py`
  - map runtime-readiness and blocker errors to recovery guidance
- `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`
  - add activation workflow and blocker semantics
- `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`
  - inventory, proof, smoke, and verifier tests
- `plugins/turbo-mode/ticket/tests/test_doctor.py`
  - doctor activation command tests
- `plugins/turbo-mode/ticket/tests/test_execute.py`
  - direct-execute gate coverage
- `plugins/turbo-mode/ticket/tests/test_engine_runner.py`
  - internal proof-binding context coverage
- `plugins/turbo-mode/ticket/tests/test_ingest.py`
  - ingest remains ungated
- `plugins/turbo-mode/ticket/tests/test_hook.py`
  - hook output contract plus activation-smoke allow-path coverage
- `plugins/turbo-mode/ticket/tests/test_hook_integration.py`
  - subprocess-level hook contract coverage that must move with the new
    app-server-supported hook output shape
- `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
  - docs and skill contract checks
- `plugins/turbo-mode/ticket/tests/test_ux.py`
  - UX mapping for activation failures

## Activation Proof Schema

The final proof stays small enough to inspect manually, but it is only an index
to raw evidence under the contained smoke run directory.

```json
{
  "schema_version": "installed_ticket_runtime_readiness-v1",
  "status": "activated",
  "created_at": "2026-05-20T00:00:00Z",
  "expires_at": "2026-05-21T00:00:00Z",
  "run_nonce": "ticket-runtime-20260520T000000Z-0123456789abcdef",
  "project_root": "/absolute/project/root",
  "ticket_plugin": {
    "plugin_id": "ticket@turbo-mode",
    "name": "ticket",
    "version": "1.4.0",
    "installed_cache_root": "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0",
    "plugin_manifest_path": "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/.codex-plugin/plugin.json",
    "plugin_manifest_sha256": "<sha256>"
  },
  "runtime_identity": {
    "codex_version": "codex-cli 0.x.y",
    "executable_path": "/absolute/path/to/codex",
    "executable_sha256": "<sha256-or-null>",
    "accepted_response_schema_version": "ticket-app-server-readiness-v1",
    "parser_version": "installed-ticket-runtime-readiness-v1"
  },
  "inventory": {
    "request_methods": [
      "initialize",
      "initialized",
      "plugin/read",
      "plugin/list",
      "skills/list",
      "hooks/list"
    ],
    "marketplace_path": "/absolute/path/to/.agents/plugins/marketplace.json",
    "cwd": "/absolute/project/root",
    "transcript_sha256": "<sha256>",
    "plugin_read_source_path": "/absolute/source/root/plugins/turbo-mode/ticket",
    "installed_runtime_root": "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0",
    "hook": {
      "plugin_id": "ticket@turbo-mode",
      "event_name": "preToolUse",
      "matcher": "Bash",
      "hook_manifest_path": "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/hooks.json",
      "hook_manifest_sha256": "<sha256>",
      "guard_command": "python3 /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/ticket_engine_guard.py",
      "guard_script_path": "/Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/hooks/ticket_engine_guard.py",
      "guard_script_sha256": "<sha256>"
    }
  },
  "hook_membrane_proof": {
    "runner": "app_server_turn",
    "status": "passed",
    "command": "python3 -B /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_engine_activation_smoke.py execute /absolute/project/root/.codex/ticket-runtime-smoke/<run_nonce>/payload.json",
    "smoke_project_root": ".codex/ticket-runtime-smoke/<run_nonce>",
    "cwd": ".codex/ticket-runtime-smoke/<run_nonce>",
    "payload_path": ".codex/ticket-runtime-smoke/<run_nonce>/payload.json",
    "tickets_dir": ".codex/ticket-runtime-smoke/<run_nonce>/docs/tickets",
    "hook_request_origin": "user",
    "hook_injected": true,
    "session_id": "<non-empty-session-id>",
    "nonce": "ticket-runtime-20260520T000000Z-0123456789abcdef",
    "engine_stdout_sha256": "<sha256>",
    "engine_state": "ok_create",
    "ticket_path": ".codex/ticket-runtime-smoke/<run_nonce>/docs/tickets/2026-05-20-example.md",
    "ticket_sha256": "<sha256>",
    "audit_file_path": ".codex/ticket-runtime-smoke/<run_nonce>/docs/tickets/.audit/2026-05-20/<session>.jsonl",
    "audit_file_sha256": "<sha256>"
  },
  "agentcontrol_hook_traversal_smoke": {
    "runner": "agentcontrol_child_turn",
    "status": "not_captured",
    "reason": "no_concrete_harness_named",
    "captured_example_shape": {
      "status": "captured",
      "command": "python3 -B /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_engine_activation_smoke.py execute /absolute/project/root/.codex/ticket-runtime-smoke/<run_nonce>/agentcontrol/payload.json",
      "same_hook_command": true,
      "same_hook_manifest_sha256": "<sha256>",
      "same_guard_script_sha256": "<sha256>",
      "hook_request_origin": "user",
      "hook_injected": true,
      "session_id": "<non-empty-session-id>",
      "payload_sha256": "<sha256>",
      "raw_events_sha256": "<sha256>",
      "engine_state": "ok_create"
    }
  },
  "post_activation_gated_smokes": {
    "status": "passed",
    "required_surfaces": ["direct_execute"],
    "surface_results": {
      "direct_execute": {
        "runner": "app_server_turn",
        "command": "python3 -B /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_engine_agent.py execute /absolute/project/root/.codex/ticket-runtime-smoke/<run_nonce>/post-direct/post-direct-payload.json",
        "execute_surface": "direct_execute",
        "runtime_readiness_required": true,
        "engine_state": "ok_create",
        "raw_events_sha256": "<sha256>",
        "engine_stdout_sha256": "<sha256>",
        "ticket_path": ".codex/ticket-runtime-smoke/<run_nonce>/post-direct/docs/tickets/2026-05-20-example.md",
        "ticket_sha256": "<sha256>"
      }
    }
  },
  "activation_scope": {
    "gated_execute_surfaces": ["direct_execute"],
    "certified_entrypoints": ["ticket_engine_agent.py"],
    "certified_policy_lane": "ticket_engine_agent.py execute + autonomy_mode=auto_audit",
    "excluded_mutation_paths": [
      "ingest_dispatch",
      "activation_smoke_bootstrap",
      "ticket_capture.py",
      "ticket_update.py",
      "ticket_workflow.py"
    ],
    "autonomy_mode": "auto_audit",
    "caller_identity_proven": false,
    "hook_request_origin_contract": "provenance_metadata_only_currently_user"
  },
  "raw_evidence": {
    "run_dir": ".codex/ticket-runtime-smoke/<run_nonce>",
    "app_server_inventory_transcript": "raw/app-server-inventory-transcript.jsonl",
    "app_server_transcript": "raw/app-server-transcript.jsonl",
    "hook_membrane_events": "raw/hook-membrane-events.jsonl",
    "agentcontrol_hook_traversal_events": null,
    "post_activation_events": "raw/post-activation-gated-events.jsonl",
    "payload_before": "raw/payload-before.json",
    "payload_after": "raw/payload-after.json",
    "engine_stdout": "raw/engine-stdout.json",
    "engine_stderr": "raw/engine-stderr.txt"
  }
}
```

When a concrete AgentControl harness exists during installed activation,
`agentcontrol_hook_traversal_smoke.status` may be `captured` and must match the
captured example shape, and `raw_evidence.agentcontrol_hook_traversal_events`
must point at the captured raw transcript. Without a concrete harness, `status`
must remain `not_captured`, `raw_evidence.agentcontrol_hook_traversal_events`
must be `null`, and the proof must include a reason. That does not block V1
direct-execute activation and must not be described as identity proof.

Rules:

- `required_surfaces` must be exactly `["direct_execute"]` in V1.
- No `capture_execute` or `update_execute` fields may appear in a successful V1
  proof.
- The proof must bind installed root identity from live `hooks/list` plus
  corroborating `skills/list`, not from `plugin/read` alone.
- The proof file is an index over bound evidence only; acceptance requires
  revalidating the hashes and transcripts named by the file.
- The proof must reject raw-evidence deletion, stale age, path drift,
  executing-root mismatch, stale or mismatched installed plugin manifest hash,
  stale or mismatched hook manifest hash, stale or mismatched guard script hash,
  inventory transcript hash mismatch, hook membrane transcript hash mismatch,
  post-activation transcript hash mismatch, nonce mismatch, or payload hash
  mismatch.
- `raw_evidence.agentcontrol_hook_traversal_events` is required only when
  `agentcontrol_hook_traversal_smoke.status == "captured"`; it must be `null`
  when status is `not_captured`.
- If `agentcontrol_hook_traversal_smoke.status == "captured"`, the verifier must
  validate its raw transcript and same-hook bindings.
- If `agentcontrol_hook_traversal_smoke.status == "not_captured"`, the verifier
  must require a reason and must not treat the missing traversal as caller
  identity evidence.

## Verification Harness

Focused tests while implementing:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_runtime_readiness.py \
  tests/test_doctor.py \
  tests/test_engine_runner.py \
  tests/test_execute.py \
  tests/test_ingest.py \
  tests/test_hook.py \
  tests/test_hook_integration.py \
  tests/test_docs_contract.py \
  tests/test_ux.py \
  -q
```

Full Ticket suite:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

Changed-path lint:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check \
  plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py \
  plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
  plugins/turbo-mode/ticket/scripts/ticket_triage.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_activation_smoke.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py \
  plugins/turbo-mode/ticket/scripts/ticket_ux.py \
  plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py \
  plugins/turbo-mode/ticket/tests/test_runtime_readiness.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py \
  plugins/turbo-mode/ticket/tests/test_engine_runner.py \
  plugins/turbo-mode/ticket/tests/test_execute.py \
  plugins/turbo-mode/ticket/tests/test_ingest.py \
  plugins/turbo-mode/ticket/tests/test_hook.py \
  plugins/turbo-mode/ticket/tests/test_hook_integration.py \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py \
  plugins/turbo-mode/ticket/tests/test_ux.py
```

Whitespace gate:

```bash
git diff --check
```

Local runtime artifact ignore gate:

```bash
git check-ignore -v .codex/ticket-runtime-proof.json
git check-ignore -v .codex/ticket-runtime-smoke-preflight/app-server-driver-preflight.jsonl
git check-ignore -v .codex/ticket-runtime-smoke/example/raw/app-server-transcript.jsonl
```

Expected: each command reports the narrow `.gitignore` rule that covers the
path. If any command prints nothing, patch `.gitignore` before generating the
artifact. A final `git status --short` must not show `.codex/ticket-runtime-*`
paths as untracked source material.

Live CLI and schema preflight:

```bash
codex --version
codex app-server --help
codex app-server generate-json-schema --experimental --out /private/tmp/codex-app-schema
```

Installed activation check, only after explicit installed refresh and only after
Gates A/B pass, Task 2 source-local hook-contract repair/tests pass, and the
Task 4 direct-execute engine gate plus final activation-promotion tests pass:

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_doctor.py \
  activate-runtime /Users/jp/Projects/active/codex-tool-dev/docs/tickets \
  --marketplace-path /Users/jp/Projects/active/codex-tool-dev/.agents/plugins/marketplace.json
```

Expected live success shape after refresh:

- `state == "ok"`
- `data.mode == "activate-runtime"`
- `data.proof.status == "activated"`
- `data.proof.activation_scope.gated_execute_surfaces == ["direct_execute"]`

This is the first point in the plan where the new canonical
`ticket_engine_activation_smoke.py execute` command is required to exist in the
installed cache and prove itself live. This is also the point where Gate C
becomes blocking again on the installed runtime: if the refreshed installed hook
still emits unsupported output, activation must fail closed with
`hook_contract_blocked`.

## Stop Conditions

- If Gate A fails, stop with `host_policy_blocked`.
- If Gate B fails, stop with `deterministic_driver_unavailable`.
- If `.codex/ticket-runtime-proof.json`,
  `.codex/ticket-runtime-smoke-preflight/`, or `.codex/ticket-runtime-smoke/`
  is not ignored by a narrow `.gitignore` rule before a command writes it, stop
  and patch the ignore policy before continuing.
- If generated proof or smoke artifacts appear in `git status --short` as
  ordinary untracked source material, stop and fix the ignore policy before
  staging or committing anything.
- If inventory cannot prove exactly one Ticket Bash `preToolUse` hook, stop.
- If the smoke cannot prove exactly one canonical `commandExecution` plus one
  same-turn installed `hook/completed`, stop.
- If the certified direct-execute lane still returns `origin_mismatch` because
  the current host reports `hook_request_origin="user"`, stop and fix the
  runner/core hook-membrane contract before continuing.
- If Task 2 cannot add source-local coverage proving
  `ticket_engine_activation_smoke.py execute` exists and is accepted by the
  source hook allowlist, stop before Task 3.
- If Task 2 cannot replace the current unsupported hook output contract with a
  source-local app-server-accepted contract and prove it in focused tests, stop
  before Task 3.
- If `ticket_doctor.py activate-runtime` writes
  `.codex/ticket-runtime-proof.json` or runs the final post-proof
  `direct_execute` smoke before the Task 4 engine gate exists and passes, stop.
- If the smoke can mutate outside the contained smoke tickets directory, stop.
- If a concrete AgentControl traversal harness is named and captured during
  installed activation, but the resulting smoke does not traverse the same
  installed hook membrane, stop.
- If the activation bootstrap bypass can be selected by normal entrypoints,
  payload fields, or CLI flags, stop.
- If the proof does not bind installed executing root and current hashes, stop.
- If implementation pressure expands scope to capture/update wrappers, stop and
  split that into a separate follow-up ticket.
- If docs start claiming host-owned agent identity or real consumer migration,
  stop and rewrite the wording before merge.

## Commit Boundaries

- Commit 1: this plan only.
- Commit 2: narrow local-runtime artifact ignore policy if needed, disposable
  Gate B driver, direct-execute proof schema, and verifier tests.
- Commit 3: inventory collector, hook contract preflight, and deterministic
  smoke runner.
- Commit 4: `ticket_doctor.py activate-runtime` diagnostics and candidate-proof
  wiring only; no final proof write.
- Commit 5: direct-execute engine gate and final activation-proof promotion.
- Commit 6: docs, skill wording, and final verification.

---

### Task 0: Baseline And Prerequisite Gates

**Files:**

- Read: `docs/superpowers/plans/2026-05-20-ticket-runtime-readiness-activation.md`
- Read: `docs/tickets/2026-05-18-activation-capable-ticket-runtime-readiness.md`
- Read: `plugins/turbo-mode/ticket/README.md`
- Add or update only if missing/broken:
  `plugins/turbo-mode/tools/refresh/app_server_turn_driver.py`
- Add or update only if the driver is missing/broken:
  `plugins/turbo-mode/tools/refresh/tests/test_app_server_turn_driver.py`

- [ ] **Step 1: Confirm branch and dirty state**

```bash
git status --short --branch
```

Expected: branch and dirty state recorded. Preserve unrelated dirty work.

- [ ] **Step 2: Reconcile base explicitly**

```bash
git rev-list --left-right --count origin/main...HEAD
```

Expected: base status recorded and explicitly reconciled. `0 0` is the cleanest
implementation base. Any other output is a blocker until the worker records the
chosen reconciliation: rebase/merge/switch from the current `HEAD`, or treat the
current plan/docs patch as pre-implementation draft state and start
implementation only after branch/base cleanup.

- [ ] **Step 3: Create implementation branch after base reconciliation**

```bash
git switch -c fix/ticket-runtime-readiness-activation-v1
```

Expected: all remaining implementation and any disposable Gate B driver edits
happen on the fix branch.

- [ ] **Step 3.5: Establish local runtime artifact ignore policy**

Run before any Gate A/B command that writes under `.codex/ticket-runtime-*`:

```bash
git check-ignore -v .codex/ticket-runtime-proof.json
git check-ignore -v .codex/ticket-runtime-smoke-preflight/app-server-driver-preflight.jsonl
git check-ignore -v .codex/ticket-runtime-smoke/example/raw/app-server-transcript.jsonl
```

Expected: each command reports a narrow `.gitignore` rule for the named Ticket
runtime proof/smoke path. If any command prints no match, patch `.gitignore`
with exactly:

```gitignore
.codex/ticket-runtime-proof.json
.codex/ticket-runtime-smoke-preflight/
.codex/ticket-runtime-smoke/
```

Then rerun the `git check-ignore -v` commands. Do not add or accept a broad
`.codex/` ignore rule; `.codex/skills/**` and other source-owned `.codex`
content must remain trackable.

- [ ] **Step 4: Prepare the disposable Gate B driver if missing/broken**

Allowed scope:

- add narrow Ticket runtime proof/smoke rules to `.gitignore` only if Step 3.5
  proves they are missing
- add or repair `plugins/turbo-mode/tools/refresh/app_server_turn_driver.py`
- add or repair `plugins/turbo-mode/tools/refresh/tests/test_app_server_turn_driver.py`
- write only preflight artifacts under
  `<PROJECT_ROOT>/.codex/ticket-runtime-smoke-preflight/`
- do not import Ticket runtime code
- do not write `.codex/ticket-runtime-proof.json`
- do not mutate `/Users/jp/.codex/plugins/cache`

Focused test command:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run pytest plugins/turbo-mode/tools/refresh/tests/test_app_server_turn_driver.py -q
```

Expected: PASS, or the worker records why the disposable driver cannot satisfy
Gate B and stops with `deterministic_driver_unavailable`.

- [ ] **Step 5: Validate Gate A**

Required outcome:

- fresh evidence that the contained `workspaceWrite` turn now works on this host
- no recurrence of
  `sandbox-exec: sandbox_apply: Operation not permitted`
- the already-installed probe command reaches command execution plus installed
  hook traversal:

```bash
python3 -B <INSTALLED_TICKET_ROOT>/scripts/ticket_engine_agent.py execute <PAYLOAD_PATH>
```

If that exact blocker still reproduces or no fresh contrary evidence exists,
stop with `host_policy_blocked`.

- [ ] **Step 6: Validate Gate B**

Required outcome:

- one non-prompted preflight transcript at
  `<PROJECT_ROOT>/.codex/ticket-runtime-smoke-preflight/app-server-driver-preflight.jsonl`
  showing:
  - raw rows shaped as `{"direction": "send"|"recv", "body": ...}`
  - `initialize`, `initialized`, `thread/start`, and `turn/start`
  - `thread/start.params.ephemeral == true` when supported by the regenerated
    app-server schema, or an explicit
    `app_server_state_scope=runtime_local_diagnostic` classification if the
    host persists app-server thread/turn state outside the project-local
    preflight directory
  - exactly one canonical `commandExecution`
  - exactly one same-turn installed Ticket `hook/completed`
  - no approval-request methods
- the transcript was produced by
  `plugins/turbo-mode/tools/refresh/app_server_turn_driver.py`, not an unnamed
  spike

Run:

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run python plugins/turbo-mode/tools/refresh/app_server_turn_driver.py \
  --project-root /Users/jp/Projects/active/codex-tool-dev \
  --contained-root /Users/jp/Projects/active/codex-tool-dev/.codex/ticket-runtime-smoke-preflight/contained \
  --installed-ticket-root /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0 \
  --marketplace-path /Users/jp/Projects/active/codex-tool-dev/.agents/plugins/marketplace.json \
  --out /Users/jp/Projects/active/codex-tool-dev/.codex/ticket-runtime-smoke-preflight/app-server-driver-preflight.jsonl
```

The canonical command for this gate is:

```bash
python3 -B <INSTALLED_TICKET_ROOT>/scripts/ticket_engine_agent.py execute <PAYLOAD_PATH>
```

Do not count readonly output from
`plugins/turbo-mode/tools/refresh/app_server_inventory.py` as a Gate B pass by
itself.

For Gate B only, a post-hook engine-layer failure from the probe command is
acceptable if the transcript still proves exactly one contained
`commandExecution` item and one same-turn installed `hook/completed`.

If the named driver cannot produce that exact transcript non-interactively, stop
with `deterministic_driver_unavailable`.

- [ ] **Step 7: Capture Gate C diagnostic status**

Required outcome:

- either:
  - installed hook completion is already accepted by app-server without
    unsupported `permissionDecision` warnings
  - or the current installed failure is recorded as
    `hook_contract_needs_source_repair` for Task 2

If the installed hook still fails this diagnostic, record it and continue to
Task 2. Do not claim installed readiness from the diagnostic pass/fail state
alone.

---

### Task 1: Proof Schema And Base Verifier

**Files:**

- Modify only if Task 0 proves the narrow local runtime artifact ignores are
  missing: `.gitignore`
- Add or keep from Task 0:
  `plugins/turbo-mode/tools/refresh/app_server_turn_driver.py`
- Add or keep from Task 0:
  `plugins/turbo-mode/tools/refresh/tests/test_app_server_turn_driver.py`
- Add: `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- Add: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`

- [ ] **Step 1: Add failing verifier tests**

Test cases:

- missing proof file rejects agent direct execute
- source-checkout execution cannot satisfy installed-runtime proof
- handwritten or copied JSON without matching evidence rejects
- proof with deleted raw evidence rejects
- proof with stale age rejects
- proof with mismatched current `plugin_manifest_sha256` rejects
- proof with mismatched current `hook_manifest_sha256` rejects
- proof with mismatched current `guard_script_sha256` rejects
- proof with mismatched inventory transcript hash rejects
- proof with mismatched hook membrane transcript hash rejects
- proof with mismatched post-activation transcript hash rejects
- proof with mismatched installed executing root rejects
- proof with mismatched nonce or payload hash rejects
- proof with `gated_execute_surfaces != ["direct_execute"]` rejects in V1
- proof naming `capture_execute` or `update_execute` rejects in V1

- [ ] **Step 2: Implement base proof schema and verifier**

Implementation requirements:

- expose `verify_installed_ticket_runtime_readiness_for_execute()`
- bind proof target project root separately from contained smoke root
- derive executing plugin root from `Path(__file__).resolve().parents[1]`
- reject caller-supplied plugin-root or cache-root impersonation
- require `activation_scope.gated_execute_surfaces == ["direct_execute"]`
- re-hash and compare the current installed plugin manifest, hook manifest, guard
  script, raw inventory transcript, raw hook membrane transcript, raw
  post-activation transcript, payload, and nonce before accepting the proof

- [ ] **Step 3: Run focused tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_runtime_readiness.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit schema and verifier**

```bash
git add \
  .gitignore \
  plugins/turbo-mode/tools/refresh/app_server_turn_driver.py \
  plugins/turbo-mode/tools/refresh/tests/test_app_server_turn_driver.py \
  plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py \
  plugins/turbo-mode/ticket/tests/test_runtime_readiness.py
git commit -m "feat(ticket): add direct-execute runtime proof verifier"
```

---

### Task 2: Inventory Collector, Source-Local Activation Command, And Deterministic Smoke Runner

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- Add: `plugins/turbo-mode/ticket/scripts/ticket_engine_activation_smoke.py`
- Modify: `plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_hook.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_hook_integration.py`

- [ ] **Step 1: Add failing inventory and smoke tests**

Test cases:

- inventory sends exactly `initialize`, `initialized`, `plugin/read`,
  `plugin/list`, `skills/list`, `hooks/list`
- inventory rejects zero or duplicate Ticket hooks
- smoke rejects anything other than one canonical command
- smoke rejects missing or failed same-turn `hook/completed`
- smoke rejects mutation outside contained smoke tickets dir
- verifier accepts fixture-shaped `agentcontrol_hook_traversal_smoke` evidence
  only when raw transcript hashes and same-hook bindings match
- verifier accepts `agentcontrol_hook_traversal_smoke.status == "not_captured"`
  only when `raw_evidence.agentcontrol_hook_traversal_events is None` and an
  explicit reason is present, without treating it as caller-identity proof
- hook tests reject unsupported output shape and allow only the canonical
  activation-smoke command
- hook integration tests stop asserting `hookSpecificOutput.permissionDecision`
  and instead validate the repaired app-server-supported hook output contract
- source-local hook tests prove the repaired hook output contract is accepted by
  app-server semantics and no longer emits the current unsupported
  `permissionDecision` shape
- source-local tests prove `ticket_engine_activation_smoke.py` exists and the
  source hook allowlist accepts exactly its canonical command shape once added

- [ ] **Step 2: Implement collector and smoke runner**

Implementation requirements:

- copy only constants-free patterns from
  `plugins/turbo-mode/tools/refresh/app_server_inventory.py`
- keep Ticket runtime code independent from the refresh tooling package
- collect raw inventory transcript and raw smoke transcript separately
- implement verifier semantics for optional AgentControl child traversal evidence:
  validate a fixture-shaped captured transcript when provided, and allow
  `not_captured` with a reason when no concrete live harness exists
- drive only the canonical bootstrap command:

```bash
python3 -B <INSTALLED_TICKET_ROOT>/scripts/ticket_engine_activation_smoke.py execute <PAYLOAD_PATH>
```

- treat that command as source-local only until explicit installed refresh; do
  not require it to exist in the installed cache before Task 6
- replace the current unsupported hook output contract in
  `ticket_engine_guard.py` with the app-server-supported allow/deny output shape
  required by the new focused tests
- write `raw/engine-stdout.json`, payload before/after snapshots, ticket hash,
  and audit hash under the contained smoke run directory
- do not use prompt text as proof input
- treat AgentControl child traversal as optional installed-activation
  corroboration, not as caller-identity proof or a substitute for the primary
  deterministic driver

- [ ] **Step 3: Run focused tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_runtime_readiness.py \
  tests/test_hook.py \
  tests/test_hook_integration.py \
  -q
```

Expected: PASS.

- [ ] **Step 3.5: Enforce the post-Task-2 stop boundary**

Required outcome:

- source-local focused tests now prove the new canonical activation-smoke
  command exists in source and is accepted by the source hook allowlist
- source-local focused tests now prove the repaired hook output contract no
  longer emits the unsupported `permissionDecision` shape
- source-local focused tests now prove verifier handling for
  `agentcontrol_hook_traversal_smoke`: captured fixture evidence must bind to the
  same hook identity and a raw transcript path, while `not_captured` requires a
  reason, requires no raw transcript path, and is not identity proof

If that source-local proof is missing, stop before Task 3. Do not continue on
the assumption that the installed cache will fix it later.

- [ ] **Step 4: Commit inventory and smoke**

```bash
git add \
  plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_activation_smoke.py \
  plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py \
  plugins/turbo-mode/ticket/tests/test_runtime_readiness.py \
  plugins/turbo-mode/ticket/tests/test_hook.py \
  plugins/turbo-mode/ticket/tests/test_hook_integration.py
git commit -m "feat(ticket): add direct-execute activation smoke"
```

---

### Task 3: Doctor Activation Diagnostics And Candidate Proof Plumbing

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_triage.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_doctor.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`

- [ ] **Step 1: Add failing doctor tests**

Test cases:

- Gate A failure returns `policy_blocked` with `error_code=host_policy_blocked`
- Gate B failure returns `policy_blocked` with
  `error_code=deterministic_driver_unavailable`
- post-refresh installed hook-contract failure returns `policy_blocked` with
  `error_code=hook_contract_blocked`
- `activate-runtime` can build and validate a candidate proof from live inventory
  plus bootstrap smoke, but does not write `.codex/ticket-runtime-proof.json`
  before the direct-execute engine gate exists
- `diagnose` stays read-only and never promotes proof
- candidate activation records `agentcontrol_hook_traversal_smoke.status` as
  either `not_captured` with a reason, or `captured` with same-hook membrane
  bindings if a concrete harness is supplied

- [ ] **Step 2: Implement `activate-runtime`**

Implementation requirements:

- build candidate proof from live inventory plus bootstrap smoke
- keep the candidate proof in memory or under the contained smoke run directory;
  do not write or promote `.codex/ticket-runtime-proof.json` in Task 3
- do not run the final post-proof `ticket_engine_agent.py execute` smoke in Task
  3, because the direct-execute readiness gate is not implemented until Task 4
- make any attempted final activation report `policy_blocked` with
  `error_code=engine_gate_required` until Task 4 wires promotion
- surface blocker codes explicitly in JSON response
- fail closed with `hook_contract_blocked` if the refreshed installed hook still
  emits unsupported output during live activation
- do not add `--plugin-root` or `--cache-root`

- [ ] **Step 3: Run focused tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_doctor.py \
  tests/test_runtime_readiness.py \
  -q
```

Expected: PASS.

- [ ] **Step 4: Commit doctor diagnostics**

```bash
git add \
  plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
  plugins/turbo-mode/ticket/scripts/ticket_triage.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py \
  plugins/turbo-mode/ticket/tests/test_runtime_readiness.py
git commit -m "feat(ticket): add runtime activation diagnostics"
```

---

### Task 4: Origin Decoupling, Direct-Execute Engine Gate, And Final Proof Promotion

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_doctor.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_triage.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_execute.py`
- Add: `plugins/turbo-mode/ticket/tests/test_engine_runner.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_ingest.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_doctor.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`

- [ ] **Step 1: Add failing gate tests**

Test cases:

- `ticket_engine_agent.py execute` with hardcoded entrypoint lane and
  hook-injected `hook_request_origin="user"` reaches the runtime-readiness gate
  instead of failing early with `origin_mismatch`
- `ticket_engine_agent.py execute` with `request_origin="agent"` and
  `autonomy_mode: auto_audit` fails with
  `runtime_readiness_required` when proof is absent
- same path succeeds when a valid activated proof is present and executing root
  matches
- `activate-runtime` now runs the final post-proof smoke only for
  `direct_execute`
- successful activation writes `.codex/ticket-runtime-proof.json` only after the
  direct-execute gate is present and closeout verification passes
- candidate proof with `status="activation_in_progress"` cannot satisfy normal
  execute
- ingest stays ungated
- no payload field can claim `direct_execute` certification on behalf of an
  uncertified path
- activation bootstrap bypass remains private to
  `ticket_engine_activation_smoke.py`
- non-certified flows must not treat `hook_request_origin` as caller identity or
  as a bypass into the certified direct-execute lane

- [ ] **Step 2: Implement the gate**

Implementation requirements:

- in `ticket_engine_runner.py`, keep hardcoded entrypoint `request_origin`
  authoritative when the caller supplies it; preserve `hook_request_origin` as
  separate metadata instead of failing early on the current host's
  `"user"` observation
- in `ticket_engine_core.py`, replace the blanket
  `hook_request_origin != request_origin` rejection with the V1 trust boundary:
  require hook traversal metadata to be present, but do not require equality for
  the certified direct-execute lane on the current host
- do not let workflow, capture, update, or payload fields elevate themselves to
  certified direct-execute readiness through hook metadata
- keep `direct_execute` internal to the certified entrypoint path
- do not add a public `execute_surface` payload field in V1
- pass internal proof-binding context from runner to core only for execute
- reject normal execution if proof is absent, stale, or mismatched
- leave user-origin mutation behavior unchanged
- complete `ticket_doctor.py activate-runtime` promotion only in this task:
  revalidate the candidate proof, run the gated post-proof direct-execute smoke,
  run closeout verification, then write the final proof
- keep `engine_gate_required` until the promotion path can prove the engine gate
  behavior with focused tests

- [ ] **Step 3: Run focused tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_execute.py \
  tests/test_engine_runner.py \
  tests/test_ingest.py \
  tests/test_doctor.py \
  tests/test_runtime_readiness.py \
  -q
```

Expected: PASS.

- [ ] **Step 4: Commit engine gate**

```bash
git add \
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py \
  plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
  plugins/turbo-mode/ticket/scripts/ticket_triage.py \
  plugins/turbo-mode/ticket/tests/test_execute.py \
  plugins/turbo-mode/ticket/tests/test_engine_runner.py \
  plugins/turbo-mode/ticket/tests/test_ingest.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py \
  plugins/turbo-mode/ticket/tests/test_runtime_readiness.py
git commit -m "feat(ticket): gate direct execute and promote runtime proof"
```

---

### Task 5: Docs And Skill Contract

**Files:**

- Modify: `plugins/turbo-mode/ticket/README.md`
- Modify: `plugins/turbo-mode/ticket/HANDBOOK.md`
- Modify: `plugins/turbo-mode/ticket/references/ticket-contract.md`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_ux.py`
- Modify: `plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md`
- Modify: `plugins/turbo-mode/ticket/tests/test_docs_contract.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_ux.py`

- [ ] **Step 1: Read writing-principles before doc edits**

```bash
sed -n '1,220p' /Users/jp/.agents/skills/writing-principles/SKILL.md
```

Expected: guidance read before editing instruction-style docs.

- [ ] **Step 2: Add failing docs tests**

Assertions to add:

- README, `HANDBOOK.md`, and `ticket-contract.md` say activation V1 certifies
  only
  `ticket_engine_agent.py execute`
- docs say activation proves hook-mediated wiring, not host-owned agent identity
- docs say `hook_request_origin` is metadata-only on the current host and no
  longer an equality gate for the certified direct-execute path
- docs say wrapper capture/update paths are out of scope and require a separate
  follow-up
- docs say `dangerFullAccess` and prompt-driven smokes are diagnostics only, and
  AgentControl child smoke is optional installed-activation corroboration rather
  than identity proof
- doctor skill documents blocker codes, including `engine_gate_required`, and
  direct-execute-only scope

- [ ] **Step 3: Update docs and UX**

Required wording:

- direct, explicit trust-boundary language
- no stale operator text that says hook `agent_id` presence determines
  `request_origin` for the current activation contract
- no claim of consumer migration outside this repo
- no claim of AgentControl identity proof or prompt-harness fallback
- explicit wording that captured AgentControl child smoke, when a concrete
  harness exists, proves same-membrane traversal only
- recovery guidance for `host_policy_blocked`,
  `deterministic_driver_unavailable`, `hook_contract_blocked`,
  `engine_gate_required`, and `runtime_readiness_required`

- [ ] **Step 4: Run docs and UX tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_docs_contract.py \
  tests/test_ux.py \
  -q
```

Expected: PASS.

- [ ] **Step 5: Commit docs**

```bash
git add \
  plugins/turbo-mode/ticket/README.md \
  plugins/turbo-mode/ticket/HANDBOOK.md \
  plugins/turbo-mode/ticket/references/ticket-contract.md \
  plugins/turbo-mode/ticket/scripts/ticket_ux.py \
  plugins/turbo-mode/ticket/skills/ticket-doctor/SKILL.md \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py \
  plugins/turbo-mode/ticket/tests/test_ux.py
git commit -m "docs(ticket): narrow activation contract to direct execute"
```

---

### Task 6: Final Verification And Approval-Gated Installed Activation

**Files:**

- Verify only; no planned source edits. Installed activation may write the
  project-local proof artifact only after the approval-gated refresh boundary is
  satisfied.

- [ ] **Step 1: Run focused implementation verification**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_runtime_readiness.py \
  tests/test_doctor.py \
  tests/test_engine_runner.py \
  tests/test_execute.py \
  tests/test_ingest.py \
  tests/test_hook.py \
  tests/test_hook_integration.py \
  tests/test_docs_contract.py \
  tests/test_ux.py \
  -q
```

Expected: PASS.

- [ ] **Step 2: Run full Ticket suite**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest -q
```

Expected: PASS.

- [ ] **Step 3: Run changed-path lint and whitespace gates**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run ruff check \
  plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py \
  plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
  plugins/turbo-mode/ticket/scripts/ticket_triage.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_activation_smoke.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py \
  plugins/turbo-mode/ticket/scripts/ticket_ux.py \
  plugins/turbo-mode/ticket/hooks/ticket_engine_guard.py \
  plugins/turbo-mode/ticket/tests/test_runtime_readiness.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py \
  plugins/turbo-mode/ticket/tests/test_engine_runner.py \
  plugins/turbo-mode/ticket/tests/test_execute.py \
  plugins/turbo-mode/ticket/tests/test_ingest.py \
  plugins/turbo-mode/ticket/tests/test_hook.py \
  plugins/turbo-mode/ticket/tests/test_hook_integration.py \
  plugins/turbo-mode/ticket/tests/test_docs_contract.py \
  plugins/turbo-mode/ticket/tests/test_ux.py
git diff --check
```

Expected: PASS.

- [ ] **Step 3.5: Run local runtime artifact visibility gates**

```bash
git check-ignore -v .codex/ticket-runtime-proof.json
git check-ignore -v .codex/ticket-runtime-smoke-preflight/app-server-driver-preflight.jsonl
git check-ignore -v .codex/ticket-runtime-smoke/example/raw/app-server-transcript.jsonl
git status --short
```

Expected:

- each `git check-ignore -v` command reports the narrow Ticket runtime
  proof/smoke rule from `.gitignore`
- `git status --short` does not show `.codex/ticket-runtime-proof.json`,
  `.codex/ticket-runtime-smoke-preflight/`, or `.codex/ticket-runtime-smoke/` as
  untracked source material

If any runtime proof or smoke artifact appears as ordinary untracked source
material, stop and repair the ignore policy before staging or committing.

- [ ] **Step 4: Source closeout if no explicit refresh approval exists**

If the source implementation is complete but the installed cache has not been
explicitly refreshed in this session, stop here and report:

`source repaired, installed runtime not activated`

This is the expected source-slice closeout, not an installed-readiness success.
Do not run the installed activation command against a stale cache copy.

- [ ] **Step 5: Approval-gated installed activation check**

Run this only after:

- the source implementation is complete
- the user explicitly approves a separate installed-cache refresh workflow
  outside this plan, or confirms that refresh already happened in this session
- the installed cache has been refreshed explicitly
- Gates A/B are freshly green on this host
- Task 2 source-local hook-contract repair/tests are green
- Task 4 direct-execute engine gate and final activation-promotion tests are
  green
- if a concrete AgentControl harness exists, the child traversal smoke is ready
  to be captured as same-membrane corroboration; otherwise the proof must record
  `agentcontrol_hook_traversal_smoke.status == "not_captured"` with a reason and
  `raw_evidence.agentcontrol_hook_traversal_events == null`

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_doctor.py \
  activate-runtime /Users/jp/Projects/active/codex-tool-dev/docs/tickets \
  --marketplace-path /Users/jp/Projects/active/codex-tool-dev/.agents/plugins/marketplace.json
```

Expected:

- success writes `.codex/ticket-runtime-proof.json`
- proof scope is exactly `["direct_execute"]`
- proof records `hook_membrane_proof`
- proof records `agentcontrol_hook_traversal_smoke.status` as either
  `not_captured` with a reason or `captured` with validated same-hook bindings
- failure reports one of the explicit blocker codes or
  `runtime_readiness_failed`

If refresh has not happened or the host gates are still blocked, report
`source repaired, installed runtime not activated`.

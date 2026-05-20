# Ticket Runtime Readiness Activation V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement activation-capable Ticket runtime readiness for the documented live agent execute contract only: `ticket_engine_agent.py execute` under `request_origin="agent"` and `autonomy_mode: auto_audit`, and only on hosts that can actually run the pinned app-server policy.

**Architecture:** Split the work into three explicit layers. First, prove the host can run the required contained `workspaceWrite` app-server turn and that the host exposes a deterministic command-driving path; if either prerequisite fails, stop before repo implementation. Second, build Ticket-owned installed-runtime proof production around live app-server inventory plus a direct-execute-only hook-mediated smoke. Third, gate only the documented direct agent execute surface. This plan proves installed hook-mediated wiring and installed-runtime identity. It does not prove host-owned agent identity, consumer migration outside this repo, or future capture/update agent-wrapper flows.

**Tech Stack:** Python >=3.11, pytest, Codex CLI `app-server` JSON-RPC, project-local `.codex` proof artifacts, bytecode-safe `uv run` verification.

---

## Decision Freeze

### Trust Boundary

Activation V1 proves installed hook-mediated wiring, not host-owned agent
identity.

Current Codex hook input on this machine exposes hook-observed provenance such as
`session_id` and `hook_request_origin`, but it does not expose a trustworthy
host-owned "this was spawned by agent X" signal. Therefore:

- Treat `hook_request_origin` as observed metadata.
- Keep `ticket_engine_agent.py` as the policy-selecting entrypoint for
  `request_origin="agent"`.
- For the certified V1 direct-execute path, remove the current
  `hook_request_origin == request_origin` hard gate in the runner/core path so
  the installed host's observed `hook_request_origin="user"` metadata can reach
  the runtime-readiness gate.
- Do not claim that activation proves host-owned agent identity.
- State this boundary plainly in docs and error messaging.

### Scope Freeze

Activation V1 covers only the live documented agent contract in
`plugins/turbo-mode/ticket/README.md`:

- Certified execute surface: `ticket_engine_agent.py execute`
- Certified readiness surface name: `direct_execute`
- Certified policy shape: `request_origin="agent"` plus
  `autonomy_mode: auto_audit`

Out of scope for this plan:

- `ticket_capture_agent.py`
- `ticket_update_agent.py`
- wrapper prepare/execute same-thread fingerprint proof
- real consuming-project caller migration outside this repo
- AgentControl child traversal proof

If capture/update agent wrappers become real supported consumers later, capture
that as a separate follow-up ticket before widening the proof schema or engine
gate.

### Activation Preconditions

This plan is not executable until all of the following are true on the target
host:

1. A contained `workspaceWrite` app-server turn can execute the installed Ticket
   prerequisite probe command without failing early with
   `sandbox-exec: sandbox_apply: Operation not permitted`.
2. The host exposes a deterministic app-server command-driving path for exactly
   one existing contained Bash command and the resulting raw `commandExecution` and
   `hook/completed` evidence.
3. The installed Ticket hook output contract is accepted by app-server without
   the currently observed unsupported `permissionDecision` warning/failure path.

If any prerequisite is false, stop before source implementation. Do not treat
`dangerFullAccess`, prompt-only model turns, or AgentControl availability as an
activation fallback.

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

`<PROJECT_ROOT>/.codex/ticket-runtime-proof.json` is installed-runtime proof. It
is not:

- source proof
- cache-copy proof
- docs-readiness proof
- host-identity proof
- consumer-migration proof

The proof must fail closed if raw evidence is missing, stale, mismatched, or no
longer points at the live installed runtime.

### Proof Scope

Activation closeout must set:

```json
{
  "activation_scope": {
    "gated_execute_surfaces": ["direct_execute"],
    "certified_entrypoints": ["ticket_engine_agent.py"],
    "excluded_mutation_paths": [
      "ingest_dispatch",
      "activation_smoke_bootstrap",
      "ticket_capture.py",
      "ticket_update.py",
      "ticket_workflow.py"
    ],
    "request_origin": "agent",
    "autonomy_mode": "auto_audit",
    "hook_request_origin_contract": "metadata_only_currently_user"
  }
}
```

Anything broader is a different plan.

## Prerequisite Gates

Run these gates before repo edits beyond this plan file. If any gate fails, the
result is a blocker report, not partial activation work.

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

- A non-prompted JSON-RPC session to
  `codex app-server --listen stdio://` that writes
  `<PROJECT_ROOT>/.codex/ticket-runtime-smoke-preflight/app-server-driver-preflight.jsonl`
  using raw rows shaped exactly as
  `{"direction": "send"|"recv", "body": ...}`.
- That transcript must prove one contained turn for the already-installed
  prerequisite probe command:

```bash
python3 -B <INSTALLED_TICKET_ROOT>/scripts/ticket_engine_agent.py execute <PAYLOAD_PATH>
```

- Accepted pass transcript contents:
  - `send` rows for `initialize`, `initialized`, `thread/start`, and
    `turn/start`
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

- An existing helper or local spike can produce that exact preflight transcript
  non-interactively before implementation starts.

Fail condition:

- No existing helper or local spike can produce that exact transcript
  non-interactively, or the only available path is prompt-driven /
  AgentControl-mediated.

Failure handling:

- Stop with `deterministic_driver_unavailable`.
- A prompt/AgentControl harness may still be preserved as diagnostic-only
  evidence, but it must not authorize or block activation proof issuance.

### Gate C: Installed Hook Output Diagnostic

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

## Non-Goals

- Do not mutate `/Users/jp/.codex/plugins/cache`.
- Do not run guarded refresh, plugin install, personal-plugin sync, or
  marketplace edits.
- Do not broaden activation to `ticket_capture.py`, `ticket_update.py`, or
  `ticket_workflow.py`.
- Do not add `ticket_capture_agent.py` or `ticket_update_agent.py`.
- Do not add a public payload field or CLI flag that selects `execute_surface`.
- Do not use AgentControl child turns as proof input.
- Do not use prompt-driven app-server turns as blocking proof input.
- Do not use `dangerFullAccess` as activation fallback.
- Do not claim real consuming-project migration outside this repo.
- Do not claim host-owned agent identity.
- Do not gate ingest or read-only commands.

## Source Files To Read First

Before implementation, re-read these live files:

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
  "schema_version": "installed-ticket-runtime-readiness-v1",
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
  "hook_membrane_smoke": {
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
    "excluded_mutation_paths": [
      "ingest_dispatch",
      "activation_smoke_bootstrap",
      "ticket_capture.py",
      "ticket_update.py",
      "ticket_workflow.py"
    ],
    "request_origin": "agent",
    "autonomy_mode": "auto_audit",
    "hook_request_origin_contract": "metadata_only_currently_user"
  },
  "raw_evidence": {
    "run_dir": ".codex/ticket-runtime-smoke/<run_nonce>",
    "app_server_inventory_transcript": "raw/app-server-inventory-transcript.jsonl",
    "app_server_transcript": "raw/app-server-transcript.jsonl",
    "hook_membrane_events": "raw/hook-membrane-events.jsonl",
    "post_activation_events": "raw/post-activation-gated-events.jsonl",
    "payload_before": "raw/payload-before.json",
    "payload_after": "raw/payload-after.json",
    "engine_stdout": "raw/engine-stdout.json",
    "engine_stderr": "raw/engine-stderr.txt"
  }
}
```

Rules:

- `required_surfaces` must be exactly `["direct_execute"]` in V1.
- No `capture_execute` or `update_execute` fields may appear in a successful V1
  proof.
- The proof must bind installed root identity from live `hooks/list` plus
  corroborating `skills/list`, not from `plugin/read` alone.
- The proof must reject raw-evidence deletion, stale age, path drift, or
  executing-root mismatch.

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

Live CLI and schema preflight:

```bash
codex --version
codex app-server --help
```

Installed activation check, only after explicit installed refresh and only after
Gates A/B pass plus Task 2 source-local hook-contract repair/tests pass:

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
- If inventory cannot prove exactly one Ticket Bash `preToolUse` hook, stop.
- If the smoke cannot prove exactly one canonical `commandExecution` plus one
  same-turn installed `hook/completed`, stop.
- If the certified direct agent execute path still returns `origin_mismatch`
  before runtime-readiness verification, stop and fix the runner/core origin
  contract before continuing.
- If Task 2 cannot add source-local coverage proving
  `ticket_engine_activation_smoke.py execute` exists and is accepted by the
  source hook allowlist, stop before Task 3.
- If Task 2 cannot replace the current unsupported hook output contract with a
  source-local app-server-accepted contract and prove it in focused tests, stop
  before Task 3.
- If the smoke can mutate outside the contained smoke tickets directory, stop.
- If the activation bootstrap bypass can be selected by normal entrypoints,
  payload fields, or CLI flags, stop.
- If the proof does not bind installed executing root and current hashes, stop.
- If implementation pressure expands scope to capture/update wrappers, stop and
  split that into a separate follow-up ticket.
- If docs start claiming host-owned agent identity or real consumer migration,
  stop and rewrite the wording before merge.

## Commit Boundaries

- Commit 1: this plan only.
- Commit 2: direct-execute proof schema and verifier tests.
- Commit 3: inventory collector, hook contract preflight, and deterministic
  smoke runner.
- Commit 4: `ticket_doctor.py activate-runtime` and diagnostics wiring.
- Commit 5: direct-execute engine gate.
- Commit 6: docs, skill wording, and final verification.

---

### Task 0: Baseline And Prerequisite Gates

**Files:**

- Read: `docs/superpowers/plans/2026-05-20-ticket-runtime-readiness-activation.md`
- Read: `docs/tickets/2026-05-18-activation-capable-ticket-runtime-readiness.md`
- Read: `plugins/turbo-mode/ticket/README.md`

- [ ] **Step 1: Confirm branch and dirty state**

```bash
git status --short --branch
```

Expected: branch and dirty state recorded. Preserve unrelated dirty work.

- [ ] **Step 2: Hard-stop on stale base**

```bash
git rev-list --left-right --count origin/main...HEAD
```

Expected: `0 0`. If not, stop before implementation and reconcile the base.

- [ ] **Step 3: Validate Gate A**

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

- [ ] **Step 4: Validate Gate B**

Required outcome:

- one non-prompted preflight transcript at
  `<PROJECT_ROOT>/.codex/ticket-runtime-smoke-preflight/app-server-driver-preflight.jsonl`
  showing:
  - raw rows shaped as `{"direction": "send"|"recv", "body": ...}`
  - `initialize`, `initialized`, `thread/start`, and `turn/start`
  - exactly one canonical `commandExecution`
  - exactly one same-turn installed Ticket `hook/completed`
  - no approval-request methods

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

If no existing helper or local spike can produce that exact transcript
non-interactively, stop with `deterministic_driver_unavailable`.

- [ ] **Step 5: Capture Gate C diagnostic status**

Required outcome:

- either:
  - installed hook completion is already accepted by app-server without
    unsupported `permissionDecision` warnings
  - or the current installed failure is recorded as
    `hook_contract_needs_source_repair` for Task 2

If the installed hook still fails this diagnostic, record it and continue to
Task 2. Do not claim installed readiness from the diagnostic pass/fail state
alone.

- [ ] **Step 6: Create implementation branch after gates pass**

```bash
git switch -c fix/ticket-runtime-readiness-activation-v1
```

Expected: all remaining implementation happens on the fix branch.

---

### Task 1: Proof Schema And Base Verifier

**Files:**

- Add: `plugins/turbo-mode/ticket/scripts/ticket_runtime_readiness.py`
- Add: `plugins/turbo-mode/ticket/tests/test_runtime_readiness.py`

- [ ] **Step 1: Add failing verifier tests**

Test cases:

- missing proof file rejects agent direct execute
- source-checkout execution cannot satisfy installed-runtime proof
- proof with deleted raw evidence rejects
- proof with stale age rejects
- proof with `gated_execute_surfaces != ["direct_execute"]` rejects in V1
- proof naming `capture_execute` or `update_execute` rejects in V1

- [ ] **Step 2: Implement base proof schema and verifier**

Implementation requirements:

- expose `verify_activation_closeout_proof_for_execute()`
- bind proof target project root separately from contained smoke root
- derive executing plugin root from `Path(__file__).resolve().parents[1]`
- reject caller-supplied plugin-root or cache-root impersonation
- require `activation_scope.gated_execute_surfaces == ["direct_execute"]`

- [ ] **Step 3: Run focused tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest tests/test_runtime_readiness.py -q
```

Expected: PASS.

- [ ] **Step 4: Commit schema and verifier**

```bash
git add \
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
- do not use prompt text or AgentControl as proof input

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

### Task 3: Doctor Activation Command And Diagnostics

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
- successful activation writes `.codex/ticket-runtime-proof.json`
- `diagnose` stays read-only and never promotes proof

- [ ] **Step 2: Implement `activate-runtime`**

Implementation requirements:

- build candidate proof from live inventory plus bootstrap smoke
- run direct post-proof smoke only for `direct_execute`
- write final proof only after closeout verification passes
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

- [ ] **Step 4: Commit doctor activation**

```bash
git add \
  plugins/turbo-mode/ticket/scripts/ticket_doctor.py \
  plugins/turbo-mode/ticket/scripts/ticket_triage.py \
  plugins/turbo-mode/ticket/tests/test_doctor.py \
  plugins/turbo-mode/ticket/tests/test_runtime_readiness.py
git commit -m "feat(ticket): add runtime activation doctor command"
```

---

### Task 4: Origin Decoupling And Direct-Execute Engine Gate

**Files:**

- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_core.py`
- Modify: `plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_execute.py`
- Add: `plugins/turbo-mode/ticket/tests/test_engine_runner.py`
- Modify: `plugins/turbo-mode/ticket/tests/test_ingest.py`

- [ ] **Step 1: Add failing gate tests**

Test cases:

- `ticket_engine_agent.py execute` with hardcoded `request_origin="agent"` and
  hook-injected `hook_request_origin="user"` reaches the runtime-readiness gate
  instead of failing early with `origin_mismatch`
- `ticket_engine_agent.py execute` with `request_origin="agent"` and
  `autonomy_mode: auto_audit` fails with
  `runtime_readiness_required` when proof is absent
- same path succeeds when a valid activated proof is present and executing root
  matches
- ingest stays ungated
- no payload field can claim `direct_execute` certification on behalf of an
  uncertified path
- activation bootstrap bypass remains private to
  `ticket_engine_activation_smoke.py`
- non-certified flows must not infer `request_origin="agent"` from
  `hook_request_origin` or payload fields

- [ ] **Step 2: Implement the gate**

Implementation requirements:

- in `ticket_engine_runner.py`, keep hardcoded entrypoint `request_origin`
  authoritative when the caller supplies it; preserve `hook_request_origin` as
  separate metadata instead of failing early on the current host's
  `"user"` observation
- in `ticket_engine_core.py`, replace the blanket
  `hook_request_origin != request_origin` rejection with the V1 trust boundary:
  require hook traversal metadata to be present, but do not require equality for
  the certified direct agent execute path on the current host
- do not let workflow, capture, update, or payload fields elevate themselves to
  certified agent origin through hook metadata
- keep `direct_execute` internal to the certified entrypoint path
- do not add a public `execute_surface` payload field in V1
- pass internal proof-binding context from runner to core only for execute
- reject normal execution if proof is absent, stale, or mismatched
- leave user-origin mutation behavior unchanged

- [ ] **Step 3: Run focused tests**

```bash
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/codex-tool-dev-pycache \
  uv run --directory plugins/turbo-mode/ticket pytest \
  tests/test_execute.py \
  tests/test_engine_runner.py \
  tests/test_ingest.py \
  -q
```

Expected: PASS.

- [ ] **Step 4: Commit engine gate**

```bash
git add \
  plugins/turbo-mode/ticket/scripts/ticket_engine_core.py \
  plugins/turbo-mode/ticket/scripts/ticket_engine_runner.py \
  plugins/turbo-mode/ticket/tests/test_execute.py \
  plugins/turbo-mode/ticket/tests/test_engine_runner.py \
  plugins/turbo-mode/ticket/tests/test_ingest.py
git commit -m "feat(ticket): gate direct agent execute on runtime proof"
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
- docs say `dangerFullAccess`, prompt-driven smokes, and AgentControl are
  diagnostics only
- doctor skill documents blocker codes and direct-execute-only scope

- [ ] **Step 3: Update docs and UX**

Required wording:

- direct, explicit trust-boundary language
- no stale operator text that says hook `agent_id` presence determines
  `request_origin` for the current activation contract
- no claim of consumer migration outside this repo
- no claim of AgentControl or prompt-harness proof
- recovery guidance for `host_policy_blocked`,
  `deterministic_driver_unavailable`, `hook_contract_blocked`, and
  `runtime_readiness_required`

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

### Task 6: Final Verification And Optional Installed Activation

**Files:**

- Verify only; no planned source edits

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

- [ ] **Step 4: Optional installed activation check**

Run this only after:

- the source implementation is complete
- the installed cache has been refreshed explicitly
- Gates A/B are freshly green on this host
- Task 2 source-local hook-contract repair/tests are green

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -B \
  /Users/jp/.codex/plugins/cache/turbo-mode/ticket/1.4.0/scripts/ticket_doctor.py \
  activate-runtime /Users/jp/Projects/active/codex-tool-dev/docs/tickets \
  --marketplace-path /Users/jp/Projects/active/codex-tool-dev/.agents/plugins/marketplace.json
```

Expected:

- success writes `.codex/ticket-runtime-proof.json`
- proof scope is exactly `["direct_execute"]`
- failure reports one of the explicit blocker codes or
  `runtime_readiness_failed`

If refresh has not happened or the host gates are still blocked, report
`source repaired, installed runtime not activated`.
